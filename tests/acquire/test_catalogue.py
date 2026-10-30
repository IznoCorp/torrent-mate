"""Tests for the library-wide aired catalogue (migration 026, store, refresh)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from personalscraper.acquire import catalogue as catalogue_module
from personalscraper.acquire import store as acquire_store
from personalscraper.acquire.catalogue import (
    CatalogueEpisode,
    CatalogueStore,
    ProviderClients,
    aired_by_season,
    refresh_catalogue,
)
from personalscraper.acquire.errors import AcquireCorruptError
from personalscraper.api._contracts import ApiError
from personalscraper.api.metadata._base import EpisodeInfo, MediaDetails, SeasonInfo
from personalscraper.core.sqlite import SqliteSchemaNewerError, apply_migrations

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "migrations"
NOW = 1_800_000_000.0
DAY = 86400.0


def _ep(season: int, episode: int, air: str | None = "2020-01-01", title: str | None = None) -> CatalogueEpisode:
    return CatalogueEpisode(season, episode, date.fromisoformat(air) if air else None, title)


@pytest.fixture
def store(tmp_path: Path) -> CatalogueStore:
    """A store over a fresh, fully migrated acquire.db."""
    s = CatalogueStore(tmp_path / "acquire.db")
    yield s
    s.close()


class TestMigration026:
    """026 adds the two catalogue tables on top of a database at 025."""

    def test_applies_on_a_database_at_025(self, tmp_path: Path) -> None:
        """A 025 database is migrated to 026 with both tables and no loss."""
        only_to_025 = tmp_path / "m025"
        only_to_025.mkdir()
        for sql in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if int(sql.name[:3]) <= 25:
                (only_to_025 / sql.name).write_text(sql.read_text())
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        apply_migrations(conn, only_to_025)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 25

        apply_migrations(conn, MIGRATIONS_DIR)

        assert conn.execute("PRAGMA user_version").fetchone()[0] == 26
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"catalogue_show", "catalogue_episode"} <= tables


class TestNewerThanTheCode:
    """An ``acquire.db`` migrated past the code is refused by the catalogue's opener."""

    def test_opening_a_newer_store_is_refused_untouched(self, tmp_path: Path) -> None:
        """The first use raises ``SqliteSchemaNewerError``; the store keeps its version and gets no table."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        newer = max(int(sql.name[:3]) for sql in MIGRATIONS_DIR.glob("*.sql")) + 1
        conn.execute(f"PRAGMA user_version = {newer}")
        conn.close()
        catalogue = CatalogueStore(db_path)

        with pytest.raises(SqliteSchemaNewerError):
            catalogue.episodes("tvdb", "1")

        catalogue.close()
        with sqlite3.connect(str(db_path)) as check:
            assert check.execute("PRAGMA user_version").fetchone()[0] == newer
        check.close()


class TestReplaceShow:
    """replace_show writes a show's rows atomically."""

    def test_round_trip(self, store: CatalogueStore) -> None:
        """What is written is read back, ordered by season then episode."""
        store.replace_show("tvdb", "1", "Continuing", [_ep(1, 2, "2020-01-08"), _ep(1, 1, None, "Pilot")], NOW)
        assert store.episodes("tvdb", "1") == [_ep(1, 1, None, "Pilot"), _ep(1, 2, "2020-01-08")]

    def test_never_fetched_reads_none(self, store: CatalogueStore) -> None:
        """A show with no row reads None, distinct from a fetched show with no episodes."""
        assert store.episodes("tvdb", "404") is None
        store.replace_show("tvdb", "404", None, [], NOW)
        assert store.episodes("tvdb", "404") == []

    def test_replaces_previous_rows(self, store: CatalogueStore) -> None:
        """A second write drops the episodes the provider no longer lists."""
        store.replace_show("tvdb", "1", "Continuing", [_ep(1, 1), _ep(1, 2)], NOW)
        store.replace_show("tvdb", "1", "Ended", [_ep(1, 1)], NOW + 1)
        assert store.episodes("tvdb", "1") == [_ep(1, 1)]

    def test_is_atomic(self, store: CatalogueStore) -> None:
        """A failure mid-write leaves the previous rows untouched."""
        store.replace_show("tvdb", "1", "Continuing", [_ep(1, 1)], NOW)
        duplicate = [_ep(1, 1), _ep(1, 1)]  # primary-key violation on the second insert
        with pytest.raises(sqlite3.IntegrityError):
            store.replace_show("tvdb", "1", "Ended", duplicate, NOW + 1)
        assert store.episodes("tvdb", "1") == [_ep(1, 1)]

    def test_providers_do_not_mix(self, store: CatalogueStore) -> None:
        """The same id under two providers is two shows."""
        store.replace_show("tvdb", "1", None, [_ep(1, 1)], NOW)
        store.replace_show("tmdb", "1", None, [_ep(2, 5)], NOW)
        assert store.episodes("tvdb", "1") == [_ep(1, 1)]
        assert store.episodes("tmdb", "1") == [_ep(2, 5)]


