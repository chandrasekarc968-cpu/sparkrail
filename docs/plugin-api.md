# SparkRail Plugin API Specification (v1.0.0)

All endpoints conform to versioned canonical schemas (`/api/v1/...`).

---

## 1. Statutory Governance & Authorization Headers

| Header Name | Type | Description | Required In |
|---|---|---|---|
| `X-Actor-ID` | String | Unique staff/controller ID (e.g., `EMP-10492`). | Sign-off & Mutation endpoints |
| `X-Actor-Role` | String | One of: `CTPC`, `SR_DOM`, `SECTION_CONTROLLER`, `STATION_MASTER`. | Sign-off & Mutation endpoints |
| `Idempotency-Key` | UUID / String | Unique client token ensuring at-most-once execution. | `POST` endpoints |
| `If-Match` | String / Integer | Entity version tag for optimistic concurrency control. | Approval & Mutation endpoints |

---

## 2. API Endpoints Reference

### System & Health

#### `GET /api/v1/health`
Returns runtime status, operational mode (`synthetic`, `shadow`, or `live`), solver availability, geometry schema version, and cryptographic audit integrity.

**Response (200 OK)**:
```json
{
  "status": "ok",
  "plugin_version": "1.0.0",
  "mode": "synthetic",
  "is_synthetic": true,
  "is_shadow": false,
  "is_live": false,
  "live_permitted": false,
  "geometry_schema_version": "1.0.0",
  "solver_available": true,
  "solver_mode": "CP-SAT / ALNS Deterministic Fallback",
  "audit_chain": {
    "is_intact": true,
    "chain_length": 14,
    "error": null
  },
  "statutory_safety_rules": {
    "advisory_only": true,
    "zero_physical_actuation": true,
    "active_possession_immutability": true,
    "four_role_approval_enforced": true,
    "microscopic_safety_blocking": true
  },
  "timestamp": "2026-09-12T19:30:00Z"
}
```

---

### Optimization & Possessions

#### `POST /api/v1/optimization/runs`
Executes an end-to-end multi-department optimization run (Tier 1 clustering + Tier 2 CP-SAT/ALNS + Tier 3 microscopic validation).

#### `GET /api/v1/optimization/runs/{run_id}`
Retrieves details, solver objective value, runtime, and scheduled demands of a previous run.

#### `POST /api/v1/optimization/possession-schedule`
Returns the comprehensive BDMS-compatible advisory possession schedule payload including primary possessions, shadow bundles, machines, crews, OHE electrical isolations, and train regulation plans.

---

### Recommendations & Human Sign-Off

#### `GET /api/v1/recommendations/{recommendation_id}`
Retrieves a specific recommendation docket with current 4-role approval progress and expiry timestamp.

#### `POST /api/v1/recommendations/{recommendation_id}/approve`
Records a statutory sign-off from an authorized controller role.
- **Rules**:
  - Enforces `If-Match` optimistic concurrency.
  - Enforces recommendation expiry (`410 Gone` if past expiry).
  - Validates `X-Actor-Role` against claimed role.
  - Recommendation is marked `APPROVED` and `SANCTIONED` **only when all 4 roles have approved**.

#### `POST /api/v1/recommendations/{recommendation_id}/reject`
Records a formal rejection. Requires minimum 5-character operational justification comment. Marks recommendation `REJECTED`.

#### `POST /api/v1/recommendations/{recommendation_id}/override`
Records an operational override with mandatory justification code and text (min 10 characters).

---

### Disruption Rescheduling

#### `POST /api/v1/disruptions`
Submits an operational disruption (e.g. train delay >=15 min, machine failure).
- Localizes within 30 km radius and 180 min forward horizon.
- Strictly preserves `GRANTED` and `IN_PROGRESS` possessions without shifting.
- Re-runs safety validation and produces advisory revisions.

---

### Audit & Cryptographic Verification

#### `GET /api/v1/advisory/audit`
Retrieves chronologically ordered audit records.

#### `GET /api/v1/advisory/audit/verify`
Verifies SHA-256 hash-chain integrity from the genesis record across all subsequent records.

---

### Geometry & KPIs

#### `GET /api/v1/network/geometry`
Returns canonical 3D network geometry (tracks, crossovers, signals, OHE masts, feeding posts) adhering to `geometry_schema_version: "1.0.0"`.

#### `GET /api/v1/kpis`
Returns comparative evaluation metrics (BUE, SBR, PII train delay, closure hours saved).

---

### Advisory Schedule Export

#### `GET /api/v1/advisory/export`
Query Parameters:
- `format`: `json` | `csv` | `html` | `pdf`
- `run_id`: (Optional) Optimization run ID.
- `recommendation_id`: (Optional) Specific recommendation ID.

Returns advisory package with mandatory `ADVISORY ONLY: HUMAN APPROVAL REQUIRED` notice, provenance, input snapshot hashes, and statutory operational limitation disclaimer.
