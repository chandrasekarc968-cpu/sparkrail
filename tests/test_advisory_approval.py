"""
Tests for BDMS Advisory and Statutory Governance Workflow:
Advisory proposal generation, multi-role approval hierarchy (CTPC -> SR_DOM),
operational rejection, override with mandatory justification, and tamper-evident audit logging.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


class TestAdvisoryWorkflow:
    def test_generate_advisory_proposal(self):
        resp = client.post("/advisory/proposals", json={
            "division_code": "PRYJ",
            "horizon_hours": 24,
            "freeze_week1": True,
            "dry_run": True,
            "requested_by": "CTPC_TEST_AGENT"
        })
        assert resp.status_code == 200
        data = resp.json()

        assert "optimization_run_id" in data
        assert data["division_code"] == "PRYJ"
        assert data["advisory_mode"] == "ADVISORY_ONLY_NOT_EXECUTED"
        assert data["schema_version"] == "1.0.0"
        assert data["approval_status"] == "PENDING_CTPC_REVIEW"
        assert data["safety_status"] in ("SAFETY_CERTIFIED", "SAFETY_REJECTED")
        assert len(data["recommended_blocks"]) > 0
        assert "CTPC" in data["approval_chain"]
        assert "SR_DOM" in data["approval_chain"]

    def test_idempotency_key_duplicate_prevention(self):
        idemp_key = "IDEMP-TEST-UNIQUE-KEY-884"
        headers = {"Idempotency-Key": idemp_key}
        payload = {
            "division_code": "PRYJ",
            "horizon_hours": 24,
            "dry_run": True
        }

        resp1 = client.post("/advisory/proposals", json=payload, headers=headers)
        assert resp1.status_code == 200
        run_id_1 = resp1.json()["optimization_run_id"]

        resp2 = client.post("/advisory/proposals", json=payload, headers=headers)
        assert resp2.status_code == 200
        run_id_2 = resp2.json()["optimization_run_id"]

        # Duplicate idempotency key must return the identical proposal run ID without re-executing
        assert run_id_1 == run_id_2

    def test_statutory_approval_chain_progression(self):
        # 1. Create proposal
        gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
        prop_id = gen_resp.json()["optimization_run_id"]

        # 2. CTPC Approval
        ctpc_action = {
            "role": "CTPC",
            "approver_id": "EMP-CTPC-01",
            "approver_name": "Chief Controller HQ",
            "decision": "APPROVED",
            "comments": "Corridor traffic window cleared."
        }
        resp_ctpc = client.post(f"/advisory/proposals/{prop_id}/approve", json=ctpc_action)
        assert resp_ctpc.status_code == 200
        data_ctpc = resp_ctpc.json()
        assert data_ctpc["approval_chain"]["CTPC"]["status"] == "APPROVED"
        assert data_ctpc["approval_status"] == "PENDING_CTPC_REVIEW"  # Requires Sr. DOM to complete sanction

        # 3. Sr. DOM Approval
        sr_dom_action = {
            "role": "SR_DOM",
            "approver_id": "EMP-SRDOM-01",
            "approver_name": "Sr. Divisional Operations Manager",
            "decision": "APPROVED",
            "comments": "Sanction granted for Week 1 execution."
        }
        resp_sr_dom = client.post(f"/advisory/proposals/{prop_id}/approve", json=sr_dom_action)
        assert resp_sr_dom.status_code == 200
        data_sr_dom = resp_sr_dom.json()
        assert data_sr_dom["approval_chain"]["SR_DOM"]["status"] == "APPROVED"
        # When both CTPC and Sr. DOM sign off, proposal transitions to SANCTIONED
        assert data_sr_dom["approval_status"] == "SANCTIONED"
        assert all(b["lifecycle_state"] == "SANCTIONED" for b in data_sr_dom["recommended_blocks"])

    def test_proposal_rejection(self):
        gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
        prop_id = gen_resp.json()["optimization_run_id"]

        reject_action = {
            "role": "SECTION_CONTROLLER",
            "approver_id": "EMP-SC-01",
            "approver_name": "Section Controller Aligarh",
            "decision": "REJECTED",
            "comments": "High traffic density: priority military freight rake passing."
        }
        resp = client.post(f"/advisory/proposals/{prop_id}/reject", json=reject_action)
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_status"] == "REJECTED"
        assert data["approval_chain"]["SECTION_CONTROLLER"]["status"] == "REJECTED"
        assert all(b["lifecycle_state"] == "REJECTED" for b in data["recommended_blocks"])

    def test_operational_override_with_audit(self):
        gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
        prop_id = gen_resp.json()["optimization_run_id"]

        override_req = {
            "user_id": "SR_DOM_OVERRIDE_01",
            "role": "SR_DOM",
            "reason_code": "EMERGENCY_DERAILMENT_RISK",
            "justification": "Urgent rail defect observed on B2; shifting block window forward by 2 hours.",
            "overridden_schedule": {"recommended_blocks": []}
        }
        resp = client.post(f"/advisory/proposals/{prop_id}/override", json=override_req)
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == "OVERRIDE_RECORDED"
        assert res_data["reason_code"] == "EMERGENCY_DERAILMENT_RISK"

        # Check audit trail has recorded the override event
        audit_resp = client.get("/advisory/audit?limit=20")
        assert audit_resp.status_code == 200
        audits = audit_resp.json()
        assert any(
            a["event_type"] == "OPERATIONAL_OVERRIDE" and a["resource_id"] == prop_id
            for a in audits
        )
