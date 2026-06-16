"""App-layer per-card Health field reporter (health-field, fail-soft, on-change).

This module is the imperative shell around the PURE per-card mapping in
:mod:`kanbanmate.core.health`. It maintains a custom per-card "Health" single-select
field on the board (the chip carrying the operator's OWN vocabulary — a workaround for
GitHub's fixed, un-renameable status-update pill enum). Every tick that took a snapshot:

1. ensures the "Health" field exists (lazily, once, cached cross-restart in the store);
2. computes each card's Health from its live agent state + column (PURE);
3. writes ONLY the cards whose computed value CHANGED (the on-change discipline — the
   per-card last-written value is persisted, so unchanged cards cost zero API calls).

**Fail-soft is the whole point** (mirrors :func:`kanbanmate.app.status_reporter.report_status`):
:func:`apply_health` wraps its entire body so ANY exception — network, parse, missing
data — is logged at WARNING and swallowed; it must NEVER raise into
:func:`kanbanmate.app.tick.tick` or block a launch. Each per-card write is INDIVIDUALLY
guarded too, so one bad card never drops the rest. The Health chips are observability,
never load-bearing.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` but MUST NOT import
``cli`` or ``daemon`` (DESIGN §3.2). This module imports only ``core`` + ``ports`` and
speaks to GitHub exclusively through the injected
:class:`~kanbanmate.ports.board.ProjectHealthReporter` Protocol (the production client's
mutations carry its mandatory connect+read timeouts).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kanbanmate.adapters.github.types import HealthField
from kanbanmate.core.domain import BoardSnapshot
from kanbanmate.core.health import compute_health
from kanbanmate.ports.store import TicketStatus

if TYPE_CHECKING:  # pragma: no cover - import only for type checking (no runtime cycle)
    from kanbanmate.app.actions import Deps
    from kanbanmate.app.tick import TickConfig
    from kanbanmate.ports.store import TicketState

logger = logging.getLogger(__name__)


class _NullHealthReporter:
    """A no-op :class:`~kanbanmate.ports.board.ProjectHealthReporter` (the safe default).

    Satisfies the port so :class:`~kanbanmate.app.actions.Deps` defaults to a reporter that
    touches NOTHING — used when no real GitHub client is wired (offline tests, legacy
    ``Deps(...)`` constructions that predate the health-field feature).
    :meth:`ensure_health_field` returns an empty :class:`HealthField` and
    :meth:`set_item_health` is a no-op, so a tick whose reporter is this null one never
    touches the network (the Health chips are observability, never load-bearing).

    Lives here (not in :mod:`kanbanmate.app.actions`) so ``actions.py`` — already at the
    1000-LOC ceiling — only IMPORTS the no-op rather than carrying its body.
    """

    def ensure_health_field(self, project_id: str) -> HealthField:
        """Return an empty Health field (no network). See the class docstring.

        Args:
            project_id: Ignored.

        Returns:
            An empty :class:`HealthField` (no field id, no options).
        """
        return HealthField(field_id="", options={})

    def set_item_health(self, item_id: str, value: str) -> None:
        """No-op (no write). See the class docstring.

        Args:
            item_id: Ignored.
            value: Ignored.
        """
        return None


def _ensure_field_cached(deps: Deps) -> HealthField | None:
    """Resolve the Health field, preferring the store's cross-restart cache.

    A cache HIT (both the field id and a non-empty options map are persisted) returns a
    :class:`HealthField` with NO network call — the daemon's every-tick fast path. A miss
    ensures the field via the reporter (creating it the first time post-merge/restart),
    then persists the field id + options so later ticks (and later restarts) hit the cache.

    Args:
        deps: The injected adapter bundle (``health_reporter`` + ``store`` + ``project_id``).

    Returns:
        The resolved :class:`HealthField`, or ``None`` when the ensure produced no usable
        field (an empty id/options — e.g. the null reporter) so the caller skips the step.
    """
    field_id = deps.store.get_health_field_id()
    options = deps.store.get_health_options()
    if field_id and options:
        return HealthField(field_id=field_id, options=options)
    # Cache miss → ensure via GitHub (creates the field the first time), then persist so
    # every later tick is a cheap cache hit.
    field = deps.health_reporter.ensure_health_field(deps.project_id)
    if not field.field_id or not field.options:
        return None  # null reporter / unusable field → render nothing
    deps.store.set_health_field_id(field.field_id)
    deps.store.set_health_options(field.options)
    return field


def apply_health(
    deps: Deps,
    config: TickConfig,
    *,
    running: tuple[TicketState, ...],
    snapshot: BoardSnapshot | None,
    now: float,
) -> None:
    """Set each card's Health value ON CHANGE (the tick's fail-soft Health step).

    Wholly **fail-soft**: ANY exception is logged WARNING and swallowed — it NEVER raises
    into :func:`kanbanmate.app.tick.tick` or blocks a launch (mirrors
    :func:`kanbanmate.app.status_reporter.report_status`). Skips entirely when no snapshot
    was taken this tick (no fresh card→column view to act on — the cheap probe was
    unchanged, so nothing could have moved).

    The flow:

    1. Project-rebind guard: when the store's bound project differs from
       ``deps.project_id`` (the registry was re-pointed at a new board), drop the stale
       field id/options + every per-card last-written marker, then re-bind.
    2. Ensure the Health field (store-cached after the first ensure; created on the first
       tick post-merge/restart).
    3. For each snapshot card: derive its live status (RUNNING/WAITING/None) from the
       running set, compute its Health (PURE), and write it ONLY when it differs from the
       persisted last-written value — then persist the new value.

    Args:
        deps: The injected adapter bundle — ``deps.health_reporter`` (the
            :class:`~kanbanmate.ports.board.ProjectHealthReporter`), ``deps.store`` (the
            field/option/last-written markers), and ``deps.project_id`` (the bound board).
        config: The per-tick policy inputs; ``blocked_column`` / ``done_column`` thread
            into the pure mapping so it is not hardcoded to the default labels.
        running: The persisted LIVE ticket states (RUNNING + WAITING — the same view
            :func:`report_status` consumes), used to derive each card's agent state.
        snapshot: The board snapshot taken this tick (the card→column view), or ``None``
            when the probe was unchanged (the step early-returns then).
        now: The tick's wall-clock time (accepted for signature symmetry with
            ``report_status``; the Health step itself is time-independent).
    """
    if snapshot is None:
        return  # nothing fresh to reconcile; the cheap probe was unchanged
    try:
        # 1. Project-rebind guard (mirror report_status §2b): the field id/options +
        #    per-card markers are board-wide, so after a registry re-point they belong to
        #    the OLD board — drop them + re-bind so the new board gets a fresh ensure.
        if deps.store.get_health_project_id() != deps.project_id:
            deps.store.clear_health_markers()
            deps.store.set_health_project_id(deps.project_id)

        # 2. Resolve the field (store cache hit, else ensure+persist). ``None`` → no usable
        #    field (e.g. the null reporter) → render nothing this tick.
        field = _ensure_field_cached(deps)
        if field is None:
            return

        # Build {issue -> live status} from the running set (RUNNING/WAITING). A card with
        # no entry has no live agent.
        live: dict[int, TicketStatus] = {st.issue_number: st.status for st in running}

        for ticket in snapshot.tickets:
            try:
                # A draft item (no linked issue) can never have an agent → None status.
                status = live.get(ticket.issue_number) if ticket.issue_number is not None else None
                value = compute_health(
                    is_running=status is TicketStatus.RUNNING,
                    is_waiting=status is TicketStatus.WAITING,
                    column_key=ticket.column_key,
                    blocked_column=config.blocked_column,
                    done_column=config.done_column,
                )
                # ON-CHANGE: skip a card whose computed value equals the last-written one
                # (no per-tick API spam). A first-seen card (None) always writes.
                if value == deps.store.get_item_health(ticket.item_id):
                    continue
                deps.health_reporter.set_item_health(ticket.item_id, value)
                deps.store.set_item_health(ticket.item_id, value)
            except Exception:  # noqa: BLE001 — per-card fail-soft: one bad card must not drop the rest
                logger.warning(
                    "health: write failed for item %s; continuing",
                    ticket.item_id,
                    exc_info=True,
                )

        # 3. Bounded GC (Candidate 3): drop per-card ``health/last/<item>`` markers for cards no
        #    longer on the board so the marker directory stays proportional to the live board (it
        #    previously grew unbounded — nothing pruned a card that left). Fail-soft (the whole
        #    apply_health body already swallows; the store method is itself fail-soft too).
        deps.store.prune_item_health({t.item_id for t in snapshot.tickets})
    except Exception:  # noqa: BLE001 — observability only: NEVER raise into the tick / block a launch
        logger.warning("health: refresh failed; card chips are stale", exc_info=True)
