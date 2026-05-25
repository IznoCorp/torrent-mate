"""Variance-sourced regression test for canonical_provider repair (2026-05-25 run).

On 2026-05-25, the pipeline audit (DEVIATION #7, ACCEPTANCE_FAIL #4) reported:
209 ``kind='show'`` items with ``canonical_provider='tmdb'`` instead of ``'tvdb'``,
and 142 ``kind='movie'`` items with ``canonical_provider IS NULL``.

The synthetic test in ``test_canonical_provider_repair.py`` covers the repair
LOGIC with toy data (Show 1..N).  This file is the VARIANCE complement: it seeds
rows mirroring real-world shapes from the run docs, exercising five variance
dimensions that the synthetic test does not cover:

1. **Mixed external_ids_json shapes**: shows with only tvdb, only tmdb, both
   providers, imdb-only, and malformed payloads (empty object, null values,
   wrong-shaped arrays).
2. **Real-world titles**: French and English titles with accents (Concours
   Parallele), apostrophes (LOL Qui rit, sort !, Peaky Blinders L'Immortel),
   exclamation marks (American Dad!), parentheses (FROM (2022)), special
   characters (Stranger Things Tales from '85).
3. **Movies with NULL canonical_provider**: real movie titles from the run
   (I Origins, Peaky Blinders L'Immortel, Projet Derniere Chance, Mikado,
   Dossier 137).
4. **Edge cases**: no-tvdb-id shows (must stay 'tmdb'), empty/nulled
   external_ids_json, imdb-only rows, already-correct rows that must stay
   untouched.
5. **Scale**: ~30 seed rows (not 209/142) but with enough variance to verify
   the predicate-guarded UPDATE correctly identifies the fixable subset and
   does not touch edge-case rows or correctly-set rows.

Seed categories (all counts in comments):
  - 10 shows needing fix (canonical_provider='tmdb' + valid tvdb.series_id)
  -  5 shows correctly set (canonical_provider='tvdb') — must stay unchanged
  -  5 shows edge-case-no-flip (canonical_provider='tmdb' but tvdb id missing,
      NULL json, etc.) — must NOT flip
  -  5 movies needing fix (canonical_provider=NULL + valid tmdb.id)
  -  5 movies correctly set (canonical_provider='tmdb') — must stay unchanged
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
    import re

    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    start = clean.rfind("{")
    if start == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[start:])


def _seed_real_world_variance(conn: sqlite3.Connection) -> None:
    """Seed ~30 rows mirroring real-world media_item variance from the 2026-05-25 run.

    Row categories (tracked via canonical_provider + external_ids_json shape):
      fixed_shows     = 10  (canonical_provider='tmdb' + tvdb.series_id)
      correct_shows   =  5  (canonical_provider='tvdb' — must stay)
      edge_shows      =  5  (canonical_provider='tmdb' but NOT fixable)
      fixed_movies    =  5  (canonical_provider=NULL + tmdb.id)
      correct_movies  =  5  (canonical_provider='tmdb' — must stay)
    """
    now = 1700000000

    # ── fixed_shows (10): canonical_provider='tmdb' + valid tvdb.series_id ──
    shows_fixable = [
        ("Top Chef", "Top Chef", "tv_shows", {"tvdb": {"series_id": "261388"}, "tmdb": {"series_id": "47776"}}),
        ("American Dad!", "American Dad!", "tv_shows", {"tvdb": {"series_id": "79432"}, "tmdb": {"series_id": "1435"}}),
        (
            "FROM (2022)",
            "FROM (2022)",
            "tv_shows",
            {"tvdb": {"series_id": "401003"}, "tmdb": {"series_id": "124364"}, "imdb": {"series_id": "tt9813792"}},
        ),
        (
            "Stranger Things Tales from '85",
            "Stranger Things Tales from '85",
            "tv_shows",
            {"tvdb": {"series_id": "420001"}, "tmdb": {"series_id": "210001"}},
        ),
        (
            "LOL Qui rit, sort !",
            "LOL Qui rit, sort !",
            "tv_shows",
            {"tvdb": {"series_id": "415678"}, "tmdb": {"series_id": "129101"}},
        ),
        (
            "Dexter New Blood",
            "Dexter New Blood",
            "tv_shows",
            {"tvdb": {"series_id": "392652"}, "tmdb": {"series_id": "131085"}},
        ),
        ("The Boys", "The Boys", "tv_shows", {"tvdb": {"series_id": "360149"}, "tmdb": {"series_id": "76479"}}),
        (
            "Top Chef Le Concours Parallele",
            "Top Chef Le Concours Parallele",
            "tv_shows",
            {"tvdb": {"series_id": "475278"}, "tmdb": {"series_id": "279001"}},
        ),
        (
            "Imperfect Women",
            "Imperfect Women",
            "tv_shows",
            {"tvdb": {"series_id": "448179"}, "tmdb": {"series_id": "108181"}},
        ),
        (
            "Maximum Pleasure Guaranteed",
            "Maximum Pleasure Guaranteed",
            "tv_shows",
            {"tvdb": {"series_id": "460793"}, "tmdb": {"series_id": "285404"}},
        ),
    ]
    for title, title_sort, cat_id, eids in shows_fixable:
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('show', ?, ?, ?, ?, 'tmdb', ?, ?)",
            (title, title_sort, cat_id, json.dumps(eids), now, now),
        )

    # ── correct_shows (5): canonical_provider already 'tvdb' — must stay ──
    shows_correct = [
        ("Breaking Bad", "Breaking Bad", "tv_shows", {"tvdb": {"series_id": "81189"}, "tmdb": {"series_id": "1396"}}),
        (
            "Game of Thrones",
            "Game of Thrones",
            "tv_shows",
            {"tvdb": {"series_id": "121361"}, "tmdb": {"series_id": "1399"}},
        ),
        ("The Crown", "The Crown", "tv_shows", {"tvdb": {"series_id": "295681"}, "tmdb": {"series_id": "65494"}}),
        ("Chernobyl", "Chernobyl", "tv_shows", {"tvdb": {"series_id": "351245"}, "tmdb": {"series_id": "87108"}}),
        (
            "The Queen's Gambit",
            "The Queen's Gambit",
            "tv_shows",
            {"tvdb": {"series_id": "375403"}, "tmdb": {"series_id": "87739"}},
        ),
    ]
    for title, title_sort, cat_id, eids in shows_correct:
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('show', ?, ?, ?, ?, 'tvdb', ?, ?)",
            (title, title_sort, cat_id, json.dumps(eids), now, now),
        )

    # ── edge_shows (5): canonical_provider='tmdb' but NOT fixable ──
    # 1. Only tmdb id (no tvdb key at all) — must stay 'tmdb'
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'TmdbOnly Show', 'TmdbOnly Show', 'tv_shows', ?, 'tmdb', ?, ?)",
        (json.dumps({"tmdb": {"series_id": "99901"}}), now, now),
    )
    # 2. Empty external_ids_json — must stay 'tmdb'
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'EmptyJSON Show', 'EmptyJSON Show', 'tv_shows', '{}', 'tmdb', ?, ?)",
        (now, now),
    )
    # 3. Only imdb id (no tvdb, no tmdb in external_ids_json) — must NOT flip
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'IMDBOnly Show', 'IMDBOnly Show', 'tv_shows', ?, 'tmdb', ?, ?)",
        (json.dumps({"imdb": {"series_id": "tt0099999"}}), now, now),
    )
    # 4. tvdb key is an array (not an object) — json_extract → NULL, must NOT flip
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'ArrayTvdb Show', 'ArrayTvdb Show', 'tv_shows', ?, 'tmdb', ?, ?)",
        (json.dumps({"tvdb": []}), now, now),
    )
    # 5. tvdb key present but value is null — json_extract → NULL → must NOT flip
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'NullTvdb Show', 'NullTvdb Show', 'tv_shows', ?, 'tmdb', ?, ?)",
        (json.dumps({"tvdb": None}), now, now),
    )

    # ── fixed_movies (5): canonical_provider=NULL + valid tmdb.id ──
    movies_fixable = [
        ("I Origins", "I Origins", "movies", {"tmdb": {"id": "157336"}, "imdb": {"id": "tt2884206"}}),
        (
            "Peaky Blinders L'Immortel",
            "Peaky Blinders L'Immortel",
            "movies",
            {"tmdb": {"id": "990001"}, "imdb": {"id": "tt33000001"}},
        ),
        (
            "Projet Derniere Chance",
            "Projet Derniere Chance",
            "movies",
            {"tmdb": {"id": "990002"}, "imdb": {"id": "tt33000002"}},
        ),
        ("Mikado", "Mikado", "movies", {"tmdb": {"id": "990003"}}),
        ("Dossier 137", "Dossier 137", "movies", {"tmdb": {"id": "1294698"}, "imdb": {"id": "tt34794183"}}),
    ]
    for title, title_sort, cat_id, eids in movies_fixable:
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('movie', ?, ?, ?, ?, NULL, ?, ?)",
            (title, title_sort, cat_id, json.dumps(eids), now, now),
        )

    # ── correct_movies (5): canonical_provider already 'tmdb' — must stay ──
    movies_correct = [
        ("Inception", "Inception", "movies", {"tmdb": {"id": "27205"}, "imdb": {"id": "tt1375666"}}),
        ("The Matrix", "The Matrix", "movies", {"tmdb": {"id": "603"}, "imdb": {"id": "tt0133093"}}),
        ("Interstellar", "Interstellar", "movies", {"tmdb": {"id": "157336"}, "imdb": {"id": "tt0816692"}}),
        ("The Dark Knight", "The Dark Knight", "movies", {"tmdb": {"id": "155"}, "imdb": {"id": "tt0468569"}}),
        ("Pulp Fiction", "Pulp Fiction", "movies", {"tmdb": {"id": "680"}, "imdb": {"id": "tt0110912"}}),
    ]
    for title, title_sort, cat_id, eids in movies_correct:
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('movie', ?, ?, ?, ?, 'tmdb', ?, ?)",
            (title, title_sort, cat_id, json.dumps(eids), now, now),
        )

    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: repair correctly partitions fixable vs edge-case vs correct rows
# ══════════════════════════════════════════════════════════════════════════════


def test_real_world_variance_repair_correctly_partitions(tmp_path: Path, test_config: Any) -> None:
    """Seed 30 variance-rich rows, run --apply, assert correct partition.

    Expected: 10 shows + 5 movies fixed.  All correctly-set rows and edge-case
    rows must remain untouched.  Re-run must be idempotent (0 fixes).
    """
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_real_world_variance(conn)
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-canonical-provider", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["fixed_shows"] == 10, f"Expected 10 fixed_shows, got {data}"
    assert data["fixed_movies"] == 5, f"Expected 5 fixed_movies, got {data}"

    # Verify DB state.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    # All 10 fixable shows now have canonical_provider='tvdb'.
    show_rows = conn.execute(
        "SELECT title, canonical_provider FROM media_item WHERE kind='show' ORDER BY title"
    ).fetchall()
    for row in show_rows:
        if row["title"] in {
            "TmdbOnly Show",
            "EmptyJSON Show",
            "IMDBOnly Show",
            "ArrayTvdb Show",
            "NullTvdb Show",
        }:
            assert row["canonical_provider"] == "tmdb", f"Edge-case show should stay 'tmdb': {dict(row)}"
        else:
            assert row["canonical_provider"] == "tvdb", f"Show should be 'tvdb' after repair: {dict(row)}"

    # All movies (fixable + correct) have canonical_provider='tmdb'.
    movie_rows = conn.execute(
        "SELECT title, canonical_provider FROM media_item WHERE kind='movie' ORDER BY title"
    ).fetchall()
    for row in movie_rows:
        assert row["canonical_provider"] == "tmdb", f"Movie should be 'tmdb': {dict(row)}"

    conn.close()

    # Idempotence: re-run produces 0 fixes.
    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result2 = run_cli(["--format", "json", "library-fix-canonical-provider", "--db", str(db_path), "--apply"])
    assert result2.exit_code == 0, result2.output
    data2 = _json_from_result(result2)
    assert data2["fixed_shows"] == 0, f"Second pass should fix 0 shows, got {data2}"
    assert data2["fixed_movies"] == 0, f"Second pass should fix 0 movies, got {data2}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: dry-run reports correct counts without mutation
# ══════════════════════════════════════════════════════════════════════════════


def test_real_world_variance_dry_run_reports_correctly(tmp_path: Path, test_config: Any) -> None:
    """Dry-run reports would_fix counts (10/5), DB unchanged after."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_real_world_variance(conn)

    # Snapshot before dry-run.
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
    assert data["would_fix_shows"] == 10, f"Expected 10 would_fix_shows, got {data}"
    assert data["would_fix_movies"] == 5, f"Expected 5 would_fix_movies, got {data}"

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


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: malformed external_ids_json does not crash
# ══════════════════════════════════════════════════════════════════════════════


