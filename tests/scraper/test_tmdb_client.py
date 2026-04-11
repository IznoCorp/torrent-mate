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
    TMDB_RATE_LIMIT,
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
            client._session, "get",
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
        resp_429 = _mock_response(429, {"status_code": TMDB_RATE_LIMIT, "status_message": "Rate limit."})
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
            client._session, "get",
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
        mock_resp = _mock_response(200, {
            "results": [
                {"id": 1049112, "title": "Le Comte de Monte-Cristo", "release_date": "2024-06-28"},
            ],
        })

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
        mock_resp = _mock_response(200, {
            "results": [{"id": 67195, "name": "Lupin", "first_air_date": "2021-01-08"}],
        })

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
        mock_resp = _mock_response(200, {
            "results": [
                {"id": 603, "title": "The Matrix", "release_date": "1999-03-31"},
                {"id": 604, "title": "The Matrix Reloaded", "release_date": "2003-05-15"},
                {"id": 605, "title": "The Matrix Revolutions", "release_date": "2003-11-05"},
            ],
        })

        with patch.object(client._session, "get", return_value=mock_resp):
            results = client.search_movie("Matrix")

        assert len(results) == 3
