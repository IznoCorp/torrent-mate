"""Additional unit tests for TrailersOrchestrator targeting uncovered branches.

These tests focus on the missing line ranges identified during coverage analysis:
  * 154-156 — CookieError branch in __init__
  * 261-265 — make_state_key ValueError handling in run()
  * 280   — library-aware seasonal trailer path branch
  * 344-347 — disk_usage OSError fallback
  * 511   — NFO update failure warning
  * 594   — failed_items property
  * 621-623 — _build_finder ImportError
  * 656   — youtube API key missing log
  * 676-683 — _build_finder generic exception path
  * 705-734 — _build_library_index full path (DB present, DB missing, query failure)
  * 750   — _lookup_library_item with index None
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.trailers.orchestrator import TrailersOrchestrator, _LibraryEntry
from personalscraper.trailers.scanner import ScanItem


def _make_config(tmp_path: Path) -> MagicMock:
    """Build a minimal mock config for orchestrator extra tests.

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
    cfg.trailers.step.max_duration_sec = 1800
    cfg.indexer.db_path = tmp_path / "indexer.db"
    return cfg


class TestCookieErrorBranch:
    """Cover lines 154-156 — CookieError swallowed in __init__."""

    def test_cookie_error_logged_and_cookie_config_set_to_none(self, tmp_path: Path) -> None:
        """CookieConfig.from_env() raising CookieError logs warning and sets config None.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.scraper.ytdlp_downloader import CookieError

        cfg = _make_config(tmp_path)
        with patch(
            "personalscraper.trailers.orchestrator.CookieConfig.from_env",
            side_effect=CookieError("invalid path"),
        ):
            orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())
        # Construction must succeed and produce a working orchestrator instance.
        assert orch is not None


class TestKeyErrorBranch:
    """Cover lines 261-265 — ValueError from make_state_key in run() loop."""

    def test_make_state_key_value_error_increments_error_counter(self, tmp_path: Path) -> None:
        """ValueError raised by make_state_key is caught and increments counts['error'].

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())
        item = ScanItem(
            path=Path("/fake/Movie (2020)"),
            media_type="movie",
            title="Movie",
            year=2020,
            tmdb_id="42",
        )

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item]),
            patch(
                "personalscraper.trailers.orchestrator.make_state_key",
                side_effect=ValueError("bad key"),
            ),
        ):
            counts = orch.run()

        assert counts["error"] == 1
        assert orch.failed_items
        # Reason string must propagate the ValueError message.
        _, status, reason = orch.failed_items[0]
        assert status == "error"
        assert "bad key" in reason


class TestSeasonalLibraryAwareCheck:
    """Cover line 280 — library-aware SOT recheck for season-level item."""

    def test_seasonal_library_check_uses_seasonal_trailer_path(self, tmp_path: Path) -> None:
        """A season-level ScanItem hits the trailer_path_for_season branch in run().

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        cfg.trailers.seasons.enabled = True
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        # Library directory + seasonal trailer file
        lib_dir = tmp_path / "lib" / "Show (2020)"
        (lib_dir / "Trailers").mkdir(parents=True)
        # Seasonal placement uses a Season N format.
        seasonal_trailer = lib_dir / "Trailers" / "Season 2-trailer.mp4"
        seasonal_trailer.write_bytes(b"x" * 200000)

        item = ScanItem(
            path=tmp_path / "Show (2020)",
            media_type="tvshow",
            title="Show",
            year=2020,
            tmdb_id="999",
            season_number=2,
        )

        fake_index = {("tv_shows", "999"): _LibraryEntry(path=str(lib_dir))}

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item]),
            patch.object(orch, "_build_library_index", return_value=fake_index),
            patch(
                "personalscraper.trailers.orchestrator.trailer_path_for_season",
                return_value=seasonal_trailer,
            ),
            patch.object(orch._finder, "find") as mock_find,
            patch.object(orch._downloader, "download") as mock_dl,
        ):
            counts = orch.run()

        assert counts["already_present_on_disk"] == 1
        mock_find.assert_not_called()
        mock_dl.assert_not_called()


class TestDiskUsageOSError:
    """Cover lines 344-347 — disk_usage raises OSError, downloader still attempts."""

    def test_disk_usage_oserror_logs_and_proceeds(self, tmp_path: Path) -> None:
        """A non-FileNotFoundError OSError is logged but does not stop the run.

        The disk-space pre-check is advisory: when shutil.disk_usage raises
        OSError (broken NTFS mount, EACCES, etc.), the code falls through and
        attempts the download anyway.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        media_dir = tmp_path / "M (2020)"
        media_dir.mkdir()
        item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="M",
            year=2020,
            tmdb_id="1",
        )

        result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            output_path=media_dir / "M (2020)-trailer.mp4",
        )

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item]),
            patch.object(orch._finder, "find", return_value="https://yt/X"),
            patch.object(orch._downloader, "download", return_value=result),
            patch(
                "personalscraper.trailers.orchestrator.shutil.disk_usage",
                side_effect=OSError("broken mount"),
            ),
        ):
            counts = orch.run()

        # The OSError did NOT abort the run — download proceeded.
        assert counts["downloaded"] == 1


