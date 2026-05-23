"""E2E tests for ``personalscraper library-doctor`` — CLI-level harness.

Exercises all 10 health checks via CliRunner with a synthetic DB and
patched config.  The closure-of-loop test (BD-D regression guard) seeds
phantom paths, runs reconcile+repair via CLI, then asserts the doctor's
phantom_paths check transitions from WARN to OK.
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
    seed_phantom_path,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── helpers ───────────────────────────────────────────────────────────────────


def _get_check(data: dict, name: str) -> dict | None:
    """Find a check by name in the doctor output."""
    for c in data.get("checks", []):
        if c.get("name") == name:
            return c
    return None


# ── 1. Smoke / happy path ─────────────────────────────────────────────────────


def test_doctor_clean_db_overall_ok(tmp_path, test_config) -> None:
    """Clean DB → all checks pass, exit 0, overall_status='ok'."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-doctor"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["overall_status"] in ("ok", "skip"), (
        f"Unexpected overall_status on clean DB: {data}"
    )

    # Verify every expected check is present and not FAIL.
    check_names = {c["name"] for c in data["checks"]}
    expected = {
        "integrity_check",
        "foreign_keys_pragma",
        "foreign_key_check",
        "schema_version_coherent",
        "no_stuck_scan_run",
        "repair_queue_backlog",
        "index_outbox_lag",
        "merkle_drift",
        "canonical_provider_populated",
        "phantom_paths",
    }
    for name in expected:
        assert name in check_names, f"Check '{name}' missing from doctor output"
        chk = _get_check(data, name)
        assert chk is not None
        assert chk["status"] != "fail", (
            f"Check '{name}' FAIL on clean DB: {chk}"
        )


# ── 2. Realistic scenarios ────────────────────────────────────────────────────


def test_doctor_reports_canonical_provider_warn_below_threshold(
    tmp_path, test_config
) -> None:
    """50% canonical_provider coverage + threshold=80% → WARN."""
    db_path = make_synthetic_db(tmp_path)
    # Seed 2 items: 1 with canonical_provider, 1 without → 50% coverage.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    _cols = "kind, title, title_sort, category_id, date_created, date_modified, canonical_provider"
    conn.execute(
        f"INSERT INTO media_item({_cols}) VALUES ('movie', 'Movie A', 'Movie A', 'movies', ?, ?, 'tmdb')",
        (now, now),
    )
    conn.execute(
        f"INSERT INTO media_item({_cols}) VALUES ('movie', 'Movie B', 'Movie B', 'movies', ?, ?, NULL)",
        (now, now),
    )
    conn.commit()
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "--format", "json", "library-doctor",
                "--canonical-threshold-pct", "80",
            ]
        )

    assert result.exit_code != 0, (
        f"Expected non-zero exit for WARN, got {result.exit_code}: {result.output}"
    )
    data = json_from_result(result)
    assert data["overall_status"] == "warn", (
        f"Expected overall_status='warn' for 50% < 80%, got {data}"
    )
    chk = _get_check(data, "canonical_provider_populated")
    assert chk is not None, "canonical_provider_populated check missing"
    assert chk["status"] == "warn", (
        f"Expected warn status, got {chk}"
    )


def test_doctor_reports_repair_queue_backlog_above_threshold(
    tmp_path, test_config
) -> None:
    """3 pending repair rows + threshold=1 → WARN."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    for i in range(3):
        conn.execute(
            "INSERT INTO repair_queue(scope, scope_id, reason, payload_json, enqueued_at, status)"
            " VALUES ('item', ?, 'test.backlog', '{}', ?, 'pending')",
            (i + 1, now),
        )
    conn.commit()
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "--format", "json", "library-doctor",
                "--repair-queue-threshold", "1",
            ]
        )

    assert result.exit_code != 0, result.output
    data = json_from_result(result)
    assert data["overall_status"] in ("warn", "fail"), (
        f"Expected warn/fail for backlog, got {data}"
    )
    chk = _get_check(data, "repair_queue_backlog")
    assert chk is not None
    assert chk["status"] == "warn", (
        f"Expected warn for repair_queue_backlog at count=3 threshold=1, got {chk}"
    )


# ── 3. Closure-of-loop (THE BD-D PATTERN) ─────────────────────────────────────


def test_doctor_after_phantom_paths_then_repair_closes_warning(
    tmp_path, test_config
) -> None:
    """Seed phantom → doctor WARNs → reconcile+repair → doctor OK.

    This is the BD-D regression at the doctor level: phantom_paths check
    must transition from WARN back to OK after the repair drain actually
    removes the path row (closure-of-loop).
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Seed a phantom path in the DB.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "DoctorDisk", tmp_path)
    seed_phantom_path(conn, disk_id, "phantom_dir", n_files=2)
    conn.close()

    # Step 1: doctor should WARN about phantom_paths.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["--format", "json", "library-doctor"])
    assert r1.exit_code != 0, (
        f"Expected non-zero exit when phantom paths present: {r1.output}"
    )
    d1 = json_from_result(r1)
    phantom1 = _get_check(d1, "phantom_paths")
    assert phantom1 is not None, "phantom_paths check missing"
    assert phantom1["status"] == "warn", (
        f"Pre-condition: expected phantom_paths=warn, got {phantom1}"
    )

    # Step 2: reconcile + enqueue the phantom paths.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(
            ["--format", "json", "library-reconcile", "--enqueue-repairs"]
        )
    assert r2.exit_code == 0, r2.output

    # Step 3: repair drain.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r3 = run_cli(["--format", "json", "library-repair"])
    assert r3.exit_code == 0, r3.output
    d3 = json_from_result(r3)
    assert d3["pending_depth"] == 0, f"Repair queue not empty: {d3}"

    # Step 4: doctor must now be OK (phantom_paths check transitions to ok).
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r4 = run_cli(["--format", "json", "library-doctor"])
    assert r4.exit_code == 0, (
        f"CLOSURE-OF-LOOP BROKEN: doctor still non-zero after repair: {r4.output}"
    )
    d4 = json_from_result(r4)
    phantom4 = _get_check(d4, "phantom_paths")
    assert phantom4 is not None, "phantom_paths check missing after repair"
    assert phantom4["status"] == "ok", (
        f"CLOSURE-OF-LOOP BROKEN: phantom_paths still {phantom4['status']} "
        f"after repair drain: {phantom4}"
    )
    assert d4["overall_status"] in ("ok", "skip"), (
        f"CLOSURE-OF-LOOP BROKEN: overall_status={d4['overall_status']} after repair: {d4}"
    )


# ── 4. Idempotence ────────────────────────────────────────────────────────────


def test_doctor_idempotent(tmp_path, test_config) -> None:
    """Two consecutive doctor invocations return the same report."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["--format", "json", "library-doctor"])
        r2 = run_cli(["--format", "json", "library-doctor"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    d1 = json_from_result(r1)
    d2 = json_from_result(r2)

    # Timestamps may differ between runs, but statuses should be identical.
    assert d1["overall_status"] == d2["overall_status"], (
        f"Overall status changed between runs: {d1['overall_status']} vs {d2['overall_status']}"
    )
    for c1, c2 in zip(d1["checks"], d2["checks"]):
        assert c1["name"] == c2["name"]
        assert c1["status"] == c2["status"], (
            f"Check '{c1['name']}' changed: {c1['status']} → {c2['status']}"
        )
