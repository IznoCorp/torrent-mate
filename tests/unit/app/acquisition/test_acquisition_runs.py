"""``AcquisitionRuns``: a detect, a search and a grab asked through the supervisor's queue, and the schedule (K3 P13).

Each ask is one request of kind ``acquisition``: two equal asks waiting are one (the same uid), never
a refusal for lock or lane. A search and a grab are the caller's own to ask (or ``pilot.any``'s), on a
standing follow or one-off request named by the medium's key. A grab that names a release by its handle
puts the release's name AND the wanted row it was chosen on on the job; a handle that names nothing in
the stored sets is refused, never swapped for another release.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from _repo_paths import ROOT

from personalscraper.acquire.domain import WantedCandidate
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.acquisition.releases import release_handle
from personalscraper.app.acquisition.seasons import HeldShow
from personalscraper.app.acquisition.triggers import PASS_CRONS, AcquisitionRuns
from personalscraper.app.errors import AppBadRequest, AppForbidden, AppNotFound, RefusalCode
from personalscraper.app.supervisor.model import AcquisitionJob, JobKind, Lane, RunKind
from personalscraper.conf.environment import Environment
from personalscraper.core.identity import MediaRef
from tests.unit.app.acquisition.follow_world import ALICE, BOB, CAROL, OWNER, SYSTEM, FollowWorld, actor

SHOW = AcquisitionKey.parse("tvdb:81189")


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


def _triggers(world: FollowWorld, environment: Environment = Environment.PROD) -> AcquisitionRuns:
    """The service over the world's stores and queue.

    Args:
        world: The world.
        environment: The environment whose schedule the status reads.

    Returns:
        The service.
    """
    return AcquisitionRuns(
        open_store=world.open_store,
        runs=world.runs,
        owner=lambda: OWNER,
        environment=lambda: environment,
        clock=lambda: world.clock,
    )


def _followed(world: FollowWorld) -> int:
    """Alice follows :data:`SHOW`; its prime is settled away so the queue is empty.

    Args:
        world: The world.

    Returns:
        The follow's row.
    """
    world.follows.create(actor(ALICE), SHOW, title="Breaking Bad", kind="show", year=2008)
    (row,) = world.store.follow.find_all_by_ref(SHOW.ref(), kind="show")
    assert row.id is not None
    world.settle_all()
    return row.id


def _offered(world: FollowWorld, followed_id: int, episode: int, *titles: str) -> tuple[int, list[str]]:
    """One available episode row of the follow whose last search stored *titles*.

    Args:
        world: The world.
        followed_id: The follow.
        episode: The episode (season 1).
        titles: The stored candidates' names, best first.

    Returns:
        The row's id and the handle of each candidate, in the order given.
    """
    wanted_id = world.episode(followed_id, 1, episode, "available")
    candidates = [
        WantedCandidate(
            rank=rank,
            provider="c411",
            title=title,
            info_hash=f"hash-{rank}-{episode}",
            size_bytes=rank,
            seeders=1,
            resolution=None,
            source=None,
            language=None,
            score=1,
            season=1,
            episode=episode,
            searched_at=1,
        )
        for rank, title in enumerate(titles, start=1)
    ]
    world.store.candidates.replace(wanted_id, candidates)
    return wanted_id, [release_handle(wanted_id, one) for one in candidates]


def _queued(world: FollowWorld) -> list[tuple[str, AcquisitionJob]]:
    """The acquisition requests waiting.

    Args:
        world: The world.

    Returns:
        ``(uid, job)`` each, oldest first.
    """
    return [(str(one.uid), one.job) for one in world.app_store.runs.queued(Lane.ACQUISITION)]


# ── detect ───────────────────────────────────────────────────────────────────


def test_a_detection_queues_a_whole_detect_and_answers_its_uid(world: FollowWorld) -> None:
    """One request of kind ``acquisition``, a detect of every follow, under the answered uid."""
    uid = _triggers(world).detect(SYSTEM)

    assert _queued(world) == [(uid, AcquisitionJob(JobKind.DETECT))]
    request = world.app_store.runs.get(uid)  # type: ignore[arg-type]
    assert request is not None and request.kind is RunKind.ACQUISITION


def test_a_second_detection_waiting_answers_the_same_uid(world: FollowWorld) -> None:
    """Asked twice while it waits: the same request, never a refusal."""
    who = SYSTEM

    first, second = _triggers(world).detect(who), _triggers(world).detect(who)

    assert first == second
    assert len(_queued(world)) == 1


def test_a_detection_without_pipeline_control_is_refused_and_queues_nothing(world: FollowWorld) -> None:
    """``runDetection`` asks ``pipeline.control``: a member's acquisition rights do not open it."""
    with pytest.raises(AppForbidden) as refused:
        _triggers(world).detect(actor(ALICE))

    assert refused.value.code is RefusalCode.RIGHT_MISSING
    assert _queued(world) == []


