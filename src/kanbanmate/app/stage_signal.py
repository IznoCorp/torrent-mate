"""App-layer stage-sticky upsert: the single I/O orchestrator (DESIGN §8.1).

This module is the imperative shell around the PURE stage-comment helpers in
:mod:`kanbanmate.core.stage_comment`. It owns the one create-or-update flow every
status producer (dispatcher 🟡 / session-end ⚠️ / reaper ⛔ / teardown ❌) and the
agent's progress append go through, driven entirely against the
:class:`~kanbanmate.ports.board.BoardWriter` port — never a concrete client.

It is a port of the PoC ``engine/stage_comment.py::upsert_stage_comment``, adapted
to NEW's conventions:

* The ``repo`` argument is DROPPED — NEW's ``GithubClient`` is single-repo, so the
  port methods (``list_issue_comments`` / ``comment`` / ``update_comment``) hide the
  repo from callers.
* On CREATE the function RETURNS ``None`` — it does NOT issue a second
  ``list_issue_comments`` round-trip to re-locate the just-created comment id (OLD's
  best-effort post-create re-locate is dropped). Returning ``None`` after a
  successful create is acceptable per fail-soft: every caller treats the id as
  best-effort, and the NEXT upsert re-finds the sticky by its marker.
* All GitHub I/O is best-effort / fail-soft: any exception is logged once to the
  module logger and swallowed (``return None``), so signaling never breaks the
  launch / advance / reap / teardown that triggered it (DESIGN §8.1).

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` but MUST NOT import
``cli`` or ``daemon`` (DESIGN §3.2). This module imports only ``core`` + ``ports``.
"""

from __future__ import annotations

import logging

from kanbanmate.core.stage_comment import (
    LABELS,
    HeaderInfo,
    StageStatus,
    _stamp,
    compose,
    fmt_timestamp,
    marker,
    render_header,
    split_sticky,
)
from kanbanmate.ports.board import BoardWriter

logger = logging.getLogger(__name__)


def upsert_stage_comment(
    writer: BoardWriter,
    issue: int,
    stage: str,
    *,
    header: HeaderInfo | None = None,
    append: str | None = None,
    now: float | None = None,
) -> int | None:
    """Create-or-update the ``stage`` sticky on ``issue`` (DESIGN §8.1; port of the PoC).

    Behaviour (mirrors the PoC control flow exactly):

    * FOUND: split the body, swap the header (when ``header`` is given) keeping the
      existing one otherwise, append a stamped progress line (when ``append`` is
      given), and PATCH it in place — a single ``list_issue_comments`` call backs the
      locate + body read.
    * ABSENT + a ``header`` carrying a running status, OR an ``append``: CREATE the
      sticky. The function then RETURNS ``None`` (no post-create re-locate round-trip;
      the next upsert re-finds the sticky by its marker).
    * ABSENT + a finalize-only call (a terminal ``header`` — done / interrupted /
      blocked / cancelled — with no ``append``): SILENT NO-OP. There is nothing to
      finalize, so no comment is created.

    FAIL-SOFT: ANY exception from ``writer.list_issue_comments`` / ``writer.comment`` /
    ``writer.update_comment`` is caught, logged once to the module logger, and
    swallowed — signaling never breaks dispatch / advance / reap / teardown.

    Args:
        writer: A :class:`~kanbanmate.ports.board.BoardWriter` exposing
            ``list_issue_comments`` / ``comment`` / ``update_comment``.
        issue: The issue number carrying the sticky.
        stage: The exact v2 column name owning the sticky.
        header: The new header to render, or ``None`` to preserve the existing one.
        append: A raw progress line to stamp + append, or ``None``.
        now: Optional epoch override for deterministic stamping (tests).

    Returns:
        The integer comment id on an in-place PATCH; ``None`` on a CREATE, a no-op,
        or any fail-soft swallow.
    """
    try:
        comments = writer.list_issue_comments(issue)
        needle = marker(stage)
        # Locate the sticky on the SAME listing we will read the body from (one call):
        # the core ``find_stage_comment_id`` wants ``CommentLike`` (``.id`` / ``.body``),
        # but NEW's ``CommentRef`` exposes ``.comment_id`` — so match the marker directly
        # here and keep the integer id (it round-trips into ``update_comment``).
        located = next((c for c in comments if needle in (c.body or "")), None)
        if located is not None:
            cid = located.comment_id
            hdr, prog = split_sticky(located.body or "")
            new_header = render_header(header) if header is not None else hdr
            if append:
                prog = prog + [_stamp(append, now=now)]
            new_body = compose(new_header, prog)
            # Body-diff guard (#10): a re-upsert that produces a body IDENTICAL to the existing one
            # (e.g. the dashboard's per-tick ⏳ WAITING re-upsert with no header/progress change)
            # would otherwise issue a wasteful PATCH every 10s. Skip the PATCH when nothing changed —
            # the sticky is already correct, so the round-trip is pure waste against the rate limit.
            if new_body == (located.body or ""):
                return cid
            writer.update_comment(cid, new_body)
            return cid
        # ABSENT: only create when there is something live to show (a running header or
        # an append). A finalize-only call for a stage with no sticky is a no-op.
        if header is None:
            new_header = render_header(HeaderInfo(stage=stage, status="running"))
        elif header.status != "running" and not append:
            return None
        else:
            new_header = render_header(header)
        prog = [_stamp(append, now=now)] if append else []
        writer.comment(issue, compose(new_header, prog))
        # NEW does NOT re-locate the just-created comment id (OLD's post-create
        # round-trip is dropped): return None — the next upsert re-finds it by marker.
        return None
    except Exception:  # noqa: BLE001 — best-effort: never break the producer (DESIGN §8.1)
        logger.exception(
            "stage-comment upsert failed for #%s stage=%r; signaling continues.",
            issue,
            stage,
        )
        return None


