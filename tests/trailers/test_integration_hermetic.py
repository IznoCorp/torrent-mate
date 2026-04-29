"""Hermetic E2E integration tests for the trailers feature.

Exercises the full TrailersOrchestrator stack -- scan -> find -> download ->
placement -> state -- without any network calls or real media files.

All external edges are mocked:
  - TrailerFinder.find  -> returns a canned YouTube URL string
  - YtdlpDownloader.download  -> copies tests/trailers/fixtures/sample-trailer.mp4
    to the target output path, then returns DownloadResult(SUCCESS)
  - TrailersOrchestrator._build_library_index  -> returns a controlled index dict

These tests run by default (no ``@pytest.mark.network`` guard) and must finish
in < 5 seconds combined, satisfying the 30-second CI budget.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus
from personalscraper.trailers.orchestrator import TrailersOrchestrator, _LibraryEntry
from personalscraper.trailers.placement import trailer_exists, trailer_path_for, trailer_path_for_season
from personalscraper.trailers.scanner import ScanItem
from personalscraper.trailers.state import TrailerStatus

# Canonical path to the pre-built minimal mp4 fixture used as a fake download.
_SAMPLE_TRAILER = Path(__file__).parent / "fixtures" / "sample-trailer.mp4"

# Minimum size the orchestrator uses to validate a trailer (from default config).
_MIN_SIZE = 102_400  # 100 KiB -- matches TrailersConfig default

_FAKE_YT_URL = "https://www.youtube.com/watch?v=FAKEID_HERMETIC"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, *, seasons_enabled: bool = False) -> MagicMock:
    """Build a minimal mock Config for hermetic E2E tests.

    Args:
        tmp_path: Pytest tmp_path used for the state file directory.
        seasons_enabled: Whether to enable season-level trailer discovery.

    Returns:
        MagicMock configured with all fields that TrailersOrchestrator reads.
    """
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.languages = ["fr-FR", "en-US"]
    cfg.trailers.fallback_youtube_search = False
    cfg.trailers.search_query_format = "{title} {year} bande annonce"
    cfg.trailers.filters.min_file_size_bytes = _MIN_SIZE
    cfg.trailers.filters.max_filesize_mb = 500
    cfg.trailers.state_file = str(tmp_path / ".data" / "trailers_state.json")
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.ytdlp.format = "best[ext=mp4]/best"
    cfg.trailers.ytdlp.socket_timeout_sec = 30
    cfg.trailers.ytdlp.retries = 3
    cfg.trailers.seasons.enabled = seasons_enabled
    cfg.trailers.seasons.language_fallback = None
    cfg.trailers.seasons.search_query_format = "{title} {year} saison {season} bande annonce"
    cfg.trailers.library_check.movies = False
    cfg.trailers.library_check.tv_shows = True
    # Large budget so time-based tests do not flake.
    cfg.trailers.step.max_duration_sec = 1800
    return cfg


def _copy_fixture_on_download(url: str, output_path: Path) -> DownloadResult:  # noqa: ARG001
    """Side-effect for YtdlpDownloader.download -- copies sample fixture to output path.

    Simulates a successful yt-dlp download by copying the pre-built mp4 fixture
    to the target location. This makes trailer_exists() pass without any
    real network call or yt-dlp invocation.

    Args:
        url: YouTube URL (ignored -- same fixture regardless of URL).
        output_path: Destination path that the real downloader would write to.

    Returns:
        DownloadResult with status=SUCCESS and output_path set.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_SAMPLE_TRAILER, output_path)
    return DownloadResult(status=DownloadStatus.SUCCESS, output_path=output_path)


# ---------------------------------------------------------------------------
# Sub-phase 9.1a -- Hermetic E2E: movie trailer golden path
# ---------------------------------------------------------------------------


