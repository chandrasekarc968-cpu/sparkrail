# Canonical Geometry Contract Specification (v1.0.0)

**Schema Specification:** `geometry_schema_version: "1.0.0"`  
**Standard:** Indian Railways Advisory Decision-Support Platform  
**Target Architecture:** FastAPI REST API (`/network/geometry/v1`) & React Three.js Frontend  

---

## 1. Provenance Requirements (Critical Safety Boundary #4)

Every entity returned by the geometry API or displayed on the 3D map MUST inherit from `BaseEntityProvenance`:

```json
{
  "source_system": "TMS | TDMS | SMMS | COA | RTIS | BDMS | SYNTHETIC_GENERATOR",
  "source_record_id": "REC-STR-00123",
  "schema_version": "1.0.0",
  "geometry_source": "surveyed | authoritative | synthetic",
  "coordinate_reference_system": "LOCAL_CORRIDOR | EPSG:4326",
  "source_timestamp": "2026-09-04T08:30:00Z",
  "ingestion_timestamp": "2026-09-04T08:35:10Z",
  "data_freshness_seconds": 42.5,
  "confidence": 0.98,
  "validation_status": "VALIDATED | SYNTHETIC | STALE | LOW_CONFIDENCE | INVALID | CONTRADICTORY | UNAVAILABLE"
}
```

---

## 2. Validation Status Enumeration

| Validation Status | Description | Operational Treatment in 3D Map |
|:---|:---|:---|
| `VALIDATED` | Surveyed geometry verified against IR engineering records. | Rendered as trusted operational baseline. |
| `SYNTHETIC` | Deterministically generated fixture for simulation. | Prominently badged `SYNTHETIC DATA` in inspector and header. |
| `STALE` | Ingestion age exceeds 300 seconds. | Warning banner displayed; position shown with dashed uncertainty bounds. |
| `LOW_CONFIDENCE` | Confidence score $< 0.80$. | Amber advisory highlight; flagged for manual field verification. |
| `INVALID` | Violates mathematical or physical bounds. | **REJECTED**: Blocked from 3D scene; logged to audit trail. |
| `CONTRADICTORY` | Multiple conflicting source coordinates. | Red exclamation indicator; blocks approval workflow. |
| `UNAVAILABLE` | Telemetry dropped or sensor disconnected. | Visual placeholder indicator; tagged as unavailable. |

---

## 3. Supported Entity Schemas

### 3.1 TrackSection & TrackCenterline
Represents directional trackage (UP, DOWN, Loop, Siding).
- `id`: Unique section ID (`TRK_B1_UP`)
- `line_id`: Parent corridor code (`SFG-MZP-DN`)
- `track_type`: `"UP" | "DOWN" | "LOOP" | "SIDING" | "CROSSOVER"`
- `chainage_start_km`: Start KP (must be $< \text{chainage\_end\_km}$)
- `chainage_end_km`: End KP
- `start_coord`: `{"x": -400.0, "y": 0.0, "z": 2.2}`
- `end_coord`: `{"x": -300.0, "y": 0.0, "z": 4.2}`
- `path_points`: Array of at least 2 finite 3D coordinates
- `speed_limit_kmh`: Max permissible speed
- `gradient_permille`: Track slope

### 3.2 Station & Junction (`StationNode`)
- `id`: Node code (`NODE_PRYJ`)
- `name`: Full name (`Prayagraj Junction`)
- `code`: IR 3-4 letter station code (`PRYJ`)
- `node_type`: `"station" | "junction" | "terminal" | "halt"`
- `chainage_km`: Linear distance along corridor
- `platforms`: Platform track count
- `connected_blocks`: List of adjoining block sections
- `position`: Local Euclidean 3D coordinates

### 3.3 Interlocking & Crossover
- `id`: Turnout / crossover identifier (`XOVER_BEP_01`)
- `from_track_section_id`: Source track section
- `to_track_section_id`: Target track section
- `max_diverging_speed_kmh`: Turnout speed limit (typically 30 or 50 km/h)
- `point_machine_id`: SMMS asset reference

### 3.4 Signal & Track Circuit
- `id`: Signal code (`SIG_B4_UP`)
- `referenced_track_section_id`: Associated track section (MANDATORY)
- `chainage_km`: Location along track
- `aspect`: `"clear" | "caution" | "attention" | "danger"`
- `direction`: `"UP" | "DOWN"`
- `position`: 3D coordinates offset from rail centerline

### 3.5 OHE Infrastructure
- `OHEMast`: Mast coordinate, catenary height (typically 5.5m), `is_isolated` flag.
- `ElementarySection`: Bounded electrical section, mapped tracks, isolator switches.
- `FeedingPost`: Substation feeder feed-in location, voltage rating (25kV).
- `IsolatorSwitch`: Manual/motorized switch (`CLOSED` = live, `OPEN` = isolated).

### 3.6 Possession & Shadow Bundle
- `PossessionEntity`: `id`, `department`, `chainage_start_km`, `chainage_end_km`, `start_time_hours`, `end_time_hours`, `status` (`"REQUESTED" | "SANCTIONED" | "GRANTED" | "IN_PROGRESS" | "COMPLETED"`), `is_locked` (**MUST be true if GRANTED or IN_PROGRESS**).
- `ShadowPossessionBundle`: Primary possession ID, secondary jobs, common block, total TCI benefit.

### 3.7 ConflictMarker
- `id`: Conflict reference
- `conflict_type`: `"train_versus_possession" | "fixed_block_collision" | "ohe_isolation_conflict" | ...`
- `severity`: `"CRITICAL" | "MAJOR" | "WARNING" | "INFO"`
- `blocks_approval`: `true` for CRITICAL and MAJOR
- `description`: Plain-English operational impact
- `suggested_resolution`: Advisory resolution path

---

## 4. Strict Rejection Rules

The geometry validation pipeline unconditionally rejects:
1. **NaN or Infinite Coordinates:** Any coordinate containing `NaN`, `Infinity`, or non-numeric types.
2. **Reversed Chainage:** Track sections or possessions where `chainage_start_km >= chainage_end_km`.
3. **Zero-Length Tracks:** Tracks with Euclidean distance $< 0.001\text{ m}$.
4. **Dangling Signals:** Signals with missing or unresolvable `referenced_track_section_id`.
5. **Dangling OHE Sections:** Elementary sections referencing track sections not in the corridor.
6. **Safety Boundary #6 Violation:** Any possession in `GRANTED` or `IN_PROGRESS` status where `is_locked: false`.
7. **Schema Incompatibility:** Payloads where `geometry_schema_version` is missing or major version $\ne 1$.
8. **Unknown Coordinate Systems:** Payloads with CRS other than `LOCAL_CORRIDOR` or `EPSG:4326`.
