import copy
import pytest

from src.data_pipeline.models import (
    Scenario,
    Department,
    ScheduledJob,
    FixedMaintenanceBlock
)
from src.data_pipeline.synthetic_data import generate_synthetic_data
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.optimization.milp_solver import MaintenanceSchedulerMILP
from src.optimization.safety_validator import (
    validate_schedule_safety,
    SafetyAuditResult,
    SafetyViolationError
)

@pytest.fixture
def scenario():
    return generate_synthetic_data(seed=26027, num_blocks=8, num_jobs=20, num_trains=10)

@pytest.fixture
def solved_schedule(scenario):
    scorer = TaskCriticalityScorer()
    tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}
    scheduler = MaintenanceSchedulerMILP()
    return scheduler.solve(scenario, tcis)

def test_solver_output_passes_safety_audit(scenario, solved_schedule):
    """Verifies that the MILP / Fallback solver produces a 100% safe schedule."""
    audit = validate_schedule_safety(solved_schedule, scenario)
    assert audit.is_safe is True
    assert len(audit.violations) == 0
    assert audit.total_scheduled_jobs > 0

def test_detects_fixed_block_collision(scenario, solved_schedule):
    """Detects when a routine job collides with a fixed mega block on the same section."""
    sched = copy.deepcopy(solved_schedule)
    # Inject an overlap: FB1 is on B1 from 2.0 to 6.0
    sched["scheduled_jobs"].append({
        "job_id": "J_UNSAFE_ROUTINE",
        "block_id": "B1",
        "start_time": 3.0,
        "end_time": 5.0,
        "tci": 50.0,
        "department": "Engineering"
    })
    # Add dummy routine job to scenario
    scen = copy.deepcopy(scenario)
    dummy_job = copy.deepcopy(scen.jobs[0])
    dummy_job.id = "J_UNSAFE_ROUTINE"
    dummy_job.block_id = "B1"
    dummy_job.duration = 2.0
    dummy_job.is_fixed = False
    scen.jobs.append(dummy_job)

    audit = validate_schedule_safety(sched, scen)
    assert audit.is_safe is False
    assert any("collides with external Fixed Mega Block" in v for v in audit.violations)

def test_detects_incompatible_departments(scenario, solved_schedule):
    """Detects concurrent OHE power isolation and S&T signaling on the same block."""
    sched = copy.deepcopy(solved_schedule)
    scen = copy.deepcopy(scenario)

    j_ohe = copy.deepcopy(scen.jobs[0])
    j_ohe.id = "J_TEST_OHE"
    j_ohe.department = Department.OHE
    j_ohe.block_id = "B3"
    j_ohe.duration = 2.0
    scen.jobs.append(j_ohe)

    j_st = copy.deepcopy(scen.jobs[0])
    j_st.id = "J_TEST_ST"
    j_st.department = Department.S_AND_T
    j_st.block_id = "B3"
    j_st.duration = 2.0
    scen.jobs.append(j_st)

    sched["scheduled_jobs"].extend([
        {"job_id": "J_TEST_OHE", "block_id": "B3", "start_time": 4.0, "end_time": 6.0, "department": "OHE", "tci": 60.0},
        {"job_id": "J_TEST_ST", "block_id": "B3", "start_time": 4.0, "end_time": 6.0, "department": "S&T", "tci": 60.0}
    ])

    audit = validate_schedule_safety(sched, scen)
    assert audit.is_safe is False
    assert any("Incompatible departments" in v for v in audit.violations)

def test_detects_resource_overallocation(scenario, solved_schedule):
    """Detects when machinery demand exceeds fleet capacity."""
    sched = copy.deepcopy(solved_schedule)
    scen = copy.deepcopy(scenario)

    # R_BCM capacity is 2
    for i in range(3):
        j = copy.deepcopy(scen.jobs[0])
        j.id = f"J_BCM_{i}"
        j.required_resources = {"R_BCM": 1}
        j.duration = 2.0
        scen.jobs.append(j)
        sched["scheduled_jobs"].append({
            "job_id": f"J_BCM_{i}",
            "block_id": f"B{i+2}",
            "start_time": 8.0,
            "end_time": 10.0,
            "department": "Engineering",
            "tci": 50.0
        })

    audit = validate_schedule_safety(sched, scen)
    assert audit.is_safe is False
    assert any("Resource overallocation" in v for v in audit.violations)

def test_detects_premium_train_sla_breach(scenario, solved_schedule):
    """Detects when a premium train exceeds the 1.0h delay SLA limit."""
    sched = copy.deepcopy(solved_schedule)
    sched["train_delays"]["T1"] = 1.8  # T1 is premium

    audit = validate_schedule_safety(sched, scenario)
    assert audit.is_safe is False
    assert any("Punctuality SLA breach" in v for v in audit.violations)