class TestHermeticMovieTrailer:
    """E2E golden path: movie trailer is discovered and placed correctly.

    Verifies:
    - Trailer file lands at {movie_dir}/{name}-trailer.mp4 (flat convention).
    - trailer_exists() returns True for the placed file.
    - State entry has status=DOWNLOADED, youtube_url matches the fake URL.
    """

    def test_movie_trailer_placed_at_flat_path(self, tmp_path: Path) -> None:
        """Trailer is placed next to the media file with the -trailer suffix.

        The mock finder returns a YouTube URL; the mock downloader copies the
        sample fixture to the expected flat path. Asserts file placement and
        state entry.
        """
        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()

        cfg = _make_config(tmp_path)
        # Disable library check so the test never hits library_scanner.
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = False
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        scan_item = ScanItem(
            path=movie_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )

        # Act: patch scanner + finder + downloader for a hermetic run.
        with (
            patch.object(orch._scanner, "scan_staging", return_value=[scan_item]),
            patch.object(orch._finder, "find", return_value=_FAKE_YT_URL),
            patch.object(orch._downloader, "download", side_effect=_copy_fixture_on_download),
        ):
            counts = orch.run()

        # Assert: trailer file placed at expected flat path.
        expected_trailer = trailer_path_for(movie_dir, "Fight Club (1999)", ext="mp4")
        assert expected_trailer.exists(), f"Trailer file not found at {expected_trailer}"
        assert trailer_exists(expected_trailer, min_size_bytes=_MIN_SIZE), (
            f"Trailer file present but too small: {expected_trailer.stat().st_size} bytes"
        )

        # Assert: counters.
        assert counts["downloaded"] == 1, f"Expected 1 downloaded, got {counts}"

        # Assert: state entry persisted with correct fields.
        state = orch._state_store.get("movie:tmdb:550")
        assert state is not None, "State entry not written"
        assert state.status == TrailerStatus.DOWNLOADED
        assert state.youtube_url == _FAKE_YT_URL

    def test_youtube_url_stored_in_state_for_nfo_propagation(self, tmp_path: Path) -> None:
        """Successful download propagates YouTube URL into NFO <trailer> tag.

        The state entry persists the YouTube URL; simultaneously the orchestrator
        calls write_trailer_url_to_nfo to populate the <trailer> element in the
        NFO file so that Plex / Kodi have a remote-trailer fallback.
        """
        movie_dir = tmp_path / "Inception (2010)"
        movie_dir.mkdir()

        # Create a minimal NFO file with an empty <trailer> tag.
        nfo_path = movie_dir / "Inception.nfo"
        nfo_path.write_bytes(b'<?xml version="1.0" encoding="utf-8"?><movie><trailer></trailer></movie>')

        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = False
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        scan_item = ScanItem(
            path=movie_dir,
            media_type="movie",
            title="Inception",
            year=2010,
            tmdb_id="27205",
            nfo_path=nfo_path,
        )

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[scan_item]),
            patch.object(orch._finder, "find", return_value=_FAKE_YT_URL),
            patch.object(orch._downloader, "download", side_effect=_copy_fixture_on_download),
        ):
            orch.run()

        # Assert: state entry carries youtube_url and trailer_path.
        state = orch._state_store.get("movie:tmdb:27205")
        assert state is not None, "State entry not written"
        assert state.youtube_url == _FAKE_YT_URL, (
            f"Expected youtube_url={_FAKE_YT_URL!r} in state, got {state.youtube_url!r}"
        )
        assert state.trailer_path is not None, "trailer_path not set in state"
        expected_trailer = trailer_path_for(movie_dir, "Inception (2010)", ext="mp4")
        assert state.trailer_path == str(expected_trailer)

        # Assert: NFO <trailer> tag was populated with the YouTube URL.
        tree = ET.parse(nfo_path)
        trailer_elem = tree.getroot().find("trailer")
        assert trailer_elem is not None, "<trailer> element missing from NFO"
        assert trailer_elem.text == _FAKE_YT_URL, (
            f"Expected <trailer>{_FAKE_YT_URL}</trailer> in NFO, got {trailer_elem.text!r}"
        )


# ---------------------------------------------------------------------------
# Sub-phase 9.1c -- Season trailer E2E fixture
# ---------------------------------------------------------------------------


