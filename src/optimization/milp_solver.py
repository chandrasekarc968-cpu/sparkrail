from typing import Dict, Any, List, Tuple, Optional
import warnings
import time

from src.data_pipeline.models import (
    Scenario,
    MaintenanceJob,
    Department,
    ScheduledJob,
    UnscheduledJobReason,
    OptimizedSchedule
)

try:
    from pyscipopt import Model, quicksum
    SCIP_AVAILABLE = True
except ImportError:
    SCIP_AVAILABLE = False
    warnings.warn(
        "PySCIPOpt not found. Falling back to non-optimal heuristic solver for local execution.",
        ImportWarning
    )

class MaintenanceSchedulerMILP:
    """
    Mixed-Integer Linear Programming (MILP) scheduler for railway track possessions.
    Formulated using PySCIPOpt with a deterministic fallback heuristic.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        opt_cfg = self.config.get("optimization", {})
        self.time_limit = float(opt_cfg.get("time_limit_seconds", 60))
        weights = opt_cfg.get("weights", {})
        self.w_tci = float(weights.get("tci_completion", 100.0))
        self.w_closure = float(weights.get("closure_time", 1.0))
        self.w_delay = float(weights.get("train_delay", 5.0))
        self.w_startup = float(weights.get("separate_closure_penalty", 2.0))
        self.w_shadow = float(weights.get("shadow_consolidation_reward", 10.0))
        self.horizon = int(opt_cfg.get("horizon_hours", 24))

    @staticmethod
    def are_departments_incompatible(d1: Department, d2: Department) -> bool:
        """
        Rule: OHE (Traction Power Isolation) and S&T (Signaling & Telecom) cannot 
        operate concurrently on the same track section.
        """
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
        result["runtime_seconds"] = round(time.time() - start_time, 4)
        return result

    def _solve_scip(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        model = Model("SparkRail_Shadow_Block_MILP")
        model.setRealParam("limits/time", self.time_limit)
        model.hideOutput(True)

        blocks = [b.id for b in scenario.blocks]
        jobs = scenario.jobs
        trains = scenario.trains
        resources = scenario.resources
        fixed_blocks = scenario.fixed_blocks

        # 1. Decision Variables
        # x[j, t]: binary, job j starts at hour t
        x: Dict[Tuple[str, int], Any] = {}
        # u[j]: binary, job j is selected for scheduling in this horizon
        u: Dict[str, Any] = {}
        # y[k, t]: binary, block k is closed at hour t
        y: Dict[Tuple[str, int], Any] = {}
        # v[k, t]: binary, a separate closure window starts at hour t on block k
        v: Dict[Tuple[str, int], Any] = {}
        # shadow[k, t]: binary, shadow block consolidation active on block k at hour t
        shadow: Dict[Tuple[str, int], Any] = {}

        for k in blocks:
            for t in range(self.horizon):
                y[k, t] = model.addVar(vtype="B", name=f"y_{k}_{t}")
                v[k, t] = model.addVar(vtype="B", name=f"v_{k}_{t}")
                shadow[k, t] = model.addVar(vtype="B", name=f"shadow_{k}_{t}")

        for job in jobs:
            u[job.id] = model.addVar(vtype="B", name=f"u_{job.id}")
            dur = int(job.duration)
            for t in range(self.horizon):
                if t <= self.horizon - dur:
                    x[job.id, t] = model.addVar(vtype="B", name=f"x_{job.id}_{t}")

        # 2. Constraints

        # a) Job selection linking
        for job in jobs:
            dur = int(job.duration)
            valid_starts = [x[job.id, t] for t in range(self.horizon - dur + 1)]
            model.addCons(quicksum(valid_starts) == u[job.id], name=f"job_select_{job.id}")

            # Fixed / Frozen jobs (e.g. Week 1 freeze)
            if job.is_fixed and job.fixed_start is not None:
                start_t = int(job.fixed_start)
                if 0 <= start_t <= self.horizon - dur:
                    model.addCons(x[job.id, start_t] == 1, name=f"fixed_start_{job.id}")
                    model.addCons(u[job.id] == 1, name=f"fixed_sched_{job.id}")
                else:
                    model.addCons(u[job.id] == 0, name=f"fixed_out_bounds_{job.id}")

        # b) Fixed external maintenance blocks
        for fb in fixed_blocks:
            k = fb.block_id
            start = max(0, int(fb.start_time))
            end = min(self.horizon, int(fb.end_time))
            for t in range(start, end):
                model.addCons(y[k, t] == 1, name=f"fb_{fb.id}_{t}")

        # c) Block closure linking: any active job forces y[k, t] = 1
        for job in jobs:
            k = job.block_id
            dur = int(job.duration)
            for t_start in range(self.horizon - dur + 1):
                for t_active in range(t_start, t_start + dur):
                    model.addCons(y[k, t_active] >= x[job.id, t_start], name=f"closure_{job.id}_{t_start}_{t_active}")

        # d) Separate closure setup penalty: v[k, t] >= y[k, t] - y[k, t-1]
        for k in blocks:
            model.addCons(v[k, 0] >= y[k, 0], name=f"startup_{k}_0")
            for t in range(1, self.horizon):
                model.addCons(v[k, t] >= y[k, t] - y[k, t - 1], name=f"startup_{k}_{t}")

        # e) Incompatible departments (OHE vs S&T) on the same block at hour t
        for k in blocks:
            for t in range(self.horizon):
                ohe_active = []
                st_active = []
                all_active = []
                for job in jobs:
                    if job.block_id == k:
                        dur = int(job.duration)
                        active_vars = [
                            x[job.id, t_start]
                            for t_start in range(max(0, t - dur + 1), min(t + 1, self.horizon - dur + 1))
                            if (job.id, t_start) in x
                        ]
                        if active_vars:
                            all_active.extend(active_vars)
                            if job.department == Department.OHE:
                                ohe_active.extend(active_vars)
                            elif job.department == Department.S_AND_T:
                                st_active.extend(active_vars)

                if ohe_active and st_active:
                    model.addCons(
                        quicksum(ohe_active) + quicksum(st_active) <= 1,
                        name=f"incompat_ohe_st_{k}_{t}"
                    )

                # f) Shadow block consolidation reward constraint:
                # shadow[k, t] can be 1 only if at least 2 jobs are active simultaneously on block k at hour t
                if len(all_active) >= 2:
                    model.addCons(2 * shadow[k, t] <= quicksum(all_active), name=f"shadow_req_{k}_{t}")
                else:
                    model.addCons(shadow[k, t] == 0, name=f"no_shadow_{k}_{t}")

        # g) Resource Capacity constraints
        for r in resources:
            for t in range(self.horizon):
                res_usage = []
                for job in jobs:
                    req = job.required_resources.get(r.id, 0)
                    if req > 0:
                        dur = int(job.duration)
                        for t_start in range(max(0, t - dur + 1), min(t + 1, self.horizon - dur + 1)):
                            if (job.id, t_start) in x:
                                res_usage.append(req * x[job.id, t_start])
                if res_usage:
                    model.addCons(quicksum(res_usage) <= r.capacity, name=f"cap_{r.id}_{t}")

        # h) Train movement conflicts and delay calculations
        train_delays: Dict[str, Any] = {}
        for train in trains:
            train_delays[train.id] = model.addVar(vtype="C", lb=0.0, name=f"delay_{train.id}")
            t_start = max(0, int(train.scheduled_start))
            t_end = min(self.horizon, int(train.scheduled_end))
            
            overlap_closures = [
                y[k, t]
                for k in train.route
                if k in blocks
                for t in range(t_start, t_end)
            ]
            if overlap_closures:
                model.addCons(train_delays[train.id] >= quicksum(overlap_closures), name=f"train_delay_{train.id}")
            else:
                model.addCons(train_delays[train.id] == 0.0, name=f"zero_delay_{train.id}")

            # Premium train strict delay upper bound (max 1.0 hr delay permitted)
            if train.category.lower() == "premium":
                model.addCons(train_delays[train.id] <= 1.0, name=f"premium_limit_{train.id}")

        # 3. Objective Function Formulation
        tci_term = quicksum(job_tcis.get(job.id, 0.0) * u[job.id] for job in jobs)
        closure_term = quicksum(y[k, t] for k in blocks for t in range(self.horizon))
        startup_term = quicksum(v[k, t] for k in blocks for t in range(self.horizon))
        shadow_term = quicksum(shadow[k, t] for k in blocks for t in range(self.horizon))
        
        # Weighted delay term with premium train multiplier
        delay_terms = []
        for train in trains:
            mult = 3.0 if train.category.lower() == "premium" else 1.0
            delay_terms.append(mult * train_delays[train.id])
        weighted_delay_term = quicksum(delay_terms)

        objective = (
            self.w_closure * closure_term +
            self.w_startup * startup_term +
            self.w_delay * weighted_delay_term -
            self.w_tci * tci_term -
            self.w_shadow * shadow_term
        )
        model.setObjective(objective, "minimize")

        # 4. Optimize
        model.optimize()
        status = model.getStatus()

        if status not in ("optimal", "feasible"):
            # Return diagnostic info without crashing
            diagnostics = self._diagnose_infeasibility(scenario, job_tcis)
            return {
                "status": status,
                "solver": "PySCIPOpt",
                "scheduled_jobs": [],
                "unscheduled_jobs": [
                    UnscheduledJobReason(job_id=j.id, reason="Infeasible model constraint").model_dump()
                    for j in jobs
                ],
                "train_delays": {t.id: 0.0 for t in trains},
                "total_closure_time": 0.0,
                "objective_value": 0.0,
                "diagnostics": diagnostics
            }

        # 5. Extract Scheduled and Unscheduled Jobs
        scheduled_jobs: List[Dict[str, Any]] = []
        scheduled_ids = set()
        block_time_jobs: Dict[Tuple[str, int], List[str]] = {}

        for job in jobs:
            dur = int(job.duration)
            if model.getVal(u[job.id]) > 0.5:
                start_time = -1
                for t in range(self.horizon - dur + 1):
                    if (job.id, t) in x and model.getVal(x[job.id, t]) > 0.5:
                        start_time = t
                        break
                if start_time >= 0:
                    scheduled_ids.add(job.id)
                    assigned_res = [r.name for r in resources if job.required_resources.get(r.id, 0) > 0]
                    sched_obj = ScheduledJob(
                        job_id=job.id,
                        block_id=job.block_id,
                        start_time=float(start_time),
                        end_time=float(start_time + job.duration),
                        tci=float(job_tcis.get(job.id, 0.0)),
                        department=job.department,
                        assigned_resources=assigned_res
                    )
                    scheduled_jobs.append(sched_obj.model_dump())
                    for t in range(start_time, int(start_time + job.duration)):
                        block_time_jobs.setdefault((job.block_id, t), []).append(job.id)

        # Mark Shadow Blocks & Shadow Partners
        for s_job in scheduled_jobs:
            k = s_job["block_id"]
            start = int(s_job["start_time"])
            end = int(s_job["end_time"])
            partners = set()
            for t in range(start, end):
                for other_id in block_time_jobs.get((k, t), []):
                    if other_id != s_job["job_id"]:
                        partners.add(other_id)
            if partners:
                s_job["is_shadow_block"] = True
                s_job["shadow_with_jobs"] = sorted(list(partners))

        # Determine exact unscheduled reasons for rejected jobs
        unscheduled_jobs = self._derive_unscheduled_reasons(
            scenario, scheduled_ids, job_tcis, scheduled_jobs
        )

        total_closure = float(sum(model.getVal(y[k, t]) for k in blocks for t in range(self.horizon)))
        delays = {train.id: round(float(model.getVal(train_delays[train.id])), 2) for train in trains}

        obj_components = {
            "tci_term": round(float(sum(job_tcis.get(j.id, 0.0) * model.getVal(u[j.id]) for j in jobs)), 2),
            "closure_hours": round(total_closure, 2),
            "startup_penalties": round(float(sum(model.getVal(v[k, t]) for k in blocks for t in range(self.horizon))), 2),
            "shadow_rewards": round(float(sum(model.getVal(shadow[k, t]) for k in blocks for t in range(self.horizon))), 2),
            "train_delay_hours": round(float(sum(delays.values())), 2)
        }

        return {
            "status": status,
            "solver": "PySCIPOpt",
            "scheduled_jobs": scheduled_jobs,
            "unscheduled_jobs": unscheduled_jobs,
            "train_delays": delays,
            "total_closure_time": total_closure,
            "objective_value": round(float(model.getObjVal()), 2),
            "objective_components": obj_components
        }

    def _diagnose_infeasibility(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        """Provides human-readable diagnostics when MILP problem cannot be solved."""
        issues = []
        for j in scenario.jobs:
            if j.is_fixed and j.fixed_start is not None:
                dur = int(j.duration)
                if j.fixed_start < 0 or j.fixed_start + dur > self.horizon:
                    issues.append(f"Job {j.id} fixed outside horizon [0, {self.horizon}].")

        for t in scenario.trains:
            if t.category.lower() == "premium":
                for fb in scenario.fixed_blocks:
                    if fb.block_id in t.route:
                        overlap = min(fb.end_time, t.scheduled_end) - max(fb.start_time, t.scheduled_start)
                        if overlap > 1.0:
                            issues.append(
                                f"Fixed Block {fb.id} forces >1.0h delay on Premium Train {t.id}."
                            )
        return {"infeasibility_diagnostics": issues or ["Tight resource, train, or department constraints."]}

    def _derive_unscheduled_reasons(
        self,
        scenario: Scenario,
        scheduled_ids: set,
        job_tcis: Dict[str, float],
        scheduled_jobs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Determines exact, domain-specific reasons for unscheduled jobs."""
        unscheduled = []
        for job in scenario.jobs:
            if job.id in scheduled_ids:
                continue

            dur = int(job.duration)
            if dur > self.horizon:
                reason = f"Job duration ({dur}h) exceeds horizon ({self.horizon}h)."
                conflict = "Horizon Bound"
            elif job.is_fixed and (job.fixed_start is None or job.fixed_start + dur > self.horizon):
                reason = "Fixed schedule time outside planning window."
                conflict = "Frozen Schedule"
            else:
                # Check department conflicts on target block
                dept_conflict = False
                res_conflict = False
                for s in scheduled_jobs:
                    if s["block_id"] == job.block_id:
                        if self.are_departments_incompatible(job.department, Department(s["department"])):
                            dept_conflict = True
                            conflict = f"Incompatible with {s['department']} (Job {s['job_id']})"
                            reason = f"OHE/S&T safety isolation conflict with {s['job_id']} on section {job.block_id}."
                            break

                if not dept_conflict:
                    # Check resource limitation
                    for r_id, req in job.required_resources.items():
                        res_obj = next((r for r in scenario.resources if r.id == r_id), None)
                        if res_obj and req > res_obj.capacity:
                            res_conflict = True
                            conflict = f"Resource {res_obj.name}"
                            reason = f"Required resource {res_obj.name} exceeds available capacity ({res_obj.capacity})."
                            break

                if not dept_conflict and not res_conflict:
                    conflict = "Priority Tradeoff"
                    reason = f"Traffic corridor bottleneck; displaced by higher TCI priority tasks."

            unscheduled.append(
                UnscheduledJobReason(
                    job_id=job.id,
                    reason=reason,
                    conflict_with=conflict,
                    potential_window="Next Rolling Horizon (Week 2)"
                ).model_dump()
            )
        return unscheduled

    def _solve_heuristic(self, scenario: Scenario, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        """
        NON_OPTIMAL_FALLBACK: Deterministic, greedy fallback heuristic for environments where SCIP is unavailable.
        Explicitly labeled NON_OPTIMAL_FALLBACK; never claims optimality.
        """
        sorted_jobs = sorted(
            scenario.jobs,
            key=lambda j: (j.is_fixed, job_tcis.get(j.id, 0.0)),
            reverse=True
        )

        scheduled_jobs: List[Dict[str, Any]] = []
        unscheduled_jobs: List[Dict[str, Any]] = []
        block_closures: Dict[str, set] = {b.id: set() for b in scenario.blocks}
        dept_active: Dict[str, Dict[int, List[Department]]] = {
            b.id: {t: [] for t in range(self.horizon)} for b in scenario.blocks
        }
        resource_usage: Dict[str, List[int]] = {r.id: [0] * self.horizon for r in scenario.resources}

        # Apply Fixed Blocks
        for fb in scenario.fixed_blocks:
            k = fb.block_id
            for t in range(int(fb.start_time), int(fb.end_time)):
                if 0 <= t < self.horizon:
                    block_closures[k].add(t)

        scheduled_ids = set()

        for job in sorted_jobs:
            dur = int(job.duration)
            k = job.block_id

            if job.is_fixed and job.fixed_start is not None:
                start_t = int(job.fixed_start)
                if start_t < 0 or start_t + dur > self.horizon:
                    unscheduled_jobs.append(
                        UnscheduledJobReason(
                            job_id=job.id,
                            reason="Fixed start time outside horizon.",
                            conflict_with="Horizon Bound"
                        ).model_dump()
                    )
                    continue

                scheduled_ids.add(job.id)
                assigned_res = [r.name for r in scenario.resources if job.required_resources.get(r.id, 0) > 0]
                scheduled_jobs.append(ScheduledJob(
                    job_id=job.id,
                    block_id=k,
                    start_time=float(start_t),
                    end_time=float(start_t + dur),
                    tci=float(job_tcis.get(job.id, 0.0)),
                    department=job.department,
                    assigned_resources=assigned_res
                ).model_dump())

                for t in range(start_t, start_t + dur):
                    block_closures[k].add(t)
                    dept_active[k][t].append(job.department)
                    for r_id, req in job.required_resources.items():
                        if r_id in resource_usage:
                            resource_usage[r_id][t] += req
                continue

            # Find best candidate slot
            best_t = None
            for t_cand in range(self.horizon - dur + 1):
                # 1. Department compatibility
                incompat = False
                for t in range(t_cand, t_cand + dur):
                    for d in dept_active[k][t]:
                        if self.are_departments_incompatible(job.department, d):
                            incompat = True
                            break
                    if incompat:
                        break
                if incompat:
                    continue

                # 2. Premium train delay limit check (max 1.0 hr)
                hypothetical_delays = 0.0
                for tr in scenario.trains:
                    if tr.category.lower() == "premium" and k in tr.route:
                        tr_s = int(tr.scheduled_start)
                        tr_e = int(tr.scheduled_end)
                        for t in range(max(t_cand, tr_s), min(t_cand + dur, tr_e)):
                            hypothetical_delays += 1.0
                if hypothetical_delays > 1.0:
                    continue

                # 3. Resource capacity check
                res_ok = True
                for r_id, req in job.required_resources.items():
                    res_cap = next((r.capacity for r in scenario.resources if r.id == r_id), 0)
                    for t in range(t_cand, t_cand + dur):
                        if resource_usage[r_id][t] + req > res_cap:
                            res_ok = False
                            break
                    if not res_ok:
                        break
                if not res_ok:
                    continue

                best_t = t_cand
                break

            if best_t is not None:
                scheduled_ids.add(job.id)
                assigned_res = [r.name for r in scenario.resources if job.required_resources.get(r.id, 0) > 0]
                scheduled_jobs.append(ScheduledJob(
                    job_id=job.id,
                    block_id=k,
                    start_time=float(best_t),
                    end_time=float(best_t + dur),
                    tci=float(job_tcis.get(job.id, 0.0)),
                    department=job.department,
                    assigned_resources=assigned_res
                ).model_dump())

                for t in range(best_t, best_t + dur):
                    block_closures[k].add(t)
                    dept_active[k][t].append(job.department)
                    for r_id, req in job.required_resources.items():
                        if r_id in resource_usage:
                            resource_usage[r_id][t] += req
            else:
                unscheduled_jobs.append(
                    UnscheduledJobReason(
                        job_id=job.id,
                        reason=f"Capacity or premium train conflict on section {job.block_id}.",
                        conflict_with="Corridor Capacity",
                        potential_window="Week 2"
                    ).model_dump()
                )

        # Mark shadow blocks
        for s_job in scheduled_jobs:
            k = s_job["block_id"]
            start = int(s_job["start_time"])
            end = int(s_job["end_time"])
            partners = set()
            for other in scheduled_jobs:
                if other["job_id"] != s_job["job_id"] and other["block_id"] == k:
                    o_s = int(other["start_time"])
                    o_e = int(other["end_time"])
                    if max(start, o_s) < min(end, o_e):
                        partners.add(other["job_id"])
            if partners:
                s_job["is_shadow_block"] = True
                s_job["shadow_with_jobs"] = sorted(list(partners))

        # Calculate delays
        train_delays = {t.id: 0.0 for t in scenario.trains}
        for tr in scenario.trains:
            for k in tr.route:
                for t in range(int(tr.scheduled_start), int(tr.scheduled_end)):
                    if t in block_closures.get(k, set()):
                        train_delays[tr.id] += 1.0

        total_closure_time = float(sum(len(c) for c in block_closures.values()))

        return {
            "status": "heuristic_feasible",
            "solver": "NON_OPTIMAL_FALLBACK",
            "scheduled_jobs": scheduled_jobs,
            "unscheduled_jobs": unscheduled_jobs,
            "train_delays": train_delays,
            "total_closure_time": total_closure_time,
            "objective_value": 0.0,
            "objective_components": {
                "tci_term": round(sum(job_tcis.get(j_id, 0.0) for j_id in scheduled_ids), 2),
                "closure_hours": total_closure_time,
                "train_delay_hours": round(sum(train_delays.values()), 2)
            }
        }
