"""Unit tests for TrailersOrchestrator, full pipeline glue.

All dependencies (TrailerFinder, YtdlpDownloader, TrailerStateStore) are mocked.
Scanner is patched to return controlled ScanItem lists.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.event_bus import EventBus
from personalscraper.trailers.orchestrator import TrailersOrchestrator, _LibraryEntry
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
    return TrailersOrchestrator(
        config=config,
        staging_dir=tmp_path,
        event_bus=EventBus(),
        registry=MagicMock(spec=ProviderRegistry),
    )


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
        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

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


class TestTrailersOrchestratorFallback:
    """Tests for the same-run YouTube-search fallback (feat/trailer-fallback).

    All tests reproduce the SMG/FROM miss: TMDB finds a URL, download fails,
    fallback searches YouTube, re-download may succeed or fail. AC-1..AC-7.
    """

    def test_ytdlp_failure_triggers_youtube_fallback_and_succeeds(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-1: TMDB URL -> YTDLP_ERROR, YouTube search -> ALT_URL -> SUCCESS.

        Reproduces the Super Mario Galaxy / FROM miss (2026-06-16 run).
        download() is called twice; final state is DOWNLOADED with
        source=="youtube" and youtube_url==ALT_URL. ytdlp_error counter stays 0.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        alt_url = "https://youtube.com/watch?v=ALT_GOOD"

        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        success_result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            output_path=MagicMock(),
            error_message=None,
        )
        download_mock = MagicMock(side_effect=[fail_result, success_result])

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=alt_url),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        # download called twice: once with tmdb_url, once with alt_url
        # (assert on the URL positionally; the path arg is an internal Path object)
        assert download_mock.call_count == 2
        assert download_mock.call_args_list[0].args[0] == tmdb_url
        assert download_mock.call_args_list[1].args[0] == alt_url

        # Counters: success path, not error path
        assert counts.get("downloaded", 0) == 1
        assert counts.get("ytdlp_error", 0) == 0

        # State written with DOWNLOADED + source=youtube + youtube_url=alt_url
        assert mock_state.call_count == 1
        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.DOWNLOADED
        assert state_arg.source == "youtube"
        assert state_arg.youtube_url == alt_url
        # DESIGN §State: one logical item-attempt even though two URLs were tried.
        assert state_arg.attempts == 1

    def test_ytdlp_failure_fallback_also_fails_keeps_terminal_state(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-2: Both downloads fail -> download x2, ytdlp_error==1, terminal state.

        When the fallback also returns YTDLP_ERROR, the item ends in the same
        terminal state as before (YTDLP_ERROR + next_retry_at) and the counter
        increments once.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        alt_url = "https://youtube.com/watch?v=ALT_ALSO_DEAD"

        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(side_effect=[fail_result, fail_result])

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=alt_url),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        assert download_mock.call_count == 2
        assert counts.get("ytdlp_error", 0) == 1
        assert counts.get("downloaded", 0) == 0

        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.YTDLP_ERROR
        assert state_arg.next_retry_at is not None
        # DESIGN §State: the fallback re-download must not inflate the attempt count.
        assert state_arg.attempts == 1

    def test_ytdlp_failure_fallback_returns_none_no_second_download(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-3: YouTube search returns None -> no 2nd download, terminal state.

        When the search engine finds nothing, the fallback is a no-op:
        download is called exactly once and the item fails terminally.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=None),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        assert download_mock.call_count == 1
        assert counts.get("ytdlp_error", 0) == 1

        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.YTDLP_ERROR

    def test_ytdlp_failure_fallback_returns_same_url_no_double_download(
        self, orchestrator: "TrailersOrchestrator"
    ) -> None:
        """AC-4: YouTube search returns the already-failed URL -> tried-set blocks 2nd download.

        When the fallback search returns the same URL that just failed,
        the tried-set guard prevents a redundant re-download.
        download is called exactly once.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        tmdb_url = "https://youtube.com/watch?v=SAME"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=tmdb_url),
        ):
            orchestrator.run()

        assert download_mock.call_count == 1

    def test_fallback_disabled_by_config(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-5: fallback_youtube_search=False -> search NOT called, download x1, terminal.

        When the operator disables the fallback, behavior is identical to
        pre-0.35.0: one download attempt, terminal failure, no YouTube search.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        orchestrator._config.trailers.fallback_youtube_search = False

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)
        search_mock = MagicMock()

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", search_mock),
        ):
            counts = orchestrator.run()

        search_mock.assert_not_called()
        assert download_mock.call_count == 1
        assert counts.get("ytdlp_error", 0) == 1

    def test_fallback_youtube_circuit_open_is_clean(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-6: CircuitOpenError from YouTube search -> no crash, no 2nd download, terminal.

        A tripped YouTube circuit breaker must not propagate as an unhandled
        exception. The fallback is silently skipped and the item fails
        terminally (same as search-returns-None).
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.api._contracts import CircuitOpenError
        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(
                orchestrator._finder._youtube_search,
                "search",
                side_effect=CircuitOpenError("youtube", 30.0),
            ),
        ):
            # Must NOT raise
            counts = orchestrator.run()

        assert download_mock.call_count == 1
        assert counts.get("ytdlp_error", 0) == 1

    def test_http_error_also_triggers_fallback(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-7: HTTP_ERROR also falls back to YouTube search.

        The fallback must activate on ALL non-SUCCESS statuses, not just
        YTDLP_ERROR. BOT_DETECTED is excluded: re-downloading immediately
        would reset bot_detected_consecutive_attempts incorrectly.
        Only HTTP_ERROR is covered here (YTDLP_ERROR covered by AC-1..AC-3).
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        alt_url = "https://youtube.com/watch?v=ALT_GOOD"

        http_fail = DownloadResult(status=DownloadStatus.HTTP_ERROR, output_path=None, error_message="403")
        success_result = DownloadResult(status=DownloadStatus.SUCCESS, output_path=MagicMock(), error_message=None)
        download_mock = MagicMock(side_effect=[http_fail, success_result])

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=alt_url),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        assert download_mock.call_count == 2
        assert download_mock.call_args_list[1].args[0] == alt_url
        assert counts.get("downloaded", 0) == 1
        assert counts.get("http_error", 0) == 0

        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.DOWNLOADED
        # Discriminating: the persisted URL is the fallback alt, not the dead TMDB URL.
        assert state_arg.youtube_url == alt_url

    def test_bot_detected_does_not_trigger_fallback(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-7 companion: BOT_DETECTED is EXCLUDED from the fallback.

        Re-downloading on BOT_DETECTED would reset bot_detected_consecutive_attempts
        incorrectly, so the fallback must NOT fire: the search is never called and
        there is exactly one download. Locks in the exclusion (orchestrator.py:503)
        against a mutation that drops BOT_DETECTED from the exclusion tuple.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        bot_result = DownloadResult(status=DownloadStatus.BOT_DETECTED, output_path=None, error_message="bot")
        download_mock = MagicMock(return_value=bot_result)
        search_mock = MagicMock(return_value="https://youtube.com/watch?v=ALT_GOOD")

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", search_mock),
        ):
            counts = orchestrator.run()

        search_mock.assert_not_called()
        assert download_mock.call_count == 1
        assert counts.get("bot_detected", 0) == 1


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
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

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

    These tests verify that the orchestrator calls _build_library_index
    at most once per run, honours per-media-type toggles, and correctly
    short-circuits items when a valid trailer is found on a storage disk.
    """

    def _make_lib_index(self, path: str, category: str, tmdb_id: str) -> dict:
        """Build a fake library index dict for mocking _build_library_index.

        Args:
            path: Filesystem path string for the library entry.
            category: Category ID string (e.g. ``"tv_shows"``).
            tmdb_id: TMDB ID string to use as the index key.

        Returns:
            Dict mapping ``(category, tmdb_id)`` to a :class:`_LibraryEntry`,
            matching the shape returned by the real ``_build_library_index``.
        """
        return {(category, tmdb_id): _LibraryEntry(path=path)}

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
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

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

        # Create the library directory with a valid trailer at the Plex
        # TV-show subfolder location (Trailers/<show>.mp4).
        lib_show_dir = tmp_path / "lib" / "Breaking Bad (2008)"
        (lib_show_dir / "Trailers").mkdir(parents=True)
        lib_trailer = lib_show_dir / "Trailers" / "Breaking Bad (2008).mp4"
        lib_trailer.write_bytes(b"x" * 200000)

        # Build fake library index: (category, tmdb_id) -> _LibraryEntry(path)
        fake_index = {("tv_shows", "1396"): _LibraryEntry(path=str(lib_show_dir))}

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item]),
            patch.object(orch._finder, "find") as mock_find,
            patch.object(orch._downloader, "download") as mock_dl,
            patch.object(orch, "_build_library_index", return_value=fake_index),
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
        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

        item = ScanItem(
            path=Path("/fake/Breaking Bad (2008)"),
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
        )

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
            patch.object(orch, "_build_library_index", return_value={}),
        ):
            counts = orch.run()

        # No library match -> falls through to staging check -> downloader reachable
        assert counts["downloaded"] == 1
        assert counts["already_present_on_disk"] == 0

    def test_run_raises_when_finder_unavailable(self, tmp_path: Path) -> None:
        """run() raises RuntimeError immediately when _finder is None (C10).

        When the finder could not be constructed (import failure / misconfig),
        run() must raise rather than silently persisting NO_TRAILER_AVAILABLE
        for every item it never actually inspected.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )
        # Force finder to None to simulate import/config failure.
        orch._finder = None

        with pytest.raises(RuntimeError, match="trailers finder unavailable"):
            orch.run()

    def test_finder_exception_persisted_as_http_error_not_skipped_by_filter(self, tmp_path: Path) -> None:
        """finder.find() exception persists HTTP_ERROR state, not SKIPPED_BY_FILTER (I5).

        A transient network or API error from the finder must be recorded with
        TrailerStatus.HTTP_ERROR so the item is retried with backoff — not
        SKIPPED_BY_FILTER which implies an intentional filter exclusion.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

        persisted_states: list[TrailerStatus] = []

        def capturing_set(key: str, state: object) -> None:
            from personalscraper.trailers.state import TrailerState

            assert isinstance(state, TrailerState)
            persisted_states.append(state.status)

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orch._finder, "find", side_effect=ConnectionError("network timeout")),
            patch.object(orch._state_store, "set", side_effect=capturing_set),
        ):
            counts = orch.run()

        assert counts["error"] == 1
        assert persisted_states == [TrailerStatus.HTTP_ERROR], (
            "finder exception must persist HTTP_ERROR, not SKIPPED_BY_FILTER"
        )

    def test_library_aware_recheck_disabled_for_both_types_skips_scan(self, tmp_path: Path) -> None:
        """When both library_check toggles are False, scan_library is never called.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = False
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

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
            patch.object(orch, "_build_library_index", return_value={}) as mock_build,
        ):
            orch.run()

        mock_build.assert_not_called()

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
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

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

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[movie_item, tv_item]),
            patch.object(orch._finder, "find", return_value=None),
            patch.object(orch, "_build_library_index", return_value={}) as mock_build,
        ):
            orch.run()

        # Called once for the TV item (lazy init). Not called for the movie.
        mock_build.assert_called_once()

    def test_library_aware_recheck_movies_opted_in(self, tmp_path: Path) -> None:
        """When library_check.movies=True, movie items also trigger the library check.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = True
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

        movie_item = ScanItem(
            path=Path("/fake/Fight Club (1999)"),
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[movie_item]),
            patch.object(orch._finder, "find", return_value=None),
            patch.object(orch, "_build_library_index", return_value={}) as mock_build,
        ):
            orch.run()

        # Library check triggered even for movie items when opted in
        mock_build.assert_called_once()

    def test_library_scan_called_only_once_per_run(self, tmp_path: Path) -> None:
        """scan_library is called at most once per run(), not once per TV item.

        With two TV show items and tv_shows=True, the index is built once on the
        first item, then reused for the second.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

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

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[tv_a, tv_b]),
            patch.object(orch._finder, "find", return_value=None),
            patch.object(orch, "_build_library_index", return_value={}) as mock_build,
        ):
            orch.run()

        # Only one library index build regardless of item count
        assert mock_build.call_count == 1


