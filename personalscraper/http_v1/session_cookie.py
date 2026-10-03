"""v1's session cookie, ``tm_v1_session``, and the resolver that reads it.

v1 reads only ``tm_v1_session`` and v0 only ``tm_session``: one browser may hold both
on one host, and neither ever signs the other's requests in. The value is opaque; the
server keeps only its sha256 (:mod:`personalscraper.app.accounts.sessions`).
"""

from __future__ import annotations

from typing import Final

from fastapi import Request, Response

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.conf.models.web import WebConfig

#: The cookie v1's session travels in.
SESSION_COOKIE: Final = "tm_v1_session"

_SECONDS_PER_HOUR: Final = 3600


def set_session_cookie(response: Response, token: str, web: WebConfig) -> None:
    """Hand the browser a session's value.

    Args:
        response: The answer to set the cookie on.
        token: The session's value.
        web: The web configuration (``session_ttl_hours``, ``cookie_secure``).
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=web.session_ttl_hours * _SECONDS_PER_HOUR,
        path="/",
        secure=web.cookie_secure,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response, web: WebConfig) -> None:
    """Tell the browser to drop the session cookie, with the attributes it was set with.

    Args:
        response: The answer to clear the cookie on.
        web: The web configuration (``cookie_secure``).
    """
    response.delete_cookie(SESSION_COOKIE, path="/", secure=web.cookie_secure, httponly=True, samesite="strict")


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

        Args:
            request: The incoming request.

        Returns:
            The signed-in actor, or ``None`` with no cookie (the store is not touched)
            or with an unknown, expired or revoked session.
        """
        token = session_token(request)
        if token is None:
            return None
        return self._sessions.resolve(token)
