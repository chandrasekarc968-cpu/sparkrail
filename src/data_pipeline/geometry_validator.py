import math
from typing import Dict, Any, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from src.data_pipeline.models import (
    NetworkGeometryResponse,
    GeometryTrack,
    GeometryNode,
    StationNode,
    SignalMarker,
    OHEMast,
    Coordinate3D,
    Scenario
)

class GeometryValidationError(ValueError):
    """Raised when railway 3D network geometry violates spatial or topological invariants."""
    pass

class GeometryValidationResult(BaseModel):
    is_valid: bool
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    disconnected_components: List[List[str]] = Field(default_factory=list)
    total_tracks_checked: int = 0
    total_nodes_checked: int = 0

DEFAULT_BOUNDS = {
    "min_x": -1000.0,
    "max_x": 1000.0,
    "min_y": -50.0,
    "max_y": 150.0,
    "min_z": -200.0,
    "max_z": 200.0
}

def _check_coord_finite_and_bounds(
    coord: Coordinate3D,
    name: str,
    issues: List[str],
    bounds: Dict[str, float]
):
    for axis, val in [("x", coord.x), ("y", coord.y), ("z", coord.z)]:
        if not math.isfinite(val):
            issues.append(f"{name} has non-finite coordinate {axis}={val}")
            return
        min_b = bounds.get(f"min_{axis}")
        max_b = bounds.get(f"max_{axis}")
        if min_b is not None and val < min_b:
            issues.append(f"{name} {axis}={val} is below minimum bound ({min_b})")
        if max_b is not None and val > max_b:
            issues.append(f"{name} {axis}={val} exceeds maximum bound ({max_b})")

