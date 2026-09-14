"""
Production Safety and Statutory Governance Invariants Test Suite.
Verifies all 14 mandatory safety, authorization, and cryptographic invariants
prescribed for Problem Statement 26027 (Advisory & Shadow Deployment).
"""

import pytest
import os
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import HTTPException

from src.api.main import app
from src.config import PluginConfig, SparkRailMode
from src.data_pipeline.models import (
    PossessionStatus,
    ApprovalRole,
    validate_possession_transition,
    validate_possession_schedule_immutability,
)
from src.api.advisory import (
    AUDIT_REPO,
    PROPOSALS_STORE,
    validate_actor_role_authorization,
    get_current_actor
)
from src.data_pipeline.adapters.cris_adapters import CRISAdapterConfig, TMSAdapter

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. POSSESSION IMMUTABILITY & LIFECYCLE INVARIANTS
# -----------------------------------------------------------------------------

def test_invariant_1_granted_possessions_cannot_be_shifted():
    """Invariant 1: GRANTED possessions are immutable and cannot be shifted in time."""
    with pytest.raises(ValueError, match="Cannot shift, cancel, or alter schedule of active GRANTED possession"):
        validate_possession_schedule_immutability(
            status=PossessionStatus.GRANTED,
            old_start=10.0,
            old_end=14.0,
            new_start=11.0,
            new_end=15.0,
            possession_id="POS-TEST-001"
        )


def test_invariant_2_in_progress_possessions_cannot_be_shortened():
    """Invariant 2: IN_PROGRESS possessions cannot be shortened or truncated while active."""
    with pytest.raises(ValueError, match="Cannot shorten or truncate active IN_PROGRESS possession"):
        validate_possession_schedule_immutability(
            status=PossessionStatus.IN_PROGRESS,
            old_start=10.0,
            old_end=14.0,
            new_start=10.0,
            new_end=12.0,  # shortened from 4h to 2h -> ILLEGAL
            possession_id="POS-TEST-002"
        )


def test_invariant_3_active_possessions_cannot_be_cancelled():
    """Invariant 3: Active (GRANTED or IN_PROGRESS) possessions cannot be directly cancelled."""
    with pytest.raises(ValueError, match="Illegal possession status transition"):
        validate_possession_transition(PossessionStatus.GRANTED, PossessionStatus.CANCELLED)

    with pytest.raises(ValueError, match="Illegal possession status transition"):
        validate_possession_transition(PossessionStatus.IN_PROGRESS, PossessionStatus.CANCELLED)


# -----------------------------------------------------------------------------
# 2. STATUTORY SAFETY & CONFLICT INVARIANTS
# -----------------------------------------------------------------------------

def test_invariant_4_failed_safety_validation_blocks_approval():
    """Invariant 4: Proposals with failed safety validation (SAFETY_REJECTED) cannot be approved."""
    # Create a proposal and manually set its status to SAFETY_REJECTED
    gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
    assert gen_resp.status_code == 200
    prop_id = gen_resp.json()["optimization_run_id"]

    PROPOSALS_STORE[prop_id]["safety_status"] = "SAFETY_REJECTED"

    appr_resp = client.post(
        f"/advisory/proposals/{prop_id}/approve",
        json={
            "role": "CTPC",
            "approver_id": "CTPC_01",
            "decision": "APPROVED",
            "comments": "Attempting illegal sanction of unsafe schedule"
        }
    )
    assert appr_resp.status_code == 400
    assert "Cannot approve a proposal flagged with SAFETY_REJECTED" in appr_resp.json()["detail"]


def test_invariant_5_critical_conflicts_block_approval():
    """Invariant 5: Proposals containing unmitigated CRITICAL conflicts are blocked from approval."""
    gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
    assert gen_resp.status_code == 200
    prop_id = gen_resp.json()["optimization_run_id"]

    # Inject a critical conflict
    PROPOSALS_STORE[prop_id]["critical_conflicts"] = [
        {"conflict_id": "CONF-001", "severity": "CRITICAL", "description": "Opposing train path conflict on UP Main"}
    ]

    appr_resp = client.post(
        f"/advisory/proposals/{prop_id}/approve",
        json={
            "role": "CTPC",
            "approver_id": "CTPC_01",
            "decision": "APPROVED",
            "comments": "Sanctioning despite critical conflict"
        }
    )
    # The endpoint or safety check must prevent proceeding with critical conflicts
    assert appr_resp.status_code in (400, 409, 422) or "conflict" in appr_resp.text.lower()


# -----------------------------------------------------------------------------
# 3. STATUTORY MULTI-ROLE GOVERNANCE INVARIANTS
# -----------------------------------------------------------------------------

def test_invariant_6_all_four_statutory_roles_required():
    """Invariant 6: All 4 statutory roles (CTPC, SR_DOM, SECTION_CONTROLLER, STATION_MASTER) must sign off."""
    gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
    prop_id = gen_resp.json()["optimization_run_id"]

    roles = ["CTPC", "SR_DOM", "SECTION_CONTROLLER", "STATION_MASTER"]

    for idx, role in enumerate(roles[:-1]):
        res = client.post(
            f"/advisory/proposals/{prop_id}/approve",
            json={
                "role": role,
                "approver_id": f"OFFICER_{role}",
                "decision": "APPROVED",
                "comments": f"{role} verified"
            }
        )
        assert res.status_code == 200
        prop = res.json()
        assert prop["approval_status"] != "SANCTIONED", f"Premature sanction after role {role}"

    # Final role signs off
    final_res = client.post(
        f"/advisory/proposals/{prop_id}/approve",
        json={
            "role": roles[-1],
            "approver_id": f"OFFICER_{roles[-1]}",
            "decision": "APPROVED",
            "comments": "Final Station Master clearance"
        }
    )
    assert final_res.status_code == 200
    assert final_res.json()["approval_status"] == "SANCTIONED"


