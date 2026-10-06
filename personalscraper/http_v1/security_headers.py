"""The security headers the served application sets itself, whatever the reverse proxy does.

The application owns them for the reason it owns compression: they must survive a proxy
reconfiguration, and it is the application that knows what it serves. The
``Content-Security-Policy`` is not in the register yet: its text is the operator's ruling.
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


class SecurityHeaders:
    """Pure ASGI middleware adding :data:`SECURITY_HEADERS` to every HTTP response.

    A header a route already set is kept: the middleware only fills what is missing, so the
    same middleware may wrap a mounted application and its parent without doubling a value.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an application.

        Args:
            app: The inner ASGI application.
        """
        self.app = app

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
                for name, value in SECURITY_HEADERS.items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
