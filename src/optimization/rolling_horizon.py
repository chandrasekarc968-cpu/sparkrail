from typing import Dict, Any, List, Optional, Tuple
import copy
import time
from src.data_pipeline.models import (
    Scenario,
    MaintenanceJob,
    FixedMaintenanceBlock,
    ScheduledJob
)
from src.optimization.milp_solver import MaintenanceSchedulerMILP

class ScheduleAuditEvent:
    """Represents a discrete audit event in the rolling horizon life-cycle."""
    def __init__(
        self,
        event_id: str,
        action: str,
        job_id: str,
        reason: str,
        old_start: Optional[float] = None,
        new_start: Optional[float] = None
    ):
        self.event_id = event_id
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.action = action
        self.job_id = job_id
        self.reason = reason
        self.old_start = old_start
        self.new_start = new_start

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "job_id": self.job_id,
            "reason": self.reason,
            "old_start": self.old_start,
            "new_start": self.new_start
        }

class RollingHorizonScheduler:
    """
    Manages the multi-week rolling horizon planning lifecycle:
    - Week 1 Freeze (immediate operational lock)
    - Re-optimization of future flexible weeks
    - Weekly rollover and executed job archiving
    - Daily dynamic disruption replanning
    - Preservation of executed and frozen jobs
    - Full structured audit trail
    - Scenario-based freight ETA calculations
    """
    
    def __init__(self, freeze_duration_hours: int = 24, total_horizon_hours: int = 168):
        self.freeze_duration = freeze_duration_hours
        self.total_horizon = total_horizon_hours
        self.audit_log: List[Dict[str, Any]] = []
        self.executed_history: List[Dict[str, Any]] = []

    def apply_freeze(self, previous_schedule: Dict[str, Any], scenario: Scenario) -> Scenario:
        """
        Locks all jobs scheduled within the freeze duration (e.g. Week 1).
        Preserves their start times and marks them as is_fixed=True.
        """
        new_scenario = copy.deepcopy(scenario)
        if not previous_schedule or "scheduled_jobs" not in previous_schedule:
            return new_scenario

        frozen_by_id: Dict[str, float] = {}
        for s_job in previous_schedule.get("scheduled_jobs", []):
            start = float(s_job["start_time"])
            if start < self.freeze_duration:
                frozen_by_id[s_job["job_id"]] = start

        for job in new_scenario.jobs:
            if job.id in frozen_by_id:
                old_start = job.fixed_start
                job.is_fixed = True
                job.fixed_start = frozen_by_id[job.id]
                self._record_audit(
                    action="freeze",
                    job_id=job.id,
                    reason=f"Locked into Week 1 Frozen Operational Window (t={job.fixed_start})",
                    old_start=old_start,
                    new_start=job.fixed_start
                )

        return new_scenario

    def replan_disruption(
        self,
        current_schedule: Dict[str, Any],
        scenario: Scenario,
        disruption: Dict[str, Any],
        job_tcis: Dict[str, float],
        solver: MaintenanceSchedulerMILP
    ) -> Dict[str, Any]:
        """
        Daily disruption replanning:
        Given an unexpected emergency track possession or speed restriction,
        re-optimizes flexible jobs around the disruption while preserving all frozen/executed jobs.
        """
        replanned_scenario = copy.deepcopy(scenario)

        # 1. Inject emergency fixed block
        d_block_id = disruption.get("block_id", "B1")
        d_start = float(disruption.get("start_time", 0.0))
        d_end = float(disruption.get("end_time", d_start + 2.0))
        d_reason = disruption.get("reason", "Emergency Track Possession Disruption")

        emergency_fb = FixedMaintenanceBlock(
            id=f"EMERGENCY_{int(time.time())}",
            block_id=d_block_id,
            start_time=d_start,
            end_time=d_end,
            reason=d_reason
        )
        replanned_scenario.fixed_blocks.append(emergency_fb)

        # 2. Preserve frozen jobs
        replanned_scenario = self.apply_freeze(current_schedule, replanned_scenario)

        # 3. Solve new schedule
        new_result = solver.solve(replanned_scenario, job_tcis)

        # 4. Compare and record audit trail of shifted jobs
        prev_starts = {j["job_id"]: j["start_time"] for j in current_schedule.get("scheduled_jobs", [])}
        for s_job in new_result.get("scheduled_jobs", []):
            j_id = s_job["job_id"]
            if j_id in prev_starts and prev_starts[j_id] != s_job["start_time"]:
                self._record_audit(
                    action="replan_shift",
                    job_id=j_id,
                    reason=f"Shifted due to {d_reason} on block {d_block_id}",
                    old_start=prev_starts[j_id],
                    new_start=s_job["start_time"]
                )

        return new_result

    def weekly_rollover(
        self,
        current_schedule: Dict[str, Any],
        scenario: Scenario,
        elapsed_hours: int = 24
    ) -> Tuple[List[Dict[str, Any]], Scenario]:
        """
        Advances the timeline by elapsed_hours (e.g. 1 week or 24 hours):
        - Archives executed jobs completed before elapsed_hours
        - Rolls forward remaining future jobs and shifts their coordinates
        """
        executed = []
        remaining_jobs = []

        scheduled_lookup = {
            j["job_id"]: j for j in current_schedule.get("scheduled_jobs", [])
        }

        for job in scenario.jobs:
            s_info = scheduled_lookup.get(job.id)
            if s_info and float(s_info["end_time"]) <= elapsed_hours:
                # Job executed
                executed.append(s_info)
                self.executed_history.append(s_info)
                self._record_audit(
                    action="archive_executed",
                    job_id=job.id,
                    reason=f"Job executed and archived in elapsed window [0, {elapsed_hours}]",
                    old_start=s_info["start_time"],
                    new_start=None
                )
            else:
                # Shift forward
                new_job = copy.deepcopy(job)
                if new_job.is_fixed and new_job.fixed_start is not None:
                    new_job.fixed_start = max(0.0, new_job.fixed_start - elapsed_hours)
                remaining_jobs.append(new_job)

        new_scenario = copy.deepcopy(scenario)
        new_scenario.jobs = remaining_jobs
        return executed, new_scenario

    def calculate_freight_etas(
        self,
        schedule: Dict[str, Any],
        scenario: Scenario,
        scenario_mode: str = "normal"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Scenario-based freight ETA mode:
        Computes transit times, scheduled vs estimated arrivals, and delay buffers 
        for all freight trains under current maintenance block possessions.
        """
        congestion_mult = 1.0
        if scenario_mode == "congested":
            congestion_mult = 1.35
        elif scenario_mode == "surge":
            congestion_mult = 1.60

        freight_delays = schedule.get("train_delays", {})
        results: Dict[str, Dict[str, Any]] = {}

        for train in scenario.trains:
            if train.category.lower() == "freight":
                base_transit = float(train.scheduled_end - train.scheduled_start)
                possession_delay = float(freight_delays.get(train.id, 0.0))
                adjusted_transit = round((base_transit + possession_delay) * congestion_mult, 2)
                eta = round(train.scheduled_start + adjusted_transit, 2)

                results[train.id] = {
                    "train_id": train.id,
                    "category": train.category,
                    "route": train.route,
                    "scheduled_departure": train.scheduled_start,
                    "scheduled_arrival": train.scheduled_end,
                    "estimated_arrival": eta,
                    "transit_hours": adjusted_transit,
                    "possession_delay_hours": possession_delay,
                    "scenario_mode": scenario_mode,
                    "on_time": possession_delay == 0.0
                }
        return results

    def _record_audit(
        self,
        action: str,
        job_id: str,
        reason: str,
        old_start: Optional[float] = None,
        new_start: Optional[float] = None
    ) -> None:
        event = ScheduleAuditEvent(
            event_id=f"AUD-{len(self.audit_log)+1:04d}",
            action=action,
            job_id=job_id,
            reason=reason,
            old_start=old_start,
            new_start=new_start
        )
        self.audit_log.append(event.to_dict())

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return list(self.audit_log)
