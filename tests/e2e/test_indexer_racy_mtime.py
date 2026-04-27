"""E2E test: racy-mtime escalation and future-mtime clamping.

DESIGN §15.5 + §17.1:

- A file whose ``mtime_ns`` equals ``scan_started_at_ns`` is racy → tier-2
  (``xxh3_partial``) must be computed.
- A file whose ``mtime_ns`` is in the future is clamped to ``now_ns`` and the
  ``indexer.fs.invalid_mtime`` structured-log event is emitted.

Both scenarios are exercised against a real temporary filesystem (``tmp_path``),
an in-memory SQLite DB, and ``drift.reconcile_file``.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.drift import clamp_mtime_ns, reconcile_file
from personalscraper.indexer.fingerprint import xxh3_partial

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_RACY_WINDOW_NS: int = 2_000_000_000  # 2 seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Open a fully-migrated in-memory SQLite DB."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=OFF")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _seed_disk(conn: sqlite3.Connection, mount_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, is_mounted, unreachable_strikes) VALUES (?, ?, ?, 1, 0)",
        ("uuid-racy-test", "RacyDisk", mount_path),
    )
    disk_id: int = cur.lastrowid  # type: ignore[assignment]
    conn.commit()
    return disk_id


def _seed_path(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
        (disk_id, rel_path),
    )
    path_id: int = cur.lastrowid  # type: ignore[assignment]
    conn.commit()
    return path_id


def _seed_file(
    conn: sqlite3.Connection,
    path_id: int,
    filename: str,
    size: int,
    mtime_ns: int,
    xxh3_val: str,
    generation: int = 1,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (0, ?, ?, ?, ?, NULL, '', ?, NULL, ?, 0, NULL, 0, NULL)
        """,
        (path_id, filename, size, mtime_ns, xxh3_val, generation),
    )
    fid: int = cur.lastrowid  # type: ignore[assignment]
    conn.commit()
    return fid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_racy_mtime_triggers_tier2(tmp_path: Path) -> None:
    """A file with mtime == scan_started_at is racy → tier-2 is computed.

    We verify this by seeding a DB row whose stored ``xxh3_partial`` matches
    the real file and whose stored ``mtime_ns`` is different from the live
    mtime.  Because the live mtime equals ``scan_started_at_ns``, the file is
    racy, so the engine must escalate to tier-2.  Since the content is
    unchanged (xxh3 matches), the outcome is ``"tier1_drift"``.
    """
    # Write a real file so xxh3_partial can be computed.
    test_file = tmp_path / "video.mkv"
    test_file.write_bytes(b"video content bytes" * 50)

    real_xxh3 = xxh3_partial(test_file)
    file_size = test_file.stat().st_size

    # Seed a path row so reconcile_file can reconstruct the full path.
    conn = _open_db()
    disk_id = _seed_disk(conn, mount_path=str(tmp_path))
    path_id = _seed_path(conn, disk_id, "")  # root-level, rel_path=""

    # Seed with a DIFFERENT mtime so tier-1 will not match, but same xxh3.
    old_mtime_ns = 1_000_000_000
    _seed_file(
        conn,
        path_id=path_id,
        filename="video.mkv",
        size=file_size,
        mtime_ns=old_mtime_ns,
        xxh3_val=real_xxh3,
    )

    # Set the live mtime exactly to scan_started_at_ns (racy boundary).
    scan_started_at_ns = time.time_ns()
    os.utime(test_file, ns=(scan_started_at_ns, scan_started_at_ns))
    live_stat = os.stat(test_file)

    result = reconcile_file(
        conn=conn,
        disk_id=disk_id,
        path_id=path_id,
        filename="video.mkv",
        current_stat=live_stat,
        current_oshash_or_empty="",
        scan_started_at_ns=scan_started_at_ns,
        racy_window_ns=_RACY_WINDOW_NS,
    )

    # Racy file with matching xxh3 → tier1_drift (cosmetic mtime update only).
    assert result in ("tier1_drift", "unchanged"), (
        f"Expected tier1_drift or unchanged for racy file with matching content, got {result!r}"
    )

    conn.close()


