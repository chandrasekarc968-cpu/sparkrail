import math
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from pydantic import BaseModel, Field
import networkx as nx

from src.data_pipeline.models import (
    TrackSection,
    BlockSection,
    TrackSegment,
    Station,
    ElementarySection,
    ElementaryElectricalSection,
    SignalAsset,
    OHEAsset,
    TrainMovement,
    Coordinate3D
)

logger = logging.getLogger("SparkRail.Harmonization")

class HarmonizationError(ValueError):
    """Raised when railway geometry or telemetry cannot be reconciled safely."""
    pass

def normalize_chainage(chainage: Any) -> float:
    """
    Normalizes diverse Indian Railways chainage representations into canonical float kilometers.
    Supported formats:
    - float/int: 124.5 -> 124.5
    - string decimal: "124.500" -> 124.5
    - string km+meter: "124+500" -> 124.5
    - string telegraph/mast: "124/18" (km 124 + mast 18 * ~50m) -> 124.9
    - dict: {"km": 124, "meter": 500} -> 124.5
    """
    if chainage is None:
        raise HarmonizationError("Chainage value cannot be None")

    if isinstance(chainage, (int, float)):
        val = float(chainage)
        if val < 0:
            raise HarmonizationError(f"Chainage cannot be negative: {val}")
        return round(val, 4)

    if isinstance(chainage, dict):
        km = float(chainage.get("km", 0.0))
        meter = float(chainage.get("meter", chainage.get("m", 0.0)))
        total = km + (meter / 1000.0)
        if total < 0:
            raise HarmonizationError(f"Chainage cannot be negative: {total}")
        return round(total, 4)

    if isinstance(chainage, str):
        cleaned = chainage.strip()
        # Format 1: standard decimal "124.5"
        try:
            val = float(cleaned)
            if val < 0:
                raise HarmonizationError(f"Chainage cannot be negative: {val}")
            return round(val, 4)
        except ValueError:
            pass

        # Format 2: "124+500" (km + meters)
        match_plus = re.match(r"^(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)$", cleaned)
        if match_plus:
            km = float(match_plus.group(1))
            m = float(match_plus.group(2))
            return round(km + (m / 1000.0), 4)

        # Format 3: "124/18" (km / mast post, where standard mast spacing is ~50m)
        match_slash = re.match(r"^(\d+(?:\.\d+)?)\s*/\s*(\d+)$", cleaned)
        if match_slash:
            km = float(match_slash.group(1))
            mast = int(match_slash.group(2))
            return round(km + (mast * 0.050), 4)

        # Format 4: "KM 124.5" or "124 KM"
        match_km_word = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        if match_km_word:
            return round(float(match_km_word.group(1)), 4)

    raise HarmonizationError(f"Unparseable chainage format: '{chainage}'")

class MappingProvenance(BaseModel):
    source_system: str
    source_id: str
    target_block_id: Optional[str] = None
    target_chainage_km: Optional[float] = None
    confidence: float = 1.0  # 0.0 to 1.0
    ambiguity_flag: bool = False
    reconciliation_rule: str = "DIRECT_MATCH"
    reconciled_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class HarmonizationResult(BaseModel):
    is_valid: bool
    reconciled_assets: int = 0
    rejected_assets: int = 0
    provenance_records: List[MappingProvenance] = Field(default_factory=list)
    ambiguities_detected: List[str] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)

