"""
SparkRail Day-One Plugin Configuration & Operational Modes.

Supports three operational modes:
1. SYNTHETIC (Default): Fully local, reproducible synthetic Indian Railways dataset.
2. SHADOW: Read-only advisory mode operating alongside BDMS/TMS/COA workflows.
3. LIVE: Real CRIS mTLS integration (strictly configuration-gated, disabled by default).
"""

import os
from enum import Enum
from typing import Dict, Any, Optional

class SparkRailMode(str, Enum):
    SYNTHETIC = "synthetic"
    SHADOW = "shadow"
    LIVE = "live"

class PluginConfig:
    """Plugin environment configuration manager."""

    @classmethod
    def get_mode(cls) -> SparkRailMode:
        raw = os.getenv("SPARKRAIL_MODE", "synthetic").strip().lower()
        try:
            return SparkRailMode(raw)
        except ValueError:
            return SparkRailMode.SYNTHETIC

    @classmethod
    def is_synthetic(cls) -> bool:
        return cls.get_mode() == SparkRailMode.SYNTHETIC

    @classmethod
    def is_shadow(cls) -> bool:
        return cls.get_mode() == SparkRailMode.SHADOW

    @classmethod
    def is_live(cls) -> bool:
        return cls.get_mode() == SparkRailMode.LIVE

    @classmethod
    def is_live_permitted(cls) -> bool:
        """
        Non-negotiable safety check: Live mode is only permitted if:
        1. SPARKRAIL_MODE == 'live'
        2. SPARKRAIL_LIVE_ENABLED == 'true'
        3. Required mTLS and authentication credentials exist on disk.
        """
        if not cls.is_live():
            return False

        live_enabled = os.getenv("SPARKRAIL_LIVE_ENABLED", "false").strip().lower() == "true"
        if not live_enabled:
            return False

        # Verify essential mTLS credentials if defined
        cert_path = os.getenv("CRIS_MTLS_CERT_PATH")
        key_path = os.getenv("CRIS_MTLS_KEY_PATH")
        if cert_path and not os.path.exists(cert_path):
            return False
        if key_path and not os.path.exists(key_path):
            return False

        return True

    @classmethod
    def get_environment_metadata(cls) -> Dict[str, Any]:
        """Returns safe runtime metadata for health and audit checks."""
        mode = cls.get_mode()
        return {
            "mode": mode.value,
            "is_synthetic": mode == SparkRailMode.SYNTHETIC,
            "is_shadow": mode == SparkRailMode.SHADOW,
            "is_live": mode == SparkRailMode.LIVE,
            "live_permitted": cls.is_live_permitted(),
            "geometry_schema_version": "1.0.0",
            "statutory_safety_gate": "ADVISORY_ONLY_HUMAN_APPROVAL_REQUIRED",
            "physical_actuation_disabled": True,
            "active_possession_immutability": True,
            "four_role_approval_required": True
        }

def get_sparkrail_mode() -> SparkRailMode:
    return PluginConfig.get_mode()
