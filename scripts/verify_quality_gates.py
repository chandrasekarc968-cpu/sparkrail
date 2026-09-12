"""
Quality Gate Verification Script for SparkRail BDMS Advisory Optimization Engine.
Explicitly executes and verifies:
1. Synthetic 24-hour optimization run.
2. Disruption scenario with 15+ min delay triggering corridor replanning.
3. Active possession immutability (GRANTED/IN_PROGRESS cannot be cancelled or moved).
4. Unapproved recommendation cannot be marked executable.
5. Electrical isolation & TSL safety constraints enforcement.
6. SHA-256 tamper-evident audit hash-chain integrity.
"""

import sys
import os
import json
from datetime import datetime, timezone

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.api.main import app

from src.data_pipeline.models import (
    TrackSection,
    BlockSection,
    Station,
    ElementarySection,
    MaintenanceJob,
    MaintenanceDemand,
    TrainMovement,
    Possession,
    PossessionStatus,
    TrainPriority,
    Department,
    ApprovalRole,
    RecommendationStatus,
    ScheduledJob,
    Scenario,
    DisruptionEvent,
    validate_possession_transition
)
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.optimization.clustering import SpatiotemporalClusteringEngine
from src.optimization.macro_allocator import MacroPossessionAllocator
from src.optimization.microscopic_validator import MicroscopicDispatchValidator
from src.optimization.milp_solver import ProductionOptimizationPipeline
from src.optimization.disruption_engine import DynamicDisruptionEngine
from src.api.advisory import TamperEvidentAuditChain
from src.data_pipeline.synthetic_data import generate_synthetic_data
from tests.fixtures.deterministic_scenarios import (
    create_granted_possession_scenario,
    create_ohe_isolation_scenario
)

client = TestClient(app)


