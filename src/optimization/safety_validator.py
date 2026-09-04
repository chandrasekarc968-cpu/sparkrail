from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    Scenario,
    Department,
    ScheduledJob,
    OptimizedSchedule
)

class SafetyViolationError(ValueError):
    """Raised when an optimized railway schedule violates hard operational safety rules."""
    pass

class SafetyAuditResult(BaseModel):
    is_safe: bool
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    total_scheduled_jobs: int = 0
    total_fixed_blocks_checked: int = 0
    total_trains_checked: int = 0

def are_departments_incompatible(d1: Department | str, d2: Department | str) -> bool:
    """
    Railway Safety Invariant:
    OHE (25kV AC Traction Power Isolation) and S&T (Signaling & Telecom live circuit testing)
    cannot be performed simultaneously on the same track section due to mutual electrocution
    and false signal indication hazards.
    """
    v1 = d1.value if isinstance(d1, Department) else str(d1)
    v2 = d2.value if isinstance(d2, Department) else str(d2)
    return (v1 == Department.OHE.value and v2 == Department.S_AND_T.value) or \
           (v2 == Department.OHE.value and v1 == Department.S_AND_T.value)

def validate_schedule_safety(
    schedule: Dict[str, Any] | OptimizedSchedule,
    scenario: Scenario,
    horizon: int = 24,
    max_premium_delay: float = 1.0,
    raise_on_error: bool = False
) -> SafetyAuditResult:
    """
    Independent railway safety audit validator.
    Strictly verifies all physical and operational safety rules:
    1. Fixed Block Non-Overlap: No routine maintenance job collides with an external fixed mega block.
    2. Department Isolation: OHE and S&T never overlap on the same block.
    3. Resource Availability: Resource usage never exceeds capacity at any hour.
    4. Premium Train SLA: No premium express service exceeds max allowed delay.
    5. Duration & Boundary: Start time >= 0, end time > start time, duration matches job requirement.
    """
    violations: List[str] = []
    warnings: List[str] = []

    # Normalize scheduled_jobs list
    if isinstance(schedule, OptimizedSchedule):
        sched_jobs = [j.model_dump() for j in schedule.scheduled_jobs]
        delays = schedule.train_delays
    else:
        sched_jobs = schedule.get("scheduled_jobs", [])
        delays = schedule.get("train_delays", {})

    job_dict = {j.id: j for j in scenario.jobs}
    resource_dict = {r.id: r for r in scenario.resources}

    # Hourly resource tracker: res_id -> [usage at t]
    resource_usage: Dict[str, List[int]] = {r.id: [0] * horizon for r in scenario.resources}

    # Hourly department tracker on each block: block_id -> hour -> list of (dept, job_id)
    block_dept_usage: Dict[str, Dict[int, List[tuple]]] = {
        b.id: {t: [] for t in range(horizon)} for b in scenario.blocks
    }

    # 1. Job Duration, Horizon Bounds, and Overlap Tracking
    for sj in sched_jobs:
        job_id = sj.get("job_id")
        block_id = sj.get("block_id")
        start_time = float(sj.get("start_time", -1))
        end_time = float(sj.get("end_time", -1))
        dept = sj.get("department")

        if start_time < 0.0 or start_time >= horizon:
            violations.append(f"Job '{job_id}' start_time ({start_time}h) outside horizon [0, {horizon}h].")
        if end_time <= start_time:
            violations.append(f"Job '{job_id}' invalid window: end_time ({end_time}h) <= start_time ({start_time}h).")

        orig_job = job_dict.get(job_id)
        if orig_job:
            expected_dur = orig_job.duration
            actual_dur = end_time - start_time
            if abs(actual_dur - expected_dur) > 1e-4:
                violations.append(
                    f"Job '{job_id}' duration mismatch: scheduled duration {actual_dur:.2f}h != required {expected_dur:.2f}h."
                )

            # Record resource usage
            int_start = max(0, int(start_time))
            int_end = min(horizon, int(end_time))
            for r_id, req in orig_job.required_resources.items():
                if r_id in resource_usage:
                    for t in range(int_start, int_end):
                        resource_usage[r_id][t] += req

            # Record department usage on block
            if block_id in block_dept_usage:
                for t in range(int_start, int_end):
                    block_dept_usage[block_id][t].append((dept, job_id))

    # 2. Fixed Block Non-Overlap Invariant
    for fb in scenario.fixed_blocks:
        fb_s = float(fb.start_time)
        fb_e = float(fb.end_time)
        fb_block = fb.block_id

        for sj in sched_jobs:
            job_id = sj.get("job_id")
            if sj.get("block_id") == fb_block:
                orig_job = job_dict.get(job_id)
                # If routine non-fixed job
                if orig_job and not orig_job.is_fixed:
                    s = float(sj.get("start_time", -1))
                    e = float(sj.get("end_time", -1))
                    if not (e <= fb_s or s >= fb_e):
                        violations.append(
                            f"Safety hazard: Job '{job_id}' on block '{fb_block}' [{s:.1f}h - {e:.1f}h] "
                            f"collides with external Fixed Mega Block '{fb.id}' [{fb_s:.1f}h - {fb_e:.1f}h]."
                        )

    # 3. Incompatible Department Safety Isolation
    for block_id, hourly in block_dept_usage.items():
        for t, depts in hourly.items():
            if len(depts) >= 2:
                for i in range(len(depts)):
                    for j in range(i + 1, len(depts)):
                        d1, j1 = depts[i]
                        d2, j2 = depts[j]
                        if are_departments_incompatible(d1, d2):
                            violations.append(
                                f"Cross-department hazard: Incompatible departments '{d1}' (Job '{j1}') "
                                f"and '{d2}' (Job '{j2}') scheduled concurrently on block '{block_id}' at T+{t}h."
                            )

    # 4. Resource Capacity Checks
    for r_id, usage_profile in resource_usage.items():
        res_obj = resource_dict.get(r_id)
        if res_obj:
            cap = res_obj.capacity
            for t, used in enumerate(usage_profile):
                if used > cap:
                    violations.append(
                        f"Resource overallocation: Resource '{res_obj.name}' ({r_id}) used {used} units at T+{t}h (capacity: {cap})."
                    )

    # 5. Premium Train Delay SLA Checks
    for tr in scenario.trains:
        if tr.category.lower() == "premium":
            tr_delay = float(delays.get(tr.id, 0.0))
            if tr_delay > max_premium_delay + 1e-4:
                violations.append(
                    f"Punctuality SLA breach: Premium Train '{tr.id}' ({tr.name or 'Premium'}) "
                    f"induced delay ({tr_delay:.2f}h) exceeds maximum allowed limit ({max_premium_delay:.2f}h)."
                )

    result = SafetyAuditResult(
        is_safe=(len(violations) == 0),
        violations=violations,
        warnings=warnings,
        total_scheduled_jobs=len(sched_jobs),
        total_fixed_blocks_checked=len(scenario.fixed_blocks),
        total_trains_checked=len(scenario.trains)
    )

    if raise_on_error and not result.is_safe:
        raise SafetyViolationError("; ".join(violations))

    return result
