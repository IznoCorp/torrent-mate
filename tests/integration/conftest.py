"""Shared fixtures for the integration test tier.

Provides infrastructure fixtures (staging tree, fake disks, Config) and
lightweight in-memory stubs for external APIs (TMDB, TVDB, qBittorrent).
All fixtures are function-scoped unless stated otherwise.

Tier isolation: this module must never import from tests.e2e — the two tiers
are independently evolvable. The guard below enforces this at collection time.
"""

import sys

# Snapshot sys.modules before any further imports so we can detect whether
# *this conftest's* import chain pulls in tests.e2e.  Only `sys` is needed
# here; the rest of the imports follow below.  This must stay above all other
# imports to capture an accurate before-state.
_e2e_in_sys_before_our_imports = "tests.e2e" in sys.modules  # noqa: E402

import json  # noqa: E402
import shutil  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402

from personalscraper.api.metadata._base import SearchResult  # noqa: E402
from personalscraper.conf import ids as CID  # noqa: E402
from personalscraper.conf.models.config import Config  # noqa: E402
from personalscraper.conf.models.disks import DiskConfig  # noqa: E402
from personalscraper.conf.staging import folder_name  # noqa: E402

# ---------------------------------------------------------------------------
# Tier isolation guard — fails collection loudly if *this conftest's* own
# imports caused tests.e2e to be loaded.
#
# In a full pytest session, e2e/ is collected before integration/ (alphabetical:
# 'e' < 'i'), so tests.e2e enters sys.modules before this conftest runs.  That
# is harmless — the guard skips when tests.e2e was already present beforehand.
# When running `pytest tests/integration/` in isolation, tests.e2e is absent;
# any drift (accidental import of e2e symbols) is caught here at collection time.
# ---------------------------------------------------------------------------
if not _e2e_in_sys_before_our_imports:
    if "tests.e2e" in sys.modules:
        raise RuntimeError("tests/integration/ must not import from tests/e2e/ — these are distinct tiers.")

# ---------------------------------------------------------------------------
# Fixture JSON payload directory
# ---------------------------------------------------------------------------
_FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Staging / disk infrastructure fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def staging_tree(tmp_path: Path, test_config: Config) -> Path:
    """Build the staging subdirectory tree under tmp_path/staging.

    Creates one subdirectory per entry in ``test_config.staging_dirs``,
    using the same ``folder_name()`` convention as production code so that
    any component reading ``config.paths.staging_dir`` sees the expected layout.

    Args:
        tmp_path: Pytest temporary directory (unique per test).
        test_config: Synthetic Config fixture from tests/fixtures/config.py.

    Returns:
        Path to the staging root (``tmp_path / "staging"``), which exists
        and contains all configured staging subdirectories.
    """
    root = tmp_path / "staging"
    root.mkdir(parents=True, exist_ok=True)
    for entry in test_config.staging_dirs:
        (root / folder_name(entry)).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def fake_disks(tmp_path: Path) -> list[Path]:
    """Build four fake disk root directories under tmp_path.

    Creates ``Disk1`` through ``Disk4`` as empty directories that can be
    used as disk paths in an integration Config without touching real storage.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        List of four Path objects (``tmp_path/Disk1`` … ``tmp_path/Disk4``),
        each existing on the filesystem.
    """
    disks: list[Path] = []
    for i in range(1, 5):
        d = tmp_path / f"Disk{i}"
        d.mkdir(parents=True, exist_ok=True)
        disks.append(d)
    return disks


