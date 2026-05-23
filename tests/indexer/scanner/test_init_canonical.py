"""init_canonical_from_nfo bootstrap tests (Phase 1.9 / DEV #54).

DEV #54 — pre tech-debt 0.16.0, ``run_backfill_ids`` skipped every
``media_item`` where ``canonical_provider IS NULL`` with the
``backfill_ids_canonical_unsupported`` debug log. On the production BDD,
1937/1937 items had ``canonical_provider NULL`` because nothing in the
scraper pipeline ever populated it. Backfill USES canonical but never
SETS it — chicken-and-egg, the entire backfill flow was a no-op.

Phase 1.9 adds :func:`init_canonical_from_nfo`. It walks rows with
``canonical_provider IS NULL``, locates the item's NFO file via the
``item_attribute(key='dispatch_path')`` row, and reads the ``type``
attribute of ``<uniqueid default="true">`` from the NFO XML. When found,
sets ``canonical_provider`` so the next ``run_backfill_ids`` pass can
make progress.

Tests in this file :

- ``test_init_canonical_from_nfo_populates_from_tvdb_default`` — the
  plan-required regression test (BD-* MUST). Seed a show item with an
  NFO containing ``<uniqueid default="true" type="tvdb">…</uniqueid>``,
  run init, assert ``canonical_provider='tvdb'``.
- ``test_init_canonical_from_nfo_populates_from_tmdb_default`` — same
  for movies with type='tmdb'.
- ``test_init_canonical_skips_items_without_dispatch_path`` — items
  with no dispatch_path attribute (scanner-only rows) are silently
  skipped.
- ``test_init_canonical_skips_items_without_nfo_file`` — items whose
  resolved NFO path doesn't exist on FS are silently skipped.
- ``test_init_canonical_skips_when_no_default_uniqueid`` — NFO with
  uniqueid elements but none ``default="true"`` → no update.
- ``test_init_canonical_idempotent`` — second run on a DB whose
  canonical was already populated returns 0 (rows excluded by
  ``WHERE canonical_provider IS NULL``).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._modes.backfill_ids import init_canonical_from_nfo

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open a real file-based SQLite DB with all migrations applied."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _seed_item(
    conn: sqlite3.Connection,
    *,
    title: str,
    kind: str,
    year: int,
    dispatch_path: str | None = None,
) -> int:
    """Insert a media_item row with canonical_provider NULL (and optional dispatch_path).

    Returns the new item_id.
    """
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO media_item "
        "(title, title_sort, kind, year, category_id, "
        "date_created, date_modified, canonical_provider, external_ids_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, '{}')",
        (title, title.lower(), kind, year, "tv_shows" if kind == "show" else "movies", now, now),
    )
    item_id: int = cur.lastrowid  # type: ignore[assignment]
    if dispatch_path is not None:
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, dispatch_path),
        )
    return item_id


def _write_show_nfo(show_dir: Path, *, uniqueid_lines: str) -> None:
    """Write a minimal tvshow.nfo with the given <uniqueid> block."""
    show_dir.mkdir(parents=True, exist_ok=True)
    (show_dir / "tvshow.nfo").write_text(
        f"<?xml version='1.0' encoding='utf-8'?>\n<tvshow>{uniqueid_lines}</tvshow>\n",
        encoding="utf-8",
    )


def _write_movie_nfo(movie_dir: Path, title: str, *, uniqueid_lines: str) -> None:
    """Write a minimal {Title}.nfo with the given <uniqueid> block."""
    movie_dir.mkdir(parents=True, exist_ok=True)
    (movie_dir / f"{title}.nfo").write_text(
        f"<?xml version='1.0' encoding='utf-8'?>\n<movie>{uniqueid_lines}</movie>\n",
        encoding="utf-8",
    )


def test_init_canonical_from_nfo_populates_from_tvdb_default(tmp_path: Path) -> None:
    """A show NFO with <uniqueid default="true" type="tvdb">…</uniqueid> populates canonical_provider='tvdb'."""
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    show_dir = tmp_path / "shows" / "Breaking Bad (2008)"
    _write_show_nfo(show_dir, uniqueid_lines='<uniqueid default="true" type="tvdb">81189</uniqueid>')
    item_id = _seed_item(conn, title="Breaking Bad", kind="show", year=2008, dispatch_path=str(show_dir))

    populated = init_canonical_from_nfo(conn)

    assert populated == 1, f"Expected 1 item populated, got {populated}"
    canonical = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    assert canonical == "tvdb", f"Expected canonical='tvdb', got {canonical!r}"


def test_init_canonical_from_nfo_populates_from_tmdb_default(tmp_path: Path) -> None:
    """A movie NFO with <uniqueid default="true" type="tmdb">…</uniqueid> populates canonical='tmdb'."""
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    movie_dir = tmp_path / "movies" / "Inception (2010)"
    _write_movie_nfo(movie_dir, "Inception", uniqueid_lines='<uniqueid default="true" type="tmdb">27205</uniqueid>')
    item_id = _seed_item(conn, title="Inception", kind="movie", year=2010, dispatch_path=str(movie_dir))

    populated = init_canonical_from_nfo(conn)

    assert populated == 1, f"Expected 1 item populated, got {populated}"
    canonical = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    assert canonical == "tmdb"


def test_init_canonical_skips_items_without_dispatch_path(tmp_path: Path) -> None:
    """Items with no dispatch_path attribute are silently skipped (scanner-only rows)."""
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    item_id = _seed_item(conn, title="Orphan", kind="show", year=2024, dispatch_path=None)

    populated = init_canonical_from_nfo(conn)

    assert populated == 0
    canonical = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    assert canonical is None, "canonical must remain NULL when no dispatch_path"


def test_init_canonical_skips_items_without_nfo_file(tmp_path: Path) -> None:
    """Items whose resolved NFO path doesn't exist on FS are silently skipped."""
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    show_dir = tmp_path / "shows" / "Phantom"
    show_dir.mkdir(parents=True, exist_ok=True)
    # NOTE: no tvshow.nfo written
    item_id = _seed_item(conn, title="Phantom", kind="show", year=2024, dispatch_path=str(show_dir))

    populated = init_canonical_from_nfo(conn)

    assert populated == 0
    canonical = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    assert canonical is None


