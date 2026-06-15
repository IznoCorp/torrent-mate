"""Tests for the imperative-shell tick (:mod:`kanbanmate.app.tick`).

The board reader is a fake returning a scripted snapshot/probe; the remaining ports are mocks
held directly for assertion (so mypy strict still sees them as ``MagicMock``). The tests assert
the dataflow contract (DESIGN §3.1): a move into an agent column launches, a move into the
reactive Cancel column tears down, an inert move is a noop, an unchanged probe does nothing
(idempotence), and an action that raises is caught so the tick continues.
"""

from __future__ import annotations

import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kanbanmate.adapters.github.types import IssueContext
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.app.actions import Deps, LaunchAction, TeardownAction
from kanbanmate.app.tick import PersistedState, TickConfig, _drain_queue, _reap_stale_agents, tick
from kanbanmate.core.antiloop import AntiLoopState, is_blocked, record_move
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import BoardSnapshot, Ticket, Transition
from kanbanmate.core.transitions import TransitionConfig, load_transitions
from kanbanmate.ports.store import TicketState, TicketStatus

# A minimal three-class board: one column that is the LAUNCH target of the
# whitelist below, one reactive (Cancel), the rest inert/terminal. Since the
# transitions-only re-architecture (DESIGN §8.0.6) the LAUNCH lives entirely on
# the transition — columns carry NO launch config — so a whitelist is ALWAYS
# threaded into the tick (``_tick_whitelist`` / ``_config``).
_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: InProgress
    name: In Progress
  - key: Cancel
    name: Cancel
    action: teardown
  - key: Done
    name: Done
"""

# The whitelist driving the three-class board. ``Backlog -> InProgress`` carries a
# prompt + profile so it LAUNCHes; the forward moves into the terminal ``Done``
# column are whitelisted no-action edges (NOOP). ``Cancel`` routing is handled by
# the reactive precedence (no whitelist row needed: a move INTO Cancel tears down,
# Cancel -> Backlog resets — both win before the whitelist verdict). Under
# transitions-only a whitelist is ALWAYS supplied (DESIGN §8.0.6).
_TICK_WHITELIST = """
project: owner/repo
transitions:
  - from: Backlog
    to: InProgress
    prompt: "/implement:phase {{code}}"
    profile: dev
  - from: Backlog
    to: Done
  - from: InProgress
    to: Done
"""

# The whitelist driving the two-agent board (``_TWO_AGENT_COLUMNS_YAML``): two
# prompt-bearing launch edges (``Backlog -> Design``, ``Design -> InProgress``)
# plus the terminal no-action edges into ``Done``.
_TWO_AGENT_WHITELIST = """
project: owner/repo
transitions:
  - from: Backlog
    to: Design
    prompt: "/implement:brainstorm {{code}}"
    profile: dev
  - from: Design
    to: InProgress
    prompt: "/implement:phase {{code}}"
    profile: dev
  - from: InProgress
    to: Done
  - from: Backlog
    to: Done
"""


def _tick_whitelist() -> TransitionConfig:
    """Build the shared three-class-board whitelist (transitions-only, DESIGN §8.0.6)."""
    return load_transitions(_TICK_WHITELIST)


def _two_agent_whitelist() -> TransitionConfig:
    """Build the shared two-agent-board whitelist (transitions-only, DESIGN §8.0.6)."""
    return load_transitions(_TWO_AGENT_WHITELIST)


class _FakeBoardReader:
    """A scripted :class:`~kanbanmate.ports.board.BoardReader` for the tick tests.

    Returns a fixed probe token and snapshot so the tick's read path is deterministic;
    ``snapshot_calls`` counts snapshots so a test can assert the cheap probe gated the fetch.
    """

    def __init__(
        self,
        probe: str,
        snapshot: BoardSnapshot,
        *,
        closed: dict[int, bool] | None = None,
        issue_state_raises: bool = False,
    ) -> None:
        """Store the scripted probe token, snapshot, and off-board ``issue_state`` script.

        Args:
            probe: The token :meth:`cheap_probe` returns every call.
            snapshot: The board state :meth:`snapshot` returns every call.
            closed: Optional ``{issue_number: is_closed}`` script for the off-board
                ``issue_state`` fallback (#13). A number absent from the map returns
                ``False`` (OPEN — conservative). Defaults to no off-board deps.
            issue_state_raises: When ``True``, every :meth:`issue_state` call raises,
                so a test can assert the fail-soft path (an undecidable dep → UNMET).
        """
        self._probe = probe
        self._snapshot = snapshot
        self.snapshot_calls = 0
        self._closed = closed or {}
        self._issue_state_raises = issue_state_raises
        # Record every issue number the off-board fallback probed, so a test can assert the
        # perf property (ZERO calls in the common all-on-board case) and the per-dep call set.
        self.issue_state_calls: list[int] = []

    def cheap_probe(self) -> str:
        """Return the scripted probe token."""
        return self._probe

    def snapshot(self) -> BoardSnapshot:
        """Return the scripted snapshot and count the call."""
        self.snapshot_calls += 1
        return self._snapshot

    def issue_state(self, number: int) -> bool:
        """Return the scripted CLOSED state for an off-board dep (#13 live fallback).

        Records the call (for the perf assertion) and either raises (when configured,
        to exercise fail-soft) or returns the scripted CLOSED flag for ``number``.
        """
        self.issue_state_calls.append(number)
        if self._issue_state_raises:
            raise RuntimeError("simulated transient issue_state failure")
        return self._closed.get(number, False)

    def issue_context(self, number: int) -> IssueContext:  # noqa: ARG002
        """Stub: empty context (tick tests never exercise launch-prompt enrichment, 18.2)."""
        return IssueContext(body="", comments=(), linked_issue_body=None)


@dataclass
class _Mocks:
    """The mocks behind a tick :class:`Deps`, kept for direct assertion under mypy."""

    board_writer: MagicMock
    workspace: MagicMock
    sessions: MagicMock
    store: MagicMock
    clock: MagicMock
    pull_requests: MagicMock
    deps: Deps


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets into a :class:`BoardSnapshot`."""
    return BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)


def _delivered_prompt(sessions: MagicMock) -> str:
    """Return the literal text send-keys'd into the REPL, joined (phase-25 §25.1).

    The launch types the filled prompt INTO the live REPL via ``send_text(..., literal=True)``
    (PoC parity), not as a positional in the launch command. This helper joins those literal
    payloads so a tick test can assert the filled content reached the agent's REPL.

    Args:
        sessions: The mocked ``Sessions`` whose ``send_text`` calls to inspect.

    Returns:
        The concatenation of every ``literal=True`` ``send_text`` payload.
    """
    return "".join(
        c.args[1] for c in sessions.send_text.call_args_list if c.kwargs.get("literal") is True
    )


def _mocks(reader: _FakeBoardReader, *, now: float = 1000.0) -> _Mocks:
    """Build a :class:`_Mocks` bundle wiring the fake reader and mocks into a :class:`Deps`.

    Args:
        reader: The fake board reader driving the read path.
        now: The value the mocked clock returns.

    Returns:
        A :class:`_Mocks` exposing both the individual mocks and the assembled :class:`Deps`.
    """
    board_writer = MagicMock()
    workspace = MagicMock()
    workspace.ensure_worktree.return_value = "/tmp/wt/ticket-7"
    # Default a worktree present (the common teardown/reap case: the TeardownAction's replay-safety
    # guard reads ``worktree_exists`` before ``remove_worktree``) with NO unpushed work. Done-arrival
    # NOOP tests set ``worktree_exists`` False explicitly to assert the no-reclaim path (#9).
    workspace.worktree_exists.return_value = True
    workspace.has_unpushed_work.return_value = False
    sessions = MagicMock()
    sessions.launch.return_value = "ticket-7"
    sessions.is_alive.return_value = True
    # Phase-25 §25.1: a prompt-bearing launch polls ``capture`` then send-keys the filled prompt
    # into the REPL. Default the snapshot to a READY-REPL marker so the bounded poll returns at once
    # (trust_seen=False) — a bare MagicMock here would crash ``classify_pane`` (the ``in`` check).
    sessions.capture.return_value = "│ > Welcome to Claude"
    store = MagicMock()
    store.list_running.return_value = ()
    # The intent drain (cockpit PR2) runs every tick; default the queue EMPTY so drain_intents
    # returns immediately (a bare MagicMock list is truthy + non-iterable and would otherwise make
    # the drain fetch an extra snapshot / churn).
    store.list_pending_intents.return_value = ()
    # The status reporter reads the operator pill-override markers every tick (cockpit PR3); default
    # them off so the bare-MagicMock truthy return does not inject a fake override into the render.
    store.get_status_override_enum.return_value = None
    store.get_status_override_note.return_value = None
    # The tick reads the kill-switch every cycle; default it off so the launch path is exercised
    # (a bare MagicMock return is truthy and would block every launch — DESIGN §10 / H5).
    store.kill_switch_active.return_value = False
    # Default the concurrency-cap gate to "slot reserved" so EXISTING launch tests still dispatch
    # under the cap (gate 13.5). An empty drain queue keeps the post-step a no-op unless a test
    # scripts a queued ticket explicitly.
    store.reserve_slot.return_value = True
    store.dequeue_pending.return_value = ()
    # Default the per-item move rate-limit gate to "not rate-limited" (zero durable moves in the
    # last hour, gate 13.6) so EXISTING reap tests still record a durable move without tripping
    # the gate. A mock default of a bare MagicMock would raise ``TypeError: '>=' not supported``
    # when ``_rate_limited`` compares it against the cap — pin it to ``0``.
    store.move_count_for_item_last_hour.return_value = 0
    # Anti-double-session guard (defect 7): default NO recent agent-advance breadcrumb so the guard's
    # "human drag vs agent self-advance" discriminator is exercised. A test modelling a legitimate
    # AGENT self-advance (the agent ran ``kanban-move`` → breadcrumb) sets this True explicitly.
    store.recent_agent_advance.return_value = False
    clock = MagicMock()
    clock.now.return_value = now
    pull_requests = MagicMock()
    deps = Deps(
        board_writer=board_writer,
        board_reader=reader,
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=pull_requests,
        # Inject a no-op sleeper so the launch's trust/ready poll runs offline (phase-25 §25.1).
        sleeper=lambda _seconds: None,
    )
    return _Mocks(board_writer, workspace, sessions, store, clock, pull_requests, deps)


def _config() -> TickConfig:
    """Build a :class:`TickConfig` from the three-class test board + its whitelist.

    A transition whitelist is ALWAYS supplied (transitions-only, DESIGN §8.0.6).
    """
    return TickConfig(columns=load_columns(_COLUMNS_YAML), transitions=_tick_whitelist())


# ---------------------------------------------------------------------------
# Decided-action dataflow
# ---------------------------------------------------------------------------


def test_move_into_agent_column_triggers_launch() -> None:
    """A ticket moving into an agent column drives the LaunchAction path."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # Baseline: the ticket was previously in Backlog (an inert -> agent transition).
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()
    assert result.actions_executed == 1
    assert result.snapshot_taken is True
    # The baseline advanced to the new column for the next diff.
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_move_into_cancel_column_triggers_teardown() -> None:
    """A ticket moving into the reactive Cancel column drives the TeardownAction path."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Cancel")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.is_alive.assert_called_once_with("ticket-7")
    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    # Teardown runs the EXHAUSTIVE purge (13.7 split), not the slot-only release. The Cancel
    # path abandons the ticket → keep_budgets=False (the default full purge, 13.8).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.sessions.launch.assert_not_called()
    assert result.actions_executed == 1


def test_cancel_teardown_forgets_in_memory_rate_limit_history() -> None:
    """A Cancel TEARDOWN resets the ticket's IN-MEMORY anti-loop history (#22 PORT).

    The PoC's exhaustive ``purge_ticket`` ZEROED the on-disk ``moves/`` rate-limit history on
    teardown; NEW's rate-limit history lives in the volatile in-memory ``AntiLoopState`` (which
    ``purge_ticket`` cannot reach). The tick must therefore ``forget`` the torn-down item so no
    stale timestamps survive into the next tick. Seed a history, drive the Cancel path, and
    assert the next state carries no entries for the cancelled item.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Cancel")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=5_000.0)
    # Seed accumulated rate-limit history for PVTI_7 (as if the daemon had moved it before),
    # plus an UNRELATED ticket's history that must SURVIVE the teardown.
    seeded = record_move(AntiLoopState(), "PVTI_7", "InProgress", now=10.0)
    seeded = record_move(seeded, "PVTI_7", "Review", now=20.0)
    seeded = record_move(seeded, "PVTI_8", "InProgress", now=30.0)
    state = PersistedState(
        columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0", antiloop=seeded
    )

    result, next_state = tick(m.deps, _config(), state)

    assert result.actions_executed == 1
    # The cancelled item's in-memory history is gone — no stale timestamps survive the teardown.
    assert "PVTI_7" not in next_state.antiloop.move_times
    assert ("PVTI_7", "InProgress") not in next_state.antiloop.recent_targets
    assert ("PVTI_7", "Review") not in next_state.antiloop.recent_targets
    # The unrelated ticket's history is untouched (forget is item-scoped).
    assert "PVTI_8" in next_state.antiloop.move_times
    assert ("PVTI_8", "InProgress") in next_state.antiloop.recent_targets


def _running_state(issue: int = 7, *, status: TicketStatus = TicketStatus.RUNNING) -> TicketState:
    """Build a LIVE persisted :class:`TicketState` for the Done-arrival tick tests (phase 28.1)."""
    return TicketState(
        issue_number=issue,
        item_id=f"PVTI_{issue}",
        session_id="sess-uuid",
        status=status,
        heartbeat=1000.0,
        stage="InProgress",
        profile="dev",
        mode="auto",
        started=900.0,
        worktree=f"/tmp/wt/ticket-{issue}",
    )


def test_done_arrival_with_running_agent_tears_down() -> None:
    """A card landing in Done WHILE its agent is RUNNING → full DONE-flavoured teardown (phase 28.1).

    Session killed, worktree removed, state purged, the done-flavoured recap posted — and the card
    is NOT moved (it STAYS in Done; the baseline simply advances to Done as for any arrival).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.store.load.return_value = _running_state(7, status=TicketStatus.RUNNING)
    m.workspace.worktree_exists.return_value = True  # #9: reclaim is keyed on the worktree
    m.workspace.discover_branch.return_value = "feat/genesis"
    # The card was in InProgress (agent column) and the operator skipped it to Done.
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    # Full teardown ran: session killed + worktree removed + state purged.
    m.sessions.is_alive.assert_called_once_with("ticket-7")
    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    # The card was NOT moved — it stays in Done.
    m.board_writer.move_card.assert_not_called()
    # Done-flavoured recap (NOT the cancel wording).
    _issue, body = m.board_writer.comment.call_args.args
    assert "moved to Done" in body
    assert "cancelled" not in body
    assert result.actions_executed == 1
    # Baseline advanced to Done so the next diff sees no change (replay-safe).
    assert next_state.columns_by_item["PVTI_7"] == "Done"


def test_done_arrival_with_waiting_agent_tears_down() -> None:
    """A WAITING agent is LIVE too — arrival in Done tears it down exactly like RUNNING (phase 28.1)."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.store.load.return_value = _running_state(7, status=TicketStatus.WAITING)
    m.workspace.worktree_exists.return_value = True  # #9: reclaim is keyed on the worktree
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    assert result.actions_executed == 1


def test_done_arrival_with_no_worktree_is_pure_noop() -> None:
    """#9: arrival in Done with NO worktree takes NO reclaim side effects — a plain NOOP.

    The reclaim is keyed on the WORKTREE (#9), not persisted state. With no worktree there is
    nothing to reclaim, so the tick must NOT tear anything down: no kill, no worktree removal, no
    purge, no recap, no card move, zero errors. (It flows through the ordinary inert-NOOP path.)
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # No worktree → nothing to reclaim (#9). No open sticky → the LEFT finalize is a silent no-op.
    m.workspace.worktree_exists.return_value = False
    m.store.load.return_value = None
    m.board_writer.list_issue_comments.return_value = []
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    # NO reclaim side effects of ANY kind.
    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    m.board_writer.comment.assert_not_called()
    m.board_writer.update_comment.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    assert result.actions_executed == 0
    assert result.errors == 0
    # The baseline still advances to Done so the next diff sees no change.
    assert next_state.columns_by_item["PVTI_7"] == "Done"


def test_done_arrival_orphan_worktree_no_state_reclaims() -> None:
    """#9: the DOMINANT orphan — a worktree with NO persisted state — IS reclaimed on Done arrival.

    Before #9 the trigger keyed on a LIVE persisted state, so this (state purged by session-end, but
    worktree left behind, then human moves to Done) was MISSED. Keying on ``worktree_exists`` fixes
    it: a clean orphan worktree is reclaimed (removed + branch deleted) even with no state.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # The dominant orphan: a worktree EXISTS but NO state (session-end purged it), clean (no unpushed).
    m.store.load.return_value = None
    m.workspace.worktree_exists.return_value = True
    m.workspace.has_unpushed_work.return_value = False
    m.workspace.discover_branch.return_value = "feat/genesis"
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    # The orphan worktree is reclaimed even with no persisted state.
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    assert result.actions_executed == 1


def test_done_arrival_unpushed_work_blocks_instead_of_destroying() -> None:
    """#9: a Done arrival on a worktree with UNPUSHED work downgrades to Blocked, NOT a teardown.

    Never silently destroy work (rank-9 verdict): a dirty/ahead worktree is KEPT and a loud Blocked
    sticky is posted instead. No remove_worktree, no purge — the operator pushes/merges then re-Dones.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.store.load.return_value = None
    m.workspace.worktree_exists.return_value = True
    m.workspace.has_unpushed_work.return_value = True  # unpushed work present
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    # The worktree is NOT destroyed; a Blocked sticky is posted instead.
    m.workspace.remove_worktree.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    _issue, body = m.board_writer.comment.call_args.args
    assert "unpushed" in body.lower()
    assert "blocked" in body.lower()
    assert result.actions_executed == 1


def test_done_arrival_replay_after_teardown_is_clean_noop() -> None:
    """#9: a SECOND Done tick after the reclaim (worktree gone) is a clean no-op (replay-safe).

    Once the first Done arrival removed the worktree, ``worktree_exists`` returns ``False``, so a
    re-fired Done diff is the pure-no-op path — no teardown, no errors, no board writes.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # Replay: the worktree was already removed by the prior reclaim.
    m.workspace.worktree_exists.return_value = False
    m.store.load.return_value = None
    # Simulate a baseline that has NOT yet recorded Done (the diff re-fires the Done arrival).
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    m.board_writer.comment.assert_not_called()
    assert result.actions_executed == 0
    assert result.errors == 0


def test_done_arrival_teardown_forgets_in_memory_rate_limit_history() -> None:
    """A Done-arrival teardown forgets the ticket's IN-MEMORY anti-loop history (#22, like Cancel)."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=5_000.0)
    m.store.load.return_value = _running_state(7, status=TicketStatus.RUNNING)
    m.workspace.worktree_exists.return_value = True  # #9: reclaim is keyed on the worktree
    seeded = record_move(AntiLoopState(), "PVTI_7", "InProgress", now=10.0)
    seeded = record_move(seeded, "PVTI_8", "InProgress", now=30.0)
    state = PersistedState(
        columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0", antiloop=seeded
    )

    result, next_state = tick(m.deps, _config(), state)

    assert result.actions_executed == 1
    # The torn-down item's in-memory history is gone; the unrelated ticket's survives.
    assert "PVTI_7" not in next_state.antiloop.move_times
    assert "PVTI_8" in next_state.antiloop.move_times


def test_post_restart_empty_baseline_resyncs_without_spurious_launches() -> None:
    """A post-restart EMPTY ``columns_by_item`` baseline re-syncs cleanly (#20 KEEP+DOC).

    The in-memory diff baseline is wiped by a daemon restart. The first tick then sees every
    card as first-contact (``from_column=None``); an inert card must re-sync silently — no
    spurious launch / teardown / rollback — just an updated baseline. DESIGN §6: "restart + diff
    recovers downtime moves". Here the card sits in an INERT column (Done), so first-contact
    leniency yields a clean NOOP-resync.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.worktree_exists.return_value = False  # #9: no worktree → Done arrival is a NOOP
    # Post-restart: EMPTY baseline (no columns_by_item), and a probe that differs from last so a
    # fresh snapshot + diff runs (last_probe is None — the daemon just started).
    state = PersistedState()

    result, next_state = tick(m.deps, _config(), state)

    # No side effects on first-contact of an inert card — a clean silent re-sync.
    m.sessions.launch.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    assert result.actions_executed == 0
    # The baseline was re-synced from the board so the NEXT diff sees no change.
    assert next_state.columns_by_item["PVTI_7"] == "Done"


def test_inert_move_is_noop() -> None:
    """A move between two inert columns executes no action."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.worktree_exists.return_value = False  # #9: no worktree → Done arrival is a NOOP
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    m.sessions.launch.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.store.save.assert_not_called()
    assert result.actions_executed == 0
    # An inert move still advances the baseline (so the next diff sees no change).
    assert next_state.columns_by_item["PVTI_7"] == "Done"


def test_configured_move_rate_limit_reaches_the_in_memory_guard() -> None:
    """#6: ``config.move_rate_limit_per_hour`` is threaded into the decision-time anti-loop guard.

    Before #6 the tick built its ``DecideContext`` WITHOUT an ``antiloop_config``, so the
    in-memory ``is_blocked`` guard used the AntiLoopConfig DEFAULT (rate_limit=10) regardless of
    the operator's ``columns.yml`` ``move_rate_limit_per_hour``. Here the ticket already has TWO
    recent in-memory moves and the config caps at 2 — so the launch must be BLOCKed. With the
    pre-#6 default-10 the same two moves would NOT trip the guard and the agent would launch,
    so a regression of the wiring fails this test.
    """
    now = 5_000.0
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=now)
    # Seed TWO recent moves (within the 3600s rate window) for the ticket being launched. The
    # targets are DIFFERENT columns than the launch target ("InProgress") so only the per-ticket
    # RATE-LIMIT guard (guard 2) is exercised, NOT the target-keyed dedup guard (guard 1).
    seeded = record_move(AntiLoopState(), "PVTI_7", "Done", now=now - 10.0)
    seeded = record_move(seeded, "PVTI_7", "Review", now=now - 5.0)
    state = PersistedState(
        columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0", antiloop=seeded
    )
    # Cap the per-hour move rate at 2 (the operator's columns.yml default). Two recent moves are
    # already on record, so the configured cap (2) trips is_blocked → BLOCK (no launch).
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML),
        move_rate_limit_per_hour=2,
        transitions=_tick_whitelist(),
    )

    tick(m.deps, config, state)

    # The configured cap reached the guard → the launch was downgraded to BLOCK (no session).
    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()


