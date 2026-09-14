import pytest
from src.data_pipeline.synthetic_data import generate_synthetic_data
from src.optimization.milp_solver import MaintenanceSchedulerMILP
from src.simulation.what_if_service import WhatIfSimulatorService
from src.data_pipeline.models import (
    WhatIfScenarioRequest,
    WhatIfModification,
    BlockShiftRequest,
    WeatherContext
)

def test_what_if_sandbox_isolation_and_simulation():
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=12, num_trains=8)
    job_tcis = {j.id: 50.0 for j in scenario.jobs}
    
    solver = MaintenanceSchedulerMILP()
    baseline = solver.solve(scenario, job_tcis)

    service = WhatIfSimulatorService()
    
    # Sr. DOM asks: "What if we extend BCM job duration by 1 hour on J1, and Train T2 is delayed by 30 mins?"
    request = WhatIfScenarioRequest(
        modifications=[
            WhatIfModification(job_id="J1", extend_duration_hours=1.0),
            WhatIfModification(train_id="T2", added_delay_min=30.0)
        ]
    )

    resp = service.run_what_if_scenario(scenario, baseline, request)

    assert resp.status == "SUCCESS"
    assert resp.run_id.startswith("WIF-")
    assert resp.delta_report is not None
    assert len(resp.delta_report.train_deltas) > 0
    assert resp.delta_report.narrative_summary_en
    assert resp.delta_report.narrative_summary_hi
    assert "वॉट-इफ" in resp.delta_report.narrative_summary_hi

    # Verify complete in-memory isolation (base scenario unaffected)
    j1_base = next(j for j in scenario.jobs if j.id == "J1")
    assert j1_base.duration < 10.0 # Base duration unmodified

def test_block_shift_evaluation_for_marey_chart():
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=10, num_trains=6)
    job_tcis = {j.id: 50.0 for j in scenario.jobs}
    solver = MaintenanceSchedulerMILP()
    schedule = solver.solve(scenario, job_tcis)

    service = WhatIfSimulatorService()
    
    # Controller drags job J1 30 minutes to the right (+30 min)
    shift_req = BlockShiftRequest(job_id="J1", shift_minutes=30.0)
    shift_resp = service.evaluate_block_shift(scenario, schedule, shift_req)

    assert shift_resp.job_id == "J1"
    assert shift_resp.new_start_hours == round(shift_resp.original_start_hours + 0.5, 2)
    assert shift_resp.bilingual_advisory["en"]
    assert shift_resp.bilingual_advisory["hi"]
    assert "खिसकाकर" in shift_resp.bilingual_advisory["hi"]
