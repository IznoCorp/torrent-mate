"""Pure stage-sticky comment helpers: marker, render, split, compose.

A stage = an agent column (Design, Plan, Implement, …).  Each stage owns ONE
GitHub comment, self-identified by a hidden HTML marker so it is re-located
across process restarts with no stored id (DESIGN §8.1).  The comment has two
zones::

    <!-- kanban:step=Design -->
    ### 🟡 Design — in progress          ← HEADER (dispatcher / session-end / reaper own it)
    - session : … · profile … · mode …
    - started : … · worktree …
    - logs : …

    **Progress**                          ← BODY (the agent owns it, via kanban-progress)
    - 20:49 — …

A header update PRESERVES the body; a progress append PRESERVES the header.  The
status is ALWAYS posted by a producer with proof (advance / session-end /
reaper) — never by the agent's good will.  All GitHub I/O is best-effort /
fail-soft (handled by the app layer — this module is PURE).

This module is a port of the PoC ``engine/stage_comment.py``, adapted to NEW's
conventions:

* Marker prefix: ``<!-- kanban:step=<stage> -->`` (NEW's shipped prefix, NOT
  the PoC's ``<!-- kanbanmate-stage:<stage> -->``), so stickies created by the
  existing one-line writer in ``bin/kanban_comment.py`` are still located after
  this upgrade.
* User-facing labels are ENGLISH (operator decision; the PoC used French).
* Body heading: ``**Progress**`` (English; the PoC used ``**Progression**``).
* ``find_stage_comment_id`` returns ``int | None`` (matching NEW's
  ``CommentRef.comment_id: int``), not a stringified id.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Status vocabulary — all user-facing strings are ENGLISH.
# ---------------------------------------------------------------------------

StageStatus = Literal["running", "waiting", "done", "interrupted", "blocked", "cancelled"]

BADGES: dict[StageStatus, str] = {
    "running": "\U0001f7e1",  # 🟡
    "waiting": "⏳",  # ⏳ — agent alive, awaiting human input (phase-27 §B)
    "done": "✅",  # ✅
    "interrupted": "⚠️",  # ⚠️
    "blocked": "⛔",  # ⛔
    "cancelled": "❌",  # ❌
}

LABELS: dict[StageStatus, str] = {
    "running": "in progress",
    # The WAITING sticky header reads "⏳ <stage> — waiting for your input": a non-terminal LIVE
    # status (no finished-timestamp line) that replaces the 🟡 "in progress" header while the agent
    # is blocked on a human decision, surfacing the need for intervention on the GitHub issue (§B).
    "waiting": "waiting for your input",
    "done": "done",
    "interrupted": "interrupted",
    "blocked": "blocked",
    "cancelled": "cancelled",
}

# Termination-line prefix for the finished-timestamp line.  Only terminal
# statuses carry one; "running" is deliberately absent.
_FINISHED_PREFIX: dict[StageStatus, str] = {
    "done": "done",
    "interrupted": "interrupted",
    "blocked": "blocked",
    "cancelled": "cancelled",
}

_PROGRESS_HEADING = "**Progress**"


# ---------------------------------------------------------------------------
# Marker — NEW's shipped prefix, kept for backward compatibility.
# ---------------------------------------------------------------------------


def marker(stage: str) -> str:
    """Return the hidden HTML self-identifying marker for ``stage``.

    Uses NEW's existing marker prefix ``<!-- kanban:step=<stage> -->`` (NOT the
    PoC's ``<!-- kanbanmate-stage:<stage> -->``) so stickies created by the
    shipped one-line writer in ``bin/kanban_comment.py`` are still located after
    this upgrade.

    Args:
        stage: The exact v2 column name (e.g. ``"Design"``, ``"PR Ready"``).

    Returns:
        The hidden HTML marker string embedding ``stage`` verbatim.
    """
    return f"<!-- kanban:step={stage} -->"


# ---------------------------------------------------------------------------
# HeaderInfo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeaderInfo:
    """Canonical header fields for a stage sticky (DESIGN §8.1).

    Rebuilt from persisted state by each producer (dispatcher / session-end /
    reaper); the agent never supplies these — only the producer with proof owns
    the status.

    Attributes:
        stage: The exact v2 column name (e.g. ``"Design"``).
        status: One of ``running`` / ``done`` / ``interrupted`` / ``blocked`` /
            ``cancelled``.
        session: Short session UUID prefix shown in the header.
        profile: Agent permission profile name (e.g. ``"docs"``).
        mode: Claude permission mode (e.g. ``"auto"``).
        started: Human-readable start timestamp.
        finished: Human-readable termination timestamp (empty when running).
        worktree: Worktree directory name (e.g. ``"ticket-37"``).
        log_hint: Command hint to tail the session logs.
        attach_hint: A concrete drop-in command (e.g. ``tmux attach -t ticket-37``) rendered as an
            extra header line ONLY for the WAITING status (31.2), so the ⏳ "waiting for your input"
            sticky tells the operator HOW to answer, not merely THAT an answer is needed. Empty for
            every other status (the line is omitted).
    """

    stage: str
    status: StageStatus
    session: str = ""
    profile: str = ""
    mode: str = ""
    started: str = ""
    finished: str = ""
    worktree: str = ""
    log_hint: str = ""
    attach_hint: str = ""


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------


def fmt_timestamp(epoch: object) -> str:
    """Format epoch seconds as ``YYYY-MM-DD HH:MM`` for a stage header.

    The single shared timestamp formatter for every stage-header producer, so
    the header is rendered identically regardless of who finalizes it.  Returns
    ``""`` for any falsy ``epoch`` (``None``, ``0``, ``0.0``, ``""``).

    Args:
        epoch: Epoch seconds (int/float/str) or a falsy value.

    Returns:
        The ``YYYY-MM-DD HH:MM`` local-time string, or ``""``.
    """
    if not epoch:
        return ""
    t = time.localtime(float(epoch))  # type: ignore[arg-type]
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d} {t.tm_hour:02d}:{t.tm_min:02d}"


# ---------------------------------------------------------------------------
# CommentLike protocol — keeps ``find_stage_comment_id`` I/O-free.
# ---------------------------------------------------------------------------


@runtime_checkable
class CommentLike(Protocol):
    """Minimal comment shape so :func:`find_stage_comment_id` stays I/O-free.

    The adapter side maps its ``CommentRef.comment_id: int`` → ``id`` and its
    ``body: str`` → ``body`` when passing a list into core.  This Protocol is
    deliberately tiny — it names only the two fields the pure locate function
    needs, and it lives in ``core/`` (not ``ports/``) so the locate logic is
    fully self-contained.
    """

    id: int
    body: str


# ---------------------------------------------------------------------------
# Locate
# ---------------------------------------------------------------------------


def find_stage_comment_id(comments: list[CommentLike], stage: str) -> int | None:
    """Return the id of the comment whose body contains ``marker(stage)``.

    The marker string is matched EXACTLY (HTML comment, spaces included), so
    ``"PR Ready"`` never matches ``"PR"``.  Returns the **integer** comment id
    (matching NEW's ``CommentRef.comment_id: int``), not a stringified id.

    Args:
        comments: A list of :class:`CommentLike` records (at minimum ``id``
            and ``body``).
        stage: The exact v2 column name to locate.

    Returns:
        The integer comment id of the matching sticky, or ``None`` if none
        matches.
    """
    needle = marker(stage)
    for c in comments:
        if needle in (c.body or ""):
            return c.id
    return None


# ---------------------------------------------------------------------------
# Split / compose
# ---------------------------------------------------------------------------


def split_sticky(body: str) -> tuple[str, list[str]]:
    """Split a sticky body into ``(header_block, progress_lines)`` at the
    ``**Progress**`` heading.

    The header block is everything BEFORE the heading (trailing blank lines
    trimmed); the progress lines are the non-empty lines AFTER it.  A body with
    no heading yields ``(body.rstrip(), [])`` — a header update preserves the
    body, and vice versa.

    Args:
        body: The full sticky comment body.

    Returns:
        A ``(header_block, progress_lines)`` tuple.
    """
    if _PROGRESS_HEADING not in body:
        return body.rstrip(), []
    head_part, _, tail = body.partition(_PROGRESS_HEADING)
    header = head_part.rstrip()
    progress = [ln for ln in tail.splitlines() if ln.strip()]
    return header, progress


def compose(header: str, progress: list[str]) -> str:
    """Assemble a full sticky body from a header block + progress lines.

    Empty progress omits the ``**Progress**`` heading entirely (a
    freshly-created running sticky with no milestones yet).  The result
    round-trips through :func:`split_sticky`.

    Args:
        header: The header block (marker + status line + metadata bullets).
        progress: The timestamped progress lines (may be empty).

    Returns:
        The full sticky body as a single string.
    """
    if not progress:
        return header
    return header + "\n\n" + _PROGRESS_HEADING + "\n" + "\n".join(progress)


# ---------------------------------------------------------------------------
# Stamp
# ---------------------------------------------------------------------------


def _stamp(line: str, *, now: float | None = None) -> str:
    """Prefix a raw progress line with an ``HH:MM`` bullet.

    The agent supplies only the text; the stamp add the timestamp so every
    progress line is prefixed with ``- HH:MM — ``.

    Args:
        line: The raw milestone text supplied by the agent.
        now: Optional epoch override for deterministic tests; defaults to
            ``time.time()``.

    Returns:
        The progress line prefixed with ``- HH:MM — ``.
    """
    ts = time.localtime(now if now is not None else time.time())
    return f"- {ts.tm_hour:02d}:{ts.tm_min:02d} — {line}"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_header(info: HeaderInfo) -> str:
    """Render the header block (marker + status line + metadata bullets).

    The first line is ALWAYS the hidden marker so future
    :func:`find_stage_comment_id` re-locates this comment.  A non-running status
    appends a finished-timestamp line (e.g. ``- done : 2026-06-05 14:30``)
    ONLY for terminal statuses (done / interrupted / blocked / cancelled).

    Args:
        info: The canonical header fields rebuilt from persisted state by a
            producer.

    Returns:
        The header block as a newline-joined string (marker first).
    """
    badge = BADGES[info.status]
    label = LABELS[info.status]
    lines = [
        marker(info.stage),
        f"### {badge} {info.stage} — {label}",
        f"- session : `{info.session}` · profile `{info.profile}` · mode `{info.mode}`",
        f"- started : {info.started} · worktree `{info.worktree}`",
        f"- logs : `{info.log_hint}`",
    ]
    # WAITING sticky only (31.2): a concrete drop-in command so the operator can attach to the
    # session and answer the pending prompt. Rendered only when an attach hint is supplied AND the
    # status is "waiting" (other statuses never carry one), keeping the terminal headers unchanged.
    if info.status == "waiting" and info.attach_hint:
        lines.append(f"- answer : `{info.attach_hint}`")
    prefix = _FINISHED_PREFIX.get(info.status)
    if prefix and info.finished:
        lines.append(f"- {prefix} : {info.finished}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State → header builder
# ---------------------------------------------------------------------------


def header_from_state(
    state: Mapping[str, object],
    issue: int,
    stage: str,
    status: StageStatus,
    *,
    finished: str = "",
) -> HeaderInfo:
    """Rebuild a canonical ``HeaderInfo`` from a persisted-state mapping.

    Accepts a ``Mapping[str, object]`` superset so callers can pass a widened
    :class:`~kanbanmate.ports.store.TicketState` via ``dataclasses.asdict(state)``
    or any other state-like mapping. ``asdict`` of the widened ``TicketState``
    (8.1.d) yields exactly the keys this builder reads — ``session_id`` /
    ``profile`` / ``mode`` / ``started`` (an epoch float) / ``worktree`` — so
    every producer (launch 🟡 / advance ✅ / session-end ⚠️ / reaper ⛔) renders
    the SAME metadata bullets the PoC did, full parity. The module stays PURE:
    it accepts a mapping rather than importing ``TicketState`` (that would
    breach the ``core``-imports-nothing-with-I/O layering rule), and the caller
    converts the dataclass to a dict at the boundary.

    Every missing field defaults to ``""`` — the header degrades gracefully
    when metadata is absent, which is normal for old-format on-disk state
    records that predate the widened ``TicketState`` (8.1.d).

    Field mapping (NEW's keys — these differ from the PoC's):

    * ``session`` ← first non-empty of ``session_uuid``, ``session_id``
    * ``profile`` ← ``profile``
    * ``mode`` ← first non-empty of ``permission_mode``, ``mode``
    * ``started`` ← :func:`fmt_timestamp` of first non-empty of
      ``started_at``, ``started`` (a ``TicketState.started`` epoch float
      formats straight through ``fmt_timestamp``)
    * ``worktree`` ← ``Path(worktree).name``

    Args:
        state: A mapping of persisted ticket fields (superset; extra keys are
            silently ignored).
        issue: The issue number (used to build the ``kanban logs`` hint).
        stage: The exact v2 column name owning the sticky.
        status: One of ``running`` / ``done`` / ``interrupted`` / ``blocked`` /
            ``cancelled``.
        finished: Pre-formatted termination timestamp (empty when running).

    Returns:
        The canonical ``HeaderInfo`` for the stage sticky.
    """

    def _first(*keys: str) -> str:
        for k in keys:
            v = state.get(k)
            if v is not None and v != "":
                return str(v)
        return ""

    started_raw = state.get("started_at") or state.get("started") or ""

    return HeaderInfo(
        stage=stage,
        status=status,
        session=_first("session_uuid", "session_id"),
        profile=_first("profile"),
        mode=_first("permission_mode", "mode"),
        started=fmt_timestamp(started_raw),
        finished=finished,
        worktree=Path(_first("worktree")).name,
        log_hint=f"kanban logs {issue}",
    )
