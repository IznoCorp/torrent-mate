"""E2E tests for ``personalscraper library-reconcile`` — CLI-level harness.

Covers all 7 detector scopes via CliRunner with a synthetic DB and
patched config.  The closure-of-loop test (BD-D regression guard) is the
anchor: it reproduces the 2026-05-23 incident where repair "succeeded"
332/332 but detect_path_missing immediately re-flagged the same paths
because the path row was never deleted.
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
    seed_media_item_with_release,
    seed_phantom_path,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── helpers ───────────────────────────────────────────────────────────────────


def _seed_db_with_phantom_path(db_path: Path, tmp_path: Path) -> tuple[int, int]:
    """Seed a disk + phantom path in *db_path*, return (disk_id, path_id).

    The disk mount_path points at *tmp_path*, which exists, so
    ``detect_path_missing`` can resolve paths under it.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "TestDisk", tmp_path)
    path_id = seed_phantom_path(conn, disk_id, "nonexistent_dir", n_files=3)
    conn.close()
    return disk_id, path_id


# ── 1. Smoke / happy path ─────────────────────────────────────────────────────


def test_reconcile_clean_db_finds_nothing(tmp_path, test_config) -> None:
    """Empty DB + library-reconcile → total_findings=0, rc=0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-reconcile"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["total_findings"] == 0, f"Unexpected findings on clean DB: {data}"
    assert data["path_missing_count"] == 0
    assert len(data["merkle_drift"]) == 0
    assert data["dispatch_path_missing_count"] == 0
    assert data["enrich_stale"] == 0
    assert data["release_orphans_count"] == 0
    assert data["files_without_release"] == 0
    assert data["season_count_drift_count"] == 0
    assert data["items_without_files_count"] == 0


# ── 2. Realistic scenarios ────────────────────────────────────────────────────


def test_reconcile_path_missing_finds_phantom_path(tmp_path, test_config) -> None:
    """Seed a phantom path → reconcile detects it in path_missing_count."""
    db_path = make_synthetic_db(tmp_path)
    _seed_db_with_phantom_path(db_path, tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-reconcile"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["path_missing_count"] >= 1, (
        f"Expected >= 1 phantom path, got path_missing_count={data['path_missing_count']}: {data}"
    )
    assert data["total_findings"] >= 1


def test_reconcile_scope_filter_limits_detection(tmp_path, test_config) -> None:
    """``--scope path_missing`` only runs the path_missing detector."""
    db_path = make_synthetic_db(tmp_path)
    _seed_db_with_phantom_path(db_path, tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-reconcile", "--scope", "path_missing"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["path_missing_count"] >= 1
    # All other detectors should be zero (scope filtered).
    assert len(data["merkle_drift"]) == 0
    assert data["dispatch_path_missing_count"] == 0


def test_reconcile_release_orphans_finds_orphan_release(tmp_path, test_config) -> None:
    """Seed media_release with no media_file → release_orphans_count >= 1."""
    db_path = make_synthetic_db(tmp_path)
    # Insert a release with no files — detect_release_orphans will flag it.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    seed_media_item_with_release(conn, "Orphan Movie", "movies")
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-reconcile"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["release_orphans_count"] >= 1, (
        f"Expected >= 1 orphan release, got {data['release_orphans_count']}: {data}"
    )


# ── 3. Closure-of-loop (THE BD-D PATTERN) ─────────────────────────────────────


def test_reconcile_path_missing_enqueue_then_repair_closes_loop(tmp_path, test_config) -> None:
    """Seed phantom → enqueue → repair → re-detect = 0.

    This is the BD-D regression test at the CLI level (2026-05-23 incident):
    soft_delete_subtree previously forgot to hard-delete the path row, so
    detect_path_missing kept re-flagging the same phantom path after repair
    claimed success.  This test fails if the closure-of-loop is broken.
    """
    db_path = make_synthetic_db(tmp_path)
    _seed_db_with_phantom_path(db_path, tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Step 1: reconcile with enqueue → repair_queue gets a row.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["--format", "json", "library-reconcile", "--enqueue-repairs"])
    assert r1.exit_code == 0, r1.output
    d1 = json_from_result(r1)
    assert d1["path_missing_count"] >= 1, f"Pre-condition: expected phantom paths before repair, got {d1}"
    assert d1["enqueued_repairs"] >= 1, f"Expected repair enqueued, got enqueued_repairs={d1['enqueued_repairs']}"

    # Step 2: drain the repair queue.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(["--format", "json", "library-repair"])
    assert r2.exit_code == 0, r2.output
    d2 = json_from_result(r2)
    assert d2["succeeded"] >= 1, f"Repair should have succeeded at least 1 row, got {d2}"
    assert d2["pending_depth"] == 0, (
        f"Repair queue should be empty after drain, got pending_depth={d2.get('pending_depth')}"
    )

    # Step 3: re-detect must return 0 phantom paths.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r3 = run_cli(["--format", "json", "library-reconcile"])
    assert r3.exit_code == 0, r3.output
    d3 = json_from_result(r3)
    assert d3["path_missing_count"] == 0, (
        f"CLOSURE-OF-LOOP BROKEN: detect_path_missing still found {d3['path_missing_count']} "
        f"phantom paths after repair drain.  This is the BD-D regression.  Full output: {d3}"
    )
    assert d3["total_findings"] == 0, (
        f"CLOSURE-OF-LOOP BROKEN: total_findings={d3['total_findings']} after repair: {d3}"
    )


# ── 4. Idempotence ────────────────────────────────────────────────────────────


def test_reconcile_idempotent_when_clean(tmp_path, test_config) -> None:
    """Two consecutive reconcile runs on a clean DB return the same output."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["--format", "json", "library-reconcile"])
        r2 = run_cli(["--format", "json", "library-reconcile"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    d1 = json_from_result(r1)
    d2 = json_from_result(r2)
    assert d1["total_findings"] == d2["total_findings"] == 0
    assert d1 == d2, f"Reconcile output changed between runs: {d1} vs {d2}"


def test_reconcile_enqueue_idempotent(tmp_path, test_config) -> None:
    """Enqueuing repairs twice does not duplicate them (partial UNIQUE index)."""
    db_path = make_synthetic_db(tmp_path)
    _seed_db_with_phantom_path(db_path, tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["--format", "json", "library-reconcile", "--enqueue-repairs"])
        r2 = run_cli(["--format", "json", "library-reconcile", "--enqueue-repairs"])

    d1 = json_from_result(r1)
    d2 = json_from_result(r2)
    # Second enqueue should find no new rows to insert (deduped).
    assert d2["enqueued_repairs"] == 0, f"Second enqueue should be a no-op, got {d2['enqueued_repairs']}"
    # The first run enqueued something.
    assert d1["enqueued_repairs"] >= 1
