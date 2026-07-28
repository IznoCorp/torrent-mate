"""A terminal ``tracker_auth`` verdict needs TWO consecutive all-auth searches.

Making the ``auth`` taxon reachable (D4) armed a live blast radius: the verdict
is terminal, so the FIRST search pass that finds every tracker's key broken
would abandon every row it walks. During an ordinary passkey rotation — the
window where all keys really are invalid at once — that is the whole queue
abandoned in one pass, on a condition that resolves itself minutes later.

The guard is a debounce, not a softening of the verdict: an unfixable failure
must still terminate, it just has to be observed twice. The first all-auth
search RECORDS ``tracker_auth`` as the row's verdict but leaves it 'pending';
only a second consecutive one abandons. Any other verdict in between resets the
count, because the row's ``last_search_outcome`` is the counter — no new column,
no new clock.

These tests pin all three transitions: first occurrence, second occurrence, and
the reset.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.acquire.orchestrator import SearchVerdict
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _pending_row(store: ConcreteAcquireStore) -> int:
    """Insert a plain queued row, due for its first search."""
    return store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=42),
            kind="movie",
            status="pending",
            enqueued_at=int(time.time()),
        )
    )


def _verdict(outcome: str) -> SearchVerdict:
    """Build the SearchVerdict the orchestrator returns for *outcome*."""
    disposition = {
        "tracker_auth": "terminal",
        "available": "available",
        "no_candidates": "not_found",
    }.get(outcome, "retryable")
    return SearchVerdict(disposition=disposition, outcome=outcome, found=None, chosen=None)  # type: ignore[arg-type]


def _service(store: ConcreteAcquireStore, bus: MagicMock) -> tuple[AcquisitionService, MagicMock]:
    """Build the search service over a real store and a scripted orchestrator."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    orchestrator = MagicMock()
    return (
        AcquisitionService(store=store, orchestrator=orchestrator, event_bus=bus, config=config),
        orchestrator,
    )


def _search_with(
    service: AcquisitionService,
    orchestrator: MagicMock,
    outcome: str,
    store: ConcreteAcquireStore,
) -> None:
    """Run ONE search pass that really reaches the orchestrator.

    Rewinds ``last_search_at`` first: consecutive passes in a test happen within
    the same second, and the cadence gate would skip every one after the first —
    the row would never be re-searched and every assertion below would pass
    vacuously. Rewinding is what the real clock does between two cron ticks.
    """
    store._conn.execute("UPDATE wanted SET last_search_at = ?", (int(time.time()) - 30 * 86_400,))
    store._conn.commit()
    orchestrator.search.return_value = _verdict(outcome)
    before = orchestrator.search.call_count
    service.run_search()
    assert orchestrator.search.call_count > before, "the pass must actually reach the orchestrator"


def _emitted_abandons(bus: MagicMock) -> list[object]:
    """Every ``WantedAbandoned`` the bus received."""
    return [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], WantedAbandoned)]


class TestFirstAllAuthVerdictDoesNotAbandon:
    """One broken-key search states the verdict but keeps the row queued."""

    def test_row_stays_pending_with_the_auth_verdict(self, store: ConcreteAcquireStore) -> None:
        """The evidence is recorded; the sentence is not passed yet."""
        rowid = _pending_row(store)
        bus = MagicMock()
        service, orchestrator = _service(store, bus)

        _search_with(service, orchestrator, "tracker_auth", store)

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "pending", "a single all-auth pass must not abandon"
        assert row.last_search_outcome == "tracker_auth", "the verdict is still recorded honestly"

    def test_no_abandon_event_on_the_first_occurrence(self, store: ConcreteAcquireStore) -> None:
        """No WantedAbandoned — nothing was abandoned."""
        _pending_row(store)
        bus = MagicMock()
        service, orchestrator = _service(store, bus)

        _search_with(service, orchestrator, "tracker_auth", store)

        assert _emitted_abandons(bus) == []


class TestSecondConsecutiveAllAuthAbandons:
    """The verdict is still terminal — it just has to be confirmed."""

    def test_row_is_abandoned(self, store: ConcreteAcquireStore) -> None:
        """Two consecutive all-auth searches: the key really is broken."""
        rowid = _pending_row(store)
        bus = MagicMock()
        service, orchestrator = _service(store, bus)

        _search_with(service, orchestrator, "tracker_auth", store)
        _search_with(service, orchestrator, "tracker_auth", store)

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "abandoned"
        assert row.last_search_outcome == "tracker_auth"

    def test_abandon_event_is_emitted_once(self, store: ConcreteAcquireStore) -> None:
        """The operator hears about it exactly once, on the confirming pass."""
        _pending_row(store)
        bus = MagicMock()
        service, orchestrator = _service(store, bus)

        _search_with(service, orchestrator, "tracker_auth", store)
        _search_with(service, orchestrator, "tracker_auth", store)

        abandons = _emitted_abandons(bus)
        assert len(abandons) == 1
        assert abandons[0].reason == "tracker_auth"  # type: ignore[attr-defined]


class TestAnInterveningVerdictResetsTheCount:
    """The counter is the row's own last verdict — recovery resets it."""

    @pytest.mark.parametrize("intervening", ["available", "no_candidates", "trackers_unavailable"])
    def test_a_non_auth_verdict_resets(self, store: ConcreteAcquireStore, intervening: str) -> None:
        """Auth → recovery → auth is TWO first occurrences, not a confirmation."""
        rowid = _pending_row(store)
        bus = MagicMock()
        service, orchestrator = _service(store, bus)

        _search_with(service, orchestrator, "tracker_auth", store)
        _search_with(service, orchestrator, intervening, store)
        # The row may now be 'available'; put it back in the search queue.
        store.wanted.set_status(rowid, "pending")
        _search_with(service, orchestrator, "tracker_auth", store)

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "pending", "the streak was broken — this is a first occurrence again"
        assert _emitted_abandons(bus) == []
