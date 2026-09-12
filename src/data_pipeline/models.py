import time
import math
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

class Department(str, Enum):
    CIVIL = "CIVIL"
    TRD = "TRD"
    SIGNAL = "SIGNAL"
    TELECOM = "TELECOM"
    # Legacy aliases for backward compatibility
    ENGINEERING = "Engineering"
    OHE = "OHE"
    S_AND_T = "S&T"

def canonical_department(dept: Any) -> str:
    """Normalizes any department string or enum to canonical IR department code."""
    val = dept.value if isinstance(dept, Department) else str(dept)
    val_upper = val.strip().upper()
    if val_upper in ("CIVIL", "ENGINEERING"):
        return "CIVIL"
    if val_upper in ("TRD", "OHE", "ELECTRICAL"):
        return "TRD"
    if val_upper in ("SIGNAL", "S&T", "S_AND_T", "SIGNALLING"):
        return "SIGNAL"
    if val_upper in ("TELECOM", "TELECOMMUNICATION"):
        return "TELECOM"
    return val_upper

class Resource(BaseModel):
    id: str
    name: str
    capacity: int = Field(..., gt=0)
    department: Optional[Department] = None
    available_units: Optional[int] = None

class TrackBlock(BaseModel):
    id: str
    chainage_start: float = Field(..., ge=0.0)
    chainage_end: float = Field(..., gt=0.0)
    description: str
    speed_restriction_kmh: Optional[float] = 100.0
    track_type: Optional[str] = "Mainline"
    electrification_status: Optional[str] = "25kV AC"
    signaling_type: Optional[str] = "Automatic"

    @model_validator(mode="after")
    def check_chainage(self) -> "TrackBlock":
        if self.chainage_start >= self.chainage_end:
            raise ValueError(f"chainage_start ({self.chainage_start}) must be strictly less than chainage_end ({self.chainage_end})")
        return self

class Train(BaseModel):
    id: str
    name: Optional[str] = None
    category: str = Field(..., description="e.g., 'premium', 'express', 'freight'")
    scheduled_start: float = Field(..., ge=0.0)
    scheduled_end: float = Field(..., gt=0.0)
    route: List[str] = Field(..., min_length=1)
    min_travel_times: Dict[str, float]
    max_speed_kmh: Optional[float] = 130.0
    current_block: Optional[str] = None
    current_delay_min: Optional[float] = 0.0
    
    @model_validator(mode="after")
    def check_time(self) -> "Train":
        if self.scheduled_start >= self.scheduled_end:
            raise ValueError("scheduled_start must be strictly less than scheduled_end")
        return self

