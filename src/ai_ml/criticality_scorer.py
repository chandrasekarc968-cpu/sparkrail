from typing import Dict, Any, Tuple, Optional
import math
import os
from src.data_pipeline.models import TCIInputs, TCIExplanation

class TaskCriticalityScorer:
    """
    Computes the Task Criticality Index (TCI) based on configurable, validated weights:
    TCI = w_safety * safety_risk + w_delay * delay_capacity_impact + w_degrad * degradation_velocity + w_overdue * overdue_penalty
    All components and final TCI are strictly normalized to [0, 100].
    """
    
    MODEL_VERSION = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        tci_cfg = self.config.get("tci", {})
        weights = tci_cfg.get("weights", {})
        
        self.w_safety = float(weights.get("safety_risk", 0.4))
        self.w_delay = float(weights.get("delay_capacity_impact", 0.3))
        self.w_degrad = float(weights.get("degradation_velocity", 0.2))
        self.w_overdue = float(weights.get("overdue_penalty", 0.1))
        
        self._validate_weights()
        
        self.use_xgb = bool(tci_cfg.get("use_xgboost_degradation", False))
        self.xgb_model_path = tci_cfg.get("xgboost_model_path", "models/tci_degradation_xgb.model")
        self._xgb_model = None

    def _validate_weights(self) -> None:
        total = self.w_safety + self.w_delay + self.w_degrad + self.w_overdue
        if not math.isclose(total, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError(f"TCI weights must sum to 1.0. Current sum is {total:.5f}")
        for name, w in [
            ("safety_risk", self.w_safety),
            ("delay_capacity_impact", self.w_delay),
            ("degradation_velocity", self.w_degrad),
            ("overdue_penalty", self.w_overdue),
        ]:
            if w < 0.0 or w > 1.0:
                raise ValueError(f"Weight '{name}' must be between 0.0 and 1.0. Got {w}")

    def _init_xgb_model(self) -> None:
        """Ensures an untrained or missing model does not silently perform inference."""
        if not os.path.exists(self.xgb_model_path):
            raise NotImplementedError(
                f"Untrained XGBoost inference prevented. Model file '{self.xgb_model_path}' not found. "
                "Provide a trained model artifact or set 'use_xgboost_degradation' to false."
            )
        try:
            import xgboost as xgb
            self._xgb_model = xgb.XGBRegressor()
            self._xgb_model.load_model(self.xgb_model_path)
        except Exception as e:
            raise NotImplementedError(
                f"Failed to load trained XGBoost model from '{self.xgb_model_path}': {e}. "
                "Untrained inference is strictly prevented."
            ) from e

    def _compute_overdue_score_100(self, days: int) -> float:
        """Non-linear penalty for overdue days normalized to [0, 100]. Maxes out at 100 for 30+ days."""
        if days <= 0:
            return 0.0
        normalized_ratio = min(1.0, math.log1p(days) / math.log1p(30))
        return normalized_ratio * 100.0

    def _get_degradation_score_100(self, inputs: TCIInputs) -> float:
        """Retrieves degradation normalized to [0, 100]."""
        if self.use_xgb:
            if self._xgb_model is None:
                self._init_xgb_model()
            pred = float(self._xgb_model.predict([[inputs.degradation_indicator]])[0])
            return max(0.0, min(100.0, pred * 100.0))
        
        # Rule-based degradation
        raw = max(0.0, min(1.0, inputs.degradation_indicator))
        return raw * 100.0

    def calculate_tci(self, inputs: TCIInputs) -> Tuple[float, TCIExplanation]:
        """
        Calculates the normalized TCI [0-100] and returns a detailed TCIExplanation object.
        """
        s_safety_100 = max(0.0, min(1.0, inputs.safety_severity)) * 100.0
        s_delay_100 = max(0.0, min(1.0, inputs.traffic_impact)) * 100.0
        s_degrad_100 = self._get_degradation_score_100(inputs)
        s_overdue_100 = self._compute_overdue_score_100(inputs.overdue_days)

        comp_safety = self.w_safety * s_safety_100
        comp_delay = self.w_delay * s_delay_100
        comp_degrad = self.w_degrad * s_degrad_100
        comp_overdue = self.w_overdue * s_overdue_100

        final_tci = comp_safety + comp_delay + comp_degrad + comp_overdue
        final_tci = round(max(0.0, min(100.0, final_tci)), 2)

        model_mode = "xgboost_experimental" if self.use_xgb else "rule_based"
        formula = (
            f"TCI = {self.w_safety:.2f}*{s_safety_100:.1f} (Safety) + "
            f"{self.w_delay:.2f}*{s_delay_100:.1f} (Delay) + "
            f"{self.w_degrad:.2f}*{s_degrad_100:.1f} (Degradation) + "
            f"{self.w_overdue:.2f}*{s_overdue_100:.1f} (Overdue)"
        )

        explanation = TCIExplanation(
            safety_component=round(comp_safety, 2),
            delay_component=round(comp_delay, 2),
            degradation_component=round(comp_degrad, 2),
            overdue_component=round(comp_overdue, 2),
            raw_inputs=inputs,
            formula_breakdown=formula,
            model_mode=model_mode,
            model_version=self.MODEL_VERSION
        )

        return final_tci, explanation
