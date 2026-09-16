"""Standalone verification of all implemented modules (no pytest dependency)."""
import sys, os, json, tempfile
sys.path.insert(0, os.getcwd())
import numpy as np

def ok(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("  " + extra if extra else ""))

# ---- GNN ----
from src.ai_ml.gnn_encoder import build_corridor_graph, HeteroGNN, OUT_DIM
blocks = [dict(id=f"B{i}", chainage_start_km=float(i*5), chainage_end_km=float((i+1)*5),
               station="S1" if i < 2 else "S2", is_closed=False) for i in range(3)]
stations = [dict(id="S1", platforms=2, node_type="junction"),
            dict(id="S2", platforms=4, node_type="terminal")]
g = build_corridor_graph(blocks, stations)
vec = HeteroGNN().forward(g)
vec2 = HeteroGNN(seed=0).forward(g)
ok("gnn.shape", vec.shape == (OUT_DIM,), f"shape={vec.shape} OUT_DIM={OUT_DIM}")
ok("gnn.deterministic", np.allclose(vec, vec2))

# ---- SUMO + PPO ----
from src.simulation.sumo_interface import SUMODigitalTwin, ACT_SHIFT
sblocks = [dict(id=f"B{i}", chainage_start_km=float(i*2), chainage_end_km=float((i+1)*2)) for i in range(6)]
strains = [dict(id="T1", route=["B0","B1","B2","B3"], speed_kmh=40.0, category="express",
                scheduled_start=0.0, scheduled_end=12.0)]
twin = SUMODigitalTwin(sblocks, strains, horizon_hours=12.0)
twin.apply_schedule([dict(block_id="B1", start_time=1.0, end_time=3.0)])
obs = twin.reset()
ok("sumo.reset_len", len(obs) == 6 + 3, f"len={len(obs)}")
ns, r, done, info = twin.step(ACT_SHIFT)
ok("sumo.step_4tuple", isinstance(ns, (list, tuple, np.ndarray)) and isinstance(r, float) and isinstance(done, bool))

from src.ai_ml.ppo_agent import RailRLGym, train_ppo
gym = RailRLGym(twin, max_steps=24)
net, history = train_ppo(gym, episodes=5, max_steps=24, epochs=2, seed=1)
ok("ppo.history_len", len(history) == 5, f"len={len(history)}")
ok("ppo.history_float", all(isinstance(h, float) for h in history))

# ---- MILP ----
from src.optimization.milp_solver import MaintenanceSchedulerMILP, SCIP_AVAILABLE, GUROBI_AVAILABLE
from src.data_pipeline.models import (Scenario, TrackBlock, Train, MaintenanceJob,
                                      Resource, Department, TCIInputs)
mb = [TrackBlock(id=f"B{i}", chainage_start=float(i*2), chainage_end=float((i+1)*2)) for i in range(4)]
mt = [Train(id="TR1", category="express", scheduled_start=0.0, scheduled_end=12.0, route=["B0","B1","B2"])]
mr = [Resource(id="R1", name="BCM-1", capacity=2)]
mj = [MaintenanceJob(id=f"J{i}", department=Department.CIVIL, block_id=f"B{i%4}", duration=2.0,
                     required_resources={"R1":1},
                     tci_inputs=TCIInputs(safety_severity=0.9, traffic_impact=0.5,
                                          degradation_indicator=0.6, overdue_days=10)) for i in range(2)]
sc = Scenario(blocks=mb, trains=mt, jobs=mj, resources=mr)
solver = MaintenanceSchedulerMILP({"optimization": {"solver": "scip", "horizon_hours": 24}})
res = solver.solve(sc, {"J1": 80.0, "J2": 60.0})
ok("milp.scheduled_jobs_key", "scheduled_jobs" in res)
ok("milp.status", res.get("status") in ("optimal","feasible","heuristic_feasible","infeasible"), str(res.get("status")))
ok("milp.solver", res.get("solver") in ("PySCIPOpt","Gurobi","NON_OPTIMAL_FALLBACK"))

# ---- Strategic RBP ----
from src.optimization.strategic_rbp import StrategicRBPAllocator
sjobs = [MaintenanceJob(id=f"J{i}", department=Department.CIVIL, block_id=f"B{i%4}",
                       duration=(6.0 if i % 2 == 0 else 2.0), required_resources={"R1":1},
                       tci_inputs=TCIInputs(safety_severity=0.5, traffic_impact=0.5,
                                            degradation_indicator=0.5, overdue_days=5)) for i in range(10)]
sc2 = Scenario(blocks=mb, trains=[], jobs=sjobs, resources=mr)
alloc = StrategicRBPAllocator(horizon_weeks=52)
rr = alloc.allocate(sc2, job_tcis={j.id: 50.0 + float(i) for i, j in enumerate(sjobs)})
ok("rbp.horizon", rr.horizon_weeks == 52)
ok("rbp.coverage", len(rr.scheduled_job_ids) + len(rr.deferred_jobs) == 10,
   f"scheduled={len(rr.scheduled_job_ids)} deferred={len(rr.deferred_jobs)}")
ok("rbp.mega_present", rr.mega_block_count >= 1, f"mega={rr.mega_block_count}")

