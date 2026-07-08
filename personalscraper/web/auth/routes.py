"""Auth routes for the TorrentMate web UI (tm-shell feature).

Login / logout / session-me endpoints.  See docs/features/tm-shell/DESIGN.md
§4.4 for the auth design.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from personalscraper.logger import get_logger
from personalscraper.web.auth.passwords import hash_password, verify_password
from personalscraper.web.auth.ratelimit import SlidingWindowRateLimiter
from personalscraper.web.auth.tokens import create_session_token
from personalscraper.web.deps import Session, require_session

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)

# Guard against repeated warnings when the server is not fully configured.
_password_not_set_warned = False
_jwt_secret_not_set_warned = False

# Constant-work dummy hash — verify_password runs against this on a username
# mismatch so wrong-user and wrong-password failures take comparable time
# (no timing side-channel for username enumeration).  Generated once at import
# from a random password so it can never match a real credential.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))

# Process-global login rate limiter (module-level by design — see ratelimit.py).
_login_limiter = SlidingWindowRateLimiter()

# 429 body returned once a client exceeds the failed-attempt threshold.
_RATE_LIMITED_DETAIL = "Trop de tentatives — réessayez plus tard."

# Hosts treated as the local reverse proxy (Caddy) so its X-Forwarded-For is
# trusted for per-real-client keying.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _client_key(request: Request) -> str:
    """Derive the rate-limit key identifying the client behind *request*.

    Uses the peer IP normally.  When the peer is loopback — the Caddy TLS proxy
    terminating in front of the app — and an ``X-Forwarded-For`` header is
    present, the LAST forwarded address is used so per-real-client limiting
    survives the reverse proxy.  The rightmost entry is the one appended by
    the trusted local proxy (the address it directly accepted the connection
    from); any earlier entries arrive verbatim from the client and are
    spoofable — keying on them let an attacker rotate a fake leftmost value
    to dodge the login rate limit (R13).

    Args:
        request: The incoming FastAPI request.

    Returns:
        A stable string key identifying the client.
    """
    peer = request.client.host if request.client else "unknown"
    if peer in _LOOPBACK_HOSTS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return peer


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
    SameSite=Strict cookie and clears the client's failure window.  On failure,
    records the attempt and returns 401 — after too many recent failures the
    client is locked out with 429 (non-blocking, no ``time.sleep``).

    Args:
        body: The login credentials (username + password).
        request: The incoming FastAPI request (for app.state access).

    Returns:
        A ``Response`` with status 204 and a ``Set-Cookie`` header on success.

    Raises:
        HTTPException: 429 once the client exceeds the failed-attempt threshold;
            401 if the credentials are invalid or the server is not fully
            configured (missing password hash or JWT secret).
    """
    global _password_not_set_warned, _jwt_secret_not_set_warned

    config = request.app.state.config
    settings = request.app.state.settings
    web_cfg = config.web

    client_key = _client_key(request)

    # Brute-force friction: reject before doing any work once too many recent
    # failures have accrued for this client.  Non-blocking (no threadpool hog).
    if not _login_limiter.allow(client_key):
        raise HTTPException(status_code=429, detail=_RATE_LIMITED_DETAIL)

    # If no password hash is configured, warn once and always reject.
    if not settings.web_password_hash:
        if not _password_not_set_warned:
            logger.warning("web_password_not_set")
            _password_not_set_warned = True
        _login_limiter.record_failure(client_key)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # If no JWT secret is configured, tokens cannot be signed — warn once and
    # reject (mirrors the password-hash lockout).  This keeps an unset secret a
    # clean 401 instead of the PyJWT InvalidKeyError 500 it would otherwise be.
    if not settings.web_jwt_secret:
        if not _jwt_secret_not_set_warned:
            logger.warning("web_jwt_secret_not_set")
            _jwt_secret_not_set_warned = True
        _login_limiter.record_failure(client_key)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Constant-work credential check: run scrypt on BOTH failure paths so a
    # wrong username is indistinguishable by timing from a wrong password.
    username_matches = body.username == web_cfg.username
    if username_matches:
        password_matches = verify_password(body.password, settings.web_password_hash)
    else:
        verify_password(body.password, _DUMMY_HASH)
        password_matches = False

    if not (username_matches and password_matches):
        _login_limiter.record_failure(client_key)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Credentials verified — clear the failure window and issue the session.
    _login_limiter.reset(client_key)
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
