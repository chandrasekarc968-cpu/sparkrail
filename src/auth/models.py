import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Text,
    ForeignKey,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Department(str, Enum):
    OPERATING = "OPERATING"
    CIVIL = "CIVIL"
    TRD = "TRD"
    SNT = "SNT"
    ADMIN = "ADMIN"


class Role(str, Enum):
    SR_DOM = "SR_DOM"
    SECTION_CONTROLLER = "SECTION_CONTROLLER"
    CTPC = "CTPC"
    SSE_PWAY = "SSE_PWAY"
    SSE_TRD = "SSE_TRD"
    SSE_SIGNAL = "SSE_SIGNAL"
    STATION_MASTER = "STATION_MASTER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    ADMIN = "ADMIN"
    READ_ONLY_OPERATOR = "READ_ONLY_OPERATOR"


# Role-to-Capabilities Mapping for Indian Railways BDMS
ROLE_CAPABILITIES: Dict[Role, List[str]] = {
    Role.READ_ONLY_OPERATOR: [
        "VIEW_CORRIDOR",
        "VIEW_MAREY_CHART",
        "VIEW_SCHEDULE",
        "VIEW_AUDIT_LOG"
    ],
    Role.ADMIN: [
        "MANAGE_USERS",
        "VIEW_AUDIT_LOGS",
        "SYSTEM_CONFIG",
        "SECURITY_AUDIT",
        "OVERRIDE_AI_RECOMMENDATION",
        "ALL_PERMISSIONS"
    ],
    Role.SR_DOM: [
        "SANCTION_BLOCK",
        "EMERGENCY_OVERRIDE",
        "VIEW_CORRIDOR",
        "APPROVE_SCHEDULE",
        "SIGN_OFF_ADVISORY",
        "REJECT_BLOCK",
        "VIEW_AUDIT_LOG"
    ],
    Role.SECTION_CONTROLLER: [
        "DISPATCH_TRAIN",
        "GRANT_BLOCK",
        "GENERATE_PRIVATE_NUMBER",
        "VIEW_MAREY_CHART",
        "CANCEL_BLOCK",
        "SIGN_OFF_ADVISORY",
        "VIEW_CORRIDOR"
    ],
    Role.CTPC: [
        "APPROVE_OHE_ISOLATION",
        "POWER_BLOCK_PERMIT",
        "TRD_SIGN_OFF",
        "VIEW_OHE_STATUS",
        "SIGN_OFF_ADVISORY"
    ],
    Role.SSE_PWAY: [
        "REQUEST_CIVIL_BLOCK",
        "TRACK_FITNESS_CERTIFICATE",
        "REPORT_SPEED_RESTRICTION",
        "VIEW_CORRIDOR"
    ],
    Role.SSE_TRD: [
        "REQUEST_POWER_BLOCK",
        "OHE_BREAKDOWN_ALERT",
        "SUBMIT_TRD_REQUISITION",
        "VIEW_CORRIDOR"
    ],
    Role.SSE_SIGNAL: [
        "REQUEST_DISCONNECTION",
        "SIGNAL_FAILURE_LOG",
        "RECONNECTION_NOTICE",
        "VIEW_CORRIDOR"
    ],
    Role.STATION_MASTER: [
        "EXCHANGE_PRIVATE_NUMBER",
        "LINE_CLEAR_CONSENT",
        "LOCK_POINTS",
        "STATION_BLOCK_REGISTER",
        "SIGN_OFF_ADVISORY"
    ],
    Role.SYSTEM_ADMIN: [
        "MANAGE_USERS",
        "VIEW_AUDIT_LOGS",
        "SYSTEM_CONFIG",
        "SECURITY_AUDIT",
        "OVERRIDE_AI_RECOMMENDATION",
        "ALL_PERMISSIONS"
    ]
}


# -----------------------------------------------------------------------------
# SQLALCHEMY ORM TABLES
# -----------------------------------------------------------------------------

class UserTable(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pf_number = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    department = Column(SAEnum(Department, native_enum=False), nullable=False)
    role = Column(SAEnum(Role, native_enum=False), nullable=False)
    division_code = Column(String(32), nullable=False, index=True)
    zone_code = Column(String(16), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    refresh_tokens = relationship("RefreshTokenTable", back_populates="user", cascade="all, delete-orphan")


class RefreshTokenTable(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    replaced_by_token_hash = Column(String(64), nullable=True)

    user = relationship("UserTable", back_populates="refresh_tokens")


class AuditLogTable(Base):
    __tablename__ = "audit_logs"

    id = Column(String(48), primary_key=True, default=lambda: f"AUDIT-{uuid.uuid4().hex[:12].upper()}")
    user_id = Column(String(36), nullable=True, index=True)
    pf_number = Column(String(64), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    timestamp_str = Column(String(64), nullable=False)
    ip_address = Column(String(64), nullable=True)
    metadata_diff = Column(Text, nullable=True)
    previous_hash = Column(String(64), nullable=False)
    current_hash = Column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_action_timestamp", "action", "timestamp"),
    )


# -----------------------------------------------------------------------------
# PYDANTIC SCHEMAS
# -----------------------------------------------------------------------------

class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    pf_number: str
    email: str
    full_name: str
    department: Department
    role: Role
    division_code: str
    zone_code: str
    is_active: bool
    last_login: Optional[datetime] = None
    capabilities: List[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="Provident Fund Number (e.g. PF-ECR-90801) or official railway email")
    password: str = Field(..., description="User password")


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = Field(None, description="Refresh token string if not supplied in HTTP-only cookie")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=900, description="Access token expiration time in seconds")
    user: UserResponse


class UserJurisdiction(BaseModel):
    division_code: str
    zone_code: str
    department: Department
    role: Role
    authorized_actions: List[str]
