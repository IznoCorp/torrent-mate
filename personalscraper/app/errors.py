"""Refusals raised by the application layer, free of any HTTP framework.

v0 answers them through one handler registered in ``web/app.py`` (``{"detail":
detail}`` with the refusal's ``status``), byte-for-byte what Starlette's
``HTTPException`` handler answers for the statuses used here. The v1 shape is
the contract's, not this one.
"""

from __future__ import annotations

from typing import ClassVar


class AppRefusal(Exception):
    """A refusal raised by the application layer, answered by v0 as ``{"detail": detail}`` with ``status``.

    Attributes:
        status: The HTTP status class v0 answers it with (the v1 shape is the contract's, not this).
        detail: The refusal's text, carried verbatim from the v0 raise it replaces.
    """

    status: ClassVar[int] = 500

    def __init__(self, detail: str) -> None:
        """Carry the refusal's text.

        Args:
            detail: The refusal's text, answered verbatim as the v0 ``detail``.
        """
        super().__init__(detail)
        self.detail = detail


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
