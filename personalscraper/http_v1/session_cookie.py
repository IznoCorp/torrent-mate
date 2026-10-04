"""v1's session cookie, ``tm_v1_session``, and the resolver that reads it.

v1 reads only ``tm_v1_session`` and v0 only ``tm_session``: one browser may hold both
on one host, and neither ever signs the other's requests in. The value is opaque; the
server keeps only its sha256 (:mod:`personalscraper.app.accounts.sessions`).

A request that renews its session is answered with the new value, whatever the answer:
the resolver leaves it in the request's state and :class:`SessionRenewalCookie` sets it on
the response, unless the route set or cleared the cookie itself (signing in or out).
"""

from __future__ import annotations

from typing import Final

from fastapi import Request, Response
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.sessions import SessionService, session_idle_s
from personalscraper.conf.models.web import WebConfig

#: The cookie v1's session travels in.
SESSION_COOKIE: Final = "tm_v1_session"

#: The request-state key a renewed session's new value waits under for the response.
_RENEWED_STATE_KEY: Final = "renewed_session_token"


def set_session_cookie(response: Response, token: str, web: WebConfig) -> None:
    """Hand the browser a session's value.

    Args:
        response: The answer to set the cookie on.
        token: The session's value.
        web: The web configuration (``session_idle_days``, ``cookie_secure``).
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=session_idle_s(web.session_idle_days),
        path="/",
        secure=web.cookie_secure,
        httponly=True,
        # Lax, not Strict: a link from another site (a notification, a bookmark's
        # redirect) opens the interface signed in. A cross-site write still never
        # passes: the perimeter refuses every unsafe method from another origin
        # (``request.cross_origin``), which stays the CSRF guard.
        samesite="lax",
    )


def clear_session_cookie(response: Response, web: WebConfig) -> None:
    """Tell the browser to drop the session cookie, with the attributes it was set with.

    Args:
        response: The answer to clear the cookie on.
        web: The web configuration (``cookie_secure``).
    """
    response.delete_cookie(SESSION_COOKIE, path="/", secure=web.cookie_secure, httponly=True, samesite="lax")


def session_token(request: Request) -> str | None:
    """The v1 session value a request carries.

    Args:
        request: The incoming request.

    Returns:
        The ``tm_v1_session`` value, or ``None`` when absent or empty.
    """
    return request.cookies.get(SESSION_COOKIE) or None


class SessionActorResolver:
    """Resolves a request's ``tm_v1_session`` to the actor it signs in — never ``tm_session``."""

    def __init__(self, sessions: SessionService) -> None:
        """Wrap the session service.

        Args:
            sessions: The session service.
        """
        self._sessions = sessions

    def resolve(self, request: Request) -> Actor | None:
        """Resolve the request's session.

        A use that renews the session leaves the new value in the request's state, for
        :class:`SessionRenewalCookie` to hand the browser.

        Args:
            request: The incoming request.

        Returns:
            The signed-in actor, or ``None`` with no cookie (the store is not touched)
            or with an unknown, expired or revoked session.
        """
        token = session_token(request)
        if token is None:
            return None
        use = self._sessions.use(token)
        if use is None:
            return None
        if use.renewed_token is not None:
            setattr(request.state, _RENEWED_STATE_KEY, use.renewed_token)
        return use.actor


class SessionRenewalCookie:
    """Pure ASGI: sets a renewed session's new value on the response, whatever its status.

    A refused or failed request that renewed the session still hands the new value: the
    browser is never left holding only the replaced one. A response that already sets
    ``tm_v1_session`` — a sign-in, a sign-out clearing it — is left as the route made it.
    """

    def __init__(self, app: ASGIApp, *, web: WebConfig) -> None:
        """Wrap the application.

        Args:
            app: The inner ASGI application.
            web: The web configuration the cookie is set with.
        """
        self.app = app
        self._web = web

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the inner application, adding the renewed cookie to its response's start.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # The dict ``request.state`` writes into, created here so the inner layers share it.
        state: dict[str, object] = scope.setdefault("state", {})

        async def send_with_cookie(message: Message) -> None:
            """Forward one message, the renewed cookie added to the response's start.

            Args:
                message: The ASGI message.
            """
            token = state.get(_RENEWED_STATE_KEY)
            if message["type"] == "http.response.start" and isinstance(token, str):
                headers = MutableHeaders(scope=message)
                prefix = f"{SESSION_COOKIE}="
                if not any(value.startswith(prefix) for value in headers.getlist("set-cookie")):
                    cookie = Response()
                    set_session_cookie(cookie, token, self._web)
                    headers.append("set-cookie", cookie.headers["set-cookie"])
            await send(message)

        await self.app(scope, receive, send_with_cookie)
