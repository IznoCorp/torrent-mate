"""Firebase Cloud Messaging sender — one push message to one device, over HTTP v1.

The push channel of the ratio alert (``docs/features/backend-bricks/fcm-push/DESIGN.md``;
Q10 2026-10-01: FCM, web push on the installed PWA, Android and iOS). This module
delivers ONE message to ONE registration token and says what happened as an
OUTCOME CODE; who receives a message, when, and in which words are not its
business (the dispatcher fans out, K5 triggers, the device's worker words it).

**A message is facts, never a sentence.** :class:`PushMessage` carries a code, its
parameters and an in-app link; it is sent as a DATA-ONLY web-push message, so the
service worker composes what is shown from ``fr.json`` — the wire carries no
French and no English.

**Fail-soft, like the notify family**: :meth:`FcmSender.send` never raises on a
delivery failure; every failure is a :class:`PushOutcome`:

- ``UNREGISTERED`` (404) → ``TOKEN_DEAD``, revoke it;
- ``INVALID_ARGUMENT`` (400) → ``REJECTED`` — the payload or the token's format;
- any 429 (``QUOTA_EXCEEDED``, Google's ``RESOURCE_EXHAUSTED``, no code at all) →
  ``QUOTA_EXCEEDED``, the PROJECT's quota, at least a minute of back-off;
- ``UNAVAILABLE`` (503), ``INTERNAL`` (500) → ``RETRY_LATER``, with ``Retry-After``
  when given;
- ``SENDER_ID_MISMATCH`` (403), ``THIRD_PARTY_AUTH_ERROR``, a 401 / 403 on OUR
  credentials, an unreadable service-account file, a refused access-token grant →
  ``MISCONFIGURED``. ONE Firebase project serves every environment (F-2), so a token
  of another sender means our service account is the wrong project — revoking the
  token would wipe every device for a configuration fault;
- no answer → ``UNREACHABLE``.

**Secrets never appear anywhere**, the discipline of ``api/plex.py``: the device
token travels in the JSON body and the access token in ``Authorization`` only;
failures log ``error=type(exc).__name__`` and FCM's ``errorCode`` — never the
exception, never ``exc_info`` (the console renderer prints frame locals, and the
frames of ``requests`` hold the headers), never a body; every call catches
``Exception``; redirects are not followed (``requests`` strips only
``Authorization`` on a cross-host redirect, and the body holds the device token).
The service account's private key stays inside the ``google-auth`` credentials
object; :meth:`FcmSender.__repr__` names the project alone.
"""

from __future__ import annotations

import functools
import json
import math
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import requests

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from google.oauth2.service_account import Credentials
    from typing_extensions import Self

log = get_logger("api.fcm")

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

#: Connect / read timeouts. A push is a notification, not a transaction: a slow
#: Google answer is reported UNREACHABLE and the caller decides.
_TIMEOUT: tuple[float, float] = (5.0, 15.0)

#: Firebase asks at least a minute of back-off on QUOTA_EXCEEDED.
_QUOTA_BACKOFF_SECONDS = 60.0

#: The longest ``Retry-After`` honoured: a day, the default TTL of a :class:`PushMessage` —
#: FCM would drop the message by then, so a longer wait is never useful, and a broken or
#: hostile header must not park the channel for years.
RETRY_AFTER_CEILING_SECONDS = 86_400.0

#: The type URL of the FCM-specific error detail, which carries ``errorCode``.
_FCM_ERROR_TYPE = "type.googleapis.com/google.firebase.fcm.v1.FcmError"


