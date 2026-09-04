import os
import math
import copy
import requests
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

class UnifiedApiClient:
    """
    Transparent API client that tests against the live HTTP socket if available,
    falling back to FastAPI's TestClient for offline local testing.
    Ensures zero boundary mocking while retaining offline test suite capability.
    """
    def __init__(self):
        self.base_url = os.environ.get("SPARKRAIL_API_URL", "http://127.0.0.1:8000")
        self.is_live = False
        try:
            r = requests.get(f"{self.base_url}/health", timeout=1.0)
            if r.status_code == 200:
                self.is_live = True
        except Exception:
            self.is_live = False
        self.test_client = TestClient(app)

    def get(self, path: str, headers: dict = None, **kwargs):
        if self.is_live:
            return requests.get(f"{self.base_url}{path}", headers=headers, **kwargs)
        return self.test_client.get(path, headers=headers, **kwargs)

    def post(self, path: str, json: dict = None, headers: dict = None, data: str = None, **kwargs):
        if self.is_live:
            return requests.post(f"{self.base_url}{path}", json=json, headers=headers, data=data, **kwargs)
        return self.test_client.post(path, json=json, headers=headers, data=data, **kwargs)

@pytest.fixture(scope="module")
def api():
    return UnifiedApiClient()


def test_health_contract(api):
    """
    GET /health contract verification.
    Asserts HTTP 200, required fields, and solver engine designation.
    """
    resp = api.get("/health")
    assert resp.status_code == 200
    data = resp.json()

    for field in ["status", "version", "geometry_schema_version", "solver_available", "solver_name", "data_mode", "commit_sha"]:
        assert field in data, f"Missing field '{field}' in /health response"

    assert data["status"] == "ok"
    assert data["version"] != ""
    assert data["geometry_schema_version"] == "1.0.0"
    assert data["solver_name"] in ("PySCIPOpt", "NON_OPTIMAL_FALLBACK")
    assert isinstance(data["solver_available"], bool)


def test_generate_data_contract(api):
    """
    POST /data/generate contract verification.
    Asserts HTTP 200, matching output counts, and present output_path.
    """
    payload = {
        "seed": 26027,
        "num_blocks": 8,
        "num_jobs": 20,
        "num_trains": 10
    }
    resp = api.post("/data/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["blocks_count"] == 8
    assert data["jobs_count"] == 20
    assert data["trains_count"] == 10
    assert data["seed"] == 26027
    assert "output_path" in data and len(data["output_path"]) > 0


def test_scenario_contract(api):
    """
    GET /scenario contract verification.
    Asserts topology connectivity, block references, and stable geometry.
    """
    resp = api.get("/scenario")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data.get("blocks", [])) > 0
    assert len(data.get("jobs", [])) > 0
    assert len(data.get("trains", [])) > 0
    assert len(data.get("resources", [])) > 0

    block_ids = {b["id"] for b in data["blocks"]}

    for b in data["blocks"]:
        assert "id" in b and len(b["id"]) > 0
        assert "chainage_start" in b and "chainage_end" in b
        assert b["chainage_end"] > b["chainage_start"]
        assert math.isfinite(b["chainage_start"]) and math.isfinite(b["chainage_end"])

    for job in data["jobs"]:
        assert job["block_id"] in block_ids, f"Job {job['id']} references non-existent block {job['block_id']}"

    for train in data["trains"]:
        for blk in train["route"]:
            assert blk in block_ids, f"Train {train['id']} route references unknown block {blk}"


def test_geometry_contract(api):
    """
    GET /network/geometry contract verification.
    Asserts 3D spatial geometry, valid finite coordinates, no duplicate nodes, and connectivity.
    """
    scen_resp = api.get("/scenario")
    assert scen_resp.status_code == 200
    block_ids = {b["id"] for b in scen_resp.json()["blocks"]}

    resp = api.get("/network/geometry")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data.get("tracks", [])) > 0
    assert len(data.get("nodes", [])) > 0

    node_ids = set()
    for node in data["nodes"]:
        assert "id" in node
        assert node["id"] not in node_ids, f"Duplicate node ID detected: {node['id']}"
        node_ids.add(node["id"])
        assert "position" in node
        for axis in ("x", "y", "z"):
            assert math.isfinite(node["position"][axis])

    for track in data["tracks"]:
        assert "block_id" in track
        assert track["block_id"] in block_ids, f"Track block {track['block_id']} not in scenario"
        for pt in ("start_coord", "end_coord"):
            assert pt in track
            for axis in ("x", "y", "z"):
                assert math.isfinite(track[pt][axis])

    assert len(node_ids) >= 2


