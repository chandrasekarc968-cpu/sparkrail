"""
Tests for Canonical Railway Topology Service.
Validates multigraph adjacency, routing, TSL corridor resolution,
OHE/Signalling zones, and spatial queries.
"""
import pytest
from starlette.testclient import TestClient

from src.api.main import app
from src.data_pipeline.models import PossessionEntity, Train, ValidationStatus
from src.data_pipeline.synthetic_data import generate_synthetic_data, generate_network_geometry
from src.data_pipeline.topology import CanonicalRailwayTopology

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def topology():
    scen = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=10, num_trains=5)
    geom = generate_network_geometry(scen)
    return CanonicalRailwayTopology(geom)

def test_topology_multigraph_connectivity(topology):
    """Topology multigraph must be fully connected across the 8 blocks in both UP and DOWN directions."""
    val = topology.validate_topology_connectivity()
    assert val["is_valid"] is True
    assert len(val["isolated_sections"]) == 0
    assert val["total_sections"] >= 16  # 8 UP + 8 DOWN sections minimum

def test_topology_track_by_chainage(topology):
    """Querying track section by chainage must locate the correct section and direction."""
    # Km 15.0 is in Block B2 (10-20 km)
    up_sec = topology.get_track_section_by_chainage(15.0, direction="UP")
    assert up_sec is not None
    assert up_sec.block_id == "B2"
    assert up_sec.track_direction == "UP"
    assert up_sec.chainage_start_km <= 15.0 <= up_sec.chainage_end_km

    dn_sec = topology.get_track_section_by_chainage(15.0, direction="DOWN")
    assert dn_sec is not None
    assert dn_sec.block_id == "B2"
    assert dn_sec.track_direction == "DOWN"

def test_topology_nearest_station(topology):
    """Nearest station query must return the geographically closest station and distance."""
    # Near Subedarganj (Km 0)
    stn, dist = topology.get_nearest_station(1.5)
    assert stn.code == "SFG"
    assert dist == pytest.approx(1.5, abs=0.1)

    # Near Naini Junction (Km 20)
    stn, dist = topology.get_nearest_station(19.8)
    assert stn.code == "NYN"
    assert dist == pytest.approx(0.2, abs=0.1)

def test_topology_adjacent_sections(topology):
    """Adjacent sections query must return contiguous block connections."""
    adj_up = topology.get_adjacent_sections("SEC_B2_UP", direction="UP")
    assert "SEC_B3_UP" in adj_up

    adj_dn = topology.get_adjacent_sections("SEC_B2_DOWN", direction="DOWN")
    assert "SEC_B1_DOWN" in adj_dn

def test_topology_route_preserves_direction(topology):
    """Finding route from km 5 to km 35 on UP line must return ordered sequence of sections."""
    route = topology.find_route(5.0, 35.0, direction="UP")
    assert len(route) >= 4
    block_ids = [s.block_id for s in route]
    assert block_ids == ["B1", "B2", "B3", "B4"]

def test_topology_affected_ohe_and_signalling(topology):
    """Querying affected infrastructure for block 2 must return elementary sections and interlocking."""
    affected_ohe = topology.get_affected_ohe_sections(["SEC_B2_UP"])
    assert len(affected_ohe) > 0
    assert any("B2" in es.associated_tracks[0] for es in affected_ohe)

    affected_ixl = topology.get_affected_signalling_zones(["SEC_B2_UP"])
    assert len(affected_ixl) > 0
    assert any("PRYJ" in ixl.station_code or "NYN" in ixl.station_code for ixl in affected_ixl)

def test_topology_valid_tsl_corridor(topology):
    """Temporary Single Line (TSL) calculation on opposite line when one line is blocked."""
    tsl = topology.get_valid_tsl_corridor("SEC_B2_DOWN", start_km=10.0, end_km=20.0)
    assert tsl["is_valid_tsl"] is True
    assert tsl["healthy_track_id"] == "SEC_B2_UP"
    assert tsl["single_line_speed_limit_kmh"] == 40.0

def test_topology_api_endpoints(client):
    """GET /network/topology and POST /network/topology/query endpoint integration."""
    res = client.get("/network/topology")
    assert res.status_code == 200
    top = res.json()
    assert top["schema_version"] == "1.0.0"
    assert top["validation"]["is_valid"] is True
    assert len(top["stations"]) >= 5

    # Test POST query: track_by_chainage
    q_res = client.post("/network/topology/query", json={
        "action": "track_by_chainage",
        "chainage_km": 25.0,
        "direction": "UP"
    })
    assert q_res.status_code == 200
    assert q_res.json()["result"]["block_id"] == "B3"

    # Test POST query: nearest_station
    q_stn = client.post("/network/topology/query", json={
        "action": "nearest_station",
        "chainage_km": 0.5
    })
    assert q_stn.status_code == 200
    assert q_stn.json()["station"]["code"] == "SFG"
