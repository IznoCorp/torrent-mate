"""E2E tests for ``personalscraper library-index`` — CLI-level harness.

Covers full-mode, quick-mode short-circuit, bulk-change protection,
and the BD-D #2 regression guard (soft_delete_subtree merkle refresh).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_GUARD = "personalscraper.indexer.scanner.guard_disk_mounted"

# ── helpers ───────────────────────────────────────────────────────────────────


def _create_disk_with_files(mount: Path, n_files: int = 3) -> None:
    """Create *mount* directory and *n_files* .mkv test files under it."""
    mount.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        f = mount / f"test_{i:03d}.mkv"
        f.write_bytes(b"X" * 131072)  # 128 KiB — enough for oshash


def _pre_seed_disk(db_path: Path, label: str, mount: Path) -> int:
    """Seed a disk row and return its id, so bootstrap is not triggered."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, label, mount)
    conn.close()
    return disk_id


def _run_index(args: list[str], config, db_path):
    """Run ``library-index`` with config + guard patched, return CliRunner Result."""
    cfg = make_test_config_with_db(config, db_path)
    with (
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_GUARD, return_value=None),
    ):
        return run_cli(["library-index", *args])


def _full_scan(db_path: Path, config) -> None:
    """Run library-index --mode full to populate the DB from scratch.

    Precondition: a disk row must already exist in the DB for the mount
    path that contains the test files.  Call ``_pre_seed_disk`` first.
    """
    result = _run_index(["--mode", "full"], config, db_path)
    assert result.exit_code == 0, f"full scan failed: {result.output}"


# ── 1. Smoke / dry-run ───────────────────────────────────────────────────────


def test_index_help_exits_zero() -> None:
    """``library-index --help`` exits 0."""
    result = run_cli(["library-index", "--help"])
    assert result.exit_code == 0


def test_index_dry_run_no_writes(tmp_path, test_config) -> None:
    """Dry-run does not persist any rows."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _create_disk_with_files(mount, n_files=3)
    _pre_seed_disk(db_path, "drive_a", mount)

    result = _run_index(["--mode", "full", "--dry-run"], test_config, db_path)
    assert result.exit_code == 0, result.output

    # Verify no rows were persisted after dry-run.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    path_count = conn.execute("SELECT COUNT(*) FROM path").fetchone()[0]
    mf_count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
    conn.close()
    assert path_count == 0, f"Expected 0 path rows after dry-run, got {path_count}"
    assert mf_count == 0, f"Expected 0 media_file rows after dry-run, got {mf_count}"


# ── 2. Full mode ─────────────────────────────────────────────────────────────


def test_index_full_mode_creates_disk_and_paths(tmp_path, test_config) -> None:
    """Full scan on a synthetic FS populates disk, path, and media_file rows."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _create_disk_with_files(mount, n_files=3)
    disk_id = _pre_seed_disk(db_path, "drive_a", mount)

    result = _run_index(["--mode", "full"], test_config, db_path)
    assert result.exit_code == 0, result.output

    data = json_from_result(result)
    assert data["files_walked"] == 3
    assert data["dirs_walked"] >= 1
    assert data["status"] == "ok"

    # Verify DB state.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    path_count = conn.execute("SELECT COUNT(*) FROM path").fetchone()[0]
    assert path_count >= 1, "Expected at least 1 path row"
    mf_count = conn.execute("SELECT COUNT(*) FROM media_file WHERE deleted_at IS NULL").fetchone()[0]
    assert mf_count == 3, f"Expected 3 media_file rows, got {mf_count}"
    row = conn.execute("SELECT merkle_root FROM disk WHERE id = ?", (disk_id,)).fetchone()
    assert row is not None
    assert row[0] is not None, "merkle_root should be populated after first full scan"
    conn.close()


# ── 3. Quick mode ────────────────────────────────────────────────────────────


