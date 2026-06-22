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
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from kanbanmate.app.actions import (
    BlockAction,
    Deps,
    LaunchAction,
    ResetAction,
    RollbackAction,
    RunScriptAction,
    TeardownAction,
)
from kanbanmate.app.body_status import update_body_status
from kanbanmate.app.default_status import normalize_default_status
from kanbanmate.app.depgate import resolve_dependency_gate
from kanbanmate.app.drain import _drain_queue as _drain_queue_impl
from kanbanmate.app.health_reporter import apply_health
from kanbanmate.app.intents import drain_intents
from kanbanmate.app.reaper import reap_stale_agents
from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.app.status_reporter import latest_progress, report_status
from kanbanmate.app.transition_step import process_transition

# Re-export the per-action watchdog under the tick's historical names. The whole watchdog group (the
# bounded-execution wrappers, the per-tick thread-pool context manager, and the timeout registry)
# moved out to ``app/watchdog.py`` (LOC budget). ``tick`` only uses ``_watchdog_executor`` directly,
# but callers + tests still reference the rest VIA ``tick``: the reaper / drain / transition_step
# LAZILY ``from kanbanmate.app.tick import _run_with_watchdog`` (to dodge the import cycle), and tests
# monkeypatch ``tick._run_with_watchdog`` / ``tick._run_launch_with_watchdog`` and read
# ``tick.WatchdogStatus``. The redundant ``as`` aliasing marks each name an explicit re-export, so it
# stays live on this module's namespace (the lazy lookups + monkeypatches resolve here unchanged).
from kanbanmate.app.watchdog import (
    _IDLE_WORKER_GRACE_S as _IDLE_WORKER_GRACE_S,
    _TIMED_OUT_ACTIONS as _TIMED_OUT_ACTIONS,
    _record_timed_out_action as _record_timed_out_action,
    _run_callable_with_watchdog as _run_callable_with_watchdog,
    _run_launch_with_watchdog as _run_launch_with_watchdog,
    _run_value_with_watchdog as _run_value_with_watchdog,
    _run_with_watchdog as _run_with_watchdog,
    _watchdog_executor as _watchdog_executor,
    WatchdogStatus as WatchdogStatus,
)
from kanbanmate.core.antiloop import AntiLoopConfig, AntiLoopState
from kanbanmate.core.decide import DecideContext
from kanbanmate.core.dependency_gate import evaluate as evaluate_dependencies
from kanbanmate.core.diff import diff
from kanbanmate.core.domain import Action, ActionKind, BoardSnapshot, Column, Transition
from kanbanmate.core.stage_comment import fmt_timestamp, header_from_state
from kanbanmate.core.transitions import TransitionConfig
from kanbanmate.ports.store import TicketState

logger = logging.getLogger(__name__)

# Re-export the reaper's stale-agent sweep + the queue drain under the tick's historical private
# names. Both moved out to ``app/reaper.py`` / ``app/drain.py`` (LOC budget) but tests + callers
# still import ``_reap_stale_agents`` / ``_drain_queue`` here, so keep the aliases stable (no
# signature change). The explicit assignment (not a bare ``import ... as``) makes mypy treat the
# private names as re-exported.
_reap_stale_agents = reap_stale_agents
_drain_queue = _drain_queue_impl

# A running ticket whose agent heartbeat is older than this (seconds) is considered stale and
# reaped (DESIGN §8.3, mirrors the PoC ``reaper.HEARTBEAT_TTL``).
DEFAULT_HEARTBEAT_TTL = 1800.0

# How long (seconds) an agent may be silent before the reaper PROBES its pane for a pending human
# prompt — far shorter than the reap TTL (31.2). A blocked-on-human agent stops touching its
# heartbeat at the prompt; without this it sits unsignalled until the 1800 s reap TTL. Probing once
# silence exceeds ~180 s flips it to WAITING (signal, never reap). Strictly a DETECTION accelerator:
# a non-waiting silent agent is left until the real reap TTL, so this never changes WHEN one is reaped.
DEFAULT_WAITING_PROBE_TTL = 180.0

