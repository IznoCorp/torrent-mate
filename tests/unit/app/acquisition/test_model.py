"""The acquisition model's rules (K3 P3, DESIGN §§ 2.2–2.4): the key, the follow and its requesters.

Pure value tests: no store, no service. The ``in_force`` cases are the maquette's ``settingsOf``
(``webui/design/src/mocks/handlers/requesters.ts``): only a requester whose role holds the right
counts, the highest floor wins, and a follow is paused once every holder of the pause right asked.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.model import (
    AcquisitionKey,
    Follow,
    FollowId,
    FollowRemoved,
    InForce,
    NotARequester,
    QualityFloor,
    Requester,
    Scope,
    Via,
)
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.library.identity import Provider
from personalscraper.core.identity import MediaRef

ALICE = AccountId("account-alice")
BOB = AccountId("account-bob")
CAROL = AccountId("account-carol")
OWNER = AccountId("account-owner")
KEY = AcquisitionKey(Provider.TVDB, "81189")


def _requester(
    account: AccountId,
    *,
    floor: QualityFloor | None = None,
    paused: bool = False,
    since: int = 100,
    via: Via = Via.FOLLOW,
) -> Requester:
    """Build one requester, ``via follow``, no floor, not paused, unless told otherwise.

    Args:
        account: The asking account.
        floor: Its own quality floor.
        paused: Its own pause.
        since: When it first asked.
        via: How it asked.

    Returns:
        The requester.
    """
    return Requester(account_id=account, via=via, floor=floor, paused=paused, since=since)


def _follow(*requesters: Requester, removed_at: int | None = None) -> Follow:
    """Build a standing follow of :data:`KEY` with the given requesters.

    Args:
        *requesters: Its requesters, in order.
        removed_at: When its last requester left, ``None`` while it stands.

    Returns:
        The follow, id 7.
    """
    return Follow(id=FollowId(7), key=KEY, scope=Scope.FOLLOW, requesters=requesters, removed_at=removed_at)


def _holds(table: dict[AccountId, set[Right]]) -> Callable[[AccountId, Right], bool]:
    """A ``RightCheck`` reading a fixed table of the rights each account's role holds.

    Args:
        table: The rights held, per account; an account absent holds none.

    Returns:
        The check.
    """
    return lambda account, right: right in table.get(account, set())


def _actor(account: AccountId, *rights: Right) -> Actor:
    """An ordinary actor whose role carries exactly *rights*, under no ceiling.

    Args:
        account: The actor's account.
        *rights: The rights its role carries.

    Returns:
        The actor.
    """
    return Actor(
        account_id=account,
        name="Someone",
        role_id=RoleId("role-member"),
        role_kind=RoleKind.ORDINARY,
        role_rights=frozenset(rights),
        ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
    )


def _ids(follow: Follow) -> list[AccountId]:
    """The account ids of a follow's requesters, in order.

    Args:
        follow: The follow.

    Returns:
        The ids.
    """
    return [one.account_id for one in follow.requesters]


class TestAcquisitionKey:
    """The wire key ``<provider>:<providerId>`` (O-1 A) and the naming rule of § 2.2."""

    @pytest.mark.parametrize("wire", ["tvdb:81189", "tmdb:603", "imdb:tt0133093"])
    def test_round_trip(self, wire: str) -> None:
        """A parsed key prints back as the text it was parsed from."""
        assert AcquisitionKey.parse(wire).wire == wire

    def test_parse_names_the_provider_and_its_id(self) -> None:
        """``tmdb:603`` is TMDB's 603, and its ref holds that one id."""
        key = AcquisitionKey.parse("tmdb:603")
        assert (key.provider, key.provider_id) == (Provider.TMDB, "603")
        assert key.ref() == MediaRef(tmdb_id=603)

    @pytest.mark.parametrize(
        "wire", ["", "81189", "tvdb", "tvdb:", ":81189", "plex:1", "tvdb:abc", "tvdb:0", "imdb:603"]
    )
    def test_refusals(self, wire: str) -> None:
        """A malformed key is refused ``request.invalid``."""
        with pytest.raises(AppBadRequest) as refusal:
            AcquisitionKey.parse(wire)
        assert refusal.value.code is RefusalCode.REQUEST_INVALID

    def test_a_show_holding_tvdb_and_tmdb_is_named_tvdb(self) -> None:
        """A show is named TVDB first."""
        assert AcquisitionKey.of(MediaRef(tvdb_id=81189, tmdb_id=1396), "show").wire == "tvdb:81189"

    def test_a_film_holding_tvdb_and_tmdb_is_named_tmdb(self) -> None:
        """A film is named TMDB first, though ``ref_key`` reads TVDB first."""
        assert AcquisitionKey.of(MediaRef(tvdb_id=111, tmdb_id=603), "movie").wire == "tmdb:603"

    def test_a_film_holding_tvdb_only_is_named_tvdb(self) -> None:
        """A film with no TMDB id falls back to ``ref_key``: TVDB."""
        assert AcquisitionKey.of(MediaRef(tvdb_id=111), "movie").wire == "tvdb:111"

    def test_a_film_holding_imdb_only_is_named_imdb(self) -> None:
        """A film with neither numbered id is named by its IMDb id."""
        assert AcquisitionKey.of(MediaRef(imdb_id="tt0133093"), "movie").wire == "imdb:tt0133093"