class TestTrailersOrchestratorEdgeCases:
    """Edge-case tests for uncovered orchestrator branches."""

    def test_run_bot_detected_increments_counter(self, orchestrator: "TrailersOrchestrator", tmp_path: "Path") -> None:
        """counts[bot_detected] is incremented when downloader returns BOT_DETECTED."""
        from unittest.mock import patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

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
        """counts[http_error] is incremented when downloader returns HTTP_ERROR.

        AC-8 (back-compat): HTTP_ERROR is a non-SUCCESS/non-BOT_DETECTED status, so
        it triggers the same-run fallback. _finder._youtube_search.search is patched
        to None so the test does not make a live YouTube call (no alt URL → one
        download → terminal HTTP_ERROR, the pre-0.35.0 behavior).
        """
        from unittest.mock import patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=None),
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
        """counts[ytdlp_error] is incremented when downloader returns an unhandled status.

        AC-8 (back-compat): _finder._youtube_search.search is patched to None so the
        test does not make a live call when the same-run fallback is active.
        """
        from unittest.mock import patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

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
            patch.object(orchestrator._finder._youtube_search, "search", return_value=None),
        ):
            counts = orchestrator.run()
        assert counts["ytdlp_error"] == 1


class TestTrailersOrchestratorNfoPropagation:
    """Verify ``write_trailer_url_to_nfo`` is called only on SUCCESS and only when nfo_path is set.

    Without these tests a regression that wrote the URL on every status — or
    forgot to call write at all — would silently ship.
    """

    @staticmethod
    def _scan_item_with_nfo(tmp_path: "Path") -> ScanItem:
        """Build a ScanItem whose ``nfo_path`` exists as an empty NFO."""
        nfo = tmp_path / "Fight Club (1999).nfo"
        nfo.write_text("<movie><title>Fight Club</title></movie>", encoding="utf-8")
        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        return ScanItem(
            path=media_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
            nfo_path=nfo,
        )

    def test_nfo_written_on_success(self, orchestrator: "TrailersOrchestrator", tmp_path: "Path") -> None:
        """A successful download propagates the trailer URL into <trailer>."""
        from unittest.mock import patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        item = self._scan_item_with_nfo(tmp_path)
        url = "https://youtube.com/watch?v=Z"
        out = item.path / "Fight Club (1999)-trailer.mp4"

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
            patch.object(orchestrator._finder, "find", return_value=url),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(status=DownloadStatus.SUCCESS, output_path=out),
            ),
        ):
            orchestrator.run()

        # The file must contain the URL we returned.
        assert "watch?v=Z" in item.nfo_path.read_text(encoding="utf-8")  # type: ignore[union-attr]

    def test_nfo_not_written_on_bot_detected(self, orchestrator: "TrailersOrchestrator", tmp_path: "Path") -> None:
        """BOT_DETECTED must NOT touch the NFO (no successful download yet)."""
        from unittest.mock import patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        item = self._scan_item_with_nfo(tmp_path)
        original_nfo = item.nfo_path.read_text(encoding="utf-8")  # type: ignore[union-attr]

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(status=DownloadStatus.BOT_DETECTED, error_message="not a bot"),
            ),
        ):
            orchestrator.run()

        assert item.nfo_path.read_text(encoding="utf-8") == original_nfo  # type: ignore[union-attr]

    def test_nfo_not_written_on_http_error(self, orchestrator: "TrailersOrchestrator", tmp_path: "Path") -> None:
        """HTTP_ERROR must NOT touch the NFO.

        _finder._youtube_search.search is patched to None: HTTP_ERROR triggers the
        same-run fallback, and stubbing the search keeps the test off the network
        (no alt URL → one download → terminal HTTP_ERROR, NFO untouched).
        """
        from unittest.mock import patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        item = self._scan_item_with_nfo(tmp_path)
        original_nfo = item.nfo_path.read_text(encoding="utf-8")  # type: ignore[union-attr]

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=None),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(status=DownloadStatus.HTTP_ERROR, error_message="403"),
            ),
        ):
            orchestrator.run()

        assert item.nfo_path.read_text(encoding="utf-8") == original_nfo  # type: ignore[union-attr]

    def test_nfo_not_written_when_nfo_path_is_none(
        self, orchestrator: "TrailersOrchestrator", tmp_path: "Path"
    ) -> None:
        """A SUCCESS with item.nfo_path=None must not call write_trailer_url_to_nfo."""
        from unittest.mock import patch

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus

        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
            nfo_path=None,
        )
        out = media_dir / "Fight Club (1999)-trailer.mp4"

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(status=DownloadStatus.SUCCESS, output_path=out),
            ),
            patch("personalscraper.trailers.orchestrator.write_trailer_url_to_nfo") as mock_write,
        ):
            orchestrator.run()

        mock_write.assert_not_called()


