"""The composition root: builds the process-scoped :class:`AppContext`.

Moved out of ``cli_helpers`` (a CLI-only seam): the web and the trailers engine
borrow it too. Every client of the application layer (CLI, web) enters here.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Final, cast

from personalscraper.api.transport import RetryPolicy
from personalscraper.app.accounts.credentials import CredentialService
from personalscraper.app.accounts.notices import NoticeService
from personalscraper.app.accounts.own_sessions import OwnSessionService
from personalscraper.app.accounts.plex_sign_in import PlexSignInService
from personalscraper.app.accounts.roles import RoleService
from personalscraper.app.accounts.roster import RosterService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.accounts.sign_in_notice import SignInNotifier
from personalscraper.app.build_info import BUILD_INFO
from personalscraper.app.idempotency.service import IdempotencyService, fingerprint_key_path
from personalscraper.app.services import AppServices
from personalscraper.app.store.store import build_app_store
from personalscraper.app.supervisor.service import RunService
from personalscraper.conf.environment import StoreName, store_path
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger
from personalscraper.push.dispatch import UnconfiguredPush

log = get_logger("app.composition")

#: The retry a provider call made inside a request gets: one attempt, so a dead provider
#: cannot hold the request through a backed-off retry loop (D1).
ONE_ATTEMPT: Final[RetryPolicy] = RetryPolicy(max_attempts=1)

if TYPE_CHECKING:
    from personalscraper.acquire.catalogue import ProviderLookup, TvCatalogueClient
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.api.plex import PlexClient
    from personalscraper.api.transport import CircuitPolicy
    from personalscraper.app.library.completeness import CatalogueView
    from personalscraper.app.library.deleting import LibraryDeletion
    from personalscraper.app.library.reads import LibraryReads
    from personalscraper.app.library.rescrape import LibraryRescrape
    from personalscraper.app.library.sheets import MediaSheets
    from personalscraper.app.store.store import AppStore
    from personalscraper.conf.models.config import Config
    from personalscraper.conf.models.providers import ProvidersConfig
    from personalscraper.config import Settings
    from personalscraper.core.ownership import OwnershipChecker


def build_app_context(
    config: Config,
    settings: Settings,
    *,
    build_torrent_client: bool = False,
    provider_retry: RetryPolicy | None = None,
) -> AppContext:
    """Build the process-scoped :class:`AppContext`, once per process.

    Constructed once at the boundary of a CLI command (``personalscraper run``,
    the launchd ``library-index`` command, the four ``trailers`` subcommands)
    and once for the lifetime of the web process (``web serve``, with
    ``provider_retry=ONE_ATTEMPT``), which hands the context's bus and registry
    over to v1's services. The :class:`EventBus` is built here, the process's
    only one; subscriber wiring (``RichConsoleSubscriber``,
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
    event_bus = EventBus()
    cb_policy = _circuit_policy(config)
    provider_registry = build_provider_registry(config, settings, event_bus=event_bus, retry=provider_retry)

    # D3/D9: Boot-wire the torrent client when configured; fail-fast if
    # incapable. Gated on ``build_torrent_client`` so only commands that
    # consume the client (run/ingest/torrents_list) pay the connect+login —
    # read-only commands stay decoupled from the daemon (review #1/#2/#5).
    # No client configured (torrent.active="") → None, no error.
    torrent_client = None
    if build_torrent_client and config.torrent.active:
        from personalscraper.api.metadata.registry import (  # noqa: PLC0415
            ConfigIssue,
            RegistryConfigError,
            RegistryProviderName,
        )
        from personalscraper.api.torrent import (  # noqa: PLC0415
            TorrentAdder,
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
    from personalscraper.acquire import build_acquire_context  # noqa: PLC0415

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


def _circuit_policy(config: Config) -> CircuitPolicy:
    """The circuit breaker policy of the provider transports, from ``config.thresholds``.

    A value: each caller builds its own, all equal (the acquire context's and the
    registry's); the circuit state itself lives in each transport.

    Args:
        config: The typed configuration.

    Returns:
        The policy.
    """
    from personalscraper.api.transport import CircuitPolicy  # noqa: PLC0415

    return CircuitPolicy(
        failure_threshold=config.thresholds.circuit_breaker_threshold,
        cooldown_seconds=config.thresholds.circuit_breaker_cooldown,
    )


def build_provider_registry(
    config: Config,
    settings: Settings,
    *,
    event_bus: EventBus,
    retry: RetryPolicy | None = None,
    providers_config: ProvidersConfig | None = None,
) -> ProviderRegistry:
    """Build the process's metadata provider registry, in the configured language.

    Args:
        config: The typed configuration: ``providers``, the circuit thresholds, and
            ``scraper.language``, the language the TMDB and TVDB clients ask in.
        settings: The env-var settings (the provider API keys).
        event_bus: The process's bus, for the clients' transport events.
        retry: Optional ``RetryPolicy`` override for TMDB and TVDB; ``None`` keeps each
            provider's own, :data:`ONE_ATTEMPT` serves a request.
        providers_config: The providers section to build from instead of
            ``config.providers``.

    Returns:
        The registry.

    Raises:
        RegistryConfigError: The providers section is inconsistent or a provider's
            credential is missing.
    """
    # Lazy import: ProviderRegistry pulls the full provider tree, so we defer it to keep
    # CLI import time minimal for commands that never build one (``--help``, ``init-config``).
    from personalscraper.api.metadata.registry import ProviderRegistry  # noqa: PLC0415

    return ProviderRegistry(
        settings=settings,
        event_bus=event_bus,
        cb_policy=_circuit_policy(config),
        providers_config=config.providers if providers_config is None else providers_config,
        language=config.scraper.language,
        retry=retry,
    )


#: The providers the library reads, by the ``Settings`` field holding each one's key.
_LIBRARY_PROVIDER_KEYS: Final[dict[str, str]] = {"tmdb": "tmdb_api_key", "tvdb": "tvdb_api_key"}


def _build_library_registry(config: Config, settings: Settings, *, event_bus: EventBus) -> ProviderRegistry:
    """Build v1's registry, with :data:`ONE_ATTEMPT`, over the providers the library reads.

    The providers section is pruned to TMDB and TVDB, and to those of the two whose key
    is set, so one missing key (or another provider's) does not take the other client
    down. A key missing beside a set one is logged once (``app.providers.unavailable``);
    with neither key nothing is pruned, and the registry refuses to build as before.

    Args:
        config: The typed configuration.
        settings: The env-var settings (the provider API keys).
        event_bus: The process's bus.

    Returns:
        The registry.

    Raises:
        RegistryConfigError: The pruned providers section is inconsistent, or neither
            key is set.
    """
    from personalscraper.conf.models.providers import ProvidersConfig  # noqa: PLC0415

    keyed = {name for name, field in _LIBRARY_PROVIDER_KEYS.items() if getattr(settings, field)}
    kept = keyed or set(_LIBRARY_PROVIDER_KEYS)
    missing = sorted(set(_LIBRARY_PROVIDER_KEYS) - kept)
    if missing:
        log.error("app.providers.unavailable", issues=["missing_credentials"], providers=missing)
    pruned = ProvidersConfig(
        **{
            section: {name: priority for name, priority in entries.items() if name in kept}
            for section, entries in config.providers.model_dump().items()
        }
    )
    return build_provider_registry(config, settings, event_bus=event_bus, retry=ONE_ATTEMPT, providers_config=pruned)


class LazyProviders:
    """The process's registry for v1, built with :data:`ONE_ATTEMPT` on first use.

    The library reads its TMDB and TVDB clients through it, whether the registry is the
    services' own or one the process handed over (then the builder returns it). A build
    that raises — a :class:`RegistryConfigError` (no key at all, say) or anything else —
    is logged once (``app.providers.unavailable``) and every later call gets no client, so
    its sheets answer ``provider.unavailable`` and the process still serves the rest. Once
    closed, it builds nothing and gives no client. Thread-safe: the web serves requests
    from a pool.
    """

    def __init__(self, build: Callable[[], ProviderRegistry]) -> None:
        """Hold the builder; nothing is built yet.

        Args:
            build: Builds the registry, called at most once.
        """
        self._build = build
        self._registry: ProviderRegistry | None = None
        self._unavailable = False
        self._closed = False
        self._lock = threading.Lock()

    def get(self, provider: str) -> TvCatalogueClient | None:
        """Return the client of ``provider``, building the registry on the first call.

        Args:
            provider: ``"tvdb"`` or ``"tmdb"``.

        Returns:
            The registry's client, or ``None`` when the registry cannot be built, does
            not hold ``provider``, or this lookup is closed.
        """
        from personalscraper.api.metadata.registry import UnknownProviderError  # noqa: PLC0415

        registry = self._resolve()
        if registry is None:
            return None
        try:
            return cast("TvCatalogueClient", registry.get(provider))
        except UnknownProviderError:
            return None

    def close(self) -> None:
        """Close the registry if it was built, once; later calls get no client."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._registry is not None:
                self._registry.close()

    def _resolve(self) -> ProviderRegistry | None:
        """Return the registry, building it once; ``None`` once it failed to build or is closed.

        Returns:
            The registry, or ``None``.
        """
        from personalscraper.api.metadata.registry import RegistryConfigError  # noqa: PLC0415

        with self._lock:
            if self._closed:
                return None
            if self._registry is None and not self._unavailable:
                try:
                    self._registry = self._build()
                except RegistryConfigError as exc:
                    self._unavailable = True
                    log.error("app.providers.unavailable", issues=sorted({issue.code for issue in exc.issues}))
                except Exception as exc:  # noqa: BLE001 — any build failure leaves the sheets unavailable, not a 500
                    self._unavailable = True
                    log.error("app.providers.unavailable", error=type(exc).__name__)
            return self._registry


def build_app_services(
    config: Config,
    settings: Settings,
    *,
    event_bus: EventBus,
    providers: ProviderRegistry | None = None,
) -> AppServices:
    """Build the process's :class:`AppServices`.

    Inert: it opens no store, no connection and no publisher — ``app.db`` opens on
    the first session or account call, so building it at web boot costs nothing.
    The process's bus is handed in, and a process that already holds a registry (the
    v0 web process) hands it over too, so it holds one of each.

    Args:
        config: The typed JSON5 configuration.
        settings: The Pydantic env-var settings.
        event_bus: The process's bus.
        providers: The process's registry, built with :data:`ONE_ATTEMPT` and left to
            its owner to close; ``None`` builds one on the first provider call
            (:class:`LazyProviders`), over TMDB and TVDB as their keys allow, which these
            services own and close.

    Returns:
        The application services, on the process's :class:`EventBus`, with the build
        read at boot and the account services over the environment's ``app.db``.
    """
    from personalscraper.api.plex import PlexClient  # noqa: PLC0415

    owned: LazyProviders | None = None
    if providers is None:
        owned = LazyProviders(lambda: _build_library_registry(config, settings, event_bus=event_bus))
        lookup = owned
    else:
        given = providers
        lookup = LazyProviders(lambda: given)
    plex = PlexClient(settings.plex_url, settings.plex_token) if settings.plex_token else None
    app_store = build_app_store(config)
    runs = RunService(store=app_store, data_dir=config.paths.data_dir)
    view, library, sheets, rescrape, deletion = _build_library_services(config, lookup, plex, runs)
    sessions = SessionService(app_store, idle_days=config.web.session_idle_days)
    accounts = RosterService(app_store, event_bus)
    roles = RoleService(app_store, event_bus)
    credentials = CredentialService(app_store, sessions)
    # No FCM sender is configured yet: the in-app notice is written, the push is logged unsent.
    sign_in_notifier = SignInNotifier(app_store, UnconfiguredPush())
    sign_in_notifier.subscribe(event_bus)
    return AppServices(
        event_bus=event_bus,
        build_info=BUILD_INFO,
        library=library,
        sheets=sheets,
        rescrape=rescrape,
        deletion=deletion,
        catalogue_view=view,
        app_store=app_store,
        sessions=sessions,
        accounts=accounts,
        roles=roles,
        credentials=credentials,
        plex_sign_in=_build_plex_sign_in(config, settings, app_store, credentials, event_bus, plex),
        own_sessions=OwnSessionService(app_store, sessions),
        notices=NoticeService(app_store),
        runs=runs,
        idempotency=IdempotencyService(
            app_store, key_path=fingerprint_key_path(store_path(config.paths.data_dir, StoreName.APP))
        ),
        owned_providers=owned,
        sign_in_notifier=sign_in_notifier,
    )


def _build_plex_sign_in(
    config: Config,
    settings: Settings,
    app_store: AppStore,
    credentials: CredentialService,
    event_bus: EventBus,
    server: PlexClient | None,
) -> PlexSignInService:
    """Build the Plex door: the vault, the managed server and plex.tv's account client.

    Inert: plex.tv and the server are asked on the first sign-in only. A malformed
    ``PLEX_TOKEN_KEYS`` does not stop the process — the CLI and the password door must still
    run — it is logged by key position and the door keeps no token, as without a key.

    Args:
        config: The typed configuration (``web.plex_forward_url``).
        settings: The env-var settings (``PLEX_TOKEN``, ``PLEX_TOKEN_KEYS``).
        app_store: The environment's ``app.db``.
        credentials: The credential service, which opens the session.
        event_bus: The bus E8 is published on.
        server: The process's client of the Plex server ``PLEX_URL`` names; ``None``
            without a ``PLEX_TOKEN``.

    Returns:
        The door; with no ``PLEX_TOKEN`` it has no server and admits nobody.
    """
    from personalscraper.api.plex_account import PlexAccountClient  # noqa: PLC0415
    from personalscraper.app.accounts.token_vault import MalformedTokenKey, TokenVault  # noqa: PLC0415
    from personalscraper.conf.environment import current_environment  # noqa: PLC0415

    keys_malformed = False
    try:
        vault = TokenVault.from_settings(settings)
    except MalformedTokenKey as exc:
        log.error("plex_token.keys_malformed", error=str(exc))
        vault, keys_malformed = None, True
    return PlexSignInService(
        app_store,
        credentials,
        vault=vault,
        client_factory=lambda product, client_id: PlexAccountClient(product=product, client_identifier=client_id),
        server=server,
        server_token=settings.plex_token,
        environment=current_environment(),
        forward_url=config.web.plex_forward_url,
        bus=event_bus,
        vault_keys_malformed=keys_malformed,
    )


def _build_library_services(
    config: Config, providers: ProviderLookup, plex: PlexClient | None, runs: RunService
) -> tuple[CatalogueView, LibraryReads, MediaSheets, LibraryRescrape, LibraryDeletion]:
    """Build the library's services over one catalogue view, one index, the providers and Plex.

    Inert: the catalogue store and the ownership checker open on first use, the deletion
    authority reads ``acquire.db`` on each deletion only, and the provider clients are
    reached through ``providers`` on their first call. A registry that cannot be built (a
    missing API key) gives no client: the sheets answer ``provider.unavailable``. The
    clients make ONE attempt per call, so a dead provider cannot hold a web request
    through a backed-off retry loop (v0's sheet rule, D1). The deletion makes the decision
    the pipeline's deleters' :class:`DeleteAuthority` makes (a folder still owed to a
    tracker is kept), through a :class:`StrictDeletePermit` that opens ``acquire.db``
    read-only and refuses the deletion when it cannot read it (operator ruling R1); it
    tells the Plex server ``plex`` names, and with no client reports Plex as not configured.

    Args:
        config: The typed configuration; ``indexer.db_path`` and ``acquire.db_path`` are
            resolved by the loader.
        providers: Where the TMDB and TVDB clients are found.
        plex: The process's client of the Plex server; ``None`` without a ``PLEX_TOKEN``.
        runs: The run service the rescrape asks through.

    Returns:
        The catalogue view (which owns and closes the catalogue store and the ownership
        checker), then the reads, the sheets, the rescrape and the deletion.
    """
    # Lazy imports: the indexer pulls heavy trees; building AppServices for a command
    # that never reads the library stays import-light.
    from personalscraper.acquire.catalogue import CatalogueStore  # noqa: PLC0415
    from personalscraper.acquire.delete_authority import StrictDeletePermit  # noqa: PLC0415
    from personalscraper.app.library.completeness import CatalogueView  # noqa: PLC0415
    from personalscraper.app.library.deleting import LibraryDeletion  # noqa: PLC0415
    from personalscraper.app.library.reads import LibraryReads  # noqa: PLC0415
    from personalscraper.app.library.rescrape import LibraryRescrape  # noqa: PLC0415
    from personalscraper.app.library.sheets import MediaSheets  # noqa: PLC0415
    from personalscraper.indexer.library_view import LibraryIndex  # noqa: PLC0415
    from personalscraper.indexer.ownership import IndexerOwnershipChecker  # noqa: PLC0415

    index_db = config.indexer.db_path
    acquire_db = config.acquire.db_path
    assert index_db is not None and acquire_db is not None
    # The pipeline's decision, read-only and refusing what it cannot read (operator ruling
    # R1): the web process never creates nor migrates acquire.db, and a deletion whose seed
    # obligations are unreadable is refused rather than allowed.
    delete_permit = StrictDeletePermit(acquire_db)
    index = LibraryIndex(index_db)
    view = CatalogueView(catalogue=CatalogueStore(acquire_db), ownership=IndexerOwnershipChecker(index_db))
    sheets = MediaSheets(index=index, view=view, providers=providers)
    return (
        view,
        LibraryReads(index=index, view=view, sheets=sheets),
        sheets,
        LibraryRescrape(index=index, runs=runs),
        LibraryDeletion(
            index=index,
            index_db=index_db,
            data_dir=config.paths.data_dir,
            plex=plex,
            delete_permit=delete_permit,
            config=config,
        ),
    )


def build_ownership_checker(config: Config) -> OwnershipChecker:
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
