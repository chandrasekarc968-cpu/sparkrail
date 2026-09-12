# SparkRail Implementation Gap & Production Readiness Report

**Audit Date:** 2026-09-12  
**Commit / Target:** Day-One Deployable Railway-Planning Plugin  
**Auditor:** Automated Code Inspection + Reproducible Test Execution  
**Corridor:** Subedarganj (`SFG`) to Mirzapur (`MZP`), 80 km Electrified Double-Line Corridor, Prayagraj Division (NCR)  

---

## 1. Verified Baseline Metrics

| Gate | Verification Command | Status | Outcome |
|---|---|---|---|
| **Python Compilation** | `python -m compileall src tests` | ✅ PASS | 0 errors across all 7 modules and tests |
| **Backend Pytest Suite** | `python -m pytest` | ✅ PASS | **146 passed** (19 test files) in 44.5s |
| **Frontend Test Suite** | `npm test -- --run` | ✅ PASS | **63 passed** (12 test files) in 3.52s |
| **Frontend Production Build** | `npm run build` | ✅ PASS | `tsc -b && vite build` built in 554ms |
| **Static Deployment Artifacts** | `frontend/dist/` audit | ✅ PASS | `index.html` (relative paths `./assets/...`), `404.html` SPA redirect |
| **Plugin Mode Safety** | `test_plugin_modes_and_governance.py` | ✅ PASS | 7/7 tests passed in 1.66s |

---

## 2. Day-One Plugin Status Classification

### A. Day-One Synthetic / Demo Ready — ✅ COMPLETE
- Offline, fully deterministic synthetic corridor data seeded via `python -m src.plugin generate-seed`.
- Full 80 km electrified double-line network fixture (`Subedarganj` to `Mirzapur`).
- Renders 3D track centerlines, platforms, loops, crossovers, signals, track circuits, OHE masts, feeding posts, and trains.
- In-memory mock repositories and simulation engine.
- Interactive timeline scrubber with 1x, 5x, 15x, and 60x playback speeds.
- Accessible 2D SVG fallback when WebGL is unavailable.

### B. Day-One Shadow Mode Ready — ✅ COMPLETE
- Operates strictly alongside existing BDMS/railway operations without issuing physical commands.
- Ingests read-only snapshots from TMS, TDMS, SMMS, COA, RTIS, and BDMS adapters.
- Multi-attribute Task Criticality Index (TCI) scoring on real or static defect data.
- Tier 1 spatiotemporal clustering and Bron-Kerbosch maximal clique consolidation.
- Tier 2 CP-SAT macro corridor allocation with deterministic ALNS fallback.
- Tier 3 microscopic safety validation enforcing block headways, OHE isolation, opposing train clearance, and HOER crew rest.
- Statutory 4-role approval workflow (`CTPC`, `SR_DOM`, `SECTION_CONTROLLER`, `STATION_MASTER`).
- Cryptographic SHA-256 tamper-evident audit trail with continuous verification (`GET /api/v1/advisory/audit/verify`).
- Statutory multi-format export docket in JSON, CSV, printable HTML, and PDF-ready format.

### C. Configuration-Gated Features — 🔒 SECURE & VERIFIED
- **Live CRIS API Integration**:
  - Gated behind `SPARKRAIL_MODE=live` AND `SPARKRAIL_LIVE_ENABLED=true`.
  - Strictly requires client mTLS certificates (`CRIS_MTLS_CERT_PATH`), private key (`CRIS_MTLS_KEY_PATH`), and trusted CA bundle (`CRIS_CA_BUNDLE`).
  - Automatically fails safe if any certificate is missing or invalid.
  - Disabled by default.

### D. Experimental Features — 🧪 ISOLATED
- SUMO microscopic simulation adapter (`src/simulation/sumo_interface.py`): Isolated behind `simulation.use_sumo=false` flag.
- GNN corridor encoder (`src/ai_ml/gnn_encoder.py`): Research prototype; fallback to analytical TCI scorer is active in production.

### E. Prohibited Capabilities (Day-One Non-Negotiables) — 🚫 PROHIBITED BY DESIGN
The following capabilities are deliberately **not implemented** and possess zero code paths:
- Automatic signal clearing.
- Point-machine actuation.
- Traction breaker trip/close commands.
- Train dispatch commands.
- Automatic physical block grants.
- Direct mutation of BDMS production database records.
- Automatic shifting or shortening of `GRANTED` or `IN_PROGRESS` possessions.

---

## 3. The 15 Target Architecture Modules: Audit Matrix

| Module | Location | Test Coverage | Status |
|---|---|---|---|
| **1. Plugin Shell** | `src/plugin.py`, `src/config.py` | `test_plugin_modes_and_governance.py` | ✅ VERIFIED |
| **2. API Gateway** | `src/api/main.py` | `test_api.py`, `test_v1_api.py` | ✅ VERIFIED |
| **3. Source Adapters** | `src/data_pipeline/adapters/` | `test_cris_adapters.py` | ✅ VERIFIED |
| **4. Data Harmonization** | `src/data_pipeline/harmonization.py` | `test_canonical_models_and_harmonization.py` | ✅ VERIFIED |
| **5. Canonical Topology** | `src/data_pipeline/topology.py` | `test_canonical_topology.py` | ✅ VERIFIED |
| **6. Task Criticality** | `src/ai_ml/criticality_scorer.py` | `test_tci.py` | ✅ VERIFIED |
| **7. Tier 1 Clustering** | `src/optimization/clustering.py` | `test_three_tier_optimization.py` | ✅ VERIFIED |
| **8. Tier 2 Allocator** | `src/optimization/macro_allocator.py` | `test_milp.py` | ✅ VERIFIED |
| **9. Tier 3 Validator** | `src/optimization/microscopic_validator.py` | `test_safety_validator.py` | ✅ VERIFIED |
| **10. Disruption Engine** | `src/optimization/disruption_engine.py` | `test_disruption_engine.py` | ✅ VERIFIED |
| **11. Governance & Approval**| `src/api/advisory.py` | `test_advisory_approval.py` | ✅ VERIFIED |
| **12. Audit Service** | `src/api/advisory.py` | `test_plugin_modes_and_governance.py` | ✅ VERIFIED |
| **13. KPI & Observability** | `src/simulation/evaluator.py` | `kpi.test.ts`, `test_core.py` | ✅ VERIFIED |
| **14. 3D Digital Twin** | `frontend/src/` | `productionReadiness3D.test.tsx` | ✅ VERIFIED |
| **15. Export Service** | `src/api/export_service.py` | `test_plugin_modes_and_governance.py` | ✅ VERIFIED |

---

## 4. Remaining Operational Constraints

1. **Static Frontend Hosting**: GitHub Pages can host only the static client SPA (`frontend/dist/`). Enterprise shadow deployments requiring live optimization solving must host the Python backend independently on an internal server or container.
2. **Deterministic Fallbacks**: In environments where OR-Tools CP-SAT or SCIP binaries are unavailable, the allocator automatically and deterministically falls back to the Adaptive Large Neighborhood Search (ALNS) heuristic. Results are explicitly flagged as `FEASIBLE` and never falsely claimed as `OPTIMAL`.
3. **Statutory Human Review**: All generated possession packages remain advisory decision-support artifacts until physically sanctioned and granted by authorized railway personnel.