@pytest.fixture()
def integration_config(staging_tree: Path, fake_disks: list[Path], test_config: Config) -> Config:
    """Compose a validated Config wired to the integration fixture paths.

    Seeds from ``test_config`` (stable 11-category, 3-disk base), then
    overrides:
    - ``paths.staging_dir`` → ``staging_tree``
    - ``disks`` → four DiskConfig entries pointing at ``fake_disks``
    - ``indexer.db_path`` → ``paths.data_dir / "library.db"`` so dispatch and
      assertions share a tmp_path-scoped SQLite file (the default
      ``IndexerConfig.db_path`` is a CWD-relative path that would otherwise
      land in the developer's real ``.data/library.db``).

    The 11 builtin category IDs from ``test_config`` are redistributed
    across the four fake disks so every disk has at least one category and
    the Config passes its own validators.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        fake_disks: List of four fake disk root paths.
        test_config: Synthetic Config from tests/fixtures/config.py.

    Returns:
        Validated Config instance with paths pointing at tmp_path fixtures.
    """
    # Override paths — staging_dir points at the fixture tree.
    new_paths = test_config.paths.model_copy(update={"staging_dir": staging_tree})

    # Rebuild four DiskConfig entries.  Category distribution mirrors the
    # spirit of test_config but split across 4 disks so the smoke test can
    # assert len(fake_disks) == 4 and Config validation passes.
    new_disks = [
        DiskConfig(
            id="disk1",
            path=fake_disks[0],
            categories=[CID.MOVIES, CID.TV_SHOWS],
        ),
        DiskConfig(
            id="disk2",
            path=fake_disks[1],
            categories=[CID.ANIME, CID.MOVIES_ANIMATION, CID.TV_SHOWS_ANIMATION],
        ),
        DiskConfig(
            id="disk3",
            path=fake_disks[2],
            categories=[CID.MOVIES_DOCUMENTARY, CID.TV_SHOWS_DOCUMENTARY, CID.STANDUP],
        ),
        DiskConfig(
            id="disk4",
            path=fake_disks[3],
            categories=[CID.AUDIOBOOKS, CID.THEATER, CID.TV_PROGRAMS],
        ),
    ]

    # Pin indexer.db_path under tmp_path/data_dir so dispatch never writes
    # into the developer's real library.db via the relative default.
    new_indexer = test_config.indexer.model_copy(update={"db_path": new_paths.data_dir / "library.db"})

    # Disable disk-space thresholds so tests never fail on small /tmp partitions
    # (CI runners often have less than the default 20 GB / 100 GB thresholds).
    new_thresholds = test_config.thresholds.model_copy(
        update={"min_free_space_staging_gb": 0, "min_free_space_disk_gb": 0.0}
    )

    return test_config.model_copy(
        update={
            "paths": new_paths,
            "disks": new_disks,
            "indexer": new_indexer,
            "thresholds": new_thresholds,
        }
    )


@pytest.fixture()
def integration_config_path(integration_config: Config, tmp_path: Path) -> Path:
    """Serialise the integration Config to a JSON5-compatible file on disk.

    Plain JSON is valid JSON5, so ``json.dump`` is sufficient.  The file
    is written to ``tmp_path / "config.json5"`` and is suitable for tests
    that invoke the CLI and require a real config file path.

    Args:
        integration_config: Fully composed integration Config fixture.
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Path to the written config.json5 file.
    """
    config_path = tmp_path / "config.json5"
    # model_dump with mode="json" converts Path objects to strings,
    # which is required for json.dump serialisation.
    config_data = integration_config.model_dump(mode="json")
    config_path.write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return config_path


# ---------------------------------------------------------------------------
# Helpers — convert legacy dict-shaped TMDB/TVDB canned responses to typed
# SearchResult instances (api-unify TMDBClient / TVDBClient now emit these).
# ---------------------------------------------------------------------------


def _dict_to_movie_search_result(d: dict[str, Any]) -> SearchResult:
    """Reshape ``{"id", "title", "release_date"}`` → ``SearchResult``."""
    rd = d.get("release_date") or ""
    return SearchResult(
        provider="tmdb",
        provider_id=str(d.get("id", "")),
        title=d.get("title", ""),
        year=int(rd[:4]) if rd[:4].isdigit() else None,
        media_type="movie",
    )


def _dict_to_tv_search_result(d: dict[str, Any]) -> SearchResult:
    """Reshape ``{"id", "name", "first_air_date"}`` → ``SearchResult``."""
    fad = d.get("first_air_date") or ""
    return SearchResult(
        provider="tmdb",
        provider_id=str(d.get("id", "")),
        title=d.get("name", ""),
        year=int(fad[:4]) if fad[:4].isdigit() else None,
        media_type="tv",
    )


def _dict_to_tvdb_search_result(d: dict[str, Any]) -> SearchResult:
    """Reshape ``{"tvdb_id", "name", "year"}`` → ``SearchResult``."""
    y = str(d.get("year") or "")
    return SearchResult(
        provider="tvdb",
        provider_id=str(d.get("tvdb_id", "")),
        title=d.get("name", ""),
        year=int(y) if y.isdigit() else None,
        media_type="tv",
    )