# ---- Stochastic ETA ----
from src.optimization.stochastic_eta import build_stochastic_pipeline
ftrains = [Train(id=f"TR{i}", category="freight" if i % 2 == 0 else "express",
                scheduled_start=0.0, scheduled_end=12.0, route=[f"B{i%4}"]) for i in range(4)]
sc3 = Scenario(blocks=mb, trains=ftrains, jobs=[], resources=mr)
evaluator, optimizer, analyzer = build_stochastic_pipeline(sc3, history=None, n_scenarios=40, seed=7)
rob = evaluator.evaluate(window_start=10.0, window_duration=4.0)
ok("stoch.expected_le_worst", rob.expected_delay_hours <= rob.worst_case_delay_hours + 1e-6,
   f"exp={rob.expected_delay_hours} worst={rob.worst_case_delay_hours}")
ok("stoch.clash_range", 0.0 <= rob.clash_free_probability <= 1.0, f"clash={rob.clash_free_probability}")

# ---- TCI XGBoost ----
from src.config_loader import load_config
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.data_pipeline.models import AssetConditionTelemetry, WeatherContext
cfg = load_config("config/settings.yaml")
score = TaskCriticalityScorer(cfg)
inp = TCIInputs(safety_severity=0.8, traffic_impact=0.6, degradation_indicator=0.5, overdue_days=20)
tel = AssetConditionTelemetry(block_id="B1", trc_tqi_score=35.0, usfd_flaw_severity="REM",
                              cumulative_gmt=55.0, days_since_tamping=90)
w = WeatherContext(ambient_temp_celsius=34, rail_temp_celsius=52)
tci, expl = score.calculate_tci(inp, telemetry=tel, weather=w, asset_age_years=12.0)
ok("tci.range", 0.0 <= tci <= 100.0, f"tci={round(tci,2)}")
ok("tci.mode", expl.model_mode == "xgboost_experimental", f"mode={expl.model_mode}")

# ---- MTTG ----
from src.simulation.mttg import MTTGCalculator, GrantRecord, unmeasured_summary
calc = MTTGCalculator()
s0 = calc.summary()
ok("mttg.empty_none", s0["mttg_measured"] is False and s0["mttg_minutes"] is None)
calc.add(GrantRecord(job_id="J1", requested_iso="2026-01-01T10:00:00+00:00",
                     granted_iso="2026-01-01T10:25:00+00:00"))
s1 = calc.summary()
ok("mttg.measured", s1["mttg_measured"] is True and s1["mttg_minutes"] == 20.0)

# ---- Pipeline ----
from src.data_pipeline.streaming import LocalEventReplaySource, StreamingIngestionHub
td = tempfile.mkdtemp()
log = os.path.join(td, "e.jsonl")
open(log, "w").write("\n".join(json.dumps(r) for r in [
    {"kind":"train_movement","train_id":"T1","chainage_km":3.0,"ts_ms":1},
    {"kind":"train_movement","train_id":"T1","chainage_km":4.0,"ts_ms":2},
    {"kind":"asset_telemetry","asset_id":"A1","block_id":"B2","ts_ms":3}]))
hub = StreamingIngestionHub([LocalEventReplaySource(log)])
hub.connect()
merged = hub.consume()
ok("stream.dedup", len(merged["train_movement"]) == 1 and merged["train_movement"][0]["chainage_km"] == 4.0)
ok("stream.telemetry", len(merged["asset_telemetry"]) == 1)

from src.data_pipeline.lakehouse import chainage_to_block_join, rolling_degradation_average, SparkStreamProcessor
out = chainage_to_block_join([{"chainage_km":3.0},{"chainage_km":7.5}],
    [{"block_id":"B1","chainage_start_km":0.0,"chainage_end_km":5.0},
     {"block_id":"B2","chainage_start_km":5.0,"chainage_end_km":10.0}])
ok("lake.join", out[0]["block_id"]=="B1" and out[1]["block_id"]=="B2")
ser = [{"ts_ms":i,"degradation_velocity":float(i)} for i in range(10)]
o2 = rolling_degradation_average(ser, window=3)
ok("lake.rolling", o2[-1]["rolling_degradation_velocity"] == 8.0)
lh = SparkStreamProcessor(warehouse_root=os.path.join(td,"lh"))
p = lh.write("m", [{"id":"r1","v":1},{"id":"r2","v":2}])
back = lh.read("m")
ok("lake.roundtrip", {r["id"] for r in back} == {"r1","r2"})

from src.serving.postgis_store import GeoStore, BlockRecord
st = GeoStore(f"sqlite:///{td}/s.db")
st.upsert_blocks([BlockRecord("B1",0.0,5.0,centroid_lat=25.0,centroid_lon=80.0),
                  BlockRecord("B2",5.0,10.0,centroid_lat=25.1,centroid_lon=80.1)])
near = st.blocks_within_radius(25.0,80.0,20.0)
ok("geo.near", {b.block_id for b in near} == {"B1","B2"})
bc = st.block_by_chainage(3.0)
ok("geo.chainage", bc.block_id == "B1")
st.close()

print("\nDONE")