def test_planning_capabilities_contract(api):
    """
    GET /planning/capabilities contract verification.
    Asserts solver designation, fallback status, 3D support, and horizon days.
    """
    resp = api.get("/planning/capabilities")
    assert resp.status_code == 200
    data = resp.json()

    assert "solver_available" in data
    assert "solver_name" in data
    assert "fallback_active" in data
    assert "supports_3d_geometry" in data
    assert "routes_available" in data
    assert "supported_horizons_days" in data

    if data["fallback_active"]:
        assert data["solver_name"] == "NON_OPTIMAL_FALLBACK"
    else:
        assert data["solver_name"] == "PySCIPOpt"


def test_score_contract(api):
    """
    POST /score contract verification.
    Asserts TCI normalization [0, 100], component breakdown, and model metadata.
    """
    scen = api.get("/scenario").json()
    resp = api.post("/score", json={"scenario": scen})
    assert resp.status_code == 200
    data = resp.json()

    assert len(data.get("scored_jobs", [])) > 0
    assert "model_mode" in data and len(data["model_mode"]) > 0
    assert "model_version" in data and len(data["model_version"]) > 0

    for item in data["scored_jobs"]:
        assert "job_id" in item
        assert "tci" in item
        tci = item["tci"]
        assert 0.0 <= tci <= 100.0, f"Job {item['job_id']} TCI {tci} out of bounds [0, 100]"

        expl = item.get("explanation", {})
        assert any(k in expl for k in ("safety_component", "safety_score")), "Missing safety component"
        assert any(k in expl for k in ("delay_component", "delay_score")), "Missing delay component"
        assert any(k in expl for k in ("degradation_component", "degradation_score")), "Missing degradation component"
        assert any(k in expl for k in ("overdue_component", "overdue_score")), "Missing overdue component"
        for k in ("safety_component", "delay_component", "degradation_component", "overdue_component"):
            if k in expl:
                val = expl[k]
                assert 0.0 <= val <= 100.0, f"Explanation component {k} out of bounds: {val}"


def test_optimize_contract(api):
    """
    POST /optimize contract verification.
    Asserts job scheduling, end > start, no fixed block overlap, premium delay limit, and solver status.
    """
    scen = api.get("/scenario").json()
    opt_req = {
        "scenario": scen,
        "seed": 26027,
        "freeze_week1": False
    }
    resp = api.post("/optimize", json=opt_req)
    assert resp.status_code == 200
    data = resp.json()

    for field in ("status", "solver", "scheduled_jobs", "unscheduled_jobs", "train_delays", "total_closure_time", "runtime_seconds"):
        assert field in data, f"Missing field '{field}' in /optimize response"

    if data["solver"] == "NON_OPTIMAL_FALLBACK":
        assert data["status"] != "optimal", "Fallback optimizer must never claim optimal status"
    else:
        assert data["status"] in ("optimal", "feasible")

    fixed_blocks = scen.get("fixed_blocks", [])

    for sj in data["scheduled_jobs"]:
        for f in ("job_id", "block_id", "start_time", "end_time", "department", "tci"):
            assert f in sj, f"Scheduled job missing field {f}"
        assert sj["end_time"] > sj["start_time"], f"Job {sj['job_id']} invalid duration"

        for fb in fixed_blocks:
            if fb["block_id"] == sj["block_id"]:
                if sj["job_id"] in ("J_FIXED_1", "J_FIXED_2") or sj.get("is_fixed"):
                    continue
                overlap = not (sj["end_time"] <= fb["start_time"] or sj["start_time"] >= fb["end_time"])
                assert not overlap, f"Non-fixed Job {sj['job_id']} overlaps fixed block {fb['id']} on {fb['block_id']}"

    train_delays = data.get("train_delays", {})
    for t in scen.get("trains", []):
        if t.get("is_premium", False):
            delay = train_delays.get(t["id"], 0.0)
            assert delay <= 1.0 + 1e-4, f"Premium train {t['id']} delay {delay} exceeds 1.0h limit"