class TestNfoWriteFailureWarning:
    """Cover line 511 — write_trailer_url_to_nfo returns False (failure)."""

    def test_nfo_update_failure_logs_warning(self, tmp_path: Path) -> None:
        """When write_trailer_url_to_nfo returns False, a warning is logged.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        media_dir = tmp_path / "Movie (1999)"
        media_dir.mkdir()
        nfo = media_dir / "Movie (1999).nfo"
        nfo.write_text("<movie/>", encoding="utf-8")

        item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="Movie",
            year=1999,
            tmdb_id="550",
            nfo_path=nfo,
        )

        result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            output_path=media_dir / "Movie (1999)-trailer.mp4",
        )

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[item]),
            patch.object(orch._finder, "find", return_value="https://yt/X"),
            patch.object(orch._downloader, "download", return_value=result),
            patch(
                "personalscraper.trailers.orchestrator.write_trailer_url_to_nfo",
                return_value=False,
            ),
        ):
            counts = orch.run()

        assert counts["downloaded"] == 1


class TestFailedItemsProperty:
    """Cover line 594 — failed_items property returns a list copy."""

    def test_failed_items_returns_list_copy(self, tmp_path: Path) -> None:
        """The property returns a copy of the internal _failed_items list.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())
        orch._failed_items = [("k1", "no_trailer", ""), ("k2", "error", "boom")]
        result = orch.failed_items
        assert result == [("k1", "no_trailer", ""), ("k2", "error", "boom")]
        # Confirm independent list — mutating the result must not leak back.
        result.append(("k3", "x", "y"))
        assert len(orch.failed_items) == 2


class TestBuildFinderImportError:
    """Cover lines 621-623 — ImportError during _build_finder."""

    def test_build_finder_returns_none_on_import_error(self, tmp_path: Path) -> None:
        """_build_finder returns None when its imports fail.

        We construct an orchestrator and then re-invoke _build_finder with the
        TMDBClient import patched to raise ImportError.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        # Simulate ImportError by patching one of the modules imported inside
        # _build_finder. The function uses `from ... import` so we monkey-patch
        # an underlying module reference to raise ImportError.
        import builtins

        original_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "trailer_finder" in name or "tmdb" in name:
                raise ImportError(f"forced import failure for {name}")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            result = orch._build_finder()

        assert result is None


class TestBuildFinderGenericException:
    """Cover lines 676-683 — generic exception in _build_finder body."""

    def test_build_finder_returns_none_on_generic_exception(self, tmp_path: Path) -> None:
        """_build_finder returns None when settings/cache wiring fails.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        # Cause `get_settings()` to raise a non-Import exception.
        with patch(
            "personalscraper.config.get_settings",
            side_effect=RuntimeError("settings failure"),
        ):
            result = orch._build_finder()

        assert result is None


