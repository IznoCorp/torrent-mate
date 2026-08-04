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
            assert data["kind"] == "movie"

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
            assert data["kind"] == "tv"

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
            # §8: the degraded title is an explicit French label, never a bare id.
            assert data["title"] == "Fiche indisponible (TMDB 999)"
            # kind is None — the provider never responded, so we honestly don't know.
            assert data["kind"] is None

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


class TestMediaSheetEmptyTitle:
    """Fix 4a: an empty provider title sets degraded_reason so the banner appears."""

    def test_empty_title_sets_degraded_reason(self, test_config):
        """Provider responds successfully but returns an empty title — the response
        is marked degraded so the UI shows the warning banner alongside the fallback,
        never a confident card with a raw id as its heading (§8)."""
        details = MediaDetails(
            provider="tmdb",
            provider_id="12345",
            title="",  # empty title — the key case
            year=None,
            overview="",
            director=None,
            genres=[],
            trailer_url=None,
            series_status=None,
            episode_count=None,
            external_ids={},
            seasons=[],
        )
        fake = MagicMock()
        fake.provider_name = "tmdb"
        fake.get_movie.return_value = details
        fake.get_tv = MagicMock()

        with (
            patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake),
            patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/12345?kind=movie")
            assert resp.status_code == 200
            data = resp.json()
            # degraded_reason is set because the title is empty.
            assert data["degraded_reason"] is not None
            assert "n'a pas retourne de titre" in data["degraded_reason"]
            # The title is the fallback (bare id) but the banner IS present.
            assert data["title"] == "12345"


class TestMediaSheetKindHint:
    """Regression tests for the *kind* query parameter (Defect 1 fix)."""

    def test_kind_movie_skips_get_tv(self, test_config):
        """When kind='movie', get_tv is never called — avoids wasted round-trip."""
        details = _make_details_movie()
        fake = MagicMock()
        fake.provider_name = "tmdb"
        fake.get_movie.return_value = details
        fake.get_tv = MagicMock()

        with (
            patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake),
            patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/550?kind=movie")
            assert resp.status_code == 200
            assert fake.get_tv.call_count == 0
            assert fake.get_movie.call_count == 1
            data = resp.json()
            assert data["title"] == "Fight Club"

    def test_kind_tv_skips_get_movie(self, test_config):
        """When kind='tv', get_movie is never called."""
        details = _make_details_tv()
        fake = MagicMock()
        fake.provider_name = "tvdb"
        fake.get_tv.return_value = details
        fake.get_movie = MagicMock()

        with (
            patch("personalscraper.web.routes.media._build_tvdb_client", return_value=fake),
            patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tvdb/255968?kind=tv")
            assert resp.status_code == 200
            assert fake.get_movie.call_count == 0
            assert fake.get_tv.call_count == 1

    def test_invalid_kind_returns_422(self, test_config):
        """An invalid kind value is rejected by FastAPI validation."""
        client = _make_authenticated_client(test_config)
        resp = client.get("/api/media/tmdb/550?kind=unknown")
        assert resp.status_code == 422

    def test_circuit_open_error_degrades_no_fallback(self, test_config):
        """CircuitOpenError from get_tv must NOT trigger get_movie — degrade immediately."""
        from personalscraper.core._contracts import CircuitOpenError

        fake = MagicMock()
        fake.provider_name = "tmdb"
        fake.get_tv.side_effect = CircuitOpenError("TMDB", 120.0)
        fake.get_movie = MagicMock()

        with patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["degraded_reason"] is not None
            assert "n'a pas repondu" in data["degraded_reason"]
            # Crucially: get_movie was NEVER called.
            fake.get_movie.assert_not_called()

    def test_api_404_triggers_movie_fallback(self, test_config):
        """A genuine 404 from get_tv triggers get_movie — this is the no-hint fallback."""
        from personalscraper.core._contracts import ApiError

        movie_details = _make_details_movie()
        fake = MagicMock()
        fake.provider_name = "tmdb"
        fake.get_tv.side_effect = ApiError(provider="TMDB", http_status=404, message="Not Found")
        fake.get_movie.return_value = movie_details

        with (
            patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake),
            patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/550")
            assert resp.status_code == 200
            assert fake.get_tv.call_count == 1
            assert fake.get_movie.call_count == 1
            assert resp.json()["title"] == "Fight Club"

    def test_api_401_degrades_no_fallback(self, test_config):
        """Auth error (401) from get_tv degrades — no get_movie call."""
        from personalscraper.core._contracts import ApiError

        fake = MagicMock()
        fake.provider_name = "tmdb"
        fake.get_tv.side_effect = ApiError(provider="TMDB", http_status=401, message="Unauthorized")
        fake.get_movie = MagicMock()

        with patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/999")
            assert resp.status_code == 200
            assert resp.json()["degraded_reason"] is not None
            fake.get_movie.assert_not_called()


class TestMediaSheetCacheBound:
    """Regression tests for cache bounding (Defect 2 fix)."""

    def test_cache_never_exceeds_max(self, test_config):
        """Inserting _CACHE_MAX + 10 keys leaves at most _CACHE_MAX entries."""
        from personalscraper.web.routes import media as media_routes

        details = _make_details_movie()
        cache_max = media_routes._CACHE_MAX
        fake = MagicMock()
        fake.provider_name = "tmdb"
        fake.get_tv.side_effect = Exception("not TV")
        fake.get_movie.return_value = details

        with (
            patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake),
            patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
        ):
            client = _make_authenticated_client(test_config)
            for i in range(cache_max + 10):
                resp = client.get(f"/api/media/tmdb/{i}")
                assert resp.status_code == 200

        assert len(media_routes._cache) <= cache_max


