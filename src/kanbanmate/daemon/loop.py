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
* **Sleep-interrupt nudge (0.4.0)** — the inter-tick sleep is INTERRUPTIBLE: it sleeps in fixed
  slices via :func:`_interruptible_sleep` and returns early the moment the intent-queue nudge
  sentinel (``intents/.nudge``)'s mtime advances. The enqueue side (CLI ``kanban move`` /
  ``kanban-move``) bumps the sentinel after every ``enqueue_intent``, so an enqueued intent is
  drained within one slice (~0.5 s) instead of waiting out a full interval — WITHOUT lowering the
  interval (no API-quota cost). The mechanism is fail-soft (a sentinel read failure degrades to a
  full-interval sleep) and cross-process (a ``threading.Event`` cannot bridge the separate enqueuer
  and daemon processes).
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

# The nudge-sentinel name + its directory are owned by the store adapter (the queue's writer). The
# daemon is a top entrypoint (no upward-import constraint, see test_layering FORBIDDEN), so it imports
# those constants directly to build its path-local nudge reader — a SINGLE source of truth, so the two
# ends can never drift on the filename (#3 de-dup).
from kanbanmate.adapters.store.fs_intents import INTENTS_DIRNAME, NUDGE_FILENAME
from kanbanmate.app.wiring import WiringConfig
from kanbanmate.core.heartbeat import Heartbeat, render_heartbeat
from kanbanmate.core.interval import IntervalConfig, daemon_base_seconds, next_sleep
from kanbanmate.daemon.jsonl_log import JSONLHandler

# The CONFIG/PAUSE filenames + the registry→wiring resolution live in ``registry_wiring`` (split out
# for the LOC ceiling, #1). Re-EXPORTED here (the ``as X`` redundant-alias form marks them explicit
# re-exports for mypy) so ``daemon.loop.CONFIG_FILENAME`` / ``PAUSE_FILENAME`` stay importable for the
# many modules + tests that read them off this module (back-compat).
from kanbanmate.daemon.registry_wiring import CONFIG_FILENAME as CONFIG_FILENAME
from kanbanmate.daemon.registry_wiring import PAUSE_FILENAME as PAUSE_FILENAME
from kanbanmate.daemon.registry_wiring import (
    wiring_for_entry,
    wiring_for_selection,
)
from kanbanmate.daemon.sweep import ProjectSweepState, sweep_projects

logger = logging.getLogger(__name__)

# Default runtime root; the lock and config live directly under it (DESIGN §5 / §4).
DEFAULT_KANBAN_ROOT = Path("~/.kanban/").expanduser()

# The single-instance lock filename under the kanban root (DESIGN §5).
LOCK_FILENAME = "daemon.lock"

# Failure-mode circuit breaker (#2). The fixed 10 s cadence stays the NORMAL regime; this geometric
# back-off engages ONLY after a run of consecutive tick failures, so the daemon stops re-hammering
# GitHub every 10 s during an outage (or a dead-token 401-loop) and snaps straight back to the tight
# cadence on the first success. The escalation begins once the failure run reaches
# ``_BACKOFF_AFTER_FAILURES`` and grows geometrically, capped at ``_BACKOFF_MAX``.
_BACKOFF_AFTER_FAILURES = 3
_BACKOFF_FACTOR = 2.0
_BACKOFF_MAX = 300.0

