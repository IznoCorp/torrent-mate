"""Auth routes for the TorrentMate web UI (tm-shell feature).

Login / logout / session-me endpoints.  See docs/features/tm-shell/DESIGN.md
§4.4 for the auth design.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from personalscraper.logger import get_logger
from personalscraper.web.auth.passwords import verify_password
from personalscraper.web.auth.tokens import create_session_token
from personalscraper.web.deps import Session, require_session

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)

# Guard against repeated warnings when the password hash is not configured.
_password_not_set_warned = False


class LoginRequest(BaseModel):
    """Login request body.

    Attributes:
        username: The username to authenticate.
        password: The plaintext password to verify.
    """

    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest, request: Request) -> Response:
    """Authenticate a user and set a session cookie.

    Verifies the supplied credentials against the stored scrypt hash.  On
    success, creates a JWT session token and sets it as an HttpOnly,
    SameSite=Strict cookie.  On failure, returns 401 after a small constant
    delay (to deter timing-based user enumeration).

    Args:
        body: The login credentials (username + password).
        request: The incoming FastAPI request (for app.state access).

    Returns:
        A ``Response`` with status 204 and a ``Set-Cookie`` header on success.

    Raises:
        HTTPException: 401 if the credentials are invalid or the password
            hash has not been configured.
    """
    global _password_not_set_warned

    config = request.app.state.config
    settings = request.app.state.settings
    web_cfg = config.web

    # If no password hash is configured, warn once and always reject.
    if not settings.web_password_hash:
        if not _password_not_set_warned:
            logger.warning("web_password_not_set")
            _password_not_set_warned = True
        time.sleep(0.1)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Constant-time resistant: same sleep + same message whether user or
    # password is wrong — no enumeration vector.
    if body.username != config.web.username or not verify_password(body.password, settings.web_password_hash):
        time.sleep(0.1)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Credentials verified — create session token and set cookie.
    token = create_session_token(body.username, settings.web_jwt_secret, web_cfg.session_ttl_hours)
    resp = Response(status_code=204)
    resp.set_cookie(
        "tm_session",
        token,
        httponly=True,
        samesite="strict",
        secure=web_cfg.cookie_secure,
        path="/",
        max_age=web_cfg.session_ttl_hours * 3600,
    )
    return resp


@router.post("/logout")
def logout(session: Session = Depends(require_session)) -> Response:
    """Clear the session cookie (log out).

    Requires a valid session (guarded by ``require_session``).

    Args:
        session: The authenticated session injected by the guard.

    Returns:
        A ``Response`` with status 204 and a cookie-clearing ``Set-Cookie`` header.
    """
    resp = Response(status_code=204)
    resp.delete_cookie("tm_session", path="/")
    return resp


@router.get("/me")
def me(session: Session = Depends(require_session)) -> dict[str, str]:
    """Return the authenticated user's identity.

    Requires a valid session (guarded by ``require_session``).

    Args:
        session: The authenticated session injected by the guard.

    Returns:
        A dict with the ``username`` key.
    """
    return {"username": session.username}
