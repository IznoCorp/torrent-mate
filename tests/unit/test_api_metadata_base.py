"""Tests for metadata family base — Protocol + MetadataClient."""

from __future__ import annotations

from typing import ClassVar

import pytest

from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    MetadataClient,
    MetadataProvider,
    Notations,
    Recommendation,
    SearchResult,
    SeasonDetails,
    Video,
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
        with pytest.raises(Exception):
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


class TestMetadataProviderProtocol:
    """MetadataProvider Protocol tests."""

    def test_runtime_checkable(self) -> None:
        """A full provider passes isinstance(..., MetadataProvider)."""

        class FullProvider:
            provider_name = "test"
            REQUIRED_CREDS: list[str] = []

            def search(self, title: str, year: int | None = None, media_type: str = "movie") -> list[SearchResult]:
                return []

            def get_details(self, media_id: str, media_type: str = "movie") -> MediaDetails:
                return MediaDetails(provider="test", provider_id=media_id)

            def get_artwork_urls(self, media_id: str, media_type: str = "movie") -> list[ArtworkItem]:
                return []

            def get_keywords(self, media_id: str, media_type: str) -> list[str]:
                return []

            def get_videos(self, media_id: str, media_type: str, language: str) -> list[Video]:
                return []

            def get_season(self, tv_id: str, season: int) -> SeasonDetails:
                return SeasonDetails(provider="test", tv_id=tv_id, season_number=season)

            def get_notations(self, media_id: str, media_type: str) -> Notations | None:
                return None

            def get_recommendations(self, media_id: str, media_type: str) -> list[Recommendation]:
                return []

        provider = FullProvider()
        assert isinstance(provider, MetadataProvider)

    def test_missing_method_fails(self) -> None:
        """A class missing get_details does NOT pass isinstance check."""

        class BadProvider:
            provider_name = "test"
            REQUIRED_CREDS: list[str] = []

            def search(self, title: str, year: int | None = None, media_type: str = "movie") -> list[SearchResult]:
                return []

        provider = BadProvider()
        assert not isinstance(provider, MetadataProvider)


class TMDBFakeClient(MetadataClient):
    """Fake client for testing the explicit ``provider_name`` ClassVar contract."""

    provider_name: ClassVar[str] = "tmdbfake"
