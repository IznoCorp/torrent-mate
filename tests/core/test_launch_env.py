"""Tests for the pure launch env-prefix composer (ingress-multiproject §7 / DESIGN §8.3).

Covers: the N=1 / default-root byte-identical case (no exports), the KANBAN_ROOT export, the
multi-project KANBAN_PROJECT_ID export (only when multi_project + a project id), and quoting.
"""

from __future__ import annotations

from kanbanmate.core.launch_env import build_env_prefix

_PATH = 'export PATH=/wt/.claude/kanban-bin:"$PATH"; '


def test_n1_default_root_no_exports() -> None:
    """N=1, default root: only the PATH segment — byte-identical to the historical command."""
    out = build_env_prefix(kanban_root="", project_id="", multi_project=False, path_segment=_PATH)
    assert out == _PATH


def test_kanban_root_exported_when_non_default() -> None:
    out = build_env_prefix(
        kanban_root="/home/u/.kanban-km",
        project_id="PVT_A",
        multi_project=False,
        path_segment=_PATH,
    )
    assert out == "export KANBAN_ROOT=/home/u/.kanban-km; " + _PATH
    # N=1 (multi_project False) → NO project export even with a project_id.
    assert "KANBAN_PROJECT_ID" not in out


def test_project_id_exported_only_in_multi_project() -> None:
    out = build_env_prefix(
        kanban_root="/r", project_id="PVT_A", multi_project=True, path_segment=_PATH
    )
    assert out == "export KANBAN_ROOT=/r; export KANBAN_PROJECT_ID=PVT_A; " + _PATH


def test_multi_project_without_id_omits_export() -> None:
    out = build_env_prefix(kanban_root="", project_id="", multi_project=True, path_segment=_PATH)
    assert out == _PATH


def test_values_are_shell_quoted() -> None:
    """A root with a space stays one shell token (shlex.quote)."""
    out = build_env_prefix(
        kanban_root="/r oot", project_id="P V", multi_project=True, path_segment=_PATH
    )
    assert "export KANBAN_ROOT='/r oot'; " in out
    assert "export KANBAN_PROJECT_ID='P V'; " in out
