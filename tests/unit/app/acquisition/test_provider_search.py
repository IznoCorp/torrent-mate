"""``ProviderSearch``: v0's provider search and lookup, copied into v1's layer (K3 P11a).

Every case of v0's ``TestSearchEndpoint`` that belongs to the service rather than to the HTTP
boundary is replayed here with the same fake providers and the same expected results: the
lookup's two and the search's ten. The three answers owned by v0's route (the ``limit`` /
``offset`` bounds, the session, the empty query) replay in the route phase's tests.

The service is built by hand over fake provider clients, a fresh result cache and a fake
ownership checker: nothing here reaches a provider, a server or ``library.db``.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Literal

import pytest

from personalscraper.api.metadata._base import SearchResult
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.search import ProviderSearch, scoped_provider_clients
from personalscraper.app.acquisition.search_cache import SEARCH_CACHE, SearchResultCache
from personalscraper.app.errors import AppForbidden, AppNotFound, AppUnavailable, RefusalCode
from personalscraper.core.identity import MediaRef

_ACTOR = Actor(
    account_id="account-requester",
    name="Requester",
    role_id="requester",
    role_kind=RoleKind.ORDINARY,
    role_rights=frozenset({Right.ACQUISITION_REQUEST}),
    ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
)


class _Tmdb:
    """A fake TMDB client serving canned rows."""

    def __init__(self, movies: list[SearchResult], shows: list[SearchResult]) -> None:
        self.movies = movies
        self.shows = shows
        self.movie_calls = 0

    def search_movie(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        self.movie_calls += 1
        return self.movies

    def search_tv(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        return self.shows


class _Tvdb:
    """A fake TVDB client that finds nothing."""

    def search_series(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
        return []


def _service(
    tmdb: object,
    tvdb: object,
    *,
    cache: SearchResultCache | None = None,
    indexer_db: Path | None = None,
    ownership: object = None,
) -> ProviderSearch:
    """Build the service over the fakes, with a fresh cache unless one is given."""
    return ProviderSearch(
        clients=lambda: nullcontext((tmdb, tvdb)),
        indexer_db=indexer_db,
        ownership=ownership,  # type: ignore[arg-type]  # a fake checker factory
        cache=cache if cache is not None else SearchResultCache(),
    )


def _movie(provider_id: str, title: str, year: int, popularity: float | None = None, **extra: str) -> SearchResult:
    """A TMDB movie row."""
    return SearchResult(
        provider="tmdb",
        provider_id=provider_id,
        title=title,
        year=year,
        media_type="movie",
        popularity=popularity,
        **extra,
    )


def _show(
    provider_id: str,
    title: str,
    year: int,
    popularity: float | None = None,
    provider: Literal["tmdb", "tvdb"] = "tmdb",
) -> SearchResult:
    """A show row."""
    return SearchResult(
        provider=provider, provider_id=provider_id, title=title, year=year, media_type="tv", popularity=popularity
    )


def _dunes(count: int, *, top: float) -> list[SearchResult]:
    """``count`` « Dune » films, the first the most popular."""
    return [_movie(str(i), f"Dune {i}", 2000 + i, popularity=top - i) for i in range(count)]


class TestSearch:
    """``ProviderSearch.search`` — v0's ``run_media_search`` and its search cases."""

    def test_search_both_kinds_sorted(self) -> None:
        """Both chains run; results are kind-tagged and ranked best-first."""
        movie = _movie("438631", "Dune", 2021, 120.0, poster_url="https://img/dune.jpg", overview="Sur Arrakis.")
        show = _show("1", "Prophecy", 2024, 1.0)

        page = _service(_Tmdb([movie], [show]), _Tvdb()).search(_ACTOR, "dune", None)

        assert len(page.results) == 2
        # 'dune' matches the film exactly and the show not at all → film first.
        assert page.results[0].kind == "movie"
        assert page.results[0].title == "Dune"
        assert page.results[0].poster_url == "https://img/dune.jpg"

    def test_series_owned_is_flagged_already_owned(self, tmp_path: Path) -> None:
        """An owned SERIES is flagged, not only an owned film.

        The ownership pass once only checked ``kind == "movie"`` results, so a series present
        in the library searched silent while films showed « already owned ». A series counts
        as owned as soon as ANY live episode file exists.
        """
        movie = _movie("101", "Kaamelott — Premier volet", 2021)
        show = _show("202", "Kaamelott", 2005)
        calls: dict[str, object] = {}

        class _FakeChecker:
            def __init__(self, _path: object) -> None:
                pass

            def owns(self, ref: object, *, kind: str, **_kw: object) -> bool:
                calls["movie"] = (ref, kind)
                return True

            def owned_pairs(self, ref: object) -> set[tuple[int, int]]:
                calls["pairs"] = ref
                return {(1, 1)}

            def close(self) -> None:
                pass

        service = _service(_Tmdb([movie], [show]), _Tvdb(), indexer_db=tmp_path / "library.db", ownership=_FakeChecker)

        page = service.search(_ACTOR, "kaamelott", None)

        by_kind = {r.kind: r for r in page.results}
        assert by_kind["tv"].already_owned is True
        assert by_kind["movie"].already_owned is True
        # The series went through the episode-presence predicate with its id.
        assert getattr(calls["pairs"], "tmdb_id", None) == 202
        assert calls["movie"][1] == "movie"  # type: ignore[index]

    def test_search_kind_filter_movie_only(self) -> None:
        """kind=movie must not run the TV chain.

        The calls are recorded and counted: the TV gatherer swallows a provider's exception, so a
        fake that raises would pass even when the chain ran.
        """
        calls: list[str] = []
        movie = _movie("1", "Dune", 2021)

        class _MovieOnlyTmdb:
            def search_movie(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
                calls.append("search_movie")
                return [movie]

            def search_tv(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
                calls.append("search_tv")
                return []

        class _MovieOnlyTvdb:
            def search_series(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
                calls.append("search_series")
                return []

        page = _service(_MovieOnlyTmdb(), _MovieOnlyTvdb()).search(_ACTOR, "dune", "movie")

        assert len(page.results) == 1
        assert page.results[0].kind == "movie"
        assert calls == ["search_movie"]

    def test_total_counts_every_candidate_not_the_page(self) -> None:
        """Serving 5 of 30 says so: ``total`` is every ranked candidate."""
        page = _service(_Tmdb(_dunes(30, top=30.0), []), _Tvdb()).search(_ACTOR, "dune", "movie", limit=5)

        assert len(page.results) == 5
        assert page.total == 30
        assert page.limit == 5
        assert page.offset == 0

    def test_pages_do_not_overlap(self) -> None:
        """offset=0 and offset=10 share no candidate, and agree on the total."""
        service = _service(_Tmdb(_dunes(30, top=30.0), []), _Tvdb())

        first = service.search(_ACTOR, "dune", "movie", limit=10, offset=0)
        second = service.search(_ACTOR, "dune", "movie", limit=10, offset=10)

        ids_first = {r.provider_id for r in first.results}
        ids_second = {r.provider_id for r in second.results}
        assert ids_first & ids_second == set()
        assert first.total == second.total == 30
        assert second.offset == 10

    def test_offset_past_the_end_is_empty_not_an_error(self) -> None:
        """Paging past the last result is an empty page, still with the true total."""
        page = _service(_Tmdb([_movie("1", "Dune", 2021)], []), _Tvdb()).search(_ACTOR, "dune", "movie", offset=500)

        assert page.results == ()
        assert page.total == 1

    def test_all_kinds_share_one_popularity_scale(self) -> None:
        """« All » ranks films and shows on ONE scale, not two.

        Popularity is normalised against the most popular candidate in the lot. Ranking each
        kind in its own pass ran that normalisation twice, on two different maxima, producing
        two incomparable 1.000s. Measured in production 2026-08-05: 'monarch' put *Monarch City*
        (popularity 2.19) ahead of *Monarch: Legacy of Monsters* (popularity 34.45).
        """
        weak_film = _movie("1469143", "Monarch City", 2025, 2.19)
        popular_show = _show("202411", "Monarch: Legacy of Monsters", 2023, 34.45)

        page = _service(_Tmdb([weak_film], [popular_show]), _Tvdb()).search(_ACTOR, "monarch", None)

        assert page.results[0].title == "Monarch: Legacy of Monsters"
        assert page.results[0].kind == "tv"

    def test_kind_tag_follows_the_media_type_not_the_chain(self) -> None:
        """With one ranking pass, each row is tagged from its own media_type."""
        film = _movie("1", "Dune", 2021, 50.0)
        show = _show("2", "Dune Prophecy", 2024, 5.0, provider="tvdb")

        page = _service(_Tmdb([film], [show]), _Tvdb()).search(_ACTOR, "dune", None)

        by_id = {r.provider_id: r.kind for r in page.results}
        assert by_id[1] == "movie"
        assert by_id[2] == "tv"

    def test_second_page_does_not_re_query_the_providers(self) -> None:
        """Paging is free at the providers: the ranked lot is served from the cache.

        Before the cache, offset=30 replayed the full TMDB + TVDB fan-out and re-ranked ~130
        candidates just to hand back a window of a result set that had not changed.
        """
        tmdb = _Tmdb(_dunes(40, top=40.0), [])
        service = _service(tmdb, _Tvdb())

        first = service.search(_ACTOR, "dune-cache", "movie", limit=20, offset=0)
        second = service.search(_ACTOR, "dune-cache", "movie", limit=20, offset=20)

        assert tmdb.movie_calls == 1, "the second page called the provider again"
        assert first.total == second.total == 40
        assert {r.provider_id for r in first.results} & {r.provider_id for r in second.results} == set()

    def test_a_cached_page_opens_no_provider_clients(self) -> None:
        """A page served from the cache builds no registry: v0's route built one per page.

        The accepted deviation from the copy: the answers are v0's, the wasted registry (and its
        502 on a page the cache could have served) is not carried over.
        """
        opened: list[str] = []

        def clients() -> object:
            opened.append("opened")
            return nullcontext((_Tmdb(_dunes(40, top=40.0), []), _Tvdb()))

        service = ProviderSearch(clients=clients, indexer_db=None, cache=SearchResultCache())  # type: ignore[arg-type]

        service.search(_ACTOR, "dune", "movie", limit=20, offset=0)
        service.search(_ACTOR, "dune", "movie", limit=20, offset=20)

        assert opened == ["opened"]

    def test_cache_key_separates_kinds(self) -> None:
        """« Movies » is never served the « All » lot from the cache."""
        film = _movie("1", "Dune", 2021, 9.0)
        show = _show("2", "Dune Show", 2024, 8.0)
        service = _service(_Tmdb([film], [show]), _Tvdb())

        both = service.search(_ACTOR, "dune-kinds", None)
        movies = service.search(_ACTOR, "dune-kinds", "movie")

        assert both.total == 2
        assert movies.total == 1


class TestLookup:
    """``ProviderSearch.by_id`` — v0's ``run_media_lookup`` and its two cases."""

    def test_lookup_by_id_resolves_a_result_without_following(self) -> None:
        """A by-id lookup RESOLVES and returns — it never follows.

        The add-by-ID form once followed on submit, sight unseen, which stored a nameless
        follow. Resolving first puts a real card on screen and leaves the add to a deliberate tap.
        """

        class _Details:
            title = "Kaamelott"
            year = 2005
            overview = "Les aventures du roi Arthur."
            images: list[object] = []

        class _LookupTvdb:
            def get_series(self, provider_id: int) -> object:
                assert provider_id == 255968
                return _Details()

        result = _service(object(), _LookupTvdb()).by_id(_ACTOR, "tvdb", 255968, "tv")

        assert result.title == "Kaamelott"
        assert result.provider_id == 255968
        assert result.kind == "tv"

    def test_lookup_serves_the_first_poster_artwork(self) -> None:
        """The card carries the first ``poster`` image the provider lists, never another type."""
        from types import SimpleNamespace

        details = SimpleNamespace(
            title="Dune",
            year=2021,
            overview="  ",
            images=[
                SimpleNamespace(type="fanart", url="https://img/fanart.jpg"),
                SimpleNamespace(type="poster", url="https://img/poster.jpg"),
            ],
        )

        class _LookupTmdb:
            def get_movie(self, provider_id: int) -> object:
                return details

        result = _service(_LookupTmdb(), object()).by_id(_ACTOR, "tmdb", 438631, "movie")

        assert result.poster_url == "https://img/poster.jpg"
        assert result.overview is None
        assert result.score == 1.0

    def test_lookup_unknown_id_is_a_404_not_a_nameless_row(self) -> None:
        """An id the provider does not know FAILS as ``media.not_found``, never resolves blank."""

        class _LookupTvdb:
            def get_series(self, provider_id: int) -> object:
                raise ValueError("no such series")

        with pytest.raises(AppNotFound) as refused:
            _service(object(), _LookupTvdb()).by_id(_ACTOR, "tvdb", 999999999, "tv")

        assert refused.value.status == 404
        assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND

    def test_lookup_nameless_details_is_a_404(self) -> None:
        """A provider answering a row with no title is a 404 too (v0's second 404)."""

        class _Nameless:
            title = ""

        class _LookupTvdb:
            def get_series(self, provider_id: int) -> object:
                return _Nameless()

        with pytest.raises(AppNotFound):
            _service(object(), _LookupTvdb()).by_id(_ACTOR, "tvdb", 1, "tv")


class TestPerimeterAndSeams:
    """What the layer adds around the copy: authorisation, the failure mapping, the real seams."""

    def test_an_actor_without_the_request_right_is_refused_before_any_provider_call(self) -> None:
        """``@requires`` refuses first: ``right.missing``, no provider asked."""
        tmdb = _Tmdb([_movie("1", "Dune", 2021)], [])
        reader = Actor(
            account_id="account-reader",
            name="Reader",
            role_id="reader",
            role_kind=RoleKind.ORDINARY,
            role_rights=frozenset({Right.LIBRARY_READ}),
            ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
        )

        with pytest.raises(AppForbidden) as refused:
            _service(tmdb, _Tvdb()).search(reader, "dune", None)

        assert refused.value.code is RefusalCode.RIGHT_MISSING
        assert tmdb.movie_calls == 0

    def test_a_failing_movie_search_is_provider_unavailable(self) -> None:
        """v0's 502 on a movie-chain failure is the layer's ``provider.unavailable``."""

        class _Failing:
            def search_movie(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
                raise RuntimeError("tmdb down")

        with pytest.raises(AppUnavailable) as refused:
            _service(_Failing(), _Tvdb()).search(_ACTOR, "dune", "movie")

        assert refused.value.code is RefusalCode.PROVIDER_UNAVAILABLE
        assert refused.value.params == {"provider": "tmdb"}
        assert "tmdb down" not in refused.value.detail

    def test_the_default_cache_is_the_process_wide_one(self) -> None:
        """Left unset, the service pages through ``SEARCH_CACHE`` — the cache v0 already fills."""
        service = ProviderSearch(clients=lambda: nullcontext((object(), object())), indexer_db=None)

        assert service._cache is SEARCH_CACHE

    def test_scoped_provider_clients_closes_the_registry_when_the_body_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The registry lives for one ``with`` block and is closed even on a failure."""
        closed: list[str] = []

        class _Registry:
            def get(self, name: str) -> str:
                return name

            def close(self) -> None:
                closed.append("registry")

        class _Context:
            provider_registry = _Registry()
            acquire = None

        monkeypatch.setattr("personalscraper.app.composition.build_app_context", lambda *_a, **_kw: _Context())

        with pytest.raises(RuntimeError, match="boom"), scoped_provider_clients(object(), object()) as (tmdb, tvdb):  # type: ignore[arg-type]
            assert (tmdb, tvdb) == ("tmdb", "tvdb")
            raise RuntimeError("boom")

        assert closed == ["registry"]

    def test_scoped_provider_clients_maps_a_registry_failure_to_provider_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A registry that cannot be built is v0's 502, here ``provider.unavailable``."""

        def _broken(*_a: object, **_kw: object) -> object:
            raise RuntimeError("no api key sk-secret")

        monkeypatch.setattr("personalscraper.app.composition.build_app_context", _broken)

        with pytest.raises(AppUnavailable) as refused:
            with scoped_provider_clients(object(), object()):  # type: ignore[arg-type]
                pass

        assert refused.value.code is RefusalCode.PROVIDER_UNAVAILABLE
        assert "sk-secret" not in refused.value.detail


class TestScopedClientsTeardown:
    """The registry's lifetime: bounded retry, closed on every path, a teardown failure never masks."""

    @staticmethod
    def _context(
        monkeypatch: pytest.MonkeyPatch, *, registry: object, acquire: object = None
    ) -> list[dict[str, object]]:
        """Patch ``build_app_context`` to return a context over the given registry.

        Returns:
            The keyword arguments each build received.
        """
        built: list[dict[str, object]] = []

        class _Context:
            provider_registry = registry

        _Context.acquire = acquire  # type: ignore[attr-defined]

        def build(_config: object, _settings: object, **kwargs: object) -> object:
            built.append(kwargs)
            return _Context()

        monkeypatch.setattr("personalscraper.app.composition.build_app_context", build)
        return built

    def test_the_scope_passes_the_bounded_retry_and_closes_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The registry is built with ONE attempt and closed after a normal ``with`` block."""
        from personalscraper.app.composition import ONE_ATTEMPT

        closed: list[str] = []

        class _Registry:
            def get(self, name: str) -> str:
                return name

            def close(self) -> None:
                closed.append("registry")

        built = self._context(monkeypatch, registry=_Registry())

        with scoped_provider_clients(object(), object()):  # type: ignore[arg-type]
            assert closed == []

        assert built == [{"provider_retry": ONE_ATTEMPT}]
        assert closed == ["registry"]

    def test_a_registry_without_a_provider_is_closed_and_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A built registry that cannot hand a client over is still closed (no leaked session)."""
        closed: list[str] = []

        class _Registry:
            def get(self, name: str) -> str:
                if name == "tvdb":
                    raise KeyError(name)
                return name

            def close(self) -> None:
                closed.append("registry")

        self._context(monkeypatch, registry=_Registry())

        with pytest.raises(AppUnavailable) as refused:
            with scoped_provider_clients(object(), object()):  # type: ignore[arg-type]
                pass

        assert refused.value.code is RefusalCode.PROVIDER_UNAVAILABLE
        assert closed == ["registry"]

    def test_a_failing_teardown_never_masks_the_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A registry or acquisition handle that fails to close leaves the served answer intact."""
        attempted: list[str] = []

        class _Registry:
            def get(self, name: str) -> str:
                return name

            def close(self) -> None:
                attempted.append("registry")
                raise RuntimeError("close failed")

        class _Acquire:
            def close(self) -> None:
                attempted.append("acquire")
                raise RuntimeError("close failed")

        self._context(monkeypatch, registry=_Registry(), acquire=_Acquire())

        with scoped_provider_clients(object(), object()) as clients:  # type: ignore[arg-type]
            served = clients

        assert served == ("tmdb", "tvdb")
        assert attempted == ["registry", "acquire"]


def test_the_ownership_probe_gets_the_provider_id_as_a_media_ref(tmp_path: Path) -> None:
    """A TVDB row is probed by ``MediaRef(tvdb_id=…)``, a TMDB row by ``MediaRef(tmdb_id=…)``."""
    seen: list[MediaRef] = []

    class _Probe:
        def __init__(self, _path: object) -> None:
            pass

        def owns(self, ref: MediaRef, *, kind: str, **_kw: object) -> bool:
            seen.append(ref)
            return False

        def owned_pairs(self, ref: MediaRef) -> set[tuple[int, int]]:
            seen.append(ref)
            return set()

        def close(self) -> None:
            pass

    film = _movie("7", "Dune", 2021)
    show = _show("9", "Dune Show", 2024, provider="tvdb")

    class _ShowTvdb:
        def search_series(self, query: str, year: object = None, **_kw: object) -> list[SearchResult]:
            return [show]

    _service(_Tmdb([film], []), _ShowTvdb(), indexer_db=tmp_path / "library.db", ownership=_Probe).search(
        _ACTOR, "dune", None
    )

    assert MediaRef(tmdb_id=7) in seen
    assert MediaRef(tvdb_id=9) in seen


def test_a_lookup_is_flagged_owned_like_a_search(tmp_path: Path) -> None:
    """The by-id lookup runs the same ownership pass: a held film says so on its card."""

    class _Held:
        def __init__(self, _path: object) -> None:
            pass

        def owns(self, media_ref: MediaRef, *, kind: str, **_kw: object) -> bool:
            return media_ref == MediaRef(tmdb_id=438631) and kind == "movie"

        def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
            return set()

        def close(self) -> None:
            pass

    class _Details:
        title = "Dune"
        year = 2021
        overview = None
        images: list[object] = []

    class _LookupTmdb:
        def get_movie(self, provider_id: int) -> object:
            return _Details()

    service = _service(_LookupTmdb(), object(), indexer_db=tmp_path / "library.db", ownership=_Held)

    assert service.by_id(_ACTOR, "tmdb", 438631, "movie").already_owned is True
    assert service.by_id(_ACTOR, "tmdb", 1, "movie").already_owned is False