# The intent-queue nudge sentinel (0.4.0). The enqueue side (CLI/agent) bumps its mtime via
# ``IntentStore.nudge_daemon``; the daemon's interruptible inter-tick sleep returns early when it
# observes the mtime advance — so an enqueued intent is drained within one slice instead of a full
# poll interval, WITHOUT lowering the interval (no API-quota cost). The path components are DERIVED
# from the store adapter's own constants (#3 de-dup) so the name lives in exactly one place.
_NUDGE_RELPATH = (INTENTS_DIRNAME, NUDGE_FILENAME)
# Interruptible-sleep granularity: the worst-case nudge wake latency. 0.5 s is imperceptible for a
# cockpit yet vastly tighter than the ~10 s full interval; at most ``delay/slice`` cheap ``stat()``
# calls per inter-tick gap (~20 per 10 s) — not a busy-loop (each slice is a real ``sleep``).
_NUDGE_SLICE_SECONDS = 0.5
# Reflex fast-poll window: how many ticks after a nudge wake poll at the TIGHT base instead of the
# slow webhook fallback. It covers two post-nudge waits:
#   1. a self-initiated auto-advance whose move lags GitHub's eventual-consistent API by a beat (the
#      original reflex case — needs only a few ticks);
#   2. a kanban-done nudge where the agent is still finishing its FINAL turn: the reaper must NOT cut a
#      mid-turn agent, so it DEFERS ending the session until the pane goes idle (reaper.py
#      ``_pane_has_active_turn``). That final turn can run for tens of seconds AFTER kanban-done, and
#      the window must stay open across it — else the daemon reverts to the slow ~120 s fallback and
#      the now-idle done agent waits a full poll before its session is ended + the card advances (the
#      observed ~60 s "finished-but-idle" gap).
# 8 ticks × base (~10 s) ≈ ~100 s comfortably covers a realistic final turn while staying bounded. This
# ONLY changes the poll CADENCE, never WHEN a session is ended (the reaper's idle-guard is untouched),
# so it cannot interrupt a working agent.
_FAST_POLL_AFTER_NUDGE_TICKS = 8


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
    """Derive a SINGLE :class:`WiringConfig` from the registry, no selector (back-compat shim).

    Thin no-selector delegate to
    :func:`~kanbanmate.daemon.registry_wiring.wiring_for_selection` — kept for any caller that still
    wants "the sole project's wiring" (N=1 returns it; N>1 fails loud via
    :class:`~kanbanmate.daemon.registry_wiring.ProjectSelectionError`). New code should call
    ``wiring_for_selection`` with the operator's ``--project``/``--repo`` selector so a
    multi-project root is usable from the CLI (#1).

    Args:
        root: The runtime root (``~/.kanban``) holding ``projects.json`` + ``token``.

    Returns:
        A :class:`WiringConfig` for the resolved project.

    Raises:
        FileNotFoundError: When no project is registered (run ``kanban init`` first).
        ProjectSelectionError: When >1 project is registered and no selector disambiguates.
    """
    return wiring_for_selection(root)


def _load_wirings(config_path: Path) -> list[WiringConfig]:
    """Build the daemon's per-project :class:`WiringConfig` LIST (ingress-multiproject §3.1).

    Generalises :func:`_load_wiring_config` from "one wiring" to "N wirings — one per enabled
    project". Two sources, same precedence as the single-wiring loader:

    1. **Explicit ``config.yml``** (when it exists) — the YAML selects exactly ONE project (the
       override path is unchanged), so this returns a 1-element list. An operator running N projects
       does NOT write a ``config.yml`` — they register N projects and let the registry path drive.
    2. **The registry** (when ``config.yml`` is ABSENT) — :func:`_wirings_from_registry` builds one
       wiring per ENABLED ``projects.json`` entry. N=1 yields a 1-element list with the LEGACY FLAT
       store layout (no ``state_root``, ``multi_project=False``) → byte-identical to today.

    Args:
        config_path: The path to the daemon ``config.yml`` (its parent is the runtime root).

    Returns:
        A non-empty list of :class:`WiringConfig` (one per enabled project).

    Raises:
        FileNotFoundError: When neither ``config.yml`` nor any enabled project exists.
        ValueError / KeyError: As :func:`_load_wiring_config` raises for a malformed ``config.yml``.
    """
    if config_path.exists():
        # Explicit override selects one project → a 1-element list (the single-project path).
        return [_load_wiring_config(config_path)]
    return _wirings_from_registry(config_path.parent)


