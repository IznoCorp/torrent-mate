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
        """fetch_movie_videos returns [] and logs warning on unexpected errors."""
        with patch.object(client, "_get", side_effect=ConnectionError("timeout")):
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