class TestHermeticSeasonTrailer:
    """E2E: season-level ScanItem is processed and placed at the seasonal path.

    Fixture creates a TV show with a Saison 01/ subfolder and seasons_enabled=True.
    The TrailerFinder is stubbed to return a season trailer URL only for season-level
    queries. The yt-dlp downloader is patched to copy the sample fixture to the
    orchestrator-computed output path.

    Fixed orchestrator behaviour (Phase 9.2):
    - Season ScanItems use ``item.path = show_dir`` but are routed to
      ``trailer_path_for_season(show_dir, season_number, ext)`` — the correct
      per-season file inside ``Saison {SS:02d}/``.
    - The state KEY is correctly season-qualified: ``tv:tmdb:{id}:season:1``.
    - ``TrailerState.season_number`` is populated as 1 in the persisted entry.

    Assertions:
    - After downloading, ``trailer_exists()`` passes for the seasonal placement path.
    - State key ``tv:tmdb:1396:season:1`` has status=DOWNLOADED and season_number=1.
    - Show-level item (finder returns None) is counted as no_trailer.
    """

    def test_season_scan_item_downloads_and_state_is_season_qualified(self, tmp_path: Path) -> None:
        """Season ScanItem triggers a download placed at the seasonal path.

        The show-level ScanItem gets no URL (finder returns None -> no_trailer).
        The season ScanItem receives the URL; the downloader places the fixture at
        the per-season path: ``{show_dir}/Saison 01/Trailers/{show_dir.name} - Saison 01.mp4``
        (Plex TV-show season extras subfolder convention).

        State key is correctly qualified with ``:season:1``,
        ``TrailerState.season_number == 1``, and the state entry is DOWNLOADED.
        """
        # Arrange: create show directory with Saison 01/ subfolder.
        show_dir = tmp_path / "Breaking Bad (2008)"
        season_dir = show_dir / "Saison 01"
        season_dir.mkdir(parents=True)

        # Add a dummy episode so the scanner can detect the season.
        (season_dir / "Breaking Bad (2008) - S01E01.mkv").write_bytes(b"fake_episode")

        cfg = _make_config(tmp_path, seasons_enabled=True)
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = False
        orch = TrailersOrchestrator(config=cfg, staging_dir=tmp_path)

        # Show-level item -> finder returns None (no show-level trailer).
        show_item = ScanItem(
            path=show_dir,
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
            season_number=None,
        )
        # Season-level item -> finder returns the fake URL.
        season_item = ScanItem(
            path=show_dir,
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
            season_number=1,
        )

        def _find_side_effect(
            tmdb_id: int,  # noqa: ARG001
            media_type: str,  # noqa: ARG001
            *,
            title: str,  # noqa: ARG001
            year: int | None,  # noqa: ARG001
            season_number: int | None = None,
        ) -> str | None:
            """Return URL only for season-level queries."""
            return _FAKE_YT_URL if season_number == 1 else None

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[show_item, season_item]),
            patch.object(orch._finder, "find", side_effect=_find_side_effect),
            patch.object(orch._downloader, "download", side_effect=_copy_fixture_on_download),
        ):
            counts = orch.run()

        # Assert: counters -- 1 downloaded (season), 1 no_trailer (show-level).
        assert counts["downloaded"] == 1, f"Expected 1 downloaded, got {counts}"
        assert counts["no_trailer"] == 1, f"Expected 1 no_trailer (show-level), got {counts}"

        # Assert: trailer file placed at the seasonal path (fixed behaviour).
        # Season ScanItems use item.path = show_dir; the orchestrator routes them to
        # trailer_path_for_season(show_dir, 1) = Saison 01/{show_dir.name} - Saison 01-trailer.mp4.
        seasonal_trailer = trailer_path_for_season(show_dir, 1, "mp4")
        assert seasonal_trailer.exists(), f"Trailer not found at seasonal path: {seasonal_trailer}"
        assert trailer_exists(seasonal_trailer, min_size_bytes=_MIN_SIZE)

        # Assert: state entry for season item is keyed correctly by the composite key,
        # season_number is populated in the persisted TrailerState entry.
        season_state = orch._state_store.get("tv:tmdb:1396:season:1")
        assert season_state is not None, "State entry for season not written"
        assert season_state.status == TrailerStatus.DOWNLOADED
        assert season_state.season_number == 1, f"Expected season_number=1 in state, got {season_state.season_number!r}"


