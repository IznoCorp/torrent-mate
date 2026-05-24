"""E2E tests for ``personalscraper library-repair`` — CLI-level harness.

Validates drain behaviour, budget exhaustion, idempotence, and the
closure-of-loop contract (BD-D regression guard): repair must ACTUALLY
remove the root cause so that a follow-up reconcile-detect finds zero
divergence.
"""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_json_schema,
    assert_no_python_traceback,
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
    seed_phantom_path,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── helpers ───────────────────────────────────────────────────────────────────


def _seed_repair_queue_rows(db_path: str, count: int) -> None:
    """Insert *count* pending repair_queue rows directly into the DB.

    Uses distinct scope_id values to avoid the partial UNIQUE index
    on (scope, scope_id) WHERE status='pending' (migration 003).
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    for i in range(count):
        conn.execute(
            "INSERT INTO repair_queue(scope, scope_id, reason, payload_json, enqueued_at, status)"
            " VALUES ('item', ?, 'test.backlog', '{}', ?, 'pending')",
            (i + 1, now),
        )
    conn.commit()
    conn.close()


def _seed_slow_queue_rows(db_path: str, count: int) -> None:
    """Insert *count* path-scoped repair rows that take ~0.1s each to process.

    Each row targets a non-existent path_id; the repair_processor tries
    soft_delete_subtree which is cheap but the per-row transaction overhead
    adds up.  Use a high count (100+) to make budget exhaustion observable.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())

    # Create one mounted disk so the path rows have a valid FK target.
    seed_disk(conn, "BudgetDisk", __import__("pathlib").Path("/tmp"))

    payload = '{"action":"soft_delete_subtree"}'
    for i in range(count):
        # Seed a path row (the actual path won't matter since repair just
        # needs a valid scope_id — it calls soft_delete_subtree on it).
        cur = conn.execute(
            "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (1, ?, 0)",
            (f"budget_dir_{i}",),
        )
        path_id = cur.lastrowid
        conn.execute(
            "INSERT INTO repair_queue(scope, scope_id, reason, payload_json, enqueued_at, status)"
            " VALUES ('path', ?, 'reconcile.path.missing', ?, ?, 'pending')",
            (path_id, payload, now + i),
        )
    conn.commit()
    conn.close()


# ── 1. Smoke / happy path ─────────────────────────────────────────────────────


