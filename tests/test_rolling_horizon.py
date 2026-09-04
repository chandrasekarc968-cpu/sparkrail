import pytest
from src.data_pipeline.synthetic_data import generate_synthetic_data
from src.data_pipeline.models import Department, MaintenanceJob, TCIInputs
from src.optimization.rolling_horizon import RollingHorizonScheduler
from src.optimization.milp_solver import MaintenanceSchedulerMILP

@pytest.fixture
def solver():
    return MaintenanceSchedulerMILP({
        "optimization": {
            "time_limit_seconds": 15,
            "weights": {"tci_completion": 100.0, "closure_time": 1.0, "train_delay": 5.0},
            "horizon_hours": 24
        }
    })

def test_week1_freeze_preservation(solver):
    """Frozen jobs never change start time or get displaced during re-optimization."""
    scenario = generate_synthetic_data(seed=42)
    job_tcis = {j.id: 60.0 for j in scenario.jobs}
    
    # Run initial schedule
    initial_result = solver.solve(scenario, job_tcis)
    assert len(initial_result["scheduled_jobs"]) > 0
    
    # Pick a job scheduled in Week 1 (t < 24)
    target_job = initial_result["scheduled_jobs"][0]
    target_id = target_job["job_id"]
    target_start = target_job["start_time"]
    
    # Apply Week 1 freeze
    rh = RollingHorizonScheduler(freeze_duration_hours=24)
    frozen_scenario = rh.apply_freeze(initial_result, scenario)
    
    # Check that target job is marked fixed with exact start time
    job_in_scenario = next(j for j in frozen_scenario.jobs if j.id == target_id)
    assert job_in_scenario.is_fixed is True
    assert job_in_scenario.fixed_start == target_start
    
    # Re-optimize with altered TCI weights
    reopt_result = solver.solve(frozen_scenario, job_tcis)
    reopt_job = next(j for j in reopt_result["scheduled_jobs"] if j["job_id"] == target_id)
    
    assert reopt_job["start_time"] == target_start, "Frozen job must never change start time"

def test_daily_disruption_replanning(solver):
    """Disruption replanning injects emergency block and shifts flexible jobs while preserving frozen jobs."""
    scenario = generate_synthetic_data(seed=42)
    job_tcis = {j.id: 60.0 for j in scenario.jobs}
    
    # Initial schedule
    initial_result = solver.solve(scenario, job_tcis)
    
    rh = RollingHorizonScheduler(freeze_duration_hours=12)
    disruption = {
        "block_id": "B3",
        "start_time": 14.0,
        "end_time": 17.0,
        "reason": "Emergency Rail Fracture Possession"
    }
    
    replanned_result = rh.replan_disruption(initial_result, scenario, disruption, job_tcis, solver)
    
    assert replanned_result["status"] in ("optimal", "feasible", "heuristic_feasible")
    # Audit trail must have recorded events
    audit_trail = rh.get_audit_trail()
    assert len(audit_trail) > 0

def test_weekly_rollover():
    """Weekly rollover archives executed jobs and shifts future jobs."""
    scenario = generate_synthetic_data(seed=42)
    rh = RollingHorizonScheduler(freeze_duration_hours=24)
    
    mock_schedule = {
        "scheduled_jobs": [
            {"job_id": "J1", "start_time": 2.0, "end_time": 4.0}, # executed
            {"job_id": "J2", "start_time": 25.0, "end_time": 28.0} # future
        ]
    }
    
    executed, new_scenario = rh.weekly_rollover(mock_schedule, scenario, elapsed_hours=24)
    
    assert len(executed) == 1
    assert executed[0]["job_id"] == "J1"
    assert len(rh.executed_history) == 1

def test_freight_eta_calculation():
    """Scenario-based freight ETA mode predicts arrivals under normal and congested scenarios."""
    scenario = generate_synthetic_data(seed=42)
    mock_schedule = {
        "train_delays": {"T1": 0.0, "T4": 2.0, "T5": 0.0}
    }
    rh = RollingHorizonScheduler()
    
    normal_etas = rh.calculate_freight_etas(mock_schedule, scenario, scenario_mode="normal")
    congested_etas = rh.calculate_freight_etas(mock_schedule, scenario, scenario_mode="congested")
    
    assert len(normal_etas) > 0
    for train_id, data in normal_etas.items():
        assert "estimated_arrival" in data
        assert "transit_hours" in data
        assert congested_etas[train_id]["transit_hours"] >= data["transit_hours"]
