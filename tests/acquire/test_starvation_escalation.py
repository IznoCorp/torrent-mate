"""An episode the trackers do not carry separately must escalate to the season pack (D1).

Regression for American Dad! S15E21: the episode query returned 0 results, so the search
exited on ``no_candidates`` and the R2 conversion — armed only on ``no_matching_episode``
— could never fire. The calendar path (DETECT) was blocked in parallel by its
``owned <= total/2`` gate at 20/22 owned. The row was re-searched 17 times over 20 days
while a 4-pack, 65-seeder season release sat on the trackers.

The trigger here is EVIDENCE of failure, not the calendar: it therefore deliberately
bypasses the DETECT gates ``last_air >= 7 days`` and ``owned <= total/2``, both of which
provably blocked the four real cases.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import SeasonEscalatedAfterEpisodeFailures
from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

_PINNED_NOW = 1_700_003_600
_TVDB = 99
_FOLLOWED_ID = 1


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _season_pack_result(title: str = "Show S03E01-E05 COMPLETE 1080p") -> TrackerResult:
    """A tracker result that ``filter_to_season`` keeps."""
    return TrackerResult(
        provider="c411",
        tracker_id="t99",
        title=title,
        size=ByteSize(20_000_000_000),
        seeders=100,
        leechers=0,
        resolution="1080p",
        info_hash="seasonpack99",
        download_url="https://c411.test/torrent/99",
    )


def _seed_follow_and_catalog(
    store: ConcreteAcquireStore,
    *,
    season: int = 3,
    episodes: int = 5,
    last_air: str = "2023-01-29",
    future_air: str | None = None,
) -> None:
    """Create the follow plus an aired catalog for *season*.

    Args:
        store: The acquire store under test.
        season: Season number to populate.
        episodes: How many episodes the catalog lists.
        last_air: Air date of every episode except the optional future one.
        future_air: When set, the LAST episode airs on this (future) date, which
            makes the season not-fully-aired.
    """
    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=_TVDB), title="Test Show", added_at=1))
    rows = []
    for ep in range(1, episodes + 1):
        air = future_air if (future_air is not None and ep == episodes) else last_air
        rows.append((season, ep, f"E{ep:02d}", air))
    store.aired.replace_for_followed(_FOLLOWED_ID, rows, now=1_700_000_000)


def _starved_episode(season: int = 3, episode: int = 5, attempts: int = 1) -> WantedItem:
    """A pending episode row that has already burned *attempts* concluded searches."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=_TVDB),
        kind="episode",
        status="pending",
        enqueued_at=1_700_000_000,
        followed_id=_FOLLOWED_ID,
        season=season,
        episode=episode,
        attempts=attempts,
    )


def _run(
    store: ConcreteAcquireStore,
    verdicts: list[SearchVerdict],
) -> tuple[MagicMock, MagicMock]:
    """Drive one search pass whose orchestrator answers *verdicts* in order.

    Returns ``(orchestrator_mock, event_bus_mock)`` so tests can assert both the
    number of tracker searches performed and the events emitted.
    """
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.side_effect = verdicts
    event_bus = MagicMock()
    config = MagicMock()
    config.acquire = AcquireConfig()
    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=event_bus,
        config=config,
    )
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        svc.run_search()
    return orch, event_bus


_NO_CANDIDATES = SearchVerdict(disposition="not_found", outcome="no_candidates", found=0)
_PACK_AVAILABLE = SearchVerdict(
    disposition="available",
    outcome="available",
    found=1,
    chosen=_season_pack_result(),
)
_PACK_ABSENT = SearchVerdict(disposition="not_found", outcome="no_matching_season", found=0)


