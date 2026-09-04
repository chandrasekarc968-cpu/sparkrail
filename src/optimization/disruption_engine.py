import time
from typing import Dict, Any, List, Set, Tuple, Optional
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    Scenario,
    ScheduledJob,
    DisruptionEvent,
    OptimizedSchedule,
    PossessionLifecycle
)
from src.optimization.safety_validator import validate_schedule_safety

class DisruptionResolution(BaseModel):
    is_successful: bool
    rescheduled_schedule: OptimizedSchedule
    disruption_event: DisruptionEvent
    affected_corridor_chainage_km: Tuple[float, float]
    right_shifted_jobs: List[str] = Field(default_factory=list)
    immutable_granted_jobs: List[str] = Field(default_factory=list)
    runtime_seconds: float
    advisory_recommendation: str
    diagnostics: List[str] = Field(default_factory=list)

class DynamicDisruptionEngine:
    """
    Reactive Dynamic Disruption Rescheduler.
    Confines replanning to a localized corridor radius, preserves immutable
    GRANTED/IN_PROGRESS possessions, warm-starts from prior baseline,
    and returns certified advisory schedule in <90 seconds.
    """
    def __init__(
        self,
        default_chainage_radius_km: float = 25.0,
        max_allowed_delay_shift_hours: float = 4.0
    ):
        self.chainage_radius = default_chainage_radius_km
        self.max_shift = max_allowed_delay_shift_hours

    def handle_disruption(
        self,
        scenario: Scenario,
        current_schedule: OptimizedSchedule,
        disruption: DisruptionEvent,
        active_possession_states: Optional[Dict[str, PossessionLifecycle]] = None
    ) -> DisruptionResolution:
        start_time = time.perf_counter()
        states = active_possession_states or {}

        # 1. Identify affected corridor chainage range
        block_map = {b.id: b for b in scenario.blocks}
        affected_blocks = disruption.affected_block_ids
        
        min_km = 0.0
        max_km = 80.0
        if affected_blocks:
            min_km = min(block_map[b].chainage_start for b in affected_blocks if b in block_map)
            max_km = max(block_map[b].chainage_end for b in affected_blocks if b in block_map)
        
        # Expand by radius
        corridor_min = max(0.0, min_km - self.chainage_radius)
        corridor_max = min(80.0, max_km + self.chainage_radius)

        # 2. Identify immutable vs shiftable jobs
        immutable_jobs: List[str] = []
        right_shifted_jobs: List[str] = []
        new_scheduled_jobs: List[ScheduledJob] = []

        delay_shift_hours = disruption.delay_minutes / 60.0

        for sj in current_schedule.scheduled_jobs:
            lifecycle = states.get(sj.job_id, PossessionLifecycle.SANCTIONED)
            
            # Hard Invariant: GRANTED and IN_PROGRESS possessions cannot be moved or cancelled!
            if lifecycle in (PossessionLifecycle.GRANTED, PossessionLifecycle.IN_PROGRESS):
                immutable_jobs.append(sj.job_id)
                new_scheduled_jobs.append(sj)
                continue

            # Check if job is in affected corridor and overlaps with disruption
            b_info = block_map.get(sj.block_id)
            in_affected_zone = b_info and (b_info.chainage_start <= corridor_max and b_info.chainage_end >= corridor_min)

            if in_affected_zone and disruption.severity in ("CRITICAL", "MAJOR"):
                # Right-shift sanctioned work by delay margin
                shifted_start = sj.start_time + delay_shift_hours
                dur = sj.end_time - sj.start_time
                shifted_end = shifted_start + dur

                new_sj = sj.model_copy(update={
                    "start_time": round(shifted_start, 2),
                    "end_time": round(shifted_end, 2)
                })
                right_shifted_jobs.append(sj.job_id)
                new_scheduled_jobs.append(new_sj)
            else:
                # Unaffected corridor decision is frozen
                new_scheduled_jobs.append(sj)

        # 3. Formulate revised schedule
        rescheduled = current_schedule.model_copy(update={
            "scheduled_jobs": new_scheduled_jobs,
            "status": "rescheduled_advisory",
            "is_fallback": False
        })

        # 4. Audit safety
        safety_audit = validate_schedule_safety(rescheduled, scenario)
        elapsed = round(time.perf_counter() - start_time, 4)

        return DisruptionResolution(
            is_successful=safety_audit.is_safe,
            rescheduled_schedule=rescheduled,
            disruption_event=disruption,
            affected_corridor_chainage_km=(corridor_min, corridor_max),
            right_shifted_jobs=right_shifted_jobs,
            immutable_granted_jobs=immutable_jobs,
            runtime_seconds=elapsed,
            advisory_recommendation=(
                f"Preserved {len(immutable_jobs)} active granted blocks. "
                f"Right-shifted {len(right_shifted_jobs)} sanctioned jobs by {disruption.delay_minutes:.0f}m within KM {corridor_min:.1f}-{corridor_max:.1f} corridor."
            ),
            diagnostics=[f"Disruption handled in {elapsed*1000:.1f}ms. Safety audit passed: {safety_audit.is_safe}"]
        )
