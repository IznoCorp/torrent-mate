"""Post-dispatch reconciliation subscriber (ACQUIRE-02).

The dispatch step used to reconcile wanted rows *inside* ``DeleteAuthority``
(a delete-permit port): it closed grabbed rows, retired followed films and
emitted ``FilmAcquired``. That accreted three sub-stores + the bus behind a
narrow delete-permit contract. This subscriber lifts that concern back to the
composition layer:

- It subscribes to :class:`~personalscraper.indexer.events.LibraryScanCompleted`
  — the dispatch step's ``_enrich_after_dispatch`` runs an ``enrich`` scan right
  after draining the outbox, so by the time the scan completes the just-landed
  media is already in ``library.db`` and ownership is fresh. That makes the
  canonical ownership-based pass
  (:func:`~personalscraper.acquire.reconcile.reconcile_wanted`) the robust
  closure (the old info-hash correlation missed scraped/renamed media whose
  staging size diverged from the torrent).
- For every movie row the pass transitioned to ``done`` it retires the follow
  and emits ``FilmAcquired`` (the D2-A operator-feed toast), the retirement rule
  written once here instead of inline in the delete-permit.

Wired at the dispatch composition roots only (the standalone
``personalscraper dispatch`` command and the full-run ``DispatchStep``), never
universally — a plain ``library-index`` scan must not gain a reconciliation
side effect. ``DeleteAuthority`` keeps only ``may_delete`` /
``has_active_obligation`` + the seed-obligation recording.

Import direction: composition layer — imports ``acquire/`` (reconcile + events)
and ``indexer/`` (the scan-completed event), never triage internals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.acquire.events import FilmAcquired
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.indexer.events import LibraryScanCompleted
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.core.ownership import OwnershipChecker

log = get_logger("acquire.post_dispatch_reconcile")


class PostDispatchReconcileSubscriber:
    """Reconcile wanted rows + retire acquired films after a post-dispatch scan.

    Subscribes to :class:`LibraryScanCompleted` and, on each scan completion,
    runs :func:`reconcile_wanted` against the (now fresh) library, then retires
    every followed film whose row this pass closed and emits ``FilmAcquired``.

    The whole handler is fail-soft: the event is emitted from the scanner's
    ``finally`` block, so a reconciliation error must never propagate back into
    the scanner. Each film retirement is independently guarded so one bad follow
    never blocks the rest.

    Attributes:
        name: Subscriber identity tag for logging.
    """

    name = "post_dispatch_reconcile"

    def __init__(
        self,
        bus: EventBus,
        store: "AcquireStore",
        ownership: "OwnershipChecker",
    ) -> None:
        """Register the scan-completed handler and store the acquire ports.

        Args:
            bus: The :class:`EventBus` to subscribe to (and to emit
                ``FilmAcquired`` on).
            store: The acquire store (single-writer discipline via its
                sub-stores) — the reconciliation writes go here, not to
                ``library.db``.
            ownership: The library ownership port (RP6) used to decide which
                grabbed/pending rows the library now owns.
        """
        self._bus = bus
        self._store = store
        self._ownership = ownership
        self._tokens: list[SubscriptionToken] = [
            bus.subscribe(LibraryScanCompleted, self._on_scan_completed),
        ]

    def close(self) -> None:
        """Unsubscribe the stored token. Idempotent."""
        for token in self._tokens:
            self._bus.unsubscribe(token)
        self._tokens = []

    def _on_scan_completed(self, event: LibraryScanCompleted) -> None:
        """Reconcile wanted rows + retire acquired films (fail-soft).

        Args:
            event: The emitted :class:`LibraryScanCompleted` (its fields are not
                read — the scan is only the trigger; the reconciliation reads the
                fresh library through the ownership port).
        """
        try:
            summary = reconcile_wanted(self._store, self._ownership, None)
        except Exception as exc:  # noqa: BLE001 — fail-soft: never disrupt the scanner
            log.warning("acquire.post_dispatch_reconcile.failed", scan_mode=event.mode, error=str(exc))
            return
        for followed_id in summary.closed_movie_followed_ids:
            self._retire_acquired_film(followed_id)

    def _retire_acquired_film(self, followed_id: int) -> None:
        """Retire a followed film whose media just landed and emit ``FilmAcquired``.

        Mirrors the former ``DeleteAuthority._retire_acquired_film``: deactivate
        the follow and emit the operator-visible ``FilmAcquired`` toast. Fail-soft
        — a follow that cannot be read/deactivated is logged and skipped (the
        wanted row is already closed; the next pass finds it done and does not
        re-emit).

        Args:
            followed_id: The ``followed_series`` rowid to retire.
        """
        try:
            follow = self._store.follow.get(followed_id)
            self._store.follow.set_active(followed_id, False)
        except Exception as exc:  # noqa: BLE001 — fail-soft: one bad follow never blocks the rest
            log.warning("acquire.post_dispatch_reconcile.film_unfollow_failed", followed_id=followed_id, error=str(exc))
            return
        log.info("acquire.post_dispatch_reconcile.film_unfollowed", followed_id=followed_id)
        if follow is None:
            return
        self._bus.emit(FilmAcquired(media_ref=follow.media_ref, title=follow.title, followed_id=followed_id))


def build_post_dispatch_reconcile_subscriber(
    event_bus: EventBus,
    acquire: "AcquireContext | None",
) -> PostDispatchReconcileSubscriber | None:
    """Build + wire the post-dispatch reconcile subscriber for a dispatch call.

    Takes the two specific services it consumes — the process bus and the
    acquire lobe handle — never the whole ``AppContext`` (boundary rule: the
    composition roots destructure the bundle; internal builders receive narrow
    services). Returns ``None`` when no acquire store/ownership is configured
    (nothing to reconcile) so the dispatch entry points can wire it
    unconditionally and simply skip when absent.

    Args:
        event_bus: The process :class:`EventBus` (subscribe + FilmAcquired emit).
        acquire: The :class:`AcquireContext` carrying ``store`` + ``ownership``,
            or ``None`` when the caller has no acquire lobe.

    Returns:
        A live (already-subscribed) :class:`PostDispatchReconcileSubscriber`, or
        ``None`` when there is no acquire store.
    """
    # Duck-typed reads like ``resolve_dispatch_authority``: a bare fake acquire
    # handle carrying only ``delete_authority`` yields no store and simply gets
    # no subscriber.
    store = getattr(acquire, "store", None)
    ownership = getattr(acquire, "ownership", None)
    if store is None or ownership is None:
        return None
    return PostDispatchReconcileSubscriber(event_bus, store, ownership)


__all__ = ["PostDispatchReconcileSubscriber", "build_post_dispatch_reconcile_subscriber"]
