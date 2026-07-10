"""Tests for the registry status REST route (reg-health feature).

Covers auth guard, response shape, projection-seeded state, roster
baseline fallback, and staging read access.

See docs/features/reg-health/plan/phase-02-rest-route.md §2.2 tests.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.web.registry_projection import RegistryHealthProjection

# Reuse the helper from the pipeline route tests.
from tests.web.test_pipeline_routes import TEST_HASH, TEST_PASSWORD, TEST_USERNAME, _mount_guarded  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def registry_client(test_config) -> TestClient:
    """Create an authenticated ``TestClient`` with the registry route included.

    Builds a minimal FastAPI app (auth + registry routers only under the
    ``guarded_api`` perimeter) so assertions are isolated from other routes.

    Args:
        test_config: Synthetic ``Config`` fixture (has ``tmdb`` and ``tvdb``
            in ``Searchable``, so the roster is non-empty).

    Returns:
        A ``TestClient`` with an active session cookie.
    """
    cfg = test_config.model_copy(
        update={
            "web": test_config.web.model_copy(update={"username": TEST_USERNAME}),
        },
    )
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret="registry-test-secret",
    )

    app = FastAPI()
    app.state.config = cfg
    app.state.settings = settings
    app.state.registry_projection = RegistryHealthProjection()

    # Auth router (login/logout/me) — needed to obtain a session cookie.
    from personalscraper.web.auth.routes import router as auth_router

    app.include_router(auth_router)
    # Registry status route — the subject under test.
    from personalscraper.web.routes.registry import router as registry_router

    _mount_guarded(app, registry_router)

    client = TestClient(app, base_url="https://testserver")
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 204
    return client


# ── Auth guard ─────────────────────────────────────────────────────────────────


class TestAuthGuard:
    """Unauthenticated requests must return 401."""

    def test_unauth_returns_401(self, test_config) -> None:
        """A request without a session cookie → 401."""
        from personalscraper.web.routes.registry import router as registry_router

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        app = FastAPI()
        app.state.config = test_config
        app.state.settings = settings
        app.state.registry_projection = RegistryHealthProjection()
        _mount_guarded(app, registry_router)
        client = TestClient(app)

        resp = client.get("/api/registry/status")
        assert resp.status_code == 401


# ── Happy path ─────────────────────────────────────────────────────────────────


class TestRegistryStatus:
    """Authenticated requests against the registry status endpoint."""

    def test_returns_200_with_providers_array(self, registry_client: TestClient) -> None:
        """An authenticated request → 200 with a ``providers`` list."""
        resp = registry_client.get("/api/registry/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)

    def test_item_shape_matches_contract(self, registry_client: TestClient) -> None:
        """Every provider item has the frozen field set and valid states."""
        resp = registry_client.get("/api/registry/status")
        assert resp.status_code == 200
        providers = resp.json()["providers"]
        assert len(providers) > 0, "test_config providers roster must be non-empty"

        expected_keys = {
            "provider_name",
            "circuit_state",
            "failure_count_recent",
            "last_success_at",
            "last_failure_at",
            "last_latency_ms",
            "live",
        }
        valid_states = {"closed", "open", "half_open"}

        for item in providers:
            assert set(item.keys()) == expected_keys, f"Item keys {set(item.keys())} != {expected_keys}"
            assert item["circuit_state"] in valid_states, (
                f"circuit_state {item['circuit_state']!r} not in {valid_states}"
            )
            assert isinstance(item["failure_count_recent"], int)
            assert isinstance(item["live"], bool)

    def test_projection_seeded_open_surfaces_live_true(self, test_config) -> None:
        """A projection seeded with ``CircuitBreakerOpened`` surfaces ``open`` and ``live=True``."""
        cfg = test_config.model_copy(
            update={
                "web": test_config.web.model_copy(update={"username": TEST_USERNAME}),
            },
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret="seeded-open-secret",
        )

        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings
        projection = RegistryHealthProjection()
        projection.apply(
            "CircuitBreakerOpened",
            {"breaker": "tmdb", "failure_count": 3},
        )
        app.state.registry_projection = projection

        from personalscraper.web.auth.routes import router as auth_router

        app.include_router(auth_router)
        from personalscraper.web.routes.registry import router as registry_router

        _mount_guarded(app, registry_router)

        client = TestClient(app, base_url="https://testserver")
        resp = client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 204

        resp = client.get("/api/registry/status")
        assert resp.status_code == 200
        providers = resp.json()["providers"]

        tmdb = next((p for p in providers if p["provider_name"] == "tmdb"), None)
        assert tmdb is not None, "tmdb must be in the response"
        assert tmdb["circuit_state"] == "open"
        assert tmdb["failure_count_recent"] == 3
        assert tmdb["live"] is True
        assert tmdb["last_failure_at"] is not None

    def test_roster_provider_absent_from_projection_is_baseline(self, registry_client: TestClient) -> None:
        """A roster provider absent from the projection surfaces the optimistic baseline."""
        resp = registry_client.get("/api/registry/status")
        assert resp.status_code == 200
        providers = resp.json()["providers"]

        # The registry_client fixture creates a fresh (empty) projection, so
        # every roster provider should have live=False.
        for item in providers:
            assert item["live"] is False, f"{item['provider_name']}: expected live=False (empty projection)"
            assert item["circuit_state"] == "closed"
            assert item["failure_count_recent"] == 0
            assert item["last_success_at"] is None
            assert item["last_failure_at"] is None
            assert item["last_latency_ms"] is None

    def test_providers_sorted_by_name(self, registry_client: TestClient) -> None:
        """Provider items are sorted alphabetically by ``provider_name``."""
        resp = registry_client.get("/api/registry/status")
        assert resp.status_code == 200
        providers = resp.json()["providers"]
        names = [p["provider_name"] for p in providers]
        assert names == sorted(names), f"Providers not sorted: {names}"


# ── Staging read access ────────────────────────────────────────────────────────


class TestStaging:
    """Registry status is a read — staging must return 200, not 403."""

    def test_staging_returns_200(self, registry_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """``PERSONALSCRAPER_WEB_ROLE=staging`` → 200 (read allowed on staging)."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = registry_client.get("/api/registry/status")
        assert resp.status_code == 200


# ── Fail-soft ──────────────────────────────────────────────────────────────────


class TestFailSoft:
    """The route never returns 500 — failure degrades to an empty list."""

    def test_missing_projection_returns_empty(self, test_config) -> None:
        """Missing projection on app.state returns empty list rather than 500."""
        from personalscraper.web.routes.registry import router as registry_router

        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret="failsoft-secret",
        )
        cfg = test_config.model_copy(
            update={
                "web": test_config.web.model_copy(update={"username": TEST_USERNAME}),
            },
        )

        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings
        # Deliberately omit registry_projection from app.state.

        from personalscraper.web.auth.routes import router as auth_router

        app.include_router(auth_router)
        _mount_guarded(app, registry_router)

        client = TestClient(app, base_url="https://testserver")
        resp = client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 204

        resp = client.get("/api/registry/status")
        assert resp.status_code == 200
        assert resp.json() == {"providers": []}
