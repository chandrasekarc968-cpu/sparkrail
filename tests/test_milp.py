import pytest
from src.data_pipeline.synthetic_data import generate_synthetic_data
from src.optimization.milp_solver import MaintenanceSchedulerMILP
from src.ai_ml.criticality_scorer import TaskCriticalityScorer

def test_milp_feasibility():
    scenario = generate_synthetic_data()
    
    config = {
        "optimization": {
            "big_m": 100000.0,
            "time_limit_seconds": 10,
            "weights": {
                "tci_completion": 10.0,
                "closure_time": 1.0,
                "train_delay": 5.0
            }
        }
    }
    
    scorer = TaskCriticalityScorer({
        "tci": {"weights": {"safety_risk": 0.4, "delay_capacity_impact": 0.3, "degradation_velocity": 0.2, "overdue_penalty": 0.1}}
    })
    
    job_tcis = {}
    for job in scenario.jobs:
        tci, _ = scorer.calculate_tci(job.tci_inputs)
        job_tcis[job.id] = tci
        
    solver = MaintenanceSchedulerMILP(config, horizon_hours=12)
    result = solver.solve(scenario, job_tcis)
    
    assert result["status"] in ["optimal", "feasible"]
    assert "scheduled_jobs" in result
    
    # Check that fixed job is scheduled at fixed time
    fixed_job_found = False
    for j in result["scheduled_jobs"]:
        if j["job_id"] == "J_FIXED_1":
            fixed_job_found = True
            assert j["start_time"] == 6.0
            
    assert fixed_job_found, "Fixed job was not scheduled"
