from typing import Dict, Any, List, Tuple
from src.data_pipeline.models import Scenario, MaintenanceJob, Department, ScheduledJob, UnscheduledJobReason
import warnings
import time

try:
    from pyscipopt import Model, quicksum
    SCIP_AVAILABLE = True
except ImportError:
    SCIP_AVAILABLE = False
    warnings.warn("PySCIPOpt not found. Falling back to non-optimal heuristic solver for local execution.", ImportWarning)

class MaintenanceSchedulerMILP:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        opt_cfg = config.get("optimization", {})
        self.big_m = opt_cfg.get("big_m", 100000.0)
        self.time_limit = opt_cfg.get("time_limit_seconds", 60)
        weights = opt_cfg.get("weights", {})
        self.w_tci = weights.get("tci_completion", 100.0)
        self.w_closure = weights.get("closure_time", 1.0)
        self.w_delay = weights.get("train_delay", 5.0)
        self.horizon = opt_cfg.get("horizon_hours", 24)

    def _are_departments_incompatible(self, d1: Department, d2: Department) -> bool:
        """Rule: OHE (Traction) and S&T (Signaling) cannot work simultaneously on the same block."""
        if (d1 == Department.OHE and d2 == Department.S_AND_T) or \
           (d2 == Department.OHE and d1 == Department.S_AND_T):
            return True
        return False

    def solve(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        start_time = time.time()
        if SCIP_AVAILABLE:
            result = self._solve_scip(scenario, job_tcis)
        else:
            result = self._solve_heuristic(scenario, job_tcis)
        result["runtime_seconds"] = time.time() - start_time
        return result

    def _solve_scip(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        model = Model("Railway_Shadow_Block_Scheduling")
        model.setRealParam("limits/time", self.time_limit)
        
        # Variables
        x: Dict[Tuple[str, int], Any] = {}
        is_sched: Dict[str, Any] = {}
        y: Dict[Tuple[str, int], Any] = {}
        
        blocks = [b.id for b in scenario.blocks]
        jobs = scenario.jobs
        
        # 1. Initialize block closure variables
        for k in blocks:
            for t in range(self.horizon):
                y[k, t] = model.addVar(vtype="B", name=f"y_{k}_{t}")
                
        # Handle explicitly given fixed maintenance blocks (e.g., from external sources)
        for fb in scenario.fixed_blocks:
            k = fb.block_id
            for t in range(int(fb.start_time), int(fb.end_time)):
                if 0 <= t < self.horizon:
                    model.addCons(y[k, t] == 1, name=f"fb_{fb.id}_{t}")

        # Initialize Job variables
        for job in jobs:
            is_sched[job.id] = model.addVar(vtype="B", name=f"is_sched_{job.id}")
            for t in range(self.horizon):
                x[job.id, t] = model.addVar(vtype="B", name=f"x_{job.id}_{t}")
                
            model.addCons(quicksum(x[job.id, t] for t in range(self.horizon)) == is_sched[job.id])
            
            # Frozen / Fixed Jobs (Week 1 freeze)
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

        # Incompatible Departments constraint
        for k in blocks:
            for t in range(self.horizon):
                # OHE and S&T cannot be active at the same time `t` on block `k`
                # A job is active at t if it started at t' where t - dur < t' <= t
                ohe_active = []
                st_active = []
                for job in jobs:
                    if job.block_id == k:
                        dur = int(job.duration)
                        active_vars = [x[job.id, t_prime] for t_prime in range(max(0, t - dur + 1), t + 1)]
                        if job.department == Department.OHE:
                            ohe_active.extend(active_vars)
                        elif job.department == Department.S_AND_T:
                            st_active.extend(active_vars)
                
                # At most one type can be active
                if ohe_active and st_active:
                    # If sum(OHE) >= 1, then sum(ST) must be 0
                    model.addCons(quicksum(ohe_active) + quicksum(st_active) <= 1, name=f"incompat_{k}_{t}")

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

        # 4. Train Movement Constraints & Delay Calculation
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
                
                # Premium train delay hard limit (e.g., max 1 hour delay allowed)
                if train.category.lower() == "premium":
                    model.addCons(train_delays[train.id] <= 1.0, name=f"premium_delay_{train.id}")

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
                scheduled_jobs.append(ScheduledJob(
                    job_id=job.id, block_id=job.block_id,
                    start_time=start_time, end_time=start_time + job.duration,
                    tci=job_tcis.get(job.id, 0.0), department=job.department
                ).model_dump())
            else:
                unscheduled_jobs.append(UnscheduledJobReason(
                    job_id=job.id, reason="Lower priority or resource/capacity bottleneck."
                ).model_dump())
                
        total_closure = sum(model.getVal(y[k, t]) for k in blocks for t in range(self.horizon))
        delays = {train.id: model.getVal(train_delays[train.id]) for train in scenario.trains}
        
        return {
            "status": status,
            "solver": "PySCIPOpt",
            "scheduled_jobs": scheduled_jobs,
            "unscheduled_jobs": unscheduled_jobs,
            "train_delays": delays,
            "total_closure_time": total_closure,
            "objective_value": model.getObjVal()
        }
        
    def _solve_heuristic(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        """
        NON_OPTIMAL_FALLBACK: Deterministic, greedy fallback heuristic for local execution without SCIP.
        """
        print("[WARNING] Running NON_OPTIMAL_FALLBACK heuristic since SCIP is missing.")
        
        sorted_jobs = sorted(
            scenario.jobs, 
            key=lambda j: (j.is_fixed, job_tcis.get(j.id, 0.0)), 
            reverse=True
        )
        
        scheduled_jobs = []
        unscheduled_jobs = []
        block_closures: Dict[str, List[int]] = {b.id: [] for b in scenario.blocks}
        
        # Apply Fixed Blocks
        for fb in scenario.fixed_blocks:
            for t in range(int(fb.start_time), int(fb.end_time)):
                if t not in block_closures[fb.block_id]:
                    block_closures[fb.block_id].append(t)
                    
        resource_usage: Dict[str, List[int]] = {r.id: [0]*self.horizon for r in scenario.resources}
        train_delays = {t.id: 0.0 for t in scenario.trains}
        
        # Track active departments per block per hour
        dept_active: Dict[str, Dict[int, List[Department]]] = {b.id: {t: [] for t in range(self.horizon)} for b in scenario.blocks}
        
        for job in sorted_jobs:
            if job.is_fixed and job.fixed_start is not None:
                start_t = int(job.fixed_start)
                if start_t < 0 or start_t >= self.horizon:
                    unscheduled_jobs.append(UnscheduledJobReason(job_id=job.id, reason="Fixed out of horizon").model_dump())
                    continue
                scheduled_jobs.append(ScheduledJob(
                    job_id=job.id, block_id=job.block_id,
                    start_time=start_t, end_time=start_t + job.duration,
                    tci=job_tcis.get(job.id, 0.0), department=job.department
                ).model_dump())
                for t in range(start_t, int(start_t + job.duration)):
                    if t not in block_closures[job.block_id]:
                        block_closures[job.block_id].append(t)
                    dept_active[job.block_id][t].append(job.department)
                continue
                
            scheduled = False
            for t_candidate in range(self.horizon - int(job.duration) + 1):
                res_ok = True
                incompat = False
                
                # Check department compatibility
                for t in range(t_candidate, t_candidate + int(job.duration)):
                    active_depts = dept_active[job.block_id][t]
                    for d in active_depts:
                        if self._are_departments_incompatible(job.department, d):
                            incompat = True
                            break
                    if incompat: break
                if incompat: continue
                
                # Check premium train delays
                hypothetical_delays = 0
                for train in scenario.trains:
                    if train.category.lower() == "premium" and job.block_id in train.route:
                        if int(train.scheduled_start) <= t_candidate <= int(train.scheduled_end):
                            hypothetical_delays += 1
                if hypothetical_delays > 1.0: # Hard limit
                    continue

                for r_id, req in job.required_resources.items():
                    for t in range(t_candidate, t_candidate + int(job.duration)):
                        if resource_usage.get(r_id, [0]*self.horizon)[t] + req > \
                           next((r.capacity for r in scenario.resources if r.id == r_id), 0):
                            res_ok = False
                            break
                    if not res_ok: break
                
                if res_ok:
                    scheduled_jobs.append(ScheduledJob(
                        job_id=job.id, block_id=job.block_id,
                        start_time=t_candidate, end_time=t_candidate + job.duration,
                        tci=job_tcis.get(job.id, 0.0), department=job.department
                    ).model_dump())
                    
                    for t in range(t_candidate, t_candidate + int(job.duration)):
                        if t not in block_closures[job.block_id]:
                            block_closures[job.block_id].append(t)
                        dept_active[job.block_id][t].append(job.department)
                        for r_id, req in job.required_resources.items():
                            resource_usage[r_id][t] += req
                    scheduled = True
                    break
                    
            if not scheduled:
                unscheduled_jobs.append(UnscheduledJobReason(job_id=job.id, reason="Heuristic bottleneck").model_dump())
                
        for train in scenario.trains:
            for k in train.route:
                for t in range(int(train.scheduled_start), int(train.scheduled_end) + 1):
                    if t in block_closures.get(k, []):
                        train_delays[train.id] += 1.0
                        
        total_closure_time = sum(len(closures) for closures in block_closures.values())
        
        return {
            "status": "heuristic_feasible",
            "solver": "NON_OPTIMAL_FALLBACK",
            "scheduled_jobs": scheduled_jobs,
            "unscheduled_jobs": unscheduled_jobs,
            "train_delays": train_delays,
            "total_closure_time": total_closure_time,
            "objective_value": 0.0
        }