def test_malformed_external_ids_json_does_not_crash(tmp_path: Path, test_config: Any) -> None:
    """Malformed external_ids_json rows are skipped gracefully, no crash.

    Seeds 5 malformed rows + 2 legitimately-fixable rows (1 show, 1 movie).
    Assert no exception, only the 2 legit rows are fixed, malformed rows untouched.
    """
    db_path = make_synthetic_db(tmp_path)
    now = 1700000000

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    # Malformed rows (all kind='show', canonical_provider='tmdb').
    malformed = [
        ("Empty Object", "{}"),
        ("Null Literal", "null"),
        ("Array Shape", "[]"),
        ("Tvdb Null", json.dumps({"tvdb": None})),
        ("SeriesId Null", json.dumps({"tvdb": {"series_id": None}})),
    ]
    for title, eids_json in malformed:
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('show', ?, ?, 'tv_shows', ?, 'tmdb', ?, ?)",
            (title, title, eids_json, now, now),
        )

    # One legitimately-fixable show (has tvdb.series_id).
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'Fixable Show', 'Fixable Show', 'tv_shows', ?, 'tmdb', ?, ?)",
        (json.dumps({"tvdb": {"series_id": "99901"}, "tmdb": {"series_id": "29901"}}), now, now),
    )

    # One legitimately-fixable movie (NULL cp + valid tmdb.id).
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('movie', 'Fixable Movie', 'Fixable Movie', 'movies', ?, NULL, ?, ?)",
        (json.dumps({"tmdb": {"id": "88801"}}), now, now),
    )

    conn.commit()
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-canonical-provider", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, f"CLI crashed on malformed JSON: {result.output}"
    data = _json_from_result(result)
    assert data["fixed_shows"] == 1, (
        f"Only 'Fixable Show' should be fixed, got {data['fixed_shows']}. "
        f"Malformed rows must not trigger spurious flips."
    )
    assert data["fixed_movies"] == 1, f"Only 1 fixable movie expected, got {data}"

    # Verify state: malformed shows still 'tmdb', fixable show → 'tvdb', fixable movie → 'tmdb'.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    malformed_titles = {"Empty Object", "Null Literal", "Array Shape", "Tvdb Null", "SeriesId Null"}
    show_rows = conn.execute(
        "SELECT title, canonical_provider FROM media_item WHERE kind='show' ORDER BY title"
    ).fetchall()
    for row in show_rows:
        if row["title"] in malformed_titles:
            assert row["canonical_provider"] == "tmdb", f"Malformed row should stay 'tmdb': {dict(row)}"
        else:
            assert row["canonical_provider"] == "tvdb", f"Fixable show should be 'tvdb': {dict(row)}"

    movie_rows = conn.execute("SELECT title, canonical_provider FROM media_item WHERE kind='movie'").fetchall()
    for row in movie_rows:
        assert row["canonical_provider"] == "tmdb", f"Fixable movie should be 'tmdb': {dict(row)}"

    conn.close()
