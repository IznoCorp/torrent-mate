"""plex.tv ACCOUNT client — a PIN, the identity behind a token, and its access to this server.

The server client (``api/plex.py``) speaks to the operator's Plex Media Server with the
operator's token. This module speaks to plex.tv on behalf of a person signing in: it creates a
strong PIN, builds the page where the person confirms it, checks the PIN once, reads the
identity behind the token the PIN yields, and tells whether that identity OWNS this server, is
a member of its owner's Plex Home, is a user it is SHARED with, or none of these
(``docs/features/backend-bricks/plex-sso/DESIGN.md`` § 3; protocol: Plex's article
« Authenticating with Plex », and ``docs/reference/plex-account-api.md``).

**Stateless.** Every call takes what it needs; nothing is stored. The user's token is the
return value of :meth:`PlexAccountClient.check_pin` and the argument of
:meth:`PlexAccountClient.account` / :meth:`PlexAccountClient.server_access` — the caller
decides what becomes of it (DESIGN P-3).

**Only a 401 is a refusal.** plex.tv's article: a 401 proves a token invalid, any other status
or no answer proves nothing. Every other failure is :class:`PlexAccountUnreachable`, so the
sign-in never tells someone « refused » because plex.tv was slow.

**The token, the PIN code and the e-mail never appear anywhere** — the server client's three
rules (``api/plex.py``), applied to a token that is not ours:

1. failures log ``error=type(exc).__name__``, never the exception, never ``exc_info`` — the
   console renderer expands a traceback with frame locals, and the frames of ``requests`` hold
   the header dict;
2. every call catches ``Exception`` and re-raises a :class:`PlexAccountError` WITHOUT its
   cause (``from None``), whose text names the path and the exception type only;
3. redirects are not followed — ``requests`` strips only ``Authorization`` on a cross-host
   redirect, so a 302 would hand ``X-Plex-Token`` to another origin.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode

import requests

from personalscraper.logger import get_logger

log = get_logger("api.plex_account")

PLEX_TV = "https://plex.tv"
PLEX_AUTH_APP = "https://app.plex.tv/auth"

#: Connect / read budget. A person waits at the sign-in: bounded, and one attempt.
_TIMEOUT: tuple[float, float] = (3.0, 10.0)

#: The statuses plex.tv answers a check of a PIN past its lifetime. INFERRED: no capture holds an
#: expired PIN; the probe's fake and python-plexapi's handling point at a 404, 410 is its twin.
_PIN_GONE: frozenset[int] = frozenset({404, 410})


class PlexServerAccess(StrEnum):
    """What one Plex account is to THIS server — the codes the sign-in decides on."""

    #: The resource whose ``clientIdentifier`` is this server's ``machineIdentifier``, ``owned``.
    OWNER = "owner"
    #: That resource present, not owned, ``home`` set: a member of the owner's Plex Home.
    #: INFERRED from the ``home`` flag; to confirm with a real Home member's capture.
    HOME = "home"
    #: That resource present, not owned, not ``home``: the server is shared with the account.
    SHARED = "shared"
    #: No resource of this server in the account's list.
    NONE = "none"


@dataclass(frozen=True)
class PlexPin:
    """A strong PIN awaiting its sign-in. Carries no token.

    Attributes:
        id: plex.tv's PIN id (what a check reads).
        code: The PIN code (what the sign-in URL carries); kept out of the ``repr``.
        expires_at: Epoch seconds, from the answer's ``expiresAt`` when it carries one, else None.
    """

    id: int
    code: str = field(repr=False)
    expires_at: float | None


@dataclass(frozen=True)
class PlexAccount:
    """The identity behind a token — the only facts the sign-in needs, and no token.

    Attributes:
        plex_id: plex.tv's stable account id (``id``) — the key, never the e-mail or the name.
        uuid: plex.tv's account uuid.
        username: The account's username.
        title: The display name (``title``), what the interface shows.
        email: The account's e-mail, as plex.tv holds it — what links a local account (§ 17);
            kept out of the ``repr``.
        thumb: The avatar URL, None when the answer carries none.
    """

    plex_id: int
    uuid: str
    username: str
    title: str
    email: str = field(repr=False)
    thumb: str | None


class PlexAccountError(Exception):
    """Base. Its text never carries a token, a PIN code or an e-mail."""


class PlexAccountUnreachable(PlexAccountError):
    """plex.tv did not answer, or answered anything but the protocol's answer — the gate opens the password (F47)."""


