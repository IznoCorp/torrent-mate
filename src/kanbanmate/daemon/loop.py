"""The ``kanban run`` daemon: a supervisor-agnostic blocking poll loop (DESIGN §5).

This module is the long-running background process that drives the board. It knows **nothing**
about PM2/launchd/systemd — it is a clean blocking process so it stays testable in CI without a
supervisor and debuggable in a bare terminal (DESIGN §5). All the supervisor cares about is that
the process exits on fatal error and respects SIGTERM; both are handled here.

The loop, per DESIGN §5:

* **Single instance** — a ``flock`` on ``~/.kanban/daemon.lock`` held for the process lifetime;
  a second daemon detects the held lock and exits (belt-and-suspenders with PM2's per-name
  singleton).
* **Config reload on change** — at the top of every iteration the config file's ``mtime`` is
  compared to the last seen value; a change re-reads it (no SIGHUP needed).
* **One tick then a fixed 10 s sleep** — each iteration runs exactly one
  :func:`~kanbanmate.app.tick.tick` (via :func:`~kanbanmate.app.wiring.run_one_tick`) then sleeps
  for :func:`~kanbanmate.core.interval.next_sleep` seconds. The default
  :class:`~kanbanmate.core.interval.IntervalConfig` gives a **fixed 10 s poll cadence** — the idle
  back-off is disabled by default, so a card move is detected within ~10 s no matter how long the
  board has been quiet (the back-off remains opt-in via an explicit ``idle_max > base``).
* **Graceful shutdown** — a SIGTERM (or SIGINT) handler sets a flag the loop checks; the current
  tick always finishes before the process releases the lock and exits (no mid-tick kill).

Layering: ``daemon`` is an entrypoint at the top of the import hierarchy (DESIGN §3.2); it may
import ``app`` and ``core`` freely. It does **not** name concrete adapters — the wiring does that.
"""

from __future__ import annotations

import fcntl
import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType
from typing import IO

import yaml

from kanbanmate.app.tick import PersistedState
from kanbanmate.app.wiring import WiringConfig, run_one_tick
from kanbanmate.core.heartbeat import Heartbeat, render_heartbeat
from kanbanmate.core.interval import IntervalConfig, next_sleep
from kanbanmate.daemon.jsonl_log import JSONLHandler

logger = logging.getLogger(__name__)

# Default runtime root; the lock and config live directly under it (DESIGN §5 / §4).
DEFAULT_KANBAN_ROOT = Path("~/.kanban/").expanduser()

# The single-instance lock filename under the kanban root (DESIGN §5).
LOCK_FILENAME = "daemon.lock"

# The daemon's YAML config filename under the kanban root. Holds the wiring inputs (token, board
# id, repo, clone dir) plus a pointer to the per-repo ``columns.yml``. Phase 2's ``kanban init``
# materialises it; the loop only reads it.
CONFIG_FILENAME = "config.yml"

# The kill-switch sentinel (DESIGN §10 / H5): when present every launch is blocked for the tick.
PAUSE_FILENAME = "PAUSE"

# Failure-mode circuit breaker (#2). The fixed 10 s cadence stays the NORMAL regime; this geometric
# back-off engages ONLY after a run of consecutive tick failures, so the daemon stops re-hammering
# GitHub every 10 s during an outage (or a dead-token 401-loop) and snaps straight back to the tight
# cadence on the first success. The escalation begins once the failure run reaches
# ``_BACKOFF_AFTER_FAILURES`` and grows geometrically, capped at ``_BACKOFF_MAX``.
_BACKOFF_AFTER_FAILURES = 3
_BACKOFF_FACTOR = 2.0
_BACKOFF_MAX = 300.0


class DaemonLockError(RuntimeError):
    """Raised when another daemon already holds the single-instance lock.

    The supervisor (PM2) treats a non-zero exit as a crash; refusing to start when a sibling holds
    the ``flock`` keeps exactly one daemon driving the board (DESIGN §5).
    """


@dataclass
class _ShutdownFlag:
    """A tiny mutable flag toggled by the SIGTERM/SIGINT handler.

    The signal handler must do as little as possible; it only flips :attr:`requested`. The loop
    polls this between ticks so the **current** tick always finishes before the process exits
    (DESIGN §5 graceful shutdown — no mid-tick kill).

    Attributes:
        requested: ``True`` once a termination signal has been received.
    """

    requested: bool = False


