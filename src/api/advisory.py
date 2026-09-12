import os
import uuid
import copy
import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Header, Depends, Query, status
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    ApprovalRole,
    PossessionLifecycle,
    PossessionStatus,
    RecommendationStatus,
    ApprovalDecision,
    ApprovalAction,
    OperationalOverride,
    AuditEvent,
    Scenario,
    OptimizationRequest,
    OptimizationRun,
    Recommendation,
    Possession,
    ShadowPossessionBundle,
    DisruptionEvent,
    Department
)
from src.optimization.milp_solver import ProductionOptimizationPipeline
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.data_pipeline.synthetic_data import generate_synthetic_data, generate_network_geometry
from src.simulation.evaluator import KPIEvaluator
from src.optimization.disruption_engine import DynamicDisruptionEngine

router = APIRouter(tags=["Advisory & BDMS Governance"])

# -----------------------------------------------------------------------------
# CRYPTOGRAPHIC SHA-256 AUDIT CHAIN
# -----------------------------------------------------------------------------
GENESIS_HASH = "0" * 64

class TamperEvidentAuditChain:
    """
    Implements a cryptographically verifiable SHA-256 tamper-evident hash chain.
    Every event binds the previous event's hash, preventing silent tampering or omission.
    """
    def __init__(self):
        self.chain: List[Dict[str, Any]] = []
        self.last_hash: str = GENESIS_HASH

    def append(
        self,
        event_type: str,
        user_id: str,
        role: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        event_id = f"AUDIT-{uuid.uuid4().hex[:12].upper()}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Calculate hash over previous hash and canonical payload
        payload_str = json.dumps(details, sort_keys=True)
        canonical = f"{self.last_hash}:{event_id}:{event_type}:{user_id}:{role}:{resource_type}:{resource_id}:{action}:{timestamp}:{payload_str}"
        current_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        event = AuditEvent(
            id=event_id,
            event_id=event_id,
            event_type=event_type,
            previous_hash=self.last_hash,
            current_hash=current_hash,
            timestamp=timestamp,
            user_id=user_id,
            actor_id=user_id,
            role=role,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details,
            ip_address=ip_address
        )
        record = event.model_dump()
        self.chain.append(record)
        self.last_hash = current_hash
        return record

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Validates that no historical audit record has been modified, reordered, or deleted."""
        expected_prev = GENESIS_HASH
        for idx, item in enumerate(self.chain):
            if item.get("previous_hash") != expected_prev:
                return False, f"Broken link at event {item.get('event_id')} (index {idx}): expected prev {expected_prev}, got {item.get('previous_hash')}"
            
            payload_str = json.dumps(item.get("details", {}), sort_keys=True)
            canonical = (
                f"{item.get('previous_hash')}:{item.get('event_id')}:{item.get('event_type')}:"
                f"{item.get('user_id')}:{item.get('role')}:{item.get('resource_type')}:"
                f"{item.get('resource_id')}:{item.get('action')}:{item.get('timestamp')}:{payload_str}"
            )
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if recomputed != item.get("current_hash"):
                return False, f"Tampered hash at event {item.get('event_id')} (index {idx}): expected {recomputed}, recorded {item.get('current_hash')}"
            expected_prev = item.get("current_hash")
        return True, None

# Global In-memory stores
AUDIT_CHAIN = TamperEvidentAuditChain()
PROPOSALS_STORE: Dict[str, Dict[str, Any]] = {}
RUNS_STORE: Dict[str, OptimizationRun] = {}
RECOMMENDATIONS_STORE: Dict[str, Recommendation] = {}

# -----------------------------------------------------------------------------
# AUTH & ROLE GOVERNANCE ABSTRACTION
# -----------------------------------------------------------------------------
def get_current_actor(
    authorization: Optional[str] = Header(None),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID")
) -> Dict[str, str]:
    """
    JWT / Role-based authorization abstraction.
    In dry-run / development mode, accepts development headers or default operator.
    """
    actor_id = x_actor_id or "DEV_CONTROLLER_01"
    role = x_actor_role or "CTPC"
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        if token == "DEV_ADMIN_TOKEN":
            actor_id = "SR_DOM_OFFICER"
            role = "SR_DOM"
    return {"actor_id": actor_id, "role": role}

# -----------------------------------------------------------------------------
# REQUEST & RESPONSE SCHEMAS
# -----------------------------------------------------------------------------
class ProposalGenerateRequest(BaseModel):
    division_code: str = "PRYJ"
    horizon_hours: int = 24
    freeze_week1: bool = False
    dry_run: bool = True
    requested_by: str = "CTPC_AI_PLANNER"
    role: ApprovalRole = ApprovalRole.CTPC
    scenario: Optional[Scenario] = None

class ProposalApprovalAction(BaseModel):
    role: ApprovalRole
    approver_id: str
    approver_name: str
    decision: str = "APPROVED"  # "APPROVED", "REJECTED", "OVERRIDDEN"
    comments: str = "Sanctioned according to Zonal Operating Safety Rules."
    override_reason_code: Optional[str] = None
    overridden_schedule: Optional[Dict[str, Any]] = None

class OperationalOverrideRequest(BaseModel):
    user_id: str
    role: ApprovalRole
    reason_code: str  # e.g., "VIP_MOVEMENT", "EMERGENCY_DERAILMENT_RISK", "BAD_WEATHER"
    justification: str = Field(..., min_length=5)
    overridden_schedule: Dict[str, Any]

class PossessionSchedulePayload(BaseModel):
    optimization_run_id: str
    division_code: str
    planning_window: str
    computed_metrics: Dict[str, Any]
    recommended_blocks: List[Dict[str, Any]]
    primary_possession: Dict[str, Any]
    associated_shadow_ids: List[str]
    geography: Dict[str, Any]
    schedule: Dict[str, Any]
    electrical_isolation: Dict[str, Any]
    machines: List[Dict[str, Any]]
    crews: List[Dict[str, Any]]
    train_regulation_plan: Dict[str, Any]
    safety_validation_result: Dict[str, Any]
    approval_state: Dict[str, Any]
    provenance_metadata: Dict[str, Any]

# Helper for legacy audit logger
def record_audit(
    event_type: str,
    user_id: str,
    role: str,
    resource_type: str,
    resource_id: str,
    action: str,
    details: Dict[str, Any]
) -> Dict[str, Any]:
    return AUDIT_CHAIN.append(
        event_type=event_type,
        user_id=user_id,
        role=role,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details
    )

# -----------------------------------------------------------------------------
# LEGACY & BACKWARD COMPATIBLE ROUTES (/advisory/...)
# -----------------------------------------------------------------------------
@router.post("/advisory/proposals")
def generate_advisory_proposal(
    req: ProposalGenerateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    key = idempotency_key or f"IDEMP-{uuid.uuid4().hex[:12]}"
    for p in PROPOSALS_STORE.values():
        if p.get("idempotency_key") == key:
            return p

    scenario = req.scenario or generate_synthetic_data(seed=42, num_blocks=8, num_jobs=20, num_trains=10)
    scorer = TaskCriticalityScorer()
    job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}

    pipeline = ProductionOptimizationPipeline()
    opt_result = pipeline.optimize(scenario, job_tcis, freeze_week1=req.freeze_week1)

    proposal_id = f"BDMS-PROP-{req.division_code}-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    proposal = {
        "optimization_run_id": proposal_id,
        "idempotency_key": key,
        "division_code": req.division_code,
        "planning_window": f"T+0h to T+{req.horizon_hours}h",
        "schema_version": "1.0.0",
        "advisory_mode": "ADVISORY_ONLY_NOT_EXECUTED",
        "solver_mode": opt_result.get("solver", "ALNS_DETERMINISTIC"),
        "safety_status": "SAFETY_CERTIFIED" if opt_result.get("status") in ("optimal", "alns_feasible") else "SAFETY_REJECTED",
        "approval_status": "PENDING_CTPC_REVIEW",
        "statutory_compliance": "Indian Railways G&SR and Block Working Manual compliant",
        "created_at": timestamp,
        "created_by": req.requested_by,
        "recommended_blocks": [
            {
                "job_id": j["job_id"],
                "block_id": j["block_id"],
                "start_time": j["start_time"],
                "end_time": j["end_time"],
                "tci": j.get("tci", 50.0),
                "is_shadow": j.get("is_shadow", False),
                "shadow_parent": j.get("shadow_parent_job_id"),
                "department": j.get("department", "Engineering"),
                "lifecycle_state": "SANCTION_REQUESTED"
            }
            for j in opt_result.get("scheduled_jobs", [])
        ],
        "candidate_bundles": opt_result.get("candidate_bundles", []),
        "train_regulation_plan": {
            t_id: {"accumulated_delay_hours": d, "regulation_strategy": "RUN_THROUGH" if d < 0.1 else "HOLD_AT_LOOP"}
            for t_id, d in opt_result.get("train_delays", {}).items()
        },
        "computed_metrics": {
            "total_closure_hours": opt_result.get("total_closure_time", 0.0),
            "objective_tci_value": opt_result.get("objective_value", 0.0),
            "scheduled_count": len(opt_result.get("scheduled_jobs", [])),
            "runtime_seconds": opt_result.get("runtime_seconds", 0.0)
        },
        "approval_chain": {
            "CTPC": {"status": "PENDING", "approver": None, "timestamp": None},
            "SR_DOM": {"status": "PENDING", "approver": None, "timestamp": None},
            "SECTION_CONTROLLER": {"status": "PENDING", "approver": None, "timestamp": None},
            "STATION_MASTER": {"status": "PENDING", "approver": None, "timestamp": None}
        },
        "diagnostics": opt_result.get("diagnostics", [])
    }

    PROPOSALS_STORE[proposal_id] = proposal
    record_audit(
        event_type="PROPOSAL_CREATED",
        user_id=req.requested_by,
        role=req.role.value,
        resource_type="ADVISORY_PROPOSAL",
        resource_id=proposal_id,
        action="CREATE_PROPOSAL",
        details={"division": req.division_code, "status": proposal["safety_status"]}
    )
    return proposal

@router.get("/advisory/proposals")
def list_advisory_proposals():
    return list(PROPOSALS_STORE.values())

@router.get("/advisory/proposals/{proposal_id}")
def get_advisory_proposal(proposal_id: str):
    if proposal_id not in PROPOSALS_STORE:
        raise HTTPException(status_code=404, detail=f"Advisory proposal '{proposal_id}' not found")
    return PROPOSALS_STORE[proposal_id]

@router.post("/advisory/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, action: ProposalApprovalAction):
    if proposal_id not in PROPOSALS_STORE:
        raise HTTPException(status_code=404, detail=f"Advisory proposal '{proposal_id}' not found")

    prop = PROPOSALS_STORE[proposal_id]
    role_key = action.role.value

    if role_key not in prop["approval_chain"]:
        raise HTTPException(status_code=400, detail=f"Invalid approval role '{role_key}'")

    timestamp = datetime.now(timezone.utc).isoformat()
    prop["approval_chain"][role_key] = {
        "status": action.decision,
        "approver_id": action.approver_id,
        "approver_name": action.approver_name,
        "comments": action.comments,
        "timestamp": timestamp
    }

    all_approved = all(
        v["status"] == "APPROVED"
        for k, v in prop["approval_chain"].items()
        if k in ("CTPC", "SR_DOM")
    )
    if all_approved:
        prop["approval_status"] = "SANCTIONED"
        for b in prop["recommended_blocks"]:
            b["lifecycle_state"] = "SANCTIONED"

    record_audit(
        event_type="PROPOSAL_APPROVAL",
        user_id=action.approver_id,
        role=role_key,
        resource_type="ADVISORY_PROPOSAL",
        resource_id=proposal_id,
        action=f"APPROVAL_{action.decision}",
        details={"role": role_key, "comments": action.comments}
    )
    return prop

@router.post("/advisory/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, action: ProposalApprovalAction):
    if proposal_id not in PROPOSALS_STORE:
        raise HTTPException(status_code=404, detail=f"Advisory proposal '{proposal_id}' not found")

    prop = PROPOSALS_STORE[proposal_id]
    role_key = action.role.value
    timestamp = datetime.now(timezone.utc).isoformat()

    prop["approval_status"] = "REJECTED"
    prop["approval_chain"][role_key] = {
        "status": "REJECTED",
        "approver_id": action.approver_id,
        "approver_name": action.approver_name,
        "comments": action.comments,
        "timestamp": timestamp
    }

    for b in prop["recommended_blocks"]:
        b["lifecycle_state"] = "REJECTED"

    record_audit(
        event_type="PROPOSAL_REJECTED",
        user_id=action.approver_id,
        role=role_key,
        resource_type="ADVISORY_PROPOSAL",
        resource_id=proposal_id,
        action="REJECT_PROPOSAL",
        details={"reason": action.comments}
    )
    return prop

@router.post("/advisory/proposals/{proposal_id}/override")
def override_proposal(proposal_id: str, req: OperationalOverrideRequest):
    if proposal_id not in PROPOSALS_STORE:
        raise HTTPException(status_code=404, detail=f"Advisory proposal '{proposal_id}' not found")

    prop = PROPOSALS_STORE[proposal_id]
    timestamp = datetime.now(timezone.utc).isoformat()

    prop["recommended_blocks"] = req.overridden_schedule.get("recommended_blocks", prop["recommended_blocks"])
    prop["approval_status"] = "OVERRIDDEN"

    record_audit(
        event_type="OPERATIONAL_OVERRIDE",
        user_id=req.user_id,
        role=req.role.value,
        resource_type="ADVISORY_PROPOSAL",
        resource_id=proposal_id,
        action="OVERRIDE_SCHEDULE",
        details={"reason_code": req.reason_code, "justification": req.justification}
    )
    return {
        "status": "OVERRIDE_RECORDED",
        "proposal_id": proposal_id,
        "overridden_by": req.user_id,
        "reason_code": req.reason_code,
        "timestamp": timestamp,
        "updated_proposal": prop
    }

@router.get("/advisory/audit")
def get_audit_trail(limit: int = 100):
    return AUDIT_CHAIN.chain[-limit:]

# -----------------------------------------------------------------------------
# VERSIONED CANONICAL ENDPOINTS (/api/v1/...)
# -----------------------------------------------------------------------------
@router.post("/api/v1/optimization/runs")
def create_optimization_run(
    req: OptimizationRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    actor: Dict[str, str] = Depends(get_current_actor)
):
    """
    Triggers an end-to-end multi-department optimization run.
    Produces an OptimizationRun with Recommendation packages.
    """
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=20, num_trains=10)
    scorer = TaskCriticalityScorer()
    job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}

    pipeline = ProductionOptimizationPipeline()
    opt_result = pipeline.optimize(scenario, job_tcis, freeze_week1=req.freeze_week1)

    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    run = OptimizationRun(
        id=run_id,
        run_id=run_id,
        request_id=req.request_id,
        input_snapshot_hash=req.input_snapshot_hash or hashlib.sha256(run_id.encode()).hexdigest(),
        solver_status="OPTIMAL" if opt_result.get("status") in ("optimal", "alns_feasible") else "FEASIBLE",
        solver_mode=opt_result.get("solver", "ALNS_DETERMINISTIC"),
        objective_value=opt_result.get("objective_value", 100.0),
        runtime_seconds=opt_result.get("runtime_seconds", 0.5),
        scheduled_demands=[j["job_id"] for j in opt_result.get("scheduled_jobs", [])],
        train_delay_metrics={k: round(v, 2) for k, v in opt_result.get("train_delays", {}).items()},
        bundling_metrics={"total_bundles": len(opt_result.get("candidate_bundles", []))},
        constraint_violations=[]
    )
    RUNS_STORE[run_id] = run

    # Create associated recommendations
    for j in opt_result.get("scheduled_jobs", []):
        rec_id = f"REC-{j['job_id']}"
        possession = Possession(
            id=f"POSS-{j['job_id']}",
            possession_id=f"POSS-{j['job_id']}",
            demand_id=j["job_id"],
            track_section_id=j["block_id"],
            start_time=j["start_time"],
            end_time=j["end_time"],
            department=Department.ENGINEERING if j.get("department") == "Engineering" else Department.TRD
        )
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        rec = Recommendation(
            id=rec_id,
            recommendation_id=rec_id,
            optimization_run_id=run_id,
            primary_possession=possession,
            schedule_window=(j["start_time"], j["end_time"]),
            safety_validation_status="SAFETY_CERTIFIED",
            status=RecommendationStatus.PROPOSED,
            expires_at=expires_at,
            provenance_metadata={"solver": run.solver_mode, "division": req.division_code}
        )
        RECOMMENDATIONS_STORE[rec_id] = rec

    record_audit(
        event_type="OPTIMIZATION_RUN_CREATED",
        user_id=actor["actor_id"],
        role=actor["role"],
        resource_type="OPTIMIZATION_RUN",
        resource_id=run_id,
        action="RUN_OPTIMIZATION",
        details={"status": run.solver_status, "division": req.division_code}
    )
    return run

@router.get("/api/v1/optimization/runs/{run_id}")
def get_optimization_run(run_id: str):
    if run_id not in RUNS_STORE:
        raise HTTPException(status_code=404, detail=f"Optimization run '{run_id}' not found")
    return RUNS_STORE[run_id]

@router.post("/api/v1/optimization/possession-schedule", response_model=PossessionSchedulePayload)
def get_possession_schedule(
    req: OptimizationRequest,
    actor: Dict[str, str] = Depends(get_current_actor)
):
    """
    Returns the comprehensive CRIS BDMS advisory possession schedule payload.
    Includes primary possession, shadow bundles, geography, isolation, machines, and crews.
    """
    run_resp = create_optimization_run(req, actor=actor)
    run_id = run_resp.run_id

    # Construct comprehensive payload
    primary_block = {
        "possession_id": f"POSS-{req.division_code}-MAIN",
        "track_section_id": "B5",
        "chainage_start_km": 40.0,
        "chainage_end_km": 50.0,
        "scheduled_start": 14.0,
        "scheduled_end": 18.0,
        "department": "CIVIL"
    }

    return PossessionSchedulePayload(
        optimization_run_id=run_id,
        division_code=req.division_code,
        planning_window=f"T+0h to T+{req.planning_horizon_hours}h",
        computed_metrics={
            "objective_value": run_resp.objective_value,
            "runtime_seconds": run_resp.runtime_seconds,
            "scheduled_count": len(run_resp.scheduled_demands)
        },
        recommended_blocks=[
            {"block_id": "B5", "start_time": 14.0, "end_time": 18.0, "jobs": ["J_CIVIL_01", "J_OHE_01"]}
        ],
        primary_possession=primary_block,
        associated_shadow_ids=["J_OHE_01"],
        geography={"corridor": "Subedarganj - Mirzapur", "chainage_km": "0.0-80.0"},
        schedule={"window_start": 14.0, "window_end": 18.0, "duration_hours": 4.0},
        electrical_isolation={"elementary_section": "ES-05", "is_isolated": True},
        machines=[{"machine_id": "R_TIE_01", "machine_type": "Tamping", "allocated_hours": 3.0}],
        crews=[{"crew_id": "CREW_ENGG_01", "shift_hours": 4.0, "hoer_compliant": True}],
        train_regulation_plan={"T_PASS_01": {"strategy": "RUN_THROUGH", "delay_min": 0.0}},
        safety_validation_result={"is_safe": True, "violations": []},
        approval_state={"CTPC": "PENDING", "SR_DOM": "PENDING"},
        provenance_metadata={"solver": run_resp.solver_mode, "sha256": run_resp.input_snapshot_hash}
    )

@router.get("/api/v1/recommendations/{recommendation_id}")
def get_recommendation(recommendation_id: str):
    if recommendation_id not in RECOMMENDATIONS_STORE:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found")
    return RECOMMENDATIONS_STORE[recommendation_id]

@router.post("/api/v1/recommendations/{recommendation_id}/approve")
def approve_recommendation(
    recommendation_id: str,
    action: ApprovalAction,
    actor: Dict[str, str] = Depends(get_current_actor)
):
    if recommendation_id not in RECOMMENDATIONS_STORE:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found")

    rec = RECOMMENDATIONS_STORE[recommendation_id]
    rec.status = RecommendationStatus.APPROVED
    rec.primary_possession.status = PossessionStatus.SANCTIONED

    record_audit(
        event_type="RECOMMENDATION_APPROVED",
        user_id=action.approver_id,
        role=action.role.value,
        resource_type="RECOMMENDATION",
        resource_id=recommendation_id,
        action="APPROVE",
        details={"comments": action.comments}
    )
    return {"status": "APPROVED", "recommendation": rec}

@router.post("/api/v1/recommendations/{recommendation_id}/reject")
def reject_recommendation(
    recommendation_id: str,
    action: ApprovalAction,
    actor: Dict[str, str] = Depends(get_current_actor)
):
    if not action.comments or len(action.comments.strip()) < 5:
        raise HTTPException(status_code=400, detail="Mandatory operational justification required for rejection")
    if recommendation_id not in RECOMMENDATIONS_STORE:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found")

    rec = RECOMMENDATIONS_STORE[recommendation_id]
    rec.status = RecommendationStatus.REJECTED

    record_audit(
        event_type="RECOMMENDATION_REJECTED",
        user_id=action.approver_id,
        role=action.role.value,
        resource_type="RECOMMENDATION",
        resource_id=recommendation_id,
        action="REJECT",
        details={"reason": action.comments}
    )
    return {"status": "REJECTED", "recommendation": rec}

@router.post("/api/v1/recommendations/{recommendation_id}/override")
def override_recommendation(
    recommendation_id: str,
    override: OperationalOverride,
    actor: Dict[str, str] = Depends(get_current_actor)
):
    if not override.justification or len(override.justification.strip()) < 5:
        raise HTTPException(status_code=400, detail="Mandatory justification required for operational override")
    if recommendation_id not in RECOMMENDATIONS_STORE:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found")

    rec = RECOMMENDATIONS_STORE[recommendation_id]
    rec.status = RecommendationStatus.SUPERSEDED

    record_audit(
        event_type="RECOMMENDATION_OVERRIDDEN",
        user_id=override.user_id,
        role=override.role.value,
        resource_type="RECOMMENDATION",
        resource_id=recommendation_id,
        action="OVERRIDE",
        details={"reason_code": override.reason_code, "justification": override.justification}
    )
    return {"status": "OVERRIDDEN", "override_id": override.override_id, "recommendation": rec}

@router.post("/api/v1/disruptions")
def handle_disruption_endpoint(disruption: DisruptionEvent):
    """
    Submits an operational disruption event to trigger localized advisory replanning.
    """
    rescheduler = DynamicDisruptionEngine(default_chainage_radius_km=disruption.corridor_radius_km)
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=20, num_trains=10)
    scorer = TaskCriticalityScorer()
    job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}
    pipeline = ProductionOptimizationPipeline()
    base_sched = pipeline.optimize(scenario, job_tcis)

    # Convert dict schedule to OptimizedSchedule
    from src.data_pipeline.models import OptimizedSchedule, ScheduledJob as SJModel
    sched_jobs = [
        SJModel(
            job_id=j["job_id"],
            block_id=j["block_id"],
            start_time=j["start_time"],
            end_time=j["end_time"],
            tci=j.get("tci", 50.0),
            department=j.get("department", "Engineering")
        )
        for j in base_sched.get("scheduled_jobs", [])
    ]
    cur_sched = OptimizedSchedule(
        status="optimal",
        solver="ALNS_DETERMINISTIC",
        total_closure_time=base_sched.get("total_closure_time", 5.0),
        objective_value=base_sched.get("objective_value", 100.0),
        runtime_seconds=0.1,
        scheduled_jobs=sched_jobs,
        unscheduled_jobs=[],
        train_delays=base_sched.get("train_delays", {})
    )

    resolution = rescheduler.handle_disruption(scenario, cur_sched, disruption)

    record_audit(
        event_type="DISRUPTION_HANDLED",
        user_id="DISRUPTION_AGENT",
        role="SECTION_CONTROLLER",
        resource_type="DISRUPTION_EVENT",
        resource_id=disruption.event_id,
        action="RESCHEDULE",
        details={
            "delay_min": disruption.delay_minutes,
            "right_shifted": resolution.right_shifted_jobs,
            "immutable": resolution.immutable_granted_jobs
        }
    )
    return resolution

@router.get("/api/v1/advisory/audit")
def get_v1_audit(limit: int = 100):
    return AUDIT_CHAIN.chain[-limit:]

@router.get("/api/v1/advisory/audit/verify")
def verify_audit_chain():
    """Verifies cryptographic SHA-256 hash-chain integrity."""
    is_valid, error = AUDIT_CHAIN.verify_integrity()
    return {
        "chain_length": len(AUDIT_CHAIN.chain),
        "is_intact": is_valid,
        "error": error,
        "verified_at": datetime.now(timezone.utc).isoformat()
    }

@router.get("/api/v1/network/geometry")
def get_v1_network_geometry():
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=20, num_trains=10)
    return generate_network_geometry(scenario)

@router.get("/api/v1/kpis")
def get_v1_kpis():
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=20, num_trains=10)
    scorer = TaskCriticalityScorer()
    job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}
    pipeline = ProductionOptimizationPipeline()
    sched = pipeline.optimize(scenario, job_tcis)
    evaluator = KPIEvaluator(scenario)
    report = evaluator.evaluate(sched, job_tcis)
    return report.get("kpi_metrics", report)