def _wirings_from_registry(root: Path) -> list[WiringConfig]:
    """Build one :class:`WiringConfig` per ENABLED registry entry (ingress-multiproject §3.1).

    The N=1 collapse is the back-compat hinge: with exactly one enabled project this returns a
    1-element list whose wiring carries NO ``state_root`` (the legacy flat store layout) and
    ``multi_project=False`` (no project pin / KANBAN_PROJECT_ID export) — so an existing deployed
    single-project daemon sees ZERO behaviour change. With N>1 each wiring is rooted at the
    per-project store sub-root (``<root>/projects/<safe(pid)>``) and marked ``multi_project=True``.

    Args:
        root: The runtime root (``~/.kanban``) holding ``projects.json`` + the token(s).

    Returns:
        A non-empty list of per-project wirings (sorted by ``project_id`` for a stable sweep order).

    Raises:
        FileNotFoundError: When no project is registered, or all registered projects are disabled.
    """
    from kanbanmate.cli.init import _load_registry, _projects_path
    from kanbanmate.core.registry_resolve import enabled_entries

    projects_path = _projects_path(root)
    registry = _load_registry(projects_path) if projects_path.exists() else {}
    if not registry:
        raise FileNotFoundError(
            f"no {root / CONFIG_FILENAME} and no project registered in {projects_path} — "
            "run `kanban init --repo owner/name` first"
        )
    enabled = enabled_entries(registry)
    if not enabled:
        raise FileNotFoundError(
            f"no ENABLED project in {projects_path} — every registered project has enabled=false"
        )
    multi = len(enabled) > 1
    kill_switch = (root / PAUSE_FILENAME).exists()
    # Each enabled entry → one wiring via the SHARED single-entry builder (so the daemon sweep and
    # the CLI read-commands construct an entry's wiring identically — one source of truth, #1).
    return [
        wiring_for_entry(root, entry, multi=multi, kill_switch=kill_switch) for entry in enabled
    ]


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


def _effective_interval(wirings: list[WiringConfig], base_cfg: IntervalConfig) -> IntervalConfig:
    """Return the cadence config for this sweep, honouring webhook ingress (ingress-multiproject §5.2).

    The daemon's base poll cadence is the TIGHTEST any enabled project needs (one daemon = one
    sleep): a ``polling`` project keeps the tight ``base_cfg.base`` (10 s by default), while an
    ALL-``webhook`` daemon polls slowly at the webhook fallback cadence (the always-on safety sweep)
    and relies on the nudge for fast reaction. When a polling project is present (or the operator
    has explicitly customised the interval with ``idle_max > base`` — the opt-in back-off), the
    operator's ``base_cfg`` is returned UNCHANGED, so the deployed single-project polling daemon is
    byte-identical. Only an all-webhook daemon on the default flat interval gets the slow fallback.

    Args:
        wirings: The current per-project wirings (their ``ingress`` modes drive the cadence).
        base_cfg: The operator-configured :class:`IntervalConfig` (the override / default).

    Returns:
        ``base_cfg`` unchanged when any project polls or the operator opted into a custom back-off;
        else a flat webhook-fallback :class:`IntervalConfig` (slow safety sweep).
    """
    modes = [w.ingress for w in wirings]
    # An operator who opted into the geometric back-off (idle_max > base) keeps their config as-is.
    operator_customised = base_cfg.idle_max > base_cfg.base
    if operator_customised or any(mode == "polling" for mode in modes):
        return base_cfg
    # All-webhook on the default flat interval → the slow fallback safety sweep (nudge collapses it).
    fallback = daemon_base_seconds(modes)
    if fallback == base_cfg.base:
        return base_cfg  # already the right base (e.g. a polling daemon / empty wirings)
    return IntervalConfig(base=fallback, idle_max=fallback, backoff=base_cfg.backoff)


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


