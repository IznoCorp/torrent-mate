"""The imperative shell: one poll cycle of the unified daemon (DESIGN §3.1).

:func:`tick` performs exactly one reconciliation pass and is the only place where the pure core
(:mod:`kanbanmate.core`) meets live I/O (through ``ports`` Protocols carried on :class:`Deps`):

    cheap_probe()  →  (probe changed?)  →  snapshot()
        →  diff(persisted, snapshot)  →  ∀ Transition: decide() → Action → execute(deps)
        →  reap stale agents  →  drain queue  →  heartbeat / bookkeeping

The cycle is **idempotent**: re-running with an unchanged probe token does no work, and even a
forced re-snapshot produces no duplicate launches because the diff compares against persisted
state and the anti-loop guard in :func:`~kanbanmate.core.decide.decide` suppresses re-reactions.

Two robustness rules from DESIGN §5 are enforced here, not in the daemon loop:

* **Per-action watchdog** — each ``Action.execute`` runs under a bounded timeout in a worker
  thread, so one hung adapter call (a stuck ``git``/``tmux``/network op) aborts that action and
  the tick continues rather than freezing the daemon.
* **Exception isolation** — an exception raised by one action is caught, logged, and the tick
  carries on; one bad ticket never aborts the whole cycle.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2). ``tick`` speaks
only Protocols (via :class:`Deps`) plus the pure core; it never names a concrete adapter.
"""

from __future__ import annotations

import dataclasses
import enum
import logging
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Final
from weakref import WeakKeyDictionary

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
from kanbanmate.app.depgate import resolve_dependency_gate
from kanbanmate.app.drain import _drain_queue as _drain_queue_impl
from kanbanmate.app.health_reporter import apply_health
from kanbanmate.app.intents import drain_intents
from kanbanmate.app.reaper import _ReapMove, reap_stale_agents
from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.app.status_reporter import report_status
from kanbanmate.app.transition_step import process_transition
from kanbanmate.core.antiloop import AntiLoopConfig, AntiLoopState
from kanbanmate.core.decide import DecideContext
from kanbanmate.core.dependency_gate import evaluate as evaluate_dependencies
from kanbanmate.core.diff import diff
from kanbanmate.core.domain import Action, ActionKind, BoardSnapshot, Column, Transition
from kanbanmate.core.stage_comment import fmt_timestamp, header_from_state
from kanbanmate.core.transitions import TransitionConfig
from kanbanmate.ports.store import TicketState

logger = logging.getLogger(__name__)

# Re-export the reaper's stale-agent sweep under the tick's historical private name. The reaper
# moved to ``app/reaper.py`` (15.6 LOC budget); tests + callers still import ``_reap_stale_agents``
# from ``kanbanmate.app.tick``, so keep the alias stable (no signature change).
_reap_stale_agents = reap_stale_agents

# Re-export the queue drain under the tick's historical private name. The drain moved to
# ``app/drain.py`` (18.6 LOC budget — the Md2 reorder pushed tick.py over the 1000-LOC ceiling);
# tests + the tick body still reference ``_drain_queue`` here, so keep the alias stable. An explicit
# assignment (not a bare ``import ... as``) is what makes mypy treat the private name as re-exported.
_drain_queue = _drain_queue_impl

# Per-tick registry of GENUINELY abandoned actions, keyed by the tick's executor (phase-34). When a
# watchdog wrapper's ``future.result(timeout=...)`` raises ``FutureTimeoutError`` the worker thread is
# left running with no way to join it — a REAL leaked thread. The wrapper records the action's
# description here; ``_watchdog_executor`` reads the list at exit and warns ONLY when it is non-empty.
#
# This replaces the old ``t.is_alive()`` heuristic, which fired a false positive on EVERY successful
# action: a ``ThreadPoolExecutor`` worker stays alive IDLE (parked on the work queue) between tasks,
# so "a worker is alive at tick exit" did NOT mean "an action hung" — it was true after every
# completed action. The timeout records are the authoritative never-hang signal. The map is weak-keyed
# on the executor so a tick's records vanish with its (garbage-collected) executor — no manual reset.
_TIMED_OUT_ACTIONS: WeakKeyDictionary[ThreadPoolExecutor, list[str]] = WeakKeyDictionary()


def _record_timed_out_action(executor: ThreadPoolExecutor, description: str) -> None:
    """Record that a watchdog-bounded action on ``executor`` timed out (genuine hang).

    Appends ``description`` to the executor's per-tick abandoned-action list (created lazily on first
    timeout). ``_watchdog_executor`` reads the list at tick exit to warn about REAL leaked threads —
    a worker abandoned mid-call by :class:`~concurrent.futures.TimeoutError`, not an idle pool worker.

    Args:
        executor: The tick's shared thread pool the timed-out action ran in (the registry key).
        description: A short human-readable name of the action that hung (e.g. ``"LaunchAction"`` or
            the callable's label), surfaced in the exit warning so the leak is attributable.
    """
    _TIMED_OUT_ACTIONS.setdefault(executor, []).append(description)


# A running ticket whose agent heartbeat is older than this (seconds) is considered stale and
# reaped (DESIGN §8.3, mirrors the PoC ``reaper.HEARTBEAT_TTL``).
DEFAULT_HEARTBEAT_TTL = 1800.0

# How long (seconds) an agent may be silent before the reaper PROBES its pane for a pending human
# prompt — far shorter than the reap TTL (31.2). A blocked-on-human agent stops touching its
# heartbeat the moment it hits the prompt; without this it would sit unsignalled until the heartbeat
# crossed the full 1800 s reap TTL. Probing once silence exceeds ~180 s flips it to WAITING (signal,
# never reap) promptly. It is strictly a DETECTION accelerator: a non-waiting silent agent is left
# untouched until the real reap TTL, so this never changes WHEN an agent is reaped.
DEFAULT_WAITING_PROBE_TTL = 180.0

# The inert column a reaped (stale-agent) ticket's card is parked in (DESIGN §8.3 / §9). The reap
# step moves the card here so the stall is visible on the board; mirrors the PoC reaper's
# ``status_option_map(...).get("Blocked")`` target.
DEFAULT_BLOCKED_COLUMN = "Blocked"

