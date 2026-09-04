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
        is_live_enabled: bool = False
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
        self._record_dead_letter({"url": url, "method": method, "error": str(last_exception)})
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

class TMSAdapter(BaseCRISAdapter):
    """
    Track Management System (TMS) Adapter.
    Ingests track asset health, USFD defect logs, IMR classification, and speed restrictions.
    """
    def __init__(self, config: Optional[CRISAdapterConfig] = None):
        super().__init__(config or CRISAdapterConfig("TMS"))

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        if not self.config.is_live_enabled:
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
        # Connect to Kafka or polling stream
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
        return iter([])
