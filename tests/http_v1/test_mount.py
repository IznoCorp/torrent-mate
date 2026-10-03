"""v0's ``create_app`` mounts v1 under ``/api/v1`` only where ``web.v1_enabled`` (ruling O-K1-1 B).

Production sets nothing, so it serves nothing new; where v1 is mounted, v0's
OpenAPI document and v0's policy suites are unchanged.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from starlette.routing import Mount

from personalscraper.app.services import AppServices
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.http_v1.app import V1_PREFIX, include_v1_router, v1_lifespan
from personalscraper.web import app as web_app
from personalscraper.web.app import create_app
from personalscraper.web.static import mount_spa
from tests.unit.web.routes import test_staging_write_policy, test_web_perimeter_policy


def _settings() -> Settings:
    """Settings that never read the real ``.env``.

    Returns:
        The settings.
    """
    return Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]


def _with_v1(config: Config, enabled: bool) -> Config:
    """Copy a config with ``web.v1_enabled`` set.

    Args:
        config: The base config.
        enabled: The switch's value.

    Returns:
        The copied config.
    """
    return config.model_copy(update={"web": config.web.model_copy(update={"v1_enabled": enabled})})


def _v1_mounts(app: FastAPI) -> list[Mount]:
    """The parent's mounts at the v1 prefix.

    Args:
        app: The parent application.

    Returns:
        Every ``Mount`` whose path is :data:`V1_PREFIX`.
    """
    return [route for route in app.routes if isinstance(route, Mount) and route.path == V1_PREFIX]


def _canary_router() -> APIRouter:
    """Two v1 routes at contract paths, mount-relative, as every v1 route module writes them.

    The POST is the canary of v0's mutating-route walkers: it is no v0 route, so
    neither policy table classifies it.

    Returns:
        The router.
    """
    router = APIRouter()

    @router.get("/version", operation_id="readVersion")
    def _version() -> dict[str, str]:
        """A signed-in read."""
        return {"version": "x"}

    @router.post("/library/items/delete", operation_id="deleteLibraryItems")
    def _delete() -> dict[str, str]:
        """A right-gated write."""
        return {"ok": "yes"}

    return router


def test_the_switch_defaults_to_off(test_config: Config) -> None:
    """Production sets nothing: the key's default is off."""
    assert test_config.web.v1_enabled is False


def test_disabled_mounts_nothing(test_config: Config) -> None:
    """Off: no mount, and ``/api/v1/...`` is v0's API fallback, an empty 404."""
    app = create_app(_with_v1(test_config, False), _settings())

    response = TestClient(app).get(f"{V1_PREFIX}/anything")

    assert _v1_mounts(app) == []
    assert not hasattr(app.state, "v1_app")
    assert response.status_code == 404
    assert response.content == b""


def test_enabled_answers_a_problem(test_config: Config) -> None:
    """On: ``/api/v1/...`` is v1's, an unknown path a ``route.unknown`` Problem."""
    app = create_app(_with_v1(test_config, True), _settings())

    response = TestClient(app).get(f"{V1_PREFIX}/anything")

    assert len(_v1_mounts(app)) == 1
    assert response.status_code == 404
    assert response.json()["code"] == "route.unknown"


def test_enabled_v1_is_closed_by_default(test_config: Config) -> None:
    """On, before sessions exist: a signed-in operation answers 401 through the parent."""
    app = create_app(_with_v1(test_config, True), _settings())
    include_v1_router(app.state.v1_app, _canary_router())

    response = TestClient(app).get(f"{V1_PREFIX}/version")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


def test_enabled_leaves_the_v0_openapi_byte_identical(test_config: Config) -> None:
    """On or off, v0's OpenAPI export is the same bytes: a mount is outside ``openapi()``."""

    def export(enabled: bool) -> str:
        """Export v0's OpenAPI document with v1 mounted or not.

        Args:
            enabled: ``web.v1_enabled``.

        Returns:
            The document, serialised with sorted keys.
        """
        app = create_app(_with_v1(test_config, enabled), _settings())
        if enabled:
            include_v1_router(app.state.v1_app, _canary_router())
        return json.dumps(app.openapi(), sort_keys=True, indent=2)

    assert export(True) == export(False)


