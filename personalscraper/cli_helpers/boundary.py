"""The ``boundary()`` CLI decorator — one owner for the per-command scaffold.

Every pipeline / library Typer command repeats the same ~30-line preamble:
acquire ``pipeline.lock``, open a ``cli_step_journal`` run-journal row, bootstrap
the staging tree, build the process-scoped service bundle (``AppContext`` — or a
narrower slice for read-only commands), run the body, then unwind in the right
order. :func:`boundary` collapses that scaffold into ONE decorator so the shape
is declared, not re-hand-wired per command (DESIGN §5 T7 / COMMANDS-CLI-01).

It **generalises** — and reuses — the existing
:func:`personalscraper.cli_helpers.per_step_boundary`: the ``needs="app"`` tier
enters ``per_step_boundary`` verbatim, so correlation-id binding, provider-registry
/ acquire teardown, and the fail-soft Redis publisher stay owned by that one
context manager (it is left UNTOUCHED — its direct callers migrate in P3.3/P3.4).

needs= tiers
------------

The ``needs=`` parameter selects how much of the service graph a command pays
for. Read-only commands over-built a full ``AppContext`` (COMMANDS-CLI-06); the
tiers let them stop:

============  ===================================================  ==========================================
``needs=``    bundle it yields (``CommandContext`` fields set)      maps to (existing command shape)
============  ===================================================  ==========================================
``"app"``     full ``AppContext`` via ``per_step_boundary``         pipeline steps (``ingest``, ``sort``,
              (``app_context`` + its ``event_bus``); optional        ``scrape``, ``dispatch``, …), ``run``,
              ``build_torrent_client`` / ``stream_events``          ``torrents-list`` — anything that mutates
              passthrough                                            the FS or consumes the torrent client
``"db-read"`` config + a **read-only** ``sqlite3`` connection to    read-only library queries
              ``indexer.db_path`` (``indexer_conn``) + a fresh       (``library-status`` / ``library-search`` /
              unobserved ``EventBus`` — NO torrent client, NO        ``library-show``) that today build an
              writer, NO provider registry                           ``AppContext`` only for its bus
``"config"``  config + settings + a fresh ``EventBus`` only —       commands that read config values and touch
              no DB, no ``AppContext``                               no DB and no service (thin config readers)
============  ===================================================  ==========================================

Lock / journal are for FS-mutating pipeline steps, so they engage **only** on the
``"app"`` tier: read-only tiers never take ``pipeline.lock`` and never write a
``pipeline_run`` row, regardless of the ``lock=`` / ``journal=`` flags (the flags
still let an ``"app"``-tier read-only listing like ``torrents-list`` opt out —
``lock=False, journal=False``). ``staging=`` is honoured verbatim on every tier.

Lock-path injection (CROSS-CUTTING-03)
--------------------------------------

The decorator resolves ``config.paths.data_dir / "pipeline.lock"`` ONCE and passes
it into :func:`~personalscraper.lock.acquire_pipeline_lock` /
:func:`~personalscraper.lock.release_lock`, so
:func:`~personalscraper.lock._default_lock_file`'s ``load_config`` re-load fallback
is never reached on the primary path (that fallback is kept for direct callers).

The wrapped command receives the bundle as a ``bundle`` keyword argument, which is
hidden from the Typer/click-visible signature (via ``__signature__``) so it never
becomes a CLI option.

Telemetry (COMMANDS-CLI-05)
---------------------------

Every ``boundary()``-wrapped command records the same structured telemetry as the
root ``@cli_telemetry`` hook — ``cli.invoke.<cmd>`` on entry, ``cli.complete.<cmd>``
on clean return, ``cli.failed.<cmd>`` on an unhandled exception (``typer.Exit`` is
NOT a failure) — via :func:`~personalscraper.cli_telemetry.run_with_telemetry`. The
command name is the boundary's own ``command=`` resolution (``command=`` argument,
else the wrapped function's ``__name__``). This gives the ~30 uninstrumented
sub-app commands telemetry for free once they migrate to the boundary. The boundary
records **fail-soft**: a telemetry/logging error never breaks the command.

NO-DOUBLE-RECORD guard: a command that is *both* root-instrumented
(``command_with_telemetry`` → ``cli_telemetry``) and boundary-wrapped would
otherwise record twice. ``command_with_telemetry`` must be the OUTERMOST decorator
(it calls ``app.command``), so at runtime the outer ``cli_telemetry`` layer records
first and sets the process-scoped ``ContextVar`` sentinel in ``cli_telemetry``; the
inner boundary layer observes it via
:func:`~personalscraper.cli_telemetry.telemetry_recording_active` (inside
``run_with_telemetry``) and skips its own recording. The sentinel is a runtime
marker — not a decoration-time attribute — precisely because the inner boundary
decorator cannot see the outer ``cli_telemetry`` layer that is applied after it.

Maintainer note (name shadowing): ``cli_helpers.__init__`` re-exports this
module's ``boundary`` function, so the package attribute
``personalscraper.cli_helpers.boundary`` resolves to the *function*, not this
module (it shadows the submodule). ``from personalscraper.cli_helpers import
boundary`` and ``from personalscraper.cli_helpers.boundary import X`` both work,
but string-based ``monkeypatch.setattr("...cli_helpers.boundary.<name>", ...)``
does NOT — grab the module object via ``sys.modules`` /
``importlib.import_module`` and patch that.
"""