def test_index_quick_mode_short_circuits_on_clean_merkle(tmp_path, test_config) -> None:
    """Quick mode on a clean DB (merkle match) short-circuits without walking."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _create_disk_with_files(mount, n_files=3)
    _pre_seed_disk(db_path, "drive_a", mount)
    _full_scan(db_path, test_config)

    result = _run_index(["--mode", "quick"], test_config, db_path)
    assert result.exit_code == 0, result.output

    data = json_from_result(result)
    assert data["files_walked"] == 0, f"Quick mode should short-circuit (0 files walked), got {data}"
    assert data["disks_skipped"] >= 1, f"Expected >=1 disk skipped (merkle hit), got {data}"


def test_index_quick_bulk_change_protection_fires_without_confirm(tmp_path, test_config) -> None:
    """Quick mode raises when stored merkle ≠ computed AND FS delta > 50%."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _create_disk_with_files(mount, n_files=3)
    _pre_seed_disk(db_path, "drive_a", mount)
    _full_scan(db_path, test_config)

    # Corrupt: modify stored sizes in DB AND set a bogus merkle_root so
    # quick mode detects a merkle miss, then the bulk-change check compares
    # DB fingerprints (modified sizes) against filesystem fingerprints
    # (real sizes) and finds a > 50% delta.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("UPDATE media_file SET size_bytes = size_bytes + 999999 WHERE filename = 'test_000.mkv'")
    conn.execute("UPDATE media_file SET size_bytes = size_bytes + 999999 WHERE filename = 'test_001.mkv'")
    conn.execute("UPDATE disk SET merkle_root = '0000000000000000'")
    conn.commit()
    conn.close()

    result = _run_index(["--mode", "quick"], test_config, db_path)
    assert result.exit_code != 0, (
        f"Expected non-zero exit (bulk-change detected), got {result.exit_code}: {result.output}"
    )
    assert "bulk restore" in result.output.lower(), f"Expected 'bulk restore' message: {result.output}"


def test_index_quick_bulk_change_passes_with_confirm(tmp_path, test_config) -> None:
    """--confirm-bulk-change bypasses the freeze guard, even on high delta."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _create_disk_with_files(mount, n_files=3)
    _pre_seed_disk(db_path, "drive_a", mount)
    _full_scan(db_path, test_config)

    # Same corruption as above.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("UPDATE media_file SET size_bytes = size_bytes + 999999 WHERE filename = 'test_000.mkv'")
    conn.execute("UPDATE media_file SET size_bytes = size_bytes + 999999 WHERE filename = 'test_001.mkv'")
    conn.execute("UPDATE disk SET merkle_root = '0000000000000000'")
    conn.commit()
    conn.close()

    result = _run_index(["--mode", "quick", "--confirm-bulk-change"], test_config, db_path)
    assert result.exit_code == 0, result.output

    data = json_from_result(result)
    assert data["files_walked"] > 0, f"With confirm-bulk-change, quick mode should walk files: {data}"


# ── 4. BD-D #2 regression guard ──────────────────────────────────────────────


def test_index_post_soft_delete_subtree_no_bulk_change(tmp_path, test_config) -> None:
    """BD-D #2: after soft_delete_subtree, quick mode must NOT trip bulk-change.

    Regression for 2026-05-23 incident where soft_delete_subtree forgot to
    refresh disk.merkle_root, causing library-index --mode quick to fail with
    bulk-change-detected on every run (82-93% delta). Fix landed in commit
    00599f8 — the cascade now calls _refresh_disk_merkle.
    """
    from personalscraper.indexer.repair import soft_delete_subtree  # noqa: PLC0415

    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "drive_a"
    _create_disk_with_files(mount, n_files=3)
    _pre_seed_disk(db_path, "drive_a", mount)
    _full_scan(db_path, test_config)

    # Get a path_id to soft-delete.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    path_row = conn.execute(
        """
        SELECT p.id, p.disk_id FROM path p
        JOIN disk d ON d.id = p.disk_id
        WHERE d.mount_path = ?
        LIMIT 1
        """,
        (str(mount),),
    ).fetchone()
    assert path_row is not None, "Expected at least one path row after full scan"
    path_id = path_row[0]
    disk_id = path_row[1]

    n_soft = soft_delete_subtree(conn, path_id)
    conn.commit()
    assert n_soft >= 1, f"soft_delete_subtree should have tombstoned files, got {n_soft}"

    # Verify merkle was refreshed (not None, not bogus).
    stored_merkle = conn.execute("SELECT merkle_root FROM disk WHERE id = ?", (disk_id,)).fetchone()[0]
    assert stored_merkle is not None, "merkle_root should be refreshed after soft_delete_subtree"
    conn.close()

    # Quick mode must NOT trigger bulk-change.
    result = _run_index(["--mode", "quick"], test_config, db_path)
    assert result.exit_code == 0, (
        f"BD-D #2 REGRESSION: quick mode failed after soft_delete_subtree: "
        f"exit_code={result.exit_code}, output={result.output}"
    )
    data = json_from_result(result)
    assert data["files_walked"] == 0, (
        f"BD-D #2: expected quick mode short-circuit (merkle hit) after "
        f"soft_delete_subtree, but files_walked={data['files_walked']}. "
        f"Data: {data}"
    )
