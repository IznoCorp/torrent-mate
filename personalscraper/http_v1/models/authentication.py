"""The ``authentication`` tag's bodies, written from the contract's ``Account``, ``Role`` and ``signIn`` body.

A property the contract marks ABSENT when empty (``Account.avatar``, ``Role.name``,
``Role.defaultFor``) is ``None`` here and left out of the answer: the routes serialise
with ``response_model_exclude_none``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.repository import StartKind
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.views import AccountView, RoleView, SignInKind
from personalscraper.http_v1.contract import ContractModel
from personalscraper.i18n import Language


class RoleModel(ContractModel):
    """The contract's ``Role``.

    Attributes:
        id: The role's key.
        name: Its name when an Admin gave it one; absent on a seeded role never renamed.
        kind: ``admin`` or ``ordinary``.
        rights: The rights it carries; empty for Admin.
        default_for: Who starts on it; absent for a role nobody starts on.
    """

    id: str
    name: str | None = None
    kind: RoleKind
    rights: list[Right]
    default_for: list[StartKind] | None = None

    @classmethod
    def from_view(cls, view: RoleView) -> RoleModel:
        """Map a role view.

        Args:
            view: The service's view.

        Returns:
            The body.
        """
        return cls(
            id=view.id,
            name=view.name,
            kind=view.kind,
            rights=list(view.rights),
            default_for=list(view.default_for) or None,
        )


class AccountModel(ContractModel):
    """The contract's ``Account``: who is signed in, and what the instance forbids.

    Attributes:
        name: The display name.
        email: The e-mail.
        avatar: The picture's address — its Plex avatar, else its Gravatar; absent for an
            account that has neither.
        id: The account's key.
        role: Its one role.
        sign_in_kind: How it signs in.
        forbidden_writes: The instance's forbidden writes.
        language: The language it is spoken to in.
    """

    name: str
    email: str
    avatar: str | None = None
    id: str
    role: RoleModel
    sign_in_kind: SignInKind
    forbidden_writes: list[Right]
    language: Language

    @classmethod
    def from_view(cls, view: AccountView) -> AccountModel:
        """Map an account view.

        Args:
            view: The service's view.

        Returns:
            The body.
        """
        return cls(
            name=view.name,
            email=view.email,
            avatar=view.avatar,
            id=view.id,
            role=RoleModel.from_view(view.role),
            sign_in_kind=view.sign_in_kind,
            forbidden_writes=list(view.forbidden_writes),
            language=view.language,
        )


class SignInBody(ContractModel):
    """``signIn``'s body: the password door's two fields.

    Attributes:
        email: The account's e-mail — every account's login, matched whatever its case.
        password: The password typed.
    """

    email: str
    password: str = Field(repr=False)


class StartedPlexSignInModel(ContractModel):
    """The contract's ``StartedPlexSignIn``: the PIN, and plex.tv's page where the person confirms it.

    Attributes:
        pin_id: The PIN's key, the one ``signInWithPlex`` takes.
        sign_in_url: plex.tv's page; it carries the PIN code, so it is kept out of the ``repr``.
    """

    pin_id: int
    sign_in_url: str = Field(repr=False)


class PlexSignInBody(ContractModel):
    """``signInWithPlex``'s body.

    Attributes:
        pin_id: The PIN ``startPlexSignIn`` answered.
    """

    pin_id: int


class PlexPendingModel(ContractModel):
    """``signInWithPlex``'s 202: the PIN is not claimed yet.

    Attributes:
        pending: Always true.
    """

    pending: Literal[True]


class ChangeOwnPasswordBody(ContractModel):
    """``changeOwnPassword``'s body.

    Attributes:
        current_password: The password the account holds now.
        new_password: The password that replaces it.
    """

    current_password: str = Field(repr=False)
    new_password: str = Field(repr=False)


class SetOwnLanguageBody(ContractModel):
    """``setOwnLanguage``'s body.

    Attributes:
        language: The language chosen; a value outside ``Language`` is refused 400.
    """

    language: Language


class PasswordSet(ContractModel):
    """The acknowledgement of a password write (``changeOwnPassword``, ``resetAccountPassword``).

    Attributes:
        ok: Always true: the password is set.
    """

    ok: bool


class SignedOut(ContractModel):
    """``signOut``'s acknowledgement.

    Attributes:
        ok: Always true: the session is closed.
    """

    ok: bool
