"""
Optimization module for maintenance block scheduling.
Three-tier hierarchical architecture:
Tier 1: Demand Clustering & Maximal Clique Bundles
Tier 2: Macro Possession Window Allocation (CP-SAT / ALNS)
Tier 3: Microscopic Dispatch Validation & Benders Cuts
Dynamic Disruption Rescheduling Engine
"""

from src.optimization.clustering import SpatiotemporalClusteringEngine, CandidateBundle
from src.optimization.macro_allocator import MacroPossessionAllocator, MacroScheduleOutput
from src.optimization.microscopic_validator import MicroscopicDispatchValidator, MicroscopicValidationResult, BendersCut
from src.optimization.milp_solver import MaintenanceSchedulerMILP, ProductionOptimizationPipeline
from src.optimization.disruption_engine import DynamicDisruptionEngine, DisruptionResolution
from src.optimization.safety_validator import validate_schedule_safety, SafetyViolationError

__all__ = [
    "SpatiotemporalClusteringEngine",
    "CandidateBundle",
    "MacroPossessionAllocator",
    "MacroScheduleOutput",
    "MicroscopicDispatchValidator",
    "MicroscopicValidationResult",
    "BendersCut",
    "MaintenanceSchedulerMILP",
    "ProductionOptimizationPipeline",
    "DynamicDisruptionEngine",
    "DisruptionResolution",
    "validate_schedule_safety",
    "SafetyViolationError",
]
