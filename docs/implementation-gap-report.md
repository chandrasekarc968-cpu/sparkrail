# SparkRail Implementation Gap Report

**Audit Date:** 2026-09-12  
**Commit:** `8a7c895a14d820d3b68a11edfea05f0512f21a27`  
**Auditor:** Automated code inspection + reproducible test execution  
**Methodology:** Full `git ls-tree`, `python -m compileall src`, `pytest -q`, `npm test -- --run`, `npm run build`

---

## Baseline Verification Results

| Gate | Command | Result |
|------|---------|--------|
| Python Compilation | `python -m compileall src` | ✅ Exit code 0, all 7 packages compiled |
| Backend Tests | `pytest -q` | ✅ **121 passed** in 40.29s |
| Frontend Tests | `npm test -- --run` | ✅ **49 passed** (11 test files) in 3.55s |
| Frontend Build | `npm run build` | ✅ Built in 596ms (1,829 kB bundle) |

---

## Module-by-Module Verification

### 1. Domain Contracts — ✅ VERIFIED

**File:** `src/data_pipeline/models.py` (1,209 lines)

All 18 required strongly-typed models are implemented with Pydantic validators:

| Model | Status | Key Validations |
|-------|--------|-----------------|
| `TrackSection` / `BlockSection` | ✅ | Chainage range, division code, ID sync |
| `Station` | ✅ | Code, platforms ≥1, loop capacity ≥0 |
| `Interlocking` | ✅ | Route/point counts, signal IDs, operational flag |
| `ElementarySection` | ✅ | Track section mapping, voltage, energization state |
| `IsolatorSwitch` | ✅ | Section binding, location chainage, motorization |
| `MaintenanceDemand` | ✅ | Chainage bounds, duration >0, lifecycle sync |
| `TrainMovement` | ✅ | Priority enum, non-negative delay, route ≥1 |
| `Machine` | ✅ | Transit speed, setup/clearing time |
| `Crew` | ✅ | HOER: max 12h shift, min 12h rest, certified sections |
| `Possession` | ✅ | Status transitions, start < end, `transition_to()` method |
| `ShadowPossessionBundle` | ✅ | Primary/secondary demands, window bounds |
| `OptimizationRun` | ✅ | Solver status, runtime ≥0, ISO-8601 timestamps |
| `Recommendation` | ✅ | 4-role approval chain, expiry, version counter |
| `ApprovalAction` | ✅ | Role enum, mandatory comments, ISO-8601 |
| `OperationalOverride` | ✅ | Reason code, justification min 10 chars, audit hash |
| `DisruptionEvent` | ✅ | 30km corridor radius, 180min horizon, severity |
| `AuditEvent` | ✅ | SHA-256 hash chain, previous/current hash |
| `DataProvenance` | ✅ | Source system, freshness, confidence, validation errors |

**Lifecycle transitions** (`DRAFT→PROPOSED→SANCTIONED→GRANTED→IN_PROGRESS→COMPLETED`) verified with `validate_possession_transition()`. GRANTED→CANCELLED and IN_PROGRESS→DRAFT are correctly rejected.

**Schedule immutability** enforced via `validate_possession_schedule_immutability()`: GRANTED possessions reject any start/end time change; IN_PROGRESS reject shortening or start shift.

**ISO-8601 timezone validation** enforced on all timestamp fields via `validate_iso8601_timestamp()`.

**Tests:** `test_canonical_models_and_harmonization.py`, `test_full_pilot_compliance.py::TestPossessionLifecycleAndImmutability` (5 tests)

---

### 2. Synthetic Source Adapters — ✅ VERIFIED

**Files:** `src/data_pipeline/adapters/base.py`, `src/data_pipeline/adapters/cris_adapters.py` (690 lines)

| Adapter | Deterministic Synthetic | Retries/Backoff | mTLS | Dead-Letter | Stale Detection | Contradiction | Idempotency |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `TMSAdapter` | ✅ | ✅ 3x backoff | ✅ cert+key | ✅ JSONL | ✅ | ✅ | ✅ |
| `TDMSAdapter` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `SMMSAdapter` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `COAAdapter` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `RTISAdapter` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `BDMSAdapter` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

- Real CRIS mode requires `SPARKRAIL_LIVE_MODE=true` + credentials env vars
- `CRISReplayEngine` generates 8 canonical event types deterministically
- `process_event()`: idempotent dedup by event_id, out-of-order stale rejection, contradiction detection

**Tests:** `test_cris_adapters.py` (7 tests), `test_full_pilot_compliance.py::TestCRISAdaptersAndReplay` (3 tests)

---

### 3. Harmonization — ✅ VERIFIED

**File:** `src/data_pipeline/harmonization.py` (417 lines)

| Feature | Status |
|---------|--------|
| km/metre chainage normalization | ✅ Handles float, "124+500", "124/18", dict, "KM 124.5" |
| Asset-to-track mapping | ✅ |
| TDMS elementary-section-to-track mapping | ✅ |
| Isolator topology | ✅ |
| SMMS signalling/interlocking dependencies | ✅ |
| RTIS position projection onto track graph | ✅ Orthogonal corridor projection |
| Confidence scores | ✅ 0.0-1.0 |
| Ambiguity and out-of-range detection | ✅ |
| Canonical directed railway multigraph | ✅ NetworkX MultiDiGraph |