class TestRequesters:
    """Joining, leaving and reassigning (§ 2.3, § 2.5, § 2.6)."""

    def test_a_second_ask_joins_with_one_requester(self) -> None:
        """An account asking again stays one requester, its first ask's ``since`` kept."""
        follow = _follow(_requester(ALICE, since=100))
        again = follow.with_requester(ALICE, Via.FOLLOW, now=500)
        assert again.requesters == (_requester(ALICE, since=100),)

    def test_another_account_joins(self) -> None:
        """A second account is added after the first, asking now, with no setting."""
        follow = _follow(_requester(ALICE)).with_requester(BOB, Via.REQUEST, now=500)
        assert follow.requesters[1] == _requester(BOB, since=500, via=Via.REQUEST)

    def test_an_ask_on_a_removed_follow_revives_it(self) -> None:
        """Asking for a removed follow brings it back with the asker as requester (§ 2.5)."""
        follow = _follow(removed_at=300).with_requester(ALICE, Via.FOLLOW, now=500)
        assert follow.removed_at is None
        assert _ids(follow) == [ALICE]

    def test_leaving_keeps_the_follow_for_the_others(self) -> None:
        """One requester leaving leaves the follow standing for the rest."""
        follow = _follow(_requester(ALICE), _requester(BOB)).without_requester(ALICE, now=500)
        assert _ids(follow) == [BOB]
        assert follow.removed_at is None

    def test_the_last_leaving_removes_the_follow(self) -> None:
        """The last requester leaving sets ``removed_at``."""
        follow = _follow(_requester(ALICE)).without_requester(ALICE, now=500)
        assert follow.requesters == ()
        assert follow.removed_at == 500

    def test_leaving_a_follow_one_never_asked_for_raises(self) -> None:
        """A non-requester cannot leave."""
        with pytest.raises(NotARequester):
            _follow(_requester(ALICE)).without_requester(BOB, now=500)

    def test_reassign_moves_the_requester_without_its_settings(self) -> None:
        """The target takes the source's place, starting with no setting (O-10 A)."""
        follow = _follow(_requester(ALICE, floor=QualityFloor.P1080, paused=True), _requester(BOB))
        moved = follow.reassigned(ALICE, CAROL, now=500)
        assert _ids(moved) == [BOB, CAROL]
        assert moved.requesters[1] == _requester(CAROL, since=500)

    def test_reassign_onto_an_existing_requester_merges(self) -> None:
        """A target already asking keeps its own ask; the source is simply removed."""
        follow = _follow(_requester(ALICE), _requester(BOB, floor=QualityFloor.P720, since=200))
        moved = follow.reassigned(ALICE, BOB, now=500)
        assert moved.requesters == (_requester(BOB, floor=QualityFloor.P720, since=200),)

    def test_reassign_from_a_non_requester_raises(self) -> None:
        """Only a requester can be moved."""
        with pytest.raises(NotARequester):
            _follow(_requester(ALICE)).reassigned(BOB, CAROL, now=500)

    def test_reassign_on_a_removed_follow_raises(self) -> None:
        """A removed follow has nobody to move."""
        with pytest.raises(FollowRemoved):
            _follow(removed_at=300).reassigned(ALICE, BOB, now=500)


class TestSettings:
    """A requester's own floor and pause (round 10 Q6)."""

    def test_a_requester_sets_its_own_floor(self) -> None:
        """The floor is written on the caller's requester only, the pause untouched."""
        follow = _follow(_requester(ALICE), _requester(BOB, paused=True))
        changed = follow.with_setting(BOB, floor=QualityFloor.P2160)
        assert changed.requesters == (_requester(ALICE), _requester(BOB, floor=QualityFloor.P2160, paused=True))

    def test_a_requester_sets_its_own_pause_keeping_its_floor(self) -> None:
        """The pause is written alone when the floor is not given."""
        follow = _follow(_requester(ALICE, floor=QualityFloor.P720))
        changed = follow.with_setting(ALICE, paused=True)
        assert changed.requesters == (_requester(ALICE, floor=QualityFloor.P720, paused=True),)

    def test_a_floor_can_be_cleared(self) -> None:
        """``floor=None`` clears the requester's floor."""
        follow = _follow(_requester(ALICE, floor=QualityFloor.P720)).with_setting(ALICE, floor=None)
        assert follow.requesters[0].floor is None

    def test_a_setting_by_a_non_requester_raises(self) -> None:
        """Only a requester sets its own settings."""
        with pytest.raises(NotARequester):
            _follow(_requester(ALICE)).with_setting(BOB, paused=True)

    def test_a_setting_on_a_removed_follow_raises(self) -> None:
        """A removed follow takes no setting."""
        with pytest.raises(FollowRemoved):
            _follow(removed_at=300).with_setting(ALICE, paused=True)


