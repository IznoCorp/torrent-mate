"""Done-arrival reclaim detector: reclaim a ticket's WORKTREE when its card lands in Done.

Extracted from :mod:`kanbanmate.app.tick` (phase 28.1; the tick was at the 1000-LOC hard ceiling).
The Done-arrival rule, KEYED ON THE WORKTREE (#9): a transition landing a ticket in the configured
Done column WHILE a worktree still EXISTS for it warrants a DONE-flavoured teardown — the card STAYS
in Done. With no worktree the arrival is a PURE no-op. The detector here is the policy half (probe
the worktree + classify); the tick dispatches the returned action under its per-action watchdog
(DESIGN §5).

**#9 rationale (rank-9 verdict).** The detector USED to key on a LIVE persisted state, but by the
time a card reaches Done via a normal route, ``kanban session-end`` has already purged the state
while leaving the worktree behind — so a state-keyed trigger MISSED the dominant orphan (a worktree
with NO persisted state). Keying on ``deps.workspace.worktree_exists(issue)`` reclaims it regardless
of route. To avoid silently destroying unpushed work, a cheap ``has_unpushed_work`` probe downgrades
the reclaim to a Blocked sticky instead of a teardown when the worktree is dirty/ahead.

``TickConfig`` is imported only under ``TYPE_CHECKING`` to dodge the circular import (``tick`` imports
this module). Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2); this
module names only Protocols (via :class:`~kanbanmate.app.actions.Deps`) plus the pure core.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kanbanmate.app.actions import BlockAction, Deps, TeardownAction
from kanbanmate.core.columns import resolve_column
from kanbanmate.core.domain import Transition

if TYPE_CHECKING:
    from kanbanmate.app.tick import TickConfig

logger = logging.getLogger(__name__)


def done_arrival_teardown(
    deps: Deps,
    config: TickConfig,
    transition: Transition,
) -> TeardownAction | BlockAction | None:
    """Return a reclaim action when a card lands in Done while a worktree still EXISTS (#9).

    The Done-arrival rule, keyed on the WORKTREE (#9): a transition landing a ticket in the
    configured :attr:`~kanbanmate.app.tick.TickConfig.done_column` while a worktree still EXISTS for
    it warrants a DONE-flavoured teardown — kill the tmux session, remove the worktree (+ local
    branch), finalize the stage sticky ✅ ``done``, post the short "moved to Done" recap, and purge
    the state. This function is the pure-ish DETECTOR: it probes the worktree and returns the action
    to run (the caller dispatches it under the same per-action watchdog as every other action, so a
    hung git/tmux call cannot freeze the tick — DESIGN §5). It returns ``None`` when this is NOT a
    Done arrival, the ticket has no issue number, or NO worktree exists — in that last case the
    arrival is a PURE no-op (the dominant case once the session purged state AND removed the
    worktree), which the caller honours by its own no-op branch.

    **Worktree-keyed, not state-keyed (#9, rank-9 verdict).** ``kanban session-end`` purges the
    persisted state but leaves the worktree, so by Done arrival there is usually NO live state — a
    state-keyed trigger missed the dominant orphan. Keying on ``worktree_exists`` reclaims it on any
    route. **Unpushed-work guard.** Before destroying the worktree, ``has_unpushed_work`` is probed;
    if the worktree is dirty or ahead of the remote, the reclaim DOWNGRADES to a Blocked sticky
    (``BlockAction``) — loud, non-destructive — so unpushed work is never silently lost (the operator
    can push/merge then re-Done). The card STAYS in Done either way (the caller advances the diff
    baseline to Done as for any arrival; it is NEVER moved).

    Why a tick-level branch and not a decide-level reactive column (the design constraint): making
    Done REACTIVE would route it through the same ``decide`` precedence as Cancel, changing Cancel's
    semantics. Instead Done stays INERT and this lands purely in the NOOP path, so Cancel's
    TEARDOWN/RESET routing is unaffected. The teardown reuses the SHARED, replay-safe
    :class:`~kanbanmate.app.actions.TeardownAction` with ``flavour="done"``; it is itself fail-soft +
    replay-safe (a second Done tick finds the worktree already gone → no-op), robust to a re-fired
    diff.

    Args:
        deps: The injected adapter bundle (the worktree probes that decide reclaim-vs-not).
        config: The per-tick policy inputs (the configured ``done_column``).
        transition: The detected move; its destination is matched against ``done_column``.

    Returns:
        A ``flavour="done"`` :class:`~kanbanmate.app.actions.TeardownAction` to reclaim the
        worktree, a :class:`~kanbanmate.app.actions.BlockAction` when unpushed work blocks the
        reclaim, or ``None`` when this is not a Done arrival with a worktree (the no-op case).
    """
    issue = transition.ticket.issue_number
    if issue is None:
        return None
    # Resolve via name-then-key so the GitHub adapter's Status option NAME ("Done") matches the
    # key-indexed column model — the same load-bearing resolution decide() uses. Only the CONFIGURED
    # done column triggers this; any other inert column stays on the NOOP-forward finalize path.
    destination = resolve_column(config.columns, transition.to_column)
    if destination is None or destination.key != config.done_column:
        return None
    # Key on the WORKTREE, not persisted state (#9): the dominant orphan is a worktree with NO state
    # (session-end purged the state but left the worktree, then a human moved the card to Done). No
    # worktree → nothing to reclaim → pure no-op.
    if not deps.workspace.worktree_exists(issue):
        return None
    # Unpushed-work guard (#9, rank-9 verdict): never silently destroy work. A dirty/ahead worktree
    # downgrades to a LOUD Blocked sticky instead of a teardown — the operator pushes/merges, then
    # re-Dones to reclaim. A clean/fully-pushed worktree proceeds to the reclaim teardown.
    if deps.workspace.has_unpushed_work(issue):
        logger.warning(
            "Done arrival for #%s: worktree has UNPUSHED work — NOT destroying it; "
            "downgrading to a Blocked note (push/merge then re-Done to reclaim)",
            issue,
        )
        return BlockAction(
            ticket=transition.ticket,
            reason=(
                "moved to Done but its worktree has unpushed commits or uncommitted changes — "
                "the worktree was kept (not destroyed). Push/merge the work, then move the card "
                "out of and back into Done to reclaim the worktree"
            ),
        )
    # Clean worktree → DONE-flavoured teardown (✅ finalize + "moved to Done" recap, NO Backlog
    # re-arm). keep_budgets=False: the ticket's work is complete, so the exhaustive purge drops its
    # budgets too (like Cancel).
    logger.info("Done arrival for #%s: reclaiming clean worktree (done-flavoured teardown)", issue)
    return TeardownAction(ticket=transition.ticket, flavour="done")


def close_done_issue(deps: Deps, transition: Transition) -> bool:
    """Close the GitHub issue on a GENUINE Done arrival — idempotent + wholly fail-soft (#9 / BUG #9).

    A ticket reaching the configured Done column completes its lifecycle, so its GitHub issue must be
    CLOSED (Done = closed → the ensign "Clôturé" badge appears consistently). The engine already had a
    ``close_issue`` capability, but it only ran on the Cancel/``ticket_close`` intent path — never on a
    normal Done arrival — so merged tickets sat in Done with their issue still OPEN (live: #27, #76).

    This closes the issue for the TWO genuine-Done cases the caller dispatches it on:

    * the clean-reclaim case (``done_arrival_teardown`` returned a ``flavour="done"``
      :class:`~kanbanmate.app.actions.TeardownAction` — the worktree was clean, the work is complete), and
    * the no-worktree case (``done_arrival_teardown`` returned ``None`` BUT the card is in the Done
      column — the DOMINANT merged path, where ``session-end`` already purged state + removed the
      worktree before the card reached Done).

    It is NEVER called on the unpushed-work-blocked case (``done_arrival_teardown`` returned a
    :class:`~kanbanmate.app.actions.BlockAction`): a dirty/ahead worktree means the work is NOT finished,
    so closing the issue would be wrong. The not-Block gate lives in the caller; this function trusts it.

    The close is orthogonal to the worktree reclaim — the card STAYS in Done either way (this never
    moves it). Two robustness invariants:

    * **Idempotent.** It first probes ``deps.board_reader.issue_state(number)`` (``True`` iff already
      closed) and SKIPS an already-closed issue. This is what makes it safe to re-evaluate every Done
      tick: a Done card stays in Done and is re-diffed (or re-snapshotted on a forced tick), so without
      this guard it would re-close the issue on every poll. Resolving the issue's node id then closing
      reuses the proven ``_resolve_node_id`` + ``seeder.close_issue`` pattern from the intent path.
    * **Fail-soft.** A close failure (a GitHub error, a missing seeder, an unresolvable issue) must
      NEVER break the tick — every branch swallows + logs and returns ``False``. The arrival's worktree
      reclaim already ran (or is a no-op) independently; the issue close is a best-effort finalizer.

    Args:
        deps: The injected adapter bundle. ``deps.board_reader.issue_state`` supplies the idempotence
            probe and ``deps.seeder`` (``fetch_issue`` → node id, then ``close_issue``) does the close.
        transition: The Done arrival whose ticket's issue to close; ``issue_number`` names it.

    Returns:
        ``True`` iff this call issued a ``close_issue`` (the issue was open and the close succeeded);
        ``False`` on every skip (no issue number, no seeder, already closed, unresolvable) or failure
        (so the caller can record an event only on a real close, and never raises).
    """
    issue = transition.ticket.issue_number
    if issue is None:
        return False
    seeder = deps.seeder
    if seeder is None:
        # No seeder wired (a daemon configured without the bootstrap port): nothing to close through.
        # This is a config shape, not an error — fail-soft no-op.
        logger.debug(
            "Done arrival for #%s: no seeder configured, cannot close issue (no-op)", issue
        )
        return False
    try:
        # Idempotence: skip an already-closed issue. ``issue_state`` is ``True`` iff CLOSED. This both
        # avoids a redundant close mutation AND prevents re-closing on every subsequent Done tick (a
        # Done card stays in Done and is re-evaluated). A throwing probe is fail-soft below.
        if deps.board_reader.issue_state(issue):
            logger.debug(
                "Done arrival for #%s: issue already closed, skipping close (idempotent)", issue
            )
            return False
        # Resolve number → node id (the close mutation needs the global node id), then close. Reuses
        # the proven intent-path pattern (``_resolve_node_id`` + ``seeder.close_issue``).
        ref = seeder.fetch_issue(issue)
        node_id = ref.node_id if ref is not None else None
        if node_id is None:
            logger.warning(
                "Done arrival for #%s: could not resolve issue node id, not closing", issue
            )
            return False
        seeder.close_issue(node_id)
        logger.info("Done arrival for #%s: closed the GitHub issue (Done = closed)", issue)
        return True
    except Exception:
        # Fail-soft: a close failure (GitHub error, timeout, missing issue) must NEVER break the tick.
        # The worktree reclaim already ran independently; the close is a best-effort finalizer.
        logger.exception(
            "Done arrival for #%s: closing the issue failed; continuing (fail-soft)", issue
        )
        return False
