"""Historical rows of a REMOVED tracker must stay readable and honoured.

When a tracker is decommissioned, its client, its ``ProviderName`` member, its
activation entries and its ``tracker.json5`` provider block all disappear — but
the rows it left in ``acquire.db`` do not. A seed obligation is a promise made
to a tracker: it must keep vetoing a deletion until its seed time is served,
even though nothing in the code knows that tracker's name any more.

These tests pin that the whole read path stays **string-based and fail-soft**
for an unknown tracker name (here the decommissioned ``"torr9"``):

- the store round-trips ``source_tracker`` / ``tracker_name`` / ``tracker``
  verbatim — no enum coercion anywhere, so a removed member cannot raise
  ``ValueError``;
- :class:`DeleteAuthority` still VETOes an unmet historical obligation (the
  floors live ON the row, not in config) and still ALLOWs a served one;
- the dispatch-time writer degrades to a logged ``tracker-unresolved`` MISS
  instead of crashing when a live torrent still carries the removed tracker's
  tag;
- the grab-time writer skips silently when the tracker has no config entry;
- ``ratio_state`` and ``cross_seed_history`` rows keyed on the removed tracker
  remain readable and inert.

Where the surviving rows actually are (measured on the operator's
``.data/acquire.db`` on 2026-07-28, so the tests target the real risk rather
than an assumed one):

- ``cross_seed_history`` — **6 torr9 rows** (alongside 6 c411). This is the
  only table holding real torr9 data, and it was the one table these tests
  originally missed.
- ``seed_obligation`` — 14 rows, **all c411, zero torr9**.
- ``ratio_state`` — empty.

The obligation and ratio tests therefore pin the contract *prospectively*: no
torr9 row exists in those tables today, but the guarantee they encode (a
promise made to a tracker outlives that tracker's code) is what must hold the
next time a tracker is decommissioned while holding live obligations.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority, build_delete_authority
from personalscraper.acquire.domain import RatioState, SeedObligation
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._contracts import ProviderName
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import TrackerConfig, TrackerEconomyConfig, TrackerProviderConfig
from personalscraper.core.delete_permit import ALLOW

#: The decommissioned tracker whose rows survive in production.
_REMOVED = "torr9"

_LIVE_ECONOMY = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time=259_200)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real lazy acquire store on a temp acquire.db, closed afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A :class:`ConcreteAcquireStore` (opens on first sub-store access).
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _historical_obligation(dispatched_path: str, *, min_seed_time_s: int, added_at: int) -> SeedObligation:
    """Build a seed obligation left behind by the removed tracker.

    Args:
        dispatched_path: Absolute path the obligation guards.
        min_seed_time_s: Seeding floor stored ON the row (not read from config).
        added_at: Unix epoch seconds when the obligation was recorded.

    Returns:
        A frozen :class:`SeedObligation` whose ``source_tracker`` no longer
        matches any configured tracker.
    """
    return SeedObligation(
        info_hash="dead" * 10,
        source_tracker=_REMOVED,
        min_seed_time_s=min_seed_time_s,
        min_ratio=1.0,
        added_at=added_at,
        dispatched_path=dispatched_path,
    )


def _torrent_item(*, name: str, size_bytes: int, tags: list[str]) -> MagicMock:
    """Build a torrent item with the REAL client surface (hash/name/size_bytes/tags)."""
    item = MagicMock()
    item.hash = "dead" * 10
    item.name = name
    item.size_bytes = size_bytes
    item.tags = tags
    return item


def test_enum_no_longer_carries_the_removed_tracker() -> None:
    """Precondition: the tracker is really gone from ``ProviderName``.

    Everything below is only meaningful because coercing the stored name would
    now raise — which is exactly why no read path may coerce it.
    """
    assert not hasattr(ProviderName, "TORR9")
    with pytest.raises(ValueError, match=_REMOVED):
        ProviderName(_REMOVED)


def test_obligation_round_trips_verbatim(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """A historical obligation is stored and read back with its tracker name intact."""
    guarded = tmp_path / "library" / "Old.Film.mkv"
    store.seed.add(_historical_obligation(str(guarded), min_seed_time_s=259_200, added_at=int(time.time())))

    by_hash = store.seed.find_active_by_hash("dead" * 10)
    assert by_hash is not None
    assert by_hash.source_tracker == _REMOVED

    under = store.seed.find_active_under(guarded)
    assert [o.source_tracker for o in under] == [_REMOVED]


def test_unmet_historical_obligation_still_vetoes_deletion(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """The promise outlives the client: an unserved obligation still blocks deletion."""
    guarded = tmp_path / "library" / "Old.Film.mkv"
    guarded.parent.mkdir(parents=True)
    guarded.write_bytes(b"x")
    store.seed.add(_historical_obligation(str(guarded), min_seed_time_s=999_999, added_at=int(time.time())))

    authority = build_delete_authority(store=store, torrent_client=None, economy={})
    decision = authority.may_delete(guarded)

    assert decision is not ALLOW
    assert _REMOVED in decision.reason


def test_served_historical_obligation_allows_deletion(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Once the stored seed time is served, the historical obligation stops vetoing."""
    guarded = tmp_path / "library" / "Old.Film.mkv"
    guarded.parent.mkdir(parents=True)
    guarded.write_bytes(b"x")
    store.seed.add(
        _historical_obligation(str(guarded), min_seed_time_s=60, added_at=int(time.time()) - 3_600),
    )

    authority = build_delete_authority(store=store, torrent_client=None, economy={})

    assert authority.may_delete(guarded) is ALLOW


