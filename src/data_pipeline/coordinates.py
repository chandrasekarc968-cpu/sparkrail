import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

from src.data_pipeline.models import Coordinate3D, CoordinateSystemContract, ValidationStatus

# Authoritative Surveyed Anchor Stations for Prayagraj (PRYJ) - Mirzapur (MZP) 80 km Corridor
# Coordinates: WGS-84 (EPSG:4326) Lat/Lon, Elevation in meters (AMSL)
CORRIDOR_SURVEY_ANCHORS: List[Dict[str, Any]] = [
    {"code": "SFG", "name": "Subedarganj", "km": 0.0, "lat": 25.4412, "lon": 81.7963, "elev_m": 98.0},
    {"code": "PRYJ", "name": "Prayagraj Jn", "km": 10.0, "lat": 25.4452, "lon": 81.8294, "elev_m": 98.5},
    {"code": "NYN", "name": "Naini Jn", "km": 20.0, "lat": 25.3946, "lon": 81.8672, "elev_m": 97.0},
    {"code": "KCN", "name": "Karchana", "km": 30.0, "lat": 25.3090, "lon": 81.9320, "elev_m": 96.0},
    {"code": "BEP", "name": "Bheepur", "km": 40.0, "lat": 25.2450, "lon": 82.0120, "elev_m": 95.5},
    {"code": "MJA", "name": "Meja Road", "km": 50.0, "lat": 25.1850, "lon": 82.1150, "elev_m": 94.0},
    {"code": "UND", "name": "Unchdih", "km": 60.0, "lat": 25.1520, "lon": 82.2300, "elev_m": 93.0},
    {"code": "MNF", "name": "Manda Road", "km": 70.0, "lat": 25.1380, "lon": 82.3850, "elev_m": 91.5},
    {"code": "MZP", "name": "Mirzapur", "km": 80.0, "lat": 25.1480, "lon": 82.5680, "elev_m": 89.0},
]

# Track Lateral Offset Constants (in meters)
LINE_OFFSETS = {
    "UP": 2.2,             # UP line shifted +2.2m laterally
    "DOWN": -2.2,          # DOWN line shifted -2.2m laterally
    "CENTERLINE": 0.0,     # Corridor center line
    "LOOP_UP": 6.5,        # UP loop line
    "LOOP_DOWN": -6.5,      # DOWN loop line
    "SIDING": 10.0          # Siding track
}

class CoordinateTransformError(ValueError):
    """Raised when coordinate transformation or CRS validation fails."""
    pass