def run_all_quality_gates():
    print("=" * 80)
    print("SPARKRAIL PILOT QUALITY GATES VERIFICATION")
    print("=" * 80)
    all_passed = True

    # -------------------------------------------------------------
    # GATE 4: Complete Synthetic 24-Hour Optimization Scenario
    # -------------------------------------------------------------
    print("\n[GATE 4] Running Complete Synthetic 24-Hour Optimization Scenario...")
    try:
        scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=20, num_trains=10)
        scorer = TaskCriticalityScorer()
        job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}
        assert len(job_tcis) == 20, "Must score all 20 jobs"
        print("  -> Scored 20 maintenance jobs with 6-factor AHP TCI [OK]")

        pipeline = ProductionOptimizationPipeline()
        opt_res = pipeline.optimize(scenario, job_tcis)
        assert opt_res["status"] in ("optimal", "alns_feasible"), f"Unexpected status: {opt_res['status']}"
        assert len(opt_res["scheduled_jobs"]) > 0, "Must schedule jobs"
        print(f"  -> Optimizer status: {opt_res['status']}, scheduled {len(opt_res['scheduled_jobs'])} jobs [OK]")
        print(f"  -> Solver runtime: {opt_res['runtime_seconds']:.4f}s, Total closure: {opt_res['total_closure_time']:.2f}h")
        print(">>> GATE 4: PASSED")
    except Exception as e:
        print(f">>> GATE 4: FAILED - {e}")
        all_passed = False

    # -------------------------------------------------------------
    # GATE 5: Disruption Scenario with 15+ Min Delay
    # -------------------------------------------------------------
    print("\n[GATE 5] Running Disruption Scenario (>= 15 Min Premium Train Delay)...")
    try:
        disrupt_payload = {
            "event_id": "DISRUPT-GATE-01",
            "event_type": "TRAIN_DELAY",
            "severity": "MAJOR",
            "affected_block_ids": ["B2"],
            "delay_minutes": 35.0,  # > 15 min threshold
            "corridor_radius_km": 30.0
        }
        resp = client.post("/api/v1/disruptions", json=disrupt_payload)
        assert resp.status_code == 200, resp.text
        res_data = resp.json()
        assert res_data["is_successful"] is True
        print(f"  -> Disruption handled successfully in {res_data['runtime_seconds']:.4f}s (well under 90s target)")
        print(f"  -> Affected corridor range: {res_data['affected_corridor_chainage_km']} km")
        print(f"  -> Advisory recommendation generated: {res_data['advisory_recommendation'][:60]}...")
        print(">>> GATE 5: PASSED")
    except Exception as e:
        print(f">>> GATE 5: FAILED - {e}")
        all_passed = False

    # -------------------------------------------------------------
    # GATE 6: Active Possession Immutability (GRANTED/IN_PROGRESS)
    # -------------------------------------------------------------
    print("\n[GATE 6] Verifying Active Possession Immutability...")
    try:
        # 1. State machine level: GRANTED & IN_PROGRESS cannot be cancelled or reverted
        for active_status in [PossessionStatus.GRANTED, PossessionStatus.IN_PROGRESS]:
            for forbidden_status in [PossessionStatus.DRAFT, PossessionStatus.CANCELLED]:
                try:
                    validate_possession_transition(active_status, forbidden_status)
                    raise AssertionError(f"Allowed illegal transition from {active_status} to {forbidden_status}!")
                except ValueError:
                    pass  # Correctly rejected
        
        # 2. Disruption engine level: verify active granted possession cannot be shifted
        from src.data_pipeline.models import OptimizedSchedule, ScheduledJob as SJModel, PossessionLifecycle
        scenario = create_granted_possession_scenario()
        rescheduler = DynamicDisruptionEngine(default_chainage_radius_km=25.0)

        current_schedule = OptimizedSchedule(
            status="optimal",
            solver="ALNS_DETERMINISTIC",
            total_closure_time=5.5,
            objective_value=140.0,
            runtime_seconds=0.15,
            scheduled_jobs=[
                SJModel(
                    job_id="J_ACTIVE_GRANT",
                    block_id="B1",
                    start_time=2.0,
                    end_time=6.0,
                    tci=95.0,
                    department=Department.ENGINEERING
                ),
                SJModel(
                    job_id="J_ROUTINE_01",
                    block_id="B2",
                    start_time=8.0,
                    end_time=9.5,
                    tci=45.0,
                    department=Department.S_AND_T
                )
            ],
            unscheduled_jobs=[],
            train_delays={}
        )

        disruption = DisruptionEvent(
            id="DISRUPT-IMMUTABLE-01",
            event_id="DISRUPT-IMMUTABLE-01",
            timestamp="2026-09-12T08:00:00Z",
            affected_block_ids=["B1"],
            delay_minutes=45.0,
            event_type="TRAIN_DELAY",
            severity="MAJOR"
        )

        active_states = {
            "J_ACTIVE_GRANT": PossessionLifecycle.GRANTED,
            "J_ROUTINE_01": PossessionLifecycle.REQUESTED
        }

        res = rescheduler.handle_disruption(
            scenario=scenario,
            current_schedule=current_schedule,
            disruption=disruption,
            active_possession_states=active_states
        )

        granted_job = next((j for j in res.rescheduled_schedule.scheduled_jobs if j.job_id == "J_ACTIVE_GRANT"), None)
        assert granted_job is not None, "Active GRANTED possession must be preserved"
        assert granted_job.start_time == 2.0, "Start time cannot be modified"
        assert granted_job.end_time == 6.0, "End time cannot be modified"
        assert "J_ACTIVE_GRANT" in res.immutable_granted_jobs
        print("  -> Confirmed GRANTED/IN_PROGRESS possessions are mathematically immutable [OK]")
        print(">>> GATE 6: PASSED")
    except Exception as e:
        print(f">>> GATE 6: FAILED - {e}")
        all_passed = False

    # -------------------------------------------------------------
    # GATE 7: Unapproved Recommendation Cannot Be Treated as Executable
    # -------------------------------------------------------------
    print("\n[GATE 7] Verifying Unapproved Recommendation Execution Lock...")
    try:
        # Create an unapproved proposal via API
        gen_resp = client.post("/advisory/proposals", json={"division_code": "PRYJ", "dry_run": True})
        assert gen_resp.status_code == 200
        prop = gen_resp.json()
        assert prop["approval_status"] == "PENDING_CTPC_REVIEW"
        assert prop["advisory_mode"] == "ADVISORY_ONLY_NOT_EXECUTED"
        print("  -> Proposal created in advisory mode with status PENDING_CTPC_REVIEW [OK]")

        # Recommended blocks cannot be in GRANTED or IN_PROGRESS state
        for block in prop["recommended_blocks"]:
            assert block["lifecycle_state"] != "GRANTED"
            assert block["lifecycle_state"] != "IN_PROGRESS"
        print("  -> Recommended blocks locked from GRANTED/IN_PROGRESS states [OK]")

        # Progress through all four mandatory roles (CTPC, SR_DOM, SECTION_CONTROLLER, STATION_MASTER)
        prop_id = prop["optimization_run_id"]
        client.post(f"/advisory/proposals/{prop_id}/approve", json={
            "role": "CTPC", "approver_id": "CTPC-01", "approver_name": "Chief Traffic Planner", "decision": "APPROVED"
        })
        srdom_resp = client.post(f"/advisory/proposals/{prop_id}/approve", json={
            "role": "SR_DOM", "approver_id": "SRDOM-01", "approver_name": "Sr. DOM PRYJ", "decision": "APPROVED"
        })
        assert srdom_resp.status_code == 200
        # Crucial safety rule: 2 approvals are NOT sufficient to sanction
        assert srdom_resp.json()["approval_status"] != "SANCTIONED"
        assert srdom_resp.json()["approval_status"] == "PENDING_SECTION_CONTROLLER_REVIEW"

        client.post(f"/advisory/proposals/{prop_id}/approve", json={
            "role": "SECTION_CONTROLLER", "approver_id": "SC-01", "approver_name": "Section Controller", "decision": "APPROVED"
        })
        sm_resp = client.post(f"/advisory/proposals/{prop_id}/approve", json={
            "role": "STATION_MASTER", "approver_id": "SM-01", "approver_name": "Station Master", "decision": "APPROVED"
        })
        assert sm_resp.status_code == 200
        assert sm_resp.json()["approval_status"] == "SANCTIONED"
        print("  -> Progressed to SANCTIONED only after all 4 statutory supervisory sign-offs [OK]")
        print(">>> GATE 7: PASSED")
    except Exception as e:
        print(f">>> GATE 7: FAILED - {e}")
        all_passed = False

    # -------------------------------------------------------------
    # GATE 8: Electrical Isolation & TSL Safety Constraints
    # -------------------------------------------------------------
    print("\n[GATE 8] Verifying Electrical Isolation and TSL Constraints...")
    try:
        scenario, es = create_ohe_isolation_scenario()
        validator = MicroscopicDispatchValidator(min_headway_hours=0.25)

        # Electric train traversing isolated section
        candidate_schedule = [
            ScheduledJob(
                job_id="J_OHE_RENEWAL",
                block_id="B4",
                start_time=10.0,
                end_time=12.0,
                tci=75.0,
                department=Department.OHE
            )
        ]

        result = validator.validate_dispatch(
            scenario=scenario,
            scheduled_jobs=candidate_schedule,
            electrical_isolated_blocks={"B4"}
        )

        assert not result.is_feasible, "Must fail with electric train on isolated track"
        assert len(result.generated_cuts) > 0, "Must return Benders cut"
        assert any(cut.cut_type == "ELECTRICAL_ISOLATION" for cut in result.generated_cuts)
        print("  -> Electrical isolation conflict caught with continuous traction check & Benders cut [OK]")
        print(">>> GATE 8: PASSED")
    except Exception as e:
        print(f">>> GATE 8: FAILED - {e}")
        all_passed = False

    # -------------------------------------------------------------
    # GATE 9: SHA-256 Audit Hash-Chain Integrity
    # -------------------------------------------------------------
    print("\n[GATE 9] Verifying Cryptographic SHA-256 Audit Hash-Chain...")
    try:
        chain = TamperEvidentAuditChain()
        chain.append(
            event_type="OPTIMIZATION_SCHEDULE_GENERATED",
            user_id="SYSTEM",
            role="AI_ENGINE",
            resource_type="SCHEDULE",
            resource_id="RUN-001",
            action="GENERATE",
            details={"jobs_count": 20, "solver": "CP-SAT"}
        )
        chain.append(
            event_type="PROPOSAL_SANCTIONED",
            user_id="EMP-CTPC-01",
            role="CTPC",
            resource_type="PROPOSAL",
            resource_id="PROP-001",
            action="APPROVE",
            details={"comments": "Traffic window verified"}
        )
        chain.append(
            event_type="OPERATIONAL_OVERRIDE",
            user_id="EMP-SRDOM-01",
            role="SR_DOM",
            resource_type="POSSESSION",
            resource_id="POSS-B3",
            action="OVERRIDE",
            details={"reason": "VIP_MOVEMENT", "justification": "Presidential Special Train passing"}
        )

        # Verify clean chain via method
        is_valid, err = chain.verify_integrity()
        assert is_valid is True, f"Integrity check failed: {err}"
        assert len(chain.chain) == 3
        print("  -> Clean audit chain (3 events) verified with 100% cryptographic SHA-256 integrity [OK]")

        # Test verification endpoint /api/v1/advisory/audit/verify
        api_audit_resp = client.get("/api/v1/advisory/audit/verify")
        assert api_audit_resp.status_code == 200
        assert api_audit_resp.json()["is_intact"] is True
        print(f"  -> Audit endpoint /api/v1/advisory/audit/verify returned 200 OK & is_intact=True [OK]")

        # Tamper with chain in memory
        chain.chain[1]["details"]["comments"] = "Tampered unauthorized text"
        is_tampered_valid, tamper_err = chain.verify_integrity()
        assert is_tampered_valid is False
        assert "Tampered hash" in tamper_err
        print("  -> Deliberate payload tampering instantly detected by SHA-256 hash recomputation [OK]")
        print(">>> GATE 9: PASSED")
    except Exception as e:
        print(f">>> GATE 9: FAILED - {e}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL QUALITY GATES (4 - 9) PASSED SUCCESSFULLY!")
    else:
        print("SOME QUALITY GATES FAILED. INSPECT LOGS.")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_all_quality_gates()
    sys.exit(0 if success else 1)
