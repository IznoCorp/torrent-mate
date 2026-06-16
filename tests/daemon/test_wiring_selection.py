"""Tests for the project-aware CLI wiring selection (ingress-multiproject §8, #1).

Covers :func:`kanbanmate.daemon.registry_wiring.wiring_for_selection`: N=1 resolves FLAGLESS (no
selector, the flat store layout — back-compat); N>1 + ``--project`` resolves the exact board; N>1 +
``--repo`` resolves the sole match; N>1 with NO selector FAILS LOUD (never silently picks the wrong
board); and an ambiguous / non-matching selector fails loud naming the candidates.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH
from kanbanmate.core.registry_resolve import safe_project_id
from kanbanmate.daemon.registry_wiring import ProjectSelectionError, wiring_for_selection


def _write_clone(tmp_path: Path, name: str) -> Path:
    clone = tmp_path / name
    cols = clone / CLONE_COLUMNS_RELPATH
    cols.parent.mkdir(parents=True, exist_ok=True)
    cols.write_text("columns: []\n", encoding="utf-8")
    return clone


def _registry(root: Path, entries: dict[str, dict[str, object]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects.json").write_text(json.dumps(entries), encoding="utf-8")


def _seed_token(root: Path) -> None:
    (root / "token").write_text("tok", encoding="utf-8")


def _two_project_root(tmp_path: Path) -> None:
    """Register two enabled projects backing two different repos."""
    clone_a = _write_clone(tmp_path, "clone-a")
    clone_b = _write_clone(tmp_path, "clone-b")
    _registry(
        tmp_path,
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
        },
    )
    _seed_token(tmp_path)


def test_n1_resolves_flagless(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N=1: the sole project resolves with NO selector, flat layout (byte-identical back-compat)."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    clone = _write_clone(tmp_path, "clone-a")
    _registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "o/r1",
                "clone": str(clone),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
            }
        },
    )
    _seed_token(tmp_path)

    wiring = wiring_for_selection(tmp_path)

    assert wiring.project_id == "PVT_A"
    assert wiring.state_root == ""  # flat layout — N=1 back-compat
    assert wiring.multi_project is False


def test_n_gt_1_project_selector_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N>1 + ``--project <id>`` resolves the exact board with the per-project sub-root layout."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    _two_project_root(tmp_path)

    wiring = wiring_for_selection(tmp_path, project="PVT_B")

    assert wiring.project_id == "PVT_B"
    assert wiring.multi_project is True
    assert wiring.state_root == str(tmp_path / "projects" / safe_project_id("PVT_B"))


def test_n_gt_1_repo_selector_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N>1 + ``--repo owner/name`` resolves the sole matching board."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    _two_project_root(tmp_path)

    wiring = wiring_for_selection(tmp_path, repo="o/r1")

    assert wiring.project_id == "PVT_A"
    assert wiring.multi_project is True


def test_n_gt_1_no_selector_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N>1 with NO selector FAILS LOUD listing the candidates (never silently picks a board)."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    _two_project_root(tmp_path)

    with pytest.raises(ProjectSelectionError) as exc:
        wiring_for_selection(tmp_path)
    # The message names BOTH candidates so the operator re-runs with the right selector.
    assert "PVT_A" in str(exc.value) and "PVT_B" in str(exc.value)


def test_n_gt_1_unknown_project_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N>1 + a ``--project`` matching nothing fails loud (never falls back to a wrong board)."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    _two_project_root(tmp_path)

    with pytest.raises(ProjectSelectionError, match="PVT_NOPE"):
        wiring_for_selection(tmp_path, project="PVT_NOPE")


def test_n_gt_1_ambiguous_repo_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N>1 + a ``--repo`` backing >1 board fails loud (the operator must pass --project)."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    clone_a = _write_clone(tmp_path, "clone-a")
    clone_b = _write_clone(tmp_path, "clone-b")
    # Two boards on the SAME repo → an ambiguous --repo selector.
    _registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "o/shared",
                "clone": str(clone_a),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
            },
            "PVT_B": {
                "repo": "o/shared",
                "clone": str(clone_b),
                "project_id": "PVT_B",
                "status_field_node_id": "F",
            },
        },
    )
    _seed_token(tmp_path)

    with pytest.raises(ProjectSelectionError, match="disambiguate"):
        wiring_for_selection(tmp_path, repo="o/shared")


def test_no_registry_raises_file_not_found(tmp_path: Path) -> None:
    """An empty root (no projects.json) raises FileNotFoundError (run `kanban init` first)."""
    with pytest.raises(FileNotFoundError):
        wiring_for_selection(tmp_path)
