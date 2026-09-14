import pytest
from fastapi.testclient import TestClient
from src.api.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_what_if_scenario_api(client):
    payload = {
        "scenario_id": "latest",
        "modifications": [
            {"job_id": "J1", "extend_duration_hours": 1.0}
        ]
    }
    resp = client.post("/api/v1/simulation/scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "delta_report" in data
    assert "narrative_summary_en" in data["delta_report"]
    assert "narrative_summary_hi" in data["delta_report"]

def test_evaluate_shift_api(client):
    payload = {
        "job_id": "J1",
        "shift_minutes": 15.0
    }
    resp = client.post("/api/v1/simulation/evaluate-shift", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "J1"
    assert "bilingual_advisory" in data
    assert "en" in data["bilingual_advisory"]
    assert "hi" in data["bilingual_advisory"]

def test_xai_briefing_api(client):
    resp = client.get("/api/v1/simulation/xai-briefing")
    assert resp.status_code == 200
    data = resp.json()
    assert "en" in data
    assert "hi" in data
    assert "SparkRail" in data["en"] or "स्पार्क-रेल" in data["hi"]