class TestEscalatesOnConcludedFailures:
    """The trigger is EVIDENCE of failure, not the calendar."""

    def test_no_candidates_at_threshold_enqueues_the_season(self, store: ConcreteAcquireStore) -> None:
        """2 concluded failures + fully aired season + covering pack ⇒ season enqueued."""
        _seed_follow_and_catalog(store)
        ep_id = store.wanted.add(_starved_episode(attempts=1))

        _orch, event_bus = _run(store, [_NO_CANDIDATES, _PACK_AVAILABLE])

        season_row = store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=3, episode=None)
        assert season_row is not None, "the season pack must be enqueued"
        assert season_row.status == "pending"
        assert store.wanted.get(ep_id).status == "absorbed"

        escalations = [
            c[0][0] for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonEscalatedAfterEpisodeFailures)
        ]
        assert len(escalations) == 1, "the escalation must say WHY, not just absorb silently"
        assert escalations[0].trigger_outcome == "no_candidates"
        assert escalations[0].season == 3
        assert ep_id in escalations[0].starved_episode_ids

    def test_no_matching_episode_also_arms_the_escalation(self, store: ConcreteAcquireStore) -> None:
        """Both concluded not_found shapes trigger it, not just the empty one."""
        _seed_follow_and_catalog(store)
        store.wanted.add(_starved_episode(attempts=1))

        _run(
            store,
            [SearchVerdict(disposition="not_found", outcome="no_matching_episode", found=0), _PACK_AVAILABLE],
        )

        assert store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=3, episode=None) is not None

    def test_below_threshold_does_not_escalate_and_makes_no_extra_tracker_call(
        self, store: ConcreteAcquireStore
    ) -> None:
        """One attempt after the claim ⇒ no escalation AND no season probe (cost guard)."""
        _seed_follow_and_catalog(store)
        store.wanted.add(_starved_episode(attempts=0))

        orch, _bus = _run(store, [_NO_CANDIDATES])

        assert store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=3, episode=None) is None
        assert orch.search.call_count == 1, "no season probe may run below the threshold"

    def test_season_not_fully_aired_does_not_escalate(self, store: ConcreteAcquireStore) -> None:
        """A future episode means no pack can cover it — do not probe, do not escalate."""
        _seed_follow_and_catalog(store, future_air="2099-01-01")
        store.wanted.add(_starved_episode(attempts=1))

        orch, _bus = _run(store, [_NO_CANDIDATES])

        assert store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=3, episode=None) is None
        assert orch.search.call_count == 1, "an unfinished season must not be probed"

    def test_probe_without_covering_pack_leaves_the_episode_live(self, store: ConcreteAcquireStore) -> None:
        """No covering pack ⇒ the episode keeps its own verdict and stays queued."""
        _seed_follow_and_catalog(store)
        ep_id = store.wanted.add(_starved_episode(attempts=1))

        _run(store, [_NO_CANDIDATES, _PACK_ABSENT])

        row = store.wanted.get(ep_id)
        assert row.status == "pending", "a fruitless probe must not park the episode"
        assert row.last_search_outcome == "no_candidates"
        assert store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=3, episode=None) is None

    def test_empty_aired_catalog_does_not_escalate(self, store: ConcreteAcquireStore) -> None:
        """Unknown coverage is never treated as complete — no catalog, no probe."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=_TVDB), title="Test Show", added_at=1))
        store.wanted.add(_starved_episode(attempts=1))

        orch, _bus = _run(store, [_NO_CANDIDATES])

        assert store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=3, episode=None) is None
        assert orch.search.call_count == 1


class TestProbeIsBounded:
    """One probe per (follow, season) per pass — ten starved episodes are not ten queries."""

    def test_two_starved_episodes_same_season_probe_once(self, store: ConcreteAcquireStore) -> None:
        """The per-pass memo collapses siblings onto a single season query.

        Without the memo, every starved episode of the same season would fire its own
        identical season search — ten episodes, ten queries, every pass, forever.
        """
        _seed_follow_and_catalog(store)
        store.wanted.add(_starved_episode(episode=4, attempts=1))
        store.wanted.add(_starved_episode(episode=5, attempts=1))

        # Episode search, season probe, then at most one more episode search.
        orch, _bus = _run(store, [_NO_CANDIDATES, _PACK_AVAILABLE, _NO_CANDIDATES])

        season_queries = [c for c in orch.search.call_args_list if c[0][0].kind == "season"]
        assert len(season_queries) == 1, f"expected exactly 1 season probe, got {len(season_queries)}"


class TestProbeIsReadOnly:
    """The probe must not persist anything of its own."""

    def test_probe_item_is_never_written_to_the_store(self, store: ConcreteAcquireStore) -> None:
        """Only ONE season row exists after the pass — the enqueued one, not the probe."""
        _seed_follow_and_catalog(store)
        store.wanted.add(_starved_episode(attempts=1))

        _run(store, [_NO_CANDIDATES, _PACK_AVAILABLE])

        season_rows = store.wanted.list_for_followed(_FOLLOWED_ID, kind="season")
        assert len(season_rows) == 1, f"the transient probe must not be persisted: {season_rows}"


class TestRegressionAmericanDadS15E21:
    """The exact live shape that motivated this feature."""

    def test_episode_query_empty_season_query_has_packs_escalates(self, store: ConcreteAcquireStore) -> None:
        """Episode query 0 results, season query has covering packs ⇒ escalation.

        American Dad! S15 on 2026-08-04: 22 aired episodes, 20 owned (so DETECT gate
        (c) ``owned <= total/2`` blocked the calendar path), episode query `American
        Dad! S15E21` returned raw=0 (so R2 could not fire), season query returned 4
        packs, top 65 seeders. 17 attempts over 20 days, zero escalation.
        """
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=73141), title="American Dad!", added_at=1))
        store.aired.replace_for_followed(
            _FOLLOWED_ID,
            [(15, ep, f"E{ep:02d}", "2019-04-08") for ep in range(1, 23)],
            now=1_700_000_000,
        )
        ep_id = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=73141),
                kind="episode",
                status="pending",
                enqueued_at=1_700_000_000,
                followed_id=_FOLLOWED_ID,
                season=15,
                episode=21,
                attempts=16,
            )
        )

        _orch, event_bus = _run(store, [_NO_CANDIDATES, _PACK_AVAILABLE])

        season_row = store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=15, episode=None)
        assert season_row is not None, "S15 must escalate to the season pack"
        assert store.wanted.get(ep_id).status == "absorbed"
        assert any(isinstance(c[0][0], SeasonEscalatedAfterEpisodeFailures) for c in event_bus.emit.call_args_list)


class TestMalformedCatalogNeverKillsThePass:
    """A bad air_date must not abort the whole search pass.

    ``AiredEpisodeRow.air_date`` is a plain ``str`` from an ADVISORY cache table, and
    this feature is the first code to parse it. ``run_search`` isolates only
    ``sqlite3.OperationalError`` and ``json.JSONDecodeError``, so a ``ValueError``
    escaping the date parse would propagate out of the loop and leave every
    remaining item unsearched — one malformed row silencing the whole queue.
    """

    def test_unparseable_air_date_is_read_as_not_fully_aired(self, store: ConcreteAcquireStore) -> None:
        """A malformed date answers « coverage unknown » — no crash, no escalation."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=_TVDB), title="Test Show", added_at=1))
        store.aired.replace_for_followed(
            _FOLLOWED_ID,
            [(3, 1, "E01", "2023-01-29"), (3, 2, "E02", "TBA")],
            now=1_700_000_000,
        )
        store.wanted.add(_starved_episode(attempts=1))

        orch, _bus = _run(store, [_NO_CANDIDATES])

        assert store.wanted.find(followed_id=_FOLLOWED_ID, kind="season", season=3, episode=None) is None
        assert orch.search.call_count == 1, "unknown coverage must not be probed"

    def test_pass_completes_and_still_searches_later_items(self, store: ConcreteAcquireStore) -> None:
        """The item AFTER the malformed-catalog one is still searched.

        This is the load-bearing half: a crash here would abort the loop, and the
        summary would never fire.
        """
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=_TVDB), title="Test Show", added_at=1))
        store.aired.replace_for_followed(
            _FOLLOWED_ID,
            [(3, 5, "E05", "not-a-date")],
            now=1_700_000_000,
        )
        store.wanted.add(_starved_episode(episode=5, attempts=1))
        second_id = store.wanted.add(_starved_episode(episode=6, attempts=1))

        orch, _bus = _run(store, [_NO_CANDIDATES, _NO_CANDIDATES])

        assert orch.search.call_count == 2, "the pass must keep going after a bad catalog row"
        assert store.wanted.get(second_id).last_search_outcome == "no_candidates"
