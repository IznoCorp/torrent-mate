"""v1 answers every refusal and every failure as a ``Problem`` (X1, DESIGN C.4).

The handlers are registered on the v1 sub-application only: a v0 answer never
becomes a ``Problem``, and v0's ``{"detail"}`` handler never touches a v1 answer.
An unhandled exception is answered by :class:`ProblemOnCrash`, a pure ASGI guard,
rather than by an ``Exception`` handler: Starlette's ``ServerErrorMiddleware``
re-raises after answering, and inside a mount the exception would then reach the
parent with the response already started.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from personalscraper.app.errors import AppRefusal, RefusalCode
from personalscraper.http_v1.contract import Problem
from personalscraper.logger import get_logger

log = get_logger("http_v1.problem")

#: The one English title of each refusal code; the interface's words come from ``fr.json``.
REFUSAL_TITLES: Final[Mapping[RefusalCode, str]] = {
    RefusalCode.REQUEST_INVALID: "The request is invalid.",
    RefusalCode.REQUEST_CROSS_ORIGIN: "The request comes from another origin.",
    RefusalCode.ROUTE_UNKNOWN: "No operation answers this method and path.",
    RefusalCode.INTERNAL: "The server failed.",
    RefusalCode.AUTH_REQUIRED: "A signed-in session is required.",
    RefusalCode.AUTH_REFUSED: "The sign-in was refused.",
    RefusalCode.AUTH_PLEX_ONLY: "This account signs in with Plex and holds no password here.",
    RefusalCode.AUTH_RATE_LIMITED: "Too many failed attempts; try again later.",
    RefusalCode.AUTH_ACCESS_DISABLED: "This account's access is cut.",
    RefusalCode.RIGHT_MISSING: "A right is missing.",
    RefusalCode.INSTANCE_READ_ONLY: "This instance is read-only.",
    RefusalCode.INSTANCE_FORBIDDEN_WRITE: "This instance forbids this write.",
    RefusalCode.ACCOUNT_UNKNOWN: "No account answers this identity.",
    RefusalCode.ACCOUNT_EMAIL_INVALID: "The account's name or e-mail is invalid.",
    RefusalCode.ACCOUNT_EMAIL_TAKEN: "An account already carries this e-mail.",
    RefusalCode.ACCOUNT_ADMIN_UNTOUCHABLE: "Only an Admin touches the Admin role.",
    RefusalCode.ACCOUNT_LAST_ADMIN: "No account would be left on the Admin role.",
    RefusalCode.ACCOUNT_ACCESS_ADMIN_ONLY: "Only an Admin cuts or gives back an account's access.",
    RefusalCode.ACCOUNT_OWNER_ACCESS: "The server owner's access is never cut.",
    RefusalCode.ACCOUNT_OWN_ACCESS: "An Admin never cuts its own access.",
    RefusalCode.ACCOUNT_ADMIN_OWNER_ONLY: "Only the server's owner gives the Admin role.",
    RefusalCode.ROLE_UNKNOWN: "No role answers this identity.",
    RefusalCode.ROLE_SYSTEM_IMMUTABLE: "The Admin role is not modified.",
    RefusalCode.ROLE_OWN_ROLE: "A manager who is not Admin never touches its own role.",
    RefusalCode.ROLE_ESCALATION: "The change would give rights the caller's role does not hold.",
    RefusalCode.ROLE_NAME_REQUIRED: "A role carries the name the manager typed.",
    RefusalCode.ROLE_NAME_TAKEN: "Another role already carries this name.",
    RefusalCode.ROLE_IN_USE: "An account holds this role.",
    RefusalCode.ROLE_DEFAULT: "A newcomer starts on this role.",
    RefusalCode.RIGHT_UNKNOWN: "No right answers this name.",
    RefusalCode.PASSWORD_REQUIRED: "A local account starts with a password.",
    RefusalCode.PASSWORD_TOO_SHORT: "The password is shorter than the minimum.",
    RefusalCode.PASSWORD_TOO_WEAK: "The password lacks an uppercase letter, a digit or a special character.",
    RefusalCode.PASSWORD_CURRENT_WRONG: "The current password does not match.",
    RefusalCode.PASSWORD_HELD_BY_CLI: "The server owner's fallback password is changed on the server only.",
    RefusalCode.PASSWORD_RESET_ADMIN_ONLY: "Only an Admin resets a password.",
    RefusalCode.PASSWORD_RESET_OWN: "An Admin changes its own password with its current one.",
    RefusalCode.MEDIA_NOT_FOUND: "No medium answers this provider identity.",
    RefusalCode.PROVIDER_UNAVAILABLE: "A metadata provider did not answer.",
}

_INTERNAL_DETAIL: Final[str] = "An unexpected error occurred."
_ROUTE_UNKNOWN_STATUSES: Final[frozenset[int]] = frozenset({404, 405})


def problem_response(
    status: int,
    code: RefusalCode,
    detail: str,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the JSON answer of one ``Problem``.

    Args:
        status: The HTTP status.
        code: The refusal's code; its title comes from :data:`REFUSAL_TITLES`.
        detail: The English developer line.
        params: The typed facts of the refusal.
        headers: Extra response headers (``Allow`` on a 405).

    Returns:
        The response, media type ``application/json`` as the contract declares.
    """
    body = Problem(status=status, title=REFUSAL_TITLES[code], detail=detail, code=code, params=dict(params or {}))
    return JSONResponse(
        body.model_dump(mode="json", by_alias=True),
        status_code=status,
        headers=dict(headers) if headers else None,
    )


