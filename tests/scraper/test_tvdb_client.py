"""Tests for the TVDB API client.

Tests authentication, re-login, search, details, artworks, and
cross-reference ID extraction. Uses mocked HTTP responses.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from personalscraper.scraper.tvdb_client import (
    ARTWORK_BACKGROUND_SERIES,
    ARTWORK_POSTER_SEASON,
    ARTWORK_POSTER_SERIES,
    TVDB_SOURCE_IMDB,
    TVDB_SOURCE_TMDB_TV,
    TVDBClient,
    TVDBError,
    _is_retryable,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> TVDBClient:
    """Create a TVDBClient with a fake API key (not logged in)."""
    return TVDBClient(api_key="fake-tvdb-key")


@pytest.fixture
def logged_in_client() -> TVDBClient:
    """Create a TVDBClient that is already logged in."""
    c = TVDBClient(api_key="fake-tvdb-key")
    c._token = "fake-jwt-token"
    c._session.headers["Authorization"] = "Bearer fake-jwt-token"
    return c


def _mock_response(
    status_code: int = 200,
    json_data: dict | list | None = None,
    reason: str = "OK",
) -> MagicMock:
    """Build a mock requests.Response.

    Args:
        status_code: HTTP status code.
        json_data: JSON body to return.
        reason: HTTP reason phrase.

    Returns:
        A mock response object.
    """
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 400
    resp.reason = reason
    resp.headers = {}
    resp.json.return_value = json_data if json_data is not None else {}

    def raise_for_status() -> None:
        if status_code >= 400:
            error = requests.exceptions.HTTPError(response=resp)
            error.response = resp
            raise error

    resp.raise_for_status = raise_for_status
    return resp


# ---------------------------------------------------------------------------
# _is_retryable
# ---------------------------------------------------------------------------

class TestIsRetryable:
    """Tests for the _is_retryable predicate."""

    def test_retry_on_429(self) -> None:
        """Rate limit should be retried."""
        resp = _mock_response(429)
        exc = requests.exceptions.HTTPError(response=resp)
        exc.response = resp
        assert _is_retryable(exc) is True

    @pytest.mark.parametrize("code", [500, 502, 503, 504])
    def test_retry_on_5xx(self, code: int) -> None:
        """Server errors should be retried."""
        resp = _mock_response(code)
        exc = requests.exceptions.HTTPError(response=resp)
        exc.response = resp
        assert _is_retryable(exc) is True

    @pytest.mark.parametrize("code", [400, 401, 404])
    def test_no_retry_on_client_errors(self, code: int) -> None:
        """Client errors should NOT be retried (401 handled by re-login)."""
        resp = _mock_response(code)
        exc = requests.exceptions.HTTPError(response=resp)
        exc.response = resp
        assert _is_retryable(exc) is False

    def test_retry_on_connection_error(self) -> None:
        """Connection errors should be retried."""
        assert _is_retryable(requests.exceptions.ConnectionError()) is True

    def test_retry_on_timeout(self) -> None:
        """Timeout errors should be retried."""
        assert _is_retryable(requests.exceptions.Timeout()) is True


# ---------------------------------------------------------------------------
# TVDBClient — login
# ---------------------------------------------------------------------------

class TestTVDBClientLogin:
    """Tests for TVDB authentication."""

    def test_successful_login(self, client: TVDBClient) -> None:
        """Login should store the JWT token."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": {"token": "jwt-token-123"},
        })

        with patch.object(client._session, "post", return_value=mock_resp):
            client.login()

        assert client._token == "jwt-token-123"
        assert client._session.headers["Authorization"] == "Bearer jwt-token-123"

    def test_login_posts_apikey_only(self, client: TVDBClient) -> None:
        """Login should send apikey only (no PIN for Negotiated Contract)."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": {"token": "jwt-token"},
        })

        with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
            client.login()

        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"apikey": "fake-tvdb-key"}
        assert "pin" not in kwargs["json"]

    def test_login_invalid_key(self, client: TVDBClient) -> None:
        """Invalid API key should raise TVDBError."""
        mock_resp = _mock_response(401, {
            "status": "failure",
            "message": "InvalidAPIKey: apikey invalid",
            "data": None,
        })

        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(TVDBError) as exc_info:
                client.login()

        assert exc_info.value.http_status == 401
        assert "apikey invalid" in exc_info.value.message

    def test_login_pin_required(self, client: TVDBClient) -> None:
        """PIN required error should raise TVDBError."""
        mock_resp = _mock_response(400, {
            "status": "failure",
            "message": "InvalidValueType: pin required",
            "data": None,
        })

        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(TVDBError) as exc_info:
                client.login()

        assert exc_info.value.http_status == 400


# ---------------------------------------------------------------------------
# TVDBClient._get — base HTTP with auto-login
# ---------------------------------------------------------------------------

class TestTVDBClientGet:
    """Tests for the base _get() HTTP method."""

    def test_auto_login_on_first_request(self, client: TVDBClient) -> None:
        """First _get() should trigger login() automatically."""
        login_resp = _mock_response(200, {
            "status": "success",
            "data": {"token": "auto-token"},
        })
        data_resp = _mock_response(200, {
            "status": "success",
            "data": {"name": "Test Series"},
        })

        with patch.object(client._session, "post", return_value=login_resp), \
             patch.object(client._session, "get", return_value=data_resp):
            result = client._get("/series/1")

        assert result == {"name": "Test Series"}
        assert client._token == "auto-token"

    def test_relogin_on_401(self, logged_in_client: TVDBClient) -> None:
        """401 should trigger re-login and retry."""
        resp_401 = _mock_response(401, {"message": "Unauthorized"})
        login_resp = _mock_response(200, {
            "status": "success",
            "data": {"token": "new-token"},
        })
        resp_200 = _mock_response(200, {
            "status": "success",
            "data": {"name": "Success"},
        })

        with patch.object(logged_in_client._session, "post", return_value=login_resp), \
             patch.object(
                 logged_in_client._session, "get",
                 side_effect=[resp_401, resp_200],
             ):
            result = logged_in_client._get("/series/1")

        assert result == {"name": "Success"}
        assert logged_in_client._token == "new-token"

    def test_404_raises_tvdb_error(self, logged_in_client: TVDBClient) -> None:
        """404 should raise TVDBError (not retried)."""
        mock_resp = _mock_response(404, {"message": "Record not found"})

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            with pytest.raises(TVDBError) as exc_info:
                logged_in_client._get("/series/999999")

        assert exc_info.value.http_status == 404

    def test_successful_get(self, logged_in_client: TVDBClient) -> None:
        """Successful GET should return the data field."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": {"id": 42, "name": "Test"},
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            result = logged_in_client._get("/test")

        assert result == {"id": 42, "name": "Test"}


