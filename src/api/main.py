import os
import sys
import json
import yaml
import time
import uuid
import logging
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.data_pipeline.models import (
    Scenario,
    OptimizedSchedule,
    KPIReport,
    HealthResponse,
    DataGenerateRequest,
    DataGenerateResponse,
    ScoreRequest,
    ScoreResponse,
    ScoredJob,
    OptimizeRequest,
    EvaluateRequest,
    AssetHealthRecord,
    SystemEvent,
    NetworkGeometryResponse,
    PlanningCapabilitiesResponse,
    ConflictItem
)
from src.data_pipeline.synthetic_data import (
    generate_synthetic_data,
    save_synthetic_data,
    generate_synthetic_assets,
    generate_synthetic_events,
    generate_network_geometry,
    derive_conflicts
)
from src.data_pipeline.ingestion import DataIngestor, DataIngestionError
from src.data_pipeline.geometry_validator import validate_network_geometry, GeometryValidationError
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.optimization.milp_solver import MaintenanceSchedulerMILP, SCIP_AVAILABLE
from src.simulation.evaluator import KPIEvaluator

# Setup structured logger
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] [req:%(request_id)s] %(name)s: %(message)s"
)

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True

logger = logging.getLogger("SparkRailAPI")
logger.addFilter(RequestIdFilter())

app = FastAPI(
    title="SparkRail AI Block Planning API",
    description="Production-grade API for automated railway track possession & shadow block scheduling",
    version="1.0.0"
)

# CORS Configuration strictly from environment variable
cors_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
allowed_origins = [orig.strip() for orig in cors_env.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)

# Request ID and Structured Logging Middleware
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    start_time = time.time()

    extra = {"request_id": req_id}
    logger.info(f"Incoming {request.method} {request.url.path}", extra=extra)

    try:
        response: Response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000.0
        logger.error(f"Unhandled error processing {request.method} {request.url.path}: {exc}", extra=extra)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred while processing the request."},
            headers={"X-Request-ID": req_id}
        )

    duration_ms = (time.time() - start_time) * 1000.0
    response.headers["X-Request-ID"] = req_id
    logger.info(
        f"Completed {request.method} {request.url.path} with status {response.status_code} in {duration_ms:.2f}ms",
        extra=extra
    )
    return response

# Validation Error Handler (Sanitizes error output)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", "-")
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}", extra={"request_id": req_id})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Validation error", "errors": exc.errors()},
        headers={"X-Request-ID": req_id}
    )

def get_base_data_dir() -> str:
    """Returns configurable data directory, preventing hardcoded paths."""
    return os.getenv("SPARKRAIL_DATA_DIR", os.path.join(os.getcwd(), "data"))

def get_config() -> Dict[str, Any]:
    config_path = os.getenv("SPARKRAIL_CONFIG_PATH", "config/settings.yaml")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    return {}

# 1. Health Endpoint
@app.get("/health", response_model=HealthResponse)
def health_check():
    """
    Health check returning system status, version, solver availability,
    data mode, and git commit SHA.
    """
    commit_sha = os.getenv("GIT_COMMIT_SHA", None)
    if not commit_sha:
        try:
            import subprocess
            commit_sha = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            commit_sha = "production"

    return HealthResponse(
        status="ok",
        version="1.0.0",
        geometry_schema_version="1.0.0",
        solver_available=SCIP_AVAILABLE,
        solver_name="PySCIPOpt" if SCIP_AVAILABLE else "NON_OPTIMAL_FALLBACK",
        data_mode="local_synthetic",
        commit_sha=commit_sha
    )

# 2. Synthetic Data Generation
@app.post("/data/generate", response_model=DataGenerateResponse)
def generate_data(req: Optional[DataGenerateRequest] = None):
    """Generates deterministic synthetic railway division data."""
    params = req or DataGenerateRequest()
    data_dir = os.path.join(get_base_data_dir(), "synthetic")
    try:
        file_path = save_synthetic_data(
            path=data_dir,
            seed=params.seed,
            num_blocks=params.num_blocks,
            num_jobs=params.num_jobs,
            num_trains=params.num_trains
        )
        return DataGenerateResponse(
            message="Synthetic dataset generated successfully.",
            seed=params.seed,
            blocks_count=params.num_blocks,
            jobs_count=params.num_jobs,
            trains_count=params.num_trains,
            output_path=file_path
        )
    except Exception as e:
        logger.error(f"Error generating synthetic data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate synthetic railway scenario."
        )

