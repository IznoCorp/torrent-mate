"""Tests for app/audit (bosun §13)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from kanbanmate.app.audit import append_audit


def test_append_writes_expected_line(tmp_path: Path) -> None:
    append_audit(tmp_path, "operator", "pause_on", "active=true")
    log = (tmp_path / "control" / "audit.log").read_text(encoding="utf-8")
    assert "audit: operator operator pause_on: active=true" in log
    assert log.endswith("\n")


def test_append_is_additive(tmp_path: Path) -> None:
    append_audit(tmp_path, "op", "a", "1")
    append_audit(tmp_path, "op", "b", "2")
    lines = (tmp_path / "control" / "audit.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_append_logs_warning_on_write_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A write failure stays fail-soft (no raise) but leaves a logged breadcrumb (review-c2).

    PAUSE-toggle and project-delete are recorded ONLY in the audit log, so a silent drop there would
    erase the only trace of a privileged act. Assert append_audit does not raise AND logs a warning.
    """
    # Make <root>/control a FILE so creating it as a directory fails (NotADirectoryError/FileExists)
    # — a realistic "control/ not writable" mode. append_audit must swallow the error and log it.
    (tmp_path / "control").write_text("not a dir", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="kanbanmate.app.audit"):
        append_audit(tmp_path, "op", "pause", "active=True")  # must NOT raise
    assert any("audit append failed" in r.message for r in caplog.records)


def test_actor_login_authenticated_records_real_operator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auth ENABLED + a logged-in distinct user → the audit line carries that login, not 'operator'.

    Pins the _actor_login authenticated branch (review-c2): the verified session login becomes the
    audit attribution. Drives a real mutating admin route (POST /api/admin/pause) so the full chain
    login → session cookie → _actor_login → append_audit is exercised end-to-end.
    """
    pytest.importorskip("fastapi", reason="[ui] extra not installed")
    from fastapi.testclient import TestClient

    import kanbanmate.http.admin_routes  # noqa: F401  (register the admin routes)
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.http.auth import AuthConfig

    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text("{}", encoding="utf-8")
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = AuthConfig(login="alice", password="pw", secret="s3cr3t")

    with TestClient(api_mod.app) as client:
        login = client.post("/api/login", json={"login": "alice", "password": "pw"})
        assert login.status_code == 200 and login.json()["authenticated"] is True
        token = client.cookies.get("km_csrf")
        assert token
        r = client.post("/api/admin/pause", json={"active": True}, headers={"X-KM-CSRF": token})
        assert r.status_code == 200

    log = (root / "control" / "audit.log").read_text(encoding="utf-8")
    # The real operator login 'alice' is recorded — NOT the open-mode literal 'operator'.
    assert "audit: operator alice pause: active=True" in log
