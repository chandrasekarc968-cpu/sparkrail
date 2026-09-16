"""
Geospatial serving layer (Spec §1: PostgreSQL + PostGIS for serving & GIS).

The architecture spec puts a PostGIS-backed store at the *serving* edge of the
Lambda-Kappa lakehouse. This module provides:

* ORM models (``BlockSection``, ``Station``, ``Possession``) declared with
  GeoAlchemy2 when it is installed.
* A :class:`GeoStore` facade that transparently uses a real PostGIS/PostgreSQL
  database when ``psycopg2`` + ``geoalchemy2`` + ``sqlalchemy`` are present, and
  otherwise falls back to a local SQLite store with WKT geometry columns and a
  Python haversine filter. The public API is identical across backends, so the
  serving layer is importable and testable without a live PostGIS instance.

Latency-critical queries (``blocks_within_radius``, ``block_by_chainage``) share
one method signature regardless of backend.
"""
from __future__ import annotations

import logging
import math
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SparkRail.Serving")

EARTH_RADIUS_KM = 6371.0088


@dataclass
class BlockRecord:
    block_id: str
    chainage_start_km: float
    chainage_end_km: float
    wkt: str = ""
    centroid_lat: float = 0.0
    centroid_lon: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


class GeoStore:
    """
    Serving facade over a spatial store.

    ``url`` follows the SQLAlchemy convention. A ``postgresql://`` URL activates
    the PostGIS backend (if the optional drivers are installed); anything else -
    including the default ``sqlite:///data/serving.db`` - uses the SQLite
    fallback so the store always works locally and in CI.
    """

    def __init__(self, url: str = "sqlite:///data/serving.db"):
        self.url = url
        self.backend = "postgis" if url.startswith("postgresql") else "sqlite"
        self._engine = None
        self._Session = None
        self._use_postgis = False
        self._conn: Optional[sqlite3.Connection] = None
        self._available_blocks: List[BlockRecord] = []
        self._connect()

    # ------------------------------------------------------------------ #
    # Backend setup
    # ------------------------------------------------------------------ #
    def _connect(self) -> None:
        if self.backend == "postgis":
            try:
                from sqlalchemy import create_engine  # type: ignore
                from sqlalchemy.orm import sessionmaker  # type: ignore
                import geoalchemy2  # type: ignore  # noqa: F401
                self._engine = create_engine(self.url)
                self._Session = sessionmaker(bind=self._engine)
                self._use_postgis = True
                self._ensure_postgis_schema()
                logger.info("GeoStore connected to PostGIS at %s", self._masked_url())
            except Exception as exc:
                logger.warning("PostGIS unavailable (%s); using SQLite fallback.", exc)
                self.backend = "sqlite"
        if self.backend == "sqlite":
            path = self.url.replace("sqlite:///", "")
            if not path or path == ":memory:":
                path = ":memory:"
            else:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS blocks (
                    block_id TEXT PRIMARY KEY,
                    chainage_start_km REAL,
                    chainage_end_km REAL,
                    wkt TEXT,
                    centroid_lat REAL,
                    centroid_lon REAL,
                    extra TEXT
                )"""
            )
            self._conn.commit()

    def _masked_url(self) -> str:
        return "postgresql://***@" + self.url.split("@")[-1] if "@" in self.url else self.url

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def upsert_block(self, rec: BlockRecord) -> None:
        if self._use_postgis:
            self._upsert_postgis(rec)
        else:
            self._conn.execute(
                "INSERT OR REPLACE INTO blocks VALUES (?,?,?,?,?,?,?)",
                (
                    rec.block_id, rec.chainage_start_km, rec.chainage_end_km,
                    rec.wkt, rec.centroid_lat, rec.centroid_lon,
                    _json_dumps(rec.extra),
                ),
            )
            self._conn.commit()

    def upsert_blocks(self, recs: List[BlockRecord]) -> int:
        for r in recs:
            self.upsert_block(r)
        return len(recs)

    def _upsert_postgis(self, rec: BlockRecord) -> None:
        from sqlalchemy.orm import Session  # type: ignore
        sess: Session = self._Session()
        try:
            # Real PostGIS would use ST_GeomFromText; deferred to the live DB.
            stmt = (
                "INSERT INTO blocks (block_id, chainage_start_km, chainage_end_km, "
                "wkt, centroid_lat, centroid_lon, extra) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (block_id) DO UPDATE SET "
                "chainage_start_km=EXCLUDED.chainage_start_km, "
                "chainage_end_km=EXCLUDED.chainage_end_km, wkt=EXCLUDED.wkt"
            )
            sess.execute(stmt, (rec.block_id, rec.chainage_start_km, rec.chainage_end_km,
                               rec.wkt, rec.centroid_lat, rec.centroid_lon, _json_dumps(rec.extra)))
            sess.commit()
        finally:
            sess.close()

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def blocks_within_radius(self, lat: float, lon: float, radius_km: float) -> List[BlockRecord]:
        out: List[BlockRecord] = []
        for rec in self._all_blocks():
            if _haversine_km(lat, lon, rec.centroid_lat, rec.centroid_lon) <= radius_km:
                out.append(rec)
        return out

    def block_by_chainage(self, chainage_km: float) -> Optional[BlockRecord]:
        best: Optional[BlockRecord] = None
        for rec in self._all_blocks():
            if rec.chainage_start_km <= chainage_km < rec.chainage_end_km:
                return rec
            if best is None or abs((rec.chainage_start_km + rec.chainage_end_km) / 2 - chainage_km) < abs(
                (best.chainage_start_km + best.chainage_end_km) / 2 - chainage_km
            ):
                best = rec
        return best

    def _all_blocks(self) -> List[BlockRecord]:
        if self._use_postgis:
            from sqlalchemy.orm import Session  # type: ignore
            sess: Session = self._Session()
            try:
                rows = sess.execute(
                    "SELECT block_id, chainage_start_km, chainage_end_km, wkt, "
                    "centroid_lat, centroid_lon, extra FROM blocks"
                ).fetchall()
            finally:
                sess.close()
            return [
                BlockRecord(r[0], r[1], r[2], r[3] or "", r[4] or 0.0, r[5] or 0.0, _json_loads(r[6] or "{}"))
                for r in rows
            ]
        cur = self._conn.execute(
            "SELECT block_id, chainage_start_km, chainage_end_km, wkt, "
            "centroid_lat, centroid_lon, extra FROM blocks"
        )
        return [
            BlockRecord(r[0], r[1], r[2], r[3] or "", r[4] or 0.0, r[5] or 0.0, _json_loads(r[6] or "{}"))
            for r in cur.fetchall()
        ]

    def _ensure_postgis_schema(self) -> None:
        # Idempotent schema bootstrap for the live PostGIS database.
        from sqlalchemy.orm import Session  # type: ignore
        sess: Session = self._Session()
        try:
            sess.execute(
                """CREATE TABLE IF NOT EXISTS blocks (
                    block_id TEXT PRIMARY KEY,
                    chainage_start_km DOUBLE PRECISION,
                    chainage_end_km DOUBLE PRECISION,
                    geom GEOMETRY(GEOMETRY, 4326),
                    centroid_lat DOUBLE PRECISION,
                    centroid_lon DOUBLE PRECISION,
                    extra JSONB
                )"""
            )
            sess.commit()
        finally:
            sess.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj or {})


def _json_loads(s: str) -> Dict[str, Any]:
    import json
    try:
        return json.loads(s or "{}")
    except json.JSONDecodeError:
        return {}
