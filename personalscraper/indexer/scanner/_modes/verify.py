"""Verify scan mode driver."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

__all__ = [
    "_scan_disk_verify",
]


def _scan_disk_verify(
    conn: sqlite3.Connection,
    disk: DiskRow,
    files_visited: list[int],
    generation: int,
    budget_seconds: float | None,
    started_at_monotonic: float,
    budget_exhausted: list[bool],
    scan_run_id: int,
) -> None:
    """Re-stat every indexed file on a disk and enqueue repair on mismatch.

    Drift (size or mtime) and absence both produce a ``repair_queue`` row.
    Verify mode is non-destructive: it never soft-deletes, never recomputes
    fingerprints, and never updates ``size_bytes`` or ``mtime_ns`` on the
    DB row.  When a file's on-disk state matches the row, only
    ``last_verified_at`` and ``scan_generation`` are bumped to record that
    verification ran cleanly.  Mismatches are escalated to ``repair_queue``
    with ``scope='file'`` so an operator (or the repair worker) can
    investigate before any destructive action is taken.

    Per-file commit: partial progress survives interruption.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` to verify.
        files_visited: Single-element counter mutated in place (mirrors the
            convention of the other ``_scan_disk_*`` drivers).
        generation: Current scan generation; written to ``media_file.scan_generation``
            on every visited row so callers can detect orphaned rows from
            previous generations.
        budget_seconds: Maximum wall-clock seconds for the entire verify pass.
            ``None`` = unlimited.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_exhausted: Single-element flag set to ``True`` when the budget
            is reached.
        scan_run_id: PK of the active ``scan_run`` row for stats updates on
            budget exhaustion.
    """
    if disk.mount_path is None:
        log.warning("indexer.verify.disk_no_mount", disk_id=disk.id, label=disk.label)
        return

    # Lazy imports keep the module-level import surface small and avoid a
    # circular dependency with outbox_repo (which transitively imports schema).
    from personalscraper.indexer.repos import outbox_repo as _outbox_repo  # noqa: PLC0415
    from personalscraper.indexer.schema import RepairQueueRow  # noqa: PLC0415

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT mf.id        AS file_id,
               mf.filename  AS filename,
               mf.size_bytes AS size_bytes,
               mf.mtime_ns  AS mtime_ns,
               p.rel_path   AS rel_path
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
         WHERE p.disk_id = ?
           AND mf.deleted_at IS NULL
         ORDER BY mf.id
        """,
        (disk.id,),
    ).fetchall()
    conn.row_factory = None

    files_verified = 0
    mismatches = 0
    missing = 0

    for row in rows:
        if budget_seconds is not None:
            elapsed = time.monotonic() - started_at_monotonic
            if elapsed >= budget_seconds:
                log.info(
                    "indexer.verify.budget_exhausted",
                    disk_id=disk.id,
                    label=disk.label,
                    files_verified=files_verified,
                    mismatches=mismatches,
                    missing=missing,
                    elapsed=elapsed,
                )
                conn.execute(
                    "UPDATE scan_run SET stats_json = ? WHERE id = ?",
                    (
                        json.dumps(
                            {
                                "budget_exhausted": True,
                                "files_verified": files_verified,
                                "mismatches": mismatches,
                                "missing": missing,
                            }
                        ),
                        scan_run_id,
                    ),
                )
                conn.commit()
                budget_exhausted[0] = True
                return

        rel_path: str = row["rel_path"]
        filename: str = row["filename"]
        if rel_path == ".":
            file_path = Path(disk.mount_path) / filename
        else:
            file_path = Path(disk.mount_path) / rel_path / filename

        file_id: int = row["file_id"]
        now_s: int = int(time.time())

        try:
            st = os.stat(file_path, follow_symlinks=False)
        except FileNotFoundError:
            _outbox_repo.insert_repair_queue(
                conn,
                RepairQueueRow(
                    id=0,
                    scope="file",
                    scope_id=file_id,
                    reason="verify: file missing on disk",
                    payload_json=None,
                    enqueued_at=now_s,
                    status="pending",
                    attempted_at=None,
                    attempts=0,
                ),
            )
            missing += 1
            files_visited[0] += 1
            files_verified += 1
            conn.commit()
            continue
        except OSError as exc:
            log.warning(
                "indexer.verify.stat_failed",
                file_id=file_id,
                path=str(file_path),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            files_visited[0] += 1
            continue

        size_match = st.st_size == row["size_bytes"]
        mtime_match = st.st_mtime_ns == row["mtime_ns"]

        if size_match and mtime_match:
            # Clean verification — bump last_verified_at and scan_generation.
            conn.execute(
                "UPDATE media_file SET last_verified_at = ?, scan_generation = ? WHERE id = ?",
                (now_s, generation, file_id),
            )
        else:
            _outbox_repo.insert_repair_queue(
                conn,
                RepairQueueRow(
                    id=0,
                    scope="file",
                    scope_id=file_id,
                    reason=(f"verify: drift detected (size_match={size_match}, mtime_match={mtime_match})"),
                    payload_json=json.dumps(
                        {
                            "expected_size": row["size_bytes"],
                            "actual_size": st.st_size,
                            "expected_mtime_ns": row["mtime_ns"],
                            "actual_mtime_ns": st.st_mtime_ns,
                        }
                    ),
                    enqueued_at=now_s,
                    status="pending",
                    attempted_at=None,
                    attempts=0,
                ),
            )
            mismatches += 1
            # Still bump scan_generation so the row is reachable in this run.
            conn.execute(
                "UPDATE media_file SET scan_generation = ? WHERE id = ?",
                (generation, file_id),
            )

        files_visited[0] += 1
        files_verified += 1
        conn.commit()

    log.info(
        "indexer.verify.disk_done",
        disk_id=disk.id,
        label=disk.label,
        files_verified=files_verified,
        mismatches=mismatches,
        missing=missing,
    )