# 3. Task Criticality Index Scoring
@app.post("/score", response_model=ScoreResponse)
def score_jobs(req: Optional[ScoreRequest] = None):
    """Scores railway maintenance jobs using the multi-attribute TCI formula."""
    config = get_config()
    try:
        if req and req.scenario:
            scenario = req.scenario
        else:
            synth_path = os.path.join(get_base_data_dir(), "synthetic")
            scenario_file = os.path.join(synth_path, "scenario.json")
            if not os.path.exists(scenario_file):
                save_synthetic_data(path=synth_path)
            ingestor = DataIngestor({"data_pipeline": {"use_local_synthetic": True, "synthetic_data_path": synth_path}})
            scenario = ingestor.load_scenario()

        scorer = TaskCriticalityScorer(config)
        scored_jobs: List[ScoredJob] = []

        for job in scenario.jobs:
            tci_val, explanation = scorer.calculate_tci(job.tci_inputs)
            scored_jobs.append(ScoredJob(
                job_id=job.id,
                tci=tci_val,
                explanation=explanation
            ))

        return ScoreResponse(
            scored_jobs=scored_jobs,
            model_mode="rule_based",
            model_version=TaskCriticalityScorer.MODEL_VERSION
        )
    except Exception as e:
        logger.error(f"Error calculating TCI scores: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate Task Criticality Index scores."
        )

def build_schedule_explainability(scenario: Scenario, schedule_data: Dict[str, Any], job_tcis: Dict[str, float]) -> Dict[str, Any]:
    scorer = TaskCriticalityScorer(get_config())
    explanations = {}
    
    for sj in schedule_data.get("scheduled_jobs", []):
        job_id = sj["job_id"] if isinstance(sj, dict) else sj.job_id
        block_id = sj["block_id"] if isinstance(sj, dict) else sj.block_id
        start_time = sj["start_time"] if isinstance(sj, dict) else sj.start_time
        end_time = sj["end_time"] if isinstance(sj, dict) else sj.end_time
        is_shadow = sj.get("is_shadow_block", False) if isinstance(sj, dict) else sj.is_shadow_block
        shadow_with = sj.get("shadow_with_jobs", []) if isinstance(sj, dict) else sj.shadow_with_jobs

        job = next((j for j in scenario.jobs if j.id == job_id), None)
        tci_val = job_tcis.get(job_id, 0.0)
        tci_expl = scorer.calculate_tci(job.tci_inputs)[1] if job else None
        
        priority_reasons = []
        if job and job.is_fixed:
            priority_reasons.append("Pre-scheduled immutable mega-block commitment.")
        elif tci_val >= 0.7:
            priority_reasons.append(f"High Task Criticality Index ({tci_val:.2f}) prioritizing safety & track integrity.")
        elif job and job.tci_inputs.overdue_days > 14:
            priority_reasons.append(f"Statutory maintenance overdue by {job.tci_inputs.overdue_days} days.")
        else:
            priority_reasons.append(f"Routine preventive maintenance (TCI: {tci_val:.2f}).")
            
        consolidation = ""
        if is_shadow:
            consolidation = f"Consolidated into shadow possession with {', '.join(shadow_with)} to minimize corridor closure hours."
            
        protected_trains = [
            t.id for t in scenario.trains 
            if block_id in t.route and (t.scheduled_start >= end_time or t.scheduled_end <= start_time)
        ]
        
        explanations[job_id] = {
            "job_id": job_id,
            "tci": tci_val,
            "tci_components": tci_expl.model_dump() if tci_expl else {},
            "priority_rationale": " ".join(priority_reasons),
            "window_rationale": f"Scheduled in operational corridor gap [T+{start_time:.1f}h - T+{end_time:.1f}h].",
            "consolidation_rationale": consolidation,
            "protected_trains": protected_trains[:3],
            "active_constraints": [
                "Track possession exclusivity",
                "Department traction power isolation (PTW)" if (job and job.department.value == "OHE") else "Standard track possession clearance",
                "Resource capacity limit"
            ]
        }
        
    return explanations

