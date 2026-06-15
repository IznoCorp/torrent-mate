"""Tests for cadence-aware AcquisitionService._process_item (criterion 7).

The clock is pinned by patching ``personalscraper.acquire.service.time.time``
(the service computes ``now = int(time.time())``); patching the builtin ``int``
would also corrupt the stale-threshold arithmetic, so the time function is the
correct seam (matches the precedent in ``test_service.py`` §11d).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.acquire.cadence import Cadence, CadenceTier
from personalscraper.acquire.desired import cadence_to_json
from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.acquire.service import AcquisitionService
from personalscraper.core.identity import MediaRef

NOW = 2_000_000
ENQUEUED_RECENT = NOW - 3600  # 1h ago → Hot tier
ENQUEUED_CUTOFF = NOW - (30 * 24 * 3600)  # exactly 30d → past cutoff


def _canon_cadence() -> Cadence:
    """Return the canonical Hot/Warm/Cold/30d cadence used by these tests."""
    return Cadence(
        tiers=(
            CadenceTier(max_age_s=72 * 3600, interval_s=2 * 3600),  # Hot
            CadenceTier(max_age_s=14 * 24 * 3600, interval_s=86400),  # Warm
            CadenceTier(max_age_s=30 * 24 * 3600, interval_s=7 * 86400),  # Cold
        ),
        cutoff_s=30 * 24 * 3600,
    )


def _pending_item(enqueued_at: int, last_search_at: int | None = None, followed_id: int = 1) -> WantedItem:
    """Build a pending episode WantedItem with a known rowid for claim assertions."""
    return WantedItem(
        id=10,
        media_ref=MediaRef(tvdb_id=99),
        kind="episode",
        status="pending",
        enqueued_at=enqueued_at,
        followed_id=followed_id,
        season=1,
        episode=1,
        last_search_at=last_search_at,
        attempts=0,
    )


def _make_config() -> MagicMock:
    """Return a minimal config stub with the canonical cadence (Hot/Warm/Cold/30d)."""
    from personalscraper.conf.models.acquire import AcquireConfig

    config = MagicMock()
    config.acquire = AcquireConfig()  # default cadence — Hot/Warm/Cold/30d
    return config


def _make_service(
    pending: list[WantedItem],
    stale: list[WantedItem] | None = None,
) -> tuple[AcquisitionService, MagicMock, MagicMock, MagicMock]:
    """Build a minimal AcquisitionService with a stubbed store, orchestrator, bus, config."""
    store = MagicMock()
    store.wanted.list_pending.return_value = pending
    store.wanted.list_stale_searching.return_value = stale or []
    store.wanted.claim_for_search.return_value = True
    store.wanted.get.return_value = pending[0] if pending else None
    store.follow.get.return_value = None  # no FollowedSeries override → global cadence

    orchestrator = MagicMock()
    orchestrator.grab.return_value = MagicMock(disposition="success", info_hash="abc123")

    bus = MagicMock()
    config = _make_config()

    svc = AcquisitionService(store=store, orchestrator=orchestrator, event_bus=bus, config=config)
    return svc, store, orchestrator, bus


def test_not_due_item_is_skipped_no_claim() -> None:
    """A not-yet-due item (last_search_at 30min ago, Hot interval=2h) → skipped, no claim."""
    item = _pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=NOW - 1800)
    svc, store, orchestrator, bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_not_called()
    orchestrator.grab.assert_not_called()
    # A not-due item stays pending — the skip path must never write status (F-D).
    store.wanted.set_status.assert_not_called()
    assert summary.skipped == 1
    assert summary.grabbed == 0


def test_due_item_proceeds_to_claim() -> None:
    """A due item (last_search_at=None, Hot tier) → claim called, grab proceeds."""
    item = _pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([item])
    store.wanted.get.return_value = WantedItem(
        id=10,
        media_ref=MediaRef(tvdb_id=99),
        kind="episode",
        status="searching",
        enqueued_at=ENQUEUED_RECENT,
        followed_id=1,
        season=1,
        episode=1,
        attempts=1,
    )

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_called_once()
    assert summary.grabbed == 1


def test_cutoff_item_abandoned_no_claim() -> None:
    """Past-cutoff item → set_status('abandoned') called, WantedAbandoned emitted, no claim."""
    item = _pending_item(enqueued_at=ENQUEUED_CUTOFF, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_not_called()
    store.wanted.set_status.assert_called_once_with(10, "abandoned")
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedAbandoned)
    assert emitted.reason == "cutoff_reached"
    assert summary.abandoned == 1


def test_cutoff_abandoned_before_grab() -> None:
    """Cutoff abandon happens BEFORE any grab attempt — orchestrator.grab not called."""
    item = _pending_item(enqueued_at=ENQUEUED_CUTOFF)
    svc, store, orchestrator, bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        svc.run()

    orchestrator.grab.assert_not_called()


def test_per_series_cadence_override_abandons() -> None:
    """A per-series tight cutoff abandons an item the global default would keep.

    Proves ``service.py`` consults ``cadence_from_json(fs.cadence_json)`` via
    ``effective_cadence`` rather than the global default (F-F). The item is 3h
    old: WELL under the global-default 30d cutoff (which would keep it), but
    PAST the per-series 2h cutoff (which abandons it).

    Mutation-proof: if the service dropped the per-series override lookup, the
    global 30d default would keep the item — no abandon, no emit — and these
    asserts would fail.
    """
    # Per-series cadence: 1h Hot tier, 2h cutoff (valid: cutoff 7200 >= last tier 3600).
    per_series = Cadence(tiers=(CadenceTier(max_age_s=3600, interval_s=600),), cutoff_s=7200)
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=99),
        title="Override Series",
        added_at=NOW,
        cadence_json=cadence_to_json(per_series),
        id=1,
    )
    # 3h old → past the 2h per-series cutoff, but far under the global 30d cutoff.
    item = _pending_item(enqueued_at=NOW - 3 * 3600, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([item])
    store.follow.get.return_value = series

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_not_called()
    store.wanted.set_status.assert_called_once_with(10, "abandoned")
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedAbandoned)
    assert emitted.reason == "cutoff_reached"
    assert summary.abandoned == 1
