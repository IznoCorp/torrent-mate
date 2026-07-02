"""Integration tests for :class:`~personalscraper.acquire.cross_seed.CrossSeedService`.

Tests with faked tracker registry, transport, and torrent client covering the
10 planned cases (ACC-6). A real ``ConcreteAcquireStore`` on ``tmp_path`` and
real bencode for candidate ``.torrent`` bytes exercise ``parse_torrent_layout``
and ``structural_match`` without any parsing mocks.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.cross_seed import CrossSeedResult, CrossSeedService
from personalscraper.acquire.events import CrossSeedInjected, CrossSeedRejected
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._contracts import ApiError, MediaType, ProviderName
from personalscraper.api._units import ByteSize
from personalscraper.api.torrent._base import TorrentItem, TorrentSource
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import TrackerConfig, TrackerEconomyConfig, TrackerProviderConfig
from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.watch_seed import CrossSeedConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.tags import SEED_PURE
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# ---------------------------------------------------------------------------
# Bencode helpers — craft minimal valid .torrent bytes
# ---------------------------------------------------------------------------


def _bencode_str(s: bytes) -> bytes:
    """Encode a byte string in bencode format: ``<len>:<bytes>``."""
    return str(len(s)).encode() + b":" + s


def _bencode_int(i: int) -> bytes:
    """Encode an integer in bencode format: ``i<digits>e``."""
    return b"i" + str(i).encode() + b"e"


def _bencode_dict_items(items: list[tuple[bytes, bytes]]) -> bytes:
    """Encode a dict as ``d<key><value>...e`` from ordered pairs."""
    parts = [b"d"]
    for k, v in items:
        parts.append(_bencode_str(k))
        parts.append(v)
    parts.append(b"e")
    return b"".join(parts)


def _bencode_list(items: list[bytes]) -> bytes:
    """Encode a list as ``l<item>...e``."""
    parts = [b"l"]
    parts.extend(items)
    parts.append(b"e")
    return b"".join(parts)


def make_torrent_bytes(
    name: str = "movie",
    files: list[tuple[str, int]] | None = None,
    piece_length: int = 262144,
    meta_version: int | None = None,
) -> bytes:
    """Craft a minimal valid ``.torrent`` file as bencoded bytes.

    Produces a structurally valid bencode that both
    :func:`~personalscraper.api.torrent._base._bencode_info_hash` and
    :func:`~personalscraper.api.torrent._base.parse_torrent_layout` accept.

    Args:
        name: ``info.name`` — root name of the torrent.
        files: Ordered ``(relative_path, byte_size)`` pairs for multi-file
            torrents.  ``None`` produces a single-file torrent with a dummy
            ``length=1000`` entry.
        piece_length: ``info.piece length`` in bytes.
        meta_version: Optional ``info.meta version`` integer (v2 hybrid marker).

    Returns:
        Raw bencoded bytes suitable for ``TorrentSource.from_file``.
    """
    info_items: list[tuple[bytes, bytes]] = [
        (b"name", _bencode_str(name.encode())),
        (b"piece length", _bencode_int(piece_length)),
        (b"pieces", _bencode_str(b"\x00" * 20)),  # one fake 20-byte SHA-1 hash
    ]
    if files is not None:
        file_entries: list[bytes] = []
        for fname, fsize in files:
            file_dict = _bencode_dict_items(
                [
                    (b"length", _bencode_int(fsize)),
                    (b"path", _bencode_list([_bencode_str(fname.encode())])),
                ]
            )
            file_entries.append(file_dict)
        info_items.append((b"files", _bencode_list(file_entries)))
    else:
        info_items.append((b"length", _bencode_int(1000)))

    if meta_version is not None:
        info_items.append((b"meta version", _bencode_int(meta_version)))

    torrent = _bencode_dict_items(
        [
            (b"announce", _bencode_str(b"x")),
            (b"info", _bencode_dict_items(info_items)),
        ]
    )
    return torrent


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

_TRACKER_LACALE = "lacale"
_TRACKER_TORR9 = "torr9"

_SOURCE_HASH = "abc123def4567890abc123def4567890abc123de"  # 40-char hex
_CANDIDATE_HASH = "def456abc1237890def456abc1237890def456ab"


def _derive_injected_hash(torrent_bytes: bytes) -> str:
    """Return the v1 info-hash of *torrent_bytes* as lowercase hex."""
    return TorrentSource.from_file(torrent_bytes).info_hash


def _tracker_provider(
    enabled: bool = True,
    cross_seed: bool = True,
    min_seed_time: int = 86_400,
    min_ratio: float = 1.0,
) -> TrackerProviderConfig:
    """Build a :class:`TrackerProviderConfig` with economy set."""
    return TrackerProviderConfig(
        enabled=enabled,
        cross_seed=cross_seed,
        economy=TrackerEconomyConfig(
            target_ratio=2.0,
            min_ratio=min_ratio,
            min_seed_time=min_seed_time,
        ),
    )


def make_config(
    tmp_path: Path,
    *,
    cross_seed_enabled: bool = True,
    max_searches_per_day: int = 250,
    min_delay_between_searches_s: int = 30,
    exclude_recent_search_days: int = 3,
    verify_timeout_s: int = 120,
    tracker_providers: dict[str, TrackerProviderConfig] | None = None,
    tracker_priority: list[str] | None = None,
) -> Config:
    """Build a minimal :class:`Config` for :class:`CrossSeedService` tests.

    All paths are scoped under *tmp_path* so no real filesystem is touched.

    Args:
        tmp_path: Pytest temporary directory.
        cross_seed_enabled: Global kill-switch.
        max_searches_per_day: Daily sweep quota.
        min_delay_between_searches_s: Inter-search delay for sweep.
        exclude_recent_search_days: History look-back window.
        verify_timeout_s: Recheck verification timeout (default 120 for tests).
        tracker_providers: Per-tracker configuration dict.
        tracker_priority: Ordered tracker priority list.

    Returns:
        A validated :class:`Config` instance.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    disk_path = tmp_path / "disk_1"
    disk_path.mkdir(parents=True, exist_ok=True)

    if tracker_providers is None:
        tracker_providers = {
            _TRACKER_LACALE: _tracker_provider(),
            _TRACKER_TORR9: _tracker_provider(),
        }
    if tracker_priority is None:
        tracker_priority = [_TRACKER_LACALE, _TRACKER_TORR9]

    return Config(
        paths=PathConfig(
            staging_dir=staging_dir,
            torrent_complete_dir=tmp_path / "complete",
            data_dir=data_dir,
        ),
        disks=[
            DiskConfig(id="disk_1", path=disk_path, categories=["movies"]),
        ],
        staging_dirs=CANONICAL_STAGING_DIRS,
        categories={"movies": CategoryConfig(folder_name="Movies")},
        cross_seed=CrossSeedConfig(
            enabled=cross_seed_enabled,
            max_searches_per_day=max_searches_per_day,
            min_delay_between_searches_s=min_delay_between_searches_s,
            exclude_recent_search_days=exclude_recent_search_days,
            verify_timeout_s=verify_timeout_s,
        ),
        tracker=TrackerConfig(
            providers=tracker_providers,
            priority=tracker_priority,
        ),
    )


# ---------------------------------------------------------------------------
# Fake torrent client — implements all four protocols used by CrossSeedService
# ---------------------------------------------------------------------------


