"""The library service's test world: a fixture index, a fixture catalogue and fake providers."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pytest

from personalscraper.acquire.catalogue import CatalogueEpisode, CatalogueStore, ProviderClients
from personalscraper.api.metadata._base import MediaDetails
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.library.completeness import CatalogueView
from personalscraper.app.library.deleting import LibraryDeletion
from personalscraper.app.library.reads import LibraryReads
from personalscraper.app.library.rescrape import LibraryRescrape
from personalscraper.app.library.sheets import MediaSheets
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor.service import RunService
from personalscraper.core._contracts import ApiError
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.library_view import LibraryIndex
from personalscraper.indexer.ownership import IndexerOwnershipChecker

_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"

#: The service's « today » in every test: 2026-10-04 at noon, local time.
TODAY = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 12, 0).timestamp()


class FixtureIndex:
    """A migrated ``library.db`` the tests write rows and files into."""

    def __init__(self, path: Path) -> None:
        """Create and migrate the index with one disk.

        Args:
            path: Where ``library.db`` is written.
        """
        self.path = path
        self.conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        apply_migrations(self.conn, _MIGRATIONS_DIR)
        self.conn.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1', 'Disk1', '/d1', 1)")
        self.conn.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u2', 'Disk2', '/d2', 1)")
        self._created = 1_700_000_000

    def item(
        self,
        title: str,
        *,
        kind: str = "movie",
        year: int | None = 2020,
        category: str | None = None,
        tvdb: str | None = None,
        tmdb: str | None = None,
        imdb: str | None = None,
        canonical: str | None = None,
        title_sort: str | None = None,
        original_title: str | None = None,
        overview: str | None = None,
        poster_url: str | None = None,
        poster_file: bool = False,
        provider_read: float | None = None,
        created: int | None = None,
    ) -> int:
        """Insert one ``media_item`` row; each call is one second younger than the last.

        Args:
            title: The stored title.
            kind: ``"movie"`` or ``"show"``.
            year: The year.
            category: The leaf category; ``movies`` / ``tv_shows`` by kind when absent.
            tvdb: TVDB id.
            tmdb: TMDB id.
            imdb: IMDb id.
            canonical: ``canonical_provider``.
            title_sort: The sort title; the title when absent.
            original_title: The original title.
            overview: The NFO synopsis.
            poster_url: The NFO poster URL.
            poster_file: Whether the artwork inventory saw a poster file.
            provider_read: ``date_provider_read``.
            created: ``date_created``; the next second when absent.

        Returns:
            The row id.
        """
        ids: dict[str, dict[str, str | None]] = {}
        for provider, value in (("tvdb", tvdb), ("tmdb", tmdb), ("imdb", imdb)):
            if value is not None:
                ids[provider] = {"series_id": value, "episode_id": None}
        self._created += 1
        cur = self.conn.execute(
            "INSERT INTO media_item(kind, title, title_sort, original_title, year, category_id, date_created,"
            " date_modified, external_ids_json, canonical_provider, overview, poster_url, artwork_json,"
            " date_provider_read) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                kind,
                title,
                title_sort or title,
                original_title,
                year,
                category or ("tv_shows" if kind == "show" else "movies"),
                created if created is not None else self._created,
                0,
                json.dumps(ids),
                canonical,
                overview,
                poster_url,
                json.dumps({"poster": poster_file, "fanart": False}),
                provider_read,
            ),
        )
        assert cur.lastrowid is not None
        return cur.lastrowid

    def mount(self, disk: int, root: Path | None) -> None:
        """Point a disk at a real directory, or mark it unmounted.

        Args:
            disk: The disk id.
            root: Its mount point, or ``None`` for an unmounted disk.
        """
        self.conn.execute(
            "UPDATE disk SET mount_path = ?, is_mounted = ? WHERE id = ?",
            (str(root) if root is not None else None, int(root is not None), disk),
        )

    def _path(self, rel_path: str, disk: int) -> int:
        """Return the ``path`` id of a directory, inserting it when new."""
        self.conn.execute("INSERT OR IGNORE INTO path(disk_id, rel_path) VALUES (?, ?)", (disk, rel_path))
        return self.conn.execute("SELECT id FROM path WHERE disk_id = ? AND rel_path = ?", (disk, rel_path)).fetchone()[
            0
        ]

    def _file(self, release_id: int, path_id: int, name: str, deleted: bool) -> None:
        """Attach one file to a release."""
        self.conn.execute(
            "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
            " scan_generation, last_verified_at, deleted_at) VALUES (?,?,?,1,1,'0',1,1,?)",
            (release_id, path_id, name, 5 if deleted else None),
        )

    def movie_file(self, item_id: int, folder: str = "films/X", *, deleted: bool = False, disk: int = 1) -> None:
        """Give a movie row one file.

        Args:
            item_id: The movie row.
            folder: The file's directory.
            deleted: Whether the file is tombstoned.
            disk: The disk id.
        """
        release = self.conn.execute(
            "INSERT INTO media_release(item_id, quality) VALUES (?, '1080p')", (item_id,)
        ).lastrowid
        assert release is not None
        self._file(release, self._path(folder, disk), f"{item_id}-{release}.mkv", deleted)

    def episodes(
        self,
        item_id: int,
        season: int,
        numbers: Iterable[int],
        *,
        folder: str | None = None,
        deleted: bool = False,
        disk: int = 1,
    ) -> None:
        """Give a show row one file per episode of one season.

        Args:
            item_id: The show row.
            season: The season number.
            numbers: The episode numbers.
            folder: The season's directory; ``series/<id>/Saison NN`` when absent.
            deleted: Whether the files are tombstoned.
            disk: The disk id.
        """
        found = self.conn.execute(
            "SELECT id FROM season WHERE item_id = ? AND number = ?", (item_id, season)
        ).fetchone()
        season_id = (
            found[0]
            if found
            else self.conn.execute("INSERT INTO season(item_id, number) VALUES (?, ?)", (item_id, season)).lastrowid
        )
        path_id = self._path(folder or f"series/{item_id}/Saison {season:02d}", disk)
        for number in numbers:
            episode = self.conn.execute(
                "INSERT INTO episode(season_id, number) VALUES (?, ?)", (season_id, number)
            ).lastrowid
            release = self.conn.execute(
                "INSERT INTO media_release(episode_id, quality) VALUES (?, '1080p')", (episode,)
            ).lastrowid
            assert release is not None
            self._file(release, path_id, f"s{season}e{number}.mkv", deleted)


def catalogued(store: CatalogueStore, provider: str, provider_id: str, seasons: dict[int, list[date | None]]) -> None:
    """Write a show's catalogue: per season, one air date (or ``None``) per episode from 1.

    Args:
        store: The catalogue store.
        provider: ``"tvdb"`` or ``"tmdb"``.
        provider_id: The show's id.
        seasons: ``{season: [air date of e1, e2, …]}``.
    """
    episodes = [
        CatalogueEpisode(season, number, aired, f"S{season}E{number}")
        for season, dates in seasons.items()
        for number, aired in enumerate(dates, start=1)
    ]
    store.replace_show(provider, provider_id, "Continuing", episodes, NOW - 60)


@dataclass
class FakeClient:
    """A provider client answering from a table, or failing as told."""

    shows: dict[str, MediaDetails] = field(default_factory=dict)
    movies: dict[str, MediaDetails] = field(default_factory=dict)
    down: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)

    def _answer(self, table: dict[str, MediaDetails], what: str, provider_id: str | int) -> MediaDetails:
        """Answer one call."""
        self.calls.append((what, str(provider_id)))
        if self.down:
            raise ConnectionError("provider down")
        if str(provider_id) not in table:
            raise ApiError(provider="X", http_status=404, message="not found")
        return table[str(provider_id)]

    def get_tv(self, provider_id: str | int) -> MediaDetails:
        """Answer a show."""
        return self._answer(self.shows, "tv", provider_id)

    def get_movie(self, movie_id: str | int) -> MediaDetails:
        """Answer a movie."""
        return self._answer(self.movies, "movie", movie_id)

    def get_episodes(self, series_id: str | int, season: int) -> list[object]:
        """Never asked by the read service."""
        raise AssertionError("the read service never fetches episodes")


@dataclass
class World:
    """Everything one service test touches."""

    index: FixtureIndex
    store: CatalogueStore
    tvdb: FakeClient
    tmdb: FakeClient
    view: CatalogueView
    library: LibraryReads
    sheets: MediaSheets
    rescrape: LibraryRescrape
    deletion: LibraryDeletion
    actor: Actor
    clock: list[float]
    data_dir: Path
    app_store: AppStore
    runs: RunService


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    """A service over an empty fixture index, an empty catalogue and two fake providers.

    Args:
        tmp_path: Pytest's temporary directory.

    Yields:
        The world; its stores are closed after the test.
    """
    index = FixtureIndex(tmp_path / "library.db")
    store = CatalogueStore(tmp_path / "acquire.db")
    tvdb, tmdb = FakeClient(), FakeClient()
    clock = [NOW]
    ownership = IndexerOwnershipChecker(index.path)
    library_index = LibraryIndex(index.path)
    view = CatalogueView(catalogue=store, ownership=ownership)
    sheets = MediaSheets(
        index=library_index,
        view=view,
        providers=ProviderClients(tvdb=tvdb, tmdb=tmdb),  # type: ignore[arg-type]
        clock=lambda: clock[0],
    )
    library = LibraryReads(index=library_index, view=view, sheets=sheets, clock=lambda: clock[0])
    app_store = AppStore(tmp_path / "app.db")
    runs = RunService(store=app_store, data_dir=tmp_path)
    rescrape = LibraryRescrape(index=library_index, runs=runs)
    deletion = LibraryDeletion(index=library_index, index_db=index.path, data_dir=tmp_path)
    actor = Actor.system(InstanceCeiling(forbidden=frozenset(), read_only=False), account_id="owner", name="Owner")
    yield World(
        index, store, tvdb, tmdb, view, library, sheets, rescrape, deletion, actor, clock, tmp_path, app_store, runs
    )
    app_store.close()
    view.close()
    ownership.close()
    store.close()
    index.conn.close()
