"""``ProviderSearch`` as v1 serves it: failures said as failures, one follow batch, an IMDb id resolved.

P11a copied v0's search faithfully, v0's slips included (carried from review row 41): a provider
exception read as « not found », two dead TV providers answered as an empty page, a follow lookup
per result, an IMDb number handed to TMDB as if it were a TMDB id. These cases hold what v1 says
instead. The copy's own cases stay in ``test_provider_search.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import nullcontext

import pytest

from personalscraper.acquire.domain import FollowedSeries, FollowKind
from personalscraper.api.metadata._base import SearchResult
from personalscraper.app.acquisition.search import ProviderSearch
from personalscraper.app.acquisition.search_cache import SearchResultCache
from personalscraper.app.errors import AppBadRequest, AppUnavailable, RefusalCode
from personalscraper.core._contracts import ApiError
from personalscraper.core.identity import MediaRef
from tests.unit.app.acquisition.test_provider_search import _ACTOR, _movie, _show, _Tmdb, _Tvdb


def _service(tmdb: object, tvdb: object, follows: object = None) -> ProviderSearch:
    """Build the service over fake clients, a fresh cache and the follow lookup given.

    Args:
        tmdb: The TMDB client fake.
        tvdb: The TVDB client fake.
        follows: The follow lookup, or ``None``.

    Returns:
        The service; no indexer is configured, so nothing is flagged owned.
    """
    return ProviderSearch(
        clients=lambda: nullcontext((tmdb, tvdb)),
        indexer_db=None,
        cache=SearchResultCache(),
        follows=follows,  # type: ignore[arg-type]  # a fake lookup
    )


class _BatchLookup:
    """A follow lookup that counts how it is asked and answers a configured set of ids."""

    def __init__(self, followed: set[int] = frozenset()) -> None:  # type: ignore[assignment]
        self.followed = followed
        self.batches: list[int] = []

    def find_all_by_refs(self, lookups: Sequence[tuple[MediaRef, FollowKind | None]]) -> list[list[FollowedSeries]]:
        """Answer every lookup at once, noting how many were asked together.

        Args:
            lookups: The ``(ref, kind)`` pairs.

        Returns:
            A standing follow for each ref whose TMDB id is configured, else nothing.
        """
        self.batches.append(len(lookups))
        return [
            [FollowedSeries(media_ref=ref, title="x", added_at=1, kind=kind or "movie")]
            if ref.tmdb_id in self.followed
            else []
            for ref, kind in lookups
        ]


class _ExplodingLookup:
    """A follow store that cannot be read."""

    def find_all_by_refs(self, lookups: Sequence[tuple[MediaRef, FollowKind | None]]) -> list[list[FollowedSeries]]:
        """Fail as a locked or corrupt ``acquire.db`` does.

        Args:
            lookups: The pairs asked.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("acquire.db is locked")


class TestFollowedFlag:
    """``followed`` is read in one batch, and a store that cannot be read costs the flag only."""

    def test_a_page_is_flagged_by_one_batch_not_one_lookup_per_result(self) -> None:
        """Five results, one store call carrying five lookups."""
        lookup = _BatchLookup(followed={2})
        movies = [_movie(str(i), f"Dune {i}", 2000 + i, popularity=10.0 - i) for i in range(1, 6)]

        page = _service(_Tmdb(movies, []), _Tvdb(), lookup).search(_ACTOR, "dune", "movie")

        assert lookup.batches == [5]
        assert {r.provider_id: r.followed for r in page.results} == {1: False, 2: True, 3: False, 4: False, 5: False}

    def test_a_raising_follow_store_degrades_like_an_absent_one(self) -> None:
        """The search is served, nothing flagged followed, as with no store wired."""
        page = _service(_Tmdb([_movie("1", "Dune", 2021)], []), _Tvdb(), _ExplodingLookup()).search(
            _ACTOR, "dune", "movie"
        )

        assert [r.title for r in page.results] == ["Dune"]
        assert [r.followed for r in page.results] == [False]

    def test_a_raising_follow_store_degrades_a_lookup_too(self) -> None:
        """The lookup by id is flagged by the same pass, and degrades the same way."""
        found = _service(object(), _ById(shows={255968: "Kaamelott"}), _ExplodingLookup()).lookup(
            _ACTOR, "tvdb", "255968"
        )

        assert [(m.title, m.followed) for m in found] == [("Kaamelott", False)]


