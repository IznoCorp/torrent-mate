"""JWT session token creation and decoding (tm-shell feature).

Pure functions with no FastAPI or request dependency — testable standalone.
Uses PyJWT HS256. See docs/features/tm-shell/DESIGN.md §4.4 for the auth design.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


def create_session_token(username: str, secret: str, ttl_hours: int) -> str:
    """Create a JWT session token for the given user.

    The token carries ``{sub, iat, exp}`` claims with UTC timestamps.

    Args:
        username: The username to embed in the ``sub`` claim.
        secret: The HS256 signing secret.
        ttl_hours: Token time-to-live in hours.

    Returns:
        A signed JWT string.

    Raises:
        ValueError: If *secret* is empty.  PyJWT raises ``InvalidKeyError`` on
            an empty HMAC key; we surface a clear ``ValueError`` so the login
            route can convert it to a 401 lockout (mirrors the empty
            password-hash guard) instead of leaking a 500.
    """
    if not secret:
        raise ValueError("web_jwt_secret is not set")
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_session_token(token: str, secret: str) -> dict[str, Any] | None:
    """Decode and validate a JWT session token.

    Args:
        token: The JWT string to decode.
        secret: The HS256 signing secret.

    Returns:
        The claims dict on success, or ``None`` if the token is expired,
        malformed, signed with the wrong secret, or the secret itself is
        invalid (e.g. empty). Never raises.
    """
    # ``InvalidKeyError`` (raised for an empty secret) is a ``PyJWTError`` but
    # NOT an ``InvalidTokenError`` in PyJWT 2.x — catching ``PyJWTError`` covers
    # it.  ``ValueError`` is caught for defence in depth against any non-JWT
    # value error so this stays a true "never raises" contract.
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except (jwt.PyJWTError, jwt.InvalidKeyError, ValueError):
        return None
