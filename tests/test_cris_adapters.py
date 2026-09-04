"""
Tests for CRIS Source Adapters and Spatial Harmonization:
TMS, TDMS, SMMS, COA, RTIS, BDMS adapters, health checks, mTLS validation,
live mode gates, and linear referencing multigraph creation.
"""

import pytest
from src.data_pipeline.adapters.base import SourceHealth, SnapshotRequest
from src.data_pipeline.adapters.local_adapters import SyntheticAdapter, FixtureAdapter, ReplayAdapter
from src.data_pipeline.adapters.cris_adapters import (
    TMSAdapter,
    TDMSAdapter,
    SMMSAdapter,
    COAAdapter,
    RTISAdapter,
    BDMSAdapter,
    CRISAdapterConfig
)
from src.data_pipeline.harmonization import SpatialHarmonizationPipeline, RailwayMultiGraph, HarmonizationError
from src.data_pipeline.models import BlockSection, TrainMovement, TrainPriority


class TestLocalAdapters:
    def test_synthetic_adapter_contract(self):
        adapter = SyntheticAdapter(seed=42)
        health = adapter.health()
        assert health.is_connected
        assert health.status == "HEALTHY"
        assert health.source_name == "SYNTHETIC_GENERATOR"

        req = SnapshotRequest(division_code="PRYJ")
        snapshot = adapter.fetch_snapshot(req)
        assert snapshot.division_code == "PRYJ"
        assert snapshot.records_count > 0

    def test_replay_adapter(self):
        adapter = ReplayAdapter(event_log=[{"event_id": "EVT-01", "type": "COA_UPDATE"}])
        health = adapter.health()
        assert health.is_connected
        assert health.status == "HEALTHY"
        assert "REPLAY" in health.source_name


class TestProductionCRISAdapters:
    def test_cris_adapter_config_validation(self):
        cfg = CRISAdapterConfig(
            source_name="TMS",
            base_url="https://cris.internal.indianrailways.gov.in/tms/api/v1",
            timeout_seconds=5.0,
            is_live_enabled=False
        )
        assert cfg.source_name == "TMS"
        assert not cfg.is_live_enabled

    def test_tms_adapter_live_mode_gate(self):
        # In disabled live mode or when mock credentials are missing, health must report correctly
        cfg = CRISAdapterConfig(
            source_name="TMS",
            base_url="https://cris.test/tms",
            is_live_enabled=False
        )
        tms = TMSAdapter(cfg)
        health = tms.health()
        assert health.source_name == "TMS"
        # Since live mode is False, it reports disabled/unconnected, never silently claiming live
        assert not health.is_connected
        assert health.status == "DEGRADED"

    def test_bdms_adapter_proposal_payload_contract(self):
        cfg = CRISAdapterConfig(
            source_name="BDMS",
            base_url="https://cris.test/bdms",
            is_live_enabled=False
        )
        bdms = BDMSAdapter(cfg)
        # Outbound calls are disabled by default
        result = bdms.submit_advisory_proposal(
            proposal={
                "optimization_run_id": "TEST-PROP-01",
                "division_code": "PRYJ"
            },
            idempotency_key="IDEMP-BDMS-TEST-01"
        )
        assert result.get("status") == "ACCEPTED_FOR_ADVISORY_REVIEW"
        assert result.get("is_dry_run") is True


class TestSpatialHarmonization:
    def test_chainage_to_block_mapping(self):
        blocks = [
            BlockSection(id="B1", block_id="B1", start_station="SFG", end_station="PRYJ", chainage_start_km=0.0, chainage_end_km=10.0),
            BlockSection(id="B2", block_id="B2", start_station="PRYJ", end_station="NYN", chainage_start_km=10.0, chainage_end_km=20.0),
            BlockSection(id="B3", block_id="B3", start_station="NYN", end_station="KCN", chainage_start_km=20.0, chainage_end_km=30.0)
        ]
        harmonizer = SpatialHarmonizationPipeline(blocks)

        # Test point mapping
        block, prov = harmonizer.map_tms_chainage_to_block(15.4, source_id="AST-TRK-01")
        assert block is not None
        assert block.block_id == "B2"
        assert prov.confidence == 1.0
        assert not prov.ambiguity_flag

        # Test out-of-range chainage safely handled
        out_block, out_prov = harmonizer.map_tms_chainage_to_block(999.0, source_id="AST-TRK-99")
        assert out_block is None
        assert out_prov.ambiguity_flag is True

    def test_railway_multigraph_creation(self):
        blocks = [
            BlockSection(id="B1", block_id="B1", start_station="SFG", end_station="PRYJ", chainage_start_km=0.0, chainage_end_km=10.0),
            BlockSection(id="B2", block_id="B2", start_station="PRYJ", end_station="NYN", chainage_start_km=10.0, chainage_end_km=20.0)
        ]
        harmonizer = SpatialHarmonizationPipeline(blocks)
        graph = harmonizer.build_multigraph(electrical_sections=[], signals=[])

        assert graph is not None
        assert "B1" in graph.blocks
        assert "B2" in graph.blocks
        # Physical adjacency between B1 and B2
        assert "B2" in graph.physical_edges["B1"]
        assert "B1" in graph.physical_edges["B2"]
