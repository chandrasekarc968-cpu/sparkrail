"""
Deployment Readiness and Smoke Verification Test Suite.
Verifies both deployment paths:
A. GitHub Pages (static artifacts, base paths, absence of sensitive secrets in bundles)
B. Shadow backend (health & readiness probes, CORS headers, environment metadata, live disabled)
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import PluginConfig, SparkRailMode

client = TestClient(app)


class TestDeploymentReadiness:
    # -------------------------------------------------------------------------
    # PATH A: GITHUB PAGES DEPLOYMENT READINESS
    # -------------------------------------------------------------------------
    def test_github_pages_dist_bundle_integrity(self):
        """Verifies that the frontend static distribution exists and includes SPA routing."""
        frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
        dist_dir = os.path.join(frontend_dir, "dist")
        index_html = os.path.join(dist_dir, "index.html")
        fallback_404 = os.path.join(frontend_dir, "public", "404.html")

        # index.html exists in dist
        assert os.path.exists(index_html), "Frontend bundle not built; dist/index.html missing."
        with open(index_html, "r", encoding="utf-8") as f:
            html_content = f.read()

        # No accidentally bundled secrets
        assert "DEV_ADMIN_TOKEN" not in html_content
        assert "super-secret" not in html_content

        # SPA 404 fallback exists for GitHub Pages routing
        assert os.path.exists(fallback_404), "GitHub Pages SPA redirect 404.html missing in public/"

    def test_vite_config_configurable_base_path(self):
        """Verifies vite.config.ts supports dynamic base path configuration for GitHub Pages."""
        vite_config = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "vite.config.ts"))
        with open(vite_config, "r", encoding="utf-8") as f:
            content = f.read()
        assert "VITE_BASE_PATH" in content, "Vite config must support VITE_BASE_PATH for GitHub Pages hosting."

    # -------------------------------------------------------------------------
    # PATH B: SHADOW BACKEND DEPLOYMENT READINESS
    # -------------------------------------------------------------------------
    def test_shadow_backend_health_and_readiness_probe(self):
        """Health endpoint /health must return 200 OK with runtime diagnostics."""
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") in ("healthy", "ok")
        assert "solver_available" in data
        assert "data_mode" in data

    def test_shadow_backend_environment_metadata(self):
        """Environment metadata confirms advisory-only and shadow mode flags."""
        meta = PluginConfig.get_environment_metadata()
        assert meta["statutory_safety_gate"] == "ADVISORY_ONLY_HUMAN_APPROVAL_REQUIRED"
        assert meta["physical_actuation_disabled"] is True
        assert meta["active_possession_immutability"] is True
        # Live mode must remain disabled
        assert meta["live_permitted"] is False

    def test_shadow_backend_cors_headers(self):
        """CORS headers must be present for decoupled frontend communication."""
        res = client.options(
            "/advisory/proposals",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST"
            }
        )
        assert res.status_code in (200, 204)
        # Access-Control-Allow-Origin header is present
        assert "access-control-allow-origin" in res.headers

    def test_dockerfile_and_compose_configurations_exist(self):
        """Docker deployment configurations must exist and adhere to security practices."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        dockerfile = os.path.join(root_dir, "Dockerfile")
        compose_file = os.path.join(root_dir, "docker-compose.yml")

        assert os.path.exists(dockerfile), "Production Dockerfile must be present."
        assert os.path.exists(compose_file), "docker-compose.yml must be present."

        with open(dockerfile, "r", encoding="utf-8") as f:
            df_content = f.read()
        # Security: non-root user
        assert "USER sparkrail" in df_content, "Dockerfile must execute under an unprivileged user."
        assert "SPARKRAIL_MODE=shadow" in df_content, "Dockerfile must default to SHADOW mode."
