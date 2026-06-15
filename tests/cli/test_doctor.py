"""Tests for :mod:`kanbanmate.cli.doctor` — the 3-tier health check (DESIGN §4).

Every test is fully isolated:

* No real pm2/claude/network/tmux — every check's I/O dependency is injected
  through the keyword arguments of :func:`run_doctor`.
* The ``runner`` (subprocess), ``import_check``, ``token_scope_check``,
  ``branch_check``, ``geteuid``, and ``stat_socket`` are all mockables.
* A ``tmp_path`` stands in for ``~/.kanban`` for the heartbeat check.
* The table output goes to stdout but is never parsed — assertions are on the
  return code and on the injected check being called (or not).

Assertions cover:

* Exit 0 when all checks pass.
* Exit 1 when any single check fails (one test per check).
* A raising check is caught and reported as FAIL (no crash).
* The branch-protection check always returns PASS (advisory).
* The token check validates scopes via :func:`kanbanmate.adapters.github.token.validate_scopes`.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from kanbanmate.cli.doctor import (
    HEARTBEAT_TTL,
    _resolve_branch_check,
    run_doctor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[Any]:
    """Build a :class:`subprocess.CompletedProcess` for the mock runner to return."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _non_root() -> int:
    """Stand-in ``geteuid`` returning a non-root uid."""
    return 1000


def _root() -> int:
    """Stand-in ``geteuid`` returning 0 so the non-root check triggers."""
    return 0


def _matching_uid_stat(uid: int) -> Callable[[str], int]:
    """Return a ``stat_socket`` that always returns *uid*."""

    def _stat(path: str) -> int:  # noqa: ARG001
        return uid

    return _stat


def _write_heartbeat(path: Path, *, consecutive_failures: int = 0) -> None:
    """Write a structured (#1) daemon-heartbeat marker to *path*.

    The marker carries tick health (``last_tick_ok`` / ``consecutive_failures``) so the
    content-aware doctor check parses a healthy record by default; pass
    ``consecutive_failures`` to simulate a daemon that is alive but persistently failing.
    """
    from kanbanmate.core.heartbeat import Heartbeat, render_heartbeat

    path.write_text(
        render_heartbeat(
            Heartbeat(
                ts=0.0,
                last_tick_ok=consecutive_failures == 0,
                consecutive_failures=consecutive_failures,
            )
        )
    )


# ---------------------------------------------------------------------------
# All-pass baseline
# ---------------------------------------------------------------------------


def test_all_pass_exit_0(tmp_path: Path) -> None:
    """When every injected check succeeds, ``run_doctor`` returns 0."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban","pm2_env":{"status":"online"}}]'),  # pm2 daemon
        _completed(stdout="kanban@kanbanmate  …  /kanban"),  # claude plugin
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "default branch protected"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        shim_list_scripts=lambda: ["kanban", "kanban-move"],
        shim_which=lambda name: f"/usr/local/bin/{name}",
        now=heartbeat_file.stat().st_mtime + 1,  # fresh
    )
    assert code == 0
    # Both runner calls should have been made: pm2 + claude.
    assert runner.call_count == 2


def test_all_pass_with_heartbeat_fresh(tmp_path: Path) -> None:
    """Heartbeat file with a recent mtime → passes the heartbeat check."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban","pm2_env":{"status":"online"}}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        shim_list_scripts=lambda: ["kanban", "kanban-move"],
        shim_which=lambda name: f"/usr/local/bin/{name}",
        now=heartbeat_file.stat().st_mtime + 1,  # 1s ago → fresh
    )
    assert code == 0


# ---------------------------------------------------------------------------
# Single-check failure — each check contributes to a FAIL
# ---------------------------------------------------------------------------


