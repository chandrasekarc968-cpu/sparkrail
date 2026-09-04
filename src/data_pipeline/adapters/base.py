from typing import Protocol, Iterator, Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class SourceHealth(BaseModel):
    source_name: str
    is_connected: bool
    status: str = "HEALTHY"  # "HEALTHY", "DEGRADED", "UNAVAILABLE"
    latency_ms: float = 0.0
    last_sync_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

class SnapshotRequest(BaseModel):
    division_code: str
    timestamp: Optional[str] = None
    entity_types: List[str] = Field(default_factory=list)
    limit: Optional[int] = None

class SnapshotResponse(BaseModel):
    source_system: str
    division_code: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    records_count: int
    data: List[Dict[str, Any]]
    checksum: str = ""
    is_synthetic: bool = False

class EventSubscription(BaseModel):
    topics: List[str]
    consumer_group: str = "sparkrail-ingestion"
    division_partition_key: Optional[str] = None
    start_offset: str = "latest"  # "earliest", "latest"

class SourceEvent(BaseModel):
    event_id: str
    event_type: str
    timestamp: str
    source_system: str
    division_code: Optional[str] = None
    payload: Dict[str, Any]

class SourceAdapter(Protocol):
    """
    Standard protocol for all CRIS and local data source adapters.
    """
    def health(self) -> SourceHealth:
        """Expose connection health and latency."""
        ...

    def fetch_snapshot(self, request: SnapshotRequest) -> SnapshotResponse:
        """Pull snapshot data for the specified division and entity types."""
        ...

    def consume_events(self, request: EventSubscription) -> Iterator[SourceEvent]:
        """Stream real-time events for the active subscription."""
        ...
