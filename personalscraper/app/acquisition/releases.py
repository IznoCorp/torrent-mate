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

from typing import TYPE_CHECKING

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES
from personalscraper.app.acquisition.follow_repository import FollowRepository
from personalscraper.app.errors import AppBadRequest, RefusalCode

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import WantedCandidate, WantedItem, WantedKind
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.accounts.ids import AccountId
    from personalscraper.app.acquisition.model import AcquisitionKey

__all__ = ["ReleaseReads"]

#: The field an episode asked with no season is refused on.
_EPISODE_FIELD = "episode"


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
        kind = _kind_of(season, episode)
        follow = self._follows.get(key)
        if follow is None or follow.removed_at is not None or not follow.readable_by(actor, self._owner):
            return ()
        row = _governing(self._store.wanted.list_for_followed(follow.id, kind=kind), season, episode)
        if row is None or row.id is None:
            return ()
        return tuple(self._store.candidates.list_for(row.id))
