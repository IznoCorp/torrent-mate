"""E2E roundtrip: cross-seed injection → SEED_PURE tag → ingest skip.

Tests the full cross-seed lifecycle with faked tracker registry, transport,
and torrent client — no real network, no real qBittorrent, no 14 GB fixtures.

Covers ACC-7: injected cross-seed survives ingest skip, and watcher predicate
excludes SEED_PURE-tagged hashes.

The ingest-skip assertion is tag-based (not full pipeline):
``ingest.py:416-432`` is an unconditional ``SEED_PURE in torrent_tags → skip``
check — unconditionally skipping every torrent tagged SEED_PURE.  Verifying
that the tag is applied to the injected torrent is equivalent to verifying
the ingest step will skip it.  This avoids plumbing a full ``ingest_step``
with a fake TorrentItem and content-path resolution, which would be
disproportionate for an E2E test targeting the cross-seed→tag contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from personalscraper.acquire.events import CrossSeedInjected
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.acquire.watcher import (
    WatcherDecision,
    WatcherInput,
    WatcherService,
    WatcherState,
)
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.watch_seed import WatchConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.tags import SEED_PURE
from tests.integration.acquire.test_cross_seed_service import (
    _SOURCE_HASH,
    _TRACKER_LACALE,
    _TRACKER_TORR9,
    FakeTorrentClient,
    FakeTracker,
    FakeTransport,
    _build_service,
    _candidate_result,
    _derive_injected_hash,
    _source_item,
    make_config,
    make_registry,
    make_torrent_bytes,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# Shared fixtures (e2e-level — duplicate of integration fixtures for isolation)
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> "Iterator[ConcreteAcquireStore]":
    """Yield a real :class:`ConcreteAcquireStore` on ``tmp_path/acquire.db``.

    Mirrors the integration-level fixture in
    ``tests/integration/acquire/test_cross_seed_service.py`` so the e2e test
    does not depend on cross-test-module fixture imports.
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestCrossSeedRoundtrip:
    """ACC-7: injected cross-seed → SEED_PURE tag → ingest skips it."""

    def test_cross_seed_injection_survives_ingest_skip(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Full cross-seed roundtrip with fakes: inject → verify → tag → obligation.

        1. Source torrent exists in the fake client's completed list.
        2. Fake registry returns one matching candidate.
        3. ``CrossSeedService.check()`` injects, verifies, tags SEED_PURE,
           and writes a SeedObligation.
        4. The injected torrent carries the SEED_PURE tag.
        5. A SeedObligation is persisted via ``store.seed.find_active_under``.
        6. ``ingest.py:416-432`` unconditionally skips SEED_PURE-tagged torrents
           — the tag is the contract; a fake-ingest assertion is not needed.
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        # Fake torrent client seeded with one completed source item.
        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Fake transport returning the matching .torrent bytes.
        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

        # Fake tracker returning one candidate.
        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: FakeTracker(
                    provider=_TRACKER_TORR9,
                    transport=fake_transport,
                    results=[_candidate_result(download_url=candidate_url)],
                ),
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        injected_events: list[CrossSeedInjected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedInjected, lambda e: injected_events.append(e))

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry, event_bus=bus)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Injection happened.
        assert result.injected == [injected_hash]
        assert result.rejected == []
        assert result.skipped is False

        # SEED_PURE tag was applied on the injected torrent.
        assert SEED_PURE in fake_client.tags_added.get(injected_hash, set()), (
            "SEED_PURE tag must be on the injected torrent — ingest.py:416-432 skips unconditionally on this tag"
        )

        # SeedObligation was persisted.
        obligations = store.seed.find_active_under(Path(item.save_path))
        assert any(o.source_tracker == _TRACKER_TORR9 for o in obligations), (
            f"Expected a SeedObligation with source_tracker={_TRACKER_TORR9!r} "
            f"under {item.save_path!r}, got {obligations!r}"
        )

        # CrossSeedInjected event was emitted.
        assert len(injected_events) == 1
        assert injected_events[0].info_hash == injected_hash

    def test_watcher_predicate_ignores_seed_pure(self) -> None:
        """Watcher work predicate (W7) excludes SEED_PURE-tagged torrents.

        When a completed hash is present in ``seed_pure_hashes``, the watcher's
        work-set computation subtracts it, producing an empty ``cross_seed_new``
        set → no FIRE_RUN → IDLE.

        ``WatchConfig(enabled=True)`` is used because the default
        ``enabled=False`` returns IDLE vacuously — a disabled service has no
        interesting predicates to test.
        """
        # -- Arrange ----------------------------------------------------------
        svc = WatcherService(WatchConfig(enabled=True))
        inp = WatcherInput(
            completed_hashes=frozenset({"abc123"}),
            ingested_hashes=frozenset(),
            seed_pure_hashes=frozenset({"abc123"}),  # same hash is SEED_PURE
            sentinel_present=False,
            pipeline_lock_held=False,
            now=1_000_000.0,
        )

        # -- Act --------------------------------------------------------------
        now = 1_000_000.0
        # Safety net fires when last_successful_run_at is None or too old.
        # Pin last_successful_run_at to a recent value so it doesn't trigger.
        state = WatcherState(last_successful_run_at=now - 3600.0)
        out = svc.evaluate(inp, state)

        # -- Assert -----------------------------------------------------------
        # work_set = completed - ingested - seed_pure = {} → cross_seed_new = {}
        # No cross-seed candidates, no sentinel, safety-net window is fresh → IDLE.
        assert out.decision == WatcherDecision.IDLE, (
            f"Expected IDLE when the only completed hash is SEED_PURE, "
            f"got {out.decision.value!r} with reason={out.run_reason!r}"
        )
        assert out.cross_seed_hashes == []