# ---------------------------------------------------------------------------
# Fake API client stubs
# ---------------------------------------------------------------------------


@dataclass
class FakeCircuit:
    """Minimal stub for CircuitBreaker used by TMDBClient / TVDBClient.

    Always reports the circuit as closed (``can_proceed() → True``) so
    integration tests are never short-circuited by the breaker logic.

    Attributes:
        _open: When True, simulates an open circuit.  Default False (closed).
    """

    _open: bool = False

    def can_proceed(self) -> bool:
        """Return True when the circuit is closed (default), False when open.

        Returns:
            Whether the caller is allowed to proceed with the API call.
        """
        return not self._open

    def record_success(self) -> None:
        """No-op — stub does not track success counts.

        Returns:
            None.
        """

    def record_failure(self) -> None:
        """No-op — stub does not track failure counts.

        Returns:
            None.
        """


@dataclass
class FakeTMDB:
    """In-memory stub for TMDBClient.

    Stores canned JSON responses keyed by (endpoint_fragment, params_tuple)
    and returns them via ``_get()``. Tests can preload responses using
    ``seed()`` before exercising code that calls the client.

    Attributes:
        _responses: Mapping from endpoint path fragment to response dict.
        _default: Fallback response returned when no key matches.
        circuit: Always-closed circuit breaker stub so process_movies/process_tvshows
            never short-circuits on ``self._tmdb.circuit.can_proceed()``.
    """

    _responses: dict[str, Any] = field(default_factory=dict)
    _default: dict[str, Any] = field(default_factory=lambda: {"results": []})
    circuit: FakeCircuit = field(default_factory=FakeCircuit)

    def seed(self, endpoint_fragment: str, payload: dict[str, Any]) -> None:
        """Register a canned JSON response for a given endpoint fragment.

        Args:
            endpoint_fragment: Substring of the TMDB endpoint path
                (e.g. ``"search/movie"``, ``"movie/1020053"``).
            payload: JSON-serialisable dict to return when the endpoint
                fragment is matched.
        """
        self._responses[endpoint_fragment] = payload

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the canned response for the best-matching endpoint fragment.

        Args:
            endpoint: The TMDB endpoint path (e.g. ``"/search/movie"``).
            params: Optional query parameters (ignored by the stub).

        Returns:
            Canned dict registered via ``seed()``, or ``_default`` if no
            fragment matches.
        """
        for fragment, payload in self._responses.items():
            if fragment in endpoint:
                return payload
        return self._default

    # Minimal protocol surface so callers of search/get_movie/get_tv work.

    def search_movie(self, title: str, year: int | None = None) -> list[SearchResult]:
        """Return canned movie search results as typed SearchResult instances.

        Reshapes the legacy ``{"id", "title", "release_date"}`` dicts the canned
        responses use into the api-unify ``SearchResult`` model that the real
        TMDBClient now emits.

        Args:
            title: Movie title query (unused by stub).
            year: Optional release year filter (unused by stub).

        Returns:
            List of ``SearchResult`` instances built from canned dicts.
        """
        data = self._get("/search/movie")
        return [_dict_to_movie_search_result(r) for r in data.get("results", [])]

    def search_tv(self, title: str, year: int | None = None) -> list[SearchResult]:
        """Return canned TV search results as typed SearchResult instances.

        Args:
            title: Series title query (unused by stub).
            year: Optional first-air-year filter (unused by stub).

        Returns:
            List of ``SearchResult`` instances built from canned dicts.
        """
        data = self._get("/search/tv")
        return [_dict_to_tv_search_result(r) for r in data.get("results", [])]

    def search(self, title: str, year: int | None = None, media_type: str = "movie") -> list[SearchResult]:
        """Dispatch to search_movie or search_tv based on media_type.

        Args:
            title: Title query.
            year: Optional year filter.
            media_type: ``"movie"`` or ``"tv"``.

        Returns:
            List of result dicts.
        """
        if media_type == "tv":
            return self.search_tv(title, year)
        return self.search_movie(title, year)

    def get_movie(self, movie_id: int) -> dict[str, Any]:
        """Return canned movie details.

        Args:
            movie_id: TMDB movie ID (unused by stub).

        Returns:
            Canned response for ``movie/{movie_id}`` or default.
        """
        return self._get(f"/movie/{movie_id}")

    def get_tv(self, tv_id: int) -> dict[str, Any]:
        """Return canned TV show details.

        Args:
            tv_id: TMDB TV series ID (unused by stub).

        Returns:
            Canned response for ``tv/{tv_id}`` or default.
        """
        return self._get(f"/tv/{tv_id}")

    def get_keywords(self, tmdb_id: int, media_type: str = "movie") -> list[str]:
        """Return an empty keyword list (stub — keywords not exercised here).

        Args:
            tmdb_id: TMDB ID (unused).
            media_type: Media type (unused).

        Returns:
            Empty list.
        """
        return []


@dataclass
class FakeTVDB:
    """In-memory stub for TVDBClient.

    Mirrors FakeTMDB in design: stores canned responses keyed by endpoint
    fragment and returns them through the same minimal protocol surface.

    Attributes:
        _responses: Mapping from endpoint path fragment to response dict.
        _default: Fallback response when no fragment matches.
        circuit: Always-closed circuit breaker stub so process_tvshows never
            short-circuits on ``self._tvdb.circuit.can_proceed()``.
    """

    _responses: dict[str, Any] = field(default_factory=dict)
    _default: dict[str, Any] = field(default_factory=lambda: {"data": {}})
    circuit: FakeCircuit = field(default_factory=FakeCircuit)

    def seed(self, endpoint_fragment: str, payload: dict[str, Any]) -> None:
        """Register a canned response for a TVDB endpoint fragment.

        Args:
            endpoint_fragment: Substring matched against the endpoint path.
            payload: Dict to return on match.
        """
        self._responses[endpoint_fragment] = payload

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the canned response for the best-matching endpoint.

        Args:
            endpoint: TVDB endpoint path.
            params: Optional query parameters (ignored).

        Returns:
            Canned dict or ``_default``.
        """
        for fragment, payload in self._responses.items():
            if fragment in endpoint:
                return payload
        return self._default

    def search_series(self, title: str, year: int | None = None) -> list[SearchResult]:
        """Return canned series search results as typed SearchResult instances.

        Reshapes the legacy ``{"tvdb_id", "name", "year"}`` dicts the canned
        responses use into the api-unify ``SearchResult`` model.

        Args:
            title: Series title query (unused by stub).
            year: Optional year filter (unused by stub).

        Returns:
            List of ``SearchResult`` instances built from canned dicts.
        """
        data = self._get("/search")
        if isinstance(data, dict):
            payload = data.get("data", []) if isinstance(data.get("data"), list) else []
            return [_dict_to_tvdb_search_result(r) for r in payload]
        return []

    def search(self, title: str, year: int | None = None, media_type: str = "tv") -> list[SearchResult]:
        """MetadataProvider protocol dispatch — delegates to search_series.

        Args:
            title: Title query.
            year: Optional year filter.
            media_type: Media type (unused by stub).

        Returns:
            List of result dicts.
        """
        return self.search_series(title, year)

    def get_series(self, series_id: int) -> dict[str, Any]:
        """Return canned series details.

        Args:
            series_id: TVDB series ID (unused by stub).

        Returns:
            Canned ``data`` dict or empty dict.
        """
        raw = self._get(f"/series/{series_id}")
        if isinstance(raw, dict):
            return raw.get("data", raw)
        return {}

    def get_series_episodes(self, series_id: int, season: int) -> list[dict[str, Any]]:
        """Return an empty episode list (stub — episodes not exercised here).

        Args:
            series_id: TVDB series ID (unused).
            season: Season number (unused).

        Returns:
            Empty list.
        """
        return []