# The terminal column whose ARRIVAL tears down a still-live agent (phase 28.1). A card landing here
# while its persisted state shows a LIVE agent (RUNNING/WAITING) fires a DONE-flavoured teardown so
# the agent's session/worktree are reclaimed and the sticky finalized ✅; the card STAYS in Done. The
# common trigger is the skip-to-Done "an agent recognises the feature is already shipped" use case.
DEFAULT_DONE_COLUMN = "Done"

# Per-action watchdog budget (seconds). A single hung adapter call must not freeze the daemon
# (DESIGN §5 hang-protection (b)); the action is abandoned and the tick continues.
DEFAULT_ACTION_TIMEOUT = 120.0


@dataclass(frozen=True)
class TickConfig:
    """Static, per-tick policy inputs (DESIGN §3.1 / §8 / §8.3).

    Attributes:
        columns: The board column model (key -> :class:`Column`), used by
            :func:`~kanbanmate.core.decide.decide` to classify each transition's destination.
        kill_switch: A static fallback kill-switch. The live ``~/.kanban/PAUSE`` sentinel is read
            fresh from the store on every tick and OR-ed with this flag, so a PAUSE file appearing
            between ticks halts launches on the next poll (DESIGN §10 / H5). Leave ``False`` in
            production — the store read is authoritative; this flag exists for tests/overrides.
        heartbeat_ttl: Seconds after which a running ticket's silent agent is reaped.
        waiting_probe_ttl: Seconds of agent silence after which the reaper PROBES the pane for a
            pending human prompt (31.2) — far shorter than ``heartbeat_ttl`` so a blocked-on-human
            agent is flipped to WAITING and signalled within minutes instead of after the full reap
            TTL. Detection-only: it never reaps; a non-waiting silent agent is untouched until
            ``heartbeat_ttl``. Default :data:`DEFAULT_WAITING_PROBE_TTL` (180 s).
        action_timeout: Per-action watchdog budget in seconds.
        blocked_column: The inert column key a reaped (stale-agent) ticket's card is parked in
            (DESIGN §8.3 / §9 default ``Blocked``). The reap step moves the card here so an
            operator sees the stalled ticket on the board, not just in a comment.
        reset_target: The inert column a Cancel card must return to for a RESET (default
            ``Backlog``); forwarded to the decision context.
        done_column: The terminal column whose ARRIVAL tears down a still-live agent (phase 28.1,
            default ``Done``). A card landing here while its persisted state shows a LIVE agent
            (RUNNING/WAITING) triggers a DONE-flavoured :class:`~kanbanmate.app.actions.TeardownAction`
            (kill session, remove worktree, finalize the sticky ✅, purge state) — the card STAYS in
            Done (no move). With NO live agent the arrival is a pure NOOP. This is a tick-level
            branch in the NOOP path, NOT a decide-level reactive column: Done is left INERT/
            un-launchable and the whitelist + Cancel semantics are untouched (the rule forbids making
            Done a reset/reactive column that would change Cancel behaviour). The default ``"Done"``
            matches the engine's shipped terminal column key.
        unattended_hours: Optional ``(start_hour, end_hour)`` local-hour window during which
            unattended launches are permitted; forwarded to the decision context. ``None`` (the
            default) means launches are never time-gated (DESIGN §6 / H5).
        transitions: Optional per-(from,to) transition whitelist (phase 12). When supplied it is
            threaded into the per-tick :class:`~kanbanmate.core.decide.DecideContext` so
            :func:`~kanbanmate.core.decide.decide` classifies each concrete move against the
            whitelist (launch / run_script / noop / rollback). The composition root (phase 12.9)
            parses the clone's ``transitions.yml`` and threads the resulting
            :class:`~kanbanmate.core.transitions.TransitionConfig` here; a clone with no
            ``transitions.yml`` is wired with the built-in ``DEFAULT_TRANSITIONS`` fallback so a
            whitelist is ALWAYS supplied. ``None`` is therefore a wiring bug — :func:`decide`
            raises rather than degrade to any column model (DESIGN §8.0.6).
        concurrency_cap: Max concurrent agent sessions before a launch diverts to
            the queue (gate 13.5, DESIGN §7). Default 3, sourced from
            :class:`~kanbanmate.core.columns.BoardDefaults`.
        move_rate_limit_per_hour: Max AUTO/bot moves per ticket within the
            hour before it is parked in Blocked (gate 13.6, DESIGN §6). Default
            10, sourced from :class:`~kanbanmate.core.columns.BoardDefaults`.
    """

    columns: dict[str, Column]
    kill_switch: bool = False
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL
    waiting_probe_ttl: float = DEFAULT_WAITING_PROBE_TTL
    action_timeout: float = DEFAULT_ACTION_TIMEOUT
    blocked_column: str = DEFAULT_BLOCKED_COLUMN
    reset_target: str = "Backlog"
    done_column: str = DEFAULT_DONE_COLUMN
    unattended_hours: tuple[int, int] | None = None
    transitions: TransitionConfig | None = None
    concurrency_cap: int = 3
    move_rate_limit_per_hour: int = 10


@dataclass(frozen=True)
class TickResult:
    """Outcome of one :func:`tick`, returned so the daemon loop can adapt its cadence.

    Attributes:
        probe_token: The probe token observed this tick; the caller feeds it back as the next
            ``persisted_state.last_probe`` so an unchanged board skips the snapshot.
        snapshot_taken: ``True`` iff the probe changed and a full snapshot was fetched.
        actions_executed: How many decided actions actually ran (excludes NOOPs).
        reaped: How many stale running agents were reaped (parked in Blocked) this tick.
        relaunched: How many stale running agents were RELAUNCHED once this tick (the reaper
            retry, ``TicketState.retries < RETRY_LIMIT``). A relaunch is NOT a reap — the ticket
            keeps running — so it is counted separately for observability (DESIGN §8.3); only the
            terminal park-in-Blocked increments ``reaped``.
        errors: How many actions raised or timed out (caught and logged, never fatal).
        probe_failed: ``True`` when ``cheap_probe`` raised this tick (FIX4). The tick still ran
            every post-step (reap/done-exit/drain/heartbeat) so finished agents are not stranded,
            but it returns this flag so the daemon loop counts the poll as FAILED — feeding the
            circuit-breaker/backoff + the ``last_tick_ok``/``consecutive_failures`` observability
            (a dead token / DNS outage trips the backoff instead of looking healthy). A transient
            failure self-heals the next tick (re-probe succeeds → the failure run resets to 0).
        probe_error: The exception ``cheap_probe`` raised (``None`` on success), forwarded so the
            loop can classify a 401/403 and drop the actionable DEGRADED breadcrumb (dead-token
            observability) — exactly as it does for a tick that raised outright.
    """

    probe_token: str
    snapshot_taken: bool
    actions_executed: int
    reaped: int
    errors: int
    relaunched: int = 0
    probe_failed: bool = False
    probe_error: BaseException | None = None


