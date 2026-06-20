"""Session-cookie login for the config UI (bridge — protect internet exposure).

The config UI is loopback by default, but the operator fronts it with a reverse proxy
(``km.iznogoudatall.xyz`` via Caddy/TLS) to use it remotely. This module adds an optional
single-operator login so an exposed UI is not world-open.

Design (single operator, no DB):

* **Credentials** come from the environment (``KANBAN_MATE_UI_LOGIN`` /
  ``KANBAN_MATE_UI_PASSWORD``), loaded from the operator's gitignored ``.env`` by
  ``cli/config.py``. An **empty password DISABLES the login** (open — loopback/dev), per the
  operator's contract.
* **Session token** — a signed, expiring token (HMAC-SHA256 over ``login:expiry`` with a server
  secret), carried in an ``HttpOnly`` cookie. No server-side session store; verification is a
  constant-time signature + expiry check. Stdlib only — no new dependency.
* **Constant-time** credential comparison (:func:`hmac.compare_digest`) to avoid timing oracles.

Layering: ``http`` is a top entrypoint; this module is pure stdlib (no I/O) so the config API and
its tests can import it freely.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass

# The session cookie name + default lifetime (24h).
COOKIE_NAME = "km_ui_session"
DEFAULT_TTL_SECONDS = 24 * 3600


@dataclass(frozen=True)
class AuthConfig:
    """Resolved UI auth configuration.

    Args:
        login: The expected username.
        password: The expected password. EMPTY string disables the login (open).
        secret: The HMAC signing secret for session tokens (hex/opaque string).
        ttl: Session lifetime in seconds.
    """

    login: str
    password: str
    secret: str
    ttl: int = DEFAULT_TTL_SECONDS

    @property
    def enabled(self) -> bool:
        """``True`` when a non-empty password is configured (login required)."""
        return bool(self.password)


def verify_credentials(config: AuthConfig, login: str, password: str) -> bool:
    """Constant-time check of submitted credentials against the configured ones.

    Args:
        config: The resolved auth configuration.
        login: The submitted username.
        password: The submitted password.

    Returns:
        ``True`` when both match (and auth is enabled); ``False`` otherwise. Both comparisons
        always run (no short-circuit) to keep the timing independent of which field is wrong.
    """
    if not config.enabled:
        return False
    login_ok = hmac.compare_digest(login.encode("utf-8"), config.login.encode("utf-8"))
    pw_ok = hmac.compare_digest(password.encode("utf-8"), config.password.encode("utf-8"))
    return login_ok and pw_ok


def make_token(
    login: str, secret: str, ttl: int = DEFAULT_TTL_SECONDS, *, now: float | None = None
) -> str:
    """Mint a signed, expiring session token for ``login``.

    Args:
        login: The authenticated username to embed.
        secret: The HMAC signing secret.
        ttl: Lifetime in seconds from ``now``.
        now: Current epoch seconds (injectable for tests); defaults to :func:`time.time`.

    Returns:
        A URL-safe base64 token ``base64(login:expiry:hexsig)``.
    """
    current = time.time() if now is None else now
    expiry = int(current) + ttl
    payload = f"{login}:{expiry}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode("utf-8")).decode("ascii")


def verify_token(token: str, secret: str, *, now: float | None = None) -> str | None:
    """Verify a session token and return its login, or ``None`` if invalid/expired.

    Args:
        token: The token from the session cookie.
        secret: The HMAC signing secret.
        now: Current epoch seconds (injectable for tests); defaults to :func:`time.time`.

    Returns:
        The embedded login when the signature is valid AND not expired; otherwise ``None``.
    """
    current = time.time() if now is None else now
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        login, expiry_str, sig = raw.rsplit(":", 2)
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None
    expected = hmac.new(
        secret.encode("utf-8"), f"{login}:{expiry_str}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        if int(expiry_str) <= int(current):
            return None
    except ValueError:
        return None
    return login
