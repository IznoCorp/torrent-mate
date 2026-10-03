"""``readVersion``: the version and the commit the running process serves, to a signed-in account."""

from __future__ import annotations

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from personalscraper.app import build_info as build_info_module
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.build_info import BUILD_INFO, BuildInfo
from personalscraper.app.composition import build_app_services
from personalscraper.app.services import AppServices
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.http_v1.app import create_v1_app
from personalscraper.http_v1.perimeter import ActorResolver

# An ordinary role holding no right: readVersion asks a session, never a right.
_GUEST = Actor(
    account_id="a3",
    name="Carol",
    role_id="r3",
    role_kind=RoleKind.ORDINARY,
    role_rights=frozenset(),
    ceiling=InstanceCeiling(forbidden=frozenset(), read_only=True),
)


class _StubResolver:
    """A resolver that signs every request in as one actor."""

    def resolve(self, request: Request) -> Actor | None:
        """Answer the guest.

        Args:
            request: The request (unused).

        Returns:
            The guest actor.
        """
        return _GUEST


def _client(config: Config, services: AppServices, resolver: ActorResolver | None) -> TestClient:
    """Build a client on the v1 sub-application.

    Args:
        config: The synthetic config.
        services: The application services the routes call.
        resolver: The actor resolver; ``None`` signs nobody in.

    Returns:
        The test client.
    """
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    return TestClient(create_v1_app(config, settings, services, resolver=resolver), raise_server_exceptions=False)


def test_without_a_session_is_auth_required(test_config: Config) -> None:
    """No session: 401 ``auth.required``, as a Problem."""
    services = AppServices(event_bus=EventBus(), build_info=BUILD_INFO, library=None)  # type: ignore[arg-type] — /version reads no library

    response = _client(test_config, services, None).get("/version")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


def test_signed_in_answers_the_services_build(test_config: Config) -> None:
    """Any signed-in account, even rightless on a read-only instance, reads the services' build."""
    services = AppServices(
        event_bus=EventBus(),
        build_info=BuildInfo(version="9.9.9", commit="feedbee"),
        library=None,  # type: ignore[arg-type] — /version reads no library
    )

    response = _client(test_config, services, _StubResolver()).get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "9.9.9", "commit": "feedbee"}


def test_composition_serves_the_boot_build(test_config: Config) -> None:
    """The composed services answer this package's version and the commit read at boot."""
    services = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]

    response = _client(test_config, services, _StubResolver()).get("/version")

    assert response.json() == {"version": BUILD_INFO.version, "commit": BUILD_INFO.commit}


def test_commit_is_the_boot_value_after_a_redeploy(test_config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    """R27: a ``BUILD_COMMIT`` stamped after boot never changes what the running process answers.

    A stale process re-reading the freshly stamped file would pass itself off as the
    new build, and the deploy's post-check could no longer catch a failed restart.
    """
    services = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]
    client = _client(test_config, services, _StubResolver())
    first = client.get("/version").json()["commit"]

    monkeypatch.setattr(build_info_module, "read_build_commit", lambda static_dir: "post-deploy-sha")
    second = client.get("/version").json()["commit"]
    rebuilt = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]

    assert second == first != "post-deploy-sha"
    assert rebuilt.build_info.commit == first
