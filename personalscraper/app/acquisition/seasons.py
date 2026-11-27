"""``SeasonAsk``: a whole season asked by medium, of a follow or as a one-off request (K3 DESIGN § 2.7).

The subject is resolved by the medium's key: a standing follow asks its own season; else a show the
library OWNS (by provider id) gets a ONE-OFF REQUEST (O-2 A): a subject row of scope ``request``, never
listed among the follows and never detected for new episodes, the caller its requester ``via request``;
else ``404 acquisition.not_found``. A standing request is asked again on its own row. A removed row
asked again comes back as a request, of the asked season only: its kept open rows of other seasons,
not yet holding a torrent, are abandoned, or the engine would take them all back (it reads ``active``).
A follow written before requesters existed takes its owner's ask as a requester row, so the
supervisor's target check reads the owner among its requesters.

Everything is written in ONE store transaction (DESIGN § 2.7): the subject, its requesters and their
projection, the season row and its absorptions commit together or not at all.

The season row is written ``trigger = 'manual'`` (SR5) and absorbs the live episode rows of its season,
pointing those already holding a torrent without touching them (SR2 under Q9) — the store's
``absorb_episodes`` does both. An open season row answers ``reused`` and no season is written. A fresh
season, or a subject the write turned on, asks the supervisor for a ``prime`` of its subject after the
commit; a refused or failed ask is logged and answered ``queued: false``, the season standing.

``absorbedCount`` counts the season's AIRED episodes the library does not hold (B-380), from the
follow's aired cache, or for a request from the library's aired catalogue — not the rows absorbed.
A request whose show neither that catalogue nor an aired cache knows is refused
``409 acquisition.season_unknown``, a ``reused`` ask included, never answered 0.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.season import SeasonRecovery
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.acquisition.completeness import OwnershipReader
from personalscraper.app.acquisition.follow_repository import FollowAmbiguous, FollowRepository
from personalscraper.app.acquisition.follows import account_rights, prime
from personalscraper.app.acquisition.model import AcquisitionKey, Follow, FollowId, Scope
from personalscraper.app.acquisition.refusals import (
    refuse_ambiguous,
    refuse_not_found,
    refuse_not_requester,
    refuse_season_unknown,
)
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.library.catalogue import aired_pairs
from personalscraper.app.library.listing import held_of, open_reader
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import WantedKind
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.accounts.ids import AccountId
    from personalscraper.app.library.completeness import CatalogueView
    from personalscraper.app.store.store import AppStore
    from personalscraper.app.supervisor.service import RunService
    from personalscraper.core.identity import MediaRef
    from personalscraper.indexer.library_view import LibraryIndex

log = get_logger("app.acquisition.seasons")

__all__ = ["HeldShow", "IndexedShows", "SeasonAsk", "SeasonAsked"]

#: The episode rows a season ask takes in: the live ones are absorbed, a grabbed one only pointed (SR2).
_TAKEN_IN = frozenset({"pending", "searching", "available", "grabbed"})

#: The open rows a removed subject revived as a request gives up outside its season: those holding no torrent.
_ABANDONED_OUTSIDE = frozenset({"pending", "searching", "available"})

#: The row families a revived request is narrowed over.
_NARROWED_KINDS: tuple[WantedKind, ...] = ("episode", "season")

#: The field a season outside the numbered range is refused on.
_SEASON_FIELD = "season"

#: The last season number asked: it holds the year-numbered seasons, and SQLite binds no unbounded integer.
_LAST_SEASON = 9999


@dataclass(frozen=True)
class HeldShow:
    """A show the library holds, as a one-off request needs it.

    Attributes:
        title: Its title.
        year: Its year, ``None`` when unknown.
        ref: Every provider id the library knows it by.
        aired: The ``(season, episode)`` pairs its aired catalogue lists, ``None`` when never catalogued.
        owned: The pairs the library holds live files of.
    """

    title: str
    year: int | None
    ref: MediaRef
    aired: frozenset[tuple[int, int]] | None
    owned: frozenset[tuple[int, int]]


class HeldShows(Protocol):
    """What the library holds of a show: a port, so the season ask is tested without an index."""

    def held_show(self, ref: MediaRef) -> HeldShow | None:
        """The show the library holds live files of under the reference, if any.

        Args:
            ref: The medium, by the one id its key names.

        Returns:
            The show, or ``None`` when the library holds no live show under that id.
        """
        ...


class IndexedShows:
    """The library's shows, read through the indexer (``library.db``, never by SQL) and the aired catalogue."""

    def __init__(self, *, index: LibraryIndex, view: CatalogueView, today: Callable[[], date] = date.today) -> None:
        """Hold the index and the catalogue view; nothing is opened yet.

        Args:
            index: The library index.
            view: The aired catalogue crossed with the library (shared, closed by its owner).
            today: Today's date.
        """
        self._index = index
        self._view = view
        self._today = today

    def held_show(self, ref: MediaRef) -> HeldShow | None:
        """The show the library holds live files of under the reference, if any.

        Args:
            ref: The medium.

        Returns:
            The show; ``None`` when no live show row holds the id.

        Raises:
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        with open_reader(self._index) as reader:
            holders, folders = held_of(reader, ref)
        shows = [row for row in holders if row.kind == "show"]
        live = [row for row in shows if row.item_id in folders]
        if not live:
            return None
        held = live[0]
        held_ref = held.media_ref()
        if held_ref is None:
            return None
        episodes = self._view.catalogue_of(held)
        owned: set[tuple[int, int]] = set()
        for row in shows:
            owned |= self._view.owned_pairs(row)
        return HeldShow(
            title=held.title,
            year=held.year,
            ref=held_ref,
            aired=frozenset(aired_pairs(episodes, self._today())) if episodes is not None else None,
            owned=frozenset(owned),
        )


@dataclass(frozen=True)
class SeasonAsked:
    """The answer to a season ask.

    Attributes:
        season: The season asked.
        absorbed_count: Its aired episodes the library does not hold.
        queued: Whether a prime of its subject was asked of the supervisor.
        run_uid: That request's uid, ``None`` when none was asked.
        reused: Whether an open season row answered the ask (nothing written).
    """

    season: int
    absorbed_count: int
    queued: bool
    run_uid: str | None
    reused: bool


@dataclass(frozen=True)
class _Subject:
    """The row a season is asked of, and what counts its aired episodes.

    Attributes:
        follow: The follow or request, as written.
        row: Its ``followed_series`` row.
        held: The library's show, for a request (its catalogue counts the aired episodes).
        started: Whether writing the subject turned it on (``active`` false → true).
    """

    follow: Follow
    row: FollowedSeries
    held: HeldShow | None
    started: bool


class SeasonAsk:
    """Asks a season of a medium, for a signed-in actor."""

    def __init__(
        self,
        *,
        open_store: Callable[[], AcquireStore],
        open_ownership: Callable[[], OwnershipReader],
        shows: HeldShows,
        app_store: AppStore,
        runs: RunService,
        owner: Callable[[], AccountId],
        clock: Callable[[], float] = time.time,
        today: Callable[[], date] = date.today,
    ) -> None:
        """Build the service; nothing is opened until a call.

        Args:
            open_store: Opens the acquire store for one call (closed after it).
            open_ownership: Opens the library's ownership reader for one call (closed after it).
            shows: What the library holds of a show.
            app_store: The environment's ``app.db``: the roles in force.
            runs: The supervisor's queue the prime is asked of.
            owner: The account a follow with no requester is the ask of (ruling 9).
            clock: The epoch clock.
            today: Today's date.
        """
        self._open_store = open_store
        self._open_ownership = open_ownership
        self._shows = shows
        self._app_store = app_store
        self._runs = runs
        self._owner = owner
        self._clock = clock
        self._today = today

    @requires("grabSeasonForFollow")
    def ask(self, actor: Actor, key: AcquisitionKey, season: int) -> SeasonAsked:
        """Ask one season of the medium *key* names.

        Args:
            actor: Who asks; needs ``acquisition.pilot.own`` (a follow of its own) or ``.any``.
            key: The show's key.
            season: The season, from 1.

        Returns:
            The answer: ``reused`` when an open season row stands (primed only when the ask turned
            its subject on), else the season written and primed.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``season`` for a season outside 1 to 9999.
            AppNotFound: ``acquisition.not_found`` when no follow, request or owned show answers the key.
            AppForbidden: ``acquisition.not_requester`` on a follow the actor neither asked for nor pilots.
            AppConflict: ``follow.ambiguous`` when two rows hold the key;
                ``acquisition.season_unknown`` for a request whose show's episodes nothing lists.
        """
        if not 1 <= season <= _LAST_SEASON:
            raise AppBadRequest(
                f"A season is numbered from 1 to {_LAST_SEASON}.",
                code=RefusalCode.REQUEST_INVALID,
                params={"fields": [_SEASON_FIELD]},
            )
        now = int(self._clock())
        with closing(self._open_store()) as store, closing(self._open_ownership()) as ownership:
            with store.transaction():
                try:
                    subject = self._subject(store, actor, key, season, now)
                except FollowAmbiguous as exc:
                    raise refuse_ambiguous(key) from exc
                follow_id = subject.follow.id
                absorbed_count = self._aired_unowned(store, ownership, subject, season)
                if absorbed_count is None:
                    # Raised inside the transaction: the request row it opened is undone with it.
                    raise refuse_season_unknown(key)
                covering = SeasonRecovery(store).covering(follow_id, season)
                started = subject.started
                if covering is None and subject.follow.legacy is not None:
                    # The owner's ask on a follow made before requesters: written, so the prime's target check reads it.
                    owned = subject.follow.with_owner_ask(self._owner())
                    started = FollowRepository(store).save(owned, owned.in_force(account_rights(self._app_store)))
                season_id, absorbed = (
                    (None, 0) if covering is not None else self._write_season(store, subject, season, now)
                )
        if season_id is None:
            log.info("app.seasons.reused", followed_id=follow_id, season=season, started=started)
            run_uid = self._ask_prime(actor, follow_id) if started else None
            return SeasonAsked(
                season=season, absorbed_count=absorbed_count, queued=run_uid is not None, run_uid=run_uid, reused=True
            )
        log.info(
            "app.seasons.asked",
            followed_id=follow_id,
            season=season,
            season_wanted_id=season_id,
            absorbed=absorbed,
            scope=subject.follow.scope.value,
        )
        run_uid = self._ask_prime(actor, follow_id)
        return SeasonAsked(
            season=season, absorbed_count=absorbed_count, queued=run_uid is not None, run_uid=run_uid, reused=False
        )

    @staticmethod
    def _write_season(store: AcquireStore, subject: _Subject, season: int, now: int) -> tuple[int, int]:
        """Write the season row ``trigger='manual'`` and absorb its live episodes (inside the transaction).

        Args:
            store: The open store, its transaction open.
            subject: The subject the season is asked of.
            season: The season.
            now: Epoch seconds of the ask.

        Returns:
            The season row's id, and how many episode rows it absorbed or pointed.
        """
        follow_id = subject.follow.id
        season_id = store.wanted.add(
            WantedItem(
                media_ref=subject.row.media_ref,
                kind="season",
                status="pending",
                enqueued_at=now,
                followed_id=follow_id,
                season=season,
                episode=None,
                trigger="manual",
            )
        )
        siblings = tuple(
            item.id
            for item in store.wanted.list_for_followed(follow_id, kind="episode")
            if item.id is not None and item.season == season and item.status in _TAKEN_IN
        )
        absorbed = store.wanted.absorb_episodes(season_id, siblings) if siblings else 0
        return season_id, absorbed

    def _subject(self, store: AcquireStore, actor: Actor, key: AcquisitionKey, season: int, now: int) -> _Subject:
        """Resolve and write the subject the season is asked of (inside the transaction).

        Args:
            store: The open store, its transaction open.
            actor: Who asks.
            key: The show's key.
            season: The season asked: a removed row revived as a request keeps only its open rows.
            now: Epoch seconds of the ask.

        Returns:
            The subject: a standing follow, unchanged; or a request, the actor among its requesters.

        Raises:
            AppNotFound: ``acquisition.not_found`` when nothing answers the key.
            AppForbidden: ``acquisition.not_requester`` on a follow that is not the actor's.
            FollowAmbiguous: Two rows hold the key.
        """
        owner = self._owner()
        repository = FollowRepository(store)
        follow = repository.get(key, "show")
        held: HeldShow | None = None
        started = False
        if follow is None or follow.removed_at is not None:
            held = self._shows.held_show(key.ref())
            if held is None:
                raise refuse_not_found(key)
            if follow is None:
                # The library may know the show by an id the key does not name, which a row holds.
                follow = repository.get(AcquisitionKey.of(held.ref, "show"), "show")
        if follow is not None and follow.removed_at is None and follow.scope is Scope.FOLLOW:
            requesters = [one.account_id for one in follow.requesters_or_owner(owner)]
            if not actor.is_requester(requesters):
                raise refuse_not_requester(key)
            asked = follow
        elif follow is not None:
            revived = follow.removed_at is not None
            asked = follow.requested_by(actor.account_id, now, owner=owner)
            if revived:
                self._narrow(store, asked.id, season)
            started = repository.save(asked, asked.in_force(account_rights(self._app_store)))
        else:
            assert held is not None  # no row: the library holds the show
            row_id = store.follow.add(
                FollowedSeries(
                    media_ref=held.ref, title=held.title, added_at=now, active=False, kind="show", year=held.year
                )
            )
            asked = Follow.first_ask(
                FollowId(row_id), AcquisitionKey.of(held.ref, "show"), Scope.REQUEST, actor.account_id, now
            )
            started = repository.save(asked, asked.in_force(account_rights(self._app_store)))
            log.info("app.seasons.request_opened", followed_id=row_id, account_id=actor.account_id)
        row = repository.row(asked.id)
        if row is None:
            raise refuse_not_found(key)
        if asked.scope is Scope.REQUEST and held is None:
            held = self._shows.held_show(key.ref())
        return _Subject(follow=asked, row=row, held=held, started=started)

    @staticmethod
    def _narrow(store: AcquireStore, follow_id: FollowId, season: int) -> None:
        """Abandon a revived row's open rows outside the asked season that hold no torrent.

        A removed follow keeps its open rows (§ 2.5) and the engine takes every row of an active
        subject: revived as a one-off request of ONE season (§ 2.7), it would search and grab
        every season again. A row holding a torrent is left to the reconciliation that closes it.

        Args:
            store: The open store, its transaction open.
            follow_id: The revived subject.
            season: The season asked.
        """
        abandoned = 0
        for kind in _NARROWED_KINDS:
            for item in store.wanted.list_for_followed(follow_id, kind=kind):
                if item.id is not None and item.season != season and item.status in _ABANDONED_OUTSIDE:
                    store.wanted.set_status(item.id, "abandoned")
                    abandoned += 1
        if abandoned:
            log.info("app.seasons.request_narrowed", followed_id=follow_id, season=season, abandoned=abandoned)

    def _aired_unowned(
        self, store: AcquireStore, ownership: OwnershipReader, subject: _Subject, season: int
    ) -> int | None:
        """Count the season's aired episodes the library does not hold (B-380).

        A follow reads its aired cache; a request reads the library's aired catalogue, and its own
        cache when the library has none. A request with neither does not know; a follow whose cache
        is empty counts 0 until its first poll fills it.

        Args:
            store: The open store.
            ownership: What the library holds.
            subject: The subject.
            season: The season.

        Returns:
            The count, ``None`` for a request whose show nothing lists the episodes of.
        """
        held = subject.held
        if subject.follow.scope is Scope.REQUEST and held is not None and held.aired is not None:
            return sum(1 for pair in held.aired if pair[0] == season and pair not in held.owned)
        today = self._today().isoformat()
        cached = store.aired.list_for_followed(subject.follow.id)
        if subject.follow.scope is Scope.REQUEST and not cached:
            return None
        aired = {
            (one.season, one.episode)
            for one in cached
            if one.season == season and (not one.air_date or one.air_date <= today)
        }
        if not aired:
            return 0
        return len(aired - ownership.owned_pairs(subject.row.media_ref))

    def _ask_prime(self, actor: Actor, follow_id: FollowId) -> str | None:
        """Ask the supervisor for a prime of the subject; a refusal or a failure is logged.

        Args:
            actor: Who asked the season.
            follow_id: The subject.

        Returns:
            The request's uid, ``None`` when the ask failed.
        """
        try:
            asked = self._runs.ask_acquisition(actor, prime(follow_id))
        except Exception:  # the season stands whatever the ask does
            log.warning("app.seasons.prime_ask_failed", followed_id=follow_id, exc_info=True)
            return None
        return str(asked.uid)
