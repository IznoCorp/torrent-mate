"""App-layer rolling project status-update reporter (phase-24 §24.3, fail-soft).

This module is the imperative shell around the PURE dashboard render in
:mod:`kanbanmate.core.status_update`. It owns the ONE on-change refresh of the
Project's "Status updates" section every tick goes through: it appends this
tick's executed actions to the recent-events ring, gathers an
:class:`~kanbanmate.core.status_update.OrchestrationState` from the live running
tickets + the snapshot + the queue + the kill-switch flag (reading each running
agent's latest progress milestone off its issue sticky), renders the dashboard,
and posts it to GitHub — but ONLY when the body hash differs from the
last-posted one (no per-tick spam). The first post is a
:meth:`~kanbanmate.ports.board.ProjectStatusReporter.create_status_update`;
every later on-change refresh is an
:meth:`~kanbanmate.ports.board.ProjectStatusReporter.update_status_update` of the
persisted id (with a fresh create as the fallback when the stored id went
stale).

**Fail-soft is the whole point** (phase-24 §24): the rolling status update is
*observability*, NEVER a launch blocker. :func:`report_status` wraps its entire
body so ANY exception — network, parse, missing data — is logged at WARNING and
swallowed: it must never raise into :func:`kanbanmate.app.tick.tick` or block a
launch. Reading each agent's progress is *individually* fail-soft too, so one
bad sticky read degrades that single agent's ``progress`` to ``None`` (the pure
render already omits the progress line) rather than dropping the whole update.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` but MUST NOT
import ``cli`` or ``daemon`` (DESIGN §3.2). This module imports only ``core`` +
``ports`` and speaks to GitHub exclusively through the injected
:class:`~kanbanmate.ports.board.ProjectStatusReporter` /
:class:`~kanbanmate.ports.board.BoardWriter` Protocols (the production client's
mutations carry its mandatory connect+read timeouts).
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from kanbanmate.core.domain import ActionKind, BoardSnapshot
from kanbanmate.core.stage_comment import marker, split_sticky
from kanbanmate.core.status_update import (
    OrchestrationState,
    RunningAgent,
    StatusEvent,
    StatusUpdateRender,
    render_status,
)
from kanbanmate.ports.store import TicketStatus

if TYPE_CHECKING:  # pragma: no cover - import only for type checking (no runtime cycle)
    from kanbanmate.app.actions import Deps
    from kanbanmate.app.tick import TickConfig
    from kanbanmate.ports.store import TicketState

logger = logging.getLogger(__name__)

# Maps a decided/executed :class:`~kanbanmate.core.domain.ActionKind` to the
# coarse event ``kind`` the recent-events ring records (and the pure render's
# emoji table keys, :data:`kanbanmate.core.status_update.EVENT_EMOJI`). RESET is
# folded into ``teardown`` (a Cancel→Backlog reset is part of the same teardown
# story); ROLLBACK is a guarded bounce — surfaced as a neutral ``rollback`` the
# render falls back to a bullet for. A gate verdict (RUN_SCRIPT) is mapped at the
# call site (pass vs fail), so it is intentionally absent here.
_ACTION_EVENT_KIND: dict[ActionKind, str] = {
    ActionKind.LAUNCH: "launch",
    ActionKind.TEARDOWN: "teardown",
    ActionKind.RESET: "teardown",
    ActionKind.BLOCK: "block",
    ActionKind.ROLLBACK: "rollback",
}


# Per-agent progress-read TTL cache (#10). ``_latest_progress`` calls ``list_issue_comments`` —
# one network read PER AGENT PER TICK, BEFORE the on-change hash check — so 3 agents at the 10s
# cadence cost ~1080 reads/hour of pure waste. A short TTL cache collapses that to ~once/minute per
# agent: a cache HIT within the TTL returns the last value without a network read. Module-level so it
# survives across the per-tick ``report_status`` calls (each gets a fresh ``deps``). Keyed by
# ``(issue, stage)``; the value is ``(expiry_ts, progress)``.
_PROGRESS_TTL_SECONDS = 60.0
_progress_cache: dict[tuple[int, str], tuple[float, str | None]] = {}


def event_kind_for_action(kind: ActionKind) -> str:
    """Translate an executed :class:`ActionKind` to its recent-events ring kind.

    A RUN_SCRIPT verdict is NOT mapped here — its event is recorded at the tick
    call site as ``gate_pass`` / ``gate_fail`` from the script's exit code (the
    :class:`ActionKind` alone cannot tell pass from fail). Any unmapped kind
    (e.g. NOOP, or RUN_SCRIPT if it ever reaches here) degrades to ``"auto"`` so
    the ring never crashes on an unforeseen kind.

    Args:
        kind: The executed action's :class:`ActionKind`.

    Returns:
        The coarse event-kind string for the recent-events ring.
    """
    return _ACTION_EVENT_KIND.get(kind, "auto")


def _latest_progress(deps: Deps, issue: int, stage: str, now: float) -> str | None:
    """Read the LATEST kanban-progress milestone off ``issue``'s ``stage`` sticky (TTL-cached, #10).

    Locates the stage sticky by its hidden HTML marker (reusing the pure
    :func:`kanbanmate.core.stage_comment.marker` /
    :func:`~kanbanmate.core.stage_comment.split_sticky` helpers), splits the
    body, and returns the LAST progress line (the agent appends newest-last) with
    its ``- HH:MM — `` stamp stripped to the bare milestone text. Returns ``None``
    when the issue has no sticky, the sticky carries no progress yet, or anything
    goes wrong — the call is INDIVIDUALLY fail-soft so one bad sticky read never
    drops the whole update (the pure render omits the progress line on ``None``).

    **TTL-cached (#10).** ``list_issue_comments`` is a network read that ran per-agent EVERY tick;
    a per-``(issue, stage)`` cache with a ``_PROGRESS_TTL_SECONDS`` TTL serves a cached value within
    the window instead of re-reading, cutting ~1080 wasted reads/hour (3 agents @ 10s) to ~once/min.

    Args:
        deps: The injected adapter bundle; ``deps.board_writer.list_issue_comments``
            is the comment-reader seam (the production client carries timeouts).
        issue: The issue number whose sticky to read.
        stage: The stage (column key) owning the sticky to locate.
        now: The tick's wall-clock time (the TTL reference).

    Returns:
        The latest progress milestone text, or ``None`` on a miss / error.
    """
    # Cache HIT within the TTL → return the last value, NO network read (#10).
    cached = _progress_cache.get((issue, stage))
    if cached is not None and now < cached[0]:
        return cached[1]
    result = _read_progress_uncached(deps, issue, stage)
    # Store with a fresh expiry so the next tick within the TTL reuses it.
    _progress_cache[(issue, stage)] = (now + _PROGRESS_TTL_SECONDS, result)
    return result


def _read_progress_uncached(deps: Deps, issue: int, stage: str) -> str | None:
    """Perform the actual sticky read for :func:`_latest_progress` (the network leg).

    Args:
        deps: The injected adapter bundle (the comment-reader seam).
        issue: The issue number whose sticky to read.
        stage: The stage owning the sticky to locate.

    Returns:
        The latest progress milestone text, or ``None`` on a miss / error.
    """
    try:
        needle = marker(stage)
        located = next(
            (c for c in deps.board_writer.list_issue_comments(issue) if needle in (c.body or "")),
            None,
        )
        if located is None:
            return None
        _header, progress = split_sticky(located.body or "")
        if not progress:
            return None
        # Strip the leading "- HH:MM — " stamp the agent's progress append adds
        # (core.stage_comment._stamp), leaving the bare milestone text. The split
        # is best-effort: an unstamped line falls through unchanged.
        latest = progress[-1].lstrip("- ").strip()
        if " — " in latest:
            latest = latest.split(" — ", 1)[1].strip()
        return latest or None
    except Exception:  # noqa: BLE001 — per-agent fail-soft: one bad read must not drop the update
        logger.warning(
            "status reporter: progress read failed for #%s stage=%r; omitting progress",
            issue,
            stage,
            exc_info=True,
        )
        return None


def _running_agent(
    deps: Deps, state: TicketState, snapshot: BoardSnapshot | None, now: float
) -> RunningAgent:
    """Map one persisted running :class:`TicketState` to a :class:`RunningAgent`.

    Fields are sourced from what is persisted plus the snapshot: the title comes
    from the matching snapshot board item when available (else ``""``); the
    current column is the snapshot item's ``column_key`` (used as ``to_col``;
    ``from_col`` is left ``""`` because the launch transition's origin is not
    persisted on the state); the profile/launch time come straight off the state;
    the heartbeat age is ``now - state.heartbeat`` (the render shows ``❤ —`` for a
    missing one); and the progress is the latest sticky milestone (``None`` on a
    miss — read individually fail-soft in :func:`_latest_progress`).

    Args:
        deps: The injected adapter bundle (the comment-reader for progress).
        state: The persisted running ticket state.
        snapshot: The current board snapshot (for the title + current column), or
            ``None`` when no snapshot was taken this tick.
        now: The tick's wall-clock time (the heartbeat-age reference).

    Returns:
        The assembled :class:`RunningAgent` snapshot for the render.
    """
    issue = state.issue_number
    title = ""
    to_col = state.stage
    if snapshot is not None:
        for ticket in snapshot.tickets:
            if ticket.issue_number == issue:
                title = ticket.title
                # The live board column is the most accurate "to" — fall back to
                # the persisted launch stage when the item is off-snapshot.
                to_col = ticket.column_key or state.stage
                break
    # Resolve the REAL issue title off the snapshot board item (above). When the title is
    # genuinely absent (no snapshot this tick — the probe was unchanged — or the item is
    # off-snapshot) fall back to the BARE ``#<n>`` reference (phase-25 §25.4, bug E), NOT the
    # empty string that left the dashboard rendering ``**#140** [#140]`` — the bracketed ``[#n]``
    # was the ``code`` tag (now the profile) and the trailing title was empty, producing the
    # doubled placeholder. A bare ``#<n>`` title reads cleanly when the live title is unavailable.
    if not title:
        title = f"#{issue}"
    # A 0.0/absent heartbeat means "no heartbeat recorded yet" → None (the render
    # shows "❤ —"); otherwise the age since the last liveness touch.
    heartbeat_age = (now - state.heartbeat) if state.heartbeat else None
    progress = _latest_progress(deps, issue, state.stage, now) if state.stage else None
    return RunningAgent(
        issue=issue,
        # ``code`` is the short TYPE TAG rendered in brackets (``[docs]`` / ``[LLM]``; see
        # RunningAgent.code) — the agent's permission PROFILE is the natural tag. It was wrongly
        # set to ``f"#{issue}"``, which DUPLICATED the leading ``**#<n>**`` as ``[#<n>]`` (bug E).
        # An empty profile degrades to a neutral ``"agent"`` tag so the bracket is never bare.
        code=state.profile or "agent",
        title=title,
        from_col="",
        to_col=to_col,
        profile=state.profile,
        launched_at=state.started or state.heartbeat or now,
        heartbeat_age=heartbeat_age,
        progress=progress,
        # Phase-27 §B: a WAITING ticket renders the ⏳ marker + pushes the pill to AT_RISK. The
        # store's ``list_running`` now returns WAITING tickets alongside RUNNING, so the reporter
        # observes them here straight off the persisted status.
        waiting=state.status is TicketStatus.WAITING,
    )


def _to_status_event(record: dict[str, object]) -> StatusEvent:
    """Coerce a persisted ring event dict into a :class:`StatusEvent` for render.

    The ring persists small JSON dicts (``ts`` / ``kind`` / ``issue`` / ``detail``);
    this coerces each field to the frozen value object's type, degrading a
    missing/odd value to a safe default so a hand-edited ring never crashes the
    render.

    Args:
        record: One persisted ring event mapping.

    Returns:
        The :class:`StatusEvent` for :func:`render_status`.
    """
    raw_issue = record.get("issue")
    issue = raw_issue if isinstance(raw_issue, int) else None
    raw_ts = record.get("ts")
    ts = float(raw_ts) if isinstance(raw_ts, (int, float)) else 0.0
    return StatusEvent(
        ts=ts,
        kind=str(record.get("kind", "")),
        issue=issue,
        detail=str(record.get("detail", "")),
    )


def _recreate_rolling_update(deps: Deps, render: StatusUpdateRender, *, old_id: str | None) -> None:
    """Create a FRESH rolling status update and best-effort delete the superseded one.

    GitHub only refreshes a Project's denormalised status PILL when a status
    update is *created* — an in-place ``update`` mutates the record's fields
    (visible via the API) but leaves the project pill frozen at the value the
    rolling update had when it was first created (observed live: a board stuck
    ``OFF_TRACK`` for days while the record read ``ON_TRACK``). So both the
    enum-changed refresh AND the stale-id recovery path funnel through here:
    create the new update, persist its id, then delete the old one so the board
    keeps a SINGLE rolling pill. The delete is best-effort (a lingering orphan is
    cosmetic, never a launch blocker) — a failure is logged and swallowed.

    Args:
        deps: The injected adapter bundle (``status_reporter`` + ``store`` +
            ``project_id``).
        render: The :class:`~kanbanmate.core.status_update.StatusUpdateRender`
            carrying the body + status enum to post.
        old_id: The superseded rolling-update node id to delete after the
            create, or ``None`` when there is none (first post / post-rebind).
    """
    new_id = deps.status_reporter.create_status_update(deps.project_id, render.body, render.status)
    deps.store.set_status_update_id(new_id)
    if old_id is not None:
        # Best-effort cleanup so the project keeps a single rolling pill (phase-36).
        try:
            deps.status_reporter.delete_status_update(old_id)
        except Exception:  # noqa: BLE001 — orphan cleanup is best-effort, never fatal
            logger.warning(
                "status reporter: delete of superseded update %s failed; it lingers",
                old_id,
                exc_info=True,
            )


def report_status(
    deps: Deps,
    config: TickConfig,
    *,
    running: tuple[TicketState, ...],
    snapshot: BoardSnapshot | None,
    queue_depth: int,
    paused: bool,
    events: list[tuple[str, int | None, str]],
    now: float,
) -> None:
    """Refresh the rolling project status update on change (the tick's last step).

    Wholly **fail-soft** (phase-24 §24): the entire body is wrapped so ANY
    exception is logged at WARNING and swallowed — it NEVER raises into the tick
    or blocks a launch. The flow:

    1. Append THIS tick's executed ``events`` (each an
       ``(ActionKind, issue, detail)`` triple) to the persisted recent-events
       ring (≤10 newest), translated to the coarse ring kind.
    2. Build the :class:`OrchestrationState` from the running tickets (one
       :class:`RunningAgent` each, with per-agent progress read fail-soft), the
       queue depth, the concurrency cap, the (newest-first-rendered) ring, the
       kill-switch flag, and ``now``.
    2b. Project-rebind guard (phase-33): when the persisted status state belongs
       to a DIFFERENT project than ``deps.project_id`` (the registry was
       re-pointed at a new board), drop the stale ``update_id`` + ``body_hash`` and
       re-bind the marker to the current project, so the new board gets a fresh
       create rather than an ``update`` of the old board's pill (or a hash-match
       suppression).
    3. :func:`render_status` it; hash the body; compare to the stored hash. EQUAL
       → do nothing (no API call). DIFFERENT → ``update`` the stored id (falling
       back to ``create`` when the id is stale/absent or the update raises), then
       persist the new id (on a create) and the new body hash.

    Args:
        deps: The injected adapter bundle — ``deps.status_reporter`` (the
            :class:`~kanbanmate.ports.board.ProjectStatusReporter`),
            ``deps.board_writer`` (the comment-reader), ``deps.store`` (the ring +
            id/hash state), and ``deps.project_id`` (the board to post on).
        config: The per-tick policy inputs; ``concurrency_cap`` feeds the render.
        running: The persisted running :class:`TicketState` tuple (the agents).
        snapshot: The board snapshot taken this tick (for titles + current
            columns), or ``None`` when the probe was unchanged.
        queue_depth: The number of launches waiting in the concurrency queue.
        paused: Whether the kill-switch is engaged (→ ``INACTIVE`` health).
        events: This tick's executed actions as ``(kind, issue, detail)`` triples,
            where ``kind`` is the ALREADY-RESOLVED ring kind string
            (``launch`` / ``teardown`` / ``gate_pass`` / ``gate_fail`` / ``auto`` /
            ``block`` / ``reap`` …). The tick resolves the generic-action kinds via
            :func:`event_kind_for_action` and the gate/reap distinctions (which an
            :class:`ActionKind` alone cannot express) directly. Only actions that
            RAN this tick belong here.
        now: The tick's wall-clock time (heartbeat ages + the render timestamp).
    """
    try:
        # 1. Append this tick's executed actions to the bounded ring (≤10 newest).
        #    Each append is independently guarded so one bad write never aborts the
        #    whole report (and never the tick). ``kind`` arrives already resolved.
        for kind, issue, detail in events:
            try:
                deps.store.append_status_event(
                    {"ts": now, "kind": kind, "issue": issue, "detail": detail}
                )
            except Exception:  # noqa: BLE001 — a bad ring write must not drop the update
                logger.warning(
                    "status reporter: failed to append event %r; continuing", kind, exc_info=True
                )

        # 2. Build the orchestration snapshot. One RunningAgent per running ticket,
        #    each with its progress read individually fail-soft; the ring is read
        #    back (oldest-first) and coerced to StatusEvents (render sorts newest-
        #    first). A poison ring degrades to () inside the store.
        agents = tuple(_running_agent(deps, st, snapshot, now) for st in running)
        ring = tuple(_to_status_event(r) for r in deps.store.read_status_events())
        state = OrchestrationState(
            agents=agents,
            queue_depth=queue_depth,
            cap=config.concurrency_cap,
            events=ring,
            paused=paused,
            now=now,
        )

        # 2b. Project-rebind guard (phase-33). The id/hash markers are BOARD-WIDE,
        #     so after the operator re-points the registry at a NEW project the
        #     stored id points at the OLD board and the stored hash would suppress
        #     the first post on the new one. Detect the rebind by comparing the
        #     bound project id to the live one: on a mismatch (or a never-bound
        #     marker), drop the stale id+hash so the block below treats this as a
        #     first post, and re-bind the marker to the current project.
        rebound = deps.store.get_status_project_id() != deps.project_id
        if rebound:
            deps.store.set_status_update_id(None)
            deps.store.set_status_body_hash(None)
            deps.store.set_status_last_enum(None)
            deps.store.set_status_project_id(deps.project_id)

        # 3. Render + diff-on-change. Hash the body; an equal stored hash means the
        #    dashboard is unchanged → POST NOTHING (the on-change discipline, §24).
        #    A rebind just cleared the hash above, so the new board always posts.
        render = render_status(state)
        body_hash = hashlib.sha256(render.body.encode("utf-8")).hexdigest()
        if body_hash == deps.store.get_status_body_hash():
            return

        # The body changed → post. WHICH mutation depends on whether the health
        # ENUM changed: GitHub only refreshes a Project's denormalised status PILL
        # when a status update is *created*, never on an in-place ``update`` (the
        # in-place update DOES change the record's body + status fields the API
        # returns, but the project pill stays frozen at the value the rolling
        # update had at creation — observed live: a board stuck OFF_TRACK for days
        # while the record read ON_TRACK). So:
        #   • enum CHANGED (or first post)  → re-create (moves the pill).
        #   • enum SAME, body-only change   → cheap in-place update (pill already
        #     correct for this enum; avoids per-change pill churn / spam).
        update_id = deps.store.get_status_update_id()
        enum_changed = render.status != deps.store.get_status_last_enum()
        if update_id is not None and not enum_changed:
            try:
                deps.status_reporter.update_status_update(update_id, render.body, render.status)
            except Exception:  # noqa: BLE001 — stale id: recover by re-creating the rolling update
                logger.warning(
                    "status reporter: update of %s failed; re-creating the rolling update",
                    update_id,
                    exc_info=True,
                )
                _recreate_rolling_update(deps, render, old_id=update_id)
        else:
            # First post (no id) OR the enum changed: re-create so GitHub moves the
            # project status pill, deleting the superseded update (if any).
            _recreate_rolling_update(deps, render, old_id=update_id)

        # Persist the new body hash + enum so the next tick detects an unchanged
        # body (skip) and an enum change (re-create).
        deps.store.set_status_body_hash(body_hash)
        deps.store.set_status_last_enum(render.status)
    except Exception:  # noqa: BLE001 — observability only: NEVER raise into the tick / block a launch
        logger.warning("status reporter: refresh failed; the dashboard is stale", exc_info=True)
