"""Concrete DeletePermit + SeedObligationRecorder over acquire/store (RP3).

Deletion-time resolver: joins on seed_obligation.dispatched_path (exact
match + descendants via :meth:`_SeedSubStore.find_active_under`).  Does NOT
use torrent-client content_path — those two trees never overlap after ingest
(DESIGN §7.2).

Fail-open contract: store absent / unreadable / lock-timeout / no-obligation
/ any lookup error → ALLOW. VETO only on positively-known unmet obligation.

Logging: personalscraper.logger.get_logger (NOT structlog.get_logger).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from personalscraper.acquire.domain import SeedObligation
from personalscraper.core.delete_permit import (
    ALLOW,
    PermitDecision,
    veto,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import ConcreteAcquireStore
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.api.torrent._contracts import TorrentLister, TorrentStateInspector
    from personalscraper.conf.models.api_config import TrackerEconomyConfig

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
    ) -> None:
        """Initialise with the acquire store, torrent client, and economy map.

        Args:
            store: The ConcreteAcquireStore, or None to use fail-open fallback.
            torrent_client: A read-only torrent client (TorrentLister +
                TorrentStateInspector) for dispatch-time correlation, or None.
            economy: Tracker-name → TrackerEconomyConfig map for resolving the
                source tracker from a torrent's tags, or None.
        """
        self._store = store
        self._torrent_client = torrent_client
        self._economy = economy

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
        seed-time + path-exists). The VETO/ALLOW logic is unchanged.

        Args:
            path: Absolute path about to be deleted.

        Returns:
            ALLOW if permitted, veto(reason) if a live unmet obligation exists.
        """
        assert self._store is not None  # noqa: S101 — guarded by the caller

        obligations = self._store.seed.find_active_under(path)
        if not obligations:
            return ALLOW

        now = int(time.time())

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
            seed_time_elapsed = now - obligation.added_at
            if seed_time_elapsed >= obligation.min_seed_time_s:
                continue

            # Positively-known unmet obligation → VETO.
            reason = (
                f"seeding obligation not met: tracker={obligation.source_tracker} "
                f"info_hash={obligation.info_hash[:8]}... "
                f"elapsed={seed_time_elapsed}s < required={obligation.min_seed_time_s}s"
            )
            log.warning(
                "acquire.delete_authority.veto",
                path=str(path),
                info_hash=obligation.info_hash,
                source_tracker=obligation.source_tracker,
                seed_time_elapsed=seed_time_elapsed,
                min_seed_time_s=obligation.min_seed_time_s,
            )
            return veto(reason)

        return ALLOW

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> None:
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
        """
        if self._store is None or self._torrent_client is None:
            log.debug(
                "acquire.record_dispatch.noop",
                reason="no-store" if self._store is None else "no-client",
                dispatched_dest=str(dispatched_dest),
            )
            return

        # Single cached get_completed() — fail-soft on any client error.
        try:
            completed = self._torrent_client.get_completed()
        except Exception as exc:  # noqa: BLE001 — fail-soft: never interrupt the caller
            log.warning(
                "acquire.record_dispatch.miss",
                reason="client-error",
                error=str(exc),
                dispatched_dest=str(dispatched_dest),
            )
            return

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
            return

        # The whole correlation body below (match comprehension, is_seeding()
        # client call, tracker resolution, obligation construction + write) is
        # fail-soft per the §9 fail-open / §7.2 best-effort contract: a flaky
        # client (is_seeding raising) or any unexpected error must NOT propagate
        # into the dispatch FS path (write-before-move → would abort the move).
        # Any unexpected exception → MISS reason="unexpected-error", never raised.
        try:
            self._correlate_and_record(
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
            return

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
    ) -> None:
        """Correlate the staging source to a seeding torrent and write the obligation.

        Extracted so the whole window (match, ``is_seeding`` client call,
        tracker resolution, obligation construction + store write) sits inside a
        single fail-soft guard in :meth:`record_dispatch`.  Emits the normal
        §7.2 MISS reasons for the deterministic branches and the HIT on success.

        Args:
            completed: The cached list of completed torrents.
            basename: ``staging_source.name`` to correlate on.
            size: The (recursive) staging size to correlate on.
            dispatched_dest: The destination path recorded on the obligation.
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
            return

        if len(matches) > 1:
            log.warning(
                "acquire.record_dispatch.miss",
                reason="name+size-ambiguous",
                basename=basename,
                match_count=len(matches),
                dispatched_dest=str(dispatched_dest),
            )
            return

        item = matches[0]

        # P0-B.3 — the §5 wanted closure this correlation always promised:
        # the torrent's content is being dispatched into the library, so its
        # ``grabbed`` wanted row(s) close ``done`` HERE, at the moment the
        # media physically lands — independent of index freshness and of the
        # seed-obligation branches below (fail-soft: the ownership sweep in
        # detect/grab is the safety net).
        try:
            closed = self._store.wanted.mark_done_by_hash(item.hash)
            for row in closed:
                log.info(
                    "acquire.record_dispatch.wanted_closed",
                    wanted_id=row.id,
                    kind=row.kind,
                    season=row.season,
                    episode=row.episode,
                    info_hash=item.hash,
                )
        except Exception as exc:  # noqa: BLE001 — fail-soft: never interrupt a dispatch
            log.warning(
                "acquire.record_dispatch.wanted_close_failed",
                error=str(exc),
                info_hash=item.hash,
            )

        if not self._torrent_client.is_seeding(item):
            log.debug(
                "acquire.record_dispatch.miss",
                reason="not-seeding",
                info_hash=item.hash,
                dispatched_dest=str(dispatched_dest),
            )
            return

        resolved = self._resolve_tracker(item)
        if resolved is None:
            log.info(
                "acquire.record_dispatch.miss",
                reason="tracker-unresolved",
                info_hash=item.hash,
                tags=list(item.tags),
                dispatched_dest=str(dispatched_dest),
            )
            return

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
            return

        log.info(
            "acquire.record_dispatch.hit",
            info_hash=item.hash,
            tracker=tracker_name,
            dispatched_dest=str(dispatched_dest),
        )

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


def build_delete_authority(
    store: "ConcreteAcquireStore | None",
    torrent_client: "_ReadOnlyTorrentClient | None" = None,
    economy: "dict[str, TrackerEconomyConfig] | None" = None,
) -> DeleteAuthority:
    """Build a DeleteAuthority over the given store, torrent client, and economy map.

    Args:
        store: The ConcreteAcquireStore, or None for fail-open no-op.
        torrent_client: A read-only torrent client (TorrentLister +
            TorrentStateInspector) for dispatch-time correlation, or None.
        economy: Tracker-name → TrackerEconomyConfig map, or None.

    Returns:
        A DeleteAuthority ready for injection into dispatch/maintenance.
    """
    return DeleteAuthority(store=store, torrent_client=torrent_client, economy=economy)


__all__ = ["DeleteAuthority", "build_delete_authority"]
