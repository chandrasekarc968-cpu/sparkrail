"""
Tests for Canonical Geometry Contract (v1.0.0)
Validates entity schemas, coordinate transformations, CRS declarations, provenance,
and determinism.
"""
import pytest
from starlette.testclient import TestClient

from src.api.main import app
from src.data_pipeline.models import (
    NetworkGeometryResponse,
    ValidationStatus,
    CoordinateSystemContract
)
from src.data_pipeline.coordinates import CoordinateTransformer, CoordinateTransformError
from src.data_pipeline.synthetic_data import generate_synthetic_data, generate_network_geometry

@pytest.fixture
def client():
    return TestClient(app)

def test_canonical_geometry_contract_schema(client):
    """Network geometry v1 endpoint must return schema 1.0.0 with all canonical collections."""
    res = client.get("/network/geometry/v1")
    assert res.status_code == 200
    data = res.json()
    assert data["geometry_schema_version"] == "1.0.0"
    assert "coordinate_system" in data
    assert data["coordinate_system"]["name"] == "LOCAL_CORRIDOR"
    assert data["coordinate_system"]["transform_version"] == "1.0.0"

    # Verify canonical entity collections
    for collection in [
        "track_sections", "track_centerlines", "crossovers", "interlockings",
        "track_circuits", "elementary_sections", "feeding_posts", "isolator_switches",
        "possessions", "shadow_bundles", "speed_restrictions"
    ]:
        assert collection in data, f"Missing canonical collection: {collection}"
        assert len(data[collection]) > 0, f"Collection {collection} is empty"

def test_entity_provenance_completeness(client):
    """Every entity must include complete source provenance and validation metadata."""
    res = client.get("/network/geometry/v1")
    data = res.json()

    sample_entities = [
        data["track_sections"][0],
        data["crossovers"][0],
        data["interlockings"][0],
        data["track_circuits"][0],
        data["elementary_sections"][0],
        data["feeding_posts"][0],
        data["isolator_switches"][0],
        data["signals"][0],
        data["ohe_masts"][0],
        data["possessions"][0],
        data["speed_restrictions"][0]
    ]

    for entity in sample_entities:
        assert "id" in entity and entity["id"]
        assert "source_system" in entity and entity["source_system"]
        assert "source_record_id" in entity and entity["source_record_id"]
        assert "schema_version" in entity and entity["schema_version"] == "1.0.0"
        assert "coordinate_reference_system" in entity
        assert "source_timestamp" in entity and entity["source_timestamp"]
        assert "ingestion_timestamp" in entity and entity["ingestion_timestamp"]
        assert "confidence" in entity and 0.0 <= entity["confidence"] <= 1.0
        assert "validation_status" in entity
        assert entity["validation_status"] in [
            "VALIDATED", "SYNTHETIC", "STALE", "LOW_CONFIDENCE", "INVALID", "CONTRADICTORY", "UNAVAILABLE"
        ]

def test_coordinate_transformer_roundtrip_and_crs():
    """CoordinateTransformer must support LOCAL_CORRIDOR and EPSG:4326 with roundtrip consistency."""
    transformer = CoordinateTransformer()

    # Contract inspection
    local_cs = transformer.get_contract("LOCAL_CORRIDOR")
    assert local_cs.name == "LOCAL_CORRIDOR"
    assert local_cs.crs == "LOCAL_CORRIDOR"
    assert local_cs.units == "meters"
    assert local_cs.is_synthetic is True

    wgs_cs = transformer.get_contract("EPSG:4326")
    assert wgs_cs.crs == "EPSG:4326"
    assert wgs_cs.units == "degrees"

    # Invalid CRS rejected
    with pytest.raises(CoordinateTransformError):
        transformer.get_contract("UNKNOWN_CRS_XYZ")

    # Chainage to local corridor roundtrip
    test_chainages = [0.0, 15.5, 30.0, 48.2, 79.9]
    for ch in test_chainages:
        expected_x = -400.0 + (ch / 80.0) * 800.0
        up_pt = transformer.chainage_to_local_corridor(ch, track_direction="UP")
        dn_pt = transformer.chainage_to_local_corridor(ch, track_direction="DOWN")
        assert up_pt.x == pytest.approx(expected_x, abs=0.1)
        assert dn_pt.x == pytest.approx(expected_x, abs=0.1)
        # UP and DOWN lines maintain 4.4m lateral separation (2.2m UP, -2.2m DOWN)
        assert (up_pt.z - dn_pt.z) == pytest.approx(4.4, abs=0.01)

        # Invert back to chainage
        recovered_ch = transformer.local_corridor_to_chainage(up_pt)
        assert recovered_ch == pytest.approx(ch, abs=0.001)

    # Geographic lat/lon interpolation
    sfg_lat, sfg_lon, sfg_elev = transformer.chainage_to_geographic(0.0)
    assert sfg_lat == pytest.approx(25.4412, abs=0.001)
    assert sfg_lon == pytest.approx(81.7963, abs=0.001)

    mzp_lat, mzp_lon, mzp_elev = transformer.chainage_to_geographic(80.0)
    assert mzp_lat == pytest.approx(25.1480, abs=0.001)
    assert mzp_lon == pytest.approx(82.5680, abs=0.001)

    recovered_geo_ch, dist_m = transformer.geographic_to_chainage(sfg_lat, sfg_lon)
    assert recovered_geo_ch == pytest.approx(0.0, abs=0.1)

def test_deterministic_geometry_generation():
    """Generating network geometry twice with same scenario produces identical geometry."""
    scen1 = generate_synthetic_data(seed=999, num_blocks=8, num_jobs=10, num_trains=5)
    geom1 = generate_network_geometry(scen1)

    scen2 = generate_synthetic_data(seed=999, num_blocks=8, num_jobs=10, num_trains=5)
    geom2 = generate_network_geometry(scen2)

    assert len(geom1.track_sections) == len(geom2.track_sections)
    assert len(geom1.crossovers) == len(geom2.crossovers)
    assert len(geom1.signals) == len(geom2.signals)
    assert len(geom1.ohe_masts) == len(geom2.ohe_masts)
    assert geom1.track_sections[0].start_coord.model_dump() == geom2.track_sections[0].start_coord.model_dump()