# ---------------------------------------------------------------------------
# TVDBClient — language mapping
# ---------------------------------------------------------------------------

class TestTVDBClientLangMap:
    """Tests for language code mapping."""

    def test_fr_to_fra(self, client: TVDBClient) -> None:
        """2-char 'fr' should map to 3-char 'fra'."""
        assert client._map_lang("fr") == "fra"

    def test_en_to_eng(self, client: TVDBClient) -> None:
        """2-char 'en' should map to 3-char 'eng'."""
        assert client._map_lang("en") == "eng"

    def test_already_3_chars(self, client: TVDBClient) -> None:
        """3-char codes should pass through unchanged."""
        assert client._map_lang("fra") == "fra"

    def test_unknown_2_char(self, client: TVDBClient) -> None:
        """Unknown 2-char codes should pass through unchanged."""
        assert client._map_lang("xx") == "xx"


# ---------------------------------------------------------------------------
# TVDBClient — search
# ---------------------------------------------------------------------------

class TestTVDBClientSearch:
    """Tests for search_series()."""

    def test_search_series_basic(self, logged_in_client: TVDBClient) -> None:
        """search_series should query /search with type=series."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": [
                {"tvdb_id": "81189", "name": "Breaking Bad", "year": "2008"},
            ],
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            results = logged_in_client.search_series("Breaking Bad")

        assert len(results) == 1
        assert results[0]["tvdb_id"] == "81189"
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["query"] == "Breaking Bad"
        assert kwargs["params"]["type"] == "series"

    def test_search_series_with_year(self, logged_in_client: TVDBClient) -> None:
        """Year parameter should be passed to the API."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": [{"tvdb_id": "356882", "name": "Lupin"}],
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            logged_in_client.search_series("Lupin", year=2021)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["year"] == 2021

    def test_search_series_empty(self, logged_in_client: TVDBClient) -> None:
        """Empty search should return empty list."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": [],
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            results = logged_in_client.search_series("xyznonexistent")

        assert results == []

    def test_search_protocol_dispatches(self, logged_in_client: TVDBClient) -> None:
        """Protocol search() should use search_series."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": [{"tvdb_id": "81189"}],
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            results = logged_in_client.search("Breaking Bad", media_type="tv")

        assert len(results) == 1
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["type"] == "series"


