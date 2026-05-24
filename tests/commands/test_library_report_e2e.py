"""E2E tests for ``personalscraper library-report`` — CLI-level harness.

Tests the indexer-backed aggregate report (totals, sizes), graceful
degradation when supplementary JSON files are missing, and --format json.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_json_schema,
    assert_no_python_traceback,
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _seed_report_item(
    conn: sqlite3.Connection,
    disk_id: int,
    mount_path: Path,
    title: str,
    category_id: str,
    kind: str,
    size_bytes: int = 2_000_000_000,
) -> int:
    """Seed a minimal item → release → file chain for report aggregation.

    Returns item_id.
    """
    now = int(time.time())
    rel_path = f"cat_{category_id}/{title}"
    disk_label = f"uuid-{disk_id}"

    cursor = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "date_created, date_modified) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (kind, title, title, category_id, now, now),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]

    cursor = conn.execute(
        "INSERT INTO media_release (item_id, edition) VALUES (?, 'Standard')",
        (item_id,),
    )
    release_id: int = cursor.lastrowid  # type: ignore[assignment]

    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    path_id: int = cursor.lastrowid  # type: ignore[assignment]

    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, "
        "mtime_ns, ctime_ns, oshash, scan_generation, last_verified_at, "
        "enriched_at, deleted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'abc123', 1, ?, NULL, NULL)",
        (release_id, path_id, f"{title}.mkv", size_bytes, now, now, now),
    )

    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_disk', ?)",
        (item_id, disk_label),
    )

    conn.commit()
    return item_id


# ── 1. Help ─────────────────────────────────────────────────────────────────────


def test_report_help_exits_zero() -> None:
    """--help exits 0 and shows usage."""
    result = run_cli(["library-report", "--help"])
    assert result.exit_code == 0, result.output
    assert "statistics" in result.output.lower() or "report" in result.output.lower()


# ── 2. Aggregation from indexer ──────────────────────────────────────────────────


def test_report_aggregates_indexer_totals(tmp_path, test_config) -> None:
    """3 items + 4 files across 2 disks → report shows correct totals."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    disk_a = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    disk_b = seed_disk(conn, "drive_b", tmp_path / "drive_b")

    _seed_report_item(
        conn,
        disk_a,
        tmp_path / "drive_a",
        title="Movie A (2024)",
        category_id="movies",
        kind="movie",
        size_bytes=3_000_000_000,
    )
    _seed_report_item(
        conn,
        disk_a,
        tmp_path / "drive_a",
        title="Movie B (2023)",
        category_id="movies",
        kind="movie",
        size_bytes=2_000_000_000,
    )
    _seed_report_item(
        conn,
        disk_b,
        tmp_path / "drive_b",
        title="Show C (2024)",
        category_id="tv_shows",
        kind="show",
        size_bytes=5_000_000_000,
    )
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-report"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["total_items"] == 3, f"Expected 3 items, got {data.get('total_items')}"
    assert data["total_size_gb"] > 0, f"Expected non-zero size: {data}"

    # Size calculation: 3+2+5 GB = 10 GB → ~9.3 GiB
    total = 3_000_000_000 + 2_000_000_000 + 5_000_000_000  # 10 GB
    expected_gb = round(total / (1024**3), 1)
    assert data["total_size_gb"] == expected_gb, f"Expected {expected_gb} GB, got {data['total_size_gb']}"


# ── 3. Missing supplementary JSON ────────────────────────────────────────────────


def test_report_handles_missing_supplementary_json(tmp_path, test_config) -> None:
    """No library_validation.json / library_recommendations.json → report continues."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_report_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Solo Item (2024)",
        category_id="movies",
        kind="movie",
        size_bytes=2_000_000_000,
    )
    conn.close()

    # Ensure data_dir exists but has no validation/recommendation JSON files.
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    assert not (data_dir / "library_validation.json").exists()
    assert not (data_dir / "library_recommendations.json").exists()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-report"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    assert data["total_items"] == 1
    # Validation/recommendation sections should be zero/empty.
    assert data["validation_valid"] == 0
    assert data["recommendation_count"] == 0


# ── 4. Format JSON ──────────────────────────────────────────────────────────────


def test_report_format_json(tmp_path, test_config) -> None:
    """--format json produces a parseable JSON report."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_report_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Format Report (2024)",
        category_id="movies",
        kind="movie",
        size_bytes=2_000_000_000,
    )
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-report"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    # Check that JSON contains expected top-level fields.
    assert "generated_at" in data
    assert "total_items" in data
    assert "total_size_gb" in data
    assert "items_per_disk" in data
    assert "items_per_category" in data
    assert "nfo_valid_count" in data
    assert "nfo_invalid_count" in data
    assert isinstance(data["total_items"], int)


# ── 3. Errors ──


def test_report_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-report", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_report_db_path_none_exits_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → exit non-zero, no traceback."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-report"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_report_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-report"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_report_json_schema_valid(tmp_path, test_config) -> None:
    """``--format json`` output matches expected schema."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_report_item(conn, disk_id, tmp_path / "drive_a", title="Test (2024)", category_id="movies", kind="movie")
    conn.close()
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-report"])
    assert result.exit_code == 0
    data = assert_json_schema(
        result,
        required_keys=[
            "generated_at",
            "total_items",
            "total_size_gb",
            "items_per_disk",
            "items_per_category",
        ],
    )
    assert isinstance(data["total_items"], int)


def test_report_error_exits_nonzero(test_config) -> None:
    """Error condition → non-zero exit code."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-report"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-report`` is a read-only aggregate diagnostic command.  It
# queries the indexer database for totals/sizes/distributions and optionally
# merges supplementary JSON files (library_validation.json,
# library_recommendations.json).  No domain event is published.
