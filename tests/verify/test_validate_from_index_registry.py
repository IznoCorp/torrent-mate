"""Integration test: validate_from_index uses IndexableCheck registry loop."""

import json
import sqlite3

from personalscraper.verify.library_checks import validate_from_index


def _make_db(items: list[dict]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE media_item (
            id INTEGER PRIMARY KEY, kind TEXT, title TEXT, year INTEGER,
            category_id TEXT, nfo_status TEXT, artwork_json TEXT, title_sort TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE item_attribute (
            item_id INTEGER, key TEXT, value TEXT
        )
    """)
    for i, item in enumerate(items, start=1):
        conn.execute(
            "INSERT INTO media_item VALUES (?,?,?,?,?,?,?,?)",
            (
                i,
                item["kind"],
                item["title"],
                item.get("year"),
                item.get("category_id", "movies"),
                item.get("nfo_status"),
                item.get("artwork_json"),
                item["title"],
            ),
        )
        if "disk" in item:
            conn.execute("INSERT INTO item_attribute VALUES (?,?,?)", (i, "dispatch_disk", item["disk"]))
    conn.commit()
    return conn


def test_validate_from_index_nfo_missing_flagged() -> None:
    """nfo_status="missing" → nfo_present error flagged via registry loop."""
    conn = _make_db(
        [
            {
                "kind": "movie",
                "title": "Orphan",
                "nfo_status": "missing",
                "artwork_json": json.dumps({"poster": "p.jpg", "landscape": "l.jpg"}),
            }
        ]
    )
    result = validate_from_index(conn)
    assert result.issues_count == 1
    item = result.items[0]
    assert "nfo_present" in item.errors


def test_validate_from_index_null_nfo_status_not_flagged() -> None:
    """nfo_status=None → no NFO error (NULL indistinguishable from "not yet enriched")."""
    conn = _make_db(
        [
            {
                "kind": "movie",
                "title": "Mystery",
                "nfo_status": None,
                "artwork_json": json.dumps({"poster": "p.jpg", "landscape": "l.jpg"}),
            }
        ]
    )
    result = validate_from_index(conn)
    assert result.valid_count == 1


def test_validate_from_index_landscape_movie_only() -> None:
    """TV show with no landscape → valid (artwork_landscape.from_index returns None for tvshow)."""
    conn = _make_db(
        [
            {
                "kind": "show",
                "title": "Series",
                "nfo_status": "valid",
                "artwork_json": json.dumps({"poster": "p.jpg"}),
            }  # no landscape
        ]
    )
    result = validate_from_index(conn)
    # TV shows: landscape is NOT checked in DB-mode
    assert result.valid_count == 1
