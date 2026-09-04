import pytest
from src.data_pipeline.synthetic_data import generate_synthetic_data
from src.data_pipeline.models import (
    Department,
    MaintenanceJob,
    TCIInputs,
    FixedMaintenanceBlock,
    Train
)
from src.optimization.milp_solver import MaintenanceSchedulerMILP, SCIP_AVAILABLE

@pytest.fixture
def base_config():
    return {
        "optimization": {
            "time_limit_seconds": 15,
            "weights": {
                "tci_completion": 100.0,
                "closure_time": 1.0,
                "train_delay": 5.0,
                "separate_closure_penalty": 2.0,
                "shadow_consolidation_reward": 10.0
            },
            "horizon_hours": 24
        }
    }

def test_milp_solve_optimal(base_config):
    """MILP solver finds optimal or feasible schedule and respects fixed jobs."""
    scenario = generate_synthetic_data(seed=42)
    job_tcis = {j.id: 50.0 for j in scenario.jobs}
    
    solver = MaintenanceSchedulerMILP(base_config)
    result = solver.solve(scenario, job_tcis)
    
    assert result["status"] in ("optimal", "feasible", "heuristic_feasible")
    assert len(result["scheduled_jobs"]) > 0
    assert "objective_components" in result
    assert result["total_closure_time"] > 0
    
    # Verify fixed job J_FIXED_1 is scheduled at start_time == 2.0
    fixed_job = next((j for j in result["scheduled_jobs"] if j["job_id"] == "J_FIXED_1"), None)
    assert fixed_job is not None
    assert fixed_job["start_time"] == 2.0

def test_department_incompatibility_no_overlap(base_config):
    """OHE and S&T must NEVER overlap on the same block at the same hour."""
    scenario = generate_synthetic_data(seed=42)
    # Focus only on block B2 with 1 OHE job and 1 S&T job
    scenario.jobs = [
        MaintenanceJob(
            id="J_OHE_TEST",
            department=Department.OHE,
            block_id="B2",
            duration=3.0,
            required_resources={"R_CREW_OHE": 1},
            tci_inputs=TCIInputs(safety_severity=0.8, traffic_impact=0.8, degradation_indicator=0.8, overdue_days=10)
        ),
        MaintenanceJob(
            id="J_SNT_TEST",
            department=Department.S_AND_T,
            block_id="B2",
            duration=3.0,
            required_resources={"R_CREW_SIG": 1},
            tci_inputs=TCIInputs(safety_severity=0.8, traffic_impact=0.8, degradation_indicator=0.8, overdue_days=10)
        )
    ]
    job_tcis = {"J_OHE_TEST": 80.0, "J_SNT_TEST": 80.0}
    
    solver = MaintenanceSchedulerMILP(base_config)
    result = solver.solve(scenario, job_tcis)
    
    sched = result["scheduled_jobs"]
    if len(sched) == 2:
        j1 = next(j for j in sched if j["job_id"] == "J_OHE_TEST")
        j2 = next(j for j in sched if j["job_id"] == "J_SNT_TEST")
        # Overlap check
        overlap = max(0, min(j1["end_time"], j2["end_time"]) - max(j1["start_time"], j2["start_time"]))
        assert overlap == 0.0, f"Incompatible jobs overlapped on {j1['block_id']} for {overlap}h"

def test_compatible_departments_share_shadow_block(base_config):
    """Engineering and OHE can co-locate on the same block forming a shadow block."""
    scenario = generate_synthetic_data(seed=42)
    scenario.fixed_blocks = []
    scenario.trains = []
    
    scenario.jobs = [
        MaintenanceJob(
            id="J_ENG_CO",
            department=Department.ENGINEERING,
            block_id="B3",
            duration=3.0,
            required_resources={"R_BCM": 1},
            tci_inputs=TCIInputs(safety_severity=0.9, traffic_impact=0.9, degradation_indicator=0.9, overdue_days=20),
            is_fixed=True,
            fixed_start=5.0
        ),
        MaintenanceJob(
            id="J_OHE_CO",
            department=Department.OHE,
            block_id="B3",
            duration=2.0,
            required_resources={"R_CREW_OHE": 1},
            tci_inputs=TCIInputs(safety_severity=0.9, traffic_impact=0.9, degradation_indicator=0.9, overdue_days=20)
        )
    ]
    job_tcis = {"J_ENG_CO": 90.0, "J_OHE_CO": 90.0}
    
    solver = MaintenanceSchedulerMILP(base_config)
    result = solver.solve(scenario, job_tcis)
    
    sched = result["scheduled_jobs"]
    assert len(sched) == 2
    # Check that shadow block flag is set
    has_shadow = any(j.get("is_shadow_block") for j in sched)
    assert has_shadow, "Compatible jobs should share closure and be marked as shadow block"

def test_premium_train_delay_limit(base_config):
    """Premium trains must never exceed the 1.0 hour delay limit."""
    scenario = generate_synthetic_data(seed=42)
    job_tcis = {j.id: 50.0 for j in scenario.jobs}
    
    solver = MaintenanceSchedulerMILP(base_config)
    result = solver.solve(scenario, job_tcis)
    
    for tr in scenario.trains:
        if tr.category.lower() == "premium":
            delay = result["train_delays"].get(tr.id, 0.0)
            assert delay <= 1.0, f"Premium train {tr.id} exceeded max delay: {delay}h"

def test_fallback_scheduler_labels_non_optimal(base_config):
    """Fallback scheduler explicitly labels result as NON_OPTIMAL_FALLBACK."""
    scenario = generate_synthetic_data(seed=42)
    job_tcis = {j.id: 50.0 for j in scenario.jobs}
    
    solver = MaintenanceSchedulerMILP(base_config)
    # Explicitly invoke fallback
    result = solver._solve_heuristic(scenario, job_tcis)
    
    assert result["solver"] == "NON_OPTIMAL_FALLBACK"
    assert result["status"] == "heuristic_feasible"
    assert result["status"] != "optimal"
    assert "scheduled_jobs" in result
    assert "train_delays" in result

def test_exact_unscheduled_reasons(base_config):
    """Unscheduled jobs have exact, non-generic reasons."""
    scenario = generate_synthetic_data(seed=42)
    # Add an impossible job that exceeds the horizon
    scenario.jobs.append(
        MaintenanceJob(
            id="J_IMPOSSIBLE_DUR",
            department=Department.ENGINEERING,
            block_id="B1",
            duration=36.0, # Exceeds 24h horizon
            required_resources={"R_BCM": 1},
            tci_inputs=TCIInputs(safety_severity=0.5, traffic_impact=0.5, degradation_indicator=0.5, overdue_days=0)
        )
    )
    job_tcis = {j.id: 50.0 for j in scenario.jobs}
    
    solver = MaintenanceSchedulerMILP(base_config)
    result = solver.solve(scenario, job_tcis)
    
    rejected = next((u for u in result["unscheduled_jobs"] if u["job_id"] == "J_IMPOSSIBLE_DUR"), None)
    assert rejected is not None
    assert "exceeds horizon" in rejected["reason"].lower()