def _make_nudge_reader(kanban_root: Path) -> Callable[[], int]:
    """Return a closure reading the intent-queue nudge sentinel's NANOSECOND mtime (fail-soft → 0).

    Reads the sentinel path directly rather than constructing a store just for the nudge — mirroring
    the daemon's existing direct sentinel reads for PAUSE/DEGRADED, so the loop adds no eager adapter
    pull. The canonical store reader (:meth:`IntentStore.nudge_mtime`) is used by tests + the
    agent/CLI enqueue symmetry; the loop uses this cheap path-local twin (same file, same semantics).

    #5 mtime-granularity fix: this returns ``st_mtime_ns`` (nanosecond resolution, an ``int``) rather
    than the second-granular ``st_mtime``. On a coarse-mtime filesystem (1 s resolution) an enqueue
    within the SAME second as the tick-start baseline could share an identical ``st_mtime`` → the
    strict ``>`` comparison would MISS it (no early wake). Nanosecond mtimes make a same-second enqueue
    resolvable, so the strict ``>`` stays correct (consume-on-read: still exactly one wake per
    un-drained nudge) while detecting sub-second enqueues. The value is kept as an ``int`` (NOT cast to
    ``float``): a ns timestamp (~1.7e18) exceeds float64's exact-integer range (2**53), so a float cast
    would round away sub-~256 ns differences — exactly the fine-grained advances #5 needs to detect.

    Args:
        kanban_root: The runtime root under which ``intents/.nudge`` lives.

    Returns:
        A zero-arg closure returning the sentinel's POSIX mtime in NANOSECONDS (``int``), or ``0`` when
        absent/unreadable.
    """
    nudge_path = kanban_root.joinpath(*_NUDGE_RELPATH)

    def _read() -> int:
        try:
            return nudge_path.stat().st_mtime_ns
        except (FileNotFoundError, OSError):
            return 0

    return _read