def test_schedule_persistence_contract(api):
    """
    GET /schedule/latest and /schedule/unknown-id contract verification.
    Asserts persistence of latest schedule and 404 for unknown IDs.
    """
    latest_resp = api.get("/schedule/latest")
    assert latest_resp.status_code == 200
    latest = latest_resp.json()
    assert "scheduled_jobs" in latest
    assert "status" in latest

    unknown_resp = api.get("/schedule/unknown-nonexistent-id-999")
    assert unknown_resp.status_code == 404


def test_evaluate_contract(api):
    """
    POST /evaluate contract verification.
    Asserts presence and mathematical validity of all KPI dimensions.
    """
    resp = api.post("/evaluate", json={"schedule_id": "latest"})
    assert resp.status_code == 200
    data = resp.json()

    assert "bue_percent" in data
    assert "sbr_percent" in data
    assert "pii_delays" in data
    assert "asset_downtime_reduction_percent" in data
    assert "mttg_minutes" in data
    assert "tci_coverage_percent" in data
    assert "total_closure_hours" in data
    assert "consolidated_blocks" in data
    assert "solver_runtime_seconds" in data

    assert data["bue_percent"] >= 0.0 and math.isfinite(data["bue_percent"])
    assert data["sbr_percent"] >= 0.0 and math.isfinite(data["sbr_percent"])
    assert data["pii_delays"] >= 0.0 and math.isfinite(data["pii_delays"])
    assert data["total_closure_hours"] >= 0.0 and math.isfinite(data["total_closure_hours"])
    assert data["consolidated_blocks"] >= 0
    assert data["tci_coverage_percent"] >= 0.0 and math.isfinite(data["tci_coverage_percent"])


