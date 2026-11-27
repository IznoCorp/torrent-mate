"""The chosen release in the grab (K3 P9c, DESIGN O-14, ruled by the operator on who chose).

A release NAMED BY A PERSON (the supervisor's grab job carries a ``release``) is taken if the grab's
own re-search still offers it past the hard filters, else nothing is added and ``chosen_release_gone``
is recorded on the wanted row: never a substitute, the person chooses again. A release the ENGINE
chose itself (the ranking, no name asked) that is no longer offered is simply chosen again by the
same ranking: the best takeable release of the re-search is taken, which is today's grab.

The grab runs for real here: the service, the orchestrator and an acquire store; only the trackers
(a registry answering a scripted search) and the torrent client are fakes.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.domain import FollowedSeries, WantedCandidate, WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
from personalscraper.acquire.service import AcquisitionService, RunSummary
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._errors import TorrentFetchError
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.conf.models._ranking import RankingCriterion
from personalscraper.conf.models.acquire import AcquireConfig, BandwidthConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.units import ByteSize

_RESOLVE = "personalscraper.acquire._resolve_walk.resolve_source"
_ENQUEUED_AT = 1_700_000_000
_PINNED_NOW = _ENQUEUED_AT + 3600
_REF = MediaRef(tvdb_id=99)
_PROVIDER = "c411"

_BEST = "Severance S02E05 MULTi 1080p WEB-DL x265-AAA"
_SECOND = "Severance S02E05 MULTi 1080p WEB-DL x265-BBB"
_OTHER_EPISODE = "Severance S02E06 MULTi 1080p WEB-DL x265-CCC"
_GONE = "Severance S02E05 MULTi 2160p WEB-DL x265-ZZZ"
_PREFER_TR4KER = RankingConfig(
    min_seeders=0, criteria=[RankingCriterion(field="provider", weight=1.0, values={"tr4ker": 50, "c411": 10})]
)


class _Client:
    """A torrent client that records what it is asked to add (real methods: the grab checks its protocols)."""

    def __init__(self) -> None:
        self.added: list[str] = []

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Record the add and answer the source's hash.

        Args:
            source: The fetched torrent.
            category: Unused.
            tags: Unused.
            paused: Unused.
            limits: Unused.

        Returns:
            The torrent's info-hash.
        """
        self.added.append(source.info_hash)
        return source.info_hash

    def apply_global_limits(self, *, down_bytes_per_s: int | None, up_bytes_per_s: int | None) -> None:
        """Take the global caps the pass re-asserts, and ignore them.

        Args:
            down_bytes_per_s: Unused.
            up_bytes_per_s: Unused.
        """


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin the clock so the fixture rows stay inside the cadence cutoff."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


def _result(title: str, *, seeders: int, provider: str = _PROVIDER) -> TrackerResult:
    """Build a takeable tracker result (the default ranking scores them alike: the offered order is the rank).

    Args:
        title: The release's name.
        seeders: Its seeders.
        provider: The tracker that offers it.

    Returns:
        The result; its info-hash is derived from its name (and from the tracker when it is not the default).
    """
    suffix = "" if provider == _PROVIDER else f"-{provider}"
    return TrackerResult(
        provider=provider,
        tracker_id=f"t-{seeders}-{title[-3:]}{suffix}",
        title=title,
        size=ByteSize(5_000_000_000 + seeders),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=f"hash-{title[-3:].lower()}{suffix}",
        download_url=f"https://{provider}.test/torrent/{title[-3:]}",
    )


_FETCH_FAILS: set[str] = set()


def _fetch(candidate: TrackerResult, _transports: object) -> MagicMock:
    """Stand in for ``resolve_source``: the torrent a tracker would serve for *candidate*.

    Args:
        candidate: The release asked for.
        _transports: Unused.

    Returns:
        A source whose info-hash is the candidate's.
    """
    if candidate.provider in _FETCH_FAILS:
        raise TorrentFetchError(f"{candidate.provider} cannot serve the torrent", http_status=500)
    source = MagicMock(spec=TorrentSource)
    type(source).info_hash = candidate.info_hash
    return source


