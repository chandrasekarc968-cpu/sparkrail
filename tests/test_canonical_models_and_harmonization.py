"""
Unit and Contract Tests for Canonical Domain Models and Multi-Source Harmonization.
Validates ISO-8601 validation, possession transition immutability, chainage normalization,
dead-letter logging, and RailwayMultiGraph connectivity.
"""

import os
import json
import pytest
from datetime import datetime, timezone
from src.data_pipeline.models import (
    TrackSection,
    BlockSection,
    Station,
    Interlocking,
    ElementarySection,
    MaintenanceDemand,
    TrainMovement,
    Possession,
    PossessionStatus,
    TrainPriority,
    Department,
    ApprovalRole,
    RecommendationStatus,
    validate_possession_transition,
    validate_iso8601_timestamp
)
from src.data_pipeline.harmonization import (
    normalize_chainage,
    RailwayMultiGraph,
    SpatialHarmonizationPipeline,
    HarmonizationError
)
from src.data_pipeline.adapters.cris_adapters import (
    TMSAdapter,
    TDMSAdapter,
    SMMSAdapter,
    CRISAdapterConfig
)
from src.data_pipeline.adapters.base import SnapshotRequest


def test_possession_lifecycle_immutability():
    """GRANTED and IN_PROGRESS possessions cannot transition to CANCELLED or DRAFT."""
    # Valid transition: DRAFT -> PROPOSED -> SANCTIONED -> GRANTED -> IN_PROGRESS -> COMPLETED
    validate_possession_transition(PossessionStatus.DRAFT, PossessionStatus.PROPOSED)
    validate_possession_transition(PossessionStatus.PROPOSED, PossessionStatus.SANCTIONED)
    validate_possession_transition(PossessionStatus.SANCTIONED, PossessionStatus.GRANTED)
    validate_possession_transition(PossessionStatus.GRANTED, PossessionStatus.IN_PROGRESS)
    validate_possession_transition(PossessionStatus.IN_PROGRESS, PossessionStatus.COMPLETED)

    # Invalid transitions: GRANTED cannot be cancelled or moved back
    with pytest.raises(ValueError, match="Illegal possession status transition"):
        validate_possession_transition(PossessionStatus.GRANTED, PossessionStatus.CANCELLED)

    with pytest.raises(ValueError, match="Illegal possession status transition"):
        validate_possession_transition(PossessionStatus.IN_PROGRESS, PossessionStatus.DRAFT)


def test_iso8601_timezone_validation():
    """Timestamps must be ISO-8601 compliant with timezone awareness."""
    # Valid UTC
    valid_ts = "2026-09-12T08:00:00Z"
    assert validate_iso8601_timestamp(valid_ts) == valid_ts

    valid_offset = "2026-09-12T13:30:00+05:30"
    assert validate_iso8601_timestamp(valid_offset) == valid_offset

    # Invalid timestamp
    with pytest.raises(ValueError, match="ISO-8601"):
        validate_iso8601_timestamp("12-09-2026 08:00:00")


def test_chainage_normalization():
    """Normalizes Indian Railways chainage formats (float, +, telegraph/mast)."""
    assert normalize_chainage(124.5) == 124.5
    assert normalize_chainage("124.5") == 124.5
    assert normalize_chainage("124+500") == 124.5
    assert normalize_chainage("124+050") == 124.05
    assert normalize_chainage("124/18") == 124.9  # Mast 18 (~50m each)
    assert normalize_chainage({"km": 124, "m": 500}) == 124.5


def test_spatial_harmonization_and_multigraph():
    """Validates linear referencing and NetworkX directed track graph with electrical isolation reachability."""
    blocks = [
        BlockSection(
            id="TS1",
            block_id="TS1",
            start_station="SFG",
            end_station="NYN",
            chainage_start_km=0.0,
            chainage_end_km=10.0,
            line_id="DN",
            speed_limit_kmh=110.0,
            electrification_type="25KV_AC"
        ),
        BlockSection(
            id="TS2",
            block_id="TS2",
            start_station="NYN",
            end_station="UND",
            chainage_start_km=10.0,
            chainage_end_km=25.0,
            line_id="DN",
            speed_limit_kmh=110.0,
            electrification_type="25KV_AC"
        ),
        BlockSection(
            id="TS3",
            block_id="TS3",
            start_station="UND",
            end_station="MZP",
            chainage_start_km=25.0,
            chainage_end_km=40.0,
            line_id="DN",
            speed_limit_kmh=110.0,
            electrification_type="25KV_AC"
        )
    ]

    pipeline = SpatialHarmonizationPipeline(blocks)

    # Test TMS chainage mapping
    matched_block, prov = pipeline.map_tms_chainage_to_block(15.5, "TMS_FLAW_99")
    assert matched_block is not None
    assert matched_block.block_id == "TS2"
    assert prov.confidence == 1.0

    # Test out of bounds rejection
    oob_block, oob_prov = pipeline.map_tms_chainage_to_block(55.0, "TMS_FLAW_OOB")
    assert oob_block is None
    assert oob_prov.confidence == 0.0

    # Test multigraph construction
    es = ElementarySection(
        section_id="ES2",
        name="Substation Feeding Zone 2",
        feeding_post_id="FP_NYN",
        track_section_ids=["TS2"],
        catenary_voltage_kv=25.0,
        isolator_switch_ids=["SW1", "SW2"]
    )
    graph = pipeline.build_multigraph(electrical_sections=[es], signals=[])
    
    assert graph.find_shortest_path("TS1", "TS3") == ["TS1", "TS2", "TS3"]
    reach = graph.get_affected_blocks_for_isolation("ES2")
    assert "TS2" in reach
    assert "TS1" not in reach
    assert "TS3" not in reach


def test_dead_letter_and_stale_data_rejection(tmp_path):
    """CRIS adapter logs to dead-letter queue and rejects live fetching without authorization."""
    dead_letter_file = str(tmp_path / "dead_letter.jsonl")
    cfg = CRISAdapterConfig(
        source_name="TMS",
        mock_mode=False,
        is_live_enabled=False,
        dead_letter_file=dead_letter_file
    )
    adapter = TMSAdapter(cfg)

    # In live-disabled mode without mock authorization, fetch_snapshot must raise RuntimeError
    req = SnapshotRequest(division_code="PRYJ", mock_mode=False)
    with pytest.raises(RuntimeError, match="Live CRIS integration disabled"):
        adapter.fetch_snapshot(req)

    # Verify dead-letter logging
    adapter._record_dead_letter({
        "event_id": "STALE-001",
        "reason": "Timestamp out of sequence"
    })
    assert os.path.exists(dead_letter_file)
    with open(dead_letter_file, "r") as f:
        line = f.readline()
        record = json.loads(line)
        assert record["source"] == "TMS"
        assert record["payload"]["event_id"] == "STALE-001"
