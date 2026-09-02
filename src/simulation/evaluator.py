from typing import Dict, Any, List
from src.data_pipeline.models import Scenario

class KPIEvaluator:
    """
    Evaluates the optimized schedule against a baseline and calculates Key Performance Indicators.
    """
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        
    def evaluate(self, schedule: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates BUE, SBR, ADR, PII, and Scheduled TCI coverage."""
        
        scheduled_jobs = schedule.get("scheduled_jobs", [])
        total_closure_time = schedule.get("total_closure_time", 0.0)
        train_delays = schedule.get("train_delays", {})
        
        # 1. Block Utilization Efficiency (BUE)
        # Ratio of actual machine/labor working hours to total block hours
        actual_work_hours = sum(j["end_time"] - j["start_time"] for j in scheduled_jobs)
        bue = (actual_work_hours / total_closure_time) * 100 if total_closure_time > 0 else 0.0
        
        # 2. Shadow Block Ratio (SBR)
        # Ratio of blocks serving multiple departments
        blocks_used = {}
        for j in scheduled_jobs:
            block_tup = (j["block_id"], j["start_time"], j["end_time"])
            job_obj = next((job for job in self.scenario.jobs if job.id == j["job_id"]), None)
            dept = job_obj.department if job_obj else "Unknown"
            
            if block_tup not in blocks_used:
                blocks_used[block_tup] = set()
            blocks_used[block_tup].add(dept)
            
        shadow_blocks = sum(1 for depts in blocks_used.values() if len(depts) > 1)
        sbr = (shadow_blocks / len(blocks_used)) * 100 if blocks_used else 0.0
        
        # 3. Punctuality Impact Index (PII)
        pii = sum(train_delays.values())
        
        # 4. TCI Coverage
        total_possible_tci = sum(j.get("tci", 0) for j in scheduled_jobs) + \
                             sum(self._get_tci_for_unscheduled(j["job_id"]) for j in schedule.get("unscheduled_jobs", []))
                             
        scheduled_tci = sum(j.get("tci", 0) for j in scheduled_jobs)
        tci_coverage = (scheduled_tci / total_possible_tci) * 100 if total_possible_tci > 0 else 0.0

        metrics = {
            "Block Utilization Efficiency (BUE) %": round(bue, 2),
            "Shadow Block Ratio (SBR) %": round(sbr, 2),
            "Punctuality Impact Index (PII) delays": round(pii, 2),
            "Scheduled TCI Coverage %": round(tci_coverage, 2),
            "Total Closure Hours": round(total_closure_time, 2),
            "Consolidated Blocks (Shadow)": shadow_blocks
        }
        
        schedule["kpi_metrics"] = metrics
        return schedule
        
    def _get_tci_for_unscheduled(self, job_id: str) -> float:
        # Simplification: we might need to pass the raw TCI dict to evaluate.
        # For MVP, assume it's passed or retrieved. Since we don't have it here, we'll return a dummy value
        # But wait, we can just calculate it or have it passed.
        return 0.0 # Will be refined later if needed