def _finalize_open_stickys(
    writer: BoardWriter,
    issue: int,
    status: StageStatus,
    *,
    now: float,
) -> None:
    """Best-effort: flip every OPEN stage sticky on ``issue`` to a terminal ``status`` (DESIGN §8.2.c).

    Generalised from the PoC ``engine/teardown.py::_cancel_open_stickys`` so the SAME
    open-sticky finalize backs both teardown flavours: the Cancel path flips to ❌
    ``cancelled`` (:func:`_cancel_open_stickys`), the Done-arrival teardown flips to ✅
    ``done`` (:func:`_done_open_stickys`, phase 28.1). Lists the issue's comments via
    ``writer.list_issue_comments``; for each stage comment (membership pre-filtered on
    ``kanban:step=``), checks whether the HEADER ONLY contains an OPEN label (RUNNING
    ``"in progress"`` OR WAITING ``"waiting for your input"``). A terminal sticky
    (✅/⚠️/⛔/❌) is left as-is. The header-only check is load-bearing: an agent-authored
    progress line containing ``"in progress"`` in the body must NOT mis-classify a
    terminal sticky as open.

    FAIL-SOFT: the listing AND each individual flip are wrapped so any GitHub error
    is logged once and swallowed — signalling never breaks the teardown that
    triggered it (DESIGN §8.1).

    BOTH the membership pre-filter and the stage split key off NEW's
    ``kanban:step=`` prefix (NOT the PoC's ``kanbanmate-stage:``) — see the
    marker-prefix note in DESIGN §8.2.c.

    Args:
        writer: A :class:`~kanbanmate.ports.board.BoardWriter` exposing
            ``list_issue_comments``.
        issue: The issue number whose stickies to scan.
        status: The terminal status to flip each OPEN sticky to (``"cancelled"``
            for the Cancel path, ``"done"`` for the Done-arrival teardown).
        now: Epoch seconds for the finished timestamp (injected for test
            determinism).
    """
    # An OPEN (non-terminal) sticky is one whose header carries the RUNNING label ("in progress") OR
    # the WAITING label ("waiting for your input", phase-27 §B). A WAITING sticky is still LIVE — a
    # teardown must flip it to its terminal status too, exactly like a 🟡 running one; a terminal
    # sticky (✅/⚠️/⛔/❌) is left as-is.
    open_labels = (LABELS["running"], LABELS["waiting"])
    try:
        comments = writer.list_issue_comments(issue)
    except Exception:  # noqa: BLE001 — best-effort: never break the teardown
        logger.exception(
            "finalize-open-stickys: list_issue_comments failed for #%s; skipping.",
            issue,
        )
        return
    for c in comments:
        try:
            body = c.body or ""
            # 1. MEMBERSHIP PRE-FILTER: skip non-stage comments before any parse.
            if "kanban:step=" not in body:
                continue
            # 2. Extract the stage from the marker.
            stage = body.split("kanban:step=", 1)[1].split("-->", 1)[0].strip()
            # 3. Check the HEADER ONLY for an OPEN label (running OR waiting) — a terminal
            #    sticky (✅/⚠️/⛔) is left as-is.  Keying off the header (not
            #    the **Progress** body) is load-bearing.
            header, _progress = split_sticky(body)
            if not any(label in header for label in open_labels):
                continue
            # 4. Flip to the requested terminal status with a finished timestamp.
            upsert_stage_comment(
                writer,
                issue,
                stage,
                header=HeaderInfo(
                    stage=stage,
                    status=status,
                    finished=fmt_timestamp(now),
                ),
                now=now,
            )
        except Exception:  # noqa: BLE001 — best-effort per-sticky
            logger.exception(
                "finalize-open-stickys: flip failed for #%s comment; continuing.",
                issue,
            )


def _cancel_open_stickys(
    writer: BoardWriter,
    issue: int,
    *,
    now: float,
) -> None:
    """Best-effort: flip every open stage sticky on ``issue`` to ❌ cancelled (DESIGN §8.2.c).

    Thin wrapper over :func:`_finalize_open_stickys` with ``status="cancelled"`` — the
    Cancel-column teardown's open-sticky finalize, kept as a named seam so existing
    callers (the Cancel ``TeardownAction``) and their tests are unchanged.

    Args:
        writer: A :class:`~kanbanmate.ports.board.BoardWriter` exposing
            ``list_issue_comments``.
        issue: The issue number whose stickies to scan.
        now: Epoch seconds for the finished timestamp (injected for test
            determinism).
    """
    _finalize_open_stickys(writer, issue, "cancelled", now=now)


def _done_open_stickys(
    writer: BoardWriter,
    issue: int,
    *,
    now: float,
) -> None:
    """Best-effort: flip every open stage sticky on ``issue`` to ✅ done (phase 28.1).

    Thin wrapper over :func:`_finalize_open_stickys` with ``status="done"`` — the
    Done-arrival teardown's open-sticky finalize. A card landing in Done while its agent
    is LIVE means the work is recognised as already-shipped/complete, so the open sticky
    is finalized ✅ ``done`` (NOT ❌ ``cancelled`` — that is the abandonment wording the
    Cancel path uses).

    Args:
        writer: A :class:`~kanbanmate.ports.board.BoardWriter` exposing
            ``list_issue_comments``.
        issue: The issue number whose stickies to scan.
        now: Epoch seconds for the finished timestamp (injected for test
            determinism).
    """
    _finalize_open_stickys(writer, issue, "done", now=now)
