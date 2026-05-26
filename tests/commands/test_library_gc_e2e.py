"""E2E tests for ``personalscraper library-gc`` — CLI-level harness.

Exercises the index_outbox garbage-collection command with threshold,
dry-run, and idempotence guarantees.  Every test asserts visible
breakdown counters (BD-D pattern).
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
    seed_index_outbox,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _count_outbox_rows(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM index_outbox").fetchone()[0]
    conn.close()
    return count


def _count_outbox_by_status(db_path: str, status: str) -> int:
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM index_outbox WHERE status = ?", (status,)).fetchone()[0]
    conn.close()
    return count


# ── 1. Smoke ───────────────────────────────────────────────────────────────────


def test_gc_help_exits_zero() -> None:
    """``library-gc --help`` exits 0 and mentions the command."""
    result = run_cli(["library-gc", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-gc" in result.output


# ── 2. Realistic scenarios ────────────────────────────────────────────────────


def test_gc_empty_outbox_zero_purged(tmp_path, test_config) -> None:
    """Empty index_outbox → rows_deleted=0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc", "--older-than-days", "30"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["rows_deleted"] == 0, f"Expected 0 deleted, got {data}"
    assert data["dry_run"] is False


def test_gc_purges_done_rows_older_than_threshold(tmp_path, test_config) -> None:
    """Done rows with processed_at far in the past → purged."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    # processed_at = epoch start, always older than any threshold.
    for _ in range(4):
        seed_index_outbox(conn, status="done", processed_at=1)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc", "--older-than-days", "1"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["rows_deleted"] == 4, f"Expected 4 deleted, got {data}"
    assert data["dry_run"] is False

    # Verify rows are actually gone.
    remaining = _count_outbox_rows(str(db_path))
    assert remaining == 0, f"Expected 0 remaining rows, got {remaining}"


def test_gc_preserves_done_rows_within_threshold(tmp_path, test_config) -> None:
    """Done rows with processed_at = now → preserved (within threshold)."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    for _ in range(3):
        seed_index_outbox(conn, status="done", processed_at=now)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc", "--older-than-days", "90"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["rows_deleted"] == 0, f"Expected 0 deleted (rows are recent), got {data}"

    remaining = _count_outbox_rows(str(db_path))
    assert remaining == 3, f"Rows should be preserved, got {remaining}"


def test_gc_preserves_pending_rows(tmp_path, test_config) -> None:
    """Pending rows are NEVER purged regardless of age."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    # Pending rows with old created_at but no processed_at.
    for _ in range(3):
        seed_index_outbox(conn, status="pending")
    # Also seed a done row with old processed_at to verify only done rows are purged.
    seed_index_outbox(conn, status="done", processed_at=1)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc", "--older-than-days", "1"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    # Only the 1 done row should be deleted.
    assert data["rows_deleted"] == 1, f"Expected 1 deleted (only done row), got {data}"

    pending = _count_outbox_by_status(str(db_path), "pending")
    assert pending == 3, f"Pending rows must be preserved, got {pending}"


def test_gc_dry_run_no_writes(tmp_path, test_config) -> None:
    """``--dry-run`` reports count without DELETE."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    for _ in range(5):
        seed_index_outbox(conn, status="done", processed_at=1)
    conn.close()

    before = _count_outbox_rows(str(db_path))
    assert before == 5

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc", "--dry-run", "--older-than-days", "1"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["dry_run"] is True, f"Expected dry_run=True, got {data}"
    assert data["rows_to_delete"] == 5, f"Expected 5 rows_to_delete, got {data}"

    after = _count_outbox_rows(str(db_path))
    assert after == 5, f"Dry-run must not delete rows: {before} → {after}"


def test_gc_idempotent_on_clean_outbox(tmp_path, test_config) -> None:
    """Running gc twice on a clean outbox → second run deletes 0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    for _ in range(3):
        seed_index_outbox(conn, status="done", processed_at=1)
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["library-gc", "--older-than-days", "1"])
        r2 = run_cli(["library-gc", "--older-than-days", "1"])

    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    d1 = json_from_result(r1)
    d2 = json_from_result(r2)
    assert d1["rows_deleted"] == 3, f"First run should delete 3, got {d1}"
    assert d2["rows_deleted"] == 0, f"Second run should delete 0, got {d2}"


# ── 3. Errors ──


def test_gc_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-gc", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_gc_db_path_none_exits_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → exit 1, friendly message, no traceback."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc"])
    assert result.exit_code != 0
    assert "not configured" in result.output.lower() or "db_path" in result.output.lower()
    assert_no_python_traceback(result)


def test_gc_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc", "--older-than-days", "30"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_gc_json_schema_valid(tmp_path, test_config) -> None:
    """Output is parseable JSON with expected schema."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc", "--older-than-days", "30"])
    assert result.exit_code == 0
    assert_json_schema(result, required_keys=["dry_run", "older_than_days", "rows_deleted"])


def test_gc_error_exits_nonzero(test_config) -> None:
    """Unconfigured DB → non-zero exit."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-gc"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-gc`` creates a fresh EventBus solely for the ``open_db`` call
# (free-space guard / DiskFullWarning infrastructure event).  The GC logic
# itself (DELETE FROM index_outbox) emits no domain events.  No GcCompleted
# event class exists in the codebase.


# ── 8. Idempotence ──

# N/A: idempotence is verified by ``test_gc_idempotent_on_clean_outbox`` under
# §2 (Realistic scenarios) — it seeds 3 done rows, runs gc twice, and asserts
# rows_deleted=3 then 0.  The idempotence property (DELETE WHERE processed_at
# < threshold) holds at the SQL level and does not warrant a dedicated section.


# ── 9. Dry-run ──

# N/A: ``--dry-run`` behaviour is verified by ``test_gc_dry_run_no_writes``
# under §2 (Realistic scenarios) — it seeds 5 done rows, runs ``--dry-run``,
# and asserts dry_run=True + rows_to_delete=5 + zero rows actually deleted.
# The ``--dry-run`` flag is exercised; a dedicated section is unnecessary.


# ── 10. Closure-of-loop ──

# N/A: closure-of-loop for gc is the invariant "after gc, all outbox rows with
# processed_at < threshold are gone."  This is verified by
# ``test_gc_purges_done_rows_older_than_threshold`` (seeds → purges → asserts
# COUNT(*)=0) and ``test_gc_preserves_done_rows_within_threshold`` (asserts
# recent rows survive).  No separate closure test is needed.