from __future__ import annotations

import functools
import inspect
import sqlite3
from contextlib import ExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import typer

from personalscraper.cli_helpers import (
    _bootstrap_staging,
    per_step_boundary,
)
from personalscraper.cli_state import state
from personalscraper.cli_telemetry import run_with_telemetry
from personalscraper.config import get_settings
from personalscraper.core.event_bus import EventBus
from personalscraper.lock import (
    acquire_pipeline_lock,
    release_lock,
    scrape_locks_dir_for,
)
from personalscraper.run_journal import cli_step_journal

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.app_context import AppContext

#: The recognised ``needs=`` tiers (validated at decoration time — fail fast).
_TIERS = frozenset({"app", "db-read", "config"})

#: Console message shown (parity with the pre-boundary pipeline commands) when a
#: mutating command loses the ``pipeline.lock`` race, right before ``Exit(1)``.
_LOCK_BUSY_MESSAGE = "[red]Another instance is running. Exiting.[/red]"


@dataclass(frozen=True)
class CommandContext:
    """The needs-tier service bundle handed to a ``boundary()``-wrapped command.

    A single value object so a command declares ``bundle: CommandContext`` and
    reads exactly the slots its tier populated — instead of the boundary
    injecting a variadic set of keyword arguments. Slots absent from a tier stay
    ``None`` (see the tier table in the module docstring).

    Attributes:
        config: The typed JSON5 configuration resolved by ``cli.main``.
        settings: The Pydantic env-var settings (API keys, paths).
        needs: The tier that built this bundle (``"app"`` / ``"db-read"`` /
            ``"config"``).
        event_bus: The :class:`EventBus` to emit on — the ``AppContext`` bus on
            the ``"app"`` tier, else a fresh unobserved bus.
        app_context: The full :class:`AppContext` — set only on the ``"app"``
            tier, ``None`` otherwise.
        indexer_conn: A **read-only** ``sqlite3`` connection to
            ``indexer.db_path`` — set only on the ``"db-read"`` tier when the DB
            file exists, ``None`` otherwise.
        run_uid: The ``pipeline_run`` journal row id when journaling engaged, else
            ``None``.
    """

    config: Config
    settings: Settings
    needs: str
    event_bus: EventBus
    app_context: AppContext | None = None
    indexer_conn: sqlite3.Connection | None = None
    run_uid: str | None = None


def _open_readonly_indexer_conn(config: Config, stack: ExitStack) -> sqlite3.Connection | None:
    """Open a read-only ``sqlite3`` connection to the indexer DB (``db-read`` tier).

    Uses the SQLite ``file:...?mode=ro`` URI so the connection is genuinely
    read-only — any write raises :class:`sqlite3.OperationalError`, and no
    write-ahead log / migration is ever created. The connection's ``close`` is
    registered on *stack* so it is closed when the boundary unwinds.

    Args:
        config: The active configuration (``config.indexer.db_path`` locates the
            library DB).
        stack: The boundary's :class:`~contextlib.ExitStack`; the connection's
            ``close`` is registered on it.

    Returns:
        An open read-only connection, or ``None`` when the DB path is
        unconfigured or the file does not yet exist (fresh clone / no library).
    """
    db_path = config.indexer.db_path
    if db_path is None or not db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    stack.callback(conn.close)
    return conn


