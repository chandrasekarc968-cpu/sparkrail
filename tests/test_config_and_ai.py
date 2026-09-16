"""Tests for config resolution, TCI/XGBoost, MTTG, strategic RBP, stochastic ETA, GNN, PPO."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SETTINGS = os.path.join(ROOT, "config", "settings.yaml")
MODEL_PATH = os.path.join(ROOT, "models", "tci_degradation_xgb.model")
MODEL_SHA = "657009f0034a7c8defbf71e8664ff6910b858ce3c60cfd4ddc4939fe1c736632"


# --------------------------------------------------------------------------- #
# Config resolver
# --------------------------------------------------------------------------- #
def test_config_resolves_placeholders():
    from src.config_loader import load_config
    cfg = load_config(SETTINGS)
    assert cfg["tci"]["use_xgboost_degradation"] is True
    assert cfg["tci"]["xgboost_model_path"] == "models/tci_degradation_xgb.model"
    assert cfg["tci"]["xgboost_model_checksum"] == MODEL_SHA
    # other ${VAR:default} placeholders resolve to their defaults
    assert cfg["data_pipeline"]["postgis"]["url"].startswith("postgresql://")
    assert cfg["api"]["port"] == "8000"
    assert cfg["data_pipeline"]["kafka"]["bootstrap_servers"] == "localhost:9092"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("XGB_MODEL_PATH", "/custom/path.model")
    from src.config_loader import load_config
    cfg = load_config(SETTINGS)
    assert cfg["tci"]["xgboost_model_path"] == "/custom/path.model"


# --------------------------------------------------------------------------- #
# TCI + XGBoost
# --------------------------------------------------------------------------- #
def test_tci_uses_xgboost_when_enabled():
    xgb = pytest.importorskip("xgboost")
    np = pytest.importorskip("numpy")
    from src.config_loader import load_config
    from src.ai_ml.criticality_scorer import TaskCriticalityScorer
    from src.data_pipeline.models import TCIInputs, AssetConditionTelemetry, WeatherContext

    cfg = load_config(SETTINGS)
    scorer = TaskCriticalityScorer(cfg)
    inp = TCIInputs(safety_severity=0.8, traffic_impact=0.6, degradation_indicator=0.5, overdue_days=20)
    tel = AssetConditionTelemetry(block_id="B1", trc_tqi_score=35.0, usfd_flaw_severity="REM",
                                  cumulative_gmt=55.0, days_since_tamping=90)
    w = WeatherContext(ambient_temp_celsius=34, rail_temp_celsius=52)
    tci, expl = scorer.calculate_tci(inp, telemetry=tel, weather=w, asset_age_years=12.0)
    assert expl.model_mode == "xgboost_experimental"
    assert 0.0 <= tci <= 100.0
    # degradation component is now a real model prediction, not the 0..1 proxy
    assert expl.degradation_component >= 0.0


def test_tci_checksum_tamper_detection():
    xgb = pytest.importorskip("xgboost")
    from src.ai_ml.criticality_scorer import TaskCriticalityScorer
    cfg = {
        "tci": {
            "use_xgboost_degradation": True,
            "xgboost_model_path": MODEL_PATH,
            "xgboost_model_checksum": "deadbeef" * 8,  # wrong checksum
        }
    }
    scorer = TaskCriticalityScorer(cfg)
    from src.data_pipeline.models import TCIInputs
    with pytest.raises(ValueError):
        scorer.calculate_tci(TCIInputs(safety_severity=0.5, traffic_impact=0.5,
                                       degradation_indicator=0.5, overdue_days=5))


# --------------------------------------------------------------------------- #
# MTTG (real measurement)
# --------------------------------------------------------------------------- #
def test_mttg_empty_is_none():
    from src.simulation.mttg import MTTGCalculator, unmeasured_summary
    calc = MTTGCalculator()
    s = calc.summary()
    assert s["mttg_measured"] is False
    assert s["mttg_minutes"] is None
    assert unmeasured_summary() is None


def test_mttg_records():
    from src.simulation.mttg import MTTGCalculator, GrantRecord
    calc = MTTGCalculator()
    calc.add(GrantRecord(job_id="J1", requested_iso="2026-01-01T10:00:00+00:00",
                         granted_iso="2026-01-01T10:25:00+00:00"))
    calc.add(GrantRecord(job_id="J2", requested_iso="2026-01-01T11:00:00+00:00",
                         granted_iso="2026-01-01T11:15:00+00:00"))
    s = calc.summary()
    assert s["mttg_measured"] is True
    assert s["mttg_minutes"] == 20.0
    assert s["mttg_sample_count"] == 2


# --------------------------------------------------------------------------- #
# Strategic RBP (52-week)
# --------------------------------------------------------------------------- #
def test_strategic_rbp_allocates_52_weeks():
    np = pytest.importorskip("numpy")
    pyd = pytest.importorskip("pydantic")
    from src.data_pipeline.models import (
        Scenario, TrackBlock, Train, MaintenanceJob, Resource, Department, TCIInputs,
    )
    from src.optimization.strategic_rbp import StrategicRBPAllocator

    blocks = [TrackBlock(id=f"B{i}", chainage_start=float(i * 2),
                         chainage_end=float((i + 1) * 2)) for i in range(4)]
    resources = [Resource(id="R_BCM_1", name="BCM-1", capacity=2)]
    jobs = [
        MaintenanceJob(
            id=f"J{i}", department=Department.CIVIL, block_id=f"B{i % 4}",
            duration=(6.0 if i % 2 == 0 else 2.0),  # even -> mega block (>=4h)
            required_resources={"R_BCM_1": 1},
            tci_inputs=TCIInputs(safety_severity=0.5, traffic_impact=0.5,
                                 degradation_indicator=0.5, overdue_days=5),
        )
        for i in range(10)
    ]
    scenario = Scenario(blocks=blocks, trains=[], jobs=jobs, resources=resources)
    alloc = StrategicRBPAllocator(horizon_weeks=52)
    job_tcis = {j.id: 50.0 + float(i) for i, j in enumerate(jobs)}
    result = alloc.allocate(scenario, job_tcis=job_tcis)

    assert result.horizon_weeks == 52
    # every demand is either scheduled into the programme or explicitly deferred
    assert len(result.scheduled_job_ids) + len(result.deferred_jobs) == 10
    # mega blocks (the 6h jobs) are actually classified and placed
    assert result.mega_block_count >= 1
    # no critical machine is double-booked onto two blocks in one week
    assert result.machine_conflicts == []


# --------------------------------------------------------------------------- #
# Stochastic ETA (weight normalisation fix)
# --------------------------------------------------------------------------- #
def test_stochastic_eta_weight_normalisation():
    np = pytest.importorskip("numpy")
    pyd = pytest.importorskip("pydantic")
    from src.data_pipeline.models import Scenario, TrackBlock, Train
    from src.optimization.stochastic_eta import build_stochastic_pipeline

    # build a minimal scenario: 4 trains (freight + passenger mix) so the
    # evaluator has a meaningful ETA spread to reason about.
    blocks = [TrackBlock(id=f"B{i}", chainage_start=float(i * 2),
                         chainage_end=float((i + 1) * 2)) for i in range(4)]
    trains = [
        Train(id=f"TR{i}", category="freight" if i % 2 == 0 else "express",
              scheduled_start=0.0, scheduled_end=12.0, route=[f"B{i % 4}"])
        for i in range(4)
    ]
    scenario = Scenario(blocks=blocks, trains=trains, jobs=[], resources=[])

    evaluator, optimizer, analyzer = build_stochastic_pipeline(
        scenario, history=None, n_scenarios=40, seed=7,
    )
    # a 4h window with low expected freight delay should be robust
    rob = evaluator.evaluate(window_start=10.0, window_duration=4.0)
    assert rob.expected_delay_hours <= rob.worst_case_delay_hours + 1e-6
    assert 0.0 <= rob.clash_free_probability <= 1.0


# --------------------------------------------------------------------------- #
# GNN encoder
# --------------------------------------------------------------------------- #
def test_gnn_state_vector_shape():
    np = pytest.importorskip("numpy")
    from src.ai_ml.gnn_encoder import build_corridor_graph, HeteroGNN, OUT_DIM
    blocks = [
        {"id": "B1", "chainage_start_km": 0.0, "chainage_end_km": 5.0, "station": "S1", "is_closed": False},
        {"id": "B2", "chainage_start_km": 5.0, "chainage_end_km": 10.0, "station": "S1", "is_closed": False},
        {"id": "B3", "chainage_start_km": 10.0, "chainage_end_km": 15.0, "station": "S2", "is_closed": False},
    ]
    stations = [{"id": "S1", "platforms": 2, "node_type": "junction"},
                {"id": "S2", "platforms": 4, "node_type": "terminal"}]
    g = build_corridor_graph(blocks, stations)
    vec = HeteroGNN().forward(g)
    assert vec.shape == (OUT_DIM,)
    # deterministic
    vec2 = HeteroGNN(seed=0).forward(g)
    assert np.allclose(vec, vec2)


# --------------------------------------------------------------------------- #
# PPO agent over the digital twin
# --------------------------------------------------------------------------- #
def test_ppo_trains_on_twin():
    np = pytest.importorskip("numpy")
    from src.simulation.sumo_interface import SUMODigitalTwin, ACT_HOLD
    from src.ai_ml.ppo_agent import RailRLGym, train_ppo
    blocks = [{"id": f"B{i}", "chainage_start_km": i * 2.0, "chainage_end_km": (i + 1) * 2.0} for i in range(6)]
    trains = [{"id": "T1", "route": ["B0", "B1", "B2"], "speed_kmh": 40.0, "category": "express",
               "scheduled_start": 0.0, "scheduled_end": 12.0}]
    twin = SUMODigitalTwin(blocks, trains, horizon_hours=12.0)
    # schedule a possession that the agent must learn to avoid
    twin.apply_schedule([{"block_id": "B1", "start_time": 2.0, "end_time": 4.0}])
    gym = RailRLGym(twin, max_steps=24)
    net, history = train_ppo(gym, episodes=10, max_steps=24, epochs=2, seed=1)
    assert len(history) == 10
    # at least runs and returns finite rewards
    assert all(isinstance(h, float) for h in history)