class PushOutcome(StrEnum):
    """What one send did — the codes the dispatcher and Système act on."""

    DELIVERED = "delivered"
    TOKEN_DEAD = "token_dead"
    REJECTED = "rejected"
    RETRY_LATER = "retry_later"
    #: The PROJECT's quota (any 429): every other send would meet it too — the fan-out stops.
    QUOTA_EXCEEDED = "quota_exceeded"
    MISCONFIGURED = "misconfigured"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class PushResult:
    """The outcome of one send.

    Attributes:
        outcome: What happened.
        retry_after_seconds: How long to wait before a re-send, on ``RETRY_LATER``.
        fcm_error: FCM's ``errorCode`` (or the HTTP status name), a code — never a body.
    """

    outcome: PushOutcome
    retry_after_seconds: float | None = None
    fcm_error: str | None = None


@dataclass(frozen=True)
class PushMessage:
    """One notification, as FACTS: the device's worker turns the code into words from ``fr.json``.

    Attributes:
        code: A member of the closed push code set (e.g. ``"tracker.ratio_low"``).
        params: The code's typed parameters (``{"tracker": "c411", "ratio": 1.12}``).
        link: The in-app path the click opens — same-origin, never absolute.
        tag: Collapses a newer message onto an older one of the same tag on the device.
        ttl_seconds: How long FCM keeps it for an offline device.
        urgency: Web Push ``Urgency``.
        language: The RECIPIENT account's language (``"fr"``, ``"en"``), which the worker words
            the code in (FG-2 A); ``None`` leaves it out, and the worker words it in English.

    Raises:
        ValueError: ``link`` is not a same-origin path, or ``ttl_seconds`` is negative.
    """

    code: str
    params: Mapping[str, str | int | float] = field(default_factory=dict)
    link: str = "/"
    tag: str | None = None
    ttl_seconds: int = 86_400
    urgency: Literal["normal", "high"] = "normal"
    language: str | None = None

    def __post_init__(self) -> None:
        """Refuses a link that could leave the application, and a negative TTL.

        Raises:
            ValueError: The link is absolute, protocol-relative or not a path; the TTL is negative.
        """
        if not self.link.startswith("/") or self.link.startswith("//") or "\\" in self.link:
            raise ValueError("PushMessage.link must be a same-origin path")
        if self.ttl_seconds < 0:
            raise ValueError("PushMessage.ttl_seconds must not be negative")

    def webpush_data(self) -> dict[str, str]:
        """The ``webpush.data`` map: every value a string, as FCM requires.

        Returns:
            ``{code, params (JSON), link[, tag][, language]}``.
        """
        data = {"code": self.code, "params": json.dumps(dict(self.params), sort_keys=True), "link": self.link}
        if self.tag is not None:
            data["tag"] = self.tag
        if self.language is not None:
            data["language"] = self.language
        return data


def _retry_after(response: requests.Response) -> float | None:
    """Reads ``Retry-After`` as seconds (a number or an HTTP date).

    Args:
        response: The FCM answer.

    Returns:
        Seconds to wait, at most ``RETRY_AFTER_CEILING_SECONDS``; None when absent, unreadable
        or not finite (``inf``, ``1e400``, ``nan``).
    """
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except (TypeError, ValueError, OverflowError):
            return None
    if not math.isfinite(seconds):
        return None
    return min(max(0.0, seconds), RETRY_AFTER_CEILING_SECONDS)


def _error_code(response: requests.Response) -> str | None:
    """Reads FCM's ``errorCode``, else the Google status name, from an error answer.

    Args:
        response: The FCM answer.

    Returns:
        The code (``"UNREGISTERED"``, ``"PERMISSION_DENIED"``…), or None when the body says nothing.
    """
    try:
        error = response.json().get("error") or {}
    except (ValueError, AttributeError):
        return None
    if not isinstance(error, dict):
        return None
    for detail in error.get("details") or []:
        if isinstance(detail, dict) and detail.get("@type") == _FCM_ERROR_TYPE and detail.get("errorCode"):
            return str(detail["errorCode"])
    status = error.get("status")
    return str(status) if status else None


