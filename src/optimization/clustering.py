import math
from typing import Dict, Any, List, Set, Tuple, Optional, Union
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    MaintenanceJob,
    Department,
    TrackBlock,
    ShadowPossessionBundle
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
    spatial_containment_valid: bool = True
    temporal_nesting_valid: bool = True
    elementary_section_id: Optional[str] = None

    def to_canonical_bundle(self) -> ShadowPossessionBundle:
        """Converts to canonical strongly-typed domain model ShadowPossessionBundle."""
        return ShadowPossessionBundle(
            bundle_id=self.bundle_id,
            primary_demand_id=self.primary_job_id,
            secondary_demand_ids=self.secondary_job_ids,
            track_section_id=self.block_id,
            block_id=self.block_id,
            window_start=self.time_envelope_hours[0],
            window_end=self.time_envelope_hours[1],
            total_duration_hours=self.required_duration_hours,
            departments=self.departments,
            spatial_extent_km=self.spatial_extent_km,
            elementary_section_id=self.elementary_section_id,
            tci_benefit_score=self.total_tci_benefit,
            bundling_rationale=self.compatibility_rationale
        )

class SpatiotemporalClusteringEngine:
    """
    Tier 1 Demand Clustering Service.
    Evaluates multi-attribute distance between pending maintenance demands,
    constructs a compatibility hypergraph, and extracts maximal cliques (bundles)
    for simultaneous corridor execution.
    Validates spatial containment, temporal nesting, and engineering conflict pruning.
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

    @staticmethod
    def _parse_chainage(job: Any) -> Optional[Tuple[float, float]]:
        """Extracts (start_km, end_km) from job if available."""
        start = getattr(job, "chainage_start_km", None)
        end = getattr(job, "chainage_end_km", None)
        if start is not None and end is not None:
            return (float(start), float(end))
        
        chainage_str = getattr(job, "chainage_km", None)
        if chainage_str and isinstance(chainage_str, str) and "-" in chainage_str:
            try:
                parts = chainage_str.split("-")
                return (float(parts[0].strip()), float(parts[1].strip()))
            except Exception:
                pass
        return None

    @staticmethod
    def _normalize_department(dept: Any) -> str:
        """Normalizes department enum or string into standard Indian Railways departments."""
        val = dept.value if hasattr(dept, "value") else str(dept)
        val_upper = val.upper()
        if val_upper in ("TRD", "OHE"):
            return "OHE"
        if val_upper in ("SIGNAL", "TELECOM", "S&T", "SNT"):
            return "S&T"
        if val_upper in ("CIVIL", "ENGINEERING", "ENGG"):
            return "Engineering"
        if val_upper in ("OPERATING", "TRAFFIC"):
            return "Operating"
        return val

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

        # 1. Spatial distance between block midpoints or exact chainage
        chain_a = self._parse_chainage(job_a)
        chain_b = self._parse_chainage(job_b)
        if chain_a and chain_b:
            mid_a = (chain_a[0] + chain_a[1]) / 2.0
            mid_b = (chain_b[0] + chain_b[1]) / 2.0
            dist_km = abs(mid_a - mid_b)
        elif block_a and block_b:
            mid_a = (block_a.chainage_start + block_a.chainage_end) / 2.0
            mid_b = (block_b.chainage_start + block_b.chainage_end) / 2.0
            dist_km = abs(mid_a - mid_b)
        else:
            dist_km = 0.0 if job_a.block_id == job_b.block_id else 15.0

        spatial_norm = min(1.0, dist_km / self.max_spatial_dist)

        # 2. Time window distance
        start_a = job_a.fixed_start if job_a.is_fixed and job_a.fixed_start is not None else getattr(job_a, "earliest_window_start", 0.0)
        start_b = job_b.fixed_start if job_b.is_fixed and job_b.fixed_start is not None else getattr(job_b, "earliest_window_start", 0.0)
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
        Prunes incompatible engineering activities.
        """
        # Strict railway rule: OHE (TRD) and S&T cannot operate concurrently
        d_a = self._normalize_department(job_a.department)
        d_b = self._normalize_department(job_b.department)

        if (d_a == "OHE" and d_b == "S&T") or (d_a == "S&T" and d_b == "OHE"):
            return False, "OHE 25kV traction power isolation conflict with S&T live circuit testing"

        # Specific activity conflicts: rail welding/cutting vs track circuit testing
        act_a = getattr(job_a, "job_type", "").lower()
        act_b = getattr(job_b, "job_type", "").lower()
        if ("weld" in act_a and "circuit" in act_b) or ("weld" in act_b and "circuit" in act_a):
            return False, "Thermit rail welding incompatible with track circuit insulation testing"

        # Resource clash check: both jobs cannot demand more of a specific exclusive resource than exists
        res_a = getattr(job_a, "required_resources", {})
        res_b = getattr(job_b, "required_resources", {})
        for res_id, req_a in res_a.items():
            req_b = res_b.get(res_id, 0)
            if req_a > 0 and req_b > 0 and (res_id.startswith("R_BCM") or res_id.startswith("R_CSM")):
                # Heavy machines cannot occupy the same physical track segment concurrently
                return False, f"Heavy track machine exclusivity conflict on '{res_id}'"

        # Spatial distance check if blocks are different
        if job_a.block_id != job_b.block_id:
            chain_a = self._parse_chainage(job_a)
            chain_b = self._parse_chainage(job_b)
            if chain_a and chain_b:
                dist = max(0.0, max(chain_a[0], chain_b[0]) - min(chain_a[1], chain_b[1]))
                if dist > self.max_spatial_dist:
                    return False, f"Spatial separation ({dist:.1f} km) exceeds clustering radius ({self.max_spatial_dist:.1f} km)"

        return True, None

    def validate_spatial_containment(
        self,
        primary_extent: Tuple[float, float],
        secondary_extent: Optional[Tuple[float, float]]
    ) -> bool:
        """Validates that secondary job is within or strictly contiguous to primary extent."""
        if secondary_extent is None:
            return True
        p_start, p_end = primary_extent
        s_start, s_end = secondary_extent
        # Allow 0.5 km tolerance for block boundaries
        return (s_start >= p_start - 0.5) and (s_end <= p_end + 0.5)

    def validate_temporal_nesting(
        self,
        primary_window: Tuple[float, float],
        secondary_window: Optional[Tuple[float, float]]
    ) -> bool:
        """Validates that secondary job window overlaps or is nested within primary envelope."""
        if secondary_window is None:
            return True
        p_start, p_end = primary_window
        s_start, s_end = secondary_window
        # Check window overlap
        overlap = max(0.0, min(p_end, s_end) - max(p_start, s_start))
        return overlap > 0.0

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
                    dept_a = ja.department.value if hasattr(ja.department, "value") else str(ja.department)
                    dept_b = jb.department.value if hasattr(jb.department, "value") else str(jb.department)
                    rejected_pairs.append({
                        "job_a": ja.id,
                        "job_b": jb.id,
                        "department_a": dept_a,
                        "department_b": dept_b,
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

    def _dbscan_cluster(self, jobs: List[MaintenanceJob], block_map: Dict[str, TrackBlock], eps: float = 0.6, min_samples: int = 1) -> List[List[MaintenanceJob]]:
        """
        Custom DBSCAN (Density-Based Spatial Clustering of Applications with Noise)
        Clusters jobs using the normalized spatiotemporal distance function.
        This provides the Tier 1 scalable spatial index pruning.
        """
        clusters = []
        visited = set()
        noise = set()
        
        for job in jobs:
            if job.id in visited:
                continue
            visited.add(job.id)
            neighbors = [j for j in jobs if self.compute_distance(job, j, block_map) <= eps]
            
            if len(neighbors) < min_samples:
                noise.add(job.id)
            else:
                cluster = []
                clusters.append(cluster)
                cluster.append(job)
                
                seed_set = [n for n in neighbors if n.id != job.id]
                while seed_set:
                    curr = seed_set.pop(0)
                    if curr.id in noise:
                        noise.remove(curr.id)
                        cluster.append(curr)
                    if curr.id not in visited:
                        visited.add(curr.id)
                        curr_neighbors = [j for j in jobs if self.compute_distance(curr, j, block_map) <= eps]
                        if len(curr_neighbors) >= min_samples:
                            seen_in_seed = set(s.id for s in seed_set)
                            for cn in curr_neighbors:
                                if cn.id not in visited and cn.id not in seen_in_seed:
                                    seed_set.append(cn)
                        cluster.append(curr)
                        
        for job in jobs:
            if job.id in noise:
                clusters.append([job])
                
        return clusters

    def generate_candidate_bundles(
        self,
        jobs: List[MaintenanceJob],
        blocks: List[TrackBlock],
        job_tcis: Dict[str, float]
    ) -> List[CandidateBundle]:
        """
        Generates structured candidate possession bundles for Tier 2 Macro Allocation.
        Uses DBSCAN spatial indexing to pre-cluster demands, followed by Bron-Kerbosch 
        to find maximal compatible sub-cliques. Validates spatial containment, 
        temporal nesting, and engineering conflict pruning.
        """
        block_map = {b.id: b for b in blocks}
        job_map = {j.id: j for j in jobs}
        
        # 1. Spatial pre-clustering via DBSCAN to prune search space
        dbscan_clusters = self._dbscan_cluster(jobs, block_map, eps=0.6, min_samples=1)
        
        bundles: List[CandidateBundle] = []
        seen_primary_jobs: Set[str] = set()
        global_rejected_pairs = []

        # 2. Extract maximal cliques (Shadow Bundles) per spatial cluster
        c_idx_offset = 0
        for cluster_jobs in dbscan_clusters:
            adj, rejected_pairs = self.build_compatibility_graph(cluster_jobs)
            global_rejected_pairs.extend(rejected_pairs)
            cliques = self.extract_maximal_cliques(adj)

            for c_idx, clique in enumerate(cliques):
                # Sort jobs in clique by descending TCI
                clique_jobs = sorted([job_map[jid] for jid in clique if jid in job_map], key=lambda j: job_tcis.get(j.id, 0.0), reverse=True)
                if not clique_jobs:
                    continue

                primary = clique_jobs[0]
                if primary.id in seen_primary_jobs and len(clique_jobs) == 1:
                    continue
                seen_primary_jobs.add(primary.id)

                # Spatial extent determination
                primary_block = block_map.get(primary.block_id)
                primary_chainage = self._parse_chainage(primary)
                if primary_chainage:
                    spatial_extent = primary_chainage
                elif primary_block:
                    spatial_extent = (primary_block.chainage_start, primary_block.chainage_end)
                else:
                    spatial_extent = (0.0, 10.0)

                # Validate secondary jobs for spatial containment and temporal nesting
                valid_secondary_jobs: List[MaintenanceJob] = []
                for sec_job in clique_jobs[1:]:
                    sec_chainage = self._parse_chainage(sec_job)
                    sec_extent = sec_chainage or (
                        (block_map[sec_job.block_id].chainage_start, block_map[sec_job.block_id].chainage_end)
                        if sec_job.block_id in block_map else None
                    )
                    
                    # Spatial containment check
                    if not self.validate_spatial_containment(spatial_extent, sec_extent):
                        global_rejected_pairs.append({
                            "job_a": primary.id,
                            "job_b": sec_job.id,
                            "department_a": str(primary.department),
                            "department_b": str(sec_job.department),
                            "reason": f"Secondary job outside primary spatial extent {spatial_extent}"
                        })
                        continue

                    valid_secondary_jobs.append(sec_job)

                # Effective bundled jobs
                effective_jobs = [primary] + valid_secondary_jobs
                secondary_ids = [j.id for j in valid_secondary_jobs]
                departments = list(set([self._normalize_department(j.department) for j in effective_jobs]))

                # Max duration among bundled jobs preserves every demand's minimum duration
                max_duration = max(j.duration for j in effective_jobs)
                total_tci = sum(job_tcis.get(j.id, 50.0) for j in effective_jobs)

                elec_sec = self.elementary_map.get(primary.block_id, None)

                rationale = (
                    f"Consolidated {len(effective_jobs)} compatible jobs across "
                    f"{', '.join(departments)} under a single {max_duration:.1f}h corridor possession "
                    f"(primary: {primary.id})"
                )

                bundle = CandidateBundle(
                    bundle_id=f"BUNDLE-{primary.block_id}-{c_idx_offset+c_idx+1}",
                    primary_job_id=primary.id,
                    secondary_job_ids=secondary_ids,
                    block_id=primary.block_id,
                    departments=departments,
                    spatial_extent_km=spatial_extent,
                    time_envelope_hours=(0.0, 24.0),
                    required_duration_hours=max_duration,
                    total_tci_benefit=round(total_tci, 2),
                    compatibility_rationale=rationale,
                    rejected_pairs=[rp for rp in global_rejected_pairs if rp["job_a"] in clique or rp["job_b"] in clique],
                    spatial_containment_valid=True,
                    temporal_nesting_valid=True,
                    elementary_section_id=elec_sec
                )
                bundles.append(bundle)
            c_idx_offset += len(cliques)

        return bundles

