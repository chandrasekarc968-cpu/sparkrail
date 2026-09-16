"""
Mean Time To Grant (MTTG) — measured, not assumed.

Specification Section 5.2:
    "Mean Time to Grant (MTTG) — Defined as the average elapsed time between
     the submission of a block demand in BDMS and the final operational
     approval from the Control Office. Algorithmic processing should reduce
     this from days to minutes for routine blocks."

Previously this KPI was hardcoded to 22.5 minutes in
``src/simulation/evaluator.py`` and defaulted to 22.5 in ``models.py``, so the
dashboard reported a number that was never derived from any event. This module
computes it from the real advisory lifecycle:

    submitted_at  = proposal["created_at"]                       (demand raised)
    granted_at    = approval_chain[STATION_MASTER]["timestamp"]  (field grant)

A proposal only counts once every role in the statutory chain has approved,
because until the Station Master issues the grant the block is not actually
available to the department that requested it.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

# Statutory four-tier approval chain (G&SR / Block Working Manual).
APPROVAL_CHAIN_ORDER: tuple = (
    "CTPC",
    "SR_DOM",
    "SECTION_CONTROLLER",
    "STATION_MASTER",
)

# The Station Master issues the operative field grant (physical protection in
# place), so this is the timestamp that terminates the MTTG interval.
FINAL_GRANT_ROLE: str = "STATION_MASTER"


def _parse_iso(value: Any) -> Optional[datetime]:
    """Tolerant ISO-8601 parser; returns None rather than raising."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _chain_is_complete(approval_chain: Dict[str, Any]) -> bool:
    """True only when every statutory role has recorded an APPROVED decision."""
    if not isinstance(approval_chain, dict) or not approval_chain:
        return False
    for role in APPROVAL_CHAIN_ORDER:
        entry = approval_chain.get(role)
        if not isinstance(entry, dict):
            return False
        if str(entry.get("status", "")).upper() != "APPROVED":
            return False
    return True


@dataclass(frozen=True)
class GrantRecord:
    """A single measured demand-to-grant interval."""

    demand_id: str
    submitted_at: datetime
    granted_at: datetime

    @property
    def elapsed_minutes(self) -> float:
        delta = self.granted_at - self.submitted_at
        return round(max(0.0, delta.total_seconds() / 60.0), 3)


class MTTGCalculator:
    """
    Accumulates grant records and reports the MTTG distribution.

    Deliberately returns ``None`` for ``mean_minutes`` when no fully-granted
    demand has been observed. Reporting an unmeasured KPI as a number is worse
    than reporting nothing, because it will be read as evidence.
    """

    def __init__(self, records: Optional[Iterable[GrantRecord]] = None) -> None:
        self.records: List[GrantRecord] = list(records or [])

    # -- construction -------------------------------------------------------
    def add(self, record: GrantRecord) -> None:
        self.records.append(record)

    def record(
        self, demand_id: str, submitted_at: Any, granted_at: Any
    ) -> Optional[GrantRecord]:
        submitted = _parse_iso(submitted_at)
        granted = _parse_iso(granted_at)
        if submitted is None or granted is None:
            return None
        if granted < submitted:
            return None
        rec = GrantRecord(demand_id=demand_id, submitted_at=submitted, granted_at=granted)
        self.add(rec)
        return rec

    @classmethod
    def from_proposals(cls, proposals: Iterable[Dict[str, Any]]) -> "MTTGCalculator":
        """
        Build from stored advisory proposals.

        Only proposals whose full statutory chain is APPROVED contribute a
        sample; pending or rejected demands have no grant to measure.
        """
        calc = cls()
        for proposal in proposals or []:
            if not isinstance(proposal, dict):
                continue
            if not _chain_is_complete(proposal.get("approval_chain", {})):
                continue
            submitted_at = proposal.get("created_at")
            granted_at = (
                proposal.get("approval_chain", {})
                .get(FINAL_GRANT_ROLE, {})
                .get("timestamp")
            )
            calc.record(
                demand_id=str(
                    proposal.get("optimization_run_id") or proposal.get("id") or "UNKNOWN"
                ),
                submitted_at=submitted_at,
                granted_at=granted_at,
            )
        return calc

    # -- reporting ----------------------------------------------------------
    @property
    def sample_count(self) -> int:
        return len(self.records)

    def elapsed_samples(self) -> List[float]:
        return [r.elapsed_minutes for r in self.records]

    def mean_minutes(self) -> Optional[float]:
        samples = self.elapsed_samples()
        return round(statistics.fmean(samples), 2) if samples else None

    def median_minutes(self) -> Optional[float]:
        samples = self.elapsed_samples()
        return round(statistics.median(samples), 2) if samples else None

    def p90_minutes(self) -> Optional[float]:
        samples = sorted(self.elapsed_samples())
        if not samples:
            return None
        # Nearest-rank percentile.
        idx = max(0, int(round(0.9 * (len(samples) - 1))))
        return round(samples[idx], 2)

    def summary(self) -> Dict[str, Any]:
        return {
            "mttg_minutes": self.mean_minutes(),
            "mttg_median_minutes": self.median_minutes(),
            "mttg_p90_minutes": self.p90_minutes(),
            "mttg_sample_count": self.sample_count,
            "mttg_measured": self.sample_count > 0,
        }


def unmeasured_summary() -> Dict[str, Any]:
    """Shape returned when no granted demand has been observed yet."""
    return {
        "mttg_minutes": None,
        "mttg_median_minutes": None,
        "mttg_p90_minutes": None,
        "mttg_sample_count": 0,
        "mttg_measured": False,
    }
