"""Enrich scan mode driver."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Literal

from personalscraper._fs_utils import is_apple_double
from personalscraper.core.artwork_naming import artwork_inventory_from_names
from personalscraper.core.completeness import nfo_status as _core_nfo_status
from personalscraper.core.media_types import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS
from personalscraper.indexer.mediainfo import MediaInfoUnavailableError, MediaInfoWrapper
from personalscraper.indexer.release_linker import link_file_to_release
from personalscraper.indexer.schema import ArtworkInventory, DiskRow, MediaStreamRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

__all__ = [
    "MediaInfoWrapper",
    "os",
    "_check_nfo_status",
    "_enrich_one_file",
    "_inventory_artwork",
    "_purge_non_video_stream_rows",
    "_resolve_item_root_dir",
    "_scan_disk_enrich",
]

# ---------------------------------------------------------------------------
# Item-root resolution + NFO/NA constants
# ---------------------------------------------------------------------------

# Artwork filename detection is owned by ``core.artwork_naming`` (the ONE union
# of bare/Kodi/scraper/MediaElch spellings). Both scan modes classify through it
# so ``artwork_json`` is written identically regardless of scan path (INDEXER-03).


# Subfolders whose contents must NEVER drive the parent item's NFO/artwork
# state. ``.actors`` (Kodi actor thumbnails) and Plex extras folders contain
# only sidecars; scanning them returns "missing" / empty-inventory and would
# silently overwrite the correct values written by the actual release dir.
_ITEM_ROOT_SKIP_DIRS: frozenset[str] = frozenset(
    {
        # Kodi / Plex sentinel sub-folders (English convention).
        ".actors",
        "extras",
        "behind the scenes",
        "deleted scenes",
        "featurettes",
        "interviews",
        "scenes",
        "shorts",
        "trailers",
        "other",
        # French equivalents commonly used in this project's library.
        # ``Bonus`` / ``Boni`` / ``Inédits`` hold show extras and must
        # not drive the item's NFO/artwork state — the show-level NFO
        # lives at the show root, not inside the bonus folder.
        # ``Films`` is used to nest a movie sub-collection under a
        # show root (e.g. Lucky Luke spin-off films inside the series
        # directory) — same skip rationale.
        "bonus",
        "boni",
        "inédits",
        "inedits",
        "films",
    }
)

# TV-show season folder names — canonical SSOT from naming_patterns.
from personalscraper.naming_patterns import SEASON_DIR_RE as _TV_SEASON_DIR_RE  # noqa: E402

# Categories that do not follow the Kodi NFO convention. For these,
# ``nfo_status='missing'`` is a structural false-positive — there is no
# ``movie.nfo`` / ``tvshow.nfo`` to find because the format does not
# specify one. Setting nfo_status to NULL ("not applicable") is more
# faithful than reporting them as broken in library-report.
_NFO_NA_CATEGORIES: frozenset[str] = frozenset({"audiobooks"})


def _resolve_item_root_dir(file_path: Path) -> Path | None:
    """Return the directory whose NFO + artwork describe ``file_path``'s item.

    Movies hold their NFO and artwork next to the video file (release dir).
    TV shows hold the show-level NFO and artwork at the show root, NOT inside
    each ``Saison NN/`` season folder. ``.actors/`` (Kodi) and Plex extras
    sub-folders are sidecar-only and must never drive the item's status.

    Args:
        file_path: Absolute path of the media file being enriched.

    Returns:
        The directory to scan for NFO + artwork, or ``None`` to indicate the
        caller must SKIP the NFO/artwork DB update entirely (sidecar folder
        whose absence of NFO/artwork must not overwrite the correct values
        written by other files of the same item).
    """
    parent = file_path.parent
    if parent.name.lower() in _ITEM_ROOT_SKIP_DIRS:
        return None
    if _TV_SEASON_DIR_RE.match(parent.name):
        return parent.parent
    return parent


def _inventory_artwork(parent_dir: str) -> ArtworkInventory | None:
    """Scan *parent_dir* for known artwork filenames and return an :class:`ArtworkInventory`.

    Detection is delegated to the canonical owner
    (:func:`personalscraper.core.artwork_naming.artwork_inventory_from_names`) so
    this enrich scan mode and the full/item-stage scan mode write an identical
    ``artwork_json`` for the same directory (INDEXER-03). Only presence is
    checked — no content validation. Season posters (``seasonNN-*``) are excluded
    from item-level artwork, and MediaElch's ``-logo``/``-disc`` short aliases and
    the Kodi ``folder.jpg`` are recognized, all via the shared union.

    The directory is listed here (rather than in ``core``) so a transient
    :exc:`OSError` is caught and reported as ``None`` — the caller must skip the
    DB column update in that case so previously-valid data is not overwritten.

    Args:
        parent_dir: Absolute path of the directory to scan.

    Returns:
        :class:`ArtworkInventory` instance reflecting what artwork files exist,
        or ``None`` when the directory is not readable (transient OS error).
    """
    try:
        with os.scandir(parent_dir) as it:
            names = [entry.name for entry in it if entry.is_file()]
    except OSError as exc:
        # Directory temporarily unreadable — preserve the existing DB value.
        log.warning(
            "indexer.enrich.artwork_inventory_failed",
            parent_dir=parent_dir,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None

    return ArtworkInventory.from_presence(artwork_inventory_from_names(names))


def _purge_non_video_stream_rows(conn: sqlite3.Connection) -> int:
    """Drop ``media_stream`` rows attached to non-video files.

    pymediainfo on a ``.jpg`` reports a single ``video`` track of codec
    ``JPEG``; on a ``.srt`` it reports a ``subtitle`` track of codec
    ``SubRip``. Both are useless for the indexer (we never query them
    and the linker / recommender ignore non-video extensions) and were
    only ever inserted by the pre-extension-skip enrich code path.

    The new producer never inserts these rows (the wrapper is replaced
    by ``None`` for non-video extensions in ``_scan_disk_enrich``), so
    the cleanup is a one-shot pass: deleting these rows is idempotent
    and a no-op once the legacy data is gone. Called at the start of
    every enrich pass to converge the DB without a separate command.

    Args:
        conn: Open SQLite connection.

    Returns:
        Number of stream rows removed.
    """
    # Build the WHERE LIKE clause from VIDEO_EXTENSIONS so the cleanup
    # tracks the actual extension whitelist used by the enrich loop.
    placeholders = " OR ".join(["LOWER(mf.filename) LIKE ?"] * len(_VIDEO_EXTENSIONS))
    params = [f"%.{ext}" for ext in _VIDEO_EXTENSIONS]
    cursor = conn.execute(
        f"""
        DELETE FROM media_stream
        WHERE file_id IN (
            SELECT mf.id FROM media_file mf WHERE NOT ({placeholders})
        )
        """,  # noqa: S608 — placeholders comes from a hard-coded constant
        params,
    )
    purged: int = cursor.rowcount
    if purged > 0:
        log.info("indexer.enrich.purged_non_video_streams", purged=purged)
    return purged


def _check_nfo_status(parent_dir: str) -> Literal["missing", "invalid", "valid"] | None:
    """Return the strict NFO-validity status for *parent_dir* (the ONE definition).

    §9 / VERIFY-MAINTENANCE-03: the enrich scan mode's ``nfo_status`` column now
    converges on the single strict NFO definition shared by the scraper fast-skip,
    ``verify`` and the full-scan item stage — content validity, not mere existence.
    Validity is delegated to :func:`personalscraper.core.completeness.nfo_status`
    (which itself delegates ``complete`` to
    :func:`personalscraper.nfo_utils.is_nfo_complete`: parseable XML + at least one
    non-placeholder ``<uniqueid>``). AppleDouble sidecars (``._*.nfo`` — binary
    xattr blobs, not real NFOs) are skipped.

    - ``'valid'`` — at least one real ``.nfo`` in *parent_dir* is content-valid.
    - ``'invalid'`` — one or more real ``.nfo`` files are present but none is
      content-valid (unparseable / truncated / no non-placeholder ``<uniqueid>``).
    - ``'missing'`` — no real ``.nfo`` file found.
    - ``None`` — the directory scan raised an :exc:`OSError` (transient permission
      error or filesystem hiccup); the caller must skip the DB column update so that
      previously-valid data is not overwritten.

    Args:
        parent_dir: Absolute path of the directory to inspect.

    Returns:
        ``'valid'`` / ``'invalid'`` / ``'missing'`` per the above, or ``None`` when
        the directory is not readable.
    """
    try:
        with os.scandir(parent_dir) as it:
            candidates = [
                Path(entry.path)
                for entry in it
                if entry.name.lower().endswith(".nfo") and not is_apple_double(entry.name)
            ]
    except OSError as exc:
        # Directory temporarily unreadable — preserve the existing DB value.
        log.warning(
            "indexer.enrich.nfo_check_failed",
            parent_dir=parent_dir,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None
    if not candidates:
        return "missing"
    if any(_core_nfo_status(nfo).complete for nfo in candidates):
        return "valid"
    return "invalid"


def _enrich_one_file(
    conn: sqlite3.Connection,
    file_id: int,
    file_path: Path,
    item_id: int | None,
    wrapper: MediaInfoWrapper | None,
    nfo_artwork_cache: dict[str, tuple[str | None, ArtworkInventory | None]] | None = None,
) -> None:
    """Enrich a single ``media_file`` row with streams, NFO status, artwork, and oshash.

    Performs four enrichment steps in order:

    1. **Stream extraction** — if *wrapper* is not ``None`` and the file is large
       enough, call :meth:`~personalscraper.indexer.mediainfo.MediaInfoWrapper.extract_streams`
       and INSERT the resulting :class:`~personalscraper.indexer.schema.MediaStreamRow` objects
       into ``media_stream``, replacing any existing rows for this ``file_id``.
    2. **NFO presence check** — inspect the parent directory for ``.nfo`` files and
       update ``media_item.nfo_status`` when *item_id* is not ``None``.
    3. **Artwork inventory** — scan the parent directory for known artwork filenames
       and update ``media_item.artwork_json`` when *item_id* is not ``None``.
    4. **OSHash retry** — if the current ``media_file.oshash`` is ``NULL`` and the
       file extension is eligible (see
       :data:`~personalscraper.indexer.fingerprint.OSHASH_EXTENSIONS`), attempt to
       compute and persist the hash.  Fail-soft: an :exc:`OSError` is logged at
       WARNING and swallowed so ``enriched_at`` is still updated.

    Finally, set ``media_file.enriched_at`` to the current epoch seconds.

    Args:
        conn: Open SQLite connection.  Caller is responsible for committing.
        file_id: PK of the ``media_file`` row to enrich.
        file_path: Absolute :class:`~pathlib.Path` to the media file.
        item_id: PK of the owning ``media_item``, or ``None`` if release linkage
            has not been performed yet.
        wrapper: Configured :class:`~personalscraper.indexer.mediainfo.MediaInfoWrapper`
            instance, or ``None`` when pymediainfo is unavailable.
        nfo_artwork_cache: Optional dict keyed by parent directory, with values
            ``(nfo_status, artwork)``. Lets the caller share NFO + artwork
            results across all files in the same directory — a typical media
            folder holds 1 video + 3-10 sidecars and the FS scans for those
            checks are identical for every file. ``None`` disables caching
            (legacy behaviour, used by callers that do not see batches).
    """
    now_s = int(time.time())
    # Resolve the directory whose NFO + artwork describe the owning item.
    # This may differ from ``file_path.parent`` for TV episodes (whose
    # show-level metadata lives one level up) and is ``None`` for sidecar
    # folders (.actors/, Plex extras) — those must NOT update item state.
    item_root = _resolve_item_root_dir(file_path)
    parent_dir = str(item_root) if item_root is not None else None

    # --- Step 1: stream extraction ---
    if wrapper is not None:
        try:
            stream_rows: list[MediaStreamRow] = wrapper.extract_streams(file_path)
        except Exception:  # noqa: BLE001
            # Corrupt / unreadable file — skip stream extraction but still update
            # enriched_at so we do not re-attempt on every future enrich run.
            stream_rows = []

        if stream_rows:
            # Delete stale stream rows before re-inserting to keep the table clean.
            conn.execute("DELETE FROM media_stream WHERE file_id = ?", (file_id,))
            # Use a global 0-based index (enumerate) rather than the per-kind index
            # from MediaStreamRow.idx, which may collide across track types when the
            # UNIQUE(file_id, idx) constraint is file-scoped.
            conn.executemany(
                """
                INSERT INTO media_stream (file_id, idx, kind, codec, lang,
                    channels, width, height, duration_ms, bitrate,
                    hdr_format, is_atmos, is_default, forced, format)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        file_id,
                        global_idx,
                        row.kind,
                        row.codec,
                        row.lang,
                        row.channels,
                        row.width,
                        row.height,
                        row.duration_ms,
                        row.bitrate,
                        row.hdr_format,
                        None if row.is_atmos is None else int(row.is_atmos),
                        None if row.is_default is None else int(row.is_default),
                        None if row.forced is None else int(row.forced),
                        row.format,
                    )
                    for global_idx, row in enumerate(stream_rows)
                ],
            )

    # --- Steps 2 + 3: NFO status and artwork (only when release linkage exists
    # AND the file lives in a directory that legitimately describes the item).
    # Sidecar folders (.actors/, Extras/, etc.) are skipped: their absence of
    # NFO/artwork must not overwrite the correct state set by sibling files. ---
    if item_id is not None and parent_dir is not None:
        if nfo_artwork_cache is not None and parent_dir in nfo_artwork_cache:
            nfo_status, artwork = nfo_artwork_cache[parent_dir]
        else:
            from personalscraper.indexer.scanner import _modes as modes_api  # noqa: PLC0415

            nfo_status = modes_api._check_nfo_status(parent_dir)
            artwork = modes_api._inventory_artwork(parent_dir)
            if nfo_artwork_cache is not None:
                nfo_artwork_cache[parent_dir] = (nfo_status, artwork)

        # Categories that do not use the Kodi NFO convention (audiobooks
        # have no ``movie.nfo`` / ``tvshow.nfo`` equivalent) must not be
        # flagged as ``missing`` just because no .nfo file is present.
        # Suppress the NFO update in that case so ``nfo_status`` stays
        # NULL — interpreted as "not applicable" by readers.
        cat_row = conn.execute(
            "SELECT category_id FROM media_item WHERE id = ?",
            (item_id,),
        ).fetchone()
        if cat_row is not None and cat_row[0] in _NFO_NA_CATEGORIES:
            nfo_status = None

        # Skip column updates when either scan returned None — a transient OS error
        # occurred and the existing DB values must be preserved rather than overwritten
        # with a spurious 'missing' / empty-inventory result.
        if nfo_status is not None and artwork is not None:
            conn.execute(
                "UPDATE media_item SET nfo_status = ?, artwork_json = ? WHERE id = ?",
                (nfo_status, artwork.model_dump_json(), item_id),
            )
        elif nfo_status is not None:
            conn.execute(
                "UPDATE media_item SET nfo_status = ? WHERE id = ?",
                (nfo_status, item_id),
            )
        elif artwork is not None:
            conn.execute(
                "UPDATE media_item SET artwork_json = ? WHERE id = ?",
                (artwork.model_dump_json(), item_id),
            )

    # --- Step 4: OSHash retry (DEV #51) ---
    # Stage-A rows and rows where a previous hash attempt failed carry
    # oshash=NULL.  Retry here so the enrich pass can heal NULL rows
    # without waiting for a full re-scan.  Only eligible video extensions
    # are attempted; non-video files are skipped (oshash is not applicable).
    # Fail-soft: OSError is logged at WARNING and oshash stays NULL so that
    # enriched_at is still updated and the file is not re-queued infinitely.
    current_row = conn.execute("SELECT oshash FROM media_file WHERE id = ?", (file_id,)).fetchone()
    if current_row is not None and current_row[0] is None:
        suffix = file_path.suffix.lstrip(".").lower()
        from personalscraper.indexer import fingerprint as _fp  # noqa: PLC0415

        if suffix in _fp.OSHASH_EXTENSIONS:
            try:
                new_oshash = _fp.oshash(file_path)
                if new_oshash:
                    conn.execute(
                        "UPDATE media_file SET oshash = ? WHERE id = ?",
                        (new_oshash, file_id),
                    )
                    log.info(
                        "indexer.enrich.oshash_recomputed",
                        file_id=file_id,
                        oshash=new_oshash,
                    )
            except OSError as exc:
                log.warning(
                    "indexer.enrich.oshash_retry_failed",
                    file_id=file_id,
                    path=str(file_path),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

    # --- Set enriched_at ---
    conn.execute(
        "UPDATE media_file SET enriched_at = ? WHERE id = ?",
        (now_s, file_id),
    )


def _scan_disk_enrich(
    conn: sqlite3.Connection,
    disk: DiskRow,
    budget_seconds: float | None,
    started_at_monotonic: float,
    budget_exhausted: list[bool],
    scan_run_id: int,
    quick_enrich: bool = False,
) -> None:
    """Run the enrich-mode pass for a single disk.

    Iterates ``media_file`` rows on this disk where ``enriched_at IS NULL`` or
    ``enriched_at < (mtime_ns / 1_000_000_000)`` (file has been modified since
    last enrichment), in priority order: files whose owning ``media_item`` was
    most recently modified first (``media_item.date_modified DESC``), with
    files that have no release linkage last.

    Per-file enrichment:

    1. Recompute file path from ``path.rel_path`` and ``media_file.filename``.
    2. Extract media streams via :class:`~personalscraper.indexer.mediainfo.MediaInfoWrapper`
       (skipped silently if ``libmediainfo`` is not installed).
    3. Check NFO presence in the file's parent directory.
    4. Inventory artwork in the file's parent directory.
    5. Update ``media_file.enriched_at`` to the current epoch seconds.
    6. **Commit after each file** so partial progress survives interruption.

    If the *budget_seconds* wall-clock limit is reached between files, the loop
    exits early and ``budget_exhausted[0]`` is set to ``True``.  Any files not
    yet enriched retain ``enriched_at=NULL`` and will be picked up by the next
    enrich run.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` to enrich.
        budget_seconds: Maximum wall-clock seconds for the entire enrich pass.
            ``None`` = unlimited.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_exhausted: Single-element flag; set to ``True`` when the budget
            is exceeded.  Mutated in-place so the caller can check it after return.
        scan_run_id: PK of the active ``scan_run`` row (used for stats update on
            budget exhaustion).
        quick_enrich: When ``True``, uses ``parse_speed=0.5`` for pymediainfo
            (faster but may skip optional tags).  Default ``False`` → ``parse_speed=1.0``.
    """
    if disk.mount_path is None:
        log.warning("indexer.enrich.disk_no_mount", disk_id=disk.id, label=disk.label)
        return

    parse_speed: float = 0.5 if quick_enrich else 1.0

    # Attempt to create the pymediainfo wrapper; degrade gracefully if unavailable.
    wrapper: MediaInfoWrapper | None
    try:
        from personalscraper.indexer.scanner import _modes as modes_api  # noqa: PLC0415

        wrapper = modes_api.MediaInfoWrapper(min_size_mb=0, parse_speed=parse_speed)
    except MediaInfoUnavailableError:
        log.warning(
            "indexer.enrich.mediainfo_unavailable",
            disk_id=disk.id,
            label=disk.label,
        )
        wrapper = None

    # Query files that need enrichment, ordered by owning item's date_modified DESC.
    # Files with no release linkage (release_id IS NULL) sort last.
    conn.row_factory = sqlite3.Row
    pending = conn.execute(
        """
        SELECT mf.id            AS file_id,
               mf.filename      AS filename,
               mf.mtime_ns      AS mtime_ns,
               mf.release_id    AS release_id,
               p.rel_path       AS rel_path,
               mr.item_id       AS item_id
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
          LEFT JOIN media_release mr ON mr.id = mf.release_id
         WHERE p.disk_id = ?
           AND mf.deleted_at IS NULL
           AND (
                 mf.enriched_at IS NULL
              OR mf.enriched_at < (mf.mtime_ns / 1000000000)
           )
         ORDER BY
               CASE WHEN mf.release_id IS NULL THEN 1 ELSE 0 END ASC,
               (
                 SELECT mi.date_modified
                   FROM media_item mi
                  WHERE mi.id = mr.item_id
               ) DESC NULLS LAST
        """,
        (disk.id,),
    ).fetchall()
    conn.row_factory = None

    files_enriched = 0
    files_since_commit = 0
    # NFO + artwork results are identical for every file in the same parent
    # directory — cache them per pass so a folder with one video and ten
    # sidecars pays the FS scan cost once instead of eleven times.
    nfo_artwork_cache: dict[str, tuple[str | None, ArtworkInventory | None]] = {}
    # Batch ``conn.commit()`` every N files: each commit triggers a fsync(),
    # which is the dominant cost on the sidecar fast path now that
    # pymediainfo and ``release_linker`` are off the per-file critical path.
    # Crash safety: at most COMMIT_EVERY_N_FILES files of work are lost; the
    # next pass picks them up via ``enriched_at IS NULL``.
    _COMMIT_EVERY_N_FILES = 100

    for row in pending:
        # Budget check at each file boundary.
        if budget_seconds is not None:
            elapsed = time.monotonic() - started_at_monotonic
            if elapsed >= budget_seconds:
                log.info(
                    "indexer.enrich.budget_exhausted",
                    disk_id=disk.id,
                    label=disk.label,
                    files_enriched=files_enriched,
                    elapsed=elapsed,
                )
                conn.execute(
                    "UPDATE scan_run SET stats_json = ? WHERE id = ?",
                    (json.dumps({"budget_exhausted": True, "files_enriched": files_enriched}), scan_run_id),
                )
                # Drain any pending batched per-file work before exiting so
                # the budget cut-off does not silently lose the last <100 files.
                conn.commit()
                budget_exhausted[0] = True
                return

        # Reconstruct absolute file path from disk mount + rel_path + filename.
        rel_path: str = row["rel_path"]
        filename: str = row["filename"]
        if rel_path == ".":
            file_path = Path(disk.mount_path) / filename
        else:
            file_path = Path(disk.mount_path) / rel_path / filename

        file_id: int = row["file_id"]
        item_id: int | None = row["item_id"]
        release_id: int | None = row["release_id"]

        # Skip pymediainfo for non-video extensions: ``libmediainfo`` is the
        # parse bottleneck (~500 ms-1 s per call) and accounts for >80% of
        # the wall clock on a typical library where the bulk of files are
        # ``.jpg`` / ``.nfo`` / ``.srt`` sidecars. Pass a ``None`` wrapper to
        # ``_enrich_one_file`` for these so it skips stream extraction but
        # still runs the NFO presence check, artwork inventory, and
        # ``enriched_at`` update — the sidecar still needs to be marked as
        # processed so the next pass does not pick it up again.
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        effective_wrapper = wrapper if ext in _VIDEO_EXTENSIONS else None

        if not file_path.exists():
            # File no longer on disk — skip without updating enriched_at so the
            # scanner's miss-strikes logic handles it on the next full/incremental pass.
            log.debug(
                "indexer.enrich.file_missing",
                file_id=file_id,
                path=str(file_path),
            )
            continue

        # Stage B linkage: when a file has not been attached to a release yet
        # (cold Stage A inserts release_id=NULL), resolve the owning item via
        # the dispatch_path attribute chain and create the release / season /
        # episode rows on demand. Item id is then re-derived for downstream
        # NFO + artwork updates in _enrich_one_file.
        if release_id is None:
            try:
                new_release_id = link_file_to_release(conn, file_id, str(file_path))
            except sqlite3.Error as exc:
                log.warning(
                    "indexer.enrich.release_link_failed",
                    file_id=file_id,
                    path=str(file_path),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                new_release_id = None

            if new_release_id is not None:
                resolved = conn.execute(
                    "SELECT mr.item_id, s.item_id AS show_item_id "
                    "FROM media_release mr "
                    "LEFT JOIN episode e ON e.id = mr.episode_id "
                    "LEFT JOIN season s ON s.id = e.season_id "
                    "WHERE mr.id = ?",
                    (new_release_id,),
                ).fetchone()
                if resolved is not None:
                    item_id = resolved[0] if resolved[0] is not None else resolved[1]

        try:
            from personalscraper.indexer.scanner import _modes as modes_api  # noqa: PLC0415

            modes_api._enrich_one_file(
                conn,
                file_id,
                file_path,
                item_id,
                effective_wrapper,
                nfo_artwork_cache=nfo_artwork_cache,
            )
        except Exception:  # noqa: BLE001
            log.warning(
                "indexer.enrich.file_error",
                file_id=file_id,
                path=str(file_path),
            )
            continue

        files_enriched += 1
        files_since_commit += 1
        if files_since_commit >= _COMMIT_EVERY_N_FILES:
            conn.commit()
            files_since_commit = 0

        log.debug(
            "indexer.enrich.file_done",
            file_id=file_id,
            path=str(file_path),
        )

    # Drain the trailing batch so the very last files are persisted.
    if files_since_commit > 0:
        conn.commit()

    log.info(
        "indexer.enrich.disk_done",
        disk_id=disk.id,
        label=disk.label,
        files_enriched=files_enriched,
    )
