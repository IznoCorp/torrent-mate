"""FastAPI dependencies for accessing config and settings (tm-shell feature).

These are FastAPI dependency callables intended for use with ``Depends()``.
They read from ``request.app.state``, which is populated by ``create_app``.
"""

from __future__ import annotations

from typing import cast

from fastapi import HTTPException, Request
from pydantic import BaseModel

from personalscraper.conf.models.web import WebConfig
from personalscraper.config import Settings
from personalscraper.web.auth.tokens import decode_session_token


class Session(BaseModel):
    """Session model representing an authenticated user.

    Attributes:
        username: The authenticated username (matches the ``sub`` claim in the JWT).
    """

    username: str


def get_web_config(request: Request) -> WebConfig:
    """Dependency that extracts the WebConfig from the application state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The ``WebConfig`` instance stored on ``request.app.state.config``.
    """
    return cast(WebConfig, request.app.state.config.web)


def get_app_settings(request: Request) -> Settings:
    """Dependency that extracts the Settings from the application state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The ``Settings`` instance stored on ``request.app.state.settings``.
    """
    return cast(Settings, request.app.state.settings)


def require_session(request: Request) -> Session:
    """FastAPI dependency that validates the ``tm_session`` cookie.

    Reads the JWT session token from the ``tm_session`` cookie, decodes it,
    and verifies that the token subject matches the configured single-user
    username.  This is the auth guard for all ``/api/*`` routes except the
    health liveness probe and the login endpoint itself.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A ``Session`` instance carrying the authenticated username.

    Raises:
        HTTPException: 401 if the cookie is missing, the token is invalid
            or expired, or the ``sub`` claim does not match the configured
            username.
    """
    config = request.app.state.config
    settings = request.app.state.settings

    token = request.cookies.get("tm_session")
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_session_token(token, settings.web_jwt_secret)
    if payload is None or payload.get("sub") != config.web.username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return Session(username=payload["sub"])