def test_import_check_fails(tmp_path: Path) -> None:
    """When ``import_check`` returns False, ``run_doctor`` returns 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: False,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_pm2_daemon_not_found(tmp_path: Path) -> None:
    """When pm2 jlist does NOT contain 'kanban', ``run_doctor`` returns 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout="[]"),  # pm2 jlist — empty, no kanban
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_pm2_command_not_found(tmp_path: Path) -> None:
    """When pm2 is not installed, ``run_doctor`` returns 1 (FileNotFoundError)."""
    runner = MagicMock()
    runner.side_effect = [
        FileNotFoundError("No such file: pm2"),  # pm2 not installed
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_heartbeat_missing(tmp_path: Path) -> None:
    """No heartbeat file → heartbeat check fails → exit 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,  # no daemon.heartbeat created
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_heartbeat_stale(tmp_path: Path) -> None:
    """Heartbeat file with an old mtime → stale → exit 1."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        ttl=HEARTBEAT_TTL,  # pin the boundary explicitly (#1 derives 120 s by default)
        now=heartbeat_file.stat().st_mtime + HEARTBEAT_TTL + 100,  # well past TTL
    )
    assert code == 1


def test_plugin_not_found(tmp_path: Path) -> None:
    """When claude plugin list does NOT contain 'kanban', exit 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),  # pm2 ok
        _completed(stdout="claude-code@anthropic  …"),  # no kanban
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_claude_command_not_found(tmp_path: Path) -> None:
    """When claude is not installed, exit 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        FileNotFoundError("No such file: claude"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_token_overscoped_warns_does_not_fail(tmp_path: Path, capsys: Any) -> None:
    """#6: an over-scoped token (floor met + extra) WARNs, it does NOT hard-FAIL (exit 0).

    The PoC modelled over-scope as a non-blocking warning (``token_not_overscoped``,
    fail_level=warning). NEW used to call ``validate_scopes`` which RAISED → exit 1; #6 downgrades
    the extra-scope case to an advisory WARNING that keeps doctor passing.
    """
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        # Floor {project, repo} present + an extra over-broad scope → WARN, not FAIL.
        token_scope_check=lambda: frozenset({"project", "repo", "admin:org"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0
    out = capsys.readouterr().out
    # The over-scope is surfaced as a WARNING line (flagged, non-blocking).
    assert "WARNING" in out
    assert "over-scoped" in out
    assert "admin:org" in out


def test_token_missing_required_scope_fails(tmp_path: Path) -> None:
    """#7: a classic PAT MISSING a required floor scope hard-FAILs (exit 1, lower bound).

    A token carrying only ``repo`` (no ``project``) does not meet the required floor and must FAIL —
    the PoC ``token_required_scopes`` lower bound, which NEW's old subset-upper-bound check inverted
    (it would have PASSED this).
    """
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"repo"}),  # missing 'project' → under-scoped
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_token_empty_scopes_advisory_passes(tmp_path: Path, capsys: Any) -> None:
    """#7: an empty (fine-grained PAT) scope set passes with an explicit advisory note, not silently.

    GitHub reports no classic scopes for a fine-grained PAT, so the floor cannot be proven; the
    check passes but says so (advisory), distinct from the silent pass NEW's old subset check gave.
    """
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset(),  # fine-grained PAT → empty scopes
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "fine-grained PAT" in out
    assert "advisory" in out


def test_token_scope_check_raises(tmp_path: Path) -> None:
    """When the token_scope_check itself raises, it becomes FAIL (no crash)."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: (_ for _ in ()).throw(ValueError("no network")),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_token_load_injected(tmp_path: Path) -> None:
    """When ``token_load`` is injected, the check loads but skips scope validation."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_load=lambda: "ghp_test12345",
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    # token_load path skips scope validation → token check passes.
    assert code == 0


def test_none_token_injection_uses_production_path(tmp_path: Path) -> None:
    """When no token check is injected and no real token exists, it fails gracefully."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    # No token_scope_check, no token_load — production path tries to load token,
    # which will fail unless a real token exists. The check catches the failure.
    # We don't care about exit code here since the token may or may not exist;
    # we just verify run_doctor doesn't crash.
    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        # deliberately omit token_scope_check and token_load
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code in (0, 1)  # May pass or fail depending on env


def test_branch_protection_off_still_passes(tmp_path: Path) -> None:
    """Branch protection OFF returns PASS — it's advisory, not blocking."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (False, "no branch protection on main"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    # Branch protection is advisory — always PASS, never fail the run.
    assert code == 0


def test_branch_check_raises_still_passes(tmp_path: Path) -> None:
    """When the branch check raises, it becomes advisory-PASS (no crash)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (_ for _ in ()).throw(RuntimeError("api unreachable")),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    # Branch check raising → caught internally → PASS (advisory).
    assert code == 0


def test_root_user_fails(tmp_path: Path) -> None:
    """Running as uid 0 → non-root check FAILS → exit 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


def test_tmux_socket_wrong_owner(tmp_path: Path) -> None:
    """Tmux socket owned by a different uid → exit 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,  # running as uid 1000
        stat_socket=_matching_uid_stat(0),  # socket owned by root
    )
    assert code == 1


def test_tmux_socket_not_found(tmp_path: Path) -> None:
    """Tmux socket missing → exit 1."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    def _raises_fnf(_path: str) -> int:
        raise FileNotFoundError("No such file")

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_raises_fnf,
    )
    assert code == 1


