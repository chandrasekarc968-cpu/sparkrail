from typing import Dict, Any, List
from src.data_pipeline.models import Scenario, MaintenanceJob

class RollingHorizonScheduler:
    """
    Manages the rolling-horizon freeze mechanics for the maintenance block schedule.
    Week 1 (or the immediate freeze period) is frozen and cannot be automatically changed.
    """
    
    def __init__(self, freeze_duration_hours: int = 24):
        self.freeze_duration = freeze_duration_hours

    def apply_freeze(self, previous_schedule: Dict[str, Any], new_scenario: Scenario) -> Scenario:
        """
        Takes the previously optimized schedule and a new raw scenario.
        Modifies the new scenario to hard-fix jobs that were scheduled within the freeze window.
        """
        frozen_jobs = []
        if previous_schedule and "scheduled_jobs" in previous_schedule:
            for sched_job in previous_schedule["scheduled_jobs"]:
                start_time = sched_job["start_time"]
                if start_time < self.freeze_duration:
                    frozen_jobs.append(sched_job)
        
        # Modify the new scenario jobs in-place to enforce the freeze
        for job in new_scenario.jobs:
            # Check if this job was frozen
            for f_job in frozen_jobs:
                if job.id == f_job["job_id"]:
                    job.is_fixed = True
                    job.fixed_start = f_job["start_time"]
                    
        return new_scenario
