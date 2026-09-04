import math
import copy
import pytest

from src.data_pipeline.models import (
    NetworkGeometryResponse,
    GeometryTrack,
    StationNode,
    SignalMarker,
    OHEMast,
    Coordinate3D,
    Scenario
)
from src.data_pipeline.synthetic_data import generate_synthetic_data, generate_network_geometry
from src.data_pipeline.geometry_validator import (
    validate_network_geometry,
    GeometryValidationResult,
    GeometryValidationError
)

@pytest.fixture
def valid_scenario():
    return generate_synthetic_data(seed=26027, num_blocks=8, num_jobs=20, num_trains=10)

@pytest.fixture
def valid_geometry(valid_scenario):
    return generate_network_geometry(valid_scenario)

def test_valid_geometry_passes(valid_geometry, valid_scenario):
    """Verifies that generated canonical geometry satisfies all physical and spatial invariants."""
    res = validate_network_geometry(valid_geometry, scenario=valid_scenario)
    assert res.is_valid is True
    assert len(res.issues) == 0
    assert res.total_tracks_checked == len(valid_geometry.tracks)
    assert res.total_nodes_checked == len(valid_geometry.nodes)

def test_reject_duplicate_node_ids(valid_geometry):
    """Rejects geometry containing duplicate station or junction node IDs."""
    geom = copy.deepcopy(valid_geometry)
    geom.nodes.append(copy.deepcopy(geom.nodes[0]))
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("Duplicate node ID" in issue for issue in res.issues)

def test_reject_duplicate_track_block_ids(valid_geometry):
    """Rejects geometry containing duplicate track blocks."""
    geom = copy.deepcopy(valid_geometry)
    dup_track = copy.deepcopy(geom.tracks[0])
    geom.tracks.append(dup_track)
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("Duplicate track segment" in issue for issue in res.issues)

def test_reject_fewer_than_two_path_points(valid_geometry):
    """Rejects tracks with fewer than two path points."""
    geom = copy.deepcopy(valid_geometry)
    # Bypass pydantic validation directly in test to test validator
    geom.tracks[0].path_points = [geom.tracks[0].start_coord]
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("path_points has 1 points. Minimum required is 2." in issue for issue in res.issues)

def test_reject_reversed_or_zero_chainage(valid_geometry):
    """Rejects tracks with reversed chainage (start >= end)."""
    geom = copy.deepcopy(valid_geometry)
    geom.tracks[0].chainage_start = 50.0
    geom.tracks[0].chainage_end = 20.0
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("reversed or zero-length chainage" in issue for issue in res.issues)

def test_reject_negative_length(valid_geometry):
    """Rejects tracks with negative or zero length."""
    geom = copy.deepcopy(valid_geometry)
    geom.tracks[0].length_km = -5.0
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("non-positive or non-finite length_km" in issue for issue in res.issues)

def test_reject_unknown_scenario_block_reference(valid_geometry, valid_scenario):
    """Rejects tracks or signals referencing block IDs absent from scenario."""
    geom = copy.deepcopy(valid_geometry)
    geom.tracks[0].block_id = "B_NON_EXISTENT"
    res = validate_network_geometry(geom, scenario=valid_scenario)
    assert res.is_valid is False
    assert any("references unknown block_id" in issue for issue in res.issues)

def test_reject_out_of_bounds_coordinates(valid_geometry):
    """Rejects coordinates outside configured physical bounding box."""
    geom = copy.deepcopy(valid_geometry)
    geom.nodes[0].coordinates = Coordinate3D(x=5000.0, y=0.0, z=0.0)
    geom.nodes[0].position = geom.nodes[0].coordinates
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("exceeds maximum bound" in issue for issue in res.issues)

def test_raise_on_error_flag(valid_geometry):
    """Ensures raise_on_error=True raises GeometryValidationError."""
    geom = copy.deepcopy(valid_geometry)
    geom.tracks[0].length_km = -1.0
    with pytest.raises(GeometryValidationError) as exc_info:
        validate_network_geometry(geom, raise_on_error=True)
    assert "non-positive or non-finite length_km" in str(exc_info.value)

def test_reject_incompatible_schema_version(valid_geometry):
    """Rejects geometry with missing or incompatible major schema version."""
    geom = copy.deepcopy(valid_geometry)
    geom.geometry_schema_version = "2.0.0"
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("Incompatible geometry_schema_version '2.0.0'" in issue for issue in res.issues)

def test_reject_invalid_coordinate_system_contract(valid_geometry):
    """Rejects geometry violating local corridor coordinate system contract."""
    geom = copy.deepcopy(valid_geometry)
    geom.coordinate_system.crs = "EPSG:4326"  # Forbidden GPS coordinate reference system
    geom.coordinate_system.units = "feet"     # Forbidden non-meter units
    res = validate_network_geometry(geom)
    assert res.is_valid is False
    assert any("coordinate_system.crs must be 'LOCAL_CORRIDOR'" in issue for issue in res.issues)
    assert any("coordinate_system.units must be 'meters'" in issue for issue in res.issues)

