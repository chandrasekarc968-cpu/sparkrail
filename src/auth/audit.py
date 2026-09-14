import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.auth.models import AuditLogTable, UserTable

GENESIS_HASH = "0" * 64


def log_audit_event(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str,
    user: Optional[UserTable] = None,
    user_id: Optional[str] = None,
    pf_number: Optional[str] = None,
    metadata_diff: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLogTable:
    """
    Creates an immutable, cryptographically chained audit log entry for critical railway operations.
    Binds the previous record's SHA-256 hash to ensure tamper evidence.
    """
    uid = user.id if user else user_id
    pfn = user.pf_number if user else pf_number

    # Retrieve preceding record to chain hashes
    last_record = db.query(AuditLogTable).order_by(desc(AuditLogTable.timestamp), desc(AuditLogTable.id)).first()
    prev_hash = last_record.current_hash if last_record else GENESIS_HASH

    event_id = f"AUDIT-{uuid.uuid4().hex[:12].upper()}"
    now_dt = datetime.now(timezone.utc)
    timestamp_str = now_dt.isoformat()

    diff_str = json.dumps(metadata_diff or {}, sort_keys=True)
    canonical = (
        f"{prev_hash}:{event_id}:{action}:{uid or 'ANON'}:{pfn or 'NONE'}:"
        f"{resource_type}:{resource_id}:{timestamp_str}:{diff_str}"
    )
    curr_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    audit_entry = AuditLogTable(
        id=event_id,
        user_id=uid,
        pf_number=pfn,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        timestamp=now_dt,
        timestamp_str=timestamp_str,
        ip_address=ip_address,
        metadata_diff=diff_str,
        previous_hash=prev_hash,
        current_hash=curr_hash
    )

    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)

    # Optional: mirror into advisory.py in-memory audit chain if loaded
    try:
        from src.api.advisory import AUDIT_REPO
        role_str = (user.role.value if hasattr(user.role, "value") else str(user.role)) if user else "UNKNOWN"
        AUDIT_REPO.append_event(
            event_type="OPERATIONAL_AUDIT",
            user_id=uid or "UNKNOWN",
            role=role_str,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=metadata_diff or {},
            ip_address=ip_address
        )
    except Exception:
        pass

    return audit_entry


def verify_audit_log_chain(db: Session) -> Tuple[bool, Optional[str]]:
    """
    Verifies the cryptographic SHA-256 chain across all stored AuditLog records.
    Returns (True, None) if unbroken, or (False, reason) if tampering or link breach is detected.
    """
    records = db.query(AuditLogTable).order_by(AuditLogTable.timestamp.asc(), AuditLogTable.id.asc()).all()
    if not records:
        return True, None

    expected_prev = GENESIS_HASH
    for idx, rec in enumerate(records):
        if rec.previous_hash != expected_prev:
            return False, f"Broken link at event {rec.id} (index {idx}): expected prev {expected_prev}, got {rec.previous_hash}"

        ts_str = rec.timestamp_str if hasattr(rec, "timestamp_str") and rec.timestamp_str else (rec.timestamp.isoformat() if hasattr(rec.timestamp, "isoformat") else str(rec.timestamp))
        canonical = (
            f"{rec.previous_hash}:{rec.id}:{rec.action}:{rec.user_id or 'ANON'}:{rec.pf_number or 'NONE'}:"
            f"{rec.resource_type}:{rec.resource_id}:{ts_str}:{rec.metadata_diff or '{}'}"
        )
        recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if recomputed != rec.current_hash:
            return False, f"Tampered hash at event {rec.id} (index {idx}): expected {recomputed}, recorded {rec.current_hash}"

        expected_prev = rec.current_hash

    return True, None