class TestDue:
    """due selects what the politeness rule allows to refresh."""

    def test_never_fetched_known_shows_are_due(self, store: CatalogueStore) -> None:
        """A show the index names and the store lacks is due."""
        assert store.due(NOW, known=[("tvdb", "9")]) == [("tvdb", "9")]

    def test_continuing_show_due_after_seven_days_only(self, store: CatalogueStore) -> None:
        """A continuing show is due once older than the window, not before."""
        store.replace_show("tvdb", "1", "Continuing", [], NOW - 6 * DAY)
        store.replace_show("tvdb", "2", "Returning Series", [], NOW - 8 * DAY)
        store.replace_show("tvdb", "3", None, [], NOW - 8 * DAY)  # no status = ignorance, not ended
        assert store.due(NOW) == [("tvdb", "2"), ("tvdb", "3")]

    def test_ended_show_is_never_due_again(self, store: CatalogueStore) -> None:
        """An ended show fetched once is never refreshed, however old."""
        store.replace_show("tvdb", "1", "Ended", [_ep(1, 1)], NOW - 900 * DAY)
        store.replace_show("tmdb", "2", "Canceled", [_ep(1, 1)], NOW - 900 * DAY)
        assert store.due(NOW) == []

    def test_ended_show_stored_with_no_episode_stays_due(self, store: CatalogueStore) -> None:
        """An empty answer for an ended show is doubt, not closure: it is retried after the period."""
        store.replace_show("tvdb", "1", "Ended", [], NOW - 8 * DAY)
        store.replace_show("tvdb", "2", "Ended", [], NOW - DAY)
        assert store.due(NOW) == [("tvdb", "1")]

    def test_a_failed_show_waits_the_period_and_comes_after_the_healthy_ones(self, store: CatalogueStore) -> None:
        """A failed attempt is recorded: no retry before the period, then last in the queue."""
        store.record_failure("tvdb", "bad", NOW - 8 * DAY)  # attempted long ago: due again
        store.record_failure("tvdb", "fresh", NOW - DAY)  # attempted yesterday: backed off
        store.replace_show("tvdb", "old", "Continuing", [_ep(1, 1)], NOW - 30 * DAY)
        known = [("tvdb", "bad"), ("tvdb", "fresh"), ("tvdb", "new")]
        assert store.due(NOW, known=known) == [("tvdb", "new"), ("tvdb", "old"), ("tvdb", "bad")]

    def test_a_failed_show_is_never_read_as_fetched(self, store: CatalogueStore) -> None:
        """Recording a failure does not make the show « fetched with no episode »."""
        store.record_failure("tvdb", "bad", NOW)
        assert store.episodes("tvdb", "bad") is None

    def test_a_failure_keeps_the_previous_rows(self, store: CatalogueStore) -> None:
        """A failure on a catalogued show leaves its rows readable."""
        store.replace_show("tvdb", "1", "Continuing", [_ep(1, 1)], NOW - 30 * DAY)
        store.record_failure("tvdb", "1", NOW)
        assert store.episodes("tvdb", "1") == [_ep(1, 1)]

    def test_oldest_first_and_never_fetched_first(self, store: CatalogueStore) -> None:
        """The order is: never fetched, then the stalest."""
        store.replace_show("tvdb", "1", "Continuing", [], NOW - 10 * DAY)
        store.replace_show("tvdb", "2", "Continuing", [], NOW - 30 * DAY)
        assert store.due(NOW, known=[("tvdb", "9")]) == [("tvdb", "9"), ("tvdb", "2"), ("tvdb", "1")]


