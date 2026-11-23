"""``FollowRepository``: the acquisition model's follows, read from and written to the acquire store.

A :class:`~personalscraper.app.acquisition.model.Follow` is loaded by its key through the engine's
lookup by any provider id (K3 P1); two rows holding the key are a duplicate the repository refuses to
choose between (:class:`FollowAmbiguous`, ``409 follow.ambiguous`` at the service). Saving writes the
requesters and the PROJECTION of what they put in force (DESIGN § 2.4) on the ``followed_series`` row
in one ``BEGIN IMMEDIATE``: ``min_resolution`` ← the floor in force, ``active`` ← not paused and not
removed — the columns the engine already reads. The save answers whether ``active`` went from false
to true, the transition that asks a prime (§ 2.3), so no operation tests it on its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.acquire.domain import FollowedSeries, FollowRequester
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.acquisition.model import (
    AcquisitionKey,
    Follow,
    FollowId,
    InForce,
    QualityFloor,
    Requester,
    Scope,
    Via,
)

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore

__all__ = ["FollowAmbiguous", "FollowRepository"]


class FollowAmbiguous(Exception):
    """Two or more follow rows hold the key's id: one medium written twice (O-13 settles them).

    Attributes:
        key: The key looked up.
        follow_ids: The rows holding it.
    """

    def __init__(self, key: AcquisitionKey, follow_ids: list[FollowId]) -> None:
        """Name the key and the rows holding it.

        Args:
            key: The key looked up.
            follow_ids: The rows holding it.
        """
        super().__init__(f"{key.wire} names follows {follow_ids}")
        self.key = key
        self.follow_ids = follow_ids


def _requester(row: FollowRequester) -> Requester:
    """Map a stored requester onto the model's.

    Args:
        row: The ``acquisition_requester`` row.

    Returns:
        The model's requester.
    """
    return Requester(
        account_id=AccountId(row.account_id),
        via=Via(row.via),
        floor=QualityFloor(row.floor) if row.floor is not None else None,
        paused=row.paused,
        since=row.since,
    )


def _stored(follow_id: FollowId, requester: Requester) -> FollowRequester:
    """Map the model's requester onto the stored one.

    Args:
        follow_id: The follow it asks for.
        requester: The model's requester.

    Returns:
        The ``acquisition_requester`` row.
    """
    return FollowRequester(
        followed_id=follow_id,
        account_id=requester.account_id,
        via=requester.via.value,
        floor=int(requester.floor) if requester.floor is not None else None,
        paused=requester.paused,
        since=requester.since,
    )


class FollowRepository:
    """Loads and saves :class:`Follow` aggregates on the acquire store."""

    def __init__(self, store: AcquireStore) -> None:
        """Bind the repository to its store.

        Args:
            store: The acquire store (``follow`` and ``requesters`` sub-stores).
        """
        self._store = store

    def get(self, key: AcquisitionKey) -> Follow | None:
        """Load the follow of the medium *key* names, removed or not.

        Args:
            key: The medium's key.

        Returns:
            The follow, named by its row's own ids; ``None`` when no row holds the key.

        Raises:
            FollowAmbiguous: Two or more rows hold the key's id.
        """
        rows = self._store.follow.find_all_by_ref(key.ref())
        if not rows:
            return None
        if len(rows) > 1:
            raise FollowAmbiguous(key, [FollowId(row.id) for row in rows if row.id is not None])
        return self._aggregate(rows[0])

    def _aggregate(self, row: FollowedSeries) -> Follow:
        """Build the aggregate of one subject row and its requesters.

        Args:
            row: The ``followed_series`` row, its id set.

        Returns:
            The follow.

        Raises:
            LookupError: The row carries no rowid (never, for a row the store read).
        """
        if row.id is None:
            raise LookupError("a stored follow row carries its rowid")
        follow_id = FollowId(row.id)
        return Follow(
            id=follow_id,
            key=AcquisitionKey.of(row.media_ref, row.kind),
            scope=Scope(row.scope),
            requesters=tuple(_requester(one) for one in self._store.requesters.list_for(follow_id)),
            removed_at=row.removed_at,
        )

    def save(self, follow: Follow, in_force: InForce) -> bool:
        """Write the follow's requesters and their projection, in one transaction.

        Args:
            follow: The follow as the model left it.
            in_force: What its requesters put in force (``Follow.in_force``).

        Returns:
            True when the follow starts taking work: ``active`` false before, true after.

        Raises:
            LookupError: The follow's row no longer exists (nothing is written).
        """
        active = not in_force.paused and follow.removed_at is None
        was_active = self._store.requesters.save_follow(
            follow.id,
            [_stored(follow.id, one) for one in follow.requesters],
            removed_at=follow.removed_at,
            min_resolution=int(in_force.floor) if in_force.floor is not None else None,
            active=active,
        )
        return active and not was_active
