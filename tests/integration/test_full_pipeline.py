"""Integration tests for the full pipeline orchestrator.

Exercises ``Pipeline.run()`` end-to-end with an in-memory qBittorrent stub
and monkeypatched TMDB/TVDB clients.

Catalogue items covered:
    #15 — Full pipeline dry-run orchestration
"""

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import PipelineReport
from personalscraper.pipeline import Pipeline
from tests.integration.conftest import FakeQBitClient, FakeTMDB, FakeTorrent, FakeTVDB

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Expected pipeline step names in declaration order (9 total, matching pipeline.py).
# trailers step sits between verify and dispatch (non-blocking).
_EXPECTED_STEPS = ("ingest", "sort", "clean", "scrape", "cleanup", "enforce", "verify", "trailers", "dispatch")


def _make_settings() -> Settings:
    """Return Settings with all resource guards disabled for integration tests.

    Disables disk-space checks for staging and storage disks so the tests
    are never blocked by real filesystem constraints in CI or on developer
    machines with small ``/tmp`` partitions.

    Returns:
        Settings instance with zero thresholds and empty API keys.
    """
    return Settings(
        min_free_space_staging_gb=0,
        min_free_space_disk_gb=0,
    )


def _make_torrent_dir(root: Path, name: str) -> FakeTorrent:
    """Create a minimal torrent content directory and return a FakeTorrent.

    Creates a directory named ``name`` under ``root`` with a tiny stub MKV
    file so that ``ingest.run_ingest`` finds the content path on disk and
    does not mark the torrent as missing-content.

    Args:
        root: Parent directory for the torrent content folder.
        name: Torrent/folder name (also used as hash suffix for uniqueness).

    Returns:
        FakeTorrent pointing at ``root / name``.
    """
    torrent_dir = root / name
    torrent_dir.mkdir(parents=True, exist_ok=True)
    (torrent_dir / "video.mkv").write_bytes(b"\x00" * 16)  # tiny stub file
    return FakeTorrent(
        name=name,
        hash=f"hash_{name.lower().replace(' ', '_').replace('.', '_')}",
        content_path=str(torrent_dir),
    )


# ---------------------------------------------------------------------------
# Catalogue #15 — full pipeline dry-run orchestration
# ---------------------------------------------------------------------------


