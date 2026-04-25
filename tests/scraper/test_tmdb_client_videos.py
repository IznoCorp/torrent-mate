"""Unit tests for TMDBClient.fetch_movie_videos / fetch_tv_videos.

HTTP transport is mocked via unittest.mock.patch on TMDBClient._get.
Fixtures loaded from tests/fixtures/tmdb/.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.scraper.tmdb_client import TMDBClient, TMDBError, Video

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tmdb"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture()
def client() -> TMDBClient:
    """TMDBClient with a dummy API key (no real HTTP)."""
    return TMDBClient(api_key="test-key-placeholder")


# ── fetch_movie_videos ────────────────────────────────────────────────────────


class TestFetchMovieVideos:
    """Tests for TMDBClient.fetch_movie_videos."""

    def test_returns_video_list(self, client):
        """fetch_movie_videos returns a list of Video dataclass instances."""
        fixture = _load("movie_550_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_movie_videos(550, language="en-US")
        assert len(videos) == 2
        assert all(isinstance(v, Video) for v in videos)

    def test_video_fields_populated(self, client):
        """Video fields map correctly from the TMDB response."""
        fixture = _load("movie_550_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_movie_videos(550, language="en-US")
        trailer = next(v for v in videos if v.type == "Trailer")
        assert trailer.key == "6JnN1DmbqoU"
        assert trailer.official is True
        assert trailer.site == "YouTube"
        assert trailer.size == 1080
        assert trailer.iso_639_1 == "en"

    def test_calls_correct_endpoint(self, client):
        """fetch_movie_videos calls /movie/{id}/videos."""
        fixture = _load("movie_550_videos.json")
        mock_get = MagicMock(return_value=fixture)
        with patch.object(client, "_get", mock_get):
            client.fetch_movie_videos(550, language="en-US")
        mock_get.assert_called_once_with("/movie/550/videos", {"language": "en-US"})

    def test_returns_empty_on_404(self, client):
        """fetch_movie_videos returns [] on HTTP 404 (item not found)."""
        with patch.object(client, "_get", side_effect=TMDBError(404, 34, "Not Found")):
            result = client.fetch_movie_videos(99999, language="en-US")
        assert result == []

    def test_returns_empty_on_unexpected_exception(self, client):
        """fetch_movie_videos returns [] and logs warning on transport errors."""
        import requests

        with patch.object(client, "_get", side_effect=requests.ConnectionError("timeout")):
            result = client.fetch_movie_videos(550, language="en-US")
        assert result == []

    def test_empty_results_returns_empty_list(self, client):
        """fetch_movie_videos returns [] when TMDB results list is empty."""
        with patch.object(client, "_get", return_value={"id": 1, "results": []}):
            result = client.fetch_movie_videos(1, language="en-US")
        assert result == []


# ── fetch_tv_videos ───────────────────────────────────────────────────────────


class TestFetchTvVideos:
    """Tests for TMDBClient.fetch_tv_videos."""

    def test_returns_video_list(self, client):
        """fetch_tv_videos returns a list of Video instances."""
        fixture = _load("tv_1399_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_tv_videos(1399, language="en-US")
        assert len(videos) == 1
        assert isinstance(videos[0], Video)

    def test_calls_correct_endpoint(self, client):
        """fetch_tv_videos calls /tv/{id}/videos."""
        fixture = _load("tv_1399_videos.json")
        mock_get = MagicMock(return_value=fixture)
        with patch.object(client, "_get", mock_get):
            client.fetch_tv_videos(1399, language="en-US")
        mock_get.assert_called_once_with("/tv/1399/videos", {"language": "en-US"})

    def test_returns_empty_on_404(self, client):
        """fetch_tv_videos returns [] on HTTP 404."""
        with patch.object(client, "_get", side_effect=TMDBError(404, 34, "Not Found")):
            result = client.fetch_tv_videos(99999, language="en-US")
        assert result == []

    def test_language_override(self, client):
        """fetch_tv_videos passes the language parameter to _get."""
        mock_get = MagicMock(return_value={"id": 1, "results": []})
        with patch.object(client, "_get", mock_get):
            client.fetch_tv_videos(1, language="fr-FR")
        mock_get.assert_called_once_with("/tv/1/videos", {"language": "fr-FR"})


# ── fetch_tv_season_videos ────────────────────────────────────────────────────


class TestFetchTvSeasonVideos:
    """Tests for TMDBClient.fetch_tv_season_videos."""

    def test_fetch_tv_season_videos_returns_videos(self, client):
        """Happy path: season-level fetch returns the canonical Video list."""
        fixture = _load("tv_1399_season_1_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_tv_season_videos(1399, season_number=1, language="en-US")
        assert len(videos) == 1
        assert isinstance(videos[0], Video)
        assert videos[0].key == "BpJYNVhGf1s"

    def test_fetch_tv_season_videos_404_returns_empty(self, client):
        """Fail-soft on 404 — many shows have no season-level videos on TMDB."""
        with patch.object(client, "_get", side_effect=TMDBError(404, 34, "Not Found")):
            result = client.fetch_tv_season_videos(99999, season_number=3, language="en-US")
        assert result == []

    def test_fetch_tv_season_videos_uses_circuit_breaker(self, client):
        """Same circuit breaker (`_get`) covers show- and season-level video fetches.

        Asserted indirectly: the implementation funnels through `_fetch_videos`
        which delegates to `self._get` — the same path show-level fetches use,
        therefore the same `tmdb_videos` breaker (DESIGN §1) applies.
        """
        mock_get = MagicMock(return_value={"id": 1, "results": []})
        with patch.object(client, "_get", mock_get):
            client.fetch_tv_season_videos(1, season_number=2, language="fr-FR")
        mock_get.assert_called_once_with("/tv/1/season/2/videos", {"language": "fr-FR"})


class TestVideoNormalisation:
    """Verify Video.__post_init__ canonical-case normalisation and size validation."""

    def test_site_lowercase_normalised_to_canonical(self):
        """A lower-case "youtube" is normalised to canonical "YouTube"."""
        v = Video(id="x", site="youtube", key="k", type="Trailer", official=True, size=1080, iso_639_1="en")
        assert v.site == "YouTube"

    def test_type_multi_word_preserves_title_case(self):
        """Multi-word "behind the scenes" must become "Behind the Scenes" (NOT .capitalize())."""
        # `.capitalize()` would corrupt this to "Behind the scenes" and break
        # downstream filters that match against the TMDB-canonical "Behind the Scenes".
        v = Video(
            id="x",
            site="YouTube",
            key="k",
            type="behind the scenes",
            official=False,
            size=720,
            iso_639_1="en",
        )
        assert v.type == "Behind the Scenes"

    def test_unknown_type_passed_through(self):
        """An unrecognised type is preserved verbatim (not silently rewritten)."""
        v = Video(
            id="x",
            site="YouTube",
            key="k",
            type="Custom Promo",
            official=False,
            size=720,
            iso_639_1="en",
        )
        # No mapping for "custom promo" → original value preserved.
        assert v.type == "Custom Promo"

    def test_zero_size_rejected(self):
        """Video.size must be > 0 — zero is rejected (TMDB never returns 0)."""
        with pytest.raises(ValueError, match="must be > 0"):
            Video(id="x", site="YouTube", key="k", type="Trailer", official=True, size=0, iso_639_1="en")

    def test_negative_size_rejected(self):
        """Video.size must be > 0 — a negative integer is rejected."""
        with pytest.raises(ValueError, match="must be > 0"):
            Video(id="x", site="YouTube", key="k", type="Trailer", official=True, size=-1, iso_639_1="en")
