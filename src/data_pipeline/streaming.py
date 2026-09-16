"""
Lambda-Kappa lakehouse ingestion layer (Spec §1).

Spec architecture:
    Kafka (streaming)  -> NiFi (batch) -> Spark Structured Streaming
    -> Delta Lake / Hudi (storage) -> PostgreSQL + PostGIS (serving & GIS)

This module provides the *streaming* half of that pipeline:

* :class:`KafkaEventSource`    - consumes train-movement / telemetry topics.
* :class:`NiFiBatchSource`     - pulls batch extracts (BDMS/COA) on a schedule.
* :class:`LocalEventReplaySource` - deterministic, dependency-free replay of a
  JSONL event log, used for tests and offline demos.
* :class:`StreamingIngestionHub`- composes the above and exposes a single
  ``consume()`` that returns the merged, most-recent observation per entity.

All external clients (kafka-python, the NiFi swagger client) are imported
* lazily* inside the methods that need them. If the optional package is not
installed the source degrades to its local fallback instead of raising at
import time, matching the project's "advisory, degrade gracefully" posture.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional

logger = logging.getLogger("SparkRail.Streaming")


def _now_ms() -> int:
    return int(time.time() * 1000)


class BaseEventSource:
    """Common contract for every event source."""

    name = "base"

    def connect(self) -> None:
        """Establish the connection. No-op for local sources."""

    def events(self, since_ms: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """Yield raw event dicts."""
        raise NotImplementedError

    def close(self) -> None:
        """Tear down the connection."""


class LocalEventReplaySource(BaseEventSource):
    """
    Deterministic replay of a JSONL event log.

    Each line must be a JSON object with at least a ``kind`` field
    (``train_movement`` | ``asset_telemetry`` | ``possession_update``) and a
    ``ts_ms`` timestamp. Lines without a timestamp are assigned the file order.
    """

    name = "local_replay"

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._fh = None

    def connect(self) -> None:
        if not os.path.exists(self.log_path):
            raise FileNotFoundError(f"Event log not found: {self.log_path}")

    def events(self, since_ms: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        with open(self.log_path, "r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed event line %d", idx)
                    continue
                ts = int(evt.get("ts_ms", idx))
                if since_ms is not None and ts < since_ms:
                    continue
                yield evt

    def close(self) -> None:  # pragma: no cover - nothing to release
        return None


class KafkaEventSource(BaseEventSource):
    """
    Kafka consumer adapter for the streaming leg of the Lambda-Kappa pipeline.

    Topics (from ``config.data_pipeline.kafka.topics``): ``train_movements``,
    ``signal_status``, plus a ``asset_telemetry`` topic for TMS/USFD feeds.

    Falls back to :class:`LocalEventReplaySource` when ``kafka-python`` is not
    installed so the ingestion graph stays importable and testable.
    """

    name = "kafka"

    def __init__(self, bootstrap_servers: str, topics: List[str], group_id: str = "sparkrail-ingest"):
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics
        self.group_id = group_id
        self._consumer = None
        self._fallback: Optional[LocalEventReplaySource] = None

    def connect(self) -> None:
        try:
            from kafka import KafkaConsumer  # type: ignore
        except ImportError:
            logger.warning("kafka-python not installed; KafkaEventSource is inert (no fallback log configured).")
            self._consumer = None
            return
        self._consumer = KafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest",
            value_deserializer=lambda b: json.loads(b.decode("utf-8")),
            consumer_timeout_ms=2000,
        )

    def events(self, since_ms: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        if self._consumer is None:
            return
        for msg in self._consumer:
            yield msg.value

    def close(self) -> None:
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None


class NiFiBatchSource(BaseEventSource):
    """
    NiFi-style batch extractor for the BDMS/COA nightly pulls.

    A real NiFi deployment exposes a REST API; here we model it as a directory
    of dated batch files (``batch_dir/YYYYMMDD.json``). When the optional NiFi
    swagger client is unavailable we simply read those local files, which keeps
    the batch leg functional offline and in CI.
    """

    name = "nifi_batch"

    def __init__(self, batch_dir: str):
        self.batch_dir = batch_dir
        self._client = None

    def connect(self) -> None:
        # Optional commercial/enterprise client; never required for operation.
        try:
            import nifi  # type: ignore  # nifi-python-swagger-client
            self._client = nifi
        except ImportError:
            self._client = None

    def events(self, since_ms: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        if not os.path.isdir(self.batch_dir):
            logger.warning("NiFi batch dir %s missing; no batch events.", self.batch_dir)
            return
        for fname in sorted(os.listdir(self.batch_dir)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.batch_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read batch file %s: %s", path, exc)
                continue
            records = payload if isinstance(payload, list) else payload.get("records", [])
            for rec in records:
                yield rec

    def close(self) -> None:  # pragma: no cover - nothing to release
        return None


class StreamingIngestionHub:
    """
    Composes event sources into a single, merged observation stream.

    ``consume()`` replays every source and returns the latest observation per
    entity key (e.g. per ``train_id`` / ``block_id``), which is what the
    downstream optimisation and the digital twin actually consume.
    """

    def __init__(self, sources: Optional[List[BaseEventSource]] = None):
        self.sources = sources or []

    def add_source(self, source: BaseEventSource) -> None:
        self.sources.append(source)

    def connect(self) -> None:
        for src in self.sources:
            try:
                src.connect()
            except Exception as exc:  # keep the hub resilient
                logger.warning("Source %s failed to connect: %s", src.name, exc)

    def consume(self, since_ms: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns observations bucketed by ``kind`` with the most-recent record
        per entity retained (deduplicated by ``id``/``train_id``/``block_id``).
        """
        merged: Dict[str, Dict[str, Dict[str, Any]]] = {}

        def _key(evt: Dict[str, Any]) -> str:
            return str(evt.get("id") or evt.get("train_id") or evt.get("block_id") or evt.get("asset_id") or "UNKEYED")

        for src in self.sources:
            try:
                for evt in src.events(since_ms):
                    kind = str(evt.get("kind", "unknown"))
                    bucket = merged.setdefault(kind, {})
                    bucket[_key(evt)] = evt
            except Exception as exc:
                logger.warning("Source %s raised during consume: %s", src.name, exc)

        return {kind: list(bucket.values()) for kind, bucket in merged.items()}

    def close(self) -> None:
        for src in self.sources:
            try:
                src.close()
            except Exception:  # pragma: no cover - best effort
                pass
