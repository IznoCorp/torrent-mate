"""Tests for PAUSE kill-switch toggle route (bosun §7.3, sub-phase 2.6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path) -> Any:
    """Bootstrap the config API with a minimal project, auth off, routes registered."""
    import kanbanmate.http.config_api as api_mod

    import kanbanmate.http.admin_routes  # noqa: F401

    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_x": {
                    "repo": "O/r",
                    "clone": str(tmp_path / "clone"),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                }
            }
        ),
        encoding="utf-8",
    )
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None  # auth disabled → isolate pause
    return api_mod


# ── GET /api/admin/pause ──────────────────────────────────────────────────────


def test_pause_get_returns_false_when_no_sentinel(tmp_path: Path) -> None:
    """GET /api/admin/pause reports active=false when PAUSE sentinel is absent."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/pause")
        assert r.status_code == 200
        assert r.json()["active"] is False


# ── POST /api/admin/pause ─────────────────────────────────────────────────────


def test_pause_on_creates_sentinel_and_store_sees_it(tmp_path: Path) -> None:
    """POST /api/admin/pause {active:true} creates the PAUSE sentinel; store agrees (ACC-09)."""
    api_mod = _setup(tmp_path)
    from kanbanmate.adapters.store.fs_store import FsStateStore

    with TestClient(api_mod.app) as client:
        # Mint the CSRF cookie so the POST reaches the handler.
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/pause",
            json={"active": True},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200
        assert r.json()["active"] is True
        assert (api_mod.app.state.kanban_root / "PAUSE").exists()
        # Cross-check the daemon's own reader agrees.
        store = FsStateStore(api_mod.app.state.kanban_root)
        assert store.kill_switch_active() is True


def test_pause_off_removes_sentinel(tmp_path: Path) -> None:
    """POST /api/admin/pause {active:false} removes the PAUSE sentinel."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        # First, turn PAUSE on.
        r1 = client.post(
            "/api/admin/pause",
            json={"active": True},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r1.status_code == 200 and r1.json()["active"] is True
        # Then turn it off.
        r2 = client.post(
            "/api/admin/pause",
            json={"active": False},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r2.status_code == 200
        assert r2.json()["active"] is False
        assert not (api_mod.app.state.kanban_root / "PAUSE").exists()


def test_pause_toggle_is_idempotent(tmp_path: Path) -> None:
    """Toggling PAUSE on twice / off twice is idempotent."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        h = {"X-KM-CSRF": token} if token else {}
        # On twice.
        r1 = client.post("/api/admin/pause", json={"active": True}, headers=h)
        assert r1.status_code == 200 and r1.json()["active"] is True
        r2 = client.post("/api/admin/pause", json={"active": True}, headers=h)
        assert r2.status_code == 200 and r2.json()["active"] is True
        assert (api_mod.app.state.kanban_root / "PAUSE").exists()
        # Off twice.
        r3 = client.post("/api/admin/pause", json={"active": False}, headers=h)
        assert r3.status_code == 200 and r3.json()["active"] is False
        r4 = client.post("/api/admin/pause", json={"active": False}, headers=h)
        assert r4.status_code == 200 and r4.json()["active"] is False
        assert not (api_mod.app.state.kanban_root / "PAUSE").exists()
