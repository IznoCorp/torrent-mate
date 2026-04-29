"""Consumer parity test — sub-phase 7.6.

Verifies that ``scan_library(config, conn)`` produces a result set that is
1:1 equivalent with the v0.7 legacy ``library_scan.json`` snapshot on the
canonical v0.7 fixture filesystem (``tests/fixtures/parity/v0.7-fs/``).

Assertion contract from DESIGN §15.4.1:
- 1:1 set match on ``(title, year, category_id)`` — every item present in the
  v0.7 snapshot appears in the indexer DB, and no extra items are added.
- Per-item: ``nfo_status`` derived from ``nfo.present/valid`` matches the DB
  column value.
- Per-item: artwork presence flags (``poster``, ``fanart``) match
  ``media_item.artwork_json``.
- For TV shows: the set of season numbers matches the v0.7 ``seasons`` list.

The parity fixture filesystem is built by ``tests/fixtures/parity/build_v07_fs.py``
and committed under ``tests/fixtures/parity/v0.7-fs/`` (gitignored; re-run
``python tests/fixtures/parity/build_v07_fs.py`` to regenerate after a clean
checkout).  The ``v0.7-library_scan.json`` snapshot is committed and never
regenerated automatically.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.conf.models import (
    CategoryConfig,
    Config,
    DiskConfig,
    PathConfig,
    StagingDirConfig,
)
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.schema import ArtworkInventory
from personalscraper.library.scanner import scan_library
from tests.fixtures.parity.build_v07_fs import build as build_parity_fs

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PARITY_DIR = Path(__file__).parent.parent / "fixtures" / "parity"
_SNAPSHOT_PATH = _PARITY_DIR / "v0.7-library_scan.json"
_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# Patch target: suppress the disk-mount guard so scan_library works on our
# in-repo fixture tree without triggering macOS-specific mount checks.
_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parity_config(disk_fixture_path: Path, tmp_path: Path) -> Config:
    """Build a minimal Config pointing at the parity fixture filesystem.

    The disk ID and folder names mirror what ``build_v07_fs.py`` creates:
    - ``films/`` for movies (``default_label("movies")``)
    - ``series/`` for tv_shows (``default_label("tv_shows")``)
    - ``livres audios/`` for audiobooks (``default_label("audiobooks")``)

    Args:
        disk_fixture_path: Absolute path to the ``disk_fixture/`` root built
            by :func:`build_parity_fs`.
        tmp_path: Pytest temporary directory for staging/data paths.

    Returns:
        Validated :class:`~personalscraper.conf.models.Config` instance.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[
            DiskConfig(
                id="disk_fixture",
                path=disk_fixture_path,
                categories=["movies", "tv_shows", "audiobooks"],
            ),
        ],
        categories={
            # Override folder names to match what build_v07_fs.py creates.
            "movies": CategoryConfig(folder_name="films"),
            "tv_shows": CategoryConfig(folder_name="series"),
            "audiobooks": CategoryConfig(folder_name="livres audios"),
        },
        staging_dirs=[
            StagingDirConfig(id=1, name="movies", file_type="movie"),
            StagingDirConfig(id=2, name="tvshows", file_type="tvshow"),
            StagingDirConfig(id=97, name="temp", file_type=None, role="ingest"),
        ],
    )