@dataclass
class DaemonConfig:
    """The daemon's own runtime knobs, distinct from the per-tick :class:`WiringConfig`.

    Attributes:
        kanban_root: The runtime state root holding the lock, config, and PAUSE sentinel.
        config_path: The config file whose ``mtime`` drives the hot-reload.
        interval: The poll-interval tunables. Defaults to a fixed 10 s cadence
            (idle back-off disabled); the geometric back-off is opt-in only.
    """

    kanban_root: Path = field(default_factory=lambda: DEFAULT_KANBAN_ROOT)
    config_path: Path = field(default_factory=lambda: DEFAULT_KANBAN_ROOT / CONFIG_FILENAME)
    interval: IntervalConfig = field(default_factory=IntervalConfig)


def _install_signal_handlers(flag: _ShutdownFlag) -> None:
    """Install SIGTERM/SIGINT handlers that request a graceful shutdown.

    Both handlers only flip ``flag.requested``; the loop checks it between ticks so the current
    tick finishes cleanly before exit (DESIGN §5). SIGINT is wired too so a foreground ``kanban
    run`` (Ctrl-C, no PM2) shuts down with the same finish-tick-then-exit guarantee.

    Args:
        flag: The shared shutdown flag the handlers set.
    """

    def _handle(signum: int, _frame: FrameType | None) -> None:
        """Record the termination request without doing any work in-handler.

        Args:
            signum: The signal number received (logged for observability).
            _frame: The interrupted stack frame (unused).
        """
        logger.info("received signal %s; will exit after the current tick", signum)
        flag.requested = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)


