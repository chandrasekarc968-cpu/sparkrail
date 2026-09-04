import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.data_pipeline.synthetic_data import (
    generate_synthetic_data,
    generate_network_geometry,
    derive_conflicts
)
from src.data_pipeline.models import (
    Scenario,
    ConflictType,
    NetworkGeometryResponse,
    PlanningCapabilitiesResponse
)

@pytest.fixture
def client():
    return TestClient(app)

def test_generate_network_geometry():
    scenario = generate_synthetic_data(seed=42, num_blocks=8)
    geom = generate_network_geometry(scenario)
    
    assert isinstance(geom, NetworkGeometryResponse)
    assert geom.is_synthetic is True
    assert geom.division == "Prayagraj (PRYJ)"
    assert len(geom.nodes) >= 8
    assert len(geom.tracks) == 8
    assert len(geom.signals) == 16  # 2 signals per block
    assert len(geom.ohe_masts) == 24  # 3 masts per block
    
    # Check 3D coordinate continuity
    first_track = geom.tracks[0]
    last_track = geom.tracks[-1]
    assert first_track.start_coord.x == -400.0
    assert last_track.end_coord.x == 400.0
    assert len(first_track.path_points) == 6
    assert len(first_track.elevation_profile) == 6

def test_derive_conflicts_rule_engine():
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=20, num_trains=10)
    conflicts = derive_conflicts(scenario)
    
    assert len(conflicts) > 0
    types = [c.conflict_type for c in conflicts]
    
    # Must identify fixed blocks and overdue or safety risks
    assert ConflictType.FIXED_BLOCK_COLLISION in types
    assert ConflictType.PREMIUM_TRAIN in types
    
    # Verify conflict item schema
    for c in conflicts:
        assert c.id.startswith("CONF-")
        assert c.severity in ["CRITICAL", "MAJOR", "WARNING", "INFO"]
        assert len(c.title) > 0
        assert len(c.description) > 0
        assert len(c.suggested_resolution) > 0

def test_api_network_geometry_endpoint(client):
    client.post("/data/generate", json={"seed": 42, "num_blocks": 8, "num_jobs": 20, "num_trains": 10})
    res = client.get("/network/geometry")
    assert res.status_code == 200
    data = res.json()
    assert "division" in data
    assert "tracks" in data
    assert "nodes" in data
    assert len(data["tracks"]) == 8
    assert data["tracks"][0]["block_id"] == "B1"

def test_api_planning_capabilities_endpoint(client):
    res = client.get("/planning/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert "solver_name" in data
    assert "solver_available" in data
    assert "supports_3d_geometry" in data
    assert data["supports_3d_geometry"] is True
    assert data["demo_mode"] is True
    assert 7 in data["supported_horizons_days"]

def test_api_optimize_enrichment(client):
    res = client.post("/optimize", json={"freeze_week1": False})
    assert res.status_code == 200
    data = res.json()
    assert "conflicts" in data
    assert "shadow_block_groups" in data
    assert "explainability" in data
    assert "is_fallback" in data
    
    # Check explainability format for scheduled jobs
    if data["scheduled_jobs"]:
        first_job_id = data["scheduled_jobs"][0]["job_id"]
        assert first_job_id in data["explainability"]
        expl = data["explainability"][first_job_id]
        assert "tci" in expl
        assert "priority_rationale" in expl
        assert "window_rationale" in expl
        assert "protected_trains" in expl
