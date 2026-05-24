"""Tests for metadata family base — Protocol + MetadataClient."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import ClassVar

import pytest

from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    MetadataClient,
    Notations,
    Recommendation,
    SearchResult,
    SeasonDetails,
    Video,
)
from personalscraper.api.metadata._contracts import (
    ArtworkProvider,
    EpisodeFetcher,
    KeywordProvider,
    MovieDetailsProvider,
    RatingProvider,
    RecommendationProvider,
    Searchable,
    TvDetailsProvider,
    VideoProvider,
)


class TestTypedModels:
    """Construction and immutability tests for typed response models."""

    def test_search_result_construction(self) -> None:
        """SearchResult builds with provider, provider_id, title and sensible defaults."""
        sr = SearchResult(provider="tmdb", provider_id="123", title="Test Movie")
        assert sr.provider == "tmdb"
        assert sr.provider_id == "123"
        assert sr.media_type == "movie"
        assert sr.overview == ""

    def test_media_details_defaults(self) -> None:
        """MediaDetails has empty defaults for list and string fields."""
        md = MediaDetails(provider="tmdb", provider_id="123")
        assert md.title == ""
        assert md.genres == []
        assert md.images == []

    def test_artwork_item(self) -> None:
        """ArtworkItem stores type, url, language, and optional season."""
        ai = ArtworkItem(type="poster", url="http://example.com/poster.jpg", language="fr")
        assert ai.type == "poster"
        assert ai.season is None

    def test_notations(self) -> None:
        """Notations stores provider, source, score, and optional votes_count."""
        n = Notations(provider="tmdb", source="imdb", score=7.5, votes_count=1000)
        assert n.score == 7.5
        assert n.votes_count == 1000

    def test_recommendation(self) -> None:
        """Recommendation stores provider, title, reason, and optional year."""
        r = Recommendation(provider="trakt", provider_id="456", title="Similar Movie", reason="Because you liked X")
        assert r.media_type == "movie"

    def test_video(self) -> None:
        """Video stores id, site, key, type, and optional metadata."""
        v = Video(id="abc", site="youtube", key="dQw4w9WgXcQ", type="trailer", official=True, size=1080)
        assert v.key == "dQw4w9WgXcQ"
        assert v.iso_639_1 == ""

    def test_episode_info(self) -> None:
        """EpisodeInfo stores episode_number, title, overview, air_date."""
        ei = EpisodeInfo(episode_number=1, title="Pilot", air_date="2024-01-15")
        assert ei.episode_number == 1
        assert ei.runtime_minutes is None

    def test_season_details(self) -> None:
        """SeasonDetails stores provider, tv_id, season_number, and episodes list."""
        episodes = [EpisodeInfo(episode_number=1, title="Pilot")]
        sd = SeasonDetails(provider="tvdb", tv_id="789", season_number=1, episodes=episodes)
        assert sd.season_number == 1
        assert len(sd.episodes) == 1

    def test_models_are_frozen(self) -> None:
        """All models are frozen dataclasses — mutation raises an error."""
        sr = SearchResult(provider="tmdb", provider_id="123", title="Test")
        with pytest.raises(FrozenInstanceError):
            sr.title = "New Title"  # type: ignore[misc]


class TestMetadataClient:
    """MetadataClient base class tests."""

    def test_provider_name(self) -> None:
        """provider_name is read from the subclass ClassVar declaration."""
        client = TMDBFakeClient(None)  # type: ignore[arg-type]
        assert client.provider_name == "tmdbfake"

    def test_missing_provider_name_raises(self) -> None:
        """Forgetting to declare provider_name fails at *class definition* time."""
        with pytest.raises(TypeError, match="must declare an explicit provider_name"):

            class _Bare(MetadataClient):  # type: ignore[unused-ignore]  # noqa: F841
                pass

    def test_missing_provider_name_raises_even_with_custom_init(self) -> None:
        """The ``__init_subclass__`` guard fires at class-creation time.

        Subclasses that override ``__init__`` and skip ``super().__init__()``
        still trigger the check — this is the load-bearing scenario the
        design explicitly calls out: instance-time hooks (``__init__``) can
        be bypassed; class-creation hooks cannot.
        """
        with pytest.raises(TypeError, match="must declare an explicit provider_name"):

            class _CustomInit(MetadataClient):  # type: ignore[unused-ignore]  # noqa: F841
                def __init__(self) -> None:  # deliberately skips super().__init__()
                    self.flag = "should never reach this"

    def test_empty_string_provider_name_raises(self) -> None:
        """An explicit but empty-string ``provider_name`` is rejected too."""
        with pytest.raises(TypeError, match="must declare an explicit provider_name"):

            class _Empty(MetadataClient):  # type: ignore[unused-ignore]  # noqa: F841
                provider_name: ClassVar[str] = ""

    def test_default_get_notations_raises(self) -> None:
        """Default get_notations raises NotImplementedError with provider name."""
        client = TMDBFakeClient(None)  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError, match="tmdbfake does not support notations"):
            client.get_notations("123", "movie")

    def test_default_get_recommendations_raises(self) -> None:
        """Default get_recommendations raises NotImplementedError."""
        client = TMDBFakeClient(None)  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError, match="tmdbfake does not support recommendations"):
            client.get_recommendations("123", "movie")

    def test_default_get_artwork_urls_raises(self) -> None:
        """Default get_artwork_urls raises NotImplementedError."""
        client = TMDBFakeClient(None)  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError, match="tmdbfake does not support artwork"):
            client.get_artwork_urls("123")

    def test_override_capability(self) -> None:
        """Subclass can override a capability method and return typed result."""

        class TMDBClient(MetadataClient):
            provider_name: ClassVar[str] = "tmdb"

            def get_notations(self, media_id: str, media_type: str) -> Notations | None:
                return Notations(provider="tmdb", source="tmdb", score=8.0)

        client = TMDBClient(None)  # type: ignore[arg-type]
        result = client.get_notations("123", "movie")
        assert result is not None
        assert result.score == 8.0


class TestProviderNameClassVarValues:
    """Each real metadata client must expose the canonical lowercase ``provider_name``.

    Without this table-test, a copy-paste typo (e.g. ``"tdmb"``) in a
    ClassVar would only surface via downstream string comparisons —
    silent bugs in error messages, log routing and ``ProviderName``
    enum lookups.
    """

    @pytest.mark.parametrize(
        ("import_path", "class_name", "expected_provider_name"),
        [
            ("personalscraper.api.metadata.tmdb", "TMDBClient", "tmdb"),
            ("personalscraper.api.metadata.tvdb", "TVDBClient", "tvdb"),
            ("personalscraper.api.metadata.omdb", "OMDBClient", "omdb"),
            ("personalscraper.api.metadata.trakt", "TraktClient", "trakt"),
        ],
    )
    def test_real_client_provider_name(self, import_path: str, class_name: str, expected_provider_name: str) -> None:
        """Real metadata client classes expose the canonical lowercase identifier."""
        import importlib  # noqa: PLC0415

        module = importlib.import_module(import_path)
        client_cls = getattr(module, class_name)
        assert client_cls.provider_name == expected_provider_name, (
            f"{class_name}.provider_name must equal {expected_provider_name!r}; got {client_cls.provider_name!r}."
        )


class TestAtomicCapabilityProtocols:
    """Atomic capability Protocol isinstance checks (DEV #29).

    Each test pins the contract that a class satisfying a single atomic
    capability passes ``isinstance`` against that Protocol — and that a
    class missing the required method does NOT. This replaces the former
    monolithic ``MetadataProvider`` isinstance assertions, whose removal
    is gated on these tests being in place first (sub-phase 5.1 before 5.4).
    """

    # -- Searchable -----------------------------------------------------------

    def test_searchable_passes(self) -> None:
        """A class exposing ``search`` satisfies the Searchable Protocol."""

        class Impl:
            def search(
                self,
                title: str,
                year: int | None = None,
                media_type: str = "movie",
            ) -> list[SearchResult]:
                return []

        assert isinstance(Impl(), Searchable)

    def test_searchable_fails_without_search(self) -> None:
        """A class without ``search`` does NOT satisfy Searchable."""

        class Impl:
            pass

        assert not isinstance(Impl(), Searchable)

    # -- MovieDetailsProvider -------------------------------------------------

    def test_movie_details_provider_passes(self) -> None:
        """A class exposing ``get_movie`` satisfies MovieDetailsProvider."""

        class Impl:
            def get_movie(self, provider_id: str) -> MediaDetails:
                return MediaDetails(provider="test", provider_id=provider_id)

        assert isinstance(Impl(), MovieDetailsProvider)

    def test_movie_details_provider_fails_without_get_movie(self) -> None:
        """A class without ``get_movie`` does NOT satisfy MovieDetailsProvider."""

        class Impl:
            def get_tv(self, provider_id: str) -> MediaDetails:
                return MediaDetails(provider="test", provider_id=provider_id)

        assert not isinstance(Impl(), MovieDetailsProvider)

    # -- TvDetailsProvider ----------------------------------------------------

    def test_tv_details_provider_passes(self) -> None:
        """A class exposing ``get_tv`` satisfies TvDetailsProvider."""

        class Impl:
            def get_tv(self, provider_id: str) -> MediaDetails:
                return MediaDetails(provider="test", provider_id=provider_id)

        assert isinstance(Impl(), TvDetailsProvider)

    def test_tv_details_provider_fails_without_get_tv(self) -> None:
        """A class without ``get_tv`` does NOT satisfy TvDetailsProvider."""

        class Impl:
            def get_movie(self, provider_id: str) -> MediaDetails:
                return MediaDetails(provider="test", provider_id=provider_id)

        assert not isinstance(Impl(), TvDetailsProvider)

    # -- EpisodeFetcher -------------------------------------------------------

    def test_episode_fetcher_passes(self) -> None:
        """A class exposing ``get_episodes`` satisfies EpisodeFetcher."""

        class Impl:
            def get_episodes(self, series_id: str, season: int) -> list[EpisodeInfo]:
                return []

        assert isinstance(Impl(), EpisodeFetcher)

    def test_episode_fetcher_fails_without_get_episodes(self) -> None:
        """A class without ``get_episodes`` does NOT satisfy EpisodeFetcher."""

        class Impl:
            def get_season(self, tv_id: str, season: int) -> SeasonDetails:
                return SeasonDetails(provider="test", tv_id=tv_id, season_number=season)

        assert not isinstance(Impl(), EpisodeFetcher)

    # -- RatingProvider -------------------------------------------------------

    def test_rating_provider_passes(self) -> None:
        """A class exposing ``get_rating`` satisfies RatingProvider."""

        class Impl:
            def get_rating(self, provider_id: str) -> list[Notations] | None:
                return None

        assert isinstance(Impl(), RatingProvider)

    def test_rating_provider_fails_without_get_rating(self) -> None:
        """A class without ``get_rating`` does NOT satisfy RatingProvider."""

        class Impl:
            def get_notations(self, media_id: str, media_type: str) -> Notations | None:
                return None

        assert not isinstance(Impl(), RatingProvider)

    # -- ArtworkProvider ------------------------------------------------------

    def test_artwork_provider_passes(self) -> None:
        """A class exposing ``get_artwork_urls`` satisfies ArtworkProvider."""

        class Impl:
            def get_artwork_urls(self, media_id: str, media_type: str = "movie") -> list[ArtworkItem]:
                return []

        assert isinstance(Impl(), ArtworkProvider)

    def test_artwork_provider_fails_without_get_artwork_urls(self) -> None:
        """A class without ``get_artwork_urls`` does NOT satisfy ArtworkProvider."""

        class Impl:
            pass

        assert not isinstance(Impl(), ArtworkProvider)

    # -- KeywordProvider ------------------------------------------------------

    def test_keyword_provider_passes(self) -> None:
        """A class exposing ``get_keywords`` satisfies KeywordProvider."""

        class Impl:
            def get_keywords(self, media_id: str, media_type: str) -> list[str]:
                return []

        assert isinstance(Impl(), KeywordProvider)

    def test_keyword_provider_fails_without_get_keywords(self) -> None:
        """A class without ``get_keywords`` does NOT satisfy KeywordProvider."""

        class Impl:
            pass

        assert not isinstance(Impl(), KeywordProvider)

    # -- VideoProvider --------------------------------------------------------

    def test_video_provider_passes(self) -> None:
        """A class exposing ``get_videos`` satisfies VideoProvider."""

        class Impl:
            def get_videos(self, media_id: str, media_type: str, language: str) -> list[Video]:
                return []

        assert isinstance(Impl(), VideoProvider)

    def test_video_provider_fails_without_get_videos(self) -> None:
        """A class without ``get_videos`` does NOT satisfy VideoProvider."""

        class Impl:
            pass

        assert not isinstance(Impl(), VideoProvider)

    # -- RecommendationProvider -----------------------------------------------

    def test_recommendation_provider_passes(self) -> None:
        """A class exposing ``get_recommendations`` satisfies RecommendationProvider."""

        class Impl:
            def get_recommendations(self, media_id: str, media_type: str) -> list[Recommendation]:
                return []

        assert isinstance(Impl(), RecommendationProvider)

    def test_recommendation_provider_fails_without_get_recommendations(self) -> None:
        """A class without ``get_recommendations`` does NOT satisfy RecommendationProvider."""

        class Impl:
            pass

        assert not isinstance(Impl(), RecommendationProvider)


class TMDBFakeClient(MetadataClient):
    """Fake client for testing the explicit ``provider_name`` ClassVar contract."""

    provider_name: ClassVar[str] = "tmdbfake"