@dataclass(frozen=True)
class PersistedState:
    """The daemon's in-memory carry-over between ticks (the diff baseline).

    The authoritative per-ticket runtime state lives in the :class:`~kanbanmate.ports.store.StateStore`;
    this small record is only the polling baseline the imperative shell threads tick-to-tick.

    **In-memory diff baseline (#20 KEEP+DOC — DESIGN §5/§6).** ``columns_by_item`` is the NEW
    replacement for the PoC's durable per-item ``columns/<item>`` ledger (state.py:151-173), which
    persisted across restarts and seeded at board-add (``None`` == first contact). NEW keeps this
    baseline IN MEMORY only — it is NOT persisted across a daemon restart. The accepted semantics
    shift: the FIRST tick post-restart sees an EMPTY ``columns_by_item``, so EVERY card looks like
    first-contact (``diff`` yields ``from_column=None``), and the tick re-syncs silently against the
    live board WITHOUT spurious launches (first-contact leniency, ``diff.py``). This is the intended
    "restart + diff recovers downtime moves" behaviour (DESIGN §6) — the board is the source of
    truth and the baseline rebuilds from it, rather than a durable on-disk seed-at-add ledger.

    Attributes:
        columns_by_item: Mapping of ``item_id`` to the column key each ticket occupied at the
            previous poll — the left-hand side of :func:`~kanbanmate.core.diff.diff`. In-memory
            only (see the class note above): an empty baseline after a restart re-syncs from the
            board as first-contact, no spurious launches (#20).
        last_probe: The probe token captured on the previous tick; an equal token this tick means
            the board is unchanged and no snapshot is fetched.
        antiloop: The accumulated anti-loop state (target-keyed dedup + per-ticket rate-limit). It
            threads tick-to-tick alongside the diff baseline so the daemon can recognise its **own**
            recent board moves. This is *defense-in-depth*, not the production idempotence backstop:
            per DESIGN §6 the diff-against-persisted-state comparison (a recorded bot move produces
            no diff next poll) is the primary guard; this guard is a secondary runaway-loop net.
    """

    columns_by_item: dict[str, str] = field(default_factory=dict)
    last_probe: str | None = None
    antiloop: AntiLoopState = field(default_factory=AntiLoopState)


def _build_action(
    action: Action,
    snapshot: BoardSnapshot,
    deps: Deps,
) -> (
    LaunchAction
    | TeardownAction
    | ResetAction
    | BlockAction
    | RollbackAction
    | RunScriptAction
    | None
):
    """Translate a pure :class:`Action` into its command object.

    A LAUNCH verdict is additionally passed through the **hybrid dependency gate**
    (#13, DESIGN §9). The pure :func:`~kanbanmate.core.dependency_gate.evaluate`
    resolves each ``Depends on #N`` against the snapshot into a tri-state
    :class:`~kanbanmate.core.dependency_gate.DependencyVerdict` (MET / UNMET /
    UNKNOWN). The resolution is two-layered, **snapshot-primary**:

    * **Snapshot decides the common case** with ZERO I/O. When the verdict is
      :meth:`~kanbanmate.core.dependency_gate.DependencyVerdict.fully_met` (no UNMET
      dep, no UNKNOWN dep) the launch proceeds; when ``met`` is ``False`` (an
      on-board dep is not done) it is a hard block — no live query can satisfy an
      on-board not-done dep, so none is made. This is the perf property: a ticket
      whose deps are all on the board triggers ZERO ``issue_state`` calls.
    * **Live fallback resolves only the UNKNOWN deps.** When ``verdict.unresolved``
      is non-empty (deps absent from the snapshot — e.g. closed-as-not-planned or
      moved off the board), the gate queries ``deps.board_reader.issue_state(n)``
      for EACH such dep: CLOSED → that dep is MET; OPEN → UNMET. The launch proceeds
      iff ``verdict.met`` AND every unresolved dep resolved to CLOSED. This recovers
      the PoC behaviour (a closed-but-off-board dep satisfies its dependent) without
      the per-tick N queries of the all-on-board case.

    **Fail-soft + bounded.** A throwing/slow ``issue_state`` leaves that dep UNMET
    (conservative — NEVER launch on an undecidable dep); each call inherits the
    client's mandatory connect+read timeouts (CLAUDE.md). The residual edge the
    fallback cannot fix: an issue that is OPEN but whose work is genuinely done
    out-of-band is still UNMET — the correct fix is to represent it on the board.

    If any dependency is unmet the launch is *replaced* by a
    :class:`~kanbanmate.app.actions.BlockAction` carrying the gate's reason, so no
    agent starts while a blocker is still open. The gate runs here, in the
    imperative shell, because it needs the live snapshot AND the live ``issue_state``
    seam — :func:`decide` stays a pure function of the single transition and never
    sees the whole board or does any I/O.

    The two whitelist verdicts (phase 12) carry their per-transition routing on the
    pure :class:`Action`; this function threads it onto the command object:

    * :attr:`ActionKind.ROLLBACK` → a :class:`~kanbanmate.app.actions.RollbackAction`
      bouncing the card back to ``action.to_column`` (which, for a ROLLBACK, is the
      ``from_col`` the move was rejected from — the load-bearing dual use of
      ``Action.to_column``).
    * :attr:`ActionKind.RUN_SCRIPT` → a :class:`~kanbanmate.app.actions.RunScriptAction`
      running the mechanical (no-LLM) script, carrying ``on_fail`` / ``advance`` /
      ``to_column`` for phase 13 to consume.
    * :attr:`ActionKind.LAUNCH` additionally carries the matched transition's
      ``prompt`` / ``script`` / ``profile`` / ``permission_mode`` / ``on_fail`` /
      ``advance`` so the launched agent runs the FILLED ``/implement:*`` prompt
      (the headline parity fix) rather than the bare global ``agent_command``. The
      launch profile is the transition's ``profile`` ONLY — the agent launches AT
      the transition, so its profile comes from the transition; there is NO per-
      column default tier (transitions-only model, DESIGN §8.0.6; see
      :class:`~kanbanmate.app.actions.LaunchAction`).

    Args:
        action: The decision produced by :func:`~kanbanmate.core.decide.decide`.
        snapshot: The current board snapshot, used by the dependency gate to
            resolve each ``Depends on #N`` reference to its column.
        deps: The injected adapter bundle; ``deps.board_reader.issue_state`` is the
            live fallback for the UNKNOWN (off-board) deps the snapshot cannot decide.

    Returns:
        The matching command action, or ``None`` for :attr:`ActionKind.NOOP` (nothing to do).
    """
    kind = action.kind
    if kind is ActionKind.LAUNCH:
        # Hybrid dependency gate (#13, DESIGN §9). The pure tri-state verdict decides
        # the common all-on-board case with ZERO I/O; only its UNKNOWN (off-board)
        # deps fall through to the live ``issue_state`` fallback below. Block instead
        # of launching when any dep is unmet (on-board not-done, or off-board not-closed).
        verdict = evaluate_dependencies(action.ticket.body, snapshot)
        ready, reason = resolve_dependency_gate(verdict, deps)
        if not ready:
            logger.info(
                "launch for #%s gated by dependency gate: %s",
                action.ticket.issue_number,
                reason,
            )
            return BlockAction(ticket=action.ticket, reason=reason)
        # Carry the matched transition's routing onto the launch so the agent runs the FILLED
        # per-transition /implement:* prompt instead of the bare Deps.agent_command (phase 12).
        # A None prompt (the bare-launch fallback — no prompt) leaves LaunchAction on its fallback path.
        # Phase 20 (DESIGN §8.0.6): the launch profile is the transition's `profile` ONLY — the
        # agent launches AT the transition, so there is no per-column default; the launch FAILS
        # LOUD when the transition leaves `profile` empty (no silent global).
        return LaunchAction(
            ticket=action.ticket,
            prompt=action.prompt,
            script=action.script,
            profile=action.profile,
            permission_mode=action.permission_mode,
            on_fail=action.on_fail,
            advance=action.advance,
        )
    if kind is ActionKind.TEARDOWN:
        return TeardownAction(ticket=action.ticket)
    if kind is ActionKind.RESET:
        return ResetAction(ticket=action.ticket)
    if kind is ActionKind.BLOCK:
        return BlockAction(ticket=action.ticket, reason=action.reason)
    if kind is ActionKind.ROLLBACK:
        # Bounce the card back to its origin column. ``action.to_column`` carries the from_col
        # the rejected move departed (the dual use mirrored from the PoC Decision.column).
        return RollbackAction(
            ticket=action.ticket,
            to_column=action.to_column,
            reason=action.reason,
        )
    if kind is ActionKind.RUN_SCRIPT:
        # Mechanical (no-LLM) script transition. ``script`` is never None on a RUN_SCRIPT verdict
        # (decide() only emits it when ``t.script and not t.prompt``); ``or ""`` narrows the
        # Optional to str for the action's non-Optional field without changing behaviour.
        return RunScriptAction(
            ticket=action.ticket,
            script=action.script or "",
            on_fail=action.on_fail,
            advance=action.advance,
            to_column=action.to_column,
        )
    # NOOP and any unforeseen kind: nothing to execute.
    return None


