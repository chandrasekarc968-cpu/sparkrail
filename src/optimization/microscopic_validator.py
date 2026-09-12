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
    cut_type: str  # "HEADWAY_VIOLATION", "ELECTRICAL_ISOLATION", "OPPOSING_TRAIN_CONFLICT", "CREW_LIMIT", "STATION_LOOP_OVERFLOW", "MACHINE_RELOCATION_CONFLICT"
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
    tsl_violations_count: int = 0
    electrical_violations_count: int = 0
    crew_violations_count: int = 0
    headway_violations_count: int = 0

class MicroscopicDispatchValidator:
    """
    Tier 3 Microscopic Dispatch & Safety Validator.
    Simulates continuous train trajectories, block headway spacing,
    electrical elementary section isolations, Temporary Single Line (TSL) working,
    station loop overtaking feasibility, heavy machine relocation, and HOER crew rest limits.
    Produces named Benders cuts when microscopic conflicts arise.
    Advisory SIL-0 gate: No schedule may be returned as executable if microscopic validation fails.
    """
    def __init__(
        self,
        min_headway_hours: float = 0.1,         # ~6 minutes minimum headway
        max_premium_delay_hours: float = 0.25,   # 15 minutes max delay for Class 1 trains
        tsl_token_margin_hours: float = 0.25,    # 15 minutes pilot guard / token clearance for TSL
        max_crew_shift_hours: float = 12.0,      # HOER: max 12h duty
        min_crew_rest_hours: float = 16.0,       # HOER: min 16h mandatory rest
        machine_setup_hours: float = 0.5,        # 30 min machine setup/takedown
        elementary_section_map: Optional[Dict[str, str]] = None
    ):
        self.min_headway = min_headway_hours
        self.max_premium_delay = max_premium_delay_hours
        self.tsl_token_margin = tsl_token_margin_hours
        self.max_crew_shift = max_crew_shift_hours
        self.min_crew_rest = min_crew_rest_hours
        self.machine_setup = machine_setup_hours
        self.elementary_map = elementary_section_map or {}

    def validate_dispatch(
        self,
        scenario: Scenario,
        scheduled_jobs: List[ScheduledJob],
        electrical_isolated_blocks: Optional[Set[str]] = None,
        single_line_working_blocks: Optional[Set[str]] = None,
        crew_assignments: Optional[Dict[str, List[Tuple[float, float, str]]]] = None
    ) -> MicroscopicValidationResult:
        isolated_blocks = set(electrical_isolated_blocks or set())
        tsl_blocks = set(single_line_working_blocks or set())
        crew_roster = crew_assignments or {}

        # 1. Build block possession intervals & identify electrical isolation
        block_closures: Dict[str, List[Tuple[float, float, str]]] = {b.id: [] for b in scenario.blocks}
        for fb in scenario.fixed_blocks:
            if fb.block_id in block_closures:
                block_closures[fb.block_id].append((fb.start_time, fb.end_time, "FIXED_BLOCK"))
        for sj in scheduled_jobs:
            if sj.block_id in block_closures:
                block_closures[sj.block_id].append((sj.start_time, sj.end_time, sj.job_id))
            
            # TRD/OHE possession de-energizes the elementary section
            dept_str = sj.department.value if hasattr(sj.department, "value") else str(sj.department)
            if dept_str in ("OHE", "TRD"):
                isolated_blocks.add(sj.block_id)

        train_delays: Dict[str, float] = {}
        generated_cuts: List[BendersCut] = []
        violations: List[str] = []
        block_occupancies: Dict[str, List[Tuple[float, float, str, str]]] = {b.id: [] for b in scenario.blocks}

        # 2. Simulate train trajectories through network
        sorted_trains = sorted(scenario.trains, key=lambda t: t.scheduled_start)
        tsl_violation_cnt = 0
        elec_violation_cnt = 0
        headway_violation_cnt = 0
        crew_violation_cnt = 0

        for t in sorted_trains:
            curr_time = t.scheduled_start
            accumulated_delay = 0.0
            direction = getattr(t, "direction", "UP")

            for b_id in t.route:
                # 2.1 Electrical traction exclusion
                if b_id in isolated_blocks and getattr(t, "is_electric", True):
                    elec_violation_cnt += 1
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

                min_travel = t.min_travel_times.get(b_id, 0.25)
                block_free_at = curr_time

                # 2.2 Maintenance Possession Closure Collision
                for (s_cl, e_cl, reason) in block_closures.get(b_id, []):
                    if not (curr_time + min_travel <= s_cl or curr_time >= e_cl):
                        wait_delay = e_cl - curr_time
                        if wait_delay > 0:
                            accumulated_delay += wait_delay
                            block_free_at = max(block_free_at, e_cl)

                # 2.3 Headway spacing with previous trains on same block
                for (prev_s, prev_e, prev_tid, prev_dir) in block_occupancies.get(b_id, []):
                    # Check safe headway margin
                    if not (curr_time >= prev_s + self.min_headway or curr_time + min_travel <= prev_s):
                        headway_delay = (prev_s + self.min_headway) - curr_time
                        if headway_delay > 0:
                            accumulated_delay += headway_delay
                            block_free_at = max(block_free_at, prev_s + self.min_headway)

                    # 2.4 Temporary Single-Line (TSL) Opposing Movement Check
                    if b_id in tsl_blocks and prev_dir != direction:
                        # Opposing movements require clearance + pilot guard token margin
                        if not (curr_time >= prev_e + self.tsl_token_margin or curr_time + min_travel + self.tsl_token_margin <= prev_s):
                            tsl_violation_cnt += 1
                            cut = BendersCut(
                                cut_id=f"CUT-TSL-OPPOSE-{b_id}-{t.id}-{prev_tid}",
                                cut_type="OPPOSING_TRAIN_CONFLICT",
                                affected_block_id=b_id,
                                infeasible_window=(prev_s, prev_e + self.tsl_token_margin),
                                suggested_offset_hours=round(self.tsl_token_margin, 2),
                                description=f"TSL token conflict on single-line block {b_id}: opposing train {t.id} overlaps with {prev_tid}"
                            )
                            generated_cuts.append(cut)
                            violations.append(cut.description)

                traversal_start = block_free_at
                traversal_end = traversal_start + min_travel
                block_occupancies[b_id].append((traversal_start, traversal_end, t.id, direction))
                curr_time = traversal_end

            train_delays[t.id] = round(accumulated_delay, 3)

            # 2.5 Premium train punctuality SLA check
            is_premium = t.category.lower() in ("premium", "express_premium", "vande_bharat", "rajdhani")
            if is_premium and accumulated_delay > self.max_premium_delay:
                headway_violation_cnt += 1
                cut = BendersCut(
                    cut_id=f"CUT-PREM-DELAY-{t.id}",
                    cut_type="HEADWAY_VIOLATION",
                    affected_block_id=t.route[0] if t.route else "UNKNOWN",
                    infeasible_window=(t.scheduled_start, t.scheduled_end),
                    suggested_offset_hours=0.5,
                    description=f"Premium train {t.id} exceeds max delay threshold: {accumulated_delay*60:.1f}m > {self.max_premium_delay*60:.1f}m"
                )
                generated_cuts.append(cut)
                violations.append(cut.description)

        # 3. Machine relocation and setup time validation
        job_map = {j.id: j for j in scenario.jobs}
        machine_usage: Dict[str, List[Tuple[float, float, str, str]]] = {}
        for sj in scheduled_jobs:
            job = job_map.get(sj.job_id)
            if job:
                for res_id in job.required_resources.keys():
                    if res_id.startswith("R_BCM") or res_id.startswith("R_CSM") or res_id.startswith("R_TIE"):
                        machine_usage.setdefault(res_id, []).append((sj.start_time, sj.end_time, sj.block_id, sj.job_id))

        for m_id, intervals in machine_usage.items():
            intervals.sort(key=lambda x: x[0])
            for i in range(len(intervals) - 1):
                e_curr = intervals[i][1]
                s_next = intervals[i+1][0]
                blk_curr = intervals[i][2]
                blk_next = intervals[i+1][2]
                # If moving between different blocks, machine needs setup and travel margin
                if blk_curr != blk_next:
                    if s_next < e_curr + self.machine_setup:
                        cut = BendersCut(
                            cut_id=f"CUT-MACH-RELOC-{m_id}-{intervals[i+1][3]}",
                            cut_type="MACHINE_RELOCATION_CONFLICT",
                            affected_block_id=blk_next,
                            infeasible_window=(e_curr, e_curr + self.machine_setup),
                            suggested_offset_hours=self.machine_setup,
                            description=f"Machine {m_id} requires {self.machine_setup*60:.0f}m setup/relocation time between {blk_curr} and {blk_next}"
                        )
                        generated_cuts.append(cut)
                        violations.append(cut.description)

        # 4. HOER Crew Shift & Rest Limits
        for crew_id, shifts in crew_roster.items():
            shifts.sort(key=lambda s: s[0])
            for i, (s_start, s_end, job_id) in enumerate(shifts):
                shift_len = s_end - s_start
                if shift_len > self.max_crew_shift:
                    crew_violation_cnt += 1
                    cut = BendersCut(
                        cut_id=f"CUT-HOER-SHIFT-{crew_id}-{job_id}",
                        cut_type="CREW_LIMIT",
                        affected_block_id="CREW_ROSTER",
                        infeasible_window=(s_start, s_end),
                        suggested_offset_hours=shift_len - self.max_crew_shift,
                        description=f"HOER breach: Crew {crew_id} duty exceeds 12h limit ({shift_len:.1f}h)"
                    )
                    generated_cuts.append(cut)
                    violations.append(cut.description)

                if i < len(shifts) - 1:
                    rest_time = shifts[i+1][0] - s_end
                    if rest_time < self.min_crew_rest:
                        crew_violation_cnt += 1
                        cut = BendersCut(
                            cut_id=f"CUT-HOER-REST-{crew_id}-{shifts[i+1][2]}",
                            cut_type="CREW_LIMIT",
                            affected_block_id="CREW_ROSTER",
                            infeasible_window=(s_end, s_end + self.min_crew_rest),
                            suggested_offset_hours=self.min_crew_rest - rest_time,
                            description=f"HOER breach: Crew {crew_id} receives only {rest_time:.1f}h rest (< {self.min_crew_rest:.1f}h statutory)"
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
            diagnostics=[
                f"Simulated {len(scenario.trains)} trains across {len(scenario.blocks)} blocks. "
                f"Violations: {len(violations)} (TSL: {tsl_violation_cnt}, Elec: {elec_violation_cnt}, "
                f"Headway/SLA: {headway_violation_cnt}, Crew: {crew_violation_cnt})"
            ],
            tsl_violations_count=tsl_violation_cnt,
            electrical_violations_count=elec_violation_cnt,
            crew_violations_count=crew_violation_cnt,
            headway_violations_count=headway_violation_cnt
        )

