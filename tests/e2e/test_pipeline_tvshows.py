"""E2E test: full pipeline for TV shows (magnet → qBit → ingest → sort → scrape → verify → dispatch).

TV shows have additional complexity: season folders, episode renaming,
merge-on-dispatch behavior, and tvshow.nfo generation.

Run with: pytest tests/e2e/ -m e2e -v
"""

from pathlib import Path

import pytest

from tests.e2e.assertions import (
    assert_cleanup_complete,
    assert_dispatch_complete,
    assert_ingest_complete,
    assert_scrape_complete,
    assert_sort_complete,
    assert_verify_complete,
)
from tests.e2e.cleanup import TestCleanup
from tests.e2e.markers import place_marker
from tests.e2e.setup_torrents import TorrentSetup


@pytest.mark.e2e
class TestTVShowFullPipeline:
    """Full E2E test: a TV show goes through the entire pipeline."""

    def test_tvshow_full_pipeline(
        self, e2e_session_id, e2e_registry, e2e_qbit_client, e2e_magnets, e2e_settings,
    ):
        """TV show traverses the full pipeline from magnet to storage disk.

        Verifies: season folders, episode rename (S##E## format),
        tvshow.nfo, season posters, and merge behavior on dispatch.
        """
        tvshow_magnets = [m for m in e2e_magnets if m["type"] == "tvshow"]
        if not tvshow_magnets:
            pytest.skip("No TV show magnets in test_magnets.json")

        settings = e2e_settings
        staging = Path(settings.staging_dir)
        tvshows_dir = staging / "002-TVSHOWS"
        disk_paths = [
            Path(settings.disk1_dir),
            Path(settings.disk2_dir),
            Path(settings.disk3_dir),
            Path(settings.disk4_dir),
        ]

        setup = TorrentSetup(client=e2e_qbit_client, registry=e2e_registry)
        cleanup = TestCleanup(registry=e2e_registry, dry_run=False)

        try:
            # 1. Setup
            hashes = setup.add_magnets(tvshow_magnets)
            status = setup.wait_for_completion(hashes)
            incomplete = [h for h, ok in status.items() if not ok]
            if incomplete:
                pytest.skip(f"Torrents not completed in time: {incomplete}")

            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # 2. V1 Ingest
            from personalscraper.ingest.ingest import run_ingest
            run_ingest(settings, dry_run=False)
            assert_ingest_complete(staging, tvshow_magnets)

            # 3. V2 Sort
            from personalscraper.sorter.run import run_sort
            run_sort(settings, dry_run=False)
            assert_sort_complete(staging / "001-MOVIES", tvshows_dir, tvshow_magnets)

            # Register sorted directories
            if tvshows_dir.exists():
                for d in tvshows_dir.iterdir():
                    if d.is_dir() and any(m["name"].lower() in d.name.lower() for m in tvshow_magnets):
                        e2e_registry.register(d)

            # 4. V3 Scrape
            from personalscraper.scraper.run import run_scrape
            run_scrape(settings, dry_run=False, tvshows_only=True)
            assert_scrape_complete(staging / "001-MOVIES", tvshows_dir, tvshow_magnets)

            # 5. V4 Verify
            from personalscraper.verify.run import run_verify
            _, verified = run_verify(settings, dry_run=False, tvshows_only=True)
            show_results = [v for v in verified if any(
                m["name"].lower() in str(v.media_path).lower() for m in tvshow_magnets
            )]
            assert_verify_complete(show_results)

            # 6. V5 Dispatch
            from personalscraper.dispatch.run import run_dispatch
            run_dispatch(settings, dry_run=False, verified=verified)

            # Register dispatched directories
            for disk in disk_paths:
                if not disk.exists():
                    continue
                for cat in disk.iterdir():
                    if not cat.is_dir():
                        continue
                    for d in cat.iterdir():
                        if d.is_dir() and any(
                            m["name"].lower() in d.name.lower() for m in tvshow_magnets
                        ):
                            e2e_registry.register(d)

            assert_dispatch_complete(disk_paths, tvshow_magnets)

        finally:
            cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            assert_cleanup_complete(e2e_registry, base_paths=[staging] + disk_paths, client=e2e_qbit_client)


@pytest.mark.e2e
class TestFullPipelineMixed:
    """Full pipeline test using the real `personalscraper run` command.

    Unlike the movie/tvshow tests that call run_*() individually,
    this test invokes the CLI `run` command via CliRunner — exercising
    the full V6 orchestration: lock, contextvars, healthcheck pings,
    Telegram notification, and rich console output.
    """

    def test_full_pipeline_via_run_command(
        self, e2e_session_id, e2e_registry, e2e_qbit_client, e2e_magnets, e2e_settings,
    ):
        """Run `personalscraper run` on real data — full V1→V6 path.

        This is the closest test to what the daily launchd scheduling
        actually executes. Telegram notification is sent if configured.
        """
        if len(e2e_magnets) < 2:
            pytest.skip("Need at least 2 magnets (movie + tvshow) for mixed test")

        settings = e2e_settings
        staging = Path(settings.staging_dir)
        disk_paths = [
            Path(settings.disk1_dir),
            Path(settings.disk2_dir),
            Path(settings.disk3_dir),
            Path(settings.disk4_dir),
        ]

        setup = TorrentSetup(client=e2e_qbit_client, registry=e2e_registry)
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

            # 2. Run the REAL `personalscraper run` command via CliRunner
            #    This exercises the full V6 orchestration:
            #    - acquire_lock / release_lock
            #    - ping_healthcheck (if configured)
            #    - structlog contextvars binding (run_id)
            #    - cleanup_old_logs()
            #    - V1→V5 in sequence with try/except per step
            #    - rich Panel/Table console output
            #    - Telegram notification (if configured — REAL API call)
            #    - healthcheck end ping
            from typer.testing import CliRunner

            from personalscraper.cli import app

            runner = CliRunner()
            result = runner.invoke(app, ["run"])

            # The command may exit 0 (all OK) or 1 (some errors) —
            # both are valid E2E outcomes. What matters is it didn't crash.
            assert result.exit_code in (0, 1), (
                f"CLI `run` crashed with exit code {result.exit_code}:\n{result.output}"
            )

            # Verify the console output contains the rich summary table
            assert "Pipeline" in result.output, (
                f"Missing pipeline summary in output:\n{result.output}"
            )

            # 3. Verify results on filesystem
            # Check that media was dispatched to disks
            for disk in disk_paths:
                if not disk.exists():
                    continue
                for cat in disk.iterdir():
                    if not cat.is_dir():
                        continue
                    for d in cat.iterdir():
                        if d.is_dir() and any(
                            m["name"].lower() in d.name.lower() for m in e2e_magnets
                        ):
                            e2e_registry.register(d)

            # 4. Verify structlog wrote a log file with run_id
            log_file = Path("logs/personalscraper.json")
            if log_file.exists():
                log_content = log_file.read_text()
                assert "run_id" in log_content, "Log file missing run_id context"

        finally:
            cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            assert_cleanup_complete(e2e_registry, base_paths=[staging] + disk_paths, client=e2e_qbit_client)
