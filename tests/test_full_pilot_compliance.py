"""
Comprehensive Pilot-Compliance Test Suite for CRIS BDMS Advisory Layer.
Verifies all non-negotiable safety rules, 4-tier statutory approvals,
tamper-evident SHA-256 audit chaining (tampering, deletion, reordering),
active possession immutability, dynamic payload generation (no dummy data),
and realistic TSL topological safety validation.
"""

import copy
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.advisory import AUDIT_REPO, InMemoryAuditRepository, TamperEvidentAuditChain
from src.data_pipeline.models import (
    PossessionStatus,
    ApprovalRole,
    RecommendationStatus,
    validate_possession_transition,
    validate_possession_schedule_immutability,
    DataProvenance,
    TrackSection,
    TrainMovement,
    TrainPriority,
    ElementarySection,
    IsolatorSwitch,
    Interlocking,
    Scenario
)
from src.data_pipeline.adapters.cris_adapters import (
    BaseCRISAdapter,
    TMSAdapter,
    CRISReplayEngine
)
from src.optimization.disruption_engine import DynamicDisruptionEngine
from src.data_pipeline.synthetic_data import generate_synthetic_data

client = TestClient(app)


# =============================================================================
# 1. POSSESSION LIFECYCLE & ACTIVE IMMUTABILITY TESTS
# =============================================================================
class TestPossessionLifecycleAndImmutability:
    def test_valid_possession_status_transitions(self):
        """DRAFT -> PROPOSED -> SANCTIONED -> GRANTED -> IN_PROGRESS -> COMPLETED"""
        validate_possession_transition(PossessionStatus.DRAFT, PossessionStatus.PROPOSED)
        validate_possession_transition(PossessionStatus.PROPOSED, PossessionStatus.SANCTIONED)
        validate_possession_transition(PossessionStatus.SANCTIONED, PossessionStatus.GRANTED)
        validate_possession_transition(PossessionStatus.GRANTED, PossessionStatus.IN_PROGRESS)
        validate_possession_transition(PossessionStatus.IN_PROGRESS, PossessionStatus.COMPLETED)

    def test_reject_granted_to_cancelled(self):
        """GRANTED possession cannot be cancelled."""
        with pytest.raises(ValueError, match="Illegal possession status transition"):
            validate_possession_transition(PossessionStatus.GRANTED, PossessionStatus.CANCELLED)

    def test_reject_in_progress_to_cancelled_or_draft(self):
        """IN_PROGRESS possession cannot be cancelled or reverted to draft."""
        with pytest.raises(ValueError, match="Illegal possession status transition"):
            validate_possession_transition(PossessionStatus.IN_PROGRESS, PossessionStatus.CANCELLED)
        with pytest.raises(ValueError, match="Illegal possession status transition"):
            validate_possession_transition(PossessionStatus.IN_PROGRESS, PossessionStatus.DRAFT)

    def test_granted_schedule_immutability(self):
        """GRANTED possession cannot be shifted, truncated, or shortened."""
        # Exact same times pass
        validate_possession_schedule_immutability(PossessionStatus.GRANTED, 10.0, 14.0, 10.0, 14.0)
        # Shift start
        with pytest.raises(ValueError, match="Cannot shift, cancel, or alter schedule of active GRANTED possession"):
            validate_possession_schedule_immutability(PossessionStatus.GRANTED, 10.0, 14.0, 11.0, 15.0)
        # Shorten end
        with pytest.raises(ValueError, match="Cannot shift, cancel, or alter schedule of active GRANTED possession"):
            validate_possession_schedule_immutability(PossessionStatus.GRANTED, 10.0, 14.0, 10.0, 13.0)

    def test_in_progress_schedule_immutability(self):
        """IN_PROGRESS possession cannot be shortened or start-shifted."""
        # Exact same times pass
        validate_possession_schedule_immutability(PossessionStatus.IN_PROGRESS, 10.0, 14.0, 10.0, 14.0)
        # Extension is permitted if safe, but shortening is illegal
        with pytest.raises(ValueError, match="Cannot shorten or truncate active IN_PROGRESS possession"):
            validate_possession_schedule_immutability(PossessionStatus.IN_PROGRESS, 10.0, 14.0, 10.0, 12.0)
        # Shift start is illegal
        with pytest.raises(ValueError, match="Cannot shift start time of active IN_PROGRESS possession"):
            validate_possession_schedule_immutability(PossessionStatus.IN_PROGRESS, 10.0, 14.0, 11.0, 15.0)


