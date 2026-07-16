"""E2E tests for ``personalscraper library-show`` — CLI-level harness.

Exercises single-item display end-to-end via CliRunner with a synthetic DB:
all sections, missing item, JSON format, and help smoke.
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
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _seed_show_item(conn: sqlite3.Connection, title: str = "Test Movie") -> int:
    """Seed a complete media_item with release, file, streams, and attributes.

    Returns the ``media_item.id`` of the created item.
    """
    now = int(time.time())

    # media_item
    cur = conn.execute(
        "INSERT INTO media_item"
        " (kind, title, title_sort, category_id, year, nfo_status, date_created, date_modified)"
        " VALUES ('movie', ?, ?, 'movies', 2023, 'valid', ?, ?)",
        (title, title, now, now),
    )
    item_id: int = cur.lastrowid  # type: ignore[assignment]

    # media_release
    cur = conn.execute(
        "INSERT INTO media_release (item_id, edition) VALUES (?, 'Standard')",
        (item_id,),
    )
    release_id: int = cur.lastrowid  # type: ignore[assignment]

    # disk
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes)"
        " VALUES ('uuid-show', 'ShowDisk', '/tmp/showdisk', ?, 1, 0)",
        (now,),
    )
    disk_id: int = cur.lastrowid  # type: ignore[assignment]

    # path
    cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, 'Movies/Test Movie', ?)",
        (disk_id, now),
    )
    path_id: int = cur.lastrowid  # type: ignore[assignment]

    # media_file
    cur = conn.execute(
        "INSERT INTO media_file"
        " (release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns, oshash,"
        "  scan_generation, last_verified_at, enriched_at, deleted_at)"
        " VALUES (?, ?, 'test.mkv', 12345678, 1700000000000000000, 1700000000000000000,"
        "  'abc123def4567890', 1, ?, NULL, NULL)",
        (release_id, path_id, now),
    )
    file_id: int = cur.lastrowid  # type: ignore[assignment]

    # media_stream
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang, width, height, is_default)"
        " VALUES (?, 0, 'video', 'h264', 'eng', 1920, 1080, 1)",
        (file_id,),
    )
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang, is_default)"
        " VALUES (?, 1, 'audio', 'aac', 'eng', 1)",
        (file_id,),
    )

    # item_attribute
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'tmdb_id', '12345')",
        (item_id,),
    )
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'quality', 'BluRay-1080p')",
        (item_id,),
    )

    conn.commit()
    return item_id


# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_show_help_exits_zero() -> None:
    """``library-show --help`` exits 0."""
    result = run_cli(["library-show", "--help"])
    assert result.exit_code == 0, result.output


# ── 2. All sections ─────────────────────────────────────────────────────────────


def test_show_existing_item_prints_all_sections(tmp_path, test_config) -> None:
    """Showing a seeded item prints item, seasons, files, attributes sections."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_show_item(conn, "Test Movie")
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-show", "1"])

    assert result.exit_code == 0, result.output
    # Default (rich) output includes the item header and sections.
    assert "media_item id=1" in result.output
    assert "Test Movie" in result.output
    assert "media_files" in result.output
    assert "item_attributes" in result.output


# ── 3. Missing item ──────────────────────────────────────────────────────────────


def test_show_missing_item_exits_two(tmp_path, test_config) -> None:
    """``library-show 99999`` exits 2 for a non-existent item id."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-show", "99999"])

    assert result.exit_code == 2, f"Expected exit 2 for missing item, got {result.exit_code}: {result.output}"


# ── 4. JSON format ──────────────────────────────────────────────────────────────


def test_show_format_json_emits_structured_dict(tmp_path, test_config) -> None:
    """``--format json`` emits a dict with item/seasons/files/attributes/deleted_history."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_show_item(conn, "Test Movie")
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-show", "1"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result, source_attr="stdout")
    for key in ("item", "files", "attributes", "deleted_history"):
        assert key in data, f"Missing key '{key}' in JSON payload: {list(data)}"
    # The item section is a dict, not a list.
    assert isinstance(data["item"], dict)
    assert data["item"]["title"] == "Test Movie"
    assert data["item_id"] == 1
    # Verify files array contains a file with streams.
    assert len(data["files"]) >= 1, f"No files in payload: {data}"
    file0 = data["files"][0]
    assert "filename" in file0
    assert "streams" in file0
    assert len(file0["streams"]) >= 1
    # Verify attributes.
    assert len(data["attributes"]) >= 1


# ── 3. Errors ──


def test_show_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-show", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_show_db_path_none_exits_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → exit non-zero, no traceback."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-show", "1"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_show_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-show", "1"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_show_json_schema_valid(tmp_path, test_config) -> None:
    """``--format json`` output matches expected schema."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _seed_show_item(conn, "Test Movie")
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-show", str(item_id)])
    assert result.exit_code == 0
    data = assert_json_schema(
        result,
        required_keys=["item", "item_id", "files", "attributes", "deleted_history"],
        source_attr="stdout",
    )
    assert isinstance(data["item"], dict)
    assert data["item"]["title"] == "Test Movie"
    assert isinstance(data["files"], list)
    assert isinstance(data["attributes"], list)


def test_show_error_exits_nonzero() -> None:
    """Invalid flag → non-zero exit code."""
    result = run_cli(["library-show", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-show`` is a read-only display command.  It runs a SELECT-based
# query to fetch a single media_item with its related rows (releases, files,
# streams, attributes, deleted_history).  No domain event is published.
# Read-only diagnostic commands like ``library-doctor`` and ``library-status``
# follow the same pattern.