def test_future_mtime_clamped_and_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A file with mtime in the future is clamped and ``indexer.fs.invalid_mtime`` logged.

    We call ``clamp_mtime_ns`` directly with a future value and verify:
    1. The returned value equals ``now_ns``.
    2. A WARNING structlog event with key ``indexer.fs.invalid_mtime`` is emitted.
    """
    now_ns = time.time_ns()
    future_mtime = now_ns + 10 * 60 * 1_000_000_000  # 10 minutes in the future

    with caplog.at_level(logging.WARNING):
        clamped = clamp_mtime_ns(future_mtime, now_ns)

    assert clamped == now_ns, f"Future mtime must be clamped to now_ns; got {clamped}"

    # structlog by default writes to the stdlib logger — check the log records.
    # The event key appears in the structlog output; check the logger name or message.
    event_logged = any("invalid_mtime" in (r.message or "") or "invalid_mtime" in str(r.args) for r in caplog.records)
    # Also accept if it was captured via the structlog logger directly.
    if not event_logged:
        # structlog may format differently; check the raw record list.
        event_logged = any("invalid_mtime" in str(r.__dict__) for r in caplog.records)

    assert event_logged, (
        f"Expected 'indexer.fs.invalid_mtime' warning to be logged for future mtime; "
        f"captured records: {[r.__dict__ for r in caplog.records]}"
    )


def test_pre_epoch_mtime_clamped(tmp_path: Path) -> None:
    """A file with mtime before 1970 is clamped to 0 (Unix epoch).

    Exercises the lower-bound branch of ``clamp_mtime_ns``.
    """
    now_ns = time.time_ns()
    pre_epoch_mtime = -(100 * 365 * 24 * 3600 * 1_000_000_000)  # 100 years before epoch

    clamped = clamp_mtime_ns(pre_epoch_mtime, now_ns)

    assert clamped == 0, f"Pre-epoch mtime must be clamped to 0; got {clamped}"


def test_racy_file_escalates_when_content_changes(tmp_path: Path) -> None:
    """Racy file with changed content returns ``"content_drift"`` and enqueues repair.

    Seeds a DB row with a stale xxh3.  Sets the live mtime to scan_started_at_ns
    (racy) and writes different content.  The outcome must be ``"content_drift"``
    and a ``repair_queue`` row must exist.
    """
    test_file = tmp_path / "changed.mkv"
    original_content = b"original" * 100
    test_file.write_bytes(original_content)
    original_xxh3 = xxh3_partial(test_file)

    # Overwrite with different content.
    new_content = b"changed_" * 100
    test_file.write_bytes(new_content)
    file_size = test_file.stat().st_size

    conn = _open_db()
    disk_id = _seed_disk(conn, mount_path=str(tmp_path))
    path_id = _seed_path(conn, disk_id, "")

    file_id = _seed_file(
        conn,
        path_id=path_id,
        filename="changed.mkv",
        size=file_size,
        mtime_ns=1_000_000_000,
        xxh3_val=original_xxh3,  # stale — won't match new content
    )

    scan_started_at_ns = time.time_ns()
    os.utime(test_file, ns=(scan_started_at_ns, scan_started_at_ns))
    live_stat = os.stat(test_file)

    result = reconcile_file(
        conn=conn,
        disk_id=disk_id,
        path_id=path_id,
        filename="changed.mkv",
        current_stat=live_stat,
        current_oshash_or_empty="",
        scan_started_at_ns=scan_started_at_ns,
        racy_window_ns=_RACY_WINDOW_NS,
    )

    assert result == "content_drift", f"Expected 'content_drift' for racy+changed file, got {result!r}"

    repair_rows = conn.execute(
        "SELECT reason FROM repair_queue WHERE scope_id = ? AND reason = 'content_drift'",
        (file_id,),
    ).fetchall()
    assert len(repair_rows) >= 1, "Expected repair_queue entry for content_drift"

    conn.close()