def _finalize_left_stage(
    deps: Deps,
    transition: Transition,
    left_state: TicketState | None,
    now: float,
) -> None:
    """Finalize the LEFT stage's sticky to ✅ "done" on an accepted forward move (DESIGN §8.1.e).

    Port of the PoC ``runner.py::_finalize_left_stage``: on an accepted, non-rollback FORWARD
    move OUT of a stickied stage, flip ``transition.from_column``'s sticky to ``status="done"``.
    The contract:

    * SILENT NO-OP when ``transition.from_column`` is falsy/``None`` (a brand-new item or a
      first-contact move has no LEFT stage to finalize) — Backlog→agent finalizes nothing.
    * SILENT NO-OP when ``left_state`` is ``None`` (no persisted LEFT state to source the header
      metadata from — nothing to finalize).
    * The header is ALWAYS built via :func:`~kanbanmate.core.stage_comment.header_from_state`
      from the LEFT stage's OWN persisted metadata (NEVER a bare ``HeaderInfo``), so the ✅
      sticky keeps the LEFT stage's session / profile / mode / started / worktree bullets — full
      parity (DESIGN §8.1.e header-provenance Fix 4/6).
    * The underlying :func:`~kanbanmate.app.stage_signal.upsert_stage_comment` is itself a silent
      no-op when ``from_column`` has no running sticky and is fully fail-soft; an extra try/except
      here is defense-in-depth so a GitHub error during the finalize can NEVER break dispatch.

    This is INDEPENDENT of whether the destination launches an agent (DESIGN §8.1.e): the caller
    runs it for BOTH the LAUNCH branch (finalize ✅, then the launch posts the new stage's 🟡) and
    the NOOP-forward branch (e.g. Plan→Ready-to-dev: finalize ✅, no launch).

    Args:
        deps: The injected adapter bundle (the board writer the upsert PATCHes through).
        transition: The accepted forward transition; ``from_column`` names the LEFT stage.
        left_state: The LEFT issue's persisted :class:`TicketState`, PRE-READ via
            ``deps.store.load(issue)`` BEFORE any ``LaunchAction.save`` overwrote the slot
            (header-provenance Fix 4/6). ``None`` when no LEFT state is persisted.
        now: The current wall-clock time, used for the finished timestamp + the upsert stamp.
    """
    from_column = transition.from_column
    issue = transition.ticket.issue_number
    # Nothing to finalize: no LEFT stage or no issue to comment on.
    if not from_column or issue is None:
        return
    try:
        # The LEFT metadata mapping for the ✅ header. When ``left_state is None`` (defect 8: the
        # COMMON ordering — the agent advanced its own card via ``kanban-move`` then exited, so
        # ``kanban-session-end`` PURGED state before this 10s poll), build the header from an EMPTY
        # mapping instead of returning: ``header_from_state`` degrades every missing bullet to ""
        # gracefully, and ``upsert_stage_comment`` does a header SWAP on the EXISTING sticky
        # (preserving its progress lines) — so the ✅ flip needs NO persisted metadata. Without this
        # the sticky stayed 🟡/⚠️ forever, and the ⚠️→✅ flip on a later human acceptance was ALWAYS
        # lost. The PoC kept an idle state record so its ✅ upsert always ran (runner.py:771-775);
        # this is the NEW analog. (Inside the try so a malformed ``asdict`` is fail-soft too.)
        left_meta: Mapping[str, object] = (
            dataclasses.asdict(left_state) if left_state is not None else {}
        )
        header = header_from_state(
            left_meta,
            issue,
            from_column,
            "done",
            finished=fmt_timestamp(now),
        )
        upsert_stage_comment(
            deps.board_writer,
            issue,
            from_column,
            header=header,
            now=now,
        )
    except Exception:
        # Defense-in-depth: the upsert already swallows GitHub errors, but a build/encode error
        # in header construction must likewise never break dispatch (DESIGN §8.1 fail-soft).
        logger.exception(
            "✅ left-stage finalize failed for #%s stage=%r; continuing",
            issue,
            from_column,
        )