class TCIInputs(BaseModel):
    safety_severity: float = Field(..., ge=0.0, le=1.0)
    traffic_impact: float = Field(..., ge=0.0, le=1.0)
    degradation_indicator: float = Field(..., ge=0.0, le=1.0)
    overdue_days: int = Field(..., ge=0)
    inspection_urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    data_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def sync_tci_aliases(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "safety_criticality" in values and "safety_severity" not in values:
                values["safety_severity"] = values["safety_criticality"]
            if "asset_degradation" in values and "degradation_indicator" not in values:
                values["degradation_indicator"] = values["asset_degradation"]
            if "deferral_penalty" in values and "overdue_days" not in values:
                values["overdue_days"] = int(values["deferral_penalty"] * 30)
        return values

class TCIExplanation(BaseModel):
    safety_component: float
    delay_component: float
    degradation_component: float
    overdue_component: float
    inspection_urgency_component: float = 0.0
    data_confidence_penalty: float = 0.0
    raw_inputs: TCIInputs
    formula_breakdown: Optional[str] = None
    model_mode: Optional[str] = "rule_based"
    model_version: Optional[str] = "1.0.0"

class ScoredJob(BaseModel):
    job_id: str
    tci: float
    explanation: TCIExplanation

class MaintenanceJob(BaseModel):
    id: str
    department: Department
    block_id: str
    duration: float = Field(..., gt=0.0)
    required_resources: Dict[str, int]
    tci_inputs: TCIInputs
    is_fixed: bool = False
    fixed_start: Optional[float] = None
    job_type: Optional[str] = "Routine Corridor Maintenance"
    due_date: Optional[str] = None
    safety_clearance_required: Optional[str] = "Standard Track Possession Clearance"
    chainage_km: Optional[str] = None
    
    @model_validator(mode="after")
    def check_fixed(self) -> "MaintenanceJob":
        if self.is_fixed and self.fixed_start is None:
            raise ValueError("fixed_start is required if is_fixed is True")
        return self

class FixedMaintenanceBlock(BaseModel):
    """Immutable, external planned maintenance block."""
    id: str
    block_id: str
    start_time: float
    end_time: float
    reason: Optional[str] = "Pre-scheduled Mega Block"
    department: Optional[Department] = None

class Scenario(BaseModel):
    blocks: List[TrackBlock]
    trains: List[Train]
    jobs: List[MaintenanceJob]
    resources: List[Resource]
    fixed_blocks: List[FixedMaintenanceBlock] = []

class ScheduleWindow(BaseModel):
    block_id: str
    start_time: float
    end_time: float
    window_type: Optional[str] = "maintenance"

class ScheduledJob(BaseModel):
    job_id: str
    block_id: str
    start_time: float
    end_time: float
    tci: float
    department: Department
    is_shadow_block: bool = False
    shadow_with_jobs: List[str] = []
    assigned_resources: List[str] = []

class UnscheduledJobReason(BaseModel):
    job_id: str
    reason: str
    conflict_with: Optional[str] = None
    potential_window: Optional[str] = None

# 3D Geometry and Canonical Spatial Representations
class Coordinate3D(BaseModel):
    """
    Explicit 3D coordinate convention for railway corridor space:
    - X: Longitudinal corridor position along track alignment in meters (e.g. -400 to +400 scaled)
    - Y: Elevation / vertical gradient profile in meters
    - Z: Lateral offset from track centerline or curvature deviation in meters
    """
    x: float
    y: float
    z: float

    @model_validator(mode="after")
    def validate_finite(self) -> "Coordinate3D":
        for axis, val in [("x", self.x), ("y", self.y), ("z", self.z)]:
            if not math.isfinite(val):
                raise ValueError(f"Coordinate '{axis}' must be a finite number, got {val}")
        return self

Vector3D = Coordinate3D

class GeometryNode(BaseModel):
    """Canonical base model for nodes positioned along the railway network."""
    id: str
    entity_type: str = "node"
    coordinates: Optional[Coordinate3D] = None
    position: Optional[Coordinate3D] = None  # Backward-compatible alias
    chainage_km: float = Field(..., ge=0.0)
    referenced_block_id: Optional[str] = None
    referenced_asset_id: Optional[str] = None
    geometry_source: str = "synthetic"
    geometry_schema_version: str = "1.0.0"
    schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def sync_coords(self) -> "GeometryNode":
        if self.position is None and self.coordinates is not None:
            self.position = self.coordinates
        elif self.coordinates is None and self.position is not None:
            self.coordinates = self.position
        elif self.coordinates is None and self.position is None:
            raise ValueError(f"Node '{self.id}' must provide either 'coordinates' or 'position'")
        return self

class StationNode(GeometryNode):
    name: str
    code: str
    entity_type: str = "station"
    node_type: str = "station"  # "station", "junction", "terminal"
    platforms: int = 2
    connected_blocks: List[str] = []

class JunctionNode(GeometryNode):
    name: str
    code: str
    entity_type: str = "junction"
    node_type: str = "junction"
    diverging_blocks: List[str] = []
    switch_type: str = "Turnout 1-in-12"
    interlocking_status: str = "Active"

class GeometryTrack(BaseModel):
    """
    Canonical 3D track model representing physical track blocks with 3D centerline path.
    """
    id: Optional[str] = None
    block_id: str
    entity_type: str = "track"
    name: str = ""
    start_coord: Coordinate3D
    end_coord: Coordinate3D
    path_points: List[Coordinate3D] = Field(..., min_length=2)
    length_km: float = Field(..., gt=0.0)
    chainage_start: float = Field(..., ge=0.0)
    chainage_end: float = Field(..., gt=0.0)
    elevation_profile: List[float] = []
    track_type: str = "Mainline"
    electrification: str = "25kV AC"
    gauge: str = "Broad Gauge 1676mm"
    speed_limit_kmh: float = 130.0
    referenced_block_id: Optional[str] = None
    geometry_source: str = "synthetic"
    geometry_schema_version: str = "1.0.0"
    schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def check_track_invariants(self) -> "GeometryTrack":
        if not self.id:
            self.id = f"TRACK_{self.block_id}"
        if not self.referenced_block_id:
            self.referenced_block_id = self.block_id
        if self.chainage_start >= self.chainage_end:
            raise ValueError(
                f"Track '{self.block_id}' chainage_start ({self.chainage_start}) must be strictly less than chainage_end ({self.chainage_end})"
            )
        return self

TrackGeometry = GeometryTrack

class SignalMarker(BaseModel):
    id: str
    entity_type: str = "signal"
    block_id: str
    referenced_block_id: Optional[str] = None
    chainage_km: float = Field(..., ge=0.0)
    coordinates: Optional[Coordinate3D] = None
    position: Coordinate3D
    aspect: str = "clear"  # "clear", "caution", "danger"
    direction: str = "UP"  # "UP", "DOWN"
    geometry_source: str = "synthetic"
    geometry_schema_version: str = "1.0.0"
    schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def sync_signal(self) -> "SignalMarker":
        if not self.referenced_block_id:
            self.referenced_block_id = self.block_id
        if self.coordinates is None:
            self.coordinates = self.position
        return self

class OHEMast(BaseModel):
    id: str
    entity_type: str = "ohe_mast"
    block_id: str
    referenced_block_id: Optional[str] = None
    coordinates: Optional[Coordinate3D] = None
    position: Coordinate3D
    chainage_km: Optional[float] = None
    catenary_height_m: float = 5.5
    is_isolated: bool = False
    geometry_source: str = "synthetic"
    geometry_schema_version: str = "1.0.0"
    schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def sync_mast(self) -> "OHEMast":
        if not self.referenced_block_id:
            self.referenced_block_id = self.block_id
        if self.coordinates is None:
            self.coordinates = self.position
        return self

class ConflictType(str, Enum):
    TRAIN_BLOCK = "train_vs_block"
    PREMIUM_TRAIN = "premium_train_risk"
    DEPT_INCOMPATIBLE = "incompatible_department"
    RESOURCE_OVERALLOCATION = "resource_overallocation"
    FIXED_BLOCK_COLLISION = "fixed_block_collision"
    SAFETY_CLEARANCE = "insufficient_safety_clearance"
    OVERDUE_CRITICAL = "overdue_critical_maintenance"

class NetworkConflict(BaseModel):
    id: str
    entity_type: str = "conflict"
    conflict_type: ConflictType
    severity: str  # "CRITICAL", "MAJOR", "WARNING", "INFO"
    block_id: str
    referenced_block_id: Optional[str] = None
    title: str
    description: str
    affected_jobs: List[str] = []
    affected_trains: List[str] = []
    time_window: Optional[Dict[str, float]] = None
    suggested_resolution: str = ""
    coordinates: Optional[Coordinate3D] = None
    position: Optional[Coordinate3D] = None
    geometry_source: str = "synthetic"
    geometry_schema_version: str = "1.0.0"
    schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def sync_conflict(self) -> "NetworkConflict":
        if not self.referenced_block_id:
            self.referenced_block_id = self.block_id
        if self.coordinates is None and self.position is not None:
            self.coordinates = self.position
        elif self.position is None and self.coordinates is not None:
            self.position = self.coordinates
        return self

ConflictItem = NetworkConflict

class KPIReport(BaseModel):
    bue_percent: float
    bue_baseline_percent: float
    sbr_percent: float
    pii_delays: float
    pii_baseline_delays: float
    tci_coverage_percent: float
    total_closure_hours: float
    baseline_closure_hours: float
    consolidated_blocks: int
    mttg_minutes: Optional[float] = 22.5
    high_crit_completion_percent: Optional[float] = 100.0
    asset_downtime_reduction_percent: Optional[float] = 25.64
    solver_runtime_seconds: Optional[float] = 0.25

class OptimizedSchedule(BaseModel):
    status: str
    solver: str
    scheduled_jobs: List[ScheduledJob]
    unscheduled_jobs: List[UnscheduledJobReason]
    train_delays: Dict[str, float]
    total_closure_time: float
    objective_value: float
    runtime_seconds: Optional[float] = None
    objective_components: Optional[Dict[str, float]] = None
    kpi_metrics: Optional[KPIReport] = None
    conflicts: List[ConflictItem] = []
    shadow_block_groups: List[Dict[str, Any]] = []
    is_fallback: bool = False
    explainability: Dict[str, Any] = {}

class AssetHealthRecord(BaseModel):
    asset_id: str
    block_id: str
    name: str
    asset_type: str
    chainage_start_km: float
    chainage_end_km: float
    health_score: float
    defect_severity: str
    degradation_velocity: float
    observed_defect_type: str
    model_predicted_risk: float
    last_ultrasonic_test: str
    days_overdue: int
    associated_job_id: Optional[str] = None
    coordinates: Optional[Coordinate3D] = None
    position: Optional[Coordinate3D] = None
    geometry_source: str = "synthetic"
    geometry_schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def sync_asset_coords(self) -> "AssetHealthRecord":
        if self.coordinates is None and self.position is not None:
            self.coordinates = self.position
        elif self.position is None and self.coordinates is not None:
            self.position = self.coordinates
        return self

class SystemEvent(BaseModel):
    id: str
    timestamp: str
    level: str
    message: str
    source: Optional[str] = "SparkRail Core"
    division: Optional[str] = "PRYJ"
    action_required: Optional[bool] = False

# API Request/Response Schemas
class HealthResponse(BaseModel):
    status: str
    version: str
    geometry_schema_version: str = "1.0.0"
    solver_available: bool
    solver_name: str
    data_mode: str
    commit_sha: Optional[str] = None

class DataGenerateRequest(BaseModel):
    seed: Optional[int] = 42
    num_blocks: Optional[int] = Field(default=8, ge=2, le=50)
    num_jobs: Optional[int] = Field(default=20, ge=1, le=100)
    num_trains: Optional[int] = Field(default=10, ge=1, le=100)

class DataGenerateResponse(BaseModel):
    message: str
    seed: int
    blocks_count: int
    jobs_count: int
    trains_count: int
    output_path: str

class ScoreRequest(BaseModel):
    scenario: Optional[Scenario] = None

class ScoreResponse(BaseModel):
    scored_jobs: List[ScoredJob]
    model_mode: str
    model_version: str

class OptimizeRequest(BaseModel):
    scenario: Optional[Scenario] = None
    seed: Optional[int] = None
    freeze_week1: Optional[bool] = False
    weights: Optional[Dict[str, float]] = None

class EvaluateRequest(BaseModel):
    schedule_id: Optional[str] = "latest"

class CoordinateSystemContract(BaseModel):
    name: str = "LOCAL_CORRIDOR"
    crs: str = "LOCAL_CORRIDOR"
    units: str = "meters"
    axis_order: List[str] = Field(default_factory=lambda: ["x", "y", "z"])
    handedness: str = "right-handed"
    origin_description: str = "Synthetic local origin for the bounded railway division"
    geometry_source: str = "synthetic"

class NetworkGeometryResponse(BaseModel):
    geometry_schema_version: str = "1.0.0"
    coordinate_system: CoordinateSystemContract = Field(default_factory=CoordinateSystemContract)
    division: str = "Prayagraj (PRYJ)"
    line_name: str = "Subedarganj - Mirzapur Mainline Corridor"
    total_length_km: float
    is_synthetic: bool = True
    geometry_source: str = "synthetic"
    coordinate_convention: str = "X: corridor longitudinal (m), Y: elevation (m), Z: lateral offset (m)"
    schema_version: str = "1.0.0"
    nodes: List[StationNode]
    tracks: List[GeometryTrack]
    signals: List[SignalMarker]
    ohe_masts: List[OHEMast]
    blocks: List[TrackBlock]
    conflicts: List[ConflictItem] = []
    junctions: List[JunctionNode] = []
    assets: List[AssetHealthRecord] = []
    disconnected_components: List[List[str]] = []

class PlanningCapabilitiesResponse(BaseModel):
    geometry_schema_version: str = "1.0.0"
    coordinate_system: CoordinateSystemContract = Field(default_factory=CoordinateSystemContract)
    solver_available: bool
    solver_name: str
    fallback_active: bool
    model_mode: str
    model_version: str
    supports_3d_geometry: bool = True
    demo_mode: bool = True
    supported_horizons_days: List[int] = [7, 14, 28]
    routes_available: List[str] = []
    max_blocks_capacity: int = 100
    max_trains_capacity: int = 200

# =====================================================================
# Canonical Indian Railways Domain Models & Enums (BDMS Specification)
# =====================================================================

def validate_iso8601_timestamp(v: str) -> str:
    """Validates that a string is a valid ISO-8601 timestamp with timezone info."""
    if not isinstance(v, str):
        raise ValueError(f"Timestamp must be a string, got {type(v)}")
    normalized = v.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception as e:
        raise ValueError(f"Invalid ISO-8601 timestamp '{v}': {e}")
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp '{v}' must be timezone-aware (e.g. UTC +00:00 or 'Z')")
    return v

class TrainPriority(str, Enum):
    PREMIUM_PASSENGER = "PREMIUM_PASSENGER"
    EXPRESS_PASSENGER = "EXPRESS_PASSENGER"
    ORDINARY_PASSENGER = "ORDINARY_PASSENGER"
    FREIGHT = "FREIGHT"
    # Legacy aliases
    PREMIUM = "PREMIUM"
    EXPRESS = "EXPRESS"

class PossessionStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    SANCTIONED = "SANCTIONED"
    GRANTED = "GRANTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    # Legacy aliases
    REQUESTED = "REQUESTED"
    CLEARANCE_PENDING = "CLEARANCE_PENDING"
    REJECTED = "REJECTED"

PossessionLifecycle = PossessionStatus

VALID_POSSESSION_TRANSITIONS: Dict[PossessionStatus, Set[PossessionStatus]] = {
    PossessionStatus.DRAFT: {PossessionStatus.PROPOSED, PossessionStatus.CANCELLED},
    PossessionStatus.PROPOSED: {PossessionStatus.SANCTIONED, PossessionStatus.REJECTED, PossessionStatus.CANCELLED},
    PossessionStatus.SANCTIONED: {PossessionStatus.GRANTED, PossessionStatus.CANCELLED, PossessionStatus.PROPOSED},
    # Hard safety invariant: A GRANTED possession cannot be shifted, cancelled, shortened, or truncated!
    PossessionStatus.GRANTED: {PossessionStatus.IN_PROGRESS},
    PossessionStatus.IN_PROGRESS: {PossessionStatus.COMPLETED, PossessionStatus.CLEARANCE_PENDING},
    PossessionStatus.CLEARANCE_PENDING: {PossessionStatus.COMPLETED},
    PossessionStatus.COMPLETED: set(),
    PossessionStatus.CANCELLED: set(),
    PossessionStatus.REJECTED: set(),
    # Legacy mappings
    PossessionStatus.REQUESTED: {PossessionStatus.PROPOSED, PossessionStatus.SANCTIONED, PossessionStatus.REJECTED, PossessionStatus.CANCELLED},
}

def validate_possession_transition(current: PossessionStatus, target: PossessionStatus) -> None:
    if current == target:
        return
    allowed = VALID_POSSESSION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(
            f"Illegal possession status transition from '{current.value}' to '{target.value}'. "
            f"Allowed transitions: {[s.value for s in allowed]}"
        )

def validate_possession_schedule_immutability(
    status: PossessionStatus,
    old_start: float,
    old_end: float,
    new_start: float,
    new_end: float,
    possession_id: str = "POSSESSION"
) -> None:
    """
    Enforces the non-negotiable safety invariant:
    GRANTED and IN_PROGRESS possessions are mathematically immutable.
    They cannot be shifted, cancelled, shortened, or truncated.
    """
    norm_status = status.value if hasattr(status, "value") else str(status)
    if norm_status == PossessionStatus.GRANTED.value:
        if abs(new_start - old_start) > 1e-4 or abs(new_end - old_end) > 1e-4:
            raise ValueError(
                f"Cannot shift, cancel, or alter schedule of active GRANTED possession '{possession_id}'. "
                f"Active possessions are mathematically immutable."
            )
    elif norm_status == PossessionStatus.IN_PROGRESS.value:
        if (new_end - new_start) < (old_end - old_start) - 1e-4:
            raise ValueError(
                f"Cannot shorten or truncate active IN_PROGRESS possession '{possession_id}'. "
                f"Active possessions are mathematically immutable."
            )
        if abs(new_start - old_start) > 1e-4:
            raise ValueError(
                f"Cannot shift start time of active IN_PROGRESS possession '{possession_id}'. "
                f"Active possessions are mathematically immutable."
            )


class ApprovalRole(str, Enum):
    CTPC = "CTPC"
    SR_DOM = "SR_DOM"
    SECTION_CONTROLLER = "SECTION_CONTROLLER"
    STATION_MASTER = "STATION_MASTER"
    # Legacy / technical aliases
    SSE_PWAY = "SSE_PWAY"
    SSE_TRD = "SSE_TRD"
    SSE_SIGNAL = "SSE_SIGNAL"

class RecommendationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"

class DataProvenance(BaseModel):
    """Canonical data lineage and provenance metadata."""
    source_system: str
    source_record_id: str
    source_timestamp: str
    ingestion_timestamp: str
    schema_version: str = "1.0.0"
    data_freshness_seconds: float = 0.0
    confidence: float = 1.0
    validation_errors: List[str] = Field(default_factory=list)

class CanonicalEntity(BaseModel):
    id: Optional[str] = None
    schema_version: str = "1.0.0"
    source_system: str = "SPARKRAIL"
    source_record_id: Optional[str] = None
    source_timestamp: Optional[str] = None
    event_timestamp: Optional[str] = None
    ingestion_timestamp: Optional[str] = None
    data_freshness: Optional[float] = None
    data_freshness_seconds: Optional[float] = None
    confidence: float = 1.0
    validation_errors: List[str] = Field(default_factory=list)
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def auto_populate_id_and_lineage(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync source_timestamp and event_timestamp
            st = data.get("source_timestamp")
            et = data.get("event_timestamp")
            if st and not et:
                data["event_timestamp"] = st
            elif et and not st:
                data["source_timestamp"] = et

            # Sync data_freshness and data_freshness_seconds
            df = data.get("data_freshness")
            dfs = data.get("data_freshness_seconds")
            if df is not None and dfs is None:
                data["data_freshness_seconds"] = df
            elif dfs is not None and df is None:
                data["data_freshness"] = dfs

            if "id" not in data or not data["id"]:
                for key in (
                    "run_id", "bundle_id", "demand_id", "event_id", "request_id",
                    "override_id", "section_id", "block_id", "station_code",
                    "machine_id", "crew_id", "possession_id", "train_id",
                    "diagnostic_id", "recommendation_id", "interlocking_id"
                ):
                    if key in data and data[key]:
                        data["id"] = data[key]
                        break
                if "id" not in data or not data["id"]:
                    data["id"] = f"{cls.__name__.upper()}-{int(time.time()*1000)}"
        return data

    @field_validator("event_timestamp", "source_timestamp", "ingestion_timestamp", mode="before")
    @classmethod
    def check_iso(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            return validate_iso8601_timestamp(v)
        return v

    def get_provenance(self) -> DataProvenance:
        now_iso = datetime.now(timezone.utc).isoformat()
        return DataProvenance(
            source_system=self.source_system,
            source_record_id=self.source_record_id or str(self.id or "UNKNOWN"),
            source_timestamp=self.source_timestamp or self.event_timestamp or now_iso,
            ingestion_timestamp=self.ingestion_timestamp or now_iso,
            schema_version=self.schema_version,
            data_freshness_seconds=self.data_freshness_seconds or 0.0,
            confidence=self.confidence,
            validation_errors=list(self.validation_errors)
        )

class RailwayZone(CanonicalEntity):
    zone_code: str
    name: str
    headquarters: str

class Division(CanonicalEntity):
    division_code: str
    name: str
    zone_code: str
    headquarters: str
    route_km: float = Field(..., gt=0.0)

class TrackSection(CanonicalEntity):
    """Canonical model for a discrete railway track block section."""
    section_id: Optional[str] = None
    block_id: Optional[str] = None
    division_code: str = "PRYJ"
    line_id: str = "MAIN_LINE"
    start_station: str
    end_station: str
    chainage_start_km: float = Field(..., ge=0.0)
    chainage_end_km: float = Field(..., gt=0.0)
    speed_limit_kmh: float = Field(default=110.0, gt=0.0)
    signaling_type: str = "Automatic"
    electrification_type: str = "25kV AC"
    elementary_section_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_section_and_block_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sec = data.get("section_id")
            blk = data.get("block_id")
            entity_id = data.get("id")
            val = sec or blk or entity_id
            if val:
                if not sec:
                    data["section_id"] = val
                if not blk:
                    data["block_id"] = val
        return data

    @model_validator(mode="after")
    def validate_chainage_bounds(self) -> "TrackSection":
        if not self.section_id and self.block_id:
            self.section_id = self.block_id
        if not self.block_id and self.section_id:
            self.block_id = self.section_id
        if not self.section_id:
            raise ValueError("TrackSection must provide either 'section_id' or 'block_id'")
        if self.chainage_start_km >= self.chainage_end_km:
            raise ValueError(
                f"TrackSection '{self.section_id}' chainage_start_km ({self.chainage_start_km}) "
                f"must be strictly less than chainage_end_km ({self.chainage_end_km})"
            )
        return self

# Backward-compatible alias
BlockSection = TrackSection

class Station(CanonicalEntity):
    code: str
    name: str
    division_code: str = "PRYJ"
    chainage_km: float = Field(..., ge=0.0)
    platforms: int = Field(default=2, ge=1)
    loop_capacity: int = Field(default=2, ge=0)
    station_type: str = "station"
    interlocking_type: str = "Electronic"

class Interlocking(CanonicalEntity):
    interlocking_id: Optional[str] = None
    station_code: str
    interlocking_type: str = "Electronic"
    route_count: int = Field(default=12, ge=1)
    point_count: int = Field(default=8, ge=0)
    signal_ids: List[str] = Field(default_factory=list)
    is_operational: bool = True

    @model_validator(mode="after")
    def set_default_id(self) -> "Interlocking":
        if not self.interlocking_id:
            self.interlocking_id = f"IXL-{self.station_code}"
        return self

class TrackSegment(CanonicalEntity):
    segment_id: str
    block_id: str
    track_type: str = "Mainline"
    start_chainage_km: float = Field(..., ge=0.0)
    end_chainage_km: float = Field(..., gt=0.0)
    gradient_permille: float = 0.0
    curvature_radius_m: Optional[float] = None

    @model_validator(mode="after")
    def check_segment_chainage(self) -> "TrackSegment":
        if self.start_chainage_km >= self.end_chainage_km:
            raise ValueError("start_chainage_km must be strictly less than end_chainage_km")
        return self

class ElementarySection(CanonicalEntity):
    """Canonical 25kV OHE power supply zone."""
    section_id: str
    name: str
    feeding_post_id: str
    catenary_voltage_kv: float = Field(default=25.0, gt=0.0)
    track_section_ids: List[str] = Field(default_factory=list)
    block_ids: List[str] = Field(default_factory=list)  # Legacy alias
    isolator_switch_ids: List[str] = Field(default_factory=list)
    is_energized: bool = True

    @model_validator(mode="after")
    def sync_track_sections(self) -> "ElementarySection":
        if not self.track_section_ids and self.block_ids:
            self.track_section_ids = list(self.block_ids)
        elif not self.block_ids and self.track_section_ids:
            self.block_ids = list(self.track_section_ids)
        return self

ElementaryElectricalSection = ElementarySection

class FeedingPost(CanonicalEntity):
    post_id: str
    name: str
    chainage_km: float = Field(..., ge=0.0)
    capacity_mva: float = Field(default=30.0, gt=0.0)
    feeding_sections: List[str] = Field(default_factory=list)

class IsolatorSwitch(CanonicalEntity):
    switch_id: str
    elementary_section_id: str
    location_chainage_km: float = Field(..., ge=0.0)
    state: str = "CLOSED"
    is_motorized: bool = True

class SignalAsset(CanonicalEntity):
    signal_id: str
    block_id: str
    chainage_km: float = Field(..., ge=0.0)
    signal_type: str = "Multi-Aspect Colour Light"
    current_aspect: str = "CLEAR"
    is_operational: bool = True

class OHEAsset(CanonicalEntity):
    mast_id: str
    block_id: str
    chainage_km: float = Field(..., ge=0.0)
    catenary_height_m: float = Field(default=5.5, gt=0.0)
    contact_wire_wear_percent: float = Field(default=12.0, ge=0.0, le=100.0)
    is_isolated: bool = False

class MaintenanceDemand(CanonicalEntity):
    """Canonical requisition demand for maintenance possession."""
    demand_id: str
    department: Department
    track_section_id: str
    block_id: Optional[str] = None  # Legacy alias
    chainage_start_km: float = Field(..., ge=0.0)
    chainage_end_km: float = Field(..., gt=0.0)
    required_duration_hours: float = Field(..., gt=0.0)
    earliest_window_start: float = Field(default=0.0, ge=0.0)
    latest_window_end: float = Field(default=24.0, gt=0.0)
    preferred_window_start: float = Field(default=0.0, ge=0.0)
    preferred_window_end: float = Field(default=24.0, gt=0.0)
    work_type: str = "Routine Corridor Maintenance"
    machine_ids: List[str] = Field(default_factory=list)
    crew_ids: List[str] = Field(default_factory=list)
    priority_score: float = Field(default=50.0, ge=0.0, le=100.0)
    status: PossessionStatus = PossessionStatus.DRAFT
    lifecycle_status: Optional[PossessionStatus] = None

    @model_validator(mode="after")
    def sync_and_validate(self) -> "MaintenanceDemand":
        if not self.block_id:
            self.block_id = self.track_section_id
        if not self.track_section_id and self.block_id:
            self.track_section_id = self.block_id
        if self.lifecycle_status is None:
            self.lifecycle_status = self.status
        else:
            self.status = self.lifecycle_status
        if self.chainage_start_km >= self.chainage_end_km:
            raise ValueError("chainage_start_km must be strictly less than chainage_end_km")
        if self.earliest_window_start >= self.latest_window_end:
            raise ValueError("earliest_window_start must be strictly less than latest_window_end")
        return self

PossessionDemand = MaintenanceDemand

class ShadowPossessionBundle(CanonicalEntity):
    bundle_id: str
    primary_demand_id: str
    secondary_demand_ids: List[str] = Field(default_factory=list)
    track_section_id: str
    block_id: Optional[str] = None
    window_start: float = Field(..., ge=0.0)
    window_end: float = Field(..., gt=0.0)
    departments: List[str] = Field(default_factory=list)
    compatibility_rationale: str = ""
    spatial_extent_km: Optional[Tuple[float, float]] = None
    total_tci_benefit: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def sync_bundle(self) -> "ShadowPossessionBundle":
        if not self.block_id:
            self.block_id = self.track_section_id
        if not self.track_section_id and self.block_id:
            self.track_section_id = self.block_id
        if self.window_start >= self.window_end:
            raise ValueError("window_start must be strictly less than window_end")
        return self

ShadowPossession = ShadowPossessionBundle

class Possession(CanonicalEntity):
    """Concrete allocated track possession."""
    possession_id: str
    demand_id: str
    track_section_id: str
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., gt=0.0)
    status: PossessionStatus = PossessionStatus.DRAFT
    department: Department
    requires_ohe_isolation: bool = False
    allocated_machines: List[str] = Field(default_factory=list)
    allocated_crews: List[str] = Field(default_factory=list)
    is_shadow: bool = False
    shadow_parent_id: Optional[str] = None

    @model_validator(mode="after")
    def check_times(self) -> "Possession":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be strictly less than end_time")
        return self

    def transition_to(self, new_status: PossessionStatus) -> None:
        validate_possession_transition(self.status, new_status)
        self.status = new_status

class TrainPriorityClass(CanonicalEntity):
    priority: TrainPriority
    speed_restriction_kmh: float = Field(..., gt=0.0)
    max_delay_minutes: float = Field(..., ge=0.0)

class TrainMovement(CanonicalEntity):
    train_id: str
    name: Optional[str] = None
    priority: TrainPriority = TrainPriority.EXPRESS_PASSENGER
    route: List[str] = Field(..., min_length=1)
    current_section: Optional[str] = None
    current_block: Optional[str] = None
    current_chainage_km: float = Field(default=0.0, ge=0.0)
    current_speed_kmh: float = Field(default=0.0, ge=0.0)
    dynamic_eta_hours: float = Field(default=0.0, ge=0.0)
    destination: str = "PRYJ"
    delay_minutes: float = Field(default=0.0, ge=0.0)
    is_electric: bool = True

    @model_validator(mode="after")
    def sync_section(self) -> "TrainMovement":
        if not self.current_section and self.current_block:
            self.current_section = self.current_block
        elif not self.current_block and self.current_section:
            self.current_block = self.current_section
        if self.delay_minutes < 0.0:
            raise ValueError(f"delay_minutes cannot be negative, got {self.delay_minutes}")
        return self

class Machine(CanonicalEntity):
    machine_id: str
    machine_type: str
    home_depot: str
    transit_speed_kmh: float = Field(default=40.0, gt=0.0)
    setup_time_hours: float = Field(default=0.5, ge=0.0)
    clearing_time_hours: float = Field(default=0.5, ge=0.0)
    is_available: bool = True

class Crew(CanonicalEntity):
    crew_id: str
    department: Department
    base_station: str
    certified_section_ids: List[str] = Field(default_factory=list)
    certified_block_ids: List[str] = Field(default_factory=list)
    # Strict Indian Railways Hours of Employment Regulations (HOER)
    max_shift_hours: float = Field(default=12.0, gt=0.0, le=12.0)
    mandatory_rest_hours: float = Field(default=16.0, ge=12.0)
    is_available: bool = True

    @model_validator(mode="after")
    def sync_blocks(self) -> "Crew":
        if not self.certified_section_ids and self.certified_block_ids:
            self.certified_section_ids = list(self.certified_block_ids)
        elif not self.certified_block_ids and self.certified_section_ids:
            self.certified_block_ids = list(self.certified_section_ids)
        return self

class CrewShift(CanonicalEntity):
    crew_id: str
    shift_start: float = Field(..., ge=0.0)
    shift_end: float = Field(..., gt=0.0)
    active_job_id: Optional[str] = None

    @model_validator(mode="after")
    def check_shift(self) -> "CrewShift":
        if self.shift_start >= self.shift_end:
            raise ValueError("shift_start must be strictly less than shift_end")
        return self

class FixedPossession(CanonicalEntity):
    possession_id: str
    block_id: str
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., gt=0.0)
    reason: str = "Pre-scheduled Mega Block"
    department: Optional[Department] = None

    @model_validator(mode="after")
    def check_time(self) -> "FixedPossession":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be strictly less than end_time")
        return self

class ScheduleWindow(CanonicalEntity):
    window_id: str
    block_id: str
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., gt=0.0)
    assigned_demands: List[str] = Field(default_factory=list)
    is_shadow: bool = False

