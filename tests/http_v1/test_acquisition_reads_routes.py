"""The acquisition's reads on v1: the release picker, the provider search, the deck and the ranking preview.

Each route makes one service call and maps its facts to the contract's bodies; these tests hold the wire:
the bodies' shapes, the statuses and ``Problem`` codes the contract declares, the rights each operation asks
and the own-scoping of the follows' reads. The services' own rules are proved in
``tests/unit/app/acquisition``; here the provider clients are fakes (no network), and the stores are real, on
the synthetic configuration's temporary ``acquire.db``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import nullcontext
from datetime import date

import pytest
from fastapi.testclient import TestClient

from personalscraper.acquire.domain import (
    FollowedSeries,
    FollowRequester,
    SuggestionRow,
    WantedCandidate,
    WantedItem,
)
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.metadata._base import SearchResult
from personalscraper.app import composition
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition import search as search_module
from personalscraper.conf.models.config import Config
from personalscraper.core import ApiError
from personalscraper.core.identity import MediaRef
from tests.http_v1.test_deprecations import _client as v0_client

_PILOT = frozenset({Right.ACQUISITION_PILOT_OWN})
_PILOT_ALL = frozenset({Right.ACQUISITION_PILOT_OWN, Right.ACQUISITION_SEE_OTHERS})
_REQUEST = frozenset({Right.ACQUISITION_REQUEST})
_CONFIGURE = frozenset({Right.CONFIGURATION_WRITE})
_LIBRARY = frozenset({Right.LIBRARY_READ})


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts on a production instance: no ceiling from the environment.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "prod")


@pytest.fixture
def acquire(test_config: Config) -> Iterator[ConcreteAcquireStore]:
    """Open the ``acquire.db`` the services read, to seed it.

    Args:
        test_config: The synthetic configuration.

    Yields:
        The store.
    """
    store = build_acquire_store(test_config.acquire)
    try:
        yield store
    finally:
        store.close()


def _candidate(rank: int, title: str, *, season: int | None = None, episode: int | None = None) -> WantedCandidate:
    """Build one ranked candidate.

    Args:
        rank: Its rank.
        title: Its release title.
        season: The season it numbers.
        episode: The episode it numbers.

    Returns:
        The candidate.
    """
    return WantedCandidate(
        rank=rank,
        provider="c411",
        title=title,
        info_hash=f"hash{rank}",
        size_bytes=1_500_000_000 * rank,
        seeders=50 - rank,
        resolution="1080p" if rank == 1 else None,
        source="WEB" if rank == 1 else None,
        language="MULTI" if rank == 1 else None,
        score=100 - rank,
        season=season,
        episode=episode,
        searched_at=400,
    )


def _seed_episode_candidates(
    store: ConcreteAcquireStore, ref: MediaRef, *, title: str = "Silo", asked_by: str | None = None
) -> int:
    """Store a follow with one open episode row and two candidates for it.

    Args:
        store: The store.
        ref: The followed medium.
        title: The follow's title.
        asked_by: The account whose ask it is, or ``None`` for a follow with no requester (the owner's).

    Returns:
        The wanted row's id.
    """
    follow = store.follow.add(FollowedSeries(media_ref=ref, title=title, added_at=100))
    if asked_by is not None:
        store.requesters.upsert(
            FollowRequester(followed_id=follow, account_id=asked_by, via="follow", floor=None, paused=False, since=200)
        )
    wanted = store.wanted.add(
        WantedItem(
            media_ref=ref, kind="episode", status="available", enqueued_at=300, followed_id=follow, season=2, episode=5
        )
    )
    store.candidates.replace(
        wanted,
        [
            _candidate(1, "Silo.S02E05.1080p", season=2, episode=5),
            _candidate(2, "Silo.S02E05.720p", season=2, episode=5),
        ],
    )
    return wanted


class TestReadReleases:
    """``GET /acquisition/releases``."""

    def test_an_item_is_read_by_its_key_season_and_episode(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """The candidates come best first, each with its handle, its sizes in gigabytes, and its numbering."""
        wanted = _seed_episode_candidates(acquire, MediaRef(tvdb_id=81189), asked_by="account-1")

        response = v1_client(rights=_PILOT).get(
            "/acquisition/releases", params={"followedId": "tvdb:81189", "season": 2, "episode": 5}
        )

        assert response.status_code == 200
        first, second = response.json()
        assert first["id"].startswith(f"{wanted}:")
        assert {key: first[key] for key in first if key != "id"} == {
            "name": "Silo.S02E05.1080p",
            "resolution": "1080p",
            "source": "WEB",
            "language": "MULTI",
            "seeders": 49,
            "sizeGigabytes": 1.5,
            "score": 99,
            "season": 2,
            "episode": 5,
        }
        assert (second["name"], second["resolution"], second["source"], second["language"]) == (
            "Silo.S02E05.720p",
            "",
            "",
            "",
        )
        assert first["id"] != second["id"]

    def test_a_whole_season_and_a_film_carry_a_null_episode_and_season(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """A film numbers no season and no episode: both are ``null`` on the wire, never absent."""
        follow = acquire.follow.add(FollowedSeries(media_ref=MediaRef(tmdb_id=603), title="Matrix", added_at=1))
        acquire.requesters.upsert(
            FollowRequester(followed_id=follow, account_id="account-1", via="follow", floor=None, paused=False, since=2)
        )
        wanted = acquire.wanted.add(
            WantedItem(
                media_ref=MediaRef(tmdb_id=603), kind="movie", status="available", enqueued_at=3, followed_id=follow
            )
        )
        acquire.candidates.replace(wanted, [_candidate(1, "The.Matrix.1999.1080p")])

        (release,) = v1_client(rights=_PILOT).get("/acquisition/releases", params={"followedId": "tmdb:603"}).json()

        assert (release["season"], release["episode"]) == (None, None)

    def test_without_a_key_every_item_the_reader_may_see_is_offered(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """No ``followedId``: what the quality profile counts against."""
        _seed_episode_candidates(acquire, MediaRef(tvdb_id=81189), asked_by="account-1")
        _seed_episode_candidates(acquire, MediaRef(tvdb_id=70000), title="Other", asked_by="account-1")

        body = v1_client(rights=_PILOT).get("/acquisition/releases").json()

        assert [release["name"] for release in body] == ["Silo.S02E05.1080p", "Silo.S02E05.720p"] * 2

    def test_a_follow_the_reader_did_not_ask_for_answers_an_empty_list(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """Own-scoped: someone else's follow is filtered out on a 200, never refused."""
        _seed_episode_candidates(acquire, MediaRef(tvdb_id=81189))

        response = v1_client(rights=_PILOT).get(
            "/acquisition/releases", params={"followedId": "tvdb:81189", "season": 2, "episode": 5}
        )

        assert (response.status_code, response.json()) == (200, [])

    def test_see_others_reads_a_follow_the_reader_did_not_ask_for(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """``acquisition.see.others`` lifts the filter."""
        _seed_episode_candidates(acquire, MediaRef(tvdb_id=81189))

        response = v1_client(rights=_PILOT_ALL).get(
            "/acquisition/releases", params={"followedId": "tvdb:81189", "season": 2, "episode": 5}
        )

        assert len(response.json()) == 2

    def test_a_key_no_follow_holds_answers_an_empty_list(self, v1_client: Callable[..., TestClient]) -> None:
        """An unknown medium has no releases."""
        response = v1_client(rights=_PILOT).get("/acquisition/releases", params={"followedId": "tvdb:1"})

        assert (response.status_code, response.json()) == (200, [])

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"followedId": "81189"}, "followedId"),
            ({"followedId": "title:Silo"}, "followedId"),
            ({"followedId": "tvdb:81189", "episode": 5}, "episode"),
            ({"followedId": "tvdb:81189", "season": 0}, "season"),
            ({"followedId": "tvdb:81189", "season": 1, "episode": -1}, "episode"),
        ],
    )
    def test_a_malformed_question_is_request_invalid_naming_its_field(
        self, v1_client: Callable[..., TestClient], params: dict[str, object], field: str
    ) -> None:
        """A key that is not a key, an episode with no season, a season below 1: 400 naming the field."""
        response = v1_client(rights=_PILOT).get("/acquisition/releases", params=params)

        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert any(named.endswith(field) for named in response.json()["params"]["fields"])

    def test_the_door_asks_a_pilot_right_and_a_session(self, v1_client: Callable[..., TestClient]) -> None:
        """No session: 401; a right other than pilot own or any: 403 naming both."""
        assert v1_client(role=None).get("/acquisition/releases").status_code == 401
        refused = v1_client(rights=_LIBRARY).get("/acquisition/releases")

        assert refused.status_code == 403
        assert refused.json()["code"] == "right.missing"
        assert refused.json()["params"]["rights"] == ["acquisition.pilot.any", "acquisition.pilot.own"]