def _run_with_watchdog(
    executor: ThreadPoolExecutor,
    command: LaunchAction
    | TeardownAction
    | ResetAction
    | BlockAction
    | RollbackAction
    | DependencyBounceAction
    | RunScriptAction
    | _ReapMove,
    deps: Deps,
    timeout: float,
) -> bool:
    """Execute one command under a bounded timeout, isolating any failure.

    The command runs in a worker thread so a hung adapter call can be abandoned after ``timeout``
    seconds (DESIGN §5). Both a timeout and any raised exception are caught and logged; neither
    aborts the surrounding tick.

    Args:
        executor: The shared thread pool the action runs in.
        command: The command object to execute.
        deps: The injected adapter bundle.
        timeout: The per-action watchdog budget in seconds.

    Returns:
        ``True`` if the action completed cleanly, ``False`` on timeout or exception.
    """
    future = executor.submit(command.execute, deps)
    try:
        future.result(timeout=timeout)
        return True
    except FutureTimeoutError:
        # The worker thread is left running (it cannot be force-killed); the watchdog only
        # bounds *our* wait so the daemon stays responsive. The next tick's diff/state guards
        # keep the result idempotent even if the abandoned action later completes. Record the
        # genuine hang so ``_watchdog_executor`` can warn about the REAL leaked thread at tick exit
        # (phase-34) — an idle pool worker is NOT a leak, but this abandoned-mid-call one is.
        _record_timed_out_action(executor, type(command).__name__)
        logger.warning(
            "action %s timed out after %.0fs; continuing", type(command).__name__, timeout
        )
        return False
    except Exception:  # noqa: BLE001 — one bad action must never abort the whole tick
        logger.exception("action %s raised; continuing", type(command).__name__)
        return False


class WatchdogStatus(enum.Enum):
    """Tri-state outcome of a watchdog-bounded LAUNCH dispatch (defect 13).

    The boolean :func:`_run_with_watchdog` collapses a TIMEOUT and an EXCEPTION into one ``False``,
    but the launch slot-release path must tell them apart:

    Members:
        OK: The action completed cleanly within the budget.
        FAILED: The action RAISED — it definitively did NOT create a session, so the reserved slot
            must be released (no live agent backs it).
        UNKNOWN: The action TIMED OUT — the worker thread is abandoned but STILL RUNNING and may yet
            create the tmux session late. Releasing the slot here would let that late launch run an
            agent with no slot (cap+1), so the slot is KEPT; the drain's already-running guard
            adjudicates next tick (a completed launch leaves a RUNNING state that holds the slot; a
            truly dead one is reconciled by the reaper).
    """

    OK = "ok"
    FAILED = "failed"
    UNKNOWN = "unknown"


def _run_launch_with_watchdog(
    executor: ThreadPoolExecutor,
    command: LaunchAction,
    deps: Deps,
    timeout: float,
) -> WatchdogStatus:
    """Run a LAUNCH dispatch under the watchdog, returning a TRI-STATE status (defect 13).

    Identical isolation to :func:`_run_with_watchdog` but distinguishes a TIMEOUT (``UNKNOWN`` — the
    abandoned worker may still create the session) from an EXCEPTION (``FAILED`` — no session
    created). The caller releases the reserved slot ONLY on ``FAILED``; on ``UNKNOWN`` it keeps the
    slot so a late-completing launch never runs an agent without one (the cap+1 the boolean watchdog
    allowed). Port of the phase-13 deferred residual (IMPLEMENTATION.md:252-254).

    Args:
        executor: The shared thread pool the launch runs in.
        command: The :class:`~kanbanmate.app.actions.LaunchAction` to dispatch.
        deps: The injected adapter bundle.
        timeout: The per-action watchdog budget in seconds.

    Returns:
        :attr:`WatchdogStatus.OK` on a clean run, :attr:`WatchdogStatus.UNKNOWN` on timeout,
        :attr:`WatchdogStatus.FAILED` on an exception.
    """
    future = executor.submit(command.execute, deps)
    try:
        future.result(timeout=timeout)
        return WatchdogStatus.OK
    except FutureTimeoutError:
        # The abandoned worker is still running and may create the tmux session late — record the
        # genuine leaked thread (phase-34) and return UNKNOWN so the caller KEEPS the slot.
        _record_timed_out_action(executor, type(command).__name__)
        logger.warning(
            "launch %s timed out after %.0fs; keeping the slot (status UNKNOWN, defect 13)",
            type(command).__name__,
            timeout,
        )
        return WatchdogStatus.UNKNOWN
    except Exception:  # noqa: BLE001 — one bad launch must never abort the whole tick
        logger.exception("launch %s raised; continuing", type(command).__name__)
        return WatchdogStatus.FAILED