class OptimizationRequest(CanonicalEntity):
    request_id: str
    division_code: str = "PRYJ"
    planning_horizon_hours: int = Field(default=24, gt=0)
    input_snapshot_hash: str
    freeze_week1: bool = False
    operational_weights: Dict[str, float] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("created_at")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_iso8601_timestamp(v)

class OptimizationRun(CanonicalEntity):
    run_id: str
    request_id: str
    input_snapshot_hash: str
    solver_status: str
    solver_mode: str
    objective_value: float
    optimality_gap: Optional[float] = None
    runtime_seconds: float = Field(..., ge=0.0)
    scheduled_demands: List[str] = Field(default_factory=list)
    deferred_demands: List[Dict[str, Any]] = Field(default_factory=list)
    train_delay_metrics: Dict[str, float] = Field(default_factory=dict)
    machine_utilization: Dict[str, float] = Field(default_factory=dict)
    bundling_metrics: Dict[str, Any] = Field(default_factory=dict)
    constraint_violations: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("created_at")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_iso8601_timestamp(v)

class Recommendation(CanonicalEntity):
    recommendation_id: str
    optimization_run_id: str
    primary_possession: Possession
    shadow_bundle: Optional[ShadowPossessionBundle] = None
    schedule_window: Tuple[float, float]
    safety_validation_status: str = "SAFETY_CERTIFIED"
    status: RecommendationStatus = RecommendationStatus.PROPOSED
    expires_at: str
    version: int = 1
    approval_chain: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "CTPC": {"status": "PENDING", "approver_id": None, "approver_name": None, "comments": None, "timestamp": None},
        "SR_DOM": {"status": "PENDING", "approver_id": None, "approver_name": None, "comments": None, "timestamp": None},
        "SECTION_CONTROLLER": {"status": "PENDING", "approver_id": None, "approver_name": None, "comments": None, "timestamp": None},
        "STATION_MASTER": {"status": "PENDING", "approver_id": None, "approver_name": None, "comments": None, "timestamp": None},
    })
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("expires_at")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_iso8601_timestamp(v)

