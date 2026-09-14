import pytest
import os
import tempfile
from src.data_pipeline.synthetic_data import save_synthetic_data
from src.data_pipeline.models import Scenario
from src.optimization.milp_solver import MaintenanceSchedulerMILP
from src.optimization.clustering import SpatiotemporalClusteringEngine
from src.optimization.safety_validator import validate_schedule_safety
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.data_pipeline.ingestion import DataIngestor

@pytest.fixture
def ddu_scenario() -> Scenario:
    # 4 Civil, 3 TRD, 2 S&T demands = 9 jobs
    # 20 mixed-priority trains
    # 3 TTM/BCM machines
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generates exactly 9 jobs and 20 trains
        save_synthetic_data(
            path=tmpdir,
            seed=42,
            num_blocks=10,
            num_jobs=9,
            num_trains=20
        )
        
        ingestor = DataIngestor({"data_pipeline": {"use_local_synthetic": True, "synthetic_data_path": tmpdir}})
        scenario = ingestor.load_scenario()
        return scenario

def test_end_to_end_optimization_safety(ddu_scenario: Scenario):
    config = {}
    
    # 1. TCI Scoring
    scorer = TaskCriticalityScorer(config)
    job_tcis = {job.id: scorer.calculate_tci(job.tci_inputs)[0] for job in ddu_scenario.jobs}
    
    # 2. Clustering
    clustering = SpatiotemporalClusteringEngine()
    bundles = clustering.generate_candidate_bundles(
        ddu_scenario.jobs,
        ddu_scenario.blocks,
        job_tcis
    )
    assert isinstance(bundles, list)
    
    # 3. MILP Optimization
    solver = MaintenanceSchedulerMILP(config)
    schedule_dict = solver.solve(ddu_scenario, job_tcis)
    
    from src.data_pipeline.models import OptimizedSchedule
    schedule = OptimizedSchedule(**schedule_dict)
    
    # 4. Safety Validation
    safety_audit = validate_schedule_safety(schedule, ddu_scenario)
    
    assert safety_audit.is_safe is True, f"Safety violations found: {safety_audit.violations}"
    assert len(safety_audit.violations) == 0
    print("End-to-End test completed. 0 Safety Violations.")