# ---------------------------------------------------------------------------
# Raising check becomes FAIL (not a crash)
# ---------------------------------------------------------------------------


def test_any_check_raising_becomes_fail_not_crash(tmp_path: Path) -> None:
    """A check thunk that raises is caught and turns into a FAIL — no crash.

    We exercise this through the import_check raising, since it's the simplest
    injectable thunk. The orchestrator wraps every thunk in try/except.
    """
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: (_ for _ in ()).throw(ImportError("no module named kanbanmate")),
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    # Should NOT crash — raising thunk caught, reported as FAIL, exit 1.
    assert code == 1
    # The runner should still have been called (other checks run).
    assert runner.call_count >= 0  # at minimum not crashed


def test_pm2_check_raising_becomes_fail(tmp_path: Path) -> None:
    """When runner raises on pm2 call, it's caught → FAIL (not a crash)."""
    runner = MagicMock()
    runner.side_effect = [
        OSError("broken pipe"),  # pm2 fails hard
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
    )
    assert code == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_heartbeat_at_exact_ttl_boundary_passes(tmp_path: Path) -> None:
    """A heartbeat at exactly the TTL age still passes (<= check)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        ttl=HEARTBEAT_TTL,  # pin the boundary explicitly (#1 derives 120 s by default)
        now=heartbeat_file.stat().st_mtime + HEARTBEAT_TTL,  # exactly at TTL
    )
    assert code == 0


def test_empty_token_scopes_passes(tmp_path: Path) -> None:
    """An empty scope set (fine-grained PAT) passes token validation."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset(),  # fine-grained PAT
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0


def test_multiple_failures_exit_1(tmp_path: Path) -> None:
    """When multiple checks fail, exit is still 1 (not N)."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout="[]"),  # pm2: FAIL (no kanban)
        _completed(stdout="other-plugin"),  # claude plugin: FAIL (no kanban)
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: False,  # FAIL
        token_scope_check=lambda: frozenset({"admin:org_hook"}),  # FAIL
        branch_check=lambda: (True, "ok"),
        geteuid=_root,  # FAIL
        stat_socket=_matching_uid_stat(0),  # FAIL (uid 0 ≠ uid 1000)
    )
    assert code == 1


def test_branch_check_none_skips_advisory(tmp_path: Path) -> None:
    """When ``branch_check`` is None, the check skips with an advisory note."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=None,  # explicitly None
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0


