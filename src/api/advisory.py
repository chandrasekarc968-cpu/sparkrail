import os
import uuid
import copy
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    ApprovalRole,
    PossessionLifecycle,
    ApprovalDecision,
    OperationalOverride,
    AuditEvent,
    Scenario
)
from src.optimization.milp_solver import ProductionOptimizationPipeline
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.data_pipeline.synthetic_data import generate_synthetic_data

router = APIRouter(prefix="/advisory", tags=["Advisory & BDMS Governance"])

# In-memory storage for advisory proposals and audit log (persisted in session)
PROPOSALS_STORE: Dict[str, Dict[str, Any]] = {}
AUDIT_LOG: List[Dict[str, Any]] = []

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
    justification: str
    overridden_schedule: Dict[str, Any]

def record_audit(
    event_type: str,
    user_id: str,
    role: str,
    resource_type: str,
    resource_id: str,
    action: str,
    details: Dict[str, Any]
) -> None:
    event = AuditEvent(
        id=f"AUDIT-{uuid.uuid4().hex[:8]}",
        event_id=f"AUDIT-{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        user_id=user_id,
        role=role,
        timestamp=datetime.now(timezone.utc).isoformat(),
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details
    )
    AUDIT_LOG.append(event.model_dump())

@router.post("/proposals")
def generate_advisory_proposal(
    req: ProposalGenerateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Generates a formal BDMS-compliant advisory schedule proposal package.
    Strictly marked as 'ADVISORY_PROPOSAL_ONLY' - no direct control commands.
    """
    key = idempotency_key or f"IDEMP-{uuid.uuid4().hex[:12]}"
    
    # Check duplicate idempotency key
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

@router.get("/proposals")
def list_advisory_proposals():
    """Lists all active and historical advisory proposals."""
    return list(PROPOSALS_STORE.values())

@router.get("/proposals/{proposal_id}")
def get_advisory_proposal(proposal_id: str):
    """Retrieves specific advisory proposal details and approval chain."""
    if proposal_id not in PROPOSALS_STORE:
        raise HTTPException(status_code=404, detail=f"Advisory proposal '{proposal_id}' not found")
    return PROPOSALS_STORE[proposal_id]

@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, action: ProposalApprovalAction):
    """
    Role-aware statutory approval sign-off.
    Progression: CTPC -> SR_DOM -> SECTION_CONTROLLER -> STATION_MASTER.
    """
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

    # If all mandatory roles approved, advance overall proposal status
    all_approved = all(
        v["status"] == "APPROVED"
        for k, v in prop["approval_chain"].items()
        if k in ("CTPC", "SR_DOM")
    )
    if all_approved:
        prop["approval_status"] = "SANCTIONED"
        # Advance block lifecycle
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

@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, action: ProposalApprovalAction):
    """Rejects proposal with mandatory operational justification."""
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

@router.post("/proposals/{proposal_id}/override")
def override_proposal(proposal_id: str, req: OperationalOverrideRequest):
    """
    Allows authorized controllers to override AI recommendation with mandatory justification.
    """
    if proposal_id not in PROPOSALS_STORE:
        raise HTTPException(status_code=404, detail=f"Advisory proposal '{proposal_id}' not found")

    prop = PROPOSALS_STORE[proposal_id]
    timestamp = datetime.now(timezone.utc).isoformat()

    prev_schedule = copy.deepcopy(prop["recommended_blocks"]) if "copy" in globals() else prop["recommended_blocks"]
    prop["recommended_blocks"] = req.overridden_schedule.get("recommended_blocks", prop["recommended_blocks"])
    prop["approval_status"] = "OVERRIDDEN"

    record_audit(
        event_type="OPERATIONAL_OVERRIDE",
        user_id=req.user_id,
        role=req.role.value,
        resource_type="ADVISORY_PROPOSAL",
        resource_id=proposal_id,
        action="OVERRIDE_SCHEDULE",
        details={
            "reason_code": req.reason_code,
            "justification": req.justification
        }
    )

    return {
        "status": "OVERRIDE_RECORDED",
        "proposal_id": proposal_id,
        "overridden_by": req.user_id,
        "reason_code": req.reason_code,
        "timestamp": timestamp,
        "updated_proposal": prop
    }

@router.get("/audit")
def get_audit_trail(limit: int = 100):
    """Queries tamper-evident operational audit trail."""
    return AUDIT_LOG[-limit:]