@dataclass
class FakeTorrent:
    """Minimal torrent record for integration tests.

    Carries only the attributes consumed by ``ingest.run_ingest(event_bus=EventBus())`` and
    ``FakeQBitClient.get_content_path()``.  Extend fields here (not in
    production code) when new ingest invariants need to be exercised.

    Attributes:
        name: Human-readable torrent name.
        hash: Unique torrent hash string.
        content_path: Absolute filesystem path to torrent content.
        ratio: Seeding ratio (upload / download).  Default 0.0.
    """

    name: str
    hash: str  # noqa: A003 — mirrors qbittorrentapi TorrentDictionary attribute name
    content_path: str
    ratio: float = 0.0


@dataclass
class FakeQBitClient:
    """In-memory stub for QBitClient / qbittorrentapi.Client.

    Supports separate completed-torrent and all-torrent lists so that tests
    can model incomplete torrents (present in qBittorrent but not yet done).

    - ``seed(torrent_list)`` sets the completed list (returned by
      ``get_completed``). The all-torrent list is set to the same
      value unless ``seed_all`` was also called.
    - ``seed_all(torrent_list)`` sets the broader all-torrent list used by
      ``get_all_hashes``.  Call this **after** ``seed()`` to add
      incomplete torrents without including them in the completed list.

    Attributes:
        _torrents: Completed torrents returned by get_completed.
        _all_torrents: All torrents (completed + incomplete) used for hash lookup.
    """

    _torrents: list[Any] = field(default_factory=list)
    _all_torrents: list[Any] = field(default_factory=list)

    def seed(self, torrent_list: list[Any]) -> None:
        """Inject completed torrents.  Also resets the all-torrent list to match.

        Call ``seed_all()`` afterwards to extend the all-torrent list with
        incomplete torrents without including them in the completed list.

        Args:
            torrent_list: List of torrent-like objects (FakeTorrent or MagicMock).
        """
        self._torrents = list(torrent_list)
        # Keep all-torrent list in sync with completed by default.
        self._all_torrents = list(torrent_list)

    def seed_all(self, torrent_list: list[Any]) -> None:
        """Extend the all-torrent list with additional (e.g. incomplete) torrents.

        The completed list is unaffected.  Duplicates (same objects as in the
        completed list) are harmless — ``get_all_hashes`` uses a set.

        Args:
            torrent_list: Additional torrent-like objects to add to the
                all-torrent list (not the completed list).
        """
        self._all_torrents = list(self._all_torrents) + list(torrent_list)

    def get_completed(self) -> list[Any]:
        """Return the seeded list of completed torrents.

        Returns:
            List of torrent objects previously injected via ``seed()``.
        """
        return list(self._torrents)

    def get_all_hashes(self) -> set[str]:
        """Return hashes of all torrents (completed + incomplete).

        Returns:
            Set of hash strings from both the completed and all-torrent lists.
        """
        return {t.hash for t in self._all_torrents if hasattr(t, "hash")}

    def get_content_path(self, torrent: Any) -> Path:
        """Resolve the filesystem path of a torrent's content.

        Args:
            torrent: A FakeTorrent or any object with a ``content_path`` attribute.

        Returns:
            Path to the torrent's content.
        """
        return Path(torrent.content_path)

    def is_seeding(self, torrent: Any) -> bool:
        """Return False — stub never reports a torrent as seeding.

        Args:
            torrent: Torrent object (unused).

        Returns:
            Always False.
        """
        return False

    def login(self) -> None:
        """No-op login (stub)."""

    def logout(self) -> None:
        """No-op logout (stub)."""

    def __enter__(self) -> "FakeQBitClient":
        """Return self as context manager.

        Returns:
            Self.
        """
        return self

    def __exit__(self, *exc: object) -> None:
        """No-op context exit.

        Args:
            *exc: Exception info (ignored).
        """


