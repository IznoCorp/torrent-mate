"""E2E tests for ``personalscraper library-verify`` — CLI-level harness.

Validates re-stat behaviour, mismatch detection, repair-queue enqueue,
--disk / --no-enqueue flags, and the closure-of-loop contract (BD-D
regression guard).
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_json_schema,
    assert_no_python_traceback,
    capture_event_bus,
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
    seed_media_file_on_disk,
    seed_phantom_path,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_GUARD = "personalscraper.indexer.scanner.guard_disk_mounted"


def _pending_repair_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM repair_queue WHERE status='pending'").fetchone()[0]
    conn.close()
    return count


# ── 1. Smoke ───────────────────────────────────────────────────────────────────


def test_verify_help_exits_zero() -> None:
    """``library-verify --help`` exits 0."""
    result = run_cli(["library-verify", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-verify" in result.output


# ── 2. Realistic scenarios ────────────────────────────────────────────────────


def test_verify_empty_db_zero_files_visited(tmp_path, test_config) -> None:
    """Fresh DB with no disk rows → files_walked=0, exit 0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-verify"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["files_walked"] == 0, f"Expected 0 files walked, got {data}"
    assert data["status"] == "ok"


def test_verify_clean_file_no_mismatch_no_enqueue(tmp_path, test_config) -> None:
    """File on disk with matching DB stats → verify walks it, no enqueue."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "CleanDisk"
    mount.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "CleanDisk", mount)
    seed_media_file_on_disk(conn, disk_id, mount, "media", "test.mkv")
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["files_walked"] >= 1, f"Expected >=1 files walked, got {data}"
    assert data["status"] == "ok"

    # No pending repairs should have been enqueued.
    pending = _pending_repair_count(str(db_path))
    assert pending == 0, f"Expected 0 pending repairs, got {pending}"


def test_verify_size_mismatch_enqueues_repair(tmp_path, test_config) -> None:
    """DB stores wrong size → verify enqueues a repair_queue row."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "SizeDisk"
    mount.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "SizeDisk", mount)
    # Store size=1 in DB, but the real file is ~30 bytes.
    seed_media_file_on_disk(conn, disk_id, mount, "media", "test.mkv", size_bytes=1)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["files_walked"] >= 1, f"Expected >=1 files walked, got {data}"

    # A repair row must have been enqueued for the size mismatch.
    pending = _pending_repair_count(str(db_path))
    assert pending >= 1, f"Expected >=1 pending repair, got {pending}"


def test_verify_mtime_mismatch_enqueues_repair(tmp_path, test_config) -> None:
    """DB stores wrong mtime → verify enqueues a repair_queue row."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "MtimeDisk"
    mount.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "MtimeDisk", mount)
    # Store mtime_ns=1 in DB, real file stat has a much larger value.
    seed_media_file_on_disk(conn, disk_id, mount, "media", "test.mkv", mtime_ns=1)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["files_walked"] >= 1, f"Expected >=1 files walked, got {data}"

    pending = _pending_repair_count(str(db_path))
    assert pending >= 1, f"Expected >=1 pending repair for mtime mismatch, got {pending}"


def test_verify_disk_filter_restricts_scope(tmp_path, test_config) -> None:
    """``--disk`` flag restricts verification to a single disk's files."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount_a = tmp_path / "DiskA"
    mount_a.mkdir()
    mount_b = tmp_path / "DiskB"
    mount_b.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_a = seed_disk(conn, "DiskA", mount_a)
    disk_b = seed_disk(conn, "DiskB", mount_b)
    # Put files on both disks with mismatched sizes so both would enqueue.
    seed_media_file_on_disk(conn, disk_a, mount_a, "media", "file_a.mkv", size_bytes=1)
    seed_media_file_on_disk(conn, disk_b, mount_b, "media", "file_b.mkv", size_bytes=1)
    conn.close()

    # Verify only DiskA.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify", "--disk", "DiskA"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    # Only 1 file should be walked (the one on DiskA).
    assert data["files_walked"] == 1, f"Expected exactly 1 file walked (DiskA only), got {data}"


