"""Integration test for the C3 wiring: ``scan(mode=full, config=cfg)`` fires pass 1.

The DESIGN promise (§4.1/§5) is that a single ``library-index --mode full``
reaches the same DB end-state as the legacy ``library-scan`` + ``library-index``.
That hinges on the indexer ``scan()`` full-mode branch invoking
:func:`personalscraper.indexer.scanner._modes.full.stage_items_pass1` once,
**only** when ``config`` is provided. This test exercises that branch
end-to-end and pins both the positive (``config=cfg`` → rich rows staged) and
the negative (``config=None`` → nothing staged) sides of the guard.

Approach (the lightest that genuinely runs ``scan()``'s full-mode branch):
call ``scan(disks=[], mode=ScanMode.full, config=cfg, ...)``. With ``disks=[]``
the per-disk file walk (pass 2) is a no-op — no real mount point, no
disk-identity sentinel write — but pass 1 (``stage_items_pass1`` →
``stage_library_items``) still iterates ``config.disks`` (the mini fs on tmp)
and stages the rich ``media_item`` / ``season`` / ``episode`` / ``item_issue``
rows. ``scan()`` reaches the pass-1 call (``__init__.py`` ~:596) before the
per-disk walk dispatch, so an empty disk list does not short-circuit it.

``canonical_provider`` is the discriminator that proves pass 1 ran: it is set
**only** by pass 1's ``build_item_row`` → ``derive_canonical_provider``; the
file walk (pass 2) never touches ``media_item`` rows at all.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner import ScanMode, scan
from tests.fixtures.config import CANONICAL_STAGING_DIRS

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"


def _build_mini_library(tmp_path: Path) -> Config:
    """Build a temp filesystem + Config mirroring the golden test's mini library.

    The fixture contains a complete movie (tmdb NFO, artwork), a no-NFO movie,
    and a TV show with one season and two episode files. Reused shape from
    ``test_item_stage_golden._build_mini_library`` so both tests exercise the
    same staging surface.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        A :class:`Config` whose single disk points at the temp filesystem.
    """
    disk = tmp_path / "Disk1" / "medias"

    # --- Movie: complete (tmdb canonical) ---
    matrix = disk / "films" / "The Matrix (1999)"
    matrix.mkdir(parents=True)
    (matrix / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
    (matrix / "The Matrix.nfo").write_text(
        "<movie><title>The Matrix</title><year>1999</year>"
        '<uniqueid type="tmdb">603</uniqueid>'
        '<uniqueid type="imdb">tt0133093</uniqueid></movie>'
    )
    (matrix / "The Matrix-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)

    # --- Movie: no NFO (folder-name fallback → nfo_missing issue) ---
    incomplete = disk / "films" / "Incomplete Movie"
    incomplete.mkdir(parents=True)
    (incomplete / "movie.mkv").write_bytes(b"\x00" * 1000)

    # --- TV Show with one season + two episodes ---
    fallout = disk / "series" / "Fallout (2024)"
    fallout.mkdir(parents=True)
    (fallout / "tvshow.nfo").write_text(
        '<tvshow><title>Fallout</title><uniqueid type="tmdb">106379</uniqueid></tvshow>'
    )
    (fallout / "poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (fallout / "season01-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    s01 = fallout / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 2000)
    (s01 / "S01E01 - The Beginning.nfo").write_text("<episodedetails><title>The Beginning</title></episodedetails>")
    (s01 / "S01E02 - The End.mkv").write_bytes(b"\x00" * 2000)

    disk_cfg = DiskConfig(id="disk1", path=disk, categories=["movies", "tv_shows"])
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={
            "movies": CategoryConfig(folder_name="films"),
            "tv_shows": CategoryConfig(folder_name="series"),
        },
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


def _fresh_db() -> sqlite3.Connection:
    """Open a fresh in-memory indexer DB with all migrations applied.

    Returns:
        Open SQLite connection ready for ``scan()`` / staging writes.
    """
    conn = sqlite3.connect(":memory:")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


@pytest.mark.integration
def test_scan_full_with_config_fires_pass1(tmp_path: Path) -> None:
    """``scan(mode=full, config=cfg)`` runs pass 1 and stages rich media_item rows.

    Drives the real ``scan()`` full-mode branch with an empty disk list (pass 2
    no-op) so only pass 1 — gated on ``mode == full and config is not None`` —
    produces rows. Proves pass 1 fired by asserting:

    * three ``media_item`` rows exist (one per media dir);
    * ``canonical_provider`` is set on the NFO-bearing items (set ONLY by pass 1
      via ``build_item_row`` → ``derive_canonical_provider``; the file walk never
      writes it);
    * the TV show has a ``season`` row (pass 1's season/episode upsert);
    * the no-NFO movie carries an ``nfo_missing`` ``item_issue`` (DESIGN §4.3
      decision #2 — never silently dropped).
    """
    cfg = _build_mini_library(tmp_path)
    conn = _fresh_db()

    # disks=[] → the per-disk file walk (pass 2) is a no-op (no mount point,
    # no sentinel). The full-mode branch still calls stage_items_pass1 ONCE,
    # which iterates cfg.disks (the tmp fs) and stages the rich rows.
    result = scan(
        disks=[],
        mode=ScanMode.full,
        generation=1,
        conn=conn,
        config=cfg,
        event_bus=EventBus(),
    )
    assert result.status == "ok", f"scan() did not finish ok: {result.status!r}"

    # Pass 1 ran: one media_item row per media directory.
    item_count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    assert item_count == 3, f"expected 3 staged media_item rows, got {item_count}"

    # canonical_provider is the pass-1 discriminator — set only by build_item_row.
    matrix_cp = conn.execute(
        "SELECT canonical_provider FROM media_item WHERE title = ? AND kind = ?",
        ("The Matrix", "movie"),
    ).fetchone()
    assert matrix_cp is not None, "The Matrix row missing — pass 1 did not stage it"
    assert matrix_cp[0] == "tmdb", f"canonical_provider not derived by pass 1: {matrix_cp[0]!r}"

    show_cp = conn.execute(
        "SELECT id, canonical_provider FROM media_item WHERE title = ? AND kind = ?",
        ("Fallout", "show"),
    ).fetchone()
    assert show_cp is not None, "Fallout show row missing — pass 1 did not stage it"
    show_id, show_canonical = show_cp
    assert show_canonical == "tmdb", f"show canonical_provider not set by pass 1: {show_canonical!r}"

    # Seasons exist for the show (pass 1's season/episode upsert ran).
    season_count = conn.execute("SELECT COUNT(*) FROM season WHERE item_id = ?", (show_id,)).fetchone()[0]
    assert season_count == 1, f"expected 1 season for the show, got {season_count}"

    # The no-NFO movie is indexed AND flagged nfo_missing (never dropped).
    incomplete_id = conn.execute(
        "SELECT id FROM media_item WHERE title = ? AND kind = ?",
        ("Incomplete Movie", "movie"),
    ).fetchone()
    assert incomplete_id is not None, "no-NFO movie was dropped (regression)"
    nfo_missing = conn.execute(
        "SELECT COUNT(*) FROM item_issue WHERE item_id = ? AND type = 'nfo_missing'",
        (incomplete_id[0],),
    ).fetchone()[0]
    assert nfo_missing >= 1, "no-NFO movie not flagged with nfo_missing item_issue"

    conn.close()


@pytest.mark.integration
def test_scan_full_without_config_stages_nothing(tmp_path: Path) -> None:
    """``scan(mode=full, config=None)`` must NOT run pass 1 (the guard).

    The other ``scan()`` callers (verify, dispatch enrich, ``scan_library``'s own
    ``_indexer_scan``) pass ``config=None`` and must not double-stage rich rows.
    With ``disks=[]`` and ``config=None`` there is nothing to walk AND no pass 1,
    so zero ``media_item`` rows must be created.
    """
    _ = _build_mini_library(tmp_path)  # build the fs but deliberately pass no config
    conn = _fresh_db()

    result = scan(
        disks=[],
        mode=ScanMode.full,
        generation=1,
        conn=conn,
        config=None,
        event_bus=EventBus(),
    )
    assert result.status == "ok", f"scan() did not finish ok: {result.status!r}"

    item_count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    assert item_count == 0, f"config=None must not stage any media_item rows; got {item_count}"

    conn.close()


@pytest.mark.integration
def test_scan_full_with_config_matches_direct_stage(tmp_path: Path) -> None:
    """The rows staged via ``scan(config=cfg)`` equal a direct ``stage_library_items``.

    Confirms the ``scan()`` full-mode branch routes through the same pass-1
    driver (no divergent wiring): the ``media_item`` titles + canonical providers
    produced through ``scan()`` match those produced by calling
    ``stage_library_items`` directly on the same config.
    """
    from personalscraper.indexer.scanner._modes._item_stage import stage_library_items

    cfg = _build_mini_library(tmp_path)

    conn_scan = _fresh_db()
    scan(disks=[], mode=ScanMode.full, generation=1, conn=conn_scan, config=cfg, event_bus=EventBus())
    via_scan: list[tuple[Any, ...]] = conn_scan.execute(
        "SELECT title, kind, canonical_provider FROM media_item ORDER BY kind, title"
    ).fetchall()
    conn_scan.close()

    conn_direct = _fresh_db()
    stage_library_items(conn_direct, cfg)
    via_direct: list[tuple[Any, ...]] = conn_direct.execute(
        "SELECT title, kind, canonical_provider FROM media_item ORDER BY kind, title"
    ).fetchall()
    conn_direct.close()

    assert via_scan == via_direct, (
        f"scan() full-mode branch diverged from direct stage_library_items.\n"
        f"via scan():   {via_scan}\n"
        f"via direct:   {via_direct}"
    )
