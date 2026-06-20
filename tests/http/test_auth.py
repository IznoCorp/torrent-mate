"""Tests for the config-UI login: token signing + credential check + protected endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kanbanmate.http.auth import (
    AuthConfig,
    make_token,
    verify_credentials,
    verify_token,
)

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402


# --- pure auth primitives ---------------------------------------------------------------


def test_disabled_when_password_empty() -> None:
    cfg = AuthConfig(login="admin", password="", secret="s")
    assert cfg.enabled is False
    assert verify_credentials(cfg, "admin", "") is False  # never authenticates when disabled


def test_verify_credentials_ok_and_wrong() -> None:
    cfg = AuthConfig(login="admin", password="hunter2", secret="s")
    assert cfg.enabled is True
    assert verify_credentials(cfg, "admin", "hunter2") is True
    assert verify_credentials(cfg, "admin", "nope") is False
    assert verify_credentials(cfg, "root", "hunter2") is False


def test_token_round_trip_and_tamper_and_expiry() -> None:
    tok = make_token("admin", "secret", ttl=100, now=1000.0)
    assert verify_token(tok, "secret", now=1050.0) == "admin"
    # wrong secret → rejected
    assert verify_token(tok, "other", now=1050.0) is None
    # expired → rejected
    assert verify_token(tok, "secret", now=2000.0) is None
    # garbage → rejected, not raised
    assert verify_token("not-a-token", "secret") is None


# --- protected endpoints ----------------------------------------------------------------


def _root_with_config(tmp_path: Path) -> Path:
    """A registry + clone so /api/config can resolve a board."""
    from kanbanmate.core.transitions_defaults import render_transitions_yaml
    import importlib.resources as r

    root = tmp_path / "root"
    root.mkdir()
    ck = tmp_path / "clone" / ".claude" / "kanban"
    ck.mkdir(parents=True)
    ck.joinpath("transitions.yml").write_text(render_transitions_yaml("Org/repo"), encoding="utf-8")
    cols = (r.files("kanbanmate") / "assets" / "columns.yml.tmpl").read_text()
    ck.joinpath("columns.yml").write_text(cols, encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_x": {
                    "repo": "Org/repo",
                    "clone": str(tmp_path / "clone"),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                }
            }
        ),
        encoding="utf-8",
    )
    return root


def _client(tmp_path: Path, enabled: bool) -> TestClient:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _root_with_config(tmp_path)
    api_mod.app.state.auth = AuthConfig(
        login="admin", password="hunter2" if enabled else "", secret="testsecret"
    )
    return TestClient(api_mod.app)


def test_protected_endpoint_401_without_login(tmp_path: Path) -> None:
    with _client(tmp_path, enabled=True) as client:
        assert client.get("/api/config").status_code == 401
        # health + session stay open
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/session").json()["authenticated"] is False


def test_login_then_access(tmp_path: Path) -> None:
    with _client(tmp_path, enabled=True) as client:
        bad = client.post("/api/login", json={"login": "admin", "password": "wrong"})
        assert bad.status_code == 401
        ok = client.post("/api/login", json={"login": "admin", "password": "hunter2"})
        assert ok.status_code == 200 and ok.json()["authenticated"] is True
        # TestClient keeps the Set-Cookie → subsequent calls are authorised
        assert client.get("/api/config").status_code == 200
        assert client.get("/api/session").json()["authenticated"] is True
        client.post("/api/logout")
        assert client.get("/api/config").status_code == 401


def test_open_when_auth_disabled(tmp_path: Path) -> None:
    with _client(tmp_path, enabled=False) as client:
        # No password configured → no login required.
        assert client.get("/api/config").status_code == 200
        assert client.get("/api/session").json()["auth_enabled"] is False
