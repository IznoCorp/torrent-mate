"""A world the follow service and the season ask are tested in: a real acquire store, ``app.db`` and supervisor queue.

Both stores live on the test's ``tmp_path``; the supervisor's :class:`RunService` is the real one, its
target authorised against the acquire store's requesters as in production (``AcquireRequesters``).
The library is a fake: what it holds is set by the test.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.model import Account, Role
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.acquisition.completeness import FollowCompleteness
from personalscraper.app.acquisition.follows import FollowService
from personalscraper.app.acquisition.seasons import HeldShow, SeasonAsk
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor.model import JobKind, RunKind, Settlement
from personalscraper.app.supervisor.requesters import AcquireRequesters
from personalscraper.app.supervisor.service import RunService
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
READ_ONLY = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)
TODAY = date(2026, 11, 23)
NOW = 1_800_000_000

OWNER = AccountId("account-owner")
ALICE = AccountId("account-alice")
BOB = AccountId("account-bob")
CAROL = AccountId("account-carol")
DAVE = AccountId("account-dave")
ERIN = AccountId("account-erin")
FRANK = AccountId("account-frank")

#: What an ordinary member's role holds: ask, follow, pilot its own, set its own quality and pause.
MEMBER_RIGHTS = frozenset(
    {
        Right.ACQUISITION_REQUEST,
        Right.ACQUISITION_FOLLOW,
        Right.ACQUISITION_PILOT_OWN,
        Right.ACQUISITION_QUALITY_OWN,
        Right.ACQUISITION_PAUSE_OWN,
    }
)
MEMBER = RoleId("role-member")
#: A member who also reads every follow.
SEER = RoleId("role-seer")
#: A member who pilots every acquisition, without reading the others' follows.
PILOT = RoleId("role-pilot")
#: A role that may reassign, and pilots every acquisition (the primes a reassign asks are its).
MANAGER = RoleId("role-manager")
#: A member who may follow and restore, but not ask for a medium (no ``acquisition.request``).
WATCHER = RoleId("role-watcher")

ROLES: dict[RoleId, frozenset[Right]] = {
    MEMBER: MEMBER_RIGHTS,
    SEER: MEMBER_RIGHTS | {Right.ACQUISITION_SEE_OTHERS},
    PILOT: MEMBER_RIGHTS | {Right.ACQUISITION_PILOT_ANY},
    MANAGER: MEMBER_RIGHTS | {Right.ACQUISITION_REASSIGN, Right.ACQUISITION_PILOT_ANY},
    WATCHER: MEMBER_RIGHTS - {Right.ACQUISITION_REQUEST},
}
ACCOUNTS: dict[AccountId, RoleId] = {
    ALICE: MEMBER,
    BOB: MEMBER,
    CAROL: PILOT,
    DAVE: SEER,
    ERIN: MANAGER,
    FRANK: WATCHER,
}

#: The system actor, the owner's: who primes a follow a re-projection turns on.
SYSTEM = Actor.system(NO_CEILING, account_id=OWNER, name="owner")


@dataclass
class FakeOwnership:
    """The library's ownership, as the test sets it.

    Attributes:
        pairs: The ``(season, episode)`` pairs held, for any show.
        movies: Whether a film is held.
    """

    pairs: set[tuple[int, int]] = field(default_factory=set)
    movies: bool = False

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Whether a work is held.

        Args:
            media_ref: Ignored.
            kind: The work's kind.
            season: The episode's season.
            episode: The episode's number.

        Returns:
            The movie flag, or the episode's pair among those held.
        """
        return self.movies if kind == "movie" else (season, episode) in self.pairs

    def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
        """The pairs held.

        Args:
            media_ref: Ignored.

        Returns:
            A copy of the held pairs.
        """
        return set(self.pairs)

    def close(self) -> None:
        """Nothing to release."""


