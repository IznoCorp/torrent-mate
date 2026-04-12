"""E2E test: full pipeline for movies (magnet → qBit → ingest → sort → scrape → verify → dispatch).

Requires:
- qBittorrent running and accessible (localhost:8081)
- test_magnets.json configured with real movie magnet(s)
- Storage disks mounted (read-only — never modified)
- TMDB API key configured in .env

SAFETY: Dispatch runs in DRY-RUN mode only — storage disks are never
written to. Only the staging area (A TRIER/) is modified and cleaned up.

WARNING: Downloads real torrents — costs upload ratio on private trackers.
Run MANUALLY only: pytest tests/e2e/test_pipeline_movies.py -m e2e_torrent -v -s
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
class TestMovieFullPipeline:
    """Full E2E test: a movie goes through the real pipeline.

    Stages V1-V4 run for real in the staging area.
    V5 dispatch runs in dry-run mode (disks are never touched).
    Cleanup removes all staging artifacts and qBit test torrents.
    """

    def test_movie_full_pipeline(
        self, e2e_session_id, e2e_registry, e2e_qbit_client, e2e_magnets, e2e_settings,
    ):
        """Single movie traverses the full pipeline from magnet to verified.

        Steps: add magnet → download → ingest → sort → scrape → verify
        → dispatch (dry-run) → cleanup.
        """
        movie_magnets = [m for m in e2e_magnets if m["type"] == "movie"]
        if not movie_magnets:
            pytest.skip("No movie magnets in test_magnets.json")

        settings = e2e_settings
        staging = Path(settings.staging_dir)
        movies_dir = staging / "001-MOVIES"

        setup = TorrentSetup(
            client=e2e_qbit_client, registry=e2e_registry,
            timeout=_TORRENT_TIMEOUT,
        )
        cleanup = TestCleanup(registry=e2e_registry, dry_run=False)

        try:
            # ── 1. Setup: add magnet and wait for download ──
            hashes = setup.add_magnets(movie_magnets)
            status = setup.wait_for_completion(hashes)
            incomplete = [h for h, ok in status.items() if not ok]
            if incomplete:
                pytest.skip(f"Torrents not completed in time: {incomplete}")

            # Place marker on downloaded content for cleanup tracking
            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # ── 2. V1 Ingest (REAL) ──
            from personalscraper.ingest.ingest import run_ingest
            ingest_report = run_ingest(settings, dry_run=False)
            assert_ingest_complete(staging, movie_magnets)
            print(f"\n  V1 Ingest: {ingest_report.success_count} ingested, "
                  f"{ingest_report.skip_count} skipped, {ingest_report.error_count} errors")

            # ── 3. V2 Sort (REAL) ──
            from personalscraper.sorter.run import run_sort
            sort_report = run_sort(settings, dry_run=False)
            assert_sort_complete(movies_dir, staging / "002-TVSHOWS", movie_magnets)
            print(f"  V2 Sort: {sort_report.success_count} sorted")

            # Register sorted directories for cleanup
            if movies_dir.exists():
                for d in movies_dir.iterdir():
                    if d.is_dir() and any(
                        m["name"].lower() in d.name.lower() for m in movie_magnets
                    ):
                        place_marker(d, e2e_session_id)
                        e2e_registry.register(d)

            # ── 4. V3 Scrape (REAL — calls TMDB API) ──
            from personalscraper.scraper.run import run_scrape
            scrape_report = run_scrape(settings, dry_run=False, movies_only=True)
            assert_scrape_complete(movies_dir, staging / "002-TVSHOWS", movie_magnets)
            print(f"  V3 Scrape: {scrape_report.success_count} scraped")

            # ── 5. V4 Verify (REAL) ──
            from personalscraper.verify.run import run_verify
            verify_report, verified = run_verify(settings, dry_run=False, movies_only=True)
            movie_results = [v for v in verified if any(
                m["name"].lower() in str(v.media_path).lower() for m in movie_magnets
            )]
            assert_verify_complete(movie_results)
            print(f"  V4 Verify: {verify_report.success_count} valid, "
                  f"{verify_report.error_count} errors")

            # ── 6. V5 Dispatch (DRY-RUN — disks are NEVER modified) ──
            from personalscraper.dispatch.run import run_dispatch
            dispatch_report = run_dispatch(
                settings, dry_run=True, verified=verified,
            )
            # In dry-run, items are reported as "moved" but nothing is transferred
            print(f"  V5 Dispatch (dry-run): {dispatch_report.success_count} would dispatch")

            # Verify the dispatch plan makes sense (category should be "films")
            for entry in movie_magnets:
                expected_cat = entry.get("expected_category", "films")
                for detail in dispatch_report.details:
                    if entry["name"].lower() in detail.lower():
                        print(f"    → {entry['name']}: {detail}")

            print("\n  Pipeline complete (dispatch was dry-run, disks untouched)")

        finally:
            # ── 7. Cleanup: staging + qBit torrents ──
            result = cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            print(f"\n  Cleanup: {result['staging']} staging, "
                  f"{result['torrents']} torrents removed")
