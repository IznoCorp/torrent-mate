"""The accounts screen's routes: the roster, an account's creation, role, password and access, and the roles.

The contract files them under its ``authentication`` tag; they live apart from the
session routes because they are another screen's, and every one calls the roster or the role service.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.accounts import (
    AccountSummaryModel,
    CreateAccountBody,
    CreateRoleBody,
    ResetAccountPasswordBody,
    RoleDeleted,
    RosterModel,
    SetAccountAccessBody,
    UpdateAccountBody,
    UpdateRoleBody,
)
from personalscraper.http_v1.models.authentication import PasswordSet, RoleModel

router = APIRouter()

#: The refusals of an operation that names an account or a role: the contract declares 404 there.
_NAMED_RESPONSES = {**PROBLEM_RESPONSES, 404: PROBLEM_RESPONSES[400]}

#: ``resetAccountPassword``'s and ``setAccountAccess``'s refusals: they name an account (404) and
#: conflict with no state (no 409).
_NAMED_NO_CONFLICT_RESPONSES = {status: answer for status, answer in _NAMED_RESPONSES.items() if status != 409}


@router.get(
    "/accounts",
    operation_id="readAccounts",
    response_model=RosterModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_accounts(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> RosterModel:
    """Every account and every role; a caller who is not Admin sees no Admin account.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The roster.
    """
    return RosterModel.from_view(app_services.accounts.read_roster(signed_in))


@router.post(
    "/accounts",
    operation_id="createAccount",
    response_model=AccountSummaryModel,
    response_model_exclude_none=True,
    status_code=201,
    responses=_NAMED_RESPONSES,
)
def create_account(
    body: CreateAccountBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> AccountSummaryModel:
    """Create a local account with its provisional password.

    Args:
        body: Its name, e-mail, role and provisional password.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The account, on its initial role.
    """
    return AccountSummaryModel.from_view(
        app_services.accounts.create_account(
            signed_in, name=body.name, email=body.email, role_id=body.role, password=body.password
        )
    )


@router.patch(
    "/accounts/{accountId}",
    operation_id="updateAccount",
    response_model=AccountSummaryModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=_NAMED_RESPONSES,
)
def update_account(
    account_id: Annotated[str, Path(alias="accountId", description="the account")],
    body: UpdateAccountBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> AccountSummaryModel:
    """Put an account on its one role.

    Args:
        account_id: The account.
        body: The role.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The account, on its new role.
    """
    return AccountSummaryModel.from_view(app_services.accounts.update_account(signed_in, account_id, role_id=body.role))


@router.post(
    "/accounts/{accountId}/password",
    operation_id="resetAccountPassword",
    response_model=PasswordSet,
    status_code=200,
    responses=_NAMED_NO_CONFLICT_RESPONSES,
)
def reset_account_password(
    account_id: Annotated[str, Path(alias="accountId", description="the account")],
    body: ResetAccountPasswordBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> PasswordSet:
    """Give a local account a provisional password; its sessions end.

    Args:
        account_id: The account.
        body: The provisional password.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        ``{"ok": true}``.
    """
    app_services.accounts.reset_account_password(signed_in, account_id, password=body.password)
    return PasswordSet(ok=True)


@router.put(
    "/accounts/{accountId}/access",
    operation_id="setAccountAccess",
    response_model=AccountSummaryModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=_NAMED_NO_CONFLICT_RESPONSES,
)
def set_account_access(
    account_id: Annotated[str, Path(alias="accountId", description="the account")],
    body: SetAccountAccessBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> AccountSummaryModel:
    """Allow or cut an account's sign-in; cutting ends every session of the account.

    Args:
        account_id: The account.
        body: Whether it may sign in.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The account, with its access as set.
    """
    return AccountSummaryModel.from_view(
        app_services.accounts.set_account_access(signed_in, account_id, allowed=body.sign_in_allowed)
    )


@router.post(
    "/roles",
    operation_id="createRole",
    response_model=RoleModel,
    response_model_exclude_none=True,
    status_code=201,
    responses=PROBLEM_RESPONSES,
)
def create_role(
    body: CreateRoleBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> RoleModel:
    """Create an ordinary role.

    Args:
        body: Its name and rights.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The role.
    """
    return RoleModel.from_view(app_services.roles.create_role(signed_in, name=body.name, rights=body.rights))


@router.patch(
    "/roles/{roleId}",
    operation_id="updateRole",
    response_model=RoleModel,
    response_model_exclude_none=True,
    status_code=200,
    responses=_NAMED_RESPONSES,
)
def update_role(
    role_id: Annotated[str, Path(alias="roleId", description="the role")],
    body: UpdateRoleBody,
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> RoleModel:
    """Rename a role or set its rights.

    Args:
        role_id: The role.
        body: Its new name and/or rights.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The role.
    """
    return RoleModel.from_view(app_services.roles.update_role(signed_in, role_id, name=body.name, rights=body.rights))


@router.delete(
    "/roles/{roleId}",
    operation_id="deleteRole",
    response_model=RoleDeleted,
    status_code=200,
    responses=_NAMED_RESPONSES,
)
def delete_role(
    role_id: Annotated[str, Path(alias="roleId", description="the role")],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> RoleDeleted:
    """Delete a role nothing depends on: no account holds it and no newcomer starts on it.

    Args:
        role_id: The role.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        ``{"ok": true}``.
    """
    app_services.roles.delete_role(signed_in, role_id)
    return RoleDeleted(ok=True)
