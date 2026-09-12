import os
import json
import time
import logging
import hashlib
from typing import Dict, Any, List, Optional, Iterator
from datetime import datetime, timezone
import httpx

from src.data_pipeline.adapters.base import (
    SourceAdapter,
    SourceHealth,
    SnapshotRequest,
    SnapshotResponse,
    EventSubscription,
    SourceEvent
)

logger = logging.getLogger("SparkRail.CRISAdapters")

class CRISAdapterConfig:
    def __init__(
        self,
        source_name: str,
        base_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        mtls_cert_path: Optional[str] = None,
        mtls_key_path: Optional[str] = None,
        ca_bundle_path: Optional[str] = None,
        kafka_brokers: Optional[str] = None,
        topic_name: Optional[str] = None,
        dead_letter_file: str = "data/dead_letter.jsonl",
        is_live_enabled: bool = False,
        mock_mode: bool = False
    ):
        self.source_name = source_name
        self.base_url = base_url or os.getenv(f"CRIS_{source_name}_URL", "https://cris.indianrailways.gov.in/api/v1")
        self.timeout_seconds = float(os.getenv(f"CRIS_{source_name}_TIMEOUT", timeout_seconds))
        self.max_retries = int(os.getenv(f"CRIS_{source_name}_MAX_RETRIES", max_retries))
        self.backoff_factor = backoff_factor
        self.mtls_cert_path = mtls_cert_path or os.getenv(f"CRIS_{source_name}_CERT_PATH")
        self.mtls_key_path = mtls_key_path or os.getenv(f"CRIS_{source_name}_KEY_PATH")
        self.ca_bundle_path = ca_bundle_path or os.getenv(f"CRIS_{source_name}_CA_BUNDLE")
        self.kafka_brokers = kafka_brokers or os.getenv("CRIS_KAFKA_BROKERS")
        self.topic_name = topic_name or os.getenv(f"CRIS_{source_name}_TOPIC", f"cris.{source_name.lower()}.events")
        self.dead_letter_file = dead_letter_file
        self.is_live_enabled = is_live_enabled or (os.getenv("SPARKRAIL_LIVE_MODE", "false").lower() == "true")
        self.mock_mode = mock_mode or (os.getenv("SPARKRAIL_MOCK_MODE", "false").lower() == "true")

