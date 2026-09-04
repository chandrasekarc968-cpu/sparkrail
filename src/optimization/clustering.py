import math
from typing import Dict, Any, List, Set, Tuple, Optional
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    MaintenanceJob,
    Department,
    TrackBlock
)

class CandidateBundle(BaseModel):
    bundle_id: str
    primary_job_id: str
    secondary_job_ids: List[str] = Field(default_factory=list)
    block_id: str
    departments: List[str] = Field(default_factory=list)
    spatial_extent_km: Tuple[float, float]
    time_envelope_hours: Tuple[float, float]
    required_duration_hours: float
    total_tci_benefit: float
    compatibility_rationale: str
    rejected_pairs: List[Dict[str, Any]] = Field(default_factory=list)

class SpatiotemporalClusteringEngine:
    """
    Tier 1 Demand Clustering Service.
    Evaluates multi-attribute distance between pending maintenance demands,
    constructs a compatibility hypergraph, and extracts maximal cliques (bundles)
    for simultaneous corridor execution.
    """
    def __init__(
        self,
        max_spatial_distance_km: float = 10.0,
        max_time_distance_hours: float = 4.0,
        elementary_section_map: Optional[Dict[str, str]] = None
    ):
        self.max_spatial_dist = max_spatial_distance_km
        self.max_time_dist = max_time_distance_hours
        # Maps block_id -> elementary_section_id
        self.elementary_map = elementary_section_map or {}

    def compute_distance(
        self,
        job_a: MaintenanceJob,
        job_b: MaintenanceJob,
        block_map: Dict[str, TrackBlock]
    ) -> float:
        """
        Computes normalized spatiotemporal distance between two maintenance jobs.
        Returns float distance, where distance >= 1.0 implies cluster separation.
        """
        block_a = block_map.get(job_a.block_id)
        block_b = block_map.get(job_b.block_id)

        # 1. Spatial distance between block midpoints
        if block_a and block_b:
            mid_a = (block_a.chainage_start + block_a.chainage_end) / 2.0
            mid_b = (block_b.chainage_start + block_b.chainage_end) / 2.0
            dist_km = abs(mid_a - mid_b)
        else:
            dist_km = 0.0 if job_a.block_id == job_b.block_id else 15.0

        spatial_norm = min(1.0, dist_km / self.max_spatial_dist)

        # 2. Time window distance
        start_a = job_a.fixed_start if job_a.is_fixed and job_a.fixed_start is not None else 0.0
        start_b = job_b.fixed_start if job_b.is_fixed and job_b.fixed_start is not None else 0.0
        time_diff = abs(start_a - start_b)
        time_norm = min(1.0, time_diff / self.max_time_dist)

        # 3. Elementary electrical section alignment
        elec_a = self.elementary_map.get(job_a.block_id)
        elec_b = self.elementary_map.get(job_b.block_id)
        elec_penalty = 0.0
        if elec_a and elec_b and elec_a != elec_b:
            elec_penalty = 0.5

        return (spatial_norm * 0.5) + (time_norm * 0.3) + elec_penalty

    def are_jobs_compatible(
        self,
        job_a: MaintenanceJob,
        job_b: MaintenanceJob
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether two jobs can be safely scheduled concurrently in a shadow bundle.
        Never allows simplistic 'same block means compatible' logic.
        """
        # Strict railway rule: OHE and S&T cannot operate concurrently
        d_a = job_a.department.value if isinstance(job_a.department, Department) else str(job_a.department)
        d_b = job_b.department.value if isinstance(job_b.department, Department) else str(job_b.department)

        if (d_a == "OHE" and d_b == "S&T") or (d_a == "S&T" and d_b == "OHE"):
            return False, "OHE 25kV traction power isolation conflict with S&T live circuit testing"

        # Resource clash check: both jobs cannot demand more of a specific resource than exists
        for res_id, req_a in job_a.required_resources.items():
            req_b = job_b.required_resources.get(res_id, 0)
            if req_a > 0 and req_b > 0 and res_id.startswith("R_BCM"):
                # BCM machines cannot operate together on the same physical section
                return False, f"Heavy track machine exclusivity conflict on '{res_id}'"

        return True, None

    def build_compatibility_graph(
        self,
        jobs: List[MaintenanceJob]
    ) -> Tuple[Dict[str, Set[str]], List[Dict[str, Any]]]:
        """
        Builds adjacency list for the compatibility graph: nodes are job IDs,
        edges exist if and only if both jobs are strictly compatible.
        """
        adj: Dict[str, Set[str]] = {j.id: set() for j in jobs}
        rejected_pairs: List[Dict[str, Any]] = []

        for i in range(len(jobs)):
            for j in range(i + 1, len(jobs)):
                ja, jb = jobs[i], jobs[j]
                compat, reason = self.are_jobs_compatible(ja, jb)
                if compat:
                    adj[ja.id].add(jb.id)
                    adj[jb.id].add(ja.id)
                else:
                    rejected_pairs.append({
                        "job_a": ja.id,
                        "job_b": jb.id,
                        "department_a": ja.department.value,
                        "department_b": jb.department.value,
                        "reason": reason
                    })

        return adj, rejected_pairs

    def extract_maximal_cliques(
        self,
        adj: Dict[str, Set[str]]
    ) -> List[Set[str]]:
        """
        Bron-Kerbosch algorithm with pivoting to extract all maximal cliques (compatible bundles).
        """
        cliques: List[Set[str]] = []

        def bron_kerbosch(R: Set[str], P: Set[str], X: Set[str]):
            if not P and not X:
                if len(R) > 0:
                    cliques.append(set(R))
                return
            # Pivot selection
            pivot = next(iter(P | X))
            for v in list(P - adj.get(pivot, set())):
                bron_kerbosch(
                    R | {v},
                    P & adj.get(v, set()),
                    X & adj.get(v, set())
                )
                P.remove(v)
                X.add(v)

        all_nodes = set(adj.keys())
        bron_kerbosch(set(), all_nodes, set())
        # Sort cliques by size descending
        return sorted(cliques, key=lambda c: len(c), reverse=True)

    def generate_candidate_bundles(
        self,
        jobs: List[MaintenanceJob],
        blocks: List[TrackBlock],
        job_tcis: Dict[str, float]
    ) -> List[CandidateBundle]:
        """
        Generates structured candidate possession bundles for Tier 2 Macro Allocation.
        """
        block_map = {b.id: b for b in blocks}
        job_map = {j.id: j for j in jobs}
        
        adj, rejected_pairs = self.build_compatibility_graph(jobs)
        cliques = self.extract_maximal_cliques(adj)

        bundles: List[CandidateBundle] = []
        seen_primary_jobs: Set[str] = set()

        for c_idx, clique in enumerate(cliques):
            # Sort jobs in clique by descending TCI
            clique_jobs = sorted([job_map[jid] for jid in clique if jid in job_map], key=lambda j: job_tcis.get(j.id, 0.0), reverse=True)
            if not clique_jobs:
                continue

            primary = clique_jobs[0]
            if primary.id in seen_primary_jobs and len(clique_jobs) == 1:
                continue
            seen_primary_jobs.add(primary.id)

            secondary_ids = [j.id for j in clique_jobs[1:]]
            departments = list(set([j.department.value for j in clique_jobs]))
            
            # Spatial extent
            primary_block = block_map.get(primary.block_id)
            if primary_block:
                spatial_extent = (primary_block.chainage_start, primary_block.chainage_end)
            else:
                spatial_extent = (0.0, 10.0)

            # Max duration among bundled jobs (shadow block duration)
            max_duration = max(j.duration for j in clique_jobs)
            total_tci = sum(job_tcis.get(j.id, 50.0) for j in clique_jobs)

            rationale = (
                f"Consolidated {len(clique_jobs)} compatible jobs across "
                f"{', '.join(departments)} under a single {max_duration:.1f}h corridor possession"
            )

            bundle = CandidateBundle(
                bundle_id=f"BUNDLE-{primary.block_id}-{c_idx+1}",
                primary_job_id=primary.id,
                secondary_job_ids=secondary_ids,
                block_id=primary.block_id,
                departments=departments,
                spatial_extent_km=spatial_extent,
                time_envelope_hours=(0.0, 24.0),
                required_duration_hours=max_duration,
                total_tci_benefit=round(total_tci, 2),
                compatibility_rationale=rationale,
                rejected_pairs=[rp for rp in rejected_pairs if rp["job_a"] in clique or rp["job_b"] in clique]
            )
            bundles.append(bundle)

        return bundles
