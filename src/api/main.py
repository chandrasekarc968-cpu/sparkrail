from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import yaml

from src.data_pipeline.synthetic_data import generate_synthetic_data, save_synthetic_data
from src.data_pipeline.ingestion import DataIngestor
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.optimization.milp_solver import MaintenanceSchedulerMILP
from src.simulation.evaluator import KPIEvaluator

app = FastAPI(
    title="SparkRail AI Block Planning API",
    description="API for the AI-Powered Automatic Block Planning System",
    version="1.0.0"
)

def load_config():
    path = "config/settings.yaml"
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f)

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.post("/data/generate")
def generate_data():
    try:
        save_synthetic_data()
        return {"message": "Synthetic data generated successfully at data/synthetic"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/score")
def score_jobs():
    config = load_config()
    try:
        ingestor = DataIngestor(config)
        scenario = ingestor.load_scenario()
        scorer = TaskCriticalityScorer(config)
        
        results = []
        for job in scenario.jobs:
            tci, explanation = scorer.calculate_tci(job.tci_inputs)
            results.append({
                "job_id": job.id,
                "tci": tci,
                "explanation": explanation
            })
        return {"scored_jobs": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize")
def optimize_schedule():
    config = load_config()
    try:
        ingestor = DataIngestor(config)
        scenario = ingestor.load_scenario()
        
        scorer = TaskCriticalityScorer(config)
        job_tcis = {job.id: scorer.calculate_tci(job.tci_inputs)[0] for job in scenario.jobs}
        
        solver = MaintenanceSchedulerMILP(config)
        result = solver.solve(scenario, job_tcis)
        
        # Save output for evaluate
        os.makedirs("data", exist_ok=True)
        with open("data/schedule_output.json", "w") as f:
            json.dump(result, f, indent=4)
            
        return {"status": result["status"], "solver": result["solver"], "total_closure_time": result["total_closure_time"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate")
def evaluate_kpis():
    config = load_config()
    try:
        ingestor = DataIngestor(config)
        scenario = ingestor.load_scenario()
        scorer = TaskCriticalityScorer(config)
        job_tcis = {job.id: scorer.calculate_tci(job.tci_inputs)[0] for job in scenario.jobs}
        
        if not os.path.exists("data/schedule_output.json"):
            raise HTTPException(status_code=404, detail="Schedule not found. Run /optimize first.")
            
        with open("data/schedule_output.json", "r") as f:
            schedule = json.load(f)
            
        evaluator = KPIEvaluator(scenario)
        result = evaluator.evaluate(schedule, job_tcis)
        
        return result["kpi_metrics"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schedule/{schedule_id}")
def get_schedule(schedule_id: str):
    # Dummy implementation assuming "latest" for MVP
    if schedule_id != "latest":
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    if not os.path.exists("data/schedule_output.json"):
        raise HTTPException(status_code=404, detail="Schedule not found.")
        
    with open("data/schedule_output.json", "r") as f:
        return json.load(f)

if __name__ == "__main__":
    import uvicorn
    config = load_config()
    host = config.get("api", {}).get("host", "0.0.0.0")
    port = int(config.get("api", {}).get("port", 8000))
    uvicorn.run(app, host=host, port=port)
