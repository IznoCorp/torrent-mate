"""The security headers the served application sets itself, whatever the reverse proxy does.

The application owns them for the reason it owns compression: they must survive a proxy
reconfiguration, and it is the application that knows what it serves.

The ``Content-Security-Policy`` is the operator's ruling (``'self'`` plus a closed list), and
it is v1's and the design host's alone: v0's pages (``frontend/``) die at the switchover and
are not under it, so the v0 application does not ask the middleware for it.
"""

from __future__ import annotations

from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: The headers every response carries, by name. One year of HTTPS-only for the host and its subdomains.
SECURITY_HEADERS: Final[dict[str, str]] = {
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

#: The policy of v1 and of the design host: the origin alone, plus the closed list of what the
#: interface shows from elsewhere — posters (TMDB, TVDB), avatars (plex.tv, which redirects to
#: assets.plex.tv, and Gravatar) and the trailer embed (YouTube). No ``style-src`` or ``script-src``
#: of its own: no ``'unsafe-inline'`` anywhere, so a React ``style`` prop or a CSSOM assignment is
#: allowed and an inline ``<style>``, ``<script>`` or ``style=""`` is not.
CONTENT_SECURITY_POLICY: Final[str] = (
    "default-src 'self'; "
    "img-src 'self' https://image.tmdb.org https://artworks.thetvdb.com https://plex.tv "
    "https://assets.plex.tv https://www.gravatar.com; "
    "frame-src https://www.youtube.com; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityHeaders:
    """Pure ASGI middleware adding :data:`SECURITY_HEADERS` to every HTTP response.

    A header a route already set is kept: the middleware only fills what is missing, so the
    same middleware may wrap a mounted application and its parent without doubling a value.
    """

    def __init__(self, app: ASGIApp, *, with_policy: bool = False) -> None:
        """Wrap an application.

        Args:
            app: The inner ASGI application.
            with_policy: Whether the responses also carry :data:`CONTENT_SECURITY_POLICY`; off for
                v0, whose pages are not under it.
        """
        self.app = app
        self.headers = {
            **SECURITY_HEADERS,
            **({"Content-Security-Policy": CONTENT_SECURITY_POLICY} if with_policy else {}),
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the call on, adding the headers at the response start.

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
                headers = MutableHeaders(scope=message)
                for name, value in self.headers.items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