class TestInForce:
    """The settings in force: the maquette's ``settingsOf`` cases."""

    def test_the_highest_floor_among_holders_wins(self) -> None:
        """Two holders' floors: the higher is in force."""
        follow = _follow(_requester(ALICE, floor=QualityFloor.P720), _requester(BOB, floor=QualityFloor.P1080))
        holds = _holds({ALICE: {Right.ACQUISITION_QUALITY_OWN}, BOB: {Right.ACQUISITION_QUALITY_OWN}})
        assert follow.in_force(holds).floor is QualityFloor.P1080

    def test_a_non_holders_floor_is_ignored(self) -> None:
        """A floor set by an account whose role lost the right enters nothing."""
        follow = _follow(_requester(ALICE, floor=QualityFloor.P720), _requester(BOB, floor=QualityFloor.P2160))
        holds = _holds({ALICE: {Right.ACQUISITION_QUALITY_OWN}})
        assert follow.in_force(holds).floor is QualityFloor.P720

    def test_no_holder_with_a_floor_means_none(self) -> None:
        """No holder set a floor: none is in force."""
        follow = _follow(_requester(ALICE), _requester(BOB, floor=QualityFloor.P2160))
        holds = _holds({ALICE: {Right.ACQUISITION_QUALITY_OWN}})
        assert follow.in_force(holds).floor is None

    def test_paused_when_every_holder_asked(self) -> None:
        """Every holder of the pause right paused: the follow is paused."""
        follow = _follow(_requester(ALICE, paused=True), _requester(BOB, paused=True))
        holds = _holds({ALICE: {Right.ACQUISITION_PAUSE_OWN}, BOB: {Right.ACQUISITION_PAUSE_OWN}})
        assert follow.in_force(holds).paused is True

    def test_not_paused_while_one_holder_did_not_ask(self) -> None:
        """One holder still wants it: the follow is not paused."""
        follow = _follow(_requester(ALICE, paused=True), _requester(BOB))
        holds = _holds({ALICE: {Right.ACQUISITION_PAUSE_OWN}, BOB: {Right.ACQUISITION_PAUSE_OWN}})
        assert follow.in_force(holds).paused is False

    def test_a_non_holder_neither_pauses_nor_holds_back_the_pause(self) -> None:
        """A non-holder's pause counts for nothing, and its not pausing blocks nothing."""
        holds = _holds({ALICE: {Right.ACQUISITION_PAUSE_OWN}})
        assert _follow(_requester(ALICE, paused=True), _requester(BOB)).in_force(holds).paused is True
        assert _follow(_requester(ALICE), _requester(BOB, paused=True)).in_force(holds).paused is False

    def test_not_paused_when_no_holder_asked_anything(self) -> None:
        """With no holder of the pause right at all, the follow is not paused, whatever was set."""
        follow = _follow(_requester(ALICE, paused=True))
        assert follow.in_force(_holds({})).paused is False

    def test_no_requester_is_nothing_in_force(self) -> None:
        """A follow with no requester has no floor and no pause in force."""
        assert _follow().in_force(_holds({})) == InForce(floor=None, paused=False)


class TestReads:
    """Who a follow belongs to, and who may read it (§ 2.3)."""

    def test_requesters_or_owner_on_an_empty_list(self) -> None:
        """A follow with no requester row reads as the owner's (ruling 9)."""
        (only,) = _follow().requesters_or_owner(OWNER)
        assert (only.account_id, only.via, only.floor, only.paused) == (OWNER, Via.FOLLOW, None, False)

    def test_requesters_or_owner_with_requesters(self) -> None:
        """A follow with requesters reads as theirs, the owner not added."""
        follow = _follow(_requester(ALICE))
        assert follow.requesters_or_owner(OWNER) == follow.requesters

    def test_see_others_reads_every_follow(self) -> None:
        """``acquisition.see.others`` reads a follow it did not ask for."""
        follow = _follow(_requester(ALICE))
        assert follow.readable_by(_actor(BOB, Right.ACQUISITION_SEE_OTHERS), OWNER) is True

    def test_a_requester_reads_its_own(self) -> None:
        """A requester with no right but membership reads its follow."""
        assert _follow(_requester(ALICE)).readable_by(_actor(ALICE), OWNER) is True

    def test_a_stranger_does_not_read_it(self) -> None:
        """An account neither asking nor holding ``see.others`` does not read it."""
        assert _follow(_requester(ALICE)).readable_by(_actor(BOB), OWNER) is False

    def test_pilot_any_without_see_others_reads_its_own_only(self) -> None:
        """``acquisition.pilot.any`` is the acts' scope, not the reads'."""
        pilot = _actor(BOB, Right.ACQUISITION_PILOT_ANY)
        assert _follow(_requester(ALICE)).readable_by(pilot, OWNER) is False
        assert _follow(_requester(BOB)).readable_by(pilot, OWNER) is True

    def test_the_owner_reads_a_follow_with_no_requester(self) -> None:
        """A requester-less follow is the owner's to read, and nobody else's without ``see.others``."""
        assert _follow().readable_by(_actor(OWNER), OWNER) is True
        assert _follow().readable_by(_actor(ALICE), OWNER) is False
