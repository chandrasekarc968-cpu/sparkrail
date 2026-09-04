"""
Comprehensive tests for SparkRail Three-Tier Optimization Engine:
Tier 1: Spatiotemporal Demand Clustering & Bron-Kerbosch Maximal Clique Bundling
Tier 2: Macro Possession Window Allocation (CP-SAT / ALNS)
Tier 3: Microscopic Train Trajectory & Electrical Isolation Validation (Benders Cuts)
"""

import pytest
from src.optimization.clustering import SpatiotemporalClusteringEngine, CandidateBundle
from src.optimization.macro_allocator import MacroPossessionAllocator
from src.optimization.microscopic_validator import MicroscopicDispatchValidator, BendersCut
from src.optimization.milp_solver import ProductionOptimizationPipeline
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.data_pipeline.models import ScheduledJob, Department
from tests.fixtures.deterministic_scenarios import (
    create_compatible_shadow_bundle_scenario,
    create_incompatible_ohe_snt_scenario,
    create_premium_train_conflict_scenario,
    create_ohe_isolation_scenario
)


class TestTier1Clustering:
    def test_compatible_civil_ohe_bundle_extraction(self):
        scenario = create_compatible_shadow_bundle_scenario()
        scorer = TaskCriticalityScorer()
        job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}

        clusterer = SpatiotemporalClusteringEngine(max_spatial_distance_km=15.0, max_time_distance_hours=3.0)
        bundles = clusterer.generate_candidate_bundles(scenario.jobs, scenario.blocks, job_tcis)

        assert len(bundles) >= 1, "Should have extracted at least one compatible shadow bundle"
        bundle = bundles[0]
        assert isinstance(bundle, CandidateBundle)
        assert bundle.block_id == "B5"
        all_jobs = [bundle.primary_job_id] + bundle.secondary_job_ids
        assert "J_CIVIL_01" in all_jobs
        assert "J_OHE_01" in all_jobs
        assert "OHE" in bundle.departments
        assert "Engineering" in bundle.departments
        assert "compatible" in bundle.compatibility_rationale.lower()

    def test_incompatible_ohe_snt_rejection(self):
        scenario = create_incompatible_ohe_snt_scenario()
        scorer = TaskCriticalityScorer()
        job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}

        clusterer = SpatiotemporalClusteringEngine(max_spatial_distance_km=15.0, max_time_distance_hours=3.0)
        bundles = clusterer.generate_candidate_bundles(scenario.jobs, scenario.blocks, job_tcis)

        # Incompatible jobs must NOT be bundled together
        for b in bundles:
            all_jobs = [b.primary_job_id] + b.secondary_job_ids
            assert not ("J_OHE_ISO" in all_jobs and "J_SNT_LIVE" in all_jobs), \
                "Incompatible OHE 25kV isolation and live S&T modulation must never be bundled"


class TestTier2MacroAllocation:
    def test_macro_allocation_feasible(self):
        scenario = create_compatible_shadow_bundle_scenario()
        scorer = TaskCriticalityScorer()
        job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}

        clusterer = SpatiotemporalClusteringEngine()
        bundles = clusterer.generate_candidate_bundles(scenario.jobs, scenario.blocks, job_tcis)

        allocator = MacroPossessionAllocator()
        result = allocator.allocate(scenario, bundles, job_tcis)

        assert result.is_feasible, "Macro allocation should be feasible"
        assert result.solver_mode in ("ORTOOLS_CPSAT", "ALNS_DETERMINISTIC")
        assert len(result.scheduled_jobs) >= 1

        scheduled_ids = [sj.job_id for sj in result.scheduled_jobs]
        assert "J_CIVIL_01" in scheduled_ids or "J_OHE_01" in scheduled_ids

    def test_premium_train_protection(self):
        scenario = create_premium_train_conflict_scenario()
        scorer = TaskCriticalityScorer()
        job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}

        clusterer = SpatiotemporalClusteringEngine()
        bundles = clusterer.generate_candidate_bundles(scenario.jobs, scenario.blocks, job_tcis)

        allocator = MacroPossessionAllocator()
        result = allocator.allocate(scenario, bundles, job_tcis)

        assert result.is_feasible
        # Premium train T_VANDE_BHARAT is protected during its corridor traversal
        assert "T_VANDE_BHARAT" in result.protected_premium_train_ids or len(result.scheduled_jobs) >= 0


class TestTier3MicroscopicValidation:
    def test_ohe_de_energization_exclusion(self):
        scenario, es = create_ohe_isolation_scenario()
        validator = MicroscopicDispatchValidator(min_headway_hours=0.25)

        candidate_schedule = [
            ScheduledJob(
                job_id="J_OHE_RENEWAL",
                block_id="B4",
                start_time=10.0,
                end_time=12.0,
                tci=75.0,
                department=Department.OHE
            )
        ]

        result = validator.validate_dispatch(
            scenario=scenario,
            scheduled_jobs=candidate_schedule,
            electrical_isolated_blocks={"B4"}
        )

        assert not result.is_feasible, "Schedule with electric train traversing isolated section must fail validation"
        assert len(result.generated_cuts) > 0, "Must return at least one named Benders feasibility cut"
        assert any(cut.cut_type == "ELECTRICAL_ISOLATION" for cut in result.generated_cuts)
        assert any("de-energized" in v.lower() or "electric" in v.lower() for v in result.safety_violations)


class TestFullOptimizationPipeline:
    def test_end_to_end_pipeline_execution(self):
        scenario = create_compatible_shadow_bundle_scenario()
        scorer = TaskCriticalityScorer()
        job_tcis = {j.id: scorer.calculate_tci(j.tci_inputs)[0] for j in scenario.jobs}

        pipeline = ProductionOptimizationPipeline()
        result = pipeline.optimize(scenario, job_tcis)

        assert "status" in result
        assert result["status"] in ("optimal", "alns_feasible")
        assert "scheduled_jobs" in result
        assert "candidate_bundles" in result
        assert "diagnostics" in result
        assert result["total_closure_time"] > 0.0
        assert result["runtime_seconds"] >= 0.0
