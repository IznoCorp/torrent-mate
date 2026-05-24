"""Regression tests for ``init_canonical_from_nfo``.

2026-05-23 prod incident: `library-init-canonical` ran on 1491 items and
reported ``populated=0`` silently. Investigation: 92 % of items had an NFO
declaring ``<uniqueid default="true" type="imdb">`` ALSO carrying a
``tmdb`` uniqueid as a secondary id — perfectly usable as a canonical
anchor, but the parser only looked at the default attribute.

These tests guard against three classes of silent failure:

1. Fallback: when default is unsupported (imdb/anidb/...), the parser
   must look for any other supported uniqueid (tvdb/tmdb).
2. Observability: the return value must surface a per-outcome breakdown
   (populated, no_default, parse_error, unsupported_no_fallback, ...) so
   the operator can see WHY ``populated=0`` happened, instead of guessing.
3. Idempotence: re-running on an already-populated row is a no-op.

Tests use real on-disk NFO fixtures (small XML strings) rather than mocks
so they exercise the real ET.parse codepath — including malformed-XML and
URL-after-closing-tag cases observed in production.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.scanner._modes.backfill_ids import (
    InitCanonicalStats,
    _parse_canonical_from_nfo,
    init_canonical_from_nfo,
)


def _open_mem_db() -> sqlite3.Connection:
    """Open an in-memory DB with the full migration set applied."""
    from personalscraper.core.event_bus import EventBus
    from personalscraper.indexer import migrations as _migrations_pkg
    from personalscraper.indexer.db import apply_migrations, open_db

    conn = open_db(Path(":memory:"), event_bus=EventBus())
    apply_migrations(conn, Path(_migrations_pkg.__file__).parent)
    return conn


def _seed_show(
    conn: sqlite3.Connection,
    *,
    title: str,
    dispatch_path: str | None,
) -> int:
    """Insert a media_item (kind=show) with optional dispatch_path attr."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, nfo_status, "
        "artwork_json, date_created, date_modified, canonical_provider) "
        "VALUES ('show', ?, ?, 'tv_shows', 'valid', '{}', ?, ?, NULL)",
        (title, title.lower(), now, now),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]
    if dispatch_path is not None:
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, dispatch_path),
        )
    return item_id


def _write_nfo(folder: Path, kind: str, content: str) -> Path:
    """Write a tvshow.nfo (kind=show) or <stem>.nfo (kind=movie)."""
    folder.mkdir(parents=True, exist_ok=True)
    name = "tvshow.nfo" if kind == "show" else "movie.nfo"
    nfo = folder / name
    nfo.write_text(content, encoding="utf-8")
    return nfo


def _seed_item_full(
    conn: sqlite3.Connection,
    *,
    title: str,
    kind: str = "show",
    canonical_provider: str | None = None,
    external_ids_json: str | None = None,
    dispatch_path: str | None = None,
) -> int:
    """Insert a media_item with explicit canonical_provider and external_ids_json.

    More flexible than _seed_show which hardcodes canonical_provider=NULL and
    does not accept external_ids_json. Used by tests that need specific
    pre-existing state for chicken-and-egg, merge-additive, and cohort routing
    scenarios.
    """
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, nfo_status, "
        "artwork_json, date_created, date_modified, canonical_provider, external_ids_json) "
        "VALUES (?, ?, ?, 'tv_shows', 'valid', '{}', ?, ?, ?, ?)",
        (kind, title, title.lower(), now, now, canonical_provider, external_ids_json),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]
    if dispatch_path is not None:
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, dispatch_path),
        )
    return item_id


# ───────────────────────────────────────────────────────────────────────────
# _parse_canonical_from_nfo — pure-function tests
# ───────────────────────────────────────────────────────────────────────────


def test_parse_default_tvdb_returns_ok_default(tmp_path: Path) -> None:
    """``<uniqueid default="true" type="tvdb">`` → ('tvdb', 'ok_default', {tvdb: id})."""
    nfo = _write_nfo(
        tmp_path,
        "show",
        '<?xml version="1.0"?><tvshow><uniqueid default="true" type="tvdb">12345</uniqueid></tvshow>',
    )
    provider, outcome, ids = _parse_canonical_from_nfo(nfo)
    assert provider == "tvdb"
    assert outcome == "ok_default"
    assert ids == {"tvdb": "12345"}