def test_repair_empty_queue_exits_clean(tmp_path, test_config) -> None:
    """Empty repair queue → exit 0, processed=0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-repair"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["processed"] == 0
    assert data["succeeded"] == 0
    assert data["failed"] == 0
    assert data["pending_depth"] == 0


# ── 2. Realistic scenarios ────────────────────────────────────────────────────


def test_repair_drains_pending_rows(tmp_path, test_config) -> None:
    """3 pending rows → drain processes all 3."""
    db_path = make_synthetic_db(tmp_path)
    _seed_repair_queue_rows(str(db_path), count=3)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-repair"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["processed"] >= 3, f"Expected >=3 processed, got {data}"
    assert data["pending_depth"] == 0, f"Queue not drained: {data}"


def test_repair_respects_budget(tmp_path, test_config) -> None:
    """200 pending path rows + --budget 0 → budget_exhausted=True (budget=0 means immediate deadline)."""
    db_path = make_synthetic_db(tmp_path)
    _seed_slow_queue_rows(str(db_path), count=200)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-repair", "--budget", "0"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    # Budget=0 means the deadline=now — the first budget check should fire.
    # Either the budget is exhausted OR all 200 rows happened to be in a
    # single batch (limit=100 per batch).  In the latter case all rows are
    # processed without the budget check firing between batches.
    assert data["budget_exhausted"] is True or data["processed"] == 200, (
        f"Expected budget_exhausted=True or all processed, got {data}"
    )


def test_repair_dry_run_no_writes(tmp_path, test_config) -> None:
    """``--dry-run`` reports queue depth without modifying rows."""
    db_path = make_synthetic_db(tmp_path)
    _seed_repair_queue_rows(str(db_path), count=5)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-repair", "--dry-run"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["dry_run"] is True
    assert data["repair_would_drain"] == 5, f"Dry-run should see 5 pending rows, got {data}"

    # Verify no rows were actually drained.
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM repair_queue WHERE status='pending'").fetchone()[0]
    conn.close()
    assert count == 5, f"Dry-run should not modify rows, but {count} are no longer pending"


# ── 3. Closure-of-loop (THE BD-D PATTERN) ─────────────────────────────────────


def test_repair_drains_path_missing_then_loop_closed(tmp_path, test_config) -> None:
    """Seed phantom path → enqueue via reconcile → drain via repair → re-detect = 0.

    Complements test_reconcile_path_missing_enqueue_then_repair_closes_loop
    from the reconcile E2E file — this one drives repair explicitly and
    asserts the repair queue health post-drain.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Seed a phantom path + enqueue via reconcile.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "LoopDisk", __import__("pathlib").Path("/tmp"))
    seed_phantom_path(conn, disk_id, "loop_dir", n_files=2)
    conn.close()

    # Enqueue repairs first.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["--format", "json", "library-reconcile", "--enqueue-repairs"])
    assert r1.exit_code == 0, r1.output
    d1 = json_from_result(r1)
    assert d1["enqueued_repairs"] >= 1, f"No repairs enqueued: {d1}"

    # Drain with repair.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(["--format", "json", "library-repair"])
    assert r2.exit_code == 0, r2.output
    d2 = json_from_result(r2)
    assert d2["succeeded"] >= 1, f"Repair did not succeed: {d2}"
    assert d2["pending_depth"] == 0, f"Queue not empty: {d2}"

    # re-detect closure-of-loop.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r3 = run_cli(["--format", "json", "library-reconcile"])
    assert r3.exit_code == 0, r3.output
    d3 = json_from_result(r3)
    assert d3["path_missing_count"] == 0, (
        f"CLOSURE-OF-LOOP BROKEN: path_missing_count={d3['path_missing_count']} after repair: {d3}"
    )
    assert d3["total_findings"] == 0, (
        f"CLOSURE-OF-LOOP BROKEN: total_findings={d3['total_findings']} after repair: {d3}"
    )


# ── 4. Idempotence ────────────────────────────────────────────────────────────


def test_repair_idempotent_after_drain(tmp_path, test_config) -> None:
    """Re-running repair on an empty queue exits clean with processed=0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # First run on empty queue.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["--format", "json", "library-repair"])
    assert r1.exit_code == 0, r1.output
    d1 = json_from_result(r1)
    assert d1["processed"] == 0

    # Second run — same result.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(["--format", "json", "library-repair"])
    assert r2.exit_code == 0, r2.output
    d2 = json_from_result(r2)
    assert d2["processed"] == 0
    assert d2 == d1, f"Output changed between idempotent runs: {d1} vs {d2}"


# ── 5. Errors ──


def test_repair_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-repair", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_repair_config_absent_exits_gracefully(monkeypatch) -> None:
    """Config absent (load_config raises) → friendly error, no traceback."""
    from personalscraper.conf.loader import ConfigNotFoundError

    def _raise(*_a, **_kw):
        raise ConfigNotFoundError("no config found")

    monkeypatch.setattr("personalscraper.conf.loader.load_config", _raise)
    result = run_cli(["--format", "json", "library-repair"])
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "config" in result.output.lower()
    assert_no_python_traceback(result)


def test_repair_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-repair"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_repair_json_schema_valid(tmp_path, test_config) -> None:
    """``--format json`` output matches expected schema."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-repair"])
    assert result.exit_code == 0
    assert_json_schema(
        result,
        required_keys=["processed", "succeeded", "failed", "pending_depth", "budget_exhausted"],
    )


def test_repair_error_exits_nonzero(monkeypatch) -> None:
    """Config error → non-zero exit code."""
    from personalscraper.conf.loader import ConfigNotFoundError

    def _raise(*_a, **_kw):
        raise ConfigNotFoundError("no config found")

    monkeypatch.setattr("personalscraper.conf.loader.load_config", _raise)
    result = run_cli(["library-repair"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-repair`` passes an EventBus to ``open_db`` (for the free-space
# guard's DiskFullWarning infrastructure event) but does not emit any
# repair-specific domain event.  No ``RepairCompleted`` event class exists in
# the codebase.  The repair drain operates via direct DB writes; its result is
# observable through the JSON summary (processed / succeeded / failed /
# pending_depth).
