"""The ``authentication`` tag's routes: the password door, the signed-in account and its session."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ratelimit import rate_limit_key
from personalscraper.app.errors import AppUnauthenticated, RefusalCode
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.authentication import AccountModel, SignedOut, SignInBody
from personalscraper.http_v1.session_cookie import clear_session_cookie, session_token, set_session_cookie

router = APIRouter()

#: ``signIn`` also declares the limiter's 429.
_SIGN_IN_RESPONSES = {**PROBLEM_RESPONSES, 429: PROBLEM_RESPONSES[401]}


def signed_in_token(request: Request) -> str:
    """The session value the perimeter resolved the request's actor from.

    Args:
        request: The incoming request, already through the perimeter.

    Returns:
        The ``tm_v1_session`` value.

    Raises:
        AppUnauthenticated: ``auth.required`` — no value (only reachable outside the
            perimeter's resolution, e.g. an injected resolver).
    """
    token = session_token(request)
    if token is None:
        raise AppUnauthenticated("This operation requires a signed-in session.", code=RefusalCode.AUTH_REQUIRED)
    return token


@router.post(
    "/auth/login",
    operation_id="signIn",
    response_model=AccountModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=_SIGN_IN_RESPONSES,
)
def sign_in(
    body: SignInBody,
    request: Request,
    response: Response,
    app_services: Annotated[AppServices, Depends(services)],
) -> AccountModel:
    """Open a session from an e-mail and a password, and hand its cookie.

    A public operation: the perimeter resolves no session, so a ``tm_v1_session`` the
    browser already carries is ignored and replaced by the new one.

    Args:
        body: The e-mail and the password.
        request: The incoming request (the client's key, its user agent, the web configuration).
        response: The answer the session cookie is set on.
        app_services: The application services.

    Returns:
        The signed-in account.
    """
    client_key = rate_limit_key(request.client.host if request.client else None, request.headers.get("x-forwarded-for"))
    result = app_services.accounts.sign_in_with_password(
        body.email, body.password, client_key=client_key, user_agent=request.headers.get("user-agent")
    )
    set_session_cookie(response, result.session_token, request.app.state.config.web)
    return AccountModel.from_view(result.account)


@router.get(
    "/auth/me",
    operation_id="readAccount",
    response_model=AccountModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_account(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> AccountModel:
    """The signed-in account, its role, how it signs in, and the instance's forbidden writes.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The account.
    """
    return AccountModel.from_view(app_services.accounts.read_account(signed_in))


@router.post(
    "/auth/logout",
    operation_id="signOut",
    response_model=SignedOut,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def sign_out(
    request: Request,
    response: Response,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    token: Annotated[str, Depends(signed_in_token)],
) -> SignedOut:
    """Close the session and clear its cookie.

    Args:
        request: The incoming request (the sub-application's web configuration).
        response: The answer the cleared cookie is set on.
        signed_in: The signed-in actor.
        app_services: The application services.
        token: The session's value.

    Returns:
        ``{"ok": true}``.
    """
    app_services.accounts.sign_out(signed_in, token)
    clear_session_cookie(response, request.app.state.config.web)
    return SignedOut(ok=True)
