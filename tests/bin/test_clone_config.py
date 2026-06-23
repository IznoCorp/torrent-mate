"""Tests for the shared per-clone config loaders (:mod:`kanbanmate.bin._clone_config`).

These leaf helpers were LIFTED out of ``bin/kanban_move.py`` so ``kanban-move`` and
``kanban-session-end`` (the auto-advance backstop) share ONE source of truth. The lift must be
behaviour-preserving — ``kanban-move`` re-imports them under their original private names — and the
new pure :func:`auto_advance_target` parser must mirror ``script_route``'s ``"auto:"`` slice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kanbanmate.bin._clone_config import auto_advance_target, resolve_entry_token
from kanbanmate.cli.init import ProjectEntry


def test_auto_advance_target_parses_col() -> None:
    """``"auto:Spec"`` → ``"Spec"`` (the directive's target column key)."""
    assert auto_advance_target("auto:Spec") == "Spec"


def test_auto_advance_target_multiword_key() -> None:
    """A multiword target KEY is returned verbatim (KEY→NAME resolution is the caller's job)."""
    assert auto_advance_target("auto:PRCI") == "PRCI"


def test_auto_advance_target_strips_whitespace() -> None:
    """Surrounding whitespace on the target is stripped (matching the script-route slice)."""
    assert auto_advance_target("auto:  Plan  ") == "Plan"


def test_auto_advance_target_stop_is_none() -> None:
    """``"stop"`` (the human-review gates) → ``None``: the card STOPS, no engine move."""
    assert auto_advance_target("stop") is None


def test_auto_advance_target_empty_is_none() -> None:
    """An empty directive → ``None`` (old-format / no advance recorded)."""
    assert auto_advance_target("") is None


def test_auto_advance_target_auto_with_empty_target_is_none() -> None:
    """A malformed ``"auto:"`` with no target → ``None`` (never a blank move)."""
    assert auto_advance_target("auto:") is None
    assert auto_advance_target("auto:   ") is None


# ---------------------------------------------------------------------------
# resolve_entry_token (#4) — per-entry token resolution for the agent helpers
# ---------------------------------------------------------------------------


def _entry(token_ref: str = "") -> ProjectEntry:
    """Build a minimal :class:`ProjectEntry` carrying ``token_ref`` for the token-resolution tests."""
    return ProjectEntry(
        repo="orgB/r2",
        clone="/c",
        project_id="PVT_B",
        status_field_node_id="F",
        token_ref=token_ref,
    )


def test_resolve_entry_token_with_ref_loads_per_org_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-empty token_ref loads from ``<root>/tokens/<ref>`` (the multi-org path, #4)."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)  # the env override must not win here
    (tmp_path / "token").write_text("shared-tok", encoding="utf-8")
    (tmp_path / "tokens").mkdir()
    (tmp_path / "tokens" / "orgB").write_text("orgB-tok", encoding="utf-8")

    assert resolve_entry_token(_entry(token_ref="orgB")) == "orgB-tok"


def test_resolve_entry_token_without_ref_uses_default_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty token_ref (N=1 path) loads the shared ``<root>/token`` — byte-identical to today."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    (tmp_path / "token").write_text("shared-tok", encoding="utf-8")

    assert resolve_entry_token(_entry(token_ref="")) == "shared-tok"


def test_resolve_entry_token_env_override_wins_for_shared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$KANBAN_TOKEN`` still wins for the shared (no-ref) token (the env override path is intact)."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    monkeypatch.setenv("KANBAN_TOKEN", "env-tok")
    (tmp_path / "token").write_text("file-tok", encoding="utf-8")

    assert resolve_entry_token(_entry(token_ref="")) == "env-tok"


def test_kanban_move_reimports_lifted_helpers() -> None:
    """BACK-COMPAT: ``kanban-move`` still exposes the three lifted loaders under the old names."""
    from kanbanmate.bin import kanban_move
    from kanbanmate.bin._clone_config import (
        load_clone_columns,
        load_clone_transitions,
        resolve_entry,
    )

    assert kanban_move._resolve_entry is resolve_entry
    assert kanban_move._load_clone_columns is load_clone_columns
    assert kanban_move._load_clone_transitions is load_clone_transitions


# ---------------------------------------------------------------------------
# route_entry_column (#2, skiff) — lane → entry column resolver
# ---------------------------------------------------------------------------


def test_route_entry_column_maps_known_lanes() -> None:
    """``route_entry_column`` maps each lane to its entry column key (skiff fast-track)."""
    from kanbanmate.bin._clone_config import route_entry_column

    assert route_entry_column("full") == "Brainstorming"
    assert route_entry_column("lite") == "Scope"
    assert route_entry_column("express") == "PrepareFeature"


def test_route_entry_column_unknown_lane_is_none() -> None:
    """An unknown lane or empty string returns ``None`` (session-end backstop fail-soft)."""
    from kanbanmate.bin._clone_config import route_entry_column

    assert route_entry_column("") is None
    assert route_entry_column("turbo") is None
