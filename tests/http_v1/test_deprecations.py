"""v0 routes that have a v1 twin say so (RFC 9745 ``Deprecation`` + ``successor-version`` link).

The header is emitted only where v1 is mounted: a successor link to an unmounted
``/api/v1`` would be false.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import date

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.middleware.gzip import GZipMiddleware

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1 import deprecations
from personalscraper.http_v1.app import V1_PREFIX
from personalscraper.http_v1.deprecations import V0_TWINS, DeprecationHeaders, V0Twin
from personalscraper.web.app import create_app
from personalscraper.web.auth.passwords import hash_password

USERNAME = "testuser"
PASSWORD = "test-password"
SECRET = "deprecation-test-secret"


def _client(config: Config, *, v1_enabled: bool) -> TestClient:
    """Build the full v0 application, signed in, with v1 mounted or not.

    Args:
        config: The synthetic config.
        v1_enabled: ``web.v1_enabled``.

    Returns:
        A client holding a v0 session cookie.
    """
    web = config.web.model_copy(update={"username": USERNAME, "v1_enabled": v1_enabled})
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, web_password_hash=hash_password(PASSWORD), web_jwt_secret=SECRET
    )
    client = TestClient(create_app(config.model_copy(update={"web": web}), settings), base_url="https://testserver")
    login = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert login.status_code == 204
    return client


@pytest.fixture
def twin() -> V0Twin:
    """The ``readVersion`` twin, as registered.

    Returns:
        The register's ``GET /api/version`` line.
    """
    return V0_TWINS[("GET", "/api/version")]


def test_a_twinned_route_carries_both_headers(test_config: Config, twin: V0Twin) -> None:
    """v1 mounted: ``GET /api/version`` says it is deprecated and names its successor."""
    response = _client(test_config, v1_enabled=True).get("/api/version")

    assert response.status_code == 200
    assert twin.since == date(2026, 10, 3)
    assert response.headers["deprecation"] == "@1790985600"  # 2026-10-03 00:00 UTC, the registered line's day
    assert response.headers["link"] == '</api/v1/version>; rel="successor-version"'


def test_the_answer_is_otherwise_unchanged(test_config: Config) -> None:
    """Status and body equal those of an app with v1 off."""
    on = _client(test_config, v1_enabled=True).get("/api/version")
    off = _client(test_config, v1_enabled=False).get("/api/version")

    assert (on.status_code, on.json()) == (off.status_code, off.json())


def test_a_route_without_a_twin_carries_neither(test_config: Config) -> None:
    """v1 mounted: ``GET /api/health`` has no twin, so no header."""
    response = _client(test_config, v1_enabled=True).get("/api/health")

    assert "deprecation" not in response.headers
    assert "link" not in response.headers


def test_v1_disabled_carries_neither_anywhere(test_config: Config) -> None:
    """v1 off: not even the twinned route is marked."""
    client = _client(test_config, v1_enabled=False)

    for path in ("/api/version", "/api/health"):
        response = client.get(path)
        assert "deprecation" not in response.headers
        assert "link" not in response.headers


def test_a_twin_is_keyed_by_method(test_config: Config) -> None:
    """A different method on the same path is no twin."""
    response = _client(test_config, v1_enabled=True).post("/api/version")

    assert "deprecation" not in response.headers


def _app_with_twin(compress: bool) -> FastAPI:
    """A bare app serving ``GET /api/probe`` (twinned) under the middleware.

    Args:
        compress: Whether a ``GZipMiddleware`` sits inside the middleware, as in ``create_app``.

    Returns:
        The application.
    """
    app = FastAPI()
    if compress:
        app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(DeprecationHeaders)

    @app.get("/api/probe")
    def probe() -> dict[str, str]:
        """A twinned route with a body over 1 KB.

        Returns:
            A large body.
        """
        return {"filler": "x" * 4096}

    @app.get("/api/stream")
    async def stream() -> StreamingResponse:
        """A streamed, twinned route.

        Returns:
            A response sent in chunks.
        """

        async def chunks() -> AsyncIterator[bytes]:
            """Yield three chunks.

            Yields:
                Bytes.
            """
            for part in (b"a", b"b", b"c"):
                yield part

        return StreamingResponse(chunks())

    return app


@pytest.fixture
def probe_twins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register the probe routes as twins, restoring the register after.

    Args:
        monkeypatch: pytest's monkeypatch.
    """
    since = date(2026, 1, 2)
    monkeypatch.setattr(
        deprecations,
        "V0_TWINS",
        {
            ("GET", "/api/probe"): V0Twin("probe", "/api/v1/probe", since),
            ("GET", "/api/stream"): V0Twin("stream", "/api/v1/stream", since),
        },
    )


@pytest.mark.usefixtures("probe_twins")
def test_a_gzip_compressed_response_carries_the_headers() -> None:
    """A response over 1 KB, compressed by the app's ``GZipMiddleware``, still carries both."""
    response = TestClient(_app_with_twin(compress=True)).get("/api/probe", headers={"accept-encoding": "gzip"})

    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["deprecation"] == "@1767312000"  # 2026-01-02 00:00 UTC
    assert response.headers["link"] == '</api/v1/probe>; rel="successor-version"'
    assert response.json() == {"filler": "x" * 4096}


@pytest.mark.usefixtures("probe_twins")
def test_a_streamed_response_passes_unchanged() -> None:
    """A streamed response keeps its body whole; the headers ride on its start."""
    response = TestClient(_app_with_twin(compress=False)).get("/api/stream")

    assert response.content == b"abc"
    assert response.headers["deprecation"] == "@1767312000"  # 2026-01-02 00:00 UTC


@pytest.mark.usefixtures("probe_twins")
def test_a_non_http_scope_passes_through() -> None:
    """A websocket handshake is no response: the middleware leaves it alone."""
    app = FastAPI()
    app.add_middleware(DeprecationHeaders)

    @app.websocket("/api/ws")
    async def ws(socket: WebSocket) -> None:
        """Accept and close.

        Args:
            socket: The websocket.
        """
        await socket.accept()
        await socket.close()

    with TestClient(app).websocket_connect("/api/ws"):
        pass


def test_every_twin_is_served_by_v1(test_config: Config, make_v1_app: Callable[..., FastAPI], twin: V0Twin) -> None:
    """Each register line names an operation the v1 sub-application serves, at its successor path."""
    del test_config
    paths = make_v1_app().openapi()["paths"]
    served = {
        operation["operationId"]: f"{V1_PREFIX}{path}"
        for path, operations in paths.items()
        for operation in operations.values()
    }

    for registered in V0_TWINS.values():
        assert served[registered.operation_id] == registered.successor
    assert twin.operation_id == "readVersion"
