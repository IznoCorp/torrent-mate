"""The concurrency-cap queue drain: the tick's post-step that re-launches queued tickets.

Extracted from :mod:`kanbanmate.app.tick` (18.6 LOC budget — moving the already-running guard
above ``reserve_slot`` plus the explanatory comments pushed tick.py over the 1000-LOC hard ceiling;
the drain is a self-contained, cohesive seam that lifts out cleanly, mirroring the earlier
:mod:`kanbanmate.app.reaper` (15.6) and :mod:`kanbanmate.app.depgate` (#13) extractions).

The per-action watchdog (:func:`kanbanmate.app.tick._run_with_watchdog`) is LAZILY imported inside
:func:`_drain_queue` to avoid a circular import (``tick`` imports this module to call the drain
step). The watchdog stays in ``tick`` because the reaper and the main loop also use it, and a test
monkeypatches ``tick._run_with_watchdog`` for the drain path — the lazy lookup honours that patch.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2); this module names
only the launch action / adapter bundle plus the pure core.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from kanbanmate.app.actions import Deps, LaunchAction
from kanbanmate.core.domain import Ticket
from kanbanmate.ports.store import LIVE_STATUSES

if TYPE_CHECKING:
    from kanbanmate.app.tick import TickConfig

logger = logging.getLogger(__name__)


def _drain_queue(
    deps: Deps,
    config: TickConfig,
    executor: ThreadPoolExecutor,
    now: float,
    *,
    kill_switch: bool = False,
) -> None:
    """Drain the concurrency-cap queue, re-launching queued tickets when slots free (gate 13.5).

    Port of the PoC ``engine/reaper.py`` dequeue/apply path. Queued tickets are processed in
    lexicographic ``ticket-<n>`` marker order (a faithful port of the PoC ``sorted(glob(…))``,
    not numeric). For each queued ticket the drain:

    1. **already-running guard (13.7 timeout mitigation), CHECKED FIRST — before any slot
       reservation (Md2):** if the issue already has a RUNNING persisted state (e.g. a launch the
       watchdog abandoned that completed late), the ticket is already live — just clear the
       now-redundant marker and move on WITHOUT re-dispatching, so a tmux ``new-session
       check=True`` does not fail on the duplicate session name and churn. Crucially this branch
       does NOT ``reserve_slot`` (idempotent → it would no-op on the slot the live ticket already
       holds) and does NOT ``release_slot``: ``release_slot`` is the slot+retries teardown that
       unconditionally unlinks ``slots/ticket-<issue>`` AND every ``retries/<issue>__*`` marker, so
       calling it here would strip the LIVE ticket's pre-existing slot + fix-CI budgets — the cap
       would undercount (an extra agent could exceed ``concurrency_cap``) and in-flight retry
       budgets would be zeroed. The live session stays tracked by its RUNNING state (the reaper
       owns it via ``list_running``), so dropping only the queue marker is safe;
    2. tries to reserve a slot — when the cap is full it leaves the marker in place for the next
       sweep and moves on, so the drain NEVER exceeds the cap (PoC ``reaper.py`` no-free-slot skip);
    3. reads the rich queue payload and, when it is missing / has no ``item_id``, releases the slot
       (slot-only), clears the unlaunchable marker, logs ONE warning (visible, not a silent drop —
       PoC's empty/invalid-inputs diagnostic) and moves on;
    4. otherwise rebuilds a :class:`~kanbanmate.app.actions.LaunchAction` FAITHFUL to the one the
       cap gate would have dispatched directly (the rich payload preserves the filled
       per-transition ``/implement:*`` prompt — operator decision 2026-06-06), dispatches it under
       the watchdog, and:
       * on success clears the queue marker (the ticket is now running; its slot backs the session);
       * on failure releases the just-reserved slot (slot-only :meth:`release_slot`, 13.7) and KEEPS
         the marker for a later sweep (no leak, NO DROP — the CRITICAL keep-marker invariant the
         13.7 PoC split restores; the exhaustive purge would have deleted the marker we mean to keep).

    **Launch WHILE the marker still exists** (the PoC's race-closing rule): the marker is cleared
    ONLY after a confirmed successful launch, so a crash mid-launch leaves a re-tryable marker
    rather than dropping the ticket.

    Args:
        deps: The injected adapter bundle (the store port + the launch adapters).
        config: The per-tick policy inputs; ``concurrency_cap`` bounds the drain.
        executor: The shared thread pool backing the per-action watchdog.
        now: The current wall-clock time (informational; the rebuilt launch reads its own clock).
        kill_switch: When ``True`` (``~/.kanban/PAUSE`` active, defect 6) the drain launches NOTHING
            and reserves NO slot — it returns immediately, leaving EVERY queue marker intact so a
            resume re-drives them on a later tick. DESIGN §10 / CLAUDE.md "PAUSE stops launches".
    """
    # PAUSE short-circuit (defect 6): the drain is a LAUNCH path, so under the kill-switch it must
    # do nothing — no slot reservation, no dispatch — while preserving every queued marker (the
    # operator resumes by removing ~/.kanban/PAUSE; the next un-paused tick drains as normal).
    if kill_switch:
        return
    # Lazy import to break the tick <-> drain import cycle (tick imports this module to call the
    # drain step), and to honour a test monkeypatch of ``tick._run_with_watchdog`` for this path.
    from kanbanmate.app.tick import _run_with_watchdog

    for issue in deps.store.dequeue_pending():
        # Already-running guard FIRST — BEFORE reserve_slot (13.7 watchdog-timeout mitigation, Md2).
        # A launch the watchdog abandoned (it returned False on timeout) can complete late and
        # persist a RUNNING state while still holding its slot; its queue marker was never cleared.
        # If this queued issue is already live, re-dispatching would hit the tmux ``new-session
        # check=True`` on the duplicate ``ticket-<n>`` name and churn. So drop the now-redundant
        # queue marker and SKIP. Do NOT ``reserve_slot`` (idempotent → it would no-op on the slot
        # the live ticket already holds) and crucially do NOT ``release_slot``: it unconditionally
        # unlinks ``slots/ticket-<issue>`` AND every ``retries/<issue>__*`` fix-CI budget → the cap
        # would undercount (an extra agent could exceed the cap) and in-flight retries would be
        # zeroed. The live session stays tracked by its RUNNING state (the reaper owns it via
        # ``list_running``), so dropping only the queue marker is safe.
        existing = deps.store.load(issue)
        if existing is not None and existing.status in LIVE_STATUSES:
            # LIVE = RUNNING or WAITING (#3). A WAITING ticket is a live agent paused on a human
            # prompt; before #3 this guard tested RUNNING only, so re-dispatching a queued WAITING
            # ticket pre-killed its session (the idempotent launch kills the existing tmux session
            # first) and DISCARDED the pending human decision. Treating WAITING as live too closes
            # that hole — drop only the redundant queue marker and skip.
            deps.store.clear_queued(issue)
            continue
        # Only drain when a slot is ACTUALLY free; never exceed the cap. Leave the marker for the
        # next sweep when the cap is still full (PoC reaper no-free-slot skip). reserve_slot runs
        # ONLY for a non-running ticket, so the release paths below free a slot THIS iteration
        # actually reserved — never a live ticket's pre-existing slot.
        if not deps.store.reserve_slot(issue, config.concurrency_cap):
            continue
        payload = deps.store.load_queued(issue)
        if payload is None or "item_id" not in payload:
            # Unlaunchable marker (absent/corrupt payload, or a legacy ``{}`` marker with no
            # identity). Release the slot we just reserved and clear the marker so the ticket does
            # not churn reserve→release every sweep, and surface ONE warning so a wedged ticket is
            # visible to an operator (PoC's empty/invalid-inputs diagnostic — not a silent drop).
            deps.store.release_slot(issue)
            deps.store.clear_queued(issue)
            logger.warning(
                "drain: queued ticket #%s left queued — relaunch payload empty/invalid "
                "(no launch started); cleared the marker, needs an operator",
                issue,
            )
            continue
        # Rebuild a FAITHFUL launch from the RICH payload (operator decision — parity over
        # thinness). ``load_queued`` returns ``dict[str, object] | None``, so every value is typed
        # ``object``: coerce the ticket fields with ``str(...)`` and narrow the optional
        # prompt/script with ``isinstance`` so mypy strict is satisfied and a malformed value never
        # crashes the rebuild.
        raw_prompt = payload.get("prompt")
        prompt = raw_prompt if isinstance(raw_prompt, str) else None
        raw_script = payload.get("script")
        script = raw_script if isinstance(raw_script, str) else None
        ticket = Ticket(
            item_id=str(payload["item_id"]),
            issue_number=issue,
            title=str(payload.get("title") or f"ticket-{issue}"),
            column_key=str(payload.get("stage") or ""),
            body=str(payload.get("body") or ""),
        )
        command = LaunchAction(
            ticket=ticket,
            prompt=prompt,
            script=script,
            # Phase 20 (DESIGN §8.0.6): the transition's profile is the SOLE profile source, so the
            # rebuilt launch resolves the SAME profile a direct launch would from this persisted
            # value; an empty profile FAILS LOUD in ``_resolve_profile`` (no per-column default).
            profile=str(payload.get("profile") or ""),
            permission_mode=str(payload.get("permission_mode") or "auto"),
            on_fail=str(payload.get("on_fail") or ""),
            advance=str(payload.get("advance") or "stop"),
        )
        ok = _run_with_watchdog(executor, command, deps, config.action_timeout)
        if ok:
            # Launch confirmed: the ticket is now running (its slot backs the live session). Only
            # NOW clear the marker — the race-closing rule.
            deps.store.clear_queued(issue)
        else:
            # The launch timed out / raised (the watchdog logged + swallowed it). Release the slot
            # we just reserved so it does not leak, and KEEP the marker so a later sweep retries.
            # CRITICAL (13.7 #1): this is the SLOT-ONLY ``release_slot`` — it frees ONLY the slot and
            # leaves ``queue/ticket-<issue>`` intact. Before the 13.7 split, ``release_slot`` was the
            # exhaustive purge, so this very line DELETED the marker it means to keep — silently
            # DROPPING a transiently-failing queued ticket forever (its card sits in the agent column,
            # so the diff emits no transition and nothing re-enqueues it). The PoC kept slot-only and
            # exhaustive as two functions precisely to preserve this keep-marker-on-fail invariant.
            deps.store.release_slot(issue)