def test_the_spa_fallback_does_not_shadow_the_mount(
    test_config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a built SPA (its GET catch-all registered), ``/api/v1/...`` still answers a ``Problem``, not the HTML."""
    (tmp_path / "index.html").write_text("<html>spa</html>")
    monkeypatch.setattr(web_app, "mount_spa", lambda app, _static_dir, dev_mode: mount_spa(app, tmp_path, dev_mode))
    app = create_app(_with_v1(test_config, True), _settings())
    client = TestClient(app)

    assert "spa" in client.get("/somewhere-else").text
    response = client.get(f"{V1_PREFIX}/anything")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json()["code"] == "route.unknown"


def _policy_tests() -> Iterator[tuple[str, Callable[..., Any]]]:
    """Every test of v0's two policy suites that takes the ``app`` fixture.

    Yields:
        ``(name, callable)`` for each module-level test and each test method.
    """
    for module in (test_staging_write_policy, test_web_perimeter_policy):
        for name, member in vars(module).items():
            if name.startswith("test_") and callable(member):
                yield f"{module.__name__}.{name}", member
            elif name.startswith("Test") and inspect.isclass(member):
                for method_name, method in vars(member).items():
                    if method_name.startswith("test_"):
                        yield f"{module.__name__}.{name}.{method_name}", getattr(member(), method_name)


@pytest.mark.parametrize(("name", "policy_test"), list(_policy_tests()), ids=[n for n, _ in _policy_tests()])
def test_v0_policy_suites_pass_with_v1_mounted(test_config: Config, name: str, policy_test: Callable[..., Any]) -> None:
    """v0's policy suites stop at the v1 ``Mount``: with a v1 POST mounted, they still pass.

    v1's own policy is ``OPERATION_RIGHTS`` and ``test_rights_table``.
    """
    app = create_app(_with_v1(test_config, True), _settings())
    include_v1_router(app.state.v1_app, _canary_router())

    policy_test(app)


def test_v1_paths_are_mount_relative(test_config: Config) -> None:
    """A v1 route's path is the contract's without ``/api``: v0's ``/api/`` prefix tables never read it as theirs."""
    app = create_app(_with_v1(test_config, True), _settings())
    include_v1_router(app.state.v1_app, _canary_router())

    v1_paths = {
        path
        for path, operations in app.state.v1_app.openapi()["paths"].items()
        for operation in operations.values()
        if operation["operationId"] == "readVersion"
    }

    assert v1_paths == {"/version"}


def test_lifespan_closes_the_services() -> None:
    """The parent's lifespan closes the sub-application's services; ``None`` is a no-op."""
    closed: list[bool] = []

    class _Services(AppServices):
        """Services recording that they were closed."""

        def close(self) -> None:
            """Record the close."""
            closed.append(True)

    v1_app = FastAPI()
    v1_app.state.services = _Services(event_bus=EventBus())

    async def enter_both() -> None:
        """Enter the lifespan with no sub-application, then with one, checking nothing closes early."""
        async with v1_lifespan(None):
            pass
        async with v1_lifespan(v1_app):
            assert closed == []

    asyncio.run(enter_both())

    assert closed == [True]


def test_parent_lifespan_enters_the_v1_lifespan(test_config: Config) -> None:
    """Booting and stopping the parent closes v1's services once."""
    closed: list[bool] = []

    class _Services(AppServices):
        """Services recording that they were closed."""

        def close(self) -> None:
            """Record the close."""
            closed.append(True)

    config = _with_v1(test_config, True)
    config = config.model_copy(update={"web": config.web.model_copy(update={"enabled": False})})
    app = create_app(config, _settings())
    app.state.v1_app.state.services = _Services(event_bus=EventBus())

    with TestClient(app):
        assert closed == []

    assert closed == [True]
