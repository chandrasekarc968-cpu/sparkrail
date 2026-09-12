from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional, Any, Set, Union
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    NetworkGeometryResponse,
    TrackSection,
    StationNode,
    JunctionNode,
    Crossover,
    InterlockingZone,
    SignalMarker,
    TrackCircuit,
    ElementarySection,
    FeedingPost,
    IsolatorSwitch,
    PossessionEntity,
    ShadowPossessionBundle,
    SpeedRestrictionZone,
    ConflictItem,
    ConflictType,
    AssetHealthRecord,
    Train,
    ValidationStatus
)

class TopologyQueryError(ValueError):
    """Raised when a topology routing or connectivity query is invalid."""
    pass

class CanonicalRailwayTopology:
    """
    Canonical Directed Multigraph Topology Service for the Railway Corridor.
    Preserves UP and DOWN directions, single/double line sections, crossovers,
    interlockings, OHE elementary sections, and spatial query APIs.
    """
    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self,
        division_code: Any = "PRYJ",
        corridor_name: str = "Subedarganj - Mirzapur Mainline",
        geometry: Optional[NetworkGeometryResponse] = None
    ):
        if isinstance(division_code, NetworkGeometryResponse):
            geometry = division_code
            division_code = "PRYJ"
        self.division_code = division_code
        self.corridor_name = corridor_name
        self.total_length_km = 80.0

        # Primary indexing collections
        self.stations: Dict[str, StationNode] = {}
        self.junctions: Dict[str, JunctionNode] = {}
        self.track_sections: Dict[str, TrackSection] = {}
        self.crossovers: Dict[str, Crossover] = {}
        self.interlockings: Dict[str, InterlockingZone] = {}
        self.signals: Dict[str, SignalMarker] = {}
        self.track_circuits: Dict[str, TrackCircuit] = {}
        self.elementary_sections: Dict[str, ElementarySection] = {}
        self.feeding_posts: Dict[str, FeedingPost] = {}
        self.isolator_switches: Dict[str, IsolatorSwitch] = {}
        self.speed_restrictions: Dict[str, SpeedRestrictionZone] = {}

        # Directed multigraph adjacency: from_section_id -> list of (to_section_id, transition_type)
        self.graph_forward: Dict[str, List[Tuple[str, str]]] = {}
        self.graph_backward: Dict[str, List[Tuple[str, str]]] = {}

        if geometry is not None:
            self._load_from_geometry(geometry)

    def _load_from_geometry(self, geometry: NetworkGeometryResponse):
        for node in geometry.nodes:
            self.add_station(node)
        
        up_sections = []
        dn_sections = []
        for sec in geometry.track_sections:
            self.add_track_section(sec)
            if sec.track_direction == "UP":
                up_sections.append(sec)
            elif sec.track_direction == "DOWN":
                dn_sections.append(sec)
        
        up_sections.sort(key=lambda s: s.chainage_start_km)
        self.link_sequential_tracks(up_sections)
        dn_sections.sort(key=lambda s: s.chainage_end_km, reverse=True)
        self.link_sequential_tracks(dn_sections)

        for xover in geometry.crossovers:
            self.add_crossover(xover)
        for ixl in geometry.interlockings:
            self.add_interlocking(ixl)
        for sig in geometry.signals:
            self.add_signal(sig)
        for tc in geometry.track_circuits:
            self.add_track_circuit(tc)
        for es in geometry.elementary_sections:
            self.add_elementary_section(es)
        for fp in geometry.feeding_posts:
            self.add_feeding_post(fp)
        for sw in geometry.isolator_switches:
            self.add_isolator_switch(sw)
        for sr in geometry.speed_restrictions:
            self.add_speed_restriction(sr)

    def add_station(self, station: StationNode):
        self.stations[station.code] = station

    def add_junction(self, junction: JunctionNode):
        self.junctions[junction.code] = junction

    def add_track_section(self, section: TrackSection):
        self.track_sections[section.id] = section
        if section.id not in self.graph_forward:
            self.graph_forward[section.id] = []
        if section.id not in self.graph_backward:
            self.graph_backward[section.id] = []

    def add_crossover(self, crossover: Crossover):
        self.crossovers[crossover.id] = crossover
        # Link from_track to to_track
        if crossover.from_track_id in self.graph_forward:
            self.graph_forward[crossover.from_track_id].append((crossover.to_track_id, "CROSSOVER"))
        if crossover.to_track_id in self.graph_backward:
            self.graph_backward[crossover.to_track_id].append((crossover.from_track_id, "CROSSOVER"))

    def add_interlocking(self, zone: InterlockingZone):
        self.interlockings[zone.id] = zone

    def add_signal(self, signal: SignalMarker):
        self.signals[signal.id] = signal

    def add_track_circuit(self, circuit: TrackCircuit):
        self.track_circuits[circuit.id] = circuit

    def add_elementary_section(self, elem: ElementarySection):
        self.elementary_sections[elem.id] = elem

    def add_feeding_post(self, post: FeedingPost):
        self.feeding_posts[post.id] = post

    def add_isolator_switch(self, switch: IsolatorSwitch):
        self.isolator_switches[switch.id] = switch

    def add_speed_restriction(self, sr: SpeedRestrictionZone):
        self.speed_restrictions[sr.id] = sr

    def link_sequential_tracks(self, sections: List[TrackSection]):
        """Connects a sequence of track sections in direction of chainage."""
        for i in range(len(sections) - 1):
            s1 = sections[i]
            s2 = sections[i + 1]
            if s1.id not in self.graph_forward:
                self.graph_forward[s1.id] = []
            if s2.id not in self.graph_backward:
                self.graph_backward[s2.id] = []
            self.graph_forward[s1.id].append((s2.id, "NORMAL"))
            self.graph_backward[s2.id].append((s1.id, "NORMAL"))

    # =========================================================================
    # Topology Query APIs
    # =========================================================================

    def get_track_section_by_chainage(
        self,
        chainage_km: float,
        direction: str = "UP"
    ) -> Optional[TrackSection]:
        """Finds track section covering a given chainage in specified direction."""
        dir_upper = direction.upper()
        for sec in self.track_sections.values():
            if sec.track_direction in (dir_upper, "BIDIRECTIONAL"):
                if sec.chainage_start_km <= chainage_km <= sec.chainage_end_km:
                    return sec
        return None

    def get_nearest_station(self, chainage_km: float) -> Tuple[Optional[StationNode], float]:
        """Returns the nearest station and distance in km."""
        if not self.stations:
            return None, float("inf")
        nearest = None
        min_dist = float("inf")
        for stn in self.stations.values():
            dist = abs(stn.chainage_km - chainage_km)
            if dist < min_dist:
                min_dist = dist
                nearest = stn
        return nearest, round(min_dist, 2)

    def get_adjacent_sections(
        self,
        section_id: str,
        traversal: str = "FORWARD",
        direction: Optional[str] = None
    ) -> List[str]:
        """Returns adjacent track section IDs following topology graph edges."""
        if direction:
            traversal = "FORWARD"
        graph = self.graph_forward if traversal.upper() == "FORWARD" else self.graph_backward
        neighbors = graph.get(section_id, [])
        return [n_id for n_id, _ in neighbors if n_id in self.track_sections]

    def find_route(
        self,
        from_loc: Any,
        to_loc: Any,
        direction: str = "UP"
    ) -> List[TrackSection]:
        """
        Computes the canonical sequence of track sections between two stations or chainages.
        """
        if isinstance(from_loc, (int, float)):
            start_km = float(from_loc)
        else:
            from_stn = self.stations.get(str(from_loc))
            if not from_stn:
                raise TopologyQueryError(f"Station code '{from_loc}' not found in corridor.")
            start_km = from_stn.chainage_km

        if isinstance(to_loc, (int, float)):
            end_km = float(to_loc)
        else:
            to_stn = self.stations.get(str(to_loc))
            if not to_stn:
                raise TopologyQueryError(f"Station code '{to_loc}' not found in corridor.")
            end_km = to_stn.chainage_km

        is_forward = end_km >= start_km
        min_km = min(start_km, end_km)
        max_km = max(start_km, end_km)

        matching = [
            s for s in self.track_sections.values()
            if (min_km <= s.chainage_end_km and s.chainage_start_km <= max_km)
            and (s.track_direction in (direction.upper(), "BIDIRECTIONAL"))
        ]
        matching.sort(key=lambda s: s.chainage_start_km, reverse=(not is_forward))
        return matching

    def get_affected_ohe_sections(self, track_section_ids: List[str]) -> List[ElementarySection]:
        """Returns all OHE elementary sections that isolate or overlap the given tracks."""
        track_set = set(track_section_ids)
        affected: List[ElementarySection] = []
        for elem in self.elementary_sections.values():
            if any(t in track_set for t in elem.associated_tracks):
                affected.append(elem)
        return affected

    def get_affected_signalling_zones(self, track_section_ids: List[str]) -> List[InterlockingZone]:
        """Returns all interlocking zones governing or intersecting the given tracks."""
        affected: List[InterlockingZone] = []
        track_objs = [self.track_sections[t] for t in track_section_ids if t in self.track_sections]
        if not track_objs:
            return affected

        min_km = min(t.chainage_start_km for t in track_objs)
        max_km = max(t.chainage_end_km for t in track_objs)

        for zone in self.interlockings.values():
            # Check overlap in chainage
            if not (zone.chainage_end_km < min_km or zone.chainage_start_km > max_km):
                affected.append(zone)
        return affected

    def get_valid_tsl_corridor(
        self,
        closed_track_id: str,
        start_km: Optional[float] = None,
        end_km: Optional[float] = None,
        direction: str = "UP"
    ) -> Dict[str, Any]:
        """
        Temporary Single Line (TSL) Working Routing:
        When an UP (or DOWN) track is closed for possession, identifies the nearest
        facing crossover ahead and trailing crossover behind to divert trains onto
        the parallel active track under pilot protection.
        """
        closed_track = self.track_sections.get(closed_track_id)
        if not closed_track:
            raise TopologyQueryError(f"Track '{closed_track_id}' not found for TSL query.")

        c_start = start_km if start_km is not None else closed_track.chainage_start_km
        c_end = end_km if end_km is not None else closed_track.chainage_end_km

        # Find parallel opposite-direction track
        opp_dir = "DOWN" if closed_track.track_direction == "UP" else "UP"
        parallel_track = self.get_track_section_by_chainage(
            (c_start + c_end) / 2.0,
            direction=opp_dir
        )

        # Find entry crossover (before start) and exit crossover (after end)
        entry_xover = None
        exit_xover = None
        for xover in self.crossovers.values():
            if xover.chainage_km <= c_start + 1.0:
                if entry_xover is None or xover.chainage_km > entry_xover.chainage_km:
                    entry_xover = xover
            if xover.chainage_km >= c_end - 1.0:
                if exit_xover is None or xover.chainage_km < exit_xover.chainage_km:
                    exit_xover = xover

        return {
            "is_valid_tsl": bool(parallel_track and entry_xover and exit_xover),
            "closed_track_id": closed_track_id,
            "closed_chainage_km": [c_start, c_end],
            "healthy_track_id": parallel_track.id if parallel_track else None,
            "parallel_active_track_id": parallel_track.id if parallel_track else None,
            "entry_crossover_id": entry_xover.id if entry_xover else None,
            "exit_crossover_id": exit_xover.id if exit_xover else None,
            "single_line_speed_limit_kmh": 40.0,
            "tsl_max_speed_kmh": 25.0,  # Statutory IR limit for first train on TSL
            "pilot_protection_required": True,
            "status": "VALID_TSL_CORRIDOR" if (parallel_track and entry_xover and exit_xover) else "UNAVAILABLE"
        }

    def find_possession_train_conflicts(
        self,
        possession: PossessionEntity,
        trains: List[Train]
    ) -> List[ConflictItem]:
        """
        Detects operational train-vs-possession conflicts along the topological route.
        """
        conflicts: List[ConflictItem] = []
        poss_start_h = possession.start_time_hours
        poss_end_h = possession.end_time_hours
        poss_tracks = set(possession.affected_tracks or [possession.block_id])

        for train in trains:
            # Check if train route intersects affected tracks
            train_tracks = set(train.route)
            overlap_tracks = poss_tracks.intersection(train_tracks)
            if overlap_tracks:
                # Check time window overlap
                if not (train.scheduled_end <= poss_start_h or train.scheduled_start >= poss_end_h):
                    is_crit = (train.category.upper() in ("PREMIUM", "PREMIUM_PASSENGER"))
                    conflicts.append(ConflictItem(
                        id=f"CONF-TOPOLOGY-{train.id}-{possession.id}",
                        conflict_type=ConflictType.TRAIN_BLOCK,
                        severity="CRITICAL" if is_crit else "MAJOR",
                        block_id=list(overlap_tracks)[0],
                        title=f"Train Contention: {train.id} ({train.category}) vs Possession {possession.id}",
                        description=(
                            f"Train {train.id} traverses {list(overlap_tracks)} during possession window "
                            f"[T+{poss_start_h:.1f}h - T+{poss_end_h:.1f}h]."
                        ),
                        affected_jobs=[possession.job_id],
                        affected_trains=[train.id],
                        time_window={"start": max(train.scheduled_start, poss_start_h), "end": min(train.scheduled_end, poss_end_h)},
                        suggested_resolution="Divert via crossover TSL or apply MILP train regulation.",
                        blocks_approval=True,
                        validation_status=ValidationStatus.VALIDATED
                    ))
        return conflicts

    def get_assets_in_possession(
        self,
        possession_or_tracks: Any,
        start_km: Optional[float] = None,
        end_km: Optional[float] = None,
        assets: Optional[List[AssetHealthRecord]] = None
    ) -> List[Any]:
        """Identifies all physical assets situated within the possession boundary."""
        if isinstance(possession_or_tracks, PossessionEntity):
            s_km = possession_or_tracks.chainage_start_km
            e_km = possession_or_tracks.chainage_end_km
            target_assets = assets or []
        else:
            s_km = start_km or 0.0
            e_km = end_km or 80.0
            target_assets = assets or []
        
        in_boundary = []
        for ast in target_assets:
            if not (ast.chainage_end_km < s_km or ast.chainage_start_km > e_km):
                in_boundary.append(ast)
        return in_boundary

    def validate_topology_connectivity(self) -> Dict[str, Any]:
        """
        Validates corridor connectivity:
        - Detects disjoint corridor components (gaps > 0.5 km)
        - Detects orphaned tracks with no forward or backward links
        """
        issues: List[str] = []
        if not self.track_sections:
            return {"is_valid": False, "issues": ["Topology contains no track sections"], "components": [], "isolated_sections": [], "total_sections": 0}

        up_sections = sorted(
            [s for s in self.track_sections.values() if s.track_direction in ("UP", "BIDIRECTIONAL")],
            key=lambda s: s.chainage_start_km
        )

        components: List[List[str]] = []
        if up_sections:
            curr = [up_sections[0].id]
            curr_end = up_sections[0].chainage_end_km
            for s in up_sections[1:]:
                if s.chainage_start_km > curr_end + 0.5:
                    components.append(curr)
                    curr = [s.id]
                else:
                    curr.append(s.id)
                curr_end = max(curr_end, s.chainage_end_km)
            components.append(curr)

        is_connected = len(components) <= 1
        if not is_connected:
            issues.append(f"Topology has {len(components)} disconnected components along UP corridor.")

        isolated = [
            s_id for s_id in self.track_sections
            if not self.graph_forward.get(s_id) and not self.graph_backward.get(s_id)
        ]

        return {
            "is_valid": is_connected and len(isolated) == 0,
            "issues": issues,
            "components": components,
            "isolated_sections": isolated,
            "total_sections": len(self.track_sections)
        }