def _build_bundle(
    needs: str,
    config: Config,
    settings: Settings,
    *,
    build_torrent_client: bool,
    stream_events: bool,
    run_uid: str | None,
    stack: ExitStack,
) -> CommandContext:
    """Build the :class:`CommandContext` for *needs*, registering teardown on *stack*.

    The ``"app"`` tier enters :func:`per_step_boundary` (unchanged) so the
    ``AppContext`` lifecycle — correlation-id binding, provider-registry / acquire
    teardown, optional Redis publisher — stays owned by that one context manager.
    The read-only tiers build no ``AppContext`` and no torrent client.

    Args:
        needs: The validated tier name.
        config: The active configuration.
        settings: The env-var settings.
        build_torrent_client: Forwarded to ``per_step_boundary`` on the ``"app"``
            tier (D3 fail-fast connect+login). Ignored on read-only tiers.
        stream_events: Forwarded to ``per_step_boundary`` on the ``"app"`` tier
            (wire the fail-soft Redis publisher for the universal run journal).
            Ignored on read-only tiers.
        run_uid: The journal row id to stamp onto the bundle (or ``None``).
        stack: The boundary's :class:`~contextlib.ExitStack` for tier teardown.

    Returns:
        The populated :class:`CommandContext`.
    """
    if needs == "app":
        app_context = stack.enter_context(
            per_step_boundary(
                config,
                settings,
                build_torrent_client=build_torrent_client,
                stream_events=stream_events,
            )
        )
        return CommandContext(
            config=config,
            settings=settings,
            needs=needs,
            event_bus=app_context.event_bus,
            app_context=app_context,
            run_uid=run_uid,
        )
    if needs == "db-read":
        return CommandContext(
            config=config,
            settings=settings,
            needs=needs,
            event_bus=EventBus(),
            indexer_conn=_open_readonly_indexer_conn(config, stack),
            run_uid=run_uid,
        )
    # "config" tier — no DB, no AppContext, just a fresh unobserved bus.
    return CommandContext(
        config=config,
        settings=settings,
        needs=needs,
        event_bus=EventBus(),
        run_uid=run_uid,
    )


def _visible_signature(func: Callable[..., Any]) -> inspect.Signature:
    """Return *func*'s signature with the injected ``bundle`` parameter removed.

    Typer/click introspect the callback signature to build CLI options; the
    ``bundle`` parameter is supplied by the boundary, not the command line, so it
    must not appear as an option. The returned signature is stamped onto the
    wrapper's ``__signature__`` (which :func:`inspect.signature` honours ahead of
    the ``functools.wraps`` ``__wrapped__`` chain).

    Args:
        func: The command function being decorated. Must declare a ``bundle``
            parameter.

    Returns:
        The signature of *func* without its ``bundle`` parameter.

    Raises:
        TypeError: If *func* declares no ``bundle`` parameter.
    """
    params = list(inspect.signature(func).parameters.values())
    if not any(p.name == "bundle" for p in params):
        raise TypeError(
            f"boundary()-decorated command {getattr(func, '__name__', func)!r} must declare a "
            "'bundle' parameter (it receives the CommandContext); declare it keyword-only or last."
        )
    return inspect.Signature([p for p in params if p.name != "bundle"])