class TestMediaSheetOwnershipTvEmptyCatalog:
    """Defect 3 regression: TV series with empty seasons catalog uses owned_pairs.

    Not owns(kind='movie') — the provider method that succeeded (not the
    catalog length) decides the ownership kind.
    """

    def test_tv_empty_catalog_uses_owned_pairs(self, test_config):
        """TV with seasons=[] calls owned_pairs, never owns(kind='movie')."""
        details = MediaDetails(
            provider="tvdb",
            provider_id="475278",
            title="Top Chef Le Concours Parallele",
            year=2024,
            overview="",
            director=None,
            genres=["Reality"],
            trailer_url=None,
            series_status="Returning Series",
            episode_count=0,
            external_ids={"tmdb": "315820"},
            seasons=[],  # EMPTY catalog — the key case
        )
        fake = MagicMock()
        fake.provider_name = "tvdb"
        fake.get_tv.return_value = details

        # Create a fake library.db so the existence check passes.
        db_path = test_config.indexer.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch()

        mock_checker = MagicMock()
        mock_checker.owned_pairs.return_value = {(1, 1), (1, 2)}

        with (
            patch("personalscraper.web.routes.media._build_tvdb_client", return_value=fake),
            patch(
                "personalscraper.indexer.ownership.IndexerOwnershipChecker",
                return_value=mock_checker,
            ),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tvdb/475278?kind=tv")
            assert resp.status_code == 200

            # owned_pairs was called (TV path).
            mock_checker.owned_pairs.assert_called_once()
            # owns(kind="movie") was NEVER called.
            mock_checker.owns.assert_not_called()

            data = resp.json()
            # Empty seasons list but ownership block exists.
            assert data["ownership"]["seasons"] == []
            # owned is True because owned_pairs returned data.
            assert data["ownership"]["owned"] is True


class TestMediaSheetResolvedKind:
    """Defect: the server exposes the resolved media kind, not a client-side guess.

    The provider method that succeeded (get_tv vs get_movie) is the ground truth.
    The frontend must never infer this from signals like seasons length or
    series_status — those can all be empty/null for a real TV series.
    """

    def test_tv_zero_signals_returns_kind_tv(self, test_config):
        """TV with no season catalog, no status, no episode count → kind == "tv".

        Top Chef Le Concours Parallele (TVDB 475278) is the real instance:
        0 episodes, 0 seasons, and no series_status in the provider payload.
        The old client-side heuristic (data.series_status !== null || …) would
        return false and render the series as a film.
        """
        details = MediaDetails(
            provider="tvdb",
            provider_id="475278",
            title="Top Chef Le Concours Parallele",
            year=2024,
            overview="",
            director=None,
            genres=["Reality"],
            trailer_url=None,
            series_status=None,  # absent from provider
            episode_count=None,  # absent from provider
            external_ids={"tmdb": "315820"},
            seasons=[],  # empty catalog
        )
        fake = MagicMock()
        fake.provider_name = "tvdb"
        fake.get_tv.return_value = details

        with (
            patch("personalscraper.web.routes.media._build_tvdb_client", return_value=fake),
            patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tvdb/475278?kind=tv")
            assert resp.status_code == 200
            data = resp.json()
            # The SERVER knows this is a TV series — get_tv succeeded.
            assert data["kind"] == "tv"
            # All heuristic signals are absent — proving the client can't infer.
            assert data["series_status"] is None
            assert data["episode_count"] is None
            assert data["seasons"] == []

    def test_movie_returns_kind_movie(self, test_config):
        """A movie lookup (get_movie succeeded) returns kind == "movie"."""
        details = _make_details_movie()
        fake = MagicMock()
        fake.provider_name = "tmdb"
        fake.get_movie.return_value = details
        fake.get_tv = MagicMock()

        with (
            patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake),
            patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
        ):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/550?kind=movie")
            assert resp.status_code == 200
            assert resp.json()["kind"] == "movie"

    def test_degraded_returns_kind_none(self, test_config):
        """Provider failure → kind is None (honest "we don't know")."""
        fake = _fake_tmdb_client(None)
        fake.get_movie.side_effect = Exception("Connection refused")
        with patch("personalscraper.web.routes.media._build_tmdb_client", return_value=fake):
            client = _make_authenticated_client(test_config)
            resp = client.get("/api/media/tmdb/999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["degraded_reason"] is not None
            assert data["kind"] is None