def test_request_id_contract(api):
    """
    X-Request-ID propagation contract verification.
    Asserts header return and custom ID echo.
    """
    resp = api.get("/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers

    custom_id = "test-sparkrail-e2e-trace-7777"
    resp2 = api.get("/health", headers={"X-Request-ID": custom_id})
    assert resp2.status_code == 200
    assert resp2.headers.get("x-request-id") == custom_id


def test_validation_error_contract(api):
    """
    HTTP 422 contract verification for malformed payloads.
    Asserts sanitized error response without leaking stack traces or internal paths.
    """
    # 1. Invalid data generate
    resp1 = api.post("/data/generate", json={"seed": "not-an-int", "num_blocks": -5})
    assert resp1.status_code == 422
    body1 = resp1.text.lower()
    assert "traceback" not in body1
    assert "c:\\" not in body1 and "/home/" not in body1

    # 2. Invalid score
    resp2 = api.post("/score", json={"scenario": {"blocks": "invalid-shape"}})
    assert resp2.status_code == 422
    body2 = resp2.text.lower()
    assert "traceback" not in body2
    assert "c:\\" not in body2

    # 3. Invalid optimize
    resp3 = api.post("/optimize", json={"weights": {"safety": "invalid"}})
    assert resp3.status_code == 422
    body3 = resp3.text.lower()
    assert "traceback" not in body3
    assert "c:\\" not in body3


def test_determinism_contract(api):
    """
    Determinism contract verification for identical seed across pipeline.
    """
    api.post("/data/generate", json={"seed": 26027, "num_blocks": 8, "num_jobs": 20, "num_trains": 10})
    scen1 = api.get("/scenario").json()
    opt1 = api.post("/optimize", json={"scenario": scen1, "seed": 26027}).json()
    eval1 = api.post("/evaluate", json={"schedule_id": "latest"}).json()

    api.post("/data/generate", json={"seed": 26027, "num_blocks": 8, "num_jobs": 20, "num_trains": 10})
    scen2 = api.get("/scenario").json()
    opt2 = api.post("/optimize", json={"scenario": scen2, "seed": 26027}).json()
    eval2 = api.post("/evaluate", json={"schedule_id": "latest"}).json()

    # Normalize runtime and timestamps
    def normalize_sched(s):
        c = copy.deepcopy(s)
        c.pop("runtime_seconds", None)
        if "kpi_metrics" in c and isinstance(c["kpi_metrics"], dict):
            c["kpi_metrics"].pop("solver_runtime_seconds", None)
        return c

    def normalize_eval(e):
        c = copy.deepcopy(e)
        c.pop("solver_runtime_seconds", None)
        return c

    assert len(opt1["scheduled_jobs"]) == len(opt2["scheduled_jobs"])
    assert normalize_sched(opt1) == normalize_sched(opt2)
    assert normalize_eval(eval1) == normalize_eval(eval2)


def test_frontend_backend_schema_contract(api):
    """
    Frontend TypeScript / Backend JSON schema contract verification.
    Ensures backend responses directly satisfy frontend TypeScript interfaces.
    """
    # 1. /scenario -> Scenario
    scen = api.get("/scenario").json()
    assert isinstance(scen["blocks"], list)
    assert isinstance(scen["trains"], list)
    assert isinstance(scen["jobs"], list)
    assert isinstance(scen["resources"], list)
    assert isinstance(scen["fixed_blocks"], list)

    for b in scen["blocks"]:
        assert isinstance(b["id"], str)
        assert isinstance(b.get("description", b.get("name", "")), str)
        assert isinstance(b.get("chainage_start", b.get("chainage_start_km", 0)), (int, float))
        assert isinstance(b.get("chainage_end", b.get("chainage_end_km", 0)), (int, float))
        assert isinstance(b["speed_restriction_kmh"], (int, float))
        assert isinstance(b["electrification_status"], str)
        assert isinstance(b["signaling_type"], str)

    # 2. /network/geometry -> NetworkGeometryResponse
    geo = api.get("/network/geometry").json()
    assert geo["geometry_schema_version"] == "1.0.0"
    assert "coordinate_system" in geo
    assert geo["coordinate_system"]["name"] == "LOCAL_CORRIDOR"
    assert geo["coordinate_system"]["crs"] == "LOCAL_CORRIDOR"
    assert geo["coordinate_system"]["units"] == "meters"
    assert geo["coordinate_system"]["axis_order"] == ["x", "y", "z"]
    assert geo["coordinate_system"]["handedness"] == "right-handed"
    assert geo["coordinate_system"]["geometry_source"] == "synthetic"
    assert isinstance(geo["division"], str)
    assert isinstance(geo["line_name"], str)
    assert isinstance(geo["total_length_km"], (int, float))
    assert isinstance(geo["is_synthetic"], bool)
    assert isinstance(geo["nodes"], list)
    assert isinstance(geo["tracks"], list)
    assert isinstance(geo["signals"], list)
    assert isinstance(geo["ohe_masts"], list)
    assert isinstance(geo["assets"], list)
    assert len(geo["assets"]) > 0
    assert "position" in geo["assets"][0] and geo["assets"][0]["position"] is not None

    # 3. /schedule/latest -> OptimizedSchedule
    sched = api.get("/schedule/latest").json()
    assert isinstance(sched["status"], str)
    assert isinstance(sched["solver"], str)
    assert isinstance(sched["scheduled_jobs"], list)
    assert isinstance(sched["unscheduled_jobs"], list)
    assert isinstance(sched["train_delays"], dict)
    assert isinstance(sched["total_closure_time"], (int, float))
    assert isinstance(sched["objective_value"], (int, float))

    # 4. /assets/health -> AssetHealthRecord[]
    assets = api.get("/assets/health").json()
    assert isinstance(assets, list)
    for a in assets:
        assert isinstance(a["asset_id"], str)
        assert isinstance(a["block_id"], str)
        assert isinstance(a["health_score"], (int, float))
        assert isinstance(a["defect_severity"], str)

    # 5. /events -> SystemEvent[]
    events = api.get("/events").json()
    assert isinstance(events, list)
    for ev in events:
        assert isinstance(ev["id"], str)
        assert isinstance(ev["timestamp"], str)
        assert isinstance(ev["level"], str)
        assert isinstance(ev["message"], str)
