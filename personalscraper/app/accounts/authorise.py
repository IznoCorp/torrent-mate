"""``authorise``: the one authorisation path (§ 17, NE-DOIT-PAS-7).

The v1 perimeter calls it for every operation; the instance ceiling is one of
its terms, never a second check beside it.
"""

from __future__ import annotations

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.rights import AnyOf, Public, Requirement, Right, SignedIn
from personalscraper.app.errors import AppForbidden, AppUnauthenticated, RefusalCode


def authorise(actor: Actor | None, requirement: Requirement) -> None:
    """Refuse the actor what the requirement does not let it do.

    Args:
        actor: The signed-in actor, or ``None`` when the request carries no
            valid session.
        requirement: What the operation asks for.

    Raises:
        AppUnauthenticated: ``auth.required`` — no actor on an operation that asks
            a session.
        AppForbidden: ``instance.read_only`` — a session write on a read-only instance;
            ``instance.forbidden_write`` — the role carries an asked right but the
            ceiling forbids it (``params.right``); ``right.missing`` — no asked right
            is held (``params.rights``, sorted).
    """
    if isinstance(requirement, Public):
        return
    if actor is None:
        raise AppUnauthenticated("This operation requires a signed-in session.", code=RefusalCode.AUTH_REQUIRED)
    if isinstance(requirement, SignedIn):
        if requirement.write and actor.ceiling.read_only:
            raise AppForbidden("This instance is read-only.", code=RefusalCode.INSTANCE_READ_ONLY)
        return
    _authorise_any_of(actor, requirement)


def _authorise_any_of(actor: Actor, requirement: AnyOf) -> None:
    """Refuse a right-gated operation when none of its rights is held.

    Args:
        actor: The signed-in actor.
        requirement: The rights any one of which opens the operation.

    Raises:
        AppForbidden: ``instance.forbidden_write`` or ``right.missing`` (see :func:`authorise`).
    """
    if actor.holds_any(requirement.rights):
        return
    asked = sorted(requirement.rights)
    # A right the role grants but the ceiling subtracts is the instance's refusal, not
    # the role's: the interface names the instance, not a missing right.
    for right in asked:
        if right in actor.ceiling.forbidden and _role_grants(actor, right):
            raise AppForbidden(
                f"This instance forbids {right.value}.",
                code=RefusalCode.INSTANCE_FORBIDDEN_WRITE,
                params={"right": right.value},
            )
    raise AppForbidden(
        "The signed-in account holds none of the rights this operation asks for.",
        code=RefusalCode.RIGHT_MISSING,
        params={"rights": [right.value for right in asked]},
    )


def _role_grants(actor: Actor, right: Right) -> bool:
    """Whether the actor's role grants a right, before the ceiling subtracts.

    Args:
        actor: The signed-in actor.
        right: The right asked about.

    Returns:
        True when the role is Admin or carries the right.
    """
    return actor.role_kind is RoleKind.ADMIN or right in actor.role_rights