def _follow(store: ConcreteAcquireStore) -> int:
    """Return the rowid of the show's follow.

    Args:
        store: The acquire store.

    Returns:
        The follow's rowid.
    """
    return store.follow.add(FollowedSeries(media_ref=_REF, title="Severance", added_at=1))


def _available(store: ConcreteAcquireStore, episode: int, *, candidates: Sequence[str] = ()) -> int:
    """Insert an episode row a search concluded takeable, with the candidates it stored.

    Args:
        store: The acquire store.
        episode: The episode number (season 2).
        candidates: The names of the candidate set the search stored, best first.

    Returns:
        The row's rowid.
    """
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=_REF,
            kind="episode",
            status="pending",
            enqueued_at=_ENQUEUED_AT,
            followed_id=_follow(store),
            season=2,
            episode=episode,
        )
    )
    store.wanted.claim_for_search(wanted_id, _PINNED_NOW)
    store.wanted.record_search_outcome(wanted_id, "available", len(candidates) or 1)
    store.wanted.set_status(wanted_id, "available")
    store.candidates.replace(
        wanted_id,
        [
            WantedCandidate(
                rank=rank,
                provider=_PROVIDER,
                title=title,
                info_hash=f"hash-{title[-3:].lower()}",
                size_bytes=1,
                seeders=1,
                resolution=None,
                source=None,
                language=None,
                score=1,
                season=2,
                episode=episode,
                searched_at=1,
            )
            for rank, title in enumerate(candidates, start=1)
        ],
    )
    return wanted_id


def _last_grab(store: ConcreteAcquireStore, wanted_id: int) -> tuple[str | None, int | None]:
    """Read the reason and the time of the row's last failed grab (a column the domain row does not carry).

    Args:
        store: The acquire store.
        wanted_id: The wanted row's rowid.

    Returns:
        ``(last_grab_reason, last_grab_at)``.
    """
    row = store.wanted._conn.execute(  # the persisted column itself
        "SELECT last_grab_reason, last_grab_at FROM wanted WHERE id = ?", (wanted_id,)
    ).fetchone()
    return row[0], row[1]


def _grab(
    store: ConcreteAcquireStore,
    client: _Client,
    offered: SearchOutcome | Sequence[TrackerResult],
    *,
    release: str | None = None,
    ranking: RankingConfig | None = None,
    fetch_fails: frozenset[str] = frozenset(),
) -> tuple[RunSummary, MagicMock]:
    """Run the grab pass of the follow with trackers answering *offered*.

    Args:
        store: The acquire store.
        client: The torrent client the grab adds to.
        offered: What the trackers return: results, or a whole outcome (an outage).
        release: The release a person named; ``None`` for the engine's own choice.
        ranking: The ranking the orchestrator scores with; a plain one when ``None`` (offered order = rank).
        fetch_fails: The trackers that cannot serve the torrent of a release they offer.

    Returns:
        The pass's counts, and the registry (to read how often the trackers were searched).
    """
    registry = MagicMock()
    registry.search_candidates.return_value = (
        offered
        if isinstance(offered, SearchOutcome)
        else SearchOutcome(results=list(offered), trackers_queried=1, trackers_errored=0)
    )
    registry.transports.return_value = {_PROVIDER: MagicMock()}
    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=client,  # type: ignore[arg-type]
        event_bus=EventBus(),
        ranking=ranking or RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )
    config = MagicMock()
    config.acquire = AcquireConfig()
    service = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,
        event_bus=MagicMock(),
        config=config,
    )
    followed_id = _follow(store)
    kwargs: dict[str, object] = {} if release is None else {"release": release}
    _FETCH_FAILS.clear()
    _FETCH_FAILS.update(fetch_fails)
    with patch(_RESOLVE, side_effect=_fetch):
        return service.run(followed_id=followed_id, **kwargs), registry  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A release named by a person
