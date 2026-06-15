"""Tests for the ``kanban-move`` agent helper (:mod:`kanbanmate.bin.kanban_move`).

The mandatory contract under test is the **anti-loop guard** (DESIGN §8.0.5): ``kanban-move`` must
**refuse** to move a card into a **launch-transition target** — a column that is the destination of
a prompt-bearing whitelisted transition (no ``move_card`` call, non-zero exit) — and must **call**
:meth:`~kanbanmate.adapters.github.client.GithubClient.move_card` for any non-launch target. The
refusal is keyed on the transition whitelist, NOT a static column class. A fake board client
records calls so no test touches the network; the column model and the transition whitelist are
supplied directly so nothing is read off the clone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from kanbanmate.bin import kanban_move
from kanbanmate.bin.kanban_move import main, resolve_target_column
from kanbanmate.core.domain import Column, ColumnClass
from kanbanmate.core.transitions import load_transitions
from kanbanmate.ports.store import TicketState, TicketStatus

# A small board model covering the columns the launch-target tests target. The
# ``column_class`` here is irrelevant to the guard (which keys on the transition
# whitelist, not the class, DESIGN §8.0.5) — it only satisfies the Column model; the
# guard verdict comes entirely from ``_TRANSITIONS`` below.
_COLUMNS: dict[str, Column] = {
    "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),
    "ReadyToDev": Column(key="ReadyToDev", name="Ready to dev", column_class=ColumnClass.INERT),
    "InProgress": Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),
    "PRCI": Column(key="PRCI", name="PR/CI", column_class=ColumnClass.INERT),
    "Review": Column(key="Review", name="Review", column_class=ColumnClass.INERT),
    "Cancel": Column(key="Cancel", name="Cancel", column_class=ColumnClass.REACTIVE),
    "Merge": Column(key="Merge", name="Merge", column_class=ColumnClass.INERT),
    "Done": Column(key="Done", name="Done", column_class=ColumnClass.INERT),
}

# A transition whitelist mirroring the load-bearing shape of DEFAULT_TRANSITIONS: the
# prompt-bearing rows (InProgress / PRCI / Review are launch targets), the Review→Merge
# SCRIPT gate (no prompt → Merge is NOT a launch target → merge=human-only preserved),
# and inert no-ops (Backlog, ReadyToDev, Done are reachable).
_TRANSITIONS = load_transitions(
    "project: test/repo\n"
    "transitions:\n"
    "  - {from: 'Backlog', to: 'ReadyToDev'}\n"  # no-op → ReadyToDev is inert
    "  - {from: 'PrepareFeature', to: 'InProgress', prompt: 'implement'}\n"
    "  - {from: 'InProgress', to: 'PRCI', prompt: 'fix'}\n"
    "  - {from: 'PRCI', to: 'Review', prompt: 'review'}\n"
    "  - {from: 'Review', to: 'Merge', script: 'bin/check-merge-ready.sh'}\n"  # GATE, no prompt
    "  - {from: 'Merge', to: 'Done'}\n"  # terminal no-op
    "  - {from: '*', to: 'Cancel'}\n"  # reactive no-op
)


class FakeBoard:
    """A board-client double recording every ``move_card`` call (never hits the network)."""

    def __init__(self) -> None:
        """Initialise an empty call log."""
        self.calls: list[tuple[Any, ...]] = []

    def move_card(self, item_id: str, column_key: str) -> None:
        """Record the move so a test can assert exactly which column was targeted."""
        self.calls.append(("move", item_id, column_key))


class FakeStore:
    """A store double recording ``record_agent_advance`` calls (the breadcrumb writer).

    ``load`` returns the injected :class:`TicketState`; ``record_agent_advance`` records the
    ``(issue, now)`` pair so a test can assert the breadcrumb was dropped keyed by ISSUE number
    (the 8.1.d invariant). Setting ``raise_on_advance`` makes the breadcrumb write blow up so the
    warn-not-abort path (the move still succeeds) is exercised.
    """

    def __init__(self, state: TicketState | None, *, raise_on_advance: bool = False) -> None:
        """Store the state ``load`` returns and the breadcrumb-failure toggle.

        Args:
            state: The :class:`TicketState` ``load`` returns for any issue.
            raise_on_advance: When ``True``, ``record_agent_advance`` raises (the move must still
                succeed — warn-not-abort).
        """
        self._state = state
        self._raise = raise_on_advance
        self.advances: list[tuple[int, float]] = []

    def load(self, issue: int) -> TicketState | None:
        """Return the injected state (independent of ``issue``)."""
        return self._state

    def record_agent_advance(self, issue_number: int, *, now: float) -> None:
        """Record the advance breadcrumb keyed by ISSUE number (8.1.d invariant)."""
        if self._raise:
            raise OSError("disk full")
        self.advances.append((issue_number, now))


@dataclass(frozen=True)
class _FakeEntry:
    """A minimal stand-in for :class:`~kanbanmate.cli.init.ProjectEntry`."""

    repo: str = "IznoCorp/demo"
    project_id: str = "PVT_PROJECT"
    clone: str = "/tmp/clone"
    status_field_node_id: str = "PVTSSF"
    option_map: dict[str, str] = field(default_factory=dict)


def _state(item_id: str = "PVTI_ITEM") -> TicketState:
    """Return a running :class:`TicketState` carrying ``item_id`` (the move target)."""
    return TicketState(
        issue_number=7,
        item_id=item_id,
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
    )


_MISSING = object()


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    board: FakeBoard,
    *,
    state: TicketState | None | Any = _MISSING,
    raise_on_advance: bool = False,
) -> FakeStore:
    """Patch token/registry/columns/store/client so ``main`` uses the fakes.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        board: The fake board client every ``GithubClient(...)`` call should yield.
        state: The :class:`TicketState` the fake store returns for the issue. Omitted defaults to
            a running state with a non-empty ``item_id``; pass ``None`` explicitly to simulate a
            ticket with no persisted state.
        raise_on_advance: When ``True``, the fake store's ``record_agent_advance`` raises so the
            breadcrumb-write-failure (warn-not-abort) path is exercised.

    Returns:
        The :class:`FakeStore` wired in, so a test can assert the recorded advances.
    """
    resolved: TicketState | None = _state() if state is _MISSING else state
    store = FakeStore(resolved, raise_on_advance=raise_on_advance)
    monkeypatch.setattr(kanban_move, "load_token", lambda: "tok")
    monkeypatch.setattr(kanban_move, "_resolve_entry", lambda: _FakeEntry())
    monkeypatch.setattr(kanban_move, "_load_clone_columns", lambda entry: _COLUMNS)
    monkeypatch.setattr(kanban_move, "_load_clone_transitions", lambda entry: _TRANSITIONS)
    monkeypatch.setattr(kanban_move, "FsStateStore", lambda *a, **k: store)
    monkeypatch.setattr(kanban_move, "GithubClient", lambda *a, **k: board)
    return store


# ---------------------------------------------------------------------------
# resolve_target_column: key OR name resolution
# ---------------------------------------------------------------------------


def test_resolve_target_column_by_key() -> None:
    """A column is resolvable by its stable ``key``."""
    assert resolve_target_column(_COLUMNS, "InProgress").name == "In Progress"


def test_resolve_target_column_by_name() -> None:
    """A column is also resolvable by its human-readable ``name``."""
    assert resolve_target_column(_COLUMNS, "In Progress").key == "InProgress"


def test_resolve_target_column_unknown_raises() -> None:
    """An unknown target raises ``KeyError`` listing the known columns."""
    with pytest.raises(KeyError):
        resolve_target_column(_COLUMNS, "Nope")


# ---------------------------------------------------------------------------
# Anti-loop guard (DESIGN §8.0.5) — the mandatory contract (launch-target keyed)
# ---------------------------------------------------------------------------


def test_refuses_launch_target_no_move(monkeypatch: pytest.MonkeyPatch) -> None:
    """REFUSE: a launch-transition target exits non-zero and NEVER calls move_card (anti-loop).

    ``InProgress`` / ``PRCI`` / ``Review`` are each the destination of a prompt-bearing
    transition in the whitelist, so moving a card into one would re-fire that launch — the
    guard refuses (DESIGN §8.0.5), keyed on the whitelist, not a column class.
    """
    board = FakeBoard()
    _wire(monkeypatch, board)

    # By key.
    assert main(["7", "InProgress"]) == 1
    assert main(["7", "PRCI"]) == 1
    assert main(["7", "Review"]) == 1
    # And by human-readable name (resolved to its key before the membership test).
    assert main(["7", "In Progress"]) == 1

    # The whole point: no move was ever issued for a launch target.
    assert board.calls == []


def test_moves_to_inert_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLOW: a non-launch (inert/terminal) target calls move_card with the column NAME."""
    board = FakeBoard()
    _wire(monkeypatch, board)

    # Backlog, Ready to dev, and Done are not launch-transition targets.
    assert main(["7", "Backlog"]) == 0
    assert main(["7", "Ready to dev"]) == 0
    assert main(["7", "Done"]) == 0
    assert board.calls == [
        ("move", "PVTI_ITEM", "Backlog"),
        ("move", "PVTI_ITEM", "Ready to dev"),
        ("move", "PVTI_ITEM", "Done"),
    ]


