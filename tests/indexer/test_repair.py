"""Unit tests for personalscraper.indexer.repair.

Covers:

- ``test_enqueue_repair_creates_row`` — call enqueue_repair, assert row is
  inserted in repair_queue with correct fields.
- ``test_drain_processes_in_fifo_order`` — enqueue 3 rows, drain, assert
  processor is called in ascending enqueued_at order.
- ``test_drain_budget_exhaustion`` — enqueue 5 rows with a slow processor,
  assert fewer rows are processed and ``budget_exhausted=True``.
- ``test_failed_processor_marks_row_failed`` — processor raises, assert row
  status transitions to ``'failed'``.
- ``test_get_queue_health_empty_returns_none_and_zero`` — empty queue returns
  ``(None, 0)``.
- ``test_get_queue_health_with_pending_returns_age_and_depth`` — enqueue a row
  with a historic enqueued_at, assert returned age matches and depth is 1.
- ``test_soft_delete_subtree_sets_deleted_at`` — soft_delete_subtree marks all
  live media_file rows under the given path_id (BD-D regression).
- ``test_repair_processor_soft_delete_subtree_drains_via_library_repair`` —
  drain with repair_processor on a scope='path'/soft_delete_subtree row
  soft-deletes all files under the missing path (BD-D integration).
- ``test_repair_processor_content_drift_*`` — scope='file'/content_drift rows
  must actually refresh the stale content-derived columns (oshash,
  xxh3_partial, enriched_at) instead of falling through to the
  unknown_action no-op (2026-07-08 regression: 14 content_drift rows were
  "succeeded" without any repair).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repair import (
    drain,
    enqueue_repair,
    get_queue_health,
    repair_processor,
    soft_delete_subtree,
)
from personalscraper.indexer.repos import log_repo
from personalscraper.indexer.schema import DeletedItemRow, RepairQueueRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _open_mem_db() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with all migrations applied and FK enforcement enabled."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_enqueue_repair_creates_row() -> None:
    """enqueue_repair inserts a row with correct fields and status='pending'."""
    conn = _open_mem_db()

    rowid = enqueue_repair(
        conn,
        scope="file",
        scope_id=42,
        reason="content_drift",
        payload={"extra": "data"},
    )
    conn.commit()

    row = conn.execute(
        "SELECT scope, scope_id, reason, status, attempts, attempted_at FROM repair_queue WHERE id = ?",
        (rowid,),
    ).fetchone()

    assert row is not None
    scope, scope_id, reason, status, attempts, attempted_at = row
    assert scope == "file"
    assert scope_id == 42
    assert reason == "content_drift"
    assert status == "pending"
    assert attempts == 0
    assert attempted_at is None


def test_drain_processes_in_fifo_order() -> None:
    """Drain calls the processor on rows in ascending enqueued_at order."""
    conn = _open_mem_db()

    # Insert three rows with explicitly ordered timestamps (oldest first).
    base = int(time.time()) - 1000
    _sql = (
        "INSERT INTO repair_queue"
        " (scope, scope_id, reason, payload_json, enqueued_at, status, attempted_at, attempts)"
        " VALUES ('file', ?, 'test', '{}', ?, 'pending', NULL, 0)"
    )
    for i, offset in enumerate([200, 100, 300]):
        conn.execute(_sql, (i + 1, base + offset))
    conn.commit()

    processed_scope_ids: list[int | None] = []

    def _capture_processor(c: sqlite3.Connection, row: RepairQueueRow) -> None:
        processed_scope_ids.append(row.scope_id)

    stats = drain(conn, budget_seconds=30.0, processor=_capture_processor)

    # Expect FIFO: offsets ascending → 100, 200, 300 → scope_ids 2, 1, 3.
    assert processed_scope_ids == [2, 1, 3]
    assert stats.processed == 3
    assert stats.succeeded == 3
    assert stats.failed == 0
    assert not stats.budget_exhausted


def test_drain_budget_exhaustion() -> None:
    """Drain halts when the wall-clock budget is exceeded."""
    conn = _open_mem_db()

    base = int(time.time()) - 100
    _sql2 = (
        "INSERT INTO repair_queue"
        " (scope, scope_id, reason, payload_json, enqueued_at, status, attempted_at, attempts)"
        " VALUES ('file', ?, 'test', '{}', ?, 'pending', NULL, 0)"
    )
    for i in range(5):
        conn.execute(_sql2, (i + 1, base + i))
    conn.commit()

    call_count = 0

    def _slow_processor(c: sqlite3.Connection, row: RepairQueueRow) -> None:
        nonlocal call_count
        call_count += 1
        time.sleep(0.6)  # > 0.5 s per row

    # Budget of 1.0 s → at most ~1-2 rows before the deadline is hit.
    stats = drain(conn, budget_seconds=1.0, processor=_slow_processor)

    # Budget check happens BEFORE processing each row, so the loop is interrupted
    # before starting the row that would exceed the budget.  With a 1.0 s budget
    # and ~0.6 s per call we expect exactly 1 row fully processed before the
    # second check fires.
    assert stats.budget_exhausted is True
    assert stats.processed <= 2  # generous upper bound
    assert call_count <= 2


def test_failed_processor_marks_row_failed() -> None:
    """A processor that raises transitions the row to status='failed'."""
    conn = _open_mem_db()

    rowid = enqueue_repair(conn, scope="file", scope_id=99, reason="boom", payload=None)
    conn.commit()

    def _failing_processor(c: sqlite3.Connection, row: RepairQueueRow) -> None:
        raise RuntimeError("intentional failure")

    stats = drain(conn, budget_seconds=30.0, processor=_failing_processor)

    assert stats.failed == 1
    assert stats.succeeded == 0

    status_row = conn.execute("SELECT status FROM repair_queue WHERE id = ?", (rowid,)).fetchone()
    assert status_row is not None
    assert status_row[0] == "failed"


def test_get_queue_health_empty_returns_none_and_zero() -> None:
    """get_queue_health on an empty queue returns (None, 0)."""
    conn = _open_mem_db()

    oldest, depth = get_queue_health(conn)

    assert oldest is None
    assert depth == 0


def test_get_queue_health_with_pending_returns_age_and_depth() -> None:
    """get_queue_health returns the approximate age and depth of pending rows."""
    conn = _open_mem_db()

    # Insert a row enqueued 1 hour ago.
    one_hour_ago = int(time.time()) - 3600
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, payload_json, enqueued_at, status, attempted_at, attempts)"
        " VALUES ('file', 1, 'test', '{}', ?, 'pending', NULL, 0)",
        (one_hour_ago,),
    )
    conn.commit()

    oldest, depth = get_queue_health(conn)

    assert depth == 1
    assert oldest is not None
    # Age should be approximately 3600 s — allow ±5 s for test execution.
    assert 3595 <= oldest <= 3605


# ---------------------------------------------------------------------------
# soft_delete_subtree
# ---------------------------------------------------------------------------


def _seed_disk_and_path(conn: sqlite3.Connection) -> tuple[int, int]:
    """Insert a minimal disk + path row and return (disk_id, path_id)."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES ('uuid-test', 'TestDisk', '/mnt/test', ?, 1, 0)",
        (now,),
    )
    disk_id: int = cursor.lastrowid  # type: ignore[assignment]
    cursor2 = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, 'shows/Gone', 0)",
        (disk_id,),
    )
    path_id: int = cursor2.lastrowid  # type: ignore[assignment]
    conn.commit()
    return disk_id, path_id