class FakeTorrentClient:
    """In-memory fake implementing all four torrent capability protocols.

    Implements :class:`TorrentLister`, :class:`TorrentInjector`,
    :class:`TorrentController`, and :class:`TorrentTagger`.

    Tracks injected hashes, tags, resumes, and deletes so tests can assert
    against the recorded calls.
    """

    def __init__(self, completed: list[TorrentItem] | None = None) -> None:
        """Initialise with an optional list of completed :class:`TorrentItem`.

        Args:
            completed: Pre-seeded list of completed torrents returned by
                :meth:`get_completed`. Each injection appends to this list.
        """
        self._completed: list[TorrentItem] = list(completed) if completed else []
        # Per-hash state maps.
        self._files: dict[str, list[tuple[str, int]]] = {}
        self._props: dict[str, dict[str, object]] = {}
        # Call records for assertions.
        self.injected: list[tuple[bytes, str, bool, bool]] = []  # (bytes, save_path, recheck, paused)
        self.injected_hashes: list[str] = []
        self.resumed: list[str] = []
        self.deleted: list[tuple[str, bool]] = []  # (hash, delete_files)
        self.tags_added: dict[str, set[str]] = {}  # hash -> set of tags
        self.tags_removed: dict[str, set[str]] = {}  # hash -> set of tags

    # -- Seeding helpers ------------------------------------------------------

    def seed_item(self, item: TorrentItem) -> None:
        """Register a completed torrent item."""
        self._completed.append(item)

    def seed_files(self, info_hash: str, files: list[tuple[str, int]]) -> None:
        """Pre-seed :meth:`list_files` response for *info_hash*."""
        self._files[info_hash] = list(files)

    def seed_properties(self, info_hash: str, props: dict[str, object]) -> None:
        """Pre-seed :meth:`properties` response for *info_hash*."""
        self._props[info_hash] = dict(props)

    # -- TorrentLister ---------------------------------------------------------

    def get_completed(self) -> list[TorrentItem]:
        """Return all completed torrents (pre-seeded + injected)."""
        return list(self._completed)

    def get_all_hashes(self) -> set[str]:
        """Return all known hashes."""
        return {t.hash for t in self._completed}

    # -- TorrentInjector ------------------------------------------------------

    def inject(
        self,
        torrent_bytes: bytes,
        *,
        save_path: str,
        recheck: bool = True,
        paused: bool = True,
    ) -> str:
        """Record the injection and return the derived info-hash.

        Args:
            torrent_bytes: Raw ``.torrent`` bytes.
            save_path: Target save directory.
            recheck: Whether to recheck after add.
            paused: Whether to add in paused state.

        Returns:
            The v1 info-hash of the injected torrent.
        """
        info_hash = _derive_injected_hash(torrent_bytes)
        self.injected.append((torrent_bytes, save_path, recheck, paused))
        self.injected_hashes.append(info_hash)
        # Add a completed entry so _verify_injection can find it.
        name = f"cross-seed-{info_hash[:8]}"
        injected_item = TorrentItem(
            hash=info_hash,
            name=name,
            size_bytes=1000,
            progress=1.0,  # Immediately "verified" by default.
            state="pausedUP",
            save_path=save_path,
            tags=[],
        )
        self._completed.append(injected_item)
        # Seed file list + properties for the injected hash so the next
        # list_files / properties call succeeds.
        self._files[info_hash] = self._files.get(_SOURCE_HASH, [("cross_seed.mkv", 1000)])
        self._props[info_hash] = {"piece_size": 262144}
        return info_hash

    def list_files(self, info_hash: str) -> list[tuple[str, int]]:
        """Return pre-seeded file list for *info_hash*."""
        return list(self._files.get(info_hash, []))

    def properties(self, info_hash: str) -> dict[str, object]:
        """Return pre-seeded properties for *info_hash*."""
        return dict(self._props.get(info_hash, {}))

    # -- TorrentController ----------------------------------------------------

    def pause(self, hash: str) -> None:
        """No-op stub."""

    def resume(self, hash: str) -> None:
        """Record the resume call."""
        self.resumed.append(hash)

    def delete(self, hash: str, *, delete_files: bool = False) -> None:
        """Record the delete call."""
        self.deleted.append((hash, delete_files))

    # -- TorrentTagger --------------------------------------------------------

    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Record added tags (idempotent)."""
        self.tags_added.setdefault(info_hash, set()).update(tags)

    def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Record removed tags (idempotent)."""
        self.tags_removed.setdefault(info_hash, set()).update(tags)


# ---------------------------------------------------------------------------
# Fake tracker + transport
# ---------------------------------------------------------------------------


class FakeTransport:
    """Minimal fake :class:`HttpTransport` — returns pre-seeded bytes by URL."""

    def __init__(
        self,
        provider_name: str = _TRACKER_TORR9,
        responses: dict[str, bytes] | None = None,
    ) -> None:
        """Initialise with named provider and response map.

        Args:
            provider_name: Provider identifier (matches ``TrackerResult.provider``).
            responses: ``{url -> bytes}`` mapping for ``get_bytes``.
        """
        self.provider_name = provider_name
        self._responses: dict[str, bytes] = dict(responses) if responses else {}

    def seed(self, url: str, data: bytes) -> None:
        """Register a canned response for *url*."""
        self._responses[url] = data

    def get_bytes(self, url: str) -> bytes:
        """Return the pre-seeded bytes for *url*.

        Args:
            url: The download URL (matched exactly against seeded keys).

        Returns:
            The pre-seeded bytes.

        Raises:
            KeyError: No response seeded for *url*.
        """
        return self._responses[url]


class FakeTracker:
    """Fake :class:`TorrentSearchable` returning pre-seeded search results."""

    def __init__(
        self,
        provider: str,
        transport: FakeTransport | None = None,
        results: list[TrackerResult] | None = None,
    ) -> None:
        """Initialise with provider name and optional transport.

        Args:
            provider: Tracker provider name (e.g. ``"torr9"``).
            transport: Transport instance exposed via ``_open_transport``.
            results: Pre-seeded search results returned by ``search()``.
        """
        self._provider = provider
        self._open_transport = transport
        self._results: list[TrackerResult] = list(results) if results else []

    def seed_results(self, results: list[TrackerResult]) -> None:
        """Replace the result list returned by :meth:`search`."""
        self._results = list(results)

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]:
        """Return pre-seeded results (ignoring *query*)."""
        return list(self._results)


def make_registry(
    trackers: dict[str, FakeTracker],
    priority: list[str] | None = None,
) -> "FakeRegistry":
    """Build a fake :class:`TrackerRegistry` from :class:`FakeTracker` instances.

    Args:
        trackers: ``{name: FakeTracker}`` mapping.
        priority: Ordered tracker priority list (defaults to ``trackers`` keys).

    Returns:
        A :class:`FakeRegistry` wrapping the trackers.
    """
    return FakeRegistry(trackers, priority or list(trackers.keys()))