def _run_value_with_watchdog(
    executor: ThreadPoolExecutor,
    fn: Callable[[], tuple[int, str]],
    timeout: float,
) -> tuple[bool, tuple[int, str]]:
    """Run a VALUE-returning check-script call under the same bounded watchdog (15.6).

    The check-script seam (``run_check_script``) returns an ``(exit_code, output)`` verdict, which
    the void-returning :func:`_run_with_watchdog` cannot surface. This variant runs ``fn`` in the
    shared worker thread and returns ``(ok, verdict)``: ``ok`` is ``True`` iff ``fn`` completed
    within ``timeout`` (mirroring :func:`_run_with_watchdog`'s timeout/exception isolation), and
    ``verdict`` is ``fn``'s return value on success or a safe ``(0, "")`` placeholder on
    timeout/exception. The subprocess inside ``fn`` is itself 120s-bounded in the workspace adapter;
    this watchdog additionally bounds a hung ``gh`` inside the script so the sweep stays responsive.

    Args:
        executor: The shared thread pool the call runs in.
        fn: The zero-arg callable producing the ``(exit_code, output)`` verdict.
        timeout: The per-action watchdog budget in seconds.

    Returns:
        ``(ok, (exit_code, output))`` — ``ok`` is ``False`` (with a ``(0, "")`` placeholder verdict)
        on timeout or exception, so the caller can skip routing a phantom verdict.
    """
    future = executor.submit(fn)
    try:
        return True, future.result(timeout=timeout)
    except FutureTimeoutError:
        # Record the genuine hang (phase-34): the worker is abandoned mid-call and leaks, so the
        # exit warning in ``_watchdog_executor`` should fire — distinct from a benign idle worker.
        _record_timed_out_action(executor, "check-script")
        logger.warning("check-script timed out after %.0fs; continuing", timeout)
        return False, (0, "")
    except Exception:  # noqa: BLE001 — a wedged script must never abort the whole tick
        logger.exception("check-script raised; continuing")
        return False, (0, "")


def _run_callable_with_watchdog(
    executor: ThreadPoolExecutor,
    fn: Callable[[], object],
    timeout: float,
    *,
    label: str,
) -> bool:
    """Run a void/side-effecting callable under the bounded watchdog (#6).

    The general-purpose sibling of :func:`_run_with_watchdog` (which needs an action object with an
    ``.execute`` method). Used to bound the launch-gate's pre-create ``ensure_worktree`` call, which
    ran DIRECTLY on the tick thread before #6 — a network-touching ``git fetch`` outside any
    watchdog. Now it runs in the shared worker thread bounded by ``timeout``, so a hung pre-create
    can never freeze the daemon. Both timeout and exception are caught and logged.

    Args:
        executor: The shared thread pool the call runs in.
        fn: The zero-arg callable to run (its return value is discarded).
        timeout: The per-action watchdog budget in seconds.
        label: A short name for the call, used in the timeout/error log line.

    Returns:
        ``True`` if ``fn`` completed cleanly within ``timeout``, ``False`` on timeout or exception.
    """
    future = executor.submit(fn)
    try:
        future.result(timeout=timeout)
        return True
    except FutureTimeoutError:
        # Record the genuine hang (phase-34) under the caller-supplied label so the exit warning
        # can name the leaked pre-create/gate call — an idle pool worker must NOT trip the warning.
        _record_timed_out_action(executor, label)
        logger.warning("%s timed out after %.0fs; continuing", label, timeout)
        return False
    except Exception:  # noqa: BLE001 — a hung pre-create must never abort the whole tick
        logger.exception("%s raised; continuing", label)
        return False


#: Short grace period (seconds) given to idle pool workers to wind down after the non-blocking
#: shutdown, before any leak is assessed. A ``ThreadPoolExecutor`` worker parks IDLE on the work
#: queue between tasks and exits a beat after ``shutdown()`` signals it; this brief join lets that
#: happen so a just-finished action's worker is never mistaken for a hang (phase-34). It does NOT
#: gate the never-hang guarantee — the authoritative leak signal is the timeout registry, not
#: aliveness — so it is intentionally tiny.
_IDLE_WORKER_GRACE_S: Final[float] = 0.2


@contextmanager
def _watchdog_executor() -> Iterator[ThreadPoolExecutor]:
    """Yield the per-tick thread pool with a NON-BLOCKING shutdown (#6, real never-hang).

    The plain ``with ThreadPoolExecutor(...)`` calls ``shutdown(wait=True)`` on exit, which BLOCKS
    until every worker finishes — so one hung adapter call (the very case the per-action watchdog
    abandons) would freeze the whole daemon at tick exit, defeating the never-hang guarantee
    (CLAUDE.md). This context manager instead, on exit, calls
    ``shutdown(wait=False, cancel_futures=True)`` so the tick returns IMMEDIATELY even if a worker is
    wedged.

    **Leak detection (phase-34).** It warns about an abandoned thread using the AUTHORITATIVE signal:
    the per-tick timeout registry (:data:`_TIMED_OUT_ACTIONS`), populated by the watchdog wrappers
    whenever a ``future.result(timeout=...)`` actually raised ``TimeoutError``. That is the only case
    where a worker is genuinely orphaned. The previous implementation counted ``t.is_alive()`` on the
    pool's ``_threads``, but a ``ThreadPoolExecutor`` worker stays alive IDLE (parked on the work
    queue) BETWEEN tasks — so that check fired a FALSE POSITIVE after EVERY successful action, even
    when the action completed and had effects on the board. Now the warning fires only on a real hang
    and names the offending action(s), so the leak is both correct and attributable. As a belt-and-
    braces nicety, idle workers get a short grace join (:data:`_IDLE_WORKER_GRACE_S`) after the
    non-blocking shutdown so a just-finished worker has wound down before exit — but no leak is
    inferred from aliveness; the timeout records are the sole signal.

    A running worker cannot be force-killed (Python has no thread-kill), so a truly wedged adapter
    call leaks ONE thread per occurrence; the warning makes that visible, and the next tick's
    diff/state guards keep the result idempotent if the abandoned action later completes.

    Yields:
        A :class:`~concurrent.futures.ThreadPoolExecutor` for the tick's watchdog-bounded actions.
    """
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kanban-tick")
    try:
        yield executor
    finally:
        # NON-BLOCKING: return immediately even if a worker is wedged. ``cancel_futures=True`` drops
        # any not-yet-started work; a running worker cannot be force-killed but the tick no longer
        # waits on it.
        executor.shutdown(wait=False, cancel_futures=True)
        # Give idle workers a tiny grace to wind down post-shutdown so a just-finished action's
        # worker is not lingering — purely cosmetic; the leak verdict is the timeout registry below.
        for t in getattr(executor, "_threads", ()):
            t.join(timeout=_IDLE_WORKER_GRACE_S)
        # Warn ONLY when a watchdog wrapper recorded a genuine timeout this tick — those are the REAL
        # leaked threads (abandoned mid-call). An idle/just-finished pool worker is NOT a leak, so it
        # no longer trips this warning (the old ``is_alive()`` heuristic did, on every action).
        abandoned = _TIMED_OUT_ACTIONS.pop(executor, [])
        if abandoned:
            logger.warning(
                "tick exiting with %d abandoned hung action(s) (worker thread leaked, cannot be "
                "force-killed); NOT waiting (never-hang). Abandoned: %s",
                len(abandoned),
                ", ".join(abandoned),
            )


