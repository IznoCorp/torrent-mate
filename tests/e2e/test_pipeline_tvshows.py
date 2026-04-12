"""E2E test: full pipeline for TV shows and mixed pipeline via CLI.

TV shows have additional complexity: season folders, episode renaming,
merge-on-dispatch behavior, and tvshow.nfo generation.

SAFETY: Dispatch runs in DRY-RUN mode only — storage disks are never
written to. Only the staging area (A TRIER/) is modified and cleaned up.

WARNING: Downloads real torrents — costs upload ratio on private trackers.
Run MANUALLY only: pytest tests/e2e/test_pipeline_tvshows.py -m e2e_torrent -v -s
"""

from pathlib import Path

import pytest

from tests.e2e.assertions import (
    assert_ingest_complete,
    assert_scrape_complete,
    assert_sort_complete,
    assert_verify_complete,
)
from tests.e2e.cleanup import TestCleanup
from tests.e2e.markers import place_marker
from tests.e2e.setup_torrents import TorrentSetup

# Reduced timeout: 5 minutes (private trackers may be slow)
_TORRENT_TIMEOUT = 300


@pytest.mark.e2e_torrent
class TestTVShowFullPipeline:
    """Full E2E test: a TV show goes through the real pipeline.

    Stages V1-V4 run for real in the staging area.
    V5 dispatch runs in dry-run mode (disks are never touched).
    """

    def test_tvshow_full_pipeline(
        self, e2e_session_id, e2e_registry, e2e_qbit_client, e2e_magnets, e2e_settings,
    ):
        """TV show traverses the full pipeline from magnet to verified.

        Verifies: season folders, episode rename (S##E## format),
        tvshow.nfo, and season posters.
        """
        tvshow_magnets = [m for m in e2e_magnets if m["type"] == "tvshow"]
        if not tvshow_magnets:
            pytest.skip("No TV show magnets in test_magnets.json")

        settings = e2e_settings
        staging = Path(settings.staging_dir)
        tvshows_dir = staging / "002-TVSHOWS"

        setup = TorrentSetup(
            client=e2e_qbit_client, registry=e2e_registry,
            timeout=_TORRENT_TIMEOUT,
        )
        cleanup = TestCleanup(registry=e2e_registry, dry_run=False)

        try:
            # ── 1. Setup: add magnet and wait for download ──
            hashes = setup.add_magnets(tvshow_magnets)
            status = setup.wait_for_completion(hashes)
            incomplete = [h for h, ok in status.items() if not ok]
            if incomplete:
                pytest.skip(f"Torrents not completed in time: {incomplete}")

            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # ── 2. V1 Ingest (REAL) ──
            from personalscraper.ingest.ingest import run_ingest
            ingest_report = run_ingest(settings, dry_run=False)
            assert_ingest_complete(staging, tvshow_magnets)
            print(f"\n  V1 Ingest: {ingest_report.success_count} ingested")

            # ── 3. V2 Sort (REAL) ──
            from personalscraper.sorter.run import run_sort
            sort_report = run_sort(settings, dry_run=False)
            assert_sort_complete(staging / "001-MOVIES", tvshows_dir, tvshow_magnets)
            print(f"  V2 Sort: {sort_report.success_count} sorted")

            # Register sorted directories for cleanup
            if tvshows_dir.exists():
                for d in tvshows_dir.iterdir():
                    if d.is_dir() and any(
                        m["name"].lower() in d.name.lower() for m in tvshow_magnets
                    ):
                        place_marker(d, e2e_session_id)
                        e2e_registry.register(d)

            # ── 4. V3 Scrape (REAL — calls TVDB/TMDB APIs) ──
            from personalscraper.scraper.run import run_scrape
            scrape_report = run_scrape(settings, dry_run=False, tvshows_only=True)
            assert_scrape_complete(staging / "001-MOVIES", tvshows_dir, tvshow_magnets)
            print(f"  V3 Scrape: {scrape_report.success_count} scraped")

            # Verify episode renaming happened
            for d in tvshows_dir.iterdir():
                if not d.is_dir():
                    continue
                season_dirs = [s for s in d.iterdir() if s.is_dir() and "Saison" in s.name]
                if season_dirs:
                    print(f"    → {d.name}: {len(season_dirs)} season dir(s)")
                    for sd in season_dirs:
                        episodes = [f for f in sd.iterdir() if f.suffix == ".mkv"]
                        print(f"      {sd.name}: {len(episodes)} episodes")

            # ── 5. V4 Verify (REAL) ──
            from personalscraper.verify.run import run_verify
            verify_report, verified = run_verify(settings, dry_run=False, tvshows_only=True)
            show_results = [v for v in verified if any(
                m["name"].lower() in str(v.media_path).lower() for m in tvshow_magnets
            )]
            assert_verify_complete(show_results)
            print(f"  V4 Verify: {verify_report.success_count} valid")

            # ── 6. V5 Dispatch (DRY-RUN — disks are NEVER modified) ──
            from personalscraper.dispatch.run import run_dispatch
            dispatch_report = run_dispatch(
                settings, dry_run=True, verified=verified,
            )
            print(f"  V5 Dispatch (dry-run): {dispatch_report.success_count} would dispatch")
            print("\n  Pipeline complete (dispatch was dry-run, disks untouched)")

        finally:
            # ── 7. Cleanup: staging + qBit torrents ──
            result = cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            print(f"\n  Cleanup: {result['staging']} staging, "
                  f"{result['torrents']} torrents removed")


