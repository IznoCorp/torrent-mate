"""Characterization golden: library-index --mode full == legacy library-scan DB end-state.

This test is the safety net for Phase 3's deletion of library/scanner.py.
It must pass before any deletion is attempted. If it fails, Phase 3 is blocked.

Baseline = the **real** ``scan_library`` (the live legacy path) on a temp
filesystem fixture. ``scan_library`` calls the indexer file walk
(``_indexer_scan``) at the very end for ``media_file`` / ``path`` rows; that
terminal call triggers a disk-identity bootstrap that writes a sentinel to the
volume root and fails on a tmp filesystem. We monkeypatch ``_indexer_scan`` to
a no-op so the REAL ``media_item`` / ``season`` / ``episode`` / ``item_issue`` /
``item_attribute`` creation (which — after obj#5 — routes through the shared
``upsert_item_with_attrs`` SSOT) runs unchanged, while only the file/path walk
(never compared) is skipped.

Result = the new ``stage_library_items`` (pass 1 of ``library-index --mode
full``) on a fresh in-memory DB with the **same** config. The snapshot covers
the full DESIGN §4.3 behaviour-set — all stable ``media_item`` columns plus
``item_issue`` types, ``season`` rows, ``episode`` rows, and the three
``dispatch_*`` flex attributes — so the equality assertion is the honest
deletion safety net (no column-trimming to force a pass).
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
from tests.fixtures.config import CANONICAL_STAGING_DIRS

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"

# The three dispatch flex-attribute keys (parity with item_repo._ATTR_DISPATCH_*).
# Snapshotted per item so the trailers / dispatch / release_linker INNER JOINs
# stay byte-identical across the legacy → new cutover (DESIGN §4.3).
_DISPATCH_ATTR_KEYS = ("dispatch_path", "dispatch_disk", "dispatch_normalized_title")


def _build_mini_library(tmp_path: Path) -> dict[str, Any]:
    """Build a temp filesystem + Config that mirrors the mini_library fixture.

    Replicates ``tests/library/test_integration.py`` lines 40-124 inline so
    the golden test is self-contained and does not depend on conftest fixtures.
    The fixture contains:

    * A complete movie "The Matrix (1999)" with tmdb+imdb NFO, artwork,
      ``.actors``, and ``.DS_Store``.
    * A no-NFO "Incomplete Movie".
    * A TV show "Fallout (2024)" with tmdb NFO, artwork, and ``Saison 01/``
      containing two episode files (one with a sibling .nfo, one without).

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Dict with keys ``disk``, ``config``, ``disk_cfg``.
    """
    disk = tmp_path / "Disk1" / "medias"

    # --- Movie: complete ---
    matrix = disk / "films" / "The Matrix (1999)"
    matrix.mkdir(parents=True)
    (matrix / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
    (matrix / "The Matrix.nfo").write_text(
        "<movie><title>The Matrix</title><year>1999</year>"
        '<uniqueid type="tmdb">603</uniqueid>'
        '<uniqueid type="imdb">tt0133093</uniqueid></movie>'
    )
    (matrix / "The Matrix-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (matrix / "The Matrix-landscape.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    actors = matrix / ".actors"
    actors.mkdir()
    (actors / "Keanu Reeves.jpg").write_bytes(b"\x00" * 50)
    (matrix / ".DS_Store").write_bytes(b"\x00" * 10)

    # --- Movie: incomplete (no NFO, bad naming) ---
    incomplete = disk / "films" / "Incomplete Movie"
    incomplete.mkdir(parents=True)
    (incomplete / "movie.mkv").write_bytes(b"\x00" * 1000)

    # --- TV Show ---
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
    show_actors = fallout / ".actors"
    show_actors.mkdir()
    (show_actors / "Ella Purnell.jpg").write_bytes(b"\x00" * 50)
    (fallout / "empty_release_dir").mkdir()

    # Build DiskConfig + Config for scan operations (mirrors mini_library lines 90-110).
    disk_cfg = DiskConfig(id="disk1", path=disk, categories=["movies", "tv_shows"])
    config = Config(
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

    return {"disk": disk, "config": config, "disk_cfg": disk_cfg}


def _snapshot_db(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Capture the full DESIGN §4.3 behaviour-set, keyed by ``(kind, title)``.

    For every ``media_item`` row this snapshots:

    * all stable ``media_item`` columns (excludes the volatile / auto-stamped
      ``id``, ``date_created``, ``date_modified``, ``date_metadata_refreshed``,
      ``is_locked``);
    * the sorted set of ``item_issue.type`` values;
    * per-item ``season`` rows as sorted ``(number, episode_count, has_poster,
      episodes_with_nfo)`` tuples;
    * per-season ``episode`` rows as sorted ``(number, title)`` tuples;
    * the three ``dispatch_*`` flex attributes from ``item_attribute``.

    Sorting every nested set makes the comparison insertion-order-independent;
    keying on ``(kind, title)`` makes it ``media_item.id``-independent (the two
    DBs assign PKs in different orders). This is the honest deletion net — no
    column is trimmed to force a pass.

    Args:
        conn: Open SQLite connection with migrations applied and data populated.

    Returns:
        List of per-item dicts, ordered by ``(kind, title)``.
    """
    item_rows = conn.execute(
        """
        SELECT id, title, title_sort, original_title, kind, year, category_id,
               external_ids_json, ratings_json, canonical_provider, nfo_status,
               artwork_json, preferred_lang
          FROM media_item
         ORDER BY kind, title
        """
    ).fetchall()
    item_cols = [
        "title",
        "title_sort",
        "original_title",
        "kind",
        "year",
        "category_id",
        "external_ids_json",
        "ratings_json",
        "canonical_provider",
        "nfo_status",
        "artwork_json",
        "preferred_lang",
    ]

    snapshot: list[dict[str, Any]] = []
    for row in item_rows:
        item_id = row[0]
        item: dict[str, Any] = dict(zip(item_cols, row[1:]))

        # item_issue: sorted set of type values for this item.
        item["issue_types"] = sorted(
            r[0] for r in conn.execute("SELECT type FROM item_issue WHERE item_id = ?", (item_id,)).fetchall()
        )

        # season + episode rows for this item (sorted, id-independent).
        seasons: list[dict[str, Any]] = []
        season_rows = conn.execute(
            """
            SELECT id, number, episode_count, has_poster, episodes_with_nfo
              FROM season WHERE item_id = ? ORDER BY number
            """,
            (item_id,),
        ).fetchall()
        for s_id, number, ep_count, has_poster, eps_with_nfo in season_rows:
            episodes = sorted(
                (ep_num, title)
                for ep_num, title in conn.execute(
                    "SELECT number, title FROM episode WHERE season_id = ?", (s_id,)
                ).fetchall()
            )
            seasons.append(
                {
                    "number": number,
                    "episode_count": ep_count,
                    "has_poster": has_poster,
                    "episodes_with_nfo": eps_with_nfo,
                    "episodes": episodes,
                }
            )
        item["seasons"] = seasons

        # The three dispatch_* flex attributes (trailers / dispatch INNER JOINs).
        item["dispatch_attrs"] = {
            key: (
                conn.execute(
                    "SELECT value FROM item_attribute WHERE item_id = ? AND key = ?",
                    (item_id, key),
                ).fetchone()
                or (None,)
            )[0]
            for key in _DISPATCH_ATTR_KEYS
        }

        snapshot.append(item)

    return snapshot


