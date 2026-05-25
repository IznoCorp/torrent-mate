"""Regression tests for ``library-fix-canonical-provider`` repair CLI.

Covers:
- End-to-end repair of shows (canonical_provider='tmdb' → 'tvdb') and
  movies (canonical_provider=NULL → 'tmdb').
- Idempotence: re-running the repair after a successful pass touches 0 rows.
- Dry-run: ``--apply`` False reports counts without mutating the DB.
- Control rows: items already in the correct state are left untouched.

Seeds an on-disk migrated DB via :func:`_e2e_helpers.make_synthetic_db`,
invokes the Typer CLI via :func:`_e2e_helpers.run_cli`, and asserts the
JSON output schema and DB state after each operation.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.commands._e2e_helpers import make_synthetic_db, run_cli


def _json_from_result(result: Any) -> dict[str, Any]:
    raw: str = result.output.strip()
    # Strip Rich ANSI escape codes.
    import re

    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    start = clean.rfind("{")
    if start == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[start:])


def _seed_repair_data(conn: sqlite3.Connection) -> None:
    """Seed 5 broken shows + 3 broken movies + 2 control rows."""
    now = 1700000000

    # 5 shows: kind='show', canonical_provider='tmdb', with tvdb.series_id
    for i in range(1, 6):
        eids = json.dumps({"tvdb": {"series_id": f"100{i}"}, "tmdb": {"series_id": f"200{i}"}})
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('show', ?, ?, 'tv_shows', ?, 'tmdb', ?, ?)",
            (f"Show {i}", f"Show {i}", eids, now, now),
        )

    # 3 movies: kind='movie', canonical_provider=NULL, with tmdb.id
    for i in range(1, 4):
        eids = json.dumps({"tmdb": {"id": f"300{i}"}})
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('movie', ?, ?, 'movies', ?, NULL, ?, ?)",
            (f"Movie {i}", f"Movie {i}", eids, now, now),
        )

    # Control: movie already with canonical_provider='tmdb' — must stay unchanged.
    eids_ctrl_movie = json.dumps({"tmdb": {"id": "9991"}})
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('movie', 'Ctrl Movie OK', 'Ctrl Movie OK', 'movies', ?, 'tmdb', ?, ?)",
        (eids_ctrl_movie, now, now),
    )

    # Control: show already with canonical_provider='tvdb' — must stay unchanged.
    eids_ctrl_show = json.dumps({"tvdb": {"series_id": "9992"}, "tmdb": {"series_id": "29992"}})
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'Ctrl Show OK', 'Ctrl Show OK', 'tv_shows', ?, 'tvdb', ?, ?)",
        (eids_ctrl_show, now, now),
    )

    conn.commit()


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------


def test_repair_fixes_canonical_provider(tmp_path: Path, test_config: Any) -> None:
    """--apply corrects 5 shows + 3 movies, leaves 2 control rows untouched."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_repair_data(conn)
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-canonical-provider", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["fixed_shows"] == 5, f"Expected 5 fixed_shows, got {data}"
    assert data["fixed_movies"] == 3, f"Expected 3 fixed_movies, got {data}"

    # Verify DB state.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    # All 5 shows now have canonical_provider='tvdb'.
    show_rows = conn.execute(
        "SELECT title, canonical_provider FROM media_item WHERE kind='show' ORDER BY title"
    ).fetchall()
    for row in show_rows:
        if row["title"] == "Ctrl Show OK":
            assert row["canonical_provider"] == "tvdb", f"Control show changed: {dict(row)}"
        else:
            assert row["canonical_provider"] == "tvdb", f"Show not fixed: {dict(row)}"

    # All 3 broken movies now have canonical_provider='tmdb'.
    movie_rows = conn.execute(
        "SELECT title, canonical_provider FROM media_item WHERE kind='movie' ORDER BY title"
    ).fetchall()
    for row in movie_rows:
        assert row["canonical_provider"] == "tmdb", f"Movie not fixed: {dict(row)}"

    conn.close()


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


def test_repair_idempotent_after_fix(tmp_path: Path, test_config: Any) -> None:
    """Re-running --apply on already-fixed items reports zero fixes."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_repair_data(conn)
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        # First pass.
        result1 = run_cli(["--format", "json", "library-fix-canonical-provider", "--db", str(db_path), "--apply"])
        assert result1.exit_code == 0, result1.output
        data1 = _json_from_result(result1)
        assert data1["fixed_shows"] == 5
        assert data1["fixed_movies"] == 3

        # Second pass — idempotent.
        result2 = run_cli(["--format", "json", "library-fix-canonical-provider", "--db", str(db_path), "--apply"])
        assert result2.exit_code == 0, result2.output
        data2 = _json_from_result(result2)
        assert data2["fixed_shows"] == 0, f"Second pass should fix 0 shows, got {data2}"
        assert data2["fixed_movies"] == 0, f"Second pass should fix 0 movies, got {data2}"


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def test_repair_dry_run_reports_counts_without_mutation(tmp_path: Path, test_config: Any) -> None:
    """Dry-run reports would_fix counts, does not mutate DB, and has apply=False."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_repair_data(conn)

    # Snapshot before dry-run (as list of tuples for type-stable comparison).
    before_shows = [
        (r["title"], r["canonical_provider"])
        for r in conn.execute(
            "SELECT title, canonical_provider FROM media_item WHERE kind='show' ORDER BY title"
        ).fetchall()
    ]
    before_movies = [
        (r["title"], r["canonical_provider"])
        for r in conn.execute(
            "SELECT title, canonical_provider FROM media_item WHERE kind='movie' ORDER BY title"
        ).fetchall()
    ]
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-canonical-provider", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is False
    assert data["would_fix_shows"] == 5, f"Expected 5 would_fix_shows, got {data}"
    assert data["would_fix_movies"] == 3, f"Expected 3 would_fix_movies, got {data}"

    # DB must be unchanged.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    after_shows = [
        (r["title"], r["canonical_provider"])
        for r in conn.execute(
            "SELECT title, canonical_provider FROM media_item WHERE kind='show' ORDER BY title"
        ).fetchall()
    ]
    after_movies = [
        (r["title"], r["canonical_provider"])
        for r in conn.execute(
            "SELECT title, canonical_provider FROM media_item WHERE kind='movie' ORDER BY title"
        ).fetchall()
    ]
    conn.close()

    assert before_shows == after_shows, "Dry-run mutated show rows"
    assert before_movies == after_movies, "Dry-run mutated movie rows"