def test_init_canonical_skips_when_no_default_uniqueid(tmp_path: Path) -> None:
    """NFO with <uniqueid> elements but none ``default="true"`` → no update.

    Common case for items scraped before the default attribute was standardized.
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    show_dir = tmp_path / "shows" / "Legacy Show"
    _write_show_nfo(
        show_dir,
        uniqueid_lines='<uniqueid type="tvdb">81189</uniqueid><uniqueid type="tmdb">1396</uniqueid>',
    )
    item_id = _seed_item(conn, title="Legacy Show", kind="show", year=2008, dispatch_path=str(show_dir))

    populated = init_canonical_from_nfo(conn)

    assert populated == 0, "No default uniqueid → must not update"
    canonical = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    assert canonical is None


def test_init_canonical_skips_unsupported_type_attr(tmp_path: Path) -> None:
    """Regression : NFO default uniqueid with non-tvdb/tmdb type is skipped (live prod bug).

    Discovered 2026-05-23 on live BDD : after 22 items populated successfully,
    init_canonical_from_nfo crashed with::

        IntegrityError: CHECK constraint failed: canonical_provider IN ('tvdb', 'tmdb')

    The function returned the raw type attr from the NFO (e.g. 'imdb',
    'anidb', 'tvmaze'). These ARE valid cross-provider IDs that live in
    external_ids_json, but the schema CHECK on canonical_provider accepts
    only tvdb / tmdb because those are the only providers that drive
    primary scrape orchestration (DESIGN §3).

    Fix : the parser filters out non-tvdb/tmdb types so the walker
    continues to the next item instead of crashing mid-batch.
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    show_dir = tmp_path / "shows" / "Anime Show"
    _write_show_nfo(
        show_dir,
        uniqueid_lines='<uniqueid default="true" type="anidb">1234</uniqueid><uniqueid type="tvdb">5678</uniqueid>',
    )
    item_id = _seed_item(conn, title="Anime Show", kind="show", year=2024, dispatch_path=str(show_dir))

    # Must not crash. populated count = 0 because the only default uniqueid
    # has an unsupported type ; tvdb uniqueid lacks default="true".
    populated = init_canonical_from_nfo(conn)

    assert populated == 0, f"Expected 0 (unsupported type), got {populated}"
    canonical = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    assert canonical is None


def test_init_canonical_idempotent(tmp_path: Path) -> None:
    """Second run on a DB whose canonical is already populated returns 0."""
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    show_dir = tmp_path / "shows" / "Show"
    _write_show_nfo(show_dir, uniqueid_lines='<uniqueid default="true" type="tvdb">1</uniqueid>')
    _seed_item(conn, title="Show", kind="show", year=2024, dispatch_path=str(show_dir))

    first = init_canonical_from_nfo(conn)
    assert first == 1, f"First run must populate 1 item, got {first}"

    # Second run — no rows match WHERE canonical_provider IS NULL anymore
    second = init_canonical_from_nfo(conn)
    assert second == 0, f"Second run must be a no-op, got {second}"


def test_library_init_canonical_cli_command_exists() -> None:
    """library-init-canonical CLI command is exposed and exits 0 on --help.

    Smoke test : the new sub-command must be discoverable via the CLI app
    so the operator can invoke it as documented in the phase plan.
    """
    from personalscraper.cli import app
    from tests.conftest import make_cli_runner

    runner = make_cli_runner()
    result = runner.invoke(app, ["library-init-canonical", "--help"])
    assert result.exit_code == 0, f"--help must exit 0, got {result.exit_code}. Output:\n{result.output}"