**Tests:** `test_canonical_models_and_harmonization.py`, `test_cris_adapters.py::TestSpatialHarmonization`

---

### 4. TCI Scoring — ✅ VERIFIED

**File:** `src/ai_ml/criticality_scorer.py` (330 lines)

- 6-factor deterministic score: safety, traffic impact, degradation, deferral, inspection urgency, data confidence
- AHP pairwise matrix derivation (4x4 and 6x6)
- Conservative missing-data imputation
- XGBoost gated behind feature flag + model file + checksum verification
- Non-linear overdue penalty, explainable breakdown

**Tests:** `test_tci.py` (12 tests)

---

### 5. Tier 1 Clustering — ✅ VERIFIED

**File:** `src/optimization/clustering.py` (371 lines)

- Spatiotemporal distance metric, compatibility graph, Bron-Kerbosch maximal cliques with pivoting
- OHE/S&T incompatibility, heavy machine exclusivity, spatial containment, temporal nesting
- Explainable rejection reasons

**Tests:** `test_three_tier_optimization.py::TestTier1Clustering` (2 tests)

---

### 6. Tier 2 Allocation — ✅ VERIFIED

**File:** `src/optimization/macro_allocator.py` (546 lines)

- OR-Tools CP-SAT formulation with deterministic ALNS fallback
- ALNS operators: worst-delay removal, corridor-sweep removal, regret-3 insertion
- Premium train protection, fixed block immutability, machine exclusivity
- Never labels heuristic as optimal, SHA-256 input hash

**Tests:** `test_three_tier_optimization.py::TestTier2` (2 tests), `test_milp.py` (6 tests)

---

### 7. Tier 3 Microscopic Safety Validation — ✅ VERIFIED

**File:** `src/optimization/microscopic_validator.py` (256 lines)

- Train travel times, headways, track occupancy, fixed-block collisions
- OHE elementary-section isolation, electric-train exclusion
- Machine relocation, crew shift/rest (HOER), TSL opposing movements
- Premium-train delay limits, Benders-style cuts (6 types)
- Failed validation blocks executable recommendation

**Tests:** `test_three_tier_optimization.py::TestTier3` (1 test), `test_safety_validator.py` (5 tests)

---

### 8. Disruption Rescheduling — ✅ VERIFIED

**File:** `src/optimization/disruption_engine.py` (266 lines)

- Triggers: premium delay ≥15min, equipment failure, weather, upstream, stale state
- 30km corridor radius, 180min forward horizon
- Freezes unaffected decisions, shifts SANCTIONED only
- GRANTED/IN_PROGRESS byte-for-byte preservation
- TSL topology validation (not "_TSL" append)

**Tests:** `test_disruption_engine.py` (3 tests), `test_full_pilot_compliance.py::TestTopologicalTSLDisruption` (1 test)

---

### 9. Governance API — ✅ VERIFIED

**File:** `src/api/advisory.py` (1,025 lines)

All 11 endpoints implemented. 4-role statutory approval, no hardcoded payloads, dynamic payload generation, idempotency keys, optimistic concurrency, recommendation expiry, SHA-256 tamper-evident audit chain, advisory-only default.

**Tests:** `test_advisory_approval.py` (4), `test_v1_api.py` (5), `test_full_pilot_compliance.py` (9 governance + audit tests)

---

### 10. Test Summary

| Category | Count | Status |
|----------|-------|--------|
| Backend Tests | 121 | ✅ ALL PASS |
| Frontend Tests | 49 | ✅ ALL PASS |
| **Total** | **170** | **✅ ALL PASS** |

All tests run without live CRIS, Kafka, PostgreSQL, SUMO, Gurobi, or private credentials.

---

### 11. Feature Classification

| Category | Features |
|----------|----------|
| **Verified Synthetic MVP** | 18 domain models, 6 CRIS adapters, harmonization, TCI scorer, Tier 1/2/3 optimization, disruption engine, governance API, SHA-256 audit chain, 3D frontend |
| **Configuration-Gated** | Live CRIS endpoints, mTLS, Kafka streaming, SUMO simulation |
| **Experimental / Feature-Gated** | XGBoost degradation scoring, GNN encoder |
| **Unimplemented** | Station loop meet capacity modeling (partial), SUMO co-sim, real Kafka consumer |

---

## Non-Negotiable Safety Rule Compliance

| Rule | Status |
|------|--------|
| Advisory-only | ✅ All outputs `ADVISORY_ONLY_NOT_EXECUTED` |
| GRANTED/IN_PROGRESS immutable | ✅ |
| Unapproved not executable | ✅ Requires all 4 roles |
| Real CRIS disabled by default | ✅ |
| Synthetic fixtures locally | ✅ |
| Stale/invalid data flagged | ✅ |
| Never fabricate geometry | ✅ |
| No benchmark claims without tests | ✅ |

---

**Audited Commit:** `8a7c895a14d820d3b68a11edfea05f0512f21a27`  
**Remaining Gaps:** Station loop capacity modeling (partial), SUMO co-simulation (out of scope), Kafka consumer (config-gated)  
**Pilot-Ready Status:** ✅ Advisory-only synthetic MVP verified
