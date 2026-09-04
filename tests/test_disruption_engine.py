"""
Tests for Live Disruption Rescheduler:
Localized corridor extraction, warm-start rescheduling, and hard immutability of
active GRANTED and IN_PROGRESS track possessions.
"""

import pytest
import time
from src.optimization.disruption_engine import DynamicDisruptionEngine
from src.data_pipeline.models import (
    Scenario,
    MaintenanceJob,
    DisruptionEvent,
    PossessionLifecycle,
    OptimizedSchedule,
    ScheduledJob,
    Department,
    TCIInputs
)
from tests.fixtures.deterministic_scenarios import create_granted_possession_scenario, get_standard_blocks


class TestDisruptionEngine:
    def test_granted_possession_immutability(self):
        scenario = create_granted_possession_scenario()
        rescheduler = DynamicDisruptionEngine(default_chainage_radius_km=25.0)

        current_schedule = OptimizedSchedule(
            status="optimal",
            solver="ALNS_DETERMINISTIC",
            total_closure_time=5.5,
            objective_value=140.0,
            runtime_seconds=0.15,
            scheduled_jobs=[
                ScheduledJob(
                    job_id="J_ACTIVE_GRANT",
                    block_id="B1",
                    start_time=2.0,
                    end_time=6.0,
                    tci=95.0,
                    department=Department.ENGINEERING
                ),
                ScheduledJob(
                    job_id="J_ROUTINE_01",
                    block_id="B2",
                    start_time=8.0,
                    end_time=9.5,
                    tci=45.0,
                    department=Department.S_AND_T
                )
            ],
            unscheduled_jobs=[],
            train_delays={}
        )

        # Trigger disruption on B1 with delay of 1.5 hours
        disruption = DisruptionEvent(
            id="DISRUPT-001",
            event_id="DISRUPT-001",
            timestamp="2026-09-04T08:00:00Z",
            affected_block_ids=["B1"],
            delay_minutes=90.0,
            event_type="TRAIN_DELAY",
            severity="MAJOR"
        )

        active_states = {
            "J_ACTIVE_GRANT": PossessionLifecycle.GRANTED,
            "J_ROUTINE_01": PossessionLifecycle.REQUESTED
        }

        start_ts = time.perf_counter()
        result = rescheduler.handle_disruption(
            scenario=scenario,
            current_schedule=current_schedule,
            disruption=disruption,
            active_possession_states=active_states
        )
        duration = time.perf_counter() - start_ts

        assert duration < 90.0, f"Disruption reschedule took {duration:.2f}s (exceeded 90s target)"
        assert result.is_successful, "Rescheduling should succeed"

        # Hard invariant: GRANTED block J_ACTIVE_GRANT must remain completely unchanged
        granted_job = next((j for j in result.rescheduled_schedule.scheduled_jobs if j.job_id == "J_ACTIVE_GRANT"), None)
        assert granted_job is not None, "Active GRANTED possession must be preserved"
        assert granted_job.start_time == 2.0, "GRANTED possession start_time cannot be changed"
        assert granted_job.end_time == 6.0, "GRANTED possession end_time cannot be compressed"
        assert "J_ACTIVE_GRANT" in result.immutable_granted_jobs

    def test_corridor_bounding_radius(self):
        scenario = Scenario(
            blocks=get_standard_blocks(),
            jobs=[
                MaintenanceJob(
                    id="J_ACTIVE_GRANT",
                    block_id="B1",
                    department=Department.ENGINEERING,
                    duration=4.0,
                    required_resources={"R_BCM": 1},
                    tci_inputs=TCIInputs(safety_severity=0.9, traffic_impact=0.8, degradation_indicator=0.8, overdue_days=20),
                    is_fixed=True,
                    fixed_start=2.0
                ),
                MaintenanceJob(
                    id="J_FAR_AWAY",
                    block_id="B7",
                    department=Department.S_AND_T,
                    duration=2.0,
                    required_resources={"R_CREW_SIG": 1},
                    tci_inputs=TCIInputs(safety_severity=0.5, traffic_impact=0.4, degradation_indicator=0.4, overdue_days=4)
                )
            ],
            trains=[],
            resources=[]
        )
        rescheduler = DynamicDisruptionEngine(default_chainage_radius_km=15.0)

        disruption = DisruptionEvent(
            id="DISRUPT-002",
            event_id="DISRUPT-002",
            timestamp="2026-09-04T08:00:00Z",
            affected_block_ids=["B1"],
            delay_minutes=30.0,
            event_type="EQUIPMENT_FAILURE",
            severity="MODERATE"
        )

        current_schedule = OptimizedSchedule(
            status="optimal",
            solver="ALNS_DETERMINISTIC",
            total_closure_time=6.0,
            objective_value=140.0,
            runtime_seconds=0.12,
            scheduled_jobs=[
                ScheduledJob(job_id="J_ACTIVE_GRANT", block_id="B1", start_time=2.0, end_time=6.0, tci=90.0, department=Department.ENGINEERING),
                ScheduledJob(job_id="J_FAR_AWAY", block_id="B7", start_time=10.0, end_time=12.0, tci=50.0, department=Department.S_AND_T)
            ],
            unscheduled_jobs=[],
            train_delays={}
        )

        result = rescheduler.handle_disruption(scenario, current_schedule, disruption)
        assert result.is_successful

        # Corridor radius was 15km around km 0-10 (range 0 to 25 km)
        assert result.affected_corridor_chainage_km[0] <= 5.0
        assert result.affected_corridor_chainage_km[1] >= 15.0
        # J_FAR_AWAY on B7 is at km 60-70, well outside the corridor, so it remains unchanged
        far_job = next((j for j in result.rescheduled_schedule.scheduled_jobs if j.job_id == "J_FAR_AWAY"), None)
        assert far_job is not None
        assert far_job.start_time == 10.0
