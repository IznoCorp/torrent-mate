"""Tests for GET /api/media/{provider}/{provider_id} (media-sheet feature D1-D9).

Validates: full response, degraded response (never 500), cache hit,
movie vs TV differences, auth guard, and unknown provider rejection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from personalscraper.api.metadata._base import MediaDetails
from personalscraper.config import Settings
from personalscraper.web.auth.passwords import hash_password
from tests.web._web_harness import guarded_client

TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"
TEST_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture(autouse=True)
def _clear_media_cache():
    """Clear the module-level media sheet cache between tests."""
    from personalscraper.web.routes import media as media_routes

    media_routes._cache.clear()
    yield
    media_routes._cache.clear()


def _make_details_movie():
    """Build a mock MediaDetails for a movie (Fight Club)."""
    return MediaDetails(
        provider="tmdb",
        provider_id="550",
        title="Fight Club",
        year=1999,
        overview="First rule: you do not talk about it.",
        director="David Fincher",
        genres=["Drama", "Thriller"],
        trailer_url=None,
        series_status=None,
        episode_count=None,
        external_ids={"imdb": "tt0137523", "tvdb": "0"},
        seasons=[],
    )


def _make_details_tv():
    """Build a mock MediaDetails for a TV show (Top Chef)."""
    from personalscraper.api.metadata._base import SeasonInfo

    return MediaDetails(
        provider="tvdb",
        provider_id="255968",
        title="Top Chef",
        year=2010,
        overview="Cooking competition.",
        director=None,
        genres=["Reality"],
        trailer_url=None,
        series_status="Returning Series",
        episode_count=300,
        external_ids={"tmdb": "12345", "imdb": "tt1234567"},
        seasons=[
            SeasonInfo(season_number=1, episode_count=12),
            SeasonInfo(season_number=2, episode_count=14),
        ],
    )


def _login(client: TestClient) -> None:
    """Log in with test credentials via POST /api/auth/login."""
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 204


class TestMediaSheetEndpoint:
    """Integration tests for GET /api/media/{provider}/{provider_id}."""

    def test_full_movie_response(self, test_config):
        """200 with full movie metadata when provider responds."""
        details = _make_details_movie()
        with (
            patch(
                "personalscraper.web.routes.media._build_tmdb_client",
                return_value=_fake_tmdb_client(details),
            ),
            patch(
                "personalscraper.web.routes.media._build_ownership_block",
                return_value=None,
            ),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/550")
            assert resp.status_code == 200
            data = resp.json()
            assert data["provider"] == "tmdb"
            assert data["title"] == "Fight Club"
            assert data["director"] == "David Fincher"
            # D4: movie has no series_status
            assert data["series_status"] is None
            assert data["year"] == 1999

    def test_full_tv_response(self, test_config):
        """200 with full TV metadata including series_status."""
        details = _make_details_tv()
        with (
            patch(
                "personalscraper.web.routes.media._build_tvdb_client",
                return_value=_fake_tvdb_client(details),
            ),
            patch(
                "personalscraper.web.routes.media._build_ownership_block",
                return_value=None,
            ),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tvdb/255968")
            assert resp.status_code == 200
            data = resp.json()
            assert data["provider"] == "tvdb"
            assert data["series_status"] == "Returning Series"
            assert len(data["seasons"]) == 2
            assert data["seasons"][0]["season_number"] == 1
            assert data["seasons"][0]["episode_count"] == 12

    def test_degraded_response_on_provider_failure(self, test_config):
        """DESIGN D9: provider failure returns 200 with degraded_reason, NEVER 500."""
        fake = _fake_tmdb_client(None)
        fake.get_movie.side_effect = Exception("Connection refused")
        with patch(
            "personalscraper.web.routes.media._build_tmdb_client",
            return_value=fake,
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["degraded_reason"] is not None
            assert "n'a pas repondu" in data["degraded_reason"]
            # Identity fields still present (D9)
            assert data["provider"] == "tmdb"
            assert data["provider_id"] == "999"

    def test_cache_hit_calls_provider_once(self, test_config):
        """DESIGN D6: two consecutive requests hit the provider ONCE."""
        details = _make_details_movie()
        fake = _fake_tmdb_client(details)
        with (
            patch(
                "personalscraper.web.routes.media._build_tmdb_client",
                return_value=fake,
            ),
            patch(
                "personalscraper.web.routes.media._build_ownership_block",
                return_value=None,
            ),
        ):
            client = _make_authenticated_client(test_config)
            # First call
            resp1 = client.get("/api/media/tmdb/550")
            assert resp1.status_code == 200
            # Second call - should hit cache, not provider
            resp2 = client.get("/api/media/tmdb/550")
            assert resp2.status_code == 200
            # TV is tried first (once), fails, then movie is tried (once)
            assert fake.get_tv.call_count == 1
            assert fake.get_movie.call_count == 1

    def test_unknown_provider_returns_400(self, test_config):
        """Provider not in [tmdb, tvdb] returns 400."""
        client = _make_authenticated_client(test_config)
        resp = client.get("/api/media/imdb/tt0137523")
        assert resp.status_code == 400
        assert "inconnu" in resp.json()["detail"].lower()

    def test_unauthenticated_returns_401(self, test_config):
        """Endpoint is behind the guarded_api perimeter -> 401 without session."""
        from personalscraper.config import Settings
        from personalscraper.web.routes.media import router as media_router
        from tests.web._web_harness import guarded_client as mk_gc

        client = mk_gc(
            config=test_config,
            settings=Settings(_env_file=None),
            routers=media_router,
            with_auth=True,
            https=True,
            login=None,  # no login -> no session cookie
        )
        resp = client.get("/api/media/tmdb/550")
        assert resp.status_code == 401


def _fake_tmdb_client(details):
    """Build a fake TMDB client whose get_movie returns *details*."""
    fake = MagicMock()
    fake.provider_name = "tmdb"
    fake.get_tv.side_effect = Exception("not a TV show")
    fake.get_movie.return_value = details
    return fake


def _fake_tvdb_client(details):
    """Build a fake TVDB client whose get_tv returns *details*."""
    fake = MagicMock()
    fake.provider_name = "tvdb"
    fake.get_tv.return_value = details
    return fake


def _make_authenticated_client(test_config):
    """Return a TestClient logged in with test credentials."""
    web_cfg = test_config.web.model_copy(update={"username": TEST_USERNAME})
    cfg = test_config.model_copy(update={"web": web_cfg})
    settings = Settings(
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret="test-secret",
        tmdb_api_key="fake-tmdb-key",
        tvdb_api_key="fake-tvdb-key",
    )
    return guarded_client(
        config=cfg,
        settings=settings,
        routers=_media_router(),
        with_auth=True,
        https=True,
        login=(TEST_USERNAME, TEST_PASSWORD),
    )


def _media_router():
    """Import the media router (lazy to avoid import-time side effects)."""
    from personalscraper.web.routes.media import router

    return router