class ApprovalAction(CanonicalEntity):
    action_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    role: ApprovalRole
    approver_id: str
    approver_name: Optional[str] = "Railway Officer"
    decision: str = "APPROVED"  # "APPROVED", "REJECTED", "OVERRIDDEN"
    comments: str = "Sanctioned pursuant to Indian Railways G&SR."
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="before")
    @classmethod
    def set_approval_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "action_id" not in data or not data["action_id"]:
                data["action_id"] = f"ACT-{int(time.time()*1000)}"
            if "recommendation_id" not in data or not data["recommendation_id"]:
                data["recommendation_id"] = "REC-DEFAULT"
            if "approver_name" not in data or not data["approver_name"]:
                data["approver_name"] = data.get("approver_id", "Railway Officer")
        return data

    @field_validator("timestamp")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_iso8601_timestamp(v)

ApprovalDecision = ApprovalAction

class ApprovalRequest(CanonicalEntity):
    proposal_id: str
    division_code: str
    requested_by: str
    role: ApprovalRole
    submission_time: str
    scheduled_windows: List[Dict[str, Any]]
    safety_status: str
    explainability: Dict[str, Any] = Field(default_factory=dict)

class OperationalOverride(CanonicalEntity):
    override_id: str
    recommendation_id: str
    user_id: str
    role: ApprovalRole
    reason_code: str  # e.g., "VIP_MOVEMENT", "BAD_WEATHER", "EMERGENCY_DERAILMENT_RISK"
    justification: str = Field(..., min_length=10)
    previous_schedule: Dict[str, Any]
    overridden_schedule: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    safety_audit_passed: bool = True
    audit_hash: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_iso8601_timestamp(v)

