"""Enrich backfill scan mode driver."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from personalscraper.core.media_types import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS
from personalscraper.indexer.mediainfo import MediaInfoUnavailableError, MediaInfoWrapper
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

__all__ = [
    "_scan_disk_enrich_backfill",
]


def _scan_disk_enrich_backfill(
    conn: sqlite3.Connection,
    disk: DiskRow,
    budget_seconds: float | None,
    started_at_monotonic: float,
    budget_exhausted: list[bool],
    scan_run_id: int,
    quick_enrich: bool = False,
) -> None:
    """Backfill missing migration-004 columns on already-enriched files.

    Targets ``media_file`` rows whose ``media_stream`` rows still carry
    ``NULL`` in the columns added by migration 004 (``hdr_format``,
    ``is_atmos``, ``is_default``, ``forced``, ``format``). Re-extracts
    streams via the wrapper and **UPDATEs the existing ``media_stream``
    rows in place** by ``(file_id, idx)`` — no DELETE / re-INSERT, no
    NFO / artwork / linker work, no ``enriched_at`` write. Significantly
    cheaper than a full re-enrich because:

    * The query filter eliminates files that are already complete.
    * UPDATE in place avoids the DELETE-then-INSERT churn on
      ``media_stream`` (and the cascade on ``idx_stream_*`` indexes).
    * The NFO presence check, artwork inventory, and release linkage
      were already performed during the original enrich; running them
      again would re-touch ``media_item`` rows for no gain.

    Files whose container is fast-path supported (Matroska / WebM)
    benefit from the enzyme reader; the rest hit the pymediainfo slow
    path under ``_MEDIAINFO_PARSE_LOCK``.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` to scan.
        budget_seconds: Maximum wall-clock seconds for the pass; ``None``
            means unlimited.
        started_at_monotonic: :func:`time.monotonic` value captured at
            scan start, used to test the budget.
        budget_exhausted: Single-element flag set to ``True`` when the
            budget is reached.
        scan_run_id: PK of the active ``scan_run`` row, written into the
            stats payload on budget exhaustion.
        quick_enrich: When ``True``, uses ``parse_speed=0.5``.
    """
    if disk.mount_path is None:
        log.warning("indexer.enrich.disk_no_mount", disk_id=disk.id, label=disk.label)
        return

    parse_speed: float = 0.5 if quick_enrich else 1.0

    wrapper: MediaInfoWrapper | None
    try:
        from personalscraper.indexer.scanner import _modes as modes_api  # noqa: PLC0415

        wrapper = modes_api.MediaInfoWrapper(min_size_mb=0, parse_speed=parse_speed)
    except MediaInfoUnavailableError:
        log.warning("indexer.enrich.mediainfo_unavailable", disk_id=disk.id, label=disk.label)
        wrapper = None

    if wrapper is None:
        # Without pymediainfo / enzyme we cannot fill any column — bail
        # cleanly so the caller's outer loop continues to the next disk.
        return

    conn.row_factory = sqlite3.Row
    pending = conn.execute(
        """
        SELECT DISTINCT mf.id        AS file_id,
                        mf.filename  AS filename,
                        p.rel_path   AS rel_path
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
          JOIN media_stream s ON s.file_id = mf.id
         WHERE p.disk_id = ?
           AND mf.deleted_at IS NULL
           AND mf.enriched_at IS NOT NULL
           AND (
                  (s.kind = 'video' AND s.hdr_format IS NULL)
               OR (s.kind = 'audio' AND s.is_atmos IS NULL)
               OR (s.kind = 'subtitle' AND s.format IS NULL)
               OR s.is_default IS NULL
           )
         ORDER BY mf.id
        """,
        (disk.id,),
    ).fetchall()
    conn.row_factory = None

    files_backfilled = 0

    for row in pending:
        if budget_seconds is not None:
            elapsed = time.monotonic() - started_at_monotonic
            if elapsed >= budget_seconds:
                log.info(
                    "indexer.enrich.backfill_budget_exhausted",
                    disk_id=disk.id,
                    label=disk.label,
                    files_backfilled=files_backfilled,
                    elapsed=elapsed,
                )
                conn.execute(
                    "UPDATE scan_run SET stats_json = ? WHERE id = ?",
                    (json.dumps({"budget_exhausted": True, "files_backfilled": files_backfilled}), scan_run_id),
                )
                conn.commit()
                budget_exhausted[0] = True
                return

        rel_path: str = row["rel_path"]
        filename: str = row["filename"]
        file_id: int = row["file_id"]

        # Skip non-video extensions outright — they have media_stream rows
        # only when pymediainfo previously hallucinated tracks for sidecars,
        # which is rare and not worth re-checking.
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in _VIDEO_EXTENSIONS:
            continue

        if rel_path == ".":
            file_path = Path(disk.mount_path) / filename
        else:
            file_path = Path(disk.mount_path) / rel_path / filename

        if not file_path.exists():
            log.debug("indexer.enrich.backfill_file_missing", file_id=file_id, path=str(file_path))
            continue

        try:
            stream_rows = wrapper.extract_streams(file_path)
        except Exception:  # noqa: BLE001 — pymediainfo / enzyme can raise broadly
            log.warning("indexer.enrich.backfill_extract_failed", file_id=file_id, path=str(file_path))
            continue

        if not stream_rows:
            continue

        for global_idx, sr in enumerate(stream_rows):
            conn.execute(
                """
                UPDATE media_stream
                   SET hdr_format = COALESCE(media_stream.hdr_format, ?),
                       is_atmos   = COALESCE(media_stream.is_atmos,   ?),
                       is_default = COALESCE(media_stream.is_default, ?),
                       forced     = COALESCE(media_stream.forced,     ?),
                       format     = COALESCE(media_stream.format,     ?)
                 WHERE file_id = ? AND idx = ?
                """,
                (
                    sr.hdr_format,
                    None if sr.is_atmos is None else int(sr.is_atmos),
                    None if sr.is_default is None else int(sr.is_default),
                    None if sr.forced is None else int(sr.forced),
                    sr.format,
                    file_id,
                    global_idx,
                ),
            )

        conn.commit()
        files_backfilled += 1
        log.debug("indexer.enrich.backfill_file_done", file_id=file_id, path=str(file_path))

    log.info(
        "indexer.enrich.backfill_disk_done",
        disk_id=disk.id,
        label=disk.label,
        files_backfilled=files_backfilled,
    )