# ---------------------------------------------------------------------------


def test_a_named_release_still_offered_is_taken_though_it_is_not_the_best(store: ConcreteAcquireStore) -> None:
    """The named release is taken, not the engine's top pick."""
    wanted_id = _available(store, 5, candidates=[_BEST, _SECOND])
    client = _Client()

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90), _result(_SECOND, seeders=40)], release=_SECOND)

    assert summary.grabbed == 1
    assert client.added == ["hash-bbb"]
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert (row.status, row.grabbed_hash) == ("grabbed", "hash-bbb")
    assert _last_grab(store, wanted_id)[0] is None


def test_a_named_release_that_is_gone_adds_nothing_and_records_why(store: ConcreteAcquireStore) -> None:
    """Gone from the re-search: no substitute, the reason on the row, the row still wanted."""
    wanted_id = _available(store, 5, candidates=[_GONE, _BEST])
    client = _Client()

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90), _result(_SECOND, seeders=40)], release=_GONE)

    assert client.added == []
    assert (summary.grabbed, summary.release_gone) == (0, 1)
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert _last_grab(store, wanted_id) == ("chosen_release_gone", _PINNED_NOW)
    assert row.status == "available"
    assert row.grabbed_hash is None


def test_a_named_release_is_gone_when_the_trackers_offer_nothing_at_all(store: ConcreteAcquireStore) -> None:
    """A healthy empty search concluded: what the person named is not there."""
    wanted_id = _available(store, 5, candidates=[_BEST])
    client = _Client()

    summary, _ = _grab(store, client, [], release=_BEST)

    assert client.added == []
    assert summary.release_gone == 1
    assert _last_grab(store, wanted_id)[0] == "chosen_release_gone"
    assert store.candidates.list_for(wanted_id) == []
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert (row.status, row.last_search_outcome, row.last_search_found) == ("pending", "no_candidates", 0)


def test_an_outage_is_not_a_gone_release_but_still_holds_the_unmet_pick(store: ConcreteAcquireStore) -> None:
    """Panne ≠ absence: the release is not « gone », yet the person's pick is unmet, so the row is held."""
    wanted_id = _available(store, 5, candidates=[_BEST])
    client = _Client()
    down = SearchOutcome(
        results=[],
        trackers_queried=1,
        trackers_errored=1,
        errored_names=[_PROVIDER],
        errors={_PROVIDER: "api"},
        queried_names=[_PROVIDER],
    )

    summary, _ = _grab(store, client, down, release=_BEST)

    assert client.added == []
    assert summary.release_gone == 0
    assert _last_grab(store, wanted_id)[0] == "chosen_release_failed"


def test_a_named_release_is_asked_of_the_rows_whose_candidates_carry_it(store: ConcreteAcquireStore) -> None:
    """Another episode of the follow is neither searched nor touched by a release that is not its own."""
    own = _available(store, 5, candidates=[_BEST])
    other = _available(store, 6, candidates=[_OTHER_EPISODE])
    client = _Client()

    summary, registry = _grab(
        store, client, [_result(_BEST, seeders=90), _result(_OTHER_EPISODE, seeders=80)], release=_BEST
    )

    assert client.added == ["hash-aaa"]
    assert summary.grabbed == 1
    assert registry.search_candidates.call_count == 1
    untouched = store.wanted.get(other)
    assert untouched is not None
    assert untouched.status == "available"
    assert _last_grab(store, other)[0] is None
    taken = store.wanted.get(own)
    assert taken is not None
    assert taken.status == "grabbed"


