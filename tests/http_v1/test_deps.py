"""What a v1 route receives from ``deps``: the services always, the actor only through the perimeter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from personalscraper.app.services import AppServices
from personalscraper.http_v1.app import include_v1_router
from personalscraper.http_v1.deps import actor, services


def test_actor_without_a_resolved_actor_is_internal(make_v1_app: Callable[..., FastAPI]) -> None:
    """A public operation asking for an actor gets none from the perimeter: a server defect, 500 ``internal``."""
    router = APIRouter()

    @router.post("/auth/plex/start", operation_id="startPlexSignIn")
    def _public(_: Annotated[object, Depends(actor)]) -> dict[str, str]:
        """A public operation wrongly asking for the actor."""
        return {"ok": "yes"}

    app = make_v1_app()
    include_v1_router(app, router)

    response = TestClient(app, raise_server_exceptions=False).post("/auth/plex/start")

    assert response.status_code == 500
    assert response.json()["code"] == "internal"


def test_services_are_the_ones_the_sub_application_was_given(make_v1_app: Callable[..., FastAPI]) -> None:
    """``deps.services`` hands a route the very object ``create_v1_app`` stored."""
    router = APIRouter()
    seen: list[AppServices] = []

    @router.post("/auth/plex/start", operation_id="startPlexSignIn")
    def _public(given: Annotated[AppServices, Depends(services)]) -> dict[str, str]:
        """A public operation recording the services it received."""
        seen.append(given)
        return {"ok": "yes"}

    app = make_v1_app()
    include_v1_router(app, router)

    response = TestClient(app).post("/auth/plex/start")

    assert response.status_code == 200
    assert seen == [app.state.services]
    assert seen[0] is app.state.services