#: FCM errorCode → outcome. The HTTP status decides only when no code is given.
_BY_CODE: Mapping[str, PushOutcome] = {
    "UNREGISTERED": PushOutcome.TOKEN_DEAD,
    # One project (F-2): a token of another sender is OUR service account's fault, never the token's.
    "SENDER_ID_MISMATCH": PushOutcome.MISCONFIGURED,
    "INVALID_ARGUMENT": PushOutcome.REJECTED,
    "QUOTA_EXCEEDED": PushOutcome.QUOTA_EXCEEDED,
    "RESOURCE_EXHAUSTED": PushOutcome.QUOTA_EXCEEDED,
    "UNAVAILABLE": PushOutcome.RETRY_LATER,
    "INTERNAL": PushOutcome.RETRY_LATER,
    "THIRD_PARTY_AUTH_ERROR": PushOutcome.MISCONFIGURED,
    "UNAUTHENTICATED": PushOutcome.MISCONFIGURED,
    "PERMISSION_DENIED": PushOutcome.MISCONFIGURED,
    "NOT_FOUND": PushOutcome.MISCONFIGURED,
}


def classify(response: requests.Response) -> PushResult:
    """Maps one FCM answer to its outcome (Firebase's error-code table).

    Args:
        response: The FCM answer.

    Returns:
        The result. A 404 is a dead TOKEN only when FCM's own ``errorCode`` says so; without
        it (a wrong project, a disabled API) it is our configuration. The quota is decided
        HERE, once: any 429, whatever its body says, is ``QUOTA_EXCEEDED``.
    """
    if response.status_code == 200:
        return PushResult(PushOutcome.DELIVERED)
    code = _error_code(response)
    outcome = PushOutcome.QUOTA_EXCEEDED if response.status_code == 429 else _BY_CODE.get(code or "")
    if outcome is None:
        if response.status_code in (401, 403, 404):
            outcome = PushOutcome.MISCONFIGURED
        elif response.status_code >= 500:
            outcome = PushOutcome.RETRY_LATER
        else:
            outcome = PushOutcome.REJECTED
    retry_after = None
    if outcome is PushOutcome.RETRY_LATER:
        retry_after = _retry_after(response)
    elif outcome is PushOutcome.QUOTA_EXCEEDED:
        retry_after = max(_retry_after(response) or 0.0, _QUOTA_BACKOFF_SECONDS)
    return PushResult(outcome, retry_after_seconds=retry_after, fcm_error=code or f"HTTP_{response.status_code}")