class BaseCRISAdapter:
    """
    Base implementation for all production CRIS adapters.
    Enforces mTLS, timeout, bounded backoff retry, dead-letter logging,
    and strict rejection of synthetic fallbacks when in live mode.
    """
    def __init__(self, config: CRISAdapterConfig):
        self.config = config
        self.source_name = config.source_name
        self.last_sync_timestamp: Optional[str] = None
        self._last_latency_ms: float = 0.0

    def _get_http_client(self) -> httpx.Client:
        # Validate certificate paths if provided
        cert = None
        if self.config.mtls_cert_path and self.config.mtls_key_path:
            if not os.path.exists(self.config.mtls_cert_path):
                raise FileNotFoundError(f"mTLS certificate not found at: {self.config.mtls_cert_path}")
            if not os.path.exists(self.config.mtls_key_path):
                raise FileNotFoundError(f"mTLS private key not found at: {self.config.mtls_key_path}")
            cert = (self.config.mtls_cert_path, self.config.mtls_key_path)

        verify: Any = True
        if self.config.ca_bundle_path:
            if not os.path.exists(self.config.ca_bundle_path):
                raise FileNotFoundError(f"CA bundle not found at: {self.config.ca_bundle_path}")
            verify = self.config.ca_bundle_path

        return httpx.Client(
            cert=cert,
            verify=verify,
            timeout=self.config.timeout_seconds
        )

    def _execute_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        last_exception: Optional[Exception] = None
        
        for attempt in range(1, self.config.max_retries + 1):
            start = time.perf_counter()
            try:
                with self._get_http_client() as client:
                    resp = client.request(method, url, **kwargs)
                    self._last_latency_ms = (time.perf_counter() - start) * 1000.0
                    resp.raise_for_status()
                    self.last_sync_timestamp = datetime.now(timezone.utc).isoformat()
                    return resp
            except Exception as e:
                self._last_latency_ms = (time.perf_counter() - start) * 1000.0
                last_exception = e
                logger.warning(
                    f"[{self.source_name}] Attempt {attempt}/{self.config.max_retries} failed for {url}: {e}"
                )
                if attempt < self.config.max_retries:
                    sleep_time = self.config.backoff_factor ** attempt
                    time.sleep(sleep_time)

        # All retries exhausted
        self._record_dead_letter({
            "url": url,
            "method": method,
            "error_type": type(last_exception).__name__,
            "error_message": str(last_exception),
            "attempts": self.config.max_retries,
            "kwargs_keys": list(kwargs.keys())
        })
        raise RuntimeError(f"[{self.source_name}] Request failed after {self.config.max_retries} attempts: {last_exception}")

    def _record_dead_letter(self, payload: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self.config.dead_letter_file), exist_ok=True)
            with open(self.config.dead_letter_file, "a") as f:
                entry = {
                    "source": self.source_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": payload
                }
                f.write(json.dumps(entry) + "\n")
        except Exception as err:
            logger.error(f"Failed to record dead-letter entry: {err}")

    def health(self) -> SourceHealth:
        if not self.config.is_live_enabled:
            return SourceHealth(
                source_name=self.source_name,
                is_connected=False,
                status="DEGRADED",
                latency_ms=0.0,
                details={"mode": "configuration_gated", "message": "Live integration disabled by configuration."}
            )

        try:
            resp = self._execute_with_retry("GET", "/health")
            return SourceHealth(
                source_name=self.source_name,
                is_connected=True,
                status="HEALTHY",
                latency_ms=round(self._last_latency_ms, 2),
                last_sync_timestamp=self.last_sync_timestamp or datetime.now(timezone.utc).isoformat(),
                details=resp.json() if resp.status_code == 200 else {}
            )
        except Exception as e:
            return SourceHealth(
                source_name=self.source_name,
                is_connected=False,
                status="UNAVAILABLE",
                latency_ms=round(self._last_latency_ms, 2),
                error_message=str(e),
                details={"error": str(e)}
            )

    def _is_mock_allowed(self, request: SnapshotRequest) -> bool:
        return self.config.mock_mode or getattr(request, "mock_mode", False)

    def process_event(
        self,
        event: Dict[str, Any],
        current_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Idempotent, safe event processing with stale detection, contradiction detection,
        and dead-letter queue logging.
        """
        if not hasattr(self, "_processed_events"):
            self._processed_events = set()
        if not hasattr(self, "_last_entity_timestamps"):
            self._last_entity_timestamps = {}

        event_id = event.get("event_id", f"EVT-{int(time.time()*1000)}")
        ts_str = event.get("timestamp")
        payload = event.get("payload", {})

        # 1. Idempotency check
        if event_id in self._processed_events:
            return {
                "status": "STALE_OR_DUPLICATE_REJECTED",
                "reason": "Duplicate event ID already processed",
                "event_id": event_id
            }

        # 2. Timestamp parse & freshness / stale check
        try:
            if ts_str:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                event_epoch = dt.timestamp()
                
                # Check entity-level sequence
                entity_key = payload.get("track_section_id") or payload.get("train_id") or payload.get("asset_id") or event_id
                last_seen = self._last_entity_timestamps.get(entity_key)
                if last_seen and event_epoch < last_seen:
                    self._record_dead_letter({
                        "event": event,
                        "reason": f"Out-of-order stale event for {entity_key}: {event_epoch} < {last_seen}"
                    })
                    return {
                        "status": "STALE_OR_DUPLICATE_REJECTED",
                        "reason": "Out of sequence timestamp",
                        "event_id": event_id
                    }
                self._last_entity_timestamps[entity_key] = event_epoch
        except Exception as e:
            self._record_dead_letter({"event": event, "reason": f"Unparseable timestamp: {e}"})
            return {"status": "REJECTED_FORMAT", "reason": str(e), "event_id": event_id}

        # 3. Contradiction detection against current_context
        if current_context:
            contradiction = self._check_contradictions(event, current_context)
            if contradiction:
                self._record_dead_letter({"event": event, "reason": contradiction})
                return {
                    "status": "CONTRADICTION_REJECTED",
                    "reason": contradiction,
                    "event_id": event_id
                }

        self._processed_events.add(event_id)
        return {
            "status": "INGESTED",
            "event_id": event_id,
            "source": self.source_name,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

    def _check_contradictions(self, event: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})
        
        # Rule 1: Electric train occupying an isolated section
        if event_type == "TRAIN_MOVEMENT" and payload.get("traction_type") == "ELECTRIC":
            section_id = payload.get("track_section_id")
            isolated_sections = context.get("isolated_sections", set())
            if section_id in isolated_sections:
                return f"Contradiction: Electric train '{payload.get('train_id')}' occupying electrically isolated section '{section_id}'"
        
        # Rule 2: Multiple trains on same block without headway
        if event_type == "TRAIN_MOVEMENT":
            section_id = payload.get("track_section_id")
            occupied_blocks = context.get("occupied_blocks", {})
            current_occupant = occupied_blocks.get(section_id)
            if current_occupant and current_occupant != payload.get("train_id"):
                return f"Contradiction: Block '{section_id}' reported occupied by both '{current_occupant}' and '{payload.get('train_id')}'"

        return None

class TMSAdapter(BaseCRISAdapter):
    """
    Track Management System (TMS) Adapter.
    Ingests track asset health, USFD defect logs, IMR classification, and speed restrictions.
    """
    def __init__(self, config: Optional[CRISAdapterConfig] = None):
        super().__init__(config or CRISAdapterConfig("TMS"))

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        if not self.config.is_live_enabled:
            if self._is_mock_allowed(request):
                # Deterministic synthetic TMS dataset for division
                mock_items = [
                    {"asset_id": f"TMS-{request.division_code}-RAIL-01", "track_section_id": "B1", "usfd_defect_depth": 35.0, "is_imr": False, "speed_restriction_kmh": 100.0},
                    {"asset_id": f"TMS-{request.division_code}-JOINT-02", "track_section_id": "B3", "usfd_defect_depth": 85.0, "is_imr": True, "speed_restriction_kmh": 30.0},
                    {"asset_id": f"TMS-{request.division_code}-TURNOUT-03", "track_section_id": "B5", "usfd_defect_depth": 15.0, "is_imr": False, "speed_restriction_kmh": 120.0},
                ]
                checksum = hashlib.sha256(json.dumps(mock_items, sort_keys=True).encode()).hexdigest()
                return SnapshotResponse(
                    source_system="TMS",
                    division_code=request.division_code,
                    records_count=len(mock_items),
                    data=mock_items,
                    checksum=checksum,
                    is_synthetic=True
                )
            raise RuntimeError(
                f"[{self.source_name}] Live CRIS integration disabled. Never return synthetic data silently in live mode."
            )
        
        resp = self._execute_with_retry(
            "GET",
            f"/divisions/{request.division_code}/track-assets",
            params={"limit": request.limit or 500}
        )
        data = resp.json()
        checksum = hashlib.sha256(resp.content).hexdigest()
        return SnapshotResponse(
            source_system="TMS",
            division_code=request.division_code,
            records_count=len(data.get("items", [])),
            data=data.get("items", []),
            checksum=checksum,
            is_synthetic=False
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        if self.config.mock_mode:
            div = request.division_partition_key or "PRYJ"
            for i in range(3):
                yield SourceEvent(
                    event_id=f"TMS-EVT-{div}-{i+1}",
                    event_type="USFD_DEFECT_DETECTED",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    source_system="TMS",
                    division_code=div,
                    payload={"asset_id": f"AST-{div}-{i+1}", "defect_severity": "IMR" if i == 0 else "OBSERVED"}
                )
            return
        return iter([])

class TDMSAdapter(BaseCRISAdapter):
    """
    Traction Distribution Management System (TDMS) Adapter.
    Ingests 25kV feeding posts, elementary sections, isolator switch states, and catenary wear.
    """
    def __init__(self, config: Optional[CRISAdapterConfig] = None):
        super().__init__(config or CRISAdapterConfig("TDMS"))

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        if not self.config.is_live_enabled:
            if self._is_mock_allowed(request):
                mock_sections = [
                    {"section_id": f"ES-{request.division_code}-01", "feeding_post_id": "FP_SUBEDARGANJ", "voltage_kv": 25.0, "track_sections": ["B1", "B2"], "is_energized": True},
                    {"section_id": f"ES-{request.division_code}-02", "feeding_post_id": "FP_NAINI", "voltage_kv": 25.0, "track_sections": ["B3", "B4"], "is_energized": True},
                    {"section_id": f"ES-{request.division_code}-03", "feeding_post_id": "FP_MIRZAPUR", "voltage_kv": 25.0, "track_sections": ["B5", "B6", "B7", "B8"], "is_energized": True}
                ]
                checksum = hashlib.sha256(json.dumps(mock_sections, sort_keys=True).encode()).hexdigest()
                return SnapshotResponse(
                    source_system="TDMS",
                    division_code=request.division_code,
                    records_count=len(mock_sections),
                    data=mock_sections,
                    checksum=checksum,
                    is_synthetic=True
                )
            raise RuntimeError(f"[{self.source_name}] Live CRIS integration disabled.")
        
        resp = self._execute_with_retry("GET", f"/divisions/{request.division_code}/electrical-sections")
        data = resp.json()
        checksum = hashlib.sha256(resp.content).hexdigest()
        return SnapshotResponse(
            source_system="TDMS",
            division_code=request.division_code,
            records_count=len(data.get("sections", [])),
            data=data.get("sections", []),
            checksum=checksum,
            is_synthetic=False
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        if self.config.mock_mode:
            div = request.division_partition_key or "PRYJ"
            yield SourceEvent(
                event_id=f"TDMS-EVT-{div}-01",
                event_type="ISOLATOR_STATE_CHANGED",
                timestamp=datetime.now(timezone.utc).isoformat(),
                source_system="TDMS",
                division_code=div,
                payload={"switch_id": "ISO-01", "state": "OPEN"}
            )
            return
        return iter([])

class SMMSAdapter(BaseCRISAdapter):
    """
    Signaling Maintenance Management System (SMMS) Adapter.
    Ingests points, track circuits, route tables, interlocking status, and signal aspects.
    """
    def __init__(self, config: Optional[CRISAdapterConfig] = None):
        super().__init__(config or CRISAdapterConfig("SMMS"))

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        if not self.config.is_live_enabled:
            if self._is_mock_allowed(request):
                mock_assets = [
                    {"signal_id": f"SIG-{request.division_code}-01", "track_section_id": "B1", "aspect": "CLEAR", "is_operational": True},
                    {"point_id": f"PT-{request.division_code}-101", "station": "PRYJ", "route": "MAIN_DOWN", "is_locked": True}
                ]
                checksum = hashlib.sha256(json.dumps(mock_assets, sort_keys=True).encode()).hexdigest()
                return SnapshotResponse(
                    source_system="SMMS",
                    division_code=request.division_code,
                    records_count=len(mock_assets),
                    data=mock_assets,
                    checksum=checksum,
                    is_synthetic=True
                )
            raise RuntimeError(f"[{self.source_name}] Live CRIS integration disabled.")
        
        resp = self._execute_with_retry("GET", f"/divisions/{request.division_code}/signaling-inventory")
        data = resp.json()
        checksum = hashlib.sha256(resp.content).hexdigest()
        return SnapshotResponse(
            source_system="SMMS",
            division_code=request.division_code,
            records_count=len(data.get("assets", [])),
            data=data.get("assets", []),
            checksum=checksum,
            is_synthetic=False
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        return iter([])

class COAAdapter(BaseCRISAdapter):
    """
    Control Office Application (COA) Adapter.
    Ingests scheduled timetables, train precedence, active train movements, and Section Controller logs.
    """
    def __init__(self, config: Optional[CRISAdapterConfig] = None):
        super().__init__(config or CRISAdapterConfig("COA"))

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        if not self.config.is_live_enabled:
            if self._is_mock_allowed(request):
                mock_trains = [
                    {"train_id": "22436", "name": "Vande Bharat Exp", "priority": "PREMIUM_PASSENGER", "delay_min": 0.0, "route": ["B1", "B2", "B3", "B4"]},
                    {"train_id": "12302", "name": "Howrah Rajdhani", "priority": "PREMIUM_PASSENGER", "delay_min": 5.0, "route": ["B1", "B2", "B3", "B4", "B5"]},
                    {"train_id": "12428", "name": "Rewa Express", "priority": "EXPRESS_PASSENGER", "delay_min": 12.0, "route": ["B3", "B4", "B5", "B6"]},
                ]
                checksum = hashlib.sha256(json.dumps(mock_trains, sort_keys=True).encode()).hexdigest()
                return SnapshotResponse(
                    source_system="COA",
                    division_code=request.division_code,
                    records_count=len(mock_trains),
                    data=mock_trains,
                    checksum=checksum,
                    is_synthetic=True
                )
            raise RuntimeError(f"[{self.source_name}] Live CRIS integration disabled.")
        
        resp = self._execute_with_retry("GET", f"/divisions/{request.division_code}/train-graph")
        data = resp.json()
        checksum = hashlib.sha256(resp.content).hexdigest()
        return SnapshotResponse(
            source_system="COA",
            division_code=request.division_code,
            records_count=len(data.get("trains", [])),
            data=data.get("trains", []),
            checksum=checksum,
            is_synthetic=False
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        if self.config.mock_mode:
            div = request.division_partition_key or "PRYJ"
            yield SourceEvent(
                event_id=f"COA-EVT-{div}-01",
                event_type="TRAIN_DELAY_REPORTED",
                timestamp=datetime.now(timezone.utc).isoformat(),
                source_system="COA",
                division_code=div,
                payload={"train_id": "22436", "delay_minutes": 18.0}
            )
            return
        return iter([])

class RTISAdapter(BaseCRISAdapter):
    """
    Real-Time Train Information System (RTIS) Adapter.
    Ingests high-frequency locomotive GPS telemetry, speeds, and block occupancies.
    """
    def __init__(self, config: Optional[CRISAdapterConfig] = None):
        super().__init__(config or CRISAdapterConfig("RTIS"))

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        if not self.config.is_live_enabled:
            if self._is_mock_allowed(request):
                mock_telemetry = [
                    {"loco_id": "WAP7-30201", "train_id": "22436", "lat": 25.435, "lon": 81.846, "speed_kmh": 125.0, "timestamp": datetime.now(timezone.utc).isoformat()},
                    {"loco_id": "WAP7-30455", "train_id": "12302", "lat": 25.350, "lon": 82.020, "speed_kmh": 110.0, "timestamp": datetime.now(timezone.utc).isoformat()}
                ]
                checksum = hashlib.sha256(json.dumps(mock_telemetry, sort_keys=True).encode()).hexdigest()
                return SnapshotResponse(
                    source_system="RTIS",
                    division_code=request.division_code,
                    records_count=len(mock_telemetry),
                    data=mock_telemetry,
                    checksum=checksum,
                    is_synthetic=True
                )
            raise RuntimeError(f"[{self.source_name}] Live CRIS integration disabled.")
        
        resp = self._execute_with_retry("GET", f"/divisions/{request.division_code}/loco-telemetry")
        data = resp.json()
        checksum = hashlib.sha256(resp.content).hexdigest()
        return SnapshotResponse(
            source_system="RTIS",
            division_code=request.division_code,
            records_count=len(data.get("telemetry", [])),
            data=data.get("telemetry", []),
            checksum=checksum,
            is_synthetic=False
        )

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        if self.config.mock_mode:
            div = request.division_partition_key or "PRYJ"
            for step in range(3):
                yield SourceEvent(
                    event_id=f"RTIS-EVT-{div}-{step+1}",
                    event_type="LOCO_GPS_PULSE",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    source_system="RTIS",
                    division_code=div,
                    payload={"loco_id": "WAP7-30201", "speed_kmh": 120.0 + step * 2, "chainage_km": 15.0 + step * 1.5}
                )
            return
        return iter([])

class BDMSAdapter(BaseCRISAdapter):
    """
    Block & Disconnection Management System (BDMS) Adapter.
    Ingests maintenance demands, submits advisory proposals, and tracks approval/grant lifecycle.
    """
    def __init__(self, config: Optional[CRISAdapterConfig] = None):
        super().__init__(config or CRISAdapterConfig("BDMS"))

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        if not self.config.is_live_enabled:
            if self._is_mock_allowed(request):
                mock_reqs = [
                    {"requisition_id": f"BDMS-{request.division_code}-REQ-01", "track_section_id": "B5", "department": "CIVIL", "duration_hours": 3.0, "status": "SANCTIONED"},
                    {"requisition_id": f"BDMS-{request.division_code}-REQ-02", "track_section_id": "B5", "department": "TRD", "duration_hours": 2.5, "status": "SANCTIONED"}
                ]
                checksum = hashlib.sha256(json.dumps(mock_reqs, sort_keys=True).encode()).hexdigest()
                return SnapshotResponse(
                    source_system="BDMS",
                    division_code=request.division_code,
                    records_count=len(mock_reqs),
                    data=mock_reqs,
                    checksum=checksum,
                    is_synthetic=True
                )
            raise RuntimeError(f"[{self.source_name}] Live CRIS integration disabled.")
        
        resp = self._execute_with_retry("GET", f"/divisions/{request.division_code}/possession-requisitions")
        data = resp.json()
        checksum = hashlib.sha256(resp.content).hexdigest()
        return SnapshotResponse(
            source_system="BDMS",
            division_code=request.division_code,
            records_count=len(data.get("requisitions", [])),
            data=data.get("requisitions", []),
            checksum=checksum,
            is_synthetic=False
        )

    def submit_advisory_proposal(self, proposal: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        """
        Submits an advisory possession proposal package to BDMS.
        Outbound calls are configuration-gated and strictly require an idempotency key.
        """
        if not self.config.is_live_enabled:
            # Dry-run / synthetic response
            logger.info(f"[{self.source_name}] Dry-run advisory proposal submitted with key {idempotency_key}")
            return {
                "status": "ACCEPTED_FOR_ADVISORY_REVIEW",
                "proposal_id": proposal.get("optimization_run_id", "DRY-RUN-1"),
                "idempotency_key": idempotency_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_dry_run": True
            }

        headers = {"Idempotency-Key": idempotency_key, "Content-Type": "application/json"}
        resp = self._execute_with_retry(
            "POST",
            "/optimization/possession-schedule",
            json=proposal,
            headers=headers
        )
        return resp.json()

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        if self.config.mock_mode:
            div = request.division_partition_key or "PRYJ"
            yield SourceEvent(
                event_id=f"BDMS-EVT-{div}-01",
                event_type="POSSESSION_SANCTION_UPDATED",
                timestamp=datetime.now(timezone.utc).isoformat(),
                source_system="BDMS",
                division_code=div,
                payload={"requisition_id": f"BDMS-{div}-REQ-01", "new_status": "SANCTIONED"}
            )
            return
        return iter([])


class CRISReplayEngine:
    """
    Deterministic synthetic event replay generator for the 8 canonical railway event types:
    1. TRAIN_MOVEMENT (RTIS)
    2. TRAIN_DELAY (COA)
    3. POSSESSION_STATUS (BDMS)
    4. OHE_ISOLATION (TDMS)
    5. SIGNAL_DISCONNECTION (SMMS)
    6. MACHINE_FAILURE (TMS)
    7. WEATHER_RESTRICTION (COA/Operating)
    8. WORK_COMPLETION (BDMS)
    """
    @staticmethod
    def generate_replay_events(division_code: str = "PRYJ", start_epoch: Optional[float] = None) -> List[Dict[str, Any]]:
        base_epoch = start_epoch or datetime.now(timezone.utc).timestamp()
        
        def ts(offset_min: float) -> str:
            return datetime.fromtimestamp(base_epoch + offset_min * 60, timezone.utc).isoformat()

        return [
            # 1. TRAIN_MOVEMENT (RTIS)
            {
                "event_id": f"RTIS-MOV-{division_code}-001",
                "event_type": "TRAIN_MOVEMENT",
                "source_system": "RTIS",
                "timestamp": ts(0.0),
                "division_code": division_code,
                "payload": {"train_id": "T22436", "loco_id": "WAP7-30201", "track_section_id": "B1", "speed_kmh": 125.0, "traction_type": "ELECTRIC"}
            },
            # 2. TRAIN_DELAY (COA)
            {
                "event_id": f"COA-DLY-{division_code}-002",
                "event_type": "TRAIN_DELAY",
                "source_system": "COA",
                "timestamp": ts(5.0),
                "division_code": division_code,
                "payload": {"train_id": "T12302", "delay_minutes": 18.0, "reason": "Caution Order at KM 45"}
            },
            # 3. POSSESSION_STATUS (BDMS)
            {
                "event_id": f"BDMS-POS-{division_code}-003",
                "event_type": "POSSESSION_STATUS",
                "source_system": "BDMS",
                "timestamp": ts(10.0),
                "division_code": division_code,
                "payload": {"possession_id": "POSS-B3-CIVIL", "track_section_id": "B3", "old_status": "SANCTIONED", "new_status": "GRANTED"}
            },
            # 4. OHE_ISOLATION (TDMS)
            {
                "event_id": f"TDMS-ISO-{division_code}-004",
                "event_type": "OHE_ISOLATION",
                "source_system": "TDMS",
                "timestamp": ts(12.0),
                "division_code": division_code,
                "payload": {"elementary_section_id": "ES-02", "switch_id": "SW-ISO-21", "state": "OPEN", "affected_tracks": ["B3", "B4"]}
            },
            # 5. SIGNAL_DISCONNECTION (SMMS)
            {
                "event_id": f"SMMS-SIG-{division_code}-005",
                "event_type": "SIGNAL_DISCONNECTION",
                "source_system": "SMMS",
                "timestamp": ts(15.0),
                "division_code": division_code,
                "payload": {"signal_id": "SIG-NYN-12", "track_section_id": "B3", "disconnection_notice_number": "DN-2026-88"}
            },
            # 6. MACHINE_FAILURE (TMS)
            {
                "event_id": f"TMS-MCH-{division_code}-006",
                "event_type": "MACHINE_FAILURE",
                "source_system": "TMS",
                "timestamp": ts(20.0),
                "division_code": division_code,
                "payload": {"machine_id": "R_BCM_01", "machine_type": "Ballast Cleaning Machine", "failure_code": "HYDRAULIC_LEAK", "track_section_id": "B3"}
            },
            # 7. WEATHER_RESTRICTION (Operating)
            {
                "event_id": f"OP-WTH-{division_code}-007",
                "event_type": "WEATHER_RESTRICTION",
                "source_system": "COA",
                "timestamp": ts(25.0),
                "division_code": division_code,
                "payload": {"corridor_segment": "SFG-NYN", "speed_restriction_kmh": 60.0, "reason": "HEAVY_FOG_VISIBILITY_POOR"}
            },
            # 8. WORK_COMPLETION (BDMS)
            {
                "event_id": f"BDMS-CMP-{division_code}-008",
                "event_type": "WORK_COMPLETION",
                "source_system": "BDMS",
                "timestamp": ts(45.0),
                "division_code": division_code,
                "payload": {"possession_id": "POSS-B3-CIVIL", "track_section_id": "B3", "track_fit_certified": True, "speed_restored_kmh": 100.0}
            }
        ]


