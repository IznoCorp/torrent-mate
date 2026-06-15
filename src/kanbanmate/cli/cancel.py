"""``kanban cancel <issue>`` — manual teardown of a ticket's agent (DESIGN §8.2).

``kanban cancel`` is the operator's manual hand on the same teardown the daemon runs when a card
lands in the Cancel column: it kills the ticket's tmux session, removes its worktree, releases the
concurrency slot, and posts a recap comment. To stay byte-for-byte consistent with the autonomous
path it **reuses the app-layer** :class:`~kanbanmate.app.actions.TeardownAction` rather than
re-implementing teardown — exactly the action the reaper and the Cancel-column decision execute.

**Divergence from the PoC (#10 KEEP+DOC, anchored in DESIGN §8.2).** The PoC
``cli/plan_cancel.py:24-34`` was deliberately NON-destructive: it killed the tmux session and marked
the ticket ``cancelled`` but NEVER removed the worktree (``worktree remove --force`` was banned,
PoC §4.5). NEW unifies the manual ``kanban cancel`` and the Cancel-column teardown into ONE
destructive :class:`TeardownAction` (kill → ``remove_worktree(force=True)`` → branch ``-D`` → release
slot → close the open PR → recap) per the phase-8.2 operator decision. The destruction is intentional,
not an accident of reuse: **resumability moves to the kept REMOTE branch + a Backlog re-arm** (the PR
close does NOT delete the remote ref, so the branch survives and re-moving the card to Backlog
re-launches against it), rather than to a retained local worktree. An operator carrying the PoC's
non-destructive mental model should expect the worktree to be gone after a cancel.

The persisted state supplies the ``item_id`` so the reconstructed
:class:`~kanbanmate.core.domain.Ticket` carries the same identity the launch recorded; when no state
is persisted (already cancelled, never launched) the teardown still runs idempotently against a
minimal ticket — every step of :class:`TeardownAction` tolerates an absent target.

Layering: ``cli`` is an entrypoint at the top of the import hierarchy (DESIGN §3.2); it may import
``app`` (:class:`Deps`, :class:`TeardownAction`) and build them through the composition root.
"""

from __future__ import annotations

import logging

from kanbanmate.app.actions import Deps, TeardownAction
from kanbanmate.app.wiring import WiringConfig, build_deps
from kanbanmate.core.decide import DEFAULT_RESET_TARGET
from kanbanmate.core.domain import Ticket

logger = logging.getLogger(__name__)


def build_cancel_ticket(deps: Deps, issue_number: int) -> Ticket:
    """Reconstruct the minimal :class:`~kanbanmate.core.domain.Ticket` to tear down ``issue_number``.

    The teardown only needs the issue number (worktree/session/slot are keyed by it) and the
    ``item_id`` (carried through for parity with the launch-time ticket). The ``item_id`` is read
    from persisted state when present; an empty string is used when the ticket has no state, which is
    harmless — :class:`~kanbanmate.app.actions.TeardownAction` never dereferences it for a cancel.

    Args:
        deps: The wired adapter bundle whose ``store`` is consulted for the persisted ``item_id``.
        issue_number: The GitHub issue number to tear down.

    Returns:
        A :class:`~kanbanmate.core.domain.Ticket` carrying the issue number and (best-effort) item id.
    """
    state = deps.store.load(issue_number)
    item_id = state.item_id if state is not None else ""
    # Title/column_key are immaterial to teardown (it keys off the issue number); mirror the
    # reaper's minimal-ticket reconstruction in ``app.tick`` so the two paths behave identically.
    return Ticket(
        item_id=item_id,
        issue_number=issue_number,
        title=f"ticket-{issue_number}",
        column_key="",
    )


def cancel(issue_number: int, *, deps: Deps) -> None:
    """Run the manual teardown for ``issue_number`` via the app-layer ``TeardownAction``.

    Reconstructs the ticket from persisted state and executes the **same**
    :class:`~kanbanmate.app.actions.TeardownAction` the daemon uses, so a manual cancel and an
    automatic Cancel-column teardown are indistinguishable in effect (kill session, remove worktree,
    release slot, recap comment).

    Args:
        issue_number: The GitHub issue number whose agent to tear down.
        deps: The wired adapter bundle to execute the teardown against (injected; tests pass a fake
            bundle so no real tmux/git/network is touched).
    """
    ticket = build_cancel_ticket(deps, issue_number)
    TeardownAction(ticket=ticket).execute(deps)
    # Reset the card to the reset target (Backlog) AFTER the teardown (phase-25 §25.3, bug C). The
    # autonomous Cancel→Backlog reset is operator-driven (a human moves the card, which the daemon
    # reconciles as a RESET); but ``kanban cancel`` is run while the card SITS in the triggering
    # column, so the teardown alone leaves it there (an inconsistent board: a torn-down card stuck
    # in e.g. ``Spec``). Mirror the reset by moving the card to ``DEFAULT_RESET_TARGET`` here, keyed
    # off the persisted ``item_id`` resolved above (an empty id means no state was persisted, so
    # there is no card identity to move — skip). FAIL-SOFT: a board error must NOT break the
    # (already-applied) teardown — the local cleanup is the load-bearing effect; the move is the
    # board-consistency courtesy.
    if ticket.item_id:
        try:
            deps.board_writer.move_card(ticket.item_id, DEFAULT_RESET_TARGET)
        except Exception:
            logger.exception(
                "cancel: reset-to-%s move failed for #%s; teardown already applied, continuing",
                DEFAULT_RESET_TARGET,
                issue_number,
            )


def cancel_from_config(issue_number: int, config: WiringConfig) -> None:
    """Wire production dependencies from ``config`` and run the cancel (the CLI's production path).

    Args:
        issue_number: The GitHub issue number whose agent to tear down.
        config: The runtime configuration the composition root builds the concrete adapters from.
    """
    cancel(issue_number, deps=build_deps(config))