def _internal() -> JSONResponse:
    """Build the 500 ``internal`` answer, which says nothing of the failure.

    Returns:
        The response.
    """
    return problem_response(500, RefusalCode.INTERNAL, _INTERNAL_DETAIL)


def install_problem_handlers(app: FastAPI) -> None:
    """Register the handlers answering refusals, refused requests and unknown routes as ``Problem``.

    Args:
        app: The v1 sub-application (never the v0 parent).
    """

    @app.exception_handler(AppRefusal)
    async def _app_refusal(request: Request, exc: AppRefusal) -> JSONResponse:
        """Answer an application-layer refusal.

        Args:
            request: The refused request.
            exc: The refusal.

        Returns:
            Its status, code and params; a code-less refusal is a v1 defect, answered 500.
        """
        if exc.code is None:
            log.error("v1_codeless_refusal", refusal=type(exc).__name__, path=request.url.path)
            return _internal()
        return problem_response(exc.status, exc.code, exc.detail, exc.params)

    @app.exception_handler(RequestValidationError)
    async def _request_invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Answer a body or parameter the contract refuses, naming where and never the value.

        Args:
            _: The refused request (unused).
            exc: FastAPI's validation failure.

        Returns:
            400 ``request.invalid``, ``params.fields`` the dotted locations.
        """
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        return problem_response(
            400,
            RefusalCode.REQUEST_INVALID,
            "The request does not match the contract.",
            {"fields": fields},
        )

    @app.exception_handler(HTTPException)
    async def _http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        """Answer the router's own refusals: no route at that path, or not under that method.

        Args:
            request: The refused request.
            exc: The router's exception.

        Returns:
            404/405 ``route.unknown``; any other status is a v1 defect (a v1 route raises
            refusals, never ``HTTPException``), answered 500.
        """
        if exc.status_code in _ROUTE_UNKNOWN_STATUSES:
            return problem_response(
                exc.status_code,
                RefusalCode.ROUTE_UNKNOWN,
                "No v1 operation at this method and path.",
                headers=exc.headers,
            )
        log.error("v1_http_exception", status=exc.status_code, path=request.url.path)
        return _internal()


class ProblemOnCrash:
    """Pure ASGI guard: an unhandled exception becomes a 500 ``internal`` Problem.

    Sits inside the sub-application's ``ServerErrorMiddleware``, so the exception
    never reaches it — nor the parent, when the sub-application is mounted. The
    traceback goes to the log, never to the body. Once the response has started
    nothing can be answered any more: the response is left incomplete, which the
    server ends by closing the connection. It never re-raises.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the application.

        Args:
            app: The inner ASGI application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the inner application, answering a crash before the response starts.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.

        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def _send(message: Message) -> None:
            """Forward one message, noting whether the response has started.

            Args:
                message: The ASGI message the inner application sends.
            """
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            log.error("v1_unhandled_exception", path=scope.get("path"), started=started, exc_info=True)
            if not started:
                await _internal()(scope, receive, send)
