"""The rights of the ACL and what an operation asks for.

``Right`` is the contract's ``#/components/schemas/Right`` enum, verbatim. A
``Requirement`` is what one operation asks: nothing (``Public``), a session
(``SignedIn``), or one right among several (``AnyOf``). The table naming every
operation's requirement is ``http_v1/rights.py``; the one path that applies it is
``authorise``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeAlias


class Right(StrEnum):
    """One right of the ACL, in the contract's own names (``#/components/schemas/Right``)."""

    LIBRARY_READ = "library.read"
    LIBRARY_DELETE = "library.delete"
    LIBRARY_RESCRAPE = "library.rescrape"
    ACQUISITION_REQUEST = "acquisition.request"
    ACQUISITION_FOLLOW = "acquisition.follow"
    ACQUISITION_PILOT_OWN = "acquisition.pilot.own"
    ACQUISITION_PILOT_ANY = "acquisition.pilot.any"
    ACQUISITION_SEE_OTHERS = "acquisition.see.others"
    ACQUISITION_TODO_VIEW = "acquisition.todo.view"
    ACQUISITION_QUALITY_OWN = "acquisition.quality.own"
    ACQUISITION_PAUSE_OWN = "acquisition.pause.own"
    ACQUISITION_REASSIGN = "acquisition.reassign"
    PIPELINE_CONTROL = "pipeline.control"
    TRACKERS_VIEW = "trackers.view"
    TRACKERS_CONTROL = "trackers.control"
    TRACKERS_UPLOAD = "trackers.upload"
    SYSTEM_VIEW = "system.view"
    CONFIGURATION_VIEW = "configuration.view"
    CONFIGURATION_WRITE = "configuration.write"
    ACCOUNTS_MANAGE = "accounts.manage"
    AUTH_PASSWORD = "auth.password"


#: Every WRITE right — what an instance's forbidden-writes list may name (ruling 23).
#: The view rights and the password door are never forbidden writes. Mirrors the
#: maquette's ``WRITE_RIGHTS`` (``frontend/maquette/design/src/lib/rights.ts``).
WRITE_RIGHTS: Final[frozenset[Right]] = frozenset(
    {
        Right.LIBRARY_DELETE,
        Right.LIBRARY_RESCRAPE,
        Right.ACQUISITION_REQUEST,
        Right.ACQUISITION_FOLLOW,
        Right.ACQUISITION_PILOT_OWN,
        Right.ACQUISITION_PILOT_ANY,
        Right.ACQUISITION_QUALITY_OWN,
        Right.ACQUISITION_PAUSE_OWN,
        Right.ACQUISITION_REASSIGN,
        Right.PIPELINE_CONTROL,
        Right.TRACKERS_CONTROL,
        Right.TRACKERS_UPLOAD,
        Right.CONFIGURATION_WRITE,
        Right.ACCOUNTS_MANAGE,
    }
)


@dataclass(frozen=True)
class Public:
    """No session asked: the sign-in operations."""


@dataclass(frozen=True)
class SignedIn:
    """Any signed-in account, no right: the session's own acts and the unrefused reads.

    Attributes:
        write: True when the act writes, so a read-only instance refuses it (the
            account's own notification writes, ruling of 2026-10-03).
    """

    write: bool = False


@dataclass(frozen=True)
class AnyOf:
    """One right held among these. A write names exactly one, so a ceiling can subtract it by name.

    Attributes:
        rights: The rights any one of which opens the operation.
    """

    rights: frozenset[Right]


Requirement: TypeAlias = Public | SignedIn | AnyOf


def holds(right: Right) -> AnyOf:
    """Ask for one right.

    Args:
        right: The right the operation asks for.

    Returns:
        The requirement of that right alone.
    """
    return AnyOf(frozenset({right}))
