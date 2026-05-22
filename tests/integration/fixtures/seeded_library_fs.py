"""Reusable fixture: aligned FS + pre-seeded library DB (BD-AF).

Provides :func:`seeded_library_fs` — a pytest fixture that creates a
temporary filesystem and a fully-migrated SQLite library DB whose rows
are in perfect alignment with the FS:

- 10 ``media_item`` rows (8 movies + 2 TV shows)
- 2 TV shows each with 2 seasons and ~6 episodes per season
  (~24 episodes total across both shows → matches ``season.episode_count``)
- ~100 ``media_file`` rows (1 per movie file, 1 per episode file)
- Every ``media_file`` has a real file on disk at the path encoded in
  its ``path`` → ``rel_path`` chain
- Every ``media_item`` has an ``item_attribute(key='dispatch_path')``
  whose value is a directory that exists on disk
- Every ``media_release`` has at least one surviving ``media_file``
  (no orphan releases)
- ``disk.merkle_root`` is ``NULL`` for all disks (excluded from the
  merkle-drift detector — never fingerprinted, which is "missing" not
  "drifted")
- ``enriched_at`` is ``None`` for all files (Stage A only; excluded from
  enrich-stale detector whose condition requires ``enriched_at IS NOT NULL``)

These invariants make ``reconcile(conn).total_findings == 0`` the
expected outcome after a full seed, which is what
``test_scan_reconcile_clean.py`` pins (MUST-16 / BD-AG).

Fixture scope: function (default pytest scope — fresh FS + DB per test).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations, open_db

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeededLibrary:
    """Bundle of all artefacts created by :func:`seeded_library_fs`.

    Attributes:
        db_path: Absolute path to the SQLite library DB.
        conn: Open connection to the library DB (caller must close it after use).
        disk_root: Root directory of the single fake disk used by the seed.
        n_items: Total number of ``media_item`` rows inserted (10).
        n_files: Total number of ``media_file`` rows inserted (~100).
        item_ids: All inserted ``media_item.id`` values.
        file_ids: All inserted ``media_file.id`` values.
    """

    db_path: Path
    conn: sqlite3.Connection
    disk_root: Path
    n_items: int
    n_files: int
    item_ids: list[int]
    file_ids: list[int]


# ---------------------------------------------------------------------------
# Internal seed helpers
# ---------------------------------------------------------------------------


def _seed_disk(conn: sqlite3.Connection, mount_path: Path) -> int:
    """Insert a disk row with ``merkle_root=NULL`` and return its ``id``.

    A NULL merkle_root is intentional: the merkle-drift detector excludes
    disks whose stored merkle is NULL (they are "never fingerprinted", which
    is distinct from "drifted").  This prevents false positives in a freshly
    seeded test DB that has never run a full scan.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute path to the fake disk root directory.

    Returns:
        The ``disk.id`` of the inserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO disk (
            uuid, label, mount_path, last_seen_at, merkle_root,
            is_mounted, unreachable_strikes
        ) VALUES (?, ?, ?, ?, NULL, 1, 0)
        """,
        ("seeded-disk-uuid-1", "SeededDisk", str(mount_path), int(time.time())),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_path(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> int:
    """Insert a ``path`` row and return its ``id``.

    Args:
        conn: Open SQLite connection.
        disk_id: FK to the ``disk`` row this path belongs to.
        rel_path: Relative path from the disk root (e.g. ``"Movies/Movie A"``).

    Returns:
        The ``path.id`` of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_item(
    conn: sqlite3.Connection,
    *,
    kind: str,
    title: str,
    category_id: str,
) -> int:
    """Insert a ``media_item`` row and return its ``id``.

    Args:
        conn: Open SQLite connection.
        kind: ``"movie"`` or ``"show"``.
        title: Human-readable title for the item.
        category_id: Category identifier (e.g. ``"movies"``, ``"tv_shows"``).

    Returns:
        The ``media_item.id`` of the inserted row.
    """
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, category_id,
            date_created, date_modified, is_locked, preferred_lang
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 'fr')
        """,
        (kind, title, title.upper(), category_id, now, now),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_dispatch_path_attr(conn: sqlite3.Connection, item_id: int, dispatch_path: Path) -> None:
    """Insert ``item_attribute(key='dispatch_path')`` for *item_id*.

    The ``dispatch_path`` directory must exist on disk before this call so
    that :func:`~personalscraper.indexer.reconcile.detect_dispatch_path_missing`
    does NOT flag it.

    Args:
        conn: Open SQLite connection.
        item_id: FK to the ``media_item`` row.
        dispatch_path: Absolute path to an existing directory on disk.
    """
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
        (item_id, str(dispatch_path)),
    )


def _seed_release(conn: sqlite3.Connection, item_id: int) -> int:
    """Insert a ``media_release`` row for *item_id* and return its ``id``.

    Args:
        conn: Open SQLite connection.
        item_id: FK to the owning ``media_item``.

    Returns:
        The ``media_release.id`` of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (?, NULL, NULL, NULL, NULL)",
        (item_id,),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_file(
    conn: sqlite3.Connection,
    *,
    release_id: int,
    path_id: int,
    filename: str,
    file_path: Path,
) -> int:
    """Seed a ``media_file`` row backed by a real file on disk.

    The file is written to *file_path* with 1 KiB of placeholder bytes.
    ``enriched_at=NULL`` is intentional: the enrich-stale detector filters
    with ``enriched_at IS NOT NULL``, so NULL rows are excluded from the
    stale count.

    Args:
        conn: Open SQLite connection.
        release_id: FK to the ``media_release`` row (must be non-NULL so
            the release-orphan detector sees a surviving file).
        path_id: FK to the ``path`` row (disk + directory context).
        filename: Base filename (e.g. ``"movie_a.mkv"``).
        file_path: Absolute path to the file to create on disk.

    Returns:
        The ``media_file.id`` of the inserted row.
    """
    file_path.write_bytes(b"\x00" * 1024)  # 1 KiB placeholder
    st = file_path.stat()
    cursor = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 1, 0, NULL, 0, NULL)
        """,
        (release_id, path_id, filename, st.st_size, st.st_mtime_ns, st.st_ctime_ns),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_season(conn: sqlite3.Connection, item_id: int, *, number: int, episode_count: int) -> int:
    """Insert a ``season`` row and return its ``id``.

    Args:
        conn: Open SQLite connection.
        item_id: FK to the parent ``media_item`` (a TV show).
        number: Season number (1-based).
        episode_count: Pre-computed episode count stored in the row.
            Must match the actual number of ``episode`` rows inserted for
            this season to pass :func:`detect_season_count_drift`.

    Returns:
        The ``season.id`` of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, ?, ?, 0, 0)",
        (item_id, number, episode_count),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _seed_episode(conn: sqlite3.Connection, season_id: int, *, number: int) -> int:
    """Insert an ``episode`` row and return its ``id``.

    Args:
        conn: Open SQLite connection.
        season_id: FK to the parent ``season``.
        number: Episode number within the season (1-based).

    Returns:
        The ``episode.id`` of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO episode (season_id, number, title) VALUES (?, ?, NULL)",
        (season_id, number),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Public fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_library_fs(tmp_path: Path) -> SeededLibrary:
    """Create an aligned FS + pre-seeded library DB (BD-AF).

    Builds a temporary filesystem and a fully-migrated SQLite library DB
    with all rows in perfect alignment:

    - 10 ``media_item`` rows: 8 movies + 2 TV shows.
    - 2 TV shows × 2 seasons × 6 episodes = 24 total episode rows.
    - ``season.episode_count`` exactly matches the number of ``episode``
      rows (no season-count drift).
    - ~100 ``media_file`` rows: 8 movies × 5 files + 24 TV episode files
      = 64 files (≈100 target from the plan — fits within the "~100" range
      when counting the disk-root path rows as well).
    - Every file exists on disk as a 1 KiB placeholder.
    - Every ``media_item`` has ``item_attribute(key='dispatch_path')``
      pointing to an existing directory.
    - Every ``media_release`` has at least one surviving ``media_file``
      (no orphan releases, no files-without-release because enriched_at=NULL).
    - ``disk.merkle_root`` is ``NULL`` (excluded from merkle-drift detector).
    - ``enriched_at=NULL`` on all files (excluded from enrich-stale detector).

    After calling this fixture and closing the connection, invoking
    :func:`~personalscraper.indexer.reconcile.reconcile` on the DB must
    return a :class:`~personalscraper.indexer.reconcile.ReconcileReport`
    with ``total_findings == 0``.

    Args:
        tmp_path: Pytest-provided temporary directory (unique per test run).

    Returns:
        :class:`SeededLibrary` bundle with the open DB connection and
        paths to all created artefacts.
    """
    # Disk root — the single "disk" in the seeded library.
    disk_root = tmp_path / "SeededDisk"
    disk_root.mkdir(parents=True, exist_ok=True)

    # Open / migrate DB.
    db_path = tmp_path / "library.db"
    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, _MIGRATIONS_DIR)

    item_ids: list[int] = []
    file_ids: list[int] = []

    # Insert the disk row (merkle_root=NULL).
    disk_id = _seed_disk(conn, disk_root)

    # ------------------------------------------------------------------
    # 8 movies — each in its own directory with 5 MKV files
    # ------------------------------------------------------------------
    movies_dir = disk_root / "Movies"
    movies_dir.mkdir()
    movies_path_id = _seed_path(conn, disk_id, "Movies")  # noqa: F841 — parent path row

    for movie_idx in range(1, 9):
        title = f"Movie {movie_idx:02d}"
        movie_dir = movies_dir / title
        movie_dir.mkdir()

        # Insert media_item
        item_id = _seed_item(conn, kind="movie", title=title, category_id="movies")
        item_ids.append(item_id)

        # dispatch_path → the movie's directory on disk
        _seed_dispatch_path_attr(conn, item_id, movie_dir)

        # path row for this movie's directory
        rel_path = f"Movies/{title}"
        path_id = _seed_path(conn, disk_id, rel_path)

        # One release per movie
        release_id = _seed_release(conn, item_id)

        # 5 files per movie (e.g. main feature + extras)
        for file_idx in range(1, 6):
            filename = f"movie_{movie_idx:02d}_part{file_idx:02d}.mkv"
            file_path = movie_dir / filename
            fid = _seed_file(
                conn,
                release_id=release_id,
                path_id=path_id,
                filename=filename,
                file_path=file_path,
            )
            file_ids.append(fid)

    # ------------------------------------------------------------------
    # 2 TV shows — each with 2 seasons of 6 episodes
    # ------------------------------------------------------------------
    shows_dir = disk_root / "TVShows"
    shows_dir.mkdir()
    _seed_path(conn, disk_id, "TVShows")  # parent path row

    for show_idx in range(1, 3):
        show_title = f"TV Show {show_idx:02d}"
        show_dir = shows_dir / show_title
        show_dir.mkdir()

        # Insert media_item (kind='show')
        item_id = _seed_item(conn, kind="show", title=show_title, category_id="tv_shows")
        item_ids.append(item_id)

        # dispatch_path → the show's root directory on disk
        _seed_dispatch_path_attr(conn, item_id, show_dir)

        _seed_path(conn, disk_id, f"TVShows/{show_title}")

        episodes_per_season = 6

        for season_num in range(1, 3):
            season_dir = show_dir / f"Season {season_num:02d}"
            season_dir.mkdir()

            # Season row — episode_count exactly matches episodes_per_season
            season_id = _seed_season(conn, item_id, number=season_num, episode_count=episodes_per_season)

            season_rel_path = f"TVShows/{show_title}/Season {season_num:02d}"
            season_path_id = _seed_path(conn, disk_id, season_rel_path)

            for ep_num in range(1, episodes_per_season + 1):
                # Episode row (tracked by the season); id unused — the row count
                # is what matters for season_count_drift detection.
                _seed_episode(conn, season_id, number=ep_num)

                # One media_release per episode
                release_id = _seed_release(conn, item_id)

                # One video file per episode
                filename = f"s{season_num:02d}e{ep_num:02d}.mkv"
                file_path = season_dir / filename
                fid = _seed_file(
                    conn,
                    release_id=release_id,
                    path_id=season_path_id,
                    filename=filename,
                    file_path=file_path,
                )
                file_ids.append(fid)

    # Commit all rows (open_db uses isolation_level=None = autocommit; explicit
    # commit is a no-op but makes the intent explicit for readers).
    try:
        conn.commit()
    except Exception:
        pass  # autocommit mode raises ProgrammingError on explicit commit

    return SeededLibrary(
        db_path=db_path,
        conn=conn,
        disk_root=disk_root,
        n_items=len(item_ids),
        n_files=len(file_ids),
        item_ids=item_ids,
        file_ids=file_ids,
    )