def test_default_move_rate_limit_does_not_block_two_moves() -> None:
    """#6 contrast: under the DEFAULT cap (10) the same two recent moves do NOT block a launch.

    Proves the BLOCK in the sibling test is the CONFIGURED cap (2) tripping, not some unrelated
    guard: with the default 10 the two-move ticket still LAUNCHes.
    """
    now = 5_000.0
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=now)
    # Same two-move seed as the sibling test (into non-target columns so only guard 2 is in play).
    seeded = record_move(AntiLoopState(), "PVTI_7", "Done", now=now - 10.0)
    seeded = record_move(seeded, "PVTI_7", "Review", now=now - 5.0)
    state = PersistedState(
        columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0", antiloop=seeded
    )
    # Default move_rate_limit_per_hour (10) — two recent moves are well under the cap.
    config = TickConfig(columns=load_columns(_COLUMNS_YAML), transitions=_tick_whitelist())

    result, _ = tick(m.deps, config, state)

    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1


def test_move_by_option_name_triggers_launch() -> None:
    """The adapter→decide seam: a ticket whose column_key is the option NAME LAUNCHes.

    The github adapter sets ``Ticket.column_key`` to the GitHub Status option NAME
    ("In Progress"), not the key ("InProgress"); the diff then carries that NAME as the
    transition's ``to_column``. Before the name/key resolution the column model lookup
    missed entirely → NOOP → no launch on the real default board. This test feeds the
    NAME (the variance the key-based unit tests masked) and asserts a LAUNCH.
    """
    # column_key is the option NAME the adapter emits, not the key.
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="In Progress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1
    # The baseline advances to the NAME the board reported (the next diff compares names).
    assert next_state.columns_by_item["PVTI_7"] == "In Progress"


def test_unmet_dependency_bounces_card_back_to_from_column() -> None:
    """A ticket entering an agent column with an unmet ``Depends on #N`` is BOUNCED back (phase 32).

    The dependency gate (DESIGN §9) parses ``Depends on #N`` from the issue body; while the
    referenced issue is still in a non-done column the launch is gated. No worktree/session is
    created, and the card is RETURNED to its from-column (Backlog) — never stranded in the
    triggering column — with a dependency-named recap comment. The next-tick baseline is the
    bounce target (the ROLLBACK idempotency seam), so the bounce does not re-fire.
    """
    blocked = Ticket(
        item_id="PVTI_7",
        issue_number=7,
        title="t",
        column_key="InProgress",
        body="Depends on #5",
    )
    # The dependency #5 is still In Progress on the same board → unmet. It is already in the
    # baseline (no transition of its own), so this tick only decides on #7's move.
    dep = Ticket(item_id="PVTI_5", issue_number=5, title="dep", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(blocked, dep))
    m = _mocks(reader)
    state = PersistedState(
        columns_by_item={"PVTI_7": "Backlog", "PVTI_5": "InProgress"}, last_probe="probe-0"
    )

    result, next_state = tick(m.deps, _config(), state)

    # No agent machinery touched — the gate replaced #7's LAUNCH with a dependency bounce.
    m.workspace.ensure_worktree.assert_not_called()
    m.sessions.launch.assert_not_called()
    m.store.save.assert_not_called()
    # The card is bounced BACK to its from-column (Backlog), not left stranded in InProgress.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Backlog")
    # The recap surfaces the unmet-dependency reason + the bounce target + the re-drag guidance.
    m.board_writer.comment.assert_called_once()
    body = m.board_writer.comment.call_args.args[1]
    assert "#5 (in InProgress)" in body
    assert "card returned to Backlog" in body
    assert "once dependencies are Done" in body
    # The bounce still counts as an executed action (it ran cleanly, no error).
    assert result.actions_executed == 1
    assert result.errors == 0
    # The diff baseline is the BOUNCE TARGET (Backlog), not the rejected destination (InProgress),
    # so a re-tick against the settled board produces no re-bounce (the idempotency seam).
    assert next_state.columns_by_item["PVTI_7"] == "Backlog"


def test_met_dependency_allows_launch() -> None:
    """The same ticket launches once its declared dependency reaches a done column."""
    ready = Ticket(
        item_id="PVTI_7",
        issue_number=7,
        title="t",
        column_key="InProgress",
        body="Depends on #5",
    )
    # The dependency #5 is now Done → the gate is satisfied. Already in the baseline so this
    # tick only decides on #7's move.
    dep = Ticket(item_id="PVTI_5", issue_number=5, title="dep", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ready, dep))
    m = _mocks(reader)
    state = PersistedState(
        columns_by_item={"PVTI_7": "Backlog", "PVTI_5": "Done"}, last_probe="probe-0"
    )

    result, _ = tick(m.deps, _config(), state)

    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()
    assert result.actions_executed == 1


def test_no_dependency_in_body_launches() -> None:
    """A ticket whose body declares no dependency launches unchanged (back-compat)."""
    ticket = Ticket(
        item_id="PVTI_7",
        issue_number=7,
        title="t",
        column_key="InProgress",
        body="A plain issue body with no dependency marker.",
    )
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1


def test_on_board_dependency_triggers_zero_issue_state_calls() -> None:
    """A dep fully on the board is decided by the snapshot — ZERO live queries (#13 perf)."""
    ready = Ticket(
        item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress", body="Depends on #5"
    )
    # #5 is on the board AND done → the snapshot fully decides the gate, no fallback fires.
    dep = Ticket(item_id="PVTI_5", issue_number=5, title="dep", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ready, dep))
    m = _mocks(reader)
    state = PersistedState(
        columns_by_item={"PVTI_7": "Backlog", "PVTI_5": "Done"}, last_probe="probe-0"
    )

    result, _ = tick(m.deps, _config(), state)

    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1
    # The perf property: no off-board fallback query was made.
    assert reader.issue_state_calls == []


def test_closed_off_board_dependency_passes_via_live_fallback() -> None:
    """A dep CLOSED but absent from the board PASSES the gate via ``issue_state`` (#13 parity)."""
    ticket = Ticket(
        item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress", body="Depends on #5"
    )
    # #5 is NOT on the board (e.g. closed-as-not-planned) but is CLOSED → the fallback satisfies it.
    reader = _FakeBoardReader("probe-1", _snapshot(ticket), closed={5: True})
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1
    # The fallback fired EXACTLY for the off-board dep.
    assert reader.issue_state_calls == [5]


def test_open_off_board_dependency_bounces_via_live_fallback() -> None:
    """A dep OPEN and absent from the board is UNMET via the fallback — bounced back (#13/phase 32)."""
    ticket = Ticket(
        item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress", body="Depends on #5"
    )
    # #5 is off-board AND still OPEN → the fallback resolves it UNMET, gating the LAUNCH → bounce.
    reader = _FakeBoardReader("probe-1", _snapshot(ticket), closed={5: False})
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    # The card is bounced back to Backlog; the recap names the off-board dep.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Backlog")
    m.board_writer.comment.assert_called_once()
    body = m.board_writer.comment.call_args.args[1]
    assert "#5" in body
    assert reader.issue_state_calls == [5]
    assert result.actions_executed == 1  # the bounce ran cleanly


def test_throwing_issue_state_fails_soft_to_unmet() -> None:
    """A throwing ``issue_state`` leaves the off-board dep UNMET — never launches (#13 fail-soft)."""
    ticket = Ticket(
        item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress", body="Depends on #5"
    )
    # #5 is off-board and the live probe RAISES → conservative: treat as UNMET, do not launch.
    reader = _FakeBoardReader("probe-1", _snapshot(ticket), issue_state_raises=True)
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.launch.assert_not_called()
    # Fail-soft UNMET → the launch is gated and the card bounced back to Backlog.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Backlog")
    m.board_writer.comment.assert_called_once()
    assert reader.issue_state_calls == [5]
    assert result.actions_executed == 1  # the bounce ran; the throwing probe was swallowed
    assert result.errors == 0  # fail-soft: the gate did not surface as a tick error


def test_unknown_destination_column_logs_warning_and_noops(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A first-contact move into a column unknown to the model logs a warning and runs no action.

    A misconfiguration (columns.yml out of sync with the board's Status options) must be
    distinguishable from an intentional inert NOOP, which is otherwise silent (errors-6). A
    first-contact card (no baseline ⇒ ``from_column=None``) into an unknown column has no origin to
    bounce to, so the transitions-only verdict is a recording NOOP (not a ROLLBACK) — and the
    unknown-column warning fires on that NOOP branch.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Ghost Column")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # First-contact: EMPTY baseline so the diff yields from_column=None (no origin to roll back to).
    state = PersistedState(last_probe="probe-0")

    with caplog.at_level(logging.WARNING, logger="kanbanmate.app.tick"):
        result, next_state = tick(m.deps, _config(), state)

    m.sessions.launch.assert_not_called()
    assert result.actions_executed == 0
    # The baseline still advances (the card *is* in that column on the board).
    assert next_state.columns_by_item["PVTI_7"] == "Ghost Column"
    # The unknown column is named in a warning so a misconfiguration is not silent.
    assert any(
        "unknown column" in rec.message and "Ghost Column" in rec.getMessage()
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# Idempotence + probe gating
# ---------------------------------------------------------------------------


def test_unchanged_probe_skips_snapshot_and_does_nothing() -> None:
    """When the probe token is unchanged, no snapshot is fetched and no action runs."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # last_probe already equals the reader's probe -> the board is assumed unchanged.
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    assert reader.snapshot_calls == 0
    assert result.snapshot_taken is False
    m.sessions.launch.assert_not_called()
    assert result.actions_executed == 0


def test_idempotent_second_tick_does_not_relaunch() -> None:
    """Two ticks against the same board produce exactly one launch (idempotence)."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    # First tick: the inert -> agent transition launches once.
    _, state2 = tick(m.deps, _config(), state)
    assert m.sessions.launch.call_count == 1

    # Second tick: same probe token now matches the carried-over baseline -> no work, no
    # duplicate launch. This is the core idempotence guarantee (DESIGN §3.1).
    result2, _ = tick(m.deps, _config(), state2)
    assert m.sessions.launch.call_count == 1
    assert result2.snapshot_taken is False
    assert reader.snapshot_calls == 1


# ---------------------------------------------------------------------------
# Robustness: exception isolation + reaping
# ---------------------------------------------------------------------------


def test_raised_action_is_caught_and_tick_continues() -> None:
    """An action that raises is caught (counted as an error) and the tick still completes."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # Make the launch path explode inside the worker thread.
    m.workspace.ensure_worktree.side_effect = RuntimeError("git blew up")
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    # The exception was swallowed; the tick returned a result with the error counted.
    assert result.errors == 1
    assert result.actions_executed == 0
    # The baseline still advanced (the card *is* in the new column), so the next tick does not
    # replay the failed launch every cycle.
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_watchdog_timeout_counts_as_error_and_tick_continues() -> None:
    """An action blocking past ``action_timeout`` hits the FutureTimeoutError branch.

    When an adapter call hangs past the per-action watchdog budget the action is
    counted as an error (not executed), the tick completes, and the baseline advances
    so the stalled action does not replay every cycle. This exercises the ``except
    FutureTimeoutError`` path in :func:`~kanbanmate.app.tick._run_with_watchdog`,
    distinct from the ``except Exception`` path tested by
    :func:`test_raised_action_is_caught_and_tick_continues`.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # Make the launch path block past the watchdog budget. The worker thread sleeps;
    # the main thread's future.result(timeout=0.01) raises FutureTimeoutError.
    m.workspace.ensure_worktree.side_effect = lambda *args, **kwargs: time.sleep(0.05)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), action_timeout=0.01, transitions=_tick_whitelist()
    )

    result, next_state = tick(m.deps, config, state)

    # The timeout is counted as an error, not as a successful execution.
    assert result.errors >= 1
    assert result.actions_executed == 0
    # The baseline still advances (the card *is* in the new column on the board).
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_reap_stale_agent_tears_down_and_blocks() -> None:
    """A running ticket past the heartbeat TTL is torn down and blocked by the reap step."""
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    # One running ticket whose heartbeat is far older than the default 1800s TTL.
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
    )
    m.store.list_running.return_value = (stale,)
    # Probe unchanged so only the reap step runs (proves reaping is independent of the diff).
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The block comment is posted, but the reap is NON-DESTRUCTIVE (defect 5, ``reap`` flavour): the
    # worktree is NOT removed, the branch NOT deleted, the PR NOT closed — a stalled agent keeps its
    # unpushed work (PoC parity). Under Approach A the reaper does not kill a dead session (nothing
    # to kill; teardown only kills a live session).
    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.workspace.delete_branch.assert_not_called()
    m.pull_requests.close_open_pr_for_branch.assert_not_called()
    # The reap's TeardownAction purges the runtime markers but PRESERVES the per-issue budgets
    # → keep_budgets=True (13.8), so the durable §6 rate-limit accumulates across reaps.
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    # ONE comment only: the reaper's block-reason (the reap flavour posts NO teardown recap).
    assert m.board_writer.comment.call_count == 1  # block reason only
    # The card is also parked in the Blocked column so the stall shows on the board (DESIGN §8.3).
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    # No relaunch — the reaper must never resurrect the dead agent.
    m.sessions.launch.assert_not_called()
    assert result.reaped == 1


def test_reap_uses_configured_blocked_column() -> None:
    """The reaper parks the card in ``TickConfig.blocked_column`` (custom column key honoured)."""
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
    )
    m.store.list_running.return_value = (stale,)
    state = PersistedState(last_probe="probe-1")
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), blocked_column="Stalled", transitions=_tick_whitelist()
    )

    result, _ = tick(m.deps, config, state)

    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Stalled")
    assert result.reaped == 1


def test_reap_reason_is_dead_session_and_alive_stale_is_not_reaped() -> None:
    """The reap reason is "dead agent session"; an alive+stale agent is parked WAITING, not reaped.

    Under Approach A the reap path is reached ONLY for a DEAD session, so the stall comment always
    names the dead session. An agent merely past the heartbeat TTL but whose session is STILL ALIVE
    is parked WAITING (never killed) — it posts NO reap comment.
    """
    # Case 1: dead session (is_alive False), heartbeat fresh-ish but session gone → dead-session reap.
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = False  # session GONE → the dead-session trigger
    dead = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=10_000.0,  # fresh heartbeat — only the dead session triggers the reap
    )
    m.store.list_running.return_value = (dead,)
    tick(m.deps, _config(), PersistedState(last_probe="probe-1"))
    dead_comment = " ".join(c.args[1] for c in m.board_writer.comment.call_args_list)
    assert "dead agent session" in dead_comment

    # Case 2: stale heartbeat but session STILL ALIVE → parked WAITING, NOT reaped (Approach A).
    reader2 = _FakeBoardReader("probe-1", _snapshot())
    m2 = _mocks(reader2, now=10_000.0)
    m2.sessions.is_alive.return_value = True  # session alive…
    m2.sessions.capture.return_value = "idle / no prompt"  # …no waiting marker, but still ALIVE
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # ancient → past the TTL
    )
    m2.store.list_running.return_value = (stale,)
    result2, _ = tick(m2.deps, _config(), PersistedState(last_probe="probe-1"))
    # No reap, no kill, no Blocked move — the live session is parked WAITING instead.
    m2.sessions.kill.assert_not_called()
    m2.board_writer.move_card.assert_not_called()
    assert result2.reaped == 0
    saved2 = [c.args[0] for c in m2.store.save.call_args_list]
    assert any(s.status is TicketStatus.WAITING for s in saved2)


def test_fresh_agent_is_not_reaped() -> None:
    """A running ticket within the TTL is left alone by the reap step (no teardown, no move)."""
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=1000.0)
    fresh = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=900.0,  # only 100s old, well within the 1800s TTL
    )
    m.store.list_running.return_value = (fresh,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    # No teardown ran — neither the exhaustive purge nor the slot-only release was called.
    m.store.purge_ticket.assert_not_called()
    m.store.release_slot.assert_not_called()
    assert result.reaped == 0


# ---------------------------------------------------------------------------
# Reaper relaunch-once (15.2 / RETRY_LIMIT): a stale running session is relaunched
# ONCE (kill + bump retries + REFRESH heartbeat + relaunch SAME stage) before Blocked.
# Port of the PoC ``reaper.apply`` block-with-retry branch (reaper.py:106-184).
# ---------------------------------------------------------------------------


def test_reaper_relaunches_stale_session_once() -> None:
    """A DEAD session with ``retries == 0`` (and a stage) is RELAUNCHED once, not blocked.

    Port of the PoC ``reaper.apply`` retry branch (reaper.py:156-166). Under Approach A the relaunch
    path is reached only for a DEAD session (an alive one is parked WAITING): ``retries`` is bumped to
    1, the heartbeat is REFRESHED to ``now`` (the load-bearing refresh, DESIGN §8.3) and the status
    set back to RUNNING, and a fresh LaunchAction for the SAME stage runs — the card is NOT parked in
    Blocked. The kill is a no-op for the already-dead session (``is_alive`` False → skipped). The
    retry is counted as ``relaunched``, never ``reaped``.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = False  # DEAD session → the reap/relaunch path (Approach A)
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # ancient → past the TTL
        stage="InProgress",  # a recorded stage so the relaunch can re-enter the column
        # Phase 20 (DESIGN §8.0.6): the reaper relaunch reuses the PERSISTED profile (the agent
        # launches AT the transition, so the relaunch — an internal retry, not a board move — has
        # no transition to read; it re-runs under the profile the original launch resolved).
        profile="dev",
        retries=0,  # under RETRY_LIMIT → RETRY branch
    )
    m.store.list_running.return_value = (stale,)
    state = PersistedState(last_probe="probe-1")  # probe unchanged → only the reap step runs

    result, _ = tick(m.deps, _config(), state)

    # The session liveness was probed; the kill is SKIPPED for the already-dead session (Approach A —
    # the reaper never kills, and a dead session has nothing to kill).
    m.sessions.is_alive.assert_any_call("ticket-7")
    m.sessions.kill.assert_not_called()
    # A fresh LaunchAction ran for the SAME stage (the relaunch re-enters the agent column).
    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    m.sessions.launch.assert_called_once()
    # The card was NOT parked in Blocked — the retry keeps the ticket running.
    m.board_writer.move_card.assert_not_called()
    # The reaper did NOT tear the ticket down (the running session is relaunched, not abandoned).
    m.workspace.remove_worktree.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    # The saved state carries retries==1, status==RUNNING, heartbeat REFRESHED to now. Two saves
    # happen: the reaper's bump-and-refresh save, then the relaunch's LaunchAction.save — the
    # bump save is the one carrying the refreshed reaper state (retries=1, heartbeat=now).
    saved_states = [c.args[0] for c in m.store.save.call_args_list]
    bumped = next(s for s in saved_states if s.retries == 1)
    assert bumped.status is TicketStatus.RUNNING
    assert bumped.heartbeat == 10_000.0  # the load-bearing heartbeat refresh
    assert bumped.stage == "InProgress"
    # Phase 20 (DESIGN §8.0.6): the relaunch's LaunchAction resolved its profile from the PERSISTED
    # ``state.profile`` (not a column default) — the relaunch save carries the same ``dev``.
    relaunched_save = next(s for s in saved_states if s.session_id != "ticket-7")
    assert relaunched_save.profile == "dev"
    # The relaunch's LaunchAction state write PRESERVES the bumped retry budget (retries==1), not the
    # default 0 — otherwise RETRY_LIMIT never trips and the reaper relaunches forever (the helm #5
    # infinite-relaunch bug). See ``test_reaper_relaunch_preserves_retry_budget``.
    assert relaunched_save.retries == 1
    # A successful relaunch is counted separately from a reap.
    assert result.relaunched == 1
    assert result.reaped == 0


def test_reaper_relaunch_preserves_retry_budget() -> None:
    """Fix: a reaper relaunch's bumped ``retries`` SURVIVES the LaunchAction state write.

    ``_try_relaunch`` bumps ``retries`` to 1 (the pre-save) and dispatches a LaunchAction. The
    LaunchAction writes a fresh ``TicketState``; before the fix it omitted ``retries`` so the field
    defaulted to 0, silently RESETTING the budget — every subsequent reap saw ``retries == 0`` and
    relaunched again, an infinite loop that never escalated to Blocked (RETRY_LIMIT defeated). The fix
    threads ``retries = state.retries + 1`` onto the LaunchAction, so EVERY state the relaunch persists
    carries ``retries == 1``. A SECOND reap of the same (still dead) session then sees
    ``retries >= RETRY_LIMIT`` and parks it in Blocked instead of relaunching forever.
    """
    # First reap: a dead session at retries==0 → relaunch; every persisted state must carry retries==1.
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = False  # DEAD → reap/relaunch path
    m.sessions.launch.return_value = "newsess"  # the relaunch's fresh session id
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        profile="dev",
        retries=0,
    )
    m.store.list_running.return_value = (stale,)

    result, _ = tick(m.deps, _config(), PersistedState(last_probe="probe-1"))

    assert result.relaunched == 1
    saved = [c.args[0] for c in m.store.save.call_args_list if c.args[0].issue_number == 7]
    assert saved, "expected the relaunch to persist state for #7"
    # The pre-save AND the LaunchAction save must BOTH carry retries==1 (no reset to 0).
    assert all(s.retries == 1 for s in saved), [s.retries for s in saved]

    # Second reap: the same session is still dead and now at retries==1 (>= RETRY_LIMIT) → it parks in
    # Blocked instead of relaunching again (proving the preserved budget actually trips the limit).
    reader2 = _FakeBoardReader("probe-1", _snapshot())
    m2 = _mocks(reader2, now=20_000.0)
    m2.sessions.is_alive.return_value = False
    relaunched_state = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="newsess",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        profile="dev",
        retries=1,  # carried over from the first relaunch
    )
    m2.store.list_running.return_value = (relaunched_state,)

    result2, _ = tick(m2.deps, _config(), PersistedState(last_probe="probe-1"))

    m2.sessions.launch.assert_not_called()  # no second relaunch
    m2.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    assert result2.reaped == 1
    assert result2.relaunched == 0


def test_reaper_under_pause_does_not_relaunch_parks_blocked() -> None:
    """Under PAUSE (kill_switch) a stale agent is NOT relaunched — it parks in Blocked (defect 6).

    Normally a stale agent with ``retries == 0`` is relaunched; with the kill-switch on, the RETRY
    branch is suppressed so no agent launches, and the ticket falls through to the non-destructive
    BLOCK park (kill + move Blocked). The reap bookkeeping stays intact.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        profile="dev",
        retries=0,  # under RETRY_LIMIT → would normally RELAUNCH, but PAUSE suppresses it
    )
    m.store.list_running.return_value = (stale,)

    with ThreadPoolExecutor(max_workers=1) as executor:
        reaped, relaunched, _errors, _antiloop = _reap_stale_agents(
            m.deps, _config(), executor, 10_000.0, AntiLoopState(), kill_switch=True
        )

    # No launch under PAUSE — the relaunch is suppressed, the ticket parks in Blocked instead.
    m.sessions.launch.assert_not_called()
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    assert relaunched == 0
    assert reaped == 1