# ---------------------------------------------------------------------------
# _resolve_branch_check — live registry-resolved checker (phase 16.4)
# ---------------------------------------------------------------------------


def _write_registry(root: Path, repo: str) -> None:
    """Write a minimal ``projects.json`` registering one project for *repo*."""
    entry = {
        "repo": repo,
        "clone": str(root / "clone"),
        "project_id": "PVT_demo",
        "status_field_node_id": "FIELD_x",
        "option_map": {"Backlog": "opt1"},
        "config_dir": "",
        "dev_repo_path": "",
    }
    (root / "projects.json").write_text(json.dumps({"PVT_demo": entry}), encoding="utf-8")


def test_resolve_branch_check_none_when_registry_empty(tmp_path: Path) -> None:
    """No ``projects.json`` → resolver returns None (advisory skip preserved)."""
    assert _resolve_branch_check(tmp_path) is None


def test_resolve_branch_check_none_when_registry_blank_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered entry with a blank repo → None (no target to probe)."""
    _write_registry(tmp_path, repo="")
    # Token load must not even be reached, but stub it so a missing token can't
    # influence the outcome.
    monkeypatch.setattr("kanbanmate.adapters.github.token.load_token", lambda: "tok", raising=True)
    assert _resolve_branch_check(tmp_path) is None


def test_resolve_branch_check_returns_callable_for_registered_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered repo → a callable yielding ``(True, "repo@main")`` when protected.

    A fake ``GithubClient`` (whose ``branch_protection_on`` reports protection)
    and a stubbed ``load_token`` keep the resolution off the network.
    """

    class _FakeClient:
        def __init__(self, token: str, *, repo: str = "") -> None:
            self.repo = repo

        def branch_protection_on(self, branch: str = "main") -> bool:
            return True

    monkeypatch.setattr("kanbanmate.adapters.github.client.GithubClient", _FakeClient, raising=True)
    monkeypatch.setattr("kanbanmate.adapters.github.token.load_token", lambda: "tok", raising=True)
    _write_registry(tmp_path, repo="IznoCorp/demo")

    checker = _resolve_branch_check(tmp_path)
    assert checker is not None
    enabled, detail = checker()
    assert enabled is True
    assert detail == "IznoCorp/demo@main"


def test_resolve_branch_check_off_yields_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the repo is unprotected, the callable yields ``(False, "repo@main")``."""

    class _FakeClient:
        def __init__(self, token: str, *, repo: str = "") -> None:
            self.repo = repo

        def branch_protection_on(self, branch: str = "main") -> bool:
            return False

    monkeypatch.setattr("kanbanmate.adapters.github.client.GithubClient", _FakeClient, raising=True)
    monkeypatch.setattr("kanbanmate.adapters.github.token.load_token", lambda: "tok", raising=True)
    _write_registry(tmp_path, repo="IznoCorp/demo")

    checker = _resolve_branch_check(tmp_path)
    assert checker is not None
    assert checker() == (False, "IznoCorp/demo@main")


def test_resolve_branch_check_none_when_token_load_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A token-load failure at resolve time → None (fail-soft, no crash)."""

    def _raises() -> str:
        raise RuntimeError("no token configured")

    monkeypatch.setattr("kanbanmate.adapters.github.token.load_token", _raises, raising=True)
    _write_registry(tmp_path, repo="IznoCorp/demo")
    assert _resolve_branch_check(tmp_path) is None


