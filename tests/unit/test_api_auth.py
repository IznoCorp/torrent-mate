"""Tests for AuthMethod implementations."""

import requests

from personalscraper.api.transport._auth import ApiKeyAuth, BearerAuth, LoginAuth, NoAuth


class TestBearerAuth:
    """BearerAuth tests."""

    def test_apply_sets_authorization_header(self) -> None:
        """apply() sets Authorization: Bearer <token>."""
        session = requests.Session()
        auth = BearerAuth("my-token")
        auth.apply(session)
        assert session.headers["Authorization"] == "Bearer my-token"

    def test_auth_params_is_empty(self) -> None:
        """auth_params() returns {}."""
        assert BearerAuth("tok").auth_params() == {}


class TestApiKeyAuthHeader:
    """ApiKeyAuth with location='header'."""

    def test_apply_mutates_session_header(self) -> None:
        """apply() sets the custom header on the session."""
        session = requests.Session()
        auth = ApiKeyAuth("secret", param="x-api-key", location="header")
        auth.apply(session)
        assert session.headers["x-api-key"] == "secret"

    def test_auth_params_is_empty(self) -> None:
        """Header auth has no per-request params."""
        auth = ApiKeyAuth("secret", param="x-api-key", location="header")
        assert auth.auth_params() == {}

    def test_default_param_name(self) -> None:
        """Default param is 'api_key'."""
        session = requests.Session()
        auth = ApiKeyAuth("secret", location="header")
        auth.apply(session)
        assert session.headers["api_key"] == "secret"


class TestApiKeyAuthQuery:
    """ApiKeyAuth with location='query'."""

    def test_apply_does_not_mutate_session(self) -> None:
        """Query auth does not touch the session."""
        session = requests.Session()
        original_headers = dict(session.headers)
        auth = ApiKeyAuth("secret", location="query")
        auth.apply(session)
        assert dict(session.headers) == original_headers

    def test_auth_params_returns_key(self) -> None:
        """auth_params() returns the query param dict."""
        auth = ApiKeyAuth("secret", location="query")
        assert auth.auth_params() == {"api_key": "secret"}

    def test_custom_param_name(self) -> None:
        """Custom param name is used in auth_params()."""
        auth = ApiKeyAuth("trakt-key", param="trakt-api-key", location="query")
        assert auth.auth_params() == {"trakt-api-key": "trakt-key"}


class TestApiKeyAuthValidation:
    """ApiKeyAuth constructor validation."""

    def test_invalid_location_raises(self) -> None:
        """Invalid location raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="location must be"):
            ApiKeyAuth("secret", location="body")


class TestLoginAuth:
    """LoginAuth tests."""

    def test_apply_sets_session_auth(self) -> None:
        """apply() sets session.auth tuple for Basic Auth."""
        session = requests.Session()
        auth = LoginAuth("admin", "pass123")
        auth.apply(session)
        assert session.auth == ("admin", "pass123")

    def test_auth_params_is_empty(self) -> None:
        """auth_params() returns {}."""
        assert LoginAuth("u", "p").auth_params() == {}


class TestNoAuth:
    """NoAuth tests."""

    def test_apply_is_noop(self) -> None:
        """apply() does nothing."""
        session = requests.Session()
        original_headers = dict(session.headers)
        NoAuth().apply(session)
        assert dict(session.headers) == original_headers

    def test_auth_params_is_empty(self) -> None:
        """auth_params() returns {}."""
        assert NoAuth().auth_params() == {}
