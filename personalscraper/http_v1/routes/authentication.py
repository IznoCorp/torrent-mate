"""The ``authentication`` tag's routes: the signed-in account and its session."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.errors import AppUnauthenticated, RefusalCode
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.authentication import AccountModel, SignedOut
from personalscraper.http_v1.session_cookie import clear_session_cookie, session_token

router = APIRouter()


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