def test_record_dispatch_degrades_to_a_logged_miss(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A live torrent still tagged with the removed tracker yields a MISS, not a crash."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    item = _torrent_item(name="Film.mkv", size_bytes=512, tags=[_REMOVED])
    client = MagicMock()
    client.get_completed.return_value = [item]
    client.is_seeding.return_value = True

    authority = DeleteAuthority(store=store, torrent_client=client, economy={"c411": _LIVE_ECONOMY})
    authority.record_dispatch(staging_source=staging, dispatched_dest=dest)

    # No obligation written (the tag resolves to no configured economy), and the
    # store was never even opened — the MISS returns before any write.
    assert store.seed.find_active_by_hash("dead" * 10) is None
    assert "tracker-unresolved" in caplog.text


def test_grab_obligation_writer_skips_the_removed_tracker(store: ConcreteAcquireStore) -> None:
    """The grab-time writer skips silently when the tracker has no config entry."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    config.tracker = TrackerConfig(
        providers={"c411": TrackerProviderConfig(enabled=True, economy=_LIVE_ECONOMY)},
        priority=["c411"],
    )
    service = AcquisitionService(
        store=store,
        orchestrator=MagicMock(),
        event_bus=MagicMock(),
        config=config,
    )

    service._record_seed_obligation("beef" * 10, _REMOVED)  # must not raise

    assert store.seed.find_active_by_hash("beef" * 10) is None


def test_historical_cross_seed_row_stays_readable_and_inert(store: ConcreteAcquireStore) -> None:
    """A ``cross_seed_history`` row from the removed tracker reads back and affects nobody.

    This is the ONE table that actually holds torr9 rows in production (6 of
    them). ``tracker`` is only ever a bound parameter in a ``WHERE`` / ``INSERT``
    — never SELECTed back out and never coerced to ``ProviderName`` — so the row
    stays readable under its own name, and a live tracker's dedup lookup for the
    same source hash is unaffected by it.
    """
    source_hash = "cafe" * 10

    store.cross_seed.record_search(source_hash, _REMOVED)

    # Readable under the removed tracker's own name.
    assert store.cross_seed.was_searched_recently(source_hash, _REMOVED, days=30) is True
    # Inert for everyone else: the historical row must not make a live tracker
    # look "already searched" and suppress a legitimate cross-seed search.
    assert store.cross_seed.was_searched_recently(source_hash, "c411", days=30) is False


def test_historical_ratio_state_row_stays_readable(store: ConcreteAcquireStore) -> None:
    """``ratio_state`` is keyed by a plain tracker name — a removed one still reads back."""
    store.ratio.upsert(
        RatioState(
            tracker_name=_REMOVED,
            observed_ratio=1.8,
            accumulated_seed_time_s=500_000,
            hnr_count=0,
            updated_at=int(time.time()),
        )
    )

    row = store.ratio.get(_REMOVED)

    assert row is not None
    assert row.tracker_name == _REMOVED
    assert row.observed_ratio == 1.8
