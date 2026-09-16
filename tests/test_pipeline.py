"""Tests for the ingestion / lakehouse / serving / digital-twin pipeline modules."""
import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# --------------------------------------------------------------------------- #
# Streaming ingestion
# --------------------------------------------------------------------------- #
def _write_log(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def test_local_replay_and_dedup():
    from src.data_pipeline.streaming import (
        LocalEventReplaySource, StreamingIngestionHub,
    )
    with tempfile.TemporaryDirectory() as td:
        log = os.path.join(td, "events.jsonl")
        _write_log(log, [
            {"kind": "train_movement", "train_id": "T1", "chainage_km": 3.0, "ts_ms": 1},
            {"kind": "train_movement", "train_id": "T1", "chainage_km": 4.0, "ts_ms": 2},
            {"kind": "asset_telemetry", "asset_id": "A1", "block_id": "B2", "ts_ms": 3},
        ])
        hub = StreamingIngestionHub([LocalEventReplaySource(log)])
        hub.connect()
        merged = hub.consume()
        # T1 should be de-duplicated (latest wins) -> 1 train_movement + 1 telemetry
        assert len(merged["train_movement"]) == 1
        assert merged["train_movement"][0]["chainage_km"] == 4.0
        assert len(merged["asset_telemetry"]) == 1


def test_kafka_source_imports_without_kafka():
    from src.data_pipeline.streaming import KafkaEventSource
    # Constructing and connecting must not raise even if kafka-python is absent.
    src = KafkaEventSource("localhost:9092", ["train_movements"])
    src.connect()  # logs a warning, stays inert
    assert src.events() is None or list(src.events()) == []


# --------------------------------------------------------------------------- #
# Lakehouse transforms + persistence
# --------------------------------------------------------------------------- #
def test_chainage_to_block_join():
    from src.data_pipeline.lakehouse import chainage_to_block_join
    blocks = [
        {"block_id": "B1", "chainage_start_km": 0.0, "chainage_end_km": 5.0},
        {"block_id": "B2", "chainage_start_km": 5.0, "chainage_end_km": 10.0},
    ]
    events = [{"chainage_km": 3.0}, {"chainage_km": 7.5}]
    out = chainage_to_block_join(events, blocks)
    assert out[0]["block_id"] == "B1"
    assert out[1]["block_id"] == "B2"


def test_rolling_degradation_average():
    from src.data_pipeline.lakehouse import rolling_degradation_average
    series = [{"ts_ms": i, "degradation_velocity": float(i)} for i in range(10)]
    out = rolling_degradation_average(series, window=3)
    assert "rolling_degradation_velocity" in out[-1]
    # last window of size 3 over [7,8,9] -> mean 8.0
    assert out[-1]["rolling_degradation_velocity"] == 8.0


def test_lakehouse_write_read_roundtrip():
    from src.data_pipeline.lakehouse import SparkStreamProcessor
    with tempfile.TemporaryDirectory() as td:
        proc = SparkStreamProcessor(warehouse_root=os.path.join(td, "lh"))
        recs = [{"id": "r1", "v": 1}, {"id": "r2", "v": 2}]
        path = proc.write("metrics", recs)
        assert os.path.exists(path)
        back = proc.read("metrics")
        assert {r["id"] for r in back} == {"r1", "r2"}


# --------------------------------------------------------------------------- #
# PostGIS serving (SQLite fallback)
# --------------------------------------------------------------------------- #
def test_geostore_sqlite_fallback():
    from src.serving.postgis_store import GeoStore, BlockRecord
    with tempfile.TemporaryDirectory() as td:
        store = GeoStore(f"sqlite:///{td}/serving.db")
        store.upsert_blocks([
            BlockRecord("B1", 0.0, 5.0, centroid_lat=25.0, centroid_lon=80.0),
            BlockRecord("B2", 5.0, 10.0, centroid_lat=25.1, centroid_lon=80.1),
        ])
        near = store.blocks_within_radius(25.0, 80.0, 20.0)
        assert {b.block_id for b in near} == {"B1", "B2"}
        by_ch = store.block_by_chainage(3.0)
        assert by_ch.block_id == "B1"
        store.close()


# --------------------------------------------------------------------------- #
# SUMO digital twin
# --------------------------------------------------------------------------- #
def test_sumo_twin_step_and_reward():
    from src.simulation.sumo_interface import SUMODigitalTwin, ACT_SHIFT
    blocks = [{"id": f"B{i}", "chainage_start_km": i * 2.0, "chainage_end_km": (i + 1) * 2.0} for i in range(6)]
    trains = [{"id": "T1", "route": ["B0", "B1", "B2", "B3"], "speed_kmh": 40.0,
               "category": "express", "scheduled_start": 0.0, "scheduled_end": 12.0}]
    twin = SUMODigitalTwin(blocks, trains, horizon_hours=12.0)
    twin.apply_schedule([{"block_id": "B1", "start_time": 1.0, "end_time": 3.0}])
    obs = twin.reset()
    assert len(obs) == 6 + 3  # 6 block flags + 3 train features
    total_reward = 0.0
    done = False
    while not done:
        ns, r, done, info = twin.step(ACT_SHIFT)
        total_reward += r
    assert isinstance(total_reward, float)