def _seed_media_file(conn: sqlite3.Connection, path_id: int, filename: str = "ep.mkv") -> int:
    """Insert a live media_file row under *path_id* and return its id."""
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, enriched_at, scan_generation, last_verified_at, deleted_at
        ) VALUES (NULL, ?, ?, 1000, 1700000000000000000, 1700000000000000000,
                  NULL, NULL, 1, ?, NULL)
        """,
        (path_id, filename, now),
    )
    file_id: int = cursor.lastrowid  # type: ignore[assignment]
    conn.commit()
    return file_id


def test_soft_delete_subtree_cascade_deletes_files_and_path() -> None:
    """soft_delete_subtree tombstones files THEN hard-prunes them + the path row.

    Regression contract (closure-of-loop, 2026-05-23): without the cascade,
    detect_path_missing keeps re-flagging the same path row at every reconcile
    run because the row never goes away.  This test fails if the function
    reverts to UPDATE-only behavior.
    """
    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)

    file_id_1 = _seed_media_file(conn, path_id, "ep01.mkv")
    file_id_2 = _seed_media_file(conn, path_id, "ep02.mkv")

    count = soft_delete_subtree(conn, path_id)
    conn.commit()

    assert count == 2, "Expected return value to count live files tombstoned (step 1)"

    # Step 2 hard-delete: files are gone from the table.
    for fid in (file_id_1, file_id_2):
        row = conn.execute("SELECT id FROM media_file WHERE id = ?", (fid,)).fetchone()
        assert row is None, f"media_file id={fid} was NOT hard-deleted — cascade broken"

    # Step 3 path row deleted: closes the detect_path_missing loop.
    path_row = conn.execute("SELECT id FROM path WHERE id = ?", (path_id,)).fetchone()
    assert path_row is None, "path row was NOT deleted — detector will loop forever"


def test_soft_delete_subtree_idempotent_on_already_pruned_path() -> None:
    """Calling soft_delete_subtree on an unknown path_id is a no-op (no exception).

    Defensive: library-repair may re-drain a queue row whose path was already
    pruned by a previous run.  The function must not raise.
    """
    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)
    # Prune once.
    soft_delete_subtree(conn, path_id)
    conn.commit()
    # Prune again on the gone path_id — must not raise, returns 0.
    count = soft_delete_subtree(conn, path_id)
    conn.commit()
    assert count == 0


def test_soft_delete_subtree_refreshes_disk_merkle() -> None:
    """soft_delete_subtree must refresh disk.merkle_root after the cascade.

    Regression contract (2026-05-23 incident #2): the c5e2bbd cascade fix
    closed the path_missing loop but left disk.merkle_root stale, which
    caused ``library-index --mode quick`` to trip its bulk-change protection
    on every prune (4 disks × 80-93% delta in production).  This test fails
    if soft_delete_subtree reverts to "prune-only without merkle refresh".
    """
    from personalscraper.indexer.merkle import FileFingerprint, compute_merkle_root  # noqa: PLC0415
    from personalscraper.indexer.reconcile import detect_merkle_drift  # noqa: PLC0415

    conn = _open_mem_db()
    disk_id, path_id = _seed_disk_and_path(conn)

    # Seed 2 live media_file rows under the path with deterministic fingerprints
    # AND a stored merkle that matches the seed (so the disk starts clean).
    file_id_1 = _seed_media_file(conn, path_id, "ep01.mkv")
    file_id_2 = _seed_media_file(conn, path_id, "ep02.mkv")
    # Give them oshashes so they count for merkle.
    conn.execute("UPDATE media_file SET oshash = 'aaaa111100002222' WHERE id = ?", (file_id_1,))
    conn.execute("UPDATE media_file SET oshash = 'bbbb333300004444' WHERE id = ?", (file_id_2,))
    # Compute initial merkle from current state and store it.
    initial_fingerprints = [
        FileFingerprint(path_id=path_id, size=1000, mtime_ns=1700000000000000000, oshash="aaaa111100002222"),
        FileFingerprint(path_id=path_id, size=1000, mtime_ns=1700000000000000000, oshash="bbbb333300004444"),
    ]
    initial_merkle = compute_merkle_root(initial_fingerprints)
    conn.execute("UPDATE disk SET merkle_root = ? WHERE id = ?", (initial_merkle, disk_id))
    conn.commit()

    # Pre-condition: detector reports no drift.
    assert detect_merkle_drift(conn) == [], "Pre-condition: stored merkle must match computed merkle"

    # Action: prune the path subtree.
    soft_delete_subtree(conn, path_id)
    conn.commit()

    # Post-condition: detector STILL reports no drift, because the cascade
    # refreshed disk.merkle_root to match the new (empty) live file set.
    drift = detect_merkle_drift(conn)
    assert drift == [], (
        f"detect_merkle_drift returned {drift} after soft_delete_subtree — "
        "the cascade did not refresh disk.merkle_root, the bulk-change "
        "protection will trip on the next library-index --mode quick"
    )

    # Sanity: the new merkle is the hash of the empty fingerprint set.
    new_root = conn.execute("SELECT merkle_root FROM disk WHERE id = ?", (disk_id,)).fetchone()[0]
    expected_empty = compute_merkle_root([])
    assert new_root == expected_empty, f"Expected merkle_root to be the empty-set hash {expected_empty}, got {new_root}"


def test_repair_processor_drains_path_missing_closes_detector_loop() -> None:
    """End-to-end: enqueue path_missing → drain → re-detect returns 0.

    Regression contract (2026-05-23 incident): a repair "succeeded" 332/332
    while detect_path_missing still reported 332 phantom paths immediately
    after, because the path row was never removed.  This test fails if the
    pipeline regresses to soft-only behavior.
    """
    from personalscraper.indexer.reconcile import detect_path_missing  # noqa: PLC0415

    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)
    _seed_media_file(conn, path_id, "movie.mkv")

    # The seed path does NOT exist on disk (rel_path uses a synthetic name),
    # so detect_path_missing must flag it before repair.
    assert path_id in detect_path_missing(conn), "Pre-condition: synthetic path must be flagged by detect_path_missing"

    payload = json.dumps({"detector": "path_missing", "action": "soft_delete_subtree"})
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, payload_json, enqueued_at, status, attempted_at, attempts)"
        " VALUES ('path', ?, 'reconcile.path.missing', ?, ?, 'pending', NULL, 0)",
        (path_id, payload, int(time.time())),
    )
    conn.commit()

    stats = drain(conn, budget_seconds=30.0, processor=repair_processor)
    assert stats.succeeded == 1, f"Expected 1 succeeded, got {stats}"

    # The detector must now return 0 — closing the loop the original repair left open.
    still_missing = detect_path_missing(conn)
    assert path_id not in still_missing, (
        f"detect_path_missing still flagged path_id={path_id} after repair drain — closure-of-loop regression"
    )


# ---------------------------------------------------------------------------
# repair_content_drift (scope='file', reason='content_drift')
# ---------------------------------------------------------------------------


def _seed_disk_path_at(conn: sqlite3.Connection, mount_path: Path, rel_path: str) -> tuple[int, int]:
    """Insert a disk row mounted at *mount_path* + a path row and return (disk_id, path_id)."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES ('uuid-drift', 'DriftDisk', ?, ?, 1, 0)",
        (str(mount_path), now),
    )
    disk_id: int = cursor.lastrowid  # type: ignore[assignment]
    cursor2 = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    path_id: int = cursor2.lastrowid  # type: ignore[assignment]
    conn.commit()
    return disk_id, path_id