def boundary(
    *,
    needs: str = "app",
    lock: bool = True,
    journal: bool = True,
    staging: bool = True,
    build_torrent_client: bool = False,
    stream_events: bool = False,
    command: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a Typer command with the shared per-command boundary scaffold.

    Owns, in one place, the preamble every pipeline / library command repeats:
    acquire ``pipeline.lock`` (mutating commands only), open a ``cli_step_journal``
    run-journal row, bootstrap the staging tree, build the ``needs=`` service
    bundle, run the body, and unwind in the correct order in a ``finally``. See
    the module docstring for the tier table and the lock/journal engagement rule.

    The wrapped command must declare a ``bundle`` parameter (ideally keyword-only
    or last); it receives the :class:`CommandContext` there. ``bundle`` is hidden
    from the Typer-visible signature so it never becomes a CLI option.

    Args:
        needs: Service tier — ``"app"`` (full ``AppContext``, default),
            ``"db-read"`` (config + read-only indexer connection), or ``"config"``
            (config only). Validated at decoration time.
        lock: Acquire ``pipeline.lock`` for the command's lifetime. Honoured only
            on the ``"app"`` tier (read-only tiers never lock); an ``"app"``-tier
            read-only listing opts out with ``lock=False``. On a lost race the
            command prints the busy message and raises ``typer.Exit(1)``.
        journal: Open a ``cli_step_journal`` ``pipeline_run`` row. Honoured only on
            the ``"app"`` tier (read-only tiers never journal).
        staging: Call ``ensure_staging_tree`` before the body (honoured on every
            tier).
        build_torrent_client: Passthrough to ``per_step_boundary`` — build +
            validate the torrent client at boot (``"app"`` tier only).
        stream_events: Passthrough to ``per_step_boundary`` — wire the fail-soft
            Redis event publisher for the universal run journal (``"app"`` tier,
            pipeline steps only).
        command: Name recorded in the journal row. Defaults to the wrapped
            function's ``__name__`` (matches the pipeline step names).

    Returns:
        A decorator that wraps a Typer command with the boundary scaffold.

    Raises:
        ValueError: If *needs* is not one of the recognised tiers.
    """
    if needs not in _TIERS:
        raise ValueError(f"boundary(needs={needs!r}) is invalid; expected one of {sorted(_TIERS)}.")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        visible = _visible_signature(func)
        command_name = command if command is not None else getattr(func, "__name__", "command")

        def _run(*args: Any, **kwargs: Any) -> Any:
            # ``ctx`` is always the Typer command's first parameter (click passes
            # it); typed Any because it arrives positionally or by keyword.
            ctx: Any = args[0] if args else kwargs.get("ctx")
            config = ctx.obj.config
            settings = get_settings()
            dry_run = bool(kwargs.get("dry_run", False))

            data_dir = config.paths.data_dir
            lock_file = data_dir / "pipeline.lock"
            # Lock/journal are pipeline-step concerns → "app" tier only. Read-only
            # tiers never take pipeline.lock nor write a pipeline_run row.
            do_lock = lock and needs == "app"
            do_journal = journal and needs == "app"

            if do_lock and not acquire_pipeline_lock(lock_file, scrape_locks_dir_for(data_dir)):
                state["console"].print(_LOCK_BUSY_MESSAGE)
                raise typer.Exit(1)
            try:
                with ExitStack() as stack:
                    run_uid: str | None = (
                        stack.enter_context(cli_step_journal(config, command=command_name, dry_run=dry_run))
                        if do_journal
                        else None
                    )
                    if staging:
                        _bootstrap_staging(ctx)
                    bundle = _build_bundle(
                        needs,
                        config,
                        settings,
                        build_torrent_client=build_torrent_client,
                        stream_events=stream_events,
                        run_uid=run_uid,
                        stack=stack,
                    )
                    return func(*args, bundle=bundle, **kwargs)
            finally:
                # Injected lock path (CROSS-CUTTING-03): release with the same
                # resolved path, so lock.py never re-loads config on this path.
                if do_lock:
                    release_lock(lock_file=lock_file)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Record the same invoke/complete/failed telemetry as the root
            # ``@cli_telemetry`` hook, fail-soft. ``run_with_telemetry`` owns the
            # no-double-record sentinel: when a root ``cli_telemetry`` layer is
            # already recording (this command is also ``command_with_telemetry``-
            # wrapped), it skips and runs ``_run`` directly (see module docstring).
            return run_with_telemetry(command_name, _run, args, kwargs, fail_soft=True)

        # Hide the injected ``bundle`` parameter from Typer/click introspection.
        wrapper.__signature__ = visible  # type: ignore[attr-defined]
        return wrapper

    return decorator


__all__ = ["CommandContext", "boundary"]
