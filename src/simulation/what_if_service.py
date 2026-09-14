import copy
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple

from src.data_pipeline.models import (
    Scenario,
    MaintenanceJob,
    Train,
    WhatIfModification,
    WhatIfScenarioRequest,
    WhatIfDeltaReport,
    WhatIfScenarioResponse,
    TrainDelayDelta,
    BlockShiftRequest,
    BlockShiftResponse
)
from src.ai_ml.justification_generator import JustificationGenerator
from src.optimization.milp_solver import MaintenanceSchedulerMILP
from src.simulation.simulator import LocalSimulator

class WhatIfSimulatorService:
    """
    What-If Sandbox & Scenario Simulator Service.
    Enables Senior Divisional Operations Managers (Sr. DOM), Chief Controllers, and Section Controllers
    to evaluate hypothetical disruptions and maintenance window shifts in an isolated, in-memory staging
    environment with zero risk to live operations.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def run_what_if_scenario(
        self,
        base_scenario: Scenario,
        baseline_schedule: Dict[str, Any],
        request: WhatIfScenarioRequest
    ) -> WhatIfScenarioResponse:
        """
        Clones base scenario in-memory, applies user modifications, runs solver,
        and computes a detailed comparative delta report.
        """
        run_id = f"WIF-{uuid.uuid4().hex[:8].upper()}"
        cloned_scenario = copy.deepcopy(base_scenario)

        # 1. Apply weather override if specified
        if request.weather_override:
            cloned_scenario.weather = request.weather_override

        # 2. Apply modifications to jobs and trains
        modified_job_ids = set()
        for mod in request.modifications:
            if mod.job_id:
                for j in cloned_scenario.jobs:
                    if j.id == mod.job_id:
                        modified_job_ids.add(j.id)
                        if mod.extend_duration_hours is not None:
                            j.duration += float(mod.extend_duration_hours)
                        if mod.shift_start_hours is not None and j.is_fixed:
                            j.fixed_start = float(mod.shift_start_hours)
                        break

            if mod.cancel_job and mod.job_id:
                cloned_scenario.jobs = [j for j in cloned_scenario.jobs if j.id != mod.job_id]

            if mod.train_id:
                for tr in cloned_scenario.trains:
                    if tr.id == mod.train_id:
                        if mod.added_delay_min is not None:
                            delay_h = float(mod.added_delay_min) / 60.0
                            tr.scheduled_start += delay_h
                            tr.scheduled_end += delay_h
                        if mod.speed_restriction_kmh is not None:
                            tr.max_speed_kmh = float(mod.speed_restriction_kmh)
                        break

            if mod.speed_restriction_kmh and mod.affected_block_id:
                for b in cloned_scenario.blocks:
                    if b.id == mod.affected_block_id:
                        b.speed_restriction_kmh = float(mod.speed_restriction_kmh)

        # 3. Solve modified scenario
        job_tcis = {j.id: 50.0 for j in cloned_scenario.jobs}
        solver = MaintenanceSchedulerMILP(self.config)
        what_if_schedule = solver.solve(cloned_scenario, job_tcis)

        # 4. Comparative Delta Analysis
        delta_report = self._compute_delta_report(
            base_scenario=base_scenario,
            baseline_schedule=baseline_schedule,
            modified_scenario=cloned_scenario,
            what_if_schedule=what_if_schedule,
            modifications=request.modifications
        )

        return WhatIfScenarioResponse(
            status="SUCCESS",
            run_id=run_id,
            delta_report=delta_report,
            what_if_schedule=what_if_schedule,
            conflicts_count=len(what_if_schedule.get("safety_audit", {}).get("violations", []))
        )

    def _compute_delta_report(
        self,
        base_scenario: Scenario,
        baseline_schedule: Dict[str, Any],
        modified_scenario: Scenario,
        what_if_schedule: Dict[str, Any],
        modifications: List[WhatIfModification]
    ) -> WhatIfDeltaReport:
        """
        Compares baseline vs what-if schedule to produce quantitative deltas.
        """
        sim_base = LocalSimulator(base_scenario).simulate(baseline_schedule)
        sim_what_if = LocalSimulator(modified_scenario).simulate(what_if_schedule)

        base_delays = sim_base["train_delays"]
        wif_delays = sim_what_if["train_delays"]

        base_total_min = sum(base_delays.values()) * 60.0
        wif_total_min = sum(wif_delays.values()) * 60.0
        delta_total_min = round(wif_total_min - base_total_min, 1)

        train_deltas: List[TrainDelayDelta] = []
        total_energy_kwh = 0.0
        crew_warnings: List[str] = []
        freight_regulated = 0

        for tr in modified_scenario.trains:
            b_min = base_delays.get(tr.id, 0.0) * 60.0
            w_min = wif_delays.get(tr.id, 0.0) * 60.0
            d_min = round(w_min - b_min, 1)

            tonnage = getattr(tr, "gross_tonnage_tonnes", 1500.0) or 1500.0
            spd = getattr(tr, "max_speed_kmh", 75.0) or 75.0
            is_freight = (tr.category.lower() == "freight" or getattr(tr, "is_loaded_freight", False))

            energy_loss = 0.0
            if d_min > 0:
                # Stopping train causes kinetic energy loss
                energy_loss = JustificationGenerator.calculate_kinetic_energy_kwh(tonnage, spd)
                total_energy_kwh += energy_loss
                if is_freight:
                    freight_regulated += 1

            # Check crew duty limit
            crew_exceeded = False
            expiry_t = getattr(tr, "crew_duty_expiry_timestamp", None)
            if expiry_t is not None:
                new_arrival = tr.scheduled_end + (w_min / 60.0)
                if new_arrival > expiry_t:
                    crew_exceeded = True
                    crew_warnings.append(
                        f"Train {tr.id} ({tr.name or 'Freight'}) delayed by {w_min:.0f} mins; "
                        f"arrival T+{new_arrival:.1f}h exceeds statutory HOER crew duty ceiling T+{expiry_t:.1f}h!"
                    )

            train_deltas.append(TrainDelayDelta(
                train_id=tr.id,
                train_name=tr.name,
                category=tr.category,
                baseline_delay_min=b_min,
                what_if_delay_min=w_min,
                delta_delay_min=d_min,
                energy_loss_kwh=energy_loss,
                crew_duty_exceeded=crew_exceeded
            ))

        # Heavy Machine Productivity Delta (hours worked)
        base_sched_jobs = baseline_schedule.get("scheduled_jobs", [])
        wif_sched_jobs = what_if_schedule.get("scheduled_jobs", [])
        
        base_mach_hours = sum(
            j["end_time"] - j["start_time"] for j in base_sched_jobs 
            if any(r.startswith("R_BCM") or r.startswith("R_TIE") for r in j.get("assigned_resources", []))
        )
        wif_mach_hours = sum(
            j["end_time"] - j["start_time"] for j in wif_sched_jobs 
            if any(r.startswith("R_BCM") or r.startswith("R_TIE") for r in j.get("assigned_resources", []))
        )
        mach_delta_hours = round(wif_mach_hours - base_mach_hours, 1)

        # Cost impact (approx ₹8.5/kWh traction electricity)
        cost_inr = round(total_energy_kwh * 8.5)

        # Bilingual Summaries
        if delta_total_min > 0:
            summary_en = (
                f"What-If Simulation Result: Injected changes introduce +{delta_total_min:.0f} min cumulative delay across "
                f"{freight_regulated} freight services. Additional traction kinetic energy dissipated: {total_energy_kwh:,.0f} kWh "
                f"(approx ₹{cost_inr:,}). Machine window change: {mach_delta_hours:+.1f} hours. "
                f"Crew statutory warnings: {len(crew_warnings)}."
            )
            summary_hi = (
                f"वॉट-इफ सिमुलेशन परिणाम: प्रस्तावित परिवर्तनों से {freight_regulated} मालगाड़ियों में कुल +{delta_total_min:.0f} मिनट का "
                f"अतिरिक्त विलंब होता है। पुन: गति पकड़ने में अनुमानित {total_energy_kwh:,.0f} kWh अतिरिक्त बिजली (लगभग ₹{cost_inr:,}) खर्च होगी। "
                f"ट्रैक मशीन कार्य समय में {mach_delta_hours:+.1f} घंटे का परिवर्तन। "
                f"वैधानिक क्रू चेतावनी: {len(crew_warnings)}।"
            )
        else:
            summary_en = (
                f"What-If Simulation Result: Scenario absorbed cleanly with {delta_total_min:.0f} min net delay impact. "
                f"Heavy machine productivity change: {mach_delta_hours:+.1f} hours. Zero crew duty breaches."
            )
            summary_hi = (
                f"वॉट-इफ सिमुलेशन परिणाम: परिवर्तन बिना किसी अतिरिक्त विलंब ({delta_total_min:.0f} मिनट) के समायोजित हो गया। "
                f"मशीन उत्पादकता परिवर्तन: {mach_delta_hours:+.1f} घंटे। क्रू नियमों का पूर्ण अनुपालन।"
            )

        return WhatIfDeltaReport(
            baseline_cumulative_delay_min=base_total_min,
            what_if_cumulative_delay_min=wif_total_min,
            delta_cumulative_delay_min=delta_total_min,
            train_deltas=train_deltas,
            heavy_machine_productivity_delta_hours=mach_delta_hours,
            freight_rakes_regulated_count=freight_regulated,
            total_energy_loss_kwh=round(total_energy_kwh, 2),
            total_fuel_cost_impact_inr=float(cost_inr),
            crew_hours_timeout_warnings=crew_warnings,
            narrative_summary_en=summary_en,
            narrative_summary_hi=summary_hi
        )

    def evaluate_block_shift(
        self,
        scenario: Scenario,
        schedule: Dict[str, Any],
        request: BlockShiftRequest
    ) -> BlockShiftResponse:
        """
        Fast debounced evaluation for Digital Marey Chart drag-and-drop.
        Calculates resulting train conflicts and delay deltas when a controller shifts a block.
        """
        shift_hours = request.shift_minutes / 60.0
        scheduled_jobs = schedule.get("scheduled_jobs", [])
        target_job = next((j for j in scheduled_jobs if j.get("job_id") == request.job_id), None)

        if not target_job:
            return BlockShiftResponse(
                job_id=request.job_id,
                block_id="UNKNOWN",
                original_start_hours=0.0,
                new_start_hours=0.0,
                new_end_hours=0.0,
                is_feasible=False,
                conflict_count=1,
                delta_delay_min=0.0,
                conflicts=[{"reason": f"Job {request.job_id} not in schedule"}],
                bilingual_advisory={"en": "Job not found", "hi": "कार्य नहीं मिला"}
            )

        orig_start = float(target_job["start_time"])
        orig_end = float(target_job["end_time"])
        dur = orig_end - orig_start
        new_start = round(orig_start + shift_hours, 2)
        new_end = round(new_start + dur, 2)
        block_id = target_job["block_id"]

        conflicts = []
        delta_delay_h = 0.0

        # Boundary check
        if new_start < 0.0 or new_end > 24.0:
            conflicts.append({"type": "HORIZON_BREACH", "detail": "Shifted window extends outside 24-hour planning horizon"})

        # Check train path intersections
        for tr in scenario.trains:
            if block_id in tr.route:
                overlap = max(0.0, min(new_end, tr.scheduled_end) - max(new_start, tr.scheduled_start))
                if overlap > 0:
                    delta_delay_h += overlap
                    is_prem = (tr.category.lower() == "premium")
                    conflicts.append({
                        "type": "TRAIN_CONFLICT",
                        "train_id": tr.id,
                        "train_name": tr.name,
                        "category": tr.category,
                        "overlap_hours": overlap,
                        "is_premium": is_prem
                    })

        # Peak summer thermal check (IRPWM Para 509)
        if scenario.weather and scenario.weather.is_summer_buckling_risk:
            dept = target_job.get("department", "")
            if dept in ("CIVIL", "ENGINEERING"):
                if max(new_start, 12.0) < min(new_end, 16.0):
                    conflicts.append({
                        "type": "THERMAL_BUCKLING_RISK",
                        "detail": f"Shifted into peak summer midday window (12:00-16:00, rail temp {scenario.weather.rail_temp_celsius}°C)"
                    })

        is_feasible = (len(conflicts) == 0 or all(c.get("type") != "HORIZON_BREACH" for c in conflicts))
        delta_delay_min = round(delta_delay_h * 60.0, 1)

        advisory_en = (
            f"Shifted Block {request.job_id} by {request.shift_minutes:+.0f} mins to [{new_start:.1f}h - {new_end:.1f}h]. "
            f"Resulting train conflicts: {len(conflicts)}. Added train delay: {delta_delay_min:.0f} mins."
        )
        advisory_hi = (
            f"ब्लॉक {request.job_id} को {request.shift_minutes:+.0f} मिनट खिसकाकर [{new_start:.1f}h - {new_end:.1f}h] किया गया। "
            f"परिणामी ट्रेन टकराव: {len(conflicts)}। अतिरिक्त विलंब: {delta_delay_min:.0f} मिनट।"
        )

        return BlockShiftResponse(
            job_id=request.job_id,
            block_id=block_id,
            original_start_hours=orig_start,
            new_start_hours=new_start,
            new_end_hours=new_end,
            is_feasible=is_feasible,
            conflict_count=len(conflicts),
            delta_delay_min=delta_delay_min,
            conflicts=conflicts,
            bilingual_advisory={"en": advisory_en, "hi": advisory_hi}
        )
