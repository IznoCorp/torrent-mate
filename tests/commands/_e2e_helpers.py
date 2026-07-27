"""Shared E2E helpers for library-* command tests.

Centralized to avoid copy-paste in 25+ test files.
Each helper is importable by individual _e2e.py files without pulling in
transitive test dependencies (Typer CliRunner, pytest fixtures, etc.).
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from personalscraper.conf.models.config import Config


def make_synthetic_db(tmp_path: Path) -> Path:
    """Create a fully-migrated DB in tmp_path/library.db. Return the path."""
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

    db_path = tmp_path / "test_indexer.db"
    migrations_dir = Path(_migrations_pkg.__file__).parent
    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, migrations_dir)
    conn.commit()
    conn.close()
    return db_path


def make_test_config_with_db(test_config: Config, db_path: Path) -> Config:
    """Return a copy of *test_config* with ``indexer.db_path`` pointed at *db_path*."""
    return test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": db_path})})


def seed_disk(conn: sqlite3.Connection, label: str, mount_path: Path) -> int:
    """Insert a mounted disk row and return its id."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (f"uuid-{label}", label, str(mount_path), now),
    )
    conn.commit()
    return cursor.lastrowid


def seed_phantom_path(
    conn: sqlite3.Connection,
    disk_id: int,
    rel_path: str,
    n_files: int = 3,
) -> int:
    """Seed a path row whose absolute path doesn't exist + *n_files* media_files under it.

    Returns the path_id.  ``detect_path_missing`` will flag it because
    ``mount_path / rel_path`` does not exist on the filesystem.
    """
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    path_id: int = cursor.lastrowid  # type: ignore[assignment]
    for i in range(n_files):
        conn.execute(
            """
            INSERT INTO media_file (
                release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
                oshash, enriched_at, scan_generation, last_verified_at, deleted_at
            ) VALUES (NULL, ?, ?, 1000, 1700000000000000000, 1700000000000000000,
                      NULL, NULL, 1, ?, NULL)
            """,
            (path_id, f"file_{i}.mkv", now),
        )
    conn.commit()
    return path_id


def seed_media_item_with_release(
    conn: sqlite3.Connection,
    title: str | None = None,
    category_id: str = "movies",
) -> int:
    """Insert a minimal media_item + media_release pair and return the release_id.

    When ``title`` is ``None`` (default), generates a unique title via
    ``uuid4().hex[:8]`` to satisfy migration 007's ``UNIQUE(title, kind)``
    constraint without relying on global mutable state.
    """
    if title is None:
        title = f"Test Movie {uuid.uuid4().hex[:8]}"
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES ('movie', ?, ?, ?, ?, ?)",
        (title, title, category_id, now, now),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]
    cursor2 = conn.execute(
        "INSERT INTO media_release (item_id, edition) VALUES (?, 'Standard')",
        (item_id,),
    )
    conn.commit()
    return cursor2.lastrowid  # type: ignore[return-value]


