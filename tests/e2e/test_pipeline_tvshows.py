"""E2E test: full pipeline for TV shows and mixed pipeline via CLI.

TV shows have additional complexity: season folders, episode renaming,
merge-on-dispatch behavior, and tvshow.nfo generation.

SAFETY: Dispatch runs in DRY-RUN mode only — storage disks are never
written to. Only the staging area is modified and cleaned up.

WARNING: Downloads real torrents — costs upload ratio on private trackers.
Run MANUALLY only: pytest -m e2e_torrent -v -s
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.core.event_bus import EventBus
from tests.e2e.assertions import (
    assert_ingest_complete,
    assert_scrape_complete,
    assert_sort_complete,
    assert_verify_complete,
)
from tests.e2e.cleanup import TestCleanup
from tests.e2e.markers import place_marker
from tests.e2e.setup_torrents import TorrentSetup


@pytest.mark.e2e_torrent
class TestTVShowFullPipeline:
    """Full E2E test: a TV show goes through the real pipeline.

    Stages V1-V4 run for real in the staging area.
    V5 dispatch runs in dry-run mode (disks are never touched).
    """

    def test_tvshow_full_pipeline(
        self,
        e2e_session_id,
        e2e_registry,
        e2e_qbit_client,
        e2e_torrent_files,
        e2e_settings,
    ):
        """TV show traverses the full pipeline from torrent to verified.

        Verifies: season folders, episode rename (S##E## format),
        tvshow.nfo, and season posters.
        """
        # Filter TV show torrents (heuristic: contains "S01" or similar)
        tvshow_torrents = [f for f in e2e_torrent_files if any(f"S{s:02d}" in f.name for s in range(1, 30))]
        if not tvshow_torrents:
            pytest.skip("No TV show .torrent files in assets/torrents/")

        from personalscraper.conf.loader import load_config, resolve_config_path

        settings = e2e_settings
        e2e_config = load_config(resolve_config_path(None))
        staging = Path(e2e_config.paths.staging_dir)
        tvshows_dir = staging / "002-TVSHOWS"

        setup = TorrentSetup(client=e2e_qbit_client, registry=e2e_registry)
        cleanup = TestCleanup(
            registry=e2e_registry,
            dry_run=False,
            staging_dir=staging,
            disk_paths=[Path(d.path) for d in e2e_config.disks],
        )

        try:
            # ── 1. Setup: add .torrent files and wait for download ──
            hashes = setup.add_torrent_files(tvshow_torrents)
            names = setup.get_torrent_names(hashes)
            print(f"\n  Added {len(hashes)} TV show torrent(s): {list(names.values())}")

            setup.wait_for_completion(hashes)

            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # ── 2. V1 Ingest (REAL) ──
            from personalscraper.ingest.ingest import run_ingest

            ingest_report = run_ingest(
                settings, dry_run=False, config=e2e_config, event_bus=EventBus(), torrent_client=e2e_qbit_client
            )
            print(f"  V1 Ingest: {ingest_report.success_count} ingested")

            expected = [{"name": n, "type": "tvshow"} for n in names.values()]
            assert_ingest_complete(staging, expected)

            # ── 3. V2 Sort (REAL) ──
            from personalscraper.sorter.run import run_sort

            sort_report = run_sort(
                settings, staging_dir=staging, config=e2e_config, dry_run=False, event_bus=EventBus()
            )
            print(f"  V2 Sort: {sort_report.success_count} sorted")
            assert_sort_complete(staging / "001-MOVIES", tvshows_dir, expected)

            # Register sorted directories for cleanup
            if tvshows_dir.exists():
                for d in tvshows_dir.iterdir():
                    if d.is_dir():
                        place_marker(d, e2e_session_id)
                        e2e_registry.register(d)

            # ── 4. V3 Scrape (REAL — calls TVDB/TMDB APIs) ──
            from personalscraper.scraper.run import run_scrape

            scrape_report = run_scrape(
                settings,
                config=e2e_config,
                dry_run=False,
                tvshows_only=True,
                event_bus=EventBus(),
                registry=MagicMock(),
            )
            print(f"  V3 Scrape: {scrape_report.success_count} scraped")
            assert_scrape_complete(staging / "001-MOVIES", tvshows_dir, expected)

            # ── 4b. Golden file assertions (optional — skip if no golden file) ──
            from tests.e2e.assertions import (
                assert_scrape_golden,
                assert_structure_golden,
                find_media_dir,
            )
            from tests.e2e.golden import match_torrent_to_golden

            for torrent_name in names.values():
                golden = match_torrent_to_golden(torrent_name)
                if golden:
                    print(f"  Golden match: {torrent_name} → {golden.name}")
                    media_dir = find_media_dir(tvshows_dir, golden.nfo["folder_name_pattern"])
                    assert_scrape_golden(media_dir, golden)
                    assert_structure_golden(media_dir, golden)
                else:
                    print(f"  No golden file for {torrent_name} — smoke tests only")

            # Show episode structure
            for d in tvshows_dir.iterdir():
                if not d.is_dir():
                    continue
                season_dirs = [s for s in d.iterdir() if s.is_dir() and "Saison" in s.name]
                if season_dirs:
                    print(f"    → {d.name}: {len(season_dirs)} season dir(s)")
                    for sd in season_dirs:
                        episodes = [f for f in sd.iterdir() if f.suffix in (".mkv", ".mp4")]
                        print(f"      {sd.name}: {len(episodes)} episodes")

            # ── 5. V4 Verify (REAL) ──
            from personalscraper.verify.run import run_verify

            verify_report, verified = run_verify(
                settings, config=e2e_config, dry_run=False, tvshows_only=True, event_bus=EventBus()
            )
            print(f"  V4 Verify: {verify_report.success_count} valid")
            test_results = [v for v in verified if any(n.lower() in str(v.media_path).lower() for n in names.values())]
            assert_verify_complete(test_results)

            # ── 6. V5 Dispatch (DRY-RUN — disks are NEVER modified) ──
            from personalscraper.dispatch.run import run_dispatch

            dispatch_report, _ = run_dispatch(
                settings, config=e2e_config, dry_run=True, verified=verified, event_bus=EventBus()
            )
            print(f"  V5 Dispatch (dry-run): {dispatch_report.success_count} would dispatch")

            print("\n  Pipeline complete (dispatch was dry-run, disks untouched)")

        finally:
            # ── 7. Cleanup: staging + qBit torrents ──
            result = cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            print(f"\n  Cleanup: {result['staging']} staging, {result['torrents']} torrents removed")


@pytest.mark.e2e_torrent
class TestFullPipelineMixed:
    """Full pipeline test using the real `personalscraper run --dry-run` command.

    Invokes the CLI via CliRunner — exercising the full V6 orchestration.
    """

    def test_full_pipeline_via_run_command(
        self,
        e2e_session_id,
        e2e_registry,
        e2e_qbit_client,
        e2e_torrent_files,
        e2e_settings,
    ):
        """Run `personalscraper run --dry-run` on real downloaded data.

        Verifies lock, pipeline report, and rich console output.
        """
        if len(e2e_torrent_files) < 2:
            pytest.skip("Need at least 2 .torrent files (movie + tvshow) for mixed test")

        from personalscraper.conf.loader import load_config, resolve_config_path

        settings = e2e_settings
        e2e_config = load_config(resolve_config_path(None))
        staging = Path(e2e_config.paths.staging_dir)

        setup = TorrentSetup(client=e2e_qbit_client, registry=e2e_registry)
        cleanup = TestCleanup(
            registry=e2e_registry,
            dry_run=False,
            staging_dir=staging,
            disk_paths=[Path(d.path) for d in e2e_config.disks],
        )

        try:
            # 1. Setup: download all test torrents
            hashes = setup.add_torrent_files(e2e_torrent_files)
            names = setup.get_torrent_names(hashes)
            print(f"\n  Added {len(hashes)} torrent(s): {list(names.values())}")

            setup.wait_for_completion(hashes)

            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # 2. Ingest first so there's data in staging for the run command
            from personalscraper.ingest.ingest import run_ingest

            run_ingest(settings, dry_run=False, config=e2e_config, event_bus=EventBus(), torrent_client=e2e_qbit_client)

            # Register ingested items for cleanup
            for item in staging.iterdir():
                if item.is_dir() and not item.name.startswith(("0", ".")):
                    e2e_registry.register(item)

            # 3. Run the CLI `run --dry-run` command
            from typer.testing import CliRunner

            from personalscraper.cli import app

            runner = CliRunner()
            cli_result = runner.invoke(app, ["run", "--dry-run"])

            assert cli_result.exit_code in (0, 1), (
                f"CLI `run --dry-run` crashed (exit={cli_result.exit_code}):\n{cli_result.output}"
            )
            assert "Pipeline" in cli_result.output, f"Missing pipeline summary:\n{cli_result.output}"
            print(f"\n  CLI `run --dry-run` completed (exit={cli_result.exit_code})")
            print(f"  Output preview: {cli_result.output[:500]}")

        finally:
            result = cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            print(f"\n  Cleanup: {result['staging']} staging, {result['torrents']} torrents removed")
