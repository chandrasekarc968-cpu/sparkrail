from typing import List, Dict, Any, Optional
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

# 3D Geometry and Spatial Representations
class Vector3D(BaseModel):
    x: float
    y: float
    z: float

class TrackGeometry(BaseModel):
    block_id: str
    name: str = ""
    start_coord: Vector3D
    end_coord: Vector3D
    path_points: List[Vector3D] = []
    length_km: float
    chainage_start: float
    chainage_end: float
    elevation_profile: List[float] = []
    track_type: str = "Mainline"
    electrification: str = "25kV AC"
    gauge: str = "Broad Gauge 1676mm"
    speed_limit_kmh: float = 130.0

class StationNode(BaseModel):
    id: str
    name: str
    code: str
    position: Vector3D
    chainage_km: float
    node_type: str = "station"  # "station", "junction", "terminal"
    platforms: int = 2
    connected_blocks: List[str] = []

class SignalMarker(BaseModel):
    id: str
    block_id: str
    chainage_km: float
    position: Vector3D
    aspect: str = "clear"  # "clear", "caution", "danger"
    direction: str = "UP"  # "UP", "DOWN"

class OHEMast(BaseModel):
    id: str
    block_id: str
    position: Vector3D
    catenary_height_m: float = 5.5
    is_isolated: bool = False

class ConflictType(str, Enum):
    TRAIN_BLOCK = "train_vs_block"
    PREMIUM_TRAIN = "premium_train_risk"
    DEPT_INCOMPATIBLE = "incompatible_department"
    RESOURCE_OVERALLOCATION = "resource_overallocation"
    FIXED_BLOCK_COLLISION = "fixed_block_collision"
    SAFETY_CLEARANCE = "insufficient_safety_clearance"
    OVERDUE_CRITICAL = "overdue_critical_maintenance"

class ConflictItem(BaseModel):
    id: str
    conflict_type: ConflictType
    severity: str  # "CRITICAL", "MAJOR", "WARNING", "INFO"
    block_id: str
    title: str
    description: str
    affected_jobs: List[str] = []
    affected_trains: List[str] = []
    time_window: Optional[Dict[str, float]] = None
    suggested_resolution: str = ""
    position: Optional[Vector3D] = None

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

class NetworkGeometryResponse(BaseModel):
    division: str = "Prayagraj (PRYJ)"
    line_name: str = "Subedarganj - Mirzapur Mainline Corridor"
    total_length_km: float
    is_synthetic: bool = True
    nodes: List[StationNode]
    tracks: List[TrackGeometry]
    signals: List[SignalMarker]
    ohe_masts: List[OHEMast]
    blocks: List[TrackBlock]
    conflicts: List[ConflictItem] = []

class PlanningCapabilitiesResponse(BaseModel):
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
