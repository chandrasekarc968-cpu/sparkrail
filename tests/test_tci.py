import pytest
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.data_pipeline.models import TCIInputs

def test_tci_weight_validation_success():
    """Valid weights summing to 1.0 succeed."""
    scorer = TaskCriticalityScorer({
        "tci": {"weights": {"safety_risk": 0.4, "delay_capacity_impact": 0.3, "degradation_velocity": 0.2, "overdue_penalty": 0.1}}
    })
    assert scorer.w_safety == 0.4
    assert scorer.w_delay == 0.3
    assert scorer.w_degrad == 0.2
    assert scorer.w_overdue == 0.1

def test_tci_weight_validation_failure_sum():
    """Weights not summing to 1.0 must raise ValueError."""
    with pytest.raises(ValueError, match="TCI weights must sum to 1.0"):
        TaskCriticalityScorer({
            "tci": {"weights": {"safety_risk": 0.5, "delay_capacity_impact": 0.5, "degradation_velocity": 0.5, "overdue_penalty": 0.5}}
        })

def test_tci_weight_validation_negative():
    """Negative weights must raise ValueError."""
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        TaskCriticalityScorer({
            "tci": {"weights": {"safety_risk": 1.2, "delay_capacity_impact": -0.2, "degradation_velocity": 0.0, "overdue_penalty": 0.0}}
        })

def test_tci_normalization_bounds():
    """Scores are strictly bounded to [0, 100]."""
    scorer = TaskCriticalityScorer()
    
    # Minimum inputs
    min_inputs = TCIInputs(safety_severity=0.0, traffic_impact=0.0, degradation_indicator=0.0, overdue_days=0)
    score_min, expl_min = scorer.calculate_tci(min_inputs)
    assert score_min == 0.0
    assert expl_min.safety_component == 0.0
    assert expl_min.overdue_component == 0.0

    # Maximum inputs
    max_inputs = TCIInputs(safety_severity=1.0, traffic_impact=1.0, degradation_indicator=1.0, overdue_days=100)
    score_max, expl_max = scorer.calculate_tci(max_inputs)
    assert 99.9 <= score_max <= 100.0

def test_tci_overdue_penalty_curve():
    """Overdue penalty increases non-linearly with days overdue."""
    scorer = TaskCriticalityScorer()
    
    inputs_0 = TCIInputs(safety_severity=0.5, traffic_impact=0.5, degradation_indicator=0.5, overdue_days=0)
    inputs_7 = TCIInputs(safety_severity=0.5, traffic_impact=0.5, degradation_indicator=0.5, overdue_days=7)
    inputs_30 = TCIInputs(safety_severity=0.5, traffic_impact=0.5, degradation_indicator=0.5, overdue_days=30)
    inputs_60 = TCIInputs(safety_severity=0.5, traffic_impact=0.5, degradation_indicator=0.5, overdue_days=60)
    
    s0, e0 = scorer.calculate_tci(inputs_0)
    s7, e7 = scorer.calculate_tci(inputs_7)
    s30, e30 = scorer.calculate_tci(inputs_30)
    s60, e60 = scorer.calculate_tci(inputs_60)
    
    assert e0.overdue_component == 0.0
    assert e7.overdue_component > e0.overdue_component
    assert e30.overdue_component > e7.overdue_component
    # 30 and 60 days max out at full penalty
    assert e60.overdue_component == e30.overdue_component

def test_tci_explanation_completeness():
    """Explanation contains all required components, model mode, and version."""
    scorer = TaskCriticalityScorer()
    inputs = TCIInputs(safety_severity=0.8, traffic_impact=0.6, degradation_indicator=0.7, overdue_days=15)
    tci, explanation = scorer.calculate_tci(inputs)
    
    assert explanation.safety_component > 0.0
    assert explanation.delay_component > 0.0
    assert explanation.degradation_component > 0.0
    assert explanation.overdue_component > 0.0
    assert explanation.model_mode == "rule_based"
    assert explanation.model_version == "1.0.0"
    assert "TCI = " in explanation.formula_breakdown
    assert explanation.raw_inputs.safety_severity == 0.8
    # Sum of components equals final score
    component_sum = (
        explanation.safety_component +
        explanation.delay_component +
        explanation.degradation_component +
        explanation.overdue_component
    )
    assert abs(component_sum - tci) <= 0.05

