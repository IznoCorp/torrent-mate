"""Unit tests for TrailersOrchestrator, full pipeline glue.

All dependencies (TrailerFinder, YtdlpDownloader, TrailerStateStore) are mocked.
Scanner is patched to return controlled ScanItem lists.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.scanner import ScanItem
from personalscraper.trailers.state import TrailerStatus


def _make_config(tmp_path: Path) -> MagicMock:
    """Build a minimal mock config for orchestrator unit tests.

    Args:
        tmp_path: Pytest tmp_path fixture used for state file location.

    Returns:
        MagicMock configured with all fields the orchestrator reads.
    """
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.languages = ["fr-FR", "en-US"]
    cfg.trailers.fallback_youtube_search = True
    cfg.trailers.search_query_format = "{title} {year} bande annonce"
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.filters.max_filesize_mb = 500
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.ytdlp.format = "best[ext=mp4]/best"
    cfg.trailers.ytdlp.socket_timeout_sec = 30
    cfg.trailers.ytdlp.retries = 3
    cfg.trailers.seasons.enabled = False
    cfg.trailers.seasons.language_fallback = None
    cfg.trailers.seasons.search_query_format = "{title} {year} saison {season} bande annonce"
    cfg.trailers.library_check.movies = False
    cfg.trailers.library_check.tv_shows = True
    # Step budget - use a large value by default so tests are not affected
    cfg.trailers.step.max_duration_sec = 1800
    return cfg


@pytest.fixture()
def orchestrator(tmp_path: Path) -> TrailersOrchestrator:
    """Provide a default TrailersOrchestrator for unit tests.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        A TrailersOrchestrator instance backed by a mock config.
    """
    config = _make_config(tmp_path)
    return TrailersOrchestrator(config=config, staging_dir=tmp_path)


_SCAN_ITEM = ScanItem(
    path=Path("/fake/Fight Club (1999)"),
    media_type="movie",
    title="Fight Club",
    year=1999,
    tmdb_id="550",
)


class TestTrailersOrchestratorBasic:
    """Basic counter and SOT tests for TrailersOrchestrator.run().

    All scraper/state dependencies are patched at the object level.
    """

    def test_downloaded_increments_counter(self, orchestrator: TrailersOrchestrator, tmp_path: Path) -> None:
        """counts[downloaded] is incremented when download succeeds.

        Args:
            orchestrator: Orchestrator fixture.
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(
                    status=DownloadStatus.SUCCESS,
                    output_path=tmp_path / "Fight Club (1999)-trailer.mp4",
                ),
            ),
        ):
            counts = orchestrator.run()
        assert counts["downloaded"] == 1

    def test_already_present_increments_counter(self, orchestrator: TrailersOrchestrator, tmp_path: Path) -> None:
        """counts[already_present] when trailer file exists before download.

        Args:
            orchestrator: Orchestrator fixture.
            tmp_path: Pytest tmp_path fixture.
        """
        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        trailer = media_dir / "Fight Club (1999)-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)

        item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )
        with patch.object(orchestrator._scanner, "scan_staging", return_value=[item]):
            counts = orchestrator.run()
        assert counts["already_present"] == 1

    def test_no_trailer_increments_counter_when_finder_returns_none(self, orchestrator: TrailersOrchestrator) -> None:
        """counts[no_trailer] when TrailerFinder.find() returns None.

        Args:
            orchestrator: Orchestrator fixture.
        """
        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=None),
        ):
            counts = orchestrator.run()
        assert counts["no_trailer"] == 1

    def test_skipped_by_state_when_should_skip(self, orchestrator: TrailersOrchestrator) -> None:
        """counts[skipped_by_state] when state store says should_skip.

        Args:
            orchestrator: Orchestrator fixture.
        """
        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._state_store, "should_skip", return_value=True),
        ):
            counts = orchestrator.run()
        assert counts["skipped_by_state"] == 1

    def test_empty_scan_returns_zero_counts(self, orchestrator: TrailersOrchestrator) -> None:
        """run() returns all-zero counts when scanner finds nothing.

        Args:
            orchestrator: Orchestrator fixture.
        """
        with patch.object(orchestrator._scanner, "scan_staging", return_value=[]):
            counts = orchestrator.run()
        assert all(v == 0 for v in counts.values())

    def test_sot_recheck_before_download(self, orchestrator: TrailersOrchestrator, tmp_path: Path) -> None:
        """Orchestrator re-checks trailer_exists immediately before download.

        Race simulation: the scanner reports the item as missing a trailer, but
        the trailer file materializes between scan and download. The SOT re-check
        MUST see the file and short-circuit to already_present.

        Args:
            orchestrator: Orchestrator fixture.
            tmp_path: Pytest tmp_path fixture.
        """
        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        trailer = media_dir / "Fight Club (1999)-trailer.mp4"

        item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )

        def create_trailer_on_find(  # noqa: ARG001
            tmdb_id: int, media_type: str, *, title: str, year: int, season_number: int | None = None
        ) -> str:
            # Simulate trailer appearing between scan and the SOT re-check.
            trailer.write_bytes(b"x" * 200000)
            return "https://youtube.com/watch?v=X"

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
            patch.object(orchestrator._finder, "find", side_effect=create_trailer_on_find),
            patch.object(orchestrator._downloader, "download") as mock_download,
        ):
            counts = orchestrator.run()

        assert counts.get("already_present", 0) == 1, (
            "SOT re-check failed to notice trailer that appeared between scan and download"
        )
        assert counts.get("downloaded", 0) == 0, "Downloader was called despite the trailer already existing on disk"
        mock_download.assert_not_called()


