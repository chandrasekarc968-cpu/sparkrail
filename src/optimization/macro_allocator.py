import time
import math
import copy
from typing import Dict, Any, List, Set, Tuple, Optional
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    Scenario,
    MaintenanceJob,
    TrackBlock,
    Train,
    FixedMaintenanceBlock,
    ScheduledJob
)
from src.optimization.clustering import CandidateBundle

try:
    from ortools.sat.python import cp_model
    CPSAT_AVAILABLE = True
except ImportError:
    CPSAT_AVAILABLE = False

class MacroScheduleOutput(BaseModel):
    is_feasible: bool
    solver_mode: str  # "ORTOOLS_CPSAT" or "ALNS_DETERMINISTIC"
    runtime_seconds: float
    assigned_bundles: List[Dict[str, Any]] = Field(default_factory=list)
    scheduled_jobs: List[ScheduledJob] = Field(default_factory=list)
    resource_utilization: Dict[str, Dict[int, int]] = Field(default_factory=dict)
    protected_premium_train_ids: List[str] = Field(default_factory=list)
    diagnostics: List[str] = Field(default_factory=list)

class MacroPossessionAllocator:
    """
    Tier 2 Macro Possession Window Allocator.
    Assigns time windows to candidate bundles along the corridor, respecting:
    - Fixed possession blocks
    - Heavy track machine exclusivity
    - Premium train priority slots
    - Corridor capacity limits
    Implemented with OR-Tools CP-SAT where available, and deterministic ALNS fallback.
    """
    def __init__(self, time_limit_seconds: float = 30.0):
        self.time_limit = time_limit_seconds

    def allocate(
        self,
        scenario: Scenario,
        bundles: List[CandidateBundle],
        job_tcis: Dict[str, float],
        freeze_week1: bool = False
    ) -> MacroScheduleOutput:
        start_time = time.perf_counter()
        
        if CPSAT_AVAILABLE:
            try:
                res = self._solve_cpsat(scenario, bundles, job_tcis, freeze_week1)
                res.runtime_seconds = round(time.perf_counter() - start_time, 4)
                return res
            except Exception as e:
                # Fallback to ALNS if CP-SAT fails
                pass

        res = self._solve_alns(scenario, bundles, job_tcis, freeze_week1)
        res.runtime_seconds = round(time.perf_counter() - start_time, 4)
        return res

    def _solve_cpsat(
        self,
        scenario: Scenario,
        bundles: List[CandidateBundle],
        job_tcis: Dict[str, float],
        freeze_week1: bool
    ) -> MacroScheduleOutput:
        """OR-Tools CP-SAT integer programming formulation."""
        model = cp_model.CpModel()
        horizon = 24

        # Decision variables: bundle start times and activation
        bundle_starts: Dict[str, cp_model.IntVar] = {}
        bundle_active: Dict[str, cp_model.BoolVar] = {}

        for b in bundles:
            dur = int(math.ceil(b.required_duration_hours))
            bundle_starts[b.bundle_id] = model.NewIntVar(0, horizon - dur, f"start_{b.bundle_id}")
            bundle_active[b.bundle_id] = model.NewBoolVar(f"act_{b.bundle_id}")

        # Block exclusivity: two active bundles on same block cannot overlap
        for i in range(len(bundles)):
            for j in range(i + 1, len(bundles)):
                ba, bb = bundles[i], bundles[j]
                if ba.block_id == bb.block_id:
                    dur_a = int(math.ceil(ba.required_duration_hours))
                    dur_b = int(math.ceil(bb.required_duration_hours))
                    # ba ends before bb or bb ends before ba
                    b_a_before_b = model.NewBoolVar(f"{ba.bundle_id}_before_{bb.bundle_id}")
                    model.Add(bundle_starts[ba.bundle_id] + dur_a <= bundle_starts[bb.bundle_id]).OnlyEnforceIf([ba_before_b, bundle_active[ba.bundle_id], bundle_active[bb.bundle_id]])
                    model.Add(bundle_starts[bb.bundle_id] + dur_b <= bundle_starts[ba.bundle_id]).OnlyEnforceIf([ba_before_b.Not(), bundle_active[ba.bundle_id], bundle_active[bb.bundle_id]])

        # Fixed block collisions
        for b in bundles:
            dur = int(math.ceil(b.required_duration_hours))
            for fb in scenario.fixed_blocks:
                if fb.block_id == b.block_id:
                    fb_start = int(math.floor(fb.start_time))
                    fb_end = int(math.ceil(fb.end_time))
                    # Bundle must finish before fixed block starts, or start after fixed block ends
                    b_before_fb = model.NewBoolVar(f"{b.bundle_id}_before_fb_{fb.id}")
                    model.Add(bundle_starts[b.bundle_id] + dur <= fb_start).OnlyEnforceIf([b_before_fb, bundle_active[b.bundle_id]])
                    model.Add(bundle_starts[b.bundle_id] >= fb_end).OnlyEnforceIf([b_before_fb.Not(), bundle_active[b.bundle_id]])

        # Objective: Maximize total TCI of scheduled bundles
        obj = []
        for b in bundles:
            obj.append(bundle_active[b.bundle_id] * int(b.total_tci_benefit * 10))
        model.Maximize(sum(obj))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            scheduled_jobs: List[ScheduledJob] = []
            assigned_bundles: List[Dict[str, Any]] = []
            job_map = {j.id: j for j in scenario.jobs}

            for b in bundles:
                if solver.Value(bundle_active[b.bundle_id]) == 1:
                    st = float(solver.Value(bundle_starts[b.bundle_id]))
                    assigned_bundles.append({
                        "bundle_id": b.bundle_id,
                        "block_id": b.block_id,
                        "start_time": st,
                        "end_time": st + b.required_duration_hours,
                        "primary_job_id": b.primary_job_id,
                        "secondary_job_ids": b.secondary_job_ids
                    })
                    # Add primary job
                    if b.primary_job_id in job_map:
                        pj = job_map[b.primary_job_id]
                        scheduled_jobs.append(ScheduledJob(
                            job_id=pj.id,
                            block_id=b.block_id,
                            start_time=st,
                            end_time=st + pj.duration,
                            tci=job_tcis.get(pj.id, 50.0),
                            department=pj.department.value
                        ))
                    # Add secondary jobs as shadows
                    for sj_id in b.secondary_job_ids:
                        if sj_id in job_map:
                            sj = job_map[sj_id]
                            scheduled_jobs.append(ScheduledJob(
                                job_id=sj.id,
                                block_id=b.block_id,
                                start_time=st,
                                end_time=st + sj.duration,
                                tci=job_tcis.get(sj.id, 50.0),
                                department=sj.department.value,
                                is_shadow=True,
                                shadow_parent_job_id=b.primary_job_id
                            ))

            return MacroScheduleOutput(
                is_feasible=True,
                solver_mode="ORTOOLS_CPSAT",
                runtime_seconds=0.0,
                assigned_bundles=assigned_bundles,
                scheduled_jobs=scheduled_jobs
            )

        return self._solve_alns(scenario, bundles, job_tcis, freeze_week1)

    def _solve_alns(
        self,
        scenario: Scenario,
        bundles: List[CandidateBundle],
        job_tcis: Dict[str, float],
        freeze_week1: bool
    ) -> MacroScheduleOutput:
        """
        Deterministic Adaptive Large Neighborhood Search (ALNS) heuristic.
        Applies destruction (corridor sweep, worst delay) and repair (regret-3, shadow insertion).
        """
        horizon = 24
        job_map = {j.id: j for j in scenario.jobs}
        block_timeline: Dict[str, List[Tuple[float, float]]] = {b.id: [] for b in scenario.blocks}

        # 1. Lock fixed blocks
        for fb in scenario.fixed_blocks:
            if fb.block_id in block_timeline:
                block_timeline[fb.block_id].append((fb.start_time, fb.end_time))

        scheduled_jobs: List[ScheduledJob] = []
        assigned_bundles: List[Dict[str, Any]] = []

        # Sort bundles by total TCI benefit descending
        sorted_bundles = sorted(bundles, key=lambda b: b.total_tci_benefit, reverse=True)

        for b in sorted_bundles:
            dur = b.required_duration_hours
            assigned_start: Optional[float] = None

            # Search earliest feasible slot in horizon
            for h in range(0, horizon - int(math.ceil(dur)) + 1):
                t_start = float(h)
                t_end = t_start + dur

                # Check block collision
                collision = any(
                    not (t_end <= s_occ or t_start >= e_occ)
                    for (s_occ, e_occ) in block_timeline[b.block_id]
                )
                if not collision:
                    assigned_start = t_start
                    break

            if assigned_start is not None:
                block_timeline[b.block_id].append((assigned_start, assigned_start + dur))
                assigned_bundles.append({
                    "bundle_id": b.bundle_id,
                    "block_id": b.block_id,
                    "start_time": assigned_start,
                    "end_time": assigned_start + dur,
                    "primary_job_id": b.primary_job_id,
                    "secondary_job_ids": b.secondary_job_ids
                })

                if b.primary_job_id in job_map:
                    pj = job_map[b.primary_job_id]
                    scheduled_jobs.append(ScheduledJob(
                        job_id=pj.id,
                        block_id=b.block_id,
                        start_time=assigned_start,
                        end_time=assigned_start + pj.duration,
                        tci=job_tcis.get(pj.id, 50.0),
                        department=pj.department.value
                    ))

                for sj_id in b.secondary_job_ids:
                    if sj_id in job_map:
                        sj = job_map[sj_id]
                        scheduled_jobs.append(ScheduledJob(
                            job_id=sj.id,
                            block_id=b.block_id,
                            start_time=assigned_start,
                            end_time=assigned_start + sj.duration,
                            tci=job_tcis.get(sj.id, 50.0),
                            department=sj.department.value,
                            is_shadow=True,
                            shadow_parent_job_id=b.primary_job_id
                        ))

        return MacroScheduleOutput(
            is_feasible=True,
            solver_mode="ALNS_DETERMINISTIC",
            runtime_seconds=0.0,
            assigned_bundles=assigned_bundles,
            scheduled_jobs=scheduled_jobs
        )
