"""Concrete DeletePermit + SeedObligationRecorder over acquire/store (RP3).

Deletion-time resolver: joins on seed_obligation.dispatched_path (exact
match + descendants via :meth:`_SeedSubStore.find_active_under`).  Does NOT
use torrent-client content_path — those two trees never overlap after ingest
(DESIGN §7.2).

Fail-open contract: store absent / unreadable / lock-timeout / no-obligation
/ any lookup error → ALLOW. VETO only on positively-known unmet obligation.
:class:`StrictDeletePermit` makes the same decision for the library's deletion
from the interface, and RAISES where this one allows (operator ruling R1).

Logging: personalscraper.logger.get_logger (NOT structlog.get_logger).
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.store import _SeedSubStore
from personalscraper.api.torrent._base import scoped
from personalscraper.core.delete_permit import (
    ALLOW,
    ObligationsUnreadable,
    PermitDecision,
    veto,
)
from personalscraper.core.event_bus import current_run_uid
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import ConcreteAcquireStore
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.api.torrent._contracts import TorrentLister, TorrentStateInspector
    from personalscraper.conf.models.api_config import TorrentScope, TrackerEconomyConfig
    from personalscraper.core.event_bus import Event

    class _ReadOnlyTorrentClient(TorrentLister, TorrentStateInspector, Protocol):
        """Read-only torrent client: lists completed torrents + inspects seeding state.

        ``record_dispatch`` only needs to enumerate completed torrents
        (:meth:`TorrentLister.get_completed`) and inspect their seeding state
        (:meth:`TorrentStateInspector.is_seeding`). Both ``QBitClient`` and
        ``TransmissionClient`` compose these two capabilities, so this
        intersection expresses the exact requirement without coupling to a
        concrete client.
        """


log = get_logger("acquire.delete_authority")


class DeleteAuthority:
    """Implements DeletePermit and SeedObligationRecorder over the acquire store.

    Injected into dispatch/run.py and maintenance/disk_cleaner.py at the
    composition root. Never imported by those modules directly.

    Attributes:
        _store: The ConcreteAcquireStore (or None if store is absent).
        _torrent_client: A read-only torrent client (TorrentLister +
            TorrentStateInspector), or None — used by record_dispatch to
            correlate the staging source to a live seeding torrent.
        _economy: Mapping of tracker name → TrackerEconomyConfig used to
            resolve the source tracker from the torrent's tags and snapshot
            the min_seed_time / min_ratio into the obligation, or None.
    """

    def __init__(
        self,
        store: "ConcreteAcquireStore | None",
        torrent_client: "_ReadOnlyTorrentClient | None" = None,
        economy: "dict[str, TrackerEconomyConfig] | None" = None,
        scope: "TorrentScope | None" = None,
    ) -> None:
        """Initialise with the acquire store, torrent client, and economy map.

        Args:
            store: The ConcreteAcquireStore, or None to use fail-open fallback.
            torrent_client: A read-only torrent client (TorrentLister +
                TorrentStateInspector) for dispatch-time correlation, or None.
            economy: Tracker-name → TrackerEconomyConfig map for resolving the
                source tracker from a torrent's tags, or None.
            scope: The instance's scope in a shared client — ``record_dispatch``
                then correlates only the torrents of its category; ``None`` =
                the whole client.
        """
        self._store = store
        self._torrent_client = torrent_client
        self._economy = economy
        self._scope = scope

    def has_active_obligation(self, info_hash: str) -> bool:
        """Return ``True`` when *info_hash* has a live, unmet seed obligation.

        Implements :class:`~personalscraper.core.delete_permit.SeedObligationChecker`
        for ingest's fail-safe copy-vs-move decision. Fail-SAFE: on any lookup
        error, or when the store is absent, return ``False`` — ingest then
        relies on its live seeding probe instead of asserting a phantom
        obligation. A positive ``True`` (obligation active, released_at NULL)
        makes ingest COPY, preserving a paused-but-owing torrent's seed.

        Args:
            info_hash: The torrent info-hash to check.

        Returns:
            ``True`` when a positively-known active obligation exists.
        """
        if self._store is None:
            return False
        try:
            return self._store.seed.find_active_by_hash(info_hash) is not None
        except Exception as exc:  # noqa: BLE001 — fail-safe: unknown → no positive obligation
            log.warning("acquire.delete_authority.obligation_check_failed", info_hash=info_hash, error=str(exc))
            return False

    def may_delete(self, path: Path) -> PermitDecision:
        """Consult persisted seed obligations before permitting a deletion.

        Uses :meth:`_SeedSubStore.find_active_under` to match the deletion
        path AND its descendants (DESIGN §7.2): when disk_cleaner deletes a
        directory D and an obligation's dispatched_path is D/file.mkv, the
        resolver finds that obligation.  The LIKE is boundary-safe so D does
        NOT match D-other or Dx.

        Fail-open: any error anywhere in the lookup — the store query OR the
        per-obligation seed-time / path-exists checks (a pathological
        ``dispatched_path`` raising ENAMETOOLONG/EACCES on ``Path.exists()``) —
        → ALLOW (DESIGN §9).  VETO only when a positively-known unmet obligation
        exists AND the dispatched_path still exists on disk (path-exists guard
        makes stale obligations inert).  Seed-time only; ratio is deferred to C1.

        Args:
            path: Absolute path about to be deleted.

        Returns:
            ALLOW if permitted, veto(reason) if a live unmet obligation exists.
        """
        if self._store is None:
            log.debug("acquire.delete_authority.no_store", path=str(path))
            return ALLOW

        # Fail-open guard spans the ENTIRE lookup: find_active_under AND the
        # per-obligation seed-time / path-exists checks (F1). Path.exists()
        # re-raises an OSError whose errno is not benign (ENAMETOOLONG on a
        # >255-byte path, EACCES on an unreadable parent), so a pathological
        # dispatched_path must NOT make may_delete raise into the deleter —
        # DESIGN §9 requires ALLOW on any error (fail CLOSED is forbidden).
        try:
            return self._evaluate_obligations(path)
        except Exception as exc:  # noqa: BLE001 — fail-open: any error → ALLOW
            log.warning(
                "acquire.delete_authority.lookup_failed",
                path=str(path),
                error=str(exc),
            )
            return ALLOW

    def _evaluate_obligations(self, path: Path) -> PermitDecision:
        """Return the permit decision for *path* (raises propagate to the guard).

        Extracted from :meth:`may_delete` so the fail-open ``try/except`` wraps
        BOTH the store lookup and the per-obligation loop (find_active_under +
        seed-time + path-exists). The VETO/ALLOW logic is :func:`_decide`'s.

        Args:
            path: Absolute path about to be deleted.

        Returns:
            ALLOW if permitted, veto(reason) if a live unmet obligation exists.
        """
        assert self._store is not None  # noqa: S101 — guarded by the caller
        return _decide(self._store.seed, path)

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> list[Event]:
        """Correlate the staging source to a live seeding torrent and persist an obligation.

        DESIGN §7.2 dispatch-time obligation writer:

        - Calls :meth:`TorrentLister.get_completed` **once** (cached locally),
          fail-soft: any exception is logged and swallowed (never raised).
        - Correlates by **basename + size**: ``item.name == staging_source.name``
          AND ``item.size_bytes`` equals the staging size. For a FILE that is
          ``staging_source.stat().st_size``; for a DIRECTORY (dispatch passes a
          directory) it is the RECURSIVE content size — see :meth:`_staging_size`
          (C1: a directory's bare inode size never matches a multi-GB torrent).
          Zero matches → MISS ``no-live-torrent``; more than one → MISS
          ``name+size-ambiguous`` (never guessed).
        - The matched item must be seeding (``client.is_seeding(item)`` — a
          CLIENT method taking the item, per :class:`TorrentStateInspector`);
          otherwise MISS ``not-seeding``.
        - Resolves the source tracker by intersecting ``item.tags`` with the
          configured ``economy`` keys (RP1 tag convention). No tag maps to a
          configured economy → MISS ``tracker-unresolved`` (no global default
          is invented — an honest MISS is correct per the coverage envelope).
        - HIT: writes a :class:`SeedObligation` with ``info_hash=item.hash``,
          the resolved tracker, the economy's ``min_seed_time`` / ``min_ratio``,
          and ``dispatched_path=str(dispatched_dest)``. This is
          **write-before-move**: the caller invokes this BEFORE the FS move, so
          ``dispatched_dest`` does not yet exist — that is fine, the path is
          merely recorded. The store write is **fail-soft** (errors swallowed +
          logged ``acquire.record_dispatch.write_failed``).

        Every outcome is logged: ``acquire.record_dispatch.hit`` (info_hash,
        dest, tracker) or ``acquire.record_dispatch.miss`` (reason, dest) — the
        §7.2 HIT/MISS observability.

        Args:
            staging_source: Absolute path of the file in the staging area.
            dispatched_dest: Absolute path of the destination after dispatch
                (does not yet exist at call time).

        Returns:
            Always an empty list. Wanted-row closure + followed-film retirement
            (D2-A) moved to the post-dispatch reconcile subscriber (ACQUIRE-02);
            this recorder only persists the seed obligation. The ``list[Event]``
            return type is kept so the dispatch template's emit loop is
            byte-identical (it iterates an empty list).
        """
        # Provenance (advisory / #30 / F0 completeness): record the dispatch of the
        # folder currently at staging_source → its final destination. Best-effort
        # (the sub-store swallows any error) + no-op for an untracked (manual/direct)
        # item. Done BEFORE the client guard: provenance needs only the store, so a
        # dispatch with no torrent client still completes the journey record.
        if self._store is not None:
            self._store.provenance.record_dispatch_by_path(
                str(staging_source),
                dispatch_path=str(dispatched_dest),
                dispatched_at=int(time.time()),
                run_uid=current_run_uid(),  # F3: the dispatching run (None outside a run)
            )

        if self._store is None or self._torrent_client is None:
            log.debug(
                "acquire.record_dispatch.noop",
                reason="no-store" if self._store is None else "no-client",
                dispatched_dest=str(dispatched_dest),
            )
            return []

        # Single cached get_completed() — fail-soft on any client error.
        try:
            completed = scoped(self._torrent_client.get_completed(), self._scope)
        except Exception as exc:  # noqa: BLE001 — fail-soft: never interrupt the caller
            log.warning(
                "acquire.record_dispatch.miss",
                reason="client-error",
                error=str(exc),
                dispatched_dest=str(dispatched_dest),
            )
            return []

        basename = staging_source.name
        try:
            size = self._staging_size(staging_source)
        except OSError as exc:
            # staging_source missing, or an rglob/stat error while walking a
            # directory tree — an honest MISS is correct rather than a guess.
            log.warning(
                "acquire.record_dispatch.miss",
                reason="stat-error",
                error=str(exc),
                dispatched_dest=str(dispatched_dest),
            )
            return []

        # The whole correlation body below (match comprehension, is_seeding()
        # client call, tracker resolution, obligation construction + write) is
        # fail-soft per the §9 fail-open / §7.2 best-effort contract: a flaky
        # client (is_seeding raising) or any unexpected error must NOT propagate
        # into the dispatch FS path (write-before-move → would abort the move).
        # Any unexpected exception → MISS reason="unexpected-error", never raised.
        try:
            return self._correlate_and_record(
                completed=completed,
                basename=basename,
                size=size,
                dispatched_dest=dispatched_dest,
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft correlation window
            log.warning(
                "acquire.record_dispatch.miss",
                reason="unexpected-error",
                error=str(exc),
                dispatched_dest=str(dispatched_dest),
            )
            return []

    @staticmethod
    def _staging_size(staging_source: Path) -> int:
        """Return the byte size used to correlate *staging_source* to a torrent.

        For a regular file this is ``stat().st_size``.  For a directory it is
        the RECURSIVE content size — the sum of every contained file's size —
        because ``dispatch_movie`` / ``dispatch_tvshow`` pass a DIRECTORY as the
        staging source: its bare inode size (~KB) would never match a torrent's
        multi-GB ``size_bytes``, so every directory dispatch MISSed and no
        obligation was ever written (C1).  Stdlib-only (``rglob``) — acquire/
        must not import dispatch/_transfer.

        NOTE: processed / renamed media (sample-stripped, RAR-extracted,
        renamed) may still MISS because the staging tree's total size diverges
        from the torrent's reported size — that is an honest, fail-open MISS;
        full torrent↔media linkage arrives with acquisition (RP5b).  This fix
        makes the verbatim-folder-torrent case work, not every media case.

        Args:
            staging_source: The staging file or directory.

        Returns:
            The byte size to compare against ``item.size_bytes``.

        Raises:
            OSError: If ``stat`` on the source (or any walked file) fails — the
                caller turns this into a fail-soft MISS reason="stat-error".
        """
        if staging_source.is_dir():
            return sum(f.stat().st_size for f in staging_source.rglob("*") if f.is_file())
        return staging_source.stat().st_size

    def _correlate_and_record(
        self,
        *,
        completed: "list[TorrentItem]",
        basename: str,
        size: int,
        dispatched_dest: Path,
    ) -> list[Event]:
        """Correlate the staging source to a seeding torrent and write the obligation.

        Extracted so the whole window (match, ``is_seeding`` client call,
        tracker resolution, obligation construction + store write) sits inside a
        single fail-soft guard in :meth:`record_dispatch`.  Emits the normal
        §7.2 MISS reasons for the deterministic branches and the HIT on success.

        Wanted-row closure + followed-film retirement (D2-A) do NOT run here:
        that reconciliation left the delete-permit (ACQUIRE-02) for an explicit
        post-dispatch reconcile subscriber
        (:class:`~personalscraper.subscribers.dispatch_reconcile.PostDispatchReconcileSubscriber`),
        which closes owned rows via the canonical ownership pass over the
        freshly-enriched library. This method now records ONLY the seed
        obligation.

        Args:
            completed: The cached list of completed torrents.
            basename: ``staging_source.name`` to correlate on.
            size: The (recursive) staging size to correlate on.
            dispatched_dest: The destination path recorded on the obligation.

        Returns:
            Always an empty list — the recorder announces nothing itself. The
            ``list[Event]`` return is kept so the dispatch template's emit loop
            is byte-identical (it iterates an empty list).
        """
        # ``self._store`` is non-None here (guarded by the record_dispatch
        # pre-checks); assert for the type checker.
        assert self._store is not None  # noqa: S101
        assert self._torrent_client is not None  # noqa: S101

        matches = [t for t in completed if t.name == basename and t.size_bytes == size]

        if not matches:
            log.debug(
                "acquire.record_dispatch.miss",
                reason="no-live-torrent",
                basename=basename,
                size=size,
                dispatched_dest=str(dispatched_dest),
            )
            return []

        if len(matches) > 1:
            log.warning(
                "acquire.record_dispatch.miss",
                reason="name+size-ambiguous",
                basename=basename,
                match_count=len(matches),
                dispatched_dest=str(dispatched_dest),
            )
            return []

        item = matches[0]

        if not self._torrent_client.is_seeding(item):
            log.debug(
                "acquire.record_dispatch.miss",
                reason="not-seeding",
                info_hash=item.hash,
                dispatched_dest=str(dispatched_dest),
            )
            return []

        resolved = self._resolve_tracker(item)
        if resolved is None:
            log.info(
                "acquire.record_dispatch.miss",
                reason="tracker-unresolved",
                info_hash=item.hash,
                tags=list(item.tags),
                dispatched_dest=str(dispatched_dest),
            )
            return []

        tracker_name, economy = resolved

        # Write-before-move, fail-soft: a write error must never interrupt the
        # dispatch (a lost obligation degrades to fail-open at deletion time).
        # When the grab-time writer already recorded this hash (2026-07-15 —
        # obligations are created at grab, path-less), BACKFILL its
        # dispatched_path instead of inserting a duplicate.
        try:
            if self._store.seed.find_active_by_hash(item.hash) is not None:
                self._store.seed.set_dispatched_path(item.hash, str(dispatched_dest))
            else:
                self._store.seed.add(
                    SeedObligation(
                        info_hash=item.hash,
                        source_tracker=tracker_name,
                        min_seed_time_s=economy.min_seed_time,
                        min_ratio=economy.min_ratio,
                        added_at=int(time.time()),
                        dispatched_path=str(dispatched_dest),
                    )
                )
        except Exception as exc:  # noqa: BLE001 — fail-soft store write
            log.warning(
                "acquire.record_dispatch.write_failed",
                error=str(exc),
                info_hash=item.hash,
                dispatched_dest=str(dispatched_dest),
            )
            return []

        log.info(
            "acquire.record_dispatch.hit",
            info_hash=item.hash,
            tracker=tracker_name,
            dispatched_dest=str(dispatched_dest),
        )
        return []

    def record_grab_obligation(self, info_hash: str) -> bool:
        """Record the seed obligation of a grab recovered from the crash window (D2).

        The grab-time writer in ``AcquisitionService`` never ran (the process
        died between ``add()`` and ``mark_grabbed``), so the torrent is seeding
        with nothing protecting it from the deletion authority. The
        reconciliation calls this once it has confirmed the torrent is really in
        the client.

        The ``wanted`` row carries no tracker column, so the tracker is resolved
        the same way :meth:`record_dispatch` does it — from the torrent's own
        tags intersected with the configured economy map (the acquisition flow
        tags every torrent with its source tracker). An unresolvable tracker is
        an honest MISS: no obligation is invented with made-up floors.

        Fail-soft throughout: a client error, a missing store or a store write
        failure returns ``False`` and never interrupts the sweep.

        Args:
            info_hash: Info-hash of the recovered torrent.

        Returns:
            ``True`` iff an obligation was written by this call (``False`` when
            one already existed, the tracker was unresolvable, or anything
            failed).
        """
        if self._store is None or self._torrent_client is None or not info_hash:
            return False
        try:
            if self._store.seed.find_active_by_hash(info_hash) is not None:
                return False  # idempotent: the obligation is already there
            items = list(self._torrent_client.get_by_hashes({info_hash.lower()}))
            item = next((t for t in items if t.hash.lower() == info_hash.lower()), None)
            if item is None:
                log.debug("acquire.record_grab_obligation.no_live_torrent", info_hash=info_hash)
                return False
            resolved = self._resolve_tracker(item)
            if resolved is None:
                log.info(
                    "acquire.record_grab_obligation.miss",
                    reason="tracker-unresolved",
                    info_hash=info_hash,
                    tags=list(item.tags),
                )
                return False
            tracker_name, economy = resolved
            self._store.seed.add(
                SeedObligation(
                    info_hash=item.hash,
                    source_tracker=tracker_name,
                    min_seed_time_s=economy.min_seed_time,
                    min_ratio=economy.min_ratio,
                    added_at=int(time.time()),
                    dispatched_path=None,
                )
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft: the sweep must survive
            log.warning("acquire.record_grab_obligation.failed", info_hash=info_hash, error=str(exc))
            return False
        log.info("acquire.record_grab_obligation.recorded", info_hash=info_hash, tracker=tracker_name)
        return True

    def _resolve_tracker(self, item: "TorrentItem") -> "tuple[str, TrackerEconomyConfig] | None":
        """Resolve the source tracker for *item* from its tags and the economy map.

        The RP1 acquisition flow tags each torrent with its source tracker.
        Manually-added torrents usually carry no such tag, so a MISS here is
        the honest TODAY outcome (no global default is invented). The first
        tag that names a configured economy tracker wins.

        Args:
            item: The matched, seeding torrent.

        Returns:
            A ``(tracker_name, economy)`` pair if a tag maps to a configured
            economy, else ``None``.
        """
        if not self._economy:
            return None
        for tag in item.tags:
            economy = self._economy.get(tag)
            if economy is not None:
                return tag, economy
        return None

    def mark_breach(self, path: Path) -> None:
        """Mark every active obligation under *path* as breached (DESIGN §7.3).

        Called by the dispatch flow when the "real media wins" rule deletes a
        live payload before its seed obligation is met. Delegates to
        :meth:`_SeedSubStore.mark_breached_under` (boundary-safe descendant
        match). **Fail-soft**: a missing store is a silent no-op and any store
        write error is swallowed + logged — the caller is never interrupted.

        Args:
            path: Absolute path whose active obligations are breached.
        """
        if self._store is None:
            log.debug("acquire.mark_breach.noop", reason="no-store", path=str(path))
            return
        try:
            count = self._store.seed.mark_breached_under(path, int(time.time()))
        except Exception as exc:  # noqa: BLE001 — fail-soft store write
            log.warning("acquire.mark_breach.failed", path=str(path), error=str(exc))
            return
        log.info("acquire.mark_breach.done", path=str(path), count=count)


def _decide(seed: "_SeedSubStore", path: Path) -> PermitDecision:
    """Decide whether *path* may go, from the active obligations under it (raises on any lookup error).

    VETO only when a positively-known unmet obligation exists AND its
    dispatched_path still exists on disk (the path-exists guard makes stale
    obligations inert). Seed-time only; ratio is deferred to C1. The veto names
    the first unmet obligation and carries, as ``owed_until``, the latest moment
    any of them is met (``added_at + min_seed_time_s``).

    Args:
        seed: The ``seed_obligation`` sub-store to read.
        path: Absolute path about to be deleted.

    Returns:
        ALLOW if permitted, veto(reason) if a live unmet obligation exists.
    """
    obligations = seed.find_active_under(path)
    if not obligations:
        return ALLOW

    now = int(time.time())
    unmet: list[SeedObligation] = []

    for obligation in obligations:
        # Path-exists guard: a stale obligation (crash before move,
        # dispatched_path for a file that was never created) is inert.
        dp = obligation.dispatched_path
        if dp is not None and not Path(dp).exists():
            log.debug(
                "acquire.delete_authority.stale_obligation_inert",
                path=str(path),
                info_hash=obligation.info_hash,
            )
            continue

        # Seed-time check (ratio deferred to C1).
        if now - obligation.added_at >= obligation.min_seed_time_s:
            continue
        unmet.append(obligation)

    if not unmet:
        return ALLOW

    # Positively-known unmet obligation → VETO.
    first = unmet[0]
    seed_time_elapsed = now - first.added_at
    reason = (
        f"seeding obligation not met: tracker={first.source_tracker} "
        f"info_hash={first.info_hash[:8]}... "
        f"elapsed={seed_time_elapsed}s < required={first.min_seed_time_s}s"
    )
    log.warning(
        "acquire.delete_authority.veto",
        path=str(path),
        info_hash=first.info_hash,
        source_tracker=first.source_tracker,
        seed_time_elapsed=seed_time_elapsed,
        min_seed_time_s=first.min_seed_time_s,
    )
    return veto(reason, owed_until=max(one.added_at + one.min_seed_time_s for one in unmet))


#: How long a read of ``acquire.db`` waits for a writer's lock before it is unreadable.
_READ_TIMEOUT_S: Final[float] = 5.0


class StrictDeletePermit:
    """The library deletion's permit: the seed obligations read, or the deletion refused (operator ruling R1).

    The same decision as :class:`DeleteAuthority` (:func:`_decide`), with the opposite
    answer to what cannot be read: where the pipeline's deleters ALLOW (DESIGN § 9,
    fail-open), a deletion started from the interface is refused, since a medium still
    owed to a tracker cannot be told apart. ``acquire.db`` is opened READ-ONLY for each
    decision and closed after it: the web process never creates it, never migrates it,
    never quarantines it, and holds no connection between two decisions.
    """

    def __init__(self, db_path: Path) -> None:
        """Hold the path of ``acquire.db``; nothing is opened yet.

        Args:
            db_path: Path of ``acquire.db`` (resolved by the config layer).
        """
        self._db_path = db_path

    def may_delete(self, path: Path) -> PermitDecision:
        """Consult the persisted seed obligations, refusing to answer when they cannot be read.

        Args:
            path: Absolute path about to be deleted.

        Returns:
            ALLOW if permitted, veto(reason, owed_until=…) if a live unmet obligation exists.

        Raises:
            ObligationsUnreadable: ``acquire.db`` is absent, corrupt, locked past
                :data:`_READ_TIMEOUT_S`, of a schema the read does not know, or any
                lookup failed.
        """
        if not self._db_path.is_file():
            log.warning("acquire.delete_authority.store_absent", path=str(path))
            raise ObligationsUnreadable("acquire.db is absent")
        try:
            with closing(
                sqlite3.connect(f"{self._db_path.as_uri()}?mode=ro", uri=True, timeout=_READ_TIMEOUT_S)
            ) as conn:
                conn.execute("PRAGMA query_only = ON")
                return _decide(_SeedSubStore(conn), path)
        except Exception as exc:
            log.warning(
                "acquire.delete_authority.store_unreadable",
                path=str(path),
                error=type(exc).__name__,
                detail=str(exc),
            )
            raise ObligationsUnreadable(f"acquire.db cannot be read: {type(exc).__name__}") from exc


def build_delete_authority(
    store: "ConcreteAcquireStore | None",
    torrent_client: "_ReadOnlyTorrentClient | None" = None,
    economy: "dict[str, TrackerEconomyConfig] | None" = None,
    scope: "TorrentScope | None" = None,
) -> DeleteAuthority:
    """Build a DeleteAuthority over the given store, torrent client, and economy map.

    Args:
        store: The ConcreteAcquireStore, or None for fail-open no-op.
        torrent_client: A read-only torrent client (TorrentLister +
            TorrentStateInspector) for dispatch-time correlation, or None.
        economy: Tracker-name → TrackerEconomyConfig map, or None.
        scope: The instance's scope in a shared client, or None for the whole client.

    Returns:
        A DeleteAuthority ready for injection into dispatch/maintenance.
    """
    return DeleteAuthority(store=store, torrent_client=torrent_client, economy=economy, scope=scope)


__all__ = ["DeleteAuthority", "StrictDeletePermit", "build_delete_authority"]