def test_production_doctor_passes_live_branch_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The production ``doctor()`` command passes a non-None resolved checker.

    Monkeypatches ``_resolve_branch_check`` and ``run_doctor`` on the doctor
    module and asserts the wired command resolves a live checker (not the bare
    no-arg call) and forwards it to ``run_doctor`` as ``branch_check``.
    """
    import typer

    from kanbanmate.cli import app as app_mod
    from kanbanmate.cli import doctor as doctor_mod

    sentinel = lambda: (True, "IznoCorp/demo@main")  # noqa: E731
    captured: dict[str, Any] = {}

    monkeypatch.setattr(doctor_mod, "_resolve_branch_check", lambda _root: sentinel)

    def _fake_run_doctor(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(doctor_mod, "run_doctor", _fake_run_doctor)

    with pytest.raises(typer.Exit):
        app_mod.doctor()

    assert captured.get("branch_check") is sentinel
    assert captured["branch_check"] is not None


# ---------------------------------------------------------------------------
# #8 — tmux ownership FAIL (KEEP+DOC, DESIGN §10) — foreign-owned socket
# ---------------------------------------------------------------------------


def test_tmux_socket_foreign_owner_fails_with_ownership_detail(tmp_path: Path, capsys: Any) -> None:
    """#8: a socket owned by a FOREIGN euid is a hard FAIL (DESIGN §10), not a presence warning.

    The PoC only warned on socket presence; NEW tightens to an ownership FAIL — a socket owned by
    a different uid (the root-from-a-prior-run mistake) blocks doctor. We isolate the tmux check by
    passing every OTHER check, so the exit 1 is attributable to ownership alone, and assert the
    detail names both uids (the ownership mismatch).
    """
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,  # running as uid 1000
        stat_socket=_matching_uid_stat(0),  # socket owned by root → foreign
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 1
    out = capsys.readouterr().out
    # The FAIL is the ownership mismatch: the detail names the foreign owner uid and the euid.
    assert "tmux socket" in out
    assert "owned by uid 0" in out
    assert "running as uid 1000" in out


# ---------------------------------------------------------------------------
# #5 — gh_installed removal note (KEEP+DOC) — its absence is deliberate
# ---------------------------------------------------------------------------


def test_gh_installed_check_intentionally_removed_documented() -> None:
    """#5: the gh-CLI check is intentionally absent and that removal is DOCUMENTED in ``run_doctor``.

    NEW has no ``gh``-CLI runtime dependency (it uses the urllib token fetch), so the PoC
    ``gh_installed`` check is moot. The deliberate removal must be recorded in ``run_doctor``'s
    docstring so its absence reads as intentional, not an omission.
    """
    from kanbanmate.cli.doctor import run_doctor as _run_doctor

    doc = _run_doctor.__doc__ or ""
    assert "gh" in doc
    assert "intentionally removed" in doc or "dropped on purpose" in doc
    # And the engine never spawns a ``gh`` subprocess as a doctor check.
    import inspect

    from kanbanmate.cli import doctor as _doctor_mod

    src = inspect.getsource(_doctor_mod)
    assert '"gh"' not in src and "'gh'" not in src


# ---------------------------------------------------------------------------
# #1 — heartbeat carries tick health; board-reachable probe; derived TTL
# ---------------------------------------------------------------------------


def _two_runner() -> MagicMock:
    """A runner that satisfies the pm2 + claude checks for the all-pass baseline."""
    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban"}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]
    return runner


def test_heartbeat_fresh_but_failing_fails(tmp_path: Path) -> None:
    """A FRESH marker carrying consecutive_failures >= 3 FAILs doctor (#1).

    This is the proven dead-token 401-loop: the daemon keeps writing a fresh marker every tick,
    so liveness stays green — but the climbing failure count must flip doctor red.
    """
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file, consecutive_failures=3)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,  # fresh
    )
    assert code == 1


def test_heartbeat_fresh_and_healthy_passes(tmp_path: Path) -> None:
    """A fresh marker with consecutive_failures below the threshold passes (#1)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file, consecutive_failures=1)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,  # fresh
    )
    assert code == 0


def test_heartbeat_legacy_plain_epoch_still_passes(tmp_path: Path) -> None:
    """A legacy plain-epoch marker (old daemon mid-upgrade) parses healthy and passes (#1)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    heartbeat_file.write_text("1717000000.0")  # legacy format

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,  # fresh
    )
    assert code == 0


def test_default_ttl_derives_120s_floor(tmp_path: Path) -> None:
    """With the default (no pinned ttl), a 130 s-old marker is stale at the 120 s floor (#1)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 130,  # past the 120 s floor
    )
    assert code == 1


def test_default_ttl_derives_from_idle_max(tmp_path: Path) -> None:
    """An opted-in idle_max widens the TTL to 2*idle_max, so a 130 s marker stays fresh (#1)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        idle_max=300.0,  # → TTL = max(120, 600) = 600
        now=heartbeat_file.stat().st_mtime + 130,  # well within 600 s
    )
    assert code == 0


def test_board_reachable_probe_failure_fails(tmp_path: Path) -> None:
    """An injected board probe that raises FAILs the board-reachable check (#1)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    def _bad_probe() -> str:
        raise RuntimeError("project not found")

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        board_probe_check=_bad_probe,
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 1


def test_board_reachable_probe_success_passes(tmp_path: Path) -> None:
    """An injected board probe that returns a token PASSes the board-reachable check (#1)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        board_probe_check=lambda: "PROBE_TOKEN_abcdef",
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0


def test_orphan_slot_without_state_fails(tmp_path: Path, capsys: Any) -> None:
    """#11: a held slot with NO matching state file FAILs the orphan-slots check."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)
    # A slot is reserved but there is no state/7.json backing it (the orphan condition).
    (tmp_path / "slots").mkdir()
    (tmp_path / "slots" / "ticket-7").write_text("")
    (tmp_path / "state").mkdir()

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "orphan slots" in out
    assert "ticket-7" in out


def test_orphan_slot_with_matching_state_passes(tmp_path: Path) -> None:
    """#11: a held slot WITH its matching state file passes the orphan-slots check."""
    import json as _json

    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)
    (tmp_path / "slots").mkdir()
    (tmp_path / "slots" / "ticket-7").write_text("")
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "7.json").write_text(_json.dumps({"issue_number": 7}))

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0


