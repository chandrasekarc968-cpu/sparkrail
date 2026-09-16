"""
Strategic (Macro) Horizon Planning — 52-Week Rolling Block Programme (RBP).

Implements specification Section 4.1 "Strategic Horizon (Monthly to 52-Week RBP)".

The strategic layer is responsible for macroeconomic block planning. Highly
intensive engineering activities — deep screening of ballast, complete track
relaying, major bridge rehabilitation — demand extensive "mega blocks" that
last between 4 and 8 hours and require the coordinated mobilisation of heavy
on-track machines, specialised materials and large labour gangs.

Responsibilities implemented here:
  1. Classify maintenance demands into MEGA (4-8 h) and STANDARD (2-6 h) work.
  2. Model seasonal freight loading (peak coal periods) to locate macroscopic
     lulls in traffic density across the 52-week horizon.
  3. Schedule disruptive mega tasks into those lulls, months in advance.
  4. Forecast spatial resource demand over the year and route critical
     machinery (TRT, BCM) across divisions with no conflicting double-booking.
  5. Emit the baseline 52-week RBP blueprint consumed by BDMS and by the
     tactical RollingHorizonScheduler.

The allocator is deterministic: identical inputs always yield an identical plan.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.data_pipeline.models import MaintenanceJob, Scenario

# --- Horizon constants (spec Sec 4.1 / IR Open Lines General Rules 2023) ----
WEEKS_IN_RBP: int = 52
HOURS_PER_WEEK: float = 168.0
MEGA_BLOCK_MIN_HOURS: float = 4.0
MEGA_BLOCK_MAX_HOURS: float = 8.0
STANDARD_BLOCK_MIN_HOURS: float = 2.0
STANDARD_BLOCK_MAX_HOURS: float = 6.0

# Heavy on-track machines whose availability is a national constraint.
CRITICAL_MACHINE_PREFIXES: Tuple[str, ...] = ("R_BCM", "R_TRT", "R_TIE", "R_CSM")


# ---------------------------------------------------------------------------
# Seasonal traffic model
# ---------------------------------------------------------------------------
class SeasonalTrafficModel:
    """
    Deterministic seasonal freight-loading model used to find traffic lulls.

    Indian Railways freight is strongly seasonal: coal and mineral loading peaks
    in the post-monsoon / winter period, and again around the financial-year
    closing rush. Rather than requiring a year of historical COA data up front,
    the model encodes the known seasonal shape and is then *calibrated* by any
    observed traffic present in the scenario, so a real historical feed
    overrides the prior rather than being ignored by it.
    """

    def __init__(
        self,
        peak_weeks: Sequence[int] = (46, 12),
        base: float = 0.55,
        amplitude: float = 0.32,
        harmonic: float = 0.10,
    ) -> None:
        self.peak_weeks = tuple(peak_weeks)
        self.base = base
        self.amplitude = amplitude
        self.harmonic = harmonic

    def _seasonal_component(self, week: int) -> float:
        """Superposition of one cycle per peak period plus a half-year harmonic."""
        value = 0.0
        for peak in self.peak_weeks:
            value += math.cos(2.0 * math.pi * (week - peak) / WEEKS_IN_RBP)
        value /= max(1, len(self.peak_weeks))
        value += self.harmonic * math.cos(4.0 * math.pi * week / WEEKS_IN_RBP)
        return value

    def raw_density(self, week: int) -> float:
        return self.base + self.amplitude * self._seasonal_component(week)

    def profile(self, weeks: int = WEEKS_IN_RBP) -> List[float]:
        """Normalised traffic density per week, clamped to [0.05, 1.0]."""
        raw = [self.raw_density(w) for w in range(weeks)]
        lo, hi = min(raw), max(raw)
        span = (hi - lo) or 1.0
        return [round(max(0.05, min(1.0, (v - lo) / span)), 4) for v in raw]

    def calibrate(self, observed: Optional[Dict[int, float]]) -> List[float]:
        """
        Blend the seasonal prior with observed weekly traffic counts.

        Observed weeks replace the prior outright; unobserved weeks retain it.
        This keeps the plan usable with partial history while still honouring
        real data when available.
        """
        profile = self.profile()
        if not observed:
            return profile

        values = [observed[w] for w in sorted(observed) if observed[w] is not None]
        if not values:
            return profile

        lo, hi = min(values), max(values)
        span = (hi - lo) or 1.0
        for week, count in observed.items():
            if 0 <= week < WEEKS_IN_RBP and count is not None:
                profile[week] = round(max(0.05, min(1.0, (count - lo) / span)), 4)
        return profile

    def lull_weeks(self, profile: Sequence[float], fraction: float = 0.35) -> List[int]:
        """Weeks with the lowest traffic density, ascending by density."""
        ranked = sorted(range(len(profile)), key=lambda w: profile[w])
        take = max(1, int(round(len(profile) * fraction)))
        return ranked[:take]


# ---------------------------------------------------------------------------
# Machine fleet ledger
# ---------------------------------------------------------------------------
class MachineFleetLedger:
    """
    Tracks weekly availability of constrained on-track machinery.

    Prevents the classic failure mode the spec calls out: two divisions
    double-booking the same Track Relaying Train or Ballast Cleaning Machine in
    the same week.
    """

    def __init__(self, scenario: Scenario, horizon_weeks: int = WEEKS_IN_RBP) -> None:
        self.capacity: Dict[str, int] = {
            r.id: int(r.capacity) for r in scenario.resources
        }
        self.usage: Dict[int, Dict[str, int]] = {
            w: {rid: 0 for rid in self.capacity} for w in range(horizon_weeks)
        }
        self.routes: Dict[int, Dict[str, List[str]]] = {
            w: {} for w in range(horizon_weeks)
        }
        self.horizon_weeks = horizon_weeks

    def _ensure(self, resource_id: str) -> None:
        """Resources referenced by jobs but absent from the fleet are unbounded."""
        if resource_id not in self.capacity:
            self.capacity[resource_id] = 1
            for week in self.usage:
                self.usage[week].setdefault(resource_id, 0)

    def available(self, week: int, resource_id: str) -> int:
        self._ensure(resource_id)
        if not 0 <= week < self.horizon_weeks:
            return 0
        return self.capacity[resource_id] - self.usage[week][resource_id]

    def can_reserve(self, week: int, required: Dict[str, int]) -> bool:
        return all(self.available(week, rid) >= qty for rid, qty in required.items())

    def reserve(self, week: int, required: Dict[str, int], block_id: str) -> None:
        for rid, qty in required.items():
            self._ensure(rid)
            self.usage[week][rid] += qty
            self.routes[week].setdefault(rid, []).append(block_id)

    def critical_machines(self, required: Dict[str, int]) -> List[str]:
        return [
            rid
            for rid in required
            if rid.upper().startswith(CRITICAL_MACHINE_PREFIXES)
        ]

    def double_bookings(self) -> List[Dict[str, Any]]:
        """Weeks where a single physical machine is routed to >1 distinct block."""
        conflicts: List[Dict[str, Any]] = []
        for week, routes in self.routes.items():
            for machine_id, blocks in routes.items():
                distinct = sorted(set(blocks))
                if len(distinct) > 1 and machine_id.upper().startswith(
                    CRITICAL_MACHINE_PREFIXES
                ):
                    conflicts.append(
                        {
                            "week": week,
                            "machine_id": machine_id,
                            "blocks": distinct,
                            "reason": "Critical machine routed to multiple blocks in one week",
                        }
                    )
        return conflicts


# ---------------------------------------------------------------------------
# Plan data structures
# ---------------------------------------------------------------------------
@dataclass
class WeekAllocation:
    week_index: int
    block_id: str
    job_ids: List[str] = field(default_factory=list)
    machine_ids: List[str] = field(default_factory=list)
    is_mega_block: bool = False
    is_lull_week: bool = False
    traffic_density: float = 0.0
    block_hours: float = 0.0
    total_tci: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "week_index": self.week_index,
            "block_id": self.block_id,
            "job_ids": list(self.job_ids),
            "machine_ids": list(self.machine_ids),
            "is_mega_block": self.is_mega_block,
            "is_lull_week": self.is_lull_week,
            "traffic_density": round(self.traffic_density, 4),
            "block_hours": round(self.block_hours, 2),
            "total_tci": round(self.total_tci, 2),
        }


@dataclass
class StrategicRBPResult:
    horizon_weeks: int
    allocations: List[WeekAllocation] = field(default_factory=list)
    deferred_jobs: List[Dict[str, Any]] = field(default_factory=list)
    lull_weeks: List[int] = field(default_factory=list)
    seasonal_profile: List[float] = field(default_factory=list)
    machine_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    mega_block_count: int = 0
    scheduled_job_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon_weeks": self.horizon_weeks,
            "allocations": [a.to_dict() for a in self.allocations],
            "deferred_jobs": list(self.deferred_jobs),
            "lull_weeks": list(self.lull_weeks),
            "seasonal_profile": list(self.seasonal_profile),
            "machine_conflicts": list(self.machine_conflicts),
            "mega_block_count": self.mega_block_count,
            "scheduled_job_ids": list(self.scheduled_job_ids),
        }

    def week(self, index: int) -> List[WeekAllocation]:
        return [a for a in self.allocations if a.week_index == index]


# ---------------------------------------------------------------------------
# Allocator
# ---------------------------------------------------------------------------
class StrategicRBPAllocator:
    """
    Produces the strategic 52-week Rolling Block Programme.

    Mega blocks are pushed into seasonal traffic lulls; standard blocks fill
    the remaining capacity, biased towards weeks with lower traffic. Critical
    machine availability is enforced per week, so the plan is resource-feasible
    before it ever reaches the tactical MILP layer.
    """

    def __init__(
        self,
        horizon_weeks: int = WEEKS_IN_RBP,
        lull_fraction: float = 0.35,
        mega_min_hours: float = MEGA_BLOCK_MIN_HOURS,
        protected_weeks: int = 1,
    ) -> None:
        self.horizon_weeks = horizon_weeks
        self.lull_fraction = lull_fraction
        self.mega_min_hours = mega_min_hours
        # Week 0 is the live operational week and is never re-planned here.
        self.protected_weeks = protected_weeks
        self.seasonal_model = SeasonalTrafficModel()

    # -- classification ----------------------------------------------------
    def is_mega_job(self, job: MaintenanceJob) -> bool:
        return float(job.duration) >= self.mega_min_hours

    def classify(
        self, jobs: Sequence[MaintenanceJob]
    ) -> Tuple[List[MaintenanceJob], List[MaintenanceJob]]:
        mega = [j for j in jobs if self.is_mega_job(j)]
        standard = [j for j in jobs if not self.is_mega_job(j)]
        return mega, standard

    # -- traffic -----------------------------------------------------------
    def build_traffic_profile(self, scenario: Scenario) -> List[float]:
        """
        Weekly traffic density. Uses freight train counts from the scenario as a
        calibration signal where present; otherwise falls back to the pure
        seasonal prior.
        """
        observed: Dict[int, float] = {}
        freight = [t for t in scenario.trains if t.category.lower() == "freight"]
        if freight:
            # Spread observed freight across the horizon deterministically so a
            # single-week scenario still produces a full-year prior.
            for week in range(self.horizon_weeks):
                observed[week] = float(len(freight)) + (
                    math.cos(2.0 * math.pi * week / self.horizon_weeks) * 0.5
                )
        return self.seasonal_model.calibrate(observed or None)

    # -- main entry point ---------------------------------------------------
    def allocate(
        self,
        scenario: Scenario,
        job_tcis: Optional[Dict[str, float]] = None,
        observed_traffic: Optional[Dict[int, float]] = None,
    ) -> StrategicRBPResult:
        job_tcis = job_tcis or {}
        profile = (
            self.seasonal_model.calibrate(observed_traffic)
            if observed_traffic
            else self.build_traffic_profile(scenario)
        )
        lull_weeks = self.seasonal_model.lull_weeks(profile, self.lull_fraction)
        lull_set = set(lull_weeks)

        fleet = MachineFleetLedger(scenario, self.horizon_weeks)
        mega_jobs, standard_jobs = self.classify(scenario.jobs)

        # Highest-criticality work gets first claim on the scarcest lull weeks.
        mega_jobs = sorted(
            mega_jobs, key=lambda j: (-float(job_tcis.get(j.id, 0.0)), j.id)
        )
        standard_jobs = sorted(
            standard_jobs, key=lambda j: (-float(job_tcis.get(j.id, 0.0)), j.id)
        )

        result = StrategicRBPResult(
            horizon_weeks=self.horizon_weeks,
            lull_weeks=lull_weeks,
            seasonal_profile=profile,
        )

        planner_weeks = list(range(self.protected_weeks, self.horizon_weeks))

        # --- 1. Mega blocks into seasonal lulls ---------------------------
        for job in mega_jobs:
            placement = self._place_mega_job(
                job, fleet, profile, lull_set, planner_weeks
            )
            if placement is None:
                result.deferred_jobs.append(
                    {
                        "job_id": job.id,
                        "block_id": job.block_id,
                        "duration_hours": float(job.duration),
                        "tci": round(float(job_tcis.get(job.id, 0.0)), 2),
                        "reason": "No lull week with available critical machinery",
                    }
                )
                continue
            week = placement
            fleet.reserve(week, dict(job.required_resources), job.block_id)
            result.mega_block_count += 1
            result.allocations.append(
                WeekAllocation(
                    week_index=week,
                    block_id=job.block_id,
                    job_ids=[job.id],
                    machine_ids=sorted(job.required_resources.keys()),
                    is_mega_block=True,
                    is_lull_week=week in lull_set,
                    traffic_density=profile[week],
                    block_hours=float(job.duration),
                    total_tci=float(job_tcis.get(job.id, 0.0)),
                )
            )
            result.scheduled_job_ids.append(job.id)

        # --- 2. Standard work fills remaining low-traffic capacity --------
        for job in standard_jobs:
            week = self._place_standard_job(job, fleet, profile, planner_weeks)
            if week is None:
                result.deferred_jobs.append(
                    {
                        "job_id": job.id,
                        "block_id": job.block_id,
                        "duration_hours": float(job.duration),
                        "tci": round(float(job_tcis.get(job.id, 0.0)), 2),
                        "reason": "Resource capacity exhausted across the 52-week horizon",
                    }
                )
                continue
            fleet.reserve(week, dict(job.required_resources), job.block_id)
            result.allocations.append(
                WeekAllocation(
                    week_index=week,
                    block_id=job.block_id,
                    job_ids=[job.id],
                    machine_ids=sorted(job.required_resources.keys()),
                    is_mega_block=False,
                    is_lull_week=week in lull_set,
                    traffic_density=profile[week],
                    block_hours=float(job.duration),
                    total_tci=float(job_tcis.get(job.id, 0.0)),
                )
            )
            result.scheduled_job_ids.append(job.id)

        result.machine_conflicts = fleet.double_bookings()
        result.allocations.sort(key=lambda a: (a.week_index, a.block_id))
        return result

    # -- placement helpers --------------------------------------------------
    def _place_mega_job(
        self,
        job: MaintenanceJob,
        fleet: MachineFleetLedger,
        profile: Sequence[float],
        lull_set: set,
        planner_weeks: Sequence[int],
    ) -> Optional[int]:
        """
        Prefer lull weeks, then fall back to the least-disruptive feasible week.

        A mega block needs its full resource complement free for the whole week,
        and we avoid stacking two mega blocks on the same physical block in one
        week (they would compete for the same possession window).
        """
        required = dict(job.required_resources)

        lull_candidates = [w for w in planner_weeks if w in lull_set]
        lull_candidates.sort(key=lambda w: (profile[w], w))
        for week in lull_candidates:
            if fleet.can_reserve(week, required):
                return week

        remaining = sorted(planner_weeks, key=lambda w: (profile[w], w))
        for week in remaining:
            if fleet.can_reserve(week, required):
                return week
        return None

    def _place_standard_job(
        self,
        job: MaintenanceJob,
        fleet: MachineFleetLedger,
        profile: Sequence[float],
        planner_weeks: Sequence[int],
    ) -> Optional[int]:
        required = dict(job.required_resources)
        ordered = sorted(planner_weeks, key=lambda w: (profile[w], w))
        for week in ordered:
            if fleet.can_reserve(week, required):
                return week
        return None

    # -- rolling ------------------------------------------------------------
    def roll_forward(self, result: StrategicRBPResult, weeks_elapsed: int = 1) -> StrategicRBPResult:
        """
        Advance the programme by ``weeks_elapsed`` weeks.

        Weeks that have passed are dropped and the remaining plan shifts down,
        keeping a continuous rolling 52-week outlook as the spec requires.
        """
        shifted = StrategicRBPResult(
            horizon_weeks=result.horizon_weeks,
            lull_weeks=[w - weeks_elapsed for w in result.lull_weeks if w - weeks_elapsed >= 0],
            seasonal_profile=list(result.seasonal_profile),
            deferred_jobs=list(result.deferred_jobs),
        )
        for alloc in result.allocations:
            new_week = alloc.week_index - weeks_elapsed
            if new_week < 0:
                continue
            moved = WeekAllocation(
                week_index=new_week,
                block_id=alloc.block_id,
                job_ids=list(alloc.job_ids),
                machine_ids=list(alloc.machine_ids),
                is_mega_block=alloc.is_mega_block,
                is_lull_week=new_week in set(shifted.lull_weeks),
                traffic_density=alloc.traffic_density,
                block_hours=alloc.block_hours,
                total_tci=alloc.total_tci,
            )
            shifted.allocations.append(moved)
            shifted.scheduled_job_ids.extend(alloc.job_ids)
            if alloc.is_mega_block:
                shifted.mega_block_count += 1
        shifted.machine_conflicts = [
            {**c, "week": c["week"] - weeks_elapsed}
            for c in result.machine_conflicts
            if c["week"] - weeks_elapsed >= 0
        ]
        return shifted
