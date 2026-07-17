"""Shared web-test harness builders (tests-arch consolidation, phase 12).

Centralises the FastAPI app + ``TestClient`` construction that was previously
duplicated across ~26 web test modules.  Three *genuinely different* builder
families are provided and kept separate on purpose — they exercise different
perimeters, so merging them would blur the behavioural contracts the tests
assert on:

* ``make_web_app`` / ``web_client`` — the **full** application built by
  :func:`personalscraper.web.app.create_app` (lifespan, SPA mount, every
  router, the single ``guarded_api`` perimeter).  Used by the auth / health /
  version / relay / config-restart-impact / acquisition-route tests.
* ``build_guarded_app`` / ``guarded_client`` — an **isolated** app that mounts
  only the router(s) under test behind the same ``require_session`` guard
  perimeter (web-ui.md §6).  Used by the pipeline / maintenance / decisions /
  registry-status / staging-media / history route tests that assert on one
  router in isolation.
* ``build_router_app`` — a **minimal** app that mounts a router with no guard
  (used by the config-editor route tests, which authenticate via the
  ``X-Requested-With`` CSRF header rather than a session cookie).
* ``mount_guarded`` — the shared guard-perimeter helper (previously copy-pasted
  verbatim into 7 modules).

These are plain functions (not fixtures) so both the ``tests/web`` and
``tests/unit/web`` trees can import them regardless of conftest scope.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.web.app import create_app
from personalscraper.web.deps import require_session

#: Base URL that replays the ``Secure`` ``tm_session`` cookie across requests.
HTTPS_BASE_URL = "https://testserver"


def _default_settings() -> Settings:
    """Return a default ``Settings`` that never reads the real ``.env`` file."""
    return Settings(_env_file=None)  # type: ignore[call-arg]


def make_web_app(config: Config, settings: Settings | None = None) -> FastAPI:
    """Build the full application via ``create_app`` (all routers + SPA + lifespan).

    Args:
        config: The ``Config`` to build the app with.
        settings: Optional ``Settings`` (default: ``Settings(_env_file=None)``).

    Returns:
        The fully-wired ``FastAPI`` application.
    """
    return create_app(config, settings if settings is not None else _default_settings())


def web_client(
    config: Config,
    settings: Settings | None = None,
    *,
    https: bool = False,
) -> TestClient:
    """Return a ``TestClient`` wrapping the full ``create_app`` application.

    Args:
        config: The ``Config`` to build the app with.
        settings: Optional ``Settings`` (default: ``Settings(_env_file=None)``).
        https: When ``True``, use ``base_url="https://testserver"`` so the
            ``Secure`` session cookie is replayed across requests.

    Returns:
        A ``TestClient`` ready for request assertions.
    """
    app = make_web_app(config, settings)
    if https:
        return TestClient(app, base_url=HTTPS_BASE_URL)
    return TestClient(app)


def mount_guarded(app: FastAPI, *routers: APIRouter) -> None:
    """Mount *routers* behind the session-guard perimeter, mirroring app.py (R14).

    Handlers no longer carry a per-route ``Depends(require_session)`` — the guard
    lives on the parent router only (web-ui.md §6), so isolated test apps must
    reproduce the same perimeter to exercise auth.

    Args:
        app: The ``FastAPI`` app to mount onto.
        *routers: One or more routers to include behind the guard.
    """
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    for router in routers:
        guarded_api.include_router(router)
    app.include_router(guarded_api)


def _as_routers(routers: APIRouter | Iterable[APIRouter]) -> list[APIRouter]:
    """Normalise a single router or an iterable of routers to a list."""
    if isinstance(routers, APIRouter):
        return [routers]
    return list(routers)


def build_guarded_app(
    *,
    config: Config,
    settings: Settings,
    routers: APIRouter | Iterable[APIRouter],
    with_auth: bool = True,
) -> FastAPI:
    """Build an isolated app with *routers* behind the guard perimeter.

    Wires ``config`` and ``settings`` onto ``app.state`` exactly as
    ``create_app`` does, so guarded route handlers resolve them at request time.

    Args:
        config: The ``Config`` — wired onto ``app.state.config``.
        settings: The ``Settings`` — wired onto ``app.state.settings``.
        routers: A single ``APIRouter`` or an iterable of them, mounted behind
            ``require_session``.
        with_auth: When ``True`` (default), also mount the auth router so
            ``/api/auth/login`` is reachable for cookie-based auth.

    Returns:
        The isolated ``FastAPI`` app (not yet wrapped in a ``TestClient``).
    """
    app = FastAPI()
    app.state.config = config
    app.state.settings = settings
    if with_auth:
        from personalscraper.web.auth.routes import router as auth_router

        app.include_router(auth_router)
    mount_guarded(app, *_as_routers(routers))
    return app


def guarded_client(
    *,
    config: Config,
    settings: Settings,
    routers: APIRouter | Iterable[APIRouter],
    with_auth: bool = True,
    https: bool = True,
    login: tuple[str, str] | None = None,
) -> TestClient:
    """Return a ``TestClient`` for an isolated guarded app; optionally log in.

    Args:
        config: The ``Config`` for the isolated app.
        settings: The ``Settings`` for the isolated app.
        routers: Router(s) mounted behind ``require_session``.
        with_auth: When ``True`` (default), mount the auth router.
        https: When ``True`` (default), use ``base_url="https://testserver"``.
        login: ``(username, password)`` — when given, POST ``/api/auth/login``
            and assert 204 so the returned client carries the session cookie.

    Returns:
        A ``TestClient`` (authenticated when *login* is supplied).
    """
    app = build_guarded_app(
        config=config, settings=settings, routers=routers, with_auth=with_auth
    )
    client = TestClient(app, base_url=HTTPS_BASE_URL) if https else TestClient(app)
    if login is not None:
        resp = client.post(
            "/api/auth/login", json={"username": login[0], "password": login[1]}
        )
        assert resp.status_code == 204, f"Login failed: {resp.status_code}"
    return client


def build_router_app(*routers: APIRouter) -> FastAPI:
    """Build a minimal app that mounts *routers* directly (no guard perimeter).

    Used by the config-editor route tests, which authenticate via the
    ``X-Requested-With`` CSRF header rather than a session cookie, so no
    ``require_session`` guard is wired.

    Args:
        *routers: Routers to include directly on the app.

    Returns:
        A minimal ``FastAPI`` app with *routers* mounted.
    """
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    return app
