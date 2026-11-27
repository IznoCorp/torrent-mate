"""``FollowService``: the follows' use cases on a real acquire store, ``app.db`` and supervisor queue (K3 P7).

A follow is one row shared by its requesters: a second ask joins, the last leaving removes it softly,
``restore`` puts it back as it was. What the requesters put in force is projected on the row the engine
reads (``min_resolution``, ``active``). Reads are filtered by membership unless the reader holds
``acquisition.see.others`` — ``acquisition.pilot.any`` is the acts' scope, not the reads'. A write that
starts a follow taking work asks the supervisor for one ``prime`` of it; the ask never breaks the write.
"""

from __future__ import annotations

import dataclasses
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.acquire._requester_store import _RequesterSubStore
from personalscraper.acquire.domain import FollowRequester
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.follow_repository import FollowRepository
from personalscraper.app.acquisition.follows import FollowService
from personalscraper.app.acquisition.model import AcquisitionKey, QualityFloor
from personalscraper.app.errors import AppForbidden, AppNotFound, AppRefusal, RefusalCode
from personalscraper.app.supervisor.model import RunTrigger
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from tests.conftest import LoggedEvents
from tests.unit.app.acquisition.follow_world import (
    ALICE,
    BOB,
    CAROL,
    DAVE,
    ERIN,
    FRANK,
    MEMBER,
    MEMBER_RIGHTS,
    NO_CEILING,
    NOW,
    OWNER,
    READ_ONLY,
    SYSTEM,
    TODAY,
    FollowWorld,
    actor,
)

SHOW = AcquisitionKey.parse("tvdb:81189")
FILM = AcquisitionKey.parse("tmdb:603")


@pytest.fixture
def world(tmp_path: Path) -> Iterator[FollowWorld]:
    """A world with an empty acquire store, the seeded roster and an empty queue.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The world.
    """
    built = FollowWorld(tmp_path)
    try:
        yield built
    finally:
        built.close()


def _create(world: FollowWorld, account: AccountId, key: AcquisitionKey = SHOW) -> int:
    """Follow a medium as an account and return the follow's row.

    Args:
        world: The world.
        account: Who follows.
        key: The medium.

    Returns:
        The row.
    """
    world.follows.create(actor(account), key, title="Breaking Bad", kind="show", year=2008)
    rows = world.store.follow.find_all_by_ref(key.ref(), kind="show")
    assert len(rows) == 1
    assert rows[0].id is not None
    return rows[0].id


def _code(refusal: pytest.ExceptionInfo[AppRefusal]) -> RefusalCode | None:
    """The code a refusal carries.

    Args:
        refusal: The caught refusal.

    Returns:
        Its code.
    """
    return refusal.value.code