# ---------------------------------------------------------------------------
# Monkeypatched fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_tmdb(monkeypatch: pytest.MonkeyPatch) -> FakeTMDB:
    """Monkeypatch TMDBClient with an in-memory FakeTMDB stub.

    Patches ``personalscraper.api.metadata.tmdb.TMDBClient`` so that any
    code constructing a TMDBClient receives a FakeTMDB instance instead.
    Preloads canned responses from ``tests/integration/fixtures/tmdb/``.

    We patch the class constructor (``__new__`` via side_effect on the class
    mock) rather than ``_session`` because the stub replaces the entire
    client object — no real HTTP session is created at all.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Configured FakeTMDB instance with fixture payloads pre-seeded.
    """
    stub = FakeTMDB()

    # Pre-seed from fixture files so any test can rely on known payloads.
    for json_file in (_FIXTURES_DIR / "tmdb").glob("*.json"):
        payload = json.loads(json_file.read_text(encoding="utf-8"))
        # Key by stem (e.g. "movie_shrinking", "tv_fallout", "search_empty")
        stub.seed(json_file.stem, payload)

    # Build a mock TMDBClient class that accepts the new constructor
    # (transport=HttpTransport(..., event_bus=EventBus()), language=...) and also supports
    # the .policy() classmethod used by orchestrator/rescraper.
    mock_cls = MagicMock()
    mock_cls.policy.return_value = MagicMock()  # TransportPolicy mock
    mock_cls.return_value = stub  # TMDBClient(transport=...) returns the stub

    monkeypatch.setattr(
        "personalscraper.api.metadata.tmdb.TMDBClient",
        mock_cls,
    )
    monkeypatch.setattr(
        "personalscraper.scraper.scraper.TMDBClient",
        mock_cls,
    )
    # Mock HttpTransport so Scraper.__init__ doesn't build real sessions.
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.post.return_value = {"data": {"token": "mock-jwt"}}

    monkeypatch.setattr(
        "personalscraper.api.transport._http.HttpTransport",
        lambda *a, **kw: mock_instance,
    )
    monkeypatch.setattr(
        "personalscraper.api.metadata.tvdb.HttpTransport",
        lambda *a, **kw: mock_instance,
    )
    return stub