class FcmSender:
    """Firebase Cloud Messaging HTTP v1 — one message, one token. Fail-soft: never raises on delivery.

    Attributes:
        provider_name: ``"fcm"``.
        REQUIRED_CREDS: The ``.env`` variable naming the service-account file.
    """

    provider_name: ClassVar[str] = "fcm"
    REQUIRED_CREDS: ClassVar[list[str]] = ["FCM_SERVICE_ACCOUNT_FILE"]

    def __init__(
        self,
        *,
        project_id: str,
        credentials: Credentials | None,
        session: requests.Session | None = None,
    ) -> None:
        """Builds the sender.

        Args:
            project_id: The Firebase project id (what the send URL names).
            credentials: Service-account credentials scoped to ``FCM_SCOPE``; None when the
                file could not be read — every send then answers ``MISCONFIGURED``.
            session: The HTTP session, for both the token grant and the send (injected in tests).
        """
        from google.auth.transport.requests import Request

        self._project_id = project_id
        self._credentials = credentials
        self._session = session or requests.Session()
        # ONE grant request for the sender's life: google-auth's ``Request`` closes its
        # session when it is collected, so a request built per refresh would close the
        # session the sends use. Bound by the sender's timeout: google-auth's own default
        # is 120 s per attempt, and it retries a transient grant failure itself (3 attempts,
        # exponential back-off) — the one retry this sender does not control.
        self._grant_request = functools.partial(Request(session=self._session), timeout=_TIMEOUT)

    @classmethod
    def from_service_account_file(cls, path: Path, *, session: requests.Session | None = None) -> Self:
        """Reads the project id from the file; the private key stays inside the credentials object.

        Fail-soft: an unreadable or malformed file yields a sender whose sends answer
        ``MISCONFIGURED``, logged with the exception TYPE only (the file holds the key).

        Args:
            path: The service-account JSON file (``FCM_SERVICE_ACCOUNT_FILE``).
            session: The HTTP session.

        Returns:
            The sender.
        """
        from google.oauth2 import service_account

        try:
            credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                str(path), scopes=[FCM_SCOPE]
            )
            project_id = str(credentials.project_id or "")
        except Exception as exc:  # noqa: BLE001 — the file's content must not reach a log or a caller
            log.warning("fcm.service_account_unreadable", error=type(exc).__name__)
            return cls(project_id="", credentials=None, session=session)
        return cls(project_id=project_id, credentials=credentials, session=session)

    @property
    def project_id(self) -> str:
        """The Firebase project id ('' when the service account could not be read)."""
        return self._project_id

    def _access_token(self) -> str | PushResult:
        """Returns a valid access token, minting one when needed.

        Returns:
            The token, or the failure's result (``MISCONFIGURED`` / ``UNREACHABLE``).
        """
        if self._credentials is None or not self._project_id:
            return PushResult(PushOutcome.MISCONFIGURED, fcm_error="NO_CREDENTIALS")
        if self._credentials.valid:
            return str(self._credentials.token)
        from google.auth import exceptions as auth_exceptions

        try:
            self._credentials.refresh(self._grant_request)  # type: ignore[no-untyped-call]
        except auth_exceptions.RefreshError as exc:
            log.warning("fcm.access_token_refused", error=type(exc).__name__)
            return PushResult(PushOutcome.MISCONFIGURED, fcm_error="TOKEN_GRANT_REFUSED")
        except Exception as exc:  # noqa: BLE001 — the assertion and the key live in these frames
            log.warning("fcm.access_token_unreachable", error=type(exc).__name__)
            return PushResult(PushOutcome.UNREACHABLE, fcm_error=type(exc).__name__)
        return str(self._credentials.token)

    def send(self, token: str, message: PushMessage, *, validate_only: bool = False) -> PushResult:
        """Sends one data-only web-push message to one registration token.

        Args:
            token: The device's FCM registration token.
            message: What to say, as facts.
            validate_only: Ask FCM to check the request without delivering it.

        Returns:
            The outcome; never raises on a delivery failure.
        """
        access = self._access_token()
        if isinstance(access, PushResult):
            return access
        body: dict[str, Any] = {
            "message": {
                "token": token,
                "webpush": {
                    "headers": {"TTL": str(message.ttl_seconds), "Urgency": message.urgency},
                    "data": message.webpush_data(),
                },
            }
        }
        if validate_only:
            body["validate_only"] = True
        try:
            response = self._session.post(
                FCM_SEND_URL.format(project_id=self._project_id),
                json=body,
                headers={"Authorization": f"Bearer {access}"},
                timeout=_TIMEOUT,
                allow_redirects=False,
            )
            result = classify(response)
        except Exception as exc:  # noqa: BLE001 — the device and access tokens live in these frames
            log.warning("fcm.send_failed", error=type(exc).__name__)
            return PushResult(PushOutcome.UNREACHABLE, fcm_error=type(exc).__name__)
        if result.outcome is not PushOutcome.DELIVERED:
            log.info("fcm.send_not_delivered", outcome=result.outcome.value, fcm_error=result.fcm_error)
        return result

    def __repr__(self) -> str:
        """``FcmSender(project_id=…)`` — no key, no token."""
        return f"FcmSender(project_id={self._project_id!r})"


__all__ = ["FCM_SCOPE", "FcmSender", "PushMessage", "PushOutcome", "PushResult", "classify"]
