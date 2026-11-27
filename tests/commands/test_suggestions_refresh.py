"""``personalscraper acquisition-suggestions-refresh`` and the refresh it drives (K3 P11c, DESIGN § 2.11).

The provider is a fake ``RecommendationProvider`` that records what it was asked; the library is
a fake index whose reader serves ``IndexItem`` rows — no ``library.db`` is opened, by SQL or
otherwise. The acquire store is a real one on ``tmp_path``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.acquire.domain import FollowedSeries, SuggestionRow
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.acquire.suggestions_refresh import DEFAULT_MIN_INTERVAL_S
from personalscraper.acquire.suggestions_refresh import refresh_suggestions as _refresh
from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import Recommendation
from personalscraper.app.acquisition.held_titles import held_titles
from personalscraper.app.schedulers.registry import CRON_JOBS
from personalscraper.cli import app
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import IndexItem, IndexUnavailable
from tests.indexer.test_ecosystem import _ECOSYSTEM_PATH, _get_app_by_name, _job_schedule, _parse_ecosystem_apps

runner = CliRunner()
_MODULE = "personalscraper.commands.suggestions_refresh"
_NOW = 1_800_000_000


class _Provider:
    """A fake ``RecommendationProvider``: answers canned recommendations and records every ask."""

    def __init__(
        self,
        name: str = "trakt",
        answers: dict[str, list[Recommendation]] | None = None,
        failing: set[str] | None = None,
    ) -> None:
        self.provider_name = name
        self.answers = answers or {}
        self.failing = failing or set()
        self.calls: list[tuple[str, MediaType]] = []

    def get_recommendations(self, media_id: str, media_type: MediaType = MediaType.MOVIE) -> list[Recommendation]:
        """Record the ask, then fail or answer for the seed."""
        self.calls.append((media_id, media_type))
        if media_id in self.failing:
            raise RuntimeError("provider down")
        return self.answers.get(media_id, [])


class _FakeIndex:
    """A fake ``LibraryIndex``: its reader serves rows, and counts its opens."""

    def __init__(self, items: list[IndexItem] | Exception) -> None:
        self.items = items
        self.opened = 0

    def reader(self):  # noqa: ANN201 — a context manager, as the real index's
        """Open a reader over the rows, or raise what an absent index raises."""
        self.opened += 1
        if isinstance(self.items, Exception):
            raise self.items
        return nullcontext(SimpleNamespace(live_items=lambda: list(self.items)))


def refresh_suggestions(store: ConcreteAcquireStore, index: _FakeIndex, providers: list[_Provider], **kwargs: object):  # noqa: ANN201
    """Run the refresh with the library read through ``index``, as the command wires it."""
    return _refresh(store, lambda: held_titles(index), providers, **kwargs)  # type: ignore[arg-type]


def _item(kind: Literal["movie", "show"], title: str, **ids: int | str) -> IndexItem:
    """A library row holding ``ids`` (``tvdb`` / ``tmdb`` ints, ``imdb`` text)."""
    return IndexItem(
        item_id=len(title),  # type: ignore[arg-type]
        kind=kind,
        title=title,
        title_sort=title,
        original_title=None,
        year=2000,
        category_id="movies" if kind == "movie" else "tv_shows",
        overview=None,
        ids=ids,
        canonical_provider=None,
        poster_url=None,
        has_local_poster=False,
        date_created=1,
        date_provider_read=None,
    )


def _rec(provider_id: str, title: str, media_type: MediaType = MediaType.TV, provider: str = "trakt") -> Recommendation:
    """A recommendation as a provider answers it."""
    return Recommendation(provider=provider, provider_id=provider_id, title=title, year=2019, media_type=media_type)


@pytest.fixture(autouse=True)
def no_sql_on_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any ``sqlite3.connect`` on a ``library.db`` fail: the library is read through the index.

    PLAN P11c asks the refresh tested "with the library read through a fake index — no
    ``library.db`` opened by SQL". The fakes alone do not enforce that: code that opened the file
    itself, beside the fake index, would pass. This refuses the open.
    """
    real_connect = sqlite3.connect

    def guarded(database: object, *args: object, **kwargs: object) -> sqlite3.Connection:
        if "library.db" in str(database):
            raise AssertionError(f"the library was opened by SQL, not through the index: {database}")
        return real_connect(database, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(sqlite3, "connect", guarded)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """A real acquire store."""
    opened = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield opened
    finally:
        opened.close()


def _deck(store: ConcreteAcquireStore) -> list[SuggestionRow]:
    """The stored deck, whole."""
    return store.suggestions.after(None, 1000)


class TestSeeds:
    """The deck is built from the follows' and the library's ids."""

    def test_follows_seed_first_then_the_library_through_the_index(self, store: ConcreteAcquireStore) -> None:
        """The provider is asked by IMDb id (Trakt's), a film as a film and a show as a show."""
        store.follow.add(
            FollowedSeries(media_ref=MediaRef(tvdb_id=1, imdb_id="tt0000001"), title="Followed", added_at=1)
        )
        index = _FakeIndex(
            [
                _item("movie", "Held film", tmdb=2, imdb="tt0000002"),
                _item("show", "Held show", tvdb=3, imdb="tt0000003"),
            ]
        )
        provider = _Provider()

        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        assert provider.calls == [
            ("tt0000001", MediaType.TV),
            ("tt0000002", MediaType.MOVIE),
            ("tt0000003", MediaType.TV),
        ]
        assert index.opened == 1

    def test_a_title_followed_and_held_seeds_once_as_followed(self, store: ConcreteAcquireStore) -> None:
        """The same ids from both sources are one seed, and the follow names it."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(imdb_id="tt0000001"), title="Both", added_at=1))
        index = _FakeIndex([_item("show", "Both", imdb="tt0000001")])
        provider = _Provider(answers={"tt0000001": [_rec("sugg", "Suggested")]})

        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        assert len(provider.calls) == 1
        (row,) = _deck(store)
        assert (row.reason, row.seed_key) == ("similar_to_followed", "imdb:tt0000001")

    def test_a_seed_the_provider_cannot_be_asked_by_is_not_asked(self, store: ConcreteAcquireStore) -> None:
        """Trakt takes an IMDb id: a library row holding only a TMDB id is no seed for it, and costs no slot."""
        index = _FakeIndex([_item("show", "TMDB only", tmdb=5), _item("show", "Has IMDb", imdb="tt0000009")])
        provider = _Provider()

        report = refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=1)

        assert provider.calls == [("tt0000009", MediaType.TV)]
        assert report.remaining == 0

    def test_a_tmdb_provider_is_asked_by_the_tmdb_id(self, store: ConcreteAcquireStore) -> None:
        """Each provider is asked by the id it numbers titles with."""
        index = _FakeIndex([_item("movie", "Film", tmdb=603, imdb="tt0133093")])
        provider = _Provider("tmdb")

        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        assert provider.calls == [("603", MediaType.MOVIE)]

    def test_a_removed_or_paused_follow_is_no_seed(self, store: ConcreteAcquireStore) -> None:
        """Only standing, active follows seed."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(imdb_id="tt0000001"), title="Active", added_at=1))
        paused = store.follow.add(FollowedSeries(media_ref=MediaRef(imdb_id="tt0000002"), title="Paused", added_at=1))
        store.follow.set_active(paused, False)
        provider = _Provider()

        refresh_suggestions(store, _FakeIndex([]), [provider], now=_NOW, max_seeds=10)

        assert provider.calls == [("tt0000001", MediaType.TV)]

    def test_an_absent_index_leaves_the_follows_to_seed(self, store: ConcreteAcquireStore) -> None:
        """No ``library.db`` yet: the run seeds from the follows alone, it does not fail."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(imdb_id="tt0000001"), title="Active", added_at=1))
        provider = _Provider()

        refresh_suggestions(store, _FakeIndex(IndexUnavailable("absent")), [provider], now=_NOW, max_seeds=10)

        assert provider.calls == [("tt0000001", MediaType.TV)]


class TestDeck:
    """What a refresh stores."""

    def test_the_rows_carry_their_reason_and_seed(self, store: ConcreteAcquireStore) -> None:
        """A recommendation becomes a row: provider, id, kind, title, year, the reason code and the seed key."""
        index = _FakeIndex([_item("movie", "Held", tmdb=603, imdb="tt0133093")])
        provider = _Provider(answers={"tt0133093": [_rec("the-matrix-reloaded", "Reloaded", MediaType.MOVIE)]})

        report = refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        (row,) = _deck(store)
        assert (row.provider, row.provider_id, row.kind, row.title, row.year) == (
            "trakt",
            "the-matrix-reloaded",
            "movie",
            "Reloaded",
            2019,
        )
        assert (row.reason, row.seed_key, row.refreshed_at) == ("similar_to_owned", "tmdb:603", _NOW)
        assert (row.rating, row.poster) == (None, None)
        assert report.stored == 1 and report.asked == 1 and report.failed == 0

    def test_the_ids_a_provider_gives_beside_the_slug_are_stored(self, store: ConcreteAcquireStore) -> None:
        """A Trakt-shaped recommendation (slug as the id, imdb / tmdb / tvdb alongside) keeps them all."""
        index = _FakeIndex([_item("show", "Held", imdb="tt1")])
        recommendation = Recommendation(
            provider="trakt",
            provider_id="breaking-bad",
            title="Breaking Bad",
            year=2008,
            media_type=MediaType.TV,
            external_ids={"imdb": "tt0903747", "tmdb": "1396", "tvdb": "81189"},
        )
        provider = _Provider(answers={"tt1": [recommendation]})

        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        (row,) = _deck(store)
        assert (row.provider_id, row.external_ids) == (
            "breaking-bad",
            {"imdb": "tt0903747", "tmdb": "1396", "tvdb": "81189"},
        )

    def test_a_title_two_seeds_recommend_is_stored_once_for_the_first(self, store: ConcreteAcquireStore) -> None:
        """One row per (provider, id, kind); the first seed's reason stands."""
        index = _FakeIndex([_item("show", "A", imdb="tt1"), _item("show", "B", imdb="tt2")])
        provider = _Provider(answers={"tt1": [_rec("x", "X")], "tt2": [_rec("x", "X"), _rec("y", "Y")]})

        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        assert [(r.provider_id, r.seed_key) for r in _deck(store)] == [("x", "imdb:tt1"), ("y", "imdb:tt2")]

    def test_a_refresh_replaces_the_previous_deck(self, store: ConcreteAcquireStore) -> None:
        """The deck is the last refresh's, whole."""
        index = _FakeIndex([_item("show", "A", imdb="tt1")])
        provider = _Provider(answers={"tt1": [_rec("old", "Old")]})
        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)
        provider.answers = {"tt1": [_rec("new", "New")]}

        refresh_suggestions(store, index, [provider], now=_NOW + DEFAULT_MIN_INTERVAL_S + 1, max_seeds=10)

        assert [r.provider_id for r in _deck(store)] == ["new"]

    def test_a_recommendation_without_an_id_or_a_title_is_dropped(self, store: ConcreteAcquireStore) -> None:
        """A provider's half-empty row is no suggestion."""
        index = _FakeIndex([_item("show", "A", imdb="tt1")])
        provider = _Provider(answers={"tt1": [_rec("", "No id"), _rec("noname", ""), _rec("ok", "Fine")]})

        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        assert [r.provider_id for r in _deck(store)] == ["ok"]