def test_reaper_relaunch_rebuilds_launchaction_with_persisted_prompt(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The reaper relaunch rebuilds a LaunchAction carrying the PERSISTED relaunch inputs.

    Phase-25 §25.2 (PoC parity): the relaunch inputs (prompt / script / permission_mode / on_fail /
    advance / profile) persisted at launch are re-threaded onto the rebuilt
    :class:`~kanbanmate.app.actions.LaunchAction`, so a reaper relaunch RE-DELIVERS the prompt via
    the 25.1 send-keys path instead of spawning a PROMPTLESS idle agent (the regression). We capture
    the command ``_try_relaunch`` hands to the watchdog and assert every relaunch input rode across.
    """
    from kanbanmate.app import tick as tick_mod
    from kanbanmate.app.reaper import _try_relaunch

    captured: list[object] = []

    def _capture_watchdog(executor, command, deps, timeout):  # type: ignore[no-untyped-def]
        # Stand in for the real watchdog: record the rebuilt command, report a clean dispatch.
        captured.append(command)
        return True

    monkeypatch.setattr(tick_mod, "_run_with_watchdog", _capture_watchdog)

    deps = MagicMock()
    deps.sessions.is_alive.return_value = False  # no live session to kill
    state = TicketState(
        issue_number=140,
        item_id="PVTI_140",
        session_id="ticket-140",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="Spec",
        profile="docs",
        mode="acceptEdits",  # the persisted permission_mode the relaunch must re-thread
        prompt="/implement:brainstorm #140",  # the FILLED launch prompt (the load-bearing input)
        script="check.sh",
        on_fail="block",
        advance="next",
        # Defect 4: the persisted title + body must ride onto the rebuilt Ticket so the relaunched
        # agent parses the SAME codename/design_path/plan_paths and does NOT self-DESYNC.
        title="[A2] My feature",
        body="**codename**: my-feature\n**design**: docs/features/my-feature/DESIGN.md",
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        ok = _try_relaunch(deps, _config(), executor, state, now=10_000.0)

    assert ok is True
    # Exactly one command was dispatched — the rebuilt LaunchAction.
    assert len(captured) == 1
    relaunch = captured[0]
    assert isinstance(relaunch, LaunchAction)
    # The relaunch carries the PERSISTED prompt (the headline parity fix — NOT a promptless agent).
    assert relaunch.prompt == "/implement:brainstorm #140"
    # …and every other persisted relaunch input: script / permission_mode (off ``mode``) / on_fail /
    # advance / profile, plus the SAME stage as the launch column key.
    assert relaunch.script == "check.sh"
    assert relaunch.permission_mode == "acceptEdits"
    assert relaunch.on_fail == "block"
    assert relaunch.advance == "next"
    assert relaunch.profile == "docs"
    assert relaunch.ticket.column_key == "Spec"
    assert relaunch.ticket.issue_number == 140
    # Defect 4: the rebuilt Ticket carries the PERSISTED title + body (not ``ticket-140`` / "") so
    # parse_ticket_fields recovers the codename/design_path/plan_paths and the agent does not DESYNC.
    assert relaunch.ticket.title == "[A2] My feature"
    assert "**codename**: my-feature" in relaunch.ticket.body


def test_reaper_blocks_after_retry_limit_reached() -> None:
    """A SECOND stale sweep (``retries == 1 >= RETRY_LIMIT``) parks the card in Blocked.

    The retry budget is spent, so the existing BLOCK flow runs: TeardownAction (kill / remove
    worktree / release slot), move to ``blocked_column``, ⛔ flip. ``reaped == 1``, no relaunch.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        retries=1,  # already at RETRY_LIMIT → BLOCK branch (no further relaunch)
    )
    m.store.list_running.return_value = (stale,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The block flow uses the NON-DESTRUCTIVE ``reap`` flavour (defect 5): purge state + park in
    # Blocked ONLY. The worktree is NOT removed, the branch NOT deleted, the PR NOT closed — a
    # twice-stalled agent keeps its unpushed work and open PR (PoC parity). Under Approach A the
    # reaper does not kill a dead session (nothing to kill; teardown only kills a live session).
    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.workspace.delete_branch.assert_not_called()
    m.pull_requests.close_open_pr_for_branch.assert_not_called()
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    # No relaunch — the budget is spent.
    m.sessions.launch.assert_not_called()
    assert result.reaped == 1
    assert result.relaunched == 0


def test_reaper_relaunch_that_raises_parks_in_blocked() -> None:
    """A relaunch that RAISES falls through to the BLOCK branch (port reaper.py:173-182).

    One bad retry must not starve the sweep: the failed relaunch is caught, the ticket gets a
    visible Blocked signal (counted as ``reaped``), and the sweep continues. We force the failure
    by making the LaunchAction's ``sessions.launch`` raise.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        profile="dev",  # phase 20: a resolvable persisted profile so the FAILURE is the launch
        retries=0,  # under RETRY_LIMIT → RETRY branch is attempted first
    )
    m.store.list_running.return_value = (stale,)
    # The relaunch's LaunchAction.execute blows up inside the watchdog → the retry "raises".
    m.sessions.launch.side_effect = RuntimeError("tmux new-session failed")
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The retry was attempted (kill + relaunch dispatched) but failed, so the ticket is parked.
    m.sessions.launch.assert_called_once()
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    # The failed retry is a reap (the ticket got its visible Blocked signal), NOT a relaunch.
    assert result.reaped == 1
    assert result.relaunched == 0
    # The failed relaunch is counted as an error (one bad retry, the sweep continued).
    assert result.errors >= 1


def test_reaper_writes_idle_before_teardown_so_purge_failure_never_leaves_running_zombie() -> None:
    """A stale agent that blocks (retries >= RETRY_LIMIT) with a FAIL-SOFT purge_ticket must leave
    the persisted state as ``IDLE``, not ``RUNNING`` — no fresh-heartbeat zombie.

    Port of the PoC ``reaper._move_to_blocked`` ordering (reaper.py:87-88): the terminal status
    is written BEFORE the teardown runs, so a partial purge failure cannot leave a RUNNING state
    with a refreshed heartbeat that the next sweep skips forever. This test forces the failure by
    making ``purge_ticket`` raise; the assertion is on the ``save`` call's status value.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        retries=1,  # >= RETRY_LIMIT → BLOCK branch (no retry attempted)
    )
    m.store.list_running.return_value = (stale,)
    # The purge itself fails — the state file lingers. The IDLE write MUST have happened first.
    m.store.purge_ticket.side_effect = OSError("disk full")
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The sweep survived the purge failure (fail-soft).
    # The ticket still got its visible Blocked signal (comments + move).
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    # The critical invariant: the LAST save for this issue carries status=IDLE, not RUNNING.
    # Even though the purge failed and the state file lingers, a subsequent list_running()
    # (which filters to status==RUNNING) would NOT return it — no zombie.
    saved_for_7 = [c.args[0] for c in m.store.save.call_args_list if c.args[0].issue_number == 7]
    assert saved_for_7, "expected at least one save for issue #7"
    last_save = saved_for_7[-1]
    assert last_save.status is TicketStatus.IDLE, (
        f"terminal save must be IDLE so purge failure leaves no RUNNING zombie, "
        f"got {last_save.status}"
    )
    assert result.reaped == 1
    assert result.relaunched == 0
    # The purge failure was caught inside TeardownAction (fail-soft) so the watchdog itself
    # returned True; the reaper's errors tally only counts watchdog-level failures, not
    # internal TeardownAction step failures. The ticket still got its visible Blocked signal.


def test_ticket_status_idle_member_is_load_bearing_and_referenced_by_reaper() -> None:
    """``TicketStatus.IDLE`` must keep existing AND stay referenced by the reaper (#21 KEEP+DOC).

    #21 was RE-SCOPED from REMOVE to KEEP+DOC: ``IDLE`` became load-bearing in phase 15.2 (the
    reaper writes ``status=IDLE`` before its teardown purge so a fail-soft purge failure cannot
    leave a fresh-heartbeat RUNNING zombie). This guard test fails loudly if a future change
    silently drops the member or the reaper's live use of it.
    """
    import inspect

    from kanbanmate.app import reaper as reaper_module

    # The enum member still exists with its on-disk value.
    assert TicketStatus.IDLE.value == "idle"
    # The reaper source references it (the terminal non-RUNNING write before teardown).
    reaper_src = inspect.getsource(reaper_module)
    assert "TicketStatus.IDLE" in reaper_src, (
        "the reaper must write status=IDLE before teardown (15.2 zombie guard); "
        "TicketStatus.IDLE was silently removed from app/reaper.py"
    )


def test_reaper_skips_retry_when_stage_empty() -> None:
    """A stale agent with ``stage == ""`` skips the retry and blocks directly (fail-soft).

    An old-format state with no recorded stage cannot relaunch (the relaunch would re-enter no
    column), so the reaper goes straight to the BLOCK branch even though ``retries < RETRY_LIMIT``.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="",  # old-format: no recorded stage → fail-soft straight to BLOCK
        retries=0,  # under the limit, but the empty stage overrides → no relaunch
    )
    m.store.list_running.return_value = (stale,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # No relaunch (no launch dispatched, no worktree ensured) — straight to Blocked.
    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    assert result.reaped == 1
    assert result.relaunched == 0


def test_reaper_relaunched_reported_separately_from_reaped() -> None:
    """``relaunched`` is reported on ``TickResult`` distinctly from ``reaped`` (observability).

    Two stale agents in one sweep: one with ``retries == 0`` (relaunched) and one with
    ``retries == 1`` (blocked). The result tallies them in their own counters.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD sessions → reach the reap path (Approach A reaps only dead sessions)
    )
    retry_agent = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        profile="dev",  # phase 20: the relaunch reuses the persisted profile (DESIGN §8.0.6)
        retries=0,
    )
    block_agent = TicketState(
        issue_number=8,
        item_id="PVTI_8",
        session_id="ticket-8",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        retries=1,
    )
    m.store.list_running.return_value = (retry_agent, block_agent)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # Exactly one relaunch (#7) and exactly one reap (#8), reported in distinct counters.
    assert result.relaunched == 1
    assert result.reaped == 1
    # The blocked agent's card is parked; the relaunched agent's is not.
    m.board_writer.move_card.assert_called_once_with("PVTI_8", "Blocked")


# ---------------------------------------------------------------------------
# #26 PORT — reaper dead-session trigger. The reap gate widens from heartbeat-stale ONLY to
# heartbeat-stale OR dead-tmux-session: a crashed agent whose LAST heartbeat is still fresh but
# whose session died is reaped immediately (the PoC reaper.sweep two-trigger gate, reaper.py:49-57),
# not after the full TTL. The probe is fail-closed: a throwing is_alive leaves the heartbeat-TTL
# path intact (a fresh ticket is NOT wrongly reaped, and the sweep does not crash).
# ---------------------------------------------------------------------------


def test_reaper_reaps_dead_session_even_with_fresh_heartbeat() -> None:
    """A running ticket whose tmux session DIED is reaped even with a FRESH heartbeat (#26).

    The heartbeat is well within the TTL, so the OLD heartbeat-only gate would have SKIPPED it; the
    widened gate reaps it because ``is_alive`` reports the session gone. With ``retries == 1`` the
    ticket is at the limit, so it goes straight to the BLOCK branch (teardown + park-in-Blocked) —
    the assertion proves the dead-session trigger fired (the move-to-Blocked would never happen
    under the heartbeat-only gate for a fresh ticket).
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=1000.0)
    m.sessions.is_alive.return_value = False  # the tmux session DIED
    fresh_but_dead = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=900.0,  # only 100s old — well within the 1800s TTL (would be skipped on hb alone)
        stage="InProgress",
        retries=1,  # >= RETRY_LIMIT → straight to BLOCK (proves the dead-session gate, not a retry)
    )
    m.store.list_running.return_value = (fresh_but_dead,)
    state = PersistedState(last_probe="probe-1")  # probe unchanged → only the reap step runs

    result, _ = tick(m.deps, _config(), state)

    # The fresh-but-dead ticket was reaped: teardown + parked in Blocked despite the fresh heartbeat.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    assert result.reaped == 1


def test_reaper_relaunches_dead_session_with_fresh_heartbeat_under_retry_limit() -> None:
    """A fresh-heartbeat ticket whose session DIED with ``retries < RETRY_LIMIT`` is RELAUNCHED
    once (#26 composes with the 15.2 RETRY branch, not just BLOCK).

    The dead-session gate triggers the reap; because the retry budget is intact the EXISTING 15.2
    RETRY/BLOCK branching relaunches the same stage (kill + bump retries + refresh heartbeat +
    relaunch) rather than blocking — the PoC reaped a dead session immediately; NEW relaunches it
    once first. The relaunch is counted as ``relaunched``, the card is NOT parked.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=1000.0)
    m.sessions.is_alive.return_value = False  # the session is gone
    fresh_but_dead = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=900.0,  # fresh heartbeat — only the dead session triggers the reap
        stage="InProgress",
        profile="dev",  # phase 20: the relaunch reuses the persisted profile (DESIGN §8.0.6)
        retries=0,  # under RETRY_LIMIT → RETRY branch
    )
    m.store.list_running.return_value = (fresh_but_dead,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The 15.2 RETRY branch ran: a fresh LaunchAction for the same stage, no park-in-Blocked.
    m.sessions.launch.assert_called_once()
    m.board_writer.move_card.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    assert result.relaunched == 1
    assert result.reaped == 0


def test_reaper_does_not_reap_fresh_heartbeat_with_live_session() -> None:
    """The common case: a fresh heartbeat AND a live session is NOT reaped (no spurious reap).

    Both gate conditions hold (fresh AND alive), so the reaper skips the ticket — no teardown, no
    move, no relaunch. ``is_alive`` defaults to ``True`` in the fixture (a live session).
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=1000.0)
    m.sessions.is_alive.return_value = True  # the session is live
    fresh_alive = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=900.0,  # fresh
    )
    m.store.list_running.return_value = (fresh_alive,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    m.sessions.launch.assert_not_called()
    assert result.reaped == 0
    assert result.relaunched == 0


def test_reaper_throwing_is_alive_leaves_heartbeat_path_intact() -> None:
    """A throwing ``is_alive`` is FAIL-CLOSED: a fresh-heartbeat ticket is NOT wrongly reaped and
    the sweep does not crash (#26 fail-closed on the probe).

    The probe raises, so the dead-session signal is unavailable; the gate falls back to the
    heartbeat-only decision (skip if fresh). A fresh ticket with a throwing probe stays running.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=1000.0)
    m.sessions.is_alive.side_effect = RuntimeError("tmux server unreachable")
    fresh = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=900.0,  # fresh — the heartbeat-TTL path must still skip it
    )
    m.store.list_running.return_value = (fresh,)
    state = PersistedState(last_probe="probe-1")

    # The sweep must not crash on the throwing probe.
    result, _ = tick(m.deps, _config(), state)

    # Fail-closed: the fresh ticket is NOT reaped despite the probe failure.
    m.board_writer.move_card.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.sessions.launch.assert_not_called()
    assert result.reaped == 0
    assert result.relaunched == 0