def _seed_stale_media_file(
    conn: sqlite3.Connection,
    path_id: int,
    filename: str,
    *,
    oshash: str | None,
) -> int:
    """Insert a media_file row whose content-derived columns are deliberately stale."""
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, enriched_at,
            scan_generation, last_verified_at, deleted_at
        ) VALUES (NULL, ?, ?, 1, 1700000000000000000, 1700000000000000000,
                  ?, 'stalestalestale1', 'stalestalestale2', 1650000000,
                  1, ?, NULL)
        """,
        (path_id, filename, oshash, now),
    )
    file_id: int = cursor.lastrowid  # type: ignore[assignment]
    conn.commit()
    return file_id


def _enqueue_content_drift(conn: sqlite3.Connection, file_id: int) -> None:
    """Insert a content_drift repair row exactly the way drift.enqueue_repair does."""
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, payload_json, enqueued_at, status, attempted_at, attempts)"
        " VALUES ('file', ?, 'content_drift', '{}', ?, 'pending', NULL, 0)",
        (file_id, int(time.time())),
    )
    conn.commit()


def test_repair_processor_content_drift_refreshes_stale_fingerprint(tmp_path: Path) -> None:
    """A content_drift row must refresh oshash/xxh3_partial and invalidate enrichment.

    Regression contract (2026-07-08 incident): 14 content_drift rows drained
    "succeeded" via the unknown_action no-op — the stale oshash was never
    recomputed, so tier-3 rename detection and release linking kept matching
    on the OLD content identity.  This test fails if repair_processor falls
    back to the no-op for scope='file'/content_drift.
    """
    from personalscraper.indexer import fingerprint as fp  # noqa: PLC0415

    conn = _open_mem_db()
    media_dir = tmp_path / "films" / "Drifted (2020)"
    media_dir.mkdir(parents=True)
    live = media_dir / "Drifted.mkv"
    live.write_bytes(b"NEW CONTENT AFTER DRIFT " * 4096)

    _, path_id = _seed_disk_path_at(conn, tmp_path, "films/Drifted (2020)")
    file_id = _seed_stale_media_file(conn, path_id, "Drifted.mkv", oshash="00000000deadbeef")
    _enqueue_content_drift(conn, file_id)

    stats = drain(conn, budget_seconds=30.0, processor=repair_processor)
    assert stats.succeeded == 1, f"Expected 1 succeeded, got {stats}"

    row = conn.execute(
        "SELECT size_bytes, oshash, xxh3_partial, xxh3_full, enriched_at FROM media_file WHERE id = ?",
        (file_id,),
    ).fetchone()
    size_bytes, oshash_val, xxh3_val, xxh3_full, enriched_at = row

    assert size_bytes == live.stat().st_size, "size_bytes was not refreshed from the live file"
    assert oshash_val == fp.oshash(live), "stale oshash was not recomputed — tier-3 rename detection stays broken"
    assert xxh3_val == fp.xxh3_partial(live), "stale xxh3_partial was not recomputed"
    assert xxh3_full is None, "stale xxh3_full must be reset to NULL (unknown after content change)"
    assert enriched_at is None, "enriched_at must be invalidated so the enrich pass re-extracts streams"


def test_repair_processor_content_drift_non_video_keeps_oshash_null(tmp_path: Path) -> None:
    """A non-video sidecar (oshash=NULL) is refreshed without growing an oshash."""
    from personalscraper.indexer import fingerprint as fp  # noqa: PLC0415

    conn = _open_mem_db()
    media_dir = tmp_path / "series" / "Show (1999)"
    media_dir.mkdir(parents=True)
    live = media_dir / "tvshow.nfo"
    live.write_bytes(b"<tvshow><title>Rewritten</title></tvshow>")

    _, path_id = _seed_disk_path_at(conn, tmp_path, "series/Show (1999)")
    file_id = _seed_stale_media_file(conn, path_id, "tvshow.nfo", oshash=None)
    _enqueue_content_drift(conn, file_id)

    stats = drain(conn, budget_seconds=30.0, processor=repair_processor)
    assert stats.succeeded == 1, f"Expected 1 succeeded, got {stats}"

    row = conn.execute(
        "SELECT oshash, xxh3_partial, enriched_at FROM media_file WHERE id = ?",
        (file_id,),
    ).fetchone()
    oshash_val, xxh3_val, enriched_at = row

    assert oshash_val is None, "oshash must stay NULL for non-video sidecars"
    assert xxh3_val == fp.xxh3_partial(live), "stale xxh3_partial was not recomputed"
    assert enriched_at is None, "enriched_at must be invalidated so the enrich pass re-checks the sidecar"


def test_repair_processor_content_drift_missing_file_is_graceful_noop(tmp_path: Path) -> None:
    """A content_drift row whose file vanished must complete as done, not failed.

    Disappearance is owned by the scan's miss-strikes path — the repair must
    neither raise (which would mark the row failed and leave it re-tripping
    the 7-day WARN) nor touch the stored row.
    """
    conn = _open_mem_db()
    _, path_id = _seed_disk_path_at(conn, tmp_path, "films/Vanished (2021)")
    file_id = _seed_stale_media_file(conn, path_id, "Vanished.mkv", oshash="00000000deadbeef")
    _enqueue_content_drift(conn, file_id)

    stats = drain(conn, budget_seconds=30.0, processor=repair_processor)
    assert stats.succeeded == 1, f"Expected graceful done, got {stats}"

    row = conn.execute(
        "SELECT oshash, xxh3_partial, enriched_at FROM media_file WHERE id = ?",
        (file_id,),
    ).fetchone()
    assert row == ("00000000deadbeef", "stalestalestale1", 1650000000), (
        "stored row must be left untouched when the live file is missing"
    )


def test_repair_processor_content_drift_refreshes_disk_merkle(tmp_path: Path) -> None:
    """An oshash change through content_drift repair must keep disk.merkle_root coherent.

    Same contract as test_soft_delete_subtree_refreshes_disk_merkle: any repair
    that rewrites an oshash shifts the disk's fingerprint set, and a stale
    stored merkle root re-trips the bulk-change protection on mass drift
    (2026-06-30 scenario).
    """
    from personalscraper.indexer.merkle import FileFingerprint, compute_merkle_root  # noqa: PLC0415
    from personalscraper.indexer.reconcile import detect_merkle_drift  # noqa: PLC0415

    conn = _open_mem_db()
    media_dir = tmp_path / "films" / "Drifted (2020)"
    media_dir.mkdir(parents=True)
    live = media_dir / "Drifted.mkv"
    live.write_bytes(b"NEW CONTENT AFTER DRIFT " * 4096)

    disk_id, path_id = _seed_disk_path_at(conn, tmp_path, "films/Drifted (2020)")
    file_id = _seed_stale_media_file(conn, path_id, "Drifted.mkv", oshash="00000000deadbeef")
    # Store the merkle matching the CURRENT (stale) DB state so the disk starts clean.
    initial = compute_merkle_root(
        [FileFingerprint(path_id=path_id, size=1, mtime_ns=1700000000000000000, oshash="00000000deadbeef")]
    )
    conn.execute("UPDATE disk SET merkle_root = ? WHERE id = ?", (initial, disk_id))
    conn.commit()
    assert detect_merkle_drift(conn) == [], "Pre-condition: stored merkle must match computed merkle"

    _enqueue_content_drift(conn, file_id)
    stats = drain(conn, budget_seconds=30.0, processor=repair_processor)
    assert stats.succeeded == 1, f"Expected 1 succeeded, got {stats}"

    assert detect_merkle_drift(conn) == [], (
        "disk.merkle_root left stale after the oshash rewrite — bulk-change protection will trip on mass drift"
    )


# ---------------------------------------------------------------------------
# soft_delete_subtree — audit trail
# ---------------------------------------------------------------------------


def _tombstones(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return every deleted_item row, oldest first."""
    conn.row_factory = sqlite3.Row
    return list(conn.execute("SELECT * FROM deleted_item ORDER BY id").fetchall())


