"""Repo-specific tests for tv_repo: season + episode insertion and trigger enforcement.

Focuses on behaviors not covered by the round-trip tests in test_schema.py:
- Happy-path insert of season + episode under a kind='show' item
- trg_season_requires_show rejects a season insert when parent kind='movie'
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo, tv_repo
from personalscraper.indexer.schema import EpisodeRow, MediaItemRow, SeasonRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB seeded with the full migration chain.

    Returns:
        An open :class:`sqlite3.Connection` with the full schema applied.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _insert_item(c: sqlite3.Connection, kind: str) -> int:
    """Insert a media_item with the given kind and return its id.

    Args:
        c: Open SQLite connection.
        kind: ``'show'`` or ``'movie'``.

    Returns:
        The rowid of the inserted media item.
    """
    now = int(time.time())
    return item_repo.insert(
        c,
        MediaItemRow(
            id=0,
            kind=kind,
            title="Test Title",
            title_sort="Test Title",
            original_title=None,
            year=2024,
            category_id="tv_shows" if kind == "show" else "movies",
            tmdb_id=None,
            imdb_id=None,
            tvdb_id=None,
            nfo_status=None,
            artwork_json=None,
            date_created=now,
            date_modified=now,
            date_metadata_refreshed=None,
            is_locked=0,
            preferred_lang="en",
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_insert_season_under_show_succeeds(conn: sqlite3.Connection) -> None:
    """insert_season succeeds when item_id references a kind='show' row."""
    show_id = _insert_item(conn, "show")
    season_row = SeasonRow(id=0, item_id=show_id, number=1, episode_count=0, has_poster=0, episodes_with_nfo=0)
    season_id = tv_repo.insert_season(conn, season_row)
    assert isinstance(season_id, int)
    assert season_id > 0


def test_insert_episode_under_season_succeeds(conn: sqlite3.Connection) -> None:
    """insert_episode succeeds for a valid season linked to a show."""
    show_id = _insert_item(conn, "show")
    season_id = tv_repo.insert_season(
        conn, SeasonRow(id=0, item_id=show_id, number=1, episode_count=0, has_poster=0, episodes_with_nfo=0)
    )
    ep_row = EpisodeRow(id=0, season_id=season_id, number=1, title="Pilot")
    ep_id = tv_repo.insert_episode(conn, ep_row)
    assert isinstance(ep_id, int)
    assert ep_id > 0

    fetched = tv_repo.get_episode_by_id(conn, ep_id)
    assert fetched is not None
    assert fetched.title == "Pilot"
    assert fetched.number == 1


def test_trg_season_requires_show_rejects_movie_parent(conn: sqlite3.Connection) -> None:
    """trg_season_requires_show fires and raises IntegrityError when parent kind='movie'."""
    movie_id = _insert_item(conn, "movie")
    season_row = SeasonRow(id=0, item_id=movie_id, number=1, episode_count=0, has_poster=0, episodes_with_nfo=0)

    with pytest.raises(sqlite3.IntegrityError):
        tv_repo.insert_season(conn, season_row)


def test_get_season_by_id_returns_correct_row(conn: sqlite3.Connection) -> None:
    """get_season_by_id returns the expected SeasonRow after insertion."""
    show_id = _insert_item(conn, "show")
    season_row = SeasonRow(id=0, item_id=show_id, number=2, episode_count=5, has_poster=1, episodes_with_nfo=3)
    season_id = tv_repo.insert_season(conn, season_row)

    fetched = tv_repo.get_season_by_id(conn, season_id)
    assert fetched is not None
    assert fetched.number == 2
    assert fetched.episode_count == 5
    assert fetched.has_poster == 1
    assert fetched.episodes_with_nfo == 3


def test_get_episodes_for_season_returns_ordered_list(conn: sqlite3.Connection) -> None:
    """get_episodes_for_season returns episodes in ascending number order."""
    show_id = _insert_item(conn, "show")
    season_id = tv_repo.insert_season(
        conn, SeasonRow(id=0, item_id=show_id, number=1, episode_count=0, has_poster=0, episodes_with_nfo=0)
    )
    tv_repo.insert_episode(conn, EpisodeRow(id=0, season_id=season_id, number=3, title="Third"))
    tv_repo.insert_episode(conn, EpisodeRow(id=0, season_id=season_id, number=1, title="First"))
    tv_repo.insert_episode(conn, EpisodeRow(id=0, season_id=season_id, number=2, title="Second"))

    episodes = tv_repo.get_episodes_for_season(conn, season_id)
    assert [ep.number for ep in episodes] == [1, 2, 3]
