from typing import Dict, Any, List, Tuple
from src.data_pipeline.models import Scenario, MaintenanceJob
import warnings

try:
    from pyscipopt import Model, quicksum
    SCIP_AVAILABLE = True
except ImportError:
    SCIP_AVAILABLE = False
    warnings.warn("PySCIPOpt not found. Falling back to non-optimal heuristic solver for local execution.", ImportWarning)

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

    def solve(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        """
        Solves the block scheduling problem. Uses PySCIPOpt if available,
        otherwise uses a deterministic non-optimal heuristic fallback.
        """
        if SCIP_AVAILABLE:
            return self._solve_scip(scenario, job_tcis)
        else:
            return self._solve_heuristic(scenario, job_tcis)

    def _solve_scip(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        model = Model("Railway_Shadow_Block_Scheduling")
        model.setRealParam("limits/time", self.time_limit)
        
        # Variables
        x: Dict[Tuple[str, int], Any] = {}
        is_sched: Dict[str, Any] = {}
        y: Dict[Tuple[str, int], Any] = {}
        
        blocks = [b.id for b in scenario.blocks]
        jobs = scenario.jobs
        
        # 1. Initialize variables
        for k in blocks:
            for t in range(self.horizon):
                y[k, t] = model.addVar(vtype="B", name=f"y_{k}_{t}")
                
        for job in jobs:
            is_sched[job.id] = model.addVar(vtype="B", name=f"is_sched_{job.id}")
            for t in range(self.horizon):
                x[job.id, t] = model.addVar(vtype="B", name=f"x_{job.id}_{t}")
                
            model.addCons(quicksum(x[job.id, t] for t in range(self.horizon)) == is_sched[job.id])
            
            if job.is_fixed and job.fixed_start is not None:
                start_t = int(job.fixed_start)
                if 0 <= start_t < self.horizon:
                    model.addCons(x[job.id, start_t] == 1)
                    model.addCons(is_sched[job.id] == 1)
                else:
                    model.addCons(is_sched[job.id] == 0) 
                    
        # 2. Block Closure Constraints (Shadow Blocking)
        for job in jobs:
            dur = int(job.duration)
            k = job.block_id
            for t in range(self.horizon):
                for t_active in range(t, min(self.horizon, t + dur)):
                    model.addCons(y[k, t_active] >= x[job.id, t])
                    
        # 3. Resource Constraints
        for r in scenario.resources:
            for t in range(self.horizon):
                resource_usage = []
                for job in jobs:
                    req = job.required_resources.get(r.id, 0)
                    if req > 0:
                        dur = int(job.duration)
                        for t_prime in range(max(0, t - dur + 1), t + 1):
                            resource_usage.append(req * x[job.id, t_prime])
                if resource_usage:
                    model.addCons(quicksum(resource_usage) <= r.capacity, name=f"res_{r.id}_{t}")

        # 4. Train Movement Constraints
        train_delays: Dict[str, Any] = {}
        for train in scenario.trains:
            train_delays[train.id] = model.addVar(vtype="C", lb=0.0, name=f"delay_{train.id}")
            
            train_start = int(train.scheduled_start)
            train_end = int(train.scheduled_end)
            
            overlap_closures = []
            for k in train.route:
                for t in range(train_start, min(self.horizon, train_end + 1)):
                    overlap_closures.append(y[k, t])
                    
            if overlap_closures:
                model.addCons(train_delays[train.id] >= quicksum(overlap_closures))

        # 5. Objective
        tci_term = quicksum(job_tcis.get(job.id, 0.0) * is_sched[job.id] for job in jobs)
        closure_term = quicksum(y[k, t] for k in blocks for t in range(self.horizon))
        delay_term = quicksum(train_delays[train.id] for train in scenario.trains)
        
        model.setObjective(
            self.w_closure * closure_term + self.w_delay * delay_term - self.w_tci * tci_term, 
            "minimize"
        )
        
        model.optimize()
        status = model.getStatus()
        
        if status not in ("optimal", "feasible"):
            return {"status": status, "error": "Model infeasible or unbounded."}
            
        scheduled_jobs = []
        unscheduled_jobs = []
        
        for job in jobs:
            if model.getVal(is_sched[job.id]) > 0.5:
                start_time = -1
                for t in range(self.horizon):
                    if model.getVal(x[job.id, t]) > 0.5:
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
                
        total_closure = sum(model.getVal(y[k, t]) for k in blocks for t in range(self.horizon))
        delays = {train.id: model.getVal(train_delays[train.id]) for train in scenario.trains}
        
        return {
            "status": status,
            "scheduled_jobs": scheduled_jobs,
            "unscheduled_jobs": unscheduled_jobs,
            "train_delays": delays,
            "total_closure_time": total_closure,
            "objective_value": model.getObjVal(),
            "kpi_metrics": {}
        }
        
    def _solve_heuristic(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        """
        Deterministic, non-optimal fallback heuristic for local execution without SCIP.
        Uses a simple greedy approach: Sorts jobs by TCI and schedules them as early as possible 
        while trying to shadow-block where feasible.
        """
        print("[WARNING] Running non-optimal fallback heuristic since SCIP is missing.")
        
        # Sort jobs by fixed status (first), then TCI (descending)
        sorted_jobs = sorted(
            scenario.jobs, 
            key=lambda j: (j.is_fixed, job_tcis.get(j.id, 0.0)), 
            reverse=True
        )
        
        scheduled_jobs = []
        unscheduled_jobs = []
        block_closures: Dict[str, List[int]] = {b.id: [] for b in scenario.blocks}
        resource_usage: Dict[str, List[int]] = {r.id: [0]*self.horizon for r in scenario.resources}
        train_delays = {t.id: 0.0 for t in scenario.trains}
        
        for job in sorted_jobs:
            if job.is_fixed and job.fixed_start is not None:
                start_t = int(job.fixed_start)
                scheduled_jobs.append({
                    "job_id": job.id, "block_id": job.block_id,
                    "start_time": start_t, "end_time": start_t + job.duration,
                    "tci": job_tcis.get(job.id, 0.0)
                })
                for t in range(start_t, int(start_t + job.duration)):
                    if t not in block_closures[job.block_id]:
                        block_closures[job.block_id].append(t)
                continue
                
            # Try to schedule on an existing open shadow block if possible
            scheduled = False
            for t_candidate in range(self.horizon - int(job.duration) + 1):
                # Check resources
                res_ok = True
                for r_id, req in job.required_resources.items():
                    for t in range(t_candidate, t_candidate + int(job.duration)):
                        if resource_usage.get(r_id, [0]*self.horizon)[t] + req > \
                           next((r.capacity for r in scenario.resources if r.id == r_id), 0):
                            res_ok = False
                            break
                    if not res_ok:
                        break
                
                if res_ok:
                    # Found a slot!
                    scheduled_jobs.append({
                        "job_id": job.id, "block_id": job.block_id,
                        "start_time": t_candidate, "end_time": t_candidate + job.duration,
                        "tci": job_tcis.get(job.id, 0.0)
                    })
                    # Consume resources and close blocks
                    for t in range(t_candidate, t_candidate + int(job.duration)):
                        if t not in block_closures[job.block_id]:
                            block_closures[job.block_id].append(t)
                        for r_id, req in job.required_resources.items():
                            resource_usage[r_id][t] += req
                    scheduled = True
                    break
                    
            if not scheduled:
                unscheduled_jobs.append({"job_id": job.id, "reason": "Heuristic bottleneck"})
                
        # Calculate train delays based on closures
        for train in scenario.trains:
            for k in train.route:
                for t in range(int(train.scheduled_start), int(train.scheduled_end) + 1):
                    if t in block_closures.get(k, []):
                        train_delays[train.id] += 1.0
                        
        total_closure_time = sum(len(closures) for closures in block_closures.values())
        
        return {
            "status": "heuristic_feasible",
            "scheduled_jobs": scheduled_jobs,
            "unscheduled_jobs": unscheduled_jobs,
            "train_delays": train_delays,
            "total_closure_time": total_closure_time,
            "objective_value": 0.0, # Not true optimal obj
            "kpi_metrics": {}
        }
