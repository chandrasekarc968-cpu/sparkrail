import hashlib
import json
import time
from typing import Iterator, List, Dict, Any, Optional
from datetime import datetime, timezone

from src.data_pipeline.adapters.base import (
    SourceAdapter,
    SourceHealth,
    SnapshotRequest,
    SnapshotResponse,
    EventSubscription,
    SourceEvent
)
from src.data_pipeline.synthetic_data import generate_synthetic_data

class SyntheticAdapter:
    """
    Generates deterministic synthetic Indian Railways corridor data.
    Clearly tags all output as synthetic.
    """
    def __init__(self, seed: int = 42, num_blocks: int = 8, num_jobs: int = 20, num_trains: int = 10):
        self.source_name = "SYNTHETIC_GENERATOR"
        self.seed = seed
        self.num_blocks = num_blocks
        self.num_jobs = num_jobs
        self.num_trains = num_trains
        self._connected = True

    def health(self) -> SourceHealth:
        return SourceHealth(
            source_name=self.source_name,
            is_connected=self._connected,
            status="HEALTHY",
            latency_ms=0.5,
            details={"seed": self.seed, "mode": "synthetic"}
        )

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        start_time = time.time()
        scenario = generate_synthetic_data(
            seed=self.seed,
            num_blocks=self.num_blocks,
            num_jobs=self.num_jobs,
            num_trains=self.num_trains
        )
        data = [
            {"type": "scenario", "content": scenario.model_dump()},
            {"type": "blocks", "items": [b.model_dump() for b in scenario.blocks]},
            {"type": "jobs", "items": [j.model_dump() for j in scenario.jobs]},
            {"type": "trains", "items": [t.model_dump() for t in scenario.trains]}
        ]
        payload_bytes = json.dumps(data, sort_keys=True).encode()
        checksum = hashlib.sha256(payload_bytes).hexdigest()

        return SnapshotResponse(
            source_system=self.source_name,
            division_code=request.division_code,
            timestamp=datetime.now(timezone.utc).isoformat(),
            records_count=len(scenario.blocks) + len(scenario.jobs) + len(scenario.trains),
            data=data,
            checksum=checksum,
            is_synthetic=True
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        # Yield deterministic synthetic telemetry events
        for i in range(5):
            yield SourceEvent(
                event_id=f"SYNTH-EVT-{i+1}",
                event_type="SYNTHETIC_TELEMETRY_PULSE",
                timestamp=datetime.now(timezone.utc).isoformat(),
                source_system=self.source_name,
                division_code=request.division_partition_key or "PRYJ",
                payload={"step": i, "simulated_train_id": f"T{i+1}", "status": "ON_TIME"}
            )

class FixtureAdapter:
    """
    Loads deterministic scenarios from static test fixtures or pre-defined dictionaries.
    """
    def __init__(self, fixture_data: Optional[Dict[str, Any]] = None):
        self.source_name = "FIXTURE_ADAPTER"
        self.fixture_data = fixture_data or {}

    def health(self) -> SourceHealth:
        return SourceHealth(
            source_name=self.source_name,
            is_connected=True,
            status="HEALTHY",
            latency_ms=0.1,
            details={"has_fixture": bool(self.fixture_data)}
        )

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        records = [self.fixture_data] if self.fixture_data else []
        checksum = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
        return SnapshotResponse(
            source_system=self.source_name,
            division_code=request.division_code,
            timestamp=datetime.now(timezone.utc).isoformat(),
            records_count=len(records),
            data=records,
            checksum=checksum,
            is_synthetic=True
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        events = self.fixture_data.get("events", [])
        for evt in events:
            yield SourceEvent(
                event_id=evt.get("event_id", f"FIX-EVT-{time.time()}"),
                event_type=evt.get("event_type", "FIXTURE_EVENT"),
                timestamp=evt.get("timestamp", datetime.now(timezone.utc).isoformat()),
                source_system=self.source_name,
                division_code=request.division_partition_key,
                payload=evt.get("payload", {})
            )

class ReplayAdapter:
    """
    Replays historical timestamped event logs for shadow-mode and backtesting.
    """
    def __init__(self, event_log: List[Dict[str, Any]], speed_multiplier: float = 1.0):
        self.source_name = "REPLAY_ADAPTER"
        self.event_log = event_log
        self.speed_multiplier = speed_multiplier

    def health(self) -> SourceHealth:
        return SourceHealth(
            source_name=self.source_name,
            is_connected=True,
            status="HEALTHY",
            latency_ms=0.2,
            details={"event_count": len(self.event_log), "speed_multiplier": self.speed_multiplier}
        )

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        checksum = hashlib.sha256(json.dumps(self.event_log, sort_keys=True).encode()).hexdigest()
        return SnapshotResponse(
            source_system=self.source_name,
            division_code=request.division_code,
            timestamp=datetime.now(timezone.utc).isoformat(),
            records_count=len(self.event_log),
            data=self.event_log,
            checksum=checksum,
            is_synthetic=False
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        for raw in self.event_log:
            yield SourceEvent(
                event_id=raw.get("event_id", "REPLAY-EVT"),
                event_type=raw.get("event_type", "HISTORICAL_REPLAY"),
                timestamp=raw.get("timestamp", datetime.now(timezone.utc).isoformat()),
                source_system=self.source_name,
                division_code=raw.get("division_code") or request.division_partition_key,
                payload=raw.get("payload", raw)
            )