@pytest.mark.integration
def test_full_mode_db_equals_library_scan_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """library-index --mode full must produce the same DB end-state as library-scan.

    Baseline = the REAL ``scan_library`` (live legacy path). Its terminal
    ``_indexer_scan`` call (file/path walk) is monkeypatched to a no-op so the
    disk-identity sentinel bootstrap does not fail on the tmp filesystem and so
    only the never-compared ``media_file`` / ``path`` rows are skipped; the
    ``media_item`` / ``season`` / ``episode`` / ``item_issue`` / ``item_attribute``
    writes — which after obj#5 route through ``upsert_item_with_attrs`` — run
    unchanged.

    Result = the new ``stage_library_items`` (pass 1 of ``library-index --mode
    full``) on the same config.

    Both run against a fresh in-memory DB with all migrations applied; the
    snapshot covers the full DESIGN §4.3 behaviour-set. Every field must be
    byte-identical EXCEPT ``item_issue`` types: the new path is a documented
    SUPERSET — DESIGN §4.3 decision #2 has it flag no-NFO dirs with an extra
    ``nfo_missing`` / ``nfo_incomplete`` tag the legacy path never emitted, so
    the issue set is asserted as ``legacy ⊆ new ⊆ legacy ∪ {no-NFO tags}``.
    """
    from personalscraper.indexer.scanner._modes._item_stage import stage_library_items
    from personalscraper.library.scanner import scan_library

    fixture = _build_mini_library(tmp_path)
    config = fixture["config"]

    # --- Baseline: the REAL scan_library, with only the terminal file/path
    # walk neutralised (it writes media_file/path rows we do not compare and
    # bootstraps a disk-identity sentinel that fails on tmp filesystems). ---
    monkeypatch.setattr("personalscraper.library.scanner._indexer_scan", lambda **kwargs: None)
    conn_legacy = sqlite3.connect(":memory:")
    apply_migrations(conn_legacy, MIGRATIONS_DIR)
    scan_library(config, conn_legacy, event_bus=EventBus())
    baseline = _snapshot_db(conn_legacy)
    conn_legacy.close()

    # --- New path: stage_library_items (pass 1 of library-index --mode full) ---
    conn_new = sqlite3.connect(":memory:")
    apply_migrations(conn_new, MIGRATIONS_DIR)
    stage_library_items(conn_new, config)
    result = _snapshot_db(conn_new)
    conn_new.close()

    assert baseline, "Baseline must not be empty — fixture has 3 media dirs"
    assert len(baseline) == 3, f"Expected 3 media_item rows, got {len(baseline)}"
    assert len(result) == len(baseline), f"media_item count mismatch: baseline={len(baseline)} result={len(result)}"

    # The new path is a documented SUPERSET of the legacy issue set: DESIGN §4.3
    # decision #2 has it flag no-NFO directories with an extra ``nfo_missing`` /
    # ``nfo_incomplete`` ``item_issue`` tag that the legacy ``scan_library`` path
    # never emitted (legacy only recorded the directory-hygiene tags). Every
    # OTHER field must be byte-identical, so we compare the core verbatim and
    # treat ``issue_types`` separately rather than trim it from the snapshot
    # (keeping the net honest).
    _NO_NFO_AUGMENTATION = {"nfo_missing", "nfo_incomplete"}

    for base_item, new_item in zip(baseline, result):
        assert (new_item["kind"], new_item["title"]) == (base_item["kind"], base_item["title"]), (
            f"item ordering mismatch: baseline={base_item['kind']}/{base_item['title']} "
            f"result={new_item['kind']}/{new_item['title']}"
        )

        # Core: every field except ``issue_types`` must be byte-identical.
        base_core = {k: v for k, v in base_item.items() if k != "issue_types"}
        new_core = {k: v for k, v in new_item.items() if k != "issue_types"}
        assert new_core == base_core, (
            f"DB end-state mismatch (non-issue fields) for "
            f"{base_item['kind']}/{base_item['title']}.\n\n"
            f"Baseline:\n{base_core}\n\nResult:\n{new_core}"
        )

        # Issue set: new ⊇ legacy, and the only delta is the documented no-NFO
        # augmentation. Any other extra/missing tag is a real regression.
        base_issues = set(base_item["issue_types"])
        new_issues = set(new_item["issue_types"])
        assert base_issues <= new_issues, (
            f"new path dropped a legacy issue tag for {base_item['kind']}/{base_item['title']}: "
            f"legacy={sorted(base_issues)} new={sorted(new_issues)}"
        )
        extra = new_issues - base_issues
        assert extra <= _NO_NFO_AUGMENTATION, (
            f"new path added an UNEXPECTED issue tag for {base_item['kind']}/{base_item['title']}: "
            f"extra={sorted(extra)} (only {sorted(_NO_NFO_AUGMENTATION)} are the documented "
            f"DESIGN §4.3 decision-#2 no-NFO augmentation)"
        )
        # When the documented augmentation fires, it must agree with nfo_status.
        if extra:
            assert base_item["nfo_status"] in ("missing", "invalid"), (
                f"no-NFO augmentation {sorted(extra)} fired on a valid-NFO item "
                f"{base_item['kind']}/{base_item['title']} (nfo_status={base_item['nfo_status']!r})"
            )