class _Tmdb:
    """A TMDB fake: one search page, and details by id."""

    def __init__(
        self,
        movies: list[SearchResult] | None = None,
        shows: list[SearchResult] | None = None,
        *,
        fail: Exception | None = None,
    ) -> None:
        self.movies = movies or []
        self.shows = shows or []
        self.fail = fail
        self.asked: list[tuple[str, object]] = []

    def search_movie(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        self.asked.append(("search_movie", query))
        if self.fail is not None:
            raise self.fail
        return self.movies

    def search_tv(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        self.asked.append(("search_tv", query))
        return self.shows

    def get_movie(self, provider_id: int) -> object:
        self.asked.append(("get_movie", provider_id))
        if self.fail is not None:
            raise self.fail
        if provider_id != 603:
            raise ApiError(provider="tmdb", http_status=404, message="not found")
        return _Details("The Matrix")

    def get_tv(self, provider_id: int) -> object:
        self.asked.append(("get_tv", provider_id))
        raise ApiError(provider="tmdb", http_status=404, message="not found")

    def find_ids_by_imdb(self, imdb_id: str) -> dict[str, int]:
        self.asked.append(("find_ids_by_imdb", imdb_id))
        return {"movie": 603} if imdb_id == "tt0133093" else {}


class _Tvdb:
    """A TVDB fake that finds nothing."""

    def search_series(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        return []


class _Details:
    """A provider's details of one medium."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.year = 1999
        self.overview = "Neo."
        self.images: list[object] = []


@pytest.fixture
def tmdb(monkeypatch: pytest.MonkeyPatch) -> _Tmdb:
    """Serve the search from fake clients, a fresh result cache each test.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.

    Returns:
        The TMDB fake, to configure and to read the calls off.
    """
    fake = _Tmdb(
        movies=[
            SearchResult(
                provider="tmdb",
                provider_id="603",
                title="The Matrix",
                year=1999,
                media_type="movie",
                popularity=50.0,
                poster_url="https://img/matrix.jpg",
                overview="Neo.",
            )
        ],
        shows=[
            SearchResult(
                provider="tmdb", provider_id="95396", title="Severance", year=2022, media_type="tv", popularity=40.0
            )
        ],
    )
    monkeypatch.setattr(search_module, "scoped_provider_clients", lambda config, settings: nullcontext((fake, _Tvdb())))
    search_module.SEARCH_CACHE.clear()
    yield fake
    search_module.SEARCH_CACHE.clear()


def _films(count: int) -> list[SearchResult]:
    """Films a search for « dune » finds, the most popular first.

    Args:
        count: How many.

    Returns:
        The films, titled ``Dune 0`` … ``Dune <count - 1>``.
    """
    return [
        SearchResult(
            provider="tmdb",
            provider_id=str(1000 + n),
            title=f"Dune {n}",
            year=2000 + n,
            media_type="movie",
            popularity=100.0 - n,
        )
        for n in range(count)
    ]


class TestSearchProviders:
    """``GET /acquisition/search``."""

    def test_a_search_answers_the_page_and_its_total(self, v1_client: Callable[..., TestClient], tmdb: _Tmdb) -> None:
        """Each result carries the contract's fields: ``show`` for a television title, its ids, owned and followed."""
        response = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "matrix"})

        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["shown"]) == (2, 2)
        assert body["results"][0] == {
            "title": "The Matrix",
            "year": 1999,
            "kind": "movie",
            "overview": "Neo.",
            "owned": False,
            "followed": False,
            "ids": {"tmdb": 603},
            "poster": "https://img/matrix.jpg",
        }
        assert [(r["kind"], r["ids"]) for r in body["results"]] == [("movie", {"tmdb": 603}), ("show", {"tmdb": 95396})]
        assert body["results"][1]["poster"] is None
        assert body["results"][1]["overview"] == ""

    def test_a_followed_title_is_flagged(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb, acquire: ConcreteAcquireStore
    ) -> None:
        """The follow store is read, by id, and flags the result it holds."""
        acquire.follow.add(FollowedSeries(media_ref=MediaRef(tmdb_id=603), title="Matrix", added_at=1, kind="movie"))

        results = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "matrix"}).json()["results"]

        assert {r["title"]: r["followed"] for r in results} == {"The Matrix": True, "Severance": False}

    def test_a_page_holds_twenty_results_and_the_total_says_how_many_there_are(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """The contract declares no offset or limit: the first twenty are served, ``total`` names the rest."""
        tmdb.movies = [
            SearchResult(
                provider="tmdb",
                provider_id=str(1000 + n),
                title=f"Dune {n}",
                year=2000 + n,
                media_type="movie",
                popularity=100.0 - n,
            )
            for n in range(25)
        ]
        tmdb.shows = []

        body = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "dune"}).json()

        assert (body["shown"], body["total"], len(body["results"])) == (20, 25, 20)

    def test_the_second_page_of_a_search_is_reached_by_offset(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """K3-G14: ``offset`` reaches what the first page left, under the same total."""
        tmdb.movies = _films(25)
        tmdb.shows = []
        client = v1_client(rights=_REQUEST)

        first = client.get("/acquisition/search", params={"query": "dune"}).json()
        second = client.get("/acquisition/search", params={"query": "dune", "offset": 20}).json()

        assert (second["shown"], second["total"], len(second["results"])) == (5, 25, 5)
        assert not {r["title"] for r in first["results"]} & {r["title"] for r in second["results"]}

    def test_a_limit_bounds_the_page(self, v1_client: Callable[..., TestClient], tmdb: _Tmdb) -> None:
        """K3-G14: ``limit`` sets how many results the page carries, from the offset on."""
        tmdb.movies = _films(25)
        tmdb.shows = []
        client = v1_client(rights=_REQUEST)

        whole = client.get("/acquisition/search", params={"query": "dune", "limit": 100}).json()
        page = client.get("/acquisition/search", params={"query": "dune", "limit": 3, "offset": 3}).json()

        assert (whole["shown"], whole["total"]) == (25, 25)
        assert (page["shown"], page["results"]) == (3, whole["results"][3:6])

    @pytest.mark.parametrize(("name", "value"), [("limit", 0), ("limit", 101), ("offset", -1)])
    def test_a_page_out_of_bounds_is_request_invalid_naming_it(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb, name: str, value: int
    ) -> None:
        """K3-G14: a page the contract's bounds refuse is 400 ``request.invalid``, and no provider is asked."""
        response = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "dune", name: value})

        assert (response.status_code, response.json()["code"]) == (400, "request.invalid")
        assert response.json()["params"]["fields"] == [f"query.{name}"]
        assert tmdb.asked == []

    def test_a_follow_store_that_cannot_be_read_fails_the_search_never_says_not_followed(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``followed=false`` on a followed title is a false fact: the answer is the 500 problem, no results."""

        def locked(self: object, lookups: object) -> list[list[FollowedSeries]]:
            raise RuntimeError("acquire.db is locked")

        monkeypatch.setattr(composition._PerCallFollowLookup, "find_all_by_refs", locked)

        response = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "matrix"})

        assert response.status_code == 500
        assert response.json()["code"] == "internal"
        assert "results" not in response.json()

    def test_a_kind_restricts_the_search(self, v1_client: Callable[..., TestClient], tmdb: _Tmdb) -> None:
        """``show`` asks the television chain only; ``movie`` the film chain only."""
        shows = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "x", "kind": "show"}).json()

        assert [r["kind"] for r in shows["results"]] == ["show"]
        assert ("search_movie", "x") not in tmdb.asked

    def test_a_kind_that_is_neither_is_request_invalid_naming_it(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """Only films and shows can be asked for."""
        response = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "x", "kind": "tv"})

        assert response.status_code == 400
        assert response.json()["params"] == {"fields": ["kind"]}
        assert tmdb.asked == []

    @pytest.mark.parametrize("params", [{}, {"query": ""}, {"query": "   "}])
    def test_nothing_typed_is_no_result_and_asks_no_provider(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb, params: dict[str, str]
    ) -> None:
        """The add screen asks on opening, before a letter: an empty page on a 200, nothing asked."""
        response = v1_client(rights=_REQUEST).get("/acquisition/search", params=params)

        assert (response.status_code, response.json()) == (200, {"total": 0, "shown": 0, "results": []})
        assert tmdb.asked == []

    def test_a_provider_that_cannot_answer_is_unavailable_not_an_empty_page(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """The film chain failing: 503 ``provider.unavailable`` naming it."""
        tmdb.fail = ApiError(provider="tmdb", http_status=503, message="down")

        response = v1_client(rights=_REQUEST).get("/acquisition/search", params={"query": "matrix"})

        assert response.status_code == 503
        assert response.json()["code"] == "provider.unavailable"
        assert response.json()["params"] == {"provider": "tmdb"}

    def test_the_door_asks_a_session_and_the_request_right(self, v1_client: Callable[..., TestClient]) -> None:
        """No session: 401; without ``acquisition.request``: 403."""
        assert v1_client(role=None).get("/acquisition/search", params={"query": "x"}).status_code == 401
        refused = v1_client(rights=_LIBRARY).get("/acquisition/search", params={"query": "x"})

        assert refused.status_code == 403
        assert refused.json()["params"] == {"rights": ["acquisition.request"]}


class TestSearchProviderById:
    """``GET /acquisition/search/by-id``."""

    def test_an_identifier_a_source_knows_answers_that_medium(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """One result, its ids the key its sheet is addressed by."""
        response = v1_client(rights=_REQUEST).get("/acquisition/search/by-id", params={"provider": "tmdb", "id": "603"})

        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["shown"]) == (1, 1)
        assert (body["results"][0]["title"], body["results"][0]["kind"], body["results"][0]["ids"]) == (
            "The Matrix",
            "movie",
            {"tmdb": 603},
        )

    def test_an_identifier_no_source_knows_answers_no_result(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """« Or no result »: a 200 with an empty page, never a 404 the contract does not declare."""
        response = v1_client(rights=_REQUEST).get("/acquisition/search/by-id", params={"provider": "tmdb", "id": "999"})

        assert (response.status_code, response.json()) == (200, {"total": 0, "shown": 0, "results": []})

    def test_an_imdb_identifier_is_resolved_at_tmdb_not_handed_to_it(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """TMDB is asked what the IMDb id numbers, then for that TMDB id: never ``get_movie('tt…')``."""
        body = (
            v1_client(rights=_REQUEST)
            .get("/acquisition/search/by-id", params={"provider": "imdb", "id": "tt0133093"})
            .json()
        )

        assert [r["title"] for r in body["results"]] == ["The Matrix"]
        assert tmdb.asked[0] == ("find_ids_by_imdb", "tt0133093")
        assert ("get_movie", "tt0133093") not in tmdb.asked

    def test_a_provider_failure_is_unavailable_not_no_result(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb
    ) -> None:
        """A source that cannot answer is not a source that does not know."""
        tmdb.fail = ApiError(provider="tmdb", http_status=500, message="boom")

        response = v1_client(rights=_REQUEST).get("/acquisition/search/by-id", params={"provider": "tmdb", "id": "603"})

        assert response.status_code == 503
        assert response.json()["code"] == "provider.unavailable"

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"provider": "tmdb", "id": "tt0133093"}, "id"),
            ({"provider": "imdb", "id": "603"}, "id"),
            ({"provider": "tvdb", "id": "abc"}, "id"),
            ({"provider": "trakt", "id": "603"}, "provider"),
        ],
    )
    def test_an_identifier_out_of_its_sources_format_is_request_invalid(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb, params: dict[str, str], field: str
    ) -> None:
        """Digits for TMDB and TVDB, « tt » and digits for IMDb; a source the contract does not list: 400."""
        response = v1_client(rights=_REQUEST).get("/acquisition/search/by-id", params=params)

        assert response.status_code == 400
        assert any(named.endswith(field) for named in response.json()["params"]["fields"])
        assert tmdb.asked == []

    def test_the_door_asks_a_session_and_the_request_right(self, v1_client: Callable[..., TestClient]) -> None:
        """No session: 401; without ``acquisition.request``: 403 naming it."""
        params = {"provider": "tmdb", "id": "603"}
        assert v1_client(role=None).get("/acquisition/search/by-id", params=params).status_code == 401
        refused = v1_client(rights=_LIBRARY).get("/acquisition/search/by-id", params=params)

        assert refused.status_code == 403
        assert refused.json()["code"] == "right.missing"
        assert refused.json()["params"] == {"rights": ["acquisition.request"]}

    def test_a_follow_store_that_cannot_be_read_fails_the_lookup(
        self, v1_client: Callable[..., TestClient], tmdb: _Tmdb, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same pass flags a lookup: a locked store is a 500 problem, never ``followed=false``."""

        def locked(self: object, lookups: object) -> list[list[FollowedSeries]]:
            raise RuntimeError("acquire.db is locked")

        monkeypatch.setattr(composition._PerCallFollowLookup, "find_all_by_refs", locked)

        response = v1_client(rights=_REQUEST).get("/acquisition/search/by-id", params={"provider": "tmdb", "id": "603"})

        assert (response.status_code, response.json()["code"]) == (500, "internal")

    def test_the_question_needs_its_two_parameters(self, v1_client: Callable[..., TestClient]) -> None:
        """Neither the source nor the identifier may be left out."""
        client = v1_client(rights=_REQUEST)

        assert client.get("/acquisition/search/by-id", params={"provider": "tmdb"}).status_code == 400
        assert client.get("/acquisition/search/by-id", params={"id": "603"}).status_code == 400


def _deck(store: ConcreteAcquireStore, count: int) -> None:
    """Fill the deck with ``count`` titles, ``Title 1`` … , each a TMDB show.

    Args:
        store: The store.
        count: How many.
    """
    store.suggestions.replace_deck(
        [
            SuggestionRow(
                provider="tmdb",
                provider_id=str(n),
                kind="show" if n % 2 else "movie",
                title=f"Title {n}",
                year=2020 + n if n != 2 else None,
                rating=7.5 if n != 3 else None,
                poster="https://img/p.jpg" if n == 1 else None,
                reason="similar_to_owned",
                seed_key="tmdb:603",
                refreshed_at=1_800_000_000,
            )
            for n in range(1, count + 1)
        ]
    )


class TestReadSuggestions:
    """``GET /acquisition/suggestions``."""

    def test_a_card_carries_the_contracts_fields(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """A show of the deck: its year as text, the reason's code as ``why``, its ids, no full-screen poster."""
        _deck(acquire, 3)

        cards = v1_client(rights=_REQUEST).get("/acquisition/suggestions").json()

        assert cards[0] == {
            "title": "Title 1",
            "year": "2021",
            "kind": "show",
            "rating": 7.5,
            "why": ["similar_to_owned"],
            "ids": {"tmdb": 1},
            "poster": "https://img/p.jpg",
            "posterHighDefinition": None,
        }

    def test_what_the_deck_lacks_is_an_empty_text_and_a_zero_never_a_null(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """The contract types ``year`` as text and ``rating`` as a number: an unknown year is ``""``, a rating ``0``."""
        _deck(acquire, 3)

        cards = v1_client(rights=_REQUEST).get("/acquisition/suggestions").json()

        assert (cards[1]["year"], cards[2]["rating"]) == ("", 0)

    def test_the_deck_continues_past_the_last_title_the_reader_holds(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """``after`` is the title of the last card (the interface's own way); an exhausted deck is an empty list."""
        _deck(acquire, 25)
        client = v1_client(rights=_REQUEST)

        first = client.get("/acquisition/suggestions").json()
        second = client.get("/acquisition/suggestions", params={"after": first[-1]["title"]}).json()
        third = client.get("/acquisition/suggestions", params={"after": second[-1]["title"]}).json()

        assert [c["title"] for c in first] == [f"Title {n}" for n in range(1, 21)]
        assert [c["title"] for c in second] == [f"Title {n}" for n in range(21, 26)]
        assert third == []

    def test_after_a_title_two_cards_bear_restarts_past_the_first_of_them(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """A LIMIT OF THE CONTRACT, pinned: ``after`` is a title, and a title is not unique in the deck.

        A film and a show can bear one title. The page continues past the FIRST card of that title, so a
        reader whose last card is the second one is served the cards between the two again.
        """
        titles = ["Dune", "Arrival", "Dune", "Tenet"]
        acquire.suggestions.replace_deck(
            [
                SuggestionRow(
                    provider="tmdb",
                    provider_id=str(n),
                    kind="movie" if n % 2 else "show",
                    title=title,
                    year=2021,
                    rating=7.0,
                    poster=None,
                    reason="similar_to_owned",
                    seed_key="tmdb:603",
                    refreshed_at=1_800_000_000,
                )
                for n, title in enumerate(titles, start=1)
            ]
        )

        served = v1_client(rights=_REQUEST).get("/acquisition/suggestions", params={"after": "Dune"}).json()

        assert [(c["title"], c["kind"]) for c in served] == [("Arrival", "show"), ("Dune", "movie"), ("Tenet", "show")]

    def test_the_next_cursor_continues_the_deck_to_its_end(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """K3-G13: each page carries the ``nextCursor`` the next one is asked with; the last carries ``null``."""
        _deck(acquire, 25)
        client = v1_client(rights=_REQUEST)

        first = client.get("/acquisition/suggestions").json()
        second = client.get("/acquisition/suggestions", params={"cursor": first["nextCursor"]}).json()

        assert [c["title"] for c in first["suggestions"]] == [f"Title {n}" for n in range(1, 21)]
        assert [c["title"] for c in second["suggestions"]] == [f"Title {n}" for n in range(21, 26)]
        assert second["nextCursor"] is None

    def test_two_cards_bearing_one_title_do_not_restart_the_deck(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """K3-G13: a page ending on the second card of a title continues past THAT card, not the first."""
        titles = [f"Title {n}" for n in range(1, 23)]
        titles[4] = titles[19] = "Dune"
        acquire.suggestions.replace_deck(
            [
                SuggestionRow(
                    provider="tmdb",
                    provider_id=str(n),
                    kind="movie" if n % 2 else "show",
                    title=title,
                    year=2021,
                    rating=7.0,
                    poster=None,
                    reason="similar_to_owned",
                    seed_key="tmdb:603",
                    refreshed_at=1_800_000_000,
                )
                for n, title in enumerate(titles, start=1)
            ]
        )
        client = v1_client(rights=_REQUEST)

        first = client.get("/acquisition/suggestions").json()
        second = client.get("/acquisition/suggestions", params={"cursor": first["nextCursor"]}).json()

        assert first["suggestions"][-1]["title"] == "Dune"
        assert [c["title"] for c in second["suggestions"]] == ["Title 21", "Title 22"]

    @pytest.mark.parametrize("cursor", ["Dune", "-1", "1.5"])
    def test_a_cursor_the_deck_never_gave_is_request_invalid_naming_it(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore, cursor: str
    ) -> None:
        """K3-G13: a cursor is the server's own; anything else is refused, never guessed."""
        _deck(acquire, 3)

        response = v1_client(rights=_REQUEST).get("/acquisition/suggestions", params={"cursor": cursor})

        assert (response.status_code, response.json()["code"]) == (400, "request.invalid")
        assert response.json()["params"]["fields"] == ["cursor"]

    def test_a_followed_title_is_left_out(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """The deck is minus what the reader already follows."""
        _deck(acquire, 3)
        acquire.follow.add(FollowedSeries(media_ref=MediaRef(tmdb_id=1), title="Title 1", added_at=1, kind="show"))

        titles = [c["title"] for c in v1_client(rights=_REQUEST).get("/acquisition/suggestions").json()]

        assert titles == ["Title 2", "Title 3"]

    def test_the_door_asks_a_session_and_the_request_right(self, v1_client: Callable[..., TestClient]) -> None:
        """No session: 401; without ``acquisition.request``: 403."""
        assert v1_client(role=None).get("/acquisition/suggestions").status_code == 401
        assert v1_client(rights=_LIBRARY).get("/acquisition/suggestions").status_code == 403


def _ranking(**overrides: object) -> dict[str, object]:
    """Build a ranking body the way the interface asks for a preview.

    Args:
        **overrides: Keys to replace.

    Returns:
        The body.
    """
    body: dict[str, object] = {
        "criteria": [
            {"field": "resolution", "weight": 3, "values": {"2160p": 20, "1080p": 10}},
            {"field": "seeders", "weight": 1, "thresholds": [{"at": 10, "score": 5}], "prefer": "higher"},
        ],
        "minSeeders": 10,
        "bonuses": {"freeleech": 10, "silverleech": 5},
    }
    body.update(overrides)
    return body


class TestPreviewRanking:
    """``POST /acquisition/ranking/preview``."""

    def test_every_sample_is_scored_and_the_ones_under_the_floor_sink_last(
        self, v1_client: Callable[..., TestClient], test_config: Config
    ) -> None:
        """Twelve samples, none dropped; an excluded one is flagged and after every kept one."""
        response = v1_client(rights=_CONFIGURE).post("/acquisition/ranking/preview", json=_ranking())

        assert response.status_code == 200
        body = response.json()
        assert len(body["ranked"]) == 12
        flags = [row["excluded"] for row in body["ranked"]]
        assert flags == sorted(flags)
        assert any(flags)
        assert body["knownTrackers"] == sorted(test_config.tracker.providers)
        assert {row["trackerRatioState"] for row in body["ranked"]} == {None}

    def test_a_criterion_naming_the_ratio_state_scores_the_standing_of_the_trackers_economy(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``trackerRatioState`` is ``tracker_ratio_state`` in the engine; the standing is the resolver's."""
        monkeypatch.setattr(
            composition,
            "ratio_standing_of",
            lambda open_store, economies: lambda tracker: "under_floor" if tracker == "tr4ker" else None,
        )
        ranking = _ranking(
            criteria=[{"field": "trackerRatioState", "weight": 1, "values": {"under_floor": -1000}}], minSeeders=0
        )

        rows = v1_client(rights=_CONFIGURE).post("/acquisition/ranking/preview", json=ranking).json()["ranked"]

        by_tracker = {row["provider"]: (row["trackerRatioState"], row["score"]) for row in rows if not row["freeleech"]}
        assert by_tracker["tr4ker"] == ("under_floor", -1000)
        assert by_tracker["c411"] == (None, 0)

    def test_a_size_criterion_by_its_contract_name_scores_the_size(self, v1_client: Callable[..., TestClient]) -> None:
        """``sizeBytes`` on the wire is the engine's ``size``."""
        ranking = _ranking(
            criteria=[
                {
                    "field": "sizeBytes",
                    "weight": 1,
                    "thresholds": [{"at": 50_000_000_000, "score": 7}],
                    "prefer": "higher",
                }
            ],
            minSeeders=0,
        )

        rows = v1_client(rights=_CONFIGURE).post("/acquisition/ranking/preview", json=ranking).json()["ranked"]

        scored = {row["title"]: row["score"] for row in rows}
        assert scored["Demo.2025.TRUEFRENCH.2160p.REMUX.BluRay.x265 — tr4ker"] == 7  # 52 GB
        assert scored["Sample.2024.VFF.1080p.WEB-DL.x264 — c411"] == 0  # 4 GB

    def test_a_malformed_ranking_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """A body missing a required property, or carrying an unknown one: 400."""
        client = v1_client(rights=_CONFIGURE)

        assert client.post("/acquisition/ranking/preview", json={"criteria": []}).status_code == 400
        assert client.post("/acquisition/ranking/preview", json=_ranking(unknown=1)).status_code == 400

    def test_the_door_asks_a_session_and_the_configuration_right(self, v1_client: Callable[..., TestClient]) -> None:
        """No session: 401; ``acquisition.request`` alone does not configure: 403."""
        assert v1_client(role=None).post("/acquisition/ranking/preview", json=_ranking()).status_code == 401
        refused = v1_client(rights=_REQUEST).post("/acquisition/ranking/preview", json=_ranking())

        assert refused.status_code == 403
        assert refused.json()["params"] == {"rights": ["configuration.write"]}


class TestV0Twins:
    """The v0 routes the three operations replace tell their callers (RFC 9745)."""

    @pytest.mark.parametrize(
        ("method", "v0_path", "successor"),
        [
            ("get", "/api/acquisition/search", "/api/v1/acquisition/search"),
            ("get", "/api/acquisition/lookup", "/api/v1/acquisition/search/by-id"),
            ("post", "/api/acquisition/ranking/preview", "/api/v1/acquisition/ranking/preview"),
        ],
    )
    def test_a_twinned_v0_route_names_its_v1_successor(
        self, test_config: Config, method: str, v0_path: str, successor: str
    ) -> None:
        """Whatever v0 answers (a 422 here, no provider asked), it names its successor."""
        client = v0_client(test_config, v1_enabled=True)
        response = client.request(method, v0_path, json={} if method == "post" else None)

        assert response.headers["deprecation"] == "@" + str(
            int((date(2026, 11, 27) - date(1970, 1, 1)).total_seconds())
        )
        assert response.headers["link"] == f'<{successor}>; rel="successor-version"'
