import os
import json
import pytest
import hashlib
from fastapi.testclient import TestClient

from src.config import PluginConfig, SparkRailMode
from src.api.main import app
from src.api.advisory import AUDIT_REPO
from src.api.export_service import AdvisoryExportService
from src.data_pipeline.models import (
    Possession,
    PossessionStatus,
    Department,
    OptimizationRequest,
    Corridor,
    Platform,
    Junction,
    Signal,
    MaintenanceAsset,
    Conflict
)
from src.data_pipeline.adapters.cris_adapters import CRISAdapterConfig, TMSAdapter

client = TestClient(app)

def test_plugin_mode_detection(monkeypatch):
    """Verifies default mode is synthetic, and respects SPARKRAIL_MODE env var."""
    monkeypatch.delenv("SPARKRAIL_MODE", raising=False)
    assert PluginConfig.get_mode() == SparkRailMode.SYNTHETIC
    assert PluginConfig.is_synthetic() is True
    assert PluginConfig.is_shadow() is False
    assert PluginConfig.is_live() is False

    monkeypatch.setenv("SPARKRAIL_MODE", "shadow")
    assert PluginConfig.get_mode() == SparkRailMode.SHADOW
    assert PluginConfig.is_shadow() is True

    monkeypatch.setenv("SPARKRAIL_MODE", "live")
    assert PluginConfig.get_mode() == SparkRailMode.LIVE
    assert PluginConfig.is_live() is True

def test_live_mode_safety_gating(monkeypatch):
    """Verifies that live mode is rejected unless SPARKRAIL_LIVE_ENABLED=true and credentials exist."""
    monkeypatch.setenv("SPARKRAIL_MODE", "live")
    monkeypatch.delenv("SPARKRAIL_LIVE_ENABLED", raising=False)
    # Disabled by default
    assert PluginConfig.is_live_permitted() is False

    # Enabled without certs (or non-existent paths)
    monkeypatch.setenv("SPARKRAIL_LIVE_ENABLED", "true")
    monkeypatch.setenv("CRIS_MTLS_CERT_PATH", "/non/existent/cert.pem")
    assert PluginConfig.is_live_permitted() is False

def test_domain_models_instantiation():
    """Verifies all required day-one domain models can be instantiated with valid types."""
    corridor = Corridor(
        corridor_id="CORR-PRYJ-01",
        name="Subedarganj - Mirzapur Mainline",
        division_code="PRYJ",
        start_station_code="SFG",
        end_station_code="MZP",
        total_length_km=80.0
    )
    assert corridor.corridor_id == "CORR-PRYJ-01"

    platform = Platform(
        platform_id="PF-SFG-01",
        station_code="SFG",
        platform_number=1,
        length_meters=650.0
    )
    assert platform.platform_number == 1

    signal = Signal(
        id="SIG-SFG-01",
        block_id="B1",
        chainage_km=0.5,
        position={"x": 0, "y": 0, "z": 0},
        direction="UP"
    )
    assert signal.entity_type == "signal"

def test_possession_immutability():
    """Verifies that GRANTED and IN_PROGRESS possessions cannot be shifted or cancelled."""
    poss = Possession(
        id="POSS-TEST-01",
        possession_id="POSS-TEST-01",
        demand_id="DEM-01",
        track_section_id="B1",
        start_time=2.0,
        end_time=6.0,
        status=PossessionStatus.DRAFT,
        department=Department.ENGINEERING
    )

    # DRAFT can be modified
    poss.modify_window(3.0, 7.0)
    assert poss.start_time == 3.0
    assert poss.end_time == 7.0

    # Advance to SANCTIONED then GRANTED
    poss.transition_to(PossessionStatus.PROPOSED)
    poss.transition_to(PossessionStatus.SANCTIONED)
    poss.transition_to(PossessionStatus.GRANTED)
    assert poss.status == PossessionStatus.GRANTED

    # Modifying window on GRANTED must fail
    with pytest.raises(ValueError, match="strictly immutable"):
        poss.modify_window(4.0, 8.0)

    # Cancelling GRANTED must fail
    with pytest.raises(ValueError, match="Illegal possession status transition"):
        poss.transition_to(PossessionStatus.CANCELLED)

    # Transition to IN_PROGRESS
    poss.transition_to(PossessionStatus.IN_PROGRESS)
    assert poss.status == PossessionStatus.IN_PROGRESS

    # Modifying window on IN_PROGRESS must fail
    with pytest.raises(ValueError, match="strictly immutable"):
        poss.modify_window(5.0, 9.0)

    # Cancelling IN_PROGRESS must fail
    with pytest.raises(ValueError, match="Illegal possession status transition"):
        poss.transition_to(PossessionStatus.CANCELLED)