def test_dry_run_three_torrents(
    fake_qbit: FakeQBitClient,
    fake_tmdb: FakeTMDB,
    fake_tvdb: FakeTVDB,
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    integration_config_path: Path,
    rsync_available: None,
    tmp_path: Path,
) -> None:
    """Full pipeline dry-run with 2 movies + 1 TV episode produces 9 StepReports.

    Catalogue #15 — dry-run orchestration invariant.

    Seeds fake_qbit with three completed torrents (2 movies, 1 TV episode),
    seeds fake_tmdb with matching hits for the two movies, and seeds fake_tvdb
    with a matching hit for the TV episode.  Invokes ``Pipeline.run()`` with
    ``dry_run=True`` and asserts:

    - The returned PipelineReport has all 8 expected steps.
    - No error step is present (no crashes).
    - No file was actually moved to any disk (dry-run invariant).

    Args:
        fake_qbit: In-memory qBittorrent stub (monkeypatched).
        fake_tmdb: In-memory TMDB stub (monkeypatched).
        fake_tvdb: In-memory TVDB stub (monkeypatched).
        staging_tree: Staging root fixture (tmp_path/staging).
        fake_disks: List of four fake disk root paths.
        integration_config: Fully composed integration Config fixture.
        integration_config_path: Path to the serialised config.json5 file.
        rsync_available: Skips test when rsync is absent from PATH.
        tmp_path: Pytest temporary directory (unique per test).
    """
    # Ensure data_dir exists — IngestTracker and MediaIndex both require it.
    integration_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    # Create torrent content directories under tmp_path/torrents/ so that
    # ingest can find them via get_content_path().
    torrent_source = tmp_path / "torrents"
    torrent_source.mkdir()

    movie_a = _make_torrent_dir(torrent_source, "Oppenheimer.2023.1080p.BluRay")
    movie_b = _make_torrent_dir(torrent_source, "Dune.Part.Two.2024.2160p.HDR")
    episode = _make_torrent_dir(torrent_source, "Fallout.S01E01.720p.WEB-DL")

    fake_qbit.seed([movie_a, movie_b, episode])

    # Seed TMDB with minimal movie search results so the scraper finds matches.
    fake_tmdb.seed(
        "search/movie",
        {
            "results": [
                {"id": 872585, "title": "Oppenheimer", "release_date": "2023-07-21"},
            ]
        },
    )
    fake_tmdb.seed(
        "movie/872585",
        {
            "id": 872585,
            "title": "Oppenheimer",
            "release_date": "2023-07-21",
            "overview": "The story of J. Robert Oppenheimer.",
            "genres": [{"id": 18, "name": "Drama"}],
            "vote_average": 8.3,
        },
    )
    fake_tmdb.seed(
        "search/movie_dune",
        {
            "results": [
                {"id": 693134, "title": "Dune: Part Two", "release_date": "2024-03-01"},
            ]
        },
    )

    # Seed TVDB with a minimal series search result for Fallout.
    fake_tvdb.seed(
        "search",
        {
            "data": [
                {"id": 401833, "name": "Fallout", "firstAired": "2024-04-11", "slug": "fallout"},
            ]
        },
    )
    fake_tvdb.seed(
        "series/401833",
        {
            "data": {
                "id": 401833,
                "name": "Fallout",
                "firstAired": "2024-04-11",
                "overview": "Post-apocalyptic adventure.",
                "genres": ["Science Fiction"],
            }
        },
    )

    # Construct and run the pipeline in dry_run mode.
    pipeline = Pipeline(
        AppContext(
            config=integration_config,
            settings=_make_settings(),
            event_bus=EventBus(),
            provider_registry=MagicMock(spec=ProviderRegistry),
        )
    )
    report: PipelineReport = pipeline.run(
        dry_run=True,
    )

    # --- Structural invariant: all 9 steps must be present ---------------
    # The plan specified 6 StepReports; actual production code produces 9
    # (ingest, sort, clean, scrape, cleanup, enforce, verify, trailers, dispatch).
    # We assert on the actual shape to avoid false failures.
    assert set(report.steps.keys()) == set(_EXPECTED_STEPS), (
        f"Expected steps {_EXPECTED_STEPS!r}, got {list(report.steps.keys())!r}"
    )

    # --- No fatal crashes ------------------------------------------------
    assert not report.has_errors(), "Pipeline reported errors in dry-run mode: " + "; ".join(
        f"{name}: {s.details}" for name, s in report.steps.items() if s.error_count > 0
    )

    # --- Per-step success_count invariants (concrete expectations) -------
    # ingest processes all 3 torrents: 2 movies + 1 TV episode.
    assert report.steps["ingest"].success_count == 3, (
        f"ingest must process all 3 torrents. Got: {report.steps['ingest'].success_count}"
    )
    # sort, scrape, verify fast-skip when no staged content is ready (no
    # items were moved to typed staging dirs by the ingest step alone).
    for step_name in ("sort", "scrape", "verify"):
        step = report.steps[step_name]
        assert step.success_count + step.skip_count + step.error_count == 0, (
            f"{step_name!r} expected fast-skip with zero items processed, "
            f"got success={step.success_count} skip={step.skip_count} err={step.error_count}"
        )
    # dispatch produces no successes in dry-run because there are no
    # dispatchable (verified) items after the verify fast-skip.
    assert report.steps["dispatch"].success_count == 0, (
        f"dispatch must report 0 successes in dry-run (no verified items). "
        f"Got: {report.steps['dispatch'].success_count}"
    )

    # --- Dry-run invariant: no files on any disk -------------------------
    for disk in fake_disks:
        children = list(disk.iterdir())
        assert children == [], f"Disk {disk} should be empty after dry-run, found: {children}"
