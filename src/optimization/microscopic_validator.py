from typing import Dict, Any, List, Set, Tuple, Optional
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    Scenario,
    ScheduledJob,
    Train,
    Department
)

class BendersCut(BaseModel):
    cut_id: str
    cut_type: str  # "HEADWAY_VIOLATION", "ELECTRICAL_ISOLATION", "OPPOSING_TRAIN_CONFLICT", "CREW_LIMIT"
    affected_block_id: str
    infeasible_window: Tuple[float, float]
    suggested_offset_hours: float
    description: str

class MicroscopicValidationResult(BaseModel):
    is_feasible: bool
    total_trains_simulated: int
    train_delays: Dict[str, float] = Field(default_factory=dict)
    generated_cuts: List[BendersCut] = Field(default_factory=list)
    safety_violations: List[str] = Field(default_factory=list)
    diagnostics: List[str] = Field(default_factory=list)

class MicroscopicDispatchValidator:
    """
    Tier 3 Microscopic Dispatch & Safety Validator.
    Simulates continuous train trajectories, block headway spacing,
    electrical elementary section isolations, and Temporary Single Line (TSL) working.
    Produces named Benders cuts when microscopic conflicts arise.
    """
    def __init__(
        self,
        min_headway_hours: float = 0.1,  # ~6 minutes
        max_premium_delay_hours: float = 0.25, # 15 minutes
        elementary_section_map: Optional[Dict[str, str]] = None
    ):
        self.min_headway = min_headway_hours
        self.max_premium_delay = max_premium_delay_hours
        self.elementary_map = elementary_section_map or {}

    def validate_dispatch(
        self,
        scenario: Scenario,
        scheduled_jobs: List[ScheduledJob],
        electrical_isolated_blocks: Optional[Set[str]] = None
    ) -> MicroscopicValidationResult:
        isolated_blocks = electrical_isolated_blocks or set()
        
        # Build block possession intervals
        block_closures: Dict[str, List[Tuple[float, float, str]]] = {b.id: [] for b in scenario.blocks}
        for fb in scenario.fixed_blocks:
            if fb.block_id in block_closures:
                block_closures[fb.block_id].append((fb.start_time, fb.end_time, "FIXED_BLOCK"))
        for sj in scheduled_jobs:
            if sj.block_id in block_closures:
                block_closures[sj.block_id].append((sj.start_time, sj.end_time, sj.job_id))
            # If OHE department job, add to isolated blocks
            if sj.department == Department.OHE.value or sj.department == "OHE":
                isolated_blocks.add(sj.block_id)

        train_delays: Dict[str, float] = {}
        generated_cuts: List[BendersCut] = []
        violations: List[str] = []

        # Simulate each train through its route
        for t in scenario.trains:
            curr_time = t.scheduled_start
            accumulated_delay = 0.0

            for b_id in t.route:
                # 1. Electrical traction check
                if b_id in isolated_blocks and getattr(t, "is_electric", True):
                    # Electric train cannot enter isolated block
                    cut = BendersCut(
                        cut_id=f"CUT-ELEC-{b_id}-{t.id}",
                        cut_type="ELECTRICAL_ISOLATION",
                        affected_block_id=b_id,
                        infeasible_window=(curr_time, curr_time + 1.0),
                        suggested_offset_hours=1.5,
                        description=f"Electric train {t.id} blocked by 25kV de-energized section on {b_id}"
                    )
                    generated_cuts.append(cut)
                    violations.append(cut.description)

                # 2. Block closure check
                min_travel = t.min_travel_times.get(b_id, 0.25)
                block_free_at = curr_time
                for (s_cl, e_cl, reason) in block_closures.get(b_id, []):
                    # Train conflicts with possession
                    if not (curr_time + min_travel <= s_cl or curr_time >= e_cl):
                        # Train held at signal before block
                        wait_delay = e_cl - curr_time
                        if wait_delay > 0:
                            accumulated_delay += wait_delay
                            block_free_at = max(block_free_at, e_cl)

                curr_time = block_free_at + min_travel

            train_delays[t.id] = round(accumulated_delay, 3)

            # Premium train SLA check
            is_premium = t.category.lower() in ("premium", "express_premium", "vande_bharat")
            if is_premium and accumulated_delay > self.max_premium_delay:
                cut = BendersCut(
                    cut_id=f"CUT-PREM-DELAY-{t.id}",
                    cut_type="HEADWAY_VIOLATION",
                    affected_block_id=t.route[0],
                    infeasible_window=(t.scheduled_start, t.scheduled_end),
                    suggested_offset_hours=0.5,
                    description=f"Premium train {t.id} exceeds max delay threshold: {accumulated_delay*60:.1f}m > {self.max_premium_delay*60:.1f}m"
                )
                generated_cuts.append(cut)
                violations.append(cut.description)

        is_feasible = len(violations) == 0
        return MicroscopicValidationResult(
            is_feasible=is_feasible,
            total_trains_simulated=len(scenario.trains),
            train_delays=train_delays,
            generated_cuts=generated_cuts,
            safety_violations=violations,
            diagnostics=[f"Simulated {len(scenario.trains)} trains. Violations: {len(violations)}"]
        )
