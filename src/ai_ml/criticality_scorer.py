import math
import os
import hashlib
from typing import Dict, Any, Tuple, Optional, List
from src.data_pipeline.models import TCIInputs, TCIExplanation

class TaskCriticalityScorer:
    """
    Computes the Task Criticality Index (TCI) based on configurable, validated weights:
    TCI = w_safety * safety_risk + w_delay * delay_capacity_impact + w_degrad * degradation_velocity + w_overdue * overdue_penalty
    All components and final TCI are strictly normalized to [0, 100].
    """
    
    MODEL_VERSION = "1.0.0"
    FEATURE_SCHEMA_VERSION = "1.0.0"

    # Standard Indian Railways Analytic Hierarchy Process (AHP) baseline weights
    AHP_BASELINE_WEIGHTS = {
        "safety_risk": 0.40,
        "delay_capacity_impact": 0.30,
        "degradation_velocity": 0.20,
        "overdue_penalty": 0.10
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        tci_cfg = self.config.get("tci", {})
        
        # Load weights from config, AHP matrix, or standard baseline
        if "ahp_matrix" in tci_cfg:
            weights = self._derive_weights_from_ahp(tci_cfg["ahp_matrix"])
        else:
            weights = tci_cfg.get("weights", self.AHP_BASELINE_WEIGHTS)
        
        self.w_safety = float(weights.get("safety_risk", 0.40))
        self.w_delay = float(weights.get("delay_capacity_impact", 0.30))
        self.w_degrad = float(weights.get("degradation_velocity", 0.20))
        self.w_overdue = float(weights.get("overdue_penalty", 0.10))
        
        self._validate_weights()
        
        self.use_xgb = bool(tci_cfg.get("use_xgboost_degradation", False))
        self.xgb_model_path = tci_cfg.get("xgboost_model_path", "models/tci_degradation_xgb.model")
        self.expected_xgb_checksum = tci_cfg.get("xgboost_model_checksum", None)
        self._xgb_model = None

    def _derive_weights_from_ahp(self, matrix: List[List[float]]) -> Dict[str, float]:
        """
        Derives normalized priority weights from an AHP 4x4 pairwise comparison matrix.
        Criteria order: [safety_risk, delay_impact, degradation_velocity, overdue_penalty]
        """
        if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
            return self.AHP_BASELINE_WEIGHTS

        # Approximate principal eigenvector via normalized geometric mean
        geom_means = [math.prod(row) ** 0.25 for row in matrix]
        total_geom = sum(geom_means)
        if total_geom <= 0:
            return self.AHP_BASELINE_WEIGHTS
        
        norm_weights = [round(gm / total_geom, 4) for gm in geom_means]
        # Ensure exact sum to 1.0
        diff = 1.0 - sum(norm_weights)
        norm_weights[0] += diff

        return {
            "safety_risk": norm_weights[0],
            "delay_capacity_impact": norm_weights[1],
            "degradation_velocity": norm_weights[2],
            "overdue_penalty": norm_weights[3]
        }

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
        
        # Verify model checksum if specified in configuration
        if self.expected_xgb_checksum:
            with open(self.xgb_model_path, "rb") as f:
                actual_sha = hashlib.sha256(f.read()).hexdigest()
            if actual_sha != self.expected_xgb_checksum:
                raise ValueError(
                    f"XGBoost model checksum verification failed! Expected {self.expected_xgb_checksum}, got {actual_sha}"
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

    def calculate_tci_from_evidence(self, evidence: Dict[str, Any]) -> Tuple[float, TCIExplanation]:
        """
        Synthesizes multi-attribute physical evidence into TCIInputs with conservative
        missing-data imputation. Safety-critical defects cannot receive a low score
        solely because of missing numerical readings.
        """
        # 1. Safety Score from USFD, IMR, Track Geometry
        safety_severity = 0.2  # baseline routine
        if evidence.get("is_imr_defect", False):
            safety_severity = max(safety_severity, 0.95)  # Immediate Removal defect
        elif evidence.get("is_usfd_flaw", False):
            flaw_depth = evidence.get("flaw_depth_percent", None)
            if flaw_depth is not None:
                safety_severity = max(safety_severity, min(1.0, flaw_depth / 100.0))
            else:
                # Conservative upper-bound imputation when numerical depth is missing
                safety_severity = max(safety_severity, 0.85)

        if evidence.get("speed_restriction_imposed", False):
            safety_severity = max(safety_severity, 0.80)

        # 2. Delay Impact from Traffic Density & Centrality
        traffic_impact = 0.3
        if evidence.get("is_junction_block", False):
            traffic_impact = max(traffic_impact, 0.85)
        train_count = evidence.get("trains_per_day", 50)
        traffic_impact = max(traffic_impact, min(1.0, train_count / 120.0))

        # 3. Degradation Velocity from GMT & Asset Age
        degradation = 0.25
        gmt = evidence.get("cumulative_gmt", 20.0)
        degradation = max(degradation, min(1.0, gmt / 80.0))

        # 4. Overdue Days
        overdue_days = int(evidence.get("days_overdue", 0))

        inputs = TCIInputs(
            safety_severity=round(safety_severity, 3),
            traffic_impact=round(traffic_impact, 3),
            degradation_indicator=round(degradation, 3),
            overdue_days=overdue_days
        )
        return self.calculate_tci(inputs)