def test_tci_deterministic_output():
    """Identical inputs yield exact identical scores across repeated runs."""
    scorer1 = TaskCriticalityScorer()
    scorer2 = TaskCriticalityScorer()
    inputs = TCIInputs(safety_severity=0.45, traffic_impact=0.65, degradation_indicator=0.85, overdue_days=12)
    
    tci1, expl1 = scorer1.calculate_tci(inputs)
    tci2, expl2 = scorer2.calculate_tci(inputs)
    
    assert tci1 == tci2
    assert expl1.safety_component == expl2.safety_component

def test_tci_untrained_xgboost_guard():
    """Attempting XGBoost inference without trained model raises NotImplementedError."""
    scorer = TaskCriticalityScorer({
        "tci": {"use_xgboost_degradation": True, "xgboost_model_path": "non_existent_path.model"}
    })
    inputs = TCIInputs(safety_severity=0.5, traffic_impact=0.5, degradation_indicator=0.5, overdue_days=0)
    with pytest.raises(NotImplementedError, match="Untrained XGBoost inference prevented"):
        scorer.calculate_tci(inputs)

def test_tci_6_factor_ahp_matrix():
    """Valid 6x6 AHP comparison matrix derives normalized 6 weights summing to 1.0."""
    # 6 criteria: safety, delay, degradation, overdue, urgency, confidence
    matrix = [
        [1.0, 1.5, 2.0, 3.0, 3.0, 3.0],
        [1/1.5, 1.0, 1.5, 2.0, 2.5, 2.5],
        [1/2.0, 1/1.5, 1.0, 1.5, 2.0, 2.0],
        [1/3.0, 1/2.0, 1/1.5, 1.0, 1.5, 1.5],
        [1/3.0, 1/2.5, 1/2.0, 1/1.5, 1.0, 1.0],
        [1/3.0, 1/2.5, 1/2.0, 1/1.5, 1.0, 1.0],
    ]
    scorer = TaskCriticalityScorer({"tci": {"ahp_matrix": matrix}})
    assert scorer.w_urgency > 0.0
    assert scorer.w_confidence > 0.0
    total_w = (
        scorer.w_safety + scorer.w_delay + scorer.w_degrad +
        scorer.w_overdue + scorer.w_urgency + scorer.w_confidence
    )
    assert abs(total_w - 1.0) < 1e-4

    inputs = TCIInputs(
        safety_severity=0.8,
        traffic_impact=0.6,
        degradation_indicator=0.5,
        overdue_days=10,
        inspection_urgency=0.9,
        data_confidence=0.7
    )
    score, expl = scorer.calculate_tci(inputs)
    assert 0.0 <= score <= 100.0
    assert expl.inspection_urgency_component > 0.0
    assert expl.data_confidence_penalty > 0.0

def test_tci_conservative_imputation_missing_data():
    """Missing USFD flaw depth and traffic metrics must trigger conservative upper-bound imputation."""
    scorer = TaskCriticalityScorer()
    
    # Evidence with USFD flaw but missing flaw_depth_percent and missing traffic
    evidence_missing = {
        "is_usfd_flaw": True,
        "is_mainline": True,
        # flaw_depth_percent is omitted
        # trains_per_day is omitted
        "cumulative_gmt": 40.0,
        "days_overdue": 5
    }
    score, expl = scorer.calculate_tci_from_evidence(evidence_missing)
    
    # Missing flaw depth must conservatively be imputed to at least 0.85
    assert expl.raw_inputs.safety_severity >= 0.85
    # Missing traffic on mainline conservatively imputed to at least 0.60
    assert expl.raw_inputs.traffic_impact >= 0.60
    # Data confidence must be degraded due to missing fields
    assert expl.raw_inputs.data_confidence < 1.0
    # Overall score must reflect high priority
    assert score >= 55.0

def test_tci_extreme_risk_imr_defect():
    """Immediate Removal (IMR) defect must receive maximum safety severity (1.0)."""
    scorer = TaskCriticalityScorer()
    evidence_imr = {
        "is_imr_defect": True,
        "trains_per_day": 80,
        "cumulative_gmt": 35.0,
        "days_overdue": 0
    }
    score, expl = scorer.calculate_tci_from_evidence(evidence_imr)
    assert expl.raw_inputs.safety_severity == 1.0
    # With safety weight 0.40, safety component alone must be 40.0
    assert expl.safety_component == 40.0

def test_tci_statutory_inspection_urgency():
    """Statutory inspection due sets inspection_urgency to 1.0."""
    scorer = TaskCriticalityScorer()
    evidence = {
        "is_statutory_inspection_due": True,
        "is_mainline": True,
        "days_overdue": 3
    }
    _, expl = scorer.calculate_tci_from_evidence(evidence)
    assert expl.raw_inputs.inspection_urgency == 1.0

