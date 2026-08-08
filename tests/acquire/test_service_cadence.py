"""Tests for the cadence-aware gates of both AcquisitionService passes (criterion 7).

Since the acq-states search/grab split the two gates live in different places:

- the CUTOFF (30 days) is applied by BOTH passes before claiming — it ages an
  item out of the queue whatever it is waiting for;
- the CADENCE tier interval belongs to ``run_search`` ALONE. It spaces the
  re-verification of an episode the trackers do not have yet; an item a search
  already concluded takeable is grabbed at the next tick regardless of its tier
  (re-gating it there would strand a known-available item for hours).

The clock is pinned by patching ``personalscraper.acquire.service.time.time``
(the service computes ``now = int(time.time())``); patching the builtin ``int``
would also corrupt the stale-threshold arithmetic, so the time function is the
correct seam (matches the precedent in ``test_service.py`` §11d).
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.cadence import Cadence, CadenceTier
from personalscraper.acquire.desired import cadence_to_json
from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.acquire.orchestrator import SearchVerdict
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


def _available_item(enqueued_at: int, last_search_at: int | None = None, followed_id: int = 1) -> WantedItem:
    """Build an ``available`` episode WantedItem — the GRAB pass's input.

    Same row as :func:`_pending_item` one status apart, so a gate assertion can
    be compared between the two passes without any other variable moving.
    """
    return replace(
        _pending_item(enqueued_at, last_search_at, followed_id),
        status="available",
        last_search_outcome="available",
        last_search_found=3,
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
    available: list[WantedItem] | None = None,
) -> tuple[AcquisitionService, MagicMock, MagicMock, MagicMock]:
    """Build a minimal AcquisitionService with a stubbed store, orchestrator, bus, config.

    Args:
        pending: Rows ``list_pending()`` returns — the SEARCH pass's queue.
        stale: Rows ``list_stale_searching()`` returns (both passes sweep them).
        available: Rows ``list_available()`` returns — the GRAB pass's queue.

    Returns:
        The service and its stubbed ``(store, orchestrator, bus)``.
    """
    store = MagicMock()
    store.wanted.list_pending.return_value = pending
    store.wanted.list_available.return_value = available or []
    store.wanted.list_stale_searching.return_value = stale or []
    store.wanted.claim_for_search.return_value = True
    store.wanted.claim_for_grab.return_value = True
    store.wanted.get.return_value = (available or pending or [None])[0]
    store.follow.get.return_value = None  # no FollowedSeries override → global cadence

    orchestrator = MagicMock()
    orchestrator.grab.return_value = MagicMock(disposition="success", info_hash="abc123")

    bus = MagicMock()
    config = _make_config()

    svc = AcquisitionService(store=store, orchestrator=orchestrator, event_bus=bus, config=config)
    return svc, store, orchestrator, bus


def test_grab_pass_ignores_cadence_and_claims_via_claim_for_grab() -> None:
    """A not-yet-due AVAILABLE item is still claimed — by claim_for_grab (no cadence gate).

    Was ``test_not_due_item_is_skipped_no_claim``: the cadence skip moved to
    ``run_search`` (covered below), and its counterpart here is the guarantee
    that the grab pass does NOT re-apply it. Also pins WHICH claim the pass
    uses: ``claim_for_grab`` matches ``status='available'``, so calling
    ``claim_for_search`` instead would silently no-op on every available row.
    """
    item = _available_item(enqueued_at=ENQUEUED_RECENT, last_search_at=NOW - 1800)
    svc, store, orchestrator, _bus = _make_service([], available=[item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_grab.assert_called_once_with(10, NOW)
    store.wanted.claim_for_search.assert_not_called()
    orchestrator.grab.assert_called_once()
    assert summary.grabbed == 1
    assert summary.skipped == 0


def test_grab_pass_recovers_a_stale_searching_row_via_claim_for_search() -> None:
    """A stale 'searching' row is reclaimed ATOMICALLY, then claimed by claim_for_search.

    Was ``test_due_item_proceeds_to_claim``: « a due item proceeds to claim »
    now splits by queue. The available queue is covered above; this pins the
    OTHER claim path — the sweep recovers the orphan to 'pending' (the only
    status ``claim_for_search`` matches), so the row is recovered instead of
    skipped forever.

    The recovery goes through ``reclaim_stale_searching`` (one rowcount-gated
    UPDATE) rather than a blind ``set_status``: the row was listed at the top of
    the pass, so an unguarded write reverts whatever a concurrent runner did in
    between (PR #320 review, F-B2).
    """
    stale = replace(_pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=NOW - 7200), status="searching")
    svc, store, orchestrator, _bus = _make_service([], stale=[stale])
    store.wanted.reclaim_stale_searching.return_value = True
    store.wanted.get.return_value = replace(stale, status="searching", attempts=1)

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.reclaim_stale_searching.assert_called_once_with(10, NOW - 3600)
    store.wanted.set_status.assert_not_called()
    store.wanted.claim_for_search.assert_called_once_with(10, NOW)
    store.wanted.claim_for_grab.assert_not_called()
    assert summary.grabbed == 1


def test_grab_pass_skips_a_stale_row_whose_recovery_is_lost() -> None:
    """Losing the atomic recovery skips the row — never a blind overwrite.

    A concurrent runner grabbed the row (or re-claimed it) between the pass's
    listing and this item's turn: ``reclaim_stale_searching`` returns ``False``
    and the item is skipped, with NO claim and NO status write of our own
    (PR #320 review, F-B2).
    """
    stale = replace(_pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=NOW - 7200), status="searching")
    svc, store, orchestrator, _bus = _make_service([], stale=[stale])
    store.wanted.reclaim_stale_searching.return_value = False

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_not_called()
    store.wanted.claim_for_grab.assert_not_called()
    store.wanted.set_status.assert_not_called()
    orchestrator.grab.assert_not_called()
    assert summary.skipped == 1


def test_cutoff_item_abandoned_no_claim() -> None:
    """Past-cutoff available item → set_status('abandoned'), WantedAbandoned emitted, no claim.

    The cutoff is the one gate the GRAB pass keeps: it bounds infinite retries
    on an item the client keeps refusing.
    """
    item = _available_item(enqueued_at=ENQUEUED_CUTOFF, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([], available=[item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_grab.assert_not_called()
    store.wanted.claim_for_search.assert_not_called()
    store.wanted.set_status.assert_called_once_with(10, "abandoned")
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedAbandoned)
    assert emitted.reason == "cutoff_reached"
    assert summary.abandoned == 1


def test_cutoff_abandoned_before_grab() -> None:
    """Cutoff abandon happens BEFORE any grab attempt — orchestrator.grab not called."""
    item = _available_item(enqueued_at=ENQUEUED_CUTOFF)
    svc, store, orchestrator, bus = _make_service([], available=[item])

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
    item = _available_item(enqueued_at=NOW - 3 * 3600, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([], available=[item])
    store.follow.get.return_value = series

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_grab.assert_not_called()
    store.wanted.set_status.assert_called_once_with(10, "abandoned")
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedAbandoned)
    assert emitted.reason == "cutoff_reached"
    assert summary.abandoned == 1


def test_malformed_per_series_cadence_logs_series_and_uses_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A malformed per-series cadence_json logs the series identity, then uses the default.

    F-L (silent-failure FINDING 1): the call site logs
    ``acquire.service.cadence_override_dropped`` WITH the owning series so the
    drop is attributable, AND the item still proceeds under the GLOBAL default
    (the malformed override is fail-soft, not abandoning the item).

    Mutation-proof: fails if the call site doesn't log the drop (no event in
    ``caplog.text``), OR if the malformed override is not fail-soft to the
    default (the item would not be grabbed / claim never called).
    """
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=99),
        title="Broken Cadence Series",
        added_at=NOW,
        cadence_json='{"broken',  # malformed → cadence_from_json returns None
        id=1,
    )
    # RECENT item (Hot tier) → far inside the global default's 30d cutoff.
    item = _available_item(enqueued_at=ENQUEUED_RECENT, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([], available=[item])
    store.follow.get.return_value = series

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    # The drop is logged with the series identity (structlog event name in caplog.text).
    assert "acquire.service.cadence_override_dropped" in caplog.text

    # Fail-soft to the global default: the item proceeds (claim + grab), not abandoned.
    store.wanted.claim_for_grab.assert_called_once()
    assert summary.grabbed == 1
    assert summary.abandoned == 0


# ---------------------------------------------------------------------------
# The SEARCH pass carries the SAME gates (acq-states phase 2)
# ---------------------------------------------------------------------------
#
# Cadence belongs to the search pass: it is what spaces the re-verification of
# an episode the trackers do not have yet. The grab pass takes a known-available
# item at its next tick regardless of cadence. If run_search ever loses these
# gates, every pass would re-query every tracker for the whole backlog
# (NE-DOIT-PAS-8, tracker burst).


def test_search_pass_skips_a_not_due_item_without_claiming() -> None:
    """run_search honours the cadence gate: not-due → skipped, no claim, no search."""
    item = _pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=NOW - 1800)
    svc, store, orchestrator, _bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run_search()

    store.wanted.claim_for_search.assert_not_called()
    orchestrator.search.assert_not_called()
    # A not-due item stays pending — the skip path must never write status.
    store.wanted.set_status.assert_not_called()
    store.wanted.record_search_outcome.assert_not_called()
    assert summary.skipped == 1
    assert summary.available == 0


def test_search_pass_ages_out_a_past_cutoff_item_without_searching() -> None:
    """run_search applies the cutoff: past-cutoff → abandoned + emitted, never searched."""
    item = _pending_item(enqueued_at=ENQUEUED_CUTOFF, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run_search()

    store.wanted.claim_for_search.assert_not_called()
    orchestrator.search.assert_not_called()
    store.wanted.set_status.assert_called_once_with(10, "abandoned")
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedAbandoned)
    assert emitted.reason == "cutoff_reached"
    assert summary.abandoned == 1


def test_search_pass_claims_a_due_item() -> None:
    """A due item (never searched, Hot tier) IS claimed and searched by run_search."""
    item = _pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=None)
    svc, store, orchestrator, _bus = _make_service([item])
    orchestrator.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=2,
    )

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run_search()

    store.wanted.claim_for_search.assert_called_once()
    orchestrator.search.assert_called_once()
    store.wanted.record_search_outcome.assert_called_once_with(10, "available", 2, best=None)
    store.wanted.set_status.assert_called_once_with(10, "available")
    assert summary.available == 1