class TestPoliteness:
    """The refresh costs the providers little, as the catalogue's does."""

    def test_max_bounds_the_seeds_asked_and_counts_the_rest(self, store: ConcreteAcquireStore) -> None:
        """At most ``max_seeds`` seeds are asked in one run; the report says how many wait."""
        index = _FakeIndex([_item("show", f"S{i}", imdb=f"tt{i}") for i in range(5)])
        provider = _Provider()

        report = refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=2)

        assert len(provider.calls) == 2
        assert report.asked == 2 and report.remaining == 3

    def test_the_seeds_left_over_are_the_next_runs_first(self, store: ConcreteAcquireStore) -> None:
        """With more seeds than ``max_seeds`` every seed is asked within a few runs, not the same head each time."""
        index = _FakeIndex([_item("show", f"S{i}", imdb=f"tt{i}") for i in (1, 2, 3)])
        provider = _Provider()

        first = refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=2, force=True)
        second = refresh_suggestions(store, index, [provider], now=_NOW + 10, max_seeds=2, force=True)
        third = refresh_suggestions(store, index, [provider], now=_NOW + 20, max_seeds=2, force=True)

        asked = [c[0] for c in provider.calls]
        assert asked[:2] == ["tt1", "tt2"]
        assert asked[2] == "tt3"  # the seed left over by the first run goes first in the second
        assert asked[4] == "tt2"  # and the one asked longest ago, in the third
        assert (first.remaining, second.remaining, third.remaining) == (1, 1, 1)

    def test_a_follow_goes_before_the_library_among_seeds_never_asked(self, store: ConcreteAcquireStore) -> None:
        """No run has asked anyone yet: the follows go first, the library after, as before."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(imdb_id="tt9"), title="Followed", added_at=1))
        index = _FakeIndex([_item("show", "Held", imdb="tt1")])
        provider = _Provider()

        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=1)

        assert [c[0] for c in provider.calls] == ["tt9"]

    def test_a_seed_that_failed_is_not_marked_asked_and_is_retried_first(self, store: ConcreteAcquireStore) -> None:
        """Only a seed a provider answered for moves to the back of the line."""
        index = _FakeIndex([_item("show", f"S{i}", imdb=f"tt{i}") for i in (1, 2, 3)])
        provider = _Provider(failing={"tt1"})
        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=2, force=True)
        provider.calls.clear()
        provider.failing = set()

        refresh_suggestions(store, index, [provider], now=_NOW + 10, max_seeds=2, force=True)

        assert [c[0] for c in provider.calls] == ["tt1", "tt3"]

    def test_a_weekly_cron_is_not_skipped_by_the_gate(self, store: ConcreteAcquireStore) -> None:
        """The cron fires a week apart, give or take the start-up time: a run a few seconds early still asks."""
        week = 7 * 86400
        index = _FakeIndex([_item("show", "A", imdb="tt1")])
        provider = _Provider(answers={"tt1": [_rec("x", "X")]})
        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)
        provider.calls.clear()

        report = refresh_suggestions(store, index, [provider], now=_NOW + week - 5, max_seeds=10)

        assert not report.fresh
        assert provider.calls == [("tt1", MediaType.TV)]

    def test_a_deck_refreshed_within_the_interval_asks_nobody(self, store: ConcreteAcquireStore) -> None:
        """A second run inside the period makes no provider call and leaves the deck as it is."""
        index = _FakeIndex([_item("show", "A", imdb="tt1")])
        provider = _Provider(answers={"tt1": [_rec("x", "X")]})
        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)
        provider.calls.clear()

        report = refresh_suggestions(store, index, [provider], now=_NOW + DEFAULT_MIN_INTERVAL_S - 1, max_seeds=10)

        assert provider.calls == []
        assert report.fresh and report.asked == 0
        assert [r.provider_id for r in _deck(store)] == ["x"]

    def test_the_interval_elapsed_or_forced_asks_again(self, store: ConcreteAcquireStore) -> None:
        """Past the period, or with ``force``, the providers are asked."""
        index = _FakeIndex([_item("show", "A", imdb="tt1")])
        provider = _Provider(answers={"tt1": [_rec("x", "X")]})
        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        refresh_suggestions(store, index, [provider], now=_NOW + DEFAULT_MIN_INTERVAL_S, max_seeds=10)
        refresh_suggestions(store, index, [provider], now=_NOW + DEFAULT_MIN_INTERVAL_S + 1, max_seeds=10, force=True)

        assert len(provider.calls) == 3


class TestFailures:
    """A provider that fails does not cost the deck."""

    def test_one_failing_seed_is_counted_and_the_run_goes_on(self, store: ConcreteAcquireStore) -> None:
        """The other seeds' recommendations are stored."""
        index = _FakeIndex([_item("show", "Bad", imdb="tt1"), _item("show", "Good", imdb="tt2")])
        provider = _Provider(answers={"tt2": [_rec("x", "X")]}, failing={"tt1"})

        report = refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)

        assert (report.asked, report.failed, report.stored) == (1, 1, 1)
        assert [r.provider_id for r in _deck(store)] == ["x"]

    def test_when_every_ask_fails_the_previous_deck_and_its_date_stand(self, store: ConcreteAcquireStore) -> None:
        """A provider outage does not empty the deck nor make it look fresh."""
        index = _FakeIndex([_item("show", "A", imdb="tt1")])
        provider = _Provider(answers={"tt1": [_rec("x", "X")]})
        refresh_suggestions(store, index, [provider], now=_NOW, max_seeds=10)
        provider.failing = {"tt1"}

        report = refresh_suggestions(store, index, [provider], now=_NOW + DEFAULT_MIN_INTERVAL_S + 1, max_seeds=10)

        assert (report.asked, report.failed) == (0, 1)
        assert [r.provider_id for r in _deck(store)] == ["x"]
        assert store.suggestions.refreshed_at() == _NOW

    def test_no_provider_configured_asks_nobody_and_keeps_the_deck(self, store: ConcreteAcquireStore) -> None:
        """No recommendation provider is an unconfigured option, not an error."""
        index = _FakeIndex([_item("show", "A", imdb="tt1")])

        report = refresh_suggestions(store, index, [], now=_NOW, max_seeds=10)

        assert (report.asked, report.failed, report.stored) == (0, 0, 0)


