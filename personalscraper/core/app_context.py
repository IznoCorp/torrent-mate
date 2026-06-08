"""Process-scoped service bundle.

``AppContext`` is the long-lived service container constructed once per
process at the system boundary (CLI entry, launchd scan entry, future Web UI
or Watcher boot). It carries the three services that EVERY pipeline run,
indexer scan, or trailer-CLI invocation needs: ``config`` (the typed JSON5
configuration), ``settings`` (Pydantic env-var settings), and ``event_bus``
(the in-process :class:`EventBus`).

**Boundary-only rule** (DESIGN.md §Architecture, codified by the AST test
at ``tests/architecture/test_app_context_boundary.py``): internal
components MUST NOT receive AppContext "for convenience". Inject the
specific services they need (a ``Config``, a single ``MetadataClient``,
etc.) — never the whole bundle. The allowlist of authorized boundary
modules lives in the same test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Imported under TYPE_CHECKING to avoid a circular import: ``Config``
    # and ``Settings`` may transitively import modules that reach back here.
    # The frozen dataclass stores them by reference; the runtime never
    # inspects their types.
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus


@dataclass(frozen=True)
class AppContext:
    """Long-lived process-scoped service bundle.

    Constructed exactly once per process at the system boundary. Frozen
    because the bundle's identity is part of every event's correlation
    context — swapping a service mid-process would break invariants that
    later phases (subscribers, AST boundary test) rely on.

    Attributes:
        config: The typed JSON5 configuration loaded at boundary.
        settings: The Pydantic env-var settings (API keys, paths).
        event_bus: The in-process ``EventBus`` for cross-component events.
        provider_registry: The configured :class:`ProviderRegistry`
            instantiated at boot (DESIGN §5.2 / feat/registry §6.1). Bundles
            every metadata provider (TMDB, TVDB, OMDB, …) with circuit
            policy + event-bus instrumentation. Boundary modules read it to
            hand the registry (or specific capabilities) down to the
            components that need them — see the boundary allowlist in
            ``tests/architecture/test_app_context_boundary.py``.
        torrent_client: Active torrent client, or ``None`` when no torrent
            client is configured (DESIGN D3/D9). Boundary modules read this
            field to pass the client to pipeline steps without re-building it.
        tracker_registry: Configured :class:`TrackerRegistry` built at boot
            by :func:`~personalscraper.api.tracker._factory.build_tracker_registry`
            (called from the composition root), or ``None`` when no tracker
            is configured. In production the composition root always sets this
            to a real (possibly empty) registry. (RP5a — tracker-wiring.)
    """

    config: Config
    settings: Settings
    event_bus: EventBus
    provider_registry: ProviderRegistry
    torrent_client: "QBitClient | TransmissionClient | None" = None
    tracker_registry: "TrackerRegistry | None" = None  # RP5a — own port handle


__all__ = ["AppContext"]