class CoordinateTransformer:
    """
    Explicit transformation pipeline between:
    - Linear Referencing (chainage in km)
    - Local Corridor 3D Coordinates (metric X longitudinal, Y elevation, Z lateral)
    - Geographic WGS84 (EPSG:4326) Latitude, Longitude, Elevation
    """
    TRANSFORM_VERSION = "1.0.0"
    DEFAULT_TOTAL_KM = 80.0
    CORRIDOR_SCALED_X_SPAN = 800.0  # -400.0 to +400.0 in visual local corridor space

    def __init__(self, total_km: float = 80.0, default_crs: str = "LOCAL_CORRIDOR"):
        if not math.isfinite(total_km) or total_km <= 0.0:
            raise CoordinateTransformError(f"Invalid total_km: {total_km}. Must be positive finite.")
        self.total_km = float(total_km)
        self.default_crs = default_crs

    def get_contract(self, crs: Optional[str] = None, is_synthetic: bool = True) -> CoordinateSystemContract:
        target_crs = crs or self.default_crs
        if target_crs not in ("LOCAL_CORRIDOR", "EPSG:4326", "EPSG:32644"):
            raise CoordinateTransformError(f"Unsupported coordinate reference system: '{target_crs}'")

        if target_crs == "LOCAL_CORRIDOR":
            return CoordinateSystemContract(
                name="LOCAL_CORRIDOR",
                crs="LOCAL_CORRIDOR",
                units="meters",
                axis_order=["x", "y", "z"],
                handedness="right-handed",
                origin_description="Synthetic local origin for the bounded railway division",
                geometry_source="synthetic" if is_synthetic else "surveyed",
                transform_version=self.TRANSFORM_VERSION,
                is_synthetic=is_synthetic
            )
        else:
            return CoordinateSystemContract(
                name="WGS84 Geographic 2D/3D",
                crs="EPSG:4326",
                units="degrees",
                axis_order=["latitude", "longitude", "altitude"],
                handedness="right-handed",
                origin_description="WGS84 Ellipsoid, Indian Railways North Central Zone",
                geometry_source="surveyed" if not is_synthetic else "synthetic",
                transform_version=self.TRANSFORM_VERSION,
                is_synthetic=is_synthetic
            )

    def validate_chainage(self, chainage_km: float) -> float:
        """Validates that chainage is finite, non-negative, and within corridor limits."""
        if not isinstance(chainage_km, (int, float)) or not math.isfinite(chainage_km):
            raise CoordinateTransformError(f"Chainage must be a finite number, got: {chainage_km}")
        if chainage_km < 0.0:
            raise CoordinateTransformError(f"Chainage cannot be negative, got: {chainage_km} km")
        if chainage_km > self.total_km + 10.0:  # Allow 10 km corridor buffer
            raise CoordinateTransformError(f"Chainage {chainage_km} km exceeds corridor limit ({self.total_km} km)")
        return float(chainage_km)

    def chainage_to_local_corridor(
        self,
        chainage_km: float,
        lateral_offset_m: float = 0.0,
        track_direction: str = "CENTERLINE"
    ) -> Coordinate3D:
        """
        Converts corridor chainage (km) into local 3D Euclidean coordinates.
        - X: Longitudinal corridor position along track alignment (-400 to +400 m)
        - Y: Elevation profile with gentle bridge/flyover curvature
        - Z: Lateral curvature deviation + line separation offset
        """
        km = self.validate_chainage(chainage_km)
        ratio = km / max(1.0, self.total_km)

        # Longitudinal X axis
        x = -400.0 + (ratio * self.CORRIDOR_SCALED_X_SPAN)

        # Track line lateral offset (UP, DOWN, LOOP, etc.)
        line_offset = LINE_OFFSETS.get(track_direction.upper(), 0.0)
        total_lateral = line_offset + float(lateral_offset_m)

        # Z: Natural gentle railway curvature (max 16m lateral sweep) plus track separation
        z = math.sin(ratio * math.pi * 2.5) * 16.0 + total_lateral

        # Y: Elevation profile (bridge grade over Yamuna near Naini, Km 18-24)
        bridge_bump = 1.2 if (18.0 <= km <= 24.0) else 0.0
        y = math.sin(ratio * math.pi * 3.0) * 2.5 + bridge_bump

        return Coordinate3D(x=round(x, 3), y=round(y, 3), z=round(z, 3))

    def local_corridor_to_chainage(self, coord: Coordinate3D) -> float:
        """
        Inverts local corridor X coordinate back to linear chainage (km).
        """
        if not math.isfinite(coord.x):
            raise CoordinateTransformError(f"Non-finite X coordinate: {coord.x}")
        # x goes from -400.0 (0 km) to +400.0 (total_km)
        ratio = (coord.x + 400.0) / self.CORRIDOR_SCALED_X_SPAN
        ratio = max(0.0, min(1.0, ratio))
        return round(ratio * self.total_km, 3)

    def chainage_to_geographic(
        self,
        chainage_km: float,
        lateral_offset_m: float = 0.0
    ) -> Tuple[float, float, float]:
        """
        Maps linear chainage to geographic WGS-84 (Lat, Lon, Altitude_m)
        using piecewise linear interpolation between authoritative surveyed station anchors.
        """
        km = self.validate_chainage(chainage_km)

        # Find segment in CORRIDOR_SURVEY_ANCHORS
        anchors = CORRIDOR_SURVEY_ANCHORS
        for i in range(len(anchors) - 1):
            a0 = anchors[i]
            a1 = anchors[i + 1]
            if a0["km"] <= km <= a1["km"]:
                seg_len = a1["km"] - a0["km"]
                t = 0.0 if seg_len <= 0 else (km - a0["km"]) / seg_len
                lat = a0["lat"] + (a1["lat"] - a0["lat"]) * t
                lon = a0["lon"] + (a1["lon"] - a0["lon"]) * t
                elev = a0["elev_m"] + (a1["elev_m"] - a0["elev_m"]) * t

                # Apply lateral offset in degrees (approx 1 degree lat ~ 111,000m)
                if lateral_offset_m != 0.0:
                    d_deg = lateral_offset_m / 111000.0
                    lat += d_deg * 0.5
                    lon += d_deg * 0.5

                return round(lat, 6), round(lon, 6), round(elev, 2)

        # Beyond last anchor
        last = anchors[-1]
        return round(last["lat"], 6), round(last["lon"], 6), round(last["elev_m"], 2)

    def geographic_to_chainage(self, lat: float, lon: float) -> Tuple[float, float]:
        """
        Projects a geographic point (lat, lon) onto the corridor centerline.
        Returns: (chainage_km, distance_to_centerline_m)
        """
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise CoordinateTransformError(f"Non-finite lat/lon coordinates: ({lat}, {lon})")

        anchors = CORRIDOR_SURVEY_ANCHORS
        min_dist_m = float("inf")
        best_chainage_km = 0.0

        for i in range(len(anchors) - 1):
            a0 = anchors[i]
            a1 = anchors[i + 1]

            # Approximate Euclidean distance in meters on small flat patch
            # 1 deg lat ~ 111,139 m, 1 deg lon ~ 111,139 * cos(lat) m
            cos_lat = math.cos(math.radians(lat))
            x0 = (a0["lon"] - lon) * 111139.0 * cos_lat
            y0 = (a0["lat"] - lat) * 111139.0
            x1 = (a1["lon"] - lon) * 111139.0 * cos_lat
            y1 = (a1["lat"] - lat) * 111139.0

            dx = x1 - x0
            dy = y1 - y0
            seg_len_sq = dx * dx + dy * dy
            if seg_len_sq > 0:
                # Project point onto segment
                u = max(0.0, min(1.0, -(x0 * dx + y0 * dy) / seg_len_sq))
                proj_x = x0 + u * dx
                proj_y = y0 + u * dy
                dist = math.sqrt(proj_x * proj_x + proj_y * proj_y)
                if dist < min_dist_m:
                    min_dist_m = dist
                    best_chainage_km = a0["km"] + u * (a1["km"] - a0["km"])

        return round(best_chainage_km, 3), round(min_dist_m, 2)

    def round_trip_test(self, chainage_km: float, tolerance_km: float = 0.05) -> bool:
        """
        Validates round-trip consistency: chainage -> local_corridor -> chainage.
        """
        coord = self.chainage_to_local_corridor(chainage_km)
        reverted_km = self.local_corridor_to_chainage(coord)
        diff = abs(reverted_km - chainage_km)
        return diff <= tolerance_km