def _interruptible_sleep(
    delay: float,
    *,
    sleep: Callable[[float], object],
    nudge_mtime: Callable[[], int],
    flag: _ShutdownFlag,
    baseline: int | None = None,
    slice_seconds: float = _NUDGE_SLICE_SECONDS,
) -> bool:
    """Sleep up to ``delay`` seconds, returning EARLY on a nudge (mtime bump) or shutdown (0.4.0).

    Sleeps in fixed ``slice_seconds`` slices; after each slice it re-reads ``nudge_mtime`` and
    returns the moment it advances past ``baseline`` — so an enqueued intent wakes the daemon within
    one slice instead of a full interval, WITHOUT a busy-loop (each slice is a real ``sleep``) and
    WITHOUT changing the poll interval. The shutdown flag is also honoured between slices, so a SIGTERM
    during the inter-tick sleep exits within one slice (a bonus responsiveness improvement that does
    not change the finish-tick-then-exit guarantee — the current tick already completed before this is
    called). Fail-soft: a ``nudge_mtime`` read that raises is treated as "no nudge" (degrades to the
    full-interval sleep).

    Consume-on-read via mtime monotonicity. The ``baseline`` is captured by the CALLER at TICK START
    (#2 fix), BEFORE ``run_one_tick`` (hence before ``drain_intents`` and the whole post-drain window),
    rather than here at sleep entry. This closes a latency hole: an intent enqueued in the tick's
    post-drain window (after ``drain_intents`` ran but before this sleep) now has an mtime > the
    tick-start baseline → it wakes THIS sleep, instead of waiting a full extra cycle for the next
    sleep-entry baseline to notice it. A single un-drained nudge still wakes exactly one sleep: a
    nudge already present + drained before tick start has an mtime ≤ baseline (no wake); a nudge after
    tick start (drained or not) wakes this sleep, and the next tick captures a fresh baseline. ``None``
    falls back to capturing the baseline here (the pre-#2 behaviour, kept for the test seam).

    Args:
        delay: The full inter-tick sleep budget in seconds (``<= 0`` returns immediately).
        sleep: The sleep callable (injected for tests); called once per slice.
        nudge_mtime: The nudge-sentinel mtime reader (a bump past ``baseline`` wakes early).
        flag: The shared shutdown flag, re-checked between slices.
        baseline: The nudge-mtime baseline (nanoseconds, ``int``) captured by the caller at tick start
            (#2). ``None`` → capture it here at sleep entry (legacy fallback / test seam).
        slice_seconds: The slice granularity (the worst-case nudge wake latency). A ``<= 0`` value
            degrades to :data:`_NUDGE_SLICE_SECONDS` so a misconfigured slice can never busy-loop
            (``sleep(0)`` that never decrements ``remaining``) — defensive (#6).

    Returns:
        ``True`` when a nudge (mtime bump past ``baseline``) woke the sleep EARLY — the caller uses
        this to open a fast-poll window that beats GitHub's eventual-consistent API after a self-move
        (reflex). ``False`` when the full ``delay`` elapsed, ``delay <= 0``, or the shutdown flag was
        set (none of which warrant a fast re-check).
    """
    if delay <= 0:
        return False
    # #6 defensive guard: a non-positive slice would make ``chunk = min(slice, remaining)`` <= 0, so
    # ``sleep(0)`` would never decrement ``remaining`` → a tight busy-loop. Clamp to the default.
    if slice_seconds <= 0:
        slice_seconds = _NUDGE_SLICE_SECONDS
    if baseline is None:
        # Legacy fallback (no caller-supplied baseline): capture at sleep entry, fail-soft to 0.
        try:
            baseline = nudge_mtime()
        except Exception:  # noqa: BLE001 — fail-soft: degrade to a normal full-interval sleep
            baseline = 0
    remaining = delay
    while remaining > 0 and not flag.requested:
        chunk = min(slice_seconds, remaining)
        sleep(chunk)
        remaining -= chunk
        try:
            if nudge_mtime() > baseline:
                return True  # an intent was enqueued — wake now, drain on the next tick
        except Exception:  # noqa: BLE001 — fail-soft: ignore a stat failure, keep sleeping
            pass
    # The full delay elapsed (or the shutdown flag tripped) with no nudge — a plain timeout.
    return False


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

    # The intent-queue nudge reader (0.4.0): a cheap path-local closure the interruptible sleep polls
    # so an enqueued intent wakes the daemon within one slice instead of a full interval. Built once
    # (the root is fixed for the process lifetime); fail-soft inside (a missing sentinel → 0.0).
    nudge_mtime = _make_nudge_reader(config.kanban_root)

    lock_path = config.kanban_root / LOCK_FILENAME
    lock_handle = _acquire_lock(lock_path)
    logger.info("kanban daemon started (lock %s held)", lock_path)

    # Per-project bookkeeping carried across sweeps (ingress-multiproject §3.1): one
    # ``ProjectSweepState`` per project_id (its diff baseline + circuit-breaker). N=1 → a single
    # entry, byte-identical to the old single ``PersistedState`` threading.
    state_by_project: dict[str, ProjectSweepState] = {}
    wirings: list[WiringConfig] | None = None
    last_mtime: float | None = None
    # Seed "last activity" at start so the first idle stretch backs off from now, not the epoch.
    last_activity = time.time()
    iterations = 0
    # Tick-health bookkeeping for the structured heartbeat (#1). ``consecutive_failures`` is the
    # OBSERVABILITY signal — the WORST per-project failure run after a sweep — written into
    # ``daemon.heartbeat`` so doctor can FAIL a daemon that is alive but persistently failing (the
    # proven dead-token 401-loop incident), and used to drop the DEGRADED breadcrumb on an auth
    # failure. ``backoff_failures`` is the SEPARATE per-project-aware circuit-breaker input (#5) —
    # the BEST (lowest) per-project run — so the inter-tick back-off engages only when EVERY project
    # is failing; one failing project never throttles a healthy sibling's sweep.
    consecutive_failures = 0
    backoff_failures = 0
    # Reflex fast-poll window (#auto-advance latency): a positive counter forces the next few
    # inter-tick sleeps onto the TIGHT base after a nudge wake, so a self-initiated auto-advance whose
    # move lags GitHub's eventual-consistent API is still picked up within ~base seconds instead of
    # the slow webhook fallback. Decremented per fast tick; refreshed on every nudge wake.
    fast_ticks_remaining = 0

    try:
        while not flag.requested:
            if max_iterations is not None and iterations >= max_iterations:
                break

            # Step 1: config-reload-on-change (DESIGN §5). Re-read on first pass or mtime change.
            # The registry path has no single config.yml mtime to watch, so the registry is also
            # re-read every iteration (cheap: one small JSON read) so a newly-registered / disabled
            # project is picked up without a restart. The config.yml override path keeps the
            # mtime-gated reload (its YAML is the watched file).
            current_mtime = _config_mtime(config.config_path)
            if wirings is None or current_mtime != last_mtime or current_mtime is None:
                try:
                    wirings = _load_wirings(config.config_path)
                except Exception:
                    if wirings is None:
                        # First load — no last-good config to fall back to. Let it propagate: a
                        # daemon that can't load its initial config legitimately fails to start.
                        raise
                    logger.exception(
                        "config reload failed — bad or malformed %s? Keeping last-good config",
                        config.config_path,
                    )
                else:
                    logger.info(
                        "loaded config (%d project(s)) from %s",
                        len(wirings),
                        config.config_path,
                    )
                # Update the mtime marker even on a failed reload so a config.yml override path does
                # not retry-storm on a persistently-bad file.
                last_mtime = current_mtime

            # #2 post-drain-window fix: capture the nudge baseline at SWEEP START — BEFORE the sweep
            # (hence before drain_intents and the whole post-drain window) — so an intent enqueued in
            # the post-drain window wakes THIS sleep. Fail-soft: a read error degrades to 0.
            try:
                nudge_baseline = nudge_mtime()
            except Exception:  # noqa: BLE001 — fail-soft: a stat error → no baseline (wake on any bump)
                nudge_baseline = 0

            # Step 2: ONE sweep — one idempotent tick PER ENABLED PROJECT (§3.1). Each project carries
            # its own diff baseline + circuit-breaker; a failing project never crashes the sweep or
            # trips a healthy sibling. The sweep is wholly internally fail-soft per project, so a
            # raise here is unexpected (defensive): treat it as a daemon-level failure. The rollup
            # aggregates the per-project outcomes into the idle-clock + back-off signals.
            #
            # P2 self-wake: while the fast-poll window is open (it was opened by the PREVIOUS
            # iteration's nudge wake — a self-move auto-advance, an operator CLI intent, or a webhook),
            # FORCE the sweep to re-snapshot even on an unchanged cheap_probe. cheap_probe excludes the
            # intent queue and can be stable across a restart-present move, so without this a nudged
            # tick would probe-gate the snapshot and never see the move (the probe-starves-debounce /
            # CLI-move stall). The window is bounded by ``_FAST_POLL_AFTER_NUDGE_TICKS`` so the forced
            # GraphQL snapshots are capped; a quiescent daemon (window closed) keeps the probe gate.
            force_snapshot = fast_ticks_remaining > 0
            now = time.time()
            assert wirings is not None  # the first-load raise above guarantees this
            try:
                rollup = sweep_projects(
                    wirings,
                    state_by_project,
                    kanban_root=config.kanban_root,
                    now=now,
                    force_snapshot=force_snapshot,
                )
            except Exception:  # noqa: BLE001 — a sweep-level raise must not crash the daemon
                logger.exception("sweep raised; continuing")
                # A sweep-LEVEL raise (defensive — the sweep is internally per-project fail-soft)
                # fails the whole daemon: bump BOTH the observability and the back-off runs.
                consecutive_failures += 1
                backoff_failures += 1
            else:
                # Observability run = the WORST per-project run this sweep (a single failing project
                # still surfaces a DEGRADED token). Back-off run = the BEST (lowest) per-project run
                # (#5) so the daemon backs off only when EVERY project is failing — a healthy sibling
                # keeps the tight cadence. A clean sweep (max==0) clears the DEGRADED sentinel.
                consecutive_failures = rollup.max_consecutive_failures
                backoff_failures = rollup.min_consecutive_failures
                if consecutive_failures == 0:
                    _clear_degraded(config.kanban_root)
                elif rollup.last_error is not None:
                    # A failing sweep with an auth error (401/403) drops the DEGRADED sentinel + an
                    # actionable log line so doctor/status surface a dead/over-broad token (#1).
                    _log_actionable_auth_failure(rollup.last_error, config.kanban_root)
                # Anything happened on ANY project ⇒ reset the idle clock so the cadence stays tight.
                if rollup.any_snapshot or rollup.any_action or rollup.any_reap:
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

            # Cadence (ingress-multiproject §5.2): the daemon runs ONE inter-tick sleep after the
            # sweep, so the base cadence is the TIGHTEST any enabled project needs — a ``polling``
            # project pulls the daemon to the tight 10 s, while an ALL-``webhook`` daemon polls
            # slowly (the safety-sweep fallback) and relies on the sub-second nudge for fast
            # reaction. The webhook nudge collapses the wait to one slice regardless. The historical
            # single-project default (config.yml override path / a polling registry) stays the tight
            # 10 s cadence, so the deployed daemon is unchanged.
            cadence = _effective_interval(wirings, config.interval)
            base_delay = next_sleep(last_activity, now, cadence)
            # During a run of consecutive failures the circuit breaker (#2) escalates the delay
            # geometrically (capped 300 s) so the daemon stops re-hammering GitHub through an outage.
            # The back-off keys on ``backoff_failures`` — the BEST per-project run (#5) — so it
            # engages ONLY when EVERY project is failing; a single healthy project (min==0) keeps the
            # cadence tight (its sweep is never throttled by a failing sibling). A clean sweep resets
            # the run above, snapping the delay back to the cadence base.
            delay = _failure_backoff_sleep(backoff_failures, base_delay)
            # Reflex fast-poll window: while the counter is open, re-check at the TIGHT base instead of
            # the slow webhook fallback so a self-initiated auto-advance lagging GitHub's eventual-
            # consistent API is caught within ~base seconds, not after another ~120 s fallback. Gated
            # off during a failure back-off (``backoff_failures == 0``) so an outage is never
            # re-hammered. A polling daemon already sits at the base, so this is a no-op there.
            if fast_ticks_remaining > 0 and backoff_failures == 0:
                delay = min(delay, config.interval.base)
                fast_ticks_remaining -= 1
            # Interruptible inter-tick sleep (0.4.0): sleeps the full ``delay`` UNLESS an intent is
            # enqueued (the enqueue side bumps the nudge sentinel), in which case it returns within one
            # slice so the next tick drains the intent near-instantly — no interval reduction, no API
            # cost. Also wakes on the shutdown flag. The nudge interrupts the geometric back-off sleep
            # too, so an operator intent wakes a backed-off daemon within a slice (desirable). The
            # baseline is the TICK-START value (#2) so a post-drain-window enqueue still wakes here.
            woke_on_nudge = _interruptible_sleep(
                delay, sleep=sleep, nudge_mtime=nudge_mtime, flag=flag, baseline=nudge_baseline
            )
            # A nudge wake (self-move auto-advance, operator intent, or webhook) opens/refreshes the
            # fast-poll window: the just-completed sweep may have read a board that still lagged the
            # move, so re-check fast for the next few ticks to fire the next-stage launch promptly.
            if woke_on_nudge:
                fast_ticks_remaining = _FAST_POLL_AFTER_NUDGE_TICKS
                # tug FIX 5 — observability: surface a nudge-driven early wake at INFO so an operator
                # action's fast path (UI drag / kanban move / ticket create → nudge) is VISIBLE in
                # daemon.jsonl, distinguishable from a scheduled-tick wake. Cheap (one log line); no
                # behaviour change. ``project(s)`` names the sweep breadth (the nudge is daemon-level,
                # so it is not attributable to a single project here).
                logger.info(
                    "woke early on nudge (project(s)=%d) — draining within one slice",
                    len(wirings),
                )
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