def test_a_release_no_stored_set_carries_asks_and_holds_no_row(store: ConcreteAcquireStore) -> None:
    """A set replaced since the choice names nothing: no row a person never chose is asked or held (finding 2)."""
    first = _available(store, 5, candidates=[_BEST])
    second = _available(store, 6, candidates=[_OTHER_EPISODE])
    client = _Client()

    summary, registry = _grab(
        store, client, [_result(_BEST, seeders=90), _result(_OTHER_EPISODE, seeders=80)], release=_GONE
    )

    assert client.added == []
    assert (summary.grabbed, summary.release_gone) == (0, 0)
    assert registry.search_candidates.call_count == 0
    for wanted_id in (first, second):
        assert _last_grab(store, wanted_id)[0] is None
    follow_up, _ = _grab(store, client, [_result(_BEST, seeders=90), _result(_OTHER_EPISODE, seeders=80)])
    assert follow_up.grabbed == 2


@pytest.mark.parametrize(
    "offered",
    [[], [_OTHER_EPISODE]],
    ids=["no_candidates", "no_matching_episode"],
)
def test_a_named_release_with_nothing_offered_keeps_the_verdict_clears_the_set_and_holds(
    store: ConcreteAcquireStore, offered: list[str]
) -> None:
    """Every path where the re-search concluded nothing: verdict recorded, picker cleared, row held (finding 1)."""
    wanted_id = _available(store, 5, candidates=[_GONE])
    client = _Client()

    summary, _ = _grab(store, client, [_result(t, seeders=50) for t in offered], release=_GONE)

    assert (summary.grabbed, summary.release_gone) == (0, 1)
    assert store.candidates.list_for(wanted_id) == []
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert (row.status, row.last_search_found) == ("pending", 0)
    assert _last_grab(store, wanted_id)[0] == "chosen_release_gone"


def test_a_named_run_asks_only_the_owner_rows_not_a_stale_searching_row(store: ConcreteAcquireStore) -> None:
    """A stale-'searching' row of the follow is not handed a choice made for another row (finding 3)."""
    owner = _available(store, 5, candidates=[_GONE])
    stale = _stale_searching(store, 6)
    client = _Client()

    summary, registry = _grab(store, client, [_result(_OTHER_EPISODE, seeders=80)], release=_GONE)

    assert registry.search_candidates.call_count == 1
    assert summary.release_gone == 1
    assert _last_grab(store, owner)[0] == "chosen_release_gone"
    assert _last_grab(store, stale)[0] is None


def test_a_scheduled_grab_leaves_a_held_stale_searching_row_alone(store: ConcreteAcquireStore) -> None:
    """The hold also keeps a held row left 'searching' by a killed claim out of the unnamed pass (finding 3)."""
    stale = _stale_searching(store, 5)
    store.wanted.record_grab_failure(stale, "chosen_release_gone", _PINNED_NOW)
    client = _Client()

    summary, registry = _grab(store, client, [_result(_BEST, seeders=90)])

    assert (summary.grabbed, registry.search_candidates.call_count) == (0, 0)
    assert client.added == []


def _stale_searching(store: ConcreteAcquireStore, episode: int) -> int:
    """Insert an episode row left 'searching' long ago by a killed claim.

    Args:
        store: The acquire store.
        episode: The episode number (season 2).

    Returns:
        The row's rowid.
    """
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=_REF,
            kind="episode",
            status="pending",
            enqueued_at=_ENQUEUED_AT,
            followed_id=_follow(store),
            season=2,
            episode=episode,
        )
    )
    store.wanted.claim_for_search(wanted_id, 1)  # long before the stale threshold
    return wanted_id


# ---------------------------------------------------------------------------
# A row whose person-named release is gone waits for the person (operator, O-14)
# ---------------------------------------------------------------------------