@dataclass
class FakeShows:
    """The library's shows, as the test sets them.

    Attributes:
        shows: The held show per id text of the key that finds it.
    """

    shows: dict[str, HeldShow] = field(default_factory=dict)

    def held_show(self, ref: MediaRef) -> HeldShow | None:
        """The show held under the ref's one id.

        Args:
            ref: The medium.

        Returns:
            The show, or ``None``.
        """
        return next((show for key, show in self.shows.items() if key in _ids(ref)), None)


def _ids(ref: MediaRef) -> set[str]:
    """The ref's ids as ``provider:id`` texts.

    Args:
        ref: The ref.

    Returns:
        The texts.
    """
    texts = set()
    if ref.tvdb_id is not None:
        texts.add(f"tvdb:{ref.tvdb_id}")
    if ref.tmdb_id is not None:
        texts.add(f"tmdb:{ref.tmdb_id}")
    if ref.imdb_id is not None:
        texts.add(f"imdb:{ref.imdb_id}")
    return texts


def actor(account: AccountId, *, ceiling: InstanceCeiling = NO_CEILING, role: RoleId | None = None) -> Actor:
    """The actor of a seeded account, its role's rights as the roster holds them.

    Args:
        account: The account.
        ceiling: The instance's ceiling.
        role: The role it acts with, when not its seeded one (the owner, whose seeded role is Admin).

    Returns:
        The actor.
    """
    role = role if role is not None else ACCOUNTS[account]
    return Actor(
        account_id=account,
        name=account.removeprefix("account-"),
        role_id=role,
        role_kind=RoleKind.ORDINARY,
        role_rights=ROLES[role],
        ceiling=ceiling,
    )


