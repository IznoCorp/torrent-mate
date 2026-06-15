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