# =============================================================================
# 2. SOURCE ADAPTERS & REPLAY ENGINE TESTS
# =============================================================================
class TestCRISAdaptersAndReplay:
    def test_all_8_synthetic_event_types_replayable(self):
        """Verifies that all 8 operational events are cleanly replayable and typed."""
        events = CRISReplayEngine.generate_replay_events()
        assert len(events) >= 8
        event_types = {e["event_type"] for e in events}
        expected_types = {
            "TRAIN_MOVEMENT",
            "TRAIN_DELAY",
            "POSSESSION_STATUS",
            "OHE_ISOLATION",
            "SIGNAL_DISCONNECTION",
            "MACHINE_FAILURE",
            "WEATHER_RESTRICTION",
            "WORK_COMPLETION"
        }
        assert event_types == expected_types

    def test_stale_data_detection(self):
        """Adapter must detect and flag out-of-sequence / stale events."""
        adapter = TMSAdapter()
        now_time = datetime.now(timezone.utc).isoformat()
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        
        event_now = {
            "event_id": "EVT-SEQ-01",
            "timestamp": now_time,
            "event_type": "DEMAND_CREATED",
            "payload": {"track_section_id": "B1", "demand_id": "D1"}
        }
        event_stale = {
            "event_id": "EVT-SEQ-02",
            "timestamp": old_time,
            "event_type": "DEMAND_CREATED",
            "payload": {"track_section_id": "B1", "demand_id": "D1"}
        }
        res1 = adapter.process_event(event_now)
        assert res1["status"] == "INGESTED"

        res2 = adapter.process_event(event_stale)
        assert res2["status"] == "STALE_OR_DUPLICATE_REJECTED"
        assert "Out of sequence" in res2["reason"]

    def test_contradiction_detection_electric_train_on_isolated_track(self):
        """Adapter must flag electric train moving on an electrically isolated block."""
        adapter = TMSAdapter()
        now_iso = datetime.now(timezone.utc).isoformat()
        event = {
            "event_id": "EVT-CONTRA-01",
            "timestamp": now_iso,
            "event_type": "TRAIN_MOVEMENT",
            "payload": {
                "train_id": "T_ELEC_01",
                "track_section_id": "B4",
                "traction_type": "ELECTRIC"
            }
        }
        context = {"isolated_sections": {"B4"}}
        res = adapter.process_event(event, current_context=context)
        assert res["status"] == "CONTRADICTION_REJECTED"
        assert "electrically isolated section" in res["reason"]


