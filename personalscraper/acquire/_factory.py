"""Config-driven factory for AcquireContext — acquire-lobe RP5c.

Mirrors ``api/tracker/_factory.py``: thin assembler at the composition-root
boundary. Delegates tracker construction entirely to the unchanged
``build_tracker_registry`` from RP5a. Adds no new validation — boot
validation remains RP5a's; ``TrackerConfigError`` still surfaces at the same
boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.acquire.context import AcquireContext
from personalscraper.acquire.delete_authority import build_delete_authority
from personalscraper.acquire.store import build_acquire_store
from personalscraper.api.tracker._factory import build_tracker_registry
from personalscraper.core.ownership import NullOwnershipChecker

if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.api.transport._policy import CircuitPolicy
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.ownership import OwnershipChecker


def build_acquire_context(
    config: "Config",
    settings: "Settings",
    *,
    event_bus: "EventBus",
    cb_policy: "CircuitPolicy",
    torrent_client: "QBitClient | TransmissionClient | None" = None,
    ownership: "OwnershipChecker | None" = None,
) -> AcquireContext:
    """Build the AcquireContext at the composition-root boundary.

    Delegates tracker registry construction to the unchanged
    :func:`~personalscraper.api.tracker._factory.build_tracker_registry`
    (RP5a). Fills the ``store`` slot with a **lazily-built**
    :class:`~personalscraper.acquire.store.ConcreteAcquireStore`
    (:func:`~personalscraper.acquire.store.build_acquire_store`): the handle is
    inert at build time — it opens no connection, takes no lock and runs no
    migration until the first sub-store access. Open/migration errors
    (``AcquireLockError`` / ``AcquireCorruptError`` / ``AcquireMigrationError``)
    therefore surface at **first access**, not at boot — fail-open-friendly for
    the deletion path. Tracker errors still fail loud at boot. Borrows
    ``torrent_client`` from the caller; does NOT build or validate it (that is
    the torrent-client boundary's responsibility).

    Also builds a stateless :class:`DeleteAuthority` over the same lazy store:
    it is fail-open (returns ALLOW) when the store is ``None``, and costs
    nothing at boot.

    ``TrackerConfigError`` raised by ``build_tracker_registry`` propagates
    unchanged — fail-loud at the same boundary as ``RegistryConfigError``.

    Args:
        config: Typed JSON5 configuration loaded at the boundary.
        settings: Pydantic env-var settings (API keys, paths).
        event_bus: In-process event bus forwarded to the tracker registry.
        cb_policy: Circuit-breaker policy forwarded to the tracker registry;
            reserved for future circuit-wiring — not yet threaded into the
            tracker transports.
        torrent_client: Already-built torrent client, or ``None``.
            Lifecycle is NOT owned by ``AcquireContext`` — it is shared with
            the ``ingest`` boundary.
        ownership: Pre-built :class:`OwnershipChecker` port implementation
            (RP6), or ``None``. Typed on the CORE port — the concrete
            ``IndexerOwnershipChecker`` (which reads ``library.db``) is built at
            the TRUE composition root (``cli_helpers._build_app_context``) and
            injected here, so ``acquire/`` never imports ``indexer/`` (the
            layering boundary holds). ``None`` falls back to
            :class:`NullOwnershipChecker` (always ``False``), the safe default
            for unit tests and commands with no library wired.

    Returns:
        A populated :class:`AcquireContext` with ``tracker_registry`` set, a
        lazily-built ``store`` (opens on first use), a stateless
        ``delete_authority``, ``torrent_client`` forwarded, and the injected
        (or ``NullOwnershipChecker``) ``ownership`` handle.

    Raises:
        TrackerConfigError: Any error-severity issue found in the tracker
            config (surfaced by ``build_tracker_registry``).
    """
    tracker_registry = build_tracker_registry(
        config.tracker,
        config.ranking,
        settings=settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
    )
    # Inert at build (no I/O): opens lazily on first sub-store access. A mock
    # config whose .acquire is never touched leaks nothing, so no path guard is
    # needed at the composition root.
    store = build_acquire_store(config.acquire)
    # Per-tracker seeding economy map (tracker_name → TrackerEconomyConfig) for
    # the dispatch-time obligation writer (DESIGN §7.2). Only trackers that
    # declare an explicit `economy` block participate; activation-only trackers
    # (economy is None) are intentionally absent, so record_dispatch records an
    # honest tracker-unresolved MISS for their torrents.
    economy = {
        name: provider.economy for name, provider in config.tracker.providers.items() if provider.economy is not None
    }
    # Stateless — fail-open when store is None, costs nothing at boot. The
    # torrent_client (read-only here) and economy feed record_dispatch's
    # basename+size correlation + tracker resolution.
    delete_authority = build_delete_authority(
        store=store,
        torrent_client=torrent_client,
        economy=economy,
    )
    # GrabCore is the single grab handle (orchestrator + service). It is built
    # ONLY here — the only frame holding registry + config.ranking +
    # torrent_client + event_bus + store together. It is None when there is no
    # torrent_client (read-only / dry-run can still search+filter+rank via the
    # registry, but cannot add). Transports come from the registry's phase-2
    # accessor so resolve_source never reaches back into the registry.
    grab: GrabCore | None = None
    if torrent_client is not None:
        from personalscraper.acquire.orchestrator import GrabOrchestrator  # noqa: PLC0415
        from personalscraper.acquire.service import (  # noqa: PLC0415
            AcquisitionService,
            GrabCore,
        )

        orchestrator = GrabOrchestrator(
            tracker_registry=tracker_registry,
            transports=tracker_registry.transports(),
            torrent_client=torrent_client,
            event_bus=event_bus,
            ranking=config.ranking,
        )
        service = AcquisitionService(
            store=store,
            orchestrator=orchestrator,
            event_bus=event_bus,
            config=config,
        )
        grab = GrabCore(service=service, orchestrator=orchestrator)

    # RP6: ownership handle (single field, anti-service-locator). The concrete
    # IndexerOwnershipChecker is built+injected at the composition root; this
    # frame only forwards it (acquire/ stays free of any indexer/ import). When
    # no checker is injected, fall back to the fail-open NullOwnershipChecker so
    # the field is always a valid port impl.
    return AcquireContext(
        tracker_registry=tracker_registry,
        store=store,
        delete_authority=delete_authority,
        torrent_client=torrent_client,
        grab=grab,
        ownership=ownership if ownership is not None else NullOwnershipChecker(),
    )


__all__ = ["build_acquire_context"]
