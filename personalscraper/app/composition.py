"""The composition root: builds the process-scoped :class:`AppContext`.

Moved out of ``cli_helpers`` (a CLI-only seam): the web and the trailers engine
borrow it too. Every client of the application layer (CLI, web) enters here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.app.accounts.service import AccountService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.build_info import BUILD_INFO
from personalscraper.app.services import AppServices
from personalscraper.app.store.store import build_app_store
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("app.composition")

if TYPE_CHECKING:
    from personalscraper.api.transport._policy import RetryPolicy
    from personalscraper.app.library.service import LibraryService
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.ownership import OwnershipChecker


def build_app_context(
    config: "Config",
    settings: "Settings",
    *,
    build_torrent_client: bool = False,
    provider_retry: "RetryPolicy | None" = None,
) -> AppContext:
    """Build the process-scoped :class:`AppContext` for a CLI invocation.

    Constructed once per CLI command invocation at the boundary
    (``personalscraper run``, the launchd ``library-index`` command, the
    four ``trailers`` subcommands). The :class:`EventBus` is a fresh
    in-process instance; subscriber wiring (``RichConsoleSubscriber``,
    ``TelegramSubscriber``, …) is the caller's responsibility.

    The :class:`ProviderRegistry` is instantiated here from ``settings`` +
    ``config.providers`` so the whole process shares ONE registry (DESIGN
    §6.1 boot sequence). A misconfigured providers section raises
    :class:`RegistryConfigError` at this boundary — fail loud at boot
    rather than discover the problem mid-pipeline.

    The torrent client (DESIGN D3/D9) is built and validated **only** when
    ``build_torrent_client`` is True — i.e. for the commands that actually
    consume ``ctx.torrent_client`` (``run``, ``ingest``, ``torrents_list``).
    ``build_active_torrent_client`` performs a live network connect + login,
    so building it unconditionally would couple every read-only command
    (``library *``, ``trailers``, ``maintenance``) to a reachable torrent
    daemon and could even write a 1-hour auth lockout that blocks the next
    ingest. Read-only commands leave ``build_torrent_client`` at its default
    and get ``torrent_client=None`` with no daemon contact (review #1/#2/#5).

    The :class:`~personalscraper.acquire.context.AcquireContext` (RP5c) is
    built unconditionally for every command that goes through the single
    composition root. It owns the :class:`TrackerRegistry` (migrated from
    RP5a) and the optional ``AcquireStore`` slot (RP3). A misconfigured
    tracker raises
    :class:`~personalscraper.api.tracker._errors.TrackerConfigError` at this
    boundary — fail-loud, parity with ``RegistryConfigError``.

    Args:
        config: The typed JSON5 configuration loaded by ``cli.main``.
        settings: The Pydantic env-var settings (API keys, paths).
        build_torrent_client: When True and a torrent client is configured,
            resolve + validate it at boot (D3 fail-fast). When False
            (default), ``torrent_client`` stays None and no torrent daemon is
            contacted — used by commands that never touch the torrent client.
        provider_retry: Optional ``RetryPolicy`` override forwarded to the
            metadata providers (TMDB / TVDB). ``None`` — every CLI/pipeline
            path — keeps each provider's own policy. A caller building this
            context INSIDE a web request passes ``max_attempts=1`` so a dead
            provider cannot hold the request through the full backed-off retry
            loop (D1).

    Returns:
        A frozen :class:`AppContext` ready to drive ``Pipeline.__init__``
        or the orchestrator entrypoints for the launchd / trailers
        commands.
    """
    # Lazy imports: ProviderRegistry pulls the full provider tree, so we
    # defer it to keep CLI import time minimal for commands that never
    # build an AppContext (``--help``, ``init-config``).
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.api.transport._policy import CircuitPolicy

    event_bus = EventBus()
    cb_policy = CircuitPolicy(
        failure_threshold=config.thresholds.circuit_breaker_threshold,
        cooldown_seconds=config.thresholds.circuit_breaker_cooldown,
    )
    provider_registry = ProviderRegistry(
        settings=settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
        providers_config=config.providers,
        retry=provider_retry,
    )

    # D3/D9: Boot-wire the torrent client when configured; fail-fast if
    # incapable. Gated on ``build_torrent_client`` so only commands that
    # consume the client (run/ingest/torrents_list) pay the connect+login —
    # read-only commands stay decoupled from the daemon (review #1/#2/#5).
    # No client configured (torrent.active="") → None, no error.
    torrent_client = None
    if build_torrent_client and config.torrent.active:
        from personalscraper.api.metadata.registry import (  # noqa: PLC0415
            ConfigIssue,
            RegistryProviderName,
        )
        from personalscraper.api.metadata.registry._errors import (  # noqa: PLC0415
            RegistryConfigError,
        )
        from personalscraper.api.torrent._contracts import (  # noqa: PLC0415
            TorrentAdder,
        )
        from personalscraper.api.torrent._factory import (  # noqa: PLC0415
            build_active_torrent_client,
        )

        raw_client = build_active_torrent_client(config.torrent)
        if not isinstance(raw_client, TorrentAdder):
            raise RegistryConfigError(
                [
                    ConfigIssue(
                        code="protocol_mismatch",
                        section="torrent",
                        provider=RegistryProviderName(config.torrent.active),
                        message=(
                            f"Active torrent client {config.torrent.active!r} "
                            "does not compose TorrentAdder. Verify the client "
                            "implementation or configuration."
                        ),
                    )
                ]
            )
        torrent_client = raw_client

    # RP5c: build the acquisition lobe handle at boot (lazy import mirrors the
    # provider_registry pattern — keeps --help / init-config network-light).
    # Delegates tracker registry construction to build_tracker_registry (RP5a
    # unchanged). TrackerConfigError surfaces here on any misconfig: fail-loud
    # at the same boundary as RegistryConfigError (metadata/torrent). The
    # torrent client is borrowed (shared with ingest); acquire.close() does
    # NOT own its lifecycle.
    from personalscraper.acquire._factory import build_acquire_context  # noqa: PLC0415

    # RP6: build the ownership checker at the TRUE composition root. This is the
    # only frame that may import indexer/ AND see config.indexer.db_path, so it
    # bridges the acquire⇏indexer boundary: it constructs the concrete
    # IndexerOwnershipChecker and injects it as the core OwnershipChecker port,
    # keeping acquire/ free of any indexer import (the layering guard stays
    # green). The checker is INERT here — it opens NO connection and takes NO
    # lock at boot; its lazy, read-only, lock-free library.db connection opens on
    # the first owns() call, so the shared composition root never serializes
    # unrelated commands. When library.db is unconfigured or absent, the acquire
    # factory falls back to NullOwnershipChecker (always-False, fail-open).
    ownership = build_ownership_checker(config)

    acquire = build_acquire_context(
        config,
        settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
        torrent_client=torrent_client,
        ownership=ownership,
    )

    # DESIGN §3.4: warn if the resolved config dir is inside an ancestor git
    # working tree (the pre-relocation crash-at-boot vector).  ONE call site
    # at the TRUE composition root covers every CLI command AND the web daemon
    # (commands/web.py boot path → build_app_context → here).  Fail-soft:
    # warnings are logged but never block boot.
    from personalscraper.conf.loader import resolve_config_path
    from personalscraper.verify.config_home import check_config_home

    config_dir = resolve_config_path()
    for warning in check_config_home(config_dir, report_missing=False):
        log.warning(warning)

    return AppContext(
        config=config,
        settings=settings,
        event_bus=event_bus,
        provider_registry=provider_registry,
        torrent_client=torrent_client,
        acquire=acquire,
    )


def build_app_services(config: "Config", settings: "Settings") -> AppServices:
    """Build the process's :class:`AppServices`.

    Inert: it opens no store, no connection and no publisher — ``app.db`` opens on
    the first session or account call, so building it at web boot costs nothing.

    Args:
        config: The typed JSON5 configuration.
        settings: The Pydantic env-var settings.

    Returns:
        The application services, with a fresh in-process :class:`EventBus`, the
        build read at boot, and the account services over the environment's ``app.db``.
    """
    event_bus = EventBus()
    app_store = build_app_store(config)
    sessions = SessionService(lambda: app_store.accounts, idle_days=config.web.session_idle_days)
    accounts = AccountService(lambda: app_store.accounts, sessions, event_bus)
    return AppServices(
        event_bus=event_bus,
        build_info=BUILD_INFO,
        library=_build_library_service(config, settings, event_bus),
        app_store=app_store,
        sessions=sessions,
        accounts=accounts,
    )


def _build_library_service(config: "Config", settings: "Settings", event_bus: EventBus) -> "LibraryService":
    """Build the library's read service over the index, the aired catalogue and the providers.

    Inert: the catalogue store and the ownership checker open on first use, and the
    provider clients connect on their first call (TVDB logs in then). A provider whose
    API key is not set gets no client: its sheets answer ``provider.unavailable``. The
    clients make ONE attempt per call, so a dead provider cannot hold a web request
    through a backed-off retry loop (v0's sheet rule, D1).

    Args:
        config: The typed configuration; ``indexer.db_path`` and ``acquire.db_path`` are
            resolved by the loader.
        settings: The env-var settings (the provider API keys).
        event_bus: The process's bus, for the clients' transport events.

    Returns:
        The service.
    """
    # Lazy imports: the provider clients and the indexer pull heavy trees; building
    # AppServices for a command that never reads the library stays import-light.
    from personalscraper.acquire.catalogue import CatalogueStore, ProviderClients  # noqa: PLC0415
    from personalscraper.api.metadata.tmdb import TMDBClient  # noqa: PLC0415
    from personalscraper.api.metadata.tvdb import TVDBClient  # noqa: PLC0415
    from personalscraper.api.transport._http import HttpTransport  # noqa: PLC0415
    from personalscraper.api.transport._policy import RetryPolicy  # noqa: PLC0415
    from personalscraper.app.library.service import LibraryService  # noqa: PLC0415
    from personalscraper.indexer.ownership import IndexerOwnershipChecker  # noqa: PLC0415

    index_db = config.indexer.db_path
    acquire_db = config.acquire.db_path
    assert index_db is not None and acquire_db is not None  # noqa: S101 — resolved by the config loader
    once = RetryPolicy(max_attempts=1)
    tmdb = (
        TMDBClient(
            HttpTransport(TMDBClient.policy(settings.tmdb_api_key, retry=once), event_bus=event_bus),
            language="fr-FR",
        )
        if settings.tmdb_api_key
        else None
    )
    tvdb = (
        TVDBClient(settings.tvdb_api_key, language="fr-FR", retry=once, event_bus=event_bus)
        if settings.tvdb_api_key
        else None
    )
    return LibraryService(
        index_db=index_db,
        data_dir=config.paths.data_dir,
        catalogue=CatalogueStore(acquire_db),
        ownership=IndexerOwnershipChecker(index_db),
        providers=ProviderClients(tvdb=tvdb, tmdb=tmdb),
    )


def build_ownership_checker(config: "Config") -> "OwnershipChecker":
    """Build the RP6 ownership checker from the configured ``library.db`` path.

    Returns an :class:`~personalscraper.indexer.ownership.IndexerOwnershipChecker`
    when ``config.indexer.db_path`` is configured AND the file exists on disk;
    otherwise a :class:`~personalscraper.core.ownership.NullOwnershipChecker`
    (always-``False``, fail-open). Returning ``NullOwnershipChecker`` for a
    missing/unconfigured DB keeps first-run / dry-run / no-library commands safe
    (a wanted item is never silently skipped because ownership can't be
    verified).

    This helper lives at the TRUE composition root (``app.composition``), the only
    layer permitted to import ``indexer/`` while also seeing the config; it
    bridges the acquire⇏indexer boundary by handing back the neutral
    ``OwnershipChecker`` core port. The returned ``IndexerOwnershipChecker`` is
    INERT: it opens NO connection and takes NO lock here. Its lazy, read-only,
    lock-free connection opens on the first ``owns()`` call, so building the
    shared :class:`AppContext` never takes a lifetime lock on ``library.db`` and
    never serializes unrelated commands (the acquire.db lifetime-lock regression
    lesson).

    Args:
        config: The typed JSON5 configuration; ``config.indexer.db_path`` holds
            the resolved ``library.db`` path (or ``None`` if unconfigured).

    Returns:
        An ``OwnershipChecker`` port implementation — concrete indexer-backed
        when the library exists, ``NullOwnershipChecker`` otherwise.
    """
    from personalscraper.core.ownership import NullOwnershipChecker  # noqa: PLC0415

    db_path = config.indexer.db_path
    if db_path is None or not db_path.exists():
        return NullOwnershipChecker()
    # Lazy import: indexer/ pulls the SQLite machinery; defer it so commands that
    # never build an AppContext stay import-light. app/composition is NOT subject to
    # the acquire/ layering guard, so this indexer import is legal here.
    from personalscraper.indexer.ownership import IndexerOwnershipChecker  # noqa: PLC0415

    return IndexerOwnershipChecker(db_path)
