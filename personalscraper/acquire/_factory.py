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
from personalscraper.api.tracker._factory import build_tracker_registry

if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.api.transport._policy import CircuitPolicy
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus


def build_acquire_context(
    config: "Config",
    settings: "Settings",
    *,
    event_bus: "EventBus",
    cb_policy: "CircuitPolicy",
    torrent_client: "QBitClient | TransmissionClient | None" = None,
) -> AcquireContext:
    """Build the AcquireContext at the composition-root boundary.

    Delegates tracker registry construction to the unchanged
    :func:`~personalscraper.api.tracker._factory.build_tracker_registry`
    (RP5a). Sets ``store=None`` — RP3 fills the slot when the acquisition
    DB is wired. Borrows ``torrent_client`` from the caller; does NOT build
    or validate it (that is the torrent-client boundary's responsibility).

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

    Returns:
        A populated :class:`AcquireContext` with ``tracker_registry`` set,
        ``store=None``, and ``torrent_client`` forwarded.

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
    return AcquireContext(
        tracker_registry=tracker_registry,
        store=None,
        torrent_client=torrent_client,
    )


__all__ = ["build_acquire_context"]
