"""Tests for the PURE tri-state dependency gate (:mod:`kanbanmate.core.dependency_gate`).

The gate is pure (#13): an issue body + a board snapshot in, a frozen
:class:`~kanbanmate.core.dependency_gate.DependencyVerdict` out, with NO I/O. Each
``Depends on #N`` resolves to MET (dep in a done column), UNMET (on board, not
done), or UNKNOWN (absent from the snapshot → reported in ``unresolved`` for the
imperative shell to resolve live). These tests pin that tri-state partition and the
``fully_met`` shortcut WITHOUT any network seam — the live ``issue_state`` fallback
is exercised in ``tests/app/test_tick.py``.
"""

from __future__ import annotations

from kanbanmate.core.dependency_gate import (
    DependencyVerdict,
    evaluate,
    parse_dependencies,
)
from kanbanmate.core.domain import BoardSnapshot, Ticket


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets into a :class:`BoardSnapshot` (capture time is irrelevant here)."""
    return BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)


def _ticket(number: int, column: str) -> Ticket:
    """Build a minimal issue-backed ticket in ``column`` for dependency lookups."""
    return Ticket(item_id=f"PVTI_{number}", issue_number=number, title="t", column_key=column)


def test_no_dependencies_is_met_with_empty_unresolved() -> None:
    """A body with no ``Depends on #N`` is MET with no unresolved deps (default)."""
    verdict = evaluate("A plain body with no dependency marker.", _snapshot())

    assert isinstance(verdict, DependencyVerdict)
    assert verdict.met is True
    assert verdict.unresolved == ()
    assert verdict.fully_met() is True
    assert "no declared dependencies" in verdict.reason


def test_dependency_in_done_is_met() -> None:
    """A dep whose card is in a done column (``Done``) resolves MET (no I/O)."""
    dep = _ticket(5, "Done")
    verdict = evaluate("Depends on #5", _snapshot(dep))

    assert verdict.met is True
    assert verdict.unresolved == ()
    assert verdict.fully_met() is True


def test_dependency_in_merge_is_met() -> None:
    """The ``Merge`` column also satisfies a dependency (DESIGN §9 done set)."""
    verdict = evaluate("Depends on #5", _snapshot(_ticket(5, "Merge")))

    assert verdict.fully_met() is True


def test_dependency_on_board_not_done_is_unmet() -> None:
    """A dep on the board but NOT in a done column is UNMET (hard block, no I/O)."""
    dep = _ticket(5, "InProgress")
    verdict = evaluate("Depends on #5", _snapshot(dep))

    assert verdict.met is False
    # UNMET deps are on-board: they are NOT unresolved (no live query can help).
    assert verdict.unresolved == ()
    assert verdict.fully_met() is False
    assert "#5 (in InProgress)" in verdict.reason


def test_dependency_absent_from_snapshot_is_unknown() -> None:
    """A dep absent from the snapshot is UNKNOWN → reported in ``unresolved`` (no I/O)."""
    # The snapshot has the dependent (#7) but NOT the dependency (#5).
    verdict = evaluate("Depends on #5", _snapshot(_ticket(7, "InProgress")))

    # ``met`` reflects only the on-board deps (none unmet) — the gate is not a hard block.
    assert verdict.met is True
    # The off-board dep is reported for the live fallback to resolve.
    assert verdict.unresolved == (5,)
    # Not fully met by the snapshot alone — the caller must resolve #5 live.
    assert verdict.fully_met() is False
    assert "#5" in verdict.reason


def test_mixed_unmet_and_unknown_is_blocked_with_both_reported() -> None:
    """An on-board-not-done dep + an off-board dep: UNMET wins, UNKNOWN still reported."""
    on_board_not_done = _ticket(5, "InProgress")
    verdict = evaluate("Depends on #5 and depends on #9", _snapshot(on_board_not_done))

    assert verdict.met is False  # #5 is a hard block
    assert verdict.unresolved == (9,)  # #9 is off-board → still reported
    assert verdict.fully_met() is False
    assert "#5 (in InProgress)" in verdict.reason
    assert "#9" in verdict.reason


def test_multiple_unknown_deps_preserve_first_seen_order() -> None:
    """Several off-board deps appear in ``unresolved`` in first-seen, de-duplicated order."""
    verdict = evaluate("Depends on #9\nDepends on #3\nDepends on #9", _snapshot())

    assert verdict.unresolved == (9, 3)


def test_verdict_is_frozen() -> None:
    """:class:`DependencyVerdict` is a frozen value object (hashable, immutable)."""
    verdict = DependencyVerdict(met=True, unresolved=(1, 2), reason="r")
    # A frozen dataclass is hashable and rejects attribute assignment.
    assert hash(verdict) == hash(DependencyVerdict(met=True, unresolved=(1, 2), reason="r"))


def test_parse_dependencies_is_case_insensitive_and_deduped() -> None:
    """``parse_dependencies`` extracts numbers case-insensitively, in first-seen order."""
    assert parse_dependencies("DEPENDS ON #4 then depends on #4 and Depends On #2") == [4, 2]