def test_reaper_stale_heartbeat_throwing_is_alive_parks_waiting_never_kills() -> None:
    """A STALE ticket whose ``is_alive`` probe THROWS is treated as alive (fail-OPEN) → WAITING.

    Under Approach A the reaper never kills a session it cannot prove is dead. ``_session_alive`` is
    fail-OPEN (a throwing probe reports "alive"), so a stale ticket with an unreachable tmux server is
    parked WAITING and signalled — NOT killed/reaped. This supersedes the pre-Approach-A #26 behavior
    (which reaped on the heartbeat trigger when the probe failed): an uncertain liveness state must
    never destroy a possibly-live session.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.side_effect = RuntimeError("tmux server unreachable")
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # ancient → past the TTL, but the probe cannot confirm the session is dead
        stage="InProgress",
        retries=1,
    )
    m.store.list_running.return_value = (stale,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # Fail-OPEN → treated alive → parked WAITING, never killed/reaped/parked-in-Blocked.
    m.sessions.kill.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    saved = [c.args[0] for c in m.store.save.call_args_list]
    assert any(s.status is TicketStatus.WAITING for s in saved)
    assert result.reaped == 0
    assert result.relaunched == 0


# ---------------------------------------------------------------------------
# Phase-27 §B — agent "waiting-for-input" state. A STALE-heartbeat agent whose tmux session is STILL
# ALIVE and whose pane shows a PENDING human prompt is NOT hung: mark it WAITING (signal the user),
# never reap/relaunch/bump-retries. Resume on a heartbeat refresh; reap on a dead session; reap a
# non-waiting (idle/hung) or fail-closed-broken pane.
# ---------------------------------------------------------------------------


def test_reaper_marks_waiting_on_stale_alive_waiting_pane_no_reap() -> None:
    """A stale + alive agent at an interactive prompt is marked WAITING — NOT reaped/relaunched.

    The session is alive and the captured pane shows a pending human prompt, so the reaper persists
    ``status=WAITING`` (heartbeat + retries UNTOUCHED), signals via the ⏳ sticky, and does NOT kill,
    tear down, relaunch, or park-in-Blocked. ``reaped == relaunched == 0``.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = True  # the session is ALIVE
    # The pane shows a pending choice/confirmation — the agent is waiting for the human.
    m.sessions.capture.return_value = "❯ 1. Yes\n  2. No\nEnter to select, Esc to cancel"
    stale_waiting = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # stale → past the TTL
        stage="InProgress",
        profile="dev",
        retries=0,
    )
    m.store.list_running.return_value = (stale_waiting,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # NOT reaped/relaunched: no kill, no teardown, no relaunch, no park-in-Blocked.
    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    m.sessions.launch.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    # WAITING persisted, heartbeat + retries UNTOUCHED (the agent is alive, legitimately silent).
    saved = [c.args[0] for c in m.store.save.call_args_list]
    waiting_save = next(s for s in saved if s.status is TicketStatus.WAITING)
    assert waiting_save.heartbeat == 0.0  # NOT refreshed
    assert waiting_save.retries == 0  # NOT bumped
    # The user is signalled on the issue (the ⏳ waiting sticky upsert posts a comment).
    assert m.board_writer.list_issue_comments.called
    assert result.reaped == 0
    assert result.relaunched == 0


def test_reaper_marks_waiting_on_stale_alive_idle_pane_never_kills() -> None:
    """Approach A: a stale + ALIVE agent at a BARE idle prompt is parked WAITING — NEVER killed.

    Even when the captured pane shows only the idle ``❯`` cursor (no recognised waiting marker), an
    ALIVE session is never killed/relaunched/parked: the reaper cannot tell "hung" from "blocked on a
    free-text human prompt", and killing a live session would destroy interactive/unpushed work. It
    is parked WAITING + the operator signalled (the kill+relaunch path is DEAD-session-only). This
    supersedes the pre-Approach-A behavior that reaped a non-waiting-marker alive pane.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = True  # alive...
    m.sessions.capture.return_value = "❯ "  # ...a BARE idle prompt — no recognised waiting marker
    stale_idle = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # stale
        stage="InProgress",
        retries=1,  # would have been >= RETRY_LIMIT → BLOCK under the old behavior
    )
    m.store.list_running.return_value = (stale_idle,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # NEVER killed/relaunched/torn-down/parked — the live session is preserved.
    m.sessions.kill.assert_not_called()
    m.sessions.launch.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    # Parked WAITING instead (heartbeat + retries UNTOUCHED).
    saved = [c.args[0] for c in m.store.save.call_args_list]
    waiting_save = next(s for s in saved if s.status is TicketStatus.WAITING)
    assert waiting_save.heartbeat == 0.0
    assert waiting_save.retries == 1
    assert result.reaped == 0
    assert result.relaunched == 0


def test_reaper_never_kills_live_interactive_brainstorm_with_free_text_prompt() -> None:
    """Regression (helm #5): a long interactive brainstorm at a FREE-TEXT prompt is never killed.

    The brainstorm stage asks OPEN questions one at a time; while it waits for the operator the agent
    makes no tool calls (its heartbeat goes stale) and sits at a bare ``❯`` prompt with the question
    in scrollback — which shows NONE of the :data:`WAITING_FOR_INPUT_MARKERS` (no picker / ``(y/n)``
    / "do you want"). Before this fix the reaper read that stale+alive session as "hung" and
    killed+relaunched it, destroying the operator's in-progress brainstorm (and the relaunch reset the
    retry budget, so it repeated every TTL forever). Now an ALIVE session is ALWAYS parked WAITING +
    signalled — never killed, relaunched, torn down, or moved.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = True  # the operator's brainstorm session is ALIVE
    # A free-text brainstorm prompt: the question is in scrollback, the agent waits at a bare ❯.
    m.sessions.capture.return_value = (
        "What is the primary goal of this configuration interface?\n\n❯ "
    )
    stale_brainstorm = TicketState(
        issue_number=5,
        item_id="PVTI_5",
        session_id="ticket-5",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # stale → past the reap TTL (a long interactive brainstorm)
        stage="Brainstorming",
        profile="docs",
        retries=0,  # under RETRY_LIMIT → the OLD code would have relaunched (killing the session)
    )
    m.store.list_running.return_value = (stale_brainstorm,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The live session is preserved — no kill, no relaunch, no teardown, no Blocked move.
    m.sessions.kill.assert_not_called()
    m.sessions.launch.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.store.purge_ticket.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    # Parked WAITING (heartbeat + retries untouched) and the operator is signalled on the issue.
    saved = [c.args[0] for c in m.store.save.call_args_list]
    waiting_save = next(s for s in saved if s.status is TicketStatus.WAITING)
    assert waiting_save.issue_number == 5
    assert waiting_save.heartbeat == 0.0
    assert waiting_save.retries == 0
    assert m.board_writer.list_issue_comments.called  # the ⏳ waiting sticky upsert
    assert result.reaped == 0
    assert result.relaunched == 0


def test_reaper_early_waiting_detection_before_reap_ttl() -> None:
    """31.2: a RUNNING agent SILENT past the waiting-probe TTL but FRESH vs the reap TTL → WAITING.

    A blocked-on-human agent stops touching its heartbeat the instant it hits the prompt. Before
    31.2 it sat unsignalled until the heartbeat crossed the full 1800 s reap TTL; now, once silence
    exceeds the short waiting-probe TTL (180 s) and the pane shows a pending prompt, it is flipped
    to WAITING early — signalled within minutes, NOT reaped/relaunched/parked.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = True  # alive
    # The pane shows a pending confirmation at the bottom — the agent is blocked on the human.
    m.sessions.capture.return_value = "Do you want to proceed? (y/n)"
    early_waiting = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        # Silent for 500 s: PAST the 180 s waiting-probe TTL but well under the 1800 s reap TTL
        # (still "fresh"), so the early-probe path fires without the stale-reap path running.
        heartbeat=9_500.0,
        stage="InProgress",
        profile="dev",
        retries=0,
    )
    m.store.list_running.return_value = (early_waiting,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # Flipped to WAITING early — never reaped/relaunched/killed/parked.
    saved = [c.args[0] for c in m.store.save.call_args_list]
    waiting_save = next(s for s in saved if s.status is TicketStatus.WAITING)
    assert waiting_save.issue_number == 7
    assert (
        waiting_save.heartbeat == 9_500.0
    )  # heartbeat UNTOUCHED (the agent is legitimately silent)
    m.sessions.kill.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    m.sessions.launch.assert_not_called()
    assert result.reaped == 0
    assert result.relaunched == 0


def test_reaper_no_early_probe_when_heartbeat_recent() -> None:
    """31.2: a RUNNING agent silent UNDER the waiting-probe TTL is NOT probed (no premature WAITING).

    A briefly-silent healthy agent (silence < 180 s) is left alone — the pane is never captured, so
    a normal working agent is never misread as waiting.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = True
    recent = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=9_950.0,  # silent only 50 s — under the 180 s waiting-probe TTL
        stage="InProgress",
        profile="dev",
    )
    m.store.list_running.return_value = (recent,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # Not probed, not flipped: the pane is never captured for this fresh, recently-active agent.
    m.sessions.capture.assert_not_called()
    saved = [c.args[0] for c in m.store.save.call_args_list]
    assert not any(s.status is TicketStatus.WAITING for s in saved)
    assert result.reaped == 0


def test_reaper_restores_running_when_waiting_ticket_heartbeat_refreshes() -> None:
    """A WAITING ticket whose heartbeat is now FRESH (human answered → agent resumed) → RUNNING.

    A fresh heartbeat + alive session means the agent is working again — restore it to RUNNING and
    leave it be (no reap, no relaunch).
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=1000.0)
    m.sessions.is_alive.return_value = True
    resumed = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.WAITING,  # was parked WAITING on a prior tick
        heartbeat=900.0,  # now FRESH (the human answered → the agent resumed tool calls)
        stage="InProgress",
    )
    m.store.list_running.return_value = (resumed,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # Restored to RUNNING; not reaped/relaunched.
    saved = [c.args[0] for c in m.store.save.call_args_list]
    restored = next(s for s in saved if s.status is TicketStatus.RUNNING)
    assert restored.issue_number == 7
    m.sessions.kill.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    m.sessions.launch.assert_not_called()
    assert result.reaped == 0
    assert result.relaunched == 0
    # 31.2: the restore re-flips the stage sticky to the 🟡 running header (it was ⏳ while WAITING),
    # so the issue no longer reads "waiting for your input" once the agent has resumed.
    assert m.board_writer.list_issue_comments.called  # the sticky upsert located the comment


def test_reaper_reaps_waiting_ticket_when_session_dies() -> None:
    """A WAITING ticket whose tmux session DIED is reaped (the human never answered; the agent gone).

    With the session dead the WAITING state is moot — the reaper reaps it via the normal path.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = False  # the WAITING agent's session DIED
    dead_waiting = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.WAITING,
        heartbeat=0.0,  # stale (and session dead)
        stage="InProgress",
        retries=1,  # >= RETRY_LIMIT → straight to BLOCK
    )
    m.store.list_running.return_value = (dead_waiting,)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The dead-session WAITING ticket is reaped (capture is never consulted — the session is gone).
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    m.sessions.capture.assert_not_called()
    assert result.reaped == 1


def test_reaper_alive_stale_parks_waiting_even_if_pane_would_raise() -> None:
    """An alive + stale agent is parked WAITING WITHOUT consulting the pane (Approach A).

    The stale-but-alive path no longer probes the pane to decide reap-vs-wait — an alive session is
    ALWAYS parked WAITING (never killed), so a broken ``capture`` is irrelevant: the pane is not even
    captured. This proves the live session is preserved regardless of pane state, and the sweep does
    not crash.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = True  # alive...
    m.sessions.capture.side_effect = RuntimeError(
        "capture-pane failed"
    )  # ...and even a broken pane is irrelevant on the stale-alive path
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # stale
        stage="InProgress",
        retries=1,
    )
    m.store.list_running.return_value = (stale,)
    state = PersistedState(last_probe="probe-1")

    # The sweep must not crash; the pane is never even captured on the stale-alive path.
    result, _ = tick(m.deps, _config(), state)

    m.sessions.capture.assert_not_called()
    m.sessions.kill.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    saved = [c.args[0] for c in m.store.save.call_args_list]
    assert any(s.status is TicketStatus.WAITING for s in saved)
    assert result.reaped == 0


# ---------------------------------------------------------------------------
# Anti-loop: the daemon records its own moves and threads the state across ticks
# (defense-in-depth, DESIGN §6 / §3.3 — secondary to the diff-baseline backstop)
# ---------------------------------------------------------------------------


def _stale_running(item_id: str = "PVTI_7", issue_number: int = 7) -> TicketState:
    """Build a running :class:`TicketState` whose heartbeat is far past the TTL."""
    return TicketState(
        issue_number=issue_number,
        item_id=item_id,
        session_id=f"ticket-{issue_number}",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,  # ancient: always reaped against any realistic ``now``
    )


def test_reap_records_its_own_move_into_antiloop_state() -> None:
    """The daemon records its own reap move-to-Blocked into the returned anti-loop state.

    The reap step issues the daemon's *own* ``move_card`` into the Blocked column. That self-move
    must be fed to :func:`~kanbanmate.core.antiloop.record_move` so the guard can recognise it
    later — proving the state the tick returns is no longer a fresh empty one.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    m.store.list_running.return_value = (_stale_running(),)
    state = PersistedState(last_probe="probe-1")  # probe unchanged → only the reap step runs

    result, next_state = tick(m.deps, _config(), state)

    assert result.reaped == 1
    # The (item_id, Blocked) marker is present, and a repeated move to the same target at the same
    # time is now dedup-guarded by is_blocked — i.e. the accumulated state is live, not empty.
    assert ("PVTI_7", "Blocked") in next_state.antiloop.recent_targets
    assert is_blocked(next_state.antiloop, "PVTI_7", "Blocked", now=10_000.0) is True


def test_reaper_teardown_preserves_in_memory_history_and_adds_park_move() -> None:
    """The reaper teardown PRESERVES the in-memory rate-limit history (#22 plan-drift).

    Unlike the Cancel ``TeardownAction`` (abandonment → ``forget``), the reaper parks the card in
    Blocked with ``keep_budgets=True`` (13.8): the ticket MAY continue, so its in-memory rate-limit
    accumulator MUST survive the teardown for the runaway-loop backstop (DESIGN §6). Prior history
    is kept AND the fresh park move is appended (a genuine daemon AUTO move feeds the counter). This
    matches the PoC, whose reaper ``_move_to_blocked`` used slot-only ``release_slot`` and never
    zeroed ``moves/`` — only the Cancel/reset ``purge_ticket`` did. See the NOTE in app/reaper.py.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    m.store.list_running.return_value = (_stale_running(),)
    # Seed a prior reap move for the item (e.g. an earlier tick parked it once already).
    seeded = record_move(AntiLoopState(), "PVTI_7", "Blocked", now=1.0)
    state = PersistedState(last_probe="probe-1", antiloop=seeded)

    result, next_state = tick(m.deps, _config(), state)

    assert result.reaped == 1
    # The prior history SURVIVES the reaper teardown and the fresh park move is APPENDED — the
    # in-memory accumulator grows so the runaway-loop backstop can observe repeated reap moves.
    assert next_state.antiloop.move_times.get("PVTI_7") == (1.0, 10_000.0)
    assert next_state.antiloop.recent_targets[("PVTI_7", "Blocked")] == 10_000.0


def test_failed_reap_move_is_not_recorded() -> None:
    """A reap whose move-to-Blocked fails records nothing (only landed moves are recorded).

    The partial-failure path in :func:`~kanbanmate.app.tick._reap_stale_agents` is exercised:
    when a reap sub-action (``move_card``) raises, the agent is NOT counted as reaped and the
    error is recorded (``errors >= 1``). This is the branch where ``ok_block and ok_teardown``
    are True but ``ok_move`` is False, so the ``else: errors += 1`` runs.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    m.store.list_running.return_value = (_stale_running(),)
    # The board move blows up → ok_move is False → the move must not be recorded.
    m.board_writer.move_card.side_effect = RuntimeError("github move failed")
    state = PersistedState(last_probe="probe-1")

    result, next_state = tick(m.deps, _config(), state)

    assert ("PVTI_7", "Blocked") not in next_state.antiloop.recent_targets
    # The agent is not counted as reaped because one sub-action failed.
    assert result.reaped == 0
    # The partial failure is counted as an error.
    assert result.errors >= 1


def test_antiloop_state_threads_across_two_ticks() -> None:
    """The anti-loop state accumulates across ticks (two reap moves both recorded).

    The same self-move at two different times is recorded each tick; the per-ticket rate-limit
    timestamps grow, proving the state threads tick-to-tick rather than resetting each cycle.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    m.store.list_running.return_value = (_stale_running(),)

    # Tick 1 at t=10_000 records the move once.
    _, state1 = tick(m.deps, _config(), PersistedState(last_probe="probe-1"))
    assert state1.antiloop.move_times["PVTI_7"] == (10_000.0,)

    # Tick 2 at t=10_100 (still inside the rate window) threads state1 in and appends a second
    # timestamp — the accumulator carried over rather than starting fresh.
    m.clock.now.return_value = 10_100.0
    _, state2 = tick(m.deps, _config(), state1)
    assert state2.antiloop.move_times["PVTI_7"] == (10_000.0, 10_100.0)
    # And the most-recent target marker advanced to the second move's time.
    assert state2.antiloop.recent_targets[("PVTI_7", "Blocked")] == 10_100.0


def test_repeated_self_move_to_same_target_is_dedup_guarded() -> None:
    """A repeated daemon move to the same target within the TTL is blocked by the live guard.

    Recording a reap move into Blocked makes a *second* move into Blocked for the same ticket
    "recent": :func:`is_blocked` evaluated on the threaded state returns ``True`` within the TTL and
    ``False`` once it has elapsed — proving ``antiloop_state`` is now live, not always-empty.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    m.store.list_running.return_value = (_stale_running(),)

    _, state = tick(m.deps, _config(), PersistedState(last_probe="probe-1"))

    # Within the default recent TTL (600s) the same (ticket, target) move is deduplicated.
    assert is_blocked(state.antiloop, "PVTI_7", "Blocked", now=10_500.0) is True
    # Once the TTL has elapsed the dedup guard releases (and no rate-limit trip from one move).
    assert is_blocked(state.antiloop, "PVTI_7", "Blocked", now=20_000.0) is False


# ---------------------------------------------------------------------------
# Stage-sticky ⛔ flip on stale-agent reap (DESIGN §8.1.c)
# ---------------------------------------------------------------------------


def _stale_with_stage(
    stage: str = "InProgress",
    item_id: str = "PVTI_7",
    issue_number: int = 7,
    retries: int = 1,
) -> TicketState:
    """Build a running TicketState with stage + header metadata set (post-8.1.d widened shape).

    The heartbeat is ancient so the reaper always picks it up. ``retries`` defaults to ``1``
    (``>= RETRY_LIMIT``) so the reaper parks it STRAIGHT in Blocked — these stage-sticky tests
    exercise the ⛔-flip BLOCK path, not the 15.2 relaunch-once retry (which fires only at
    ``retries < RETRY_LIMIT``). A new relaunch test overrides ``retries=0`` explicitly.
    """
    return TicketState(
        issue_number=issue_number,
        item_id=item_id,
        session_id=f"ticket-{issue_number}",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage=stage,
        profile="docs",
        mode="acceptEdits",
        started=8000.0,
        worktree="/tmp/worktrees/ticket-7",
        retries=retries,
    )


def test_reaper_flips_stage_sticky_to_blocked() -> None:
    """When reaping a stale agent, the reaper flips the existing stage sticky to ⛔ "blocked".

    The header is built from the stale TicketState's OWN metadata (DESIGN §8.1.c), so the
    ⛔ sticky carries the original launch context (profile / mode / started / worktree), not
    the reaper's. The existing kill/teardown/move/release steps still execute as before.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    m.store.list_running.return_value = (_stale_with_stage(),)
    # Simulate an existing running sticky that the LaunchAction created.
    existing = MagicMock()
    existing.comment_id = 456
    existing.body = (
        "<!-- kanban:step=InProgress -->\n"
        "### 🟡 InProgress — in progress\n"
        "- session : `ticket-7` · profile `docs` · mode `acceptEdits`\n"
        "- started : 1970-01-01 02:13 · worktree `ticket-7`\n"
        "- logs : `kanban logs 7`\n"
        "\n"
        "**Progress**\n"
        "- 02:14 — some progress line\n"
    )
    m.board_writer.list_issue_comments.return_value = [existing]
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The purge / move steps still run, but the reap is NON-DESTRUCTIVE (defect 5): no worktree
    # removal (the ``reap`` flavour skips it). Under Approach A the reaper does not kill a dead
    # session (nothing to kill; teardown only kills a live session).
    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    # Reaper teardown preserves the per-issue budgets → keep_budgets=True (13.8).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    assert result.reaped == 1

    # The stage sticky is PATCHed ONCE — only the reaper's ⛔ ``blocked`` flip (DESIGN §8.1.c).
    # The ``reap`` flavour SKIPS the TeardownAction's ❌ ``cancelled`` finalize (defect 5), so the
    # ticket is never mis-stamped "cancelled" before the reaper stamps "blocked".
    assert m.board_writer.update_comment.call_count == 1
    # That single update is the ⛔ blocked flip — the reaper's final word.
    updated_body: str = m.board_writer.update_comment.call_args.args[1]
    # The ⛔ badge and "blocked" label replace the 🟡 running header.
    assert "⛔" in updated_body
    assert "blocked" in updated_body
    # The progress zone is preserved across the header swap.
    assert "some progress line" in updated_body
    # A finished-timestamp line is appended (terminal status).
    assert "blocked :" in updated_body
    # The ⛔ header carries the original metadata (from the stale state).
    assert "docs" in updated_body
    assert "ticket-7" in updated_body


def test_reaper_skips_flip_when_stage_empty() -> None:
    """When the stale TicketState has no stage (stage==""), the ⛔ flip is skipped.

    Old-format state files (pre-8.1.d) have stage="" — there is nothing to finalize.
    The existing kill/teardown/move/release still execute normally.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    # stage="" is the default; this mimics an old-format state file.
    m.store.list_running.return_value = (_stale_running(),)
    state = PersistedState(last_probe="probe-1")

    result, _ = tick(m.deps, _config(), state)

    # The critical reap steps still completed. Under Approach A the reaper does not kill a dead
    # session (nothing to kill; teardown only kills a live session).
    m.sessions.kill.assert_not_called()
    # Reaper teardown preserves the per-issue budgets → keep_budgets=True (13.8).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    assert result.reaped == 1
    # No stage-comment I/O was attempted (list_issue_comments never called for this ticket).
    # The update_comment path was never hit.
    m.board_writer.update_comment.assert_not_called()


def test_reaper_sticky_flip_fail_soft() -> None:
    """When the stage-comment upsert raises during the ⛔ flip, the reap still completes.

    A GitHub error during the flip is logged and swallowed (DESIGN §8.1 fail-soft) — it must
    never prevent the kill/teardown/move/release from completing, and must not affect the
    reap tally (the agent is still counted as reaped).
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = (
        False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
    )
    m.store.list_running.return_value = (_stale_with_stage(),)
    # Network down during the upsert — the list fails.
    m.board_writer.list_issue_comments.side_effect = RuntimeError("network down")
    state = PersistedState(last_probe="probe-1")

    # Must NOT raise.
    result, _ = tick(m.deps, _config(), state)

    # The critical reap steps still completed despite the flip failure. The reap is
    # NON-DESTRUCTIVE (defect 5): no worktree removal. Under Approach A the reaper does not kill a
    # dead session (nothing to kill; teardown only kills a live session).
    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    # Reaper teardown preserves the per-issue budgets → keep_budgets=True (13.8).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    # The agent is still counted as reaped — the flip failure doesn't affect the tally.
    assert result.reaped == 1


# ---------------------------------------------------------------------------
# ✅-on-advance: the daemon finalizes the LEFT stage on a forward move (DESIGN §8.1.e)
# ---------------------------------------------------------------------------

# A two-launch-stage board so a Design→InProgress LAUNCH has a stickied LEFT stage to finalize.
# Phase 20 (DESIGN §8.0.6): the launch profile comes from the TRANSITION (``_TWO_AGENT_WHITELIST``
# carries ``profile: dev`` on each launch edge); ``columns.yml`` is a bare set carrying no
# launch config — Design and InProgress are plain INERT columns, the launch lives on the transition.
_TWO_AGENT_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: Design
    name: Design
  - key: InProgress
    name: In Progress
  - key: Cancel
    name: Cancel
    action: teardown
  - key: Done
    name: Done
"""


def _left_state(stage: str = "Design") -> TicketState:
    """Build a LEFT-stage :class:`TicketState` carrying its OWN launch metadata.

    The metadata (profile / mode / started / worktree) is what the ✅ finalize must source from
    the PRE-READ LEFT state so the finished sticky keeps the LEFT stage's context (DESIGN §8.1.e
    header-provenance), NOT the new stage's.
    """
    return TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage=stage,
        profile="docs-left",
        mode="acceptEdits",
        started=8000.0,
        worktree="/tmp/worktrees/ticket-7-left",
    )


def _existing_sticky(stage: str) -> MagicMock:
    """Return a fake running 🟡 sticky comment for ``stage`` (the LEFT stage's open sticky)."""
    existing = MagicMock()
    existing.comment_id = 123
    existing.body = (
        f"<!-- kanban:step={stage} -->\n"
        f"### 🟡 {stage} — in progress\n"
        "- session : `ticket-7` · profile `docs-left` · mode `acceptEdits`\n"
        "- started : 1970-01-01 02:13 · worktree `ticket-7-left`\n"
        "- logs : `kanban logs 7`\n"
        "\n"
        "**Progress**\n"
        "- 02:14 — left stage progress line\n"
    )
    return existing


def test_done_arrival_with_running_agent_finalizes_left_sticky_done() -> None:
    """A card skipped to Done WHILE its agent is RUNNING tears down + finalizes the sticky ✅ done.

    Phase 28.1: this used to be a NOOP-forward that merely finalized the LEFT sticky (the #91 e2e
    bug — the agent was left running). Now the live-agent Done arrival is a FULL teardown whose
    ✅-done sticky finalize STILL flips the open 🟡 sticky to ✅ "done" with a finished timestamp,
    AND additionally kills the session + removes the worktree + purges the state.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    # A live (RUNNING) agent in InProgress, with an open running sticky.
    m.store.load.return_value = _left_state(stage="InProgress")
    m.workspace.worktree_exists.return_value = True  # #9: reclaim is keyed on the worktree
    m.board_writer.list_issue_comments.return_value = [_existing_sticky("InProgress")]
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, next_state = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # The agent was torn down (the headline fix), and the action counted.
    m.sessions.launch.assert_not_called()
    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    assert result.actions_executed == 1
    # The open sticky was PATCHed to ✅ done (the teardown's done-flavoured finalize).
    m.board_writer.update_comment.assert_called_once()
    updated: str = m.board_writer.update_comment.call_args.args[1]
    assert "✅" in updated
    assert "done" in updated
    assert "done :" in updated  # finished-timestamp line (terminal status)
    # The progress zone is preserved across the header swap.
    assert "left stage progress line" in updated
    # The card STAYS in Done; the baseline advanced to Done for the next diff.
    assert next_state.columns_by_item["PVTI_7"] == "Done"


def test_done_arrival_running_agent_unstickied_tears_down_without_finalize() -> None:
    """A live-agent Done arrival with NO open sticky still tears down (no sticky to finalize).

    The teardown's ✅-done finalize is a silent no-op when there is no open sticky, but the session
    kill + worktree removal + purge + the "moved to Done" recap still run (phase 28.1).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    # A live agent (status RUNNING) but NO open stage sticky on the issue.
    m.store.load.return_value = _left_state(stage="InProgress")
    m.workspace.worktree_exists.return_value = True  # #9: reclaim is keyed on the worktree
    m.board_writer.list_issue_comments.return_value = []  # no sticky to finalize
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # No sticky → no patch/create, but the teardown still kills + purges + posts the done recap.
    m.board_writer.update_comment.assert_not_called()
    m.sessions.kill.assert_called_once_with("ticket-7")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    _issue, body = m.board_writer.comment.call_args.args
    assert "moved to Done" in body
    assert result.actions_executed == 1


def test_launch_finalizes_left_stage_with_left_metadata_and_opens_new() -> None:
    """A LAUNCH (Design→InProgress) finalizes the LEFT (Design) ✅ AND opens the new 🟡.

    Header provenance (DESIGN §8.1.e Fix 4/6): the ✅ sticky carries the LEFT (Design) stage's
    OWN metadata (profile ``docs-left``, the Design worktree) — sourced from the PRE-READ LEFT
    ``TicketState`` — NOT the new InProgress stage's metadata.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    # The PRE-READ LEFT state is the Design stage's state (its own metadata).
    m.store.load.return_value = _left_state(stage="Design")
    # The AGENT advanced its own card (Design→InProgress) — it ran ``kanban-move``, dropping the
    # advance breadcrumb. That exempts this forward advance from the anti-double-session guard
    # (defect 7) even though the prior-stage state lingers LIVE and the session is still alive.
    m.store.recent_agent_advance.return_value = True
    # The issue already carries the Design stage's open 🟡 sticky.
    m.board_writer.list_issue_comments.return_value = [_existing_sticky("Design")]
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, _ = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # The new agent launched (Design→InProgress is an agent destination).
    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1
    # The tick PRE-READ the LEFT state before the LaunchAction overwrote the slot.
    m.store.load.assert_any_call(7)
    # The LEFT (Design) sticky was finalized ✅ done, carrying the LEFT stage's OWN metadata.
    m.board_writer.update_comment.assert_called_once()
    updated: str = m.board_writer.update_comment.call_args.args[1]
    assert "<!-- kanban:step=Design -->" in updated  # the LEFT stage's sticky, not the new one
    assert "✅" in updated and "done" in updated
    assert "docs-left" in updated  # LEFT (Design) profile, NOT the new stage's
    assert "ticket-7-left" in updated  # LEFT (Design) worktree name
    # The new InProgress 🟡 sticky was opened by the LaunchAction (created via comment()).
    assert m.board_writer.comment.called
    new_body = m.board_writer.comment.call_args.args[1]
    assert "<!-- kanban:step=InProgress -->" in new_body
    assert "🟡" in new_body


def test_launch_finalize_is_fail_soft_when_writer_raises() -> None:
    """A writer exception during the ✅ finalize is swallowed — the launch still counts.

    The finalize is internally fail-soft (DESIGN §8.1): a GitHub error during the LEFT-stage flip
    must never break dispatch nor turn the launch into an error.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    m.store.load.return_value = _left_state(stage="Design")
    # Agent self-advance (breadcrumb present) → exempt from the anti-double-session guard (defect 7).
    m.store.recent_agent_advance.return_value = True
    # The finalize's listing blows up — must be swallowed (fail-soft).
    m.board_writer.list_issue_comments.side_effect = RuntimeError("network down")
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    # Must NOT raise.
    result, _ = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # The launch still ran and is counted; the finalize failure did not surface as an error.
    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1
    assert result.errors == 0