def test_soft_delete_subtree_records_every_pruned_file() -> None:
    """The prune leaves an audit record per file, not merely a log line.

    The docstring promised step 1's count as an "audit trail", but the rows
    were hard-deleted immediately and nothing reached ``deleted_item`` — the
    table ``apply_soft_deletes`` writes for exactly this purpose. A prune that
    turns out to have been wrong (an unmounted disk, a case or unicode-form
    mismatch) left nothing to reconstruct from.
    """
    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)
    _seed_media_file(conn, path_id, "ep01.mkv")
    _seed_media_file(conn, path_id, "ep02.mkv")

    soft_delete_subtree(conn, path_id)
    conn.commit()

    rows = _tombstones(conn)
    assert len(rows) == 2, "every hard-deleted media_file must leave a tombstone"
    assert {row["kind"] for row in rows} == {"file"}
    assert {row["reason"] for row in rows} == {"subtree_pruned"}
    assert {json.loads(row["payload_json"])["filename"] for row in rows} == {"ep01.mkv", "ep02.mkv"}


def test_soft_delete_subtree_snapshot_survives_the_path_row() -> None:
    """The snapshot names the path itself, because the path row is deleted too.

    ``apply_soft_deletes`` stores ``path_id``, which is enough while the path
    row lives. Here step 3 deletes it, so a record holding only that id points
    at nothing. The snapshot carries the disk and the relative path instead.
    """
    conn = _open_mem_db()
    disk_id, path_id = _seed_disk_and_path(conn)
    file_id = _seed_media_file(conn, path_id, "ep01.mkv")

    soft_delete_subtree(conn, path_id)
    conn.commit()

    tombstone = _tombstones(conn)[0]
    payload = json.loads(tombstone["payload_json"])

    # EVERY field is asserted. Blanking six of them at once — original_id, id,
    # path_id, oshash, mtime_ns, deleted_at — left this suite green, so an audit
    # record could be written with no identity at all and nothing would notice.
    assert tombstone["original_id"] == file_id
    assert payload == {
        "id": file_id,
        "release_id": None,
        "path_id": path_id,
        "disk_id": disk_id,
        "rel_path": "shows/Gone",
        "filename": "ep01.mkv",
        "oshash": None,
        "size_bytes": 1000,
        "mtime_ns": 1700000000000000000,
        "miss_strikes": 0,
        # Step 1 stamps only rows that were live, so this field tells the two
        # cases apart: equal to the tombstone's own stamp means THIS call
        # retired the row; an earlier value means the strike mechanism had.
        "deleted_at": tombstone["deleted_at"],
    }


