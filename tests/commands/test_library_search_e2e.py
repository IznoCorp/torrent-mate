"""E2E tests for ``personalscraper library-search`` — CLI-level harness.

Exercises the flex-attr query language end-to-end via CliRunner with a
synthetic DB: field filters, negation, limit, unknown-field error, and
empty-DB behaviour.
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


def _seed_items(conn: sqlite3.Connection, items: list[dict]) -> None:
    """Insert multiple media_item rows from a list of field dicts."""
    now = int(time.time())
    for item in items:
        conn.execute(
            "INSERT INTO media_item"
            " (kind, title, title_sort, category_id, year, nfo_status, date_created, date_modified)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.get("kind", "movie"),
                item.get("title", "Untitled"),
                item.get("title", "Untitled"),
                item.get("category_id", "movies"),
                item.get("year"),
                item.get("nfo_status"),
                now,
                now,
            ),
        )
    conn.commit()


# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_search_help_exits_zero() -> None:
    """``library-search --help`` exits 0."""
    result = run_cli(["library-search", "--help"])
    assert result.exit_code == 0, result.output


# ── 2. Empty DB ─────────────────────────────────────────────────────────────────


def test_search_empty_db_returns_no_results(tmp_path, test_config) -> None:
    """Querying an empty DB returns exit 0 with (no results)."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-search", "year:2020"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result, source_attr="stdout")
    assert data["rows"] == []
    assert data["count"] == 0


# ── 3. Field filter ─────────────────────────────────────────────────────────────


def test_search_simple_field_filter_matches(tmp_path, test_config) -> None:
    """``year:2020`` returns only the rows whose year column equals 2020."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_items(
        conn,
        [
            {"title": "Movie 2020", "year": 2020, "nfo_status": "valid"},
            {"title": "Movie 2021", "year": 2021, "nfo_status": "valid"},
            {"title": "Show 2020", "kind": "show", "year": 2020, "category_id": "tv_shows"},
        ],
    )
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-search", "year:2020"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result, source_attr="stdout")
    assert data["count"] == 2, f"Expected 2 matches for year:2020, got {data['count']}"
    titles = {r["title"] for r in data["rows"]}
    assert titles == {"Movie 2020", "Show 2020"}


# ── 4. Negation ─────────────────────────────────────────────────────────────────


def test_search_negation_filter_excludes(tmp_path, test_config) -> None:
    """``-nfo:valid`` excludes items whose nfo_status is 'valid'."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_items(
        conn,
        [
            {"title": "Valid NFO", "year": 2020, "nfo_status": "valid"},
            {"title": "Missing NFO", "year": 2020, "nfo_status": "missing"},
            {"title": "Invalid NFO", "year": 2020, "nfo_status": "invalid"},
        ],
    )
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-search", "--", "-nfo:valid"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result, source_attr="stdout")
    assert data["count"] == 2, f"Expected 2 non-valid items, got {data['count']}"
    titles = {r["title"] for r in data["rows"]}
    assert "Valid NFO" not in titles
    assert titles == {"Missing NFO", "Invalid NFO"}


# ── 5. Limit ────────────────────────────────────────────────────────────────────


def test_search_limit_caps_results(tmp_path, test_config) -> None:
    """``--limit 3`` returns at most 3 rows even when 10 match."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_items(
        conn,
        [{"title": f"Movie {i}", "year": 2020, "nfo_status": "valid"} for i in range(10)],
    )
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-search", "--limit", "3", "year:2020"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result, source_attr="stdout")
    assert data["count"] == 3, f"Expected 3 rows with --limit 3, got {data['count']}"
    assert data["limit"] == 3


# ── 6. Unknown field ────────────────────────────────────────────────────────────


def test_search_unknown_field_exits_two(tmp_path, test_config) -> None:
    """Querying a flex attr with an unsupported operator (``custom:>=5``) exits 2."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-search", "custom:>=5"])

    assert result.exit_code == 2, (
        f"Expected exit 2 for invalid operator on flex attr, got {result.exit_code}: {result.output}"
    )


# ── 3. Errors ──


def test_search_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-search", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_search_db_path_none_exits_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → exit non-zero, no traceback."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-search", "year:2020"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_search_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-search", "year:2020"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_search_json_schema_valid(tmp_path, test_config) -> None:
    """``--format json`` output matches expected schema."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_items(conn, [{"title": "Test Movie", "year": 2020, "nfo_status": "valid"}])
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-search", "year:2020"])
    assert result.exit_code == 0
    data = assert_json_schema(result, required_keys=["rows", "count", "query", "limit"], source_attr="stdout")
    assert isinstance(data["rows"], list)
    assert data["count"] == 1
    assert data["query"] == "year:2020"


def test_search_error_exits_nonzero() -> None:
    """Invalid flag → non-zero exit code."""
    result = run_cli(["library-search", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-search`` is a read-only query command.  It opens the indexer
# database with a minimal ``EventBus`` (solely for the free-space guard's
# ``DiskFullWarning`` infrastructure event), runs a SELECT query, and returns
# rows.  No domain event is published.  Read-only diagnostic commands like
# ``library-doctor`` and ``library-status`` follow the same pattern.