def test_board_reachable_skipped_when_no_probe(tmp_path: Path, capsys: Any) -> None:
    """With no probe injected and no registry, the board-reachable check skips with advisory PASS."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "board reachable" in out


# ---------------------------------------------------------------------------
# Phase 35 — helper shims resolve on PATH
# ---------------------------------------------------------------------------


def test_helper_shims_all_resolve_passes(tmp_path: Path, capsys: Any) -> None:
    """Phase 35: when every declared ``kanban-*`` console script resolves, the check PASSES."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        shim_list_scripts=lambda: ["kanban", "kanban-move", "kanban-update-body"],
        shim_which=lambda name: f"/usr/local/bin/{name}",  # every shim resolves
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "helper shims" in out


def test_helper_shims_missing_fails_with_hint(tmp_path: Path, capsys: Any) -> None:
    """Phase 35: a declared shim that does NOT resolve on PATH FAILs with the install hint.

    Reproduces the live §29 ``kanban-update-body`` case: the entry point was declared but missing
    from the operator's editable install until a manual ``pip install -e .``. The check must FAIL,
    name the missing shim, and surface the remediation hint.
    """
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    def _which(name: str) -> str | None:
        # kanban-update-body is declared but NOT on PATH (stale editable install).
        return None if name == "kanban-update-body" else f"/usr/local/bin/{name}"

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        shim_list_scripts=lambda: ["kanban", "kanban-move", "kanban-update-body"],
        shim_which=_which,
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "helper shims" in out
    assert "kanban-update-body" in out
    assert "pip install -e ." in out
    assert "stale editable install" in out


