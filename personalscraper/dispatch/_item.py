"""Shared dispatch-item template (T3).

``dispatch_movie`` (replace) and ``dispatch_tvshow`` (merge) share ~85 % of
their scaffold: existing-folder detection, free-space gating, per-disk
capability + illegal-name gating, the §7.3 seed-obligation permit consult, the
transfer, the index/outbox write-through, and the ``ItemDispatched`` emit. The
only genuine divergences are *how* an existing copy is superseded (a 3-phase
crash-safe replace vs a backup/restore merge) and the family-specific labels
and hooks around it.

This module extracts that shared scaffold into a single
:func:`_dispatch_item` template parameterised by a per-family
:class:`DispatchSpec`. The divergent behaviour lives in the spec:

- ``transfer_fn`` — the strategy that supersedes an existing on-disk copy and
  reports, via :class:`TransferOutcome`, whether it *genuinely destroyed*
  existing library content (an overwrite / purge) so the template can journal
  the destruction exactly once (**F1**, DESIGN §6/§7).
- ``identity_guard`` — the §7 provider-ID overwrite guard (movie replace via
  ``<title>.nfo``; TV merge via ``tvshow.nfo``), or ``None`` for a family that
  applies no identity check.
- ``canonical_name_rule`` — how the index title is derived after the transfer.
- ``media_type`` / ``existing_action`` / ``journal_op`` / ``journal_detail`` /
  ``bus_source`` — the family-specific labels threaded through the scaffold.

The two concrete transfer strategies (:func:`replace_transfer`,
:func:`merge_transfer`) are thin adapters that REUSE the existing
``_movie.replace`` / ``_tv.merge`` / ``_transfer`` internals unchanged — they
add only the destroyed-content signal, never a second implementation of the
crash-safe transfer primitives.

The concrete movie / TV specs and the rewiring of the two entry points onto
this template land in the next sub-phase (plan phase-02 P2.3); this module is
self-contained and imports nothing from ``_movie`` / ``_tv`` at module scope so
that later rewiring cannot form an import cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from personalscraper.conf import resolver
from personalscraper.core.delete_permit import ALLOW
from personalscraper.dispatch import _transfer
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.disk_scanner import get_disk_status
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.dispatch.media_index import IndexEntry
from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.destructive_journal import record_destruction
from personalscraper.indexer.outbox._disk import disk_id_for_path
from personalscraper.indexer.outbox._publish import publish_event
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.dispatch.dispatcher import Dispatcher

log = get_logger("dispatcher.item")


@dataclass(frozen=True)
class TransferOutcome:
    """Outcome of a dispatch transfer strategy (the destroyed-content contract).

    A :func:`_dispatch_item` transfer strategy returns this instead of a bare
    ``bool`` so the template knows not only whether the transfer *succeeded* but
    whether it *genuinely destroyed* pre-existing library content — the single
    fact that gates the destructive-journal write (**F1**). An add-only TV merge
    succeeds while destroying nothing, so it reports ``destroyed=False`` and the
    template journals nothing; a movie replace or a TV merge-overwrite reports
    ``destroyed=True`` on success and the template appends exactly one row.

    Attributes:
        success: True when the transfer completed and verified (bytes landed).
        destroyed: True when existing on-disk content was genuinely superseded
            (an overwrite or a re-scrape-rename purge). Always ``False`` when
            ``success`` is ``False`` (a failed transfer restores the original).
    """

    success: bool
    destroyed: bool


#: A transfer strategy: supersede ``dest`` with ``source`` on the ``dest`` disk,
#: returning the destroyed-content outcome. Called only on the existing-copy
#: branch (a new-media move never destroys anything).
TransferFn = Callable[[Path, Path, FilesystemCapability], TransferOutcome]

#: A §7 identity guard: return a French block reason when superseding ``dest``
#: with ``source`` would overwrite a DIFFERENT media, else ``None`` (allow).
IdentityGuard = Callable[[Path, Path], "str | None"]

#: Derives the index title after a transfer from the (mutated) result + source.
CanonicalNameRule = Callable[[DispatchResult, Path], str]

#: Builds the French destructive-journal detail string from the source folder.
JournalDetail = Callable[[Path], str]


@dataclass(frozen=True)
class DispatchSpec:
    """Per-family parameters that specialise the shared dispatch template.

    Everything that differs between the movie *replace* path and the TV *merge*
    path is captured here; :func:`_dispatch_item` holds the shared scaffold.

    Attributes:
        media_type: ``"movie"`` or ``"tvshow"`` — threaded through
            ``_resolve_existing_on_filesystem`` and the ``IndexEntry`` write.
        existing_action: The :class:`DispatchResult` action reported when an
            existing copy is superseded (``"replaced"`` for movies, ``"merged"``
            for TV). Also drives the derived skip / dry-run verb.
        transfer_fn: The existing-copy transfer strategy (see :data:`TransferFn`).
        identity_guard: The §7 provider-ID overwrite guard (movie replace and TV
            merge both wire one), or ``None`` when a family applies no identity
            check.
        canonical_name_rule: Derives the index title after the transfer.
        journal_op: The destructive-journal op recorded on a genuine destruction
            (:data:`personalscraper.indexer.destructive_journal.OP_OVERWRITE`).
        journal_detail: Builds the French journal detail string from the source.
        bus_source: The ``ItemDispatched.source`` label for this family
            (``"dispatch.movie"`` / ``"dispatch.tv"``).
    """

    media_type: str
    existing_action: Literal["replaced", "merged"]
    transfer_fn: TransferFn
    identity_guard: IdentityGuard | None
    canonical_name_rule: CanonicalNameRule
    journal_op: str
    journal_detail: JournalDetail
    bus_source: str


def canonical_name_from_destination(result: DispatchResult, source_dir: Path) -> str:
    """Return the canonical index title for a completed dispatch.

    Shared by both families (their canonical-name rule is identical): a
    ``"moved"`` (new-media) action writes a brand-new folder, so the staging
    ``source_dir`` name is canonical; a supersede action (``"replaced"`` /
    ``"merged"``) writes into an existing on-disk folder whose casing is
    canonical (NTFS is case-insensitive, so rsync resolves to the pre-existing
    folder), so the destination's basename is recorded instead — otherwise the
    indexer title would drift to the staging spelling on every dispatch.

    Args:
        result: The DispatchResult with ``action`` and ``destination`` set.
        source_dir: The staging source directory being dispatched.

    Returns:
        The folder basename to persist as the index title.
    """
    if result.action != "moved" and result.destination is not None:
        return result.destination.name
    return source_dir.name


def replace_transfer(source: Path, dest: Path, capability: FilesystemCapability) -> TransferOutcome:
    """Movie transfer strategy: 3-phase crash-safe replace (REUSES ``_movie.replace``).

    A replace always supersedes the pre-existing on-disk folder in place, so a
    successful replace is, by definition, a destruction of the previous content
    (Phase 3 of :func:`personalscraper.dispatch._movie.replace` removes the
    backup copy). The underlying transfer primitive is unchanged; this adapter
    only maps its ``bool`` return onto the destroyed-content contract.

    Args:
        source: Staging movie directory (the new version).
        dest: Existing on-disk folder to replace.
        capability: Filesystem capability of the destination volume.

    Returns:
        A :class:`TransferOutcome`; ``destroyed`` mirrors ``success`` (a
        completed replace destroyed the previous folder).
    """
    from personalscraper.dispatch._movie import replace  # noqa: PLC0415  (lazy: avoid import cycle after P2.3 rewiring)

    success = replace(source, dest, capability=capability)
    return TransferOutcome(success=success, destroyed=success)


def merge_transfer(source: Path, dest: Path, capability: FilesystemCapability) -> TransferOutcome:
    """TV transfer strategy: backup/restore merge (REUSES ``_tv.merge``).

    A merge only destroys content when it supersedes an existing episode — a
    same-filename rsync overwrite, or a re-scrape rename whose ``(season,
    episode)`` key collides with an on-disk file under a different filename
    (purged by ``purge_episode_conflicts``). An add-only merge (source episodes
    the destination lacks) destroys nothing. The destroyed-content signal is
    computed BEFORE the merge (which consumes the source) and confirmed only if
    the merge succeeds — a failed merge restores every original, so nothing is
    net-destroyed. The underlying :func:`personalscraper.dispatch._tv.merge`
    transfer is unchanged.

    Args:
        source: Staging show directory (the new version).
        dest: Existing on-disk show directory to merge into.
        capability: Filesystem capability of the destination volume.

    Returns:
        A :class:`TransferOutcome`; ``destroyed`` is True only when the merge
        succeeded AND it superseded at least one existing episode.
    """
    from personalscraper.dispatch._tv import merge  # noqa: PLC0415  (lazy: avoid import cycle after P2.3 rewiring)

    would_destroy = _merge_supersedes_existing(source, dest)
    success = merge(source, dest, capability=capability)
    return TransferOutcome(success=success, destroyed=success and would_destroy)


def _merge_supersedes_existing(source: Path, dest: Path) -> bool:
    """Return True when merging ``source`` into ``dest`` would supersede content.

    Predicate (not a second merge implementation): it answers whether the merge
    would overwrite or purge any existing destination file, mirroring the two
    destruction paths of :func:`personalscraper.dispatch._tv.merge`:

    1. **Same relative path** already present on disk → the rsync merge
       overwrites it (a genuine destruction).
    2. **Same ``(season, episode)`` key under a different filename** in the same
       season subdir → ``purge_episode_conflicts`` moves the on-disk file to the
       backup and the source version replaces it (a re-scrape-rename destruction).

    An add-only merge (no shared path and no colliding episode key) returns
    ``False``. Reuses the same ``_extract_season_episode`` key parser the purge
    step uses, so the two stay in lock-step.

    Args:
        source: Staging show directory (the new version).
        dest: Existing on-disk show directory.

    Returns:
        True if the merge would supersede at least one existing destination file.
    """
    # Lazy-import mirrors purge_episode_conflicts (avoids a package-init cycle
    # between dispatcher and scraper).
    from personalscraper.scraper.episode_manager import _extract_season_episode  # noqa: PLC0415

    if not dest.is_dir():
        return False

    for src_file in source.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(source)
        # (1) Same relative path already on disk → rsync overwrites it.
        if (dest / rel).exists():
            return True
        # (2) Same (season, episode) key under a different filename in the same
        # season subdir → the purge step destroys the on-disk file.
        season, episode = _extract_season_episode(src_file.name)
        if season is None or episode is None:
            continue
        dest_season = dest / rel.parent
        if not dest_season.is_dir():
            continue
        for dest_file in dest_season.iterdir():
            if not dest_file.is_file():
                continue
            d_season, d_episode = _extract_season_episode(dest_file.name)
            if (d_season, d_episode) == (season, episode):
                return True
    return False


def _dispatch_item(
    dispatcher: Dispatcher,
    src: Path,
    category_id: str,
    spec: DispatchSpec,
) -> DispatchResult:
    """Dispatch one media item via the shared template, specialised by ``spec``.

    Shared scaffold for both families: resolve an existing on-disk copy
    (index + filesystem, year/external-id aware), and either supersede it in
    place (``spec.transfer_fn``, gated by free space, per-disk illegal-name
    capability, the optional §7 identity guard, and the §7.3 seed-obligation
    permit consult) or move new media to the most-free eligible disk. On a
    genuine destruction (``TransferOutcome.destroyed``) the template appends
    exactly one destructive-journal row (**F1**); an add-only merge journals
    nothing. Index write-through, best-effort outbox publish, and the
    ``ItemDispatched`` emit close the flow.

    Args:
        dispatcher: Dispatcher providing config, index, disks, permit/recorder,
            and the event bus.
        src: Source (staging) media directory to dispatch.
        category_id: Category ID from the classifier (e.g. ``"movies"``).
        spec: Per-family :class:`DispatchSpec` selecting replace vs merge.

    Returns:
        A :class:`DispatchResult` describing the operation.
    """
    # Lazy-import the two shared helpers that live in ``_movie`` so this module
    # stays free of a module-scope ``_movie`` import (which would cycle once
    # ``_movie`` is rewired onto this template in P2.3).
    from personalscraper.dispatch._movie import (  # noqa: PLC0415
        _disk_root_for,
        _is_skipped_for_illegal_names,
    )

    result = DispatchResult(source=src)

    # Disk statuses keyed by disk ID for the resolver / free-space gate.
    disk_statuses = [get_disk_status(c) for c in dispatcher._disk_configs]
    free_space_by_id = {s.config.id: s.free_space_gb if s.is_mounted else 0.0 for s in disk_statuses}
    item_size_gb = _transfer.dir_size_gb(src)

    # Existing-copy detection, validated against the filesystem (index can drift
    # when folders are moved manually; the resolver is year/external-id aware so
    # remakes/revivals do not collide — do not regress the dispatch_path fix).
    existing = dispatcher._resolve_existing_on_filesystem(src.name, spec.media_type, media_dir=src)

    # Family verb for the skip / dry-run reason strings (derived, not stored).
    verb = "replace" if spec.existing_action == "replaced" else "merge"

    if existing:
        dest = Path(existing.path)
        result.disk = existing.disk
        result.destination = dest

        # Free-space gate for the in-place supersede.
        threshold = max(
            dispatcher.config.thresholds.min_free_space_disk_gb,
            item_size_gb * 1.5,
        )
        disk_free = free_space_by_id.get(existing.disk, 0.0)
        if disk_free < threshold:
            result.action = "skipped"
            result.reason = f"Disk {existing.disk} full, cannot {verb}"
            return result

        # Resolve the destination disk capability, then gate illegal filenames
        # against THAT capability (None on POSIX → no restriction). Resolved
        # before the dry-run branch so dry-run is a faithful preview.
        cap = dispatcher._disk_capabilities.get(existing.disk, NTFS_MACFUSE)
        if _is_skipped_for_illegal_names(result, src, cap):
            return result

        # §7 identity guard — a supersede destroys the on-disk target, so verify
        # by provider-ID that it is the SAME media before touching it. Movie
        # replace and TV merge each wire a guard; a family with ``None`` skips
        # the check. Checked before the dry-run branch so the preview reports
        # the block too.
        if spec.identity_guard is not None:
            identity_conflict = spec.identity_guard(src, dest)
            if identity_conflict is not None:
                result.action = "skipped"
                result.reason = identity_conflict
                return result

        if dispatcher.dry_run:
            result.action = spec.existing_action
            result.reason = f"[DRY RUN] Would {verb} on {existing.disk}"
            return result

        # Three-state seedtime-aware policy (DESIGN §7.3): the supersede deletes
        # OLD on-disk content. If a live seed obligation on it is unmet, the new
        # real media still wins (O3) — but the breach is recorded, never silent.
        #
        # F2: the consult is fail-open. A permit whose may_delete raises must NOT
        # crash the dispatch — treat the error as ALLOW and do NOT mark_breach on
        # an errored consult (a breach is only recorded on a positive VETO).
        try:
            decision = dispatcher._permit.may_delete(dest)
        except Exception as exc:
            log.warning("dispatch.permit_error", path=str(dest), error=str(exc), action=verb)
            decision = ALLOW
        if decision is not ALLOW:
            log.warning("acquire.hnr_risk", path=str(dest), reason=str(decision), action=verb)
            dispatcher._recorder.mark_breach(dest)

        # Write-before-move (DESIGN §7.2): record the obligation for the NEWLY
        # dispatched media BEFORE the FS move, so a crash mid-move never loses
        # the safety constraint. Fail-soft (never raises).
        acquired_events = dispatcher._recorder.record_dispatch(staging_source=src, dispatched_dest=dest)
        outcome = spec.transfer_fn(src, dest, cap)
        result.action = spec.existing_action if outcome.success else "error"
        if outcome.success:
            # D2-A — announce the media retired at dispatch on the live feed once
            # it has actually landed. The events are opaque here (the recorder
            # built them, dispatch just emits them).
            for _evt in acquired_events:
                dispatcher._event_bus.emit(_evt)
            # §7 / Star City — append-only trail of the overwrite: journal the
            # destruction ONCE, and ONLY on a genuine destruction (F1). An
            # add-only merge destroyed nothing and journals nothing. Best-effort
            # (never breaks the dispatch), guarded by a resolved journal DB.
            if outcome.destroyed:
                _journal_db = dispatcher.config.indexer.db_path
                if _journal_db is not None:
                    record_destruction(
                        _journal_db,
                        op=spec.journal_op,
                        path=dest,
                        actor="dispatch",
                        detail=spec.journal_detail(src),
                    )
    else:
        # New media — move to the most-free eligible disk via the resolver.
        target_disk = resolver.pick_disk_for(
            dispatcher.config,
            category_id,
            free_space_by_id,
            dispatcher.config.thresholds.min_free_space_disk_gb,
            item_size_gb,
        )
        if not target_disk:
            result.action = "skipped"
            result.reason = f"No disk with enough space for category '{category_id}'"
            return result

        dest = resolver.folder_for(dispatcher.config, target_disk, category_id) / src.name
        result.disk = target_disk.id
        result.destination = dest

        cap = dispatcher._disk_capabilities.get(target_disk.id, NTFS_MACFUSE)
        if _is_skipped_for_illegal_names(result, src, cap):
            return result

        if dispatcher.dry_run:
            result.action = "moved"
            result.reason = f"[DRY RUN] Would move to {target_disk.id}"
            return result

        # Write-before-move (DESIGN §7.2): the new media may itself be a live
        # seed, so record its obligation BEFORE the FS move. No permit consult
        # here — there is no pre-existing library content to delete.
        acquired_events = dispatcher._recorder.record_dispatch(staging_source=src, dispatched_dest=dest)
        success = dispatcher._move_new(src, dest, capability=cap)
        result.action = "moved" if success else "error"
        if success:
            for _evt in acquired_events:
                dispatcher._event_bus.emit(_evt)

    # Index write-through (canonical casing rule per family; identical today).
    if result.action in (spec.existing_action, "moved") and result.destination:
        canonical_name = spec.canonical_name_rule(result, src)
        dispatcher.index.add(
            IndexEntry(
                name=canonical_name,
                disk=result.disk or "",
                category=category_id,
                path=str(result.destination),
                media_type=spec.media_type,
            )
        )

    # Best-effort outbox publish for the indexer (DESIGN §9.1).
    if result.action in (spec.existing_action, "moved") and result.destination is not None:
        _db_path = dispatcher.config.indexer.db_path
        assert _db_path is not None, "indexer.db_path must be resolved"
        resolved = disk_id_for_path(result.destination, _db_path)
        if resolved is not None:
            disk_id, rel_path = resolved
            size_bytes, max_mtime = _transfer.dir_stats(result.destination)
            publish_event(
                disk_id,
                op="move",
                payload={
                    "src_rel_path": "",
                    "dst_rel_path": rel_path,
                    "filename": result.destination.name,
                    "size_bytes": size_bytes,
                    "mtime_ns": max_mtime,
                },
                db_path=_db_path,
                source="dispatch",
            )

    # Bus emit — only on real completed transfers. Dry-run is excluded because
    # the catalog defines ItemDispatched as the record of completed transfers;
    # the action enum has no "skipped" value so dry-run logically cannot emit.
    if not dispatcher.dry_run and result.action in ("moved", spec.existing_action) and result.destination is not None:
        target_disk_path = _disk_root_for(dispatcher, result.disk)
        # ``result.action`` is typed ``str`` on DispatchResult; the guard above
        # restricts it to the three ItemDispatched literals, but narrowing a
        # ``str`` through ``in`` with a non-literal tuple element
        # (``spec.existing_action``) is not portable across mypy versions.
        # Re-derive the literal explicitly instead of casting: the value is
        # ``"moved"`` iff it is not the family's ``existing_action``. The result
        # is a genuine literal join every mypy computes identically — no cast,
        # no ignore directive. Behaviour is identical to passing ``result.action``.
        dispatched_action: Literal["moved", "merged", "replaced"] = (
            "moved" if result.action == "moved" else spec.existing_action
        )
        dispatcher._event_bus.emit(
            ItemDispatched(
                source=spec.bus_source,
                item=src.name,
                target_disk=target_disk_path,
                category_id=category_id,
                action=dispatched_action,
            ),
        )

    return result
