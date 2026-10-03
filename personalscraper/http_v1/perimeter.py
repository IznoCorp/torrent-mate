"""The v1 perimeter: the ONE authorisation dependency, registered on every router (X6, NE-DOIT-PAS-7).

No v1 route carries a dependency of its own that guards it: the perimeter reads the
route's ``operation_id``, looks its requirement up in ``OPERATION_RIGHTS`` and
applies :func:`~personalscraper.app.accounts.authorise.authorise`. The instance
ceiling is a term of ``authorise``, never a second dependency.
"""

from __future__ import annotations

from typing import Final, Protocol
from urllib.parse import urlsplit

from fastapi import Request

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import authorise
from personalscraper.app.accounts.rights import Public
from personalscraper.app.errors import AppForbidden, AppInternalError, RefusalCode
from personalscraper.http_v1.rights import OPERATION_RIGHTS
from personalscraper.logger import get_logger

log = get_logger("http_v1.perimeter")

_UNSAFE_METHODS: Final[frozenset[str]] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ActorResolver(Protocol):
    """Resolves a request's session to the actor it signs in, or to nobody."""

    def resolve(self, request: Request) -> Actor | None:
        """Resolve the request's session.

        Args:
            request: The incoming request.

        Returns:
            The signed-in actor, or ``None`` when the request carries no valid session.
        """
        ...


def _is_cross_origin(request: Request) -> bool:
    """Whether a request's ``Origin`` header names another origin than the request's own.

    Args:
        request: The incoming request.

    Returns:
        True when an ``Origin`` is present and differs from this request's scheme and
        host; a request with no ``Origin`` (a non-browser client) is not cross-origin.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return False
    parts = urlsplit(origin)
    own_host = request.headers.get("host", "")
    return (parts.scheme.lower(), parts.netloc.lower()) != (request.url.scheme.lower(), own_host.lower())


def v1_perimeter(request: Request) -> None:
    """Authorise one v1 request, or refuse it.

    1. An unsafe method from another origin is refused.
    2. The route's ``operation_id`` is looked up in ``OPERATION_RIGHTS``; an operation
       the table does not name is a server defect, never an open door.
    3. The session is resolved to an actor, unless the operation is public.
    4. ``authorise`` applies the requirement.
    5. The actor is kept on ``request.state.actor`` for :func:`~personalscraper.http_v1.deps.actor`.

    Args:
        request: The incoming request, matched to a v1 route.

    Raises:
        AppForbidden: ``request.cross_origin``, or ``authorise``'s refusals.
        AppUnauthenticated: ``auth.required`` (from ``authorise``).
        AppInternalError: ``internal`` — the route's operation is not in the table.
    """
    if request.method in _UNSAFE_METHODS and _is_cross_origin(request):
        raise AppForbidden("The request comes from another origin.", code=RefusalCode.REQUEST_CROSS_ORIGIN)
    route = request.scope.get("route")
    operation_id = getattr(route, "operation_id", None)
    requirement = OPERATION_RIGHTS.get(operation_id) if isinstance(operation_id, str) else None
    if requirement is None:
        log.error("v1_operation_without_right", operation_id=operation_id, path=request.url.path)
        raise AppInternalError("The operation has no entry in the rights table.", code=RefusalCode.INTERNAL)
    actor = None
    if not isinstance(requirement, Public):
        resolver: ActorResolver = request.app.state.actor_resolver
        actor = resolver.resolve(request)
    authorise(actor, requirement)
    request.state.actor = actor
