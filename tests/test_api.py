import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_check_payload():
    """Health check returns status, version, solver info, data mode, and commit SHA."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert "solver_available" in data
    assert "solver_name" in data
    assert data["data_mode"] == "local_synthetic"
    assert "commit_sha" in data
    assert "x-request-id" in response.headers

def test_generate_data_endpoint():
    """Data generation generates scenario and returns summary."""
    response = client.post("/data/generate", json={"seed": 99, "num_blocks": 6, "num_jobs": 15, "num_trains": 8})
    assert response.status_code == 200
    data = response.json()
    assert data["seed"] == 99
    assert data["blocks_count"] == 6
    assert data["jobs_count"] == 15
    assert data["trains_count"] == 8
    assert "successfully" in data["message"]

def test_score_jobs_endpoint():
    """Score endpoint returns scored jobs with component breakdown and model metadata."""
    response = client.post("/score")
    assert response.status_code == 200
    data = response.json()
    assert "scored_jobs" in data
    assert len(data["scored_jobs"]) > 0
    first_job = data["scored_jobs"][0]
    assert "job_id" in first_job
    assert "tci" in first_job
    assert "explanation" in first_job
    assert "safety_component" in first_job["explanation"]
    assert data["model_mode"] == "rule_based"
    assert data["model_version"] == "1.0.0"

def test_optimize_and_get_schedule():
    """Optimize returns full schedule and schedule can be retrieved via GET /schedule/latest."""
    opt_resp = client.post("/optimize", json={"seed": 42})
    assert opt_resp.status_code == 200
    opt_data = opt_resp.json()
    assert opt_data["status"] in ("optimal", "feasible", "heuristic_feasible")
    assert len(opt_data["scheduled_jobs"]) > 0
    assert "total_closure_time" in opt_data
    assert "train_delays" in opt_data
    assert "objective_components" in opt_data

    # Retrieve via GET /schedule/latest
    get_resp = client.get("/schedule/latest")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["status"] == opt_data["status"]
    assert len(get_data["scheduled_jobs"]) == len(opt_data["scheduled_jobs"])

def test_evaluate_kpis_endpoint():
    """Evaluate endpoint returns KPI metrics with BUE, SBR, PII."""
    response = client.post("/evaluate")
    assert response.status_code == 200
    data = response.json()
    assert "bue_percent" in data
    assert "sbr_percent" in data
    assert "pii_delays" in data
    assert "total_closure_hours" in data
    assert "consolidated_blocks" in data

def test_auxiliary_endpoints_for_frontend():
    """Endpoints for frontend real mode: /scenario, /assets/health, /events."""
    # Scenario
    scen_resp = client.get("/scenario")
    assert scen_resp.status_code == 200
    assert "blocks" in scen_resp.json()

    # Asset health
    asset_resp = client.get("/assets/health")
    assert asset_resp.status_code == 200
    assert isinstance(asset_resp.json(), list)
    assert len(asset_resp.json()) > 0

    # Events
    evt_resp = client.get("/events")
    assert evt_resp.status_code == 200
    assert isinstance(evt_resp.json(), list)
    assert len(evt_resp.json()) > 0

def test_schedule_not_found():
    """Requesting non-existent schedule returns 404."""
    response = client.get("/schedule/non_existent_schedule_id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_validation_error_handling():
    """Malformed request payload returns 422 with sanitized error envelope."""
    response = client.post("/data/generate", json={"num_blocks": -5}) # Invalid bounds
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    # Ensure no python internal traces leaked
    assert "Traceback" not in str(data)

def test_request_id_propagation():
    """Supplied X-Request-ID is preserved in response headers."""
    custom_id = "test-req-id-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