class TestAiredBySeason:
    """aired_by_season counts the episodes whose date has come."""

    def test_counts_dates_up_to_today_inclusive(self) -> None:
        """air_date <= today counts; later and undated do not."""
        eps = [_ep(1, 1, "2020-01-01"), _ep(1, 2, "2020-06-01"), _ep(1, 3, "2020-06-02"), _ep(1, 4, None)]
        assert aired_by_season(eps, date(2020, 6, 1)) == {1: 2}

    def test_specials_are_excluded(self) -> None:
        """Season 0 is stored but never counted."""
        assert aired_by_season([_ep(0, 1), _ep(1, 1)], date(2021, 1, 1)) == {1: 1}

    def test_a_season_with_nothing_aired_reads_zero(self) -> None:
        """A catalogued season not yet started is present with 0."""
        assert aired_by_season([_ep(2, 1, "2030-01-01")], date(2021, 1, 1)) == {2: 0}


@dataclass
class FakeClient:
    """A provider client answering from a script; raises for ids in ``fail``."""

    shows: dict[str, tuple[str | None, dict[int, list[tuple[int, str, str]]]]]
    fail: set[str] = field(default_factory=set)
    fail_season: dict[str, int] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def get_tv(self, provider_id: int | str) -> MediaDetails:
        """Answer the scripted show, or fail for ids in ``fail``."""
        pid = str(provider_id)
        self.calls.append(pid)
        if pid in self.fail:
            raise ApiError("TVDB", 500, message="boom")
        status, seasons = self.shows[pid]
        return MediaDetails(
            provider="tvdb",
            provider_id=pid,
            title="t",
            series_status=status,
            seasons=[SeasonInfo(season_number=n, episode_count=len(e)) for n, e in sorted(seasons.items())],
        )

    def get_episodes(self, series_id: str | int, season: int) -> list[EpisodeInfo]:
        """Answer the scripted episodes of one season."""
        _, seasons = self.shows[str(series_id)]
        if self.fail_season.get(str(series_id)) == season:
            raise ApiError("TVDB", 500, message="boom")
        return [EpisodeInfo(episode_number=n, title=t, air_date=d, season_number=season) for n, t, d in seasons[season]]


