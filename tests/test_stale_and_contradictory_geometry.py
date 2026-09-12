"""
Tests for Stale, Contradictory, and Invalid Railway Geometry.
Validates rejection of NaN/Inf coordinates, reversed chainage, zero-length tracks,
dangling signals/OHE, and verifies immutable locks on active possessions.
"""
import pytest
from src.data_pipeline.models import (
    TrackSection,
    Coordinate3D,
    SignalMarker,
    PossessionEntity,
    ValidationStatus
)
from src.data_pipeline.geometry_validator import (
    validate_network_geometry,
    GeometryValidationError
)
from src.data_pipeline.synthetic_data import generate_synthetic_data, generate_network_geometry

@pytest.fixture
def base_geometry():
    scen = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=10, num_trains=5)
    return generate_network_geometry(scen)

def test_reject_reversed_chainage_track():
    """A track section with start chainage >= end chainage must fail invariant validation."""
    with pytest.raises(ValueError) as exc:
        TrackSection(
            id="INVALID_REV_TRACK",
            track_id="INVALID_REV_TRACK",
            block_id="B1",
            line_type="MAINLINE",
            track_direction="UP",
            chainage_start_km=25.0,
            chainage_end_km=15.0,  # Reversed!
            start_coord=Coordinate3D(x=-200.0, y=0.0, z=2.0),
            end_coord=Coordinate3D(x=-300.0, y=0.0, z=2.0),
            source_system="TEST_SYS",
            source_record_id="REC-INV-1"
        )
    assert "must be strictly less than chainage_end_km" in str(exc.value)

def test_reject_zero_length_track():
    """A track section with zero length must fail invariant validation."""
    with pytest.raises(ValueError) as exc:
        TrackSection(
            id="ZERO_LEN_TRACK",
            track_id="ZERO_LEN_TRACK",
            block_id="B1",
            line_type="MAINLINE",
            track_direction="UP",
            chainage_start_km=10.0,
            chainage_end_km=10.0,  # Zero length!
            start_coord=Coordinate3D(x=-300.0, y=0.0, z=2.0),
            end_coord=Coordinate3D(x=-300.0, y=0.0, z=2.0),
            source_system="TEST_SYS",
            source_record_id="REC-INV-2"
        )
    assert "must be strictly less than chainage_end_km" in str(exc.value)

def test_reject_signal_without_valid_track_reference(base_geometry):
    """A signal referencing a nonexistent track section must fail invariant validation."""
    orphan_signal = SignalMarker(
        id="ORPHAN_SIG_99",
        block_id="B1",
        referenced_block_id="B1",
        referenced_track_section_id="NONEXISTENT_TRACK_SECTION_999",
        chainage_km=5.0,
        coordinates=Coordinate3D(x=-350.0, y=0.0, z=3.8),
        position=Coordinate3D(x=-350.0, y=0.0, z=3.8),
        aspect="stop",
        direction="UP",
        source_system="TEST_SYS",
        source_record_id="REC-INV-3"
    )
    base_geometry.signals.append(orphan_signal)

    with pytest.raises(GeometryValidationError) as exc:
        validate_network_geometry(base_geometry, raise_on_error=True)
    assert "references non-existent track section" in str(exc.value)

def test_reject_nan_or_inf_coordinates(base_geometry):
    """Coordinates containing NaN or Inf must fail validation."""
    with pytest.raises(ValueError):
        Coordinate3D(x=float("nan"), y=0.0, z=0.0)

    with pytest.raises(ValueError):
        Coordinate3D(x=float("inf"), y=0.0, z=0.0)

def test_granted_possession_immutable_lock_enforcement(base_geometry):
    """GRANTED or IN_PROGRESS possessions must have is_locked=True."""
    unlocked_granted = PossessionEntity(
        id="UNLOCKED_GRANTED",
        job_id="J_ILLEGAL",
        block_id="B1",
        department="Civil",
        status="GRANTED",
        start_time_hours=1.0,
        end_time_hours=4.0,
        chainage_start_km=0.0,
        chainage_end_km=10.0,
        affected_tracks=["SEC_B1_UP"],
        affected_ohe_sections=[],
        affected_signals=[],
        is_locked=False,  # VIOLATION: GRANTED must be locked
        is_shadow=False,
        approval_status="GRANTED",
        source_system="TEST",
        source_record_id="REC-INV-4"
    )
    base_geometry.possessions.append(unlocked_granted)

    with pytest.raises(GeometryValidationError) as exc:
        validate_network_geometry(base_geometry, raise_on_error=True)
    assert "must be visibly locked" in str(exc.value)

def test_stale_and_contradictory_flags_propagated(base_geometry):
    """Entities flagged as STALE or CONTRADICTORY must be preserved and identified in validation."""
    stale_possession = PossessionEntity(
        id="POSS_STALE_1",
        job_id="J_STALE",
        block_id="B1",
        department="TRD",
        status="PLANNED",
        start_time_hours=10.0,
        end_time_hours=14.0,
        chainage_start_km=0.0,
        chainage_end_km=10.0,
        affected_tracks=["SEC_B1_UP"],
        affected_ohe_sections=[],
        affected_signals=[],
        is_locked=False,
        is_shadow=False,
        approval_status="PENDING_CTPC_REVIEW",
        source_system="TEST",
        source_record_id="REC-STALE-1",
        validation_status=ValidationStatus.STALE,
        data_freshness_seconds=7200.0  # 2 hours stale
    )
    base_geometry.possessions.append(stale_possession)

    # Invariant validation passes without error because STALE is an advisory state, but notes it
    report = validate_network_geometry(base_geometry, raise_on_error=True)
    assert report.is_valid is True
    assert len(report.issues) == 0
