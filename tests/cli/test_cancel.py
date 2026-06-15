"""Tests for :mod:`kanbanmate.cli.cancel` — the manual ``kanban cancel <issue>`` teardown.

``cancel`` must reuse the app-layer :class:`~kanbanmate.app.actions.TeardownAction` (not
re-implement teardown), so the assertions check the *effects* of that action against an injected
:class:`~kanbanmate.app.actions.Deps`: the tmux session is killed (only when alive), the worktree
is force-removed, the local branch is force-deleted, the slot is released, the open PR is closed
(remote branch kept), and a recap comment is posted — the FULL Cancel-teardown parity (DESIGN §8.2)
inherited by the manual path. No real tmux/git/network is touched — every port is a ``MagicMock``.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from kanbanmate.app.actions import Deps
from kanbanmate.cli.cancel import build_cancel_ticket, cancel
from kanbanmate.ports.store import TicketState, TicketStatus


@dataclass
class _Mocks:
    """The mocks behind a cancel :class:`Deps`, kept as ``MagicMock`` for assertion under mypy."""

    board_writer: MagicMock
    workspace: MagicMock
    sessions: MagicMock
    store: MagicMock
    pull_requests: MagicMock
    deps: Deps


def _mocks(*, alive: bool, loaded_state: TicketState | None) -> _Mocks:
    """Build a :class:`_Mocks` bundle wiring mocks into a :class:`Deps` for the cancel path.

    Args:
        alive: What ``sessions.is_alive`` returns (governs whether ``kill`` is called).
        loaded_state: What ``store.load`` returns (supplies the ``item_id``).

    Returns:
        A :class:`_Mocks` exposing both the individual mocks and the assembled :class:`Deps`.
    """
    board_writer = MagicMock()
    workspace = MagicMock()
    # A real feature branch so the manual cancel exercises the branch -D + PR-close parity.
    workspace.discover_branch.return_value = "feat/genesis"
    agent_sessions = MagicMock()
    agent_sessions.is_alive.return_value = alive
    store = MagicMock()
    store.load.return_value = loaded_state
    clock = MagicMock()
    pull_requests = MagicMock()
    pull_requests.close_open_pr_for_branch.return_value = 123
    deps = Deps(
        board_writer=board_writer,
        board_reader=MagicMock(),
        workspace=workspace,
        sessions=agent_sessions,
        store=store,
        clock=clock,
        pull_requests=pull_requests,
    )
    return _Mocks(board_writer, workspace, agent_sessions, store, pull_requests, deps)


def test_cancel_runs_full_teardown_parity_for_a_live_session() -> None:
    """``cancel`` inherits the FULL Cancel-teardown parity (DESIGN §8.2).

    kill (live session) → remove_worktree(force=True) → branch -D → purge_ticket →
    close_open_pr_for_branch (remote branch kept) → recap comment.
    """
    state = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=1000.0,
    )
    m = _mocks(alive=True, loaded_state=state)

    cancel(7, deps=m.deps)

    # Session alive -> killed exactly once with the ticket-<n> name.
    m.sessions.is_alive.assert_called_once_with("ticket-7")
    m.sessions.kill.assert_called_once_with("ticket-7")
    # Worktree force-removed (a cancelled worktree is almost always dirty, DESIGN §8.2).
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    # Local branch resolved + force-deleted via the workspace seam.
    m.workspace.discover_branch.assert_called_once_with(7)
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    # Exhaustive purge (state + slot + breadcrumb + queue/moves/retries) via the 13.7 split.
    # Cancel abandons the ticket → keep_budgets=False (the default full purge, 13.8).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    # The open PR is closed for the branch; the remote branch is kept (close != delete-ref).
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    # A recap comment is posted on the issue with the full-parity text.
    m.board_writer.comment.assert_called_once()
    issue_arg, body_arg = m.board_writer.comment.call_args.args
    assert issue_arg == 7
    assert "PR closed, remote branch kept" in body_arg


def test_cancel_skips_kill_when_session_absent() -> None:
    """A dead/absent session is not killed, but the rest of the teardown still runs (idempotent)."""
    m = _mocks(alive=False, loaded_state=None)

    cancel(7, deps=m.deps)

    m.sessions.is_alive.assert_called_once_with("ticket-7")
    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    # Cancel abandons the ticket → keep_budgets=False (the default full purge, 13.8).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    m.board_writer.comment.assert_called_once()


def test_cancel_destructive_removes_worktree_closes_pr_keeps_remote_branch() -> None:
    """#10 KEEP+DOC parity (DESIGN §8.2.b): cancel is destructive — worktree removed + PR closed,
    but the REMOTE branch is kept (resumability lives on the remote branch + Backlog re-arm).

    This is the explicit divergence from the PoC's non-destructive ``plan_cancel``: NEW unifies the
    manual cancel with the Cancel-column teardown. The asserting checks are: ``remove_worktree`` IS
    called (destructive), the open PR IS closed, and the PR-close path is ``close_open_pr_for_branch``
    (a close, NOT a delete-ref) so the remote branch survives for a later re-launch.
    """
    state = TicketState(
        issue_number=7,
        item_id="PVTI_7",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=1000.0,
    )
    m = _mocks(alive=True, loaded_state=state)

    cancel(7, deps=m.deps)

    # Destructive: the worktree is force-removed (unlike the PoC's non-destructive cancel).
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    # The open PR is CLOSED for the branch...
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    # ...via a close, NOT a remote-ref delete — the remote branch is kept (no delete-ref call).
    assert not hasattr(m.pull_requests, "delete_ref") or not m.pull_requests.delete_ref.called
    # The recap names the kept-remote-branch resumability semantics.
    _issue, body = m.board_writer.comment.call_args.args
    assert "remote branch kept" in body


def test_cancel_resets_card_to_backlog_after_teardown() -> None:
    """``kanban cancel`` moves the card to the reset target (Backlog) after teardown (§25.3 bug C).

    The CLI cancel runs while the card SITS in the triggering column; the teardown alone leaves it
    there (an inconsistent board). The cancel mirrors the Cancel→Backlog reset by moving the card to
    ``DEFAULT_RESET_TARGET`` via the board writer, keyed off the persisted ``item_id``.
    """
    from kanbanmate.core.decide import DEFAULT_RESET_TARGET

    state = TicketState(
        issue_number=140,
        item_id="PVTI_140",
        session_id="ticket-140",
        status=TicketStatus.RUNNING,
        heartbeat=1000.0,
    )
    m = _mocks(alive=True, loaded_state=state)

    cancel(140, deps=m.deps)

    # The card was moved to the reset target (Backlog), keyed by the persisted item id.
    m.board_writer.move_card.assert_called_once_with("PVTI_140", DEFAULT_RESET_TARGET)
    assert DEFAULT_RESET_TARGET == "Backlog"


def test_cancel_reset_move_is_fail_soft() -> None:
    """A board error on the reset move must NOT break the (already-applied) teardown (§25.3)."""
    state = TicketState(
        issue_number=140,
        item_id="PVTI_140",
        session_id="ticket-140",
        status=TicketStatus.RUNNING,
        heartbeat=1000.0,
    )
    m = _mocks(alive=True, loaded_state=state)
    m.board_writer.move_card.side_effect = RuntimeError("github 503")

    # Must NOT raise — the teardown is the load-bearing effect; the move is a courtesy.
    cancel(140, deps=m.deps)

    # The teardown still ran in full despite the move failure.
    m.workspace.remove_worktree.assert_called_once_with(140, force=True)
    m.store.purge_ticket.assert_called_once_with(140, keep_budgets=False)
    m.board_writer.move_card.assert_called_once_with("PVTI_140", "Backlog")


def test_cancel_without_persisted_state_skips_reset_move() -> None:
    """No persisted state → no ``item_id`` → no card identity to move (the move is skipped)."""
    m = _mocks(alive=False, loaded_state=None)

    cancel(7, deps=m.deps)

    # Teardown still ran, but with no item id there is no card to reset.
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.board_writer.move_card.assert_not_called()


def test_build_cancel_ticket_uses_persisted_item_id() -> None:
    """The reconstructed ticket carries the persisted item id (parity with launch)."""
    state = TicketState(
        issue_number=42,
        item_id="PVTI_42",
        session_id="ticket-42",
        status=TicketStatus.RUNNING,
        heartbeat=1000.0,
    )
    m = _mocks(alive=True, loaded_state=state)

    ticket = build_cancel_ticket(m.deps, 42)

    assert ticket.issue_number == 42
    assert ticket.item_id == "PVTI_42"


def test_build_cancel_ticket_tolerates_missing_state() -> None:
    """With no persisted state the ticket still builds (empty item id, harmless for teardown)."""
    m = _mocks(alive=False, loaded_state=None)

    ticket = build_cancel_ticket(m.deps, 99)

    assert ticket.issue_number == 99
    assert ticket.item_id == ""