@pytest.fixture
def configured(tmp_path: Path, test_config) -> Path:
    """The test config pointed at tmp paths; returns the acquire db's path."""
    test_config.acquire.db_path = tmp_path / "acquire.db"
    test_config.indexer.db_path = tmp_path / "library.db"
    return tmp_path / "acquire.db"


def _invoke(
    provider: _Provider, index: _FakeIndex, *args: str, test_config, recorded: list[str] | None = None
) -> object:
    """Run the command with a registry serving ``provider`` and the fake ``index``.

    ``recorded`` collects the command name the run's ``pipeline_run`` row is written under.
    """
    registry = MagicMock()
    registry.providers_for.return_value = [provider]

    @contextmanager
    def fake_boundary(*_a, **_k):
        yield SimpleNamespace(provider_registry=registry)

    @contextmanager
    def fake_run_row(_config, name, *_a, **_k):
        if recorded is not None:
            recorded.append(name)
        yield MagicMock()

    with (
        patch(f"{_MODULE}.per_step_boundary", fake_boundary),
        patch(f"{_MODULE}.cli_run_row", fake_run_row),
        patch(f"{_MODULE}.LibraryIndex", return_value=index),
        patch("personalscraper.cli_helpers.get_settings"),
        patch("personalscraper.cli.load_config", return_value=test_config, create=True),
    ):
        return runner.invoke(app, ["acquisition-suggestions-refresh", *args])