def _acquire_lock(lock_path: Path) -> IO[str]:
    """Acquire the single-instance lock, or raise if another daemon holds it.

    Opens (creating if needed) ``lock_path`` and takes a non-blocking exclusive ``flock``. The
    returned open file object MUST be kept referenced for the process lifetime — closing it (or
    letting it be garbage-collected) releases the lock. The caller holds it until shutdown.

    Args:
        lock_path: The lock file path (``<kanban_root>/daemon.lock``).

    Returns:
        The open lock file handle; keep it alive to hold the lock.

    Raises:
        DaemonLockError: When another process already holds the lock.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Open for read+write, creating if absent; never truncate (so a stale file is reused safely).
    handle = open(lock_path, "a+")  # noqa: SIM115 — handle must outlive this function (held lock)
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise DaemonLockError(
            f"another kanban daemon already holds {lock_path}; refusing to start"
        ) from exc
    return handle


def _load_wiring_config(config_path: Path) -> WiringConfig:
    """Read the daemon's :class:`WiringConfig` from ``config.yml`` OR the registry.

    Two sources, in precedence order:

    1. **Explicit ``config.yml``** (when ``config_path`` exists) — the YAML document is parsed and
       resolves the per-repo ``columns.yml`` it points at. This is the override path: it carries the
       token inline and can select one of several projects.
    2. **The ``kanban init`` registry** (when ``config.yml`` is ABSENT) — the wiring is derived from
       ``<root>/projects.json`` + the ``<root>/token`` file + the clone's ``columns.yml`` via
       :func:`_wiring_from_registry`, so ``kanban run`` works straight after ``init``/``seed`` with
       no hand-written ``config.yml`` and no duplicated secret (the PAT stays in the 0600 token file).

    The kill-switch is derived from the PAUSE sentinel in the runtime root (DESIGN §10).

    Args:
        config_path: The path to the daemon ``config.yml`` (its parent is the runtime root).

    Returns:
        A :class:`WiringConfig` ready to wire and tick against.

    Raises:
        FileNotFoundError: When neither ``config.yml`` nor a registered project exists.
        ValueError: When ``config.yml`` is absent and >1 project is registered (ambiguous).
        KeyError: When a required ``config.yml`` key is missing.
    """
    if not config_path.exists():
        return _wiring_from_registry(config_path.parent)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    columns_path = Path(raw["columns_path"]).expanduser()
    columns_yaml = columns_path.read_text(encoding="utf-8")
    # transitions_path is a sibling of columns_path, defaulting beside columns.yml
    # in the clone's .claude/kanban/ dir. Tolerate an absent file — a clone without
    # a transitions.yml still ticks via the built-in DEFAULT_TRANSITIONS fallback
    # supplied by the wiring (phase 12.9), never a column model.
    transitions_path_raw = raw.get("transitions_path")
    transitions_yaml: str | None = None
    if transitions_path_raw is not None:
        transitions_path = Path(transitions_path_raw).expanduser()
        if transitions_path.exists():
            transitions_yaml = transitions_path.read_text(encoding="utf-8")
    kanban_root = raw.get("kanban_root")
    # The PAUSE sentinel lives beside the config in the runtime root (DESIGN §10).
    pause_root = Path(kanban_root).expanduser() if kanban_root else config_path.parent
    kill_switch = (pause_root / PAUSE_FILENAME).exists()
    return WiringConfig(
        token=raw["token"],
        project_id=raw["project_id"],
        repo=raw["repo"],
        clone_dir=raw["clone_dir"],
        columns_yaml=columns_yaml,
        kanban_root=kanban_root,
        base=raw.get("base", "main"),
        agent_command=raw.get("agent_command", "claude"),
        kill_switch=kill_switch,
        transitions_yaml=transitions_yaml,
        # Thread config_dir off the config.yml override too (defect 11). The registry path already
        # sets it (``entry.config_dir``); without it here the documented config.yml override left
        # config_dir="" → provision_worktree_skills was a silent no-op, so worktree agents could not
        # resolve the /implement:* skills. Defaulted "" preserves back-compat (no provisioning).
        config_dir=raw.get("config_dir", ""),
    )


def _wiring_from_registry(root: Path) -> WiringConfig:
    """Derive the daemon :class:`WiringConfig` from the ``kanban init`` registry + token file.

    Reads the single registered project from ``<root>/projects.json``, the PAT from the
    ``<root>/token`` file, and the clone's ``columns.yml`` — so the daemon wires itself with no
    hand-written ``config.yml`` and the secret is not duplicated. v1 expects exactly ONE registered
    project; for more, an explicit ``config.yml`` must select one.

    Args:
        root: The runtime root (``~/.kanban``) holding ``projects.json`` + ``token``.

    Returns:
        A :class:`WiringConfig` built from the registry entry, token file, and clone columns.

    Raises:
        FileNotFoundError: When no project is registered (run ``kanban init`` first).
        ValueError: When more than one project is registered (ambiguous; write a ``config.yml``).
    """
    # Lazy import: the registry helpers live in the CLI entrypoint. Importing them at call time
    # (not module scope) keeps the daemon importable without eagerly pulling in the CLI surface.
    from kanbanmate.adapters.github.token import load_token
    from kanbanmate.cli.init import (
        CLONE_COLUMNS_RELPATH,
        CLONE_TRANSITIONS_RELPATH,
        _load_registry,
        _projects_path,
    )

    projects_path = _projects_path(root)
    registry = _load_registry(projects_path) if projects_path.exists() else {}
    if not registry:
        raise FileNotFoundError(
            f"no {root / CONFIG_FILENAME} and no project registered in {projects_path} — "
            "run `kanban init --repo owner/name` first"
        )
    if len(registry) != 1:
        raise ValueError(
            f"{len(registry)} projects registered in {projects_path}; v1 drives exactly one. "
            f"Write an explicit {root / CONFIG_FILENAME} to select which project the daemon runs."
        )
    entry = next(iter(registry.values()))
    columns_yaml = (Path(entry.clone) / CLONE_COLUMNS_RELPATH).read_text(encoding="utf-8")
    # Read the clone's transitions.yml when it exists (a freshly-init'd clone has
    # one from phase 12.7). Absent → None → the wiring falls back to the built-in
    # DEFAULT_TRANSITIONS whitelist (phase 12.9), never a column model.
    transitions_path = Path(entry.clone) / CLONE_TRANSITIONS_RELPATH
    transitions_yaml: str | None = None
    if transitions_path.exists():
        transitions_yaml = transitions_path.read_text(encoding="utf-8")
    return WiringConfig(
        token=load_token(path=root / "token"),
        project_id=entry.project_id,
        repo=entry.repo,
        clone_dir=entry.clone,
        columns_yaml=columns_yaml,
        kanban_root=str(root),
        kill_switch=(root / PAUSE_FILENAME).exists(),
        transitions_yaml=transitions_yaml,
        # The project's .claude dir the launch provisions skills from (phase 14.6); threaded onto
        # Deps.config_dir, mirroring how clone_dir/repo are read off the registry entry. The
        # entry's ``dev_repo_path`` is deliberately NOT threaded here — it is consumed only by the
        # post-merge ``kanban-update-main`` path, which reads it off the registry directly, so it
        # never needs to reach the tick.
        config_dir=entry.config_dir,
    )


def _config_mtime(config_path: Path) -> float | None:
    """Return the config file's modification time, or ``None`` when it is absent.

    Args:
        config_path: The path to watch.

    Returns:
        The POSIX ``mtime`` in seconds, or ``None`` if the file does not exist.
    """
    try:
        return config_path.stat().st_mtime
    except FileNotFoundError:
        return None


# The sentinel a 401/403 auth failure drops beside the heartbeat so ``kanban status``/``doctor``
# can surface a DEGRADED daemon (#1). It is best-effort breadcrumb state, not a lock.
DEGRADED_FILENAME = "DEGRADED"


def _log_actionable_auth_failure(exc: BaseException, kanban_root: Path) -> None:
    """Emit an actionable log line + DEGRADED breadcrumb when a tick failed on a 401/403 (#1).

    A dead/over-broad token surfaces as a :class:`GitHubHTTPError` with status 401/403 raised out
    of the tick's ``cheap_probe``/``snapshot`` path. Logging ``tick raised; continuing`` alone is
    useless — the operator can't tell a token problem from a transient blip. This writes one
    explicit line naming the remediation (check ``~/.kanban/token``) and drops a ``DEGRADED``
    sentinel so the status surfaces the condition rather than looping silently. Any other exception
    is a no-op here (it is already logged with a full traceback by the caller).

    Args:
        exc: The exception the tick raised this poll.
        kanban_root: The runtime root the DEGRADED sentinel is written under.
    """
    # Lazy import: the parser lives in the adapters layer. Importing it at call time (only on the
    # failure path) keeps the daemon module's import surface lean and avoids an eager adapter pull.
    from kanbanmate.adapters.github._parsers import GitHubHTTPError

    if not isinstance(exc, GitHubHTTPError) or exc.status not in (401, 403):
        return
    logger.error(
        "GitHub auth failed (HTTP %s) — token invalid or over-broad; check %s",
        exc.status,
        kanban_root / "token",
    )
    # Best-effort breadcrumb: a write failure here must not compound the auth failure.
    try:
        (kanban_root / DEGRADED_FILENAME).write_text(
            f"auth HTTP {exc.status}: token invalid — check {kanban_root / 'token'}\n"
        )
    except Exception:  # noqa: BLE001 — the sentinel is advisory; never crash on a failed write
        logger.warning("failed to write DEGRADED sentinel; continuing")


def _failure_backoff_sleep(consecutive_failures: int, base_delay: float) -> float:
    """Return the poll delay, escalating geometrically only during a failure run (#2).

    The fixed cadence (``base_delay``, normally 10 s) is the NORMAL regime: while the daemon is
    healthy (or below ``_BACKOFF_AFTER_FAILURES`` consecutive failures) this returns ``base_delay``
    unchanged. Once the failure run reaches the threshold, the delay grows by ``_BACKOFF_FACTOR``
    per extra failure, capped at ``_BACKOFF_MAX`` — so a sustained outage backs the daemon off
    instead of re-hammering GitHub every 10 s. A single successful tick resets
    ``consecutive_failures`` to 0 at the call site, snapping the delay straight back to
    ``base_delay`` (failure-mode-only back-off — the fixed cadence is untouched in the normal case).

    Args:
        consecutive_failures: The current run of consecutive failed ticks.
        base_delay: The normal (healthy-regime) poll delay in seconds.

    Returns:
        ``base_delay`` while healthy/below threshold, else the geometrically-escalated delay
        clamped to ``[base_delay, _BACKOFF_MAX]``.
    """
    if consecutive_failures < _BACKOFF_AFTER_FAILURES:
        return base_delay
    # Grow from base_delay by one factor per failure beyond the threshold; clamp at the ceiling.
    extra = consecutive_failures - _BACKOFF_AFTER_FAILURES
    escalated = base_delay * (_BACKOFF_FACTOR**extra)
    return min(max(escalated, base_delay), _BACKOFF_MAX)


def _clear_degraded(kanban_root: Path) -> None:
    """Remove the DEGRADED sentinel after a tick succeeds (#1, self-recovery).

    Idempotent: a missing sentinel (the common case) is a no-op, and a removal failure is
    swallowed — clearing the breadcrumb must never crash the loop.

    Args:
        kanban_root: The runtime root the DEGRADED sentinel lives under.
    """
    try:
        (kanban_root / DEGRADED_FILENAME).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 — clearing an advisory breadcrumb must never crash the loop
        logger.warning("failed to clear DEGRADED sentinel; continuing")


def run_loop(
    daemon_config: DaemonConfig | None = None,
    *,
    max_iterations: int | None = None,
    sleep: Callable[[float], object] = time.sleep,
) -> None:
    """Run the blocking daemon loop until SIGTERM/SIGINT or ``max_iterations``.

    The loop body, per DESIGN §5:

    1. If the config file's ``mtime`` changed (or it is the first iteration), re-read the
       :class:`WiringConfig` — config-reload-on-change at the top of the tick.
    2. Run exactly one tick via :func:`~kanbanmate.app.wiring.run_one_tick`, threading the
       :class:`~kanbanmate.app.tick.PersistedState` baseline back in so the loop stays idempotent.
    3. Record the time as the last activity when the tick took a snapshot or executed work, then
       sleep for :func:`~kanbanmate.core.interval.next_sleep` seconds (a fixed 10 s cadence by
       default; the idle back-off is opt-in).
    4. Between ticks, check the shutdown flag; finish the current tick before exiting.

    A tick that raises is logged and the loop continues — a single failed cycle must not crash the
    daemon (the supervisor restart is reserved for unrecoverable process death).

    Args:
        daemon_config: The daemon runtime knobs; defaults to :class:`DaemonConfig` (``~/.kanban``).
        max_iterations: Stop after this many iterations (test seam); ``None`` runs until a signal.
        sleep: The sleep callable (injected for tests); defaults to :func:`time.sleep`.

    Raises:
        DaemonLockError: When another daemon already holds the single-instance lock.
    """
    config = daemon_config or DaemonConfig()

    # Install the structured JSONL log handler early so every log record emitted
    # during the daemon's lifetime lands in ``<root>/log/daemon.jsonl`` — the
    # file ``kanban logs`` reads (DESIGN §5). Best-effort: write failures are
    # handled inside the handler and never crash the daemon.
    jsonl_handler = JSONLHandler(config.kanban_root / "log" / "daemon.jsonl")
    logging.getLogger().addHandler(jsonl_handler)
    # Ensure INFO+ records reach our handler even when ``main()`` (and its
    # ``basicConfig(level=INFO)``) hasn't been called (test seam). Production
    # ``main()`` already sets this; the setLevel here is idempotent.
    logging.getLogger().setLevel(logging.INFO)

    flag = _ShutdownFlag()
    _install_signal_handlers(flag)

    lock_path = config.kanban_root / LOCK_FILENAME
    lock_handle = _acquire_lock(lock_path)
    logger.info("kanban daemon started (lock %s held)", lock_path)

    state = PersistedState()
    wiring: WiringConfig | None = None
    last_mtime: float | None = None
    # Seed "last activity" at start so the first idle stretch backs off from now, not the epoch.
    last_activity = time.time()
    iterations = 0
    # Tick-health bookkeeping for the structured heartbeat (#1). ``consecutive_failures``
    # counts ticks that RAISED in a row (reset to 0 on the first tick that returns); it
    # is written into ``daemon.heartbeat`` so doctor can FAIL a daemon that is alive but
    # persistently failing (the proven dead-token 401-loop incident, where the marker
    # used to stay green forever).
    consecutive_failures = 0

    try:
        while not flag.requested:
            if max_iterations is not None and iterations >= max_iterations:
                break

            # Step 1: config-reload-on-change (DESIGN §5). Re-read on first pass or mtime change.
            current_mtime = _config_mtime(config.config_path)
            if wiring is None or current_mtime != last_mtime:
                try:
                    wiring = _load_wiring_config(config.config_path)
                except Exception:
                    if wiring is None:
                        # First load — no last-good config to fall back to. Let it
                        # propagate: a daemon that can't load its initial config
                        # legitimately fails to start.
                        raise
                    logger.exception(
                        "config reload failed — bad or malformed %s? Keeping last-good config",
                        config.config_path,
                    )
                else:
                    logger.info("loaded config from %s", config.config_path)
                # Update the mtime marker even on a failed reload so we don't
                # retry-storm every iteration on a persistently-bad file; the
                # reload is re-attempted only when the mtime changes again (a new
                # write by the operator).
                last_mtime = current_mtime

            # Step 2: one idempotent tick, threading the persisted baseline forward.
            try:
                result, state = run_one_tick(wiring, state)
            except Exception as exc:  # noqa: BLE001 — one failed tick must not crash the daemon
                logger.exception("tick raised; continuing")
                result = None
                # The tick raised ⇒ this poll FAILED. Bump the consecutive-failure run so the
                # heartbeat (and doctor) surface a daemon that is alive but not succeeding (#1).
                consecutive_failures += 1
                _log_actionable_auth_failure(exc, config.kanban_root)
            else:
                # The tick RETURNED (action-level errors are isolated inside the tick and do
                # not count as a failed poll) ⇒ snap the failure run back to zero (#1) and clear
                # any DEGRADED sentinel a prior auth failure dropped, so the daemon self-recovers
                # the moment the operator fixes the token.
                consecutive_failures = 0
                _clear_degraded(config.kanban_root)

            # Step 3: anything happened this tick ⇒ reset the idle clock so the cadence stays tight.
            now = time.time()
            if result is not None and (
                result.snapshot_taken or result.actions_executed or result.reaped
            ):
                last_activity = now

            iterations += 1

            # Write the structured daemon heartbeat marker so ``kanban doctor`` can verify both
            # liveness AND tick health (#1, DESIGN §5). The marker is JSON carrying ``ts`` (the
            # freshness signal), ``last_tick_ok`` (did this tick return?), and the running
            # ``consecutive_failures`` count — so a daemon that is alive but persistently failing
            # (the dead-token 401-loop) stops looking green to doctor. Best-effort: a write failure
            # must not crash the loop — the worst case is a stale/missing heartbeat tripping doctor.
            heartbeat = Heartbeat(
                ts=now,
                last_tick_ok=consecutive_failures == 0,
                consecutive_failures=consecutive_failures,
            )
            try:
                (config.kanban_root / "daemon.heartbeat").write_text(render_heartbeat(heartbeat))
            except Exception:
                # Swallow-don't-crash: the daemon must survive a heartbeat-write failure (the
                # worst case is doctor seeing a stale marker, not a dead daemon). But a SILENT
                # swallow hides a persistent failure (a full disk, a perms regression on
                # kanban_root) — so leave a breadcrumb. logger.warning (not exception) keeps it
                # to one line per tick rather than a full traceback flood (#14).
                logger.warning("failed to write daemon heartbeat marker; continuing")

            # Finish-tick-then-exit: re-check the flag before sleeping so a SIGTERM during the tick
            # exits promptly without waiting out the poll sleep.
            if flag.requested:
                break

            # The normal cadence is the fixed-10 s ``next_sleep``; during a run of consecutive
            # failures the circuit breaker (#2) escalates it geometrically (capped 300 s) so the
            # daemon stops re-hammering GitHub through an outage. A single success resets the run
            # above, snapping the delay back to the tight cadence.
            base_delay = next_sleep(last_activity, now, config.interval)
            delay = _failure_backoff_sleep(consecutive_failures, base_delay)
            sleep(delay)
    finally:
        # Release the single-instance lock, log shutdown, and remove our
        # JSONL handler so test suites that call run_loop multiple times
        # don't accumulate stale handlers pointing at deleted tmp_paths.
        lock_handle.close()
        logger.info("kanban daemon stopped (lock released)")
        logging.getLogger().removeHandler(jsonl_handler)


def main(root: Path | None = None) -> None:
    """Console-script entry for ``kanban run``: start the blocking daemon loop.

    Configures a minimal root logger then runs :func:`run_loop`. With ``root`` ``None`` it uses the
    default ``~/.kanban`` runtime root; otherwise it points the daemon at ``root`` (its
    ``projects.json`` / ``config.yml`` / lock / PAUSE), enabling a SECOND daemon on the same machine
    for a different project under a separate root (one daemon drives one project, DESIGN §5). Kept
    side-effect-free at import time — nothing runs until this is called.

    Args:
        root: The runtime root the daemon drives; ``None`` → the default ``~/.kanban``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if root is None:
        run_loop()
    else:
        run_loop(DaemonConfig(kanban_root=root, config_path=root / CONFIG_FILENAME))
