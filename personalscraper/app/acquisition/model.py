"""The acquisition model (K3 DESIGN §§ 2.2–2.4): the key a medium is asked by, the follow and its requesters.

A follow is ONE subject row (``followed_series``) shared by every account that asked for it, each
with its own quality floor and pause. The rules over them live here, as pure methods of the frozen
:class:`Follow`: a second ask joins, the last requester leaving removes the follow, a reassigned
requester starts with no setting (O-10 A), and what is in force is read from the requesters whose
role holds the right (round 10 Q6, the maquette's ``settingsOf``). The engine never learns of
rights: the caller hands :meth:`Follow.in_force` a :data:`RightCheck`.

The typed errors are the model's; the follow service maps them to refusal codes (§ 2.13).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import IntEnum, StrEnum
from typing import Final, NewType

from personalscraper.acquire.domain import FollowKind
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.rights import Right
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.library.identity import Provider, parse_media_ref, ref_key
from personalscraper.core.identity import MediaRef

__all__ = [
    "AcquisitionKey",
    "Follow",
    "FollowId",
    "FollowRemoved",
    "FollowShared",
    "InForce",
    "NotARequester",
    "QualityFloor",
    "Requester",
    "RightCheck",
    "Scope",
    "Via",
]

#: A follow's internal id: the ``followed_series`` rowid, never on the wire.
FollowId = NewType("FollowId", int)

#: Whether an account's role holds a right, given by the follow service from the roster.
RightCheck = Callable[[AccountId, Right], bool]

#: The separator of the wire key ``<provider>:<providerId>`` (O-1 A).
_KEY_SEPARATOR: Final = ":"

#: The field a malformed wire key is refused on.
_KEY_FIELD: Final = "followedId"


class QualityFloor(IntEnum):
    """A requester's quality floor, as a vertical resolution (wire ``"720p"``, ``"1080p"``, ``"2160p"``)."""

    P720 = 720
    P1080 = 1080
    P2160 = 2160


class Via(StrEnum):
    """How an account asked for a follow."""

    FOLLOW = "follow"
    REQUEST = "request"


class Scope(StrEnum):
    """Why a subject row exists: a standing follow, or a one-off request (O-2 A)."""

    FOLLOW = "follow"
    REQUEST = "request"


class NotARequester(Exception):
    """An own-scoped act names an account that is not among the follow's requesters."""


class FollowRemoved(Exception):
    """The act needs a standing follow, and its last requester left it."""


class FollowShared(Exception):
    """The generic pause was asked on a follow other accounts also asked for."""


@dataclass(frozen=True)
class AcquisitionKey:
    """The key a medium is asked by: a provider and the id it knows the medium by (Q15).

    Attributes:
        provider: TVDB, TMDB or IMDb.
        provider_id: The id at that provider, as text.
    """

    provider: Provider
    provider_id: str

    @classmethod
    def parse(cls, wire: str) -> AcquisitionKey:
        """Parse a wire key ``"<provider>:<providerId>"``.

        Args:
            wire: The key as the wire carries it, ``tvdb:81189`` or ``tmdb:603``.

        Returns:
            The key.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``followedId``, when the key has no
                separator, an unknown provider or an id that provider cannot hold.
        """
        provider, separator, provider_id = wire.partition(_KEY_SEPARATOR)
        if separator:
            try:
                return cls.of(parse_media_ref(provider, provider_id), None)
            except AppBadRequest:
                pass
        raise AppBadRequest(
            "Malformed acquisition key.", code=RefusalCode.REQUEST_INVALID, params={"fields": [_KEY_FIELD]}
        )

    @classmethod
    def of(cls, ref: MediaRef, kind: FollowKind | None) -> AcquisitionKey:
        """Name a medium by the id DESIGN § 2.2's rule reads first.

        A show is named as K2's ``ref_key`` names it (TVDB, then TMDB, then IMDb); a film
        is named by its TMDB id when it holds one, else as ``ref_key`` names it.

        Args:
            ref: The medium's provider ids, at least one set.
            kind: ``"show"`` or ``"movie"``; ``None`` for a ref holding one id, which names
                itself whatever the kind.

        Returns:
            The key.
        """
        if kind == "movie" and ref.tmdb_id is not None:
            return cls(Provider.TMDB, str(ref.tmdb_id))
        provider, provider_id = ref_key(ref)
        return cls(provider, provider_id)

    @property
    def wire(self) -> str:
        """The key as the wire carries it.

        Returns:
            ``"<provider>:<providerId>"``.
        """
        return f"{self.provider.value}{_KEY_SEPARATOR}{self.provider_id}"

    def ref(self) -> MediaRef:
        """The reference holding this key's one id.

        Returns:
            A :class:`MediaRef` with only the key's provider id set.
        """
        return parse_media_ref(self.provider.value, self.provider_id)


