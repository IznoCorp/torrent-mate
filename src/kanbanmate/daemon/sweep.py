"""Per-project sweep: run one tick per enabled project (ingress-multiproject §3.1).

The daemon generalises from "one board per runtime root" to "N boards per daemon". The run loop
(``daemon/loop.py``) keeps the lock / signal / config-reload / interruptible-sleep skeleton and
delegates the per-project work to :func:`sweep_projects` here — mirroring the existing
``app/reaper.py`` / ``app/drain.py`` extractions that keep ``loop.py`` under the LOC ceiling.

The sweep runs each project's :func:`~kanbanmate.app.wiring.run_one_tick` SEQUENTIALLY (NOT
concurrently): sequential keeps the proven single-tick semantics, the per-action watchdog, and a
bounded GitHub rate budget; concurrency is a deferred optimisation. Each project carries its own
:class:`~kanbanmate.app.tick.PersistedState` diff baseline (the collision-free per-project store
sub-root, §3.2) and its own circuit-breaker failure count, so a failing project never trips a
healthy sibling. A daemon-level rollup (any-snapshot / any-action / any-reap / aggregate failures)
feeds the loop's idle clock + back-off exactly as the single-project loop's bookkeeping did.

Layering: ``daemon`` is a top entrypoint (DESIGN §3.2) — it may import ``app`` and ``core`` freely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from kanbanmate.app.tick import PersistedState
from kanbanmate.app.wiring import WiringConfig, run_one_tick

logger = logging.getLogger(__name__)


@dataclass
class ProjectSweepState:
    """The per-project bookkeeping carried ACROSS ticks (one instance per project_id).

    Held in the loop's ``state_by_project`` map and threaded back into the next sweep so each
    project's diff baseline + circuit-breaker survive between iterations (restart re-syncs from the
    board, exactly as the single-project loop's in-memory ``PersistedState`` does).

    Attributes:
        persisted: The project's diff baseline (the ``columns_by_item`` carried forward so a move
            does not re-fire each tick). Fresh on first sweep (cold start → full board re-sync).
        consecutive_failures: The project's own run of consecutive failed ticks (probe raise OR a
            returned-but-``probe_failed`` tick), reset to 0 on the first clean tick. Drives the
            per-project circuit-breaker; a failing project does NOT trip a healthy sibling.
    """

    persisted: PersistedState = field(default_factory=PersistedState)
    consecutive_failures: int = 0


@dataclass
class SweepResult:
    """The daemon-level rollup of one sweep over all enabled projects.

    Aggregates the per-project tick outcomes into the single signals the loop needs for its idle
    clock + back-off + heartbeat — so the loop body stays unchanged in shape (it consumed one
    ``TickResult`` before; now it consumes this rollup with the same fields).

    Attributes:
        any_snapshot: ``True`` when ANY project took a board snapshot this sweep (idle-clock reset).
        any_action: ``True`` when ANY project executed an action this sweep (idle-clock reset).
        any_reap: ``True`` when ANY project reaped/relaunched a stale agent this sweep.
        total_errors: The sum of per-project action-level errors across the sweep.
        max_consecutive_failures: The WORST per-project consecutive-failure run after this sweep —
            the OBSERVABILITY / DEGRADED-breadcrumb signal (so a single failing project still
            surfaces a dead-token 401-loop to ``doctor``/``status`` even while siblings are healthy).
        min_consecutive_failures: The BEST (lowest) per-project consecutive-failure run after this
            sweep — the daemon-level circuit-breaker / back-off input (#5). The back-off engages
            ONLY when EVERY enabled project is failing (``min > 0``); a single HEALTHY project
            (``min == 0``) keeps the daemon sweeping at its tight cadence, so one project's dead
            token never throttles a healthy sibling's sweep ("a failing project never trips a healthy
            sibling"). ``0`` when no project was swept (the empty-wirings edge → no back-off).
        projects_swept: How many enabled projects were ticked this sweep (observability).
    """

    any_snapshot: bool = False
    any_action: bool = False
    any_reap: bool = False
    total_errors: int = 0
    max_consecutive_failures: int = 0
    min_consecutive_failures: int = 0
    projects_swept: int = 0
    # The last probe/tick error observed this sweep (a 401/403 → the loop writes the DEGRADED
    # sentinel + the actionable auth-failure log line, exactly as the single-project loop did). None
    # when no project raised / probe-failed this sweep.
    last_error: BaseException | None = None


def sweep_projects(
    wirings: list[WiringConfig],
    state_by_project: dict[str, ProjectSweepState],
    *,
    kanban_root: Path,
    now: float,
    force_snapshot: bool = False,
) -> SweepResult:
    """Run one tick per project sequentially, aggregating into a daemon-level :class:`SweepResult`.

    For each wiring (one per enabled project) this threads the project's own
    :class:`ProjectSweepState` through :func:`~kanbanmate.app.wiring.run_one_tick`, updates that
    project's diff baseline + circuit-breaker, writes its per-project heartbeat marker, and folds
    the outcome into the rollup. A tick that RAISES is isolated per-project (logged, the project's
    failure run bumped) so one bad board never crashes the sweep or stalls the others. A probe
    failure (the tick returned but flagged ``probe_failed``) is likewise counted as a failed poll
    for that project (the dead-token / outage signal) without resetting its run.

    Args:
        wirings: One :class:`WiringConfig` per ENABLED project (the loop builds these from the
            registry; an N=1 root yields a 1-element list — the single-project path unchanged).
        state_by_project: The persistent per-project bookkeeping, keyed by ``project_id`` and
            MUTATED in place (the loop owns the dict across iterations).
        kanban_root: The runtime root the per-project heartbeat markers are written under.
        now: The sweep's wall-clock time (one timestamp for the whole sweep — the heartbeat ``ts``).
        force_snapshot: When ``True`` (P2) EVERY project's tick re-snapshots even on an unchanged
            probe — the loop passes this on a nudge-woken / fast-poll sweep so a CLI move or a
            restart-present move is reconciled within one slice. Default ``False`` keeps the
            probe-gated cadence (the normal poll sweep).

    Returns:
        The daemon-level :class:`SweepResult` rollup feeding the loop's idle clock + back-off.
    """
    rollup = SweepResult()
    # The per-project failure runs after this sweep — folded into the rollup's max (DEGRADED
    # observability) AND min (#5 back-off: only back off when EVERY project is failing).
    failure_runs: list[int] = []
    for wiring in wirings:
        pid = wiring.project_id
        sweep_state = state_by_project.setdefault(pid, ProjectSweepState())
        _sweep_one(
            wiring,
            sweep_state,
            rollup,
            kanban_root=kanban_root,
            now=now,
            force_snapshot=force_snapshot,
        )
        rollup.projects_swept += 1
        failure_runs.append(sweep_state.consecutive_failures)
        rollup.max_consecutive_failures = max(
            rollup.max_consecutive_failures, sweep_state.consecutive_failures
        )
    # #5: the back-off keys on the BEST (lowest) run, so one failing project never throttles a
    # healthy sibling — the daemon backs off only when EVERY project is failing (min > 0). An empty
    # sweep (no wirings) leaves min at 0 (no back-off), matching the no-projects edge.
    rollup.min_consecutive_failures = min(failure_runs) if failure_runs else 0
    return rollup


def _sweep_one(
    wiring: WiringConfig,
    sweep_state: ProjectSweepState,
    rollup: SweepResult,
    *,
    kanban_root: Path,
    now: float,
    force_snapshot: bool = False,
) -> None:
    """Tick ONE project, updating its bookkeeping + folding into ``rollup`` (isolated per project).

    Args:
        wiring: The project's wiring.
        sweep_state: The project's persistent bookkeeping (MUTATED: baseline + failure run).
        rollup: The daemon-level rollup (MUTATED in place).
        kanban_root: The runtime root the per-project heartbeat marker is written under.
        now: The sweep's wall-clock time.
        force_snapshot: Forwarded to :func:`~kanbanmate.app.wiring.run_one_tick` (P2): re-snapshot
            even on an unchanged probe (a nudge / fast-poll tick). Default ``False``.
    """
    pid = wiring.project_id
    try:
        # Pass ``force_snapshot`` ONLY when set (the nudge / fast-poll path) so the common
        # probe-gated sweep calls ``run_one_tick`` with its historical 2-arg positional signature —
        # keeping every existing 2-arg test double (``lambda w, s: ...``) working unchanged.
        if force_snapshot:
            tick_result, next_persisted = run_one_tick(
                wiring, sweep_state.persisted, force_snapshot=True
            )
        else:
            tick_result, next_persisted = run_one_tick(wiring, sweep_state.persisted)
    except Exception as exc:  # noqa: BLE001 — one project's failed tick must NOT crash the sweep
        logger.exception("project %s: tick raised; continuing", pid)
        sweep_state.consecutive_failures += 1
        rollup.last_error = exc
        _write_project_heartbeat(
            kanban_root, pid, ok=False, fails=sweep_state.consecutive_failures, now=now
        )
        return

    # The tick returned; advance the project's diff baseline so its moves do not re-fire next sweep.
    sweep_state.persisted = next_persisted

    if tick_result.probe_failed:
        # A probe failure is a FAILED poll even though the tick returned (the dead-token / outage
        # signal); bump the run WITHOUT resetting it (matches the single-project loop's FIX4 path).
        sweep_state.consecutive_failures += 1
        if tick_result.probe_error is not None:
            rollup.last_error = tick_result.probe_error
    else:
        # A clean tick snaps this project's failure run back to zero (self-recovery on the next
        # successful probe), exactly like the single-project loop.
        sweep_state.consecutive_failures = 0

    # Fold this project's outcome into the daemon-level rollup.
    rollup.any_snapshot = rollup.any_snapshot or tick_result.snapshot_taken
    rollup.any_action = rollup.any_action or bool(tick_result.actions_executed)
    rollup.any_reap = rollup.any_reap or bool(tick_result.reaped) or bool(tick_result.relaunched)
    rollup.total_errors += tick_result.errors

    _write_project_heartbeat(
        kanban_root,
        pid,
        ok=sweep_state.consecutive_failures == 0,
        fails=sweep_state.consecutive_failures,
        now=now,
    )


def _write_project_heartbeat(
    kanban_root: Path, project_id: str, *, ok: bool, fails: int, now: float
) -> None:
    """Write a PER-PROJECT heartbeat marker so doctor/status can verify each board's liveness.

    The runtime-root ``daemon.heartbeat`` (written by the loop) is daemon-wide; this per-project
    marker (``<root>/projects/heartbeats/<safe(pid)>.heartbeat``) lets ``kanban doctor`` /
    ``kanban status`` render one row per project (DESIGN §8). Best-effort: a write failure must
    never crash the sweep (the worst case is a stale per-project marker), so it is wholly swallowed.

    Args:
        kanban_root: The runtime root the marker is written under.
        project_id: The project node id the marker is keyed by (slugged for the filename).
        ok: Whether this project's last tick succeeded (``consecutive_failures == 0``).
        fails: The project's current consecutive-failure run.
        now: The marker timestamp (the freshness signal).
    """
    # Lazy import (kept off the hot path / module-import scope): the heartbeat renderer + the slug.
    from kanbanmate.core.heartbeat import Heartbeat, render_heartbeat
    from kanbanmate.core.registry_resolve import safe_project_id

    try:
        hb_dir = kanban_root / "projects" / "heartbeats"
        hb_dir.mkdir(parents=True, exist_ok=True)
        marker = hb_dir / f"{safe_project_id(project_id)}.heartbeat"
        marker.write_text(
            render_heartbeat(Heartbeat(ts=now, last_tick_ok=ok, consecutive_failures=fails))
        )
    except Exception:  # noqa: BLE001 — advisory marker; never crash the sweep on a write failure
        logger.warning("project %s: failed to write per-project heartbeat; continuing", project_id)