class FollowWorld:
    """The stores, the queue and the services of one test."""

    def __init__(self, tmp_path: Path) -> None:
        """Build the stores, seed the roster, build the services.

        Args:
            tmp_path: The test's temporary directory.
        """
        self.acquire_db = tmp_path / "acquire.db"
        self.store: ConcreteAcquireStore = self.open_store()
        self.app_store = AppStore(tmp_path / "app.db")
        for role_id, rights in ROLES.items():
            self.app_store.roles.insert_role(
                Role(id=role_id, name=role_id, kind=RoleKind.ORDINARY, rights=rights), now=1.0
            )
        for account, role_id in ACCOUNTS.items():
            self.app_store.accounts.insert_account(_account(account, role_id))
        self.app_store.accounts.insert_account(_account(OWNER, RoleId("admin")))
        self.clock = float(NOW)
        self.ownership = FakeOwnership()
        self.shows = FakeShows()
        self.runs = RunService(
            store=self.app_store,
            data_dir=tmp_path,
            clock=lambda: self.clock,
            requesters=AcquireRequesters(self.acquire_db),
        )
        self.follows = FollowService(
            open_store=self.open_store,
            open_ownership=lambda: self.ownership,
            app_store=self.app_store,
            runs=self.runs,
            owner=lambda: OWNER,
            system=lambda: SYSTEM,
            clock=lambda: self.clock,
            today=lambda: TODAY,
        )
        self.seasons = SeasonAsk(
            open_store=self.open_store,
            open_ownership=lambda: self.ownership,
            shows=self.shows,
            app_store=self.app_store,
            runs=self.runs,
            owner=lambda: OWNER,
            clock=lambda: self.clock,
            today=lambda: TODAY,
        )
        self.completeness = FollowCompleteness(
            open_store=self.open_store, open_ownership=lambda: self.ownership, owner=lambda: OWNER, today=lambda: TODAY
        )

    def open_store(self) -> ConcreteAcquireStore:
        """Open the acquire store (a fresh handle per call, as production's).

        Returns:
            The store.
        """
        return build_acquire_store(AcquireConfig(db_path=self.acquire_db))

    def close(self) -> None:
        """Close the stores."""
        self.store.close()
        self.app_store.close()

    def legacy_follow(self, ref: MediaRef, *, kind: Literal["show", "movie"] = "show", title: str = "Show") -> int:
        """A follow written before requesters existed (v0's create).

        Args:
            ref: Its ids.
            kind: Its kind.
            title: Its title.

        Returns:
            Its row.
        """
        return self.store.follow.add(FollowedSeries(media_ref=ref, title=title, added_at=100, kind=kind))

    def row(self, followed_id: int) -> FollowedSeries:
        """Read a follow's row.

        Args:
            followed_id: The row.

        Returns:
            The row.
        """
        found = self.store.follow.get(followed_id)
        assert found is not None
        return found

    def requesters(self, followed_id: int) -> dict[str, tuple[str, int | None, bool]]:
        """A follow's stored requesters.

        Args:
            followed_id: The row.

        Returns:
            ``account → (via, floor, paused)``.
        """
        return {one.account_id: (one.via, one.floor, one.paused) for one in self.store.requesters.list_for(followed_id)}

    def profile_floor(self, followed_id: int) -> int | None:
        """The ``min_resolution`` the projection wrote on a follow's row.

        Args:
            followed_id: The row.

        Returns:
            The floor, ``None`` when none.
        """
        profile = self.row(followed_id).quality_profile_json
        return None if profile is None else json.loads(profile).get("min_resolution")

    def primes(self) -> list[int | None]:
        """The follows a prime is queued for, in the order asked.

        Returns:
            Their rows.
        """
        view = self.runs.queue_view()
        return [
            request.job.followed_id
            for request in view.acquisition_queued
            if request.kind is RunKind.ACQUISITION and request.job.kind is JobKind.PRIME
        ]

    def settle_all(self) -> None:
        """Settle every queued acquisition request, as a worker would once done."""
        for request in self.runs.queue_view().acquisition_queued:
            request.admit(None, self.clock)
            request.settle(Settlement.SUCCESS, self.clock)
            with self.app_store.immediate():
                self.app_store.runs.save(request)

    def season_row(self, followed_id: int, season: int, status: str = "pending") -> int:
        """Write one season row of a follow, as the engine's season rule would.

        Args:
            followed_id: The follow.
            season: Its season.
            status: Its status.

        Returns:
            Its row.
        """
        return self.store.wanted.add(
            WantedItem(
                media_ref=self.row(followed_id).media_ref,
                kind="season",
                status=status,  # type: ignore[arg-type]
                enqueued_at=NOW - 10,
                followed_id=followed_id,
                season=season,
                episode=None,
                trigger="automatic",
            )
        )

    def status(self, wanted_id: int) -> str:
        """A wanted row's status.

        Args:
            wanted_id: The row.

        Returns:
            Its status.
        """
        found = self.store.wanted.get(wanted_id)
        assert found is not None
        return found.status

    def episode(self, followed_id: int, season: int, number: int, status: str) -> int:
        """Write one episode row of a follow; a ``grabbed`` one holds a torrent.

        Args:
            followed_id: The follow.
            season: Its season.
            number: Its number.
            status: Its status.

        Returns:
            Its row.
        """
        row_id = self.store.wanted.add(
            WantedItem(
                media_ref=self.row(followed_id).media_ref,
                kind="episode",
                status="pending" if status == "grabbed" else status,  # type: ignore[arg-type]
                enqueued_at=NOW - 10,
                followed_id=followed_id,
                season=season,
                episode=number,
            )
        )
        if status == "grabbed":
            self.store.wanted.mark_grabbed(row_id, f"{row_id:040x}")
        return row_id

    def aired(self, followed_id: int, pairs: Iterable[tuple[int, int, str]]) -> None:
        """Cache a follow's aired episodes.

        Args:
            followed_id: The follow.
            pairs: ``(season, episode, ISO air date)`` each.
        """
        self.store.aired.replace_for_followed(
            followed_id, [(season, number, None, day) for season, number, day in pairs], now=NOW - 100
        )


def _account(account: AccountId, role_id: RoleId) -> Account:
    """An account row.

    Args:
        account: Its key.
        role_id: Its role.

    Returns:
        The row.
    """
    return Account(
        id=account,
        name=account.removeprefix("account-").title(),
        email=f"{account}@example.org",
        avatar="",
        role_id=role_id,
        password_hash=None,
        created_at=1.0,
        updated_at=1.0,
    )