def test_moves_to_inert_merge_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLOW: ``Merge`` is reachable — ``Review → Merge`` is a SCRIPT gate, not a prompt.

    Because the guard keys on PROMPT-bearing transitions, the script-gated ``Review → Merge``
    row does NOT make ``Merge`` a launch target, so an agent may move a card into it. This is
    the merge=human-only preservation (DESIGN §8.0.5): the merge boundary rests on Merge being
    unreachable as a launch target + branch protection + the ``gh pr merge`` ban, not on this
    client-side refusal.
    """
    board = FakeBoard()
    _wire(monkeypatch, board)

    assert main(["7", "Merge"]) == 0
    assert board.calls == [("move", "PVTI_ITEM", "Merge")]


def test_moves_to_reactive_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLOW: a reactive no-op target (e.g. Cancel, a ``(*, to)`` no-prompt row) is permitted."""
    board = FakeBoard()
    _wire(monkeypatch, board)

    assert main(["7", "Cancel"]) == 0
    assert board.calls == [("move", "PVTI_ITEM", "Cancel")]


# ---------------------------------------------------------------------------
# main(): argv + wiring failure handling
# ---------------------------------------------------------------------------


def test_bad_arity_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrong number of arguments is a usage error (exit 2), no move issued."""
    board = FakeBoard()
    _wire(monkeypatch, board)

    assert main(["7"]) == 2
    assert main(["7", "Backlog", "extra"]) == 2
    assert board.calls == []


def test_non_int_issue_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-integer issue is rejected (exit 2), not a crash."""
    board = FakeBoard()
    _wire(monkeypatch, board)

    assert main(["notanint", "Backlog"]) == 2
    assert board.calls == []