def _make_conn() -> sqlite3.Connection:
    """Create an in-memory SQLite connection with the full indexer schema applied.

    Returns:
        Open :class:`sqlite3.Connection` with migrations applied and FK checks on.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _load_snapshot() -> dict[str, Any]:
    """Load the v0.7 library scan JSON snapshot from the committed fixture file.

    Returns:
        Parsed dict with an ``"items"`` list.

    Raises:
        FileNotFoundError: If the snapshot file is not committed or was deleted.
    """
    raw: dict[str, Any] = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return raw


def _nfo_status_from_v07(v07_nfo: dict[str, Any]) -> str:
    """Derive the DB ``nfo_status`` string from a v0.7 NFO dict.

    Maps ``present/valid`` flags used by the legacy scanner to the DB
    status strings used by the indexer.

    Args:
        v07_nfo: The ``nfo`` sub-dict from a v0.7 library scan item.

    Returns:
        ``'valid'`` | ``'invalid'`` | ``'missing'``.
    """
    if not v07_nfo.get("present", False):
        return "missing"
    if v07_nfo.get("valid", False):
        return "valid"
    return "invalid"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def parity_db_and_snapshot(tmp_path_factory: pytest.TempPathFactory) -> tuple[sqlite3.Connection, dict[str, Any]]:
    """Build the parity FS, run scan_library, and return the populated DB + snapshot.

    Module-scoped so that the (expensive) filesystem build and scan only run
    once regardless of how many test functions consume this fixture.

    Args:
        tmp_path_factory: Pytest factory for module-scoped temporary directories.

    Returns:
        Tuple of:
        - ``conn``: Open in-memory :class:`sqlite3.Connection` after
          ``scan_library()`` has populated it.
        - ``snapshot``: Parsed v0.7 library scan JSON dict.
    """
    tmp_path = tmp_path_factory.mktemp("parity")

    # Build the parity fixture filesystem under a temporary directory so that
    # the test is hermetic and does not depend on the repo-level v0.7-fs/ tree
    # being present (which is gitignored).
    disk_fixture_path = build_parity_fs(output_dir=tmp_path / "disk_fixture")

    config = _make_parity_config(disk_fixture_path, tmp_path)
    conn = _make_conn()
    snapshot = _load_snapshot()

    # Patch guard_disk_mounted so scan_library does not reject the tmp_path
    # fixture tree as "unmounted".
    with patch(_GUARD_PATCH, return_value=None):
        scan_library(config, conn)

    return conn, snapshot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_item_set_matches_v07_snapshot(
    parity_db_and_snapshot: tuple[sqlite3.Connection, dict[str, Any]],
) -> None:
    """1:1 set match on (title, year, category_id) between DB and v0.7 snapshot.

    Every item in the v0.7 library scan JSON must have a corresponding
    ``media_item`` row in the indexer DB (same title, year, and category_id),
    and no extra items must be present.
    """
    conn, snapshot = parity_db_and_snapshot
    conn.row_factory = sqlite3.Row

    # Collect DB items as a set of (title, year, category_id) tuples.
    db_rows = conn.execute("SELECT title, year, category_id FROM media_item ORDER BY title").fetchall()
    db_set = {(row["title"], row["year"], row["category_id"]) for row in db_rows}

    # Collect snapshot items with the same shape.
    snapshot_set: set[tuple[str, int | None, str]] = set()
    for item in snapshot["items"]:
        snapshot_set.add((item["title"], item["year"], item["category"]))

    assert db_set == snapshot_set, (
        f"Item sets differ.\n"
        f"  In DB but not snapshot: {db_set - snapshot_set}\n"
        f"  In snapshot but not DB: {snapshot_set - db_set}"
    )


def test_nfo_status_matches_v07_snapshot(
    parity_db_and_snapshot: tuple[sqlite3.Connection, dict[str, Any]],
) -> None:
    """nfo_status in DB matches the v0.7 snapshot nfo.present/valid flags.

    For each item in the v0.7 snapshot, retrieve the corresponding ``media_item``
    row from the DB and assert that ``nfo_status`` matches the derived status.
    """
    conn, snapshot = parity_db_and_snapshot
    conn.row_factory = sqlite3.Row

    for v07_item in snapshot["items"]:
        title = v07_item["title"]
        year = v07_item["year"]
        category_id = v07_item["category"]
        expected_nfo_status = _nfo_status_from_v07(v07_item["nfo"])

        row = conn.execute(
            "SELECT nfo_status FROM media_item WHERE title = ? AND year IS ? AND category_id = ?",
            (title, year, category_id),
        ).fetchone()

        assert row is not None, f"media_item not found for {title!r} ({year})"
        assert row["nfo_status"] == expected_nfo_status, (
            f"{title!r}: expected nfo_status={expected_nfo_status!r}, got {row['nfo_status']!r}"
        )


def test_artwork_matches_v07_snapshot(
    parity_db_and_snapshot: tuple[sqlite3.Connection, dict[str, Any]],
) -> None:
    """artwork_json poster/fanart flags in DB match the v0.7 snapshot artwork dict.

    Checks only ``poster`` and ``fanart`` since those are the two artwork types
    present in the parity fixture (the fixture does not create landscape/banner/etc.).
    """
    conn, snapshot = parity_db_and_snapshot
    conn.row_factory = sqlite3.Row

    for v07_item in snapshot["items"]:
        title = v07_item["title"]
        year = v07_item["year"]
        category_id = v07_item["category"]
        v07_artwork = v07_item["artwork"]

        row = conn.execute(
            "SELECT artwork_json FROM media_item WHERE title = ? AND year IS ? AND category_id = ?",
            (title, year, category_id),
        ).fetchone()

        assert row is not None, f"media_item not found for {title!r} ({year})"

        artwork_json_str: str | None = row["artwork_json"]
        assert artwork_json_str is not None, f"artwork_json is NULL for {title!r}"

        artwork = ArtworkInventory.model_validate_json(artwork_json_str)

        assert artwork.poster == v07_artwork["poster"], (
            f"{title!r}: poster mismatch — DB={artwork.poster}, snapshot={v07_artwork['poster']}"
        )
        assert artwork.fanart == v07_artwork["fanart"], (
            f"{title!r}: fanart mismatch — DB={artwork.fanart}, snapshot={v07_artwork['fanart']}"
        )


def test_season_numbers_match_v07_snapshot(
    parity_db_and_snapshot: tuple[sqlite3.Connection, dict[str, Any]],
) -> None:
    """Season number sets in DB match the v0.7 snapshot for all TV shows.

    Skips non-tvshow items (movies and audiobooks have ``seasons: null`` in the
    v0.7 snapshot).
    """
    conn, snapshot = parity_db_and_snapshot
    conn.row_factory = sqlite3.Row

    for v07_item in snapshot["items"]:
        if v07_item["media_type"] != "tvshow":
            continue

        title = v07_item["title"]
        year = v07_item["year"]
        category_id = v07_item["category"]
        v07_seasons: list[dict[str, Any]] = v07_item.get("seasons") or []
        expected_season_numbers = {s["number"] for s in v07_seasons}

        # Look up the media_item row to get its id.
        item_row = conn.execute(
            "SELECT id FROM media_item WHERE title = ? AND year IS ? AND category_id = ?",
            (title, year, category_id),
        ).fetchone()

        assert item_row is not None, f"media_item not found for tvshow {title!r} ({year})"

        item_id = item_row["id"]
        season_rows = conn.execute(
            "SELECT number FROM season WHERE item_id = ?",
            (item_id,),
        ).fetchall()
        db_season_numbers = {row["number"] for row in season_rows}

        assert db_season_numbers == expected_season_numbers, (
            f"{title!r}: season number mismatch — DB={db_season_numbers}, snapshot={expected_season_numbers}"
        )
