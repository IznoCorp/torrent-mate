"""Classify completed torrents that ingest would transiently skip.

The watcher's pipeline-trigger predicate is ``completed − ingested −
seed_pure``. Torrents that ingest skips for a **transient** reason — seeding
ratio not reached, source content unavailable, staging disk full — are never
marked ingested, so they stayed in that work set forever and the watcher kept
firing pipeline runs that only re-skipped them (« Pipeline » rows with empty
results, live incident 2026-07-15).

This module is the single source of truth for that transient-skip predicate:
it mirrors ingest's own guards (``run_ingest`` reasons ``ratio_below_threshold``,
``content_missing``, ``insufficient_space``) WITHOUT touching ingest semantics —
a deferred torrent is only excluded from the watcher's trigger set while its
skip condition still holds, and re-enters the moment the condition may have
cleared (ratio climbs, volume remounts, space frees). Nothing is ever marked
done, so no media can be lost.

Import direction: ``ingest/`` (triage layer). ``acquire/watcher.py`` stays
pure — the deferred set reaches it as data via ``WatcherInput``; only the
composition layers (``commands/watch.py``, web routes) call this module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.ingest.ingest import _check_disk_space
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.conf.models.config import Config

log = get_logger("ingest.deferral")

#: Deferral reasons — mirror the ingest skip-event ``details.reason`` values.
REASON_RATIO = "ratio_below_threshold"
REASON_CONTENT_MISSING = "content_missing"
REASON_INSUFFICIENT_SPACE = "insufficient_space"


def classify_deferrals(
    completed: Iterable[TorrentItem],
    *,
    min_ratio: float,
    ingest_dir: Path,
    min_free_gb: int,
    staging_probe_dirs: Sequence[Path] = (),
    exclude_hashes: frozenset[str] = frozenset(),
    disk_space_ok: Callable[[Path, int, int], bool] = _check_disk_space,
) -> dict[str, str]:
    """Map each transiently-skippable completed torrent to its deferral reason.

    A torrent is deferred when ingest would skip it for a condition that can
    clear on its own:

    - ``ratio_below_threshold`` — ``min_ratio > 0`` and the live ratio is
      below it (self-healing: the ratio only climbs).
    - ``content_missing`` — the client's ``content_path`` is unknown or absent
      on disk AND no staging copy exists (a staging copy means a run WOULD
      make progress via the ``found_in_staging`` marker, so it is not deferred).
    - ``insufficient_space`` — the staging disk lacks room for the torrent's
      declared size (approximation of ingest's on-disk measure; conservative
      either way, re-evaluated every cycle).

    Reasons are checked in ingest's own order so the reported reason matches
    what a run would actually log first.

    Args:
        completed: Live completed torrents from ``get_completed()``.
        min_ratio: ``config.ingest.min_ratio`` (0.0 disables the ratio guard).
        ingest_dir: Resolved ingest staging directory (space check target).
        min_free_gb: ``config.thresholds.min_free_space_staging_gb``.
        staging_probe_dirs: Directories where ingest would look for an
            already-staged copy (movies / tvshows staging dirs + ingest dir).
        exclude_hashes: Hashes to skip entirely (already ingested or
            seed-pure — they are outside the trigger set anyway).
        disk_space_ok: Space predicate, injectable for tests. Defaults to
            ingest's own ``_check_disk_space``.

    Returns:
        ``{info_hash: reason}`` for every deferred torrent (possibly empty).
    """
    deferred: dict[str, str] = {}
    for torrent in completed:
        if torrent.hash in exclude_hashes:
            continue
        if min_ratio > 0.0 and (torrent.ratio or 0.0) < min_ratio:
            deferred[torrent.hash] = REASON_RATIO
            continue
        content = torrent.content_path
        if content is None or not Path(content).exists():
            staged = any((d / torrent.name).exists() for d in staging_probe_dirs)
            if not staged:
                deferred[torrent.hash] = REASON_CONTENT_MISSING
                continue
        try:
            if not disk_space_ok(ingest_dir, torrent.size_bytes, min_free_gb):
                deferred[torrent.hash] = REASON_INSUFFICIENT_SPACE
                continue
        except OSError:
            # Space probe failed (ingest dir unreachable) — treat as deferred
            # so the watcher does not spin on a run that cannot transfer.
            deferred[torrent.hash] = REASON_INSUFFICIENT_SPACE
            continue
    return deferred


def deferral_probe_dirs(config: Config) -> list[Path]:
    """Return the staging directories ingest probes for an existing copy.

    Mirrors ``run_ingest``'s ``found_in_staging`` lookup (movies staging dir,
    tvshows staging dir, ingest dir) so the deferral predicate and ingest
    agree on what counts as « already staged ».

    Args:
        config: Validated application config.

    Returns:
        List of absolute directories (existence not required).
    """
    from personalscraper.conf.staging import (  # noqa: PLC0415
        find_by_file_type,
        find_ingest_dir,
        folder_name,
        staging_path,
    )
    from personalscraper.core.media_types import FileType  # noqa: PLC0415

    staging_root = config.paths.staging_dir
    ingest_dir = staging_path(config, find_ingest_dir(config))
    movies = staging_root / folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows = staging_root / folder_name(find_by_file_type(config, FileType.TVSHOW))
    return [movies, tvshows, ingest_dir]