def test_hash_prefixed_issue_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A leading ``#`` on the issue arg is stripped defensively (defect 3), not rejected.

    An agent that types ``kanban-move #7 Backlog`` (quoted, by habit) must still move the card —
    the helper strips ONE leading ``#`` before int-parsing.
    """
    board = FakeBoard()
    _wire(monkeypatch, board)

    assert main(["#7", "Backlog"]) == 0
    assert board.calls == [("move", "PVTI_ITEM", "Backlog")]


def test_missing_item_id_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """No persisted item id for the ticket fails cleanly (exit 1), no move issued."""
    board = FakeBoard()
    _wire(monkeypatch, board, state=None)

    assert main(["7", "Backlog"]) == 1
    assert board.calls == []


def test_wiring_failure_exits_one_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry/token failure is caught and reported (exit 1), never a traceback."""

    def _boom() -> _FakeEntry:
        raise RuntimeError("no registered project")

    monkeypatch.setattr(kanban_move, "_resolve_entry", _boom)

    assert main(["7", "Backlog"]) == 1


# ---------------------------------------------------------------------------
# Advance breadcrumb (DESIGN §8.1.e) — written synchronously AFTER a successful move
# ---------------------------------------------------------------------------


def test_records_advance_breadcrumb_after_successful_move(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful move drops the advance breadcrumb keyed by ISSUE number (8.1.d invariant).

    The breadcrumb is the proof the daemon's ✅-on-advance finalize relies on; it must be written
    synchronously, keyed by the issue (``7``), AFTER ``move_card`` lands.
    """
    board = FakeBoard()
    store = _wire(monkeypatch, board)

    assert main(["7", "Backlog"]) == 0
    # The move landed first, then exactly one breadcrumb keyed by the ISSUE number.
    assert board.calls == [("move", "PVTI_ITEM", "Backlog")]
    assert [issue for issue, _now in store.advances] == [7]


def test_advance_breadcrumb_failure_does_not_fail_the_move(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A breadcrumb-write failure warns to stderr but NEVER aborts the move (warn-not-abort).

    The move already landed on GitHub, so a failing ``record_agent_advance`` must not change the
    exit code — the helper still returns ``0`` and only logs a warning.
    """
    board = FakeBoard()
    _wire(monkeypatch, board, raise_on_advance=True)

    # The move succeeds (exit 0) despite the breadcrumb write blowing up.
    assert main(["7", "Backlog"]) == 0
    assert board.calls == [("move", "PVTI_ITEM", "Backlog")]
    # The failure is surfaced as a warning on stderr (not a traceback, not a non-zero exit).
    assert "warning" in capsys.readouterr().err.lower()


def test_no_breadcrumb_when_move_refused_for_launch_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An anti-loop refusal (launch target) issues no move and therefore no breadcrumb."""
    board = FakeBoard()
    store = _wire(monkeypatch, board)

    assert main(["7", "InProgress"]) == 1
    assert board.calls == []
    assert store.advances == []