def extract_shadow_groups(scheduled_jobs: List[Any]) -> List[Dict[str, Any]]:
    groups = []
    processed = set()
    for item in scheduled_jobs:
        job_id = item["job_id"] if isinstance(item, dict) else item.job_id
        is_shadow = item.get("is_shadow_block", False) if isinstance(item, dict) else item.is_shadow_block
        shadow_with = item.get("shadow_with_jobs", []) if isinstance(item, dict) else item.shadow_with_jobs
        block_id = item["block_id"] if isinstance(item, dict) else item.block_id
        start_time = item["start_time"] if isinstance(item, dict) else item.start_time
        end_time = item["end_time"] if isinstance(item, dict) else item.end_time

        if is_shadow and job_id not in processed:
            group_jobs = [job_id] + list(shadow_with)
            processed.update(group_jobs)
            groups.append({
                "group_id": f"SHADOW-{block_id}-{int(start_time)}",
                "block_id": block_id,
                "start_time": start_time,
                "end_time": end_time,
                "jobs": group_jobs
            })
    return groups

# 4. Schedule Optimization
@app.post("/optimize", response_model=OptimizedSchedule)
def optimize_schedule(req: Optional[OptimizeRequest] = None):
    """Executes MILP shadow block optimization (or heuristic fallback)."""
    config = get_config()
    try:
        if req and req.scenario:
            scenario = req.scenario
        else:
            synth_path = os.path.join(get_base_data_dir(), "synthetic")
            scenario_file = os.path.join(synth_path, "scenario.json")
            if not os.path.exists(scenario_file):
                save_synthetic_data(path=synth_path)
            ingestor = DataIngestor({"data_pipeline": {"use_local_synthetic": True, "synthetic_data_path": synth_path}})
            scenario = ingestor.load_scenario()

        scorer = TaskCriticalityScorer(config)
        job_tcis = {job.id: scorer.calculate_tci(job.tci_inputs)[0] for job in scenario.jobs}

        solver = MaintenanceSchedulerMILP(config)
        result = solver.solve(scenario, job_tcis)

        # Run KPI evaluation to enrich schedule output
        evaluator = KPIEvaluator(scenario)
        result = evaluator.evaluate(result, job_tcis)

        # Add conflicts, shadow groups, and explainability
        is_fallback = (result.get("solver") == "NON_OPTIMAL_FALLBACK")
        result["is_fallback"] = is_fallback
        result["shadow_block_groups"] = extract_shadow_groups(result.get("scheduled_jobs", []))
        result["explainability"] = build_schedule_explainability(scenario, result, job_tcis)

        # Derive operational conflicts
        temp_sched = OptimizedSchedule(**result)
        conflicts = derive_conflicts(scenario, temp_sched)
        result["conflicts"] = [c.model_dump() for c in conflicts]

        # Save schedule output safely
        data_dir = get_base_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        schedule_path = os.path.join(data_dir, "schedule_output.json")
        with open(schedule_path, "w") as f:
            json.dump(result, f, indent=4)

        return OptimizedSchedule(**result)
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete schedule optimization."
        )

# 5. KPI Evaluation
@app.post("/evaluate", response_model=KPIReport)
def evaluate_kpis(req: Optional[EvaluateRequest] = None):
    """Evaluates the optimized schedule against a manual heuristic baseline."""
    config = get_config()
    schedule_path = os.path.join(get_base_data_dir(), "schedule_output.json")
    if not os.path.exists(schedule_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found. Please run POST /optimize first."
        )

    try:
        synth_path = os.path.join(get_base_data_dir(), "synthetic")
        ingestor = DataIngestor({"data_pipeline": {"use_local_synthetic": True, "synthetic_data_path": synth_path}})
        scenario = ingestor.load_scenario()

        with open(schedule_path, "r") as f:
            schedule = json.load(f)

        scorer = TaskCriticalityScorer(config)
        job_tcis = {job.id: scorer.calculate_tci(job.tci_inputs)[0] for job in scenario.jobs}

        evaluator = KPIEvaluator(scenario)
        result = evaluator.evaluate(schedule, job_tcis)
        kpi_metrics = result["kpi_metrics"]

        # Persist KPI report
        kpi_path = os.path.join(get_base_data_dir(), "kpi_report.json")
        with open(kpi_path, "w") as f:
            json.dump(kpi_metrics, f, indent=4)

        return KPIReport(**kpi_metrics)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KPI evaluation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate schedule KPIs."
        )

