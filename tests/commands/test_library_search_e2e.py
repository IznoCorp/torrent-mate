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
    data = json_from_result(result)
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
    data = json_from_result(result)
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
    data = json_from_result(result)
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
    data = json_from_result(result)
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