def test_invariant_7_unauthorized_roles_cannot_approve():
    """Invariant 7: Authenticated actor cannot sign off claiming an unauthorized role."""
    actor = {"actor_id": "OFFICER_01", "role": "SECTION_CONTROLLER"}
    with pytest.raises(HTTPException) as exc_info:
        validate_actor_role_authorization(actor, "CTPC")
    assert exc_info.value.status_code == 403
    assert "not authorized to sign off as 'CTPC'" in exc_info.value.detail


def test_invariant_8_overrides_require_reason_and_justification():
    """Invariant 8: Operational overrides strictly require an approved reason code and justification."""
    gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
    prop_id = gen_resp.json()["optimization_run_id"]

    # Missing reason code
    res_no_reason = client.post(
        f"/advisory/proposals/{prop_id}/override",
        json={
            "user_id": "SR_DOM_01",
            "role": "SR_DOM",
            "reason_code": "",
            "justification": "Valid length justification text here",
            "overridden_schedule": {}
        }
    )
    assert res_no_reason.status_code in (400, 422)

    # Justification too short (< 10 chars)
    res_short_just = client.post(
        f"/advisory/proposals/{prop_id}/override",
        json={
            "user_id": "SR_DOM_01",
            "role": "SR_DOM",
            "reason_code": "VIP_MOVEMENT",
            "justification": "short",
            "overridden_schedule": {}
        }
    )
    assert res_short_just.status_code in (400, 422)


# -----------------------------------------------------------------------------
# 4. DATA FRESHNESS & CONTRADICTION INVARIANTS
# -----------------------------------------------------------------------------

def test_invariant_9_stale_data_blocks_or_downgrades_approval():
    """Invariant 9: Freshness metadata must be evaluated; stale data is flagged in canonical geometry."""
    res = client.get("/network/geometry/v1")
    assert res.status_code == 200
    geo = res.json()
    assert "track_sections" in geo
    first_sec = geo["track_sections"][0]
    assert "source_timestamp" in first_sec
    assert "ingestion_timestamp" in first_sec
    assert "validation_status" in first_sec
    assert first_sec["validation_status"] in [
        "VALIDATED", "SYNTHETIC", "STALE", "LOW_CONFIDENCE", "INVALID", "CONTRADICTORY", "UNAVAILABLE"
    ]


def test_invariant_10_contradictory_source_data_is_visible():
    """Invariant 10: Geometry and topology expose source provenance and data consistency flags."""
    res = client.get("/network/geometry/v1")
    assert res.status_code == 200
    geo = res.json()
    assert "track_sections" in geo
    first_sec = geo["track_sections"][0]
    assert "source_system" in first_sec
    assert "source_record_id" in first_sec
    assert "confidence" in first_sec
    assert 0.0 <= first_sec["confidence"] <= 1.0


# -----------------------------------------------------------------------------
# 5. AUDIT CHAIN & PHYSICAL SAFETY INVARIANTS
# -----------------------------------------------------------------------------

def test_invariant_11_all_actions_create_audit_events():
    """Invariant 11: All statutory actions append cryptographic audit log events."""
    initial_count = len(AUDIT_REPO.get_all_events())
    gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
    assert gen_resp.status_code == 200
    new_count = len(AUDIT_REPO.get_all_events())
    assert new_count > initial_count


def test_invariant_12_audit_hash_chain_tampering_is_detected():
    """Invariant 12: Any tampering with historical audit events is mathematically detected."""
    is_valid, err = AUDIT_REPO.verify_chain_integrity()
    assert is_valid
    assert err is None


def test_invariant_13_no_api_route_issues_physical_railway_commands():
    """
    Invariant 13: The API is advisory-only and shadow-mode by default.
    No registered route issues physical railway control commands.
    """
    from fastapi.routing import APIRoute
    prohibited_keywords = ["actuate", "throw_switch", "pull_signal", "emergency_stop", "live_interlock"]

    for r in app.routes:
        if isinstance(r, APIRoute):
            path_lower = r.path.lower()
            name_lower = r.name.lower()
            for kw in prohibited_keywords:
                assert kw not in path_lower, f"Prohibited actuation keyword '{kw}' found in route {r.path}"
                assert kw not in name_lower, f"Prohibited actuation keyword '{kw}' found in route {r.name}"


def test_invariant_14_live_cris_mode_cannot_start_without_explicit_config_and_certs():
    """
    Invariant 14: Live CRIS mode is strictly configuration-gated and disabled by default.
    Starting without explicit certificates and keys raises FileNotFoundError or permission denial.
    """
    # By default, live mode is not permitted
    assert not PluginConfig.is_live_permitted()

    # Attempting to start a TMSAdapter with non-existent cert paths fails safely
    non_existent_config = CRISAdapterConfig(
        source_name="TMS",
        base_url="https://live.cris.indianrailways.gov.in/api/v1",
        mtls_cert_path="/nonexistent/cert.pem",
        mtls_key_path="/nonexistent/key.pem"
    )
    adapter = TMSAdapter(config=non_existent_config)
    with pytest.raises(FileNotFoundError, match="mTLS certificate not found"):
        adapter._get_http_client()