def seed_scan_run(
    conn: sqlite3.Connection,
    status: str = "ok",
    mode: str = "full",
    generation: int = 1,
    disk_filter: str | None = None,
    finished_at: int | None = None,
) -> int:
    """Insert a completed scan_run row and return its id."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO scan_run (generation, mode, disk_filter, started_at, finished_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (generation, mode, disk_filter, now - 60, finished_at or now, status),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_index_outbox(
    conn: sqlite3.Connection,
    status: str = "pending",
    processed_at: int | None = None,
    event_type: str = "test.event",
    source: str = "scanner",
    op: str = "move",
) -> int:
    """Insert an index_outbox row and return its id."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO index_outbox (source, op, payload_json, created_at, processed_at, status) "
        "VALUES (?, ?, '{}', ?, ?, ?)",
        (source, op, now, processed_at, status),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_repair_queue(
    conn: sqlite3.Connection,
    scope: str = "item",
    scope_id: int = 1,
    reason: str = "test.reason",
    status: str = "pending",
) -> int:
    """Insert a repair_queue row and return its id."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, payload_json, enqueued_at, status) "
        "VALUES (?, ?, ?, '{}', ?, ?)",
        (scope, scope_id, reason, now, status),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_media_file_on_disk(
    conn: sqlite3.Connection,
    disk_id: int,
    mount_path: Path,
    rel_path: str,
    filename: str,
    size_bytes: int | None = None,
    mtime_ns: int | None = None,
    release_id: int | None = None,
) -> tuple[int, int, int]:
    """Create a real file on disk and seed matching DB rows.

    Creates the directory structure under *mount_path*, writes a file with
    deterministic content, stats it, and inserts ``path`` + ``media_file``
    rows with the actual on-disk values.

    Args:
        conn: Open SQLite connection.
        disk_id: FK to ``disk.id``.
        mount_path: The disk mount path root (must exist).
        rel_path: Relative directory under mount_path.
        filename: Name of the file to create.
        size_bytes: Override stored size (for mismatch tests).  Defaults to
            actual file size.
        mtime_ns: Override stored mtime (for mismatch tests).  Defaults to
            actual file mtime.
        release_id: FK to ``media_release.id``.  When ``None``, a minimal
            media_item + media_release pair is auto-created.

    Returns:
        ``(path_id, file_id, actual_size)`` tuple.
    """
    import hashlib as _hashlib
    import os as _os

    now = int(time.time())

    # Create directory and file.
    dir_path = mount_path / rel_path
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    content = f"test content for {filename} at {now}".encode()
    file_path.write_bytes(content)
    actual_size = _os.stat(file_path).st_size
    actual_mtime_ns = _os.stat(file_path).st_mtime_ns

    # Compute oshash.
    oshash = _hashlib.new("sha1")
    oshash.update(content)
    oshash_hex = oshash.hexdigest()[:16]

    stored_size = size_bytes if size_bytes is not None else actual_size
    stored_mtime = mtime_ns if mtime_ns is not None else actual_mtime_ns

    # Ensure release_id.
    if release_id is None:
        release_id = seed_media_item_with_release(conn)

    # Insert path row.
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, ?)",
        (disk_id, rel_path, int(dir_path.stat().st_mtime_ns)),
    )
    path_id: int = cursor.lastrowid  # type: ignore[assignment]

    # Insert media_file row.
    conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, scan_generation, last_verified_at, enriched_at, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, NULL, NULL)
        """,
        (release_id, path_id, filename, stored_size, stored_mtime, now, oshash_hex, now),
    )
    conn.commit()
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return (path_id, file_id, actual_size)


def run_cli(args: list[str]) -> Any:
    """Invoke the Typer CLI app via CliRunner and return the result object.

    Args:
        args: CLI arguments as a list of strings (e.g. ``['library-reconcile', '--format', 'json']``).

    Returns:
        The ``Result`` object from ``CliRunner.invoke``.  For tests that parse
        machine-readable stdout (e.g. JSON), use ``result.stdout`` instead of
        ``result.output`` — ``result.output`` mixes stdout + stderr while
        ``result.stdout`` is always stdout-only.
    """
    from personalscraper.cli import app  # noqa: PLC0415

    runner = CliRunner()
    return runner.invoke(app, args)


def json_from_result(result: Any, *, source_attr: str = "output") -> dict[str, Any]:
    """Extract a JSON dict from a CliRunner result.

    Handles Rich-formatted output where JSON may be interleaved with
    escape codes.  Returns the first JSON object found.

    Args:
        result: CliRunner result object.
        source_attr: ``"output"`` (default, mixed stdout+stderr) or
            ``"stdout"`` (stdout-only, for machine-readable output like JSON).
    """
    raw: str = getattr(result, source_attr).strip()
    # Strip Rich ANSI escape codes.
    import re

    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    start = clean.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[start:])  # type: ignore[no-any-return]


# ══════════════════════════════════════════════════════════════════════════════
# Realistic payload fixtures — Mock MediaDetails for scrape/rescrape e2e tests.
# Covers full / partial / show / movie shapes so callers can exercise
# graceful-degradation paths against payloads that look like real provider
# responses (not toy stubs).
# ══════════════════════════════════════════════════════════════════════════════