@pytest.fixture()
def fake_tvdb(monkeypatch: pytest.MonkeyPatch) -> FakeTVDB:
    """Monkeypatch TVDBClient with an in-memory FakeTVDB stub.

    Patches ``personalscraper.api.metadata.tvdb.TVDBClient`` so that any
    code constructing a TVDBClient receives a FakeTVDB instance instead.
    Preloads canned responses from ``tests/integration/fixtures/tvdb/``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Configured FakeTVDB instance with fixture payloads pre-seeded.
    """
    stub = FakeTVDB()

    for json_file in (_FIXTURES_DIR / "tvdb").glob("*.json"):
        payload = json.loads(json_file.read_text(encoding="utf-8"))
        stub.seed(json_file.stem, payload)

    monkeypatch.setattr(
        "personalscraper.api.metadata.tvdb.TVDBClient",
        lambda *args, **kwargs: stub,
    )
    # Also patch the already-imported name in scraper.py (same rationale as fake_tmdb).
    monkeypatch.setattr(
        "personalscraper.scraper.scraper.TVDBClient",
        lambda *args, **kwargs: stub,
    )
    return stub


@pytest.fixture()
def fake_qbit(monkeypatch: pytest.MonkeyPatch) -> FakeQBitClient:
    """Monkeypatch qbittorrentapi.Client and QBitClient with an in-memory stub.

    Patches both the underlying ``qbittorrentapi.Client`` (used in
    ``personalscraper.api.torrent.qbittorrent``) and the ``build_active_torrent_client``
    factory imported in ``personalscraper.ingest.ingest`` so that no real qBittorrent
    connection is attempted.  The stub starts with an empty torrent list;
    call ``stub.seed([...])`` to inject test torrents before running ingest.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        FakeQBitClient instance (empty torrent list by default).
    """
    stub = FakeQBitClient()

    # Patch the factory used in ingest.py so the pipeline receives the stub
    # without any network calls.
    monkeypatch.setattr(
        "personalscraper.ingest.ingest.build_active_torrent_client",
        lambda *args, **kwargs: stub,
    )
    # Also patch QBitClient directly in ingest.py for the fallback path
    # (torrent.active="" → else branch that instantiates QBitClient directly).
    monkeypatch.setattr(
        "personalscraper.ingest.ingest.QBitClient",
        lambda *args, **kwargs: stub,
    )
    # Also patch qbittorrentapi.Client to guard against direct instantiation
    # in qbittorrent.py (belt-and-suspenders: QBitClient wraps it).
    mock_qbit_cls = MagicMock()
    mock_qbit_cls.return_value = MagicMock()
    monkeypatch.setattr("personalscraper.api.torrent.qbittorrent.qbittorrentapi.Client", mock_qbit_cls)

    return stub


# ---------------------------------------------------------------------------
# Environment / infrastructure guards
# ---------------------------------------------------------------------------


@pytest.fixture()
def rsync_available() -> None:
    """Skip the test if rsync is not available on this system.

    Use as a fixture dependency for any integration test that relies on
    rsync for file transfer operations.  Raises ``pytest.skip`` at
    setup time when ``shutil.which("rsync")`` returns None.
    """
    if shutil.which("rsync") is None:
        pytest.skip("rsync not available on this system")
