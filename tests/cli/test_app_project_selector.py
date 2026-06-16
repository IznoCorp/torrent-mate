"""End-to-end CLI tests for the project-aware selector on board commands (ingress-multiproject §8, #1).

The BLOCKER was that every operator board command was UNUSABLE on a multi-project root (the wiring
resolver raised / picked wrong on N>1). These drive the real Typer ``kanban`` app via
``CliRunner``: on an N>1 root, ``kanban status`` with NO selector FAILS LOUD (exit 1 + candidate
list), and with ``--project`` it resolves (proving the command is no longer half-shipped). The N=1
flagless path is covered at the resolver level in ``tests/daemon/test_wiring_selection.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kanbanmate.cli.app import app
from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH

runner = CliRunner()


def _write_clone(tmp_path: Path, name: str) -> Path:
    clone = tmp_path / name
    cols = clone / CLONE_COLUMNS_RELPATH
    cols.parent.mkdir(parents=True, exist_ok=True)
    cols.write_text("columns: []\n", encoding="utf-8")
    return clone


def _two_project_root(tmp_path: Path) -> None:
    clone_a = _write_clone(tmp_path, "clone-a")
    clone_b = _write_clone(tmp_path, "clone-b")
    (tmp_path / "projects.json").write_text(
        json.dumps(
            {
                "PVT_A": {
                    "repo": "o/r1",
                    "clone": str(clone_a),
                    "project_id": "PVT_A",
                    "status_field_node_id": "F",
                },
                "PVT_B": {
                    "repo": "o/r2",
                    "clone": str(clone_b),
                    "project_id": "PVT_B",
                    "status_field_node_id": "F",
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "token").write_text("tok", encoding="utf-8")


def test_status_multiproject_no_selector_exits_1_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`kanban status` on an N>1 root with NO --project/--repo → exit 1 + candidate list (#1)."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    _two_project_root(tmp_path)

    result = runner.invoke(app, ["status", "--root", str(tmp_path)])

    assert result.exit_code == 1
    # Fails LOUD naming BOTH candidates — never a silent wrong-board pick or a raw traceback.
    assert "PVT_A" in result.output and "PVT_B" in result.output


def test_status_multiproject_with_project_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`kanban status --project PVT_B` on an N>1 root resolves that board (no selection error).

    The status_cmd renderer is stubbed so the test exercises ONLY the project-aware wiring path
    (no GitHub network): a resolved selection reaches build_deps + the renderer and exits 0.
    """
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    _two_project_root(tmp_path)

    captured: dict[str, object] = {}

    # Stub build_deps (so no real GitHub client is built) and the status renderer (so no network).
    import kanbanmate.cli.app as app_mod

    class _Deps:
        board_reader = object()
        store = object()

    def _fake_build_deps(wiring: object) -> _Deps:
        captured["project_id"] = wiring.project_id  # type: ignore[attr-defined]
        return _Deps()

    from kanbanmate.cli import status as status_cmd

    monkeypatch.setattr(app_mod, "build_deps", _fake_build_deps)
    monkeypatch.setattr(status_cmd, "status", lambda *a, **k: "OK PANE")

    result = runner.invoke(app, ["status", "--root", str(tmp_path), "--project", "PVT_B"])

    assert result.exit_code == 0
    assert "OK PANE" in result.output
    # The resolved wiring is the SELECTED board (proving the selector reached build_deps).
    assert captured["project_id"] == "PVT_B"
