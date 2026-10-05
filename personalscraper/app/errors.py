"""Refusals raised by the application layer, free of any HTTP framework.

v0 answers them through one handler registered in ``web/app.py`` (``{"detail":
detail}`` with the refusal's ``status``), byte-for-byte what Starlette's
``HTTPException`` handler answers for the statuses used here. v1 answers them as
the contract's ``Problem``, from the refusal's ``code`` and ``params``
(``http_v1/problem.py``): the interface composes its sentence from those, never
from ``detail``.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, TypeAlias

#: The typed facts a refusal carries for the interface's sentence — never a sentence.
RefusalParams: TypeAlias = Mapping[str, str | int | float | bool | list[str]]


class RefusalCode(StrEnum):
    """The closed set of refusal codes v1 answers (X4).

    Each lot adds its members; the interface owns every word (``fr.json``, by code).
    """

    REQUEST_INVALID = "request.invalid"
    REQUEST_CROSS_ORIGIN = "request.cross_origin"
    ROUTE_UNKNOWN = "route.unknown"
    INTERNAL = "internal"
    AUTH_REQUIRED = "auth.required"
    AUTH_REFUSED = "auth.refused"
    AUTH_PLEX_ONLY = "auth.plex_only"
    AUTH_RATE_LIMITED = "auth.rate_limited"
    AUTH_ACCESS_DISABLED = "auth.access_disabled"
    RIGHT_MISSING = "right.missing"
    INSTANCE_READ_ONLY = "instance.read_only"
    INSTANCE_FORBIDDEN_WRITE = "instance.forbidden_write"
    ACCOUNT_UNKNOWN = "account.unknown"
    ACCOUNT_EMAIL_INVALID = "account.email_invalid"
    ACCOUNT_EMAIL_TAKEN = "account.email_taken"
    ACCOUNT_ADMIN_UNTOUCHABLE = "account.admin_untouchable"
    ACCOUNT_LAST_ADMIN = "account.last_admin"
    ACCOUNT_ACCESS_ADMIN_ONLY = "account.access_admin_only"
    ACCOUNT_OWNER_ACCESS = "account.owner_access"
    ACCOUNT_OWN_ACCESS = "account.own_access"
    ACCOUNT_ADMIN_OWNER_ONLY = "account.admin_owner_only"
    ACCOUNT_OWNER_ADMIN = "account.owner_admin"
    ROLE_UNKNOWN = "role.unknown"
    ROLE_SYSTEM_IMMUTABLE = "role.system_immutable"
    ROLE_OWN_ROLE = "role.own_role"
    ROLE_ESCALATION = "role.escalation"
    ROLE_NAME_REQUIRED = "role.name_required"
    ROLE_NAME_TAKEN = "role.name_taken"
    ROLE_IN_USE = "role.in_use"
    ROLE_DEFAULT = "role.default"
    RIGHT_UNKNOWN = "right.unknown"
    PASSWORD_REQUIRED = "password.required"
    PASSWORD_TOO_SHORT = "password.too_short"
    PASSWORD_TOO_WEAK = "password.too_weak"
    PASSWORD_CURRENT_WRONG = "password.current_wrong"
    PASSWORD_HELD_BY_CLI = "password.held_by_cli"
    PASSWORD_RESET_ADMIN_ONLY = "password.reset_admin_only"
    PASSWORD_RESET_OWN = "password.reset_own"
    PLEX_UNREACHABLE = "plex.unreachable"
    PLEX_SERVER_UNREACHABLE = "plex.server_unreachable"
    PLEX_TOKEN_REFUSED = "plex.token_refused"
    PLEX_PIN_UNKNOWN = "plex.pin_unknown"
    PLEX_PIN_EXPIRED = "plex.pin_expired"
    MEDIA_NOT_FOUND = "media.not_found"
    MEDIA_AMBIGUOUS = "media.ambiguous"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    LIBRARY_LOCKED = "library.locked"
    LIBRARY_OBLIGATIONS_UNREADABLE = "library.obligations_unreadable"


class AppRefusal(Exception):
    """A refusal raised by the application layer, answered by v0 as ``{"detail": detail}`` with ``status``.

    Attributes:
        status: The HTTP status both v0 and v1 answer it with.
        detail: The refusal's text, carried verbatim from the v0 raise it replaces; v1
            answers it as the Problem's English developer line.
        code: The refusal's code, which v1 answers; ``None`` only on a refusal v0 alone
            raises (v1 answers a code-less refusal as an ``internal`` defect).
        params: The typed facts the interface composes its sentence from (empty when none).

    ``detail`` and ``params`` reach the wire verbatim, so they never carry an
    exception's text, a path, a token or any value from configuration.
    """

    status: ClassVar[int] = 500

    def __init__(
        self,
        detail: str,
        *,
        code: RefusalCode | None = None,
        params: RefusalParams | None = None,
    ) -> None:
        """Carry the refusal's text, its code and its facts.

        Args:
            detail: The refusal's text, answered verbatim as the v0 ``detail``.
            code: The refusal's code, answered by v1.
            params: The typed facts of the refusal; ``None`` means none.
        """
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.params: RefusalParams = params if params is not None else {}


class AppBadRequest(AppRefusal):
    """The request carries a body or a parameter the contract refuses."""

    status = 400


class AppUnauthenticated(AppRefusal):
    """The request carries no valid session."""

    status = 401


class AppForbidden(AppRefusal):
    """The caller may not do this: a right not held, an instance ceiling, an escalation."""

    status = 403


class AppNotFound(AppRefusal):
    """The named subject does not exist."""

    status = 404


class AppConflict(AppRefusal):
    """The request conflicts with the current state (a duplicate, an already-running launch)."""

    status = 409


class AppValidationError(AppRefusal):
    """The request's options failed validation."""

    status = 422


class AppPreconditionRequired(AppRefusal):
    """A precondition (a fresh dry-run) is required before the request is accepted."""

    status = 428


class AppInternalError(AppRefusal):
    """The application layer failed to carry out an accepted request."""

    status = 500


class AppTooManyRequests(AppRefusal):
    """The caller exceeded a rate limit (the sign-in limiter)."""

    status = 429


class AppUnavailable(AppRefusal):
    """A dependency the request needs is down (plex.tv, the torrent client)."""

    status = 503