class TestCommand:
    """The Typer command: help, report, politeness through the CLI."""

    def test_help_lists_max_and_force(self) -> None:
        """The command is registered, documents its two options, and its help comes through ``t()``."""
        result = runner.invoke(app, ["acquisition-suggestions-refresh", "--help"])
        assert result.exit_code == 0, result.output
        assert "--max" in result.output and "--force" in result.output
        assert "cli_acquisition." not in result.output  # a missing catalogue key would print as itself

    def test_a_run_stores_the_deck_and_prints_the_report(self, configured: Path, test_config) -> None:
        """The report is one JSON line; the deck is in ``acquire.db``."""
        provider = _Provider(answers={"tt1": [_rec("x", "X")]})
        index = _FakeIndex([_item("show", "A", imdb="tt1")])

        result = _invoke(provider, index, "--max", "7", test_config=test_config)

        assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
        line = next(ln for ln in result.output.splitlines() if ln.startswith("{"))  # type: ignore[attr-defined]
        assert json.loads(line) == {"asked": 1, "failed": 0, "stored": 1, "remaining": 0, "fresh": False}
        assert not test_config.indexer.db_path.exists()  # the library went through the index, never opened by SQL
        store = build_acquire_store(AcquireConfig(db_path=configured))
        try:
            assert [r.provider_id for r in _deck(store)] == ["x"]
        finally:
            store.close()

    def test_max_reaches_the_engine(self, configured: Path, test_config) -> None:
        """``--max 2`` over three seeds asks two and leaves one: the option is not ignored by the command."""
        provider = _Provider()
        index = _FakeIndex([_item("show", f"S{i}", imdb=f"tt{i}") for i in (1, 2, 3)])

        result = _invoke(provider, index, "--max", "2", test_config=test_config)

        assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
        line = next(ln for ln in result.output.splitlines() if ln.startswith("{"))  # type: ignore[attr-defined]
        summary = json.loads(line)
        assert (summary["asked"], summary["remaining"]) == (2, 1)
        assert len(provider.calls) == 2

    def test_the_scheduler_entry_its_registry_row_and_the_recorded_command_agree(
        self, configured: Path, test_config
    ) -> None:
        """The PM2 app runs the command whose run row the schedulers route matches by prefix, at the cron it shows.

        Three strings name one cron: the app's argv, the registry row's ``command_prefix`` and the
        ``schedule`` label, and the command the run records. A change to one alone would leave the
        route's ``last_run_at`` at ``None`` for ever, or show a time the cron does not fire at.
        """
        recorded: list[str] = []
        _invoke(_Provider(), _FakeIndex([]), test_config=test_config, recorded=recorded)
        (command,) = recorded
        app_entry = _get_app_by_name(_parse_ecosystem_apps(_ECOSYSTEM_PATH), "personalscraper-suggestions-refresh")
        cron, job_argv = _job_schedule(app_entry)
        row = next(job for job in CRON_JOBS if job.name == app_entry["name"])
        minute, hour, _, _, weekday = cron.split()

        assert job_argv == [command]  # the app runs the command that records the run
        assert command.startswith(row.command_prefix)  # the route finds the run by this prefix
        assert (weekday, f"{int(hour):02d}:{int(minute):02d}") == ("0", "05:30")
        assert "05:30" in row.schedule and "dimanche" in row.schedule  # french-ok: the label the route serves

    def test_a_second_run_inside_the_period_is_fresh(self, configured: Path, test_config) -> None:
        """The politeness gate holds through the CLI; ``--force`` lifts it."""
        provider = _Provider(answers={"tt1": [_rec("x", "X")]})
        index = _FakeIndex([_item("show", "A", imdb="tt1")])
        _invoke(provider, index, test_config=test_config)
        provider.calls.clear()

        again = _invoke(provider, index, test_config=test_config)
        forced = _invoke(provider, index, "--force", test_config=test_config)

        assert '"fresh": true' in again.output  # type: ignore[attr-defined]
        assert provider.calls == [("tt1", MediaType.TV)]
        assert forced.exit_code == 0  # type: ignore[attr-defined]

    def test_unconfigured_databases_exit_one(self, test_config) -> None:
        """No ``acquire.db_path`` / ``indexer.db_path``: a message and exit 1, as the catalogue's."""
        test_config.acquire.db_path = None
        result = _invoke(_Provider(), _FakeIndex([]), test_config=test_config)
        assert result.exit_code == 1  # type: ignore[attr-defined]