# The inert column a reaped (stale-agent) ticket's card is parked in (DESIGN §8.3 / §9). The reap
# step moves the card here so the stall is visible on the board; mirrors the PoC reaper's
# ``status_option_map(...).get("Blocked")`` target.
DEFAULT_BLOCKED_COLUMN = "Blocked"

# The terminal column whose ARRIVAL tears down a still-live agent (phase 28.1): a card landing here
# while its state shows a LIVE agent (RUNNING/WAITING) fires a DONE-flavoured teardown (session +
# worktree reclaimed, sticky finalized ✅; the card STAYS in Done) — the skip-to-Done use case.
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

    * **Snapshot decides the common case** with ZERO I/O. ``fully_met`` (no UNMET, no UNKNOWN dep) →
      launch; ``met`` is ``False`` (an on-board dep is not done) → a hard block (no live query can
      satisfy it). Perf property: an all-on-board ticket triggers ZERO ``issue_state`` calls.
    * **Live fallback resolves only the UNKNOWN deps.** When ``verdict.unresolved`` is non-empty
      (deps absent from the snapshot — closed-as-not-planned / moved off-board), the gate queries
      ``deps.board_reader.issue_state(n)`` per dep: CLOSED → MET, OPEN → UNMET. The launch proceeds
      iff ``verdict.met`` AND every unresolved dep resolved CLOSED (PoC parity, without N queries).

    **Fail-soft + bounded.** A throwing/slow ``issue_state`` leaves that dep UNMET (conservative —
    NEVER launch on an undecidable dep); each call inherits the client's mandatory timeouts. Residual
    edge: an OPEN issue whose work is done out-of-band is still UNMET (fix: represent it on the board).

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
    *,
    write_body_status: bool = True,
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
        write_body_status: When ``True`` (the default — NOOP-forward / RUN_SCRIPT callers), ALSO
            mirror the ✅ in the body-top status header (``from_column · done``). The LAUNCH caller
            passes ``False`` (nit 4): a ``running`` body-status write for the NEW stage immediately
            follows in the SAME tick, so writing the LEFT stage's ``done`` here would be a wasted
            second fetch+patch + an extra last-writer race window — collapse to the single end-of-tick
            ``running``. The ✅ STICKY flip still runs; only the body-status header write is skipped.
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
        # FIX 5: mirror the ✅ sticky in the body-top status header (done of the LEFT stage), fully
        # fail-soft. SKIPPED on the LAUNCH path (nit 4 — ``write_body_status=False``): the launch
        # writes the NEW stage's ``running`` in the SAME tick, so a LEFT ``done`` write here would be
        # a wasted second fetch+patch + a race window. The ✅ sticky flip above runs unconditionally.
        if write_body_status:
            # BUG A: surface the latest progress milestone off the just-completed stage's sticky (the
            # header swap above preserved its progress lines). None → fall back to "stage complete".
            progress = latest_progress(deps, issue, from_column, now)
            update_body_status(
                deps.seeder,
                issue,
                stage=from_column,
                state="done",
                summary="stage complete",
                now=now,
                latest_progress=progress,
            )
    except Exception:
        # Defense-in-depth: the upsert already swallows GitHub errors, but a build/encode error
        # in header construction must likewise never break dispatch (DESIGN §8.1 fail-soft).
        logger.exception(
            "✅ left-stage finalize failed for #%s stage=%r; continuing",
            issue,
            from_column,
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
            # Heal No-Status items to the entry column BEFORE the diff/decide loop (default-status).
            # It pre-seeds next_columns so neither this tick's diff nor the next re-fires; fail-soft.
            antiloop = normalize_default_status(
                deps,
                config,
                snapshot=snapshot,
                next_columns=next_columns,
                antiloop=antiloop,
                now=now,
                kill_switch=kill_switch,
            )
            ctx = DecideContext(
                antiloop_state=antiloop,
                # Thread the operator's configured move-rate-limit (columns.yml defaults) into the
                # in-memory anti-loop guard so ``is_blocked`` evaluates the real cap, not the
                # AntiLoopConfig DEFAULT (rate_limit=10); recent_ttl / rate_window keep their
                # defaults (_DEFAULT_RATE_WINDOW is already 3600s → "per hour" semantics, #6).
                antiloop_config=AntiLoopConfig(rate_limit=config.move_rate_limit_per_hour),
                kill_switch=kill_switch,
                now=now,
                reset_target=config.reset_target,
                unattended_hours=config.unattended_hours,
                # Thread the parsed whitelist (phase 12) so decide() classifies each concrete move
                # (launch / run_script / noop / rollback). It is ALWAYS present (wiring supplies the
                # DEFAULT_TRANSITIONS fallback), so a ``None`` here is a wiring bug (DESIGN §8.0.6).
                transitions=config.transitions,
            )
            # Restart-durable launch recovery (#55 / #27): a launch-bearing move records a durable
            # ``pending_launch`` breadcrumb (``_execute_move`` for an operator move, the engine
            # auto-advance for an autonomous one), capturing the TRUE origin column at move time. The
            # in-memory diff baseline (``columns_by_item``) is unreliable across the launch window: it
            # is WIPED on a daemon restart (#20 — the card then looks first-contact ``from=None`` →
            # ``decide`` NOOP, the #55 silent-drop) and it can lag STALE-WRONG (the live #27 bug: the
            # baseline still said ``Plan`` while the card had advanced to ``ReadyToDev``, so the
            # launch-edge move diffed as the un-whitelisted ``Plan → PrepareFeature`` and ROLLED BACK).
            # So for a breadcrumbed item still parked in the launch target, OVERRIDE the baseline with
            # the breadcrumb's recorded origin — re-creating the genuine transition so the existing
            # diff→decide→LAUNCH path fires unchanged. Targeted to breadcrumbed items only (never all
            # cards), so the #20 in-memory-baseline decision stands (no restart storm). A stale
            # breadcrumb (the card has LEFT the launch column — launched-then-advanced, or the operator
            # pulled it back) is cleared here so it can never re-fire; the consumed-on-launch clear
            # lives in ``LaunchAction.execute`` (so a successful launch fires exactly once).
            recovery_baseline = dict(persisted_state.columns_by_item)
            pending_map = deps.store.pending_launches(now=now)
            if pending_map:
                current_by_item = {t.item_id: t.column_key for t in snapshot.tickets}
                for pending_item, pending in pending_map.items():
                    if current_by_item.get(pending_item) != pending.to_col:
                        deps.store.clear_pending_launch(pending_item)
                    else:
                        recovery_baseline[pending_item] = pending.from_col
            for transition in diff(recovery_baseline, snapshot):
                # default-status double-write guard: skip a stale ``→""`` (empty-target) transition
                # whenever this item ALREADY has a NON-EMPTY ``next_columns`` entry. That entry means a
                # heal (the default-status normalization just assigned the default column NAME) or an
                # advance earlier in this loop has already set the item's target THIS tick, so the
                # ``→""`` move is a stale artifact of diffing the snapshot against the PRE-TICK baseline
                # — letting the recording-NOOP run it would revert the baseline back to "" and the next
                # tick would diff ``""→<column>`` (non-None ``from_column``) as a ROLLBACK, bouncing the
                # card back to No Status. A statusless item with NO such entry (e.g. left unhealed under
                # PAUSE) is falsy here, so it is NOT skipped and follows the unchanged NOOP path.
                if transition.to_column == "" and next_columns.get(transition.ticket.item_id):
                    continue
                # Per-transition isolation (#3): process ONE transition under a try/except so a
                # mid-loop raise advances the baseline to the destination + counts an error rather
                # than REPLAYING this move (and its launch) next tick. The full decide→build→dispatch
                # pipeline lives in ``process_transition`` (extracted for the LOC ceiling); it mutates
                # ``next_columns`` / ``status_events`` in place + returns the threaded antiloop + deltas.
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
