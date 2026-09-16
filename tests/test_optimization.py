"""Tests for the MILP solver backend selection (SCIP / Gurobi / heuristic)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _build_scenario():
    """Construct a minimal valid Scenario using the canonical pydantic models."""
    pyd = pytest.importorskip("pydantic")
    from src.data_pipeline.models import (
        Scenario, TrackBlock, Train, MaintenanceJob, Resource, TCIInputs, Department,
    )
    blocks = [TrackBlock(id=f"B{i}", chainage_start=float(i * 2), chainage_end=float((i + 1) * 2),
                         description=f"Block {i}") for i in range(4)]
    trains = [Train(id="TR1", category="express", scheduled_start=0.0, scheduled_end=12.0,
                    route=["B0", "B1", "B2"], min_travel_times={"B0": 1.0})]
    resources = [Resource(id="R1", name="BCM-1", capacity=2)]
    jobs = [
        MaintenanceJob(id="J1", department=Department.CIVIL, block_id="B0", duration=2.0,
                       required_resources={"R1": 1},
                       tci_inputs=TCIInputs(safety_severity=0.9, traffic_impact=0.5,
                                            degradation_indicator=0.6, overdue_days=10)),
        MaintenanceJob(id="J2", department=Department.CIVIL, block_id="B1", duration=2.0,
                       required_resources={"R1": 1},
                       tci_inputs=TCIInputs(safety_severity=0.7, traffic_impact=0.4,
                                            degradation_indicator=0.5, overdue_days=5)),
    ]
    return Scenario(blocks=blocks, trains=trains, jobs=jobs, resources=resources)


def test_milp_solver_scip_or_heuristic_runs():
    np = pytest.importorskip("numpy")
    from src.optimization.milp_solver import MaintenanceSchedulerMILP, SCIP_AVAILABLE
    scenario = _build_scenario()
    job_tcis = {"J1": 80.0, "J2": 60.0}
    solver = MaintenanceSchedulerMILP({"optimization": {"solver": "scip", "horizon_hours": 24}})
    result = solver.solve(scenario, job_tcis)
    assert "scheduled_jobs" in result
    assert result["status"] in ("optimal", "feasible", "heuristic_feasible", "infeasible")
    assert result["solver"] == ("PySCIPOpt" if SCIP_AVAILABLE else "NON_OPTIMAL_FALLBACK")


def test_milp_gurobi_backend_selection():
    np = pytest.importorskip("numpy")
    from src.optimization.milp_solver import MaintenanceSchedulerMILP, GUROBI_AVAILABLE
    scenario = _build_scenario()
    job_tcis = {"J1": 80.0, "J2": 60.0}
    solver = MaintenanceSchedulerMILP({"optimization": {"solver": "gurobi", "horizon_hours": 24}})
    if GUROBI_AVAILABLE:
        result = solver.solve(scenario, job_tcis)
        assert result["solver"] == "Gurobi"
    else:
        # graceful fallback to SCIP/heuristic; must not raise
        result = solver.solve(scenario, job_tcis)
        assert result["solver"] in ("PySCIPOpt", "NON_OPTIMAL_FALLBACK")


def test_milp_shadow_constraint_present():
    """The shadow consolidation constraint must exist in the SCIP model build."""
    np = pytest.importorskip("numpy")
    import src.optimization.milp_solver as m
    src_text = open(os.path.join(ROOT, "src", "optimization", "milp_solver.py")).read()
    assert "2 * shadow[k, t] <= quicksum(all_active)" in src_text
    # Gurobi port keeps the identical shadow constraint semantics
    assert "2 * shadow[k, t] <= gp.quicksum(all_active)" in src_text
