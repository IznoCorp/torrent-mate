"""What a v1 route receives: the actor the perimeter resolved, and the application services."""

from __future__ import annotations

from fastapi import Request

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.errors import AppInternalError, RefusalCode
from personalscraper.app.services import AppServices


def actor(request: Request) -> Actor:
    """The actor the perimeter signed the request in as.

    Args:
        request: The incoming request, already through the perimeter.

    Returns:
        The signed-in actor.

    Raises:
        AppInternalError: ``internal`` — no actor was resolved (a public operation
            asking for one, or a route outside the perimeter): a server defect.
    """
    signed_in = getattr(request.state, "actor", None)
    if not isinstance(signed_in, Actor):
        raise AppInternalError("The route asks for an actor the perimeter did not resolve.", code=RefusalCode.INTERNAL)
    return signed_in


def services(request: Request) -> AppServices:
    """The application services of the v1 sub-application.

    Args:
        request: The incoming request; ``request.app`` is the v1 sub-application.

    Returns:
        The services ``create_v1_app`` was given.
    """
    app_services: AppServices = request.app.state.services
    return app_services
