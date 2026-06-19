"""Tests for ``server.main``'s start-up guards (conduit review hardening, DESIGN §6/§7).

Two start-up guards run before the blocking stdio run:

* the worktree pin FILE (``.claude/kanban-issue``) must agree with ``--issue`` — a mismatch raises
  :class:`~kanbanmate.mcp.server.PinMismatchError` (refuse to start); an absent pin proceeds;
* the ``update_main`` clone pair is RESOLVED SERVER-SIDE from the registry (zero client input).

The mismatch guard runs FIRST, before any wiring, so that test needs no GitHub stubs. The
"absent proceeds" + clone-resolution tests stub the heavy wiring (``_wiring_for`` / ``build_deps`` /
``build_tick_config`` / the stdio run) so no real server / GitHub deps are built.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kanbanmate.core.domain import Column, ColumnClass
from kanbanmate.core.transitions import Transition, TransitionConfig
from kanbanmate.mcp import server as mcp_server


def _write_pin(worktree: Path, issue: int) -> None:
    """Write ``<worktree>/.claude/kanban-issue`` carrying ``issue``."""
    claude = worktree / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "kanban-issue").write_text(f"{issue}\n", encoding="utf-8")


def test_main_refuses_on_pin_file_issue_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worktree pin file naming a DIFFERENT issue than ``--issue`` refuses to start (§7)."""
    _write_pin(tmp_path, 5)  # the worktree is pinned to #5
    monkeypatch.chdir(tmp_path)
    with pytest.raises(mcp_server.PinMismatchError) as excinfo:
        # Launched with --issue 9 → disagrees with the worktree pin (#5) → refuse to start.
        mcp_server.main(root=tmp_path, issue=9, project=None, repo=None)
    assert "#5" in str(excinfo.value)
    assert "9" in str(excinfo.value)


def _stub_wiring(monkeypatch: pytest.MonkeyPatch, *, project_id: str, ran: list[bool]) -> None:
    """Stub ``_wiring_for`` / ``build_deps`` / ``build_tick_config`` + the stdio run (no live deps)."""

    class _Config:
        project_id = ""

    cfg = _Config()
    cfg.project_id = project_id

    class _Deps:
        board_reader = object()
        board_writer = object()
        store = object()
        seeder = object()

    class _Tick:
        columns: dict[str, Column] = {
            "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT)
        }
        transitions = TransitionConfig(
            project="owner/repo",
            concurrency_cap=3,
            _explicit={
                ("Backlog", "InProgress"): Transition(
                    from_col="Backlog", to_col="InProgress", profile="dev", prompt="go"
                )
            },
            _wild_to={},
            _wild_from={},
        )

    monkeypatch.setattr("kanbanmate.cli.app._wiring_for", lambda root, *, project, repo: cfg)
    monkeypatch.setattr("kanbanmate.app.wiring.build_deps", lambda config: _Deps())
    monkeypatch.setattr("kanbanmate.app.wiring.build_tick_config", lambda config: _Tick())
    # Replace the blocking stdio run with a flag-set so ``main`` returns immediately.
    monkeypatch.setattr("kanbanmate.mcp.server.anyio.run", lambda fn: ran.append(True))


def _write_registry(root: Path, *, project_id: str, clone: str, dev_repo_path: str) -> None:
    """Write a single-project ``projects.json`` under *root* carrying ``clone``/``dev_repo_path``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects.json").write_text(
        json.dumps(
            {
                project_id: {
                    "repo": "IznoCorp/demo",
                    "clone": clone,
                    "project_id": project_id,
                    "status_field_node_id": "PVTSSF",
                    "dev_repo_path": dev_repo_path,
                }
            }
        ),
        encoding="utf-8",
    )


def test_main_proceeds_when_pin_file_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No worktree pin file → ``main`` proceeds on ``--issue`` (does NOT refuse) and runs the server."""
    monkeypatch.chdir(tmp_path)  # no .claude/kanban-issue here → absent pin
    _write_registry(tmp_path, project_id="PVT_X", clone="/c", dev_repo_path="")
    ran: list[bool] = []
    _stub_wiring(monkeypatch, project_id="PVT_X", ran=ran)
    # Captures the build_server call so we can assert the resolved clone pair was threaded in.
    captured: dict[str, object] = {}
    real_build = mcp_server.build_server

    def _spy_build(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        # Return a throwaway object; the stubbed anyio.run never touches it.
        return object()

    monkeypatch.setattr(mcp_server, "build_server", _spy_build)
    mcp_server.main(root=tmp_path, issue=9, project=None, repo=None)
    assert ran == [True]  # the server run was reached (no refusal)
    # The clone pair was RESOLVED SERVER-SIDE from the registry (not from any client input).
    assert captured["clone_paths"] == ("/c", "")
    assert real_build is not _spy_build  # sanity: we patched, not the real builder


def test_main_resolves_clone_pair_from_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``main`` resolves ``(clone, dev_repo)`` from the registry entry for the wired project_id (§6)."""
    monkeypatch.chdir(tmp_path)
    _write_registry(tmp_path, project_id="PVT_Y", clone="/base", dev_repo_path="/dev")
    ran: list[bool] = []
    _stub_wiring(monkeypatch, project_id="PVT_Y", ran=ran)
    captured: dict[str, object] = {}
    monkeypatch.setattr(mcp_server, "build_server", lambda *a, **k: captured.update(k) or object())
    mcp_server.main(root=tmp_path, issue=9, project=None, repo=None)
    assert captured["clone_paths"] == ("/base", "/dev")


def test_main_clone_pair_none_when_registry_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No registry entry → ``clone_paths`` is None (fail-soft: ``update_main`` later refuses)."""
    monkeypatch.chdir(tmp_path)  # no projects.json written
    ran: list[bool] = []
    _stub_wiring(monkeypatch, project_id="PVT_MISSING", ran=ran)
    captured: dict[str, object] = {}
    monkeypatch.setattr(mcp_server, "build_server", lambda *a, **k: captured.update(k) or object())
    mcp_server.main(root=tmp_path, issue=9, project=None, repo=None)
    assert captured["clone_paths"] is None
    assert ran == [True]  # the rest of the board surface still serves