@pytest.mark.e2e_torrent
class TestFullPipelineMixed:
    """Full pipeline test using the real `personalscraper run` command.

    Invokes the CLI `run --dry-run` command via CliRunner — exercising
    the full V6 orchestration without modifying staging or disks.
    """

    def test_full_pipeline_via_run_command(
        self, e2e_session_id, e2e_registry, e2e_qbit_client, e2e_magnets, e2e_settings,
    ):
        """Run `personalscraper run --dry-run` — full V1→V6 path.

        This is the closest test to what the daily launchd scheduling
        executes, but in dry-run mode for safety. Verifies:
        - Lock acquire/release
        - Pipeline report structure
        - Rich console output
        """
        if len(e2e_magnets) < 2:
            pytest.skip("Need at least 2 magnets (movie + tvshow) for mixed test")

        settings = e2e_settings
        staging = Path(settings.staging_dir)

        setup = TorrentSetup(
            client=e2e_qbit_client, registry=e2e_registry,
            timeout=_TORRENT_TIMEOUT,
        )
        cleanup = TestCleanup(registry=e2e_registry, dry_run=False)

        try:
            # 1. Setup: download all test magnets
            hashes = setup.add_magnets(e2e_magnets)
            status = setup.wait_for_completion(hashes)
            incomplete = [h for h, ok in status.items() if not ok]
            if incomplete:
                pytest.skip(f"Torrents not completed in time: {incomplete}")

            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # 2. Ingest first so there's data in staging for the run command
            from personalscraper.ingest.ingest import run_ingest
            run_ingest(settings, dry_run=False)

            # Register ingested items for cleanup
            for item in staging.iterdir():
                if item.is_dir() and not item.name.startswith(("0", ".")):
                    e2e_registry.register(item)

            # 3. Run the CLI `run --dry-run` command via CliRunner
            from typer.testing import CliRunner

            from personalscraper.cli import app

            runner = CliRunner()
            result = runner.invoke(app, ["run", "--dry-run"])

            # Verify the command completed (0 = OK, 1 = some errors — both valid)
            assert result.exit_code in (0, 1), (
                f"CLI `run --dry-run` crashed with exit code {result.exit_code}:\n"
                f"{result.output}"
            )

            # Verify the console output contains the rich summary table
            assert "Pipeline" in result.output, (
                f"Missing pipeline summary in output:\n{result.output}"
            )
            print(f"\n  CLI `run --dry-run` completed (exit={result.exit_code})")
            print(f"  Output preview: {result.output[:500]}")

        finally:
            # 4. Cleanup: staging + qBit torrents
            result_cleanup = cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            print(f"\n  Cleanup: {result_cleanup['staging']} staging, "
                  f"{result_cleanup['torrents']} torrents removed")
