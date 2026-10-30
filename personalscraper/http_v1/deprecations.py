"""The v0 routes a v1 operation replaces, and the header that says so.

A v0 route with a v1 twin tells its callers with RFC 9745's ``Deprecation`` header
and a ``Link: …; rel="successor-version"``. :data:`V0_TWINS` is the register: a
phase that serves a v1 twin adds ONE line, and the mapping is the list of what is
deleted with v0.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Final
from urllib.parse import quote

from pydantic.alias_generators import to_snake
from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass(frozen=True)
class V0Twin:
    """One v0 route and the v1 operation that replaces it.

    Attributes:
        operation_id: The v1 operation's ``operationId``.
        successor: The v1 path template, prefix included (e.g. ``/api/v1/version``), as
            v1 serves it; its ``{name}`` segments are filled from the v0 request.
        since: The day the twin was registered; the ``Deprecation`` header's date.
    """

    operation_id: str
    successor: str
    since: date


#: A ``{name}`` segment of a successor path.
_SEGMENT: Final[re.Pattern[str]] = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: ``(METHOD, v0 path template)`` → its v1 twin.
V0_TWINS: Final[Mapping[tuple[str, str], V0Twin]] = {
    ("GET", "/api/version"): V0Twin("readVersion", "/api/v1/version", date(2026, 10, 3)),
    ("GET", "/api/auth/me"): V0Twin("readAccount", "/api/v1/auth/me", date(2026, 10, 3)),
    ("POST", "/api/auth/logout"): V0Twin("signOut", "/api/v1/auth/logout", date(2026, 10, 3)),
    ("POST", "/api/auth/login"): V0Twin("signIn", "/api/v1/auth/login", date(2026, 10, 3)),
    ("GET", "/api/media/{provider}/{provider_id}"): V0Twin(
        "readMediaSheet", "/api/v1/media/{provider}/{providerId}", date(2026, 10, 4)
    ),
}


def _successor_uri(twin: V0Twin, path_params: Mapping[str, Any]) -> str:
    """Fill the successor's ``{name}`` segments with the v0 request's path parameters.

    A ``Link`` target is a URI, never a template: the v0 sheet of ``tmdb/603`` names
    ``/api/v1/media/tmdb/603``. v1 spells a parameter in camelCase (X2) where v0 spells
    it in snake_case, so ``{providerId}`` reads v0's ``provider_id``. Each value is
    percent-encoded as one path segment.

    Args:
        twin: The registered twin.
        path_params: The path parameters the router matched on the v0 request.

    Returns:
        The successor's URI; a successor without ``{…}`` comes back unchanged.
    """

    def fill(match: re.Match[str]) -> str:
        """One segment's value, read under its v1 name, else its v0 snake_case name."""
        name = match.group(1)
        value = path_params[name] if name in path_params else path_params[to_snake(name)]
        return quote(str(value), safe="")

    return _SEGMENT.sub(fill, twin.successor)


def _deprecation_headers(twin: V0Twin, path_params: Mapping[str, Any]) -> list[tuple[bytes, bytes]]:
    """The two raw headers a twinned v0 response carries.

    Args:
        twin: The registered twin.
        path_params: The path parameters the router matched on the v0 request.

    Returns:
        ``Deprecation: @<epoch of since, 00:00 UTC>`` and the successor ``Link``.
    """
    epoch = int(datetime(twin.since.year, twin.since.month, twin.since.day, tzinfo=UTC).timestamp())
    return [
        (b"deprecation", f"@{epoch}".encode()),
        (b"link", f'<{_successor_uri(twin, path_params)}>; rel="successor-version"'.encode()),
    ]


class DeprecationHeaders:
    """Pure ASGI middleware marking the v0 responses of routes in :data:`V0_TWINS`.

    Outside every v0 route: it wraps ``send`` and, at ``http.response.start``, reads
    the route the router matched (set on this same ``scope`` before the response
    starts) and the method.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an application.

        Args:
            app: The inner ASGI application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the call on, adding the headers to a twinned route's response start.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            """Add the headers to ``http.response.start``; pass anything else through.

            Args:
                message: The outgoing ASGI message.
            """
            if message["type"] == "http.response.start":
                route: Any = scope.get("route")
                twin = V0_TWINS.get((scope["method"], getattr(route, "path", "")))
                if twin is not None:
                    headers = _deprecation_headers(twin, scope.get("path_params", {}))
                    message["headers"] = [*message.get("headers", []), *headers]
            await send(message)

        await self.app(scope, receive, send_with_headers)