# ── search and grab ──────────────────────────────────────────────────────────


def test_a_search_is_queued_for_its_follow_and_joined_when_asked_again(world: FollowWorld) -> None:
    """``searchForFollow`` is queued like the grab (O-6 B): a search of that follow, once."""
    row = _followed(world)

    first = _triggers(world).search(actor(ALICE), SHOW)
    second = _triggers(world).search(actor(ALICE), SHOW)

    assert first == second
    assert _queued(world) == [(first, AcquisitionJob(JobKind.SEARCH, followed_id=row))]


def test_a_search_behind_a_running_one_is_queued_never_refused(world: FollowWorld) -> None:
    """A pass already running absorbs nothing and refuses nothing: the new ask waits behind it."""
    _followed(world)
    first = _triggers(world).search(actor(ALICE), SHOW)
    running = world.app_store.runs.get(first)  # type: ignore[arg-type]
    assert running is not None
    running.admit(None, world.clock)
    with world.app_store.immediate():
        world.app_store.runs.save(running)

    second = _triggers(world).search(actor(ALICE), SHOW)

    assert second != first
    assert [uid for uid, _ in _queued(world)] == [second]


def test_a_grab_with_no_release_takes_what_the_search_marked_takeable(world: FollowWorld) -> None:
    """No ``releaseId``: a grab of the follow, no release and no row named."""
    row = _followed(world)

    uid = _triggers(world).grab(actor(ALICE), SHOW, None)

    assert _queued(world) == [(uid, AcquisitionJob(JobKind.GRAB, followed_id=row))]
    assert _triggers(world).grab(actor(ALICE), SHOW, None) == uid


def test_a_grab_of_a_chosen_release_names_it_and_binds_its_row(world: FollowWorld) -> None:
    """The handle gives the job the release's name and the one row it was chosen on."""
    row = _followed(world)
    _offered(world, row, 1, "Show S01E01 1080p-AAA")
    wanted_id, handles = _offered(world, row, 2, "Show S01E02 1080p-AAA", "Show S01E02 1080p-BBB")

    uid = _triggers(world).grab(actor(ALICE), SHOW, handles[1])

    assert _queued(world) == [
        (
            uid,
            AcquisitionJob(JobKind.GRAB, followed_id=row, release="Show S01E02 1080p-BBB", wanted_id=wanted_id),
        )
    ]


@pytest.mark.parametrize(
    "release_id",
    [
        "",
        "nothing",
        "x:0123456789abcdef",
        "999999:0123456789abcdef",
        f"{'9' * 40}:0123456789abcdef",
        f"{'9' * 5000}:0123456789abcdef",
    ],
    ids=["empty", "no-separator", "no-row", "unknown-row", "past-sqlite", "past-int-parsing"],
)
def test_a_handle_that_names_nothing_is_refused_and_queues_nothing(world: FollowWorld, release_id: str) -> None:
    """A handle no stored set holds: ``request.invalid`` naming ``releaseId``, never another release."""
    row = _followed(world)
    _offered(world, row, 1, "Show S01E01 1080p-AAA")

    with pytest.raises(AppBadRequest) as refused:
        _triggers(world).grab(actor(ALICE), SHOW, release_id)

    assert (refused.value.code, refused.value.params) == (RefusalCode.REQUEST_INVALID, {"fields": ["releaseId"]})
    assert _queued(world) == []


def test_a_handle_whose_set_was_replaced_is_refused(world: FollowWorld) -> None:
    """A re-search that no longer offers the release leaves a handle that names nothing."""
    row = _followed(world)
    wanted_id, (handle,) = _offered(world, row, 1, "Show S01E01 1080p-AAA")
    world.store.candidates.replace(wanted_id, [])

    with pytest.raises(AppBadRequest):
        _triggers(world).grab(actor(ALICE), SHOW, handle)


def test_a_handle_of_another_follows_row_is_refused(world: FollowWorld) -> None:
    """A row of another acquisition is not this one's to grab."""
    _followed(world)
    other = world.legacy_follow(MediaRef(tvdb_id=5), title="Other")
    _, (handle,) = _offered(world, other, 1, "Other S01E01 1080p-AAA")

    with pytest.raises(AppBadRequest):
        _triggers(world).grab(actor(ALICE), SHOW, handle)


@pytest.mark.parametrize("act", ["search", "grab"])
def test_a_key_nothing_answers_is_not_found(world: FollowWorld, act: str) -> None:
    """No follow and no request under the key: ``404 acquisition.not_found``."""
    with pytest.raises(AppNotFound) as refused:
        _ask(_triggers(world), act, ALICE, SHOW)

    assert refused.value.code is RefusalCode.ACQUISITION_NOT_FOUND


