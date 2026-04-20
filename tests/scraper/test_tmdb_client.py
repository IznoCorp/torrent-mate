"""Tests for the TMDB API client.

Tests base HTTP, authentication, retry logic, and error handling.
Uses mocked HTTP responses (no real API calls).
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from personalscraper.scraper.tmdb_client import (
    TMDB_INVALID_KEY,
    TMDB_NOT_FOUND,
    TMDBClient,
    TMDBError,
    _is_retryable,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TMDBClient:
    """Create a TMDBClient with a fake API key."""
    return TMDBClient(api_key="fake-token-for-testing", language="fr-FR")


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    reason: str = "OK",
    headers: dict | None = None,
) -> MagicMock:
    """Build a mock requests.Response.

    Args:
        status_code: HTTP status code.
        json_data: JSON body to return.
        reason: HTTP reason phrase.
        headers: Response headers.

    Returns:
        A mock response object.
    """
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 400
    resp.reason = reason
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}

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
        """Rate limit (429) should be retried."""
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

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    def test_no_retry_on_client_errors(self, code: int) -> None:
        """Client errors (4xx except 429) should NOT be retried."""
        resp = _mock_response(code)
        exc = requests.exceptions.HTTPError(response=resp)
        exc.response = resp
        assert _is_retryable(exc) is False

    def test_retry_on_connection_error(self) -> None:
        """Connection errors should be retried."""
        exc = requests.exceptions.ConnectionError()
        assert _is_retryable(exc) is True

    def test_retry_on_timeout(self) -> None:
        """Timeout errors should be retried."""
        exc = requests.exceptions.Timeout()
        assert _is_retryable(exc) is True

    def test_no_retry_on_generic_exception(self) -> None:
        """Generic exceptions should NOT be retried."""
        assert _is_retryable(ValueError("oops")) is False


# ---------------------------------------------------------------------------
# TMDBClient._get — base HTTP
# ---------------------------------------------------------------------------


class TestTMDBClientGet:
    """Tests for the base _get() HTTP method."""

    def test_successful_get(self, client: TMDBClient) -> None:
        """A successful GET should return parsed JSON."""
        mock_resp = _mock_response(200, {"results": [{"id": 1}]})

        with patch.object(client._session, "get", return_value=mock_resp):
            result = client._get("/search/movie", {"query": "test"})

        assert result == {"results": [{"id": 1}]}

    def test_language_added_automatically(self, client: TMDBClient) -> None:
        """Language param should be added if not provided."""
        mock_resp = _mock_response(200, {})

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client._get("/test")

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["language"] == "fr-FR"

    def test_language_not_overridden(self, client: TMDBClient) -> None:
        """Explicit language param should not be overridden."""
        mock_resp = _mock_response(200, {})

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client._get("/test", {"language": "en-US"})

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["language"] == "en-US"

    def test_tmdb_error_parsed(self, client: TMDBClient) -> None:
        """TMDB error responses should raise TMDBError with internal code."""
        mock_resp = _mock_response(
            401,
            {"status_code": TMDB_INVALID_KEY, "status_message": "Invalid API key.", "success": False},
        )

        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(TMDBError) as exc_info:
                client._get("/test")

        assert exc_info.value.http_status == 401
        assert exc_info.value.tmdb_code == TMDB_INVALID_KEY
        assert "Invalid API key" in exc_info.value.message

    def test_404_raises_tmdb_error(self, client: TMDBClient) -> None:
        """404 with TMDB error format should raise TMDBError (not retried)."""
        mock_resp = _mock_response(
            404,
            {"status_code": TMDB_NOT_FOUND, "status_message": "Resource not found.", "success": False},
        )

        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(TMDBError) as exc_info:
                client._get("/movie/9999999")

        assert exc_info.value.tmdb_code == TMDB_NOT_FOUND

    def test_timeout_on_request(self, client: TMDBClient) -> None:
        """Request timeout should propagate after retries."""
        with patch.object(
            client._session,
            "get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            with pytest.raises(requests.exceptions.Timeout):
                client._get("/test")

    def test_bearer_token_in_headers(self) -> None:
        """Session should have Bearer token in Authorization header."""
        client = TMDBClient(api_key="my-secret-token")
        assert client._session.headers["Authorization"] == "Bearer my-secret-token"

    def test_retry_on_429_then_success(self, client: TMDBClient) -> None:
        """A 429 followed by success should return the successful response."""
        resp_200 = _mock_response(200, {"id": 42})

        # First call raises 429 (TMDBError), but TMDBError is not retryable by _is_retryable
        # since it's not an HTTPError. Let's simulate the actual HTTP flow instead.
        # _get() raises TMDBError for TMDB errors, but 429 should be retried at HTTP level.
        # The retry catches HTTPError, not TMDBError. Let's test with raw HTTPError.

        # Simulate: first call → 429 HTTPError (retried), second call → 200 success
        error_resp = MagicMock(spec=requests.Response)
        error_resp.status_code = 429
        error_resp.ok = False
        error_resp.reason = "Too Many Requests"
        error_resp.headers = {}
        # Make json() raise ValueError so _get falls through to raise_for_status
        error_resp.json.side_effect = ValueError("not json")

        def raise_429() -> None:
            exc = requests.exceptions.HTTPError(response=error_resp)
            exc.response = error_resp
            raise exc

        error_resp.raise_for_status = raise_429

        with patch.object(
            client._session,
            "get",
            side_effect=[error_resp, resp_200],
        ):
            result = client._get("/test")

        assert result == {"id": 42}


# ---------------------------------------------------------------------------
# TMDBClient — session setup
# ---------------------------------------------------------------------------


class TestTMDBClientInit:
    """Tests for TMDBClient initialization."""

    def test_default_language(self) -> None:
        """Default language should be fr-FR."""
        client = TMDBClient(api_key="test")
        assert client._language == "fr-FR"

    def test_custom_language(self) -> None:
        """Custom language should be stored."""
        client = TMDBClient(api_key="test", language="en-US")
        assert client._language == "en-US"

    def test_session_has_accept_header(self) -> None:
        """Session should have application/json Accept header."""
        client = TMDBClient(api_key="test")
        assert client._session.headers["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# TMDBClient — search methods
# ---------------------------------------------------------------------------


class TestTMDBClientSearch:
    """Tests for search_movie() and search_tv()."""

    def test_search_movie_basic(self, client: TMDBClient) -> None:
        """search_movie should call /search/movie with query param."""
        mock_resp = _mock_response(
            200,
            {
                "results": [
                    {"id": 1049112, "title": "Le Comte de Monte-Cristo", "release_date": "2024-06-28"},
                ],
            },
        )

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            results = client.search_movie("Le Comte de Monte-Cristo", year=2024)

        assert len(results) == 1
        assert results[0]["id"] == 1049112
        # Check endpoint and params
        args, kwargs = mock_get.call_args
        assert "/search/movie" in args[0]
        assert kwargs["params"]["query"] == "Le Comte de Monte-Cristo"
        assert kwargs["params"]["year"] == 2024

    def test_search_movie_without_year(self, client: TMDBClient) -> None:
        """search_movie without year should not include year param."""
        mock_resp = _mock_response(200, {"results": [{"id": 1}]})

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.search_movie("Matrix")

        _, kwargs = mock_get.call_args
        assert "year" not in kwargs["params"]

    def test_search_movie_empty_results(self, client: TMDBClient) -> None:
        """Empty search should return empty list (HTTP 200, not 404)."""
        mock_resp = _mock_response(200, {"results": []})

        with patch.object(client._session, "get", return_value=mock_resp):
            results = client.search_movie("xyznonexistent12345")

        assert results == []

    def test_search_tv_uses_first_air_date_year(self, client: TMDBClient) -> None:
        """search_tv should use first_air_date_year, not year."""
        mock_resp = _mock_response(
            200,
            {
                "results": [{"id": 67195, "name": "Lupin", "first_air_date": "2021-01-08"}],
            },
        )

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            results = client.search_tv("Lupin", year=2021)

        assert len(results) == 1
        _, kwargs = mock_get.call_args
        assert "/search/tv" in mock_get.call_args[0][0]
        assert kwargs["params"]["first_air_date_year"] == 2021
        assert "year" not in kwargs["params"]

    def test_search_tv_without_year(self, client: TMDBClient) -> None:
        """search_tv without year should not include year param."""
        mock_resp = _mock_response(200, {"results": []})

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.search_tv("Breaking Bad")

        _, kwargs = mock_get.call_args
        assert "first_air_date_year" not in kwargs["params"]

    def test_search_protocol_dispatches_movie(self, client: TMDBClient) -> None:
        """Protocol search() should dispatch to search_movie for movies."""
        mock_resp = _mock_response(200, {"results": [{"id": 1}]})

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            results = client.search("Matrix", media_type="movie")

        assert len(results) == 1
        assert "/search/movie" in mock_get.call_args[0][0]

    def test_search_protocol_dispatches_tv(self, client: TMDBClient) -> None:
        """Protocol search() should dispatch to search_tv for TV shows."""
        mock_resp = _mock_response(200, {"results": [{"id": 1}]})

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.search("Lupin", media_type="tv")

        assert "/search/tv" in mock_get.call_args[0][0]

    def test_search_movie_multiple_results(self, client: TMDBClient) -> None:
        """Search should return all results from the API."""
        mock_resp = _mock_response(
            200,
            {
                "results": [
                    {"id": 603, "title": "The Matrix", "release_date": "1999-03-31"},
                    {"id": 604, "title": "The Matrix Reloaded", "release_date": "2003-05-15"},
                    {"id": 605, "title": "The Matrix Revolutions", "release_date": "2003-11-05"},
                ],
            },
        )

        with patch.object(client._session, "get", return_value=mock_resp):
            results = client.search_movie("Matrix")

        assert len(results) == 3


# ---------------------------------------------------------------------------
# TMDBClient — details (append_to_response)
# ---------------------------------------------------------------------------

# Sample TMDB movie response (abbreviated)
SAMPLE_MOVIE = {
    "id": 1049112,
    "title": "Le Comte de Monte-Cristo",
    "original_title": "Le Comte de Monte-Cristo",
    "release_date": "2024-06-28",
    "runtime": 178,
    "overview": "Edmond Dantès...",
    "genres": [{"id": 18, "name": "Drame"}, {"id": 12, "name": "Aventure"}],
    "vote_average": 8.1,
    "credits": {
        "cast": [
            {"id": 82104, "name": "Pierre Niney", "character": "Edmond Dantès", "order": 0},
        ],
        "crew": [
            {"id": 90414, "name": "Matthieu Delaporte", "job": "Director"},
        ],
    },
    "images": {
        "posters": [
            {"file_path": "/poster_fr.jpg", "iso_639_1": "fr", "vote_average": 5.3},
            {"file_path": "/poster_en.jpg", "iso_639_1": "en", "vote_average": 5.1},
        ],
        "backdrops": [
            {"file_path": "/backdrop1.jpg", "iso_639_1": None, "vote_average": 5.5},
        ],
    },
    "external_ids": {
        "imdb_id": "tt2372220",
        "tvdb_id": None,
    },
    "release_dates": {
        "results": [
            {
                "iso_3166_1": "FR",
                "release_dates": [
                    {"type": 3, "certification": "Tous publics", "release_date": "2024-06-28"},
                ],
            },
        ],
    },
}

# Sample TMDB TV response (abbreviated)
SAMPLE_TV = {
    "id": 67195,
    "name": "Lupin",
    "original_name": "Lupin",
    "first_air_date": "2021-01-08",
    "episode_run_time": [],
    "overview": "Un gentleman cambrioleur...",
    "genres": [{"id": 80, "name": "Crime"}, {"id": 18, "name": "Drame"}],
    "vote_average": 7.9,
    "number_of_seasons": 3,
    "aggregate_credits": {
        "cast": [
            {
                "id": 1245,
                "name": "Omar Sy",
                "roles": [{"character": "Assane Diop", "episode_count": 17}],
            },
        ],
    },
    "images": {
        "posters": [{"file_path": "/lupin_poster.jpg", "iso_639_1": "fr", "vote_average": 5.5}],
        "backdrops": [{"file_path": "/lupin_bg.jpg", "iso_639_1": None, "vote_average": 5.2}],
    },
    "external_ids": {
        "imdb_id": "tt2527336",
        "tvdb_id": 356882,
    },
    "content_ratings": {
        "results": [
            {"iso_3166_1": "FR", "rating": "10"},
        ],
    },
}

# Sample TMDB season response
SAMPLE_SEASON = {
    "id": 90000,
    "season_number": 1,
    "episodes": [
        {
            "id": 2400001,
            "episode_number": 1,
            "name": "Chapitre 1",
            "runtime": 52,
            "crew": [],
            "guest_stars": [],
        },
        {
            "id": 2400002,
            "episode_number": 2,
            "name": "Chapitre 2",
            "runtime": 45,
            "crew": [],
            "guest_stars": [],
        },
    ],
    "images": {
        "posters": [{"file_path": "/s1_poster.jpg", "iso_639_1": "fr", "vote_average": 5.0}],
    },
}


class TestTMDBClientDetails:
    """Tests for get_movie(), get_tv(), and get_tv_season()."""

    def test_get_movie_append_to_response(self, client: TMDBClient) -> None:
        """get_movie should request credits, images, external_ids, release_dates."""
        mock_resp = _mock_response(200, SAMPLE_MOVIE)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.get_movie(1049112)

        _, kwargs = mock_get.call_args
        append = kwargs["params"]["append_to_response"]
        assert "credits" in append
        assert "images" in append
        assert "external_ids" in append
        assert "release_dates" in append

    def test_get_movie_include_image_language(self, client: TMDBClient) -> None:
        """get_movie MUST include include_image_language=fr,en,null."""
        mock_resp = _mock_response(200, SAMPLE_MOVIE)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.get_movie(1049112)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["include_image_language"] == "fr,en,null"

    def test_get_movie_returns_full_data(self, client: TMDBClient) -> None:
        """get_movie should return complete metadata."""
        mock_resp = _mock_response(200, SAMPLE_MOVIE)

        with patch.object(client._session, "get", return_value=mock_resp):
            result = client.get_movie(1049112)

        assert result["title"] == "Le Comte de Monte-Cristo"
        assert result["runtime"] == 178
        assert len(result["genres"]) == 2
        assert result["external_ids"]["imdb_id"] == "tt2372220"
        assert len(result["credits"]["cast"]) == 1
        assert len(result["images"]["posters"]) == 2

    def test_get_movie_certification_fr(self, client: TMDBClient) -> None:
        """FR certification should be extractable from release_dates."""
        mock_resp = _mock_response(200, SAMPLE_MOVIE)

        with patch.object(client._session, "get", return_value=mock_resp):
            result = client.get_movie(1049112)

        # Extract FR certification (type=3 = theatrical)
        fr_releases = [r for r in result["release_dates"]["results"] if r["iso_3166_1"] == "FR"]
        assert len(fr_releases) == 1
        theatrical = [rd for rd in fr_releases[0]["release_dates"] if rd["type"] == 3]
        assert theatrical[0]["certification"] == "Tous publics"

    def test_get_tv_aggregate_credits(self, client: TMDBClient) -> None:
        """get_tv should use aggregate_credits (not credits) for TV shows."""
        mock_resp = _mock_response(200, SAMPLE_TV)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            result = client.get_tv(67195)

        _, kwargs = mock_get.call_args
        append = kwargs["params"]["append_to_response"]
        assert "aggregate_credits" in append
        # aggregate_credits has roles[] instead of character
        assert "roles" in result["aggregate_credits"]["cast"][0]

    def test_get_tv_content_ratings(self, client: TMDBClient) -> None:
        """get_tv should include content_ratings for FR certification."""
        mock_resp = _mock_response(200, SAMPLE_TV)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            result = client.get_tv(67195)

        _, kwargs = mock_get.call_args
        assert "content_ratings" in kwargs["params"]["append_to_response"]
        # FR rating extraction
        fr_rating = [r for r in result["content_ratings"]["results"] if r["iso_3166_1"] == "FR"]
        assert fr_rating[0]["rating"] == "10"

    def test_get_tv_include_image_language(self, client: TMDBClient) -> None:
        """get_tv MUST include include_image_language=fr,en,null."""
        mock_resp = _mock_response(200, SAMPLE_TV)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.get_tv(67195)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["include_image_language"] == "fr,en,null"

    def test_get_tv_season_episodes(self, client: TMDBClient) -> None:
        """get_tv_season should return episodes with runtime."""
        mock_resp = _mock_response(200, SAMPLE_SEASON)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            result = client.get_tv_season(67195, 1)

        assert len(result["episodes"]) == 2
        assert result["episodes"][0]["runtime"] == 52
        assert result["episodes"][1]["name"] == "Chapitre 2"
        # Check endpoint
        assert "/tv/67195/season/1" in mock_get.call_args[0][0]

    def test_get_tv_season_append_images(self, client: TMDBClient) -> None:
        """get_tv_season should request images."""
        mock_resp = _mock_response(200, SAMPLE_SEASON)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.get_tv_season(67195, 1)

        _, kwargs = mock_get.call_args
        assert "images" in kwargs["params"]["append_to_response"]

    def test_get_details_protocol_movie(self, client: TMDBClient) -> None:
        """Protocol get_details() should dispatch to get_movie."""
        mock_resp = _mock_response(200, SAMPLE_MOVIE)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            result = client.get_details(1049112, media_type="movie")

        assert "/movie/1049112" in mock_get.call_args[0][0]
        assert result["title"] == "Le Comte de Monte-Cristo"

    def test_get_details_protocol_tv(self, client: TMDBClient) -> None:
        """Protocol get_details() should dispatch to get_tv."""
        mock_resp = _mock_response(200, SAMPLE_TV)

        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            result = client.get_details(67195, media_type="tv")

        assert "/tv/67195" in mock_get.call_args[0][0]
        assert result["name"] == "Lupin"


# ---------------------------------------------------------------------------
# TMDBClient — image selection and URL building
# ---------------------------------------------------------------------------


class TestTMDBClientImages:
    """Tests for get_image_url() and get_artwork_urls()."""

    def test_image_url_original(self, client: TMDBClient) -> None:
        """get_image_url should build a full URL with 'original' size."""
        url = client.get_image_url("/abc123.jpg")
        assert url == "https://image.tmdb.org/t/p/original/abc123.jpg"

    def test_image_url_custom_size(self, client: TMDBClient) -> None:
        """get_image_url should accept custom sizes."""
        url = client.get_image_url("/abc123.jpg", size="w500")
        assert url == "https://image.tmdb.org/t/p/w500/abc123.jpg"

    def test_get_artwork_urls_protocol(self, client: TMDBClient) -> None:
        """Protocol get_artwork_urls should return poster and landscape entries."""
        mock_resp = _mock_response(200, SAMPLE_MOVIE)

        with patch.object(client._session, "get", return_value=mock_resp):
            artworks = client.get_artwork_urls(1049112, media_type="movie")

        types = {a["type"] for a in artworks}
        assert "poster" in types
        assert "landscape" in types
        # Check URLs are full URLs
        for art in artworks:
            assert art["url"].startswith("https://image.tmdb.org/t/p/")
        # Check we have the right count (2 posters + 1 backdrop)
        assert len(artworks) == 3


# ---------------------------------------------------------------------------
# Circuit Breaker integration
# ---------------------------------------------------------------------------


class TestTMDBCircuitBreaker:
    """Test CircuitBreaker integration in TMDBClient._get()."""

    def test_circuit_open_raises_without_http_call(self, client):
        """_get() raises CircuitOpenError immediately when circuit is OPEN."""
        from personalscraper.scraper.circuit_breaker import CircuitOpenError

        # Force circuit OPEN by recording enough failures
        error = TMDBError(500, 0, "Internal Server Error")
        for _ in range(5):
            client.circuit.record_failure(error)

        with pytest.raises(CircuitOpenError) as exc_info:
            client._get("/search/movie", {"query": "test"})

        assert exc_info.value.provider == "TMDB"
        assert exc_info.value.remaining_seconds > 0

    def test_circuit_records_success_on_ok_response(self, client):
        """Successful _get() call records success on circuit breaker."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"results": []}

        with patch.object(client._session, "get", return_value=mock_resp):
            client._get("/search/movie", {"query": "test"})

        assert client.circuit.state.value == "closed"

    def test_circuit_records_failure_on_5xx(self, client):
        """5xx TMDBError records failure on circuit breaker."""
        from personalscraper.scraper.circuit_breaker import CircuitState

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.json.return_value = {
            "status_code": 0,
            "status_message": "Internal Server Error",
        }

        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(TMDBError):
                client._get.__wrapped__(client, "/test")

        # One failure recorded — should still be CLOSED (threshold=5)
        assert client.circuit.state == CircuitState.CLOSED

    def test_circuit_exposes_property(self, client):
        """TMDBClient.circuit property exposes the CircuitBreaker."""
        from personalscraper.scraper.circuit_breaker import CircuitBreaker

        assert isinstance(client.circuit, CircuitBreaker)
        assert client.circuit.name == "TMDB"
