"""Tests for the shared per-clone config loaders (:mod:`kanbanmate.bin._clone_config`).

These leaf helpers were LIFTED out of ``bin/kanban_move.py`` so ``kanban-move`` and
``kanban-session-end`` (the auto-advance backstop) share ONE source of truth. The lift must be
behaviour-preserving — ``kanban-move`` re-imports them under their original private names — and the
new pure :func:`auto_advance_target` parser must mirror ``script_route``'s ``"auto:"`` slice.
"""

from __future__ import annotations

from kanbanmate.bin._clone_config import auto_advance_target


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