@pytest.mark.parametrize("act", ["search", "grab"])
def test_a_removed_follow_is_not_found(world: FollowWorld, act: str) -> None:
    """A removed follow is searched and grabbed no more."""
    _followed(world)
    world.follows.remove(actor(ALICE), SHOW)

    with pytest.raises(AppNotFound):
        _ask(_triggers(world), act, ALICE, SHOW)

    assert _queued(world) == []


@pytest.mark.parametrize("act", ["search", "grab"])
def test_another_accounts_acquisition_is_refused_not_requester(world: FollowWorld, act: str) -> None:
    """``pilot.own`` on a follow the caller did not ask for: ``403 acquisition.not_requester``."""
    _followed(world)

    with pytest.raises(AppForbidden) as refused:
        _ask(_triggers(world), act, BOB, SHOW)

    assert refused.value.code is RefusalCode.ACQUISITION_NOT_REQUESTER
    assert _queued(world) == []


@pytest.mark.parametrize("act", ["search", "grab"])
def test_pilot_any_acts_on_another_accounts_acquisition(world: FollowWorld, act: str) -> None:
    """``acquisition.pilot.any`` needs no requester."""
    _followed(world)

    _ask(_triggers(world), act, CAROL, SHOW)

    assert len(_queued(world)) == 1


def test_a_one_off_request_is_searched_by_its_requester(world: FollowWorld) -> None:
    """A season asked of an unfollowed show is its asker's to pilot too."""
    owned = AcquisitionKey.parse("tvdb:4242")
    world.shows.shows["tvdb:4242"] = HeldShow(
        title="Owned", year=2020, ref=MediaRef(tvdb_id=4242), aired=frozenset({(1, 1)}), owned=frozenset()
    )
    world.seasons.ask(actor(ALICE), owned, 1)
    world.settle_all()

    _triggers(world).search(actor(ALICE), owned)

    assert [job.kind for _, job in _queued(world)] == [JobKind.SEARCH]


# ── status ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("environment", "cadence", "next_search"),
    [
        (Environment.PROD, "20 3,15 * * *", "2026-11-27T15:10:00"),
        (Environment.STAGING, "50 3,15 * * *", "2026-11-27T15:40:00"),
    ],
)
def test_the_status_reads_the_environments_grab_cadence_and_next_search(
    world: FollowWorld, environment: Environment, cadence: str, next_search: str
) -> None:
    """The cron the grab runs on, and the next minute the search cron matches, with its offset."""
    world.clock = datetime(2026, 11, 27, 12, 0).timestamp()

    schedule = _triggers(world, environment).status(actor(ALICE))

    assert schedule.cadence == cadence
    assert schedule.next_search is not None
    assert schedule.next_search.startswith(next_search)
    assert datetime.fromisoformat(schedule.next_search).utcoffset() is not None


def test_a_dev_instance_schedules_nothing_so_it_announces_no_next_search(world: FollowWorld) -> None:
    """Dev has no scheduler app: the cadence is prod's, and no search is announced."""
    schedule = _triggers(world, Environment.DEV).status(actor(ALICE))

    assert (schedule.cadence, schedule.next_search) == ("20 3,15 * * *", None)


@pytest.mark.parametrize(
    ("environment", "prefix"),
    [(Environment.PROD, "personalscraper-"), (Environment.STAGING, "personalscraper-preprod-")],
)
def test_the_crons_are_the_ones_pm2_runs(environment: Environment, prefix: str) -> None:
    """The table mirrors ``ecosystem.config.js``: a cron moved there and not here fails."""
    text = (ROOT / "ecosystem.config.js").read_text(encoding="utf-8")

    def cron_of(job: str) -> str:
        """The cron of one PM2 app.

        Args:
            job: ``search`` or ``grab``.

        Returns:
            Its expression.
        """
        found = re.search(rf'name: "{prefix}{job}",.*?args: "schedule --cron \'([^\']+)\' -- {job}"', text, re.DOTALL)
        assert found is not None, job
        return found.group(1)

    crons = PASS_CRONS[environment]
    assert (crons.grab, crons.search) == (cron_of("grab"), cron_of("search"))


def _ask(service: AcquisitionRuns, act: str, account: str, key: AcquisitionKey) -> str:
    """Ask a search or a grab.

    Args:
        service: The service.
        act: ``search`` or ``grab``.
        account: Who asks.
        key: The medium.

    Returns:
        The request's uid.
    """
    who = actor(account)  # type: ignore[arg-type]
    return service.search(who, key) if act == "search" else service.grab(who, key, None)