# 6. Retrieve Schedule by ID
@app.get("/schedule/{schedule_id}", response_model=OptimizedSchedule)
def get_schedule(schedule_id: str):
    """Retrieves an optimized schedule by identifier (supports 'latest')."""
    if schedule_id != "latest":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule '{schedule_id}' not found."
        )

    schedule_path = os.path.join(get_base_data_dir(), "schedule_output.json")
    if not os.path.exists(schedule_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No schedule available. Please run POST /optimize first."
        )

    try:
        with open(schedule_path, "r") as f:
            data = json.load(f)
        return OptimizedSchedule(**data)
    except Exception as e:
        logger.error(f"Error reading schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read schedule data."
        )

# 7. Scenario Feed for Real Frontend Mode
@app.get("/scenario", response_model=Scenario)
def get_current_scenario():
    """Retrieves the active railway division scenario."""
    synth_path = os.path.join(get_base_data_dir(), "synthetic")
    scenario_file = os.path.join(synth_path, "scenario.json")
    if not os.path.exists(scenario_file):
        save_synthetic_data(path=synth_path)

    try:
        ingestor = DataIngestor({"data_pipeline": {"use_local_synthetic": True, "synthetic_data_path": synth_path}})
        return ingestor.load_scenario()
    except Exception as e:
        logger.error(f"Error loading scenario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load scenario data."
        )

# 8. Asset Health Telemetry for Real Frontend Mode
@app.get("/assets/health", response_model=List[AssetHealthRecord])
def get_assets_health():
    """Returns real-time track and electrical asset health telemetry."""
    try:
        synth_path = os.path.join(get_base_data_dir(), "synthetic")
        scenario_file = os.path.join(synth_path, "scenario.json")
        if not os.path.exists(scenario_file):
            save_synthetic_data(path=synth_path)
        ingestor = DataIngestor({"data_pipeline": {"use_local_synthetic": True, "synthetic_data_path": synth_path}})
        scenario = ingestor.load_scenario()
        return generate_synthetic_assets(scenario)
    except Exception as e:
        logger.error(f"Error generating asset telemetry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve asset telemetry."
        )

# 9. Control Room Event Stream for Real Frontend Mode
@app.get("/events", response_model=List[SystemEvent])
def get_system_events():
    """Returns the operational and solver event stream."""
    return generate_synthetic_events()

# 10. 3D Network Geometry Endpoint
@app.get("/network/geometry", response_model=NetworkGeometryResponse)
def get_network_3d_geometry():
    """
    Returns 3D spatial geometry for tracks, stations, signals, and OHE masts
    along the Prayagraj division corridor, plus active operational conflicts.
    """
    try:
        synth_path = os.path.join(get_base_data_dir(), "synthetic")
        scenario_file = os.path.join(synth_path, "scenario.json")
        if not os.path.exists(scenario_file):
            save_synthetic_data(path=synth_path)
        ingestor = DataIngestor({"data_pipeline": {"use_local_synthetic": True, "synthetic_data_path": synth_path}})
        scenario = ingestor.load_scenario()
        geom = generate_network_geometry(scenario)
        validate_network_geometry(geom, scenario=scenario, raise_on_error=True)
        return geom
    except GeometryValidationError as gve:
        logger.error(f"Geometry invariant validation failed: {gve}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Railway geometry failed invariant validation: {gve}"
        )
    except Exception as e:
        logger.error(f"Error generating 3D network geometry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate 3D network geometry."
        )

# 11. Planning Capabilities Endpoint
@app.get("/planning/capabilities", response_model=PlanningCapabilitiesResponse)
def get_planning_capabilities():
    """
    Returns solver availability, fallback status, model versions,
    supported horizons, and capacity metrics for 3D AI planning.
    """
    return PlanningCapabilitiesResponse(
        geometry_schema_version="1.0.0",
        solver_available=SCIP_AVAILABLE,
        solver_name="PySCIPOpt" if SCIP_AVAILABLE else "NON_OPTIMAL_FALLBACK",
        fallback_active=(not SCIP_AVAILABLE),
        model_mode="rule_based",
        model_version=TaskCriticalityScorer.MODEL_VERSION,
        supports_3d_geometry=True,
        demo_mode=True,
        supported_horizons_days=[7, 14, 28],
        routes_available=["Subedarganj - Mirzapur Mainline", "Naini Jn - Chheoki Bypass", "Prayagraj West Freight Loop"],
        max_blocks_capacity=100,
        max_trains_capacity=200
    )

if __name__ == "__main__":
    import uvicorn
    cfg = get_config()
    host = cfg.get("api", {}).get("host", "0.0.0.0")
    port = int(cfg.get("api", {}).get("port", 8000))
    uvicorn.run(app, host=host, port=port)