def _index(rows: list[tuple[str | None, dict[str, str]]]) -> sqlite3.Connection:
    """An in-memory index with the media_item columns the refresh reads."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE media_item (id INTEGER PRIMARY KEY, kind TEXT, canonical_provider TEXT, external_ids_json TEXT)"
    )
    for canonical, ids in rows:
        conn.execute(
            "INSERT INTO media_item (kind, canonical_provider, external_ids_json) VALUES ('show', ?, ?)",
            (canonical, json.dumps({p: {"series_id": i, "episode_id": None} for p, i in ids.items()})),
        )
    conn.execute(
        "INSERT INTO media_item (kind, canonical_provider, external_ids_json) "
        "VALUES ('movie', 'tmdb', '{\"tmdb\": {\"series_id\": \"5\"}}')"
    )
    return conn


class TestRefresh:
    """refresh_catalogue drives the providers, bounded and fail-soft."""

    def test_writes_each_show_with_specials_and_status(self, store: CatalogueStore) -> None:
        """Episodes of every season, specials included, land with the provider status."""
        tvdb = FakeClient(
            {"10": ("Continuing", {0: [(1, "Special", "2019-01-01")], 1: [(1, "Pilot", "2020-01-01"), (2, "Two", "")]})}
        )
        report = refresh_catalogue(
            store, _index([("tvdb", {"tvdb": "10"})]), ProviderClients(tvdb=tvdb, tmdb=None), now=NOW, max_shows=10
        )
        assert report.refreshed == 1 and report.failed == 0
        assert store.episodes("tvdb", "10") == [
            _ep(0, 1, "2019-01-01", "Special"),
            _ep(1, 1, "2020-01-01", "Pilot"),
            _ep(1, 2, None, "Two"),
        ]

    def test_movies_are_ignored_and_canonical_provider_wins(self, store: CatalogueStore) -> None:
        """Only shows are read; the canonical provider's id is the key, tvdb then tmdb otherwise."""
        tvdb = FakeClient(
            {"10": ("Ended", {1: [(1, "a", "2020-01-01")]}), "11": ("Ended", {1: [(1, "a", "2020-01-01")]})}
        )
        tmdb = FakeClient(
            {"20": ("Ended", {1: [(1, "a", "2020-01-01")]}), "21": ("Ended", {1: [(1, "a", "2020-01-01")]})}
        )
        index = _index(
            [
                ("tmdb", {"tvdb": "10", "tmdb": "20"}),  # canonical tmdb
                (None, {"tvdb": "11", "tmdb": "21"}),  # no canonical: tvdb first
                (None, {"tmdb": "21"}),  # duplicate of nothing already stored under tmdb 21? distinct provider key
            ]
        )
        report = refresh_catalogue(store, index, ProviderClients(tvdb=tvdb, tmdb=tmdb), now=NOW, max_shows=10)
        assert report.refreshed == 3
        assert store.episodes("tmdb", "20") is not None
        assert store.episodes("tvdb", "11") is not None
        assert store.episodes("tmdb", "21") is not None
        assert store.episodes("tvdb", "10") is None
        assert tmdb.calls == ["20", "21"] and tvdb.calls == ["11"]

    def test_max_bounds_the_run(self, store: CatalogueStore) -> None:
        """No more than max_shows providers are polled; the rest is reported."""
        shows = {str(i): ("Continuing", {1: [(1, "a", "2020-01-01")]}) for i in range(5)}
        tvdb = FakeClient(shows)
        index = _index([("tvdb", {"tvdb": str(i)}) for i in range(5)])
        report = refresh_catalogue(store, index, ProviderClients(tvdb=tvdb, tmdb=None), now=NOW, max_shows=2)
        assert len(tvdb.calls) == 2
        assert report.refreshed == 2 and report.remaining == 3

    def test_a_provider_failure_keeps_previous_rows_and_continues(self, store: CatalogueStore) -> None:
        """The failing show keeps what it had; the next show is still refreshed."""
        store.replace_show("tvdb", "1", "Continuing", [_ep(1, 1, "2020-01-01", "kept")], NOW - 30 * DAY)
        tvdb = FakeClient(
            {"1": ("Continuing", {}), "2": ("Continuing", {1: [(1, "new", "2020-01-01")]})},
            fail={"1"},
        )
        index = _index([("tvdb", {"tvdb": "1"}), ("tvdb", {"tvdb": "2"})])
        report = refresh_catalogue(store, index, ProviderClients(tvdb=tvdb, tmdb=None), now=NOW, max_shows=10)
        assert report.failed == 1 and report.refreshed == 1
        assert store.episodes("tvdb", "1") == [_ep(1, 1, "2020-01-01", "kept")]
        assert store.episodes("tvdb", "2") == [_ep(1, 1, "2020-01-01", "new")]

    def test_a_missing_client_is_skipped_not_failed(self, store: CatalogueStore) -> None:
        """A show whose provider has no client is reported skipped and never stored."""
        report = refresh_catalogue(
            store, _index([("tmdb", {"tmdb": "20"})]), ProviderClients(tvdb=None, tmdb=None), now=NOW, max_shows=10
        )
        assert report.skipped == 1 and report.refreshed == 0
        assert store.episodes("tmdb", "20") is None

    def test_fresh_and_ended_shows_are_not_polled(self, store: CatalogueStore) -> None:
        """The politeness rule is applied: nothing due, nothing polled."""
        store.replace_show("tvdb", "1", "Continuing", [], NOW - DAY)
        store.replace_show("tvdb", "2", "Ended", [_ep(1, 1)], NOW - 900 * DAY)
        tvdb = FakeClient({})
        index = _index([("tvdb", {"tvdb": "1"}), ("tvdb", {"tvdb": "2"})])
        report = refresh_catalogue(store, index, ProviderClients(tvdb=tvdb, tmdb=None), now=NOW, max_shows=10)
        assert tvdb.calls == [] and report.refreshed == 0

    def test_a_failure_on_a_later_season_keeps_every_previous_row(self, store: CatalogueStore) -> None:
        """Season 1 answers, season 2 fails: nothing of the new answer is written, the run goes on."""
        store.replace_show("tvdb", "1", "Continuing", [_ep(1, 1, "2020-01-01", "kept")], NOW - 30 * DAY)
        tvdb = FakeClient(
            {
                "1": ("Continuing", {1: [(1, "new", "2020-01-01")], 2: [(1, "new2", "2021-01-01")]}),
                "2": ("Continuing", {1: [(1, "ok", "2020-01-01")]}),
            },
            fail_season={"1": 2},
        )
        index = _index([("tvdb", {"tvdb": "1"}), ("tvdb", {"tvdb": "2"})])
        report = refresh_catalogue(store, index, ProviderClients(tvdb=tvdb, tmdb=None), now=NOW, max_shows=10)
        assert report.failed == 1 and report.refreshed == 1
        assert store.episodes("tvdb", "1") == [_ep(1, 1, "2020-01-01", "kept")]
        assert store.episodes("tvdb", "2") == [_ep(1, 1, "2020-01-01", "ok")]

    def test_a_show_failing_every_run_does_not_starve_the_others(self, store: CatalogueStore) -> None:
        """With --max 1, the permanently failing show is attempted once, then the next show gets the slot."""
        tvdb = FakeClient(
            {"bad": ("Continuing", {}), "good": ("Continuing", {1: [(1, "a", "2020-01-01")]})}, fail={"bad"}
        )
        clients = ProviderClients(tvdb=tvdb, tmdb=None)
        index = _index([("tvdb", {"tvdb": "bad"}), ("tvdb", {"tvdb": "good"})])
        first = refresh_catalogue(store, index, clients, now=NOW, max_shows=1)
        second = refresh_catalogue(store, index, clients, now=NOW + 60, max_shows=1)
        assert (first.failed, first.refreshed) == (1, 0)
        assert (second.failed, second.refreshed) == (0, 1)
        assert store.episodes("tvdb", "good") is not None
        assert store.episodes("tvdb", "bad") is None


