"""Test-first: the search pass (run_search) states availability; it never downloads.

These tests INTENTIONALLY FAIL today (ImportError / AttributeError) — the
``SearchVerdict``, ``SearchRunSummary``, and ``run_search`` API do not exist
yet. Sub-phase 2.3 implements them. Do NOT mark xfail/skip.

Design: contract_phase2.md § orchestrator.search → SearchVerdict (no
torrent-client use, no add, no emit) and § service.run_search →
SearchRunSummary.  The plan is phase-02-search-grab-split.md §2.1.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

# ---------------------------------------------------------------------------
# Reuse the house patterns from test_service.py.
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


# Pinned service clock: 1h after the items' enqueued_at (1_700_000_000). With
# the default Hot/Warm/Cold/30d cadence this puts every _pending_item in the Hot
# tier (age 1h < 72h) and well within the 30d cutoff, so a fresh row
# (last_search_at is None) is DUE immediately. Without the pin the wall clock is
# years past the cutoff and every item would age out before being searched.
_PINNED_NOW = 1_700_003_600  # enqueued_at + 3600s


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin ``service.time.time`` so the fixture rows stay due."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


def _pending_item(tvdb_id: int = 99) -> WantedItem:
    """Minimal pending WantedItem — mirrors test_service._pending_item."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="movie",
        status="pending",
        enqueued_at=1_700_000_000,
    )


def _takeable_result(
    provider: str = "lacale",
    info_hash: str = "aaaa1234",
    seeders: int = 50,
) -> TrackerResult:
    """A tracker result that will survive hard-filter + dedup + ranking."""
    return TrackerResult(
        provider=provider,
        tracker_id="t1",
        title="Inception 2010 MULTi 1080p BluRay x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=info_hash,
        download_url=f"https://{provider}.test/torrent/1",
    )


def _service(store: ConcreteAcquireStore, orchestrator: GrabOrchestrator) -> AcquisitionService:
    """Build a service with a (mock) event_bus — mirrors test_service._service."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    )


# ---------------------------------------------------------------------------
# THE tests — intentionally failing until 2.3 implements the contract.
# ---------------------------------------------------------------------------


def test_search_pass_adds_no_torrent(store: ConcreteAcquireStore) -> None:
    """The search pass states availability; it never downloads.

    Separating search from grab is the whole point: while they were one atomic
    operation, « À récupérer » existed for milliseconds inside a single function
    call and the operator could never see what was available but not yet taken.
    """
    store.wanted.add(_pending_item())

    # A fake torrent client that RECORDS every add() call. Wire it into the
    # mock orchestrator so if run_search() ever reaches through to
    # orchestrator._torrent_client.add(), the spy catches it.
    fake_client = MagicMock()

    orch = MagicMock(spec=GrabOrchestrator)
    orch._torrent_client = fake_client
    orch.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=3,
        chosen=_takeable_result(),
    )

    service = _service(store, orch)
    summary = service.run_search()

    # The flagship invariant: the torrent client was NEVER asked to add.
    fake_client.add.assert_not_called()

    # The item is now known-available (not still pending, not grabbed).
    assert summary.available == 1
    pending = store.wanted.list_pending()
    assert not any(i.media_ref.tvdb_id == 99 for i in pending), "a takeable item must leave the pending queue"

    available = store.wanted.list_available()
    assert len(available) == 1
    assert available[0].status == "available"
    assert available[0].last_search_outcome == "available"
    assert available[0].last_search_found == 3


def test_search_pass_records_available_verdict(store: ConcreteAcquireStore) -> None:
    """After run_search on a takeable item, the store row carries the verdict.

    The persisted triple (status, last_search_outcome, last_search_found)
    must match the contract: status='available', outcome='available',
    found == number of takeable candidates.
    """
    rowid = store.wanted.add(_pending_item())

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=5,
        chosen=_takeable_result(info_hash="bbbb5678"),
    )

    service = _service(store, orch)
    summary = service.run_search()

    assert summary.available == 1

    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "available", f"expected status='available' after a takeable search; got {item.status!r}"
    assert item.last_search_outcome == "available"
    assert item.last_search_found == 5, (
        f"found must equal the count passed by the orchestrator; got {item.last_search_found}"
    )


def test_search_pass_works_without_torrent_client(store: ConcreteAcquireStore) -> None:
    """Service constructed with torrent_client=None still runs run_search successfully.

    The search pass must not require the client — the orchestrator's search()
    chain (build_search_query → search_candidates → filter → dedup → rank)
    never touches it.  A service built without one must complete the pass and
    persist the verdict.
    """
    store.wanted.add(_pending_item())

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=1,
        chosen=_takeable_result(),
    )

    service = _service(store, orch)
    # Must NOT raise — the search pass has no dependency on the torrent client.
    summary = service.run_search()

    assert summary.available == 1
    available = store.wanted.list_available()
    assert len(available) == 1
