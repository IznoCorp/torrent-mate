"""E2E test: full pipeline for movies (.torrent → qBit → ingest → sort → scrape → verify).

Requires:
- qBittorrent running and accessible (localhost:8081)
- .torrent files in assets/torrents/ (at least one movie)
- Storage disks mounted (read-only — never modified)
- TMDB API key configured in .env

SAFETY: Dispatch runs in DRY-RUN mode only — storage disks are never
written to. Only the staging area (A TRIER/) is modified and cleaned up.

WARNING: Downloads real torrents — costs upload ratio on private trackers.
Run MANUALLY only: pytest -m e2e_torrent -v -s
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


@pytest.mark.e2e_torrent
class TestMovieFullPipeline:
    """Full E2E test: a movie goes through the real pipeline.

    Stages V1-V4 run for real in the staging area.
    V5 dispatch runs in dry-run mode (disks are never touched).
    Cleanup removes all staging artifacts and qBit test torrents.
    """

    def test_movie_full_pipeline(
        self,
        e2e_session_id,
        e2e_registry,
        e2e_qbit_client,
        e2e_torrent_files,
        e2e_settings,
    ):
        """Single movie traverses the full pipeline from torrent to verified.

        Steps: add .torrent → download → ingest → sort → scrape → verify
        → dispatch (dry-run) → cleanup.
        """
        # Filter movie torrents (heuristic: no "S01" or "S02" in filename)
        movie_torrents = [f for f in e2e_torrent_files if not any(f"S{s:02d}" in f.name for s in range(1, 30))]
        if not movie_torrents:
            pytest.skip("No movie .torrent files in assets/torrents/")

        settings = e2e_settings
        staging = Path(settings.staging_dir)
        movies_dir = staging / "001-MOVIES"

        setup = TorrentSetup(client=e2e_qbit_client, registry=e2e_registry)
        cleanup = TestCleanup(registry=e2e_registry, dry_run=False)

        try:
            # ── 1. Setup: add .torrent files and wait for download ──
            hashes = setup.add_torrent_files(movie_torrents)
            names = setup.get_torrent_names(hashes)
            print(f"\n  Added {len(hashes)} movie torrent(s): {list(names.values())}")

            setup.wait_for_completion(hashes)

            # Place marker on downloaded content for cleanup tracking
            for downloaded in setup.get_downloaded_paths(hashes):
                if downloaded.is_dir():
                    place_marker(downloaded, e2e_session_id)
                    e2e_registry.register(downloaded)

            # ── 2. V1 Ingest (REAL) ──
            from personalscraper.ingest.ingest import run_ingest

            ingest_report = run_ingest(settings, dry_run=False)
            print(
                f"  V1 Ingest: {ingest_report.success_count} ingested, "
                f"{ingest_report.skip_count} skipped, {ingest_report.error_count} errors"
            )

            # Build expected list from torrent names for assertions
            expected = [{"name": n, "type": "movie"} for n in names.values()]
            assert_ingest_complete(staging, expected)

            # ── 3. V2 Sort (REAL) ──
            from personalscraper.sorter.run import run_sort

            sort_report = run_sort(settings, dry_run=False)
            print(f"  V2 Sort: {sort_report.success_count} sorted")
            assert_sort_complete(movies_dir, staging / "002-TVSHOWS", expected)

            # Register sorted directories for cleanup
            if movies_dir.exists():
                for d in movies_dir.iterdir():
                    if d.is_dir():
                        place_marker(d, e2e_session_id)
                        e2e_registry.register(d)

            # ── 4. V3 Scrape (REAL — calls TMDB API) ──
            from personalscraper.scraper.run import run_scrape

            scrape_report = run_scrape(settings, dry_run=False, movies_only=True)
            print(f"  V3 Scrape: {scrape_report.success_count} scraped")
            assert_scrape_complete(movies_dir, staging / "002-TVSHOWS", expected)

            # ── 4b. Golden file assertions (optional — skip if no golden file) ──
            from tests.e2e.assertions import (
                assert_scrape_golden,
                assert_structure_golden,
                find_media_dir,
            )
            from tests.e2e.golden import match_torrent_to_golden

            golden_results = {}
            for torrent_name in names.values():
                golden = match_torrent_to_golden(torrent_name)
                if golden:
                    print(f"  Golden match: {torrent_name} → {golden.name}")
                    media_dir = find_media_dir(movies_dir, golden.nfo["folder_name_pattern"])
                    assert_scrape_golden(media_dir, golden)
                    assert_structure_golden(media_dir, golden)
                    golden_results[torrent_name] = golden
                else:
                    print(f"  No golden file for {torrent_name} — smoke tests only")

            # ── 5. V4 Verify (REAL) ──
            from personalscraper.verify.run import run_verify

            verify_report, verified = run_verify(settings, dry_run=False, movies_only=True)
            print(f"  V4 Verify: {verify_report.success_count} valid, {verify_report.error_count} errors")
            # Filter verified results to test movies only
            test_results = [v for v in verified if any(n.lower() in str(v.media_path).lower() for n in names.values())]
            assert_verify_complete(test_results)

            # ── 6. V5 Dispatch (DRY-RUN — disks are NEVER modified) ──
            from personalscraper.dispatch.run import run_dispatch

            dispatch_report = run_dispatch(settings, dry_run=True, verified=verified)
            print(f"  V5 Dispatch (dry-run): {dispatch_report.success_count} would dispatch")

            # Note: golden dispatch assertions require DispatchResult objects,
            # but run_dispatch() returns a StepReport. Dispatch golden validation
            # is deferred to the standalone dispatch tests or future refactoring.

            print("\n  Pipeline complete (dispatch was dry-run, disks untouched)")

        finally:
            # ── 7. Cleanup: staging + qBit torrents ──
            result = cleanup.cleanup_all(client=e2e_qbit_client, force=True)
            print(f"\n  Cleanup: {result['staging']} staging, {result['torrents']} torrents removed")
