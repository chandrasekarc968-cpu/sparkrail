from typing import Dict, Any, List
from src.data_pipeline.models import Scenario

class LocalSimulator:
    """
    Deterministic local simulation engine that calculates exact train delays and block usages 
    without relying on external tools like SUMO.
    """
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.horizon = 24

    def simulate(self, schedule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replays the scheduled jobs over the scenario and computes true delays.
        """
        block_closures: Dict[str, set] = {b.id: set() for b in self.scenario.blocks}
        
        # Add scheduled jobs
        for job in schedule.get("scheduled_jobs", []):
            start = int(job["start_time"])
            end = int(job["end_time"])
            for t in range(start, end):
                block_closures[job["block_id"]].add(t)
                
        # Add fixed blocks
        for fb in self.scenario.fixed_blocks:
            for t in range(int(fb.start_time), int(fb.end_time)):
                block_closures[fb.block_id].add(t)
                
        train_delays = {}
        for train in self.scenario.trains:
            delay = 0.0
            for k in train.route:
                for t in range(int(train.scheduled_start), int(train.scheduled_end)):
                    if t in block_closures.get(k, set()):
                        delay += 1.0
            train_delays[train.id] = delay
            
        total_closure_hours = sum(len(closures) for closures in block_closures.values())
        
        return {
            "train_delays": train_delays,
            "total_closure_hours": float(total_closure_hours)
        }

    def run_baseline_manual_scheduler(self, job_tcis: Dict[str, float]) -> Dict[str, Any]:
        """
        Generates a baseline schedule mimicking manual, non-shadow-block operations.
        Jobs are scheduled consecutively on blocks, causing maximum closures and delays.
        """
        sorted_jobs = sorted(self.scenario.jobs, key=lambda j: job_tcis.get(j.id, 0.0), reverse=True)
        scheduled_jobs = []
        block_closures: Dict[str, set] = {b.id: set() for b in self.scenario.blocks}
        
        for job in sorted_jobs:
            if job.is_fixed and job.fixed_start is not None:
                start = int(job.fixed_start)
                scheduled_jobs.append({
                    "job_id": job.id, "block_id": job.block_id,
                    "start_time": start, "end_time": start + job.duration,
                    "tci": job_tcis.get(job.id, 0.0), "department": job.department
                })
                for t in range(start, int(start + job.duration)):
                    block_closures[job.block_id].add(t)
                continue
                
            # Manual schedules just find the next open block without trying to stack departments
            for t_candidate in range(self.horizon - int(job.duration) + 1):
                open_slot = True
                for t in range(t_candidate, t_candidate + int(job.duration)):
                    if t in block_closures[job.block_id]:
                        open_slot = False
                        break
                if open_slot:
                    scheduled_jobs.append({
                        "job_id": job.id, "block_id": job.block_id,
                        "start_time": t_candidate, "end_time": t_candidate + job.duration,
                        "tci": job_tcis.get(job.id, 0.0), "department": job.department
                    })
                    for t in range(t_candidate, t_candidate + int(job.duration)):
                        block_closures[job.block_id].add(t)
                    break
                    
        return {"scheduled_jobs": scheduled_jobs}