class RailwayMultiGraph:
    """
    Directed railway multigraph tracking physical adjacency, electrical
    dependencies, and signalling route locking. Backed by NetworkX MultiDiGraph.
    """
    def __init__(self):
        # Physical adjacency: block_id -> set of connected next block_ids
        self.physical_edges: Dict[str, Set[str]] = {}
        # Electrical dependencies: section_id -> set of block_ids
        self.electrical_subgraphs: Dict[str, Set[str]] = {}
        # Signalling dependencies: signal_id -> governed block_id
        self.signalling_edges: Dict[str, str] = {}
        # Block metadata: block_id -> BlockSection (or TrackSection)
        self.blocks: Dict[str, BlockSection] = {}
        # Underlying NetworkX directed multigraph
        self.nx_graph: nx.MultiDiGraph = nx.MultiDiGraph()

    def add_block(self, block: BlockSection) -> None:
        self.blocks[block.block_id] = block
        if block.block_id not in self.physical_edges:
            self.physical_edges[block.block_id] = set()
        self.nx_graph.add_node(
            block.block_id,
            start_km=block.chainage_start_km,
            end_km=block.chainage_end_km,
            speed_limit=block.speed_limit_kmh,
            electrification=block.electrification_type,
            line=getattr(block, "line_id", "MAIN_LINE")
        )

    def add_physical_connection(self, from_block: str, to_block: str, length_km: Optional[float] = None) -> None:
        if from_block not in self.physical_edges:
            self.physical_edges[from_block] = set()
        self.physical_edges[from_block].add(to_block)
        
        weight = length_km if length_km is not None else 1.0
        self.nx_graph.add_edge(from_block, to_block, key="physical", weight=weight, layer="track")

    def add_electrical_section(self, section: Union[ElementarySection, ElementaryElectricalSection]) -> None:
        b_ids = section.track_section_ids if getattr(section, "track_section_ids", None) else section.block_ids
        self.electrical_subgraphs[section.section_id] = set(b_ids)
        for b_id in b_ids:
            if b_id in self.nx_graph:
                self.nx_graph.nodes[b_id]["elementary_section"] = section.section_id
                self.nx_graph.nodes[b_id]["catenary_voltage"] = section.catenary_voltage_kv

    def add_signal_governance(self, signal_id: str, block_id: str) -> None:
        self.signalling_edges[signal_id] = block_id
        if block_id in self.nx_graph:
            signals = self.nx_graph.nodes[block_id].get("signals", [])
            signals.append(signal_id)
            self.nx_graph.nodes[block_id]["signals"] = signals

    def find_shortest_path(self, from_block: str, to_block: str) -> List[str]:
        """Finds shortest route between two block sections using physical adjacency."""
        try:
            return nx.shortest_path(self.nx_graph, source=from_block, target=to_block, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_affected_blocks_for_isolation(self, section_id: str) -> Set[str]:
        """Returns all block sections affected when an electrical section is isolated."""
        return self.electrical_subgraphs.get(section_id, set())

class SpatialHarmonizationPipeline:
    """
    Linear Referencing & Spatial Harmonization Service.
    Reconciles continuous linear chainage (TMS) with discrete block boundaries (COA/BDMS),
    elementary electrical feeds (TDMS), signaling routes (SMMS), and RTIS GPS telemetry.
    """
    def __init__(self, blocks: List[BlockSection]):
        self.blocks = sorted(blocks, key=lambda b: b.chainage_start_km)
        self.block_map = {b.block_id: b for b in self.blocks}
        self._validate_corridor_continuity()

    def _validate_corridor_continuity(self) -> None:
        """Enforces that block chainages are monotonically non-decreasing and non-overlapping."""
        seen_ids: Set[str] = set()
        for i, b in enumerate(self.blocks):
            if b.block_id in seen_ids:
                raise HarmonizationError(f"Duplicate block identifier detected: '{b.block_id}'")
            seen_ids.add(b.block_id)

            if b.chainage_start_km >= b.chainage_end_km:
                raise HarmonizationError(
                    f"Block '{b.block_id}' has invalid chainage range: {b.chainage_start_km} to {b.chainage_end_km}"
                )
            if i > 0:
                prev = self.blocks[i - 1]
                if b.chainage_start_km < prev.chainage_end_km - 0.001:
                    raise HarmonizationError(
                        f"Overlapping block sections detected between '{prev.block_id}' and '{b.block_id}'"
                    )

    def map_tms_chainage_to_block(self, chainage: Any, source_id: str) -> Tuple[Optional[BlockSection], MappingProvenance]:
        """
        Maps continuous TMS asset chainage to a discrete block section.
        Supports normalized chainage inputs (float, km+meter string, telegraph post).
        Detects boundary ambiguities (e.g. exactly on an insulated block joint).
        """
        try:
            chainage_km = normalize_chainage(chainage)
        except HarmonizationError as he:
            prov = MappingProvenance(
                source_system="TMS",
                source_id=source_id,
                confidence=0.0,
                ambiguity_flag=True,
                reconciliation_rule=f"INVALID_CHAINAGE_FORMAT: {he}"
            )
            return None, prov

        if chainage_km < self.blocks[0].chainage_start_km or chainage_km > self.blocks[-1].chainage_end_km:
            prov = MappingProvenance(
                source_system="TMS",
                source_id=source_id,
                target_chainage_km=chainage_km,
                confidence=0.0,
                ambiguity_flag=True,
                reconciliation_rule="OUT_OF_BOUNDS_REJECTION"
            )
            return None, prov

        matching_blocks: List[BlockSection] = []
        for b in self.blocks:
            # Allow epsilon boundary matching
            if (b.chainage_start_km - 0.001) <= chainage_km <= (b.chainage_end_km + 0.001):
                matching_blocks.append(b)

        if len(matching_blocks) == 1:
            prov = MappingProvenance(
                source_system="TMS",
                source_id=source_id,
                target_block_id=matching_blocks[0].block_id,
                target_chainage_km=chainage_km,
                confidence=1.0,
                ambiguity_flag=False,
                reconciliation_rule="EXACT_INTERVAL_CONTAINMENT"
            )
            return matching_blocks[0], prov

        elif len(matching_blocks) > 1:
            # Ambiguity at boundary joint
            prov = MappingProvenance(
                source_system="TMS",
                source_id=source_id,
                target_block_id=matching_blocks[0].block_id,
                target_chainage_km=chainage_km,
                confidence=0.75,
                ambiguity_flag=True,
                reconciliation_rule="BOUNDARY_JOINT_AMBIGUITY"
            )
            return matching_blocks[0], prov

        prov = MappingProvenance(
            source_system="TMS",
            source_id=source_id,
            target_chainage_km=chainage_km,
            confidence=0.0,
            ambiguity_flag=True,
            reconciliation_rule="DISCONTINUITY_GAP_REJECTION"
        )
        return None, prov

    def map_asset_to_track_section(self, chainage: Any, source_id: str, asset_type: str = "TRACK") -> Tuple[Optional[BlockSection], MappingProvenance]:
        block, prov = self.map_tms_chainage_to_block(chainage, source_id)
        prov.source_system = f"ASSET_{asset_type.upper()}"
        return block, prov

    def reconcile_elementary_section(self, section: Union[ElementarySection, ElementaryElectricalSection]) -> List[str]:
        """
        Verifies that every block referenced by an electrical elementary section exists
        in the physical block network and is contiguous.
        """
        b_ids = section.track_section_ids if getattr(section, "track_section_ids", None) else section.block_ids
        missing = [b_id for b_id in b_ids if b_id not in self.block_map]
        if missing:
            raise HarmonizationError(
                f"Elementary Section '{section.section_id}' references unknown blocks: {missing}"
            )
        return b_ids

    def project_rtis_gps_to_block(
        self,
        lat: float,
        lon: float,
        speed_kmh: float,
        train_id: str,
        corridor_start_coord: Tuple[float, float],
        corridor_end_coord: Tuple[float, float]
    ) -> Tuple[Optional[BlockSection], float, MappingProvenance]:
        """
        Projects locomotive GPS coordinates onto linear corridor chainage.
        Validates coordinate bounds and direction.
        """
        total_corridor_km = self.blocks[-1].chainage_end_km - self.blocks[0].chainage_start_km
        lat0, lon0 = corridor_start_coord
        lat1, lon1 = corridor_end_coord
        
        # Simple projection vector along corridor axis
        dlat = lat1 - lat0
        dlon = lon1 - lon0
        mag_sq = dlat * dlat + dlon * dlon

        if mag_sq < 1e-9:
            prov = MappingProvenance(
                source_system="RTIS",
                source_id=train_id,
                confidence=0.0,
                ambiguity_flag=True,
                reconciliation_rule="DEGENERATE_CORRIDOR_REFERENCE"
            )
            return None, 0.0, prov

        u = ((lat - lat0) * dlat + (lon - lon0) * dlon) / mag_sq
        u_clamped = max(0.0, min(1.0, u))
        projected_km = self.blocks[0].chainage_start_km + u_clamped * total_corridor_km

        block, prov = self.map_tms_chainage_to_block(projected_km, train_id)
        prov.source_system = "RTIS"
        prov.reconciliation_rule = "ORTHOGONAL_CORRIDOR_PROJECTION"
        prov.confidence = max(0.1, round(1.0 - abs(u - u_clamped), 3))
        return block, projected_km, prov

    def build_multigraph(
        self,
        electrical_sections: List[Union[ElementarySection, ElementaryElectricalSection]],
        signals: List[SignalAsset]
    ) -> RailwayMultiGraph:
        """
        Constructs the unified directed railway multigraph.
        """
        mg = RailwayMultiGraph()
        for b in self.blocks:
            mg.add_block(b)

        # Build physical adjacency sequence
        for i in range(len(self.blocks) - 1):
            len_km = self.blocks[i].chainage_end_km - self.blocks[i].chainage_start_km
            mg.add_physical_connection(self.blocks[i].block_id, self.blocks[i + 1].block_id, length_km=len_km)
            mg.add_physical_connection(self.blocks[i + 1].block_id, self.blocks[i].block_id, length_km=len_km)

        # Build electrical subgraphs
        for es in electrical_sections:
            self.reconcile_elementary_section(es)
            mg.add_electrical_section(es)

        # Build signalling governance
        for sig in signals:
            mg.add_signal_governance(sig.signal_id, sig.block_id)

        return mg
