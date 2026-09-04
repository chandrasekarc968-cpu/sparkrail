import math
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

class Department(str, Enum):
    ENGINEERING = "Engineering"
    OHE = "OHE"
    S_AND_T = "S&T"

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

class TCIExplanation(BaseModel):
    safety_component: float
    delay_component: float
    degradation_component: float
    overdue_component: float
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

class TrainPriority(str, Enum):
    PREMIUM = "PREMIUM"
    EXPRESS = "EXPRESS"
    ORDINARY_PASSENGER = "ORDINARY_PASSENGER"
    FREIGHT = "FREIGHT"

class PossessionLifecycle(str, Enum):
    REQUESTED = "REQUESTED"
    SANCTIONED = "SANCTIONED"
    GRANTED = "GRANTED"
    IN_PROGRESS = "IN_PROGRESS"
    CLEARANCE_PENDING = "CLEARANCE_PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class ApprovalRole(str, Enum):
    CTPC = "CTPC"
    SR_DOM = "SR_DOM"
    SECTION_CONTROLLER = "SECTION_CONTROLLER"
    STATION_MASTER = "STATION_MASTER"
    SSE_PWAY = "SSE_PWAY"
    SSE_TRD = "SSE_TRD"
    SSE_SIGNAL = "SSE_SIGNAL"

class CanonicalEntity(BaseModel):
    id: str
    schema_version: str = "1.0.0"
    source_system: str = "SPARKRAIL"
    source_record_id: Optional[str] = None
    event_timestamp: Optional[str] = None
    ingestion_timestamp: Optional[str] = None
    data_freshness_seconds: Optional[float] = None
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)

class RailwayZone(CanonicalEntity):
    zone_code: str
    name: str
    headquarters: str

class Division(CanonicalEntity):
    division_code: str
    name: str
    zone_code: str
    headquarters: str
    route_km: float

class Station(CanonicalEntity):
    code: str
    name: str
    division_code: str
    chainage_km: float
    platforms: int
    station_type: str = "station"

class Interlocking(CanonicalEntity):
    station_code: str
    interlocking_type: str = "Electronic"
    route_count: int = 12
    point_count: int = 8
    is_operational: bool = True

class BlockSection(CanonicalEntity):
    block_id: str
    line_id: str = "MAIN_LINE"
    start_station: str
    end_station: str
    chainage_start_km: float
    chainage_end_km: float
    speed_limit_kmh: float = 110.0
    signaling_type: str = "Automatic"
    electrification_type: str = "25kV AC"

class TrackSegment(CanonicalEntity):
    segment_id: str
    block_id: str
    track_type: str = "Mainline"
    start_chainage_km: float
    end_chainage_km: float
    gradient_permille: float = 0.0
    curvature_radius_m: Optional[float] = None

class ElementaryElectricalSection(CanonicalEntity):
    section_id: str
    name: str
    feeding_post_id: str
    catenary_voltage_kv: float = 25.0
    block_ids: List[str]
    isolator_switch_ids: List[str] = []
    is_energized: bool = True

class FeedingPost(CanonicalEntity):
    post_id: str
    name: str
    chainage_km: float
    capacity_mva: float = 30.0
    feeding_sections: List[str] = []

class IsolatorSwitch(CanonicalEntity):
    switch_id: str
    elementary_section_id: str
    location_chainage_km: float
    state: str = "CLOSED"
    is_motorized: bool = True

class SignalAsset(CanonicalEntity):
    signal_id: str
    block_id: str
    chainage_km: float
    signal_type: str = "Multi-Aspect Colour Light"
    current_aspect: str = "CLEAR"
    is_operational: bool = True

class OHEAsset(CanonicalEntity):
    mast_id: str
    block_id: str
    chainage_km: float
    catenary_height_m: float = 5.5
    contact_wire_wear_percent: float = 12.0
    is_isolated: bool = False

class PossessionDemand(CanonicalEntity):
    demand_id: str
    department: Department
    block_id: str
    chainage_start_km: float
    chainage_end_km: float
    required_duration_hours: float
    preferred_window_start: float
    preferred_window_end: float
    work_type: str
    machine_ids: List[str] = []
    crew_ids: List[str] = []
    priority_score: float = 50.0
    lifecycle_status: PossessionLifecycle = PossessionLifecycle.REQUESTED

class ShadowPossession(CanonicalEntity):
    shadow_id: str
    primary_demand_id: str
    secondary_demand_ids: List[str]
    block_id: str
    window_start: float
    window_end: float
    departments: List[str]
    compatibility_rationale: str

class TrainPriorityClass(CanonicalEntity):
    priority: TrainPriority
    speed_restriction_kmh: float
    max_delay_minutes: float

class TrainMovement(CanonicalEntity):
    train_id: str
    name: Optional[str] = None
    priority: TrainPriority = TrainPriority.EXPRESS
    current_block: str
    current_chainage_km: float
    current_speed_kmh: float
    dynamic_eta_hours: float
    destination: str
    delay_minutes: float = 0.0

class Machine(CanonicalEntity):
    machine_id: str
    machine_type: str
    home_depot: str
    transit_speed_kmh: float = 40.0
    setup_time_hours: float = 0.5
    clearing_time_hours: float = 0.5
    is_available: bool = True

class Crew(CanonicalEntity):
    crew_id: str
    department: Department
    base_station: str
    certified_block_ids: List[str] = []
    max_shift_hours: float = 8.0
    mandatory_rest_hours: float = 12.0

class CrewShift(CanonicalEntity):
    crew_id: str
    shift_start: float
    shift_end: float
    active_job_id: Optional[str] = None

class FixedPossession(CanonicalEntity):
    possession_id: str
    block_id: str
    start_time: float
    end_time: float
    reason: str
    department: Optional[Department] = None

class ScheduleWindow(CanonicalEntity):
    window_id: str
    block_id: str
    start_time: float
    end_time: float
    assigned_demands: List[str] = []
    is_shadow: bool = False

class ApprovalRequest(CanonicalEntity):
    proposal_id: str
    division_code: str
    requested_by: str
    role: ApprovalRole
    submission_time: str
    scheduled_windows: List[Dict[str, Any]]
    safety_status: str
    explainability: Dict[str, Any] = Field(default_factory=dict)

class ApprovalDecision(CanonicalEntity):
    decision_id: str
    proposal_id: str
    role: ApprovalRole
    decision: str
    approver_id: str
    approver_name: str
    comments: str
    timestamp: str
    override_reason_code: Optional[str] = None

class OperationalOverride(CanonicalEntity):
    override_id: str
    proposal_id: str
    user_id: str
    role: ApprovalRole
    previous_schedule: Dict[str, Any]
    overridden_schedule: Dict[str, Any]
    reason_code: str
    justification: str
    timestamp: str
    safety_audit_passed: bool = True

class DisruptionEvent(CanonicalEntity):
    event_id: str
    event_type: str
    severity: str
    timestamp: str
    affected_block_ids: List[str]
    delay_minutes: float
    train_id: Optional[str] = None
    machine_id: Optional[str] = None
    localized_corridor_km_range: Optional[Tuple[float, float]] = None

class SafetyDiagnostic(CanonicalEntity):
    diagnostic_id: str
    rule_id: str
    rule_description: str
    severity: str = "CRITICAL"
    entity_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    passed: bool = True

class AuditEvent(CanonicalEntity):
    event_id: str
    event_type: str
    user_id: str
    role: Optional[str] = None
    timestamp: str
    resource_type: str
    resource_id: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
