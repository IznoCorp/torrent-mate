"""What a v1 route receives: the principal the perimeter resolved, and the application services."""

from __future__ import annotations

from fastapi import Request

from personalscraper.app.accounts.principal import Principal
from personalscraper.app.errors import AppInternalError, RefusalCode
from personalscraper.app.services import AppServices


def principal(request: Request) -> Principal:
    """The principal the perimeter signed the request in as.

    Args:
        request: The incoming request, already through the perimeter.

    Returns:
        The signed-in principal.

    Raises:
        AppInternalError: ``internal`` — no principal was resolved (a public operation
            asking for one, or a route outside the perimeter): a server defect.
    """
    signed_in = getattr(request.state, "principal", None)
    if not isinstance(signed_in, Principal):
        raise AppInternalError(
            "The route asks for a principal the perimeter did not resolve.", code=RefusalCode.INTERNAL
        )
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
