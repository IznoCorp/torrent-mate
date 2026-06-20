"""The static SPA mount serves the build when present and degrades gracefully when absent.

Both states are exercised via ``install_spa_mount`` on a FRESH app + a tmp dir, so the
result does not depend on whether the package's ``webui/`` happens to be built locally.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from kanbanmate.http.config_api import app, install_spa_mount  # noqa: E402


def test_absent_build_serves_friendly_message_not_500(tmp_path: Path) -> None:
    fresh = FastAPI()
    install_spa_mount(fresh, tmp_path / "no-webui")  # dir without index.html
    with TestClient(fresh) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "build" in resp.text.lower() or "npm" in resp.text.lower()


def test_present_build_is_served(tmp_path: Path) -> None:
    webui = tmp_path / "webui"
    webui.mkdir()
    (webui / "index.html").write_text("<!doctype html><title>bridge</title>", encoding="utf-8")
    fresh = FastAPI()
    install_spa_mount(fresh, webui)
    with TestClient(fresh) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "bridge" in resp.text.lower()


def test_api_health_still_works_on_real_app() -> None:
    # The real app mounts the SPA (built or fallback); /api/* must keep working either way.
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