def test_a_row_whose_named_release_is_gone_is_not_taken_by_the_next_scheduled_grab(
    store: ConcreteAcquireStore,
) -> None:
    """« C'est moi qui dois refaire ce choix, donc on attend »: the engine's pick never stands in."""
    held = _available(store, 5, candidates=[_GONE, _BEST])
    client = _Client()
    _grab(store, client, [_result(_BEST, seeders=90)], release=_GONE)
    assert _last_grab(store, held)[0] == "chosen_release_gone"

    summary, registry = _grab(store, client, [_result(_BEST, seeders=90), _result(_SECOND, seeders=40)])

    assert client.added == []
    assert summary.grabbed == 0
    assert registry.search_candidates.call_count == 0
    row = store.wanted.get(held)
    assert row is not None
    assert (row.status, row.grabbed_hash) == ("available", None)
    assert _last_grab(store, held)[0] == "chosen_release_gone"


def test_a_whole_queue_scheduled_grab_leaves_a_held_row_alone_and_takes_the_others(
    store: ConcreteAcquireStore,
) -> None:
    """The hold is the row's: another open row of the same follow is grabbed as ever."""
    held = _available(store, 5, candidates=[_GONE])
    free = _available(store, 6, candidates=[_OTHER_EPISODE])
    client = _Client()
    _grab(store, client, [_result(_BEST, seeders=90)], release=_GONE)
    assert _last_grab(store, held)[0] == "chosen_release_gone"
    assert _last_grab(store, free)[0] is None

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90), _result(_OTHER_EPISODE, seeders=80)])

    assert summary.grabbed == 1
    assert client.added == ["hash-ccc"]
    taken = store.wanted.get(free)
    assert taken is not None
    assert taken.status == "grabbed"
    assert _last_grab(store, held)[0] == "chosen_release_gone"


def test_a_new_manual_pick_lifts_the_hold_and_is_taken(store: ConcreteAcquireStore) -> None:
    """The person chooses again: the held row is asked, and the release is taken."""
    held = _available(store, 5, candidates=[_GONE, _BEST, _SECOND])
    client = _Client()
    _grab(store, client, [_result(_BEST, seeders=90)], release=_GONE)

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90), _result(_SECOND, seeders=40)], release=_SECOND)

    assert summary.grabbed == 1
    assert client.added == ["hash-bbb"]
    row = store.wanted.get(held)
    assert row is not None
    assert row.status == "grabbed"
    assert _last_grab(store, held)[0] is None


def test_a_failure_other_than_a_gone_release_holds_nothing(store: ConcreteAcquireStore) -> None:
    """Only a gone person-named release holds a row: an outage leaves it to the next scheduled grab."""
    wanted_id = _available(store, 5, candidates=[_BEST])
    client = _Client()
    down = SearchOutcome(
        results=[],
        trackers_queried=1,
        trackers_errored=1,
        errored_names=[_PROVIDER],
        errors={_PROVIDER: "api"},
        queried_names=[_PROVIDER],
    )
    _grab(store, client, down)

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90)])

    assert summary.grabbed == 1
    assert client.added == ["hash-aaa"]
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "grabbed"


def test_a_held_row_survives_a_named_pick_that_fails_otherwise(store: ConcreteAcquireStore) -> None:
    """Finding 4: the claim and a later failure keep the hold, so the engine's pick never stands in."""
    held = _available(store, 5, candidates=[_GONE, _BEST])
    client = _Client()
    _grab(store, client, [_result(_BEST, seeders=90)], release=_GONE)
    down = SearchOutcome(
        results=[],
        trackers_queried=1,
        trackers_errored=1,
        errored_names=[_PROVIDER],
        errors={_PROVIDER: "api"},
        queried_names=[_PROVIDER],
    )

    _grab(store, client, down, release=_GONE)
    summary, _ = _grab(store, client, [_result(_BEST, seeders=90)])

    assert (summary.grabbed, client.added) == (0, [])
    assert _last_grab(store, held)[0] in {"chosen_release_gone", "chosen_release_failed"}


