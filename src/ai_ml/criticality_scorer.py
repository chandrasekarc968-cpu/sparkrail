from typing import Dict, Any, Tuple
import math
from src.data_pipeline.models import TCIInputs

class TaskCriticalityScorer:
    """
    Computes the Task Criticality Index (TCI) based on configurable weights.
    TCI = w1*safety_risk + w2*delay_capacity_impact + w3*degradation_velocity + w4*overdue_penalty
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        weights = config.get("tci", {}).get("weights", {})
        
        self.w_safety = weights.get("safety_risk", 0.4)
        self.w_delay = weights.get("delay_capacity_impact", 0.3)
        self.w_degrad = weights.get("degradation_velocity", 0.2)
        self.w_overdue = weights.get("overdue_penalty", 0.1)
        
        self._validate_weights()
        
        self.use_xgb = config.get("tci", {}).get("use_xgboost_degradation", False)
        
    def _validate_weights(self) -> None:
        total = self.w_safety + self.w_delay + self.w_degrad + self.w_overdue
        if not math.isclose(total, 1.0, rel_tol=1e-5):
            raise ValueError(f"TCI weights must sum to 1.0. Current sum is {total}")

    def _compute_overdue_score(self, days: int) -> float:
        """Non-linear penalty for overdue days. Maxes out at 1.0 for 30+ days."""
        if days <= 0:
            return 0.0
        return min(1.0, math.log1p(days) / math.log1p(30))

    def _get_xgb_degradation(self, inputs: TCIInputs) -> float:
        """Retrieves degradation from XGBoost if enabled and trained."""
        if self.use_xgb:
            raise NotImplementedError("XGBoost degradation model is not trained. Provide a trained model or set 'use_xgboost_degradation' to false.")
        return inputs.degradation_indicator

    def calculate_tci(self, inputs: TCIInputs) -> Tuple[float, Dict[str, float]]:
        """
        Calculates the normalized TCI [0-100] and returns an explanation dictionary.
        """
        # Ensure inputs are normalized [0-1]
        s_safety = max(0.0, min(1.0, inputs.safety_severity))
        s_delay = max(0.0, min(1.0, inputs.traffic_impact))
        s_degrad = max(0.0, min(1.0, self._get_xgb_degradation(inputs)))
        s_overdue = self._compute_overdue_score(inputs.overdue_days)
        
        raw_score = (
            self.w_safety * s_safety +
            self.w_delay * s_delay +
            self.w_degrad * s_degrad +
            self.w_overdue * s_overdue
        )
        
        final_tci = raw_score * 100.0
        
        explanation = {
            "safety_component": self.w_safety * s_safety * 100,
            "delay_component": self.w_delay * s_delay * 100,
            "degradation_component": self.w_degrad * s_degrad * 100,
            "overdue_component": self.w_overdue * s_overdue * 100,
            "raw_inputs": {
                "safety_severity": s_safety,
                "traffic_impact": s_delay,
                "degradation_indicator": s_degrad,
                "overdue_days": inputs.overdue_days
            }
        }
        
        return final_tci, explanation