def test_parse_default_imdb_falls_back_to_tmdb(tmp_path: Path) -> None:
    """The BD-INIT-CANONICAL regression: default=imdb + tmdb sibling → ('tmdb', 'ok_fallback', ids)."""
    nfo = _write_nfo(
        tmp_path,
        "movie",
        '<?xml version="1.0"?><movie>'
        '<uniqueid default="true" type="imdb">tt12345</uniqueid>'
        '<uniqueid type="tmdb">67890</uniqueid>'
        "</movie>",
    )
    provider, outcome, ids = _parse_canonical_from_nfo(nfo)
    assert provider == "tmdb"
    assert outcome == "ok_fallback"
    assert ids == {"imdb": "tt12345", "tmdb": "67890"}


def test_parse_default_imdb_falls_back_to_tvdb(tmp_path: Path) -> None:
    """Fallback works for tvdb sibling too (e.g. shows with imdb-default)."""
    nfo = _write_nfo(
        tmp_path,
        "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="imdb">tt99999</uniqueid>'
        '<uniqueid type="tvdb">42</uniqueid>'
        "</tvshow>",
    )
    provider, outcome, ids = _parse_canonical_from_nfo(nfo)
    assert provider == "tvdb"
    assert outcome == "ok_fallback"
    assert ids == {"imdb": "tt99999", "tvdb": "42"}


def test_parse_default_imdb_no_supported_sibling_returns_unsupported(tmp_path: Path) -> None:
    """When default is unsupported AND no supported sibling exists → ('unsupported_no_fallback')."""
    nfo = _write_nfo(
        tmp_path,
        "movie",
        '<?xml version="1.0"?><movie>'
        '<uniqueid default="true" type="imdb">tt12345</uniqueid>'
        '<uniqueid type="anidb">9999</uniqueid>'
        "</movie>",
    )
    provider, outcome, ids = _parse_canonical_from_nfo(nfo)
    assert provider is None
    assert outcome == "unsupported_no_fallback"
    # imdb is extracted (it's in the 3-family set) but anidb is not
    assert ids == {"imdb": "tt12345"}


def test_parse_malformed_xml_returns_parse_error(tmp_path: Path) -> None:
    """The production NFO bug: URL after </tvshow> → ET.ParseError → ('parse_error', {})."""
    nfo = _write_nfo(
        tmp_path,
        "show",
        "<?xml version='1.0'?><tvshow><title>X</title></tvshow>\nhttps://www.thetvdb.com/?id=1\n",
    )
    provider, outcome, ids = _parse_canonical_from_nfo(nfo)
    assert provider is None
    assert outcome == "parse_error"
    assert ids == {}


def test_parse_no_default_uniqueid_returns_no_default(tmp_path: Path) -> None:
    """NFO without any default=true uniqueid → ('no_default', ids)."""
    nfo = _write_nfo(
        tmp_path,
        "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid type="tvdb">42</uniqueid>'  # no default attr
        "</tvshow>",
    )
    provider, outcome, ids = _parse_canonical_from_nfo(nfo)
    assert provider is None
    assert outcome == "no_default"
    # tvdb is extracted even without default attr
    assert ids == {"tvdb": "42"}


def test_parse_default_placeholder_value_falls_back_to_no_default(tmp_path: Path) -> None:
    """Default with empty/placeholder type ('', '0', 'none') is ignored."""
    nfo = _write_nfo(
        tmp_path,
        "show",
        '<?xml version="1.0"?><tvshow><uniqueid default="true" type="none">x</uniqueid></tvshow>',
    )
    provider, outcome, ids = _parse_canonical_from_nfo(nfo)
    assert provider is None
    assert outcome == "no_default"
    # type "none" is not in {tvdb, tmdb, imdb} → nothing extracted
    assert ids == {}


# ───────────────────────────────────────────────────────────────────────────
# init_canonical_from_nfo — integration tests with the DB
# ───────────────────────────────────────────────────────────────────────────