def test_a_first_named_pick_that_meets_an_outage_holds_the_row(store: ConcreteAcquireStore) -> None:
    """Finding 4: the person's choice is unmet even when no hold was set before; nothing substitutes."""
    wanted_id = _available(store, 5, candidates=[_BEST])
    client = _Client()
    down = SearchOutcome(
        results=[],
        trackers_queried=1,
        trackers_errored=1,
        errored_names=[_PROVIDER],
        errors={_PROVIDER: "api"},
        queried_names=[_PROVIDER],
    )
    _grab(store, client, down, release=_BEST)

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90)])

    assert (summary.grabbed, client.added) == (0, [])
    assert _last_grab(store, wanted_id)[0] == "chosen_release_failed"


def test_the_hold_survives_the_search_pass(store: ConcreteAcquireStore) -> None:
    """Finding 5: held → pending → searched → available → a scheduled grab still takes nothing."""
    wanted_id = _available(store, 5, candidates=[_GONE])
    client = _Client()
    _grab(store, client, [], release=_GONE)  # nothing offered: pending, held
    store.wanted._conn.execute("UPDATE wanted SET last_search_at = NULL WHERE id = ?", (wanted_id,))
    orchestrator = MagicMock(spec=GrabOrchestrator)
    orchestrator.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=1,
        chosen=_result(_BEST, seeders=90),
        ranked=((_result(_BEST, seeders=90), 10),),
    )
    config = MagicMock()
    config.acquire = AcquireConfig()
    AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    ).run_search()
    searched = store.wanted.get(wanted_id)
    assert searched is not None
    assert searched.status == "available"

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90)])

    assert (summary.grabbed, client.added) == (0, [])
    assert _last_grab(store, wanted_id)[0] == "chosen_release_gone"


def test_a_named_release_offered_by_two_trackers_is_added_once_from_the_ranked_one(
    store: ConcreteAcquireStore,
) -> None:
    """Finding 6: one release on two trackers is added once, from the ranked one; another name is never taken."""
    _available(store, 5, candidates=[_BEST])
    client = _Client()
    offered = [
        _result(_BEST, seeders=60, provider="c411"),
        _result(_BEST, seeders=90, provider="tr4ker"),
        _result(_SECOND, seeders=99, provider="c411"),
    ]

    summary, _ = _grab(store, client, offered, release=_BEST, ranking=_PREFER_TR4KER)

    assert summary.grabbed == 1
    assert client.added == ["hash-aaa-tr4ker"]


@pytest.mark.parametrize("near", [_BEST.lower(), _BEST + ".mkv", _BEST.replace("S02E05", "S02E05 "), _BEST[:-4]])
def test_a_near_name_is_not_the_named_release(store: ConcreteAcquireStore, near: str) -> None:
    """Finding 6: the match is the exact name, a case or one character off is gone."""
    wanted_id = _available(store, 5, candidates=[near])
    client = _Client()

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90)], release=near)

    assert (summary.grabbed, client.added) == (0, [])
    assert _last_grab(store, wanted_id)[0] == "chosen_release_gone"


# ---------------------------------------------------------------------------
# A release the engine chose itself, or none named
# ---------------------------------------------------------------------------


def test_with_no_release_named_the_best_ranked_is_grabbed(store: ConcreteAcquireStore) -> None:
    """Today's grab: nothing named, the ranking's top is taken."""
    wanted_id = _available(store, 5, candidates=[_BEST, _SECOND])
    client = _Client()

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90), _result(_SECOND, seeders=40)])

    assert summary.grabbed == 1
    assert client.added == ["hash-aaa"]
    assert _last_grab(store, wanted_id)[0] is None


