from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Resource(BaseModel):
    id: str
    name: str
    capacity: int

class BlockSection(BaseModel):
    id: str
    chainage_start: float
    chainage_end: float
    description: str

class Train(BaseModel):
    id: str
    category: str  # e.g., 'premium', 'express', 'freight'
    scheduled_start: float
    scheduled_end: float
    route: List[str]  # List of block section IDs
    min_travel_times: Dict[str, float]  # block_id -> time

class TCIInputs(BaseModel):
    safety_severity: float # 0 to 1
    traffic_impact: float  # 0 to 1
    degradation_indicator: float # 0 to 1
    overdue_days: int
    
class MaintenanceJob(BaseModel):
    id: str
    department: str # 'Engineering', 'OHE', 'S&T'
    block_id: str
    duration: float
    required_resources: Dict[str, int] # resource_id -> amount
    tci_inputs: TCIInputs
    is_fixed: bool = False
    fixed_start: Optional[float] = None

class Scenario(BaseModel):
    blocks: List[BlockSection]
    trains: List[Train]
    jobs: List[MaintenanceJob]
    resources: List[Resource]
    
class OptimizedSchedule(BaseModel):
    scheduled_jobs: List[Dict[str, Any]]
    unscheduled_jobs: List[Dict[str, Any]]
    train_delays: Dict[str, float]
    total_closure_time: float
    objective_value: float
    kpi_metrics: Dict[str, float]