# ---------------------------------------------------------------------------
# TVDBClient — details
# ---------------------------------------------------------------------------

# Sample TVDB series response (abbreviated)
SAMPLE_SERIES = {
    "id": 81189,
    "name": "Breaking Bad",
    "slug": "breaking-bad",
    "firstAired": "2008-01-20",
    "status": {"name": "Ended"},
    "averageRuntime": 47,
    "genres": [{"name": "Drama"}, {"name": "Thriller"}],
    "seasons": [
        {"id": 29781, "number": 1, "type": {"name": "Aired Order"}},
        {"id": 29782, "number": 2, "type": {"name": "Aired Order"}},
    ],
    "remoteIds": [
        {"id": "tt0903747", "type": TVDB_SOURCE_IMDB, "sourceName": "IMDB"},
        {"id": "1396", "type": TVDB_SOURCE_TMDB_TV, "sourceName": "TheMovieDB.com"},
    ],
    "contentRatings": [
        {"name": "TV-MA", "country": "usa"},
        {"name": "-16", "country": "fra"},
    ],
    # short=true sets these to null
    "artworks": None,
    "characters": None,
    "trailers": None,
}

SAMPLE_EPISODES = {
    "series": {"id": 81189},
    "episodes": [
        {
            "id": 349232,
            "name": "Pilot",
            "number": 1,
            "seasonNumber": 1,
            "aired": "2008-01-20",
            "runtime": 58,
            "overview": "Walter White begins...",
            "image": "https://artworks.thetvdb.com/banners/...",
        },
        {
            "id": 349233,
            "name": "Cat's in the Bag...",
            "number": 2,
            "seasonNumber": 1,
            "aired": "2008-01-27",
            "runtime": 48,
            "overview": "Walt and Jesse...",
            "image": None,
        },
    ],
}

SAMPLE_TRANSLATION = {
    "name": "Épisode pilote",
    "overview": "Walter White commence...",
    "language": "fra",
}


class TestTVDBClientDetails:
    """Tests for get_series(), get_season_episodes(), and get_episode_translation()."""

    def test_get_series_short_mode(self, logged_in_client: TVDBClient) -> None:
        """get_series should request extended with short=true."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_SERIES,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            result = logged_in_client.get_series(81189)

        _, kwargs = mock_get.call_args
        assert "/series/81189/extended" in mock_get.call_args[0][0]
        assert kwargs["params"]["short"] == "true"

    def test_get_series_returns_genres(self, logged_in_client: TVDBClient) -> None:
        """get_series should include genres."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_SERIES,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            result = logged_in_client.get_series(81189)

        assert len(result["genres"]) == 2
        assert result["genres"][0]["name"] == "Drama"

    def test_get_series_short_null_arrays(self, logged_in_client: TVDBClient) -> None:
        """short=true should set artworks/characters/trailers to null."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_SERIES,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            result = logged_in_client.get_series(81189)

        # short=true sets these to null (not [])
        assert result["artworks"] is None
        assert result["characters"] is None

    def test_get_season_episodes(self, logged_in_client: TVDBClient) -> None:
        """get_season_episodes should return filtered episodes."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_EPISODES,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            episodes = logged_in_client.get_season_episodes(81189, 1)

        assert len(episodes) == 2
        assert episodes[0]["name"] == "Pilot"
        assert episodes[0]["runtime"] == 58
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["season"] == 1
        assert kwargs["params"]["page"] == 0

    def test_get_episode_translation_fr(self, logged_in_client: TVDBClient) -> None:
        """get_episode_translation should return translated title/overview."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_TRANSLATION,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            result = logged_in_client.get_episode_translation(349232, "fra")

        assert result["name"] == "Épisode pilote"
        assert "/episodes/349232/translations/fra" in mock_get.call_args[0][0]

    def test_get_episode_translation_2char_code(self, logged_in_client: TVDBClient) -> None:
        """2-char language codes should be auto-converted to 3-char."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_TRANSLATION,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            logged_in_client.get_episode_translation(349232, "fr")

        assert "/translations/fra" in mock_get.call_args[0][0]

    def test_get_episode_translation_404(self, logged_in_client: TVDBClient) -> None:
        """Missing translation should return None (not raise)."""
        mock_resp = _mock_response(404, {"message": "Record not found"})

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            result = logged_in_client.get_episode_translation(349232, "fra")

        assert result is None