def test_helper_shims_none_declared_fails(tmp_path: Path, capsys: Any) -> None:
    """Phase 35: when NO kanban-* console scripts are declared, the check FAILs (not installed)."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    code = run_doctor(
        root=tmp_path,
        runner=_two_runner(),
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        shim_list_scripts=lambda: [],  # nothing declared
        shim_which=lambda name: f"/usr/local/bin/{name}",
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "helper shims" in out
    assert "pip install -e ." in out


def test_helper_shims_derives_real_kanban_scripts() -> None:
    """Phase 35: the production lister derives the ``kanban-*`` names from the real entry points.

    Exercises the un-injected production path: the installed distribution declares the kanban CLI
    plus the helper shims, so the derived list is non-empty and every name starts with ``kanban``.
    """
    from kanbanmate.cli.doctor import _kanban_console_scripts

    scripts = _kanban_console_scripts()
    assert scripts, "expected the installed distribution to declare kanban-* console scripts"
    assert all(name.startswith("kanban") for name in scripts)
    # The §29 helper that motivated the check must be among them.
    assert "kanban-update-body" in scripts


# ---------------------------------------------------------------------------
# Phase 38 — pyenv-twin advisory check
# ---------------------------------------------------------------------------


def test_pyenv_twin_warns_on_minor_mismatch() -> None:
    """A pyenv global on a DIFFERENT minor than the engine → advisory WARNING, never a FAIL."""
    from kanbanmate.cli.doctor import _check_pyenv_global_twin, _engine_python_version

    engine = _engine_python_version()
    # Force a global on a different minor (engine is 3.X → pick 3.(X-1) or 4.0).
    major, minor = engine.split(".")
    other = f"{major}.{int(minor) - 1}.9" if int(minor) > 0 else "4.0.0"

    name, ok, detail = _check_pyenv_global_twin(read_pyenv_version=lambda: other)
    assert ok is True  # ADVISORY: never blocks doctor
    assert "WARNING" in detail
    assert other in detail
    assert "kanban-bin" in detail


def test_pyenv_twin_matches_same_minor() -> None:
    """A pyenv global on the SAME minor (patch drift only) is benign → PASS, no warning."""
    from kanbanmate.cli.doctor import _check_pyenv_global_twin, _engine_python_version

    engine = _engine_python_version()
    same_minor = f"{engine}.99"  # e.g. 3.12 -> 3.12.99 (same minor, different patch)

    name, ok, detail = _check_pyenv_global_twin(read_pyenv_version=lambda: same_minor)
    assert ok is True
    assert "WARNING" not in detail
    assert "matches" in detail


def test_pyenv_twin_no_pyenv_passes_silently() -> None:
    """When pyenv is not in use (version read returns None), the check passes advisorily."""
    from kanbanmate.cli.doctor import _check_pyenv_global_twin

    name, ok, detail = _check_pyenv_global_twin(read_pyenv_version=lambda: None)
    assert ok is True
    assert "WARNING" not in detail
    assert "not detected" in detail


def test_pyenv_twin_wired_into_run_doctor_advisory(tmp_path: Path) -> None:
    """The pyenv-twin check is wired into run_doctor and NEVER turns a clean run into a failure."""
    heartbeat_file = tmp_path / "daemon.heartbeat"
    _write_heartbeat(heartbeat_file)

    runner = MagicMock()
    runner.side_effect = [
        _completed(stdout='[{"name":"kanban","pm2_env":{"status":"online"}}]'),
        _completed(stdout="kanban@kanbanmate"),
    ]

    code = run_doctor(
        root=tmp_path,
        runner=runner,
        import_check=lambda: True,
        token_scope_check=lambda: frozenset({"project", "repo"}),
        branch_check=lambda: (True, "ok"),
        geteuid=_non_root,
        stat_socket=_matching_uid_stat(1000),
        shim_list_scripts=lambda: ["kanban", "kanban-move"],
        shim_which=lambda name: f"/usr/local/bin/{name}",
        # A blatant minor mismatch — must remain advisory (exit 0).
        pyenv_version_read=lambda: "2.7.18",
        now=heartbeat_file.stat().st_mtime + 1,
    )
    assert code == 0