class TestHermeticLibraryAwareIdempotence:
    """E2E: orchestrator marks already_present_on_disk and skips network call.

    Fixture creates a fake library disk with an existing TV show + valid trailer
    file (size >= min_file_size_bytes). A new episode of the same show appears
    in staging. With library_check.tv_shows=True (default), the orchestrator
    must:
      - Mark the state entry with status=ALREADY_PRESENT_ON_DISK,
        trailer_path=<library path>.
      - NOT call TrailerFinder.find or YtdlpDownloader.download.
    """

    def test_library_aware_recheck_skips_when_trailer_already_on_disk(self, tmp_path: Path) -> None:
        """Orchestrator does not re-download when trailer exists on a storage disk.

        The library scan returns a LibraryScanItem for the same show with a valid
        trailer. The staging item has no trailer file yet. The orchestrator must
        short-circuit to already_present_on_disk without any network call.
        """
        # Arrange: staging item -- no trailer in staging dir.
        staging_show_dir = tmp_path / "staging" / "Breaking Bad (2008)"
        staging_show_dir.mkdir(parents=True)

        # Library item -- show + valid trailer already on disk. TV show trailers
        # live in a Trailers/ subfolder per Plex's TV Series agent, not flat.
        lib_show_dir = tmp_path / "library" / "Breaking Bad (2008)"
        lib_show_dir.mkdir(parents=True)
        (lib_show_dir / "Trailers").mkdir()
        lib_trailer = lib_show_dir / "Trailers" / "Breaking Bad (2008).mp4"
        shutil.copy2(_SAMPLE_TRAILER, lib_trailer)

        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.movies = False
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=staging_show_dir.parent)

        staging_item = ScanItem(
            path=staging_show_dir,
            media_type="tvshow",
            title="Breaking Bad",
            year=2008,
            tmdb_id="1396",
        )

        # Build a fake library index: (category, tmdb_id) -> _LibraryEntry(path)
        fake_index = {("tv_shows", "1396"): _LibraryEntry(path=str(lib_show_dir))}

        with (
            patch.object(orch._scanner, "scan_staging", return_value=[staging_item]),
            patch.object(orch._finder, "find") as mock_find,
            patch.object(orch._downloader, "download") as mock_download,
            patch.object(orch, "_build_library_index", return_value=fake_index),
        ):
            counts = orch.run()

        # Assert: short-circuited -- no network calls made.
        mock_find.assert_not_called()
        mock_download.assert_not_called()

        # Assert: counters.
        assert counts["already_present_on_disk"] == 1, f"Expected 1 already_present_on_disk, got {counts}"
        assert counts["downloaded"] == 0

        # Assert: state entry written with ALREADY_PRESENT_ON_DISK status and library path.
        state = orch._state_store.get("tv:tmdb:1396")
        assert state is not None, "State entry not written for library-aware recheck"
        assert state.status == TrailerStatus.ALREADY_PRESENT_ON_DISK
        assert state.trailer_path == str(lib_trailer)

    def test_new_show_without_library_match_proceeds_to_download(self, tmp_path: Path) -> None:
        """When no library match exists, the orchestrator falls through to download.

        Negative case: a truly new show has no entry in the library index.
        The orchestrator must reach the downloader and complete a successful download.
        """
        staging_show_dir = tmp_path / "staging" / "New Show (2025)"
        staging_show_dir.mkdir(parents=True)

        cfg = _make_config(tmp_path)
        cfg.trailers.library_check.tv_shows = True
        orch = TrailersOrchestrator(config=cfg, staging_dir=staging_show_dir.parent)

        staging_item = ScanItem(
            path=staging_show_dir,
            media_type="tvshow",
            title="New Show",
            year=2025,
            tmdb_id="99999",
        )

        # Library has no match for this show.
        with (
            patch.object(orch._scanner, "scan_staging", return_value=[staging_item]),
            patch.object(orch._finder, "find", return_value=_FAKE_YT_URL),
            patch.object(orch._downloader, "download", side_effect=_copy_fixture_on_download),
            patch.object(orch, "_build_library_index", return_value={}),
        ):
            counts = orch.run()

        # Falls through to download since no library match.
        assert counts["downloaded"] == 1, f"Expected download for new show, got {counts}"
        assert counts["already_present_on_disk"] == 0