# ---------------------------------------------------------------------------
# TVDBClient — artworks and cross-reference IDs
# ---------------------------------------------------------------------------

SAMPLE_ARTWORKS_RESPONSE = {
    "artworks": [
        {"id": 1, "image": "https://artworks.thetvdb.com/poster1.jpg", "type": ARTWORK_POSTER_SERIES, "language": "eng", "score": 10, "season": None},
        {"id": 2, "image": "https://artworks.thetvdb.com/bg1.jpg", "type": ARTWORK_BACKGROUND_SERIES, "language": None, "score": 8, "season": None},
        {"id": 3, "image": "https://artworks.thetvdb.com/s1_poster.jpg", "type": ARTWORK_POSTER_SEASON, "language": "eng", "score": 5, "season": 1},
    ],
}


class TestTVDBClientArtworks:
    """Tests for get_series_artworks(), get_artwork_types(), and get_remote_ids()."""

    def test_get_series_artworks(self, logged_in_client: TVDBClient) -> None:
        """get_series_artworks should extract artworks from extended record."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_ARTWORKS_RESPONSE,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            artworks = logged_in_client.get_series_artworks(81189)

        assert len(artworks) == 3
        assert artworks[0]["image"] == "https://artworks.thetvdb.com/poster1.jpg"

    def test_get_series_artworks_with_type_filter(self, logged_in_client: TVDBClient) -> None:
        """get_series_artworks should pass type filter to API."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": {"artworks": [{"id": 1, "type": ARTWORK_POSTER_SERIES}]},
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            logged_in_client.get_series_artworks(81189, type_id=ARTWORK_POSTER_SERIES)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["type"] == ARTWORK_POSTER_SERIES

    def test_get_artwork_types_cached(self, logged_in_client: TVDBClient) -> None:
        """get_artwork_types should cache results after first call."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": [
                {"id": 2, "name": "Poster"},
                {"id": 3, "name": "Background"},
            ],
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp) as mock_get:
            types1 = logged_in_client.get_artwork_types()
            types2 = logged_in_client.get_artwork_types()

        # Should only call API once (cached)
        assert mock_get.call_count == 1
        assert types1 == {2: "Poster", 3: "Background"}
        assert types1 is types2

    def test_get_remote_ids_imdb_and_tmdb(self) -> None:
        """get_remote_ids should extract IMDB and TMDB IDs."""
        ids = TVDBClient.get_remote_ids(SAMPLE_SERIES)
        assert ids["imdb_id"] == "tt0903747"
        assert ids["tmdb_id"] == "1396"

    def test_get_remote_ids_missing(self) -> None:
        """get_remote_ids should return None for missing IDs."""
        data = {"remoteIds": []}
        ids = TVDBClient.get_remote_ids(data)
        assert ids["imdb_id"] is None
        assert ids["tmdb_id"] is None

    def test_get_remote_ids_null_remote_ids(self) -> None:
        """get_remote_ids should handle null remoteIds (short=true)."""
        data = {"remoteIds": None}
        ids = TVDBClient.get_remote_ids(data)
        assert ids["imdb_id"] is None
        assert ids["tmdb_id"] is None

    def test_get_artwork_urls_protocol(self, logged_in_client: TVDBClient) -> None:
        """Protocol get_artwork_urls should map TVDB types to standard types."""
        mock_resp = _mock_response(200, {
            "status": "success",
            "data": SAMPLE_ARTWORKS_RESPONSE,
        })

        with patch.object(logged_in_client._session, "get", return_value=mock_resp):
            artworks = logged_in_client.get_artwork_urls(81189)

        types = [a["type"] for a in artworks]
        assert "poster" in types
        assert "landscape" in types  # Background mapped to landscape
        assert "season_poster" in types
        assert len(artworks) == 3
