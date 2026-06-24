"""Per-transition processing: decide → build → dispatch ONE detected board move.

Extracted from :mod:`kanbanmate.app.tick` (#3 + ceiling pressure). The tick's transition loop
body — the ``decide → _build_action → NOOP/RUN_SCRIPT/launch-gate/launch → baseline-advance``
pipeline for a single :class:`~kanbanmate.core.domain.Transition` — moved here so that:

* tick.py stays under the 1000-LOC hard ceiling (the #3 pre-launch already-live guard pushed it
  over), and
* each iteration can be wrapped in a per-iteration ``try/except`` in the tick (a mid-loop raise
  must advance the baseline and continue, never lose the partially-advanced baseline and replay a
  launch on the next tick — #3 isolation).

The function is a behaviour-preserving move: every branch (NOOP, Done-arrival teardown,
NOOP-forward finalize, RUN_SCRIPT routing, launch gate, pre-launch already-live guard, cap-divert
queue, dispatch + leak-safety release, ROLLBACK baseline) is byte-identical to its former home in
:func:`kanbanmate.app.tick.tick`. The shared mutable accumulators (``next_columns`` dict,
``status_events`` list) are passed in and mutated in place exactly as before; the rolled-up
``antiloop`` and the per-transition counter deltas are returned in a small result record so the
tick can fold them back into its running totals.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2). The per-action
watchdog helpers live in ``tick`` (the reaper + drain also use them); they are LAZILY imported
inside :func:`process_transition` both to break the ``tick ↔ transition_step`` import cycle and to
honour a test monkeypatch of ``tick._run_with_watchdog`` on this path.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from kanbanmate.app.actions import (
    BlockAction,
    DependencyBounceAction,
    Deps,
    LaunchAction,
    ResetAction,
    RollbackAction,
    RunScriptAction,
    TeardownAction,
)
from kanbanmate.app.body_status import update_body_status
from kanbanmate.app.done_arrival import close_done_issue, done_arrival_teardown
from kanbanmate.app.script_route import fixci_key, route_script_verdict, run_check_script
from kanbanmate.app.status_reporter import event_kind_for_action, latest_progress
from kanbanmate.core.antiloop import AntiLoopState, forget, record_move
from kanbanmate.core.columns import resolve_column
from kanbanmate.core.decide import DecideContext, decide
from kanbanmate.core.domain import Action, ActionKind, BoardSnapshot, Transition
from kanbanmate.ports.store import LIVE_STATUSES

if TYPE_CHECKING:
    # Imported only for typing: ``tick`` imports this module at runtime, so importing ``TickConfig``
    # at module scope would create a cycle. Under TYPE_CHECKING it costs nothing at import time.
    from kanbanmate.app.tick import TickConfig

logger = logging.getLogger(__name__)

# The concrete command union ``_build_action`` yields (mirrors ``tick._build_action`` exactly), or
# ``None`` for a NOOP. Named here so the dispatch call below typechecks without re-importing tick.
Command = (
    LaunchAction | TeardownAction | ResetAction | BlockAction | RollbackAction | RunScriptAction
)


def _session_alive_fail_closed(deps: Deps, issue: int) -> bool:
    """Probe whether ``ticket-<issue>``'s tmux session is alive — FAIL-CLOSED to "alive".

    Backs the anti-double-session guard (defect 7): a probe that throws/hangs must NEVER let the
    guard wrongly conclude the session is dead and proceed to a launch that KILLS the live agent. So
    on ANY probe error this reports ``True`` (alive) — the conservative direction (it bounces the
    card rather than risk discarding a live agent). Mirrors ``reaper._session_alive`` (kept local to
    avoid importing a private cross-module helper).

    Args:
        deps: The injected adapter bundle (the sessions port backing the tmux probe).
        issue: The ticket whose session liveness to probe (session name ``ticket-<issue>``).

    Returns:
        ``True`` if the session exists OR the probe raised (fail-closed); ``False`` only when the
        probe DEFINITIVELY reports the session gone.
    """
    try:
        return deps.sessions.is_alive(f"ticket-{issue}")
    except Exception:
        logger.exception(
            "anti-double-session is_alive probe failed for #%s; treating session as alive", issue
        )
        return True


@dataclass(frozen=True)
class TransitionOutcome:
    """The rolled-up result of processing ONE transition (#3).

    Attributes:
        antiloop: The anti-loop state after this transition (threaded forward to the next).
        actions_executed: How many actions RAN clean this transition (0 or 1).
        errors: How many actions raised/timed out this transition (0 or 1).
    """

    antiloop: AntiLoopState
    actions_executed: int = 0
    errors: int = 0


def process_transition(
    transition: Transition,
    *,
    deps: Deps,
    config: TickConfig,
    ctx: DecideContext,
    snapshot: BoardSnapshot,
    executor: ThreadPoolExecutor,
    now: float,
    antiloop: AntiLoopState,
    next_columns: dict[str, str],
    status_events: list[tuple[str, int | None, str]],
) -> TransitionOutcome:
    """Decide and dispatch the action for ONE detected transition (#3, extracted from ``tick``).

    A faithful move of the tick's per-transition body: it classifies the move via
    :func:`~kanbanmate.core.decide.decide`, builds the concrete command, and runs the matching
    branch (NOOP / Done-arrival teardown / NOOP-forward finalize / RUN_SCRIPT routing / launch gate
    / pre-launch already-live guard / cap-divert queue / dispatch + leak-safety release / ROLLBACK
    baseline). Every branch advances the diff baseline (``next_columns``) before returning so the
    next poll does not re-fire the move.

    ``next_columns`` and ``status_events`` are mutated IN PLACE (the same objects the tick owns);
    the updated ``antiloop`` and the per-transition counter deltas are returned in a
    :class:`TransitionOutcome`. The caller wraps THIS call in a ``try/except`` so a raise advances
    the baseline + counts an error rather than replaying the launch next tick.

    Args:
        transition: The detected board move to process.
        deps: The injected adapter bundle (store port + launch/board adapters).
        config: The per-tick :class:`~kanbanmate.app.tick.TickConfig` (imported under
            ``TYPE_CHECKING`` to avoid the ``tick ↔ transition_step`` runtime cycle).
        ctx: The decision context built once per tick (whitelist, anti-loop, kill-switch, …).
        snapshot: The current board snapshot (the dependency gate reads it).
        executor: The shared thread pool backing the per-action watchdog.
        now: The tick's wall-clock time.
        antiloop: The anti-loop state coming into this transition.
        next_columns: The diff-baseline map (mutated in place: ``item_id -> column``).
        status_events: The dashboard recent-events ring (mutated in place: only RAN actions).

    Returns:
        A :class:`TransitionOutcome` with the threaded ``antiloop`` and the ``actions_executed`` /
        ``errors`` deltas for this transition.
    """
    # Lazy import to break the tick <-> transition_step cycle (tick imports this module) and to
    # honour a test monkeypatch of ``tick._run_with_watchdog`` / ``_run_value_with_watchdog``.
    from kanbanmate.app.tick import (
        WatchdogStatus,
        _finalize_left_stage,
        _run_callable_with_watchdog,
        _run_launch_with_watchdog,
        _run_value_with_watchdog,
        _run_with_watchdog,
    )

    actions_executed = 0
    errors = 0

    action = decide(transition, config.columns, ctx)
    command = _build_action_via_tick(action, snapshot, deps)
    # Dependency-gate bounce (phase 32, DESIGN §9). The hybrid dep gate (#13) in ``_build_action``
    # turns a LAUNCH into a :class:`BlockAction` when a declared ``Depends on #N`` is unmet — but a
    # bare BlockAction only COMMENTS, leaving the card stranded in the triggering column with no
    # agent (observed live: #156 sat in Brainstorming, gated by #155). Instead, when the gate
    # blocked a LAUNCH AND the move has a real ``from_column`` to return to, bounce the card BACK to
    # that column (mirroring the un-whitelisted-move ROLLBACK): move + dep-named recap, with the
    # bounce-target baseline + bookkeeping marker below so it does not re-trigger. A first-contact
    # move (``from_column is None``) has NO origin to bounce to, so it falls through to the plain
    # BlockAction comment (the same precedent as the first-contact unknown-column NOOP).
    if (
        action.kind is ActionKind.LAUNCH
        and isinstance(command, BlockAction)
        and transition.from_column is not None
    ):
        bounce = DependencyBounceAction(
            ticket=transition.ticket,
            to_column=transition.from_column,
            reason=command.reason,
        )
        ok = _run_with_watchdog(executor, bounce, deps, config.action_timeout)
        if ok:
            actions_executed += 1
            status_events.append(
                (
                    event_kind_for_action(ActionKind.ROLLBACK),
                    transition.ticket.issue_number,
                    transition.from_column,
                )
            )
        else:
            errors += 1
        # Baseline = the BOUNCE TARGET (from_column), NOT the rejected triggering column, so the
        # next diff compares against where the card now sits and the bounce does not re-fire — the
        # ROLLBACK idempotency seam (DESIGN §6 diff baseline is the primary guard). Plus a
        # BOOKKEEPING anti-loop marker (excluded from the rate-limit counter), exactly like ROLLBACK.
        next_columns[transition.ticket.item_id] = transition.from_column
        antiloop = record_move(
            antiloop,
            transition.ticket.item_id,
            transition.from_column,
            now=now,
            bookkeeping=True,
        )
        return TransitionOutcome(antiloop, actions_executed, errors)
    if command is None:
        # NOOP — record the new column position but take no side-effect.
        # Distinguish an intentional inert NOOP from a misconfiguration: if the
        # destination token resolves to no column at all, the board names a column the
        # model does not know (a mismatched columns.yml / renamed GitHub option). Log it
        # so a silent NOOP is not mistaken for "nothing to do" (DESIGN §8 / errors-6).
        destination = resolve_column(config.columns, transition.to_column)
        done_teardown = done_arrival_teardown(deps, config, transition)
        if destination is None:
            logger.warning(
                "transition for #%s into unknown column %r: not in the column model; "
                "no action taken (check columns.yml vs the board's Status options)",
                transition.ticket.issue_number,
                transition.to_column,
            )
        elif done_teardown is not None:
            # Done-arrival reclaim (#9): the card landed in the configured Done column WHILE a
            # worktree still EXISTS, so reclaim it. ``done_arrival_teardown`` returns either a
            # DONE-flavoured TeardownAction (clean worktree → kill session, remove worktree,
            # finalize ✅, purge state) OR a BlockAction (unpushed work → loud sticky, worktree
            # KEPT, never silently destroyed). Both dispatch under the SAME per-action watchdog so a
            # hung git/tmux call cannot freeze the tick (DESIGN §5); the in-memory rate-limit history
            # is forgotten exactly like a Cancel teardown (#22). The card STAYS in Done (no move; the
            # baseline advance below records Done). Tick-level branch in the NOOP path, NOT a
            # decide-level reactive column, so Cancel semantics + the whitelist are untouched.
            ok_done = _run_with_watchdog(executor, done_teardown, deps, config.action_timeout)
            antiloop = forget(antiloop, transition.ticket.item_id)
            if ok_done:
                actions_executed += 1
                # Record the matching dashboard event: a teardown reclaim vs an unpushed-work block.
                event_kind = (
                    ActionKind.BLOCK
                    if isinstance(done_teardown, BlockAction)
                    else ActionKind.TEARDOWN
                )
                status_events.append(
                    (
                        event_kind_for_action(event_kind),
                        transition.ticket.issue_number,
                        transition.to_column,
                    )
                )
            else:
                errors += 1
            # BUG #9: a GENUINE Done arrival closes the GitHub issue (Done = closed → the ensign
            # "Clôturé" badge appears). Fire ONLY on the clean-reclaim case (a ``flavour="done"``
            # TeardownAction = the work is complete), NEVER on the unpushed-work BlockAction (the work
            # is NOT finished — closing would be wrong). The close is idempotent (skips an
            # already-closed issue) + wholly fail-soft inside ``close_done_issue``, and orthogonal to
            # the worktree reclaim above — the card STAYS in Done (the baseline advance below records
            # Done; the issue is never moved). A real close adds a dashboard "closed" event.
            if not isinstance(done_teardown, BlockAction) and close_done_issue(deps, transition):
                status_events.append(("teardown", transition.ticket.issue_number, "closed"))
            next_columns[transition.ticket.item_id] = transition.to_column
            return TransitionOutcome(antiloop, actions_executed, errors)
        elif destination is not None and transition.to_column != config.blocked_column:
            # NOOP-forward (e.g. Plan→Ready-to-dev) OR a Done arrival with NO live agent:
            # an accepted, non-rollback forward move into a REAL inert column finalizes the
            # LEFT stage ✅ (DESIGN §8.1.e), even though nothing launches. A Done arrival
            # without a live agent is just such a NOOP-forward — there is nothing to tear
            # down, so it finalizes the LEFT sticky (a silent no-op when no LEFT state/sticky
            # exists), exactly like any other inert arrival. No slot was overwritten on this
            # branch, so ``store.load`` still returns the LEFT state. (The unknown-column
            # branch above does NOT finalize — there is no real stage to advance.)
            #
            # moor: a move INTO the Blocked column is the ONE inert destination that must NOT
            # finalize the LEFT stage ✅ done — it is a PARK (the reaper's stall-park, a runaway
            # park, or a manual block), never a stage completion. The park already wrote the ⛔
            # blocked sticky for the LEFT stage; a ✅ "stage complete" flip here would OVERWRITE it
            # with a misleading "done" on a card that is actually Blocked (live: an API-stalled
            # triage agent parked Blocked by the reaper showed ✅ Triage done on its NEXT diff). The
            # ``*→Blocked`` wildcard transition makes every such park an accepted NOOP-forward, so
            # this guard — not the absence of a transition — is what suppresses the wrong finalize.
            _finalize_left_stage(
                deps,
                transition,
                deps.store.load(transition.ticket.issue_number)
                if transition.ticket.issue_number is not None
                else None,
                now,
            )
            # BUG #9: a Done arrival with NO worktree (the DOMINANT merged case — session-end already
            # purged state + removed the worktree before the card reached Done) is a genuine
            # completion, so close the GitHub issue too. Gated on the RESOLVED destination being the
            # configured Done column (compare ``destination.key``, not the raw board token, so a Status
            # option NAME ≠ column KEY still matches — the same name-then-key resolution
            # ``done_arrival_teardown`` uses). This NOOP-forward branch also serves ordinary inert
            # moves like Plan→Ready-to-dev, which must NOT close. Idempotent + fail-soft inside
            # ``close_done_issue``; the card STAYS in Done (never moved).
            if destination.key == config.done_column and close_done_issue(deps, transition):
                status_events.append(("teardown", transition.ticket.issue_number, "closed"))
        # Operator pull-back (13.7 #5): a queued card the operator dragged to an inert
        # (or unknown) column is now a NOOP — clear any queue marker (idempotent no-op
        # when absent) so a later ``_drain_queue`` sweep does not resurrect a ticket the
        # operator deliberately withdrew. The slot, if one was held, is freed by the
        # exhaustive teardown when the card eventually reaches Cancel / session-end.
        if transition.ticket.issue_number is not None:
            deps.store.clear_queued(transition.ticket.issue_number)
        next_columns[transition.ticket.item_id] = transition.to_column
        return TransitionOutcome(antiloop, actions_executed, errors)
    # RUN_SCRIPT verdict (15.6): a mechanical check-script transition. Run the script
    # (bounded — the subprocess is 120s-capped inside ``Workspace.run_transition_script``
    # and the gh client has mandatory timeouts, so the routing moves are bounded too),
    # then ROUTE the verdict through ``route_script_verdict`` (success → advance:auto
    # triggering move / record column; failure → on_fail move capped by the fix-CI cap
    # → park Blocked, or rollback). The routing OWNS the special baseline (auto vs park
    # vs rollback), so this branch sets ``next_columns`` from the outcome and returns
    # BEFORE the generic launch/baseline code below — it must NOT fall through to the
    # ROLLBACK/else baseline assignment. PRE-READ the LEFT state BEFORE running the script
    # so a success-finalize sources the LEFT stage's own metadata (header-provenance).
    if action.kind is ActionKind.RUN_SCRIPT and isinstance(command, RunScriptAction):
        # Bind the issue + script into locals BEFORE the lambda so the closure captures a
        # narrowed ``int`` (mypy cannot narrow ``transition.ticket.issue_number`` across a
        # lambda) and a stable value (no late-binding pitfall in the loop).
        script_issue = transition.ticket.issue_number
        script_path = command.script
        script_left_state = deps.store.load(script_issue) if script_issue is not None else None
        if script_issue is not None:
            ok_run, (code, output) = _run_value_with_watchdog(
                executor,
                partial(run_check_script, deps, script_issue, script_path),
                config.action_timeout,
            )
        else:
            # A draft item with no issue cannot key a worktree/script — treat as a clean
            # no-op run (route_script_verdict short-circuits on a None issue too).
            ok_run, (code, output) = True, (0, "")
        if not ok_run:
            # The script run timed out / raised (the watchdog logged + swallowed it). Do
            # NOT route a phantom verdict: leave the card where it is and advance the
            # baseline to the destination so the next diff does not re-fire. Count the error.
            errors += 1
            next_columns[transition.ticket.item_id] = transition.to_column
            return TransitionOutcome(antiloop, actions_executed, errors)
        outcome = route_script_verdict(
            deps,
            transition,
            to_column=transition.to_column,
            from_column=transition.from_column,
            on_fail=command.on_fail,
            advance=command.advance,
            exit_code=code,
            output=output,
            blocked_column=config.blocked_column,
            move_rate_limit_per_hour=config.move_rate_limit_per_hour,
            antiloop=antiloop,
            now=now,
            columns=config.columns,
        )
        antiloop = outcome.antiloop
        next_columns[transition.ticket.item_id] = outcome.baseline_column
        if outcome.finalize_left:
            _finalize_left_stage(deps, transition, script_left_state, now)
        if outcome.error:
            errors += 1
        else:
            actions_executed += 1
        # Dashboard event (phase-24 §24.3): a mechanical check-script verdict — exit 0
        # passed the gate (→ ``gate_pass``), non-zero failed it (→ ``gate_fail``).
        status_events.append(
            (
                "gate_pass" if code == 0 else "gate_fail",
                script_issue,
                transition.to_column,
            )
        )
        return TransitionOutcome(antiloop, actions_executed, errors)
    # ✅-on-advance (DESIGN §8.1.e): on a LAUNCH transition the daemon finalizes the
    # LEFT stage's sticky ✅ "done". ``LaunchAction.save`` REPLACES the single per-issue
    # ``TicketState`` slot, so the LEFT state MUST be PRE-READ via ``store.load`` BEFORE
    # the command runs (header-provenance Fix 4/6) — otherwise the ✅ sticky would be
    # stamped with the NEW stage's metadata. The finalize upsert itself runs AFTER the
    # command (it is fail-soft); only the ``load`` must precede the overwrite. Teardown /
    # reset / block transitions are NOT forward advances and never finalize.
    left_state = (
        deps.store.load(transition.ticket.issue_number)
        if action.kind is ActionKind.LAUNCH and transition.ticket.issue_number is not None
        else None
    )
    # Concurrency-cap gate (gate 13.5, DESIGN §7 — port of the PoC
    # ``runner.py`` cap gate + queue divert). Reserve a slot BEFORE dispatching the
    # launch. The dependency gate may already have turned this LAUNCH verdict into a
    # BlockAction (``_build_action``), so the cap gate guards on the CONCRETE command
    # object: ``isinstance(command, LaunchAction)`` narrows the union for the field
    # reads below, and only a real LaunchAction with an issue number reserves a slot.
    issue = transition.ticket.issue_number
    reserved = False
    # Launch GATE (15.6, port ``_apply_launch`` gate, runner.py:625-654). When a LAUNCH
    # transition carries a ``script``, run it as a GATE FIRST — BEFORE reserving the slot
    # / launching. exit ≠0 → VETO: route via ``route_script_verdict`` exactly like a
    # failed RUN_SCRIPT (the gate's on_fail IS the routing — port :650-652), set the
    # baseline/antiloop/errors from the outcome, and return (no slot reserved, no
    # agent). exit 0 → reset this loop's fix-CI counter + persist ``script_output`` (the
    # success-gate output IS the ``{{script_output}}`` value 15.7 fills) and proceed to
    # the normal launch. The shipped board has no prompt+script transition; this is parity.
    if (
        action.kind is ActionKind.LAUNCH
        and isinstance(command, LaunchAction)
        and issue is not None
        and command.script
    ):
        # Bind into locals (narrowed ``int`` + stable value) for the partial below.
        gate_issue = issue
        gate_script = command.script
        # Bug #1 ordering (PoC runner.py:643-652): the gate script's discover_branch
        # runs ``git -C <worktree> rev-parse`` (check=True) — it RAISES on a
        # not-yet-created worktree, vetoing the launch in a deadlock. Create the
        # per-ticket worktree FIRST (idempotent; the launch needs the SAME worktree
        # anyway, so this is no half-state), then gate, then launch. The pre-create runs
        # UNDER the watchdog (#6): it touches the network (``git fetch``) and ran directly on
        # the tick thread before, so a hung fetch here would freeze the daemon.
        ok_precreate = _run_callable_with_watchdog(
            executor,
            partial(deps.workspace.ensure_worktree, gate_issue, base=deps.base),
            config.action_timeout,
            label=f"ensure_worktree #{gate_issue}",
        )
        if not ok_precreate:
            # The pre-create timed out / raised — do NOT launch on a half-created worktree.
            # Leave the card and advance the baseline so the next diff does not re-fire.
            errors += 1
            next_columns[transition.ticket.item_id] = transition.to_column
            return TransitionOutcome(antiloop, actions_executed, errors)
        ok_gate, (gate_code, gate_out) = _run_value_with_watchdog(
            executor,
            partial(run_check_script, deps, gate_issue, gate_script),
            config.action_timeout,
        )
        if not ok_gate:
            # The gate run timed out / raised — do NOT launch on an unknown verdict.
            # Leave the card and advance the baseline so the next diff does not re-fire.
            errors += 1
            next_columns[transition.ticket.item_id] = transition.to_column
            return TransitionOutcome(antiloop, actions_executed, errors)
        if gate_code != 0:
            # VETO: the gate failed — route its on_fail exactly like a failed RUN_SCRIPT
            # and abort the launch (no slot reserved, no session). ``advance`` is N/A on a
            # veto (the launch is replaced by the on_fail move/rollback).
            outcome = route_script_verdict(
                deps,
                transition,
                to_column=transition.to_column,
                from_column=transition.from_column,
                on_fail=command.on_fail,
                advance=command.advance,
                exit_code=gate_code,
                output=gate_out,
                blocked_column=config.blocked_column,
                move_rate_limit_per_hour=config.move_rate_limit_per_hour,
                antiloop=antiloop,
                now=now,
                columns=config.columns,
            )
            antiloop = outcome.antiloop
            next_columns[transition.ticket.item_id] = outcome.baseline_column
            if outcome.error:
                errors += 1
            else:
                actions_executed += 1
            # Dashboard event (phase-24 §24.3): the launch GATE failed (→ ``gate_fail``);
            # no agent started, the on_fail routing handled the card.
            status_events.append(("gate_fail", gate_issue, transition.to_column))
            return TransitionOutcome(antiloop, actions_executed, errors)
        # Gate passed: reset this loop's fix-CI counter + stash the success output as the
        # {{script_output}} value (15.7 fills the placeholder from this), then launch.
        deps.store.reset_retry(issue, fixci_key(transition.to_column))
        try:
            deps.store.save_script_output(issue, gate_out)
        except Exception:
            logger.exception("gate script_output stash failed for #%s; continuing", issue)
    if action.kind is ActionKind.LAUNCH and isinstance(command, LaunchAction) and issue is not None:
        # Pre-launch already-live guard (#3): if this issue ALREADY has a LIVE agent
        # (RUNNING or WAITING) for THIS SAME destination stage, do NOT dispatch a second launch.
        # The idempotent launch (phase-27 §A) kills any existing tmux session before
        # ``new-session``, so a duplicate dispatch would KILL the live (possibly WAITING-on-human)
        # session and relaunch from scratch — discarding the agent's progress / the pending human
        # decision. The ``stage == to_column`` qualifier is LOAD-BEARING: it distinguishes a
        # spurious RE-FIRE of the same move (the destination agent is already live — skip) from a
        # legitimate FORWARD ADVANCE (the persisted state is the PRIOR stage's, whose lingering
        # RUNNING record must NOT block the new stage's launch). The diff baseline + anti-loop
        # guard normally prevent a re-fire; this guard is the last-line defense if a mid-loop raise
        # or a stale baseline replays the move.
        live = deps.store.load(issue)
        if live is not None and live.status in LIVE_STATUSES and live.stage == transition.to_column:
            logger.info(
                "skip launch for #%s — agent already live at stage %r (status=%s)",
                issue,
                transition.to_column,
                live.status.value,
            )
            next_columns[transition.ticket.item_id] = transition.to_column
            return TransitionOutcome(antiloop, actions_executed, errors)
        # Anti-double-session guard (defect 7, PoC runner.py:476-483): a HUMAN cross-stage drag of a
        # card whose agent is STILL LIVE at a DIFFERENT stage must NOT launch a second agent — the
        # idempotent launch kills the existing ``ticket-<n>`` session first (phase-27 §A), so a
        # dispatch here would DISCARD a live (possibly WAITING-on-human, mid-Q&A) agent's
        # un-persisted work. Bounce the card BACK to its origin instead (a guarded rollback), leaving
        # the live agent untouched.
        #
        # The guard fires only when ALL hold, so a legitimate FORWARD ADVANCE is never bounced:
        #   * the persisted state is LIVE (RUNNING/WAITING) at a DIFFERENT stage than the move's dest;
        #   * the tmux session is genuinely alive (probe fail-CLOSED to "alive" so a probe blip never
        #     wrongly kills a live agent) — a dead session falls through (the reaper parks the stale
        #     state and the new stage may legitimately launch); AND
        #   * there is NO recent agent-advance breadcrumb — the AGENT's own forward ``kanban-move``
        #     drops one (DESIGN §8.1.d), so a self-advance whose session hasn't died yet is EXEMPT
        #     (the PoC's "bot moves are handled earlier" exemption); only a HUMAN drag (no breadcrumb)
        #     reaches the bounce.
        if (
            live is not None
            and live.status in LIVE_STATUSES
            and live.stage != transition.to_column
            and not deps.store.recent_agent_advance(issue, now=now)
            and _session_alive_fail_closed(deps, issue)
        ):
            origin = resolve_column(config.columns, transition.from_column or "")
            bounce_target = (
                origin.name
                if origin is not None
                else (transition.from_column or transition.to_column)
            )
            logger.info(
                "anti-double-session: #%s dragged to %r while agent LIVE at %r — bouncing back to %r",
                issue,
                transition.to_column,
                live.stage,
                bounce_target,
            )
            RollbackAction(
                ticket=transition.ticket,
                to_column=bounce_target,
                reason="moved while an agent is still live (anti-double-session)",
            ).execute(deps)
            actions_executed += 1
            # Baseline = the bounce target so the diff does NOT re-fire (mirror the ROLLBACK seam).
            next_columns[transition.ticket.item_id] = bounce_target
            return TransitionOutcome(antiloop, actions_executed, errors)
        reserved = True
        if not deps.store.reserve_slot(issue, config.concurrency_cap):
            # Cap is FULL → divert to the queue instead of launching (no agent starts).
            # Persist the FULL launch routing read off the already-built command so the
            # drain rebuilds a launch BYTE-IDENTICAL to a direct one — the filled
            # per-transition ``/implement:*`` prompt is preserved (operator decision
            # 2026-06-06: rich payload, parity over thinness). Port of the PoC's
            # "cap full → QUEUE, record column, return Decision('queue')".
            deps.store.enqueue_launch(
                issue,
                {
                    "item_id": transition.ticket.item_id,
                    "stage": transition.to_column,
                    "title": transition.ticket.title,
                    "body": transition.ticket.body,
                    "prompt": command.prompt,
                    "script": command.script,
                    # Phase 20 (DESIGN §8.0.6): the transition's profile is the SOLE
                    # profile source, so the drain rebuilds the SAME resolution from it.
                    "profile": command.profile,
                    "permission_mode": command.permission_mode,
                    "on_fail": command.on_fail,
                    "advance": command.advance,
                    "enqueued_at": now,
                },
            )
            # Advance the diff baseline: the card IS in the agent column on the board,
            # so the next diff must NOT re-fire this move (otherwise it would re-queue
            # every poll). ``reserve_slot`` is idempotent per ticket, so even a re-fired
            # move would reserve nothing extra — but advancing the baseline is the
            # primary idempotence backstop (DESIGN §6). Do NOT finalize the LEFT stage:
            # nothing advanced (no agent launched), so there is no forward move to
            # finalize.
            next_columns[transition.ticket.item_id] = transition.to_column
            return TransitionOutcome(antiloop, actions_executed, errors)
    # Dispatch under the watchdog. A LAUNCH that reserved a slot runs under the TRI-STATE watchdog
    # (defect 13) so a TIMEOUT (the worker may still create the session late) is told apart from an
    # EXCEPTION (definitively no session): the slot is RELEASED only on a definitive failure, and
    # KEPT on the unknown-timeout so a late launch never runs an agent without a slot (cap+1). Every
    # other action (teardown / reset / block / rollback / run_script) keeps the boolean watchdog.
    if reserved and isinstance(command, LaunchAction):
        status = _run_launch_with_watchdog(executor, command, deps, config.action_timeout)
        ok = status is WatchdogStatus.OK
        slot_definitively_failed = status is WatchdogStatus.FAILED
    else:
        ok = _run_with_watchdog(executor, command, deps, config.action_timeout)
        # A non-launch action holds no reserved slot, so the release branch never fires for it; the
        # flag's value is irrelevant there (guarded by ``reserved`` below).
        slot_definitively_failed = not ok
    # #22 teardown rate-limit reset: a Cancel TEARDOWN (or a Cancel→Backlog RESET)
    # abandons the ticket, so its accumulated IN-MEMORY rate-limit history must NOT
    # linger (the in-memory analogue of the PoC's ``purge_ticket`` zeroing the on-disk
    # ``moves/`` history — ``release_slot``/``purge_ticket`` cannot reach this volatile
    # state). Drop the item's entries unconditionally (forget is a clean no-op when the
    # item has none) so no stale timestamps survive the teardown.
    if action.kind in (ActionKind.TEARDOWN, ActionKind.RESET):
        antiloop = forget(antiloop, transition.ticket.item_id)
    if ok:
        actions_executed += 1
        # Dashboard event (phase-24 §24.3): translate the executed action's kind to its
        # recent-events ring kind (launch / teardown / block / rollback). Recorded ONLY
        # on a clean run so the ring reflects what actually happened this tick.
        status_events.append(
            (
                event_kind_for_action(action.kind),
                transition.ticket.issue_number,
                transition.to_column,
            )
        )
        if reserved and issue is not None:
            # Stale-marker supersede (13.7 #4): a fresh DIRECT launch supersedes any
            # coexisting queue marker for this issue. Clear it (idempotent no-op when
            # absent) so the same-tick drain — or a later sweep — cannot ALSO re-dispatch
            # the now-running ticket (the double-launch window the keep-marker fix would
            # otherwise re-open). ``reserved`` is True only for a real LaunchAction with
            # an issue number, so this fires exactly on the direct-launch success path.
            deps.store.clear_queued(issue)
    else:
        errors += 1
        # Leak-safety (port of the PoC's release-on-launch-failure): the slot was reserved above but
        # the launch did not complete cleanly. Release the slot ONLY on a DEFINITIVE failure
        # (exception) — NOT on an unknown TIMEOUT (defect 13): a timed-out worker may still create
        # the session late, and releasing here would let it run an agent without a slot (cap+1). On
        # the timeout the slot is KEPT; the drain's already-running guard adjudicates next tick (a
        # completed launch leaves a RUNNING state that holds the slot; a truly dead one is
        # reconciled by the reaper, which frees the slot via its non-destructive teardown).
        if reserved and issue is not None and slot_definitively_failed:
            # SLOT-ONLY ``release_slot`` (13.7 PoC split): it frees ONLY the slot and must NOT wipe
            # ``moves/<issue>`` or ``retries/<issue>__*`` (the durable §6 counters). The SUCCESS path
            # must NOT release — there the slot backs the now-running session that session-end purges.
            deps.store.release_slot(issue)
    if action.kind is ActionKind.LAUNCH:
        # ✅-on-advance is FORWARD-ONLY (phase 8 / DESIGN §8.1.e): only a LAUNCH (and the
        # NOOP-forward branch above) finalizes the LEFT stage ✅. A ROLLBACK / RUN_SCRIPT
        # / TEARDOWN / RESET / BLOCK never enters this branch, so a rollback emphatically
        # does NOT flip the LEFT sticky to ✅ (the PoC finalizes ✅ only on accepted
        # non-rollback forward moves, runner.py:497-499,618-620). Finalize from the
        # PRE-READ state (now metadata-bearing); the LaunchAction has already opened the
        # new stage's 🟡 (8.1.c). ``write_body_status=False`` (nit 4): the body-top header is written
        # ONCE per launch tick — the new stage's ``running`` below is the meaningful end-of-tick
        # header, so skipping the LEFT stage's ``done`` body-status here collapses the same-tick
        # double write to one. The ✅ STICKY flip inside ``_finalize_left_stage`` still runs.
        _finalize_left_stage(deps, transition, left_state, now, write_body_status=False)
        # FIX 5: mirror the new stage's 🟡 running sticky in the body-top status header. Emitted
        # here (transition_step has ample LOC headroom) rather than in the near-ceiling
        # ``LaunchAction.execute`` (actions.py at 999). Fully fail-soft (it swallows every error),
        # so it can never break the launch. Skipped for a draft item with no issue number.
        if transition.ticket.issue_number is not None:
            launch_profile = command.profile if isinstance(command, LaunchAction) else ""
            # BUG A: surface the latest progress milestone in the header (None at first launch — no
            # sticky progress yet — falls back to the static "agent dispatched" summary). Fail-soft.
            progress = latest_progress(
                deps, transition.ticket.issue_number, transition.to_column, now
            )
            update_body_status(
                deps.seeder,
                transition.ticket.issue_number,
                stage=transition.to_column,
                state="running",
                summary=f"agent dispatched ({launch_profile or 'agent'})",
                now=now,
                latest_progress=progress,
            )
    # Advance the baseline regardless of success: the card *is* in the new column on
    # the board, so the next diff must compare against it. A failed action surfaces
    # via the error count / logs, not by replaying the move every tick (which would
    # spam launches). Idempotence comes PRIMARILY from advancing this diff baseline
    # (DESIGN §6: a move recorded in persisted state produces no diff next poll); the
    # anti-loop guard is a secondary defense-in-depth net, not the production backstop.
    #
    # ROLLBACK-specific baseline (the idempotency seam, phase 12.8): a ROLLBACK bounced
    # the card BACK to ``action.to_column`` (the from_col), so the baseline must record
    # the BOUNCE TARGET, not the rejected ``transition.to_column``. Otherwise the next
    # diff would compare against the rejected column and re-fire the rollback every poll
    # (the NEW analog of the PoC's bookkeeping ``record_bot_move``). For every other
    # verdict the card sits in ``transition.to_column`` on the board, so that is the
    # baseline.
    if action.kind is ActionKind.ROLLBACK:
        next_columns[transition.ticket.item_id] = action.to_column
        # #19 rollback-aware bookkeeping tag: a ROLLBACK is a daemon-issued bounce back
        # to ``action.to_column`` (the from_col). Record it as a BOOKKEEPING move so the
        # anti-loop net does not fight a legitimate rollback — the marker reads "already
        # handled, do not re-trigger" and is EXCLUDED from the rate-limit counter (a
        # guarded rollback must not eat the runaway-loop budget). This is the SECONDARY
        # guard; the diff-baseline advance above (12.8) stays the PRIMARY no-re-trigger
        # mechanism (port of the PoC's bookkeeping ``record_bot_move``, state.py:117-149).
        antiloop = record_move(
            antiloop,
            transition.ticket.item_id,
            action.to_column,
            now=now,
            bookkeeping=True,
        )
    else:
        next_columns[transition.ticket.item_id] = transition.to_column
    return TransitionOutcome(antiloop, actions_executed, errors)


def _build_action_via_tick(action: Action, snapshot: BoardSnapshot, deps: Deps) -> Command | None:
    """Call the tick's ``_build_action`` (lazily, to break the import cycle).

    Args:
        action: The pure :class:`~kanbanmate.core.domain.Action` to translate.
        snapshot: The current board snapshot.
        deps: The injected adapter bundle.

    Returns:
        The concrete command object, or ``None`` for a NOOP.
    """
    from kanbanmate.app.tick import _build_action

    return _build_action(action, snapshot, deps)
