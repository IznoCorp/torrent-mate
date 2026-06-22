"""Tests for app/health_dashboard (bosun §7.1)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from kanbanmate.app.health_dashboard import build_health
from kanbanmate.core.heartbeat import Heartbeat, render_heartbeat
from kanbanmate.core.registry_resolve import safe_project_id


def _seed_project(root: Path) -> str:
    """Write a minimal ``projects.json`` and return the project id."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_x": {
                    "repo": "O/r",
                    "clone": str(root / "clone"),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                }
            }
        ),
        encoding="utf-8",
    )
    return "PVT_x"


def _seed_heartbeat(root: Path, pid: str, *, ts: float | None = None, ok: bool = True) -> None:
    """Write a per-project heartbeat marker."""
    hb_dir = root / "projects" / "heartbeats"
    hb_dir.mkdir(parents=True, exist_ok=True)
    hb_path = hb_dir / f"{safe_project_id(pid)}.heartbeat"
    hb_path.write_text(
        render_heartbeat(Heartbeat(ts=ts if ts is not None else time.time(), last_tick_ok=ok))
    )


def test_build_health_reports_project_row(tmp_path: Path) -> None:
    """A seeded project produces a genuine non-trivial row."""
    root = tmp_path / "root"
    pid = _seed_project(root)
    out = build_health(root)
    assert "projects" in out
    rows = out["projects"]
    assert len(rows) == 1
    row = rows[0]
    assert row["project_id"] == pid
    assert row["repo"] == "O/r"
    assert "daemon_alive" in row and "heartbeat_age_s" in row and "token_present" in row
    # No heartbeat seeded → daemon_alive should be False
    assert row["daemon_alive"] is False
    # No token seeded → token_present should be False
    assert row["token_present"] is False
    # No PAUSE sentinel
    assert out["pause_active"] is False


def test_pause_active_reflects_sentinel(tmp_path: Path) -> None:
    """PAUSE sentinel file toggles pause_active to True."""
    root = tmp_path / "root"
    _seed_project(root)
    (root / "PAUSE").write_text("", encoding="utf-8")
    assert build_health(root)["pause_active"] is True


def test_heartbeat_fresh_makes_daemon_alive(tmp_path: Path) -> None:
    """A fresh heartbeat (≤120s) → daemon_alive=True, both probes green."""
    root = tmp_path / "root"
    pid = _seed_project(root)
    _seed_heartbeat(root, pid, ts=time.time(), ok=True)
    row = build_health(root)["projects"][0]
    assert row["daemon_alive"] is True
    assert row["github_api_ok"] is True
    assert row["board_ok"] is True
    assert row["heartbeat_age_s"] >= 0.0


def test_heartbeat_stale_makes_daemon_dead(tmp_path: Path) -> None:
    """A stale heartbeat (>120s) → daemon_alive=False."""
    root = tmp_path / "root"
    pid = _seed_project(root)
    _seed_heartbeat(root, pid, ts=time.time() - 200.0, ok=True)
    row = build_health(root)["projects"][0]
    assert row["daemon_alive"] is False
    # last_tick_ok is still True → probes should remain green
    assert row["github_api_ok"] is True
    assert row["board_ok"] is True


def test_token_present_when_file_exists(tmp_path: Path) -> None:
    """A shared token file → token_present=True."""
    root = tmp_path / "root"
    _seed_project(root)
    (root / "token").write_text("ghp_fake", encoding="utf-8")
    row = build_health(root)["projects"][0]
    assert row["token_present"] is True


def test_session_secret_pinned_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """KANBAN_MATE_UI_SESSION_SECRET set → session_secret_pinned=True."""
    root = tmp_path / "root"
    _seed_project(root)
    monkeypatch.setenv("KANBAN_MATE_UI_SESSION_SECRET", "s3cr3t")
    assert build_health(root)["session_secret_pinned"] is True

    monkeypatch.delenv("KANBAN_MATE_UI_SESSION_SECRET", raising=False)
    assert build_health(root)["session_secret_pinned"] is False


def test_agents_waiting_counts_waiting_tickets(tmp_path: Path) -> None:
    """WAITING tickets across per-project state dirs are counted."""
    root = tmp_path / "root"
    pid = _seed_project(root)
    safe = safe_project_id(pid)
    state_dir = root / "projects" / safe / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    # One WAITING ticket
    (state_dir / "42.json").write_text(
        json.dumps({"status": "waiting", "heartbeat": time.time()}),
        encoding="utf-8",
    )
    # One RUNNING ticket (not counted)
    (state_dir / "43.json").write_text(
        json.dumps({"status": "running", "heartbeat": time.time()}),
        encoding="utf-8",
    )
    assert build_health(root)["agents_waiting"] == 1


def test_build_health_survives_corrupt_heartbeat(tmp_path: Path) -> None:
    """A corrupt heartbeat is signalled as UNKNOWN (read_error), distinct from measured-down.

    bosun review-c2: a parse failure must NOT be collapsed into "measured down" (which would paint a
    healthy project red and could trigger an unneeded restart). Instead heartbeat_age_s is None
    (unknown) and read_error is True; the dashboard still renders (no raise).
    """
    root = tmp_path / "root"
    pid = _seed_project(root)
    safe = safe_project_id(pid)
    hb_dir = root / "projects" / "heartbeats"
    hb_dir.mkdir(parents=True, exist_ok=True)
    (hb_dir / f"{safe}.heartbeat").write_text("garbage-not-json", encoding="utf-8")
    # Must NOT raise
    row = build_health(root)["projects"][0]
    assert row["daemon_alive"] is False
    assert row["heartbeat_age_s"] is None  # UNKNOWN, not the -1.0 measured-down sentinel
    assert row["read_error"] is True
    assert row["github_api_ok"] is False
    assert row["board_ok"] is False


def test_missing_heartbeat_is_down_not_read_error(tmp_path: Path) -> None:
    """A project with NO heartbeat file is measured-down (read_error False), not unknown."""
    root = tmp_path / "root"
    _seed_project(root)
    row = build_health(root)["projects"][0]
    assert row["daemon_alive"] is False
    assert row["heartbeat_age_s"] == -1.0  # measured-down sentinel, NOT None
    assert row["read_error"] is False


def test_fresh_heartbeat_has_no_read_error(tmp_path: Path) -> None:
    """A healthy fresh heartbeat reports read_error False (the row is a genuine measurement)."""
    root = tmp_path / "root"
    pid = _seed_project(root)
    _seed_heartbeat(root, pid, ts=time.time(), ok=True)
    row = build_health(root)["projects"][0]
    assert row["read_error"] is False
    assert row["daemon_alive"] is True


def test_build_health_no_registry_is_empty(tmp_path: Path) -> None:
    """An absent registry → empty projects list, no crash."""
    root = tmp_path / "root"
    out = build_health(root)
    assert out["projects"] == []
    assert out["pause_active"] is False
    assert out["agents_waiting"] == 0
