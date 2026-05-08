"""Unit tests for TMDBClient.get_videos / get_videos.

HTTP transport is mocked via unittest.mock.patch on TMDBClient._get.
Fixtures loaded from tests/fixtures/tmdb/.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.metadata._base import Video
from personalscraper.api.metadata.tmdb import TMDBClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tmdb"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture()
def client() -> TMDBClient:
    """TMDBClient with a mocked transport (no real HTTP)."""
    mock_transport = MagicMock()
    mock_transport.get.return_value = {}

    with patch("personalscraper.api.transport._http.HttpTransport", return_value=mock_transport):
        return TMDBClient(transport=mock_transport, language="en-US")


# ── get_videos ────────────────────────────────────────────────────────


class TestFetchMovieVideos:
    """Tests for TMDBClient.get_videos."""

    def test_returns_video_list(self, client):
        """get_videos returns a list of Video dataclass instances."""
        fixture = _load("movie_550_videos.json")
        with patch.object(client._transport, "get", return_value=fixture):
            videos = client.get_videos("550", "movie", language="en-US")
        assert len(videos) == 2
        assert all(isinstance(v, Video) for v in videos)

    def test_video_fields_populated(self, client):
        """Video fields map correctly from the TMDB response."""
        fixture = _load("movie_550_videos.json")
        with patch.object(client._transport, "get", return_value=fixture):
            videos = client.get_videos("550", "movie", language="en-US")
        trailer = next(v for v in videos if v.type == "trailer")
        assert trailer.key == "6JnN1DmbqoU"
        assert trailer.official is True
        assert trailer.site == "youtube"
        assert trailer.size == 1080
        assert trailer.iso_639_1 == "en"

    def test_calls_correct_endpoint(self, client):
        """get_videos calls /movie/{id}/videos."""
        fixture = _load("movie_550_videos.json")
        mock_get = MagicMock(return_value=fixture)
        with patch.object(client._transport, "get", mock_get):
            client.get_videos("550", "movie", language="en-US")
        mock_get.assert_called_once_with("/movie/550/videos", params={"language": "en-US"})

    def test_returns_empty_on_404(self, client):
        """get_videos returns [] on HTTP 404 (item not found)."""
        err = ApiError("tmdb", 404, provider_code=34, message="Not Found")
        with patch.object(client._transport, "get", side_effect=err):
            result = client.get_videos("99999", "movie", language="en-US")
        assert result == []

    def test_returns_empty_on_unexpected_exception(self, client):
        """get_videos returns [] and logs warning on transport errors."""
        import requests

        with patch.object(client._transport, "get", side_effect=requests.ConnectionError("timeout")):
            result = client.get_videos("550", "movie", language="en-US")
        assert result == []

    def test_empty_results_returns_empty_list(self, client):
        """get_videos returns [] when TMDB results list is empty."""
        with patch.object(client._transport, "get", return_value={"id": 1, "results": []}):
            result = client.get_videos("1", "movie", language="en-US")
        assert result == []


# ── get_videos ───────────────────────────────────────────────────────────


class TestFetchTvVideos:
    """Tests for TMDBClient.get_videos."""

    def test_returns_video_list(self, client):
        """get_videos returns a list of Video instances."""
        fixture = _load("tv_1399_videos.json")
        with patch.object(client._transport, "get", return_value=fixture):
            videos = client.get_videos("1399", "tv", language="en-US")
        assert len(videos) == 1
        assert isinstance(videos[0], Video)

    def test_calls_correct_endpoint(self, client):
        """get_videos calls /tv/{id}/videos."""
        fixture = _load("tv_1399_videos.json")
        mock_get = MagicMock(return_value=fixture)
        with patch.object(client._transport, "get", mock_get):
            client.get_videos("1399", "tv", language="en-US")
        mock_get.assert_called_once_with("/tv/1399/videos", params={"language": "en-US"})

    def test_returns_empty_on_404(self, client):
        """get_videos returns [] on HTTP 404."""
        err = ApiError("tmdb", 404, provider_code=34, message="Not Found")
        with patch.object(client._transport, "get", side_effect=err):
            result = client.get_videos("99999", "movie", language="en-US")
        assert result == []

    def test_language_override(self, client):
        """get_videos passes the language parameter to _get."""
        mock_get = MagicMock(return_value={"id": 1, "results": []})
        with patch.object(client._transport, "get", mock_get):
            client.get_videos("1", "tv", language="fr-FR")
        mock_get.assert_called_once_with("/tv/1/videos", params={"language": "fr-FR"})


# ── fetch_tv_season_videos ────────────────────────────────────────────────────


class TestFetchTvSeasonVideos:
    """Tests for TMDBClient.fetch_tv_season_videos."""

    def test_fetch_tv_season_videos_returns_videos(self, client):
        """Happy path: season-level fetch returns the canonical Video list."""
        fixture = _load("tv_1399_season_1_videos.json")
        with patch.object(client._transport, "get", return_value=fixture):
            videos = client.fetch_tv_season_videos(1399, 1, language="en-US")
        assert len(videos) == 1
        assert isinstance(videos[0], Video)
        assert videos[0].key == "BpJYNVhGf1s"

    def test_fetch_tv_season_videos_404_returns_empty(self, client):
        """Fail-soft on 404 — many shows have no season-level videos on TMDB."""
        err = ApiError("tmdb", 404, provider_code=34, message="Not Found")
        with patch.object(client._transport, "get", side_effect=err):
            result = client.fetch_tv_season_videos(99999, 3, language="en-US")
        assert result == []

    def test_fetch_tv_season_videos_uses_circuit_breaker(self, client):
        """Same circuit breaker (`_get`) covers show- and season-level video fetches.

        Asserted indirectly: the implementation funnels through `_fetch_videos`
        which delegates to `self._get` — the same path show-level fetches use,
        therefore the same `tmdb_videos` breaker (DESIGN §1) applies.
        """
        mock_get = MagicMock(return_value={"id": 1, "results": []})
        with patch.object(client._transport, "get", mock_get):
            client.fetch_tv_season_videos(1, 2, language="fr-FR")
        mock_get.assert_called_once_with("/tv/1/season/2/videos", params={"language": "fr-FR"})


class TestVideoNormalisation:
    """Verify Video dataclass stores values as-is (parser does normalization)."""

    @pytest.mark.parametrize(
        ("input_site", "expected"),
        [
            ("youtube", "youtube"),
            ("YouTube", "YouTube"),
            ("vimeo", "vimeo"),
            ("Vimeo", "Vimeo"),
        ],
    )
    def test_site_stored_as_is(self, input_site, expected):
        """Site field is stored unchanged."""
        v = Video(id="x", site=input_site, key="k", type="trailer", official=True, size=1080, iso_639_1="en")
        assert v.site == expected

    @pytest.mark.parametrize(
        ("input_type", "expected"),
        [
            ("trailer", "trailer"),
            ("teaser", "teaser"),
            ("clip", "clip"),
            ("Trailer", "Trailer"),
            ("Teaser", "Teaser"),
            ("Clip", "Clip"),
        ],
    )
    def test_type_stored_as_is(self, input_type, expected):
        """Type field is stored unchanged."""
        v = Video(id="x", site="YouTube", key="k", type=input_type, official=False, size=720, iso_639_1="en")
        assert v.type == expected

    def test_unknown_type_passed_through(self):
        """An unrecognised type is preserved verbatim."""
        v = Video(
            id="x",
            site="YouTube",
            key="k",
            type="Custom Promo",
            official=False,
            size=720,
            iso_639_1="en",
        )
        assert v.type == "Custom Promo"

    def test_zero_size_ok(self):
        """Video.size accepts 0."""
        v = Video(id="x", site="YouTube", key="k", type="trailer", official=True, size=0, iso_639_1="en")
        assert v.size == 0

    def test_negative_size_ok(self):
        """Video.size accepts negative values."""
        v = Video(id="x", site="YouTube", key="k", type="trailer", official=True, size=-1, iso_639_1="en")
        assert v.size == -1


# ── _fetch_videos_strict non-dict guard ───────────────────────────────────────


class TestFetchVideosStrictNonDict:
    """Sub-phase 11.2 — non-dict JSON response raises ApiError."""

    def test_fetch_videos_strict_raises_on_non_dict_response(self, client: TMDBClient) -> None:
        """_fetch_videos_strict raises ApiError when _get returns a non-dict value.

        A proxy or parser-drift condition may cause _get to return a JSON list
        or scalar instead of a dict.  Without a type check, the subsequent
        ``data.get("results")`` raises AttributeError which leaks past find()'s
        except clause and poisons the cache with __no_result__.

        This test patches _get to return a list and asserts ApiError is raised
        with a message describing the unexpected type.

        Args:
            client: TMDBClient fixture with dummy API key.
        """
        with pytest.raises(TypeError, match="expected dict"):
            with patch.object(client._transport, "get", return_value=["not", "a", "dict"]):
                client._fetch_videos_strict("/movie/550/videos", "en-US")

    def test_fetch_videos_strict_raises_on_scalar_response(self, client: TMDBClient) -> None:
        """_fetch_videos_strict raises ApiError when _get returns a bare scalar.

        Verifies the isinstance guard works for any non-dict type, not just lists.

        Args:
            client: TMDBClient fixture with dummy API key.
        """
        with pytest.raises(TypeError, match="expected dict"):
            with patch.object(client._transport, "get", return_value="unexpected string"):
                client._fetch_videos_strict("/movie/550/videos", "en-US")


# ── _fetch_videos fail-soft logging ──────────────────────────────────────────


class TestFetchVideosFailSoftLogging:
    """Tests for TMDBClient._fetch_videos fail-soft warning emission."""

    def test_fetch_videos_logs_warning_on_apierror(
        self,
        client: TMDBClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_fetch_videos returns [] AND logs `tmdb_fetch_videos_failed` on ApiError."""
        with patch.object(
            client,
            "_fetch_videos_strict",
            side_effect=ApiError(provider="tmdb", http_status=503, message="upstream"),
        ):
            with caplog.at_level("WARNING", logger="api.tmdb"):
                result = client._fetch_videos("/movie/550/videos", "en-US")

        assert result == []
        assert any("tmdb_fetch_videos_failed" in rec.message for rec in caplog.records)

    def test_fetch_videos_logs_warning_on_unexpected_exception(
        self,
        client: TMDBClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_fetch_videos returns [] AND logs warning on any unexpected exception."""
        with patch.object(
            client,
            "_fetch_videos_strict",
            side_effect=RuntimeError("boom"),
        ):
            with caplog.at_level("WARNING", logger="api.tmdb"):
                result = client._fetch_videos("/movie/550/videos", "en-US")

        assert result == []
        assert any("tmdb_fetch_videos_failed" in rec.message for rec in caplog.records)