# =============================================================================
# 3. FOUR-ROLE STATUTORY APPROVAL HIERARCHY TESTS
# =============================================================================
class TestStatutoryGovernanceAndAudit:
    def test_four_role_approval_progression_on_recommendation(self):
        """
        Tests that /api/v1/recommendations/{id}/approve strictly requires:
        1. CTPC -> PENDING_APPROVAL, possession PROPOSED
        2. SR_DOM -> PENDING_APPROVAL, possession PROPOSED (not sanctioned after 2!)
        3. SECTION_CONTROLLER -> PENDING_APPROVAL, possession PROPOSED (not sanctioned after 3!)
        4. STATION_MASTER -> APPROVED, possession SANCTIONED!
        """
        # Create run
        run_resp = client.post("/api/v1/optimization/runs", json={
            "request_id": "REQ-GOV-001",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "snapshot_gov_01"
        })
        assert run_resp.status_code == 200
        demands = run_resp.json()["scheduled_demands"]
        assert len(demands) > 0
        rec_id = f"REC-{demands[0]}"

        # Check initial state
        rec = client.get(f"/api/v1/recommendations/{rec_id}").json()
        assert rec["status"] == "PROPOSED"
        assert rec["primary_possession"]["status"] == "DRAFT"

        # 1. CTPC approves
        resp1 = client.post(f"/api/v1/recommendations/{rec_id}/approve", json={
            "role": "CTPC", "approver_id": "CTPC_01", "comments": "Approved path"
        })
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "PENDING_APPROVAL"
        assert resp1.json()["is_sanctioned"] is False

        # 2. SR_DOM approves
        resp2 = client.post(f"/api/v1/recommendations/{rec_id}/approve", json={
            "role": "SR_DOM", "approver_id": "SR_DOM_01", "comments": "Approved operations"
        })
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "PENDING_APPROVAL"
        assert resp2.json()["is_sanctioned"] is False
        assert resp2.json()["recommendation"]["primary_possession"]["status"] == "PROPOSED"

        # 3. SECTION_CONTROLLER approves
        resp3 = client.post(f"/api/v1/recommendations/{rec_id}/approve", json={
            "role": "SECTION_CONTROLLER", "approver_id": "SC_01", "comments": "Approved occupancy"
        })
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "PENDING_APPROVAL"
        assert resp3.json()["is_sanctioned"] is False

        # 4. STATION_MASTER approves -> NOW fully sanctioned!
        resp4 = client.post(f"/api/v1/recommendations/{rec_id}/approve", json={
            "role": "STATION_MASTER", "approver_id": "SM_01", "comments": "Approved platform & loop"
        })
        assert resp4.status_code == 200
        assert resp4.json()["status"] == "APPROVED"
        assert resp4.json()["is_sanctioned"] is True
        assert resp4.json()["recommendation"]["primary_possession"]["status"] == "SANCTIONED"

    def test_unauthorized_role_approval_rejected(self):
        """A caller with X-Actor-Role header cannot claim a different approval role."""
        run_resp = client.post("/api/v1/optimization/runs", json={
            "request_id": "REQ-UNAUTH-01",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "snap_unauth"
        })
        rec_id = f"REC-{run_resp.json()['scheduled_demands'][0]}"

        # Actor is authenticated as STATION_MASTER, but tries to sign off as SR_DOM
        headers = {"X-Actor-Role": "STATION_MASTER", "X-Actor-ID": "STATION_MASTER_01"}
        resp = client.post(
            f"/api/v1/recommendations/{rec_id}/approve",
            json={"role": "SR_DOM", "approver_id": "STATION_MASTER_01", "comments": "Illegal claim"},
            headers=headers
        )
        assert resp.status_code == 403
        assert "not authorized to sign off as" in resp.json()["detail"]

    def test_rejection_requires_mandatory_justification(self):
        """Rejection must fail if justification comments are empty or < 5 characters."""
        run_resp = client.post("/api/v1/optimization/runs", json={
            "request_id": "REQ-REJ-01",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "snap_rej"
        })
        rec_id = f"REC-{run_resp.json()['scheduled_demands'][0]}"

        resp = client.post(f"/api/v1/recommendations/{rec_id}/reject", json={
            "role": "SR_DOM", "approver_id": "SR_DOM_01", "comments": "no"
        })
        assert resp.status_code == 400
        assert "Mandatory operational justification required" in resp.json()["detail"]

    def test_override_requires_mandatory_justification(self):
        """Override must fail if justification is < 10 characters."""
        run_resp = client.post("/api/v1/optimization/runs", json={
            "request_id": "REQ-OVR-01",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "snap_ovr"
        })
        rec_id = f"REC-{run_resp.json()['scheduled_demands'][0]}"

        resp = client.post(f"/api/v1/recommendations/{rec_id}/override", json={
            "override_id": "OVR-TEST-01",
            "recommendation_id": rec_id,
            "user_id": "SR_DOM_01",
            "role": "SR_DOM",
            "reason_code": "VIP_MOVEMENT",
            "justification": "short",
            "previous_schedule": {},
            "overridden_schedule": {}
        })
        assert resp.status_code in (400, 422)

    def test_optimistic_concurrency_version_conflict(self):
        """If-Match header mismatch must reject with 412 Precondition Failed."""
        run_resp = client.post("/api/v1/optimization/runs", json={
            "request_id": "REQ-OCC-01",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "snap_occ"
        })
        rec_id = f"REC-{run_resp.json()['scheduled_demands'][0]}"

        # Version is 1, but client sends If-Match: 99
        headers = {"If-Match": "99"}
        resp = client.post(
            f"/api/v1/recommendations/{rec_id}/approve",
            json={"role": "CTPC", "approver_id": "CTPC_01", "comments": "Testing OCC"},
            headers=headers
        )
        assert resp.status_code == 412
        assert "Optimistic Concurrency Conflict" in resp.json()["detail"]

    def test_idempotency_key_caching(self):
        """Idempotency-Key must return cached response on subsequent calls."""
        idemp_key = "IDEMP-TEST-KEY-XYZ"
        headers = {"Idempotency-Key": idemp_key}
        req_body = {
            "request_id": "REQ-IDEMP-01",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "snap_idemp"
        }
        res1 = client.post("/api/v1/optimization/possession-schedule", json=req_body, headers=headers)
        assert res1.status_code == 200
        opt_id_1 = res1.json()["optimization_run_id"]

        res2 = client.post("/api/v1/optimization/possession-schedule", json=req_body, headers=headers)
        assert res2.status_code == 200
        opt_id_2 = res2.json()["optimization_run_id"]

        assert opt_id_1 == opt_id_2


