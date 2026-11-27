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
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.acquire.service import AcquisitionService, RunSummary
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
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


def _result(title: str, *, seeders: int) -> TrackerResult:
    """Build a takeable tracker result (the default ranking scores them alike: the offered order is the rank).

    Args:
        title: The release's name.
        seeders: Its seeders.

    Returns:
        The result; its info-hash is derived from its name.
    """
    return TrackerResult(
        provider=_PROVIDER,
        tracker_id=f"t-{seeders}-{title[-3:]}",
        title=title,
        size=ByteSize(5_000_000_000 + seeders),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=f"hash-{title[-3:].lower()}",
        download_url=f"https://{_PROVIDER}.test/torrent/{title[-3:]}",
    )


def _fetch(candidate: TrackerResult, _transports: object) -> MagicMock:
    """Stand in for ``resolve_source``: the torrent a tracker would serve for *candidate*.

    Args:
        candidate: The release asked for.
        _transports: Unused.

    Returns:
        A source whose info-hash is the candidate's.
    """
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
) -> tuple[RunSummary, MagicMock]:
    """Run the grab pass of the follow with trackers answering *offered*.

    Args:
        store: The acquire store.
        client: The torrent client the grab adds to.
        offered: What the trackers return: results, or a whole outcome (an outage).
        release: The release a person named; ``None`` for the engine's own choice.

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
        ranking=RankingConfig(min_seeders=0),
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


def test_an_outage_is_not_a_gone_release(store: ConcreteAcquireStore) -> None:
    """Panne ≠ absence: trackers that could not answer say nothing about the named release."""
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
    assert _last_grab(store, wanted_id)[0] == "trackers_unavailable"


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


def test_a_release_no_stored_set_carries_is_asked_of_every_open_row_of_the_follow(
    store: ConcreteAcquireStore,
) -> None:
    """A set replaced since the choice no longer names it: every open row records that nothing was taken."""
    first = _available(store, 5, candidates=[_BEST])
    second = _available(store, 6, candidates=[_OTHER_EPISODE])
    client = _Client()

    summary, _ = _grab(store, client, [_result(_BEST, seeders=90), _result(_OTHER_EPISODE, seeders=80)], release=_GONE)

    assert client.added == []
    assert summary.release_gone == 2
    for wanted_id in (first, second):
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
