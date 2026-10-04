"""The accounts screen's bodies, written from the contract's ``Roster``, ``AccountSummary`` and the write bodies.

A property the contract marks ABSENT when empty (``AccountSummary.demotedFrom``) is
``None`` here and left out of the answer: the routes serialise with
``response_model_exclude_none``.
"""

from __future__ import annotations

from pydantic import Field

from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.views import AccountSummaryView, RosterView, SignInKind
from personalscraper.http_v1.contract import ContractModel
from personalscraper.http_v1.models.authentication import RoleModel


class AccountSummaryModel(ContractModel):
    """The contract's ``AccountSummary``: one account of the roster.

    Attributes:
        id: The account's key.
        name: Its display name.
        email: Its e-mail.
        role: Its one role.
        sign_in_kind: How it signs in.
        sign_in_allowed: Whether it may sign in.
        demoted_from: The role it held before its Plex link demoted it; absent otherwise.
    """

    id: str
    name: str
    email: str
    role: RoleModel
    sign_in_kind: SignInKind
    sign_in_allowed: bool
    demoted_from: str | None = None

    @classmethod
    def from_view(cls, view: AccountSummaryView) -> AccountSummaryModel:
        """Map an account summary view.

        Args:
            view: The service's view.

        Returns:
            The body.
        """
        return cls(
            id=view.id,
            name=view.name,
            email=view.email,
            role=RoleModel.from_view(view.role),
            sign_in_kind=view.sign_in_kind,
            sign_in_allowed=view.sign_in_allowed,
            demoted_from=view.demoted_from,
        )


class RosterModel(ContractModel):
    """The contract's ``Roster``: every account and every role.

    Attributes:
        accounts: The accounts.
        roles: The roles.
    """

    accounts: list[AccountSummaryModel]
    roles: list[RoleModel]

    @classmethod
    def from_view(cls, view: RosterView) -> RosterModel:
        """Map a roster view.

        Args:
            view: The service's view.

        Returns:
            The body.
        """
        return cls(
            accounts=[AccountSummaryModel.from_view(account) for account in view.accounts],
            roles=[RoleModel.from_view(role) for role in view.roles],
        )


class CreateAccountBody(ContractModel):
    """``createAccount``'s body.

    Attributes:
        name: The display name.
        email: The e-mail, every account's login.
        role: The role it starts on; absent for the role local accounts start on.
        password: The provisional password; only its hash is kept.
    """

    name: str
    email: str
    role: str | None = None
    password: str | None = Field(default=None, repr=False)


class UpdateAccountBody(ContractModel):
    """``updateAccount``'s body.

    Attributes:
        role: The role the account is put on.
    """

    role: str


class CreateRoleBody(ContractModel):
    """``createRole``'s body.

    Attributes:
        name: The role's name.
        rights: The rights it carries.
    """

    name: str
    rights: list[Right]


class UpdateRoleBody(ContractModel):
    """``updateRole``'s body; an absent field is left as it is.

    Attributes:
        name: The new name.
        rights: The new rights, replacing the list whole.
    """

    name: str | None = None
    rights: list[Right] | None = None


class ResetAccountPasswordBody(ContractModel):
    """``resetAccountPassword``'s body.

    Attributes:
        password: The provisional password an Admin gives the account.
    """

    password: str = Field(repr=False)