def test_finalize_left_stage_flips_sticky_done_when_state_already_purged() -> None:
    """The ✅ finalize still flips the LEFT sticky when session-end already purged state (defect 8).

    The COMMON ordering: the agent advanced its own card then exited, so ``kanban-session-end``
    PURGED the persisted state before this 10s poll → ``left_state is None``. The header swap needs
    NO persisted metadata (it reads the existing sticky body), so the ✅ flip must still happen —
    otherwise the sticky stayed 🟡 forever and the ⚠️→✅ flip was always lost.
    """
    from kanbanmate.app.tick import _finalize_left_stage

    m = _mocks(_FakeBoardReader("probe-1", _snapshot()), now=9000.0)
    # The LEFT (Design) stage still carries its open 🟡 sticky on the issue…
    m.board_writer.list_issue_comments.return_value = [_existing_sticky("Design")]
    transition = Transition(
        ticket=Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress"),
        from_column="Design",
        to_column="InProgress",
    )

    # …but the persisted LEFT state was ALREADY PURGED (left_state=None).
    _finalize_left_stage(m.deps, transition, None, now=9000.0)

    # The sticky is still PATCHed to ✅ done (header swap preserves the progress zone).
    m.board_writer.update_comment.assert_called_once()
    updated: str = m.board_writer.update_comment.call_args.args[1]
    assert "<!-- kanban:step=Design -->" in updated  # the LEFT stage's sticky
    assert "✅" in updated and "done" in updated
    assert "left stage progress line" in updated  # the progress zone is preserved across the swap


def test_watchdog_executor_does_not_block_on_hung_worker() -> None:
    """#6: the per-tick executor's shutdown is NON-BLOCKING — a wedged worker never freezes exit.

    A plain ``with ThreadPoolExecutor(...)`` would block at exit until the hung worker finishes; the
    ``_watchdog_executor`` context manager must return promptly via shutdown(wait=False).
    """
    import threading
    import time as _time

    from kanbanmate.app.tick import _watchdog_executor

    release = threading.Event()

    def _hang() -> None:
        # Block until released — simulates a wedged adapter call the watchdog abandoned.
        release.wait(timeout=5.0)

    start = _time.monotonic()
    with _watchdog_executor() as executor:
        executor.submit(_hang)
        # Give the worker a moment to actually start running.
        _time.sleep(0.05)
    # The context exit must NOT have waited for _hang to finish (it is still blocked).
    elapsed = _time.monotonic() - start
    assert elapsed < 2.0, f"watchdog executor blocked on the hung worker ({elapsed:.2f}s)"
    # Clean up the still-running daemon worker.
    release.set()


def test_watchdog_executor_logs_abandoned_worker(caplog: pytest.LogCaptureFixture) -> None:
    """phase-34: a GENUINE watchdog timeout this tick is logged as an abandoned hung action.

    The authoritative leak signal is a recorded ``FutureTimeoutError`` (the worker is orphaned
    mid-call), not mere worker aliveness. Drive a wrapper to time out, then assert the exit warning
    fires and NAMES the abandoned action.
    """
    import logging
    import threading

    from kanbanmate.app.tick import _run_callable_with_watchdog, _watchdog_executor

    release = threading.Event()

    with caplog.at_level(logging.WARNING):
        with _watchdog_executor() as executor:
            # A callable that outlives its tiny budget → the wrapper records a genuine hang.
            _run_callable_with_watchdog(
                executor,
                lambda: release.wait(timeout=5.0),
                timeout=0.1,
                label="ensure_worktree #42",
            )
    release.set()

    leak_lines = [
        r.getMessage() for r in caplog.records if "abandoned hung action" in r.getMessage()
    ]
    assert leak_lines, "a genuine watchdog timeout must be logged as an abandoned hung action"
    assert any("ensure_worktree #42" in m for m in leak_lines), (
        "the leak warning must name the abandoned action"
    )


def test_watchdog_executor_no_leak_warning_on_completed_action(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """phase-34 (false-positive fix): an action that completes within its budget logs NO leak.

    Regression guard for the observed false positive — every successful action used to trip
    "worker thread(s) still running" because an idle ``ThreadPoolExecutor`` worker stays alive
    between tasks. With the timeout-registry signal, a completed action must leave the exit silent.
    """
    import logging

    from kanbanmate.app.tick import _run_callable_with_watchdog, _watchdog_executor

    with caplog.at_level(logging.WARNING):
        with _watchdog_executor() as executor:
            ok = _run_callable_with_watchdog(executor, lambda: None, timeout=5.0, label="quick-op")

    assert ok is True
    assert not any(
        "abandoned hung action" in r.getMessage() or "still running" in r.getMessage()
        for r in caplog.records
    ), "a completed action must NOT produce a leaked-thread warning"


def test_run_callable_with_watchdog_times_out(caplog: pytest.LogCaptureFixture) -> None:
    """#6: ``_run_callable_with_watchdog`` returns False + logs when the callable exceeds the budget.

    This is the wrapper the launch-gate pre-create ``ensure_worktree`` now runs under, so a hung
    network ``git fetch`` is bounded instead of freezing the tick.
    """
    import logging
    import threading

    from kanbanmate.app.tick import _run_callable_with_watchdog, _watchdog_executor

    release = threading.Event()

    with caplog.at_level(logging.WARNING):
        with _watchdog_executor() as executor:
            ok = _run_callable_with_watchdog(
                executor,
                lambda: release.wait(timeout=5.0),
                timeout=0.1,  # tiny budget → the call "times out"
                label="ensure_worktree #7",
            )
    release.set()

    assert ok is False
    assert any("timed out" in r.getMessage() for r in caplog.records)


def test_run_callable_with_watchdog_success() -> None:
    """#6: a callable that completes within the budget returns True."""
    from kanbanmate.app.tick import _run_callable_with_watchdog, _watchdog_executor

    with _watchdog_executor() as executor:
        ok = _run_callable_with_watchdog(executor, lambda: None, timeout=5.0, label="quick-op")

    assert ok is True


def test_transition_iteration_isolation_advances_baseline_on_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#3: a transition whose processing RAISES counts an error, advances the baseline, and the
    tick continues — it does NOT replay the launch next tick.

    The per-iteration try/except is the isolation seam: a mid-loop raise (decide / build /
    ensure_worktree / store) must not lose the partially-advanced baseline and re-fire the move.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("simulated mid-transition failure")

    # Force the per-transition processor to raise; the tick must isolate it.
    monkeypatch.setattr("kanbanmate.app.tick.process_transition", _boom)

    result, new_state = tick(
        m.deps,
        TickConfig(columns=load_columns(_COLUMNS_YAML), transitions=_tick_whitelist()),
        state,
    )

    # The raise was caught: one error counted, the tick did NOT crash.
    assert result.errors == 1
    # The baseline advanced to the destination so the next diff does not re-fire (re-launch) it.
    assert new_state.columns_by_item.get("PVTI_7") == "InProgress"


def test_pre_launch_guard_skips_when_agent_already_live_at_same_stage() -> None:
    """#3: a re-fired LAUNCH for an issue already LIVE at the destination stage does NOT relaunch.

    The persisted state shows a RUNNING agent already AT ``InProgress`` (a spurious re-fire of the
    same move). The pre-launch guard must skip the dispatch so the idempotent launch does not kill
    + relaunch the live session — it just advances the baseline.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    # The agent is ALREADY live at the SAME destination stage (InProgress) — a re-fire.
    m.store.load.return_value = _running_state(7, status=TicketStatus.RUNNING)  # stage=InProgress
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, _ = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # No relaunch — the live session is preserved.
    m.sessions.launch.assert_not_called()
    assert result.actions_executed == 0


def test_pre_launch_guard_allows_forward_advance_with_lingering_prior_state() -> None:
    """#3: an AGENT forward advance launches even if the PRIOR stage's state lingers as RUNNING.

    The persisted state is the LEFT (Design) stage's RUNNING record; the card advanced to a NEW
    stage (InProgress). The guard's ``stage == to_column`` qualifier (and the agent-advance
    breadcrumb exemption, defect 7) must let the new-stage launch proceed — only a SAME-stage
    re-fire is blocked, and an AGENT self-advance (breadcrumb present) is never bounced.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    # The lingering state belongs to the PRIOR (Design) stage, not the new InProgress destination.
    m.store.load.return_value = _left_state(stage="Design")  # status RUNNING, stage Design
    # The AGENT advanced its own card (breadcrumb present) → exempt from the anti-double-session
    # guard even though the prior session may still be briefly alive (defect 7).
    m.store.recent_agent_advance.return_value = True
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, _ = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # The new stage launches despite the lingering prior-stage RUNNING state.
    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1


def test_anti_double_session_human_drag_of_live_agent_bounces_not_kills() -> None:
    """A HUMAN cross-stage drag of a card whose agent is LIVE bounces back, never launches (defect 7).

    The agent is LIVE at Design (RUNNING, session alive) and the human drags the card to InProgress
    WITHOUT the agent advancing (no advance breadcrumb). The guard must NOT dispatch a second launch
    (which would kill the live agent and discard its un-persisted work) — it bounces the card back
    to its origin (Design) and leaves the live session untouched.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    # The agent is LIVE at the PRIOR (Design) stage; the session is alive (default mock True).
    m.store.load.return_value = _left_state(stage="Design")
    m.sessions.is_alive.return_value = True
    # NO agent advance breadcrumb → this is a HUMAN drag, not an agent self-advance.
    m.store.recent_agent_advance.return_value = False
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, next_state = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # NO second launch (the live agent is NOT killed); the card is bounced back to Design.
    m.sessions.launch.assert_not_called()
    m.sessions.kill.assert_not_called()
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Design")
    # The bounce counts as an executed action; the baseline records the bounce target (no re-fire).
    assert result.actions_executed == 1
    assert next_state.columns_by_item["PVTI_7"] == "Design"


def test_teardown_does_not_finalize_left_stage() -> None:
    """A TEARDOWN (move into Cancel) is a reactive move, NOT a forward advance — no ✅ finalize."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Cancel")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    m.store.load.return_value = _left_state(stage="InProgress")
    m.board_writer.list_issue_comments.return_value = [_existing_sticky("InProgress")]
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(
        m.deps,
        TickConfig(
            columns=load_columns(_TWO_AGENT_COLUMNS_YAML), transitions=_two_agent_whitelist()
        ),
        state,
    )

    # Teardown ran.  The teardown's step 5 (8.2.c) flips open stickies to ❌ cancelled —
    # this is the Cancel teardown's sticky flip, NOT a ✅ done finalize (the tick's
    # _finalize_left_stage is skipped for reactive moves like Cancel).  Verify the one
    # update is ❌ cancelled, not ✅ done.
    m.workspace.remove_worktree.assert_called_once()
    m.board_writer.update_comment.assert_called_once()
    updated_body: str = m.board_writer.update_comment.call_args.args[1]
    assert "❌" in updated_body
    assert "cancelled" in updated_body
    assert "✅" not in updated_body  # emphatically NOT a done finalize
    assert result.actions_executed == 1


# ---------------------------------------------------------------------------
# ResetAction re-arm (sub-phase 8.2.d): a Cancel→Backlog purge re-arms
# the next agent move via the diff's columns_by_item baseline alone
# ---------------------------------------------------------------------------


def test_cancel_to_backlog_purge_re_arms_next_agent_move() -> None:
    """After ResetAction purges a cancelled ticket, the next Backlog→agent move launches fresh.

    Investigation outcome (sub-phase 8.2.d): NEW's poll-based ``diff(persisted, snapshot)``
    compares against the ``columns_by_item`` baseline (advanced after every tick), not against
    the ``TicketState`` store. After ``release_slot`` purges the runtime state, the baseline
    still records ``Backlog`` (set by the tick that executed the RESET), so a subsequent
    operator move into an agent column produces a fresh LAUNCH — no ``set_item_column`` call is
    needed. This is a genuine simplification the polling pivot bought over the PoC.

    The test runs TWO ticks end-to-end:
      1. Cancel → Backlog: ResetAction purges, NO agent launches (Backlog inert).
      2. Backlog → InProgress: the diff re-triggers → LaunchAction fires.
    """
    # ── Tick 1: Cancel → Backlog ──────────────────────────────────────────
    ticket_cancel = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Backlog")
    reader1 = _FakeBoardReader("probe-1", _snapshot(ticket_cancel))
    m1 = _mocks(reader1)
    state1 = PersistedState(columns_by_item={"PVTI_7": "Cancel"}, last_probe="probe-0")

    result1, next_state1 = tick(m1.deps, _config(), state1)

    # ResetAction ran: EXHAUSTIVE purge of runtime state (13.7 split), NO launch, NO worktree.
    m1.store.purge_ticket.assert_called_once_with(7)
    m1.sessions.launch.assert_not_called()
    m1.workspace.ensure_worktree.assert_not_called()
    m1.store.save.assert_not_called()
    assert result1.actions_executed == 1  # RESET is an executed action
    assert result1.snapshot_taken is True
    # The baseline records Backlog for the next diff.
    assert next_state1.columns_by_item["PVTI_7"] == "Backlog"

    # ── Tick 2: Backlog → InProgress (subsequent agent move) ──────────────
    ticket_agent = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader2 = _FakeBoardReader("probe-2", _snapshot(ticket_agent))
    m2 = _mocks(reader2)
    # Baseline carried from the first tick: the ticket sits at Backlog.
    state2 = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-1")

    result2, next_state2 = tick(m2.deps, _config(), state2)

    # RE-TRIGGER: Backlog→InProgress diff re-arms a fresh LaunchAction.
    m2.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    m2.sessions.launch.assert_called_once()
    m2.store.save.assert_called_once()
    assert result2.actions_executed == 1
    assert next_state2.columns_by_item["PVTI_7"] == "InProgress"


# ---------------------------------------------------------------------------
# Phase 12.8: the (from,to) transition whitelist threaded through the tick
# (filled launch · run_script dispatch · rollback bounce + diff baseline ·
# the phase-8 ✅ finalize stays forward-only · back-compat · reactive routing)
# ---------------------------------------------------------------------------

# A whitelist keyed to the _TWO_AGENT_COLUMNS_YAML board (Design + InProgress are AGENT columns,
# Backlog/Done inert, Cancel reactive). Authored in column KEYS, matched against the board's
# moves. NOTE (12.6 agent-class gate): a prompt transition only LAUNCHes when its DESTINATION is
# an AGENT column — so the prompt rows target InProgress (agent), never an inert column.
_WHITELIST_YAML = """
project: owner/repo
defaults:
  concurrency_cap: 3
  move_rate_limit_per_hour: 10
transitions:
  - from: Backlog
    to: InProgress
    prompt: "/implement:phase {{code}} — {{title}}"
    profile: dev
    permission_mode: auto
  - from: Design
    to: InProgress
    script: bin/check-pr-ready.sh
    on_fail: "move:Design"
    advance: stop
"""


def _two_agent_whitelist_config() -> TickConfig:
    """Build a :class:`TickConfig` from the two-agent board + the phase-12 whitelist."""
    return TickConfig(
        columns=load_columns(_TWO_AGENT_COLUMNS_YAML),
        transitions=load_transitions(_WHITELIST_YAML),
    )


def test_whitelisted_prompt_move_launches_filled_prompt() -> None:
    """A whitelisted prompt move (into an AGENT column) launches the FILLED /implement:* prompt.

    Transitions-only model (DESIGN §8.0.6): the launch is decided by the whitelisted prompt-
    transition, so the move targets InProgress (a bare INERT column) via a prompt-bearing edge.
    The launched session command must carry the SUBSTITUTED prompt (``{{code}}`` → bare ``7``, the
    ``/implement:phase`` slash-command present), NOT the bare ``deps.agent_command`` — the headline
    parity fix wired through the tick.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="My Feature", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # A fresh detached worktree reports no feature branch yet.
    m.workspace.discover_branch.return_value = None
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _two_agent_whitelist_config(), state)

    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    m.sessions.launch.assert_called_once()
    # Phase-25 §25.1: the launch command is BARE; the FILLED per-transition prompt is send-keys'd
    # into the REPL (not the bare claude fallback). Assert against the delivered prompt.
    launched_command: str = m.sessions.launch.call_args.args[2]
    assert "/implement:phase" not in launched_command  # prompt no longer in the launch command
    delivered = _delivered_prompt(m.sessions)
    assert "/implement:phase" in delivered
    # {{code}} substitutes the BARE issue number (defect 3) — helper calls need an int arg, so the
    # delivered prompt carries ``7`` (not ``#7``, which would be a bash comment / fail int()).
    assert "/implement:phase 7 —" in delivered
    assert "#7" not in delivered  # no stray '#' prefix that would break helper calls
    assert "My Feature" in delivered  # {{title}} substituted
    assert result.actions_executed == 1
    # The baseline advances to the destination for the next diff (a launch is a forward move).
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_script_only_move_dispatches_run_script() -> None:
    """A whitelisted script-only move dispatches a RunScriptAction (mechanical, no launch).

    The Design→InProgress pair carries a ``script`` but no ``prompt`` → RUN_SCRIPT. No agent
    session is launched; the workspace script-runner is invoked with the KANBAN env, and the
    tick advances the baseline to the destination.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/genesis"
    m.workspace.run_transition_script.return_value = (0, "ok")
    # Move OUT of Design (agent) so Design→InProgress matches the script-only whitelist row.
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _two_agent_whitelist_config(), state)

    # No agent launched — a run_script transition spends no session.
    m.sessions.launch.assert_not_called()
    # The mechanical script ran via the workspace runner with the KANBAN_REPO/BRANCH env.
    m.workspace.run_transition_script.assert_called_once()
    call = m.workspace.run_transition_script.call_args
    assert call.args[0] == 7
    assert call.args[1] == "bin/check-pr-ready.sh"
    env = call.args[2]
    assert env["KANBAN_BRANCH"] == "feat/genesis"
    assert "KANBAN_REPO" in env
    assert result.actions_executed == 1
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_unwhitelisted_move_rolls_back_and_baseline_is_bounce_target() -> None:
    """An un-whitelisted move dispatches a RollbackAction AND the baseline is the bounce target.

    Backlog→Done is absent from the whitelist → ROLLBACK to Backlog (the from_col). The card is
    moved BACK to Backlog and a recap comment posted. Critically, the next-tick diff baseline is
    the BOUNCE TARGET (Backlog), NOT the rejected destination (Done) — so a second tick against
    the same board produces no re-launch and no re-rollback (the idempotency seam).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _two_agent_whitelist_config(), state)

    # No agent launched — the move was rejected and bounced.
    m.sessions.launch.assert_not_called()
    # The card was moved BACK to Backlog (the bounce target), and a recap comment posted.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Backlog")
    m.board_writer.comment.assert_called_once()
    recap: str = m.board_writer.comment.call_args.args[1]
    assert "Backlog" in recap
    assert result.actions_executed == 1
    # The diff baseline is the BOUNCE TARGET (Backlog), not the rejected destination (Done).
    assert next_state.columns_by_item["PVTI_7"] == "Backlog"

    # A second tick against the SAME board: the card now sits in Backlog on the board, and the
    # baseline already records Backlog → no diff → no re-rollback, no re-launch (idempotent).
    ticket_settled = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Backlog")
    reader2 = _FakeBoardReader("probe-2", _snapshot(ticket_settled))
    m2 = _mocks(reader2)
    state2 = PersistedState(columns_by_item=dict(next_state.columns_by_item), last_probe="probe-1")

    result2, _ = tick(m2.deps, _two_agent_whitelist_config(), state2)

    m2.board_writer.move_card.assert_not_called()
    m2.sessions.launch.assert_not_called()
    assert result2.actions_executed == 0


def test_rollback_records_bookkeeping_marker_not_rate_limit() -> None:
    """A ROLLBACK bounce records a BOOKKEEPING anti-loop marker (#19 secondary guard).

    The bounce target marker is set (so an immediate re-rollback is dedup-guarded) but the move
    is EXCLUDED from the per-ticket rate-limit counter — a legitimate rollback must not eat the
    runaway-loop budget. The diff-baseline advance stays the PRIMARY no-re-trigger mechanism;
    the bookkeeping tag is the SECONDARY guard (port of the PoC bookkeeping ``record_bot_move``).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=5_000.0)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    _result, next_state = tick(m.deps, _two_agent_whitelist_config(), state)

    # The bounce target (Backlog) recency marker IS recorded — an immediate re-rollback is guarded.
    assert ("PVTI_7", "Backlog") in next_state.antiloop.recent_targets
    assert is_blocked(next_state.antiloop, "PVTI_7", "Backlog", now=5_001.0) is True
    # But it is NOT fed into the rate-limit counter (the bookkeeping exclusion, #19): a guarded
    # rollback must not count toward the runaway-loop budget.
    assert "PVTI_7" not in next_state.antiloop.move_times


def test_rollback_does_not_finalize_left_stage() -> None:
    """A ROLLBACK is NOT a forward advance — it must NOT flip the LEFT sticky to ✅ done.

    Design→Done is un-whitelisted → ROLLBACK to Design. Even though the LEFT (Design) stage has
    an open 🟡 sticky, the rollback must leave it untouched: the phase-8 ✅-on-advance finalize
    fires only for forward verdicts (LAUNCH / NOOP-forward / RUN_SCRIPT-success), never for a
    rollback (the PoC finalizes ✅ only on accepted non-rollback forward moves).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader, now=9000.0)
    # The LEFT (Design) stage's PRE-READ state + its open running sticky.
    m.store.load.return_value = _left_state(stage="Design")
    m.board_writer.list_issue_comments.return_value = [_existing_sticky("Design")]
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _two_agent_whitelist_config(), state)

    # The rollback bounced the card back to Design.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Design")
    # The LEFT (Design) sticky was NEVER flipped to ✅ — no done finalize on a rollback.
    m.board_writer.update_comment.assert_not_called()
    assert result.actions_executed == 1
    # The baseline is the bounce target (Design), so the bounce does not re-trigger.
    assert next_state.columns_by_item["PVTI_7"] == "Design"


def test_prompt_transition_launch_injects_filled_prompt() -> None:
    """A whitelisted prompt-transition LAUNCHes with the filled ``/implement:*`` prompt.

    Transitions-only (DESIGN §8.0.6): the LAUNCH is a transition concern and a prompt-bearing
    whitelisted move (``Backlog → InProgress`` carries ``/implement:phase``) launches an agent
    whose wrapped argv injects the filled prompt positional. The former legacy column-class
    path (``transitions is None`` → destination-only model, NO filled prompt) is REMOVED — there
    is no whitelist-absent fallback, so this asserts the prompt rides along.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    m.sessions.launch.assert_called_once()
    # The launch builds the real wrapped BARE argv (phase 14); the transition's prompt is delivered
    # into the REPL via send-keys (phase-25 §25.1), NOT injected into the launch command.
    launched_command: str = m.sessions.launch.call_args.args[2]
    assert "--session-id" in launched_command
    assert "; kanban-session-end 7" in launched_command
    assert "/implement:phase" not in launched_command  # prompt no longer in the launch command
    assert "/implement:phase" in _delivered_prompt(m.sessions)
    assert result.actions_executed == 1
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_reactive_cancel_teardown_routes_with_whitelist_present() -> None:
    """The reactive Cancel teardown still wins, even with a whitelist present.

    Precedence 1 (reactive routing) fires BEFORE the whitelist verdict, so a move INTO the
    reactive Cancel column tears down the agent — the whitelist never gets to roll a Cancel move
    back as "un-whitelisted" (DESIGN §8.2 / the PoC runner intercepts ``(*, Cancel)`` first).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Cancel")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(m.deps, _two_agent_whitelist_config(), state)

    # Teardown ran (session killed, worktree removed, ticket purged) — NOT a rollback.
    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    # The Cancel path abandons the ticket → keep_budgets=False (the default full purge, 13.8).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.sessions.launch.assert_not_called()
    assert result.actions_executed == 1


def test_reactive_cancel_to_backlog_resets_with_whitelist_present() -> None:
    """A Cancel→Backlog move resets (purges runtime state), even with a whitelist present.

    Precedence 1 reset routing wins before the whitelist, so leaving the reactive Cancel column
    back to the reset target (Backlog) purges the ticket — it is not classified by the whitelist.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Backlog")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    state = PersistedState(columns_by_item={"PVTI_7": "Cancel"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _two_agent_whitelist_config(), state)

    # ResetAction purged the runtime state (exhaustive purge_ticket, 13.7); no launch/rollback.
    m.store.purge_ticket.assert_called_once_with(7)
    m.sessions.launch.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    assert result.actions_executed == 1
    assert next_state.columns_by_item["PVTI_7"] == "Backlog"