class _FailingTvdb:
    """A TVDB that cannot be reached."""

    def search_series(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        raise ApiError(provider="tvdb", http_status=503, message="down")


class _FailingTmdbTv(_Tmdb):
    """A TMDB whose television search fails, its film search answering."""

    def search_tv(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        raise ApiError(provider="tmdb", http_status=503, message="down")


class TestTelevisionFailures:
    """Two television providers down is a failure, never an empty page."""

    def test_both_television_providers_failing_is_provider_unavailable(self) -> None:
        """A search for shows that nobody could answer says so."""
        with pytest.raises(AppUnavailable) as refused:
            _service(_FailingTmdbTv([], []), _FailingTvdb()).search(_ACTOR, "silo", "tv")

        assert refused.value.code is RefusalCode.PROVIDER_UNAVAILABLE

    def test_a_failed_search_is_not_cached_as_an_empty_answer(self) -> None:
        """The next try asks the providers again."""
        cache = SearchResultCache()
        service = ProviderSearch(
            clients=lambda: nullcontext((_FailingTmdbTv([], []), _FailingTvdb())), indexer_db=None, cache=cache
        )
        with pytest.raises(AppUnavailable):
            service.search(_ACTOR, "silo", "tv")

        assert cache.get("silo", "tv") is None

    def test_one_television_provider_failing_still_serves_the_other(self) -> None:
        """The degraded half is served (v0's rule, logged)."""
        shows = [_show("9", "Silo", 2023, popularity=5.0)]
        service = _service(_Tmdb([], shows), _FailingTvdb())

        assert [r.title for r in service.search(_ACTOR, "silo", "tv").results] == ["Silo"]

    def test_films_answering_beside_two_dead_television_providers_are_served(self) -> None:
        """A search of both kinds keeps the films that came: the lot is partial, not failed."""
        service = _service(_FailingTmdbTv([_movie("1", "Silo", 2020)], []), _FailingTvdb())

        assert [r.title for r in service.search(_ACTOR, "silo", None).results] == ["Silo"]


class _Details:
    """A provider's details of one medium."""

    def __init__(self, title: str = "Dune", year: int = 2021) -> None:
        self.title = title
        self.year = year
        self.overview = "Spice."
        self.images: list[object] = []


class _ById:
    """A provider client holding movies and shows by id, recording what it is asked."""

    def __init__(
        self,
        movies: dict[int, str] | None = None,
        shows: dict[int, str] | None = None,
        *,
        fail: Exception | None = None,
        imdb: dict[str, dict[str, int]] | None = None,
    ) -> None:
        self.movies = movies or {}
        self.shows = shows or {}
        self.fail = fail
        self.imdb = imdb or {}
        self.asked: list[tuple[str, object]] = []

    def _get(self, kind: str, held: dict[int, str], provider_id: object) -> object:
        self.asked.append((kind, provider_id))
        if self.fail is not None:
            raise self.fail
        if provider_id not in held:
            raise ApiError(provider="x", http_status=404, message="not found")
        return _Details(held[provider_id])  # type: ignore[index]

    def get_movie(self, provider_id: int) -> object:
        return self._get("movie", self.movies, provider_id)

    def get_tv(self, provider_id: int) -> object:
        return self._get("tv", self.shows, provider_id)

    def get_series(self, provider_id: int) -> object:
        return self._get("tv", self.shows, provider_id)

    def find_ids_by_imdb(self, imdb_id: str) -> dict[str, int]:
        self.asked.append(("find", imdb_id))
        if self.fail is not None:
            raise self.fail
        return self.imdb.get(imdb_id, {})


class TestLookup:
    """``lookup``: the medium or media a source knows under an identifier."""

    def test_a_tmdb_id_held_as_a_film_and_as_a_show_answers_both(self) -> None:
        """TMDB numbers films and shows apart: the same number can be two media."""
        client = _ById(movies={603: "The Matrix"}, shows={603: "A Show"})

        found = _service(client, object()).lookup(_ACTOR, "tmdb", "603")

        assert sorted((m.kind, m.title) for m in found) == [("movie", "The Matrix"), ("tv", "A Show")]

    def test_an_id_the_source_does_not_know_answers_nothing(self) -> None:
        """A 404 on both kinds is no result, not a failure."""
        assert _service(_ById(), object()).lookup(_ACTOR, "tmdb", "999") == ()

    def test_a_provider_failure_is_said_as_unavailable_not_as_not_found(self) -> None:
        """A 503 from the provider is the provider's: ``provider.unavailable`` naming it."""
        client = _ById(fail=ApiError(provider="tmdb", http_status=503, message="down"))

        with pytest.raises(AppUnavailable) as refused:
            _service(client, object()).lookup(_ACTOR, "tmdb", "603")

        assert refused.value.code is RefusalCode.PROVIDER_UNAVAILABLE
        assert refused.value.params == {"provider": "tmdb"}

    def test_a_transport_exception_is_unavailable_too(self) -> None:
        """A timeout is not an id the provider does not know."""
        with pytest.raises(AppUnavailable):
            _service(_ById(fail=TimeoutError("slow")), object()).lookup(_ACTOR, "tmdb", "603")

    def test_a_provider_that_is_not_configured_is_unavailable(self) -> None:
        """No client for the provider asked: a failure to answer, not an empty answer."""
        with pytest.raises(AppUnavailable) as refused:
            _service(None, None).lookup(_ACTOR, "tvdb", "81189")

        assert refused.value.params == {"provider": "tvdb"}

    @pytest.mark.parametrize(("provider", "provider_id"), [("tmdb", "tt0133093"), ("tvdb", "12a"), ("imdb", "603")])
    def test_an_identifier_not_in_its_sources_format_is_refused_before_any_call(
        self, provider: str, provider_id: str
    ) -> None:
        """Digits for TMDB and TVDB, ``tt`` and digits for IMDb; anything else is ``request.invalid`` on ``id``."""
        client = _ById(movies={603: "x"})

        with pytest.raises(AppBadRequest) as refused:
            _service(client, client).lookup(_ACTOR, provider, provider_id)

        assert refused.value.params == {"fields": ["id"]}
        assert client.asked == []

    def test_an_imdb_id_is_resolved_at_tmdb_and_never_handed_to_it_as_a_tmdb_id(self) -> None:
        """TMDB's find endpoint maps the IMDb id to TMDB ids; ``get_movie`` is asked with the TMDB id."""
        client = _ById(movies={1234: "The Clone Wars"}, imdb={"tt1185834": {"movie": 1234}})

        found = _service(client, object()).lookup(_ACTOR, "imdb", "tt1185834")

        assert [(m.provider, m.provider_id, m.kind, m.title) for m in found] == [
            ("tmdb", 1234, "movie", "The Clone Wars")
        ]
        assert client.asked == [("find", "tt1185834"), ("movie", 1234)]

    def test_an_imdb_id_tmdb_does_not_know_answers_nothing(self) -> None:
        """The find endpoint matching nothing is no result."""
        client = _ById()

        assert _service(client, object()).lookup(_ACTOR, "imdb", "tt0000001") == ()
        assert client.asked == [("find", "tt0000001")]

    def test_an_imdb_lookup_failing_at_tmdb_is_unavailable(self) -> None:
        """The provider that could not resolve the id is named, not blamed on the id."""
        client = _ById(fail=ApiError(provider="tmdb", http_status=500, message="boom"))

        with pytest.raises(AppUnavailable):
            _service(client, object()).lookup(_ACTOR, "imdb", "tt1185834")


class TestByIdKeepsItsFailures:
    """``by_id`` (one kind asked) says a failure as a failure too; only an unknown id is a 404."""

    def test_a_provider_failure_is_unavailable(self) -> None:
        """A 503 is no longer read as « not found »."""
        client = _ById(fail=ApiError(provider="tmdb", http_status=503, message="down"))

        with pytest.raises(AppUnavailable):
            _service(client, object()).by_id(_ACTOR, "tmdb", 603, "movie")
