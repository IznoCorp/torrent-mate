"""AcquireContext — frozen injection handle for the acquisition lobe (RP5c).

Mirrors the ``AppContext`` pattern: a frozen dataclass constructed once at
the composition root and carrying the owned/borrowed service handles needed
by the acquisition lobe.

Import direction: this module imports only from ``personalscraper.api`` and
``personalscraper.acquire`` — never from triage packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from personalscraper.core.ownership import NullOwnershipChecker

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.delete_authority import DeleteAuthority
    from personalscraper.acquire.service import GrabCore
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.core.ownership import OwnershipChecker


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
        grab: ``GrabCore`` sub-handle (orchestrator + acquisition service) or
            ``None``.  Built by ``_factory.build_acquire_context`` only when a
            ``torrent_client`` is present (``None`` for read-only / dry-run
            commands).  Owns no closeable resource of its own — the bus is
            borrowed and the store / registry lifecycles are owned here —
            so ``close()`` does NOT touch it.
        ownership: ``OwnershipChecker`` port implementation (RP6). Typed on the
            CORE port (``core.ownership.OwnershipChecker``), never the indexer
            impl — ``acquire/`` stays free of any ``indexer/`` import. Defaults
            to ``NullOwnershipChecker`` (always ``False``); the composition root
            injects an ``IndexerOwnershipChecker`` when ``library.db`` is
            configured and present. The injected impl holds a **lazy, read-only,
            lock-free** connection (opened on first ``owns()``), so the single
            handle takes no lifetime lock at the composition root. OWNED:
            ``close()`` closes it when it exposes a ``close()`` method (the
            indexer impl does; ``NullOwnershipChecker`` does not).
    """

    tracker_registry: "TrackerRegistry"
    store: "AcquireStore | None" = None
    delete_authority: "DeleteAuthority | None" = None
    torrent_client: "QBitClient | TransmissionClient | None" = None
    grab: "GrabCore | None" = None
    ownership: "OwnershipChecker" = field(default_factory=NullOwnershipChecker)

    def close(self) -> None:
        """Close OWNED resources: tracker_registry, store, and ownership.

        Does NOT close ``torrent_client`` — that handle is shared with the
        ``ingest`` boundary which owns its lifecycle.
        Does NOT close ``delete_authority`` — it is stateless, borrows the
        store handle, and has no ``close()`` method.
        Does NOT close ``grab`` — the ``GrabCore`` holds no closeable resource
        (its bus is borrowed; its store / registry are closed above).
        Closes ``ownership`` ONLY when it exposes a ``close()`` method: the
        injected ``IndexerOwnershipChecker`` owns a lazy read connection it must
        release (idempotent, fail-soft); ``NullOwnershipChecker`` has no
        ``close()`` and is left untouched.

        Raises:
            Exception: If ``store.close()`` raises (after RP3 wires it).
            ``close()`` does not suppress exceptions itself — fail-safety is
            delegated to the resources.  ``TrackerRegistry.close()`` is
            independently fail-soft, the RP3 store ``close()`` and the RP6
            ``IndexerOwnershipChecker.close()`` both honour the same fail-soft
            contract, so neither propagates.
        """
        self.tracker_registry.close()
        if self.store is not None:
            self.store.close()
        ownership_close = getattr(self.ownership, "close", None)
        if callable(ownership_close):
            ownership_close()


__all__ = ["AcquireContext"]