class FakeRegistry:
    """Minimal fake :class:`TrackerRegistry` — no ranking, no materialization."""

    def __init__(
        self,
        trackers: dict[str, FakeTracker],
        priority: list[str],
    ) -> None:
        """Initialise with tracker map and priority order.

        Args:
            trackers: ``{name: FakeTracker}`` mapping.
            priority: Ordered tracker priority list.
        """
        self._trackers = trackers
        self._priority = priority
        self.last_media_type: MediaType | None = None
        """The *media_type* argument received by the most recent
        :meth:`search_candidates` call, or ``None`` before the first call."""
        self._errored: set[str] = set()
        """Tracker names that should simulate an error in :meth:`search_candidates`."""

    def seed_errored(self, names: set[str]) -> None:
        """Configure which tracker names should simulate errors.

        On the next :meth:`search_candidates` call, trackers in this set
        are skipped (no results returned) and counted as errored.
        """
        self._errored = set(names)

    def search_candidates(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> SearchOutcome:
        """Search every tracker in priority order and return a raw :class:`SearchOutcome`.

        Args:
            query: Search query string.
            media_type: Media type filter.
            year: Optional release year.

        Returns:
            Merged :class:`SearchOutcome` with results from all configured trackers.
        """
        self.last_media_type = media_type
        all_results: list[TrackerResult] = []
        queried = 0
        errored = 0
        errored_names: list[str] = []
        queried_names: list[str] = []
        for name in self._priority:
            tracker = self._trackers.get(name)
            if tracker is None:
                continue
            queried += 1
            queried_names.append(name)
            if name in self._errored:
                errored += 1
                errored_names.append(name)
                continue
            all_results.extend(tracker.search(query, media_type, year))
        return SearchOutcome(
            results=all_results,
            trackers_queried=queried,
            trackers_errored=errored,
            errored_names=errored_names,
            queried_names=queried_names,
        )

    def transports(self) -> dict[str, FakeTransport]:
        """Return a ``{tracker name → FakeTransport}`` map.

        Only trackers with a non-``None`` ``_open_transport`` are included,
        matching the production :meth:`TrackerRegistry.transports` contract.

        Returns:
            Dict mapping each tracker name to its materialized transport.
        """
        result: dict[str, FakeTransport] = {}
        for name, client in self._trackers.items():
            transport = getattr(client, "_open_transport", None)
            if transport is not None:
                result[name] = transport
        return result


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real :class:`ConcreteAcquireStore` on ``tmp_path/acquire.db``.

    The store opens lazily on first sub-store access.  Closed in ``finally``
    so any test failure doesn't leak the connection.
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Shared builder — CrossSeedService with two trackers (lacale origin, torr9 target)
# ---------------------------------------------------------------------------


def _source_item(
    info_hash: str = _SOURCE_HASH,
    name: str = "Movie.2024.1080p.BluRay.x264-GROUP",
    save_path: str = "/data/torrents/Movie.2024.1080p.BluRay.x264-GROUP",
    tags: list[str] | None = None,
    progress: float = 1.0,
    content_path: str | None = None,
) -> TorrentItem:
    """Build a completed source :class:`TorrentItem`."""
    if tags is None:
        tags = [_TRACKER_LACALE]
    return TorrentItem(
        hash=info_hash,
        name=name,
        size_bytes=2_000_000_000,
        progress=progress,
        state="uploading",
        save_path=save_path,
        content_path=Path(content_path) if content_path else None,
        tags=list(tags),
    )


def _candidate_result(
    provider: str = _TRACKER_TORR9,
    title: str = "Movie.2024.1080p.BluRay.x264-GROUP",
    download_url: str = "https://torr9.example.com/dl/123",
    info_hash: str | None = None,
    tracker_id: str = "456",
) -> TrackerResult:
    """Build a :class:`TrackerResult` representing a cross-seed candidate.

    *info_hash* defaults to ``None`` to skip the hash cross-check in
    :func:`resolve_source` — the actual info-hash of the crafted bencode
    bytes differs from any hardcoded placeholder. Tests that need the
    check can pass the real hash explicitly.
    """
    return TrackerResult(
        provider=provider,
        tracker_id=tracker_id,
        title=title,
        size=ByteSize(bytes=2_000_000_000),
        seeders=10,
        leechers=0,
        download_url=download_url,
        info_hash=info_hash,
    )


def _build_service(
    config: Config,
    store: ConcreteAcquireStore,
    fake_client: FakeTorrentClient,
    fake_registry: FakeRegistry,
    clock: Any = None,
    sleep: Any = None,
    event_bus: EventBus | None = None,
) -> CrossSeedService:
    """Build a :class:`CrossSeedService` with all fakes wired in.

    Args:
        config: Test :class:`Config`.
        store: Real :class:`ConcreteAcquireStore`.
        fake_client: :class:`FakeTorrentClient` implementing all four protocols.
        fake_registry: :class:`FakeRegistry` for search + transport resolution.
        clock: Optional fake clock callable.
        sleep: Optional fake sleep callable.
        event_bus: Optional :class:`EventBus` for event assertion.  When
            ``None`` (default), a fresh :class:`EventBus` is created so
            emission is always exercised.

    Returns:
        A fully wired :class:`CrossSeedService`.
    """
    import time as _time_module

    if event_bus is None:
        event_bus = EventBus()

    return CrossSeedService(
        registry=fake_registry,  # type: ignore[arg-type]  # FakeRegistry, not TrackerRegistry
        lister=fake_client,
        injector=fake_client,
        controller=fake_client,
        tagger=fake_client,
        store=store,
        config=config,
        event_bus=event_bus,
        clock=clock if clock is not None else _time_module.monotonic,
        sleep=sleep if sleep is not None else _time_module.sleep,
    )


# ===========================================================================
# Tests: check()
# ===========================================================================


class TestCheckHappyPath:
    """test_check_injects_on_match_and_tags_and_writes_obligation (ACC-6)."""

    def test_injects_on_match_and_tags_and_writes_obligation(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Happy path: candidate matches → inject → verify → tag + obligation."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        # Fake torrent client seeded with the source item.
        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Fake transport returning the matching .torrent bytes.
        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

        # Fake tracker returning one candidate.
        fake_torrent_tracker = FakeTracker(
            provider=_TRACKER_TORR9,
            transport=fake_transport,
            results=[_candidate_result(download_url=candidate_url)],
        )
        fake_lacale_tracker = FakeTracker(
            provider=_TRACKER_LACALE,
            results=[],  # No candidates from origin tracker.
        )

        fake_registry = make_registry(
            {_TRACKER_LACALE: fake_lacale_tracker, _TRACKER_TORR9: fake_torrent_tracker},
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        injected_events: list[CrossSeedInjected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedInjected, lambda e: injected_events.append(e))

        cfg = make_config(
            tmp_path,
            tracker_providers={
                _TRACKER_LACALE: _tracker_provider(),
                _TRACKER_TORR9: _tracker_provider(min_seed_time=86_400, min_ratio=1.5),
            },
            tracker_priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        svc = _build_service(cfg, store, fake_client, fake_registry, event_bus=bus)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Media type derived from release name (D6/D7).
        assert fake_registry.last_media_type == MediaType.MOVIE

        # Result shape.
        assert result.injected == [injected_hash]
        assert result.rejected == []
        assert result.skipped is False
        assert result.skip_reason is None

        # EventBus: exactly one CrossSeedInjected emitted with the right info_hash.
        assert len(injected_events) == 1
        assert injected_events[0].info_hash == injected_hash
        assert injected_events[0].source_tracker == _TRACKER_TORR9
        assert injected_events[0].source_hash == _SOURCE_HASH
        assert injected_events[0].save_path == item.save_path

        # Torrent client calls.
        assert injected_hash in fake_client.resumed
        assert SEED_PURE in fake_client.tags_added.get(injected_hash, set())

        # SeedObligation written with target tracker's economy values.
        obligations = store.seed.find_active_under(Path(item.save_path))
        assert len(obligations) == 1
        ob = obligations[0]
        assert ob.info_hash == injected_hash
        assert ob.source_tracker == _TRACKER_TORR9  # Target tracker.
        assert ob.min_seed_time_s == 86_400  # From torr9 economy.
        assert ob.min_ratio == 1.5
        assert ob.dispatched_path == item.save_path

        # Search history recorded.
        assert store.cross_seed.was_searched_recently(_SOURCE_HASH, _TRACKER_TORR9, days=3) is True


class TestCheckRecheckFails:
    """test_check_recheck_fails_removes_without_obligation (ACC-6)."""

    def test_recheck_fails_removes_without_obligation(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Inject → recheck never reaches 100% → delete, no obligation."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Override inject to NOT add the completed item — the lister will never
        # report the injected hash as completed.
        def _inject_no_complete(
            torrent_bytes: bytes,
            *,
            save_path: str,
            recheck: bool = True,
            paused: bool = True,
        ) -> str:
            info_hash = _derive_injected_hash(torrent_bytes)
            fake_client.injected.append((torrent_bytes, save_path, recheck, paused))
            fake_client.injected_hashes.append(info_hash)
            # IMPORTANT: do NOT add a completed entry — simulates recheck never finishing.
            fake_client._files[info_hash] = fake_client._files.get(_SOURCE_HASH, [])
            fake_client._props[info_hash] = {"piece_size": 262144}
            return info_hash

        fake_client.inject = _inject_no_complete  # type: ignore[method-assign]

        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(tmp_path)

        # Fake clock: each call returns the next tick.
        # Tick 0 → deadline=120. Tick 1 → enter loop (2.0 < 120). Tick 2 → exit (130 >= 120).
        clock_ticks = iter([0.0, 2.0, 130.0])
        sleep_log: list[float] = []

        rejected_events: list[CrossSeedRejected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedRejected, lambda e: rejected_events.append(e))

        svc = _build_service(
            cfg,
            store,
            fake_client,
            fake_registry,
            clock=lambda: next(clock_ticks),
            sleep=lambda s: sleep_log.append(s),
            event_bus=bus,
        )

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Not injected.
        assert result.injected == []
        # Rejected with reason verify_timeout (deadline passed, no definitive
        # verdict — the current progress-only poll cannot distinguish a
        # completed-check-failed from a still-running recheck).
        assert len(result.rejected) == 1
        _, rejected_tracker, rejected_reason = result.rejected[0]
        assert rejected_tracker == _TRACKER_TORR9
        assert rejected_reason == "verify_timeout"

        # EventBus: a CrossSeedRejected with reason=verify_timeout was emitted.
        recheck_rejections = [e for e in rejected_events if e.reason == "verify_timeout"]
        assert len(recheck_rejections) == 1
        assert recheck_rejections[0].info_hash == injected_hash
        assert recheck_rejections[0].tracker == _TRACKER_TORR9
        assert recheck_rejections[0].source_hash == _SOURCE_HASH

        # Delete called (delete_files=False).
        assert any(h == injected_hash and not df for h, df in fake_client.deleted)

        # No obligation written.
        obligations = store.seed.find_active_under(Path(item.save_path))
        assert obligations == []

        # Sleep was called (poll interval).
        assert len(sleep_log) >= 1
        assert sleep_log[0] == 2  # _VERIFY_POLL_INTERVAL_S


class TestCheckIdempotent:
    """test_check_idempotent_rerun."""

    def test_idempotent_rerun(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Second check() on same hash → skipped (recently searched)."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(tmp_path, exclude_recent_search_days=3)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        first = svc.check(_SOURCE_HASH)
        second = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # First run: injected (happy path).
        assert len(first.injected) == 1
        assert first.skipped is False

        # Second run: all target trackers recently searched → skipped.
        assert second.skipped is True
        assert second.skip_reason == "all_excluded_recent"
        assert second.injected == []


class TestCheckOriginExcluded:
    """test_check_origin_tracker_excluded (D5 — ACC-6)."""

    def test_origin_tracker_excluded(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Source from lacale → lacale candidates excluded, torr9 candidate injected.

        The promised scenario from the phase-10 plan: the origin tracker has
        candidates (which must be excluded), AND an eligible other tracker has
        candidates → only the non-origin tracker is used.  This proves the
        origin-exclusion guard works without relying on there being zero other
        trackers (the degenerate case tested before).
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item(tags=[_TRACKER_LACALE])
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Matching .torrent bytes for the torr9 candidate.
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        # lacale (origin) has candidates — must be excluded.
        fake_lacale_transport = FakeTransport(provider_name=_TRACKER_LACALE)
        lacale_results = [_candidate_result(provider=_TRACKER_LACALE, download_url="https://lacale.example.com/dl/1")]

        # torr9 (eligible) has a structurally-matching candidate → should be injected.
        torr9_url = "https://torr9.example.com/dl/456"
        fake_torr9_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_torr9_transport.seed(torr9_url, candidate_torrent)
        torr9_results = [_candidate_result(provider=_TRACKER_TORR9, download_url=torr9_url)]

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(
                    provider=_TRACKER_LACALE,
                    transport=fake_lacale_transport,
                    results=lacale_results,
                ),
                _TRACKER_TORR9: FakeTracker(
                    provider=_TRACKER_TORR9,
                    transport=fake_torr9_transport,
                    results=torr9_results,
                ),
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        cfg = make_config(
            tmp_path,
            tracker_providers={
                _TRACKER_LACALE: _tracker_provider(),
                _TRACKER_TORR9: _tracker_provider(min_seed_time=86_400, min_ratio=1.5),
            },
            tracker_priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # torr9 candidate was injected (origin lacale excluded → not iterated).
        assert result.injected == [injected_hash]
        assert result.rejected == []
        assert result.skipped is False

        # Injected hash was resumed and tagged.
        assert injected_hash in fake_client.resumed
        assert SEED_PURE in fake_client.tags_added.get(injected_hash, set())

        # Search history recorded for torr9 only (lacale is origin → excluded).
        assert store.cross_seed.was_searched_recently(_SOURCE_HASH, _TRACKER_TORR9, days=3) is True
        # lacale was never in remaining → no search recorded.
        obligations = store.seed.find_active_under(Path(item.save_path))
        assert len(obligations) == 1
        assert obligations[0].source_tracker == _TRACKER_TORR9


class TestCheckSeedPureSkipped:
    """test_check_seed_pure_skipped."""

    def test_seed_pure_skipped(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """SEED_PURE-tagged torrent → skipped immediately."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item(tags=[_TRACKER_LACALE, SEED_PURE])
        fake_client = FakeTorrentClient(completed=[item])

        fake_registry = make_registry({})

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        assert result.skipped is True
        assert result.skip_reason == "seed_pure"
        assert result.injected == []
        # No searches should have been triggered.
        assert store.cross_seed.was_searched_recently(_SOURCE_HASH, _TRACKER_TORR9, days=3) is False


class TestCheckV2HybridSkipped:
    """test_check_v2_hybrid_skipped."""

    def test_v2_hybrid_skipped(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Local layout ``meta_version=2`` → skipped immediately.

        The fake injector's :meth:`properties` returns ``meta_version: 2``,
        and ``_build_local_layout`` reads it so the local layout has
        ``meta_version=2``.  The ``check()`` guard rejects it before any
        search.
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144, "meta_version": 2})

        fake_registry = make_registry({})
        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        assert result.skipped is True
        assert result.skip_reason == "v2_hybrid"
        assert result.injected == []


class TestCheckCrossSeedDisabledTracker:
    """test_check_cross_seed_disabled_tracker_excluded."""

    def test_cross_seed_disabled_tracker_excluded(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Tracker with ``cross_seed=false`` is never searched or injected."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        candidate_torrent = make_torrent_bytes(name=item.name, files=source_files)
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed("https://torr9.example.com/dl/123", candidate_torrent)

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: FakeTracker(
                    provider=_TRACKER_TORR9,
                    transport=fake_transport,
                    results=[_candidate_result(download_url="https://torr9.example.com/dl/123")],
                ),
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        # torr9 has cross_seed=False — should be excluded.
        cfg = make_config(
            tmp_path,
            tracker_providers={
                _TRACKER_LACALE: _tracker_provider(cross_seed=True),
                _TRACKER_TORR9: _tracker_provider(cross_seed=False),
            },
            tracker_priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # lacale is origin (excluded), torr9 cross_seed=False (excluded) → no remaining.
        assert result.skipped is True
        assert result.injected == []


# ===========================================================================
# Tests: sweep()
# ===========================================================================


class TestSweepQuotaExhausted:
    """test_sweep_quota_exhausted_stops."""

    def test_quota_exhausted_stops(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """``max_searches_per_day=2``, 3 eligible items → only 2 checked."""
        # -- Arrange ----------------------------------------------------------
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        items = [
            _source_item(info_hash=f"hash{i:040d}", name=f"Movie.{i}.2024", save_path=f"/data/Movie.{i}.2024")
            for i in range(3)
        ]
        # Items 0 and 1 tagged lacale (origin), item 2 tagged differently.
        items[2] = _source_item(
            info_hash=f"hash{2:040d}",
            name=f"Movie.{2}.2024",
            save_path=f"/data/Movie.{2}.2024",
        )

        fake_client = FakeTorrentClient(completed=list(items))
        for i in range(3):
            fake_client.seed_files(f"hash{i:040d}", source_files)
            fake_client.seed_properties(f"hash{i:040d}", {"piece_size": 262144})

        # For each item, the target tracker returns a matching candidate.
        # We need candidate torrents with matching names.
        candidate_bytes = [make_torrent_bytes(name=items[i].name, files=source_files) for i in range(3)]

        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        for i, cb in enumerate(candidate_bytes):
            fake_transport.seed(f"https://torr9.example.com/dl/{i}", cb)

        fake_torrent_tracker = FakeTracker(
            provider=_TRACKER_TORR9,
            transport=fake_transport,
            results=[
                _candidate_result(
                    provider=_TRACKER_TORR9,
                    title=items[i].name,
                    download_url=f"https://torr9.example.com/dl/{i}",
                )
                for i in range(3)
            ],
        )

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: fake_torrent_tracker,
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        cfg = make_config(tmp_path, max_searches_per_day=2)
        sleep_log: list[float] = []
        svc = _build_service(cfg, store, fake_client, fake_registry, sleep=lambda s: sleep_log.append(s))

        # -- Act --------------------------------------------------------------
        result = svc.sweep()

        # -- Assert -----------------------------------------------------------
        assert result.checked == 2  # Only 2 of 3 (quota exhausted).
        assert result.quota_exhausted is True
        # All checks that ran should have injected (happy path).
        assert result.injected == 2


class TestSweepExcludeRecent:
    """test_sweep_exclude_recent_respected."""

    def test_exclude_recent_respected(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Pre-recorded recent search → sweep skips it, quota not consumed."""
        # -- Arrange ----------------------------------------------------------
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        item = _source_item()
        # Pre-record a recent search for this source hash on torr9.
        store.cross_seed.record_search(_SOURCE_HASH, _TRACKER_TORR9)

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # torr9 DOES have candidates, but search is excluded by recent history.
        candidate_torrent = make_torrent_bytes(name=item.name, files=source_files)
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed("https://torr9.example.com/dl/123", candidate_torrent)

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: FakeTracker(
                    provider=_TRACKER_TORR9,
                    transport=fake_transport,
                    results=[_candidate_result(download_url="https://torr9.example.com/dl/123")],
                ),
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        cfg = make_config(tmp_path, max_searches_per_day=5, exclude_recent_search_days=3)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.sweep()

        # -- Assert -----------------------------------------------------------
        # The item is eligible (not seed_pure), but check() skips it because
        # torr9 was recently searched → no tracker remaining → skipped.
        # Sweep only counts quota for non-skipped checks.
        assert result.checked == 1  # check() was called.
        assert result.injected == 0  # But nothing injected (skipped inside check).
        assert result.quota_exhausted is False
        # Daily quota was NOT incremented (check returned skipped).
        assert store.cross_seed.daily_searches_remaining(5) == 5


class TestSweepDelayRespected:
    """test_sweep_delay_respected."""

    def test_delay_respected(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Fake sleep called with ``min_delay_between_searches_s`` between quota-counted checks.

        No real sleeping — assert ``sleep`` call count and arguments.
        """
        # -- Arrange ----------------------------------------------------------
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        items = [
            _source_item(info_hash=f"hash{i:040d}", name=f"Movie.{i}.2024", save_path=f"/data/Movie.{i}.2024")
            for i in range(3)
        ]

        fake_client = FakeTorrentClient(completed=list(items))
        for i in range(3):
            fake_client.seed_files(f"hash{i:040d}", source_files)
            fake_client.seed_properties(f"hash{i:040d}", {"piece_size": 262144})

        candidate_bytes = [make_torrent_bytes(name=items[i].name, files=source_files) for i in range(3)]

        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        for i, cb in enumerate(candidate_bytes):
            fake_transport.seed(f"https://torr9.example.com/dl/{i}", cb)

        fake_torrent_tracker = FakeTracker(
            provider=_TRACKER_TORR9,
            transport=fake_transport,
            results=[
                _candidate_result(
                    provider=_TRACKER_TORR9,
                    title=items[i].name,
                    download_url=f"https://torr9.example.com/dl/{i}",
                )
                for i in range(3)
            ],
        )

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: fake_torrent_tracker,
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        min_delay = 15
        cfg = make_config(tmp_path, max_searches_per_day=10, min_delay_between_searches_s=min_delay)
        sleep_log: list[float] = []
        svc = _build_service(cfg, store, fake_client, fake_registry, sleep=lambda s: sleep_log.append(s))

        # -- Act --------------------------------------------------------------
        svc.sweep()

        # -- Assert -----------------------------------------------------------
        # 3 items → 3 checks, all non-skipped → 2 sleeps (after first, after second; no sleep after last).
        assert len(sleep_log) == 2
        assert sleep_log[0] == min_delay
        assert sleep_log[1] == min_delay


# ===========================================================================
# Tests: path-frame normalization (sub-phase 10.1 regression)
# ===========================================================================


class TestPathFrameNormalization:
    """Regression: root-prefixed qBit file list matches root-excluded torrent parse."""

    def test_root_prefixed_multi_file_matches_parsed_torrent(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """qBit-style root-prefixed paths normalize to match parsed .torrent layout.

        Regression for the bug where ``torrents/files`` returns names including
        the root folder (``"Show.S01/Season 01/ep1.mkv"``) while
        ``parse_torrent_layout`` yields root-excluded paths
        (``"Season 01/ep1.mkv"``), causing ``structural_match`` to string-compare
        and always return ``FILE_LIST_MISMATCH`` for real multi-file torrents.
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item(name="Show.S01")

        # qBit-style file list: root-PREFIXED paths (the real-world frame).
        qbit_files: list[tuple[str, int]] = [
            ("Show.S01/Season 01/ep1.mkv", 1_000_000_000),
            ("Show.S01/Season 01/ep2.mkv", 1_200_000_000),
        ]
        # Parsed .torrent layout: root-EXCLUDED paths (the candidate frame).
        parsed_files: list[tuple[str, int]] = [
            ("Season 01/ep1.mkv", 1_000_000_000),
            ("Season 01/ep2.mkv", 1_200_000_000),
        ]
        piece_length = 262144
        torrent_name = "Show.S01"

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, qbit_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": piece_length})

        # Candidate .torrent bytes with the ROOT-EXCLUDED frame (same tree).
        candidate_torrent = make_torrent_bytes(
            name=torrent_name,
            files=parsed_files,
            piece_length=piece_length,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # After normalization, the paths should match → MATCH → injected.
        assert result.injected == [injected_hash], (
            f"Expected injection of {injected_hash}, got rejected: {result.rejected}"
        )
        assert result.skipped is False

    def test_renamed_qbit_root_still_matches_by_file_structure(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """When qBit display name differs but file paths share one root, strip prevails.

        The normalization uses the first path component as the layout name
        (more truthful than the renameable qBit display name).  If the parsed
        .torrent uses the same root, they match.
        """
        # -- Arrange ----------------------------------------------------------
        # qBit was renamed to "Show.S01.Renamed" but files still live under "Show.S01/".
        item = _source_item(name="Show.S01.Renamed")
        qbit_files: list[tuple[str, int]] = [
            ("Show.S01/Season 01/ep1.mkv", 1_000_000_000),
            ("Show.S01/Season 01/ep2.mkv", 1_200_000_000),
        ]
        piece_length = 262144

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, qbit_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": piece_length})

        # Candidate .torrent: root = "Show.S01" (matches the file structure).
        candidate_torrent = make_torrent_bytes(
            name="Show.S01",
            files=[("Season 01/ep1.mkv", 1_000_000_000), ("Season 01/ep2.mkv", 1_200_000_000)],
            piece_length=piece_length,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        candidate_url = "https://torr9.example.com/dl/renamed"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Normalization strips "Show.S01/" → name="Show.S01", matching candidate.
        assert result.injected == [injected_hash]

    def test_flat_multi_file_without_root_prefix_still_matches(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Entries without '/' (flat multi-file) are left as-is with item.name.

        This is the existing behaviour for torrents where files live at the
        torrent root level — the frames agree without normalization.
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item(name="Flat.Release.2024")
        files: list[tuple[str, int]] = [
            ("Flat.Release.2024.part1.mkv", 1_000_000_000),
            ("Flat.Release.2024.part2.mkv", 800_000_000),
        ]
        piece_length = 524288

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": piece_length})

        # Candidate .torrent with matching flat multi-file structure.
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=files,
            piece_length=piece_length,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        candidate_url = "https://torr9.example.com/dl/flat"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Flat multi-file (no "/" in any entry) leaves files + name as-is → MATCH.
        assert result.injected == [injected_hash]

    def test_mixed_roots_leave_files_as_is(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Entries with different first components are left as-is, using item.name.

        This is a rare but valid case (torrent with files in two different
        top-level directories).  The frames diverge and the name check will
        catch the mismatch when the candidate has a single root.
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item(name="Mixed.Release")
        mixed_files: list[tuple[str, int]] = [
            ("CD1/track01.flac", 30_000_000),
            ("CD2/track01.flac", 30_000_000),
        ]
        piece_length = 131072

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, mixed_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": piece_length})

        # Candidate .torrent with a single root "CD1" → names won't match.
        candidate_torrent = make_torrent_bytes(
            name="Mixed.Release",
            files=[("CD1/track01.flac", 30_000_000), ("CD2/track01.flac", 30_000_000)],
            piece_length=piece_length,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        candidate_url = "https://torr9.example.com/dl/mixed"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Mixed roots → files left as-is, name=item.name="Mixed.Release".
        # Candidate has same name + same file list → should MATCH.
        assert result.injected == [injected_hash]


# ===========================================================================
# Tests: self-candidate guard (sub-phase 10.2)
# ===========================================================================


class TestCheckSelfCandidate:
    """test_check_self_candidate_rejected (sub-phase 10.2)."""

    def test_self_candidate_rejected_no_inject_no_delete(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Candidate bytes hash to source hash → rejected self_candidate, no inject/delete."""
        # -- Arrange ----------------------------------------------------------
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name="Movie.2024.1080p.BluRay.x264-GROUP",
            files=source_files,
            piece_length=262144,
        )
        real_hash = _derive_injected_hash(candidate_torrent)

        item = _source_item(info_hash=real_hash)
        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(real_hash, source_files)
        fake_client.seed_properties(real_hash, {"piece_size": 262144})

        candidate_url = "https://torr9.example.com/dl/self"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

        rejected_events: list[CrossSeedRejected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedRejected, lambda e: rejected_events.append(e))

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

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry, event_bus=bus)

        # -- Act --------------------------------------------------------------
        result = svc.check(real_hash)

        # -- Assert -----------------------------------------------------------
        # Rejected with self_candidate, NO inject, NO delete.
        assert result.injected == []
        assert len(result.rejected) == 1
        _, rejected_tracker, rejected_reason = result.rejected[0]
        assert rejected_tracker == _TRACKER_TORR9
        assert rejected_reason == "self_candidate"
        assert len(fake_client.injected) == 0
        assert len(fake_client.deleted) == 0

        # EventBus: CrossSeedRejected with reason=self_candidate emitted.
        self_rejections = [e for e in rejected_events if e.reason == "self_candidate"]
        assert len(self_rejections) == 1
        assert self_rejections[0].source_hash == real_hash


class TestOriginUnresolvedWarning:
    """test_origin_unresolved_logs_warning (sub-phase 10.2)."""

    def test_origin_unresolved_logs_warning(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Origin unresolvable (no known tracker tag) → warning logged."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item(tags=["unknown_tracker"])
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: FakeTracker(provider=_TRACKER_TORR9, results=[]),
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        with caplog.at_level(logging.WARNING, logger="personalscraper.acquire.cross_seed"):
            svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        assert any("origin_unresolved" in record.message for record in caplog.records), (
            f"Expected origin_unresolved WARNING, got: {[r.message for r in caplog.records]}"
        )


class TestSelfDeleteAverted:
    """test_self_delete_averted_belt_and_braces (sub-phase 10.2)."""

    def test_self_delete_averted_belt_and_braces(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Belt-and-braces: verify-failure, injected_hash==info_hash → delete averted.

        When _bencode_info_hash raises ValueError the early self-candidate guard
        is bypassed (hash_uncomputable).  The inject still returns the source's
        own hash (qBit dedup), and if verify fails, the delete guard must
        prevent deleting the source torrent itself.
        """
        # -- Arrange ----------------------------------------------------------
        import personalscraper.acquire.cross_seed as cs_module

        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name="Movie.2024.1080p.BluRay.x264-GROUP",
            files=source_files,
            piece_length=262144,
        )

        # Source item with progress < 1.0 so _verify_injection does NOT
        # find it as "completed" — the original item and the injected hash
        # share the same hash (simulating qBit Conflict409 dedup), so a
        # progress=1.0 source would falsely pass verification.
        item = _source_item(info_hash=_SOURCE_HASH, progress=0.5)
        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Override inject: return _SOURCE_HASH (simulating qBit Conflict409
        # when injecting the same torrent) and do NOT add a completed entry
        # → verify never succeeds.
        def _inject_returns_source(
            torrent_bytes: bytes,
            *,
            save_path: str,
            recheck: bool = True,
            paused: bool = True,
        ) -> str:
            fake_client.injected.append((torrent_bytes, save_path, recheck, paused))
            fake_client.injected_hashes.append(_SOURCE_HASH)
            fake_client._files[_SOURCE_HASH] = fake_client._files.get(_SOURCE_HASH, [])
            fake_client._props[_SOURCE_HASH] = {"piece_size": 262144}
            return _SOURCE_HASH

        fake_client.inject = _inject_returns_source  # type: ignore[method-assign]

        # Monkeypatch _bencode_info_hash to raise ValueError → early guard bypassed.
        original_bencode = cs_module._bencode_info_hash  # type: ignore[attr-defined]
        cs_module._bencode_info_hash = lambda data: (_ for _ in ()).throw(  # type: ignore[attr-defined]
            ValueError("hash_uncomputable")
        )

        try:
            candidate_url = "https://torr9.example.com/dl/self-bb"
            fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
            fake_transport.seed(candidate_url, candidate_torrent)

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

            cfg = make_config(tmp_path)
            clock_ticks = iter([0.0, 2.0, 130.0])  # verify timeout after 2nd poll
            sleep_log: list[float] = []

            svc = _build_service(
                cfg,
                store,
                fake_client,
                fake_registry,
                clock=lambda: next(clock_ticks),
                sleep=lambda s: sleep_log.append(s),
            )

            # -- Act ----------------------------------------------------------
            result = svc.check(_SOURCE_HASH)

            # -- Assert -------------------------------------------------------
            # Verify failed → rejected, but delete was NOT called.
            assert result.injected == []
            assert len(result.rejected) >= 1
            assert any(r[2] == "verify_timeout" for r in result.rejected)
            assert len(fake_client.deleted) == 0, (
                f"Delete was called but should have been averted: {fake_client.deleted}"
            )
        finally:
            cs_module._bencode_info_hash = original_bencode  # type: ignore[attr-defined]


# ===========================================================================
# Tests: fail-safe finalization + sweep isolation (sub-phase 10.3)
# ===========================================================================


class TestSweepInjectErrorIsolation:
    """test_sweep_inject_api_error_continues (sub-phase 10.3a)."""

    def test_sweep_inject_api_error_continues(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Inject raises ApiError on Nth item → check() rejects inject_failed, sweep continues.

        Before sub-phase 11.3, inject ApiError propagated out of check()
        and was caught by the sweep-level except (logged sweep_item_error,
        item not counted as checked).  After 11.3, check() catches
        ApiError from inject and converts it to a CrossSeedRejected with
        reason inject_failed — the item is counted as checked (it was
        successfully evaluated, just the injection was rejected).
        """
        # -- Arrange ----------------------------------------------------------
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        items = [
            _source_item(info_hash=f"hash{i:040d}", name=f"Movie.{i}.2024", save_path=f"/data/Movie.{i}.2024")
            for i in range(3)
        ]

        fake_client = FakeTorrentClient(completed=list(items))
        for i in range(3):
            fake_client.seed_files(f"hash{i:040d}", source_files)
            fake_client.seed_properties(f"hash{i:040d}", {"piece_size": 262144})

        candidate_bytes = [make_torrent_bytes(name=items[i].name, files=source_files) for i in range(3)]

        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        for i, cb in enumerate(candidate_bytes):
            fake_transport.seed(f"https://torr9.example.com/dl/{i}", cb)

        fake_torrent_tracker = FakeTracker(
            provider=_TRACKER_TORR9,
            transport=fake_transport,
            results=[
                _candidate_result(
                    provider=_TRACKER_TORR9,
                    title=items[i].name,
                    download_url=f"https://torr9.example.com/dl/{i}",
                )
                for i in range(3)
            ],
        )

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: fake_torrent_tracker,
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        # Make inject fail on the second call (item index 1).
        inject_calls: list[int] = [0]
        original_inject = fake_client.inject

        def _inject_fail_on_nth(
            torrent_bytes: bytes,
            *,
            save_path: str,
            recheck: bool = True,
            paused: bool = True,
        ) -> str:
            inject_calls[0] += 1
            if inject_calls[0] == 2:
                raise ApiError(
                    provider=ProviderName.QBITTORRENT,
                    http_status=0,
                    message="test injection failure",
                )
            return original_inject(torrent_bytes, save_path=save_path, recheck=recheck, paused=paused)

        fake_client.inject = _inject_fail_on_nth  # type: ignore[method-assign]

        cfg = make_config(tmp_path, max_searches_per_day=10)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        with caplog.at_level(logging.WARNING, logger="personalscraper.acquire.cross_seed"):
            result = svc.sweep()

        # -- Assert -----------------------------------------------------------
        # After 11.3, check() catches inject ApiError internally and converts
        # it to a rejected inject_failed — the item IS counted as checked
        # (the check completed, injection was just rejected).
        assert result.checked == 3  # All 3 items evaluated; item 1 rejected inject_failed.
        assert result.injected == 2  # Items 0 and 2 succeeded; item 1 rejected.
        assert result.quota_exhausted is False

        # inject_failed rejection logged at WARNING from inside check().
        assert any("inject_failed" in record.message for record in caplog.records), (
            f"Expected inject_failed in WARNING, got: {[r.message for r in caplog.records]}"
        )


class TestObligationWriteFailure:
    """test_obligation_write_fails_deletes_and_rejects (sub-phase 10.3b)."""

    def test_obligation_write_fails_deletes_and_rejects(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Obligation store write raises → injection deleted, no CrossSeedInjected emitted."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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
        rejected_events: list[CrossSeedRejected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedInjected, lambda e: injected_events.append(e))
        bus.subscribe(CrossSeedRejected, lambda e: rejected_events.append(e))

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry, event_bus=bus)

        # Monkeypatch store.seed.add to raise after verification succeeds.
        with patch.object(store.seed, "add", side_effect=RuntimeError("disk full")):
            # -- Act ----------------------------------------------------------
            result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Not injected.
        assert result.injected == []

        # Rejected with obligation_write_failed.
        assert len(result.rejected) == 1
        _, rejected_tracker, rejected_reason = result.rejected[0]
        assert rejected_tracker == _TRACKER_TORR9
        assert rejected_reason == "obligation_write_failed"

        # Injection deleted (delete_files=False).
        assert any(h == injected_hash and not df for h, df in fake_client.deleted), (
            f"Expected delete of {injected_hash}, got: {fake_client.deleted}"
        )

        # No CrossSeedInjected emitted.
        assert len(injected_events) == 0

        # CrossSeedRejected with obligation_write_failed emitted.
        ob_failures = [e for e in rejected_events if e.reason == "obligation_write_failed"]
        assert len(ob_failures) == 1
        assert ob_failures[0].info_hash == injected_hash
        assert ob_failures[0].source_hash == _SOURCE_HASH


class TestResumeFailureKeepsObligation:
    """test_resume_fails_keeps_obligation_and_emits_event (sub-phase 10.3c)."""

    def test_resume_fails_keeps_obligation_and_emits_event(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Resume raises → obligation kept, ERROR logged, CrossSeedInjected still emitted."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(
            tmp_path,
            tracker_providers={
                _TRACKER_LACALE: _tracker_provider(),
                _TRACKER_TORR9: _tracker_provider(min_seed_time=86_400, min_ratio=1.5),
            },
            tracker_priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        # Override resume to raise.
        original_resume = fake_client.resume

        def _resume_raises(hash: str) -> None:
            fake_client.resumed.append(hash)
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=0,
                message="test resume failure",
            )

        fake_client.resume = _resume_raises  # type: ignore[method-assign]

        svc = _build_service(cfg, store, fake_client, fake_registry, event_bus=bus)

        # -- Act --------------------------------------------------------------
        with caplog.at_level(logging.ERROR, logger="personalscraper.acquire.cross_seed"):
            result = svc.check(_SOURCE_HASH)

        # Restore original resume.
        fake_client.resume = original_resume  # type: ignore[method-assign]

        # -- Assert -----------------------------------------------------------
        # Injection counted as success despite resume failure.
        assert result.injected == [injected_hash]

        # Stranded paused injection logged at ERROR.
        assert any("stranded_paused_injection" in record.message for record in caplog.records), (
            f"Expected stranded_paused_injection ERROR, got: {[r.message for r in caplog.records]}"
        )

        # CrossSeedInjected emitted.
        assert len(injected_events) == 1
        assert injected_events[0].info_hash == injected_hash
        assert injected_events[0].source_tracker == _TRACKER_TORR9

        # Obligation persisted.
        obligations = store.seed.find_active_under(Path(item.save_path))
        assert len(obligations) == 1
        assert obligations[0].info_hash == injected_hash


# ===========================================================================
# Tests: _media_type_for()
# ===========================================================================


class TestMediaTypeFor:
    """Unit tests for :func:`~personalscraper.acquire.cross_seed._media_type_for`."""

    def test_episode_style_name_returns_tv(self) -> None:
        """``"Show.S01E01.1080p.x264-GROUP"`` → :attr:`MediaType.TV`."""
        from personalscraper.acquire._cross_seed_support import _media_type_for

        result = _media_type_for("Show.S01E01.1080p.x264-GROUP")
        assert result == MediaType.TV

    def test_anime_style_name_returns_tv(self) -> None:
        """Anime episode pattern ``"[Group] Show - 01 (1080p)"`` → :attr:`MediaType.TV`."""
        from personalscraper.acquire._cross_seed_support import _media_type_for

        result = _media_type_for("[SubsPlease] Anime - 01 (1080p)")
        assert result == MediaType.TV

    def test_movie_style_name_returns_movie(self) -> None:
        """``"Movie.2024.1080p.BluRay.x264-GROUP"`` → :attr:`MediaType.MOVIE`."""
        from personalscraper.acquire._cross_seed_support import _media_type_for

        result = _media_type_for("Movie.2024.1080p.BluRay.x264-GROUP")
        assert result == MediaType.MOVIE

    def test_unknown_format_falls_back_to_movie(self) -> None:
        """A name guessit cannot classify → :attr:`MediaType.MOVIE` fallback."""
        from personalscraper.acquire._cross_seed_support import _media_type_for

        result = _media_type_for("SomeRandomFile.2024")
        assert result == MediaType.MOVIE

    def test_guessit_exception_falls_back_to_movie(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When guessit raises an exception → :attr:`MediaType.MOVIE` fallback."""
        from personalscraper.acquire._cross_seed_support import _media_type_for

        def _raise(*args: object, **kwargs: object) -> None:
            raise RuntimeError("guessit failure")

        monkeypatch.setattr("personalscraper.acquire._cross_seed_support.guess", _raise)

        result = _media_type_for("Show.S01E01.1080p.x264-GROUP")
        assert result == MediaType.MOVIE


# ===========================================================================
# Tests: tracker-outage handling (sub-phase 10.7)
# ===========================================================================


class TestErroredTrackerNotRecorded:
    """test_errored_tracker_not_recorded_in_history (sub-phase 10.7a)."""

    def test_errored_tracker_not_recorded_search_history(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Tracker that errors is NOT recorded in search history → retry possible.

        A tracker outage that suppresses retries for exclude_recent_search_days
        (3 d) is a silent data-loss bug.  Only trackers that actually succeeded
        (returned results or zero hits) should be recorded.
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # torr9 succeeds (has candidate), lacale errors.
        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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
        # lacale errors → no candidates from it, errored_names = ["lacale"].
        fake_registry.seed_errored({_TRACKER_LACALE})

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Injection succeeded via torr9 (the non-errored tracker).
        assert len(result.injected) == 1

        # torr9 (succeeded) IS recorded in search history.
        assert store.cross_seed.was_searched_recently(_SOURCE_HASH, _TRACKER_TORR9, days=3) is True

        # lacale (errored) is NOT recorded → retry possible next check.
        assert store.cross_seed.was_searched_recently(_SOURCE_HASH, _TRACKER_LACALE, days=3) is False


class TestVerifyTimeoutConfig:
    """test_verify_timeout_s_default_and_used (sub-phase 10.7c)."""

    def test_verify_timeout_default_is_900(self) -> None:
        """Default ``verify_timeout_s`` is 900 (15 min), not the old 120 constant."""
        cfg = CrossSeedConfig()
        assert cfg.verify_timeout_s == 900, f"Expected default 900, got {cfg.verify_timeout_s}"

    def test_verify_timeout_below_30_rejected(self) -> None:
        """Values below 30 are rejected by pydantic validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CrossSeedConfig(verify_timeout_s=10)

    def test_verify_timeout_above_7200_rejected(self) -> None:
        """Values above 7200 are rejected by pydantic validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CrossSeedConfig(verify_timeout_s=8000)

    def test_verify_timeout_emits_reason_verify_timeout(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Timeout during verify → rejection reason is ``verify_timeout``, not ``recheck_failed``."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        injected_hash = _derive_injected_hash(candidate_torrent)

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Override inject: do NOT add completed entry → verify never succeeds.
        def _inject_no_complete(
            torrent_bytes: bytes,
            *,
            save_path: str,
            recheck: bool = True,
            paused: bool = True,
        ) -> str:
            info_hash = _derive_injected_hash(torrent_bytes)
            fake_client.injected.append((torrent_bytes, save_path, recheck, paused))
            fake_client.injected_hashes.append(info_hash)
            fake_client._files[info_hash] = fake_client._files.get(_SOURCE_HASH, [])
            fake_client._props[info_hash] = {"piece_size": 262144}
            return info_hash

        fake_client.inject = _inject_no_complete  # type: ignore[method-assign]

        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        # Use a non-default verify_timeout_s to prove the config value is read.
        cfg = make_config(tmp_path, verify_timeout_s=60)
        clock_ticks = iter([0.0, 2.0, 65.0])  # deadline=60, tick 65 > 60 → timeout
        sleep_log: list[float] = []

        rejected_events: list[CrossSeedRejected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedRejected, lambda e: rejected_events.append(e))

        svc = _build_service(
            cfg,
            store,
            fake_client,
            fake_registry,
            clock=lambda: next(clock_ticks),
            sleep=lambda s: sleep_log.append(s),
            event_bus=bus,
        )

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Rejection reason is verify_timeout, not recheck_failed.
        assert len(result.rejected) == 1
        _, _, rejected_reason = result.rejected[0]
        assert rejected_reason == "verify_timeout", f"Expected verify_timeout, got {rejected_reason}"

        # CrossSeedRejected with reason=verify_timeout emitted.
        timeout_rejections = [e for e in rejected_events if e.reason == "verify_timeout"]
        assert len(timeout_rejections) == 1
        assert timeout_rejections[0].info_hash == injected_hash


# ===========================================================================
# Tests: sub-phase 11.3 — inject/layout guards + self-delete + queried_names
# ===========================================================================


class TestCheckInjectApiError:
    """test_check_inject_api_error_rejected_inject_failed (11.3a)."""

    def test_inject_api_error_rejected_inject_failed(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Inject raises ApiError → rejected inject_failed, check() continues."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

        # Override inject to raise ApiError.
        def _inject_raises_api_error(
            torrent_bytes: bytes,
            *,
            save_path: str,
            recheck: bool = True,
            paused: bool = True,
        ) -> str:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=0,
                message="test inject failure",
            )

        fake_client.inject = _inject_raises_api_error  # type: ignore[method-assign]

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

        rejected_events: list[CrossSeedRejected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedRejected, lambda e: rejected_events.append(e))

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry, event_bus=bus)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Not injected.
        assert result.injected == []
        # Rejected with inject_failed.
        assert len(result.rejected) == 1
        _, rejected_tracker, rejected_reason = result.rejected[0]
        assert rejected_tracker == _TRACKER_TORR9
        assert rejected_reason == "inject_failed"

        # CrossSeedRejected with reason=inject_failed emitted.
        inject_failures = [e for e in rejected_events if e.reason == "inject_failed"]
        assert len(inject_failures) == 1
        assert inject_failures[0].tracker == _TRACKER_TORR9
        assert inject_failures[0].source_hash == _SOURCE_HASH


class TestCheckInjectValueError:
    """test_check_inject_value_error_rejected_inject_failed (11.3a — ValueError variant)."""

    def test_inject_value_error_rejected_inject_failed(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Inject raises ValueError → rejected inject_failed, check() continues."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )
        candidate_url = "https://torr9.example.com/dl/123"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

        # Override inject to raise ValueError (simulating hash_uncomputable in inject).
        def _inject_raises_value_error(
            torrent_bytes: bytes,
            *,
            save_path: str,
            recheck: bool = True,
            paused: bool = True,
        ) -> str:
            raise ValueError("hash_uncomputable")

        fake_client.inject = _inject_raises_value_error  # type: ignore[method-assign]

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

        rejected_events: list[CrossSeedRejected] = []
        bus = EventBus()
        bus.subscribe(CrossSeedRejected, lambda e: rejected_events.append(e))

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry, event_bus=bus)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        assert result.injected == []
        assert len(result.rejected) == 1
        _, rejected_tracker, rejected_reason = result.rejected[0]
        assert rejected_tracker == _TRACKER_TORR9
        assert rejected_reason == "inject_failed"

        inject_failures = [e for e in rejected_events if e.reason == "inject_failed"]
        assert len(inject_failures) == 1
        assert inject_failures[0].tracker == _TRACKER_TORR9
        assert inject_failures[0].source_hash == _SOURCE_HASH


class TestCheckEmptyFileList:
    """test_check_empty_file_list_skips (11.3b)."""

    def test_empty_file_list_skips_no_raise(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Empty list_files → TorrentLayout ValueError → _build_local_layout returns None → skipped."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()

        fake_client = FakeTorrentClient(completed=[item])
        # Seed empty file list — TorrentLayout.__post_init__ raises ValueError
        # for empty files, but _build_local_layout catches it and returns None.
        fake_client.seed_files(_SOURCE_HASH, [])
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: FakeTracker(provider=_TRACKER_TORR9, results=[]),
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Skipped (local layout is None) — no raise, no crash.
        assert result.skipped is True
        assert result.skip_reason == "no_piece_size"
        assert result.injected == []


class TestObligationWriteFailSelfHash:
    """test_obligation_write_fail_self_hash_no_delete (11.3c)."""

    def test_obligation_write_fail_self_hash_no_delete(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Obligation write fails AND injected_hash == source_hash → delete averted."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]
        candidate_torrent = make_torrent_bytes(
            name=item.name,
            files=source_files,
            piece_length=262144,
        )

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Override inject to return _SOURCE_HASH (simulating qBit Conflict409).
        def _inject_returns_source(
            torrent_bytes: bytes,
            *,
            save_path: str,
            recheck: bool = True,
            paused: bool = True,
        ) -> str:
            fake_client.injected.append((torrent_bytes, save_path, recheck, paused))
            fake_client.injected_hashes.append(_SOURCE_HASH)
            fake_client._files[_SOURCE_HASH] = fake_client._files.get(_SOURCE_HASH, [])
            fake_client._props[_SOURCE_HASH] = {"piece_size": 262144}
            return _SOURCE_HASH

        fake_client.inject = _inject_returns_source  # type: ignore[method-assign]

        candidate_url = "https://torr9.example.com/dl/self-ob"
        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        fake_transport.seed(candidate_url, candidate_torrent)

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

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # Monkeypatch store.seed.add to raise after verification succeeds.
        with patch.object(store.seed, "add", side_effect=RuntimeError("disk full")):
            with caplog.at_level(logging.ERROR, logger="personalscraper.acquire.cross_seed"):
                # -- Act ----------------------------------------------------------
                result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Rejected with obligation_write_failed.
        assert len(result.rejected) == 1
        _, _, rejected_reason = result.rejected[0]
        assert rejected_reason == "obligation_write_failed"

        # NO delete was called (self-delete averted).
        assert len(fake_client.deleted) == 0, (
            f"Delete was called but self-delete guard should have averted it: {fake_client.deleted}"
        )

        # self_delete_averted logged at ERROR.
        assert any("self_delete_averted" in record.message for record in caplog.records), (
            f"Expected self_delete_averted ERROR, got: {[r.message for r in caplog.records]}"
        )


class TestTrackerAbsentFromRegistryNotRecorded:
    """test_tracker_absent_from_registry_not_recorded (11.3d)."""

    def test_tracker_absent_from_registry_not_recorded(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Tracker in remaining but absent from registry → NOT recorded as searched.

        When a tracker is not registered (client None in the registry), it
        never appears in queried_names.  The record_search filter must skip
        it — otherwise it gets a false 3-day lockout.
        """
        # -- Arrange ----------------------------------------------------------
        item = _source_item()
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Only lacale is registered — torr9 is absent (client None in
        # FakeRegistry).  lacale is origin (excluded from remaining),
        # torr9 is in remaining but not in queried_names.
        fake_registry = make_registry(
            {_TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[])},
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        cfg = make_config(tmp_path)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # No candidates from any tracker → no injection.
        assert result.injected == []

        # torr9 was in remaining but NOT in queried_names → NOT recorded.
        assert store.cross_seed.was_searched_recently(_SOURCE_HASH, _TRACKER_TORR9, days=3) is False, (
            "torr9 should NOT be recorded as searched — it was never queried (client None)"
        )

        # lacale is origin → excluded from remaining → never recorded either.
        assert store.cross_seed.was_searched_recently(_SOURCE_HASH, _TRACKER_LACALE, days=3) is False


# ===========================================================================
# Tests: sub-phase 11.4 — sweep item-error accounting + throttle-hole fix
# ===========================================================================


class TestSweepItemErrors:
    """test_sweep_item_errors_counted_and_throttle_holds (11.4a)."""

    def test_one_item_raises_item_errors_counted_quota_consumed(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """One item raises in sweep → item_errors=1, quota consumed, throttle holds.

        The throttle-hole fix: per-item errors used to bypass quota+need_sleep,
        allowing an unbounded fast-iterate error loop.  After the fix, even
        errored items consume a daily quota slot and set the need_sleep flag.
        """
        # -- Arrange ----------------------------------------------------------
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        items = [
            _source_item(info_hash=f"hash{i:040d}", name=f"Movie.{i}.2024", save_path=f"/data/Movie.{i}.2024")
            for i in range(3)
        ]

        fake_client = FakeTorrentClient(completed=list(items))
        for i in range(3):
            fake_client.seed_files(f"hash{i:040d}", source_files)
            fake_client.seed_properties(f"hash{i:040d}", {"piece_size": 262144})

        candidate_bytes = [make_torrent_bytes(name=items[i].name, files=source_files) for i in range(3)]

        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        for i, cb in enumerate(candidate_bytes):
            fake_transport.seed(f"https://torr9.example.com/dl/{i}", cb)

        fake_torrent_tracker = FakeTracker(
            provider=_TRACKER_TORR9,
            transport=fake_transport,
            results=[
                _candidate_result(
                    provider=_TRACKER_TORR9,
                    title=items[i].name,
                    download_url=f"https://torr9.example.com/dl/{i}",
                )
                for i in range(3)
            ],
        )

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: fake_torrent_tracker,
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        # Make check() raise on the second call (item index 1).
        import personalscraper.acquire.cross_seed as cs_module

        check_calls = [0]
        original_check = cs_module.CrossSeedService.check

        def _check_raises_on_nth(self: Any, info_hash: str) -> CrossSeedResult:
            check_calls[0] += 1
            if check_calls[0] == 2:
                raise RuntimeError("simulated transient error")
            return original_check(self, info_hash)

        cfg = make_config(tmp_path, max_searches_per_day=10)
        sleep_log: list[float] = []
        svc = _build_service(cfg, store, fake_client, fake_registry, sleep=lambda s: sleep_log.append(s))

        # -- Act --------------------------------------------------------------
        with (
            patch.object(cs_module.CrossSeedService, "check", _check_raises_on_nth),
            caplog.at_level(logging.ERROR, logger="personalscraper.acquire.cross_seed"),
        ):
            result = svc.sweep()

        # -- Assert -----------------------------------------------------------
        # Item 0 succeeded, item 1 errored, item 2 succeeded.
        assert result.checked == 2  # Two items returned normally.
        assert result.injected == 2  # Both successful checks injected.
        assert result.item_errors == 1  # One item raised.
        assert result.quota_exhausted is False

        # sweep_item_error logged at ERROR.
        assert any("sweep_item_error" in record.message for record in caplog.records), (
            f"Expected sweep_item_error ERROR, got: {[r.message for r in caplog.records]}"
        )

        # Throttle holds: sleep was called between items (at least 2 sleeps for
        # 3 items where none were skipped).  Before the fix, need_sleep was
        # never set on error paths, so the loop would fast-iterate without delay.
        assert len(sleep_log) >= 2, f"Expected >= 2 sleeps (throttle held), got {len(sleep_log)}"

        # Quota was consumed for all 3 items (including the errored one).
        # daily_searches_remaining starts at 10; 3 quota units consumed → 7 remaining.
        assert store.cross_seed.daily_searches_remaining(10) == 7, (
            f"Expected 7 remaining (3 consumed), got {store.cross_seed.daily_searches_remaining(10)}"
        )

    def test_all_items_raise_checked_zero_item_errors_positive(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Every item raises → checked=0, item_errors>0 (total failure signal)."""
        # -- Arrange ----------------------------------------------------------
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        items = [
            _source_item(info_hash=f"hash{i:040d}", name=f"Movie.{i}.2024", save_path=f"/data/Movie.{i}.2024")
            for i in range(2)
        ]

        fake_client = FakeTorrentClient(completed=list(items))
        for i in range(2):
            fake_client.seed_files(f"hash{i:040d}", source_files)
            fake_client.seed_properties(f"hash{i:040d}", {"piece_size": 262144})

        candidate_bytes = [make_torrent_bytes(name=items[i].name, files=source_files) for i in range(2)]

        fake_transport = FakeTransport(provider_name=_TRACKER_TORR9)
        for i, cb in enumerate(candidate_bytes):
            fake_transport.seed(f"https://torr9.example.com/dl/{i}", cb)

        fake_torrent_tracker = FakeTracker(
            provider=_TRACKER_TORR9,
            transport=fake_transport,
            results=[
                _candidate_result(
                    provider=_TRACKER_TORR9,
                    title=items[i].name,
                    download_url=f"https://torr9.example.com/dl/{i}",
                )
                for i in range(2)
            ],
        )

        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(provider=_TRACKER_LACALE, results=[]),
                _TRACKER_TORR9: fake_torrent_tracker,
            },
            priority=[_TRACKER_LACALE, _TRACKER_TORR9],
        )

        # Make every check() call raise.
        import personalscraper.acquire.cross_seed as cs_module

        def _check_always_raises(self: Any, info_hash: str) -> CrossSeedResult:
            raise RuntimeError("simulated persistent error")

        cfg = make_config(tmp_path, max_searches_per_day=10)
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        with (
            patch.object(cs_module.CrossSeedService, "check", _check_always_raises),
            caplog.at_level(logging.ERROR, logger="personalscraper.acquire.cross_seed"),
        ):
            result = svc.sweep()

        # -- Assert -----------------------------------------------------------
        assert result.checked == 0  # No item returned normally.
        assert result.injected == 0
        assert result.item_errors == 2  # Both items errored.
        assert result.quota_exhausted is False

        # Both errors logged.
        error_count = sum(1 for r in caplog.records if "sweep_item_error" in r.message)
        assert error_count == 2, f"Expected 2 sweep_item_error, got {error_count}"