def test_advisory_export_service():
    """Verifies all export formats contain mandatory advisory notices, provenance, and limitations."""
    payload = {
        "optimization_run_id": "RUN-EXPORT-TEST",
        "division_code": "PRYJ",
        "input_snapshot_hash": "a" * 64,
        "geography": {"corridor": "Subedarganj (SFG) - Mirzapur (MZP)"},
        "primary_possession": {
            "possession_id": "POSS-01",
            "track_section_id": "B1",
            "scheduled_start": 1.0,
            "scheduled_end": 5.0,
            "chainage_start_km": 0.0,
            "chainage_end_km": 10.0,
            "department": "ENGINEERING"
        },
        "electrical_isolation": {"is_isolated": True, "elementary_section": "ES-B1"},
        "approval_state": {"CTPC": "APPROVED", "SR_DOM": "PENDING", "SECTION_CONTROLLER": "PENDING", "STATION_MASTER": "PENDING"}
    }

    # JSON export
    json_out = AdvisoryExportService.to_json(payload)
    parsed = json.loads(json_out)
    assert "ADVISORY ONLY: HUMAN APPROVAL REQUIRED" in parsed["advisory_notice"]
    assert "STATUTORY NOTICE: SparkRail is a decision-support advisory plugin only" in parsed["limitations"]
    assert parsed["optimization_run_id"] == "RUN-EXPORT-TEST"

    # CSV export
    csv_out = AdvisoryExportService.to_csv(payload)
    assert "# NOTICE: ADVISORY ONLY: HUMAN APPROVAL REQUIRED" in csv_out
    assert "POSS-01,B1,ENGINEERING,1.0,5.0,4.0" in csv_out

    # HTML export
    html_out = AdvisoryExportService.to_html(payload)
    assert "<!DOCTYPE html>" in html_out
    assert "ADVISORY ONLY: HUMAN APPROVAL REQUIRED" in html_out
    assert "CTPC (Traction)" in html_out
    assert "Sr. DOM (Operations)" in html_out
    assert "Section Controller" in html_out
    assert "Station Master" in html_out

def test_v1_health_and_export_endpoints():
    """Verifies GET /api/v1/health and GET /api/v1/advisory/export via HTTP client."""
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    h_data = res_health.json()
    assert h_data["status"] == "ok"
    assert h_data["mode"] in ("synthetic", "shadow", "live")
    assert h_data["geometry_schema_version"] == "1.0.0"
    assert h_data["statutory_safety_rules"]["advisory_only"] is True

    # Test export JSON
    res_json = client.get("/api/v1/advisory/export?format=json")
    assert res_json.status_code == 200
    assert "ADVISORY ONLY" in res_json.json()["advisory_notice"]

    # Test export CSV
    res_csv = client.get("/api/v1/advisory/export?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "# NOTICE: ADVISORY ONLY" in res_csv.text

    # Test export HTML
    res_html = client.get("/api/v1/advisory/export?format=html")
    assert res_html.status_code == 200
    assert "<!DOCTYPE html>" in res_html.text

def test_audit_chain_tamper_evidence():
    """Verifies that any mutation of audit chain records is detected by verify_integrity."""
    is_valid, _ = AUDIT_REPO.verify_integrity()
    assert is_valid is True

    # Artificially tamper with a record
    if len(AUDIT_REPO.chain) > 0:
        original = AUDIT_REPO.chain[0]["action"]
        AUDIT_REPO.chain[0]["action"] = "TAMPERED_ACTION"
        is_tampered, err = AUDIT_REPO.verify_integrity()
        assert is_tampered is False
        assert "Tampered hash" in err
        # Restore
        AUDIT_REPO.chain[0]["action"] = original