# ---------------------------------------------------------------------------
# Phase 15.6 regression: merge-gate rollback vs check-pr-ready fix-CI re-trigger
# (on_fail:rollback → bookkeeping return · on_fail:move:<T> → re-triggering loop)
# ---------------------------------------------------------------------------

# Board for the merge gate tests: Review + Merge (both inert; the merge gate is
# a script-only mechanical check).
_MERGE_GATE_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: Review
    name: Review
  - key: Merge
    name: Merge
  - key: Done
    name: Done
"""

_MERGE_GATE_WHITELIST_YAML = """
project: owner/repo
defaults:
  concurrency_cap: 3
  move_rate_limit_per_hour: 10
transitions:
  - from: Review
    to: Merge
    script: bin/check-merge-ready.sh
    on_fail: "rollback"
  - from: Merge
    to: Done
"""


def _merge_gate_config() -> TickConfig:
    """Build a :class:`TickConfig` from the merge-gate board + whitelist."""
    return TickConfig(
        columns=load_columns(_MERGE_GATE_COLUMNS_YAML),
        transitions=load_transitions(_MERGE_GATE_WHITELIST_YAML),
    )


def test_merge_gate_failure_rollback_lands_in_review_and_stays() -> None:
    """A failed merge gate (on_fail:rollback) returns the card to Review and it STAYS there.

    Tick 1: card at Merge (moved Review→Merge), script fails → rollback to Review, baseline=Review.
    Tick 2: card in Review, baseline=Review → no diff → NO further move (NOT stranded in Merge).

    This is the defect repro: before the fix, ``on_fail:move:Review`` set baseline=Merge, so the
    next diff (Merge→Review) was un-whitelisted → ROLLBACK bounced the card BACK to Merge,
    stranding it there as a false "ready-to-merge" signal.
    """
    # ── Tick 1: Review→Merge script fails → rollback to Review ────────────
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Merge")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/genesis"
    m.workspace.run_transition_script.return_value = (1, "checks failed")  # NON-zero → failure
    state = PersistedState(columns_by_item={"PVTI_7": "Review"}, last_probe="probe-0")

    result1, next_state1 = tick(m.deps, _merge_gate_config(), state)

    # The card was moved BACK to Review (rollback target = from_col).
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Review")
    m.sessions.launch.assert_not_called()
    assert result1.actions_executed == 1
    # The diff baseline is the ROLLBACK TARGET (Review), NOT Merge.
    assert next_state1.columns_by_item["PVTI_7"] == "Review"

    # ── Tick 2: card in Review, baseline=Review → no diff → no action ─────
    ticket_settled = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Review")
    reader2 = _FakeBoardReader("probe-2", _snapshot(ticket_settled))
    m2 = _mocks(reader2)
    state2 = PersistedState(columns_by_item=dict(next_state1.columns_by_item), last_probe="probe-1")

    result2, _ = tick(m2.deps, _merge_gate_config(), state2)

    m2.board_writer.move_card.assert_not_called()
    m2.sessions.launch.assert_not_called()
    assert result2.actions_executed == 0


# Board for the fix-CI loop test: a bare column set (DESIGN §8.0.6). The fix-CI
# agent is the PRCI→InProgress prompt row in the whitelist — the launch lives on
# that transition, not on a column flag.
_FIXCI_LOOP_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: InProgress
    name: In Progress
  - key: PRCI
    name: PR/CI
  - key: Done
    name: Done
"""

_FIXCI_LOOP_WHITELIST_YAML = """
project: owner/repo
defaults:
  concurrency_cap: 3
  move_rate_limit_per_hour: 10
transitions:
  - from: InProgress
    to: PRCI
    script: bin/check-pr-ready.sh
    on_fail: "move:InProgress"
  - from: PRCI
    to: InProgress
    prompt: "/implement:fix-ci Fix the CI of {{code}} — {{title}}"
    profile: dev
    permission_mode: auto
    advance: auto:PRCI
"""


def _fixci_loop_config() -> TickConfig:
    """Build a :class:`TickConfig` from the fix-CI loop board + whitelist."""
    return TickConfig(
        columns=load_columns(_FIXCI_LOOP_COLUMNS_YAML),
        transitions=load_transitions(_FIXCI_LOOP_WHITELIST_YAML),
    )


def test_check_pr_ready_failure_re_fires_fixci_loop_across_two_ticks() -> None:
    """check-pr-ready failure (on_fail:move:InProgress) re-fires the fix-CI agent on tick 2.

    Tick 1: InProgress→PRCI check script FAILS → on_fail:move:InProgress → move to InProgress,
    baseline=PRCI (the re-fire seam).
    Tick 2: baseline=PRCI, board=InProgress → diff (PRCI→InProgress) fires a LAUNCH (fix-CI agent),
    proving the on_fail:move re-trigger genuinely continues the loop (not just sets a baseline).
    """
    # ── Tick 1: InProgress→PRCI script fails → on_fail:move:InProgress ─────
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="My Feature", column_key="PRCI")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/genesis"
    m.workspace.run_transition_script.return_value = (1, "CI red")  # NON-zero → failure
    # The failure routing calls bump_retry; return 1 (under the _FIXCI_CAP=2) → within-cap bounce.
    m.store.bump_retry.return_value = 1
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result1, next_state1 = tick(m.deps, _fixci_loop_config(), state)

    # The card was moved to the display NAME "In Progress" (defect 2: the on_fail:move:InProgress
    # directive KEY resolves to the board's display NAME so move_card lands the bounce).
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "In Progress")
    m.sessions.launch.assert_not_called()  # No launch on tick 1 (just the script check)
    assert result1.actions_executed == 1
    # Baseline = PRCI (the script column) so the next diff re-fires (PRCI→InProgress).
    assert next_state1.columns_by_item["PVTI_7"] == "PRCI"

    # ── Tick 2: PRCI→InProgress diff fires a fix-CI LAUNCH ─────────────────
    ticket2 = Ticket(item_id="PVTI_7", issue_number=7, title="My Feature", column_key="InProgress")
    reader2 = _FakeBoardReader("probe-2", _snapshot(ticket2))
    m2 = _mocks(reader2)
    m2.workspace.discover_branch.return_value = "feat/genesis"
    # Tick 2 is a LAUNCH (not RUN_SCRIPT), so run_transition_script is not called.
    state2 = PersistedState(columns_by_item=dict(next_state1.columns_by_item), last_probe="probe-1")

    result2, next_state2 = tick(m2.deps, _fixci_loop_config(), state2)

    # The diff PRCI→InProgress matches the fix-CI prompt transition → LAUNCH. The fix-CI prompt is
    # delivered into the REPL via send-keys (phase-25 §25.1), not the launch command.
    m2.sessions.launch.assert_called_once()
    launched_command: str = m2.sessions.launch.call_args.args[2]
    assert "/implement:fix-ci" not in launched_command  # prompt no longer in the launch command
    assert "/implement:fix-ci" in _delivered_prompt(m2.sessions)
    assert result2.actions_executed == 1
    # Baseline advances to InProgress (the destination) for the next diff.
    assert next_state2.columns_by_item["PVTI_7"] == "InProgress"


# ---------------------------------------------------------------------------
# Gate 13.5: the concurrency-cap gate on the LAUNCH branch + the real queue drain
# (cap-full → queue + baseline advance · leak-safety release on failed launch ·
# the drain reserves-before-launch, clears-on-success, keeps-on-fail, never exceeds
# the cap · rich-payload parity: the drained LaunchAction.prompt is preserved)
# ---------------------------------------------------------------------------


def _drain_store(now: float = 1000.0) -> MagicMock:
    """Build a MagicMock store wired for the standalone :func:`_drain_queue` tests.

    Defaults: ``reserve_slot`` succeeds (a free slot), no queued backlog. Each test overrides
    ``dequeue_pending`` / ``load_queued`` / ``reserve_slot`` for the case it exercises.
    """
    store = MagicMock()
    store.reserve_slot.return_value = True
    store.dequeue_pending.return_value = ()
    return store


def _drain_deps(store: MagicMock, *, now: float = 1000.0) -> Deps:
    """Assemble a :class:`Deps` whose store is ``store`` and whose launch adapters are mocks."""
    workspace = MagicMock()
    workspace.ensure_worktree.return_value = "/tmp/wt/ticket-7"
    workspace.discover_branch.return_value = None
    sessions = MagicMock()
    sessions.launch.return_value = "ticket-7"
    # Phase-25 §25.1: a drained prompt-bearing launch polls ``capture`` then send-keys the prompt.
    # Default the snapshot to a READY-REPL marker so the bounded poll returns at once.
    sessions.capture.return_value = "│ > Welcome to Claude"
    clock = MagicMock()
    clock.now.return_value = now
    return Deps(
        board_writer=MagicMock(),
        board_reader=MagicMock(),
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=MagicMock(),
        # No-op sleeper so the trust/ready poll runs offline (phase-25 §25.1).
        sleeper=lambda _seconds: None,
    )


def test_cap_full_diverts_launch_to_queue_and_advances_baseline() -> None:
    """At a full cap a LAUNCH does NOT dispatch — it enqueues the ticket + advances the baseline.

    With ``concurrency_cap=1`` and ``reserve_slot`` returning ``False`` (a slot already held), the
    cap gate diverts the launch: no agent session starts, a rich queue marker is written, and the
    diff baseline advances to the agent column so the next diff does NOT re-fire the move.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="My Feature", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = None
    # The cap is full: the slot reservation fails for this launch.
    m.store.reserve_slot.return_value = False
    config = TickConfig(
        columns=load_columns(_TWO_AGENT_COLUMNS_YAML),
        transitions=load_transitions(_WHITELIST_YAML),
        concurrency_cap=1,
    )
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, next_state = tick(m.deps, config, state)

    # No agent launched — the cap gate diverted the launch to the queue.
    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    # The reservation was attempted with the configured cap.
    m.store.reserve_slot.assert_called_once_with(7, 1)
    # The ticket was enqueued (a rich marker written for the drain).
    m.store.enqueue_launch.assert_called_once()
    enq_issue, payload = m.store.enqueue_launch.call_args.args
    assert enq_issue == 7
    # The baseline advanced so the move is not re-fired next tick.
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"
    # A divert is not a launch — no action executed cleanly (the launch never ran).
    assert result.actions_executed == 0


def test_cap_full_enqueues_rich_payload_not_just_identity() -> None:
    """The cap-gate marker carries the FULL launch routing (operator decision — rich payload).

    The persisted payload must include the filled ``prompt`` plus ``profile`` / ``permission_mode``
    / ``title`` / ``body`` — not just ``item_id`` / ``stage`` — so the drain can rebuild a launch
    byte-identical to a direct one (the filled /implement:* prompt is preserved, no regression to
    the bare ``agent_command``).
    """
    ticket = Ticket(
        item_id="PVTI_7",
        issue_number=7,
        title="My Feature",
        column_key="InProgress",
        body="some body",
    )
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = None
    m.store.reserve_slot.return_value = False
    config = TickConfig(
        columns=load_columns(_TWO_AGENT_COLUMNS_YAML),
        transitions=load_transitions(_WHITELIST_YAML),
        concurrency_cap=1,
    )
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    tick(m.deps, config, state)

    _, payload = m.store.enqueue_launch.call_args.args
    # Identity bits.
    assert payload["item_id"] == "PVTI_7"
    assert payload["stage"] == "InProgress"
    assert payload["title"] == "My Feature"
    assert payload["body"] == "some body"
    # The per-transition prompt is preserved (the whole point of the rich payload). It is the
    # TEMPLATE the matched transition carried — placeholders are filled at execute time inside
    # ``LaunchAction._agent_command`` (identically for a direct launch and a drained one), so the
    # marker stores the raw template, not the substituted text.
    assert payload["prompt"] is not None
    assert payload["prompt"] == "/implement:phase {{code}} — {{title}}"
    # The per-transition routing rides along too.
    assert payload["profile"] == "dev"
    assert payload["permission_mode"] == "auto"
    assert "enqueued_at" in payload
    # Phase 20 (DESIGN §8.0.6): the column-default tier is gone — the payload carries ONLY the
    # transition ``profile``, never a ``column_permission_profile`` key.
    assert "column_permission_profile" not in payload


def test_under_cap_reserves_then_launches() -> None:
    """Under the cap a LAUNCH reserves a slot then dispatches the agent (launch called once)."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)  # default reserve_slot → True (a free slot)
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(m.deps, config, state)

    m.store.reserve_slot.assert_called_once_with(7, 3)
    m.sessions.launch.assert_called_once()
    # A successful launch must NOT release the slot (it backs the now-running session).
    m.store.release_slot.assert_not_called()
    assert result.actions_executed == 1


def test_failed_launch_releases_reserved_slot_no_leak() -> None:
    """A LAUNCH whose dispatch RAISES RELEASES the reserved slot (leak-safety).

    The launch raises (ensure_worktree blows up), so the tri-state watchdog returns ``FAILED``
    (defect 13) — a DEFINITIVE failure with no session created. The reserved slot would otherwise
    leak forever (no running-state, no queue marker → the reaper never reclaims it), so the cap gate
    releases it on the definitive-failure path.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.store.reserve_slot.return_value = True
    # Make the launch fail inside the watchdog.
    m.workspace.ensure_worktree.side_effect = RuntimeError("tmux down")
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(m.deps, config, state)

    # The launch failed → the reserved slot is released so it does not leak.
    m.store.release_slot.assert_called_once_with(7)
    # The marker was NOT enqueued (the divert path never ran — the reservation succeeded).
    m.store.enqueue_launch.assert_not_called()
    assert result.errors >= 1
    assert result.actions_executed == 0


def test_timed_out_launch_keeps_reserved_slot(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A LAUNCH that TIMES OUT (UNKNOWN) KEEPS the reserved slot — never cap+1 (defect 13).

    The abandoned worker may still create the tmux session late; releasing the slot would let that
    late launch run an agent without a slot (cap+1). On the unknown-timeout the slot is KEPT; the
    drain's already-running guard adjudicates next tick. Only a DEFINITIVE failure (exception)
    releases the slot.
    """
    import kanbanmate.app.tick as tick_mod  # noqa: PLC0415

    # Force the LAUNCH dispatch to report UNKNOWN (a timeout) without actually spawning a thread.
    monkeypatch.setattr(
        tick_mod,
        "_run_launch_with_watchdog",
        lambda _executor, _command, _deps, _timeout: tick_mod.WatchdogStatus.UNKNOWN,
    )
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.store.reserve_slot.return_value = True
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(m.deps, config, state)

    # The slot is KEPT on the unknown-timeout (no cap+1); the failure is still counted.
    m.store.release_slot.assert_not_called()
    assert result.errors >= 1
    assert result.actions_executed == 0


def test_drain_launches_queued_ticket_when_slot_free_and_clears_marker() -> None:
    """``_drain_queue`` re-launches a queued ticket WHEN a slot frees and clears its marker."""
    store = _drain_store()
    store.dequeue_pending.return_value = (7,)
    store.reserve_slot.return_value = True
    store.load_queued.return_value = {
        "item_id": "PVTI_7",
        "stage": "InProgress",
        "title": "My Feature",
        "body": "b",
        "prompt": "/implement:phase #7 — My Feature",
        "profile": "dev",
        "permission_mode": "auto",
        "enqueued_at": 1000.0,
    }
    deps = _drain_deps(store)
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        _drain_queue(deps, config, executor, now=1000.0)

    store.reserve_slot.assert_called_once_with(7, 3)
    deps.sessions.launch.assert_called_once()  # type: ignore[attr-defined]
    # The marker is cleared ONLY after a confirmed launch.
    store.clear_queued.assert_called_once_with(7)
    # A successful drained launch does not release the slot.
    store.release_slot.assert_not_called()


def test_drain_under_pause_launches_nothing_keeps_markers() -> None:
    """Under PAUSE (kill_switch) the drain launches NOTHING and reserves NO slot (defect 6).

    A queued ticket with a free slot would normally re-launch; with the kill-switch on, the drain
    returns immediately, leaving the queue marker intact (no clear_queued) so a resume re-drives it.
    """
    store = _drain_store()
    store.dequeue_pending.return_value = (7,)
    store.reserve_slot.return_value = True
    store.load_queued.return_value = {
        "item_id": "PVTI_7",
        "stage": "InProgress",
        "title": "My Feature",
        "body": "b",
        "prompt": "/implement:phase 7 — My Feature",
        "profile": "dev",
        "permission_mode": "auto",
        "enqueued_at": 1000.0,
    }
    deps = _drain_deps(store)
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        _drain_queue(deps, config, executor, now=1000.0, kill_switch=True)

    # No launch, no slot reservation, and crucially the queue marker is NOT cleared.
    deps.sessions.launch.assert_not_called()  # type: ignore[attr-defined]
    store.reserve_slot.assert_not_called()
    store.clear_queued.assert_not_called()
    store.dequeue_pending.assert_not_called()


def _real_store_drain_deps(tmp_path: Path, *, now: float = 1000.0) -> tuple[FsStateStore, Deps]:
    """Build a :class:`Deps` with a REAL :class:`FsStateStore` and mock launch adapters.

    The real store is the whole point of the 13.7 drain tests: a MagicMock store makes
    ``release_slot`` a no-op recorder, which MASKED the CRITICAL defect where the (then
    exhaustive) ``release_slot`` deleted the very queue marker the failed-launch path means
    to KEEP. Driving the drain against the filesystem proves the marker actually survives
    (slot-only ``release_slot``) and the slot is actually freed.
    """
    workspace = MagicMock()
    workspace.ensure_worktree.return_value = "/tmp/wt/ticket-7"
    workspace.discover_branch.return_value = None
    sessions = MagicMock()
    sessions.launch.return_value = "ticket-7"
    clock = MagicMock()
    clock.now.return_value = now
    store = FsStateStore(tmp_path)
    deps = Deps(
        board_writer=MagicMock(),
        board_reader=MagicMock(),
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=MagicMock(),
    )
    return store, deps


def test_drain_keeps_marker_and_releases_slot_on_failed_launch(tmp_path: Path) -> None:
    """CRITICAL (13.7 #1): a FAILED drained launch KEEPS the queue marker + frees the slot.

    Driven on a REAL ``FsStateStore`` (NOT a MagicMock — the mock masked the defect): enqueue
    a ticket, reserve nothing, drain with a launch that fails, then assert ``dequeue_pending()``
    STILL returns the issue (marker KEPT, the ticket is not silently dropped) AND the slot is
    freed (a fresh ``reserve_slot`` succeeds). Before the split, ``release_slot`` was the
    exhaustive purge → it deleted the marker here and dropped the ticket forever.
    """
    store, deps = _real_store_drain_deps(tmp_path)
    # Enqueue a real queue marker.
    store.enqueue_launch(
        7,
        {
            "item_id": "PVTI_7",
            "stage": "InProgress",
            "prompt": "/implement:phase #7",
            "enqueued_at": 1000.0,
        },
    )
    # The drained launch fails inside the watchdog (ensure_worktree raises).
    deps.workspace.ensure_worktree.side_effect = RuntimeError("boom")  # type: ignore[attr-defined]
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        _drain_queue(deps, config, executor, now=1000.0)

    # The marker is KEPT for a later sweep — the ticket is NOT dropped (the CRITICAL fix).
    assert store.dequeue_pending() == (7,)
    # The slot was freed (no leak): a fresh reservation under cap=1 succeeds, proving the
    # drain's reserved slot was actually released.
    assert store.reserve_slot(7, cap=1) is True


def test_drain_never_exceeds_cap_when_no_slot_free() -> None:
    """``_drain_queue`` drains nothing when no slot is free; the marker is kept, no launch."""
    store = _drain_store()
    store.dequeue_pending.return_value = (7,)
    # Cap is full: the drain's reservation fails.
    store.reserve_slot.return_value = False
    deps = _drain_deps(store)
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=1, transitions=_tick_whitelist()
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        _drain_queue(deps, config, executor, now=1000.0)

    store.reserve_slot.assert_called_once_with(7, 1)
    # No payload read, no launch, no clear, no release — the marker is left for the next sweep.
    store.load_queued.assert_not_called()
    deps.sessions.launch.assert_not_called()  # type: ignore[attr-defined]
    store.clear_queued.assert_not_called()
    store.release_slot.assert_not_called()