class TestOpen:
    """The store opens ``acquire.db`` the way the acquire store does."""

    def test_a_corrupt_database_raises_the_acquire_error(self, tmp_path: Path) -> None:
        """A malformed file surfaces as AcquireCorruptError, as through the acquire store."""
        path = tmp_path / "acquire.db"
        path.write_bytes(b"this is not a sqlite database" * 100)
        with pytest.raises(AcquireCorruptError):
            CatalogueStore(path).episodes("tvdb", "1")

    def test_the_lock_timeout_is_the_acquire_stores(self) -> None:
        """One migration-lock timeout for every opener of acquire.db."""
        assert catalogue_module._MIGRATION_LOCK_TIMEOUT_S == acquire_store._MIGRATION_LOCK_TIMEOUT_S

    def test_a_show_without_client_does_not_consume_a_max_slot(self, store: CatalogueStore) -> None:
        """An unconfigured provider makes no call, so it cannot starve the registered one under --max 1."""
        tvdb = FakeClient({"1": ("Continuing", {1: [(1, "a", "2020-01-01")]})})
        index = _index([("tmdb", {"tmdb": "20"}), ("tvdb", {"tvdb": "1"})])
        report = refresh_catalogue(store, index, ProviderClients(tvdb=tvdb, tmdb=None), now=NOW, max_shows=1)
        assert (report.skipped, report.refreshed, report.remaining) == (1, 1, 0)
        assert store.episodes("tvdb", "1") is not None