def _make_minimal_movie_details() -> Any:
    """Return a minimal :class:`MediaDetails` for a movie.

    Covers the "API returns complete data" path with all mandatory fields
    plus one poster and one landscape image.
    """
    from personalscraper.api.metadata._base import ArtworkItem, MediaDetails  # noqa: PLC0415

    return MediaDetails(
        provider="tmdb",
        provider_id="550",
        title="Fight Club",
        original_title="Fight Club",
        year=1999,
        overview="An insomniac office worker and a devil-may-care soap maker form an underground fight club.",
        genres=["Drama", "Thriller"],
        runtime_minutes=139,
        rating=8.4,
        images=[
            ArtworkItem(type="poster", url="https://image.tmdb.org/t/p/w500/fight_club_poster.jpg"),
            ArtworkItem(type="landscape", url="https://image.tmdb.org/t/p/w500/fight_club_landscape.jpg"),
        ],
        external_ids={"imdb": "tt0137523"},
    )


def _make_minimal_show_details() -> Any:
    """Return a minimal :class:`MediaDetails` for a TV show.

    Includes one season summary so season-aware callers can verify
    season_number → episode_count linkage.
    """
    from personalscraper.api.metadata._base import MediaDetails, SeasonInfo  # noqa: PLC0415

    return MediaDetails(
        provider="tvdb",
        provider_id="121361",
        title="Breaking Bad",
        original_title="Breaking Bad",
        year=2008,
        overview="A chemistry teacher diagnosed with cancer turns to manufacturing methamphetamine.",
        genres=["Drama", "Crime"],
        runtime_minutes=47,
        rating=9.5,
        seasons=[
            SeasonInfo(season_number=1, episode_count=7),
            SeasonInfo(season_number=2, episode_count=13),
        ],
        external_ids={"imdb": "tt0903747"},
    )