def tick(
    deps: Deps,
    config: TickConfig,
    persisted_state: PersistedState,
) -> tuple[TickResult, PersistedState]:
    """Run one poll cycle and return the result plus the next persisted baseline.

    The cycle (DESIGN §3.1):

    1. ``cheap_probe()`` — if the token equals ``persisted_state.last_probe`` the board is
       unchanged; skip straight to the post-steps (no snapshot, no diff).
    2. ``snapshot()`` then ``diff(persisted, snapshot)`` to get the moved/new tickets.
    3. For each :class:`~kanbanmate.core.domain.Transition`, ``decide`` the action and run the
       matching command under the per-action watchdog (NOOPs skipped).
    4. Post-steps: reap stale agents, drain the concurrency-cap queue (re-launch queued tickets
       when a reap freed a slot), refresh the daemon heartbeat/bookkeeping.

    The returned :class:`PersistedState` becomes the next tick's baseline; the caller threads it
    back in, which is what makes the loop idempotent across restarts.

    Args:
        deps: The injected adapter bundle (all ``ports`` Protocols).
        config: The per-tick policy inputs (columns, kill-switch, TTLs, watchdog).
        persisted_state: The diff baseline carried over from the previous tick.

    Returns:
        A ``(TickResult, PersistedState)`` pair: the cycle summary and the next baseline.
    """
    now = deps.clock.now()
    # FIX4: a probe failure (GitHub 401/403/5xx, DNS outage) must DEGRADE to no-new-launches WITHOUT
    # stranding finished agents — so the post-steps (reap/done-exit/drain/heartbeat) below STILL run
    # this tick. But it must NOT masquerade as a clean tick: ``probe_failed`` is carried back on the
    # TickResult so the daemon loop counts the poll as FAILED — feeding the circuit-breaker/backoff
    # and the last_tick_ok/consecutive_failures observability (a dead token would otherwise look
    # healthy: full-cadence polling, monitor D3 green). A SUSTAINED failure trips the backoff at the
    # loop's threshold; a TRANSIENT one self-heals next tick (re-probe succeeds → the run resets).
    # The probe token returned/persisted is the PRIOR token, so last_probe never advances to a value
    # that would suppress the next real snapshot, and the diff baseline is untouched (no launches).
    probe_failed = False
    probe_error: BaseException | None = None
    try:
        probe_token = deps.board_reader.cheap_probe()
    except Exception as exc:
        logger.warning(
            "cheap_probe failed this tick; degrading to no-new-launches (reap/drain/heartbeat "
            "still run) AND marking the poll FAILED so the loop's backoff engages. Re-probing "
            "next tick.",
            exc_info=True,
        )
        probe_failed = True
        probe_error = exc  # forwarded to the loop for 401/403 classification + DEGRADED breadcrumb
        probe_token = persisted_state.last_probe or ""
    # Read the kill-switch (~/.kanban/PAUSE) fresh every tick so a PAUSE file appearing between
    # ticks stops launches on the very next poll (DESIGN §10 / H5). OR with the static config flag
    # so an explicit override still pauses even if the sentinel read is bypassed in a test.
    kill_switch = config.kill_switch or deps.store.kill_switch_active()
    snapshot_taken = False
    actions_executed = 0
    errors = 0
    next_columns = dict(persisted_state.columns_by_item)
    # Thread the accumulated anti-loop state in from the baseline so ``is_blocked`` evaluates the
    # daemon's *own* recent moves rather than a fresh empty state every tick (DESIGN §6 / §3.3).
    antiloop = persisted_state.antiloop
    # The snapshot is hoisted so the status reporter (the tick's fail-soft last step) can read
    # titles + current columns off it; it stays ``None`` when the probe was unchanged (DESIGN §8.7).
    snapshot: BoardSnapshot | None = None
    # This tick's executed-action events (kind, issue, detail), accumulated for the rolling status
    # dashboard's recent-events ring (phase-24 §24.3). Only actions that RAN this tick are recorded.
    status_events: list[tuple[str, int | None, str]] = []

    # One thread pool per tick backs every watchdog-bounded action (decided + reaped). The
    # non-blocking-shutdown context manager (#6) makes the never-hang guarantee REAL: tick exit
    # never blocks on a wedged worker (the plain ``with`` would call shutdown(wait=True)).
    with _watchdog_executor() as executor:
        # Step 1-3: only when the probe changed is a snapshot worth its API cost (DESIGN §3.1). A
        # probe FAILURE (FIX4) is gated out here too — ``snapshot`` stays ``None`` / ``snapshot_taken``
        # stays ``False`` so the launch path is skipped, while every post-step below still runs.
        if not probe_failed and probe_token != persisted_state.last_probe:
            snapshot_taken = True
            snapshot = deps.board_reader.snapshot()
            ctx = DecideContext(
                antiloop_state=antiloop,
                # Thread the operator's configured move-rate-limit (columns.yml defaults) into
                # the in-memory anti-loop guard so ``is_blocked`` evaluates against the real cap,
                # not the AntiLoopConfig DEFAULT (rate_limit=10). recent_ttl / rate_window stay at
                # their defaults — _DEFAULT_RATE_WINDOW is already 3600s (1h), so rate_limit alone
                # gives the "per hour" semantics the config promises (#6).
                antiloop_config=AntiLoopConfig(rate_limit=config.move_rate_limit_per_hour),
                kill_switch=kill_switch,
                now=now,
                reset_target=config.reset_target,
                unattended_hours=config.unattended_hours,
                # Thread the parsed whitelist (phase 12) so decide() classifies each concrete
                # move against it (launch / run_script / noop / rollback). The whitelist is ALWAYS
                # present — the wiring supplies the built-in DEFAULT_TRANSITIONS fallback for a clone
                # with no transitions.yml — so a ``None`` here is a wiring bug and decide() raises
                # (no column model; DESIGN §8.0.6).
                transitions=config.transitions,
            )
            for transition in diff(persisted_state.columns_by_item, snapshot):
                # Per-transition isolation (#3): process ONE transition under a try/except so a
                # mid-loop raise (decide / _build_action / ensure_worktree / a store call) advances
                # the baseline to the destination and counts an error — rather than losing the
                # partially-advanced baseline and REPLAYING this move (and its launch) next tick.
                # The full decide→build→dispatch pipeline lives in ``process_transition`` (extracted
                # to keep tick.py under the 1000-LOC ceiling); it mutates ``next_columns`` /
                # ``status_events`` in place and returns the threaded antiloop + counter deltas.
                try:
                    outcome = process_transition(
                        transition,
                        deps=deps,
                        config=config,
                        ctx=ctx,
                        snapshot=snapshot,
                        executor=executor,
                        now=now,
                        antiloop=antiloop,
                        next_columns=next_columns,
                        status_events=status_events,
                    )
                    antiloop = outcome.antiloop
                    actions_executed += outcome.actions_executed
                    errors += outcome.errors
                except Exception:  # noqa: BLE001 — one bad transition must never abort the tick
                    logger.exception(
                        "transition for #%s raised; advancing baseline + counting an error",
                        transition.ticket.issue_number,
                    )
                    errors += 1
                    # Advance the baseline so the next diff does NOT re-fire (and re-launch) this
                    # move — the card IS in ``to_column`` on the board, so recording it is the
                    # idempotence backstop (DESIGN §6).
                    next_columns[transition.ticket.item_id] = transition.to_column

        # Step 4a: reap stale agents (runs every tick, even when the probe was unchanged). The reap
        # step issues the daemon's own move-to-Blocked, so it threads the anti-loop state through to
        # record each move it lands (defense-in-depth, DESIGN §6). It now also relaunches a stale
        # session ONCE before parking it in Blocked (15.2 / RETRY_LIMIT), reported separately.
        reaped, relaunched, reap_errors, antiloop = _reap_stale_agents(
            deps,
            config,
            executor,
            now,
            antiloop,
            kill_switch=kill_switch,
            # The live diff baseline (item_id → current column) lets the reaper detect a card that has
            # advanced past its agent's stage and PURGE the stale state instead of relaunching the
            # wrong stage (helm #5: a Brainstorming state relaunched onto a Spec card).
            current_columns=next_columns,
        )
        errors += reap_errors
        # Dashboard event (phase-24 §24.3): a stale-agent reap or relaunch happened this tick. A
        # board-wide event (issue ``None``) — the render maps ``reap`` to the degraded (WAITING) bin.
        if reaped or relaunched:
            status_events.append(("reap", None, f"{reaped} reaped, {relaunched} relaunched"))

        # Step 4b: drain the concurrency-cap queue (gate 13.5). Runs AFTER the reap step so a reap
        # that just freed a slot is visible to the drain (DESIGN §3.1 tick post-step order: reap →
        # drain). Each queued ticket re-launches only when a slot is ACTUALLY free, so the drain
        # never exceeds the cap. Under PAUSE (kill_switch) the drain launches NOTHING but leaves the
        # queue markers intact (defect 6, DESIGN §10) so a resume re-launches them on a later tick.
        _drain_queue(deps, config, executor, now, kill_switch=kill_switch)

        # Step 4c: drain the board-mutation intent queue (cockpit PR2). The daemon is the SOLE intent
        # writer; this executes operator (and, when wired, bridled-agent) moves with the authority
        # DERIVED from the running set (never the spoofable caller field). Placed AFTER drain_queue (a
        # pathological intent can never starve launches) and BEFORE report_status (board mutations
        # land before the dashboard render). It mutates next_columns (baseline advance, so a move into
        # a triggering column does NOT re-fire next tick) + status_events in place, and is WHOLLY
        # fail-soft — drain_intents swallows every exception, so it can never raise into the tick.
        drain_intents(
            deps,
            config,
            snapshot=snapshot,
            next_columns=next_columns,
            running=tuple(deps.store.list_running()),
            status_events=status_events,
            now=now,
            kill_switch=kill_switch,
        )

        # Step 4d: heartbeat / bookkeeping — the daemon's own liveness marker (DESIGN §5). The
        # store's touch_heartbeat is keyed per ticket; the daemon-level heartbeat is written by
        # the daemon loop (run_loop writes daemon.heartbeat after each tick), so here we only
        # log the cycle for observability.
        logger.debug(
            "tick complete: probe=%s snapshot=%s actions=%d reaped=%d relaunched=%d errors=%d",
            probe_token,
            snapshot_taken,
            actions_executed,
            reaped,
            relaunched,
            errors,
        )

        # Step 4d: refresh the rolling project status-update dashboard (phase-24 §24.3). ALL the
        # gather/render/diff/post logic lives in the reporter; this is a THIN, wholly fail-soft call
        # — ``report_status`` swallows every exception, so the dashboard is observability that can
        # NEVER raise into the tick or block a launch (DESIGN §8.7). The running-ticket view comes
        # straight off the store; the snapshot (``None`` when the probe was unchanged) supplies
        # titles + current columns; ``len(dequeue_pending())`` is the queue depth.
        report_status(
            deps,
            config,
            running=deps.store.list_running(),
            snapshot=snapshot,
            queue_depth=len(deps.store.dequeue_pending()),
            paused=kill_switch,
            events=status_events,
            now=now,
        )

        # Step 4e: per-card Health single-select chips (health-field). A THIN, wholly fail-soft
        # call — ``apply_health`` swallows every exception, so the chips are observability that
        # can NEVER raise into the tick or block a launch. ``snapshot`` is ``None`` when the probe
        # was unchanged → the step early-returns (Health writes only on a tick that snapshotted,
        # which is also the only tick a column could have changed; the per-card on-change diff
        # suppresses repeats). ``list_running`` is the SAME RUNNING+WAITING view report_status uses.
        apply_health(
            deps,
            config,
            running=deps.store.list_running(),
            snapshot=snapshot,
            now=now,
        )

    result = TickResult(
        probe_token=probe_token,
        snapshot_taken=snapshot_taken,
        actions_executed=actions_executed,
        reaped=reaped,
        errors=errors,
        relaunched=relaunched,
        probe_failed=probe_failed,
        probe_error=probe_error,
    )
    next_state = replace(
        persisted_state,
        columns_by_item=next_columns,
        last_probe=probe_token,
        antiloop=antiloop,
    )
    return result, next_state