class AuditEvent(CanonicalEntity):
    event_id: str
    event_type: str = "PROPOSAL_CREATED"
    previous_hash: str = "GENESIS_HASH"
    current_hash: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str = "SYSTEM"
    actor_id: Optional[str] = None
    role: Optional[str] = None
    resource_type: str = "ADVISORY_PROPOSAL"
    resource_id: str = ""
    action: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None

    @model_validator(mode="after")
    def sync_actor(self) -> "AuditEvent":
        if not self.actor_id:
            self.actor_id = self.user_id
        if not self.user_id:
            self.user_id = self.actor_id or "SYSTEM"
        return self

    @field_validator("timestamp")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_iso8601_timestamp(v)

class DisruptionEvent(CanonicalEntity):
    event_id: str
    event_type: str = "TRAIN_DELAY"
    severity: str = "MAJOR"  # "CRITICAL", "MAJOR", "MINOR"
    affected_section_ids: List[str] = Field(default_factory=list)
    affected_block_ids: List[str] = Field(default_factory=list)
    delay_minutes: float = Field(..., ge=0.0)
    train_id: Optional[str] = None
    machine_id: Optional[str] = None
    corridor_radius_km: float = Field(default=30.0, gt=0.0)
    forward_horizon_minutes: float = Field(default=180.0, gt=0.0)
    localized_corridor_km_range: Optional[Tuple[float, float]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def sync_sections(self) -> "DisruptionEvent":
        if not self.affected_section_ids and self.affected_block_ids:
            self.affected_section_ids = list(self.affected_block_ids)
        elif not self.affected_block_ids and self.affected_section_ids:
            self.affected_block_ids = list(self.affected_section_ids)
        return self

    @field_validator("timestamp")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_iso8601_timestamp(v)

class SafetyDiagnostic(CanonicalEntity):
    diagnostic_id: str
    rule_id: str
    rule_description: str
    severity: str = "CRITICAL"
    entity_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    passed: bool = True