def _make_partial_movie_details() -> Any:
    """Return a :class:`MediaDetails` with several optional fields missing.

    Covers the "API returns partial data" path — no runtime, no genres,
    no images, no external IDs, no rating.  Callers must degrade gracefully.
    """
    from personalscraper.api.metadata._base import MediaDetails  # noqa: PLC0415

    return MediaDetails(
        provider="tmdb",
        provider_id="99999",
        title="Incomplete Movie",
        year=2020,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Mock clients (6 helpers — 9.1)
# ══════════════════════════════════════════════════════════════════════════════


def mock_qbit_client(monkeypatch: Any) -> Any:
    """Mock qBittorrent client returning a canned empty torrent list.

    Patches both ``build_active_torrent_client`` (factory path) and
    ``QBitClient`` (direct construction path in ingest).  Returns the
    mock instance so callers can configure ``.return_value`` on its
    methods (e.g. ``mock.list_torrents.return_value = [...]``).
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    mock = MagicMock()
    mock.list_torrents.return_value = []
    mock.get_torrent_properties.return_value = {}

    monkeypatch.setattr(
        "personalscraper.api.torrent._factory.build_active_torrent_client",
        lambda *a, **kw: mock,
    )
    monkeypatch.setattr(
        "personalscraper.api.torrent.qbittorrent.QBitClient",
        MagicMock(return_value=mock),
    )
    return mock


def mock_boundary_torrent_client(monkeypatch: Any, client: Any) -> Any:
    """Wire *client* as ``AppContext.torrent_client`` for boundary commands.

    Since DESIGN D3 the torrent client is boot-wired into ``AppContext`` by
    ``_build_app_context`` and read by ``torrents-list`` via
    ``per_step_boundary``.  CLI E2E tests therefore patch the boundary rather
    than the client constructors: this replaces ``per_step_boundary`` (as
    imported into ``commands.torrents``) with a context manager that yields a
    real :class:`AppContext` whose ``torrent_client`` is *client*.

    Args:
        monkeypatch: Pytest ``monkeypatch`` fixture.
        client: The mock torrent client to expose as ``ctx.torrent_client``.
            Pass ``None`` to exercise the "no torrent client configured" path.

    Returns:
        The *client* argument (for convenient inline configuration).
    """
    from contextlib import contextmanager  # noqa: PLC0415
    from unittest.mock import MagicMock  # noqa: PLC0415

    from personalscraper.cli import app as _app  # noqa: F401, PLC0415 — ensure command module imported
    from personalscraper.core.app_context import AppContext  # noqa: PLC0415
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

    @contextmanager
    def _fake_boundary(config: Any, settings: Any, *, build_torrent_client: bool = False) -> Any:
        # Mirror the real per_step_boundary signature (review #1/#2/#5 added the
        # build_torrent_client keyword); torrents-list passes it as True.
        yield AppContext(
            config=config,
            settings=settings,
            event_bus=EventBus(),
            provider_registry=MagicMock(),
            torrent_client=client,
        )

    monkeypatch.setattr("personalscraper.commands.torrents.per_step_boundary", _fake_boundary)
    return client


def mock_transmission_client(monkeypatch: Any) -> Any:
    """Mock Transmission client.

    Returns the mock instance for caller customization.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    mock = MagicMock()
    mock.list_torrents.return_value = []

    monkeypatch.setattr(
        "personalscraper.api.torrent.transmission.TransmissionClient",
        MagicMock(return_value=mock),
    )
    return mock


def mock_tmdb_client(monkeypatch: Any) -> Any:
    """Mock TMDB API client returning realistic payloads by default.

    Returns a minimal movie for ``get_movie`` and a minimal search result
    list for ``search_movie`` / ``search_show``.  Callers can override
    ``get_movie.return_value``, ``get_show.return_value``, etc. for
    scenario-specific tests (e.g. partial data, error paths).

    Also mocks ``TMDBClient.policy`` to return a safe no-op
    :class:`TransportPolicy` so the rescraper's ``HttpTransport``
    wrapper does not choke on a ``MagicMock`` inside ``RateLimiter``.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    from personalscraper.api.metadata.tmdb import TMDBClient  # noqa: PLC0415
    from personalscraper.api.transport._auth import NoAuth  # noqa: PLC0415
    from personalscraper.api.transport._policy import (  # noqa: PLC0415
        CircuitPolicy,
        RateLimitPolicy,
        RetryPolicy,
        TransportPolicy,
    )

    # ``MagicMock(spec=TMDBClient)`` so the real ``ProviderRegistry``
    # ``protocol_mismatch`` check accepts the mock as a valid implementation
    # of every capability protocol the class composes.
    mock = MagicMock(spec=TMDBClient)
    mock.get_movie.return_value = _make_minimal_movie_details()
    # TMDB's TV equivalent is ``get_tv`` (not ``get_show`` — that's TVDB).
    # Both names were stubbed historically (when the mock had no ``spec=``);
    # the spec now enforces the real signature.
    mock.get_tv.return_value = _make_minimal_show_details()
    mock.get_tv_season.return_value = None
    mock.search.return_value = []
    mock.search_movie.return_value = []
    mock.search_tv.return_value = []

    safe_policy = TransportPolicy(
        provider_name="mock-tmdb",
        base_url="https://localhost",
        auth=NoAuth(),
        timeout_seconds=1.0,
        retry=RetryPolicy(max_attempts=0),
        circuit=CircuitPolicy(failure_threshold=100, cooldown_seconds=0.0),
        rate_limit=RateLimitPolicy(requests_per_second=0.0),
    )

    cls_mock = MagicMock(return_value=mock)
    # ``TMDBClient.policy`` accepts ``api_key`` plus a keyword-only ``circuit``
    # override (used by ``ProviderRegistry`` to inject a shared circuit policy).
    # The mock ignores both and returns the safe canned policy.
    cls_mock.policy = lambda api_key, *, circuit=None: safe_policy  # type: ignore[attr-defined]

    monkeypatch.setattr(
        "personalscraper.api.metadata.tmdb.TMDBClient",
        cls_mock,
    )
    return mock


def mock_tvdb_client(monkeypatch: Any) -> Any:
    """Mock TVDB API client returning realistic payloads by default.

    Returns a minimal show for ``get_show``.  Callers can override
    ``get_show.return_value``, ``get_series_episodes.return_value``, etc.
    for scenario-specific tests.

    The mock instance uses ``MagicMock(spec=TVDBClient)`` so the
    real :class:`ProviderRegistry` ``protocol_mismatch`` check (which
    runs ``isinstance(instance, Searchable)`` etc.) accepts the mock
    as a valid implementation of every capability protocol TVDBClient
    composes.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    from personalscraper.api.metadata.tvdb import TVDBClient  # noqa: PLC0415

    mock = MagicMock(spec=TVDBClient)
    # TVDB exposes ``get_tv`` / ``get_series`` (not ``get_show``).  The spec
    # enforces the real method names; legacy callers that overrode
    # ``mock.get_show`` will now see an explicit ``AttributeError``.
    mock.get_tv.return_value = _make_minimal_show_details()
    mock.get_series.return_value = _make_minimal_show_details()
    mock.search.return_value = []
    mock.search_series.return_value = []

    monkeypatch.setattr(
        "personalscraper.api.metadata.tvdb.TVDBClient",
        MagicMock(return_value=mock),
    )
    return mock


def mock_omdb_client(monkeypatch: Any) -> Any:
    """Mock OMDB API client returning canonical (empty) payloads."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    mock = MagicMock()
    mock.get.return_value = None

    monkeypatch.setattr(
        "personalscraper.api.metadata.omdb.OMDbAdapter",
        MagicMock(return_value=mock),
    )
    return mock


def mock_trakt_client(monkeypatch: Any) -> Any:
    """Mock Trakt API client returning canonical (empty) payloads."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    mock = MagicMock()
    mock.get_ratings.return_value = {}

    monkeypatch.setattr(
        "personalscraper.api.metadata.trakt.TraktClient",
        MagicMock(return_value=mock),
    )
    return mock


def mock_yt_dlp(monkeypatch: Any) -> Any:
    """Mock yt-dlp YoutubeDL for trailer download tests.

    Returns the mock instance; callers configure ``download.return_value``
    or ``extract_info.return_value`` for realistic scenarios.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    mock = MagicMock()
    mock.extract_info.return_value = {"title": "Test Trailer", "id": "test123"}
    mock.prepare_filename.return_value = "/tmp/test-trailer.mp4"

    monkeypatch.setattr("yt_dlp.YoutubeDL", MagicMock(return_value=mock))
    return mock


# ══════════════════════════════════════════════════════════════════════════════
# FS / staging seeders (2 helpers — 9.1)
# ══════════════════════════════════════════════════════════════════════════════


def seed_pipeline_lock(staging_dir: Path) -> Path:
    """Create a ``pipeline.lock`` file to test concurrent-lock behavior.

    Args:
        staging_dir: The directory where ``pipeline.lock`` should be created.

    Returns:
        Path to the created lock file.
    """
    lock_path = staging_dir / "pipeline.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(f"pid={99999}\nstarted_at=9999999999\n")
    return lock_path


def seed_staging_layout(tmp_path: Path, config: Any) -> dict[str, Path]:
    """Create staging subdirectories from config's ``staging_dirs`` mapping.

    Creates directories like ``001-MOVIES/``, ``002-TVSHOWS/``, etc. under
    ``tmp_path``.  Returns a ``{category_id: path}`` mapping.
    """
    dirs: dict[str, Path] = {}
    for key, value in config.staging_dirs.items():
        dir_path = tmp_path / value
        dir_path.mkdir(parents=True, exist_ok=True)
        dirs[key] = dir_path
    # Ensure 097-TEMP exists (the ingest landing zone).
    temp_dir = tmp_path / "097-TEMP"
    temp_dir.mkdir(parents=True, exist_ok=True)
    dirs["097-TEMP"] = temp_dir
    return dirs


# ══════════════════════════════════════════════════════════════════════════════
# Assertion helpers (3 helpers — 9.1)
# ══════════════════════════════════════════════════════════════════════════════


def assert_no_python_traceback(result: Any) -> None:
    """Assert that result output contains no raw Python traceback.

    A non-zero exit is acceptable; this asserts the error message is
    user-friendly (no ``Traceback (most recent call last):``).
    """
    output = getattr(result, "output", "")
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    assert "Traceback (most recent call last):" not in output, f"Raw traceback found in output:\n{output}"


def assert_json_schema(
    result: Any,
    required_keys: list[str] | None = None,
    optional_keys: list[str] | None = None,
    *,
    source_attr: str = "output",
) -> dict[str, Any]:
    """Parse JSON from result and validate top-level key schema.

    Args:
        result: CliRunner result object.
        required_keys: Keys that MUST be present (fails if missing).
        optional_keys: Keys that MAY be present (logged but not enforced).
        source_attr: ``"output"`` (default) or ``"stdout"`` (for JSON commands).

    Returns:
        Parsed JSON dict (for further assertions by the caller).
    """
    data = json_from_result(result, source_attr=source_attr)
    if required_keys:
        missing = [k for k in required_keys if k not in data]
        assert not missing, f"Missing required keys in JSON output: {missing}. Got keys: {sorted(data.keys())}"
    if optional_keys:
        present = [k for k in optional_keys if k in data]
        absent = [k for k in optional_keys if k not in data]
        if absent:
            import logging  # noqa: PLC0415

            _log = logging.getLogger(__name__)
            _log.info("Optional keys absent (non-blocking): %s / present: %s", absent, present)
    return data


# ══════════════════════════════════════════════════════════════════════════════
# Events assertion (2 helpers — 9.1)
# ══════════════════════════════════════════════════════════════════════════════


def _load_matrix_event_names() -> set[str]:
    """Parse the design-conformity matrix for declared PascalCase event class names.

    Returns:
        Set of event class names (e.g. ``{"ItemProgressed", "StepStarted"}``).
        Empty set if the matrix file is unreadable.
    """
    import re  # noqa: PLC0415

    matrix_path = (
        Path(__file__).resolve().parents[2]
        / ".claude"
        / "skills"
        / "pipeline-monitor"
        / "references"
        / "design-conformity-matrix.md"
    )
    try:
        text = matrix_path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return set()

    # PascalCase identifiers that follow "(Event)" pattern or are cited as
    # "item_xyz_df events" patterns in the matrix text.  Also capture
    # names from backtick-quoted spans like ``ItemProgressed``.
    names: set[str] = set()
    # Match backtick-quoted PascalCase.
    for m in re.finditer(r"`([A-Z][a-zA-Z]+)`", text):
        names.add(m.group(1))
    # Match plain PascalCase adjacent to "(Event)".
    for m in re.finditer(r"\b([A-Z][a-zA-Z]{2,})\s*\(Event\)", text):
        names.add(m.group(1))
    # Match PascalCase followed by parenthesis — captures descriptive
    # references like ``ItemProgressed(step="ingest", ...)`` that appear
    # in matrix prose without backticks or "(Event)" suffix.
    # Uses a negative lookbehind for `(` to avoid matching markdown links
    # like ``[ItemProgressed](...)``.
    for m in re.finditer(r"(?<!\()\b([A-Z][a-zA-Z]{2,})\(", text):
        names.add(m.group(1))
    return names


def assert_events_emitted(
    captured: list[Any],
    expected_classes: list[type],
) -> None:
    """Verify emitted events against the design-conformity matrix.

    Cross-checks that every expected Event subclass was captured and
    that every captured event is known to the design-conformity matrix
    as ground truth (anti-drift).
    Falls back to a logged warning if the matrix file is unreadable.

    Args:
        captured: List of :class:`Event` instances captured by
            :func:`capture_event_bus`.
        expected_classes: Event subclasses that SHOULD appear in
            *captured* (each at least once).
    """
    matrix_names = _load_matrix_event_names()

    # Infra events emitted by the registry / transport layers that the
    # design-conformity matrix intentionally does not enumerate (the matrix
    # tracks the pipeline-domain step/item events, not the boot signal).
    # Since feat/registry Phase 15 removed the autouse stub, every CLI test
    # captures ``RegistryBootValidated`` at boot — filter it out here so
    # individual tests do not all need to know about it.
    _INFRA_EVENT_NAMES = {"RegistryBootValidated"}

    captured_names = {type(e).__name__ for e in captured} - _INFRA_EVENT_NAMES
    expected_names = {cls.__name__ for cls in expected_classes}

    # Check expected classes were emitted.
    missing = expected_names - captured_names
    assert not missing, f"Expected events not emitted: {sorted(missing)}. Captured: {sorted(captured_names)}"

    # Anti-drift check: every captured event should be known to the matrix.
    if matrix_names:
        unknown = captured_names - matrix_names
        assert not unknown, (
            f"Events captured but NOT found in design-conformity matrix (drift): "
            f"{sorted(unknown)}. Matrix names: {sorted(matrix_names)}"
        )
    else:
        import logging  # noqa: PLC0415

        _log = logging.getLogger(__name__)
        _log.warning(
            "matrix unreadable — skipping anti-drift check. "
            "TODO: verify %s against design-conformity-matrix.md manually.",
            sorted(captured_names),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Snapshot / diff utilities (3 helpers — 9.1)
# ══════════════════════════════════════════════════════════════════════════════


def fs_snapshot(path: Path) -> dict[str, str]:
    """Compute a recursive content hash of *path* for ``--dry-run`` assertions.

    Returns a ``{rel_path: hex_hash}`` mapping.  Directories are represented
    by a synthetic ``<dir>`` hash derived from their children.  Snapshots
    taken before and after ``--dry-run`` must be identical.

    Args:
        path: Root directory to snapshot.

    Returns:
        Flat dictionary mapping relative paths to SHA-256 hex digests.
    """
    import hashlib as _hashlib  # noqa: PLC0415

    snapshot: dict[str, str] = {}

    if not path.exists():
        return snapshot

    for entry in sorted(path.rglob("*")):
        rel = entry.relative_to(path).as_posix()
        if entry.is_file():
            content = entry.read_bytes()
            snapshot[rel] = _hashlib.sha256(content).hexdigest()
        elif entry.is_dir():
            # Represent a directory by hashing its children's names.
            children = sorted(p.name for p in entry.iterdir())
            snapshot[f"{rel}/<dir>"] = _hashlib.sha256("\n".join(children).encode()).hexdigest()
    return snapshot


def bdd_diff_ignoring(
    conn: Any,
    before_snapshot: dict[str, list[dict[str, Any]]],
    ignore_cols: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compare current DB state against *before_snapshot*.

    Excludes time-sensitive columns so idempotence can be verified.
    An empty diff list means no meaningful change.

    Args:
        conn: Open SQLite connection.
        before_snapshot: Dict mapping table name → list of row dicts
            captured before the operation.
        ignore_cols: Column names to exclude from comparison (defaults
            to ``["updated_at", "last_seen", "last_seen_at", "last_verified_at",
            "enriched_at", "date_modified", "processed_at", "enqueued_at",
            "started_at", "finished_at", "created_at"]``).

    Returns:
        List of diff entries, each ``{"table": str, "row_idx": int, "before": dict, "after": dict}``.
    """
    if ignore_cols is None:
        ignore_cols = [
            "updated_at",
            "last_seen",
            "last_seen_at",
            "last_verified_at",
            "enriched_at",
            "date_modified",
            "processed_at",
            "enqueued_at",
            "started_at",
            "finished_at",
            "created_at",
            "date_created",
            "ctime_ns",
            "last_inserted_at",
            "last_updated_at",
        ]

    ignore_set = set(ignore_cols)
    diffs: list[dict[str, Any]] = []

    for table, before_rows in before_snapshot.items():
        cursor = conn.execute(f"SELECT * FROM [{table}]")
        col_names = [d[0] for d in cursor.description]
        after_rows = [dict(zip(col_names, row)) for row in cursor.fetchall()]

        for idx, (before_row, after_row) in enumerate(zip(before_rows, after_rows)):
            before_filtered = {k: v for k, v in before_row.items() if k not in ignore_set}
            after_filtered = {k: v for k, v in after_row.items() if k not in ignore_set}
            if before_filtered != after_filtered:
                diffs.append(
                    {
                        "table": table,
                        "row_idx": idx,
                        "before": before_filtered,
                        "after": after_filtered,
                    }
                )
    return diffs


# ══════════════════════════════════════════════════════════════════════════════
# Event bus capture (1 helper — 9.1)
# ══════════════════════════════════════════════════════════════════════════════


def capture_event_bus(monkeypatch: Any) -> list[Any]:
    """Intercept ``EventBus.emit`` calls and record every emitted event.

    Returns a mutable list that the caller can inspect after the CLI
    invocation.  The original ``emit`` is still called so subscribers
    are not disrupted.

    Args:
        monkeypatch: Pytest ``monkeypatch`` fixture.

    Returns:
        List of captured :class:`Event` instances (in emit order).
    """
    captured: list[Any] = []

    def _capture_and_forward(self: Any, event: Any) -> None:
        captured.append(event)
        # Forward to the original emit so subscribers still fire.
        _orig_emit(self, event)

    # Lazy-import to avoid pulling the EventBus at module scope.
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

    _orig_emit = EventBus.emit  # type: ignore[assignment]
    monkeypatch.setattr(EventBus, "emit", _capture_and_forward)
    return captured
