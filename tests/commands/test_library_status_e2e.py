"""E2E tests for ``personalscraper library-status`` — CLI-level harness.

Exercises the read-only status summary view against a synthetic DB.
Every test asserts visible breakdown counters so the operator sees WHY
a number is what it is (BD-D pattern).
"""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
    seed_index_outbox,
    seed_repair_queue,
    seed_scan_run,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── 1. Smoke ───────────────────────────────────────────────────────────────────


def test_status_help_exits_zero() -> None:
    """``library-status --help`` exits 0 and mentions the command."""
    result = run_cli(["library-status", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-status" in result.output


# ── 2. Realistic scenarios ────────────────────────────────────────────────────


def test_status_empty_db_shows_no_scans(tmp_path, test_config) -> None:
    """Fresh DB — status table header, 'no scans yet', counters at zero."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-status"])

    assert result.exit_code == 0, result.output
    output = result.output
    assert "DISK" in output, f"Table header missing: {output}"
    assert "no scans yet" in output, f"'no scans yet' missing: {output}"
    assert "repair queue: depth=0" in output, f"Repair queue depth not zero: {output}"
    assert "outbox pending: 0" in output, f"Outbox pending not zero: {output}"


def test_status_after_seeded_scan_run_shows_summary(tmp_path, test_config) -> None:
    """Seed a completed scan_run + disk → status includes disk label and scan summary."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    seed_disk(conn, "StatusDisk", tmp_path / "StatusDisk")
    seed_scan_run(conn, status="ok", mode="full", generation=5, disk_filter=None)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-status"])

    assert result.exit_code == 0, result.output
    output = result.output
    assert "StatusDisk" in output, f"Disk label missing: {output}"
    assert "latest scan:" in output, f"Latest scan summary missing: {output}"
    assert "generation=5" in output, f"Generation not shown: {output}"


def test_status_shows_repair_queue_pending_count(tmp_path, test_config) -> None:
    """3 pending repair_queue rows → 'repair queue: depth=3'."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    for i in range(3):
        seed_repair_queue(conn, scope="item", scope_id=i + 1, reason="test.backlog")
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-status"])

    assert result.exit_code == 0, result.output
    assert "repair queue: depth=3" in result.output, f"Expected depth=3, got: {result.output}"


def test_status_shows_outbox_pending_count(tmp_path, test_config) -> None:
    """5 pending index_outbox rows → 'outbox pending: 5'."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    for _ in range(5):
        seed_index_outbox(conn, status="pending")
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-status"])

    assert result.exit_code == 0, result.output
    assert "outbox pending: 5" in result.output, f"Expected outbox pending=5, got: {result.output}"


# ── 3. Format flag ─────────────────────────────────────────────────────────────


def test_status_format_json_emits_parseable_json(tmp_path, test_config) -> None:
    """``--format json`` produces valid JSON with the expected top-level keys."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    seed_disk(conn, "JsonDisk", tmp_path / "JsonDisk")
    seed_scan_run(conn, status="ok", mode="full", generation=3, finished_at=now)
    seed_repair_queue(conn, scope="item", scope_id=1, reason="test.json")
    seed_index_outbox(conn, status="pending")
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-status"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)

    assert "disks" in data, f"disks key missing: {data}"
    assert isinstance(data["disks"], list)
    assert len(data["disks"]) >= 1, f"No disks in JSON output: {data}"
    assert data["disks"][0]["label"] == "JsonDisk"

    assert data["latest_scan"] is not None, f"latest_scan is None: {data}"
    assert data["latest_scan"]["status"] == "ok"

    assert "repair_queue" in data, f"repair_queue key missing: {data}"
    assert data["repair_queue"]["depth"] >= 1

    assert "outbox_pending" in data, f"outbox_pending key missing: {data}"
    assert data["outbox_pending"] >= 1

    assert "deleted_items" in data
    assert "enrich_pending" in data
    assert "category_orphans" in data
    assert "healthy" in data
