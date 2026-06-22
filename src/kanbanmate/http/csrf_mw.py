"""App-wide double-submit CSRF middleware (bosun §6).

Closes the pre-existing gap (no CSRF anywhere today — DESIGN §4 CSRF row) and protects every mutating
request, including the pre-existing unprotected writes (POST /api/config, POST /api/board/provision,
PATCH /api/projects/{id}). Double-submit needs no server-side state: the non-HttpOnly ``km_csrf``
cookie value need only match the ``X-KM-CSRF`` header (an attacker cannot read the cookie cross-site
under SOP, so cannot forge the header).

Design refinement (2.3 gate): enforcement is **gated on auth being enabled**, mirroring
``config_api._auth_guard``. CSRF only protects an AUTHENTICATED session — when auth is disabled the
server is a fully-open loopback dev instance with no session to protect, so enforcement is skipped
(this also keeps the ~34 existing mutating-endpoint tests, which run with auth disabled, green). The
``km_csrf`` cookie is ALWAYS minted (regardless of auth state) so the SPA can read + echo it. Both
``/api/login`` and ``/api/logout`` are exempt (the auth lifecycle: login has no prior cookie; logout
must never wedge on a missing token).
"""

from __future__ import annotations

import hmac
import secrets
from typing import TYPE_CHECKING, Awaitable, Callable

import fastapi

from kanbanmate.http.config_api import _auth_config, _request_is_secure, app

if TYPE_CHECKING:
    from starlette.responses import Response

_CSRF_COOKIE = "km_csrf"
_CSRF_HEADER = "x-km-csrf"
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# The auth lifecycle endpoints: login SETS the session (no prior cookie); logout must not be wedged
# by a missing/mismatched CSRF token (DESIGN §6, 2.3 refinement).
_EXEMPT_PATHS = frozenset({"/api/login", "/api/logout"})


@app.middleware("http")
async def _csrf_guard(
    request: fastapi.Request,
    call_next: Callable[[fastapi.Request], Awaitable[Response]],
) -> Response:
    """Reject mutating /api/ requests whose X-KM-CSRF header != km_csrf cookie (DESIGN §6).

    Enforcement is gated on auth being enabled (a session must exist to protect); when auth is
    disabled the check is skipped entirely. The ``km_csrf`` cookie is always minted on any response
    whose request lacked it, so the SPA can read + echo it regardless of auth state.

    Args:
        request: The incoming request.
        call_next: The downstream ASGI handler.

    Returns:
        A 403 :class:`~starlette.responses.JSONResponse` on a failed double-submit check (only when
        enforcement applies), otherwise the downstream response (with a freshly minted ``km_csrf``
        cookie when the request lacked one).
    """
    config = _auth_config()
    method = request.method.upper()
    path = request.url.path
    # Gate on auth ENABLED: CSRF only protects an authenticated session. With auth off the server is
    # open loopback dev — there is no session to forge against, and enforcing would retroactively 403
    # the existing auth-off mutating tests (2.3 refinement, DESIGN §6).
    enforce = (
        config is not None
        and config.enabled
        and method in _MUTATING
        and path.startswith("/api/")
        and path not in _EXEMPT_PATHS
    )
    if enforce:
        cookie = request.cookies.get(_CSRF_COOKIE, "")
        header = request.headers.get(_CSRF_HEADER, "")
        if not cookie or not header or not hmac.compare_digest(cookie, header):
            return fastapi.responses.JSONResponse(
                status_code=403, content={"detail": "CSRF token missing or mismatched"}
            )
    response = await call_next(request)
    # Always mint the cookie when absent (regardless of auth state) so the SPA can read + echo it.
    if _CSRF_COOKIE not in request.cookies:
        response.set_cookie(
            _CSRF_COOKIE,
            secrets.token_urlsafe(32),
            # SameSite=Strict (defense-in-depth, bosun review-c3): single-operator UI with no
            # cross-site navigation, so the CSRF token cookie need never ride a cross-site request —
            # Strict matches the session cookie and adds a second layer over the double-submit check.
            samesite="strict",
            secure=_request_is_secure(request),
            path="/",
            httponly=False,
        )
    return response