def test_init_canonical_populates_fallback_tmdb_on_imdb_default(tmp_path: Path) -> None:
    """End-to-end: a movie with default=imdb + tmdb sibling gets canonical_provider='tmdb'.

    Pre-fix the call returned populated=0 because the parser only honored
    the default attribute. Post-fix the row gets canonical_provider='tmdb'
    via fallback and the stats record it under populated_fallback.
    """
    conn = _open_mem_db()
    folder = tmp_path / "movie_dir"
    _write_nfo(
        folder,
        "movie",
        '<?xml version="1.0"?><movie>'
        '<uniqueid default="true" type="imdb">tt12345</uniqueid>'
        '<uniqueid type="tmdb">67890</uniqueid>'
        "</movie>",
    )
    # The CLI command path calls _resolve_nfo_path with kind='movie' and
    # globs *.nfo — so we keep kind=show here and write tvshow.nfo to match,
    # which lets us reuse _seed_show as the seeder.
    folder_show = tmp_path / "show_dir"
    _write_nfo(
        folder_show,
        "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="imdb">tt99999</uniqueid>'
        '<uniqueid type="tmdb">42</uniqueid>'
        "</tvshow>",
    )
    item_id = _seed_show(conn, title="ImdbDefaultShow", dispatch_path=str(folder_show))
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    conn.commit()

    assert stats.populated == 1
    assert stats.populated_fallback == 1
    assert stats.populated_default == 0
    row = conn.execute(
        "SELECT canonical_provider FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row["canonical_provider"] == "tmdb"


def test_init_canonical_counts_unsupported_no_fallback_separately(tmp_path: Path) -> None:
    """Stats distinguish 'unsupported but no fallback' from 'no default at all'."""
    conn = _open_mem_db()
    folder = tmp_path / "anidb_only"
    _write_nfo(
        folder,
        "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="imdb">tt1</uniqueid>'
        '<uniqueid type="anidb">9</uniqueid>'
        "</tvshow>",
    )
    _seed_show(conn, title="AnidbOnly", dispatch_path=str(folder))
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    assert stats.populated == 0
    assert stats.unsupported_no_fallback == 1
    assert stats.no_default_uniqueid == 0


def test_init_canonical_counts_parse_error_visibly(tmp_path: Path) -> None:
    """Malformed-XML NFOs are counted under nfo_parse_error, not silently dropped."""
    conn = _open_mem_db()
    folder = tmp_path / "broken_show"
    _write_nfo(
        folder,
        "show",
        "<?xml version='1.0'?><tvshow><title>X</title></tvshow>\nhttps://www.thetvdb.com/?id=1\n",
    )
    _seed_show(conn, title="BrokenShow", dispatch_path=str(folder))
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    assert stats.populated == 0
    assert stats.nfo_parse_error == 1
    assert stats.no_default_uniqueid == 0  # NOT silently lumped here


def test_init_canonical_counts_missing_dispatch_path(tmp_path: Path) -> None:
    """Scanner-only rows (no dispatch_path) are surfaced separately."""
    conn = _open_mem_db()
    _seed_show(conn, title="ScannerOnly", dispatch_path=None)
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    assert stats.populated == 0
    assert stats.no_dispatch_path == 1


def test_init_canonical_idempotent_skips_already_set(tmp_path: Path) -> None:
    """Items with canonical_provider already set are not in the WHERE clause."""
    conn = _open_mem_db()
    folder = tmp_path / "ok_show"
    _write_nfo(
        folder,
        "show",
        '<?xml version="1.0"?><tvshow><uniqueid default="true" type="tvdb">42</uniqueid></tvshow>',
    )
    _seed_show(conn, title="OkShow", dispatch_path=str(folder))
    conn.commit()

    stats1 = init_canonical_from_nfo(conn)
    conn.commit()
    assert stats1.populated == 1

    # Second pass: the item is no longer in the WHERE clause.
    stats2 = init_canonical_from_nfo(conn)
    assert stats2.total_visited == 0
    assert stats2.populated == 0


def test_init_canonical_stats_breakdown_sums_to_total_visited(tmp_path: Path) -> None:
    """Sanity check: every per-outcome bucket is mutually exclusive."""
    conn = _open_mem_db()
    # 1 ok_default
    folder1 = tmp_path / "ok"
    _write_nfo(
        folder1,
        "show",
        '<?xml version="1.0"?><tvshow><uniqueid default="true" type="tvdb">1</uniqueid></tvshow>',
    )
    _seed_show(conn, title="OK", dispatch_path=str(folder1))
    # 1 ok_fallback
    folder2 = tmp_path / "fallback"
    _write_nfo(
        folder2,
        "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="imdb">tt2</uniqueid>'
        '<uniqueid type="tmdb">2</uniqueid>'
        "</tvshow>",
    )
    _seed_show(conn, title="FB", dispatch_path=str(folder2))
    # 1 nfo_missing
    _seed_show(conn, title="NoNfo", dispatch_path=str(tmp_path / "ghost"))
    # 1 no_dispatch_path
    _seed_show(conn, title="NoPath", dispatch_path=None)
    conn.commit()

    stats = init_canonical_from_nfo(conn)

    total_accounted = (
        stats.populated_default
        + stats.populated_fallback
        + stats.no_dispatch_path
        + stats.nfo_missing
        + stats.nfo_parse_error
        + stats.nfo_read_error
        + stats.no_default_uniqueid
        + stats.unsupported_no_fallback
    )
    assert total_accounted == stats.total_visited == 4
    assert stats.populated_default == 1
    assert stats.populated_fallback == 1
    assert stats.nfo_missing == 1
    assert stats.no_dispatch_path == 1


def test_init_canonical_stats_dataclass_populated_property() -> None:
    """``populated`` is the sum of default + fallback."""
    s = InitCanonicalStats(populated_default=3, populated_fallback=7)
    assert s.populated == 10


# ───────────────────────────────────────────────────────────────────────────
# Phase 8.10.c shard 2 — extracted_ids + merge + cohort + dry-run + CLI output
# ───────────────────────────────────────────────────────────────────────────


# Group 1 — extracted_ids extraction via _parse_canonical_from_nfo


def test_extracted_ids_tvdb_only(tmp_path: Path) -> None:
    """NFO with single tvdb uniqueid → extracted_ids == {"tvdb": "12345"}."""
    nfo = _write_nfo(
        tmp_path, "show",
        '<?xml version="1.0"?><tvshow><uniqueid default="true" type="tvdb">12345</uniqueid></tvshow>',
    )
    _provider, _outcome, ids = _parse_canonical_from_nfo(nfo)
    assert ids == {"tvdb": "12345"}


def test_extracted_ids_all_three_families(tmp_path: Path) -> None:
    """NFO with tvdb + tmdb + imdb → extracted_ids includes all three regardless of default attr."""
    nfo = _write_nfo(
        tmp_path, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">1</uniqueid>'
        '<uniqueid type="tmdb">2</uniqueid>'
        '<uniqueid type="imdb">tt3</uniqueid>'
        "</tvshow>",
    )
    _provider, _outcome, ids = _parse_canonical_from_nfo(nfo)
    assert ids == {"tvdb": "1", "tmdb": "2", "imdb": "tt3"}


def test_extracted_ids_invalid_values_skipped(tmp_path: Path) -> None:
    """Values '0', 'none', and empty string are excluded from extracted_ids."""
    nfo = _write_nfo(
        tmp_path, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">42</uniqueid>'
        '<uniqueid type="tvdb">0</uniqueid>'
        '<uniqueid type="tvdb">none</uniqueid>'
        "<uniqueid type=\"tvdb\"></uniqueid>"
        "</tvshow>",
    )
    _provider, _outcome, ids = _parse_canonical_from_nfo(nfo)
    assert ids == {"tvdb": "42"}


def test_extracted_ids_unsupported_type_excluded(tmp_path: Path) -> None:
    """Anidb and tvmaze types are excluded; only tvdb/tmdb/imdb are supported."""
    nfo = _write_nfo(
        tmp_path, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">1</uniqueid>'
        '<uniqueid type="anidb">567</uniqueid>'
        "<uniqueid type=\"tvmaze\">99</uniqueid>"
        "</tvshow>",
    )
    _provider, _outcome, ids = _parse_canonical_from_nfo(nfo)
    assert ids == {"tvdb": "1"}
    assert "anidb" not in ids
    assert "tvmaze" not in ids


# Group 2 — merge-additive policy (integration with DB)


def test_merge_does_not_overwrite_existing(tmp_path: Path) -> None:
    """Existing external_ids values are preserved — additive policy, no overwrite.

    Item has external_ids_json='{"tmdb": {"series_id": "OLD_TMDB"}}'. NFO
    carries tmdb=67890 (the fresh value). After merge, the old tmdb value
    is preserved and external_ids_already_present is recorded.
    """
    conn = _open_mem_db()
    folder = tmp_path / "merge_no_overwrite"
    _write_nfo(
        folder, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">12345</uniqueid>'
        '<uniqueid type="tmdb">67890</uniqueid>'
        "</tvshow>",
    )
    item_id = _seed_item_full(
        conn, title="MergeNoOverwrite",
        canonical_provider=None,
        external_ids_json='{"tmdb": {"series_id": "OLD_TMDB", "episode_id": null}}',
        dispatch_path=str(folder),
    )
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    conn.commit()

    row = conn.execute(
        "SELECT canonical_provider, external_ids_json FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row["canonical_provider"] == "tvdb"
    eids = json.loads(row["external_ids_json"])
    assert eids["tvdb"] == {"series_id": "12345", "episode_id": None}
    assert eids["tmdb"] == {"series_id": "OLD_TMDB", "episode_id": None}
    assert stats.external_ids_seeded_with_canonical == 1
    assert stats.external_ids_already_present == 1


def test_merge_adds_missing_families(tmp_path: Path) -> None:
    """Existing has only tvdb; NFO adds tmdb → tvdb stays, tmdb added."""
    conn = _open_mem_db()
    folder = tmp_path / "merge_add_missing"
    _write_nfo(
        folder, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">1</uniqueid>'
        '<uniqueid type="tmdb">2</uniqueid>'
        "</tvshow>",
    )
    item_id = _seed_item_full(
        conn, title="MergeAddMissing",
        canonical_provider=None,
        external_ids_json='{"tvdb": {"series_id": "1", "episode_id": null}}',
        dispatch_path=str(folder),
    )
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    conn.commit()

    row = conn.execute(
        "SELECT external_ids_json FROM media_item WHERE id = ?", (item_id,),
    ).fetchone()
    eids = json.loads(row["external_ids_json"])
    assert eids["tvdb"] == {"series_id": "1", "episode_id": None}
    assert eids["tmdb"] == {"series_id": "2", "episode_id": None}
    assert stats.external_ids_seeded_with_canonical == 1
    assert stats.external_ids_already_present == 1


def test_merge_empty_starts_with_nfo_ids(tmp_path: Path) -> None:
    """external_ids_json='{}'; NFO has tvdb+tmdb → both inserted."""
    conn = _open_mem_db()
    folder = tmp_path / "merge_empty"
    _write_nfo(
        folder, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">1</uniqueid>'
        '<uniqueid type="tmdb">2</uniqueid>'
        "</tvshow>",
    )
    item_id = _seed_item_full(
        conn, title="MergeEmpty",
        canonical_provider=None,
        external_ids_json="{}",
        dispatch_path=str(folder),
    )
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    conn.commit()

    row = conn.execute(
        "SELECT external_ids_json FROM media_item WHERE id = ?", (item_id,),
    ).fetchone()
    eids = json.loads(row["external_ids_json"])
    assert eids["tvdb"] == {"series_id": "1", "episode_id": None}
    assert eids["tmdb"] == {"series_id": "2", "episode_id": None}
    assert stats.external_ids_seeded_with_canonical == 1
    assert stats.external_ids_already_present == 0


# Group 3 — broadened cohort routing (chicken-and-egg fix)


def test_chicken_and_egg_seeded_alone(tmp_path: Path) -> None:
    """canonical='tvdb' + external_ids='{}' → external_ids seeded, canonical unchanged.

    The chicken-and-egg cohort: canonical was populated by a pre-shard-1
    init-canonical run, but external_ids_json remained empty. This test
    asserts that only external_ids_json is seeded (without touching
    canonical_provider) and external_ids_seeded_alone is recorded.
    """
    conn = _open_mem_db()
    folder = tmp_path / "chicken_egg"
    _write_nfo(
        folder, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">12345</uniqueid>'
        '<uniqueid type="tmdb">67890</uniqueid>'
        "</tvshow>",
    )
    item_id = _seed_item_full(
        conn, title="ChickenEgg",
        canonical_provider="tvdb",
        external_ids_json="{}",
        dispatch_path=str(folder),
    )
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    conn.commit()

    row = conn.execute(
        "SELECT canonical_provider, external_ids_json FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row["canonical_provider"] == "tvdb"
    eids = json.loads(row["external_ids_json"])
    assert eids["tvdb"] == {"series_id": "12345", "episode_id": None}
    assert eids["tmdb"] == {"series_id": "67890", "episode_id": None}
    assert stats.populated == 0
    assert stats.external_ids_seeded_alone == 1
    assert stats.external_ids_seeded_with_canonical == 0


def test_null_canonical_seeded_with_canonical(tmp_path: Path) -> None:
    """canonical=NULL + external_ids='{}' → both written, external_ids_seeded_with_canonical +=1."""
    conn = _open_mem_db()
    folder = tmp_path / "null_canonical"
    _write_nfo(
        folder, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">12345</uniqueid>'
        '<uniqueid type="tmdb">67890</uniqueid>'
        "</tvshow>",
    )
    item_id = _seed_item_full(
        conn, title="NullCanonical",
        canonical_provider=None,
        external_ids_json="{}",
        dispatch_path=str(folder),
    )
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    conn.commit()

    row = conn.execute(
        "SELECT canonical_provider, external_ids_json FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row["canonical_provider"] == "tvdb"
    eids = json.loads(row["external_ids_json"])
    assert "tvdb" in eids
    assert "tmdb" in eids
    assert stats.populated == 1
    assert stats.external_ids_seeded_with_canonical == 1
    assert stats.external_ids_seeded_alone == 0


def test_items_with_canonical_and_external_ids_not_visited(tmp_path: Path) -> None:
    """Items with both canonical AND external_ids fully populated are excluded by WHERE."""
    conn = _open_mem_db()
    folder = tmp_path / "not_visited"
    _write_nfo(
        folder, "show",
        '<?xml version="1.0"?><tvshow><uniqueid default="true" type="tvdb">1</uniqueid></tvshow>',
    )
    _seed_item_full(
        conn, title="NotVisited",
        canonical_provider="tvdb",
        external_ids_json='{"tvdb": {"series_id": "X", "episode_id": null}}',
        dispatch_path=str(folder),
    )
    conn.commit()

    stats = init_canonical_from_nfo(conn)
    assert stats.total_visited == 0


# Group 4 — dry-run safety


def test_dry_run_does_not_write_external_ids(tmp_path: Path) -> None:
    """dry_run=True: stats counted (would_seed semantic) but DB unchanged."""
    conn = _open_mem_db()
    folder = tmp_path / "dry_run"
    _write_nfo(
        folder, "show",
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid default="true" type="tvdb">12345</uniqueid>'
        '<uniqueid type="tmdb">67890</uniqueid>'
        "</tvshow>",
    )
    item_id = _seed_item_full(
        conn, title="DryRun",
        canonical_provider="tvdb",
        external_ids_json="{}",
        dispatch_path=str(folder),
    )
    conn.commit()

    stats = init_canonical_from_nfo(conn, dry_run=True)

    assert stats.external_ids_seeded_alone == 1

    row = conn.execute(
        "SELECT canonical_provider, external_ids_json FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row["canonical_provider"] == "tvdb"
    assert row["external_ids_json"] == "{}"


# Group 5 — CLI output schema contract


def test_cli_output_includes_new_stats_keys() -> None:
    """InitCanonicalStats fields map correctly to the CLI JSON output keys.

    Does not require a DB; validates the dataclass→JSON contract that
    library-init-canonical's console.print(json.dumps(...)) depends on.
    """
    stats = InitCanonicalStats(
        external_ids_seeded_with_canonical=5,
        external_ids_seeded_alone=10,
        external_ids_already_present=3,
        total_visited=18,
        populated_default=4,
        populated_fallback=1,
        no_dispatch_path=2,
        nfo_missing=1,
    )

    # Mirror the CLI JSON structure from library_init_canonical command
    output = {
        "dry_run": True,
        "canonical_provider_populated": stats.populated,
        "populated_default": stats.populated_default,
        "populated_fallback": stats.populated_fallback,
        "total_visited": stats.total_visited,
        "external_ids_seeded_with_canonical": stats.external_ids_seeded_with_canonical,
        "external_ids_seeded_alone": stats.external_ids_seeded_alone,
        "external_ids_already_present": stats.external_ids_already_present,
        "skipped": {
            "no_dispatch_path": stats.no_dispatch_path,
            "nfo_missing": stats.nfo_missing,
            "nfo_parse_error": stats.nfo_parse_error,
            "nfo_read_error": stats.nfo_read_error,
            "no_default_uniqueid": stats.no_default_uniqueid,
            "unsupported_no_fallback": stats.unsupported_no_fallback,
        },
    }

    for key in (
        "external_ids_seeded_with_canonical",
        "external_ids_seeded_alone",
        "external_ids_already_present",
        "total_visited",
        "canonical_provider_populated",
    ):
        assert key in output, f"Missing key in CLI output: {key}"

    assert output["external_ids_seeded_with_canonical"] == 5
    assert output["external_ids_seeded_alone"] == 10
    assert output["external_ids_already_present"] == 3
    assert output["canonical_provider_populated"] == 5