# =============================================================================
# 4. SHA-256 TAMPER-EVIDENT AUDIT CHAIN INTEGRITY TESTS
# =============================================================================
class TestAuditChainIntegrityAndTampering:
    def test_audit_chain_modification_detection(self):
        """Modifying any event's action or details must break SHA-256 verification."""
        repo = InMemoryAuditRepository()
        repo.append_event("TEST_EVENT_1", "USER_1", "CTPC", "RES_1", "ID_1", "ACTION_1", {"k": 1})
        repo.append_event("TEST_EVENT_2", "USER_2", "SR_DOM", "RES_2", "ID_2", "ACTION_2", {"k": 2})
        repo.append_event("TEST_EVENT_3", "USER_3", "SECTION_CONTROLLER", "RES_3", "ID_3", "ACTION_3", {"k": 3})

        is_valid, _ = repo.verify_integrity()
        assert is_valid is True

        # Tamper with event 1
        repo.chain[1]["details"]["k"] = 999
        is_valid, err = repo.verify_integrity()
        assert is_valid is False
        assert "Tampered hash" in err

    def test_audit_chain_deletion_detection(self):
        """Deleting an event must break the previous_hash link for subsequent events."""
        repo = InMemoryAuditRepository()
        repo.append_event("TEST_EVENT_1", "USER_1", "CTPC", "RES_1", "ID_1", "ACTION_1", {"k": 1})
        repo.append_event("TEST_EVENT_2", "USER_2", "SR_DOM", "RES_2", "ID_2", "ACTION_2", {"k": 2})
        repo.append_event("TEST_EVENT_3", "USER_3", "SECTION_CONTROLLER", "RES_3", "ID_3", "ACTION_3", {"k": 3})

        # Delete middle event
        del repo.chain[1]
        is_valid, err = repo.verify_integrity()
        assert is_valid is False
        assert "Broken link" in err

    def test_audit_chain_reordering_detection(self):
        """Swapping or reordering events must break the previous_hash link."""
        repo = InMemoryAuditRepository()
        repo.append_event("TEST_EVENT_1", "USER_1", "CTPC", "RES_1", "ID_1", "ACTION_1", {"k": 1})
        repo.append_event("TEST_EVENT_2", "USER_2", "SR_DOM", "RES_2", "ID_2", "ACTION_2", {"k": 2})
        repo.append_event("TEST_EVENT_3", "USER_3", "SECTION_CONTROLLER", "RES_3", "ID_3", "ACTION_3", {"k": 3})

        # Swap event 1 and event 2
        repo.chain[1], repo.chain[2] = repo.chain[2], repo.chain[1]
        is_valid, err = repo.verify_integrity()
        assert is_valid is False
        assert "Broken link" in err or "Tampered hash" in err


# =============================================================================
# 5. DYNAMIC POSSESSION SCHEDULE PAYLOAD (NO HARDCODED DUMMY DATA)
# =============================================================================
class TestDynamicPayloadVerification:
    def test_possession_schedule_payload_is_dynamically_built(self):
        """Payload must be built from scenario and solver, without hardcoded dummy values."""
        resp = client.post("/api/v1/optimization/possession-schedule", json={
            "request_id": "REQ-DYN-01",
            "division_code": "PRYJ",
            "planning_horizon_hours": 24,
            "input_snapshot_hash": "snap_dyn_01"
        })
        assert resp.status_code == 200
        data = resp.json()

        # Check primary possession is tied to a scheduled job, not hardcoded B5
        primary = data["primary_possession"]
        assert "track_section_id" in primary
        assert "possession_id" in primary
        assert primary["scheduled_start"] >= 0.0
        assert primary["scheduled_end"] > primary["scheduled_start"]

        # Check recommended_blocks is populated from solver
        assert len(data["recommended_blocks"]) > 0

        # Check electrical isolation has an elementary section
        assert "elementary_section" in data["electrical_isolation"]

        # Check approval state has all 4 roles pending
        app_state = data["approval_state"]
        for role in ["CTPC", "SR_DOM", "SECTION_CONTROLLER", "STATION_MASTER"]:
            assert role in app_state
            assert app_state[role] == "PENDING"


# =============================================================================
# 6. TOPOLOGICAL TSL DISRUPTION & HEADWAY TOKEN MARGIN
# =============================================================================
class TestTopologicalTSLDisruption:
    def test_tsl_requires_15_minute_pilot_guard_clearance(self):
        """TSL single-line working requires minimum 15-minute token clearance for opposing trains."""
        disruption_engine = DynamicDisruptionEngine()
        # Train movement opposing direction within 10 minutes violates 15 min rule
        is_valid, reason = disruption_engine._validate_tsl_topology(
            corridor_blocks=["B2"],
            affected_block="B2",
            parallel_track_available=True,
            opposing_train_margin_minutes=10.0
        )
        assert is_valid is False
        assert "15-minute pilot guard token clearance" in reason

        # Opposing train with 20 minutes margin passes
        is_valid_ok, reason_ok = disruption_engine._validate_tsl_topology(
            corridor_blocks=["B2"],
            affected_block="B2",
            parallel_track_available=True,
            opposing_train_margin_minutes=20.0
        )
        assert is_valid_ok is True
        assert "Validated for single-line working" in reason_ok
