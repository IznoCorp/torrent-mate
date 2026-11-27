"""``ReleaseReads``: the release candidates of one wanted item (K3 DESIGN § 2.9, ``readReleases``).

A concluded search keeps the ranked candidates it found on the wanted row (``wanted_candidate``);
this reads them back with no tracker call. The item is named the way the contract names it: the
follow's key, and the season and episode asked — both for an episode, the season alone for a
season pack, neither for a film.

The read is own-scoped as every acquisition read is (DESIGN § 2.4): the follow is read when the
actor holds ``acquisition.see.others`` or asked for it, and otherwise answers an empty set on a
200, never a refusal. The door's own right (``acquisition.pilot.own`` or ``.any``) is the route's.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, get_args

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES, WantedKind
from personalscraper.app.acquisition.follow_repository import FollowRepository
from personalscraper.app.acquisition.model import FollowId
from personalscraper.app.errors import AppBadRequest, RefusalCode

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import WantedCandidate, WantedItem
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.accounts.ids import AccountId
    from personalscraper.app.acquisition.model import AcquisitionKey

__all__ = ["ReleaseOffer", "ReleaseReads", "release_handle"]

#: Hex digits of a release's digest kept in its handle: 64 bits, far past a collision among the few
#: dozen candidates one row holds.
_DIGEST_LENGTH: Final[int] = 16

#: Separates a handle's wanted row from its digest.
_HANDLE_SEPARATOR: Final[str] = ":"

#: The field an episode asked with no season is refused on.
_EPISODE_FIELD = "episode"


def release_handle(wanted_id: int, candidate: WantedCandidate) -> str:
    """Name one candidate of one wanted row: the handle a grab chooses a release by.

    ``<wantedId>:<digest>``: the row, so the grab finds where the choice was made without reading
    every row; and a digest of what the candidate IS (its tracker, title, hash and size), never of
    its rank. A re-search that replaces the set and still offers the release leaves the handle
    valid; one that no longer offers it leaves a handle that names nothing, and the grab says the
    release is gone rather than taking another in its place.

    Args:
        wanted_id: The wanted row the candidate was found for.
        candidate: The candidate.

    Returns:
        The handle.
    """
    identity = "\x1f".join((candidate.provider, candidate.title, candidate.info_hash or "", str(candidate.size_bytes)))
    digest = hashlib.sha256(identity.encode()).hexdigest()[:_DIGEST_LENGTH]
    return f"{wanted_id}{_HANDLE_SEPARATOR}{digest}"


@dataclass(frozen=True)
class ReleaseOffer:
    """One candidate, with the wanted row it was found for.

    Attributes:
        wanted_id: The wanted row.
        candidate: The candidate.
    """

    wanted_id: int
    candidate: WantedCandidate

    @property
    def handle(self) -> str:
        """The handle a grab chooses this release by.

        Returns:
            :func:`release_handle` of the row and the candidate.
        """
        return release_handle(self.wanted_id, self.candidate)


def _kind_of(season: int | None, episode: int | None) -> WantedKind:
    """Name the row family the asked coordinates address.

    Args:
        season: The asked season, ``None`` for a film.
        episode: The asked episode, ``None`` for a season pack or a film.

    Returns:
        ``"episode"`` for both, ``"season"`` for the season alone, ``"movie"`` for neither.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``episode``, when an episode is asked with no season.
    """
    if season is None:
        if episode is not None:
            raise AppBadRequest(
                "An episode needs its season.", code=RefusalCode.REQUEST_INVALID, params={"fields": [_EPISODE_FIELD]}
            )
        return "movie"
    return "season" if episode is None else "episode"


def _governing(rows: list[WantedItem], season: int | None, episode: int | None) -> WantedItem | None:
    """Pick the wanted row that speaks for the coordinates: the latest open one.

    A closed row is history, and its stale set is not offered; of two open rows a re-follow or a
    crash left, the highest id is the current intent (the rule of ``select_wanted_facts``).

    Args:
        rows: Every row of one follow and one kind, any status.
        season: The asked season.
        episode: The asked episode.

    Returns:
        The governing row; ``None`` when none is open at those coordinates.
    """
    open_rows = [
        row
        for row in rows
        if row.id is not None and row.season == season and row.episode == episode and row.status in OPEN_WANTED_STATUSES
    ]
    return max(open_rows, key=lambda row: row.id or 0, default=None)


def _governing_each(rows: list[WantedItem]) -> list[WantedItem]:
    """Pick, for each coordinate of a follow's rows, the open row that speaks for it.

    Args:
        rows: Every row of one follow and one kind, any status.

    Returns:
        The latest open row of each ``(season, episode)``, in the order of those coordinates' first
        open row.
    """
    coordinates = dict.fromkeys((row.season, row.episode) for row in rows)
    governing = (_governing(rows, season, episode) for season, episode in coordinates)
    return [row for row in governing if row is not None]


class ReleaseReads:
    """Reads the ranked release candidates a concluded search stored for a wanted item."""

    def __init__(self, store: AcquireStore, *, owner: AccountId) -> None:
        """Bind the read to its store.

        Args:
            store: The acquire store (``follow``, ``requesters``, ``wanted`` and ``candidates``).
            owner: The account a follow with no requester row is the ask of (DESIGN § 2.4).
        """
        self._store = store
        self._follows = FollowRepository(store)
        self._owner = owner

    def read(
        self, actor: Actor, key: AcquisitionKey, season: int | None, episode: int | None
    ) -> tuple[WantedCandidate, ...]:
        """Read the candidates of one wanted item, the best rank first.

        Args:
            actor: The reader.
            key: The medium's key.
            season: The season asked; ``None`` for a film.
            episode: The episode asked; ``None`` for a season pack or a film.

        Returns:
            The ranked candidates, each with the season and episode it numbers. Empty when no
            follow holds the key, the follow was removed or is not the actor's to read, no row
            of the follow is open at those coordinates, or no search concluded for it.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``episode``, when an episode is asked with no season.
            FollowAmbiguous: Two follow rows hold the key's id (``409 follow.ambiguous`` at the service).
        """
        return tuple(offer.candidate for offer in self.offers(actor, key, season, episode))

    def offers(
        self, actor: Actor, key: AcquisitionKey | None, season: int | None, episode: int | None
    ) -> tuple[ReleaseOffer, ...]:
        """Read the candidates a reader is offered, each with the wanted row it belongs to.

        With a key, the one item the key and the coordinates name, as :meth:`read` answers it. With
        none, every item the reader may see: the latest open row of each coordinate of every
        standing follow it may read, what the quality profile counts against. A season or an
        episode asked then keeps the rows at those coordinates.

        Args:
            actor: The reader.
            key: The medium's key, or ``None`` for every item.
            season: The season asked; ``None`` for a film, or for no narrowing without a key.
            episode: The episode asked; ``None`` for a season pack or a film.

        Returns:
            The offers, the best rank first within a row; empty when nothing is offered.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``episode``, when an episode is asked with no season.
            FollowAmbiguous: Two follow rows hold the key's id (``409 follow.ambiguous`` at the service).
        """
        if key is None:
            return self._offers_of_every(actor, season, episode)
        kind = _kind_of(season, episode)
        follow = self._follows.get(key)
        if follow is None or follow.removed_at is not None or not follow.readable_by(actor, self._owner):
            return ()
        row = _governing(self._store.wanted.list_for_followed(follow.id, kind=kind), season, episode)
        return self._offers_of_row(row)

    def _offers_of_row(self, row: WantedItem | None) -> tuple[ReleaseOffer, ...]:
        """Read the stored set of one wanted row.

        Args:
            row: The row, or ``None`` when none governs.

        Returns:
            Its candidates as offers; empty for no row or no concluded search.
        """
        if row is None or row.id is None:
            return ()
        wanted_id = row.id
        return tuple(ReleaseOffer(wanted_id, candidate) for candidate in self._store.candidates.list_for(wanted_id))

    def _offers_of_every(self, actor: Actor, season: int | None, episode: int | None) -> tuple[ReleaseOffer, ...]:
        """Read the offers of every standing follow the actor may read.

        Args:
            actor: The reader.
            season: Keep the rows at this season, when given.
            episode: Keep the rows at this episode, when given.

        Returns:
            The offers, follow by follow in the order the store lists them.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``episode``, when an episode is asked with no season.
        """
        if season is None and episode is not None:
            _kind_of(season, episode)  # refuses it
        offers: list[ReleaseOffer] = []
        for stored in self._store.follow.list_all():
            if stored.id is None or stored.removed_at is not None:
                continue
            follow = self._follows.get_by_id(FollowId(stored.id))
            if follow is None or follow.removed_at is not None or not follow.readable_by(actor, self._owner):
                continue
            for kind in get_args(WantedKind):
                rows = self._store.wanted.list_for_followed(stored.id, kind=kind)
                for row in _governing_each(rows):
                    if (season is None or row.season == season) and (episode is None or row.episode == episode):
                        offers.extend(self._offers_of_row(row))
        return tuple(offers)
