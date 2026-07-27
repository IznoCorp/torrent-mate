"""Shared fixtures for web backend tests (tm-shell feature).

Provides a ``web_app`` fixture (FastAPI ``TestClient``) wired to the synthetic
``test_config`` from ``tests/fixtures/config.py``, plus a ``make_web_client``
factory fixture for tests that need a custom ``Config``/``Settings`` or the
``https`` base-url.  The actual app + ``TestClient`` construction lives in the
shared :mod:`tests.web._web_harness` builders (phase 12 tests-arch
consolidation) so no per-file re-implementation of the app-building dance is
needed.
"""

from __future__ import annotations

import fakeredis
import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from tests.web._web_harness import web_client


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    """Reset the process-global login rate limiter around every web test.

    The limiter in ``personalscraper.web.auth.routes`` is module-level by design
    (tm-shell §4.4).  Without a reset, repeated failed-login assertions across
    unrelated tests would accumulate and eventually trip the 429 lockout,
    causing order-dependent flakes.
    """
    from personalscraper.web.auth import routes as auth_routes

    auth_routes._login_limiter.clear()
    yield
    auth_routes._login_limiter.clear()


@pytest.fixture
def make_web_client(test_config):
    """Return a factory that builds a full-app ``TestClient`` (create_app family).

    The single canonical builder for the full application: it defaults the
    ``Config`` to the synthetic ``test_config`` and the ``Settings`` to
    ``Settings(_env_file=None)`` (never reads the real ``.env``), and exposes the
    ``https`` / custom-``config`` / custom-``settings`` axes that the ~10 former
    per-file web-harness setups varied on.

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.

    Returns:
        A callable ``make(config=None, settings=None, *, https=False)`` returning
        a ``TestClient`` wrapping ``create_app``.
    """

    def _make(config=None, settings: Settings | None = None, *, https: bool = False) -> TestClient:
        return web_client(
            config if config is not None else test_config,
            settings,
            https=https,
        )

    return _make


@pytest.fixture
def web_app(test_config):
    """Create a TestClient wrapping ``create_app`` with test config + default settings.

    Uses ``Settings(_env_file=None)`` to avoid reading the real ``.env`` file.
    The synthetic ``test_config`` carries default ``WebConfig`` values
    (host, port, redis_url, etc.).

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.

    Returns:
        A ``TestClient`` instance ready for request assertions.
    """
    return web_client(test_config)


@pytest.fixture
def web_app_https(test_config):
    """Create a TestClient with ``base_url="https://testserver"`` for cookie-replay tests.

    The session cookie is set with ``Secure``, so httpx's TestClient on the
    default ``http://testserver`` will not replay it.  Use this fixture for any
    test that needs to receive and replay the ``tm_session`` cookie (login →
    /me round-trip, logout, guard checks on guarded routes).

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.

    Returns:
        A ``TestClient`` instance with ``base_url="https://testserver"``.
    """
    return web_client(test_config, https=True)


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    """Return a synchronous ``fakeredis.FakeRedis`` with decoded responses.

    Used by the :class:`RedisEventPublisher` producer tests: injected directly
    through the publisher's ``_redis`` attribute (the seam ``_get_redis``
    honours) so no real ``redis`` client is ever constructed.

    Returns:
        A ``fakeredis.FakeRedis`` instance (``decode_responses=True``).
    """
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def fake_server() -> fakeredis.FakeServer:
    """Return a shared ``fakeredis.FakeServer`` backing both sync and async clients.

    The WebSocket relay reads through an async client bound to the app's event
    loop, while relay tests XADD from the synchronous test thread.  Building a
    ``FakeAsyncRedis`` and a ``FakeRedis`` on the *same* ``FakeServer`` lets the
    async relay observe entries added from the test thread without a real Redis.

    Returns:
        A fresh ``fakeredis.FakeServer`` for one test.
    """
    return fakeredis.FakeServer()