def test_an_engine_choice_that_is_gone_is_chosen_again_by_the_ranking(store: ConcreteAcquireStore) -> None:
    """The search stored the engine's top pick; at grab time it is no longer offered: the next best is taken."""
    wanted_id = _available(store, 5, candidates=[_BEST, _SECOND])
    client = _Client()

    summary, _ = _grab(store, client, [_result(_SECOND, seeders=40)])

    assert summary.grabbed == 1
    assert summary.release_gone == 0
    assert client.added == ["hash-bbb"]
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "grabbed"
    assert _last_grab(store, wanted_id)[0] is None


# ---------------------------------------------------------------------------
# Carried from review-935: the grab's own re-search keeps the candidates honest
# ---------------------------------------------------------------------------


def test_a_re_search_that_concludes_nothing_clears_the_stored_candidates(store: ConcreteAcquireStore) -> None:
    """The picker must never offer a set the grab's own re-search found empty."""
    wanted_id = _available(store, 5, candidates=[_BEST, _SECOND])
    client = _Client()

    summary, _ = _grab(store, client, [])

    assert (summary.grabbed, summary.retried) == (0, 1)
    assert store.candidates.list_for(wanted_id) == []
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert (row.status, row.last_search_outcome, row.last_search_found) == ("pending", "no_candidates", 0)


def test_a_re_search_that_did_not_conclude_keeps_the_stored_candidates(store: ConcreteAcquireStore) -> None:
    """An outage is not knowledge: the set stays as the last concluded search left it."""
    wanted_id = _available(store, 5, candidates=[_BEST, _SECOND])
    client = _Client()
    down = SearchOutcome(
        results=[],
        trackers_queried=1,
        trackers_errored=1,
        errored_names=[_PROVIDER],
        errors={_PROVIDER: "api"},
        queried_names=[_PROVIDER],
    )

    _grab(store, client, down)

    assert [c.title for c in store.candidates.list_for(wanted_id)] == [_BEST, _SECOND]


# ---------------------------------------------------------------------------
# The automated ranking decides the engine's choice (finding 6)
# ---------------------------------------------------------------------------


def test_the_ranking_not_the_offered_order_picks_the_best(store: ConcreteAcquireStore) -> None:
    """Nothing named: the tracker the ranking prefers wins though it is offered last."""
    _available(store, 5, candidates=[_BEST])
    client = _Client()

    summary, _ = _grab(
        store,
        client,
        [_result(_BEST, seeders=90), _result(_SECOND, seeders=40, provider="tr4ker")],
        ranking=_PREFER_TR4KER,
    )

    assert summary.grabbed == 1
    assert client.added == ["hash-bbb-tr4ker"]


def test_an_engine_choice_that_is_gone_is_rechosen_by_the_ranking_not_the_offered_order(
    store: ConcreteAcquireStore,
) -> None:
    """O-14 B: the stored top is gone; of what is still offered the ranking's best is taken."""
    wanted_id = _available(store, 5, candidates=[_GONE, _BEST])
    client = _Client()

    summary, _ = _grab(
        store,
        client,
        [_result(_BEST, seeders=90), _result(_SECOND, seeders=40, provider="tr4ker")],
        ranking=_PREFER_TR4KER,
    )

    assert (summary.grabbed, summary.release_gone) == (1, 0)
    assert client.added == ["hash-bbb-tr4ker"]
    assert _last_grab(store, wanted_id)[0] is None


def test_a_claim_keeps_the_hold(store: ConcreteAcquireStore) -> None:
    """Finding 4 at the store: claiming a held row for a grab (then crashing) leaves the hold in place."""
    wanted_id = _available(store, 5, candidates=[_BEST])
    store.wanted.record_grab_failure(wanted_id, "chosen_release_gone", _PINNED_NOW)

    assert store.wanted.claim_for_grab(wanted_id, _PINNED_NOW)

    assert _last_grab(store, wanted_id) == ("chosen_release_gone", _PINNED_NOW)
    store.wanted.record_grab_failure(wanted_id, "fetch_failed", _PINNED_NOW + 1)
    assert _last_grab(store, wanted_id)[0] == "chosen_release_gone"