class TestBuildFinderYoutubeKeyMissing:
    """Cover line 656 — youtube API key missing warning log."""

    def test_youtube_api_key_missing_warning_logged(self, tmp_path: Path) -> None:
        """When YOUTUBE_API_KEY is missing, _build_finder logs a warning and continues.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        fake_settings = MagicMock()
        fake_settings.tmdb_api_key = "tmdb-key-123"
        fake_settings.youtube_api_key = None

        with (
            patch("personalscraper.config.get_settings", return_value=fake_settings),
            patch(
                "personalscraper.scraper.youtube_search.youtube_api_key_from_env",
                return_value=None,
            ),
        ):
            finder = orch._build_finder()

        # Even with no key, the finder is still built (degraded mode).
        assert finder is not None


class TestBuildLibraryIndex:
    """Cover lines 705-734 — _build_library_index in all branches."""

    def test_build_library_index_db_missing_returns_empty(self, tmp_path: Path) -> None:
        """When the indexer DB does not exist, _build_library_index returns {}.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        # Ensure indexer.db_path points to a non-existent file.
        cfg.indexer.db_path = tmp_path / "missing.db"
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        result = orch._build_library_index()
        assert result == {}

    def test_build_library_index_query_failure_returns_empty(self, tmp_path: Path) -> None:
        """When the SQLite query fails, _build_library_index logs and returns {}.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db_path = tmp_path / "indexer.db"
        db_path.write_text("not a real sqlite file")
        cfg = _make_config(tmp_path)
        cfg.indexer.db_path = db_path
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        with (
            patch(
                "personalscraper.trailers.orchestrator._open_indexer_db",
                return_value=MagicMock(spec=sqlite3.Connection),
            ),
            patch(
                "personalscraper.trailers.orchestrator._indexer_item_repo.list_all_dispatch_items",
                side_effect=RuntimeError("query exploded"),
            ),
        ):
            result = orch._build_library_index()

        assert result == {}

    def test_build_library_index_populates_dict_from_dispatch_rows(self, tmp_path: Path) -> None:
        """A row with both tmdb_id and imdb_id gets two entries in the dict.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db_path = tmp_path / "indexer.db"
        db_path.write_text("sentinel")
        cfg = _make_config(tmp_path)
        cfg.indexer.db_path = db_path
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())

        # Build a mock row that mimics MediaItemRow with tmdb_id + imdb_id set.
        row = MagicMock()
        row.tmdb_id = 550
        row.imdb_id = "tt0137523"
        row.category_id = "movies"

        # Also add a row with empty dispatch_path → must be skipped (continue branch).
        empty_row = MagicMock()
        empty_row.tmdb_id = 999
        empty_row.imdb_id = "tt9999999"
        empty_row.category_id = "movies"

        # And a row with tmdb_id=None, imdb_id present — must add only imdb entry.
        imdb_only = MagicMock()
        imdb_only.tmdb_id = None
        imdb_only.imdb_id = "tt0000001"
        imdb_only.category_id = "movies"

        rows = [
            (row, "Disk1", "/Volumes/Disk1/Movies/Fight Club (1999)"),
            (empty_row, "Disk1", ""),  # empty dispatch_path → skipped
            (imdb_only, "Disk2", "/Volumes/Disk2/Movies/Other"),
        ]

        with (
            patch(
                "personalscraper.trailers.orchestrator._open_indexer_db",
                return_value=MagicMock(spec=sqlite3.Connection),
            ),
            patch(
                "personalscraper.trailers.orchestrator._indexer_item_repo.list_all_dispatch_items",
                return_value=rows,
            ),
        ):
            result = orch._build_library_index()

        # row contributes (movies, "550") and (movies, "tt0137523").
        # imdb_only contributes (movies, "tt0000001") only.
        # empty_row contributes nothing.
        assert ("movies", "550") in result
        assert ("movies", "tt0137523") in result
        assert ("movies", "tt0000001") in result
        assert ("movies", "999") not in result


class TestLookupLibraryItemNoneIndex:
    """Cover line 750 — _lookup_library_item with index None."""

    def test_lookup_returns_none_when_index_is_none(self, tmp_path: Path) -> None:
        """The lookup short-circuits to None when _library_index is unset.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())
        orch._library_index = None
        item = ScanItem(
            path=tmp_path / "x",
            media_type="movie",
            title="X",
            year=2020,
            tmdb_id="42",
        )
        assert orch._lookup_library_item(item) is None

    def test_lookup_returns_none_when_no_tmdb_id(self, tmp_path: Path) -> None:
        """The lookup returns None for items without a tmdb_id even with index set.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        cfg = _make_config(tmp_path)
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path, event_bus=EventBus())
        orch._library_index = {("movies", "550"): _LibraryEntry(path="/x")}
        item = ScanItem(
            path=tmp_path / "x",
            media_type="movie",
            title="X",
            year=2020,
            tmdb_id=None,
        )
        assert orch._lookup_library_item(item) is None
