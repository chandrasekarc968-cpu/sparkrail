import pytest
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.data_pipeline.models import TCIInputs
from src.data_pipeline.synthetic_data import generate_synthetic_data
from src.data_pipeline.ingestion import DataIngestor
from src.simulation.evaluator import KPIEvaluator

def test_tci_scorer_weights():
    # Valid weights
    scorer = TaskCriticalityScorer({
        "tci": {"weights": {"safety_risk": 0.5, "delay_capacity_impact": 0.3, "degradation_velocity": 0.1, "overdue_penalty": 0.1}}
    })
    
    # Invalid weights
    with pytest.raises(ValueError):
        TaskCriticalityScorer({
            "tci": {"weights": {"safety_risk": 0.5, "delay_capacity_impact": 0.5, "degradation_velocity": 0.5, "overdue_penalty": 0.5}}
        })

def test_tci_calculation():
    scorer = TaskCriticalityScorer({
        "tci": {"weights": {"safety_risk": 0.4, "delay_capacity_impact": 0.3, "degradation_velocity": 0.2, "overdue_penalty": 0.1}}
    })
    
    inputs = TCIInputs(safety_severity=1.0, traffic_impact=1.0, degradation_indicator=1.0, overdue_days=30)
    tci, explanation = scorer.calculate_tci(inputs)
    
    # Should be close to 100
    assert 99.0 <= tci <= 100.0
    
    # Test XGBoost fallback
    scorer_xgb = TaskCriticalityScorer({
        "tci": {"use_xgboost_degradation": True}
    })
    with pytest.raises(NotImplementedError):
        scorer_xgb.calculate_tci(inputs)

def test_chainage_mapping():
    ingestor = DataIngestor({})
    scenario = generate_synthetic_data()
    
    assert ingestor.map_chainage_to_block(5.0, scenario) == "B1"
    assert ingestor.map_chainage_to_block(15.0, scenario) == "B2"
    assert ingestor.map_chainage_to_block(50.0, scenario) is None

def test_kpi_evaluator():
    scenario = generate_synthetic_data()
    evaluator = KPIEvaluator(scenario)
    
    # Dummy schedule
    schedule = {
        "scheduled_jobs": [
            {"job_id": "J_ENG_1", "block_id": "B2", "start_time": 2, "end_time": 4, "tci": 80.0},
            {"job_id": "J_OHE_1", "block_id": "B2", "start_time": 2, "end_time": 4, "tci": 50.0} # Shadow block!
        ],
        "unscheduled_jobs": [],
        "total_closure_time": 2.0, # Since they ran exactly at the same time on the same block
        "train_delays": {"T1": 0.0, "T2": 2.0}
    }
    
    res = evaluator.evaluate(schedule)
    metrics = res["kpi_metrics"]
    
    # BUE should be 200% since 4 hours of work done in 2 hours of closure
    assert metrics["Block Utilization Efficiency (BUE) %"] == 200.0
    # 1 out of 1 block used was a shadow block
    assert metrics["Shadow Block Ratio (SBR) %"] == 100.0
    assert metrics["Consolidated Blocks (Shadow)"] == 1
    assert metrics["Punctuality Impact Index (PII) delays"] == 2.0