def test_drain_clears_and_logs_invalid_payload_never_launches(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A queued marker with no ``item_id`` is cleared + logged once, and never launched."""
    store = _drain_store()
    store.dequeue_pending.return_value = (7,)
    store.reserve_slot.return_value = True
    # An invalid/legacy marker: no item_id to rebuild the ticket from.
    store.load_queued.return_value = {"stage": "InProgress"}
    deps = _drain_deps(store)
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    with caplog.at_level(logging.WARNING, logger="kanbanmate.app.tick"):
        with ThreadPoolExecutor(max_workers=1) as executor:
            _drain_queue(deps, config, executor, now=1000.0)

    # Released the slot, cleared the unlaunchable marker, and never launched.
    store.release_slot.assert_called_once_with(7)
    store.clear_queued.assert_called_once_with(7)
    deps.sessions.launch.assert_not_called()  # type: ignore[attr-defined]
    # Exactly one visible warning (not a silent drop).
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "#7" in warnings[0].getMessage()


def test_drain_rebuilds_faithful_launch_prompt_preserved() -> None:
    """Rich-payload parity: the drained ``LaunchAction.prompt`` equals the queued prompt (not None).

    Capture the command the drain dispatches and assert its ``prompt`` is the originally-queued
    filled prompt — proof the drained agent runs the SAME /implement:* prompt and does NOT regress
    to the bare ``agent_command``.
    """
    store = _drain_store()
    store.dequeue_pending.return_value = (7,)
    store.reserve_slot.return_value = True
    queued_prompt = "/implement:phase #7 — My Feature"
    store.load_queued.return_value = {
        "item_id": "PVTI_7",
        "stage": "InProgress",
        "title": "My Feature",
        "body": "b",
        "prompt": queued_prompt,
        "script": None,
        "profile": "dev",
        "permission_mode": "auto",
        "on_fail": "",
        "advance": "stop",
        "enqueued_at": 1000.0,
    }
    deps = _drain_deps(store)
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    # Spy on the dispatched command by recording it and reporting success.
    captured: list[object] = []

    def _spy_watchdog(
        executor: ThreadPoolExecutor, command: object, deps_arg: Deps, timeout: float
    ) -> bool:
        captured.append(command)
        return True

    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("kanbanmate.app.tick._run_with_watchdog", _spy_watchdog)
            _drain_queue(deps, config, executor, now=1000.0)

    assert len(captured) == 1
    rebuilt = captured[0]
    assert isinstance(rebuilt, LaunchAction)
    # The filled prompt is preserved — NOT None (no regression to the bare agent_command).
    assert rebuilt.prompt == queued_prompt
    assert rebuilt.prompt is not None
    # The full routing rode along faithfully.
    assert rebuilt.profile == "dev"
    # Phase 20 (DESIGN §8.0.6): the drained launch resolves its profile from the PERSISTED
    # transition ``profile`` ALONE (the payload no longer carries a column-default tier) — the
    # same value a direct launch would resolve. ``_resolve_profile`` reads only the transition.
    assert rebuilt._resolve_profile() == "dev"
    assert rebuilt.permission_mode == "auto"
    assert rebuilt.ticket.item_id == "PVTI_7"
    assert rebuilt.ticket.issue_number == 7
    assert rebuilt.ticket.title == "My Feature"
    # The marker is cleared after the (spied) successful launch.
    store.clear_queued.assert_called_once_with(7)


# ---------------------------------------------------------------------------
# Phase 13.7: PoC slot-only/purge split — real-fs integration tests that the
# false-confidence MagicMock could not cover (keep-marker invariant, leak-safety
# preserving the durable §6 counters, the drain already-running guard, stale-marker
# supersede on a fresh direct launch, and the operator pull-back marker clear)
# ---------------------------------------------------------------------------


def _real_store_full_tick_deps(
    reader: _FakeBoardReader, tmp_path: Path, *, now: float = 1000.0
) -> tuple[FsStateStore, Deps]:
    """Build a full-tick :class:`Deps` with a REAL :class:`FsStateStore` and mock adapters.

    The real store lets the 13.7 tests assert against actual on-disk markers (slot / queue /
    moves / retries) — the only way to prove the slot/purge split behaves correctly, since a
    MagicMock store reduces every store method to a no-op recorder.
    """
    workspace = MagicMock()
    workspace.ensure_worktree.return_value = "/tmp/wt/ticket-7"
    workspace.discover_branch.return_value = None
    # #9: default no worktree present so a plain inert move into Done is a NOOP (not a reclaim).
    workspace.worktree_exists.return_value = False
    workspace.has_unpushed_work.return_value = False
    sessions = MagicMock()
    sessions.launch.return_value = "ticket-7"
    sessions.is_alive.return_value = True
    clock = MagicMock()
    clock.now.return_value = now
    store = FsStateStore(tmp_path)
    deps = Deps(
        board_writer=MagicMock(),
        board_reader=reader,
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=MagicMock(),
    )
    return store, deps


def test_failed_direct_launch_preserves_moves_purges_retries_real_fs(tmp_path: Path) -> None:
    """13.7 #2 + 15.1: a failed DIRECT launch's leak-safety preserves the durable move
    rate-limit history but PURGES the retry counters.

    On a REAL ``FsStateStore``: seed ``moves/<issue>`` + ``retries/<issue>__*``, then fail a
    direct launch. The leak-safety calls ``release_slot``, which per 15.1 now purges BOTH
    the slot AND the retry counters (a cancelled/failed ticket leaves no stale ledger). The
    move rate-limit history (``moves/<issue>.json``) SURVIVES because ``release_slot`` does
    NOT touch it — the exhaustive ``purge_ticket`` handles that. The slot itself is freed
    (no leak).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    store, deps = _real_store_full_tick_deps(reader, tmp_path)
    # Seed the durable counters.
    store.record_move_for_item(7, now=1000.0)
    store.bump_retry(7, "onfail:Blocked")
    # Make the direct launch fail inside the watchdog.
    deps.workspace.ensure_worktree.side_effect = RuntimeError("tmux down")  # type: ignore[attr-defined]
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(deps, config, state)

    assert result.errors >= 1
    # The move rate-limit history SURVIVES (release_slot does NOT touch moves/).
    assert store.move_count_for_item_last_hour(7, now=1000.0) == 1
    # 15.1: the retry counters are PURGED by release_slot (a cancelled/failed ticket
    # leaves no stale retry ledger).
    assert list((store.root / "retries").glob("7__*")) == []
    # The slot was freed (no leak) — a fresh reservation under cap=1 succeeds.
    assert store.reserve_slot(7, cap=1) is True


def test_drain_already_running_guard_clears_marker_no_redispatch(tmp_path: Path) -> None:
    """13.7 guard: the drain does NOT re-dispatch a queued issue that is already RUNNING.

    A launch the watchdog abandoned can persist a RUNNING state late. With such a state present,
    the drain clears the now-redundant queue marker and does NOT dispatch a second launch (which
    would churn on the tmux duplicate-name check).
    """
    store, deps = _real_store_drain_deps(tmp_path)
    # The issue is already live: a RUNNING state is persisted.
    store.save(
        TicketState(
            issue_number=7,
            item_id="PVTI_7",
            session_id="ticket-7",
            status=TicketStatus.RUNNING,
            heartbeat=1000.0,
        )
    )
    # A stale queue marker coexists (the late-completing abandoned launch).
    store.enqueue_launch(
        7, {"item_id": "PVTI_7", "stage": "InProgress", "prompt": "/x", "enqueued_at": 1000.0}
    )
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        _drain_queue(deps, config, executor, now=1000.0)

    # No re-dispatch — the running ticket is not launched a second time.
    deps.sessions.launch.assert_not_called()  # type: ignore[attr-defined]
    # The now-redundant marker is cleared so a later sweep does not re-examine it.
    assert store.dequeue_pending() == ()


def test_drain_already_live_guard_includes_waiting(tmp_path: Path) -> None:
    """#3: the drain already-live guard treats WAITING as LIVE — no re-dispatch.

    Before #3 the guard tested RUNNING only, so a queued WAITING ticket (a live agent paused on a
    human prompt) was re-dispatched — and the idempotent launch pre-kills the existing session,
    DISCARDING the pending human decision. With LIVE = {RUNNING, WAITING} the drain drops only the
    redundant marker and does NOT relaunch.
    """
    store, deps = _real_store_drain_deps(tmp_path)
    # The issue is live but WAITING on a human prompt.
    store.save(
        TicketState(
            issue_number=7,
            item_id="PVTI_7",
            session_id="ticket-7",
            status=TicketStatus.WAITING,
            heartbeat=1000.0,
        )
    )
    store.enqueue_launch(
        7, {"item_id": "PVTI_7", "stage": "InProgress", "prompt": "/x", "enqueued_at": 1000.0}
    )
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        _drain_queue(deps, config, executor, now=1000.0)

    # The WAITING agent's session is NOT killed/relaunched; only the marker is cleared.
    deps.sessions.launch.assert_not_called()  # type: ignore[attr-defined]
    assert store.dequeue_pending() == ()


def test_drain_already_running_guard_preserves_live_slot_and_retries(tmp_path: Path) -> None:
    """Md2: the already-running guard must NOT release a LIVE ticket's slot + fix-CI budgets.

    A RUNNING state coexists with a stale queue marker AND the LIVE ticket already holds its
    concurrency-cap slot + an in-flight ``retries/<issue>__<key>`` fix-CI counter. The old order
    ``reserve_slot`` (idempotent → no-op on the held slot) THEN ``release_slot`` stripped BOTH the
    live slot and the retry budgets: ``release_slot`` unconditionally unlinks ``slots/ticket-<n>``
    and every ``retries/<n>__*``. That undercounts the cap (an extra agent could exceed it) and
    zeroes in-flight retries. Driven on a REAL ``FsStateStore`` so the actual reserve/release
    semantics are exercised (a MagicMock would mask the unlink — 18.3 discipline).
    """
    store, deps = _real_store_drain_deps(tmp_path)
    store.save(
        TicketState(
            issue_number=7,
            item_id="PVTI_7",
            session_id="ticket-7",
            status=TicketStatus.RUNNING,
            heartbeat=1000.0,
        )
    )
    # The LIVE ticket already holds its slot + an in-flight fix-CI retry budget.
    assert store.reserve_slot(7, cap=3) is True
    assert store.bump_retry(7, "onfail:PRCI") == 1
    slot_marker = tmp_path / "slots" / "ticket-7"
    # The colon in the key is sanitised to ``_`` by ``_retry_path`` → ``7__onfail_PRCI``.
    retry_marker = tmp_path / "retries" / "7__onfail_PRCI"
    assert slot_marker.exists()
    assert retry_marker.exists()
    # A stale queue marker coexists (the late-completing abandoned launch).
    store.enqueue_launch(
        7, {"item_id": "PVTI_7", "stage": "InProgress", "prompt": "/x", "enqueued_at": 1000.0}
    )
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        _drain_queue(deps, config, executor, now=1000.0)

    # The redundant queue marker is cleared and nothing was re-dispatched ...
    deps.sessions.launch.assert_not_called()  # type: ignore[attr-defined]
    assert store.dequeue_pending() == ()
    # ... but the LIVE ticket's slot + fix-CI retry budget SURVIVE (with the bug they were gone).
    assert slot_marker.exists()
    assert retry_marker.exists()
    assert store.bump_retry(7, "onfail:PRCI") == 2  # the counter was NOT reset to 0


def test_fresh_direct_launch_clears_pre_seeded_queue_marker(tmp_path: Path) -> None:
    """13.7 #4: a fresh successful DIRECT launch clears a coexisting stale queue marker.

    A stale ``queue/ticket-7`` marker is pre-seeded; a direct LAUNCH for #7 succeeds. The
    cap-gate success path clears the marker so the same-tick drain (or a later sweep) cannot
    ALSO re-dispatch the now-running ticket — closing the double-launch window.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    store, deps = _real_store_full_tick_deps(reader, tmp_path)
    # Pre-seed a stale queue marker for the same issue.
    store.enqueue_launch(
        7, {"item_id": "PVTI_7", "stage": "InProgress", "prompt": "/x", "enqueued_at": 1.0}
    )
    assert store.dequeue_pending() == (7,)
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), concurrency_cap=3, transitions=_tick_whitelist()
    )
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    result, _ = tick(deps, config, state)

    # The launch ran (under the cap) ...
    deps.sessions.launch.assert_called_once()  # type: ignore[attr-defined]
    assert result.actions_executed == 1
    # ... and the stale marker was superseded (cleared) by the fresh launch.
    assert store.dequeue_pending() == ()


def test_noop_pull_back_clears_queue_marker(tmp_path: Path) -> None:
    """13.7 #5: an operator pull-back (agent→inert NOOP) clears the queue marker.

    A queued card the operator drags to an inert column produces a NOOP. The NOOP branch clears
    the queue marker so a later ``_drain_queue`` sweep does not resurrect the withdrawn ticket.
    """
    # InProgress (agent) → Done (inert) is a NOOP-forward move.
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    store, deps = _real_store_full_tick_deps(reader, tmp_path)
    # The ticket is queued (e.g. it was diverted at cap earlier).
    store.enqueue_launch(
        7, {"item_id": "PVTI_7", "stage": "InProgress", "prompt": "/x", "enqueued_at": 1.0}
    )
    assert store.dequeue_pending() == (7,)
    config = TickConfig(columns=load_columns(_COLUMNS_YAML), transitions=_tick_whitelist())
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _ = tick(deps, config, state)

    # Nothing launched (Done is inert), and the queue marker was cleared on the pull-back.
    deps.sessions.launch.assert_not_called()  # type: ignore[attr-defined]
    assert result.actions_executed == 0
    assert store.dequeue_pending() == ()


# ---------------------------------------------------------------------------
# Gate 13.6: durable per-item move rate-limit gate (feeds the §6 park-in-Blocked
# backstop — durable history recorded on disk, gated to not double-record past cap)
# ---------------------------------------------------------------------------


def _real_store_reap_deps(
    tmp_path: Path,
    *,
    now: float = 10000.0,
) -> tuple[FsStateStore, Deps, MagicMock, MagicMock, MagicMock]:
    """Build a :class:`Deps` with a real :class:`FsStateStore` and mock adapters for reap tests.

    The real store exercises the on-disk durable move history path (gate 13.6). The
    board_writer, workspace, and sessions are mocks so their side-effects don't need real
    tmux/git/GitHub — only the store's ``record_move_for_item`` / ``move_count_for_item_last_hour``
    path is tested against the filesystem.

    Args:
        tmp_path: The pytest tmp_path fixture — the store root.
        now: The wall-clock time the mocked clock returns.

    Returns:
        A ``(store, deps, board_writer, workspace, sessions)`` tuple so each test can
        override mock behaviour (e.g. ``release_slot`` no-op for the over-cap tests).
    """
    store = FsStateStore(tmp_path)
    board_writer = MagicMock()
    workspace = MagicMock()
    sessions = MagicMock()
    sessions.is_alive.return_value = True
    clock = MagicMock()
    clock.now.return_value = now
    deps = Deps(
        board_writer=board_writer,
        board_reader=MagicMock(),
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=MagicMock(),
    )
    return store, deps, board_writer, workspace, sessions


def _reap_config(**kw: object) -> TickConfig:
    """Build a :class:`TickConfig` for the reap step with sensible defaults.

    Keyword arguments override individual fields (e.g. ``move_rate_limit_per_hour=2``).
    """
    defaults = {
        "columns": load_columns(_COLUMNS_YAML),
        "heartbeat_ttl": 1800.0,
        "action_timeout": 120.0,
        "blocked_column": "Blocked",
        "move_rate_limit_per_hour": 3,
    }
    defaults.update(kw)
    return TickConfig(**defaults)  # type: ignore[arg-type]


class TestReapDurableMoveRateLimit:
    """Tests for the durable per-item move rate-limit gate (gate 13.6 / DESIGN §6)."""

    def test_reap_records_move_into_durable_history(self, tmp_path: Path) -> None:
        """Two reaps within the hour ACCUMULATE in the durable history → count == 2.

        The reaper's own AUTO/bot move feeds the on-disk counter (``record_move_for_item``)
        — NOT just the volatile in-memory ``antiloop`` — so the §6 per-hour cap survives a
        daemon restart (the headline fix). Crucially, the reaper now constructs
        ``TeardownAction(keep_budgets=True)`` (13.8), so its teardown PRESERVES
        ``moves/<issue>.json`` — the count accumulates across reaps instead of perpetually
        resetting to 1 (the 13.7 dormant defect: purge_ticket wiped the history one step
        BEFORE the same reap re-wrote a single entry).
        """
        store, deps, _bw, _ws, _sess = _real_store_reap_deps(tmp_path, now=10000.0)
        _sess.is_alive.return_value = (
            False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
        )

        def _save_stale() -> None:
            """Re-persist the stale running ticket so the reaper picks it up again."""
            store.save(
                TicketState(
                    issue_number=7,
                    item_id="PVTI_7",
                    session_id="ticket-7",
                    status=TicketStatus.RUNNING,
                    heartbeat=0.0,
                )
            )

        config = _reap_config()

        antiloop = AntiLoopState()
        with ThreadPoolExecutor(max_workers=1) as executor:
            # First reap: tears the stale agent down (keep_budgets=True preserves moves/),
            # then records its move-to-Blocked into the durable history → count 1.
            _save_stale()
            reaped1, _relaunched1, errors1, antiloop = _reap_stale_agents(
                deps, config, executor, now=10000.0, antiloop=antiloop
            )
            # Re-save the ticket stale and reap AGAIN within the same hour. Because the
            # teardown preserves moves/, the second move-to-Blocked is appended on top of the
            # first → the durable count accumulates to 2 (not reset to 1).
            _save_stale()
            reaped2, _relaunched2, errors2, antiloop = _reap_stale_agents(
                deps, config, executor, now=10000.0, antiloop=antiloop
            )

        # Both reaps completed cleanly.
        assert (reaped1, errors1) == (1, 0)
        assert (reaped2, errors2) == (1, 0)
        # The durable on-disk history ACCUMULATED both reaper moves within the hour → 2.
        assert store.move_count_for_item_last_hour(7, now=10000.0) == 2
        # Defense-in-depth: the in-memory antiloop was ALSO fed (not replaced).
        assert ("PVTI_7", "Blocked") in antiloop.recent_targets

    def test_rate_limited_ticket_not_double_recorded(self, tmp_path: Path) -> None:
        """A ticket already at cap is NOT double-recorded by a further reap (counter stays at cap).

        Seed the durable moves file to the cap (3), then reap once more: the reaper's
        move-to-Blocked still happens (parking in Blocked IS the §6 remedy), but the
        ``record_move_for_item`` call is SKIPPED because the ticket is already at/over its
        hourly AUTO-move budget — the counter must not run away past the cap (port of OLD's
        "park instead of acting + stop feeding the loop", runner.py:504-518).
        """
        store, deps, _bw, _ws, _sess = _real_store_reap_deps(tmp_path, now=10000.0)
        _sess.is_alive.return_value = (
            False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
        )
        store.save(_stale_running())
        # Seed the durable history to the cap (3 moves within the last hour).
        for seed_ts in (9000.0, 9300.0, 9600.0):
            store.record_move_for_item(7, now=seed_ts)
        # NO stub: the reaper's TeardownAction now passes keep_budgets=True (13.8), so the REAL
        # production ``purge_ticket`` runs but PRESERVES the seeded moves/<issue>.json history.
        # The gate then sees 3 >= cap(3) and SKIPS record_move_for_item, so the count stays 3 —
        # asserted against the un-stubbed production path (the 13.7 test stubbed purge to pass).
        config = _reap_config(move_rate_limit_per_hour=3)

        with ThreadPoolExecutor(max_workers=1) as executor:
            reaped, _relaunched, errors, antiloop = _reap_stale_agents(
                deps,
                config,
                executor,
                now=10000.0,
                antiloop=AntiLoopState(),
            )

        assert reaped == 1
        # The durable count stayed at the cap — NOT cap+1. The gate read the on-disk
        # count BEFORE recording the new move, saw 3 >= 3 (rate-limited), and skipped the
        # ``record_move_for_item`` call so the counter did not run away.
        assert store.move_count_for_item_last_hour(7, now=10000.0) == 3
        # The in-memory antiloop was still fed (defense-in-depth survives).
        assert ("PVTI_7", "Blocked") in antiloop.recent_targets

    def test_gate_reads_config_move_rate_limit_per_hour(self, tmp_path: Path) -> None:
        """The rate-limit gate reads ``config.move_rate_limit_per_hour`` — tunable, not hard-pinned.

        Set the cap to 2 (not the default 10), seed 2 durable moves, and assert a third reap
        does NOT push the count past 2. Proves the gate respects the board-level knob (13.4)
        rather than a hard-coded value — the tunability the audit flagged as lost.
        """
        store, deps, _bw, _ws, _sess = _real_store_reap_deps(tmp_path, now=10000.0)
        _sess.is_alive.return_value = (
            False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
        )
        store.save(_stale_running())
        # Seed 2 moves (the cap) within the rate window.
        for seed_ts in (9000.0, 9500.0):
            store.record_move_for_item(7, now=seed_ts)
        # NO stub: the reaper's TeardownAction passes keep_budgets=True (13.8), so the REAL
        # purge_ticket preserves the seeded moves/ history; the gate then sees 2 >= cap(2) and
        # skips the record — the count stays 2 against the un-stubbed production path.
        config = _reap_config(move_rate_limit_per_hour=2)

        with ThreadPoolExecutor(max_workers=1) as executor:
            reaped, _relaunched, errors, _ = _reap_stale_agents(
                deps,
                config,
                executor,
                now=10000.0,
                antiloop=AntiLoopState(),
            )

        assert reaped == 1
        # Count stays at 2 (the configured cap), not 3, not 10 (the default).
        assert store.move_count_for_item_last_hour(7, now=10000.0) == 2

    def test_durable_count_survives_fresh_store_instance(self, tmp_path: Path) -> None:
        """The durable per-hour move count survives a fresh ``FsStateStore`` over the same root.

        This is the headline §6 fix: the on-disk ``moves/<issue>.json`` history persists
        across a daemon restart, so the per-hour cap holds — unlike the volatile in-memory
        ``antiloop`` counter which ``loop.py`` re-initialises empty at every startup.
        """
        store, deps, _bw, _ws, _sess = _real_store_reap_deps(tmp_path, now=10000.0)
        _sess.is_alive.return_value = (
            False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
        )
        stale = TicketState(
            issue_number=7,
            item_id="PVTI_7",
            session_id="ticket-7",
            status=TicketStatus.RUNNING,
            heartbeat=0.0,
        )
        store.save(stale)
        config = _reap_config()

        with ThreadPoolExecutor(max_workers=1) as executor:
            _reap_stale_agents(
                deps,
                config,
                executor,
                now=10000.0,
                antiloop=AntiLoopState(),
            )

        # The first store recorded 1 move on disk. Create a FRESH store instance over the
        # SAME root — simulating a daemon restart.
        fresh_store = FsStateStore(tmp_path)
        # The durable count survived the "restart": the moves file is still there.
        assert fresh_store.move_count_for_item_last_hour(7, now=10000.0) == 1

    def test_antiloop_still_fed_regression(self, tmp_path: Path) -> None:
        """The in-memory ``antiloop`` guard is STILL fed alongside the durable history.

        Defense-in-depth (DESIGN §6): the durable on-disk counter is the primary backstop,
        but the volatile antiloop guard is NOT replaced — both are fed on each reap move.
        This is a regression test proving the existing behavior (tested by
        ``test_reap_records_its_own_move_into_antiloop_state``) is preserved.
        """
        store, deps, _bw, _ws, _sess = _real_store_reap_deps(tmp_path, now=10000.0)
        _sess.is_alive.return_value = (
            False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
        )
        store.save(_stale_running())
        config = _reap_config()

        with ThreadPoolExecutor(max_workers=1) as executor:
            _reaped, _relaunched, _errors, antiloop = _reap_stale_agents(
                deps,
                config,
                executor,
                now=10000.0,
                antiloop=AntiLoopState(),
            )

        # The in-memory antiloop guard was fed — the (item_id, target) marker is present
        # AND the dedup guard recognises the move as recent (same behaviour as the existing
        # ``test_reap_records_its_own_move_into_antiloop_state``, which uses a mock store).
        assert ("PVTI_7", "Blocked") in antiloop.recent_targets
        assert is_blocked(antiloop, "PVTI_7", "Blocked", now=10000.0) is True


class TestKeepBudgetsLifecycle:
    """Real-fs tests for the 13.8 per-issue budget lifecycle (preserve vs full purge).

    The per-issue budgets (``moves/<issue>.json`` rate-limit history +
    ``retries/<issue>__*`` fix-CI counters) must SURVIVE a reap and a normal session-end (the
    ticket may continue), and be torn down ONLY on a true abandonment (Cancel / reset). These
    tests exercise the REAL :class:`FsStateStore` end-to-end — no mock can mask the marker
    purge (the 13.7 false-confidence MagicMock lesson).
    """

    @staticmethod
    def _seed_budgets(store: FsStateStore, issue: int = 7) -> None:
        """Seed BOTH per-issue budget markers so a teardown's effect is observable."""
        store.record_move_for_item(issue, now=10000.0)
        store.bump_retry(issue, "onfail:Review")

    @staticmethod
    def _budgets_present(store: FsStateStore, issue: int = 7) -> bool:
        """Return whether BOTH budget markers still exist for *issue*."""
        moves_present = store.move_count_for_item_last_hour(issue, now=10000.0) > 0
        retries_present = any((store.root / "retries").glob(f"{issue}__*"))
        return moves_present and retries_present

    def test_reaper_teardown_preserves_budgets(self, tmp_path: Path) -> None:
        """A reaper stale-agent teardown PRESERVES ``moves/`` + ``retries/`` (keep_budgets=True)."""
        store, deps, _bw, _ws, _sess = _real_store_reap_deps(tmp_path, now=10000.0)
        _sess.is_alive.return_value = (
            False  # DEAD session → reaches the reap path (Approach A reaps only dead sessions)
        )
        store.save(_stale_running())
        self._seed_budgets(store)

        with ThreadPoolExecutor(max_workers=1) as executor:
            reaped, _relaunched, errors, _ = _reap_stale_agents(
                deps, _reap_config(), executor, now=10000.0, antiloop=AntiLoopState()
            )

        assert (reaped, errors) == (1, 0)
        # The runtime state record was torn down (the reap stops aging the ticket) ...
        assert store.load(7) is None
        # ... but BOTH per-issue budgets SURVIVED the reap (the durable rate-limit accumulates).
        assert self._budgets_present(store) is True

    def test_cancel_default_teardown_purges_budgets(self, tmp_path: Path) -> None:
        """A DEFAULT TeardownAction (Cancel path, keep_budgets=False) PURGES both budgets."""
        store, deps, _bw, _ws, _sess = _real_store_reap_deps(tmp_path, now=10000.0)
        store.save(_stale_running())
        self._seed_budgets(store)

        # The bare TeardownAction is the Cancel path — the ticket is abandoned, full purge.
        TeardownAction(
            ticket=Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="")
        ).execute(deps)

        # Both per-issue budgets were dropped (clean slate for a future issue reuse).
        assert store.move_count_for_item_last_hour(7, now=10000.0) == 0
        assert not any((store.root / "retries").glob("7__*"))

    def test_session_end_preserves_budgets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A normal ``kanban session-end`` PRESERVES ``moves/`` + ``retries/`` (keep_budgets=True)."""
        from kanbanmate.bin import kanban_session_end

        store = FsStateStore(tmp_path)
        store.save(_stale_running())
        self._seed_budgets(store)
        # Route session-end through the real store; stub out the GitHub finalize wiring so the
        # leaf never touches the network (the budget preservation is store-side).
        monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
        monkeypatch.setattr(kanban_session_end, "_resolve_entry", lambda: MagicMock())
        monkeypatch.setattr(kanban_session_end, "load_token", lambda *a, **k: "tok")
        monkeypatch.setattr(kanban_session_end, "GithubClient", lambda *a, **k: MagicMock())
        monkeypatch.setattr(kanban_session_end, "upsert_stage_comment", MagicMock())

        assert kanban_session_end.main(["7"]) == 0

        # The runtime state record was removed (slot freed, breadcrumb consumed) ...
        assert store.load(7) is None
        # ... but the per-issue §6 + fix-CI budgets SURVIVED the inter-session idle.
        assert self._budgets_present(store) is True


# ---------------------------------------------------------------------------
# Phase 15.6: script routing EXECUTION at the tick level (on_fail / advance:auto
# / fix-CI cap / launch GATE). The routing logic itself is unit-tested in
# test_script_route.py; these assert the tick WIRES it (script run → route →
# baseline / antiloop / errors set, gate veto blocks the launch).
# ---------------------------------------------------------------------------

# A board with a Blocked column + a script-routing whitelist: a fix-CI loop (PRCI→InProgress,
# advance:auto:PRCI) so a SUCCESS re-fires, an on_fail:move loop (Design→PRCI, on_fail:move:Design)
# so a FAILURE bounces + is fix-CI-capped, and a prompt+script GATE transition (Backlog→InProgress).
_ROUTING_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: Design
    name: Design
  - key: InProgress
    name: In Progress
  - key: PRCI
    name: PR CI
  - key: Cancel
    name: Cancel
    action: teardown
  - key: Blocked
    name: Blocked
  - key: Done
    name: Done
"""