@dataclass(frozen=True)
class Requester:
    """One account's ask for a follow, and its own settings.

    Attributes:
        account_id: The asking account.
        via: How it asked.
        floor: Its own quality floor, ``None`` when none is set.
        paused: Whether it paused its own ask.
        since: Epoch seconds of its first ask.
    """

    account_id: AccountId
    via: Via
    floor: QualityFloor | None
    paused: bool
    since: int


@dataclass(frozen=True)
class InForce:
    """The settings in force on a follow, from the requesters whose role holds the right.

    Attributes:
        floor: The highest floor among the requesters holding ``acquisition.quality.own``.
        paused: Every requester holding ``acquisition.pause.own`` paused, and at least one did.
    """

    floor: QualityFloor | None
    paused: bool


class _Unset:
    """The type of :data:`_UNSET`: a setting :meth:`Follow.with_setting` leaves as it is."""


_UNSET: Final = _Unset()


@dataclass(frozen=True)
class Follow:
    """The aggregate: one subject row and the accounts that asked for it.

    Attributes:
        id: The subject row's id.
        key: The medium's key, named by :meth:`AcquisitionKey.of`.
        scope: A standing follow or a one-off request.
        requesters: Who asked, in the order they first asked; empty for a follow written
            before the model (read as the owner's, :meth:`requesters_or_owner`).
        removed_at: Epoch seconds the last requester left, ``None`` while the follow stands.
        legacy: The settings a follow with no requester row holds on its row (v0's floor and
            pause), the owner's own; ``None`` once requesters are stored.
    """

    id: FollowId
    key: AcquisitionKey
    scope: Scope
    requesters: tuple[Requester, ...]
    removed_at: int | None
    legacy: InForce | None = None

    @classmethod
    def first_ask(cls, follow_id: FollowId, key: AcquisitionKey, scope: Scope, account: AccountId, now: int) -> Follow:
        """The follow of a subject row just written for one account's ask: that account its only requester.

        A fresh row has no v0 settings to carry, so it is never read as the owner's implied ask.

        Args:
            follow_id: The new subject row.
            key: The medium's key.
            scope: A standing follow, or a one-off request.
            account: The asking account.
            now: Epoch seconds of the ask.

        Returns:
            The follow, standing, the account asking as the scope says.
        """
        asker = Requester(account_id=account, via=Via(scope.value), floor=None, paused=False, since=now)
        return cls(id=follow_id, key=key, scope=scope, requesters=(asker,), removed_at=None)

    def _members(self, owner: AccountId) -> Follow:
        """The follow with the owner's implied ask made explicit, when it stands with no requester.

        An act on a follow written before the model starts from the owner's ask, carrying the
        row's v0 settings, so neither the owner nor what it set is lost by the act.

        Args:
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow, its requesters :meth:`requesters_or_owner`'s when it had none and stands.
        """
        if self.requesters or self.removed_at is not None:
            return self
        return replace(self, requesters=self.requesters_or_owner(owner), legacy=None)

    def with_owner_ask(self, owner: AccountId) -> Follow:
        """The follow with the owner's implied ask written as a requester, when it stands with none.

        A write on a follow made before the model materialises the owner's ask, as every own-scoped
        act does: once saved, the owner is a requester the supervisor's target check reads.

        Args:
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow, the owner its requester with the row's v0 settings; unchanged when it has
            requesters or is removed.
        """
        return self._members(owner)

    def _find(self, account: AccountId) -> Requester | None:
        """The requester of one account.

        Args:
            account: The account.

        Returns:
            Its requester, or ``None`` when it did not ask.
        """
        return next((one for one in self.requesters if one.account_id == account), None)

    def _standing_requester(self, account: AccountId) -> Requester:
        """The requester an own-scoped act names, on a standing follow.

        Args:
            account: The account acting.

        Returns:
            Its requester.

        Raises:
            FollowRemoved: The follow's last requester left it.
            NotARequester: The account did not ask for it.
        """
        if self.removed_at is not None:
            raise FollowRemoved(f"follow {self.id} is removed")
        found = self._find(account)
        if found is None:
            raise NotARequester(f"{account} did not ask for follow {self.id}")
        return found

    def requesters_or_owner(self, owner: AccountId) -> tuple[Requester, ...]:
        """The follow's requesters, or the owner's ask for a follow with none (ruling 9).

        Args:
            owner: The account unattended acts are attributed to.

        Returns:
            The requesters; for a follow with none, the owner alone, with the row's v0 settings
            (none without them), asking as the follow's scope does, ``since`` 0 (unknown).
        """
        if self.requesters:
            return self.requesters
        legacy = self.legacy or InForce(floor=None, paused=False)
        return (
            Requester(account_id=owner, via=Via(self.scope.value), floor=legacy.floor, paused=legacy.paused, since=0),
        )

    def readable_by(self, actor: Actor, owner: AccountId) -> bool:
        """Whether an actor reads this follow: ``acquisition.see.others``, else membership.

        ``acquisition.pilot.any`` is the acts' scope, not the reads': its holder without
        ``see.others`` reads its own follows only.

        Args:
            actor: The reader.
            owner: The account a requester-less follow is read as.

        Returns:
            True when the actor holds ``see.others`` or is among the requesters.
        """
        if actor.holds(Right.ACQUISITION_SEE_OTHERS):
            return True
        return any(one.account_id == actor.account_id for one in self.requesters_or_owner(owner))

    def with_requester(self, account: AccountId, via: Via, now: int, *, owner: AccountId) -> Follow:
        """An account asks for the follow: it joins, or nothing changes if it already asked.

        A removed follow asked for again comes back, the asker its only requester (§ 2.5):
        whoever asked before it was removed (a one-off request ended by its season keeps its
        rows) no longer asks. A standing follow with no requester keeps its owner, with its v0
        settings, beside the asker.

        Args:
            account: The asking account.
            via: How it asks.
            now: Epoch seconds of the ask.
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow with the account among its requesters.
        """
        if self.removed_at is not None:
            revived = Requester(account_id=account, via=via, floor=None, paused=False, since=now)
            return replace(self, requesters=(revived,), removed_at=None, legacy=None)
        members = self._members(owner)
        if members._find(account) is not None:
            return members
        joined = Requester(account_id=account, via=via, floor=None, paused=False, since=now)
        return replace(members, requesters=(*members.requesters, joined), removed_at=None, legacy=None)

    def followed_by(self, account: AccountId, now: int, *, owner: AccountId) -> Follow:
        """An account follows the medium: it joins as a follower, and the subject becomes a standing follow.

        « Suivre » on a one-off request's card (§ 2.7) is this ask on the same subject: the
        request's season carries on, the row is a follow from now. A requester who asked by
        request keeps its own ask as it was.

        Args:
            account: The following account.
            now: Epoch seconds of the ask.
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow, of scope :attr:`Scope.FOLLOW`, with the account among its requesters.
        """
        return replace(self.with_requester(account, Via.FOLLOW, now, owner=owner), scope=Scope.FOLLOW)

    def requested_by(self, account: AccountId, now: int, *, owner: AccountId) -> Follow:
        """An account asks a one-off request of the medium (§ 2.7): it joins the standing subject.

        A standing follow stays a follow (its season is asked of it); a removed subject comes
        back as a request, the asker its only requester.

        Args:
            account: The asking account.
            now: Epoch seconds of the ask.
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow with the account among its requesters, of scope :attr:`Scope.REQUEST`
            when it was removed.
        """
        scope = Scope.REQUEST if self.removed_at is not None else self.scope
        return replace(self.with_requester(account, Via.REQUEST, now, owner=owner), scope=scope)

    def paused_for_all(self, paused: bool, *, owner: AccountId) -> Follow:
        """Every requester's pause set at once: the generic pause of whoever pilots every acquisition (§ 2.3).

        Args:
            paused: The pause asked.
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow, each requester's ``paused`` the one asked.

        Raises:
            FollowRemoved: The follow is removed.
        """
        if self.removed_at is not None:
            raise FollowRemoved(f"follow {self.id} is removed")
        members = self._members(owner)
        return replace(members, requesters=tuple(replace(one, paused=paused) for one in members.requesters))

    def shared_beyond(self, account: AccountId, *, owner: AccountId) -> bool:
        """Whether accounts other than *account* asked for the follow.

        Args:
            account: The account asking.
            owner: The account a requester-less follow is the ask of.

        Returns:
            True when a requester other than the account exists.
        """
        return any(one.account_id != account for one in self.requesters_or_owner(owner))

    def without_requester(self, account: AccountId, now: int, *, owner: AccountId) -> Follow:
        """An account leaves the follow; the last one leaving removes it.

        Args:
            account: The leaving account.
            now: Epoch seconds of the removal.
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow without the account, ``removed_at`` set when nobody is left.

        Raises:
            FollowRemoved: The follow is already removed.
            NotARequester: The account did not ask for it.
        """
        members = self._members(owner)
        members._standing_requester(account)
        left = tuple(one for one in members.requesters if one.account_id != account)
        return replace(members, requesters=left, removed_at=None if left else now)

    def reassigned(self, source: AccountId, target: AccountId, now: int, *, owner: AccountId) -> Follow:
        """Move one requester's ask onto another account (§ 2.6).

        The settings do not travel (O-10 A): the target asks from now, with none. A target
        already asking keeps its own ask, and the source is simply removed.

        Args:
            source: The requester moved.
            target: The account taking its place.
            now: Epoch seconds of the move.
            owner: The account a requester-less follow is the ask of.

        Returns:
            The follow with the target in the source's stead.

        Raises:
            FollowRemoved: The follow is removed.
            NotARequester: The source did not ask for it.
        """
        members = self._members(owner)
        moved = members._standing_requester(source)
        rest = tuple(one for one in members.requesters if one.account_id != source)
        if any(one.account_id == target for one in rest):
            return replace(members, requesters=rest)
        arrival = Requester(account_id=target, via=moved.via, floor=None, paused=False, since=now)
        return replace(members, requesters=(*rest, arrival))

    def with_setting(
        self,
        account: AccountId,
        *,
        owner: AccountId,
        floor: QualityFloor | None | _Unset = _UNSET,
        paused: bool | _Unset = _UNSET,
    ) -> Follow:
        """A requester writes its own floor, its own pause, or both.

        Args:
            account: The requester.
            owner: The account a requester-less follow is the ask of.
            floor: Its new floor (``None`` clears it); left as it is when not given.
            paused: Its new pause; left as it is when not given.

        Returns:
            The follow with the requester's settings changed.

        Raises:
            FollowRemoved: The follow is removed.
            NotARequester: The account did not ask for it.
        """
        members = self._members(owner)
        own = members._standing_requester(account)
        changed = replace(
            own,
            floor=own.floor if isinstance(floor, _Unset) else floor,
            paused=own.paused if isinstance(paused, _Unset) else paused,
        )
        return replace(members, requesters=tuple(changed if one is own else one for one in members.requesters))

    def in_force(self, holds: RightCheck) -> InForce:
        """The settings in force: only a requester whose role holds the right counts.

        Args:
            holds: Whether an account's role holds a right.

        Returns:
            The highest floor among the holders of ``acquisition.quality.own``; paused when
            every holder of ``acquisition.pause.own`` paused and at least one holds it. A
            standing follow with no requester keeps its row's v0 settings in force.
        """
        if not self.requesters and self.removed_at is None and self.legacy is not None:
            return self.legacy
        floors = [
            one.floor
            for one in self.requesters
            if one.floor is not None and holds(one.account_id, Right.ACQUISITION_QUALITY_OWN)
        ]
        pausers = [one for one in self.requesters if holds(one.account_id, Right.ACQUISITION_PAUSE_OWN)]
        return InForce(
            floor=max(floors) if floors else None,
            paused=bool(pausers) and all(one.paused for one in pausers),
        )
