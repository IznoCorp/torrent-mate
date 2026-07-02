"""Integration tests for :class:`~personalscraper.acquire.cross_seed.CrossSeedService`.

Tests with faked tracker registry, transport, and torrent client covering the
10 planned cases (ACC-6). A real ``ConcreteAcquireStore`` on ``tmp_path`` and
real bencode for candidate ``.torrent`` bytes exercise ``parse_torrent_layout``
and ``structural_match`` without any parsing mocks.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.cross_seed import CrossSeedService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._contracts import MediaType
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
        all_results: list[TrackerResult] = []
        queried = 0
        for name in self._priority:
            tracker = self._trackers.get(name)
            if tracker is None:
                continue
            queried += 1
            all_results.extend(tracker.search(query, media_type, year))
        return SearchOutcome(
            results=all_results,
            trackers_queried=queried,
            trackers_errored=0,
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


@pytest.fixture
def fake_clock() -> Iterator[list[float]]:
    """Yield a mutable float list usable as a fake monotonic clock.

    Usage in tests::

        clock = fake_clock
        service = CrossSeedService(..., clock=lambda: clock[0])
        clock[0] = 130.0  # advance past verify timeout
    """
    yield [0.0]


@pytest.fixture
def fake_sleep() -> Iterator[list[float]]:
    """Yield a list that records every sleep duration.

    Usage in tests::

        sleep_log = fake_sleep
        service = CrossSeedService(..., sleep=lambda s: sleep_log.append(s))
        assert sleep_log == [30.0]
    """
    yield []


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
) -> CrossSeedService:
    """Build a :class:`CrossSeedService` with all fakes wired in.

    Args:
        config: Test :class:`Config`.
        store: Real :class:`ConcreteAcquireStore`.
        fake_client: :class:`FakeTorrentClient` implementing all four protocols.
        fake_registry: :class:`FakeRegistry` for search + transport resolution.
        clock: Optional fake clock callable.
        sleep: Optional fake sleep callable.

    Returns:
        A fully wired :class:`CrossSeedService`.
    """
    import time as _time_module

    return CrossSeedService(
        registry=fake_registry,  # type: ignore[arg-type]  # FakeRegistry, not TrackerRegistry
        lister=fake_client,
        injector=fake_client,
        controller=fake_client,
        tagger=fake_client,
        store=store,
        config=config,
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
        # Result shape.
        assert result.injected == [injected_hash]
        assert result.rejected == []
        assert result.skipped is False
        assert result.skip_reason is None

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

        svc = _build_service(
            cfg,
            store,
            fake_client,
            fake_registry,
            clock=lambda: next(clock_ticks),
            sleep=lambda s: sleep_log.append(s),
        )

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Not injected.
        assert result.injected == []
        # Rejected with reason recheck_failed.
        assert len(result.rejected) == 1
        _, rejected_tracker, rejected_reason = result.rejected[0]
        assert rejected_tracker == _TRACKER_TORR9
        assert rejected_reason == "recheck_failed"

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
    """test_check_origin_tracker_excluded."""

    def test_origin_tracker_excluded(
        self,
        tmp_path: Path,
        store: ConcreteAcquireStore,
    ) -> None:
        """Source item tagged with 'lacale' → candidates from 'lacale' are not processed."""
        # -- Arrange ----------------------------------------------------------
        item = _source_item(tags=[_TRACKER_LACALE])
        source_files = [("Movie.2024.1080p.BluRay.x264-GROUP.mkv", 2_000_000_000)]

        fake_client = FakeTorrentClient(completed=[item])
        fake_client.seed_files(_SOURCE_HASH, source_files)
        fake_client.seed_properties(_SOURCE_HASH, {"piece_size": 262144})

        # Both candidates are from lacale (origin) — should be excluded.
        fake_transport = FakeTransport(provider_name=_TRACKER_LACALE)

        # Only lacale configured (no other trackers).
        fake_registry = make_registry(
            {
                _TRACKER_LACALE: FakeTracker(
                    provider=_TRACKER_LACALE,
                    transport=fake_transport,
                    results=[
                        _candidate_result(provider=_TRACKER_LACALE, download_url="https://lacale.example.com/dl/1")
                    ],
                ),
            },
            priority=[_TRACKER_LACALE],
        )

        cfg = make_config(
            tmp_path,
            tracker_providers={
                _TRACKER_LACALE: _tracker_provider(),
            },
            tracker_priority=[_TRACKER_LACALE],
        )
        svc = _build_service(cfg, store, fake_client, fake_registry)

        # -- Act --------------------------------------------------------------
        result = svc.check(_SOURCE_HASH)

        # -- Assert -----------------------------------------------------------
        # Skipped because all eligible trackers excluded (origin == only tracker).
        assert result.skipped is True
        # Could be "all_excluded_recent" if no remaining trackers after excluding origin.
        assert result.skip_reason is not None
        assert result.injected == []


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