class TestDiskSpaceAndBudget:
    """Tests for disk-space pre-check and step-budget enforcement.

    These tests verify DESIGN SS12 operational safeguards.
    """

    def test_skips_item_when_disk_space_low(self, orchestrator: TrailersOrchestrator, tmp_path: Path) -> None:
        """Items are skipped with skipped_by_filter when disk space is insufficient.

        Args:
            orchestrator: Orchestrator fixture.
            tmp_path: Pytest tmp_path fixture.
        """
        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )

        from unittest.mock import MagicMock as MM

        usage = MM()
        usage.free = 0  # effectively zero free space

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(orchestrator._downloader, "download") as mock_dl,
            patch("personalscraper.trailers.orchestrator.shutil.disk_usage", return_value=usage),
        ):
            counts = orchestrator.run()

        assert counts["skipped_by_filter"] == 1
        mock_dl.assert_not_called()

    def test_step_budget_exceeded_breaks_loop(self, tmp_path: Path) -> None:
        """When max_duration_sec=0, the loop breaks immediately after SOT check.

        The first item passes state skip and SOT checks but the budget fires
        before find() is called.  Remaining items are not attempted.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.step.max_duration_sec = 0
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        item_a = ScanItem(
            path=Path("/fake/ItemA (2000)"),
            media_type="movie",
            title="ItemA",
            year=2000,
            tmdb_id="100",
        )
        item_b = ScanItem(
            path=Path("/fake/ItemB (2001)"),
            media_type="movie",
            title="ItemB",
            year=2001,
            tmdb_id="200",
        )

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item_a, item_b]),
            patch.object(orch._finder, "find") as mock_find,
            patch.object(orch._downloader, "download") as mock_dl,
        ):
            counts = orch.run()

        # Neither item should have gotten to the finder (budget fires before find)
        mock_find.assert_not_called()
        mock_dl.assert_not_called()
        # Both items are not downloaded
        assert counts["downloaded"] == 0


class TestLibraryAwareRecheck:
    """Tests for DESIGN SS8 library-aware idempotence.

    These tests verify that the orchestrator calls library.scanner.scan_library
    at most once per run, honours per-media-type toggles, and correctly
    short-circuits items when a valid trailer is found on a storage disk.
    """

    def _make_lib_item(self, tmp_path: Path, tmdb_id: str) -> MagicMock:
        """Build a fake LibraryScanItem for the library index.

        Args:
            tmp_path: Directory to use as the item path.
            tmdb_id: TMDB ID string to set on nfo.tmdb_id.

        Returns:
            MagicMock with the fields the orchestrator reads.
        """
        lib_item = MagicMock()
        lib_item.path = str(tmp_path / "Fight Club (1999)")
        lib_item.category = "movies"
        lib_item.nfo.tmdb_id = tmdb_id
        lib_item.nfo.imdb_id = None
        return lib_item

    def test_library_aware_recheck_skips_when_trailer_on_disk(self, tmp_path: Path) -> None:
        """Orchestrator increments already_present_on_disk when trailer exists at library location.

        When library_check.tv_shows is True and the library scan returns a
        LibraryScanItem whose path contains a valid trailer, the orchestrator must:
        - increment already_present_on_disk
        - write a state entry with status=ALREADY_PRESENT_ON_DISK
        - NOT call finder.find() nor downloader.download()

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        # Create a TV show item in staging
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        item = ScanItem(
            path=show_dir,
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
        )

        # Create the library directory with a valid trailer
        lib_show_dir = tmp_path / "lib" / "Breaking Bad (2008)"
        lib_show_dir.mkdir(parents=True)
        lib_trailer = lib_show_dir / "Breaking Bad (2008)-trailer.mp4"
        lib_trailer.write_bytes(b"x" * 200000)

        # Build fake LibraryScanResult
        lib_item = MagicMock()
        lib_item.path = str(lib_show_dir)
        lib_item.category = "tv_shows"
        lib_item.nfo.tmdb_id = "1396"
        lib_item.nfo.imdb_id = None
        lib_result = MagicMock()
        lib_result.items = [lib_item]

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item]),
            patch.object(orch._finder, "find") as mock_find,
            patch.object(orch._downloader, "download") as mock_dl,
            patch(
                "personalscraper.trailers.orchestrator.library_scanner.scan_library",
                return_value=lib_result,
            ),
        ):
            counts = orch.run()

        assert counts["already_present_on_disk"] == 1
        assert counts["downloaded"] == 0
        mock_find.assert_not_called()
        mock_dl.assert_not_called()

        # State entry must be written with ALREADY_PRESENT_ON_DISK
        state = orch._state_store.get("tv:tmdb:1396")
        assert state is not None
        assert state.status == TrailerStatus.ALREADY_PRESENT_ON_DISK
        assert state.trailer_path == str(lib_trailer)

    def test_library_aware_recheck_falls_through_when_library_item_absent(self, tmp_path: Path) -> None:
        """When the library scan returns no matching item, fall through to staging SOT.

        The downloader must be reachable when the staging trailer is also missing.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        item = ScanItem(
            path=Path("/fake/Breaking Bad (2008)"),
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
        )

        empty_result = MagicMock()
        empty_result.items = []

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item]),
            patch.object(orch._finder, "find", return_value="https://youtube.com/watch?v=Y"),
            patch.object(
                orch._downloader,
                "download",
                return_value=DownloadResult(
                    status=DownloadStatus.SUCCESS,
                    output_path=Path("/fake/Breaking Bad (2008)-trailer.mp4"),
                ),
            ),
            patch(
                "personalscraper.trailers.orchestrator.library_scanner.scan_library",
                return_value=empty_result,
            ),
        ):
            counts = orch.run()

        # No library match -> falls through to staging check -> downloader reachable
        assert counts["downloaded"] == 1
        assert counts["already_present_on_disk"] == 0

    def test_library_aware_recheck_disabled_for_both_types_skips_scan(self, tmp_path: Path) -> None:
        """When both library_check toggles are False, scan_library is never called.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = False
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        tv_item = ScanItem(
            path=Path("/fake/Breaking Bad (2008)"),
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
        )
        movie_item = ScanItem(
            path=Path("/fake/Fight Club (1999)"),
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[tv_item, movie_item]),
            patch.object(orch._finder, "find", return_value=None),
            patch(
                "personalscraper.trailers.orchestrator.library_scanner.scan_library",
            ) as mock_scan,
        ):
            orch.run()

        mock_scan.assert_not_called()

    def test_library_aware_recheck_movies_off_tvshows_on_default(self, tmp_path: Path) -> None:
        """Default config: movies skip library check, TV shows trigger it.

        With movies=False and tv_shows=True (defaults):
        - A movie ScanItem skips the library check and falls through to staging.
        - A TV show ScanItem triggers scan_library (called lazily once on first TV item).

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        movie_item = ScanItem(
            path=Path("/fake/Fight Club (1999)"),
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )
        tv_item = ScanItem(
            path=Path("/fake/Breaking Bad (2008)"),
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
        )

        empty_result = MagicMock()
        empty_result.items = []

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[movie_item, tv_item]),
            patch.object(orch._finder, "find", return_value=None),
            patch(
                "personalscraper.trailers.orchestrator.library_scanner.scan_library",
                return_value=empty_result,
            ) as mock_scan,
        ):
            orch.run()

        # Called once for the TV item (lazy init). Not called for the movie.
        mock_scan.assert_called_once()

    def test_library_aware_recheck_movies_opted_in(self, tmp_path: Path) -> None:
        """When library_check.movies=True, movie items also trigger the library check.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = True
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        movie_item = ScanItem(
            path=Path("/fake/Fight Club (1999)"),
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )

        empty_result = MagicMock()
        empty_result.items = []

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[movie_item]),
            patch.object(orch._finder, "find", return_value=None),
            patch(
                "personalscraper.trailers.orchestrator.library_scanner.scan_library",
                return_value=empty_result,
            ) as mock_scan,
        ):
            orch.run()

        # Library check triggered even for movie items when opted in
        mock_scan.assert_called_once()

    def test_library_scan_called_only_once_per_run(self, tmp_path: Path) -> None:
        """scan_library is called at most once per run(), not once per TV item.

        With two TV show items and tv_shows=True, the index is built once on the
        first item, then reused for the second.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        tv_a = ScanItem(
            path=Path("/fake/Show A (2000)"),
            media_type="tvshow",
            title="Show A",
            year=2000,
            tmdb_id="1111",
        )
        tv_b = ScanItem(
            path=Path("/fake/Show B (2001)"),
            media_type="tvshow",
            title="Show B",
            year=2001,
            tmdb_id="2222",
        )

        empty_result = MagicMock()
        empty_result.items = []

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[tv_a, tv_b]),
            patch.object(orch._finder, "find", return_value=None),
            patch(
                "personalscraper.trailers.orchestrator.library_scanner.scan_library",
                return_value=empty_result,
            ) as mock_scan,
        ):
            orch.run()

        # Only one library scan regardless of item count
        assert mock_scan.call_count == 1


class TestTrailersOrchestratorEdgeCases:
    """Edge-case tests for uncovered orchestrator branches."""

    def test_run_with_config_missing_optional_attrs(self, tmp_path: "Path") -> None:
        """Orchestrator.run() falls back to defaults when AttributeError on optional config."""
        from unittest.mock import MagicMock, patch

        # Config with only required fields -- optional ones raise AttributeError
        cfg = MagicMock(spec=["trailers"])
        cfg.trailers.enabled = True
        cfg.trailers.languages = ["en-US"]
        cfg.trailers.fallback_youtube_search = False
        cfg.trailers.filters.min_file_size_bytes = 102400
        cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
        cfg.trailers.ytdlp.format = "best"
        cfg.trailers.ytdlp.socket_timeout_sec = 30
        cfg.trailers.ytdlp.retries = 3
        cfg.trailers.seasons.enabled = False
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = False
        # These will raise AttributeError to cover fallback branches
        del cfg.trailers.step
        del cfg.trailers.filters.max_filesize_mb
        del cfg.trailers.retry_after_days

        from personalscraper.trailers.orchestrator import TrailersOrchestrator

        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        with patch.object(orch._scanner, "scan_staging", return_value=[]):
            counts = orch.run()

        assert counts["downloaded"] == 0

    def test_run_bot_detected_increments_counter(self, orchestrator: "TrailersOrchestrator", tmp_path: "Path") -> None:
        """counts[bot_detected] is incremented when downloader returns BOT_DETECTED."""
        from unittest.mock import patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(
                    status=DownloadStatus.BOT_DETECTED,
                    output_path=None,
                    error_message="bot detected",
                ),
            ),
        ):
            counts = orchestrator.run()
        assert counts["bot_detected"] == 1

    def test_run_http_error_increments_counter(self, orchestrator: "TrailersOrchestrator", tmp_path: "Path") -> None:
        """counts[http_error] is incremented when downloader returns HTTP_ERROR."""
        from unittest.mock import patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(
                    status=DownloadStatus.HTTP_ERROR,
                    output_path=None,
                    error_message="403 forbidden",
                ),
            ),
        ):
            counts = orchestrator.run()
        assert counts["http_error"] == 1

    def test_run_finder_exception_increments_error(self, orchestrator: "TrailersOrchestrator") -> None:
        """counts[error] is incremented when TrailerFinder.find() raises an exception."""
        from unittest.mock import patch

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", side_effect=RuntimeError("network down")),
        ):
            counts = orchestrator.run()
        assert counts["error"] == 1

    def test_run_ytdlp_error_increments_counter(self, orchestrator: "TrailersOrchestrator") -> None:
        """counts[ytdlp_error] is incremented when downloader returns an unhandled status."""
        from unittest.mock import patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(
                    status=DownloadStatus.YTDLP_ERROR,
                    output_path=None,
                    error_message="ytdlp failed",
                ),
            ),
        ):
            counts = orchestrator.run()
        assert counts["ytdlp_error"] == 1
