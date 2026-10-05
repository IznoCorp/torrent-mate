"""The ``authentication`` tag's routes: the password and Plex doors, the signed-in account and its own acts."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.plex_sign_in import PlexPending
from personalscraper.app.accounts.ratelimit import rate_limit_key
from personalscraper.app.errors import AppUnauthenticated, RefusalCode
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.authentication import (
    AccountModel,
    ChangeOwnPasswordBody,
    PasswordSet,
    PlexPendingModel,
    PlexSignInBody,
    SetOwnLanguageBody,
    SignedOut,
    SignInBody,
    StartedPlexSignInModel,
)
from personalscraper.http_v1.session_cookie import (
    clear_plex_pin_cookie,
    clear_session_cookie,
    plex_pin_nonce,
    session_token,
    set_plex_pin_cookie,
    set_session_cookie,
)

router = APIRouter()

#: ``signIn``'s refusals as the contract declares them: the Problem answers of every operation,
#: the 403 included — a cross-origin POST is refused ``request.cross_origin`` whatever the
#: credentials, before the door looks at them — and the limiter's 429. Every failure of the
#: credentials themselves stays the one 401.
_SIGN_IN_RESPONSES = {**PROBLEM_RESPONSES, 429: PROBLEM_RESPONSES[401]}

#: ``changeOwnPassword``'s refusals: the Problem answers of every operation and the 429 of
#: its limiter on wrong current passwords.
_CHANGE_OWN_PASSWORD_RESPONSES = {**PROBLEM_RESPONSES, 429: PROBLEM_RESPONSES[401]}


#: ``signInWithPlex``'s answers besides its 200: the 202 while the PIN is unclaimed, and the
#: Problem answers of every operation.
_SIGN_IN_WITH_PLEX_RESPONSES: dict[int | str, dict[str, Any]] = {
    202: {"model": PlexPendingModel, "description": "The PIN is not claimed yet."},
    **PROBLEM_RESPONSES,
}


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
    browser already carries is ignored: the browser's cookie is replaced by the new one,
    while the server-side session it named stays valid until it expires or signs out.

    Args:
        body: The e-mail and the password.
        request: The incoming request (the client's key, its user agent, the web configuration).
        response: The answer the session cookie is set on.
        app_services: The application services.

    Returns:
        The signed-in account.
    """
    client_key = rate_limit_key(request.client.host if request.client else None, request.headers.get("x-forwarded-for"))
    result = app_services.credentials.sign_in_with_password(
        body.email, body.password, client_key=client_key, user_agent=request.headers.get("user-agent")
    )
    set_session_cookie(response, result.session_token, request.app.state.config.web)
    return AccountModel.from_view(result.account)


@router.post(
    "/auth/plex/start",
    operation_id="startPlexSignIn",
    response_model=StartedPlexSignInModel,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def start_plex_sign_in(
    request: Request,
    response: Response,
    app_services: Annotated[AppServices, Depends(services)],
) -> StartedPlexSignInModel:
    """Create a Plex PIN, bind it to this browser by the pin cookie, and answer plex.tv's page.

    Args:
        request: The incoming request (the web configuration).
        response: The answer the pin cookie is set on.
        app_services: The application services.

    Returns:
        The PIN and plex.tv's page where the person confirms it.
    """
    started = app_services.plex_sign_in.start()
    set_plex_pin_cookie(response, started.nonce, max_age=started.max_age_s, web=request.app.state.config.web)
    return StartedPlexSignInModel(pin_id=started.pin_id, sign_in_url=started.sign_in_url)


@router.post(
    "/auth/plex",
    operation_id="signInWithPlex",
    response_model=AccountModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=_SIGN_IN_WITH_PLEX_RESPONSES,
)
def sign_in_with_plex(
    body: PlexSignInBody,
    request: Request,
    response: Response,
    app_services: Annotated[AppServices, Depends(services)],
) -> AccountModel | JSONResponse:
    """Ask whether the PIN is claimed; once it is, open a session and hand its cookie.

    Args:
        body: The PIN ``startPlexSignIn`` answered.
        request: The incoming request (the pin cookie, the user agent, the web configuration).
        response: The answer the session cookie is set and the pin cookie cleared on.
        app_services: The application services.

    Returns:
        The signed-in account; or 202 ``{"pending": true}`` while the PIN is unclaimed.
    """
    web = request.app.state.config.web
    result = app_services.plex_sign_in.finish(
        body.pin_id, nonce=plex_pin_nonce(request), user_agent=request.headers.get("user-agent")
    )
    if isinstance(result, PlexPending):
        return JSONResponse(status_code=202, content=PlexPendingModel(pending=True).model_dump(by_alias=True))
    set_session_cookie(response, result.session_token, web)
    clear_plex_pin_cookie(response, web)
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
    app_services.credentials.sign_out(signed_in, token)
    clear_session_cookie(response, request.app.state.config.web)
    return SignedOut(ok=True)


@router.put(
    "/auth/password",
    operation_id="changeOwnPassword",
    response_model=PasswordSet,
    status_code=200,
    responses=_CHANGE_OWN_PASSWORD_RESPONSES,
)
def change_own_password(
    body: ChangeOwnPasswordBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    token: Annotated[str, Depends(signed_in_token)],
) -> PasswordSet:
    """Replace the signed-in local account's password; its other sessions end, this one stays.

    Args:
        body: The current password and the new one.
        signed_in: The signed-in actor.
        app_services: The application services.
        token: The caller's session value, the one kept.

    Returns:
        ``{"ok": true}``.
    """
    app_services.credentials.change_own_password(
        signed_in, token, current_password=body.current_password, new_password=body.new_password
    )
    return PasswordSet(ok=True)


@router.put(
    "/auth/language",
    operation_id="setOwnLanguage",
    response_model=AccountModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def set_own_language(
    body: SetOwnLanguageBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> AccountModel:
    """Set the language the signed-in account is spoken to in, on all its devices (FG-1 B).

    Args:
        body: The language chosen.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The account, as now held.
    """
    return AccountModel.from_view(app_services.accounts.set_own_language(signed_in, body.language))
