from fastapi.testclient import TestClient
from src.api.main import app
import json

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}

def test_generate_data():
    response = client.post("/data/generate")
    assert response.status_code == 200
    assert "successfully" in response.json()["message"]

def test_score_jobs():
    response = client.post("/score")
    assert response.status_code == 200
    data = response.json()
    assert "scored_jobs" in data
    assert len(data["scored_jobs"]) > 0

def test_optimize_schedule():
    response = client.post("/optimize")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "solver" in data

def test_evaluate_kpis():
    response = client.post("/evaluate")
    assert response.status_code == 200
    data = response.json()
    assert "bue_percent" in data
    assert "sbr_percent" in data
    assert "tci_coverage_percent" in data
