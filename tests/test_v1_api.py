"""
Tests for Canonical Versioned API /api/v1/ and Cryptographic SHA-256 Audit Chaining.
Verifies all Phase 9 endpoints, role-based approval, mandatory override reasons,
and cryptographic hash-chain integrity.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_v1_optimization_runs_and_recommendations():
    """Tests POST and GET for /api/v1/optimization/runs and recommendation workflow."""
    # 1. Create optimization run
    run_payload = {
        "request_id": "REQ-V1-TEST-001",
        "division_code": "PRYJ",
        "planning_horizon_hours": 24,
        "input_snapshot_hash": "a1b2c3d4e5f67890",
        "freeze_week1": False
    }
    resp = client.post("/api/v1/optimization/runs", json=run_payload)
    assert resp.status_code == 200, resp.text
    run_data = resp.json()
    assert "run_id" in run_data
    run_id = run_data["run_id"]
    assert run_data["solver_status"] in ("OPTIMAL", "FEASIBLE")
    assert len(run_data["scheduled_demands"]) > 0

    # 2. Retrieve optimization run
    get_resp = client.get(f"/api/v1/optimization/runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["run_id"] == run_id

    # 3. Retrieve first recommendation
    rec_id = f"REC-{run_data['scheduled_demands'][0]}"
    rec_resp = client.get(f"/api/v1/recommendations/{rec_id}")
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["recommendation_id"] == rec_id
    assert rec_data["status"] == "PROPOSED"
    assert "expires_at" in rec_data

    # 4. Approve recommendation
    app_resp = client.post(
        f"/api/v1/recommendations/{rec_id}/approve",
        json={
            "role": "CTPC",
            "approver_id": "CTPC_OFFICER_01",
            "comments": "Approved for corridor execution"
        }
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"
    assert app_resp.json()["recommendation"]["primary_possession"]["status"] == "SANCTIONED"

    # 5. Operational Override with mandatory justification
    over_resp = client.post(
        f"/api/v1/recommendations/{rec_id}/override",
        json={
            "override_id": "OVR-001",
            "recommendation_id": rec_id,
            "user_id": "SR_DOM_OFFICER",
            "role": "SR_DOM",
            "reason_code": "VIP_MOVEMENT",
            "justification": "Vande Bharat special movement requires corridor clearance",
            "previous_schedule": {},
            "overridden_schedule": {}
        }
    )
    assert over_resp.status_code == 200
    assert over_resp.json()["status"] == "OVERRIDDEN"

    # 6. Override rejection when justification is too short
    fail_over = client.post(
        f"/api/v1/recommendations/{rec_id}/override",
        json={
            "override_id": "OVR-002",
            "recommendation_id": rec_id,
            "user_id": "SR_DOM_OFFICER",
            "role": "SR_DOM",
            "reason_code": "VIP_MOVEMENT",
            "justification": "no",
            "previous_schedule": {},
            "overridden_schedule": {}
        }
    )
    assert fail_over.status_code in (400, 422)


def test_v1_possession_schedule_payload():
    """Tests the comprehensive CRIS BDMS possession schedule payload."""
    resp = client.post(
        "/api/v1/optimization/possession-schedule",
        json={
            "request_id": "REQ-V1-SCHED-01",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "deadbeef1234"
        }
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "optimization_run_id" in data
    assert data["division_code"] == "PRYJ"
    assert "planning_window" in data
    assert "computed_metrics" in data
    assert "recommended_blocks" in data
    assert "primary_possession" in data
    assert "associated_shadow_ids" in data
    assert "geography" in data
    assert "schedule" in data
    assert "electrical_isolation" in data
    assert "machines" in data
    assert "crews" in data
    assert "train_regulation_plan" in data
    assert "safety_validation_result" in data
    assert "approval_state" in data
    assert "provenance_metadata" in data


def test_v1_disruptions_and_tsl():
    """Tests POST /api/v1/disruptions for localized rescheduling."""
    disrupt_payload = {
        "event_id": "DISRUPT-V1-001",
        "event_type": "TRAIN_DELAY",
        "severity": "MAJOR",
        "affected_block_ids": ["B2"],
        "delay_minutes": 45.0,
        "corridor_radius_km": 30.0
    }
    resp = client.post("/api/v1/disruptions", json=disrupt_payload)
    assert resp.status_code == 200, resp.text
    res_data = resp.json()
    assert res_data["is_successful"] is True
    assert "runtime_seconds" in res_data
    assert len(res_data["affected_corridor_chainage_km"]) == 2
    assert "advisory_recommendation" in res_data


def test_v1_sha256_audit_chain_integrity():
    """Tests that the audit chain is cryptographically intact and passes SHA-256 verification."""
    # Query audit chain
    resp = client.get("/api/v1/advisory/audit")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) > 0

    # Verify SHA-256 chain integrity
    verify_resp = client.get("/api/v1/advisory/audit/verify")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["is_intact"] is True, f"Hash chain verification failed: {verify_data.get('error')}"
    assert verify_data["chain_length"] >= len(events)


def test_v1_network_geometry_and_kpis():
    """Tests GET /api/v1/network/geometry and /api/v1/kpis."""
    geom_resp = client.get("/api/v1/network/geometry")
    assert geom_resp.status_code == 200
    geom_data = geom_resp.json()
    assert "blocks" in geom_data
    assert "tracks" in geom_data

    kpi_resp = client.get("/api/v1/kpis")
    assert kpi_resp.status_code == 200
    kpi_data = kpi_resp.json()
    assert "bue_percent" in kpi_data