def test_verify_no_enqueue_flag_no_writes(tmp_path, test_config) -> None:
    """``--no-enqueue`` detects mismatches but inserts 0 repair rows."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "NoEnqDisk"
    mount.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "NoEnqDisk", mount)
    seed_media_file_on_disk(conn, disk_id, mount, "media", "test.mkv", size_bytes=1)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify", "--no-enqueue"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["files_walked"] >= 1, f"Expected >=1 files walked, got {data}"
    assert data["no_enqueue"] is True, f"Expected no_enqueue=True, got {data}"

    # No repair rows should be inserted.
    pending = _pending_repair_count(str(db_path))
    assert pending == 0, f"--no-enqueue must not insert repair rows, got {pending}"


# ── 3. Closure-of-loop (THE BD-D PATTERN) ─────────────────────────────────────


def test_verify_closes_loop_with_repair(tmp_path, test_config) -> None:
    """Seed phantom → reconcile enqueues → repair drains → verify finds nothing.

    This is the BD-D regression pattern for verify: after the reconcile+repair
    cycle hard-deletes phantom files, a follow-up verify must walk 0 files
    for the cleaned disk (closure-of-loop).  The repair_processor currently
    handles ``scope='path'`` + ``action='soft_delete_subtree'`` (enqueued by
    reconcile's ``detect_path_missing``), which hard-deletes media_file rows
    and the path row — leaving nothing for verify to stat.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "LoopDisk"
    mount.mkdir()

    # Seed a phantom path.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "LoopDisk", mount)
    seed_phantom_path(conn, disk_id, "phantom_dir", n_files=2)
    conn.close()

    # Step 1: Reconcile detects the phantom path and enqueues repair.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        r1 = run_cli(["--format", "json", "library-reconcile", "--enqueue-repairs"])
    assert r1.exit_code == 0, r1.output
    d1 = json_from_result(r1)
    assert d1["enqueued_repairs"] >= 1, f"No repairs enqueued: {d1}"

    # Step 2: Repair drains the queue (hard-deletes files + path).
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        r2 = run_cli(["--format", "json", "library-repair"])
    assert r2.exit_code == 0, r2.output
    d2 = json_from_result(r2)
    assert d2["succeeded"] >= 1, f"Repair did not succeed: {d2}"
    assert d2["pending_depth"] == 0, f"Queue not empty after repair: {d2}"

    # Step 3: Verify must find 0 files for the cleaned disk.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        r3 = run_cli(["library-verify"])
    assert r3.exit_code == 0, r3.output
    d3 = json_from_result(r3)
    assert d3["files_walked"] == 0, (
        f"CLOSURE-OF-LOOP BROKEN: files_walked={d3['files_walked']} after repair (expected 0): {d3}"
    )
    assert d3["status"] == "ok", f"CLOSURE-OF-LOOP BROKEN: status={d3['status']} after repair: {d3}"

    # Queue must still be empty.
    pending = _pending_repair_count(str(db_path))
    assert pending == 0, f"Repair queue not empty after closure: {pending}"


# ── 4. Idempotence ────────────────────────────────────────────────────────────


def test_verify_idempotent_on_clean_files(tmp_path, test_config) -> None:
    """Two verify runs on clean files produce the same files_walked count."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "IdemDisk"
    mount.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "IdemDisk", mount)
    seed_media_file_on_disk(conn, disk_id, mount, "media", "test.mkv")
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        r1 = run_cli(["library-verify"])
        r2 = run_cli(["library-verify"])

    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    d1 = json_from_result(r1)
    d2 = json_from_result(r2)
    assert d1["files_walked"] == d2["files_walked"], f"files_walked changed between idempotent runs: {d1} vs {d2}"
    assert d1["status"] == d2["status"]


# ── 5. Errors ──


def test_verify_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-verify", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_verify_db_path_none_exits_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → exit 1, no traceback.

    The verify command uses ``assert db_path is not None`` (not
    ``typer.echo``), so the message lands in ``result.exception`` rather
    than ``result.output``.  We assert the exit code and absence of a
    raw Python traceback.
    """
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-verify"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_verify_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_verify_nonexistent_disk_exits_gracefully(tmp_path, test_config) -> None:
    """``--disk`` pointing to a non-existent disk → friendly error, no traceback."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify", "--disk", "nonexistent_disk_xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_verify_json_schema_valid(tmp_path, test_config) -> None:
    """``--format json`` output matches expected schema."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    mount = tmp_path / "OutputDisk"
    mount.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "OutputDisk", mount)
    seed_media_file_on_disk(conn, disk_id, mount, "media", "test.mkv")
    conn.close()
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["--format", "json", "library-verify"])
    assert result.exit_code == 0
    assert_json_schema(result, required_keys=["status", "files_walked"])


def test_verify_error_exits_nonzero(tmp_path, test_config) -> None:
    """Non-existent disk → non-zero exit code."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify", "--disk", "nonexistent_disk_xyz123"])
    assert result.exit_code != 0


# ── 7. Events ──


def test_verify_emits_library_scan_completed(tmp_path, test_config, monkeypatch) -> None:
    """Verify-mode scan emits ``LibraryScanCompleted`` on the EventBus."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    mount = tmp_path / "EventDisk"
    mount.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "EventDisk", mount)
    seed_media_file_on_disk(conn, disk_id, mount, "media", "test.mkv")
    conn.close()

    captured = capture_event_bus(monkeypatch)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_GUARD, return_value=None):
        result = run_cli(["library-verify"])

    assert result.exit_code == 0, result.output
    assert len(captured) >= 1, f"Expected at least 1 event, got {len(captured)}"
    event_types = {type(e).__name__ for e in captured}
    assert "LibraryScanCompleted" in event_types, f"LibraryScanCompleted not emitted. Captured: {event_types}"
