"""``FollowService``: the follows, their requesters, quality and pause, removal, restore and reassign (K3 P7).

Every use case loads the :class:`~personalscraper.app.acquisition.model.Follow` aggregate, applies one
rule of the model, and saves it through
:class:`~personalscraper.app.acquisition.follow_repository.FollowRepository`, which writes the
requesters and their PROJECTION (``min_resolution``, ``active``, DESIGN § 2.4) on the follow's row in
one transaction. The load and the save of one follow share ONE store transaction (``BEGIN IMMEDIATE``,
:meth:`AcquireStore.transaction`): the save sets the requesters to the loaded snapshot, so a join
committed between them, by this process or another (a CLI's re-projection), would otherwise be lost.

What is in force is read from the requesters whose ROLE holds the right (round 10 Q6); the roles are
read from ``app.db``, never from the engine, which stores requesters as opaque account ids.

A write the repository reports as starting the follow (``active`` false → true: created, revived,
its last pause lifted) asks the supervisor for a ``prime`` of it, AFTER the transaction commits, so the
actor is already among the requesters the ask is authorised against (DESIGN § 2.3). The ask never
breaks the write: refused or failed, the follow stands and ``app.follows.prime_ask_failed`` is logged.

Reads filter by :meth:`Follow.readable_by` (``acquisition.see.others`` or membership), a filter on
the answer, never a refusal; ``Actor.is_requester`` is the acts' own scope, not the reads'.

``AccountRightsChanged`` (a role's rights moved) re-projects the follows its accounts asked for, so a
setting whose right was taken away stops counting; ``acquisition-follows-reproject`` does the same for
every follow on demand. A re-projection that turns a follow back on (a pause that stops counting) asks
its ``prime`` as the system actor, the act being nobody's.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal

from personalscraper.acquire.domain import FollowedSeries, FollowKind
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.accounts.events import AccountRightsChanged
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.completeness import OwnershipReader, episode_states
from personalscraper.app.acquisition.follow_repository import FollowAmbiguous, FollowRepository
from personalscraper.app.acquisition.model import (
    AcquisitionKey,
    Follow,
    FollowId,
    FollowRemoved,
    InForce,
    NotARequester,
    QualityFloor,
    RightCheck,
    Scope,
    Via,
)
from personalscraper.app.acquisition.refusals import (
    refuse_ambiguous,
    refuse_not_found,
    refuse_not_requester,
    refuse_not_restorable,
    refuse_shared,
)
from personalscraper.app.acquisition.states import derive_follow_status, derive_movie_status, select_wanted_facts
from personalscraper.app.errors import AppNotFound, RefusalCode
from personalscraper.app.supervisor.model import AcquisitionJob, JobKind, RequestState, RunTrigger
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import FollowCard, WantedItem, WantedKind
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.store.store import AppStore
    from personalscraper.app.supervisor.service import RunService
    from personalscraper.core.event_bus import EventBus, SubscriptionToken
    from personalscraper.core.identity import MediaRef

log = get_logger("app.follows")

__all__ = ["AccountRef", "FollowService", "FollowView", "Reassigned", "account_rights", "prime"]

#: The card status a follow reads while a ``prime`` of it is queued or running (v0's card, DESIGN § 2.3).
VERIFYING = "verifying"

#: The ``updateFollow`` status that pauses; any other resumes (K3-G10 makes the field an enum).
PAUSED_STATUS = "disabled"

#: What a reassign names: a standing follow, or a one-off request's card (§ 2.6).
Reassigned = Literal["follow", "card"]

#: The row families a follow's searches are counted over.
_ROW_KINDS: tuple[WantedKind, ...] = ("episode", "season", "movie")

#: The episode states the card counts as « in motion » (an absorbed episode's season carries it).
_ACQUIRING = frozenset({"acquiring", "absorbed"})


@dataclass(frozen=True)
class AccountRef:
    """An account named by an answer: a requester.

    Attributes:
        id: The account's key.
        name: Its display name; its key when the account is gone.
    """

    id: AccountId
    name: str


@dataclass(frozen=True)
class FollowView:
    """A follow as an actor reads it: the contract's ``Follow`` facts, unformatted.

    Attributes:
        key: The medium's wire key, ``"<provider>:<providerId>"``.
        title: Its title.
        kind: ``"show"`` or ``"movie"``.
        year: Its year, ``None`` when unknown.
        status: The card status (the single derivation's, ``verifying`` while a prime of it runs).
        show_status: The show's production status (« Continuing »), ``None`` for a film or unknown.
        added_at: Epoch seconds the follow was made.
        next_air_date: The next cached air date of a show, ISO, ``None`` when none is known or for a film.
        searches: Tracker queries run for its rows (``wanted.attempts`` summed).
        aired: Aired episodes known, shows only (``None`` for a film or with no cached catalogue).
        owned: Aired episodes the library holds, shows only (``None`` likewise).
        ids: The medium's provider ids.
        poster: The poster's address, ``None`` when none is known.
        requesters: Who asked for it, the owner for a follow written before requesters existed.
        own_quality: The floor the reader set, ``None`` when it set none or is not a requester.
        quality: The floor in force.
        own_paused: Whether the reader paused its own ask.
        paused: Whether the follow is paused in force.
    """

    key: str
    title: str
    kind: FollowKind
    year: int | None
    status: str
    show_status: str | None
    added_at: int
    next_air_date: str | None
    searches: int
    aired: int | None
    owned: int | None
    ids: MediaRef
    poster: str | None
    requesters: tuple[AccountRef, ...]
    own_quality: QualityFloor | None
    quality: QualityFloor | None
    own_paused: bool
    paused: bool


def prime(follow_id: FollowId) -> AcquisitionJob:
    """The amorce of one follow: its detect, then its search, then its grab.

    Args:
        follow_id: The follow's row.

    Returns:
        The supervisor's job.
    """
    return AcquisitionJob(JobKind.PRIME, followed_id=int(follow_id))


def account_rights(app_store: AppStore) -> RightCheck:
    """Whether an account's ROLE holds a right, read from ``app.db`` once per account.

    The role alone decides (Admin holds every right): what is in force on a follow is the
    requesters' standing, not the instance's ceiling, which refuses the writes themselves. An
    account or a role that no longer exists holds nothing.

    Args:
        app_store: The environment's ``app.db``.

    Returns:
        The check, memoised for the call it is made for.
    """
    roles: dict[AccountId, tuple[bool, frozenset[Right]] | None] = {}

    def holds(account: AccountId, right: Right) -> bool:
        """Whether one account's role holds one right.

        Args:
            account: The account.
            right: The right.

        Returns:
            True when its role is Admin or carries the right.
        """
        if account not in roles:
            found = app_store.accounts.account(account)
            role = app_store.roles.role(found.role_id) if found is not None else None
            roles[account] = None if role is None else (role.is_admin, role.rights)
        standing = roles[account]
        return standing is not None and (standing[0] or right in standing[1])

    return holds


class FollowService:
    """The follows' use cases, for a signed-in actor."""

    def __init__(
        self,
        *,
        open_store: Callable[[], AcquireStore],
        open_ownership: Callable[[], OwnershipReader],
        app_store: AppStore,
        runs: RunService,
        owner: Callable[[], AccountId],
        system: Callable[[], Actor],
        clock: Callable[[], float] = time.time,
        today: Callable[[], date] = date.today,
    ) -> None:
        """Build the service; nothing is opened until a call.

        Args:
            open_store: Opens the acquire store for one call (closed after it).
            open_ownership: Opens the library's ownership reader for one read (closed after it).
            app_store: The environment's ``app.db``: the roles in force, the requesters' names.
            runs: The supervisor's queue, which a follow starting to take work is primed through.
            owner: The account a follow with no requester is the ask of (ruling 9).
            system: The system actor, who asks the prime of a follow a re-projection turns on.
            clock: The epoch clock.
            today: Today's date.
        """
        self._open_store = open_store
        self._open_ownership = open_ownership
        self._app_store = app_store
        self._runs = runs
        self._owner = owner
        self._system = system
        self._clock = clock
        self._today = today

    # ── reads ────────────────────────────────────────────────────────────

    @requires("readFollows")
    def read_follows(self, actor: Actor) -> list[FollowView]:
        """The standing follows the actor may read, oldest first.

        A one-off request and a removed follow are not follows: neither is listed.

        Args:
            actor: Who reads; every follow with ``acquisition.see.others``, else those it asked for.

        Returns:
            The follows, each as the actor reads it.
        """
        owner = self._owner()
        holds = account_rights(self._app_store)
        priming = self._priming()
        with closing(self._open_store()) as store, closing(self._open_ownership()) as ownership:
            repository = FollowRepository(store)
            views: list[FollowView] = []
            for row in store.follow.list_all():
                if row.id is None or row.scope != Scope.FOLLOW.value or row.removed_at is not None:
                    continue
                follow = repository.get_by_id(FollowId(row.id))
                whole = repository.row(FollowId(row.id))  # every column: the listing's read omits the year
                if follow is None or whole is None or not follow.readable_by(actor, owner):
                    continue
                views.append(self._view(store, ownership, follow, whole, actor, owner, holds, priming))
        return views

    # ── writes ───────────────────────────────────────────────────────────

    @requires("createFollow")
    def create(
        self, actor: Actor, key: AcquisitionKey, *, title: str, kind: FollowKind, year: int | None
    ) -> FollowView:
        """Follow a medium: a new follow, or the actor joining the one that exists (DOIT-4, never a 409).

        A removed follow comes back on its own row, the actor its requester; a one-off request
        becomes a follow (« Suivre » on its card, § 2.7). A follow that starts taking work is primed.

        Args:
            actor: Who follows; needs ``acquisition.request``.
            key: The medium's key.
            title: Its title, for a new row.
            kind: ``"show"`` or ``"movie"``.
            year: Its year, for a new row.

        Returns:
            The follow as the actor reads it.

        Raises:
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        now = int(self._clock())
        with self._guarded(key) as store:
            repository = FollowRepository(store)
            found = repository.get(key, kind)
            if found is None:
                row_id = store.follow.add(
                    FollowedSeries(media_ref=key.ref(), title=title, added_at=now, active=False, kind=kind, year=year)
                )
                follow = Follow.first_ask(FollowId(row_id), key, Scope.FOLLOW, actor.account_id, now)
            else:
                follow = found.followed_by(actor.account_id, now, owner=self._owner())
            started = self._save(repository, follow)
            log.info("app.follows.requester_added", followed_id=follow.id, account_id=actor.account_id)
        return self._after_write(actor, key, follow.id, started)

    @requires("updateFollow")
    def set_status(self, actor: Actor, key: AcquisitionKey, status: str) -> FollowView:
        """The generic pause: ``disabled`` pauses, any other status resumes.

        On a follow only the actor asked for, it is the actor's own pause. On a follow others asked
        for too it is refused, unless the actor pilots every acquisition, whose pause is the whole
        follow's: every requester's pause is set (the validated maquette, DESIGN § 2.3). An actor
        that did not ask for the follow is refused as on any own-scoped act, before its sharing is
        looked at (§ 2.13).

        Args:
            actor: Who pauses; needs ``acquisition.follow``.
            key: The medium's key.
            status: The status asked.

        Returns:
            The follow as the actor reads it.

        Raises:
            AppNotFound: ``acquisition.not_found`` when no standing follow holds the key.
            AppForbidden: ``acquisition.follow_shared`` on a shared follow, ``acquisition.not_requester``
                on a follow the actor did not ask for.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        paused = status == PAUSED_STATUS
        owner = self._owner()
        with self._guarded(key) as store:
            repository = FollowRepository(store)
            follow = self._standing(repository, key)
            if actor.holds(Right.ACQUISITION_PILOT_ANY):
                changed = follow.paused_for_all(paused, owner=owner)
            elif not any(one.account_id == actor.account_id for one in follow.requesters_or_owner(owner)):
                raise refuse_not_requester(key)
            elif follow.shared_beyond(actor.account_id, owner=owner):
                raise refuse_shared(key)
            else:
                changed = follow.with_setting(actor.account_id, owner=owner, paused=paused)
            started = self._save(repository, changed)
        return self._after_write(actor, key, follow.id, started)

    @requires("deleteFollow")
    def remove(self, actor: Actor, key: AcquisitionKey) -> None:
        """The actor leaves the follow; the last one leaving removes it, softly (§ 2.5).

        A removed follow keeps its row, its history and its open wanted rows, which the pause gate
        skips; ``restore`` brings it back as it was.

        Args:
            actor: Who leaves; needs ``acquisition.follow``.
            key: The medium's key.

        Raises:
            AppNotFound: ``acquisition.not_found`` when no standing follow holds the key.
            AppForbidden: ``acquisition.not_requester`` when the actor did not ask for it.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        now = int(self._clock())
        with self._guarded(key) as store:
            repository = FollowRepository(store)
            follow = self._standing(repository, key)
            left = follow.without_requester(actor.account_id, now, owner=self._owner())
            self._save(repository, left)
        log.info(
            "app.follows.requester_removed",
            followed_id=follow.id,
            account_id=actor.account_id,
            removed=left.removed_at is not None,
        )

    @requires("restoreFollow")
    def restore(self, actor: Actor, key: AcquisitionKey) -> FollowView:
        """Put back a removed follow as it was, the actor its requester; or take the actor back into a standing one.

        Same row, year, ``addedAt``, search count and open wanted rows; primed when it starts
        taking work again. Only a FOLLOW is restored: a one-off request, ended or standing, is
        not (it ends with its season, § 2.7). A standing follow takes back an actor that could
        ask for it (``acquisition.request``, ``createFollow``'s own right): no leave is recorded,
        so this is how « the caller had only left » (§ 2.5) is told from a join by the back door.

        Args:
            actor: Who restores; needs ``acquisition.follow``.
            key: The medium's key.

        Returns:
            The follow as the actor reads it.

        Raises:
            AppNotFound: ``follow.not_restorable`` when no follow is held under the key, the key
                holds a one-off request, or the follow stands and the actor already asks for it
                or may not ask for it.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        now = int(self._clock())
        owner = self._owner()
        with self._guarded(key) as store:
            repository = FollowRepository(store)
            follow = repository.get(key)
            if follow is None or follow.scope is not Scope.FOLLOW:
                raise refuse_not_restorable(key)
            if follow.removed_at is None and (
                not actor.holds(Right.ACQUISITION_REQUEST)
                or any(one.account_id == actor.account_id for one in follow.requesters_or_owner(owner))
            ):
                raise refuse_not_restorable(key)
            back = follow.with_requester(actor.account_id, Via.FOLLOW, now, owner=owner)
            started = self._save(repository, back)
            log.info("app.follows.restored", followed_id=follow.id, account_id=actor.account_id)
        return self._after_write(actor, key, follow.id, started)

    @requires("setAcquisitionQuality")
    def set_quality(self, actor: Actor, key: AcquisitionKey, floor: QualityFloor | None) -> FollowView:
        """The actor sets its own quality floor; the highest among the right's holders is in force.

        Args:
            actor: A requester; needs ``acquisition.quality.own``.
            key: The medium's key.
            floor: Its floor, ``None`` to clear it.

        Returns:
            The follow as the actor reads it.

        Raises:
            AppNotFound: ``acquisition.not_found`` when no standing follow holds the key.
            AppForbidden: ``acquisition.not_requester`` when the actor did not ask for it.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        with self._guarded(key) as store:
            repository = FollowRepository(store)
            follow = self._standing(repository, key)
            started = self._save(repository, follow.with_setting(actor.account_id, owner=self._owner(), floor=floor))
        return self._after_write(actor, key, follow.id, started)

    @requires("setAcquisitionPause")
    def set_pause(self, actor: Actor, key: AcquisitionKey, paused: bool) -> FollowView:
        """The actor pauses or resumes its own ask; the follow pauses when every holder of the right did.

        Lifting the last pause primes the follow: the catalogue and the queue are as stale as the
        day it was paused.

        Args:
            actor: A requester; needs ``acquisition.pause.own``.
            key: The medium's key.
            paused: The pause asked.

        Returns:
            The follow as the actor reads it.

        Raises:
            AppNotFound: ``acquisition.not_found`` when no standing follow holds the key.
            AppForbidden: ``acquisition.not_requester`` when the actor did not ask for it.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        with self._guarded(key) as store:
            repository = FollowRepository(store)
            follow = self._standing(repository, key)
            started = self._save(repository, follow.with_setting(actor.account_id, owner=self._owner(), paused=paused))
        return self._after_write(actor, key, follow.id, started)

    @requires("reassignRequester")
    def reassign(
        self, actor: Actor, kind: Reassigned, key: AcquisitionKey, source: AccountId, target: AccountId
    ) -> tuple[AccountRef, ...]:
        """Move one requester's ask onto another account of the roster (§ 2.6, O-10 A).

        A target already asking keeps its own ask and the source simply leaves; the moved settings
        do not travel. ``follow`` names a standing follow, ``card`` any standing subject (a one-off
        request's card, or a follow's).

        Args:
            actor: Who reassigns; needs ``acquisition.reassign``.
            kind: What the key names.
            key: The medium's key.
            source: The requester moved.
            target: The account taking its place.

        Returns:
            The acquisition's requesters after the move.

        Raises:
            AppNotFound: ``account.unknown`` when the target is no account of the roster;
                ``acquisition.not_found`` when no such subject holds the key.
            AppForbidden: ``acquisition.not_requester`` when the source did not ask for it.
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        if self._app_store.accounts.account(target) is None:
            raise AppNotFound(
                "The target account does not exist.", code=RefusalCode.ACCOUNT_UNKNOWN, params={"accountId": target}
            )
        now = int(self._clock())
        with self._guarded(key) as store:
            repository = FollowRepository(store)
            follow = self._standing(repository, key)
            if kind == "follow" and follow.scope is not Scope.FOLLOW:
                raise refuse_not_found(key)
            try:
                moved = follow.reassigned(source, target, now, owner=self._owner())
            except NotARequester as exc:
                raise refuse_not_requester(key) from exc
            started = self._save(repository, moved)
        log.info("app.follows.requester_reassigned", followed_id=follow.id, source=source, target=target)
        if started:
            # A consequence of the move, not the reassigning actor's act: the system asks it (as the rights'
            # re-projection does), so it needs no ``acquisition.pilot.any`` of them and says whose it is.
            self._ask_prime(self._system(), follow.id, RunTrigger.SYSTEM)
        return tuple(
            AccountRef(id=one.account_id, name=self._name(one.account_id))
            for one in moved.requesters_or_owner(self._owner())
        )

    @requires("runMaintenanceAction")
    def reproject(self, actor: Actor) -> int:
        """Re-project every follow its requesters put settings in force on (``acquisition-follows-reproject``).

        Args:
            actor: Who runs the maintenance; needs ``pipeline.control``.

        Returns:
            How many follows were re-projected.
        """
        with closing(self._open_store()) as store, store.transaction():
            ids = [FollowId(row.id) for row in store.follow.list_all() if row.id is not None]
            count, started = self._reproject(store, ids)
        log.info("app.follows.reprojected", count=count, cause="maintenance", account_id=actor.account_id)
        self._prime_started(started)
        return count

    # ── the rights' subscriber ───────────────────────────────────────────

    def subscribe(self, bus: EventBus) -> SubscriptionToken:
        """Listen for :class:`AccountRightsChanged` on the process's bus.

        Args:
            bus: The bus.

        Returns:
            The subscription's token.
        """
        return bus.subscribe(AccountRightsChanged, self.on_rights_changed)

    def on_rights_changed(self, event: AccountRightsChanged) -> None:
        """Re-project the follows the accounts whose rights moved asked for.

        A failure is logged, never raised: the rights write it follows has committed.

        Args:
            event: The accounts and why their rights moved.
        """
        try:
            with closing(self._open_store()) as store, store.transaction():
                ids = [FollowId(one) for one in store.requesters.follows_of(event.account_ids)]
                count, started = self._reproject(store, ids)
        except Exception:  # a subscriber never breaks its publisher; the action repairs it
            log.exception("app.follows.reproject_failed", accounts=list(event.account_ids), cause=event.cause.value)
            return
        log.info("app.follows.reprojected", count=count, cause=event.cause.value)
        self._prime_started(started)

    # ── internals ────────────────────────────────────────────────────────

    @contextmanager
    def _guarded(self, key: AcquisitionKey) -> Iterator[AcquireStore]:
        """Open a store and ONE transaction for a load-and-save, mapping the model's errors to refusals.

        The transaction takes the writer lock before the load, so no other writer, in any process,
        commits between the load and the save; a refusal raised inside rolls back whatever was
        written.

        Args:
            key: The key the act names, for the refusals.

        Yields:
            The open store, inside its transaction.

        Raises:
            AppConflict: ``follow.ambiguous`` (from :class:`FollowAmbiguous`).
            AppNotFound: ``acquisition.not_found`` (from :class:`FollowRemoved`).
            AppForbidden: ``acquisition.not_requester`` (from :class:`NotARequester`).
        """
        with closing(self._open_store()) as store:
            try:
                with store.transaction():
                    yield store
            except FollowAmbiguous as exc:
                raise refuse_ambiguous(key) from exc
            except FollowRemoved as exc:
                raise refuse_not_found(key) from exc
            except NotARequester as exc:
                raise refuse_not_requester(key) from exc

    @staticmethod
    def _standing(repository: FollowRepository, key: AcquisitionKey) -> Follow:
        """The standing follow or request the key names.

        Args:
            repository: The repository.
            key: The key.

        Returns:
            The follow.

        Raises:
            AppNotFound: ``acquisition.not_found`` when none stands under the key.
        """
        follow = repository.get(key)
        if follow is None or follow.removed_at is not None:
            raise refuse_not_found(key)
        return follow

    def _save(self, repository: FollowRepository, follow: Follow) -> bool:
        """Save a follow with what its requesters put in force.

        Args:
            repository: The repository.
            follow: The follow as the model left it.

        Returns:
            True when it starts taking work.
        """
        return repository.save(follow, follow.in_force(account_rights(self._app_store)))

    def _reproject(self, store: AcquireStore, ids: list[FollowId]) -> tuple[int, list[FollowId]]:
        """Re-save each follow with what is in force now (inside the caller's transaction).

        Args:
            store: The open store, its transaction open.
            ids: The follows.

        Returns:
            How many were saved, and those the save turned on (taking work again).
        """
        repository = FollowRepository(store)
        holds = account_rights(self._app_store)
        count = 0
        started: list[FollowId] = []
        for follow_id in ids:
            follow = repository.get_by_id(follow_id)
            if follow is None or follow.legacy is not None:
                continue  # gone, or no requester: nothing but its own v0 settings is in force
            if repository.save(follow, follow.in_force(holds)):
                started.append(follow_id)
            count += 1
        return count, started

    def _prime_started(self, started: list[FollowId]) -> None:
        """Prime each follow a re-projection turned on, as the system actor, after the commit (§ 2.3).

        Args:
            started: The follows turned on.
        """
        if not started:
            return
        system = self._system()
        for follow_id in started:
            self._ask_prime(system, follow_id, RunTrigger.SYSTEM)

    def _after_write(self, actor: Actor, key: AcquisitionKey, follow_id: FollowId, started: bool) -> FollowView:
        """Prime a follow that starts taking work, then read it back as the actor sees it.

        Args:
            actor: Who wrote.
            key: The key the act named.
            follow_id: The follow written.
            started: Whether the write started it.

        Returns:
            The follow as the actor reads it.
        """
        if started:
            self._ask_prime(actor, follow_id)
        return self._read_one(actor, key, follow_id)

    def _ask_prime(self, actor: Actor, follow_id: FollowId, trigger: RunTrigger = RunTrigger.WEB) -> None:
        """Ask the supervisor for a prime of the follow; a refusal or a failure is logged, never raised.

        Args:
            actor: Who asks; the ask is authorised against it.
            follow_id: The follow.
            trigger: What the ask comes from: the web for an actor's own write, the system for a
                consequence nobody asked for.
        """
        try:
            asked = self._runs.ask_acquisition(actor, prime(follow_id), trigger=trigger)
        except Exception:  # the write stands whatever the ask does (DESIGN § 2.3)
            log.warning("app.follows.prime_ask_failed", followed_id=follow_id, exc_info=True)
            return
        log.info("app.follows.primed", followed_id=follow_id, uid=asked.uid, joined=asked.joined)

    def _read_one(self, actor: Actor, key: AcquisitionKey, follow_id: FollowId) -> FollowView:
        """Read one follow back after a write.

        Args:
            actor: The reader.
            key: The key the act named.
            follow_id: The follow.

        Returns:
            The follow as the actor reads it.

        Raises:
            AppNotFound: ``acquisition.not_found`` when its row went meanwhile.
        """
        owner = self._owner()
        with closing(self._open_store()) as store, closing(self._open_ownership()) as ownership:
            repository = FollowRepository(store)
            follow = repository.get_by_id(follow_id)
            row = repository.row(follow_id)
            if follow is None or row is None:
                raise refuse_not_found(key)
            return self._view(
                store, ownership, follow, row, actor, owner, account_rights(self._app_store), self._priming()
            )

    def _priming(self) -> set[int]:
        """The follows a ``prime`` is queued or running for, read from the supervisor's queue.

        Returns:
            Their rows; empty when the queue cannot be read (logged).
        """
        try:
            view = self._runs.queue_view()
        except Exception:  # an unreadable queue only loses the « verifying » reading
            log.warning("app.follows.queue_unreadable", exc_info=True)
            return set()
        requests = [*view.acquisition_queued, *([view.acquisition_running] if view.acquisition_running else [])]
        primed: set[int] = set()
        for request in requests:
            if request.state is RequestState.SETTLED:
                continue
            job = request.job
            if job.kind is JobKind.PRIME and job.followed_id is not None:
                primed.add(job.followed_id)
        return primed

    def _name(self, account: AccountId) -> str:
        """An account's display name.

        Args:
            account: Its key.

        Returns:
            Its name; its key when the account is gone.
        """
        found = self._app_store.accounts.account(account)
        return found.name if found is not None else account

    def _view(
        self,
        store: AcquireStore,
        ownership: OwnershipReader,
        follow: Follow,
        row: FollowedSeries,
        actor: Actor,
        owner: AccountId,
        holds: RightCheck,
        priming: set[int],
    ) -> FollowView:
        """Build a follow's answer from its row, its rows in the queue, the library and its requesters.

        Args:
            store: The open acquire store.
            ownership: What the library holds.
            follow: The aggregate.
            row: Its ``followed_series`` row.
            actor: The reader.
            owner: The account a requester-less follow is the ask of.
            holds: Whether an account's role holds a right.
            priming: The follows a prime is queued or running for.

        Returns:
            The answer.
        """
        requesters = follow.requesters_or_owner(owner)
        own = next((one for one in requesters if one.account_id == actor.account_id), None)
        in_force: InForce = follow.in_force(holds)
        card = store.follow.card(follow.id)
        status, aired, owned, next_air = self._status(store, ownership, row, card)
        return FollowView(
            key=follow.key.wire,
            title=row.title,
            kind=row.kind,
            year=row.year,
            status=VERIFYING if follow.id in priming else status,
            show_status=card.series_status if card is not None and row.kind == "show" else None,
            added_at=row.added_at,
            next_air_date=next_air,
            searches=sum(item.attempts for kind in _ROW_KINDS for item in self._rows(store, row, kind)),
            aired=aired,
            owned=owned,
            ids=row.media_ref,
            poster=card.poster_url if card is not None else None,
            requesters=tuple(AccountRef(id=one.account_id, name=self._name(one.account_id)) for one in requesters),
            own_quality=own.floor if own is not None else None,
            quality=in_force.floor,
            own_paused=own.paused if own is not None else False,
            paused=in_force.paused,
        )

    @staticmethod
    def _rows(store: AcquireStore, row: FollowedSeries, kind: WantedKind) -> list[WantedItem]:
        """A follow's wanted rows of one kind, every status.

        Args:
            store: The open acquire store.
            row: The follow's row.
            kind: The row family.

        Returns:
            The rows.
        """
        assert row.id is not None
        return store.wanted.list_for_followed(row.id, kind=kind)

    def _status(
        self, store: AcquireStore, ownership: OwnershipReader, row: FollowedSeries, card: FollowCard | None
    ) -> tuple[str, int | None, int | None, str | None]:
        """Derive a follow's card status from the single derivation, with its show counts.

        Args:
            store: The open acquire store.
            ownership: What the library holds.
            row: The follow's row.
            card: Its card facts (the show's production status).

        Returns:
            ``(status, aired, owned, next air date)``; the counts and the date ``None`` for a film.
        """
        today = self._today()
        if row.kind == "movie":
            status, outcome, found = select_wanted_facts(
                (item.id or 0, item.status, item.last_search_outcome, item.last_search_found)
                for item in self._rows(store, row, "movie")
            )
            return (
                derive_movie_status(
                    active=row.active,
                    owned=ownership.owns(row.media_ref, kind="movie"),
                    wanted_status=status,
                    last_search_outcome=outcome,
                    last_search_found=found,
                ),
                None,
                None,
                None,
            )
        episodes, _ = episode_states(store, ownership, row, today)
        states = [one.state for one in episodes if one.state != "announced"]
        ahead = sorted(one.air_date for one in episodes if one.state == "announced" and one.air_date)
        aired = len(states) if states else None
        status = derive_follow_status(
            active=row.active,
            aired_count=aired,
            to_grab_count=states.count("to_grab") if states else None,
            acquiring_count=sum(1 for one in states if one in _ACQUIRING) if states else None,
            pending_count=states.count("pending") if states else None,
            unverified_count=states.count("unverified") if states else None,
            announced_count=len(ahead),
            series_status=card.series_status if card is not None else None,
        )
        return status, aired, states.count("in_library") if states else None, ahead[0] if ahead else None