def test_soft_delete_subtree_records_an_already_tombstoned_file() -> None:
    """A struck-out row is hard-deleted here, and that is its own event.

    Its earlier ``n_strikes`` tombstone describes a soft delete and names a
    path row that is about to vanish; the prune is a second, later fact.
    """
    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)
    file_id = _seed_media_file(conn, path_id, "ep01.mkv")
    earlier_stamp = int(time.time()) - 3600
    conn.execute("UPDATE media_file SET deleted_at = ? WHERE id = ?", (earlier_stamp, file_id))
    conn.commit()

    count = soft_delete_subtree(conn, path_id)
    conn.commit()

    assert count == 0, "the row was already soft-deleted, so step 1 tombstones none"
    rows = _tombstones(conn)
    assert len(rows) == 1, "the hard delete is recorded even when the soft delete was not"
    assert rows[0]["reason"] == "subtree_pruned"
    # The distinguishing field: this row was retired BEFORE the prune, so its
    # snapshot keeps the earlier stamp rather than the prune's.
    payload = json.loads(rows[0]["payload_json"])
    assert payload["deleted_at"] == earlier_stamp
    assert payload["deleted_at"] != rows[0]["deleted_at"]


def test_soft_delete_subtree_on_an_empty_path_records_nothing() -> None:
    """A path holding no files has nothing to lose and writes no record."""
    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)

    soft_delete_subtree(conn, path_id)
    conn.commit()

    assert _tombstones(conn) == []


