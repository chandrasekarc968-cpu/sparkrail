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

class TrackBlock(BaseModel):
    id: str
    chainage_start: float = Field(..., ge=0.0)
    chainage_end: float = Field(..., gt=0.0)
    description: str

    @model_validator(mode="after")
    def check_chainage(self) -> "TrackBlock":
        if self.chainage_start >= self.chainage_end:
            raise ValueError(f"chainage_start ({self.chainage_start}) must be strictly less than chainage_end ({self.chainage_end})")
        return self

class Train(BaseModel):
    id: str
    category: str = Field(..., description="e.g., 'premium', 'express', 'freight'")
    scheduled_start: float = Field(..., ge=0.0)
    scheduled_end: float = Field(..., gt=0.0)
    route: List[str] = Field(..., min_length=1)
    min_travel_times: Dict[str, float]
    
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

class MaintenanceJob(BaseModel):
    id: str
    department: Department
    block_id: str
    duration: float = Field(..., gt=0.0)
    required_resources: Dict[str, int]
    tci_inputs: TCIInputs
    is_fixed: bool = False
    fixed_start: Optional[float] = None
    
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

class Scenario(BaseModel):
    blocks: List[TrackBlock]
    trains: List[Train]
    jobs: List[MaintenanceJob]
    resources: List[Resource]
    fixed_blocks: List[FixedMaintenanceBlock] = []

class ScheduleWindow(BaseModel):
    start_time: float
    end_time: float

class ScheduledJob(BaseModel):
    job_id: str
    block_id: str
    start_time: float
    end_time: float
    tci: float
    department: Department

class UnscheduledJobReason(BaseModel):
    job_id: str
    reason: str

class KPIReport(BaseModel):
    bue_percent: float
    sbr_percent: float
    pii_delays: float
    tci_coverage_percent: float
    total_closure_hours: float
    consolidated_blocks: int

class OptimizedSchedule(BaseModel):
    status: str
    scheduled_jobs: List[ScheduledJob]
    unscheduled_jobs: List[UnscheduledJobReason]
    train_delays: Dict[str, float]
    total_closure_time: float
    objective_value: float
    kpi_metrics: Optional[KPIReport] = None
