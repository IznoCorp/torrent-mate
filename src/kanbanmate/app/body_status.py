"""App-layer body-top status-header orchestrator: the single I/O wrapper for FIX 5.

This module is the imperative shell around the PURE
:func:`kanbanmate.core.body_edit.set_status_header` transform. It mirrors
:mod:`kanbanmate.app.stage_signal`'s fail-soft contract exactly: it fetches the issue body via
the :class:`~kanbanmate.ports.board.Seeder` port, sets the body-top status block, and PATCHes the
body back ONLY when it actually changed (the on-change / body-diff discipline) — a no-op when the
body-writer is unavailable (``seeder is None``).

Why body-diff-gated: :meth:`Seeder.update_issue_body` replaces the WHOLE body, so a daemon header
write can RACE an agent's ``kanban-update-body --set-field`` (last-writer-wins). Skipping the write
when nothing changed bounds API cost AND shrinks the race window; because the status block is
region-disjoint from the ``**key**:`` markers, even a losing race only stales the header region for
one tick (recovered next tick) and never eats a marker (DESIGN clean-termination §FIX-5).

Layering: ``app`` may import ``core`` + ``ports`` (DESIGN §3.2). This module imports only those.
"""

from __future__ import annotations

import logging

from kanbanmate.core.body_edit import set_status_header
from kanbanmate.core.stage_comment import fmt_timestamp
from kanbanmate.ports.board import Seeder

logger = logging.getLogger(__name__)


def update_body_status(
    seeder: Seeder | None,
    issue: int,
    *,
    stage: str,
    state: str,
    summary: str,
    now: float,
    latest_progress: str | None = None,
) -> None:
    """Best-effort: set the body-top status block on ``issue`` (FIX 5; fully fail-soft).

    Behaviour (mirrors :func:`kanbanmate.app.stage_signal.upsert_stage_comment`'s contract):

    * NO-OP when ``seeder is None`` — the body-writer is unavailable (null/offline wiring), so
      there is nothing to do.
    * Otherwise fetch the issue body, render the new body-top status block via the PURE
      :func:`~kanbanmate.core.body_edit.set_status_header`, and PATCH it back ONLY when the body
      actually changed (the body-diff gate: bounds API cost + shrinks the last-writer-wins race
      window against an agent's ``kanban-update-body``).

    PROGRESS MILESTONE (BUG A). Every caller passes a STATIC literal ``summary`` ("agent
    dispatched", "stage complete", …) — so the header never surfaced the agent's latest progress
    milestone, the most useful at-a-glance signal. When ``latest_progress`` is non-empty the
    producer has read the LATEST ``- HH:MM — <milestone>`` line off the stage sticky (via
    :func:`kanbanmate.app.status_reporter.latest_progress`) and we render IT as the header summary.
    When it is ``None``/empty (no progress line yet, a terminal/edge state, or a fail-soft miss) we
    FALL BACK to the static ``summary`` so the header never regresses to a blank line.

    FAIL-SOFT: the WHOLE body is wrapped in try/except — ANY error (fetch failure, encode error,
    patch failure) is logged once and swallowed. The header write must NEVER raise into the tick or
    block the launch / advance / reap / teardown that triggered it (DESIGN clean-termination §FIX-5).

    Args:
        seeder: The body-writer (a :class:`~kanbanmate.ports.board.Seeder` exposing
            ``fetch_issue`` + ``update_issue_body``), or ``None`` when unwired.
        issue: The issue number whose body-top header to set.
        stage: The current stage / column name.
        state: The lifecycle state word (``running`` / ``done`` / ``blocked`` / ``waiting`` /
            ``interrupted`` / ``cancelled``).
        summary: A short free-text static summary — the FALLBACK header text when no progress
            milestone is available (empty string omits the ``— …`` clause).
        now: Epoch seconds for the ``_updated …`` stamp (injected for test determinism).
        latest_progress: The agent's latest progress milestone text (the producer read it off the
            stage sticky), or ``None``/empty when none is available. When non-empty it REPLACES
            ``summary`` as the rendered header text; otherwise ``summary`` is used.
    """
    if seeder is None:
        return
    try:
        ref = seeder.fetch_issue(issue)
        current = ref.body or ""
        # Surface the latest progress milestone when the producer supplied one; otherwise keep the
        # static summary so a terminal/edge state never renders a blank header (BUG A).
        header_summary = latest_progress if latest_progress else summary
        new_body = set_status_header(
            current,
            stage=stage,
            state=state,
            summary=header_summary,
            timestamp=fmt_timestamp(now),
        )
        # Body-diff gate: skip the write when nothing changed — the on-change discipline that bounds
        # API cost and shrinks the last-writer-wins window vs an agent's ``kanban-update-body``.
        if new_body == current:
            return
        seeder.update_issue_body(ref.node_id, new_body)
    except Exception:  # noqa: BLE001 — best-effort: never break the producer (DESIGN §FIX-5)
        logger.exception(
            "body-status header update failed for #%s stage=%r; continuing.",
            issue,
            stage,
        )
