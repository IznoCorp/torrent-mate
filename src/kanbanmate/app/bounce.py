"""Bounce-the-card-back command actions (rollback + dependency gate, DESIGN §9/§11).

Extracted from :mod:`kanbanmate.app.actions` (actions.py reached the 1000-LOC hard ceiling once
the phase-32 dependency-bounce action landed; the two "bounce the card back to its origin column"
actions are a cohesive, self-contained family that lifts out cleanly). Both move the card BEFORE
posting a recap comment (a transient comment failure must never leave the board un-bounced) and
both steps are fail-soft (one failure never aborts the other, never raises out of the tick).

They are RE-EXPORTED from :mod:`kanbanmate.app.actions` (an explicit assignment at the bottom of
that module) so every existing ``from kanbanmate.app.actions import RollbackAction`` /
``DependencyBounceAction`` keeps resolving unchanged — the move is purely a ceiling-relief split,
not an API change.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2). This module names
only the pure :class:`~kanbanmate.core.domain.Ticket` and the adapter bundle
:class:`~kanbanmate.app.actions.Deps` (imported top-level — ``actions`` defines ``Deps`` before it
re-imports these classes at its own module bottom, so there is no import cycle).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kanbanmate.app.actions import Deps
from kanbanmate.core.domain import Ticket

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RollbackAction:
    """Bounce an un-whitelisted (from,to) move back to its origin column (DESIGN §11).

    Ported from the PoC ``runner.py`` ``_guarded_rollback`` (L170-209), adapted to NEW's
    ports. The PoC recorded a BOOKKEEPING bot move (``record_bot_move``) so the webhook the
    move produced was skipped and the rollback did NOT re-trigger; NEW has no webhook and no
    dedup — the **diff baseline** is the idempotency mechanism (DESIGN §6), so that bookkeeping
    step is DROPPED here. After this action runs, the tick records ``next_columns[item_id] =
    to_column`` for a ROLLBACK (phase 12.8), so the next poll compares against the column the
    card was bounced BACK to and the bounce does not re-trigger — the NEW analog of the PoC's
    ``record_bot_move``. (The bookkeeping-tag concern is phase-17 #19, not here.)

    The card is moved BEFORE the recap comment is posted: a transient comment failure must not
    leave the board un-bounced (the card sitting in the rejected column). Each step is fail-soft
    so one failure never aborts the other.

    Attributes:
        ticket: The ticket whose card to bounce back.
        to_column: The ``from_col`` to return the card to (the origin of the rejected move).
        reason: A human-readable reason, surfaced in the recap comment.
    """

    ticket: Ticket
    to_column: str
    reason: str

    def execute(self, deps: Deps) -> None:
        """Move the card back to :attr:`to_column`, then post a recap comment.

        Args:
            deps: The adapter bundle to act through.
        """
        issue = self.ticket.issue_number
        if issue is None:
            return
        # 1. Bounce the card back FIRST — the move is the load-bearing effect; the comment is a
        #    courtesy recap. Fail-soft so a board error is logged, never raised out of the tick.
        try:
            deps.board_writer.move_card(self.ticket.item_id, self.to_column)
        except Exception:
            logger.exception("rollback step 'move_card' failed for #%s; continuing", issue)
        # 2. Recap comment (English; the PoC text was French "carte ramenée en"). Fail-soft so a
        #    transient comment failure does not abort the (already-applied) bounce.
        try:
            deps.board_writer.comment(
                issue,
                f"KanbanMate: {self.reason} — card returned to {self.to_column}.",
            )
        except Exception:
            logger.exception("rollback step 'comment' failed for #%s; continuing", issue)


@dataclass(frozen=True)
class DependencyBounceAction:
    """Bounce a dependency-gated launch BACK to its from-column (phase 32, DESIGN §9).

    The hybrid dependency gate (#13) replaces a LAUNCH with this action when a declared
    ``Depends on #N`` is unmet. Before phase 32 the gate emitted a bare ``BlockAction``
    (a comment only), which left the card STRANDED in the triggering column with no agent: the
    operator saw "launch blocked by unmet dependencies" but the card sat in e.g. Brainstorming
    forever, and every poll re-decided the same block. This action instead bounces the card back
    to the column it came FROM (the ``from_col`` of the rejected move), so the board reflects that
    the move was rejected and the operator can re-drag it forward once the dependencies are Done.

    Mechanics are a deliberate MIRROR of :class:`RollbackAction` (the un-whitelisted-move bounce):
    the card is moved BEFORE the recap comment (a transient comment failure must not leave the
    board un-bounced), and BOTH steps are fail-soft so one failure never aborts the other. The
    anti-loop / no-re-trigger discipline lives in the tick: after this action runs,
    ``process_transition`` records ``next_columns[item_id] = to_column`` (the bounce target, NOT
    the rejected destination) and a BOOKKEEPING anti-loop move — exactly as for a ROLLBACK — so the
    bounce does not re-fire next poll (DESIGN §6 diff baseline is the primary guard).

    The recap comment is dependency-specific (it names the unmet deps and tells the operator to
    move the card forward again once they are Done), unlike :class:`RollbackAction`'s generic
    "card returned to <col>" recap — which is why this is its own action rather than a reused
    RollbackAction.

    Attributes:
        ticket: The ticket whose card to bounce back.
        to_column: The ``from_col`` to return the card to (the origin of the gated launch move).
        reason: The dependency gate's human-readable reason (names the unmet deps), surfaced in
            the recap comment.
    """

    ticket: Ticket
    to_column: str
    reason: str

    def execute(self, deps: Deps) -> None:
        """Move the card back to :attr:`to_column`, then post a dependency-bounce recap comment.

        Args:
            deps: The adapter bundle to act through.
        """
        issue = self.ticket.issue_number
        if issue is None:
            return
        # 1. Bounce the card back FIRST — the move is the load-bearing effect (the card must not be
        #    stranded in the triggering column); the comment is a courtesy recap. Fail-soft so a
        #    board error is logged, never raised out of the tick (mirrors RollbackAction).
        try:
            deps.board_writer.move_card(self.ticket.item_id, self.to_column)
        except Exception:
            logger.exception("dependency-bounce step 'move_card' failed for #%s; continuing", issue)
        # 2. Dependency-specific recap comment (English): name the unmet deps + the bounce target,
        #    and tell the operator to move the card forward again once the dependencies are Done.
        #    Fail-soft so a transient comment failure does not abort the (already-applied) bounce.
        try:
            deps.board_writer.comment(
                issue,
                f"KanbanMate: launch {self.reason} — card returned to {self.to_column}. "
                f"Move it forward again once dependencies are Done.",
            )
        except Exception:
            logger.exception("dependency-bounce step 'comment' failed for #%s; continuing", issue)
