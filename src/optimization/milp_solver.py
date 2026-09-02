from typing import Dict, Any, List, Tuple
from pyscipopt import Model, quicksum
from src.data_pipeline.models import Scenario, MaintenanceJob

class MaintenanceSchedulerMILP:
    def __init__(self, config: Dict[str, Any], horizon_hours: int = 24):
        self.config = config
        opt_cfg = config.get("optimization", {})
        self.big_m = opt_cfg.get("big_m", 100000.0)
        self.time_limit = opt_cfg.get("time_limit_seconds", 60)
        weights = opt_cfg.get("weights", {})
        self.w_tci = weights.get("tci_completion", 100.0)
        self.w_closure = weights.get("closure_time", 1.0)
        self.w_delay = weights.get("train_delay", 5.0)
        
        self.horizon = horizon_hours
        self.model = Model("Railway_Shadow_Block_Scheduling")
        self.model.setRealParam("limits/time", self.time_limit)
        
    def solve(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        """
        Builds and solves the MILP model for the given scenario.
        Discretizes time into 1-hour slots for shadow block consolidation.
        """
        # Variables
        # x[j, t] = 1 if job j starts at hour t
        x: Dict[Tuple[str, int], Any] = {}
        # is_sched[j] = 1 if job j is scheduled at all
        is_sched: Dict[str, Any] = {}
        # y[k, t] = 1 if block k is closed for maintenance at hour t
        y: Dict[Tuple[str, int], Any] = {}
        
        blocks = [b.id for b in scenario.blocks]
        jobs = scenario.jobs
        
        # 1. Initialize variables
        for k in blocks:
            for t in range(self.horizon):
                y[k, t] = self.model.addVar(vtype="B", name=f"y_{k}_{t}")
                
        for job in jobs:
            is_sched[job.id] = self.model.addVar(vtype="B", name=f"is_sched_{job.id}")
            for t in range(self.horizon):
                x[job.id, t] = self.model.addVar(vtype="B", name=f"x_{job.id}_{t}")
                
            # Job can start at most once
            self.model.addCons(quicksum(x[job.id, t] for t in range(self.horizon)) == is_sched[job.id])
            
            # Fixed jobs MUST be scheduled at their fixed time
            if job.is_fixed and job.fixed_start is not None:
                start_t = int(job.fixed_start)
                if 0 <= start_t < self.horizon:
                    self.model.addCons(x[job.id, start_t] == 1)
                    self.model.addCons(is_sched[job.id] == 1)
                else:
                    self.model.addCons(is_sched[job.id] == 0) # Out of horizon
                    
        # 2. Block Closure Constraints (Shadow Blocking)
        # If job j starts at t, it occupies [t, t + duration)
        for job in jobs:
            dur = int(job.duration)
            k = job.block_id
            for t in range(self.horizon):
                # For each hour the job is active, the block must be closed
                for t_active in range(t, min(self.horizon, t + dur)):
                    self.model.addCons(y[k, t_active] >= x[job.id, t])
                    
        # 3. Resource Constraints
        for r in scenario.resources:
            for t in range(self.horizon):
                # Sum of resources used by all active jobs at time t
                # A job is active at t if it started at some t' where t - dur < t' <= t
                resource_usage = []
                for job in jobs:
                    req = job.required_resources.get(r.id, 0)
                    if req > 0:
                        dur = int(job.duration)
                        for t_prime in range(max(0, t - dur + 1), t + 1):
                            resource_usage.append(req * x[job.id, t_prime])
                if resource_usage:
                    self.model.addCons(quicksum(resource_usage) <= r.capacity, name=f"res_{r.id}_{t}")

        # 4. Train Movement Constraints
        # Train delay variables
        train_delays: Dict[str, Any] = {}
        for train in scenario.trains:
            train_delays[train.id] = self.model.addVar(vtype="C", lb=0.0, name=f"delay_{train.id}")
            
            # Simplification for MVP: If a block is closed during train's scheduled time, 
            # it incurs delay. We penalize closure overlapping with scheduled train window.
            # Real routing would use continuous time dispatching, but this validates the core logic.
            train_start = int(train.scheduled_start)
            train_end = int(train.scheduled_end)
            
            overlap_closures = []
            for k in train.route:
                for t in range(train_start, min(self.horizon, train_end + 1)):
                    overlap_closures.append(y[k, t])
                    
            if overlap_closures:
                # Each hour of overlap adds to delay
                self.model.addCons(train_delays[train.id] >= quicksum(overlap_closures))

        # 5. Objective
        tci_term = quicksum(job_tcis.get(job.id, 0.0) * is_sched[job.id] for job in jobs)
        closure_term = quicksum(y[k, t] for k in blocks for t in range(self.horizon))
        delay_term = quicksum(train_delays[train.id] for train in scenario.trains)
        
        # Maximize TCI (so negative in min objective), Minimize closure (shadow blocks) & delays
        self.model.setObjective(
            self.w_closure * closure_term + self.w_delay * delay_term - self.w_tci * tci_term, 
            "minimize"
        )
        
        self.model.optimize()
        status = self.model.getStatus()
        
        if status not in ("optimal", "feasible"):
            return {"status": status, "error": "Model infeasible or unbounded."}
            
        # Extract schedule
        scheduled_jobs = []
        unscheduled_jobs = []
        
        for job in jobs:
            if self.model.getVal(is_sched[job.id]) > 0.5:
                # Find start time
                start_time = -1
                for t in range(self.horizon):
                    if self.model.getVal(x[job.id, t]) > 0.5:
                        start_time = t
                        break
                scheduled_jobs.append({
                    "job_id": job.id,
                    "block_id": job.block_id,
                    "start_time": start_time,
                    "end_time": start_time + job.duration,
                    "tci": job_tcis.get(job.id, 0.0)
                })
            else:
                unscheduled_jobs.append({
                    "job_id": job.id, 
                    "reason": "Lower priority or resource/capacity bottleneck."
                })
                
        # Total closure time calculation
        total_closure = sum(self.model.getVal(y[k, t]) for k in blocks for t in range(self.horizon))
        
        delays = {train.id: self.model.getVal(train_delays[train.id]) for train in scenario.trains}
        
        return {
            "status": status,
            "scheduled_jobs": scheduled_jobs,
            "unscheduled_jobs": unscheduled_jobs,
            "train_delays": delays,
            "total_closure_time": total_closure,
            "objective_value": self.model.getObjVal(),
            "kpi_metrics": {}
        }
