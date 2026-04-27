"""Drift detection and reconciliation engine for the media indexer.

Implements the per-file reconciliation loop described in DESIGN §8.1.

Functions:

- :func:`reconcile_file` — compare live file state against the DB index and
  classify the drift outcome.
- :func:`detect_rename` — search for an OSHash match on a new path that
  corresponds to a disappeared old path.
- :func:`enqueue_repair` — insert a row into ``repair_queue`` via
  ``outbox_repo.insert_repair_queue``.
- :func:`mark_missed_files` — increment ``miss_strikes`` for every file on a
  disk that was not visited in the current scan generation.
- :func:`clamp_mtime_ns` — sanitise raw mtime values from the filesystem
  (future or pre-1970) before storing or comparing them.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Literal

from personalscraper.indexer.fingerprint import is_racy, xxh3_partial
from personalscraper.indexer.repos import file_repo, outbox_repo
from personalscraper.indexer.schema import MediaFileRow, RepairQueueRow
from personalscraper.logger import get_logger

log = get_logger("indexer.drift")

# ---------------------------------------------------------------------------
# Public type aliases
# ---------------------------------------------------------------------------

ReconcileResult = Literal["unchanged", "tier1_drift", "content_drift", "rename", "oshash_collision", "new"]
RenameOutcome = Literal["rename_applied", "oshash_collision", "no_match"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Clamp mtime values older than this many nanoseconds before Unix epoch to 0.
_PRE_EPOCH_CLAMP: int = 0

#: Default maximum age for mtimes: 50 years in nanoseconds.
_DEFAULT_MAX_AGE_NS: int = 50 * 365 * 24 * 3600 * 1_000_000_000


# ---------------------------------------------------------------------------
# clamp_mtime_ns
# ---------------------------------------------------------------------------


def clamp_mtime_ns(mtime_ns: int, now_ns: int, max_age_ns: int = _DEFAULT_MAX_AGE_NS) -> int:
    """Clamp a raw filesystem mtime to a valid range.

    Clamps values that are:

    - In the future relative to *now_ns* — clamped down to *now_ns*.
    - Negative (pre-1970) or unreasonably old (older than *max_age_ns* before
      the Unix epoch represented as a positive age) — clamped to 0.

    Any value outside ``[0, now_ns]`` is invalid and triggers
    ``indexer.fs.invalid_mtime`` at WARNING level.

    Args:
        mtime_ns: Raw ``st_mtime_ns`` from the filesystem.
        now_ns: Current time in nanoseconds (typically ``time.time_ns()`` captured
            at scan start).
        max_age_ns: Unused — kept for API stability.  All pre-epoch values
            (``mtime_ns < 0``) are clamped to 0 regardless of magnitude.

    Returns:
        A sanitised mtime value in the range ``[0, now_ns]``.
    """
    if mtime_ns > now_ns:
        log.warning("indexer.fs.invalid_mtime", raw_mtime_ns=mtime_ns, now_ns=now_ns, action="clamped_to_now")
        return now_ns

    if mtime_ns < 0:
        log.warning(
            "indexer.fs.invalid_mtime",
            raw_mtime_ns=mtime_ns,
            now_ns=now_ns,
            action="clamped_to_epoch",
        )
        return _PRE_EPOCH_CLAMP

    return mtime_ns


# ---------------------------------------------------------------------------
# enqueue_repair
# ---------------------------------------------------------------------------


def enqueue_repair(conn: sqlite3.Connection, file_id: int, reason: str) -> None:
    """Insert a repair queue entry for the given file.

    Uses :func:`~personalscraper.indexer.repos.outbox_repo.insert_repair_queue`
    to persist the request.  The new row has ``scope='file'``, ``status='pending'``,
    and ``attempts=0``.

    Args:
        conn: Open SQLite connection.
        file_id: PK of the ``media_file`` row requiring repair.
        reason: Human-readable reason string, e.g. ``'content_drift'`` or
            ``'oshash_collision'``.
    """
    row = RepairQueueRow(
        id=0,  # ignored on insert
        scope="file",
        scope_id=file_id,
        reason=reason,
        payload_json=None,
        enqueued_at=int(time.time()),
        status="pending",
        attempted_at=None,
        attempts=0,
    )
    outbox_repo.insert_repair_queue(conn, row)
    log.debug("indexer.drift.repair_enqueued", file_id=file_id, reason=reason)


# ---------------------------------------------------------------------------
# reconcile_file
# ---------------------------------------------------------------------------


def reconcile_file(
    conn: sqlite3.Connection,
    disk_id: int,
    path_id: int,
    filename: str,
    current_stat: os.stat_result,
    current_oshash_or_empty: str,
    scan_started_at_ns: int,
    racy_window_ns: int,
) -> ReconcileResult:
    """Classify a live file against its stored index row.

    Logic (DESIGN §8.1):

    a. Look up existing ``media_file`` row by ``(path_id, filename)``.  If none
       exists return ``"new"`` — the caller is responsible for the INSERT.
    b. Compute tier-1 fingerprint of the current file.  If it matches the stored
       tier-1 AND the mtime is not racy, bump ``scan_generation`` and return
       ``"unchanged"``.
    c. If tier-1 differs OR the file is racy, compute ``xxh3_partial``.  If
       it matches the stored value, update tier-1 only and return
       ``"tier1_drift"`` (cosmetic mtime/ctime change).
    d. If ``xxh3_partial`` differs, enqueue a repair and return ``"content_drift"``.

    The caller must commit the enclosing transaction after processing all files
    in the disk's walk.

    Args:
        conn: Open SQLite connection (transaction management is the caller's
            responsibility).
        disk_id: PK of the ``disk`` row being scanned (used for rename search
            only; not written here).
        path_id: PK of the ``path`` row for the file's directory.
        filename: Bare filename (no directory component).
        current_stat: ``os.stat_result`` for the live file.
        current_oshash_or_empty: Pre-computed OSHash hex string, or ``""`` when
            OSHash is not applicable (non-video sidecar, symlink).
        scan_started_at_ns: Scan start timestamp in nanoseconds.
        racy_window_ns: Racy-mtime window width in nanoseconds.

    Returns:
        A :data:`ReconcileResult` literal indicating the outcome.
    """
    stored: MediaFileRow | None = file_repo.find_by_path_and_filename(conn, path_id, filename)

    if stored is None:
        return "new"

    # Clamp raw mtime before comparing (DESIGN §17.1 — future/pre-epoch guard).
    now_ns = time.time_ns()
    clamped_mtime_ns = clamp_mtime_ns(current_stat.st_mtime_ns, now_ns)

    # Build tier-1 tuple using the (possibly clamped) mtime and raw ctime.
    t1_current: tuple[int, int, int] = (current_stat.st_size, clamped_mtime_ns, current_stat.st_ctime_ns)
    t1_stored: tuple[int, int, int] = (stored.size_bytes, stored.mtime_ns, stored.ctime_ns or 0)

    racy = is_racy(clamped_mtime_ns, scan_started_at_ns, racy_window_ns)

    if t1_current == t1_stored and not racy:
        # Cheap skip: update generation only.
        conn.execute(
            "UPDATE media_file SET scan_generation = ? WHERE id = ?",
            (stored.scan_generation + 1, stored.id),
        )
        log.debug("indexer.drift.unchanged", file_id=stored.id, filename=filename)
        return "unchanged"

    # Escalate to tier-2.
    # For non-video files (empty oshash) we use xxh3_partial directly.
    # For video files the oshash covers rename detection; tier-2 here is xxh3_partial.
    from pathlib import Path as _Path  # noqa: PLC0415 — local import avoids circular at module level

    # We need a full path to compute xxh3_partial; caller must have already stat'd
    # the file so the path is reachable.  We reconstruct it from the path row.
    conn.row_factory = sqlite3.Row
    path_row = conn.execute("SELECT rel_path, disk_id FROM path WHERE id = ?", (path_id,)).fetchone()
    conn.row_factory = None
    if path_row is None:
        log.error("indexer.drift.path_row_missing", path_id=path_id)
        enqueue_repair(conn, stored.id, "content_drift")
        return "content_drift"

    disk_row = conn.execute("SELECT mount_path FROM disk WHERE id = ?", (path_row["disk_id"],)).fetchone()
    conn.row_factory = None
    if disk_row is None:
        log.error("indexer.drift.disk_row_missing", disk_id=disk_id)
        enqueue_repair(conn, stored.id, "content_drift")
        return "content_drift"

    # Reconstruct full path.
    mount = disk_row[0] if isinstance(disk_row, tuple) else disk_row["mount_path"]
    rel = path_row["rel_path"] if hasattr(path_row, "__getitem__") else path_row[0]
    full_path = _Path(mount) / rel / filename

    try:
        t2_current = xxh3_partial(full_path)
    except OSError as exc:
        log.warning("indexer.drift.xxh3_partial_failed", file_id=stored.id, error=str(exc))
        enqueue_repair(conn, stored.id, "content_drift")
        return "content_drift"

    if t2_current == (stored.xxh3_partial or ""):
        # Content unchanged — only tier-1 cosmetically drifted.
        conn.execute(
            """
            UPDATE media_file
               SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                   scan_generation = ?
             WHERE id = ?
            """,
            (current_stat.st_size, clamped_mtime_ns, current_stat.st_ctime_ns, stored.scan_generation + 1, stored.id),
        )
        log.debug("indexer.drift.tier1_drift", file_id=stored.id, filename=filename)
        return "tier1_drift"

    # Content actually changed.
    conn.execute(
        """
        UPDATE media_file
           SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
               xxh3_partial = ?, scan_generation = ?
         WHERE id = ?
        """,
        (
            current_stat.st_size,
            clamped_mtime_ns,
            current_stat.st_ctime_ns,
            t2_current,
            stored.scan_generation + 1,
            stored.id,
        ),
    )
    enqueue_repair(conn, stored.id, "content_drift")
    log.info("indexer.drift.content_drift", file_id=stored.id, filename=filename)
    return "content_drift"


# ---------------------------------------------------------------------------
# detect_rename
# ---------------------------------------------------------------------------


def detect_rename(
    conn: sqlite3.Connection,
    disk_id: int,
    current_path_id: int,
    filename: str,
    current_oshash: str,
) -> RenameOutcome:
    """Attempt to match a new file location to an existing index row via OSHash.

    Algorithm (DESIGN §8.1 + §17.1):

    a. Search for any ``media_file`` row on the same disk with matching
       ``oshash`` that is NOT at the current ``(path_id, filename)`` location.
    b. If no match found, return ``"no_match"``.
    c. If exactly one match: check whether the old path exists on disk.
       - Old path missing AND ``(oshash, size_bytes)`` match → apply rename
         (update ``path_id`` and ``filename``, reset ``miss_strikes=0``).
         Return ``"rename_applied"``.
       - Old path still exists → collision (two files, same hash, both present).
         Enqueue repair and return ``"oshash_collision"``.
    d. If multiple matches → cannot determine which is the source.  Enqueue
       repair for all candidates and return ``"oshash_collision"``.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the ``disk`` row being scanned.
        current_path_id: ``path.id`` of the directory where the new file was
            found.
        filename: Bare filename (no directory component) of the new file.
        current_oshash: Pre-computed OSHash hex string for the new file.

    Returns:
        A :data:`RenameOutcome` literal.
    """
    if not current_oshash:
        # No OSHash available (non-video or symlink) — cannot detect renames.
        return "no_match"

    # Get size of the current file for the collision guard (size must also match).
    conn.row_factory = sqlite3.Row
    current_row = conn.execute(
        "SELECT mf.size_bytes, p.rel_path, d.mount_path "
        "  FROM media_file mf "
        "  JOIN path p ON p.id = mf.path_id "
        "  JOIN disk d ON d.id = p.disk_id "
        " WHERE mf.path_id = ? AND mf.filename = ?",
        (current_path_id, filename),
    ).fetchone()
    conn.row_factory = None

    current_size: int | None = None
    if current_row is not None:
        current_size = current_row["size_bytes"]

    # Find candidates: same oshash on this disk, different location.
    conn.row_factory = sqlite3.Row
    candidates = conn.execute(
        """
        SELECT mf.id, mf.size_bytes, mf.path_id, mf.filename, mf.miss_strikes,
               p.rel_path, d.mount_path
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
          JOIN disk d ON d.id = p.disk_id
         WHERE mf.oshash = ?
           AND p.disk_id = ?
           AND NOT (mf.path_id = ? AND mf.filename = ?)
           AND mf.deleted_at IS NULL
        """,
        (current_oshash, disk_id, current_path_id, filename),
    ).fetchall()
    conn.row_factory = None

    if not candidates:
        return "no_match"

    if len(candidates) > 1:
        # Multiple candidates — ambiguous; enqueue collision for all.
        for cand in candidates:
            enqueue_repair(conn, cand["id"], "oshash_collision")
        log.warning(
            "indexer.drift.oshash_collision_multi",
            oshash=current_oshash,
            count=len(candidates),
        )
        return "oshash_collision"

    # Exactly one candidate.
    cand = candidates[0]
    old_full_path = Path(cand["mount_path"]) / cand["rel_path"] / cand["filename"]

    # Size guard (DESIGN §17.1): oshash + size must match.
    if current_size is not None and cand["size_bytes"] != current_size:
        enqueue_repair(conn, cand["id"], "oshash_collision")
        log.warning(
            "indexer.drift.oshash_collision_size_mismatch",
            candidate_id=cand["id"],
            cand_size=cand["size_bytes"],
            current_size=current_size,
        )
        return "oshash_collision"

    if os.path.exists(old_full_path):
        # Old path still exists on disk — two physical files with same hash.
        enqueue_repair(conn, cand["id"], "oshash_collision")
        log.warning(
            "indexer.drift.oshash_collision_both_present",
            candidate_id=cand["id"],
            old_path=str(old_full_path),
        )
        return "oshash_collision"

    # Old path is gone — treat as rename.
    conn.execute(
        "UPDATE media_file SET path_id = ?, filename = ?, miss_strikes = 0 WHERE id = ?",
        (current_path_id, filename, cand["id"]),
    )
    log.info(
        "indexer.drift.rename_applied",
        file_id=cand["id"],
        old_path=str(old_full_path),
        new_path_id=current_path_id,
        new_filename=filename,
    )
    return "rename_applied"


# ---------------------------------------------------------------------------
# mark_missed_files
# ---------------------------------------------------------------------------


def mark_missed_files(conn: sqlite3.Connection, disk_id: int, current_generation: int) -> int:
    """Increment ``miss_strikes`` for every file on a disk not seen in the current scan.

    Targets rows where ``scan_generation < current_generation`` AND
    ``deleted_at IS NULL``.  The disk must be mounted (the caller is responsible
    for checking mount status before calling this function).

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the ``disk`` row whose files should be checked.
        current_generation: The ``scan_generation`` value assigned to files
            visited in the current scan pass.

    Returns:
        Number of rows whose ``miss_strikes`` was incremented.
    """
    cursor = conn.execute(
        """
        UPDATE media_file
           SET miss_strikes = miss_strikes + 1
         WHERE path_id IN (
               SELECT id FROM path WHERE disk_id = ?
           )
           AND scan_generation < ?
           AND deleted_at IS NULL
        """,
        (disk_id, current_generation),
    )
    count: int = cursor.rowcount
    if count > 0:
        log.info("indexer.drift.miss_strikes_incremented", disk_id=disk_id, count=count, generation=current_generation)
    return count
