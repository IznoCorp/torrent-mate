"""Every refusal and every failure v1 answers is a ``Problem`` (DESIGN C.4, one test per row)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import structlog
from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from personalscraper.app.errors import AppConflict, AppForbidden, RefusalCode
from personalscraper.http_v1.app import V1_PREFIX
from personalscraper.http_v1.contract import ContractModel

_SECRET = "s3cr3t-value"


class _Body(ContractModel):
    """A body with one integer field."""

    item_count: int


def _probe_router() -> APIRouter:
    """Build routes raising each row of the table.

    Returns:
        The router.
    """
    router = APIRouter()

    @router.get("/coded")
    def _coded() -> None:
        """Raise a coded refusal."""
        raise AppForbidden("Not held.", code=RefusalCode.RIGHT_MISSING, params={"rights": ["library.read"]})

    @router.get("/codeless")
    def _codeless() -> None:
        """Raise a refusal with no code."""
        raise AppConflict("Already running.")

    @router.post("/body")
    def _body(body: _Body) -> None:
        """Take a body."""

    @router.get("/crash")
    def _crash() -> None:
        """Fail with an unhandled exception."""
        raise RuntimeError(f"boom {_SECRET}")

    return router


def _client(make_v1_app: Callable[..., FastAPI]) -> TestClient:
    """Build a client on the sub-application with the probe routes.

    Args:
        make_v1_app: The sub-application factory.

    Returns:
        A test client that does not re-raise server exceptions.
    """
    app = make_v1_app()
    app.include_router(_probe_router())
    return TestClient(app, raise_server_exceptions=False)


def test_coded_refusal_is_its_status_code_and_params(make_v1_app: Callable[..., FastAPI]) -> None:
    """Row 1: a coded refusal answers its status, its code and its params."""
    response = _client(make_v1_app).get("/coded")

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert body["status"] == 403
    assert body["code"] == "right.missing"
    assert body["params"] == {"rights": ["library.read"]}
    assert body["detail"] == "Not held."
    assert isinstance(body["title"], str) and body["title"]


def test_codeless_refusal_is_internal_and_logged(make_v1_app: Callable[..., FastAPI]) -> None:
    """Row 2: a code-less refusal is a v1 defect: 500 ``internal`` and an error log naming its class."""
    client = _client(make_v1_app)

    with structlog.testing.capture_logs() as logs:
        response = client.get("/codeless")

    assert response.status_code == 500
    assert response.json()["code"] == "internal"
    assert "Already running." not in response.text
    errors = [entry for entry in logs if entry["log_level"] == "error"]
    assert any(entry.get("refusal") == "AppConflict" for entry in errors), logs


def test_refused_body_is_request_invalid_without_the_value(make_v1_app: Callable[..., FastAPI]) -> None:
    """Row 3: a body the contract refuses is 400 ``request.invalid``, dotted locations, never the value."""
    response = _client(make_v1_app).post("/body", json={"itemCount": _SECRET})

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "request.invalid"
    assert body["params"] == {"fields": ["body.itemCount"]}
    assert _SECRET not in response.text


def test_unknown_path_is_route_unknown(make_v1_app: Callable[..., FastAPI]) -> None:
    """Row 4: no operation at that path is 404 ``route.unknown``."""
    response = _client(make_v1_app).get("/nowhere")

    assert response.status_code == 404
    assert response.json()["code"] == "route.unknown"


def test_wrong_method_is_route_unknown(make_v1_app: Callable[..., FastAPI]) -> None:
    """Row 4: a known path under another method is 405 ``route.unknown``."""
    response = _client(make_v1_app).delete("/coded")

    assert response.status_code == 405
    assert response.json()["code"] == "route.unknown"
    assert response.headers["allow"] == "GET"


def test_crash_is_internal_with_no_trace(make_v1_app: Callable[..., FastAPI]) -> None:
    """Row 5: an unhandled exception is 500 ``internal``, a fixed English line, nothing of the trace."""
    client = _client(make_v1_app)

    with structlog.testing.capture_logs() as logs:
        response = client.get("/crash")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal"
    assert body["detail"] == "An unexpected error occurred."
    assert _SECRET not in response.text
    assert "Traceback" not in response.text
    assert any(entry["log_level"] == "error" for entry in logs)


def test_crash_inside_the_mount_does_not_reach_the_parent(make_v1_app: Callable[..., FastAPI]) -> None:
    """Row 5, mounted: the parent's server-exception guard never sees the crash."""
    v1_app = make_v1_app()
    v1_app.include_router(_probe_router())
    parent = FastAPI()
    parent.mount(V1_PREFIX, v1_app)

    response = TestClient(parent, raise_server_exceptions=True).get(f"{V1_PREFIX}/crash")

    assert response.status_code == 500
    assert response.json()["code"] == "internal"


def test_crash_after_the_response_started_is_swallowed_and_never_answered_twice(
    make_v1_app: Callable[..., FastAPI],
) -> None:
    """Row 5, late: once the response has started nothing is re-raised and no second start is sent."""
    v1_app = make_v1_app()

    async def _stream_then_crash() -> AsyncIterator[bytes]:
        """Send one chunk, then fail."""
        yield b"first chunk"
        raise RuntimeError(f"boom {_SECRET}")

    @v1_app.get("/started")
    def _started() -> StreamingResponse:
        """Start a streamed response that crashes mid-way."""
        return StreamingResponse(_stream_then_crash())

    parent = FastAPI()
    parent.mount(V1_PREFIX, v1_app)
    sent: list[str] = []

    async def recorder(scope: Scope, receive: Receive, send: Send) -> None:
        """Run the parent, recording the type of every message it sends.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """

        async def _record(message: Message) -> None:
            sent.append(message["type"])
            await send(message)

        await parent(scope, receive, _record)

    with structlog.testing.capture_logs() as logs:
        response = TestClient(recorder, raise_server_exceptions=True).get(f"{V1_PREFIX}/started")

    assert response.status_code == 200
    assert _SECRET not in response.text
    assert sent.count("http.response.start") == 1
    assert any(entry["event"] == "v1_unhandled_exception" and entry["started"] is True for entry in logs)


def test_every_code_has_a_title() -> None:
    """Every refusal code answers one English title."""
    from personalscraper.http_v1.problem import REFUSAL_TITLES

    assert set(REFUSAL_TITLES) == set(RefusalCode)
    assert all(title and "\n" not in title for title in REFUSAL_TITLES.values())
