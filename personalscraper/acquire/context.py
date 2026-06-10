"""AcquireContext — frozen injection handle for the acquisition lobe (RP5c).

Mirrors the ``AppContext`` pattern: a frozen dataclass constructed once at
the composition root and carrying the owned/borrowed service handles needed
by the acquisition lobe.

Import direction: this module imports only from ``personalscraper.api`` and
``personalscraper.acquire`` — never from triage packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.delete_authority import DeleteAuthority
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.api.tracker._registry import TrackerRegistry


@dataclass(frozen=True)
class AcquireContext:
    """Frozen injection handle for the acquisition lobe.

    Constructed once per process at the composition root (inside
    ``_build_app_context``) and stored as ``AppContext.acquire``.

    Ownership semantics:
    - ``tracker_registry``: OWNED — RP5a port, migrated from ``AppContext``.
      ``close()`` will call ``tracker_registry.close()``.
    - ``store``: OWNED (when present) — filled by RP3; ``close()`` propagates.
    - ``delete_authority``: BORROWED (stateless) — built at the same boundary
      as ``store``; borrows the store handle (no lifecycle of its own).
      ``close()`` does NOT touch ``delete_authority`` — it has no ``close()``
      method and owns no resources.
    - ``torrent_client``: BORROWED — shared with ``ingest``; its lifecycle is
      managed by the ``ingest`` boundary, NOT here. ``close()`` must NOT call
      ``torrent_client.close()``.

    Attributes:
        tracker_registry: Configured ``TrackerRegistry`` (always present at
            boot; may be empty when all trackers are disabled).
        store: ``AcquireStore`` implementation or ``None``.  Slot filled by
            RP3 when the acquisition DB is wired.
        delete_authority: ``DeleteAuthority`` or ``None``.  Stateless resolver
            that borrows the store — fail-open when store is ``None``.
        torrent_client: Active torrent client or ``None``.  Borrowed from
            the shared port — ``close()`` does not own its lifecycle.
    """

    tracker_registry: "TrackerRegistry"
    store: "AcquireStore | None" = None
    delete_authority: "DeleteAuthority | None" = None
    torrent_client: "QBitClient | TransmissionClient | None" = None

    def close(self) -> None:
        """Close OWNED resources: tracker_registry and store (when present).

        Does NOT close ``torrent_client`` — that handle is shared with the
        ``ingest`` boundary which owns its lifecycle.
        Does NOT close ``delete_authority`` — it is stateless, borrows the
        store handle, and has no ``close()`` method.

        Raises:
            Exception: If ``store.close()`` raises (after RP3 wires it).
            ``close()`` does not suppress exceptions itself — fail-safety is
            delegated to the resources.  ``TrackerRegistry.close()`` is
            independently fail-soft, and the future RP3 store ``close()`` MUST
            honor the same contract or its exception will propagate.
        """
        self.tracker_registry.close()
        if self.store is not None:
            self.store.close()


__all__ = ["AcquireContext"]
