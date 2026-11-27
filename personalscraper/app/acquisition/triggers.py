"""``AcquisitionRuns``: a detect, a search and a grab asked through the supervisor, and the schedule (K3 P13).

Every ask is a request of the supervisor's acquisition lane (DESIGN § 2.12): an equal ask waiting is
joined (the same uid), else it is queued behind whatever runs. No act here runs a pass, takes a lock
or refuses for « busy »; what a pass found is read afterwards, from the follow and its releases (a
search is queued like a grab, O-6 B).

A search and a grab are scoped to the standing follow or one-off request the medium's key names, and
are the caller's own to ask (or ``acquisition.pilot.any``'s). A grab that names a release does so by
its HANDLE (:func:`~personalscraper.app.acquisition.releases.release_handle`): the job then carries the
release's name, the one wanted row it was chosen on and the handle itself, so the pick binds that row
and that very release, never a namesake. A handle no stored set of the acquisition holds is refused,
never taken for another release.

The schedule is the environment's own: what PM2's ``schedule`` apps of ``ecosystem.config.js`` run
(:data:`PASS_CRONS`), which this process never reads at run time.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Final

from personalscraper.app.accounts.authorise import requires
from personalscraper.app.acquisition.follow_repository import FollowAmbiguous, FollowRepository
from personalscraper.app.acquisition.refusals import refuse_ambiguous, refuse_not_found, refuse_not_requester
from personalscraper.app.acquisition.releases import release_handle
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.supervisor.model import AcquisitionJob, JobKind
from personalscraper.conf.environment import Environment, current_environment
from personalscraper.logger import get_logger
from personalscraper.scheduler import next_fire

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.accounts.ids import AccountId
    from personalscraper.app.acquisition.model import AcquisitionKey, Follow
    from personalscraper.app.supervisor.service import RunService

log = get_logger("app.acquisition.triggers")

__all__ = ["PASS_CRONS", "AcquisitionRuns", "AcquisitionSchedule", "PassCrons"]

#: The field a handle that names nothing is refused on.
_RELEASE_FIELD: Final = "releaseId"

#: Separates a release handle's wanted row from its digest.
_HANDLE_SEPARATOR: Final = ":"

#: The largest rowid SQLite holds: a handle naming a larger one names nothing.
_MAX_ROWID: Final = 2**63 - 1


@dataclass(frozen=True)
class PassCrons:
    """When an environment's scheduled search and grab passes run.

    Attributes:
        search: The search pass's cron, in the machine's local time.
        grab: The grab pass's cron, likewise.
    """

    search: str
    grab: str


#: The environments PM2 schedules the passes of, mirroring ``ecosystem.config.js`` (pinned by a test).
#: Dev has no scheduler app, so it is not listed.
PASS_CRONS: Final[dict[Environment, PassCrons]] = {
    Environment.PROD: PassCrons(search="10 3,15 * * *", grab="20 3,15 * * *"),
    Environment.STAGING: PassCrons(search="40 3,15 * * *", grab="50 3,15 * * *"),
}


@dataclass(frozen=True)
class AcquisitionSchedule:
    """The acquisition's schedule as the interface reads it.

    Attributes:
        cadence: The cron the grab pass runs on.
        next_search: When the search pass next runs, ISO 8601 with its offset; ``None`` on an
            instance that schedules none.
    """

    cadence: str
    next_search: str | None


class AcquisitionRuns:
    """Asks the acquisition's passes of the supervisor, for a signed-in actor."""

    def __init__(
        self,
        *,
        open_store: Callable[[], AcquireStore],
        runs: RunService,
        owner: Callable[[], AccountId],
        environment: Callable[[], Environment] = current_environment,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the service; nothing is opened until a call.

        Args:
            open_store: Opens the acquire store for one call (closed after it).
            runs: The supervisor's queue.
            owner: The account a follow with no requester is the ask of (ruling 9).
            environment: The environment whose schedule is read.
            clock: The epoch clock.
        """
        self._open_store = open_store
        self._runs = runs
        self._owner = owner
        self._environment = environment
        self._clock = clock

    @requires("runDetection")
    def detect(self, actor: Actor) -> str:
        """Ask a detection of every follow.

        Args:
            actor: Who asks; needs ``pipeline.control``.

        Returns:
            The uid of the request answering the ask.

        Raises:
            AppForbidden: ``right.missing``, ``instance.forbidden_write`` or ``instance.read_only``.
        """
        return str(self._runs.ask_acquisition(actor, AcquisitionJob(JobKind.DETECT)).uid)

    @requires("searchForFollow")
    def search(self, actor: Actor, key: AcquisitionKey) -> str:
        """Ask a search of one acquisition.

        Args:
            actor: Who asks; a requester of it, or ``acquisition.pilot.any``.
            key: The medium's key.

        Returns:
            The uid of the request answering the ask.

        Raises:
            AppNotFound: ``acquisition.not_found`` when no standing follow or request holds the key.
            AppForbidden: ``acquisition.not_requester`` on an acquisition that is not the actor's, or
                the instance's own refusals.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        with closing(self._open_store()) as store:
            follow = self._own(store, actor, key)
        job = AcquisitionJob(JobKind.SEARCH, followed_id=int(follow.id))
        return str(self._runs.ask_acquisition(actor, job).uid)

    @requires("grabForFollow")
    def grab(self, actor: Actor, key: AcquisitionKey, release_id: str | None) -> str:
        """Ask a grab of one acquisition, of a chosen release or of what the last search marked takeable.

        Args:
            actor: Who asks; a requester of it, or ``acquisition.pilot.any``.
            key: The medium's key.
            release_id: The handle of the release chosen (``Release.id``); ``None`` for the engine's pick.

        Returns:
            The uid of the request answering the ask.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``releaseId`` when the handle names no stored
                release of the acquisition.
            AppNotFound: ``acquisition.not_found`` when no standing follow or request holds the key.
            AppForbidden: ``acquisition.not_requester`` on an acquisition that is not the actor's, or
                the instance's own refusals.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        release: str | None = None
        wanted_id: int | None = None
        with closing(self._open_store()) as store:
            follow = self._own(store, actor, key)
            if release_id is not None:
                wanted_id, release = _picked(store, int(follow.id), release_id)
        job = AcquisitionJob(
            JobKind.GRAB,
            followed_id=int(follow.id),
            release=release,
            wanted_id=wanted_id,
            release_id=None if wanted_id is None else release_id,
        )
        return str(self._runs.ask_acquisition(actor, job).uid)

    @requires("readAcquisitionStatus")
    def status(self, actor: Actor) -> AcquisitionSchedule:
        """Read the grab's cadence and the next search of this environment.

        Args:
            actor: Who reads; any signed-in account.

        Returns:
            The schedule. An environment that schedules no pass answers prod's cadence and no next
            search.
        """
        crons = PASS_CRONS.get(self._environment())
        if crons is None:
            return AcquisitionSchedule(cadence=PASS_CRONS[Environment.PROD].grab, next_search=None)
        # PM2's loop reads its cron in the machine's local time; the offset is read at the fire time,
        # so a fire past a daylight-saving change carries the new one.
        fire = next_fire(crons.search, datetime.fromtimestamp(self._clock()))
        return AcquisitionSchedule(cadence=crons.grab, next_search=fire.astimezone().isoformat())

    def _own(self, store: AcquireStore, actor: Actor, key: AcquisitionKey) -> Follow:
        """The standing follow or request the key names, the actor's to pilot.

        Args:
            store: The open acquire store.
            actor: Who acts.
            key: The medium's key.

        Returns:
            The follow.

        Raises:
            AppNotFound: ``acquisition.not_found`` when none stands under the key.
            AppForbidden: ``acquisition.not_requester`` when it is not the actor's.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        try:
            follow = FollowRepository(store).get(key)
        except FollowAmbiguous as exc:
            raise refuse_ambiguous(key) from exc
        if follow is None or follow.removed_at is not None:
            raise refuse_not_found(key)
        if not actor.is_requester([one.account_id for one in follow.requesters_or_owner(self._owner())]):
            raise refuse_not_requester(key)
        return follow


def _picked(store: AcquireStore, followed_id: int, release_id: str) -> tuple[int, str]:
    """The wanted row and the release name a handle stands for.

    Args:
        store: The open acquire store.
        followed_id: The acquisition the handle must be of.
        release_id: The handle.

    Returns:
        ``(wanted row, release name)``.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``releaseId``: a malformed handle, a row that is not
            the acquisition's, or a release its stored set no longer holds.
    """
    head = release_id.partition(_HANDLE_SEPARATOR)[0]
    # The length first: Python refuses to parse a number of thousands of digits (a ValueError, not a miss).
    if head.isdecimal() and len(head) <= len(str(_MAX_ROWID)) and int(head) <= _MAX_ROWID:
        row = store.wanted.get(int(head))
        if row is not None and row.id is not None and row.followed_id == followed_id:
            for candidate in store.candidates.list_for(row.id):
                if release_handle(row.id, candidate) == release_id:
                    return row.id, candidate.title
    log.info("app.acquisition.release_unknown", followed_id=followed_id, release_id=release_id)
    raise AppBadRequest(
        "No release answers to that id.", code=RefusalCode.REQUEST_INVALID, params={"fields": [_RELEASE_FIELD]}
    )
