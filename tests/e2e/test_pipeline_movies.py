"""E2E test: full pipeline for movies (magnet → qBit → ingest → sort → scrape → verify → dispatch).

Requires:
- qBittorrent running and accessible
- test_magnets.json configured with real movie magnet(s)
- Storage disks mounted
- TMDB API key configured

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
from tests.e2e.markers import place_marker, verify_marker
from tests.e2e.setup_torrents import TorrentSetup


@pytest.mark.e2e
class TestMovieFullPipeline:
    """Full E2E test: a movie goes through the entire pipeline."""

    def test_movie_full_pipeline(
        self, e2e_session_id, e2e_registry, e2e_qbit_client, e2e_magnets, e2e_settings,
    ):
        """Single movie traverses the full pipeline from magnet to storage disk.

        Steps: setup → ingest → sort → scrape → verify → dispatch → cleanup.
        Marker survival is verified at each stage.
        """
        # Filter movie magnets only
        movie_magnets = [m for m in e2e_magnets if m["type"] == "movie"]
        if not movie_magnets:
            pytest.skip("No movie magnets in test_magnets.json")

        settings = e2e_settings
        staging = Path(settings.staging_dir)
        movies_dir = staging / "001-MOVIES"
        disk_paths = [
            Path(settings.disk1_dir),
            Path(settings.disk2_dir),
            Path(settings.disk3_dir),
            Path(settings.disk4_dir),
        ]

        setup = TorrentSetup(client=e2e_qbit_client, registry=e2e_registry)
        cleanup = TestCleanup(registry=e2e_registry, dry_run=False)

        try:
            # 1. Setup: add magnet and wait for download
            hashes = setup.add_magnets(movie_magnets)
            status = setup.wait_for_completion(hashes)
            incomplete = [h for h, ok in status.items() if not ok]
            if incomplete:
                pytest.skip(f"Torrents not completed in time: {incomplete}")

            # Place marker on downloaded content
            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # 2. V1 Ingest
            from personalscraper.ingest.ingest import run_ingest
            run_ingest(settings, dry_run=False)
            assert_ingest_complete(staging, movie_magnets)

            # 3. V2 Sort
            from personalscraper.sorter.run import run_sort
            run_sort(settings, dry_run=False)
            assert_sort_complete(movies_dir, staging / "002-TVSHOWS", movie_magnets)

            # Register sorted directories for cleanup
            if movies_dir.exists():
                for d in movies_dir.iterdir():
                    if d.is_dir() and any(m["name"].lower() in d.name.lower() for m in movie_magnets):
                        e2e_registry.register(d)

            # 4. V3 Scrape
            from personalscraper.scraper.run import run_scrape
            run_scrape(settings, dry_run=False, movies_only=True)
            assert_scrape_complete(movies_dir, staging / "002-TVSHOWS", movie_magnets)

            # 5. V4 Verify
            from personalscraper.verify.run import run_verify
            _, verified = run_verify(settings, dry_run=False, movies_only=True)
            movie_results = [v for v in verified if any(
                m["name"].lower() in str(v.media_path).lower() for m in movie_magnets
            )]
            assert_verify_complete(movie_results)

            # 6. V5 Dispatch
            from personalscraper.dispatch.run import run_dispatch
            run_dispatch(settings, dry_run=False, verified=verified)

            # Register dispatched directories for cleanup
            for disk in disk_paths:
                if not disk.exists():
                    continue
                for cat in disk.iterdir():
                    if not cat.is_dir():
                        continue
                    for d in cat.iterdir():
                        if d.is_dir() and any(
                            m["name"].lower() in d.name.lower() for m in movie_magnets
                        ):
                            e2e_registry.register(d)

            assert_dispatch_complete(disk_paths, movie_magnets)

            # Verify marker survived the entire pipeline
            for disk in disk_paths:
                for cat in disk.iterdir():
                    if not cat.is_dir():
                        continue
                    for d in cat.iterdir():
                        if d.is_dir() and any(
                            m["name"].lower() in d.name.lower() for m in movie_magnets
                        ):
                            assert verify_marker(d, e2e_session_id, e2e_registry), (
                                f"Marker lost during pipeline for {d}"
                            )

        finally:
            # 7. Cleanup: always runs even if test fails
            cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            assert_cleanup_complete(e2e_registry, base_paths=[staging] + disk_paths, client=e2e_qbit_client)