# ── Sub-phase 10.4 new tests ──────────────────────────────────────────────────


class TestCircuitOpenCounter:
    """I2 — counts['circuit_open'] increments when TMDB/YouTube circuit is open."""

    def test_circuit_open_counter_increments_when_tmdb_breaker_open(self, orchestrator: TrailersOrchestrator) -> None:
        """counts['circuit_open'] is incremented when TrailerFinder raises CircuitOpenError.

        When the TMDB or YouTube circuit breaker is open, the finder raises
        CircuitOpenError.  The orchestrator must tally these separately from
        generic errors so operators can distinguish outage events from bugs.

        Args:
            orchestrator: Orchestrator fixture.
        """
        from personalscraper.api._contracts import CircuitOpenError

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", side_effect=CircuitOpenError("youtube", 60.0)),
        ):
            counts = orchestrator.run()

        assert counts["circuit_open"] == 1
        # Generic error counter must NOT be incremented for a circuit-open event.
        assert counts["error"] == 0

    def test_circuit_open_propagates_from_tmdb_through_find_to_counter(self, tmp_path: Path) -> None:
        """Integration: TMDB breaker-open propagates through find() to orchestrator counter.

        This test exercises the full path fixed by cycle-5 PR review:
          1. Patch the underlying TMDBClient._fetch_videos_strict to raise
             CircuitOpenError (simulates the TMDB circuit breaker being OPEN).
          2. Construct a real TrailerFinder (not a mock) and wire it into a
             TrailersOrchestrator.
          3. Run the orchestrator with one scan item.
          4. Assert counts["circuit_open"] == 1 and counts["error"] == 0.

        Before the fix, find() swallowed CircuitOpenError in its TMDB-tier except
        block and fell through to YouTube, leaving circuit_open permanently at 0.
        After the fix, find() re-raises CircuitOpenError so the orchestrator's
        except-branch increments the counter correctly.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import MagicMock

        from personalscraper.api._contracts import CircuitOpenError
        from personalscraper.core.circuit import CircuitBreaker
        from personalscraper.scraper.json_ttl_cache import JsonTTLCache
        from personalscraper.trailers.discovery.trailer_finder import TrailerFinder
        from personalscraper.trailers.discovery.trailers_cache import TrailersCache
        from personalscraper.trailers.discovery.youtube_search import YoutubeSearch

        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

        # Build a real TrailerFinder with a mocked TMDB client that raises
        # CircuitOpenError on every get_videos call (the Protocol path for movies).
        tmdb_client = MagicMock()
        tmdb_client.get_videos.side_effect = CircuitOpenError("tmdb-videos", 9999.0)

        mock_provider_registry = MagicMock(spec=ProviderRegistry)
        mock_locked = MagicMock()
        mock_locked.provider = tmdb_client
        mock_locked.bound_id = "12345"
        mock_provider_registry.locked.return_value = mock_locked

        yt_breaker = CircuitBreaker(name="yt-integration", failure_threshold=5, event_bus=EventBus())
        yt_searcher = YoutubeSearch(
            "{title} {year} trailer",
            api_key="",
            quota_cache=JsonTTLCache(tmp_path / "quota_int.json"),
            breaker=yt_breaker,
        )
        cache = TrailersCache(tmp_path / "tc_int.json")
        real_finder = TrailerFinder(
            registry=mock_provider_registry,
            youtube_search=yt_searcher,
            cache=cache,
            languages=["en-US"],
        )

        # Replace the orchestrator's mocked finder with the real one.
        orch._finder = real_finder

        with patch.object(orch._scanner, "scan_staging", return_value=[_SCAN_ITEM]):
            counts = orch.run()

        # The CircuitOpenError must have propagated from find() to the orchestrator.
        assert counts["circuit_open"] == 1, (
            "CircuitOpenError from TMDB must reach the orchestrator's circuit_open counter"
        )
        assert counts["error"] == 0, "circuit_open events must not also increment the generic error counter"


# ── Sub-phase 10.5 new tests ──────────────────────────────────────────────────


class TestYtdlpRetryRoundTrip:
    """End-to-end retry contract: YTDLP_ERROR → cool-down skip → re-attempt.

    Finding 10.5/5 — pieces of the retry contract are unit-tested individually
    (compute_next_retry_at, should_skip, counter increments) but there was no
    integrated three-run scenario asserting the full life-cycle.
    """

    def test_ytdlp_failure_round_trip_persists_retry_then_skips_then_retries(
        self,
        tmp_path: Path,
    ) -> None:
        """Run 1 errors → Run 2 (in cool-down) skips → Run 3 (past cool-down) re-attempts.

        Uses a real TrailerStateStore backed by a temp file so persistence and
        should_skip are exercised together rather than mocked individually.

        Args:
            tmp_path: Pytest tmp_path fixture for isolated state file.
        """
        from datetime import datetime, timedelta, timezone

        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerState, TrailerStatus, make_state_key

        cfg = _make_config(tmp_path)
        # Single-day retry so the cool-down window is easy to reason about.
        cfg.trailers.retry_after_days = [1, 7, 30]

        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        scan_item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )

        # ── Run 1: downloader returns YTDLP_ERROR ────────────────────────────
        orch1 = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )
        fail_result = DownloadResult(
            status=DownloadStatus.YTDLP_ERROR,
            output_path=None,
            error_message="yt-dlp crashed",
        )

        with (
            patch.object(orch1._scanner, "scan_staging", return_value=[scan_item]),
            patch.object(orch1._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(orch1._downloader, "download", return_value=fail_result) as _mock_dl1,
            # Same-run YouTube fallback is on by default; patch it to a no-op so
            # this round-trip test asserts the one-download-per-run retry contract.
            patch.object(orch1._finder._youtube_search, "search", return_value=None),
        ):
            counts1 = orch1.run()

        assert counts1["ytdlp_error"] == 1
        # State must have been persisted with next_retry_at in the future.
        state_key = make_state_key("movie", {"tmdb": "550"})
        state_entry = orch1._state_store.get(state_key)
        assert state_entry is not None, "State entry not written after YTDLP_ERROR"
        assert state_entry.status == TrailerStatus.YTDLP_ERROR
        assert state_entry.attempts == 1
        assert state_entry.next_retry_at is not None

        UTC = timezone.utc
        next_retry_iso = (
            state_entry.next_retry_at
            if isinstance(state_entry.next_retry_at, str)
            else state_entry.next_retry_at.isoformat()
        )
        next_retry = datetime.fromisoformat(next_retry_iso).replace(tzinfo=UTC)
        assert next_retry > datetime.now(UTC), "next_retry_at should be in the future after Run 1"

        # ── Disk read: verify state was actually flushed to disk, not only held
        # in memory.  A regression that caches in a class-level dict would
        # silently satisfy the in-memory assertions above while this check fails.
        import json as _json  # noqa: PLC0415

        state_text = (tmp_path / ".data/trailers_state.json").read_text()
        state_disk = _json.loads(state_text)
        # The state file wraps entries under an "entries" key (versioned format).
        disk_entries = state_disk.get("entries", state_disk)
        assert state_key in disk_entries, "State key must be written to disk after Run 1"
        assert disk_entries[state_key].get("status") == "ytdlp_error", (
            "Disk-persisted status must be 'ytdlp_error' after Run 1"
        )

        # ── Run 2: within cool-down → should be skipped ──────────────────────
        orch2 = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )
        with (
            patch.object(orch2._scanner, "scan_staging", return_value=[scan_item]),
            patch.object(orch2._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(orch2._downloader, "download", return_value=fail_result) as mock_dl2,
            patch.object(orch2._finder._youtube_search, "search", return_value=None),
        ):
            counts2 = orch2.run()

        assert counts2["skipped_by_state"] == 1, "Run 2 (within cool-down) must skip the item"
        mock_dl2.assert_not_called()

        # ── Run 3: simulate cool-down elapsed by backdating next_retry_at ────
        # Overwrite the stored state entry so next_retry_at is in the past.
        past_retry = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        orch2._state_store.set(
            state_key,
            TrailerState(
                last_attempt=state_entry.last_attempt,
                attempts=1,
                status=TrailerStatus.YTDLP_ERROR,
                media_path=str(scan_item.path),
                next_retry_at=past_retry,
                youtube_url=state_entry.youtube_url,
            ),
        )

        orch3 = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )
        with (
            patch.object(orch3._scanner, "scan_staging", return_value=[scan_item]),
            patch.object(orch3._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(orch3._downloader, "download", return_value=fail_result) as mock_dl3,
            patch.object(orch3._finder._youtube_search, "search", return_value=None),
        ):
            counts3 = orch3.run()

        # The cool-down has elapsed — download must have been attempted again.
        mock_dl3.assert_called_once()
        assert counts3["ytdlp_error"] == 1, "Run 3 (past cool-down) must re-attempt download"


class TestPerItemLockContention:
    """Tests for per-item TrailerStateLocked handling in TrailersOrchestrator.run()."""

    def test_per_item_lock_contention_continues_loop(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """A TrailerStateLocked on one item's state.set() must not abort the loop.

        The orchestrator should log ``trailers_state_locked_for_item``, increment
        ``counts["error"]`` by 1 for the locked item, then continue to process the
        remaining items in the loop.

        Args:
            tmp_path: Pytest tmp_path fixture.
            caplog: Pytest log-capture fixture (stdlib bridge — structlog routes
                events through stdlib when ``wrap_for_formatter`` is active, so
                ``caplog`` is the reliable capture mechanism on CI).
        """
        from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStateLocked

        # Build two scan items: the first will trigger lock contention, the
        # second should be processed successfully.
        item_locked = ScanItem(
            path=tmp_path / "Locked Movie (2000)",
            media_type="movie",
            title="Locked Movie",
            year=2000,
            tmdb_id="111",
        )
        item_ok = ScanItem(
            path=tmp_path / "Normal Movie (2001)",
            media_type="movie",
            title="Normal Movie",
            year=2001,
            tmdb_id="222",
        )

        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(
            config=cfg,
            staging_dir=tmp_path,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )

        call_count = 0

        def _set_side_effect(key: str, state: object) -> None:
            """Raise TrailerStateLocked only on the first item's set() call."""
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TrailerStateLocked(tmp_path / "trailers_state.lock")

        success_result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            output_path=tmp_path / "Normal Movie (2001)-trailer.mp4",
        )

        def _find_side_effect(
            tmdb_id: int,
            media_type: str,
            *,
            title: str,
            year: int,
            season_number: int | None = None,
        ) -> str | None:
            """Return None for item_locked (triggers NO_TRAILER set), URL for item_ok."""
            return None if title == "Locked Movie" else "https://youtube.com/watch?v=Y"

        with caplog.at_level(logging.WARNING):
            with (
                patch.object(orch._scanner, "scan_staging", return_value=[item_locked, item_ok]),
                patch.object(orch._finder, "find", side_effect=_find_side_effect),
                patch.object(orch._downloader, "download", return_value=success_result),
                patch.object(orch._state_store, "set", side_effect=_set_side_effect),
                patch.object(orch._state_store, "auto_gc"),
            ):
                counts = orch.run()

        # The locked item: no_trailer incremented, set() raised → error incremented.
        # The second item: download succeeded → downloaded incremented, set() written OK.
        assert counts["error"] == 1, f"Expected error=1 for the locked item, got: {counts}"
        assert counts["downloaded"] == 1, f"Expected downloaded=1 for the normal item, got: {counts}"
        assert counts["no_trailer"] == 1, f"Expected no_trailer=1 for the locked item, got: {counts}"

        # The warning event must have been emitted for the locked item.
        # structlog routes events through stdlib (wrap_for_formatter + LoggerFactory),
        # so caplog.records is the authoritative capture; r.msg is a dict when the
        # record originates from a structlog call.
        def _is_lock_event(r: object) -> bool:
            msg = getattr(r, "msg", None)
            message = str(getattr(r, "message", ""))
            return (isinstance(msg, dict) and msg.get("event") == "trailers_state_locked_for_item") or (
                "trailers_state_locked_for_item" in message
            )

        lock_events = [r for r in caplog.records if _is_lock_event(r)]
        assert len(lock_events) == 1, (
            f"expected one trailers_state_locked_for_item event, got {len(lock_events)}. "
            f"Records: {[(r.levelno, getattr(r, 'msg', r.getMessage())) for r in caplog.records]}"
        )