_ROUTING_WHITELIST_YAML = """
project: owner/repo
defaults:
  concurrency_cap: 3
  move_rate_limit_per_hour: 10
transitions:
  - from: Design
    to: PRCI
    script: bin/check-pr-ready.sh
    on_fail: "move:Design"
    advance: stop
  - from: PRCI
    to: InProgress
    prompt: "/implement:phase {{code}} fix CI: {{script_output}}"
    profile: dev
    permission_mode: auto
    script: bin/check-merge-ready.sh
    on_fail: "move:PRCI"
    advance: stop
"""


def _routing_config() -> TickConfig:
    """Build a :class:`TickConfig` from the routing board + whitelist (Blocked column present)."""
    return TickConfig(
        columns=load_columns(_ROUTING_COLUMNS_YAML),
        transitions=load_transitions(_ROUTING_WHITELIST_YAML),
    )


def test_run_script_failure_routes_on_fail_move_and_baseline_re_fires() -> None:
    """A failing RUN_SCRIPT routes its ``on_fail:move`` bounce; baseline stays the script column.

    Design→PRCI (script-only) fails (exit 1, count 1 < cap). The card is bounced to Design (the
    on_fail target) and the next-tick baseline is the SCRIPT column (PRCI) so the diff re-fires the
    fix-CI loop. The failing output is persisted for the {{script_output}} consumer (15.7).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="PRCI")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/x"
    m.workspace.run_transition_script.return_value = (1, "CI red log")
    m.store.bump_retry.return_value = 1  # first failure → within cap
    m.store.load.return_value = None  # no LEFT state to finalize
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _routing_config(), state)

    m.sessions.launch.assert_not_called()
    # The on_fail bounce moved the card to Design (the on_fail:move target).
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Design")
    m.store.bump_retry.assert_called_once_with(7, "onfail:PRCI")
    # The failing output was stashed for the fix-CI {{script_output}} consumer (15.7).
    m.store.save_script_output.assert_called_once_with(7, "CI red log")
    assert result.actions_executed == 1
    assert result.errors == 0
    # Baseline = the SCRIPT column (PRCI) so the next diff re-fires (PRCI → Design) — the fix-CI loop.
    assert next_state.columns_by_item["PVTI_7"] == "PRCI"


def test_run_script_failure_over_cap_parks_in_blocked() -> None:
    """The (cap+1)-th RUN_SCRIPT failure parks the card in Blocked; baseline = Blocked (no re-fire)."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="PRCI")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/x"
    m.workspace.run_transition_script.return_value = (1, "still red")
    m.store.bump_retry.return_value = 3  # 3 > _FIXCI_CAP(2) → park Blocked
    m.store.load.return_value = None
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _routing_config(), state)

    # Parked in Blocked (the configured blocked_column), counter reset, recap comment posted.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Blocked")
    m.store.reset_retry.assert_any_call(7, "onfail:PRCI")
    m.board_writer.comment.assert_called_once()
    assert result.actions_executed == 1
    # Baseline = Blocked (bookkeeping; the diff does NOT re-fire from here).
    assert next_state.columns_by_item["PVTI_7"] == "Blocked"


def test_run_script_success_advance_auto_re_fires_and_clears_output() -> None:
    """A successful RUN_SCRIPT with ``advance:auto`` moves to the target but baseline re-fires.

    Reuses the two-agent whitelist where Design→InProgress is a script-only row, but here we give it
    an advance:auto via a custom config below. We assert: move to the auto target, baseline stays the
    script column (re-fire), the success path CLEARS the stashed output.
    """
    columns = load_columns(_ROUTING_COLUMNS_YAML)
    whitelist = load_transitions(
        """
project: owner/repo
transitions:
  - from: Design
    to: PRCI
    script: bin/check-pr-ready.sh
    on_fail: "move:Design"
    advance: "auto:InProgress"
"""
    )
    config = TickConfig(columns=columns, transitions=whitelist)

    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="PRCI")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/x"
    m.workspace.run_transition_script.return_value = (0, "all green")
    m.store.load.return_value = None
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    result, next_state = tick(m.deps, config, state)

    # The success auto-move advanced the card to the display NAME "In Progress" (defect 2: the
    # advance:auto:InProgress directive KEY resolves to the board's display NAME for move_card).
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "In Progress")
    m.store.record_move_for_item.assert_called_once_with(7, now=1000.0)
    # The success path reset the fix-CI counter and CLEARED the stashed output.
    m.store.reset_retry.assert_called_once_with(7, "onfail:PRCI")
    m.store.save_script_output.assert_called_once_with(7, "")
    assert result.actions_executed == 1
    # Baseline = the SCRIPT column (PRCI), NOT InProgress, so the next diff re-fires (PRCI→InProgress).
    assert next_state.columns_by_item["PVTI_7"] == "PRCI"


def test_run_script_persisted_output_round_trips_with_real_store(tmp_path: Path) -> None:
    """A failing RUN_SCRIPT persists output via the REAL store; success clears it (load round-trip)."""
    store = FsStateStore(root=tmp_path)
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="PRCI")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    deps = Deps(
        board_writer=m.board_writer,
        board_reader=reader,
        workspace=m.workspace,
        sessions=m.sessions,
        store=store,
        clock=m.clock,
        pull_requests=MagicMock(),
    )
    m.workspace.discover_branch.return_value = "feat/x"
    m.workspace.run_transition_script.return_value = (1, "the failing CI output")
    state = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-0")

    tick(deps, _routing_config(), state)
    # The failing output was persisted and is loadable (the 15.7 consumer reads exactly this).
    assert store.load_script_output(7) == "the failing CI output"

    # Now a SUCCESS clears it.
    m.workspace.run_transition_script.return_value = (0, "")
    reader2 = _FakeBoardReader("probe-2", _snapshot(ticket))
    deps2 = Deps(
        board_writer=m.board_writer,
        board_reader=reader2,
        workspace=m.workspace,
        sessions=m.sessions,
        store=store,
        clock=m.clock,
        pull_requests=MagicMock(),
    )
    state2 = PersistedState(columns_by_item={"PVTI_7": "Design"}, last_probe="probe-1")
    tick(deps2, _routing_config(), state2)
    assert store.load_script_output(7) == ""


def test_launch_gate_failure_vetoes_launch_and_routes_on_fail() -> None:
    """A LAUNCH with a NON-ZERO gate script does NOT launch and routes its on_fail (no agent).

    PRCI→InProgress is a prompt+script gate (on_fail:move:PRCI). The gate fails (exit 1) → VETO: no
    tmux launch, no slot reserved, no running state. The on_fail bounce moves the card to PRCI; the
    baseline stays the script column so the fix-CI loop re-fires.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/x"
    m.workspace.run_transition_script.return_value = (1, "gate failed")
    m.store.bump_retry.return_value = 1
    m.store.load.return_value = None
    state = PersistedState(columns_by_item={"PVTI_7": "PRCI"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _routing_config(), state)

    # VETO: no agent launched, no slot reserved, no running state saved.
    m.sessions.launch.assert_not_called()
    m.store.reserve_slot.assert_not_called()
    m.store.save.assert_not_called()
    # The gate's on_fail:move:PRCI bounced the card to the display NAME "PR CI" (defect 2: the
    # directive KEY "PRCI" resolves to its board display NAME for move_card). The gate transition's
    # destination is InProgress; on_fail moves to PRCI's display name.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "PR CI")
    m.store.bump_retry.assert_called_once_with(7, "onfail:InProgress")
    assert result.actions_executed == 1
    # Baseline = the script column (InProgress, the gate transition's destination) so it re-fires.
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_launch_gate_success_proceeds_to_launch_and_persists_output() -> None:
    """A LAUNCH with a ZERO gate script proceeds to launch and persists the gate output (15.7)."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="My Feature", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/x"
    m.workspace.run_transition_script.return_value = (0, "gate output for prompt")
    m.store.load.return_value = None
    state = PersistedState(columns_by_item={"PVTI_7": "PRCI"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _routing_config(), state)

    # The gate passed → the agent IS launched, the slot reserved, running state saved.
    m.sessions.launch.assert_called_once()
    m.store.reserve_slot.assert_called_once()
    m.store.save.assert_called_once()
    # The gate success reset the loop counter + persisted the gate output (the {{script_output}} value).
    m.store.reset_retry.assert_called_once_with(7, "onfail:InProgress")
    m.store.save_script_output.assert_called_once_with(7, "gate output for prompt")
    assert result.actions_executed == 1
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_launch_gate_creates_worktree_before_running_gate_script() -> None:
    """The launch-gate creates the worktree BEFORE the gate script (PoC bug #1 ordering).

    The gate script's ``run_check_script`` → ``discover_branch`` runs ``git -C <worktree>
    rev-parse`` with ``check=True``, which RAISES on a not-yet-created worktree. The previous
    MagicMock workspace returned a branch unconditionally and so MASKED the ordering bug. Here a
    faithfully-faked workspace makes ``discover_branch`` RAISE unless ``ensure_worktree`` was
    called for that ticket FIRST — so a regression (gate before worktree) raises inside the gate,
    the watchdog returns ``ok_gate=False``, the launch is vetoed and never proceeds. With the fix
    in place the worktree exists, ``discover_branch`` succeeds, the gate passes and the agent
    launches.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="My Feature", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # Order-aware workspace: track which tickets had their worktree ensured, and make the gate's
    # branch discovery depend on that ordering (the real adapter's ``git -C <missing-dir>`` failure).
    ensured: set[int] = set()

    def _ensure_worktree(ticket_number: int, *, base: str) -> str:  # noqa: ARG001
        ensured.add(ticket_number)
        return f"/tmp/wt/ticket-{ticket_number}"

    def _discover_branch(ticket_number: int) -> str:
        # A non-existent worktree → ``git -C <dir> rev-parse`` (check=True) raises. Replicate that
        # so the gate FAILS when ``ensure_worktree`` did NOT run first (the regression we guard).
        if ticket_number not in ensured:
            raise subprocess.CalledProcessError(128, ["git", "rev-parse"])
        return "feat/x"

    m.workspace.ensure_worktree.side_effect = _ensure_worktree
    m.workspace.discover_branch.side_effect = _discover_branch
    m.workspace.run_transition_script.return_value = (0, "gate output for prompt")
    m.store.load.return_value = None
    state = PersistedState(columns_by_item={"PVTI_7": "PRCI"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _routing_config(), state)

    # The worktree was ensured BEFORE the gate ran → discover_branch succeeded → gate passed →
    # the agent launched. A regression (gate before worktree) would have raised in discover_branch,
    # vetoed the launch (ok_gate=False) and left ``sessions.launch`` uncalled.
    m.workspace.ensure_worktree.assert_any_call(7, base="main")
    m.sessions.launch.assert_called_once()
    m.store.save_script_output.assert_called_once_with(7, "gate output for prompt")
    assert result.actions_executed == 1
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


# ---------------------------------------------------------------------------
# Genesis #16 (rate-limit counter feeds + BLOCK-as-comment) and #23 (re-tick → NOOP)
# ---------------------------------------------------------------------------


def test_daemon_on_fail_move_feeds_rate_limit_counter_but_launch_does_not() -> None:
    """A daemon AUTO/bot move feeds ``record_move_for_item``; a human/agent launch does NOT (#16).

    The PoC counted ONLY auto/bot moves toward the per-issue rate limit. Here a failing RUN_SCRIPT
    routes its within-cap ``on_fail:move`` bounce — a daemon-issued AUTO move that MUST feed the
    durable counter. The tick never launches an agent on this path, so the counter sees ONLY the
    autonomous bounce (a human/agent LaunchAction is never counted).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="My Feature", column_key="PRCI")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.workspace.discover_branch.return_value = "feat/genesis"
    m.workspace.run_transition_script.return_value = (1, "CI red")  # failure → on_fail:move
    m.store.bump_retry.return_value = 1  # under _FIXCI_CAP=2 → within-cap TRIGGERING bounce
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    tick(m.deps, _fixci_loop_config(), state)

    # The daemon's AUTO/bot bounce fed the durable per-issue rate-limit counter.
    m.store.record_move_for_item.assert_called_once_with(7, now=1000.0)
    # No agent launched on this tick → the counter saw ONLY the autonomous move, not a launch.
    m.sessions.launch.assert_not_called()


def test_rate_limit_tripped_launch_is_block_comment_not_board_park() -> None:
    """A tripped rate limit downgrades the launch to a BLOCK COMMENT — NOT a board park (#16).

    The in-memory anti-loop rate limit trips when the ticket has already made ``rate_limit`` AUTO
    moves in the window. NEW surfaces this as a BlockAction comment and does NOT move the card to a
    Blocked column (the diff baseline is the primary idempotence net, DESIGN §6; the backstop is
    secondary defense-in-depth that comments, never parks).
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # Seed the in-memory net with rate_limit (10) recent AUTO moves so the per-ticket rate guard
    # trips on the next launch into InProgress (DESIGN §6 backstop).
    seeded = AntiLoopState()
    for _ in range(10):
        seeded = record_move(seeded, "PVTI_7", "Done", now=999.0)
    state = PersistedState(
        columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0", antiloop=seeded
    )

    result, _ = tick(m.deps, _config(), state)

    # The launch was downgraded to a BLOCK: a comment was posted and NO agent started.
    m.sessions.launch.assert_not_called()
    m.board_writer.comment.assert_called_once()
    assert "blocked" in m.board_writer.comment.call_args.args[1]
    # Emphatically NOT a board park: the daemon did not move the card to a Blocked column.
    m.board_writer.move_card.assert_not_called()
    assert result.actions_executed == 1


def test_idempotent_re_tick_yields_noop_not_skip() -> None:
    """An already-processed move re-ticks to a NOOP, not a distinct ``skip`` verdict (#23).

    The PoC's 9-kind ``skip`` re-homes to the tick's diff baseline: a second tick whose baseline
    already records the card's column produces NO diff, so the move is NOT re-decided and NO action
    runs — the idempotent re-tick is a NOOP (no re-launch), pinning the 9→5 reorganisation.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # The baseline ALREADY records the card in InProgress (the move was processed on a prior tick),
    # and the probe token differs so a snapshot IS taken — but the diff finds no column change.
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    # No diff → no decided action → no re-launch (the PoC `skip` is this NOOP, #23).
    m.sessions.launch.assert_not_called()
    assert result.actions_executed == 0
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


# ---------------------------------------------------------------------------
# Rolling status-update reporter wiring (phase-24 §24.3): a THIN fail-soft call.
# ---------------------------------------------------------------------------


def test_status_reporter_invoked_once_per_tick() -> None:
    """The rolling status-update reporter is invoked exactly once at the end of every tick."""
    import dataclasses
    from unittest.mock import MagicMock

    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    # Pin the status-state reads the reporter touches so the spy path runs cleanly (the bare mock
    # store would otherwise make read_status_events return a non-iterable mock — swallowed, but we
    # want the reporter to reach a post so the spy is exercised).
    m.store.read_status_events.return_value = ()
    m.store.get_status_body_hash.return_value = None
    m.store.get_status_update_id.return_value = None
    spy = MagicMock()
    spy.create_status_update.return_value = "PVTSU_1"
    deps = dataclasses.replace(m.deps, status_reporter=spy, project_id="PVT_proj")
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    tick(deps, _config(), state)

    # The body changed from the (None) stored hash → exactly one create this tick.
    assert spy.create_status_update.call_count == 1


def test_tick_succeeds_if_status_reporter_raises() -> None:
    """A reporter that raises must NOT break the tick (the reporter is wholly fail-soft)."""
    import dataclasses
    from unittest.mock import MagicMock

    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    reader = _FakeBoardReader("probe-1", _snapshot(ticket))
    m = _mocks(reader)
    m.store.read_status_events.return_value = ()
    m.store.get_status_body_hash.return_value = None
    m.store.get_status_update_id.return_value = None
    boom = MagicMock()
    boom.create_status_update.side_effect = RuntimeError("status API down")
    deps = dataclasses.replace(m.deps, status_reporter=boom, project_id="PVT_proj")
    state = PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")

    # The launch still happened and the tick returned normally despite the reporter blowing up.
    result, _ = tick(deps, _config(), state)
    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1


# ---------------------------------------------------------------------------
# Wrong-stage relaunch guard (engine fix b): a DEAD-session state whose stage no longer matches the
# card's current column is PURGED instead of relaunched onto the wrong stage (live helm #5).
# ---------------------------------------------------------------------------


def test_reaper_purges_stale_wrong_stage_state_instead_of_relaunching() -> None:
    """A dead-session state whose stage ≠ the card's current column is PURGED, not relaunched.

    helm #5: the card advanced Brainstorming→Spec but the old Brainstorming running-state lingered;
    relaunching it re-delivered the BRAINSTORM prompt onto a Spec card. With the card's current column
    known (≠ state.stage), the reaper purges the stale state + posts a signal — no relaunch, no park.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = False  # DEAD session
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="Brainstorming",
        profile="docs",
        retries=0,
    )
    m.store.list_running.return_value = (stale,)

    with ThreadPoolExecutor(max_workers=1) as executor:
        reaped, relaunched, errors, _antiloop = _reap_stale_agents(
            m.deps,
            _config(),
            executor,
            10_000.0,
            AntiLoopState(),
            current_columns={"PVTI_7": "Spec"},  # the card has moved on to Spec
        )

    # No wrong-stage relaunch, no Block-park; the stale state is purged + a one-line signal posted.
    m.sessions.launch.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    assert m.board_writer.comment.called  # the re-fire signal
    assert reaped == 0
    assert relaunched == 0


def test_reaper_relaunches_when_stage_matches_current_column() -> None:
    """When the card's column still matches the agent's stage, the dead session relaunches normally.

    The wrong-stage guard must NOT fire when stage == column (a genuine crash of the correct-stage
    agent) — it relaunches as usual.
    """
    reader = _FakeBoardReader("probe-1", _snapshot())
    m = _mocks(reader, now=10_000.0)
    m.sessions.is_alive.return_value = False  # DEAD session
    m.sessions.launch.return_value = "newsess"
    stale = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="InProgress",
        profile="dev",
        retries=0,
    )
    m.store.list_running.return_value = (stale,)

    with ThreadPoolExecutor(max_workers=1) as executor:
        reaped, relaunched, _errors, _antiloop = _reap_stale_agents(
            m.deps,
            _config(),
            executor,
            10_000.0,
            AntiLoopState(),
            current_columns={"PVTI_7": "InProgress"},  # column still matches the stage
        )

    # Normal relaunch — not purged as wrong-stage.
    m.sessions.launch.assert_called_once()
    assert relaunched == 1
    assert reaped == 0