def validate_network_geometry(
    geometry: NetworkGeometryResponse,
    scenario: Optional[Scenario] = None,
    bounds: Optional[Dict[str, float]] = None,
    raise_on_error: bool = False
) -> GeometryValidationResult:
    """
    Validates complete spatial, physical, and topological invariants of railway network geometry:
    1. Coordinate validity: finite numbers, not NaN/Infinity, within corridor bounding envelope.
    2. Unique ID enforcement: no missing or duplicate IDs across nodes, tracks, signals, and masts.
    3. Track geometry integrity: >= 2 path points, positive length, chainage_start < chainage_end, no negative chainage.
    4. Topological consistency: referenced blocks and assets exist in scenario definition.
    5. Connectivity: checks corridor continuity and flags disconnected components unless explicitly declared.
    6. Co-location: flags accidental exact duplicate nodes or duplicate track segments.
    """
    effective_bounds = {**DEFAULT_BOUNDS, **(bounds or {})}
    issues: List[str] = []
    warnings: List[str] = []

    # 1. Geometry Schema Version and Coordinate System Contract Validation
    schema_ver = getattr(geometry, "geometry_schema_version", None)
    if not schema_ver:
        issues.append("NetworkGeometryResponse is missing required field 'geometry_schema_version'")
    elif not str(schema_ver).startswith("1."):
        issues.append(f"Incompatible geometry_schema_version '{schema_ver}'. Expected major version 1.")

    coord_sys = getattr(geometry, "coordinate_system", None)
    if not coord_sys:
        issues.append("NetworkGeometryResponse is missing required field 'coordinate_system'")
    else:
        if coord_sys.name != "LOCAL_CORRIDOR":
            issues.append(f"coordinate_system.name must be 'LOCAL_CORRIDOR', got '{coord_sys.name}'")
        if coord_sys.crs != "LOCAL_CORRIDOR":
            issues.append(f"coordinate_system.crs must be 'LOCAL_CORRIDOR', got '{coord_sys.crs}'")
        if coord_sys.units != "meters":
            issues.append(f"coordinate_system.units must be 'meters', got '{coord_sys.units}'")
        if coord_sys.axis_order != ["x", "y", "z"]:
            issues.append(f"coordinate_system.axis_order must be ['x', 'y', 'z'], got {coord_sys.axis_order}")
        if coord_sys.handedness != "right-handed":
            issues.append(f"coordinate_system.handedness must be 'right-handed', got '{coord_sys.handedness}'")
        if coord_sys.geometry_source not in ("synthetic", "surveyed"):
            issues.append(f"coordinate_system.geometry_source must be 'synthetic' or 'surveyed', got '{coord_sys.geometry_source}'")

    # 2. Total Length
    if not math.isfinite(geometry.total_length_km) or geometry.total_length_km <= 0.0:
        issues.append(f"Network total_length_km must be a positive finite number, got {geometry.total_length_km}")

    # 2. Node Validation
    node_ids: Set[str] = set()
    node_positions: List[Tuple[float, float, float, str]] = []

    for node in geometry.nodes:
        # ID check
        if not node.id or not str(node.id).strip():
            issues.append("Found StationNode with missing or empty ID.")
            continue
        if node.id in node_ids:
            issues.append(f"Duplicate node ID detected: '{node.id}'")
        node_ids.add(node.id)

        # Coordinate check
        pos = node.coordinates or node.position
        if pos is None:
            issues.append(f"Node '{node.id}' has missing coordinates.")
        else:
            _check_coord_finite_and_bounds(pos, f"Node '{node.id}'", issues, effective_bounds)
            # Check for duplicate exact co-location with another node
            for px, py, pz, other_id in node_positions:
                dist = math.sqrt((pos.x - px) ** 2 + (pos.y - py) ** 2 + (pos.z - pz) ** 2)
                if dist < 0.001:
                    issues.append(f"Duplicate node co-location: Node '{node.id}' co-located with '{other_id}' (dist={dist:.4f}m)")
            node_positions.append((pos.x, pos.y, pos.z, node.id))

        # Chainage check
        if not math.isfinite(node.chainage_km) or node.chainage_km < 0.0:
            issues.append(f"Node '{node.id}' has invalid chainage_km ({node.chainage_km}). Must be non-negative finite.")

        # Platforms
        if node.platforms < 1:
            issues.append(f"Node '{node.id}' must have at least 1 platform, got {node.platforms}")

    # 3. Track Validation
    track_ids: Set[str] = set()
    track_blocks: Set[str] = set()

    for track in geometry.tracks:
        # ID and Block ID
        t_id = track.id or f"TRACK_{track.block_id}"
        if t_id in track_ids:
            issues.append(f"Duplicate track ID detected: '{t_id}'")
        track_ids.add(t_id)

        if not track.block_id or not str(track.block_id).strip():
            issues.append(f"Track '{t_id}' has missing or empty block_id.")
        elif track.block_id in track_blocks:
            issues.append(f"Duplicate track segment for block_id: '{track.block_id}'")
        track_blocks.add(track.block_id)

        # Path points check
        if len(track.path_points) < 2:
            issues.append(f"Track '{track.block_id}' path_points has {len(track.path_points)} points. Minimum required is 2.")

        for idx, pt in enumerate(track.path_points):
            _check_coord_finite_and_bounds(pt, f"Track '{track.block_id}' path_point[{idx}]", issues, effective_bounds)

        # Start and End coordinates
        _check_coord_finite_and_bounds(track.start_coord, f"Track '{track.block_id}' start_coord", issues, effective_bounds)
        _check_coord_finite_and_bounds(track.end_coord, f"Track '{track.block_id}' end_coord", issues, effective_bounds)

        # Chainage invariants
        if not math.isfinite(track.chainage_start) or track.chainage_start < 0.0:
            issues.append(f"Track '{track.block_id}' has invalid chainage_start: {track.chainage_start}")
        if not math.isfinite(track.chainage_end) or track.chainage_end <= 0.0:
            issues.append(f"Track '{track.block_id}' has invalid chainage_end: {track.chainage_end}")
        if math.isfinite(track.chainage_start) and math.isfinite(track.chainage_end):
            if track.chainage_start >= track.chainage_end:
                issues.append(
                    f"Track '{track.block_id}' reversed or zero-length chainage: "
                    f"chainage_start ({track.chainage_start}) >= chainage_end ({track.chainage_end})"
                )

        # Length check
        if not math.isfinite(track.length_km) or track.length_km <= 0.0:
            issues.append(f"Track '{track.block_id}' has non-positive or non-finite length_km: {track.length_km}")

        # Speed restriction check
        if not math.isfinite(track.speed_limit_kmh) or track.speed_limit_kmh <= 0.0:
            issues.append(f"Track '{track.block_id}' speed_limit_kmh must be positive finite, got {track.speed_limit_kmh}")

    # 4. Signal and Mast Unique IDs & Finite Coordinates
    signal_ids: Set[str] = set()
    for sig in geometry.signals:
        if not sig.id:
            issues.append("Found SignalMarker with missing ID.")
            continue
        if sig.id in signal_ids:
            issues.append(f"Duplicate SignalMarker ID detected: '{sig.id}'")
        signal_ids.add(sig.id)
        pos = sig.coordinates or sig.position
        _check_coord_finite_and_bounds(pos, f"Signal '{sig.id}'", issues, effective_bounds)
        if not math.isfinite(sig.chainage_km) or sig.chainage_km < 0.0:
            issues.append(f"Signal '{sig.id}' has invalid chainage_km: {sig.chainage_km}")

    mast_ids: Set[str] = set()
    for mast in geometry.ohe_masts:
        if not mast.id:
            issues.append("Found OHEMast with missing ID.")
            continue
        if mast.id in mast_ids:
            issues.append(f"Duplicate OHEMast ID detected: '{mast.id}'")
        mast_ids.add(mast.id)
        pos = mast.coordinates or mast.position
        _check_coord_finite_and_bounds(pos, f"OHEMast '{mast.id}'", issues, effective_bounds)

    # 5. Scenario Cross-Reference Validation
    if scenario:
        valid_scenario_blocks = {b.id for b in scenario.blocks}

        for track in geometry.tracks:
            if track.block_id not in valid_scenario_blocks:
                issues.append(f"Track '{track.block_id}' references unknown block_id '{track.block_id}' not in scenario.")

        for node in geometry.nodes:
            for blk in node.connected_blocks:
                if blk not in valid_scenario_blocks:
                    issues.append(f"Node '{node.id}' references unknown connected block '{blk}' not in scenario.")

        for sig in geometry.signals:
            if sig.block_id not in valid_scenario_blocks:
                issues.append(f"Signal '{sig.id}' references unknown block_id '{sig.block_id}' not in scenario.")

        for mast in geometry.ohe_masts:
            if mast.block_id not in valid_scenario_blocks:
                issues.append(f"OHEMast '{mast.id}' references unknown block_id '{mast.block_id}' not in scenario.")

    # 6. Topological Connectivity Analysis
    # Sort tracks by chainage_start to detect gaps or disjoint corridors
    sorted_tracks = sorted(geometry.tracks, key=lambda t: t.chainage_start)
    components: List[List[str]] = []
    if sorted_tracks:
        curr_component = [sorted_tracks[0].block_id]
        curr_end_km = sorted_tracks[0].chainage_end

        for t in sorted_tracks[1:]:
            # If gap between tracks exceeds 0.5km without transition
            if t.chainage_start > curr_end_km + 0.5:
                components.append(curr_component)
                curr_component = [t.block_id]
            else:
                curr_component.append(t.block_id)
            curr_end_km = max(curr_end_km, t.chainage_end)
        components.append(curr_component)

    # If there are multiple disconnected corridor components:
    if len(components) > 1:
        # Check if the geometry response explicitly reports them
        reported_components = geometry.disconnected_components
        if not reported_components:
            issues.append(
                f"Disconnected geometry detected ({len(components)} separate corridor components: "
                f"{[c[0]+'..'+c[-1] for c in components]}), but response does not declare disconnected_components."
            )

    result = GeometryValidationResult(
        is_valid=(len(issues) == 0),
        issues=issues,
        warnings=warnings,
        disconnected_components=components,
        total_tracks_checked=len(geometry.tracks),
        total_nodes_checked=len(geometry.nodes)
    )

    if raise_on_error and not result.is_valid:
        raise GeometryValidationError("; ".join(issues))

    return result