def test_soft_delete_subtree_leaves_nothing_half_done_when_a_tombstone_fails() -> None:
    """A raise mid-loop must undo the soft delete rather than leave it standing.

    ``drain`` marks the queue row ``failed`` and then COMMITS, and nothing in
    this module rolls back. Before the audit records existed, the soft-delete
    UPDATE and the hard DELETE were adjacent with nothing between them that
    could raise. The tombstone loop sits in that gap, so a failure there left
    every file under the path marked deleted — invisible to the library while
    still present on disk — with the path row surviving, so the reconcile loop
    never closed and the merkle was never refreshed.
    """
    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)
    _seed_media_file(conn, path_id, "ep01.mkv")
    _seed_media_file(conn, path_id, "ep02.mkv")
    _seed_media_file(conn, path_id, "ep03.mkv")

    real_insert = log_repo.insert_deleted_item
    seen: list[int] = []

    def _fail_on_the_second_row(connection: sqlite3.Connection, row: DeletedItemRow) -> int:
        """Write the first tombstone, then fail as a disk error would."""
        seen.append(row.original_id)
        if len(seen) == 2:
            raise sqlite3.OperationalError("disk I/O error")
        return real_insert(connection, row)

    with patch.object(log_repo, "insert_deleted_item", _fail_on_the_second_row):
        with pytest.raises(sqlite3.OperationalError):
            soft_delete_subtree(conn, path_id)
    conn.commit()  # what drain's error handler does

    live = conn.execute(
        "SELECT COUNT(*) FROM media_file WHERE path_id = ? AND deleted_at IS NULL", (path_id,)
    ).fetchone()[0]
    assert live == 3, "every file must still be live — a committed half-delete hides files that exist"
    assert _tombstones(conn) == [], "a partial audit trail is worse than none"
    assert conn.execute("SELECT COUNT(*) FROM path WHERE id = ?", (path_id,)).fetchone()[0] == 1


def test_soft_delete_subtree_snapshot_carries_the_release_and_the_strikes() -> None:
    """Reading a tombstone back is the point, so it must name what was lost.

    ``release_id`` is the only link from a file to its release and its title;
    without it a record names a filename belonging to nothing. ``miss_strikes``
    is the corroborating evidence for whether the scanner had also stopped
    seeing the file — the field ``apply_soft_deletes`` keeps for exactly that
    reason, and the one the 2026-06-30 diagnosis depended on.
    """
    conn = _open_mem_db()
    _, path_id = _seed_disk_and_path(conn)
    file_id = _seed_media_file(conn, path_id, "ep01.mkv")
    conn.execute("UPDATE media_file SET miss_strikes = 2 WHERE id = ?", (file_id,))
    conn.commit()

    soft_delete_subtree(conn, path_id)
    conn.commit()

    payload = json.loads(_tombstones(conn)[0]["payload_json"])
    assert "release_id" in payload, "without it the record names a file belonging to nothing"
    assert payload["miss_strikes"] == 2
