"""Route tests for ``GET /api/maintenance/actions``.

Covers the actions catalog endpoint with both authenticated and
unauthenticated paths, plus structural assertions that the response
matches the registry ground truth.

Mirrors the structure of ``tests/web/test_maintenance_panels.py`` for
auth (``tm_session`` cookie via ``/api/auth/login``, ``https`` TestClient,
``tmp_path``-based ``data_dir``) and config-override idioms.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from personalscraper.web.maintenance.registry import REGISTRY

from .test_maintenance_panels import (
    _build_app,
    _build_authenticated_client,
)


class TestActionsList:
    """``GET /api/maintenance/actions`` — action catalog with category counts."""

    def test_actions_count_matches_registry(self, test_config, tmp_path: Path) -> None:
        """200 — ``actions`` list has the same length as the REGISTRY."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.get("/api/maintenance/actions")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["actions"]) == len(REGISTRY)

    def test_actions_all_ids_unique(self, test_config, tmp_path: Path) -> None:
        """200 — every action ``id`` is unique across the full registry."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.get("/api/maintenance/actions")
        assert resp.status_code == 200
        data = resp.json()

        ids = [a["id"] for a in data["actions"]]
        assert len(ids) == len(set(ids)), f"Duplicate action ids found: {[i for i in ids if ids.count(i) > 1]}"

    def test_actions_category_counts_sum(self, test_config, tmp_path: Path) -> None:
        """200 — ``category_counts`` values sum to the total number of actions."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.get("/api/maintenance/actions")
        assert resp.status_code == 200
        data = resp.json()

        assert sum(data["category_counts"].values()) == len(REGISTRY)

    def test_actions_unauthenticated(self, test_config, tmp_path: Path) -> None:
        """401 — no session cookie."""
        app, _settings = _build_app(test_config, tmp_path, with_auth=False)
        client = TestClient(app)
        resp = client.get("/api/maintenance/actions")
        assert resp.status_code == 401
