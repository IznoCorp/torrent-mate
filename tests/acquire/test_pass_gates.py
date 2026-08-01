"""R6: Season cutoff fallback — re-enqueue missing episodes, set fallback_episodes.

Tests for the :meth:`PassGatesMixin._apply_cutoff_gate` season branch
and :meth:`PassGatesMixin._fallback_season`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.cadence import Cadence, CadenceTier
from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import SeasonFellBackToEpisodes
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


# Clock pinned so the cutoff math is deterministic. The items below are
# enqueued exactly at the 30d cutoff edge (ENQUEUED_CUTOFF), making them
# eligible for the cutoff gate.
_NOW = 2_000_000
_ENQUEUED_CUTOFF = _NOW - (30 * 24 * 3600)  # exactly 30d → past cutoff


def _canon_cadence() -> Cadence:
    """Return the canonical Hot/Warm/Cold/30d cadence (same as test_service_cadence)."""
    return Cadence(
        tiers=(
            CadenceTier(max_age_s=72 * 3600, interval_s=2 * 3600),  # Hot
            CadenceTier(max_age_s=14 * 24 * 3600, interval_s=86400),  # Warm
            CadenceTier(max_age_s=30 * 24 * 3600, interval_s=7 * 86400),  # Cold
        ),
        cutoff_s=30 * 24 * 3600,
    )


def _season_item(followed_id: int = 1, season: int = 3) -> WantedItem:
    """Minimal pending season WantedItem at the cutoff edge."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=99),
        kind="season",
        status="pending",
        enqueued_at=_ENQUEUED_CUTOFF,
        followed_id=followed_id,
        season=season,
        episode=None,
        attempts=0,
    )


# ---------------------------------------------------------------------------
# R6: Season Cutoff Fallback tests
# ---------------------------------------------------------------------------


def test_season_cutoff_falls_back_to_episodes(store: ConcreteAcquireStore) -> None:
    """R6: season past cutoff → fallback_episodes + re-enqueue missing eps.

    When a season wanted is past its cadence cutoff, the gate transitions
    the season row to ``fallback_episodes``, re-enqueues the aired episodes
    individually, and emits ``SeasonFellBackToEpisodes``.
    """
    # Create the parent followed series so the FK resolves.
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=99),
            title="Test Show",
            added_at=1,
        )
    )

    # Seed the aired catalog with 8 episodes in season 3.
    episodes = [(3, i, f"E{i:02d}", f"2024-01-{i:02d}") for i in range(1, 9)]
    store.aired.replace_for_followed(1, episodes, now=_NOW)

    # Add the season wanted item and capture the real SQLite-assigned rowid.
    season_wid = store.wanted.add(_season_item())

    config = MagicMock()
    config.acquire = AcquireConfig()
    event_bus = MagicMock()

    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=MagicMock(),
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )

    # The search pass runs the cutoff gate — it has cadence_gates which include cutoff.
    with patch("personalscraper.acquire.service.time.time", return_value=_NOW):
        svc.run_search()

    # The season row must be in fallback_episodes status.
    season_after = store.wanted.get(season_wid)
    assert season_after is not None
    assert season_after.status == "fallback_episodes", f"expected fallback_episodes, got {season_after.status!r}"

    # 8 new episode wanteds must have been enqueued (one per aired ep).
    pending = store.wanted.list_pending()
    episode_pending = [i for i in pending if i.kind == "episode" and i.season == 3]
    assert len(episode_pending) == 8, f"expected 8 re-enqueued episodes, got {len(episode_pending)}"

    # SeasonFellBackToEpisodes must have been emitted.
    fallback_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonFellBackToEpisodes)]
    assert len(fallback_calls) >= 1, "SeasonFellBackToEpisodes must be emitted"
    emitted = fallback_calls[0][0][0]
    assert emitted.season_wanted_id == season_wid
    assert emitted.season == 3
    assert emitted.reenqueued_count == 8


def test_season_fallback_reenqueues_exact_missing_count(store: ConcreteAcquireStore) -> None:
    """R6: reenqueued_count matches the aired episode count.

    Prove the count in the emitted event matches the number of aired
    episodes in the catalog.
    """
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=99),
            title="Test Show",
            added_at=1,
        )
    )

    # Only 5 aired episodes in season 2.
    episodes = [(2, i, f"E{i:02d}", f"2024-01-{i:02d}") for i in range(1, 6)]
    store.aired.replace_for_followed(1, episodes, now=_NOW)

    store.wanted.add(_season_item(season=2))

    config = MagicMock()
    config.acquire = AcquireConfig()
    event_bus = MagicMock()

    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=MagicMock(),
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )

    with patch("personalscraper.acquire.service.time.time", return_value=_NOW):
        svc.run_search()

    fallback_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonFellBackToEpisodes)]
    assert len(fallback_calls) >= 1
    emitted = fallback_calls[0][0][0]
    assert emitted.reenqueued_count == 5, f"expected reenqueued_count=5, got {emitted.reenqueued_count}"

    # Verify the re-enqueued episodes have exactly the 5 episode numbers.
    pending = store.wanted.list_pending()
    episode_pending = [i for i in pending if i.kind == "episode" and i.season == 2]
    assert len(episode_pending) == 5
    reenqueued_numbers = sorted(i.episode for i in episode_pending if i.episode is not None)
    assert reenqueued_numbers == [1, 2, 3, 4, 5]


def test_season_fallback_not_triggered_for_episode(store: ConcreteAcquireStore) -> None:
    """R6 guard: an episode past cutoff still abandons normally, not via fallback."""
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=99),
            title="Test Show",
            added_at=1,
        )
    )

    episode_item = WantedItem(
        media_ref=MediaRef(tvdb_id=99),
        kind="episode",
        status="pending",
        enqueued_at=_ENQUEUED_CUTOFF,
        followed_id=1,
        season=3,
        episode=5,
        attempts=0,
    )
    ep_wid = store.wanted.add(episode_item)

    config = MagicMock()
    config.acquire = AcquireConfig()
    event_bus = MagicMock()

    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=MagicMock(),
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )

    with patch("personalscraper.acquire.service.time.time", return_value=_NOW):
        svc.run_search()

    # Episode should be abandoned, not fallback_episodes.
    after = store.wanted.get(ep_wid)
    assert after is not None
    assert after.status == "abandoned", f"episode past cutoff must be abandoned, got {after.status!r}"

    # No SeasonFellBackToEpisodes should have been emitted.
    fallback_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonFellBackToEpisodes)]
    assert len(fallback_calls) == 0, "episode cutoff must not trigger season fallback"