class PlexTokenRefused(PlexAccountError):
    """plex.tv answered 401 to the token — the sign-in is refused, nothing is wrong with plex.tv."""


class PlexPinExpired(PlexAccountError):
    """The PIN is past its lifetime — the gesture starts again."""


class PlexAccountClient:
    """The plex.tv ACCOUNT side. Stateless; the token it is handed never outlives the call."""

    def __init__(self, *, product: str, client_identifier: str, session: requests.Session | None = None) -> None:
        """Store the application's names on plex.tv.

        Args:
            product: ``X-Plex-Product`` and the sign-in URL's device product — the name plex.tv
                lists under « Authorized Devices » (one per environment).
            client_identifier: ``X-Plex-Client-Identifier`` — generated ONCE per environment and
                re-used (Plex's article); persisted by the caller, passed in here.
            session: Injected in tests; production lets the client own one.
        """
        self._product = product
        self._client_identifier = client_identifier
        self._session = session if session is not None else requests.Session()

    def __repr__(self) -> str:
        """Return a repr without the client identifier or any token."""
        return f"PlexAccountClient(product={self._product!r})"

    # -- HTTP ---------------------------------------------------------------

    def _call(
        self,
        method: str,
        path: str,
        *,
        label: str,
        token: str | None = None,
        params: Mapping[str, str] | None = None,
    ) -> tuple[int, Any]:
        """Issue one request to plex.tv and parse its body.

        Args:
            method: ``GET`` or ``POST``.
            path: plex.tv-absolute path (``/api/v2/user``).
            label: The path as it may be logged — a template, never a value (``/api/v2/pins/{id}``).
            token: A Plex token, sent in ``X-Plex-Token`` only — never in the URL or the params.
            params: Query parameters — never a token.

        Returns:
            The status and the parsed JSON body, or ``None`` for a body that is not JSON.

        Raises:
            PlexAccountUnreachable: No answer; the transport's exception is NOT chained, its
                text and its frames hold the headers.
        """
        headers = {
            "Accept": "application/json",
            "X-Plex-Product": self._product,
            "X-Plex-Client-Identifier": self._client_identifier,
        }
        if token is not None:
            headers["X-Plex-Token"] = token
        try:
            response = self._session.request(
                method,
                f"{PLEX_TV}{path}",
                params=params,
                headers=headers,
                timeout=_TIMEOUT,
                allow_redirects=False,
            )
        except Exception as exc:  # noqa: BLE001 — a token-bearing frame must not escape
            log.warning("plex_account.unreachable", path=label, error=type(exc).__name__)
            raise PlexAccountUnreachable(f"{method} {label} failed: {type(exc).__name__}") from None
        try:
            body: Any = response.json()
        except Exception:  # noqa: BLE001 — an HTML page or a truncated body is « no answer »
            body = None
        return response.status_code, body

    @staticmethod
    def _unreachable(method: str, label: str, status: int) -> PlexAccountUnreachable:
        """Log and build the error of an answer outside the protocol.

        Args:
            method: The HTTP method.
            label: The logged path template.
            status: The HTTP status.

        Returns:
            The error to raise; its text names the path and the status only.
        """
        log.warning("plex_account.unexpected_answer", path=label, status=status)
        return PlexAccountUnreachable(f"{method} {label} answered HTTP {status} outside the protocol")

    # -- The protocol -------------------------------------------------------

    def create_pin(self) -> PlexPin:
        """Create a strong PIN: ``POST /api/v2/pins?strong=true``.

        Returns:
            The PIN, its expiry read from ``expiresAt`` when present.

        Raises:
            PlexAccountUnreachable: No answer, or not a PIN.
        """
        label = "/api/v2/pins"
        status, body = self._call("POST", label, label=label, params={"strong": "true"})
        if status not in (200, 201) or not isinstance(body, dict):
            raise self._unreachable("POST", label, status)
        pin_id, code = body.get("id"), body.get("code")
        if not isinstance(pin_id, int) or isinstance(pin_id, bool) or not isinstance(code, str) or not code:
            raise self._unreachable("POST", label, status)
        return PlexPin(id=pin_id, code=code, expires_at=_epoch(body.get("expiresAt")))

    def sign_in_url(self, pin: PlexPin, *, forward_url: str | None = None) -> str:
        """Build the page where the person confirms the PIN. Pure: no request.

        Args:
            pin: The PIN :meth:`create_pin` answered.
            forward_url: Where plex.tv sends the window once confirmed; without it the window
                stays on Plex.

        Returns:
            ``https://app.plex.tv/auth#?clientID=…&code=…&context%5Bdevice%5D%5Bproduct%5D=…[&forwardUrl=…]``.
        """
        query = {"clientID": self._client_identifier, "code": pin.code, "context[device][product]": self._product}
        if forward_url is not None:
            query["forwardUrl"] = forward_url
        return f"{PLEX_AUTH_APP}#?{urlencode(query)}"

    def check_pin(self, pin_id: int, code: str) -> str | None:
        """Check a PIN ONCE: ``GET /api/v2/pins/{id}``. No loop — the caller owns the cadence (≥ 1 s).

        Args:
            pin_id: The PIN's id.
            code: The PIN's code.

        Returns:
            The user's token once the PIN is claimed, None while it is pending.

        Raises:
            PlexPinExpired: plex.tv no longer knows the PIN (404 / 410 — inferred).
            PlexAccountUnreachable: Any other failure.
        """
        label = "/api/v2/pins/{id}"
        status, body = self._call("GET", f"/api/v2/pins/{pin_id}", label=label, params={"code": code})
        if status in _PIN_GONE:
            raise PlexPinExpired("the PIN is past its lifetime")
        if status != 200 or not isinstance(body, dict):
            raise self._unreachable("GET", label, status)
        token = body.get("authToken")
        return token if isinstance(token, str) and token else None

    def account(self, token: str) -> PlexAccount:
        """Read the identity behind a token: ``GET /api/v2/user``.

        Args:
            token: The user's Plex token.

        Returns:
            The identity.

        Raises:
            PlexTokenRefused: plex.tv answered 401.
            PlexAccountUnreachable: Any other failure, an identity without an id or an e-mail included.
        """
        label = "/api/v2/user"
        status, body = self._call("GET", label, label=label, token=token)
        if status == 401:
            raise PlexTokenRefused("plex.tv refused the token")
        if status != 200 or not isinstance(body, dict):
            raise self._unreachable("GET", label, status)
        plex_id, email = body.get("id"), body.get("email")
        if not isinstance(plex_id, int) or isinstance(plex_id, bool) or not isinstance(email, str) or not email:
            raise self._unreachable("GET", label, status)
        thumb = body.get("thumb")
        return PlexAccount(
            plex_id=plex_id,
            uuid=str(body.get("uuid") or ""),
            username=str(body.get("username") or ""),
            title=str(body.get("title") or body.get("username") or ""),
            email=email,
            thumb=thumb if isinstance(thumb, str) and thumb else None,
        )

    def server_access(self, token: str, machine_identifier: str) -> PlexServerAccess:
        """Tell what the account is to this server: ``GET /api/v2/resources?includeHttps=1``.

        Read WITH THE USER'S OWN TOKEN: the resource list answers « which servers can this
        account reach, and does it own them » without the owner's token (DESIGN § 3.3).

        Args:
            token: The user's Plex token.
            machine_identifier: This server's ``machineIdentifier`` (``PlexClient.machine_identifier``).

        Returns:
            OWNER when the account owns this server's resource, HOME when the resource is not
            owned and flagged ``home``, SHARED when it is neither, NONE when it is absent.

        Raises:
            PlexTokenRefused: plex.tv answered 401.
            PlexAccountUnreachable: Any other failure.
        """
        label = "/api/v2/resources"
        status, body = self._call("GET", label, label=label, token=token, params={"includeHttps": "1"})
        if status == 401:
            raise PlexTokenRefused("plex.tv refused the token")
        if status != 200 or not isinstance(body, list):
            raise self._unreachable("GET", label, status)
        for resource in body:
            if isinstance(resource, dict) and resource.get("clientIdentifier") == machine_identifier:
                if _flag(resource.get("owned")):
                    return PlexServerAccess.OWNER
                return PlexServerAccess.HOME if _flag(resource.get("home")) else PlexServerAccess.SHARED
        return PlexServerAccess.NONE


def _flag(value: object) -> bool:
    """Read one of plex.tv's booleans, which the v2 API sends as JSON booleans and older answers as 0/1.

    Args:
        value: The raw value.

    Returns:
        True for ``true``, ``1`` or ``"1"``.
    """
    return value is True or value == 1 or value == "1"


def _epoch(value: object) -> float | None:
    """Convert plex.tv's ISO-8601 ``expiresAt`` to epoch seconds.

    Args:
        value: The raw value (``2026-10-04T12:47:35Z``).

    Returns:
        Epoch seconds, or None when absent or unreadable.
    """
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None