class TestRequesters:
    """One follow, several requesters: join, leave, restore."""

    def test_two_accounts_creating_make_one_follow_with_two_requesters(self, world: FollowWorld) -> None:
        """A second ask joins: one row, both accounts among its requesters (DOIT-4)."""
        first = _create(world, ALICE)
        second = _create(world, BOB)

        assert first == second
        assert len(world.store.follow.list_all()) == 1
        assert set(world.requesters(first)) == {ALICE, BOB}

    def test_one_of_two_leaving_keeps_the_follow_for_the_other(self, world: FollowWorld) -> None:
        """The leaving account goes; the follow stands for the one left."""
        row = _create(world, ALICE)
        _create(world, BOB)

        world.follows.remove(actor(ALICE), SHOW)

        assert set(world.requesters(row)) == {BOB}
        assert world.row(row).removed_at is None
        assert world.row(row).active is True

    def test_the_last_leaving_removes_softly_and_restore_puts_it_back_as_it_was(self, world: FollowWorld) -> None:
        """The last leaving removes the follow, row and history kept; restore answers the same ``addedAt``."""
        row = _create(world, ALICE)
        created = world.row(row)

        world.clock += 3600
        world.follows.remove(actor(ALICE), SHOW)

        removed = world.row(row)
        assert removed.removed_at == NOW + 3600
        assert removed.active is False
        assert world.follows.read_follows(actor(ALICE)) == []

        world.clock += 3600
        restored = world.follows.restore(actor(ALICE), SHOW)

        assert restored.added_at == created.added_at
        assert world.row(row).removed_at is None
        assert world.row(row).active is True
        assert set(world.requesters(row)) == {ALICE}

    def test_restore_with_nothing_removed_is_refused(self, world: FollowWorld) -> None:
        """Nothing under the key, or the actor already asking: ``follow.not_restorable``."""
        with pytest.raises(AppNotFound) as nothing:
            world.follows.restore(actor(ALICE), SHOW)
        _create(world, ALICE)
        with pytest.raises(AppNotFound) as standing:
            world.follows.restore(actor(ALICE), SHOW)

        assert _code(nothing) is RefusalCode.FOLLOW_NOT_RESTORABLE
        assert _code(standing) is RefusalCode.FOLLOW_NOT_RESTORABLE

    def test_removing_a_follow_not_asked_for_is_refused(self, world: FollowWorld) -> None:
        """An own-scoped act on someone else's follow: ``acquisition.not_requester``, nothing written."""
        row = _create(world, ALICE)

        with pytest.raises(AppForbidden) as refused:
            world.follows.remove(actor(BOB), SHOW)

        assert _code(refused) is RefusalCode.ACQUISITION_NOT_REQUESTER
        assert set(world.requesters(row)) == {ALICE}

    def test_an_act_on_nothing_is_not_found(self, world: FollowWorld) -> None:
        """No follow under the key: ``acquisition.not_found``."""
        with pytest.raises(AppNotFound) as refused:
            world.follows.set_pause(actor(ALICE), SHOW, True)

        assert _code(refused) is RefusalCode.ACQUISITION_NOT_FOUND

    def test_two_joins_interleaved_keep_both(self, world: FollowWorld) -> None:
        """Two joins whose loads interleave keep both requesters: the load and the save are serialised.

        The save sets the requesters to the snapshot it was given, so two joins loading the same
        snapshot would each write theirs and lose the other's. The load is slowed so the two overlap.
        """
        row = _create(world, ALICE)
        load = FollowRepository.get

        def slow_get(repository: FollowRepository, *args: object, **kwargs: object) -> object:
            found = load(repository, *args, **kwargs)  # type: ignore[arg-type]
            time.sleep(0.05)
            return found

        errors: list[BaseException] = []

        def join(account: AccountId) -> None:
            try:
                world.follows.create(actor(account), SHOW, title="Breaking Bad", kind="show", year=2008)
            except BaseException as exc:  # pragma: no cover — reported below
                errors.append(exc)

        with patch.object(FollowRepository, "get", slow_get):
            threads = [threading.Thread(target=join, args=(one,)) for one in (BOB, DAVE)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        assert errors == []
        assert set(world.requesters(row)) == {ALICE, BOB, DAVE}


class TestSettings:
    """Quality and pause, and their projection on the row the engine reads."""

    def test_a_setting_by_a_non_requester_is_refused(self, world: FollowWorld) -> None:
        """``setAcquisitionQuality`` on a follow the actor did not ask for: ``acquisition.not_requester``."""
        row = _create(world, ALICE)

        with pytest.raises(AppForbidden) as refused:
            world.follows.set_quality(actor(BOB), SHOW, QualityFloor.P2160)

        assert _code(refused) is RefusalCode.ACQUISITION_NOT_REQUESTER
        assert world.profile_floor(row) is None

    def test_the_projection_follows_each_write(self, world: FollowWorld) -> None:
        """The highest floor among the holders, and the pause when every holder paused, are on the row."""
        row = _create(world, ALICE)
        _create(world, BOB)
        world.settle_all()

        world.follows.set_quality(actor(ALICE), SHOW, QualityFloor.P1080)
        assert world.profile_floor(row) == 1080
        world.follows.set_quality(actor(BOB), SHOW, QualityFloor.P2160)
        assert world.profile_floor(row) == 2160
        world.follows.set_quality(actor(BOB), SHOW, None)
        assert world.profile_floor(row) == 1080

        world.follows.set_pause(actor(ALICE), SHOW, True)
        assert world.row(row).active is True
        view = world.follows.set_pause(actor(BOB), SHOW, True)
        assert world.row(row).active is False
        assert (view.paused, view.own_paused, view.status) == (True, True, "disabled")

    def test_the_generic_pause_on_a_shared_follow_is_refused(self, world: FollowWorld) -> None:
        """``updateFollow`` by a co-requester: ``acquisition.follow_shared``, nothing paused."""
        row = _create(world, ALICE)
        _create(world, BOB)

        with pytest.raises(AppForbidden) as refused:
            world.follows.set_status(actor(ALICE), SHOW, "disabled")

        assert _code(refused) is RefusalCode.ACQUISITION_FOLLOW_SHARED
        assert world.row(row).active is True

    def test_the_generic_pause_of_a_sole_requester_is_its_own(self, world: FollowWorld) -> None:
        """On a follow only the actor asked for, ``updateFollow`` sets the actor's pause."""
        row = _create(world, ALICE)

        world.follows.set_status(actor(ALICE), SHOW, "disabled")

        assert world.requesters(row)[ALICE][2] is True
        assert world.row(row).active is False

    def test_a_pilot_any_holder_pauses_the_whole_follow(self, world: FollowWorld) -> None:
        """``acquisition.pilot.any`` lifts the shared refusal: every requester's pause is set."""
        row = _create(world, ALICE)
        _create(world, BOB)

        world.follows.set_status(actor(CAROL), SHOW, "disabled")

        assert {account: paused for account, (_, _, paused) in world.requesters(row).items()} == {
            ALICE: True,
            BOB: True,
        }
        assert world.row(row).active is False

    def test_a_role_losing_the_quality_right_is_reprojected(self, world: FollowWorld) -> None:
        """``AccountRightsChanged``: the floor of a requester whose role lost the right stops counting."""
        bus = EventBus()
        world.follows.subscribe(bus)
        row = _create(world, ALICE)
        world.follows.set_quality(actor(ALICE), SHOW, QualityFloor.P2160)
        assert world.profile_floor(row) == 2160

        world.app_store.roles.update_role(
            MEMBER, name=None, rights=MEMBER_RIGHTS - {Right.ACQUISITION_QUALITY_OWN}, now=2.0
        )
        bus.emit(AccountRightsChanged(account_ids=(ALICE, BOB), cause=RightsChangeCause.ROLE_RIGHTS_CHANGED))

        assert world.profile_floor(row) is None
        assert world.requesters(row)[ALICE][1] == 2160  # the setting itself is kept

    def test_the_maintenance_reprojection_covers_every_follow(self, world: FollowWorld) -> None:
        """``acquisition-follows-reproject`` re-saves every follow with requesters, legacy ones left alone."""
        row = _create(world, ALICE)
        world.follows.set_quality(actor(ALICE), SHOW, QualityFloor.P1080)
        world.legacy_follow(MediaRef(tvdb_id=1))
        world.app_store.roles.update_role(
            MEMBER, name=None, rights=MEMBER_RIGHTS - {Right.ACQUISITION_QUALITY_OWN}, now=2.0
        )

        count = world.follows.reproject(Actor.system(NO_CEILING, account_id=OWNER, name="owner"))

        assert count == 1
        assert world.profile_floor(row) is None


class TestReads:
    """The membership filter of ``readFollows``, and the answer's facts."""

    def test_reads_are_filtered_by_membership_without_see_others(self, world: FollowWorld) -> None:
        """Alice reads hers, Bob nothing, a ``pilot.any`` holder its own only, ``see.others`` every one."""
        _create(world, ALICE)
        world.legacy_follow(MediaRef(tvdb_id=2), title="Legacy")

        assert [view.key for view in world.follows.read_follows(actor(ALICE))] == [SHOW.wire]
        assert world.follows.read_follows(actor(BOB)) == []
        assert world.follows.read_follows(actor(CAROL)) == []
        assert {view.title for view in world.follows.read_follows(actor(DAVE))} == {"Breaking Bad", "Legacy"}

    def test_a_legacy_follow_reads_as_the_owners(self, world: FollowWorld) -> None:
        """A follow with no requester row is the owner's ask (ruling 9)."""
        world.legacy_follow(MediaRef(tvdb_id=2), title="Legacy")

        (view,) = world.follows.read_follows(actor(DAVE))

        assert [one.id for one in view.requesters] == [OWNER]
        assert view.requesters[0].name == "Owner"
        assert (view.own_quality, view.own_paused) == (None, False)

    def test_the_answer_carries_the_cards_facts(self, world: FollowWorld) -> None:
        """Counts, next air date, searches and the reader's own settings come from the stores."""
        row = _create(world, ALICE)
        world.aired(row, [(1, 1, "2026-01-01"), (1, 2, "2026-01-08"), (1, 3, "2026-12-24")])
        world.ownership.pairs = {(1, 1)}
        world.follows.set_quality(actor(ALICE), SHOW, QualityFloor.P1080)

        (view,) = world.follows.read_follows(actor(ALICE))

        assert (view.aired, view.owned, view.next_air_date) == (2, 1, "2026-12-24")
        assert (view.own_quality, view.quality) == (QualityFloor.P1080, QualityFloor.P1080)
        assert view.ids == MediaRef(tvdb_id=81189)
        assert view.searches == 0
        assert view.kind == "show" and view.year == 2008

    def test_a_queued_prime_reads_verifying(self, world: FollowWorld) -> None:
        """While the follow's prime waits in the queue, its status reads ``verifying``."""
        view = world.follows.create(actor(ALICE), SHOW, title="Breaking Bad", kind="show", year=2008)

        assert view.status == "verifying"

    def test_a_request_row_is_no_follow(self, world: FollowWorld) -> None:
        """A one-off request is never listed among the follows."""
        row = world.legacy_follow(MediaRef(tvdb_id=3), title="Request")
        world.store.requesters.save_follow(row, [], removed_at=None, min_resolution=None, active=True, scope="request")

        assert world.follows.read_follows(actor(DAVE)) == []


class TestCeiling:
    """A read-only instance refuses every write before anything is written."""

    def test_every_write_is_refused_on_a_read_only_ceiling(self, world: FollowWorld) -> None:
        """Create, pause, quality, removal, restore: ``instance.read_only`` or a forbidden write; no row."""
        frozen = actor(ALICE, ceiling=READ_ONLY)
        writes = [
            lambda: world.follows.create(frozen, SHOW, title="x", kind="show", year=None),
            lambda: world.follows.set_status(frozen, SHOW, "disabled"),
            lambda: world.follows.set_pause(frozen, SHOW, True),
            lambda: world.follows.set_quality(frozen, SHOW, QualityFloor.P720),
            lambda: world.follows.remove(frozen, SHOW),
            lambda: world.follows.restore(frozen, SHOW),
        ]
        for write in writes:
            with pytest.raises(AppForbidden):
                write()

        assert world.store.follow.list_all() == []


class TestPrime:
    """A follow that starts taking work is primed once; the ask never breaks the write."""

    def test_a_created_follow_is_primed_once(self, world: FollowWorld) -> None:
        """Created → one ``prime`` of its row in the supervisor's queue, asked by its requester."""
        row = _create(world, ALICE)

        assert world.primes() == [row]
        (request,) = world.runs.queue_view().acquisition_queued
        assert request.asked_by == ALICE

    def test_a_second_requester_joining_asks_none(self, world: FollowWorld) -> None:
        """A follow already taking work is not primed again by a join."""
        row = _create(world, ALICE)
        _create(world, BOB)

        assert world.primes() == [row]

    def test_a_revived_and_a_restored_follow_are_primed(self, world: FollowWorld) -> None:
        """Removed then created again, or restored: each comes back taking work, primed once more."""
        row = _create(world, ALICE)
        world.runs.queue_view()
        world.settle_all()

        world.follows.remove(actor(ALICE), SHOW)
        _create(world, ALICE)
        assert world.primes() == [row]
        world.settle_all()

        world.follows.remove(actor(ALICE), SHOW)
        world.follows.restore(actor(ALICE), SHOW)
        assert world.primes() == [row]

    def test_the_last_pause_lifted_primes(self, world: FollowWorld) -> None:
        """The pause lifted turns the follow back on: one prime."""
        row = _create(world, ALICE)
        world.settle_all()
        world.follows.set_pause(actor(ALICE), SHOW, True)
        assert world.primes() == []

        world.follows.set_pause(actor(ALICE), SHOW, False)

        assert world.primes() == [row]

    def test_an_ask_that_raises_leaves_the_follow_written(
        self, world: FollowWorld, logged_events: LoggedEvents
    ) -> None:
        """The supervisor refusing or failing: the follow stands, ``app.follows.prime_ask_failed`` is logged."""
        with (
            patch.object(world.runs, "ask_acquisition", side_effect=RuntimeError("queue down")),
            logged_events() as events,
        ):
            row = _create(world, ALICE)

        assert set(world.requesters(row)) == {ALICE}
        assert world.row(row).active is True
        assert "app.follows.prime_ask_failed" in [event["event"] for event in events]


class TestRestoreScope:
    """``restoreFollow`` puts back a removed FOLLOW; it is no back door into a follow or a request (§ 2.5)."""

    def test_an_account_without_the_request_right_cannot_join_a_standing_follow_by_restore(
        self, world: FollowWorld
    ) -> None:
        """Frank holds ``acquisition.follow`` but not ``acquisition.request``: Alice's follow refuses him."""
        row = _create(world, ALICE)

        with pytest.raises(AppNotFound) as refused:
            world.follows.restore(actor(FRANK), SHOW)

        assert _code(refused) is RefusalCode.FOLLOW_NOT_RESTORABLE
        assert set(world.requesters(row)) == {ALICE}

    def test_a_requester_who_left_a_shared_follow_is_taken_back(self, world: FollowWorld) -> None:
        """Bob left a follow Alice still asks for; his restore takes him back (§ 2.5)."""
        row = _create(world, ALICE)
        _create(world, BOB)
        world.follows.remove(actor(BOB), SHOW)

        world.follows.restore(actor(BOB), SHOW)

        assert set(world.requesters(row)) == {ALICE, BOB}

    def test_an_ended_request_is_not_restorable(self, world: FollowWorld) -> None:
        """A one-off request its season ended stays ended: ``follow.not_restorable``, nothing revived."""
        row = world.legacy_follow(SHOW.ref(), title="Request")
        world.store.requesters.save_follow(row, [], removed_at=None, min_resolution=None, active=True, scope="request")
        world.season_row(row, 1, status="done")
        assert world.store.follow.end_request(row, now=NOW)

        with pytest.raises(AppNotFound) as refused:
            world.follows.restore(actor(ALICE), SHOW)

        assert _code(refused) is RefusalCode.FOLLOW_NOT_RESTORABLE
        assert world.row(row).removed_at == NOW
        assert world.row(row).active is False
        assert world.requesters(row) == {}

    def test_a_standing_request_is_not_restorable(self, world: FollowWorld) -> None:
        """A request still open is no follow to restore."""
        row = world.legacy_follow(SHOW.ref(), title="Request")
        world.store.requesters.save_follow(row, [], removed_at=None, min_resolution=None, active=True, scope="request")

        with pytest.raises(AppNotFound) as refused:
            world.follows.restore(actor(ALICE), SHOW)

        assert _code(refused) is RefusalCode.FOLLOW_NOT_RESTORABLE
        assert world.requesters(row) == {}


class TestGenericPauseRefusals:
    """``updateFollow``: an own-scoped act, then a shared one (§ 2.13)."""

    def test_a_non_requester_is_refused_as_not_requester_even_on_a_shared_follow(self, world: FollowWorld) -> None:
        """Bob asked nothing of a follow Alice and Dave share: ``acquisition.not_requester``, not ``follow_shared``."""
        row = _create(world, ALICE)
        _create(world, DAVE)

        with pytest.raises(AppForbidden) as refused:
            world.follows.set_status(actor(BOB), SHOW, "disabled")

        assert _code(refused) is RefusalCode.ACQUISITION_NOT_REQUESTER
        assert world.row(row).active is True


class TestReassign:
    """``reassignRequester``: one requester's ask moved onto another account (§ 2.6, O-10 A)."""

    def test_a_target_outside_the_roster_is_account_unknown(self, world: FollowWorld) -> None:
        """No such account: ``account.unknown``, nothing moved."""
        row = _create(world, ALICE)

        with pytest.raises(AppNotFound) as refused:
            world.follows.reassign(actor(ERIN), "follow", SHOW, ALICE, AccountId("account-nobody"))

        assert _code(refused) is RefusalCode.ACCOUNT_UNKNOWN
        assert set(world.requesters(row)) == {ALICE}

    def test_a_follow_named_on_a_request_row_is_not_found(self, world: FollowWorld) -> None:
        """``kind: follow`` on a one-off request: ``acquisition.not_found``; ``kind: card`` moves it."""
        row = world.legacy_follow(SHOW.ref(), title="Request")
        world.store.requesters.save_follow(row, [], removed_at=None, min_resolution=None, active=True, scope="request")
        world.store.requesters.save_follow(
            row,
            [_stored_requester(row, ALICE, via="request")],
            removed_at=None,
            min_resolution=None,
            active=True,
        )

        with pytest.raises(AppNotFound) as refused:
            world.follows.reassign(actor(ERIN), "follow", SHOW, ALICE, BOB)
        assert _code(refused) is RefusalCode.ACQUISITION_NOT_FOUND
        assert set(world.requesters(row)) == {ALICE}

        world.follows.reassign(actor(ERIN), "card", SHOW, ALICE, BOB)
        assert world.requesters(row) == {BOB: ("request", None, False)}

    def test_a_source_that_did_not_ask_is_not_requester(self, world: FollowWorld) -> None:
        """Bob asked nothing: moving his ask is ``acquisition.not_requester``."""
        row = _create(world, ALICE)

        with pytest.raises(AppForbidden) as refused:
            world.follows.reassign(actor(ERIN), "follow", SHOW, BOB, DAVE)

        assert _code(refused) is RefusalCode.ACQUISITION_NOT_REQUESTER
        assert set(world.requesters(row)) == {ALICE}

    def test_the_moved_settings_do_not_travel_and_the_projection_drops_them(self, world: FollowWorld) -> None:
        """Alice's floor leaves with her: Bob asks from now with none, the row's floor falls."""
        row = _create(world, ALICE)
        world.follows.set_quality(actor(ALICE), SHOW, QualityFloor.P2160)

        world.clock += 60
        world.follows.reassign(actor(ERIN), "follow", SHOW, ALICE, BOB)

        assert world.requesters(row) == {BOB: ("follow", None, False)}
        (moved,) = world.store.requesters.list_for(row)
        assert moved.since == NOW + 60
        assert world.profile_floor(row) is None

    def test_a_target_already_asking_merges(self, world: FollowWorld) -> None:
        """Bob already asks: Alice simply leaves, Bob's own settings kept."""
        row = _create(world, ALICE)
        _create(world, BOB)
        world.follows.set_quality(actor(BOB), SHOW, QualityFloor.P720)

        world.follows.reassign(actor(ERIN), "follow", SHOW, ALICE, BOB)

        assert world.requesters(row) == {BOB: ("follow", 720, False)}

    def test_a_reassign_answers_the_requesters_after_the_move(self, world: FollowWorld) -> None:
        """Alice moved onto Bob, who joins; Carol keeps her ask: the answer names Carol and Bob, by name."""
        _create(world, ALICE)
        _create(world, CAROL)

        after = world.follows.reassign(actor(ERIN), "follow", SHOW, ALICE, BOB)

        assert sorted((one.id, one.name) for one in after) == [(BOB, "Bob"), (CAROL, "Carol")]

    def test_a_reassign_that_turns_the_follow_on_primes_it(self, world: FollowWorld) -> None:
        """Alice alone paused it; moved onto Bob, who paused nothing, it takes work again: one prime."""
        row = _create(world, ALICE)
        world.settle_all()
        world.follows.set_pause(actor(ALICE), SHOW, True)
        assert world.row(row).active is False

        world.follows.reassign(actor(ERIN), "follow", SHOW, ALICE, BOB)

        assert world.row(row).active is True
        assert world.primes() == [row]


class TestProjectionAfterEachWrite:
    """The floor and the pause in force are written on the row after every write (§ 2.4)."""

    def test_removal_by_the_highest_floor_drops_the_floor_and_by_the_last_turns_it_off(
        self, world: FollowWorld
    ) -> None:
        """Bob's 2160p leaves with him, Alice's 1080p is in force; Alice leaving turns the row off."""
        row = _create(world, ALICE)
        _create(world, BOB)
        world.follows.set_quality(actor(ALICE), SHOW, QualityFloor.P1080)
        world.follows.set_quality(actor(BOB), SHOW, QualityFloor.P2160)

        world.follows.remove(actor(BOB), SHOW)
        assert (world.profile_floor(row), world.row(row).active) == (1080, True)

        world.follows.remove(actor(ALICE), SHOW)
        assert world.row(row).active is False

    def test_restore_turns_the_row_back_on_with_the_restorers_settings(self, world: FollowWorld) -> None:
        """Restored, the row takes work again with no floor: the settings left with the requesters."""
        row = _create(world, ALICE)
        world.follows.set_quality(actor(ALICE), SHOW, QualityFloor.P1080)
        world.follows.remove(actor(ALICE), SHOW)

        world.follows.restore(actor(ALICE), SHOW)

        assert (world.profile_floor(row), world.row(row).active) == (None, True)

    def test_a_join_lifts_a_pause_the_joiner_does_not_share(self, world: FollowWorld) -> None:
        """Alice paused alone; Bob joining unpaused means not every holder paused: the row turns on."""
        row = _create(world, ALICE)
        world.follows.set_pause(actor(ALICE), SHOW, True)
        assert world.row(row).active is False

        _create(world, BOB)

        assert world.row(row).active is True

    def test_the_pilot_any_pause_and_resume_are_projected(self, world: FollowWorld) -> None:
        """Carol's generic pause turns the row off; her resume turns it on."""
        row = _create(world, ALICE)
        _create(world, BOB)

        world.follows.set_status(actor(CAROL), SHOW, "disabled")
        assert world.row(row).active is False
        world.follows.set_status(actor(CAROL), SHOW, "active")
        assert world.row(row).active is True

    def test_a_create_on_a_request_makes_it_a_follow_with_both_asks(self, world: FollowWorld) -> None:
        """« Suivre » on a request's card: scope ``follow`` stored, the request's asker kept ``via request``."""
        row = world.legacy_follow(SHOW.ref(), title="Breaking Bad")
        world.store.requesters.save_follow(
            row,
            [_stored_requester(row, ALICE, via="request")],
            removed_at=None,
            min_resolution=None,
            active=True,
            scope="request",
        )

        world.follows.create(actor(BOB), SHOW, title="Breaking Bad", kind="show", year=2008)

        assert world.row(row).scope == "follow"
        assert world.requesters(row) == {ALICE: ("request", None, False), BOB: ("follow", None, False)}
        assert [view.key for view in world.follows.read_follows(actor(BOB))] == [SHOW.wire]


class TestOneTransaction:
    """A write is one store transaction: a failure part-way leaves nothing behind (§ 2.7, § 2.4)."""

    def test_a_create_whose_save_fails_leaves_no_row(self, world: FollowWorld) -> None:
        """The row insert and the requesters commit together: the save failing undoes the insert."""
        with (
            patch.object(_RequesterSubStore, "save_follow", side_effect=RuntimeError("disk full")),
            pytest.raises(RuntimeError),
        ):
            world.follows.create(actor(ALICE), SHOW, title="Breaking Bad", kind="show", year=2008)

        assert world.store.follow.list_all() == []
        assert world.primes() == []

    def test_a_reprojection_in_another_process_never_drops_a_join(self, world: FollowWorld, tmp_path: Path) -> None:
        """A second service on the same ``acquire.db`` (another process: its own connection, no shared lock).

        Its re-projection loads Alice alone and is slowed before its save; Bob's join lands meanwhile.
        The re-projection's transaction holds the writer lock from its load, so the join waits for it
        and both requesters stand.
        """
        row = _create(world, ALICE)
        other = FollowService(
            open_store=world.open_store,
            open_ownership=lambda: world.ownership,
            app_store=world.app_store,
            runs=world.runs,
            owner=lambda: OWNER,
            system=lambda: SYSTEM,
            clock=lambda: world.clock,
            today=lambda: TODAY,
        )
        load = FollowRepository.get_by_id
        loaded = threading.Event()

        def slow_get_by_id(repository: FollowRepository, *args: object, **kwargs: object) -> object:
            found = load(repository, *args, **kwargs)  # type: ignore[arg-type]
            if threading.current_thread().name == "reproject":
                loaded.set()
                time.sleep(0.2)
            return found

        errors: list[BaseException] = []

        def reproject() -> None:
            try:
                other.reproject(SYSTEM)
            except BaseException as exc:  # pragma: no cover — reported below
                errors.append(exc)

        with patch.object(FollowRepository, "get_by_id", slow_get_by_id):
            thread = threading.Thread(target=reproject, name="reproject")
            thread.start()
            assert loaded.wait(5)
            world.follows.create(actor(BOB), SHOW, title="Breaking Bad", kind="show", year=2008)
            thread.join()

        assert errors == []
        assert set(world.requesters(row)) == {ALICE, BOB}


class TestReprojectionPrimes:
    """A re-projection that turns a follow back on asks its prime, as the system actor (§ 2.3)."""

    def test_a_pause_that_stops_counting_primes_the_follow(self, world: FollowWorld) -> None:
        """Alice alone paused it; her role loses ``pause.own``: the row turns on, one prime asked by the system."""
        bus = EventBus()
        world.follows.subscribe(bus)
        row = _create(world, ALICE)
        world.settle_all()
        world.follows.set_pause(actor(ALICE), SHOW, True)
        assert world.row(row).active is False

        world.app_store.roles.update_role(
            MEMBER, name=None, rights=MEMBER_RIGHTS - {Right.ACQUISITION_PAUSE_OWN}, now=2.0
        )
        bus.emit(AccountRightsChanged(account_ids=(ALICE,), cause=RightsChangeCause.ROLE_RIGHTS_CHANGED))

        assert world.row(row).active is True
        assert world.primes() == [row]
        (request,) = world.runs.queue_view().acquisition_queued
        assert request.asked_by == OWNER

    def test_the_maintenance_action_primes_what_it_turns_on(self, world: FollowWorld) -> None:
        """The same through ``acquisition-follows-reproject``."""
        row = _create(world, ALICE)
        world.settle_all()
        world.follows.set_pause(actor(ALICE), SHOW, True)
        world.app_store.roles.update_role(
            MEMBER, name=None, rights=MEMBER_RIGHTS - {Right.ACQUISITION_PAUSE_OWN}, now=2.0
        )

        world.follows.reproject(SYSTEM)

        assert world.primes() == [row]


class TestSystemPrimes:
    """A prime nobody asked for is asked by the system, and its trigger says so (review-934, carried to P12)."""

    def test_a_reassign_primes_as_the_system_whatever_the_reassigning_actor_holds(self, world: FollowWorld) -> None:
        """Alice alone paused it; Erin, who may reassign but pilots only what she asked for, moves it onto Bob.

        The prime is the follow's consequence, not Erin's act: it is asked as the system actor
        (as the rights' re-projection asks it) and carries the system's trigger, so it is neither
        refused for lack of ``acquisition.pilot.any`` nor logged as the web's.
        """
        row = _create(world, ALICE)
        world.settle_all()
        world.follows.set_pause(actor(ALICE), SHOW, True)
        reassigner = dataclasses.replace(actor(ERIN), role_rights=MEMBER_RIGHTS | {Right.ACQUISITION_REASSIGN})

        world.follows.reassign(reassigner, "follow", SHOW, ALICE, BOB)

        assert world.primes() == [row]
        (request,) = world.runs.queue_view().acquisition_queued
        assert (request.asked_by, request.trigger) == (OWNER, RunTrigger.SYSTEM)

    def test_a_reprojection_prime_carries_the_system_trigger(self, world: FollowWorld) -> None:
        """The prime a re-projection asks is the system's in its trigger as well as its asker."""
        bus = EventBus()
        world.follows.subscribe(bus)
        _create(world, ALICE)
        world.settle_all()
        world.follows.set_pause(actor(ALICE), SHOW, True)
        world.app_store.roles.update_role(
            MEMBER, name=None, rights=MEMBER_RIGHTS - {Right.ACQUISITION_PAUSE_OWN}, now=2.0
        )

        bus.emit(AccountRightsChanged(account_ids=(ALICE,), cause=RightsChangeCause.ROLE_RIGHTS_CHANGED))

        (request,) = world.runs.queue_view().acquisition_queued
        assert (request.asked_by, request.trigger) == (OWNER, RunTrigger.SYSTEM)

    def test_a_prime_asked_for_an_actors_own_write_stays_the_webs(self, world: FollowWorld) -> None:
        """A create is the person's act: its prime is asked by them, under the web's trigger."""
        _create(world, ALICE)

        (request,) = world.runs.queue_view().acquisition_queued
        assert (request.asked_by, request.trigger) == (ALICE, RunTrigger.WEB)


def _stored_requester(followed_id: int, account: AccountId, *, via: str) -> FollowRequester:
    """A stored requester with no setting, asking since :data:`NOW`.

    Args:
        followed_id: The follow.
        account: The asking account.
        via: How it asked.

    Returns:
        The row.
    """
    return FollowRequester(followed_id=followed_id, account_id=account, via=via, floor=None, paused=False, since=NOW)  # type: ignore[arg-type]
