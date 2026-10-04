"""The standalone v1 server: the v1 sub-application alone, at ``/api/v1``, behind a reverse proxy.

The process the dev interface talks to serves v1 and nothing else: no v0 route, no SPA.
It trusts the proxy headers of its own reverse proxy only, so the perimeter's
cross-origin check compares an ``https`` Origin with the scheme the proxy received.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from personalscraper.app.accounts.passwords import hash_password
from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.composition import build_app_services
from personalscraper.app.services import AppServices
from personalscraper.app.store.store import build_app_store
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1 import standalone
from personalscraper.http_v1.standalone import build_standalone_v1_app

_EMAIL = "local@example.org"
_PASSWORD = "a long fallback password"
_PROXIED = "https://tm-design.example.org"
_LOGIN = {"email": _EMAIL, "password": "not the password"}


def _settings() -> Settings:
    """Settings that never read the real ``.env``.

    Returns:
        The settings.
    """
    return Settings(_env_file=None)  # type: ignore[call-arg]


def _seed_password_account(config: Config) -> None:
    """Store one Admin account signing in with ``_PASSWORD`` in the environment's ``app.db``.

    Args:
        config: The synthetic configuration.
    """
    store = build_app_store(config)
    try:
        store.accounts.insert_account(
            AccountRow(
                id="account-local",
                name="Local",
                email=_EMAIL,
                avatar="",
                role_id="admin",
                password_hash=hash_password(_PASSWORD),
                created_at=1.0,
                updated_at=1.0,
            )
        )
    finally:
        store.close()


def test_version_is_served_under_the_prefix(test_config: Config) -> None:
    """``/api/v1/version`` is routed: 401 without a session, 200 once signed in by password."""
    _seed_password_account(test_config)

    # The session cookie may be Secure: the client speaks https, as the proxy does.
    with TestClient(build_standalone_v1_app(test_config, _settings()), base_url="https://testserver") as client:
        anonymous = client.get("/api/v1/version")
        signed_in = client.post("/api/v1/auth/login", json={"email": _EMAIL, "password": _PASSWORD})
        version = client.get("/api/v1/version")

    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == "auth.required"
    assert signed_in.status_code == 200, signed_in.text
    assert version.status_code == 200
    assert set(version.json()) == {"version", "commit"}


def test_nothing_but_v1_is_served(test_config: Config) -> None:
    """No v0 route and no SPA: anything outside ``/api/v1`` is 404."""
    with TestClient(build_standalone_v1_app(test_config, _settings())) as client:
        for path in ("/", "/index.html", "/api/health", "/api/version"):
            assert client.get(path).status_code == 404, path


def test_https_origin_from_the_trusted_proxy_is_the_requests_own(test_config: Config) -> None:
    """Behind the trusted proxy (``X-Forwarded-Proto: https``) the login is not refused as cross-origin."""
    app = build_standalone_v1_app(test_config, _settings(), trusted_proxies="testclient")

    with TestClient(app, base_url="http://tm-design.example.org") as client:
        response = client.post(
            "/api/v1/auth/login", json=_LOGIN, headers={"Origin": _PROXIED, "X-Forwarded-Proto": "https"}
        )

    assert response.status_code == 401
    assert response.json()["code"] == "auth.refused"


def test_https_origin_without_the_proxy_header_is_cross_origin(test_config: Config) -> None:
    """Without ``X-Forwarded-Proto`` the request is ``http``: an ``https`` Origin is another origin."""
    app = build_standalone_v1_app(test_config, _settings(), trusted_proxies="testclient")

    with TestClient(app, base_url="http://tm-design.example.org") as client:
        response = client.post("/api/v1/auth/login", json=_LOGIN, headers={"Origin": _PROXIED})

    assert response.status_code == 403
    assert response.json()["code"] == "request.cross_origin"


def test_proxy_headers_from_an_untrusted_client_are_ignored(test_config: Config) -> None:
    """By default only 127.0.0.1 is trusted: a forged ``X-Forwarded-Proto`` changes nothing."""
    app = build_standalone_v1_app(test_config, _settings())

    with TestClient(app, base_url="http://tm-design.example.org") as client:
        response = client.post(
            "/api/v1/auth/login", json=_LOGIN, headers={"Origin": _PROXIED, "X-Forwarded-Proto": "https"}
        )

    assert response.status_code == 403
    assert response.json()["code"] == "request.cross_origin"


def test_lifespan_exit_closes_the_services(test_config: Config) -> None:
    """The v1 services are closed when the server stops, not before: their ``app.db`` is released."""
    built: list[AppServices] = []

    def _build(config: Config, settings: Settings) -> AppServices:
        """Build the real services and keep them.

        Args:
            config: The configuration.
            settings: The settings.

        Returns:
            The services.
        """
        services = build_app_services(config, settings)
        built.append(services)
        return services

    with patch.object(standalone, "build_app_services", side_effect=_build):
        app = build_standalone_v1_app(test_config, _settings())
    (services,) = built

    # ``AppServices`` is frozen; its ``close`` releases the store, which is watched instead.
    with patch.object(services.app_store, "close", wraps=services.app_store.close) as close:
        with TestClient(app):
            close.assert_not_called()
        close.assert_called_once_with()


def test_no_library_store_is_opened(test_config: Config) -> None:
    """Building and serving v1 creates no indexer database: no migration, no library.db access."""
    _seed_password_account(test_config)
    library_db = Path(test_config.indexer.db_path)
    existed = library_db.exists()

    with TestClient(build_standalone_v1_app(test_config, _settings())) as client:
        client.post("/api/v1/auth/login", json={"email": _EMAIL, "password": _PASSWORD})
        client.get("/api/v1/version")

    assert library_db.exists() is existed
