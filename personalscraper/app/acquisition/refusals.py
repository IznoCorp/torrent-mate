"""The acquisition services' refusals (K3 DESIGN § 2.13): the model's errors as coded refusals.

Each refusal names the acquisition by its wire key in ``params.followedId``, the fact the interface's
words may name; never a sentence (X4).
"""

from __future__ import annotations

from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.errors import AppConflict, AppForbidden, AppNotFound, RefusalCode

__all__ = [
    "refuse_ambiguous",
    "refuse_not_found",
    "refuse_not_requester",
    "refuse_not_restorable",
    "refuse_release_unavailable",
    "refuse_season_unknown",
    "refuse_shared",
]

#: The fact every acquisition refusal carries: the key it was asked by.
_KEY_PARAM = "followedId"


def refuse_not_found(key: AcquisitionKey) -> AppNotFound:
    """No follow, request or owned medium answers the key (or the actor may not read it).

    Args:
        key: The key asked.

    Returns:
        The ``404 acquisition.not_found`` refusal.
    """
    return AppNotFound(
        "No acquisition answers this key.", code=RefusalCode.ACQUISITION_NOT_FOUND, params={_KEY_PARAM: key.wire}
    )


def refuse_not_requester(key: AcquisitionKey) -> AppForbidden:
    """An own-scoped act on an acquisition the actor did not ask for.

    Args:
        key: The key asked.

    Returns:
        The ``403 acquisition.not_requester`` refusal.
    """
    return AppForbidden(
        "The signed-in account did not ask for this acquisition.",
        code=RefusalCode.ACQUISITION_NOT_REQUESTER,
        params={_KEY_PARAM: key.wire},
    )


def refuse_shared(key: AcquisitionKey) -> AppForbidden:
    """The generic pause asked on a follow other accounts also asked for.

    Args:
        key: The key asked.

    Returns:
        The ``403 acquisition.follow_shared`` refusal.
    """
    return AppForbidden(
        "Other accounts asked for this follow too.",
        code=RefusalCode.ACQUISITION_FOLLOW_SHARED,
        params={_KEY_PARAM: key.wire},
    )


def refuse_release_unavailable(key: AcquisitionKey) -> AppConflict:
    """A release picked on a row that cannot take it now: its pick would be dropped (O-14).

    Args:
        key: The key asked.

    Returns:
        The ``409 acquisition.release_unavailable`` refusal.
    """
    return AppConflict(
        "The release's row is not waiting to be taken.",
        code=RefusalCode.ACQUISITION_RELEASE_UNAVAILABLE,
        params={_KEY_PARAM: key.wire},
    )


def refuse_season_unknown(key: AcquisitionKey) -> AppConflict:
    """A one-off season of a show whose episodes nothing lists: what it misses cannot be told.

    Args:
        key: The key asked.

    Returns:
        The ``409 acquisition.season_unknown`` refusal.
    """
    return AppConflict(
        "The episode list of that show is not known yet.",
        code=RefusalCode.ACQUISITION_SEASON_UNKNOWN,
        params={_KEY_PARAM: key.wire},
    )


def refuse_not_restorable(key: AcquisitionKey) -> AppNotFound:
    """Nothing removed under the key can be put back.

    Args:
        key: The key asked.

    Returns:
        The ``404 follow.not_restorable`` refusal.
    """
    return AppNotFound(
        "Nothing removed under this key.", code=RefusalCode.FOLLOW_NOT_RESTORABLE, params={_KEY_PARAM: key.wire}
    )


def refuse_ambiguous(key: AcquisitionKey) -> AppConflict:
    """Two or more follow rows hold the key's id (O-13: measured, settled by K9).

    Args:
        key: The key asked.

    Returns:
        The ``409 follow.ambiguous`` refusal.
    """
    return AppConflict(
        "Several follow rows hold this key.", code=RefusalCode.FOLLOW_AMBIGUOUS, params={_KEY_PARAM: key.wire}
    )
