"""Tests for the main scraping orchestrator.

Tests movie scraping flow including folder name parsing, NFO skip logic,
match integration, and batch processing. Uses mocked API clients and
filesystem operations.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from guessit.api import GuessitException

from personalscraper.api._contracts import ApiError
from personalscraper.api.metadata._base import EpisodeInfo, SeasonDetails
from personalscraper.conf.models.scraper import ScraperConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.scraper import (
    Scraper,
    ScrapeResult,
    _find_video_file,
    _infer_year_from_child_names,
    _parse_folder_name,
    _rename_dir_case_safe,
    _tvdb_series_to_show_data,
)

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_transport() -> None:
    """Patch HttpTransport so Scraper init + TVDB bootstrap don't build real ones."""
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.post.return_value = {"data": {"token": "mock-jwt"}}
    mock_instance.get.return_value = {}

    with (
        patch("personalscraper.api.transport._http.HttpTransport", return_value=mock_instance),
        patch("personalscraper.api.metadata.tvdb.HttpTransport", return_value=mock_instance),
    ):
        yield


# ---------------------------------------------------------------------------
# Folder name parsing
# ---------------------------------------------------------------------------


class TestParseFolderName:
    """Tests for _parse_folder_name."""

    def test_standard_format(self) -> None:
        """Should parse 'Title (Year)' format."""
        title, year = _parse_folder_name("The Matrix (1999)")
        assert title == "The Matrix"
        assert year == 1999

    def test_french_title(self) -> None:
        """Should handle French titles with accents."""
        title, year = _parse_folder_name("La Quête d'Ewilan (2026)")
        assert title == "La Quête d'Ewilan"
        assert year == 2026

    def test_no_year(self) -> None:
        """Should return None year for titles without year."""
        title, year = _parse_folder_name("Some Movie")
        assert title == "Some Movie"
        assert year is None

    def test_year_in_title(self) -> None:
        """Should handle year at end in parentheses."""
        title, year = _parse_folder_name("2001 A Space Odyssey (1968)")
        assert title == "2001 A Space Odyssey"
        assert year == 1968


# ---------------------------------------------------------------------------
# Video file finding
# ---------------------------------------------------------------------------


class TestFindVideoFile:
    """Tests for _find_video_file."""

    def test_finds_mkv(self, tmp_path: Path) -> None:
        """Should find .mkv files."""
        (tmp_path / "movie.mkv").write_text("video")
        (tmp_path / "movie.nfo").write_text("nfo")
        result = _find_video_file(tmp_path)
        assert result is not None
        assert result.name == "movie.mkv"

    def test_no_video(self, tmp_path: Path) -> None:
        """Should return None if no video files."""
        (tmp_path / "readme.txt").write_text("text")
        result = _find_video_file(tmp_path)
        assert result is None

    def test_stat_oserror_falls_back_to_first_candidate(self, tmp_path: Path) -> None:
        """When stat() fails on one candidate, fall back to first candidate."""
        (tmp_path / "first.mkv").write_text("small")

        # Create a broken symlink — stat() on a dangling symlink may fail
        # differently depending on OS. On macOS, os.stat() on a dangling
        # symlink with follow_symlinks=True raises FileNotFoundError which
        # is a subclass of OSError.
        broken = tmp_path / "second.mkv"
        broken.symlink_to(tmp_path / "nonexistent_target")

        # max() uses stat().st_size via the key lambda. With
        # follow_symlinks=True (default for Path.stat()), the dangling
        # symlink triggers an OSError (FileNotFoundError), which the
        # try/except OSError in _find_video_file catches, falling back
        # to candidates[0].
        result = _find_video_file(tmp_path)

        assert result is not None
        assert result.name == "first.mkv"


class TestInferYearFromChildNames:
    """Tests for release child year inference."""

    def test_infers_year_from_matching_release_subdir(self, tmp_path: Path) -> None:
        """Should use a matching release subdirectory year."""
        show_dir = tmp_path / "Les secrets du Prince Andrew"
        release_dir = show_dir / "Les.secrets.du.Prince.Andrew.2023.S01.DOC.FRENCH.1080p.WEB.H264-BOUBA"
        release_dir.mkdir(parents=True)
        (release_dir / "Les.secrets.du.Prince.Andrew.S01E01.mkv").write_text("video")

        assert _infer_year_from_child_names(show_dir, "Les secrets du Prince Andrew") == 2023

    def test_ignores_unrelated_child_title(self, tmp_path: Path) -> None:
        """Should not infer a year from an unrelated child release."""
        show_dir = tmp_path / "Les secrets du Prince Andrew"
        release_dir = show_dir / "Different.Show.2023.S01.FRENCH.1080p.WEB"
        release_dir.mkdir(parents=True)
        (release_dir / "Different.Show.S01E01.mkv").write_text("video")

        assert _infer_year_from_child_names(show_dir, "Les secrets du Prince Andrew") is None


class TestScraperLanguage:
    """Tests for configured scraper metadata language."""

    def test_tvdb_series_uses_configured_translation(self) -> None:
        """TVDB show data should prefer the configured-language title."""
        show_data = _tvdb_series_to_show_data(
            {
                "name": "INVINCIBLE (2021)",
                "originalName": None,
                "translations": {"fra": "Invincible", "eng": "INVINCIBLE (2021)"},
                "year": "2021",
            },
            tvdb_id=368207,
            preferred_language="fr-FR",
        )

        assert show_data["name"] == "Invincible"
        assert show_data["original_name"] == "INVINCIBLE (2021)"

    def test_tvdb_series_fetches_configured_translation(self) -> None:
        """TVDB show data uses translations embedded in the extended response."""
        tvdb = MagicMock()
        tvdb.get_artwork_urls.return_value = []

        show_data = _tvdb_series_to_show_data(
            {
                "name": "INVINCIBLE (2021)",
                "year": "2021",
                "overview": "English overview",
                "translations": {"fr": "Invincible", "fra": "Invincible"},
            },
            tvdb_id=368207,
            tvdb_client=tvdb,
            preferred_language="fr-FR",
        )

        assert show_data["name"] == "Invincible"
        tvdb.get_artwork_urls.assert_called_once()

    def test_config_language_overrides_settings_for_tmdb_client(
        self,
        test_config,
    ) -> None:
        """Config scraper.language should be passed to TMDB."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        settings.artwork_language = "fr"
        settings.circuit_breaker_threshold = 5
        settings.circuit_breaker_cooldown = 300

        config = test_config.model_copy(
            update={
                "scraper": ScraperConfig(
                    language="en-US",
                    fallback_language="fr-FR",
                    prefer_local_title=False,
                ),
            }
        )

        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient") as tmdb_cls,
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            scraper = Scraper(settings, NamingPatterns(), config=config, event_bus=EventBus())

        assert scraper._scraper_language == "en-US"
        assert scraper._tvdb_language == "eng"
        tmdb_cls.assert_called_once()
        assert tmdb_cls.call_args.kwargs["language"] == "en-US"


class TestRenameDirCaseSafe:
    """Tests for case-only directory rename helper."""

    def test_same_path_uses_temp_rename(self, tmp_path: Path) -> None:
        """Same-file rename should preserve directory contents."""
        source = tmp_path / "INVINCIBLE (2021)"
        source.mkdir()
        (source / "tvshow.nfo").write_text("nfo")

        result = _rename_dir_case_safe(source, source)

        assert result == source
        assert (source / "tvshow.nfo").read_text() == "nfo"


# ---------------------------------------------------------------------------
# Video file finding — nested torrent structures (bug #6)
# ---------------------------------------------------------------------------


class TestFindVideoFileNested:
    """Tests for _find_video_file with nested torrent structures."""

    def test_finds_mkv_in_subdirectory(self, tmp_path: Path) -> None:
        """Video file in a release-group subdirectory should be found."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        release_dir = movie_dir / "Movie.2025.1080p.BluRay.x264-GROUP"
        release_dir.mkdir()
        video = release_dir / "Movie.2025.1080p.BluRay.x264-GROUP.mkv"
        video.write_bytes(b"\x00" * 1000)

        from personalscraper.scraper.scraper import _find_video_file

        result = _find_video_file(movie_dir)

        assert result is not None
        assert result == video

    def test_picks_largest_when_multiple_videos(self, tmp_path: Path) -> None:
        """When multiple video files exist, pick the largest (main feature)."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        sample = movie_dir / "Sample.mkv"
        sample.write_bytes(b"\x00" * 100)
        main = movie_dir / "sub" / "Movie.mkv"
        main.parent.mkdir()
        main.write_bytes(b"\x00" * 10000)

        from personalscraper.scraper.scraper import _find_video_file

        result = _find_video_file(movie_dir)

        assert result == main

    def test_finds_video_in_deeply_nested_dir(self, tmp_path: Path) -> None:
        """Video in a 2-level deep structure should still be found."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        deep = movie_dir / "Release" / "Subs"
        deep.mkdir(parents=True)
        video = movie_dir / "Release" / "Movie.mkv"
        video.write_bytes(b"\x00" * 1000)

        from personalscraper.scraper.scraper import _find_video_file

        result = _find_video_file(movie_dir)

        assert result == video

    def test_skips_trailers_subfolder(self, tmp_path: Path) -> None:
        """Plex Trailers/ subfolder must be ignored — its .mp4 is a trailer, not the main video."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        main = movie_dir / "Movie.mkv"
        main.write_bytes(b"\x00" * 10000)
        trailers = movie_dir / "Trailers"
        trailers.mkdir()
        # Trailer is larger to prove that size alone wouldn't disambiguate
        (trailers / "Movie (2025).mp4").write_bytes(b"\x00" * 100000)

        from personalscraper.scraper.scraper import _find_video_file

        result = _find_video_file(movie_dir)

        assert result == main, "trailer file in Trailers/ must not be picked as main video"


# ---------------------------------------------------------------------------
# Empty release-group dir cleanup (bug #7, #8)
# ---------------------------------------------------------------------------


class TestCleanupEmptyReleaseDirs:
    """Tests for empty release-group directory cleanup after episode rename."""

    def test_empty_release_dirs_removed(self, tmp_path: Path) -> None:
        """Empty release-group subdirectories should be removed after rename."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()

        # Simulate post-rename state: episodes moved to Saison 01/,
        # but empty release-group dirs remain
        (show_dir / "Saison 01").mkdir()
        (show_dir / "Saison 01" / "S01E01 - Title.mkv").write_bytes(b"ep1")

        # Empty release-group dirs (should be removed)
        (show_dir / "Show.S01E01.1080p.WEB-GROUP").mkdir()
        (show_dir / "Show.S01E02.1080p.WEB-GROUP").mkdir()

        # Non-empty dir (should NOT be removed)
        leftover = show_dir / "Show.S01E03.1080p.WEB-GROUP"
        leftover.mkdir()
        (leftover / "S01E03.mkv").write_bytes(b"ep3")

        # .actors dir (should NOT be removed even if empty)
        (show_dir / ".actors").mkdir()

        from personalscraper.scraper.scraper import _cleanup_empty_release_dirs

        removed = _cleanup_empty_release_dirs(show_dir)

        assert removed == 2
        assert not (show_dir / "Show.S01E01.1080p.WEB-GROUP").exists()
        assert not (show_dir / "Show.S01E02.1080p.WEB-GROUP").exists()
        assert (show_dir / "Show.S01E03.1080p.WEB-GROUP").exists()  # Non-empty
        assert (show_dir / ".actors").exists()  # Hidden dir preserved
        assert (show_dir / "Saison 01").exists()  # Season dir preserved


# ---------------------------------------------------------------------------
# Movie scraping orchestration
# ---------------------------------------------------------------------------


class TestScrapeMovie:
    """Tests for Scraper.scrape_movie."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_skip_if_nfo_exists(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should skip movie if valid .nfo already exists."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        # Valid NFO must have <uniqueid> to pass _is_nfo_complete
        (movie_dir / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')

        result = scraper.scrape_movie(movie_dir)
        assert result.action == "skipped_already_done"

    def test_skip_low_confidence(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should skip if no confident match found."""
        movie_dir = tmp_path / "Unknown Movie (2024)"
        movie_dir.mkdir()

        with patch("personalscraper.scraper.scraper.match_movie", return_value=None):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "skipped_low_confidence"

    def test_full_scrape_flow(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should complete full scrape: match → details → NFO → artwork."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.mkv").write_text("video")

        match = MatchResult(
            api_id=603,
            api_title="The Matrix",
            api_year=1999,
            confidence=0.95,
            source="tmdb",
        )
        movie_data = {
            "id": 603,
            "title": "The Matrix",
            "overview": "A computer hacker...",
            "vote_average": 8.2,
            "vote_count": 20000,
            "genres": [{"name": "Action"}],
            "release_date": "1999-03-31",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0133093"},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        assert result.match == match
        assert result.nfo_written is True
        # Verify NFO was written
        assert (movie_dir / "The Matrix.nfo").exists()

    def test_error_on_match_failure(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should return error result on match exception."""
        movie_dir = tmp_path / "Bad Movie (2024)"
        movie_dir.mkdir()

        with patch(
            "personalscraper.scraper.scraper.match_movie",
            side_effect=ConnectionError("API down"),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "error"
        assert "API down" in (result.error or "")


# ---------------------------------------------------------------------------
# Batch movie processing
# ---------------------------------------------------------------------------


class TestProcessMovies:
    """Tests for Scraper.process_movies."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked clients."""
        with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_processes_all_subdirs(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should call scrape_movie for each subdirectory."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "Movie A (2024)").mkdir()
        (movies_dir / "Movie B (2024)").mkdir()
        # Hidden directories should be skipped
        (movies_dir / ".hidden").mkdir()

        with patch.object(scraper, "scrape_movie") as mock_scrape:
            mock_scrape.return_value = ScrapeResult(
                media_path=Path("."),
                media_type="movie",
                action="scraped",
            )
            results = scraper.process_movies(movies_dir)

        assert len(results) == 2
        assert mock_scrape.call_count == 2

    def test_nonexistent_dir(self, scraper: Scraper, tmp_path: Path) -> None:
        """Should return empty list for nonexistent directory."""
        results = scraper.process_movies(tmp_path / "nonexistent")
        assert results == []

    def test_handles_scrape_error(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should catch exceptions and add error results."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "Bad Movie (2024)").mkdir()

        with patch.object(
            scraper,
            "scrape_movie",
            side_effect=RuntimeError("unexpected"),
        ):
            results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"


# ---------------------------------------------------------------------------
# TV show scraping orchestration
# ---------------------------------------------------------------------------


class TestScrapeTvshow:
    """Tests for Scraper.scrape_tvshow."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_skip_if_tvshow_nfo_exists(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should skip show when the previous scrape is coherent.

        The fast path requires more than a parseable NFO with a uniqueid:
        ``_verify_existing_scrape`` also enforces canonical folder name,
        NFO title/year, show-level artwork, episode naming, and sibling
        episode NFOs. Any drift re-triggers a full scrape.
        """
        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text(
            '<tvshow><title>Fallout</title><year>2024</year><uniqueid type="tvdb">123</uniqueid></tvshow>'
        )
        (show_dir / "poster.jpg").write_bytes(b"\xff")
        (show_dir / "landscape.jpg").write_bytes(b"\xff")
        season_dir = show_dir / "Saison 01"
        season_dir.mkdir()
        (season_dir / "S01E01 - The Beginning.mkv").write_bytes(b"\x00")
        # Phase 4 drift hardening requires the canonical uniqueid on
        # the sibling episode NFO — tvshow.nfo above declares tvdb.
        (season_dir / "S01E01 - The Beginning.nfo").write_text(
            '<episodedetails><title>The Beginning</title><uniqueid type="tvdb">9001</uniqueid></episodedetails>'
        )

        result = scraper.scrape_tvshow(show_dir)
        assert result.action == "skipped_already_done"

    def test_recovers_missing_season_poster_on_valid_tvshow(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should recover season posters during the valid-NFO fast path."""
        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text(
            ('<tvshow><title>Fallout</title><year>2024</year><uniqueid type="tmdb">106379</uniqueid></tvshow>')
        )
        (show_dir / "poster.jpg").write_bytes(b"\xff")
        (show_dir / "landscape.jpg").write_bytes(b"\xff")
        season_dir = show_dir / "Saison 01"
        season_dir.mkdir()
        (season_dir / "S01E01 - The Beginning.mkv").write_bytes(b"\x00")
        # Show's tvshow.nfo is tmdb-canonical → episode NFO carries tmdb.
        (season_dir / "S01E01 - The Beginning.nfo").write_text(
            '<episodedetails><title>The Beginning</title><uniqueid type="tmdb">5005</uniqueid></episodedetails>'
        )

        show_data = {
            "id": 106379,
            "name": "Fallout",
            "images": {"posters": [], "backdrops": []},
            "seasons": [{"season_number": 1, "poster_path": "/season01.jpg"}],
        }
        season_poster = show_dir / "season01-poster.jpg"

        def fake_download_tvshow_artwork(*args: object, **kwargs: object) -> list[Path]:
            season_poster.write_bytes(b"\xff")
            return [season_poster]

        with (
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(scraper._artwork, "download_tvshow_artwork", side_effect=fake_download_tvshow_artwork),
        ):
            result = scraper.scrape_tvshow(show_dir)

        assert result.action == "artwork_recovered"
        assert result.artwork_downloaded == ["season01-poster.jpg"]
        assert season_poster.exists()

    def _build_coherent_show_dir(
        self,
        tmp_path: Path,
        folder_name: str = "Fallout (2024)",
        nfo_title: str = "Fallout",
        nfo_year: str = "2024",
        with_poster: bool = True,
        with_landscape: bool = True,
        episode_name: str = "S01E01 - The Beginning",
        with_episode_nfo: bool = True,
    ) -> Path:
        """Build a minimal TV show dir that passes _verify_existing_scrape."""
        show_dir = tmp_path / folder_name
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text(
            f'<tvshow><title>{nfo_title}</title><year>{nfo_year}</year><uniqueid type="tvdb">123</uniqueid></tvshow>'
        )
        if with_poster:
            (show_dir / "poster.jpg").write_bytes(b"\xff")
        if with_landscape:
            (show_dir / "landscape.jpg").write_bytes(b"\xff")
        season_dir = show_dir / "Saison 01"
        season_dir.mkdir()
        (season_dir / f"{episode_name}.mkv").write_bytes(b"\x00")
        if with_episode_nfo:
            # _build_coherent_show_dir constructs a tvshow.nfo with a
            # canonical tvdb uniqueid (above), so the episode NFO must
            # also expose a tvdb uniqueid to clear the phase-4 drift
            # check.
            (season_dir / f"{episode_name}.nfo").write_text(
                '<episodedetails><title>The Beginning</title><uniqueid type="tvdb">9001</uniqueid></episodedetails>'
            )
        return show_dir

    def test_verify_existing_scrape_passes_on_coherent_dir(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Coherent show dir returns (True, "ok")."""
        show_dir = self._build_coherent_show_dir(tmp_path)
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert is_valid
        assert reason == "ok"

    def test_verify_rejects_folder_name_drift(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Folder name not equal to sanitize(title (year)) → drift detected."""
        show_dir = self._build_coherent_show_dir(
            tmp_path,
            folder_name="Fallout (FR) (2024)",  # non-canonical
        )
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert not is_valid
        assert reason.startswith("folder_name_drift")

    def test_verify_rejects_nfo_title_with_duplicate_year(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """NFO title must not carry the year when <year> is separate."""
        show_dir = self._build_coherent_show_dir(
            tmp_path,
            folder_name="INVINCIBLE (2021)",
            nfo_title="INVINCIBLE (2021)",
            nfo_year="2021",
        )

        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")

        assert not is_valid
        assert reason == "nfo_title_contains_year"

    def test_verify_tolerates_nfc_nfd_equivalence(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Folder names differing only in NFC/NFD codepoints are NOT drift.

        macOS APFS/HFS+ stores filenames in NFD ("è" → "e" + U+0300), while
        Python strings built from scraper output are typically NFC ("è" as
        U+00E8). A naive byte-level compare treats them as different; the
        drift check must normalize both sides to NFC to avoid a phantom
        rename-into-self that would empty the folder.
        """
        import unicodedata as _ud

        nfc_title = "Top Chef Le Concours Parallèle"  # NFC form in the NFO
        nfd_folder = _ud.normalize("NFD", f"{nfc_title} (2026)")  # NFD on disk
        show_dir = self._build_coherent_show_dir(
            tmp_path,
            folder_name=nfd_folder,
            nfo_title=nfc_title,
            nfo_year="2026",
        )
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert is_valid, f"NFC/NFD mismatch wrongly treated as drift: {reason}"

    def test_verify_rejects_title_less_legacy_episode(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Legacy "SxxExx.ext" fallback is detected as drift.

        The previous fallback form (before the synthetic-title fallback) left
        episodes named "S17E08.mkv". The verify now requires every episode
        file to include a title segment so those legacy files get re-scraped.
        """
        show_dir = self._build_coherent_show_dir(
            tmp_path,
            episode_name="S01E01",  # no title segment
            with_episode_nfo=False,
        )
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert not is_valid
        assert reason.startswith("episode_naming_drift")

    def test_verify_rejects_missing_episode_nfo(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Episode video without a sibling NFO → drift."""
        show_dir = self._build_coherent_show_dir(tmp_path, with_episode_nfo=False)
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert not is_valid
        assert reason.startswith("episode_nfo_missing")

    def test_verify_accepts_synthetic_fallback_episode_without_nfo(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Synthetic-fallback episode names (``SxxExx - Episode N``) without NFO are not drift.

        When the scraper finds no TMDB record for an episode it falls back to
        ``S01E08 - Episode 8.mkv`` and intentionally writes no sibling NFO
        (refuses to fabricate metadata). Without this carve-out the verify
        step would flag it as drift on every dry-run, triggering an endless
        rescrape loop. Regression test for the fix in 372d522.
        """
        show_dir = self._build_coherent_show_dir(
            tmp_path,
            episode_name="S01E09 - Episode 9",
            with_episode_nfo=False,
        )
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert is_valid, f"synthetic fallback should pass, got reason={reason!r}"
        assert reason == "ok"

        # Zero-padded variant ("Episode 09") must also be accepted.
        padded_root = tmp_path / "padded"
        padded_root.mkdir()
        show_dir2 = self._build_coherent_show_dir(
            padded_root,
            episode_name="S01E09 - Episode 09",
            with_episode_nfo=False,
        )
        is_valid2, reason2 = scraper._verify_existing_scrape(show_dir2, show_dir2 / "tvshow.nfo")
        assert is_valid2, f"zero-padded synthetic fallback should pass, got reason={reason2!r}"

    def test_verify_rejects_missing_poster(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Missing poster.jpg → drift (dispatch needs artwork)."""
        show_dir = self._build_coherent_show_dir(tmp_path, with_poster=False)
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert not is_valid
        assert reason == "poster_missing"

    def test_verify_rejects_missing_landscape(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Missing landscape.jpg → drift."""
        show_dir = self._build_coherent_show_dir(tmp_path, with_landscape=False)
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert not is_valid
        assert reason == "landscape_missing"

    def test_verify_rejects_nfo_without_title(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """NFO missing <title> → drift."""
        show_dir = self._build_coherent_show_dir(tmp_path, nfo_title="")
        is_valid, reason = scraper._verify_existing_scrape(show_dir, show_dir / "tvshow.nfo")
        assert not is_valid
        assert reason == "nfo_missing_title"

    def test_skip_low_confidence(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should skip if no confident match found."""
        show_dir = tmp_path / "Unknown Show (2024)"
        show_dir.mkdir()

        with patch("personalscraper.scraper.scraper.match_tvshow", return_value=None):
            result = scraper.scrape_tvshow(show_dir)

        assert result.action == "skipped_low_confidence"

    def test_full_scrape_flow(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should complete full scrape: match → details → NFO → artwork."""
        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        match = MatchResult(
            api_id=106379,
            api_title="Fallout",
            api_year=2024,
            confidence=0.95,
            source="tmdb",
        )
        show_data = {
            "id": 106379,
            "name": "Fallout",
            "original_name": "Fallout",
            "overview": "Test",
            "vote_average": 8.1,
            "vote_count": 2000,
            "genres": [],
            "first_air_date": "2024-04-10",
            "status": "Returning Series",
            "networks": [{"name": "Prime Video"}],
            "origin_country": ["US"],
            "number_of_episodes": 8,
            "number_of_seasons": 1,
            "external_ids": {"imdb_id": "tt12637874", "tvdb_id": 416744},
            "aggregate_credits": {"cast": []},
            "images": {"posters": [], "backdrops": []},
            "content_ratings": {"results": []},
            "seasons": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_tvshow", return_value=match),
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(scraper._artwork, "download_tvshow_artwork", return_value=[]),
        ):
            result = scraper.scrape_tvshow(show_dir)

        assert result.action == "scraped"
        assert result.match == match
        assert result.nfo_written is True
        assert (show_dir / "tvshow.nfo").exists()

    def test_tvdb_only_show_scraped_when_no_tmdb_crossref(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """TVDB-matched show with no TMDB cross-ref should be scraped, not aborted.

        Reproduces Bug 3: "Top Chef France" matches on TVDB with high confidence
        but has no TMDB equivalent. Current code sets error="No TMDB ID available"
        and returns. Fix: continue with TVDB-only data (rename, NFO, artwork).
        """
        show_dir = tmp_path / "Top Chef France (2010)"
        show_dir.mkdir()

        match = MatchResult(
            api_id=99999,
            api_title="Top Chef France",
            api_year=2010,
            confidence=0.98,
            source="tvdb",
        )
        tvdb_series_data = {
            "id": 99999,
            "name": "Top Chef France",
            "originalName": "Top Chef France",
            "overview": "French cooking competition.",
            "status": {"name": "Continuing"},
            "genres": [{"name": "Reality"}],
            "seasons": [],
            "contentRatings": [],
            "remoteIds": [],  # No TMDB cross-ref
        }

        with (
            patch("personalscraper.scraper.scraper.match_tvshow", return_value=match),
            patch.object(scraper._tvdb, "get_series", return_value=tvdb_series_data),
            patch.object(scraper._tvdb, "get_remote_ids", return_value={}),  # No tmdb_id
            patch.object(scraper._artwork, "download_tvshow_artwork", return_value=[]),
        ):
            result = scraper.scrape_tvshow(show_dir)

        # Must NOT abort — should complete the scrape with TVDB data
        assert result.action == "scraped", f"Expected scraped, got {result.action} ({result.error})"
        assert result.error is None
        assert result.nfo_written is True
        assert (show_dir / "tvshow.nfo").exists()

    def test_tvdb_only_show_scraped_when_tmdb_404(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """TVDB-matched show that 404s on TMDB should be scraped, not aborted.

        Reproduces Bug 3 variant: tmdb_id is found in remoteIds, but TMDB
        returns 404 (show deleted / mismatched). Fix: fall back to TVDB-only data.
        """
        show_dir = tmp_path / "Top Chef France (2010)"
        show_dir.mkdir()

        match = MatchResult(
            api_id=99999,
            api_title="Top Chef France",
            api_year=2010,
            confidence=0.98,
            source="tvdb",
        )
        tvdb_series_data = {
            "id": 99999,
            "name": "Top Chef France",
            "originalName": "Top Chef France",
            "overview": "French cooking competition.",
            "status": {"name": "Continuing"},
            "genres": [{"name": "Reality"}],
            "seasons": [],
            "contentRatings": [],
            "remoteIds": [{"sourceName": "TheMovieDB.com", "id": "777"}],
        }

        with (
            patch("personalscraper.scraper.scraper.match_tvshow", return_value=match),
            patch.object(scraper._tvdb, "get_series", return_value=tvdb_series_data),
            patch.object(scraper._tvdb, "get_remote_ids", return_value={"tmdb_id": "777"}),
            patch.object(
                scraper._tmdb,
                "get_tv",
                side_effect=ApiError("tmdb", 404, provider_code=34, message="Resource not found"),
            ),
            patch.object(scraper._artwork, "download_tvshow_artwork", return_value=[]),
        ):
            result = scraper.scrape_tvshow(show_dir)

        # Must NOT abort — fall back to TVDB-only data
        assert result.action == "scraped", f"Expected scraped, got {result.action} ({result.error})"
        assert result.error is None
        assert result.nfo_written is True


# ---------------------------------------------------------------------------
# Batch TV show processing
# ---------------------------------------------------------------------------


class TestProcessTvshows:
    """Tests for Scraper.process_tvshows."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked clients."""
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_processes_all_subdirs(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Should call scrape_tvshow for each subdirectory."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        (tvshows_dir / "Show A (2024)").mkdir()
        (tvshows_dir / "Show B (2025)").mkdir()
        (tvshows_dir / ".hidden").mkdir()

        with patch.object(scraper, "scrape_tvshow") as mock_scrape:
            mock_scrape.return_value = ScrapeResult(
                media_path=Path("."),
                media_type="tvshow",
                action="scraped",
            )
            results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 2
        assert mock_scrape.call_count == 2

    def test_nonexistent_dir(self, scraper: Scraper, tmp_path: Path) -> None:
        """Should return empty list for nonexistent directory."""
        results = scraper.process_tvshows(tmp_path / "nonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# Additional scraper orchestration tests (V7.x)
# ---------------------------------------------------------------------------


class TestScrapeMovieExtra:
    """Additional tests for movie scraping edge cases."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_process_movie_api_failure(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """API failure should return error result, pipeline continues."""
        movie_dir = tmp_path / "ApiDown (2024)"
        movie_dir.mkdir()

        with patch(
            "personalscraper.scraper.scraper.match_movie",
            side_effect=ConnectionError("TMDB unreachable"),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "error"
        assert "TMDB unreachable" in (result.error or "")

    def test_process_movie_low_confidence_returns_match(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Low confidence match should return MatchResult with low score."""
        movie_dir = tmp_path / "Ambiguous (2024)"
        movie_dir.mkdir()

        low_match = MatchResult(
            api_id=1,
            api_title="Something Else",
            api_year=2024,
            confidence=0.3,
            source="tmdb",
        )
        with patch("personalscraper.scraper.scraper.match_movie", return_value=low_match):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "skipped_low_confidence"

    def test_scraper_already_scraped_skip(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Valid NFO exists should skip (tested via scrape_movie, not process)."""
        movie_dir = tmp_path / "Already (2024)"
        movie_dir.mkdir()
        (movie_dir / "Already.nfo").write_text('<movie><uniqueid type="tmdb">999</uniqueid></movie>')

        result = scraper.scrape_movie(movie_dir)
        assert result.action == "skipped_already_done"


class TestScrapeTvshowExtra:
    """Additional tests for TV show scraping edge cases."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_process_tvshow_api_failure(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """API failure for TV show should return error result."""
        show_dir = tmp_path / "ApiDown (2024)"
        show_dir.mkdir()

        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            side_effect=ConnectionError("TVDB unreachable"),
        ):
            result = scraper.scrape_tvshow(show_dir)

        assert result.action == "error"
        assert "TVDB unreachable" in (result.error or "")

    def test_process_tvshows_handles_error(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Exception in scrape_tvshow should produce error result in batch."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        (tvshows_dir / "Crash Show (2024)").mkdir()

        with patch.object(
            scraper,
            "scrape_tvshow",
            side_effect=RuntimeError("unexpected"),
        ):
            results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action == "error"


# ---------------------------------------------------------------------------
# Circuit breaker fallback
# ---------------------------------------------------------------------------


class TestCircuitBreakerFallback:
    """Test inter-provider fallback when circuit breakers are OPEN."""

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with real CircuitBreaker instances."""
        from personalscraper.core.circuit import CircuitBreaker

        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        # Replace mock circuits with real ones for testing.
        # ``circuit`` is a read-only property on the real clients; the
        # MagicMock replacement still accepts assignment. Type ignores
        # acknowledge the mock-vs-real shape divergence.
        s._tmdb.circuit = CircuitBreaker(name="TMDB", event_bus=EventBus())  # type: ignore[misc]
        s._tvdb.circuit = CircuitBreaker(name="TVDB", event_bus=EventBus())  # type: ignore[misc]
        return s

    def test_process_movies_skips_when_tmdb_circuit_open(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """Movies are skipped when TMDB circuit is OPEN."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "Movie A (2024)").mkdir()
        (movies_dir / "Movie B (2024)").mkdir()

        # Force TMDB circuit OPEN
        error = ApiError("test", 500, provider_code=0, message="Internal Server Error")
        for _ in range(5):
            scraper._tmdb.circuit.record_failure(error)

        results = scraper.process_movies(movies_dir)

        assert len(results) == 2
        assert all(r.action == "error" for r in results)
        assert all("circuit breaker OPEN" in (r.error or "") for r in results)

    def test_process_movies_catches_circuit_open_during_scrape(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """CircuitOpenError during scrape_movie is caught gracefully."""
        from personalscraper.api._contracts import CircuitOpenError

        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "Movie A (2024)").mkdir()

        with patch.object(
            scraper,
            "scrape_movie",
            side_effect=CircuitOpenError("TMDB", 120.0),
        ):
            results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "TMDB" in (results[0].error or "")

    def test_process_tvshows_skips_when_both_circuits_open(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """TV shows are skipped when both TVDB and TMDB circuits are OPEN."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        (tvshows_dir / "Show A (2024)").mkdir()

        # Force both circuits OPEN
        tmdb_err = ApiError("test", 500, provider_code=0, message="Internal Server Error")
        tvdb_err = ApiError("tvdb", 502, message="Bad Gateway")
        for _ in range(5):
            scraper._tmdb.circuit.record_failure(tmdb_err)
            scraper._tvdb.circuit.record_failure(tvdb_err)

        results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "Both" in (results[0].error or "")

    def test_process_tvshows_continues_when_only_tvdb_open(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """TV shows still process when only TVDB is OPEN (TMDB fallback)."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        (tvshows_dir / "Show A (2024)").mkdir()

        # Force only TVDB circuit OPEN — TMDB is still available
        tvdb_err = ApiError("tvdb", 502, message="Bad Gateway")
        for _ in range(5):
            scraper._tvdb.circuit.record_failure(tvdb_err)

        # scrape_tvshow should be called (TMDB fallback possible)
        mock_result = ScrapeResult(
            media_path=tvshows_dir / "Show A (2024)",
            media_type="tvshow",
            action="scraped",
        )
        with patch.object(scraper, "scrape_tvshow", return_value=mock_result):
            results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action == "scraped"


# ---------------------------------------------------------------------------
# Stale artwork cleanup after folder rename
# ---------------------------------------------------------------------------


class TestCleanupStaleFiles:
    """Tests for _cleanup_stale_files after folder rename."""

    def test_old_artwork_with_colon_removed_after_rename(self, tmp_path: Path) -> None:
        """Old artwork files with ':' should be deleted when sanitized versions exist."""
        movie_dir = tmp_path / "Title Subtitle (2025)"
        movie_dir.mkdir()

        # Old files (from previous scrape, with colon)
        (movie_dir / "Title : Subtitle-poster.jpg").write_bytes(b"old_poster")
        (movie_dir / "Title : Subtitle-landscape.jpg").write_bytes(b"old_landscape")
        (movie_dir / "Title : Subtitle.nfo").write_bytes(b"old_nfo")

        # New files (from current scrape, sanitized)
        (movie_dir / "Title Subtitle-poster.jpg").write_bytes(b"new_poster")
        (movie_dir / "Title Subtitle-landscape.jpg").write_bytes(b"new_landscape")
        (movie_dir / "Title Subtitle.nfo").write_bytes(b"new_nfo")

        # Video file (should NOT be touched)
        (movie_dir / "Title Subtitle.mkv").write_bytes(b"video")

        from personalscraper.scraper.scraper import _cleanup_stale_files

        _cleanup_stale_files(movie_dir, "Title : Subtitle", "Title Subtitle")

        # Old files should be gone
        assert not (movie_dir / "Title : Subtitle-poster.jpg").exists()
        assert not (movie_dir / "Title : Subtitle-landscape.jpg").exists()
        assert not (movie_dir / "Title : Subtitle.nfo").exists()

        # New files should remain
        assert (movie_dir / "Title Subtitle-poster.jpg").exists()
        assert (movie_dir / "Title Subtitle-landscape.jpg").exists()
        assert (movie_dir / "Title Subtitle.nfo").exists()

        # Video untouched
        assert (movie_dir / "Title Subtitle.mkv").exists()

    def test_no_deletion_when_no_sanitized_duplicate(self, tmp_path: Path) -> None:
        """Old files should NOT be deleted if no sanitized equivalent exists."""
        movie_dir = tmp_path / "Title Subtitle (2025)"
        movie_dir.mkdir()

        # Only old file, no new equivalent
        (movie_dir / "Title : Subtitle-poster.jpg").write_bytes(b"old_poster")

        from personalscraper.scraper.scraper import _cleanup_stale_files

        _cleanup_stale_files(movie_dir, "Title : Subtitle", "Title Subtitle")

        # Should NOT be deleted (no replacement exists)
        assert (movie_dir / "Title : Subtitle-poster.jpg").exists()

    def test_no_crash_on_empty_directory(self, tmp_path: Path) -> None:
        """Should handle empty directories without error."""
        movie_dir = tmp_path / "Empty (2025)"
        movie_dir.mkdir()

        from personalscraper.scraper.scraper import _cleanup_stale_files

        _cleanup_stale_files(movie_dir, "Old Name", "New Name")  # No crash


# ---------------------------------------------------------------------------
# _repair_movie_dir — residual NFO removal
# ---------------------------------------------------------------------------


class TestRepairMovieDir:
    """Tests for Scraper._repair_movie_dir."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_repair_movie_dir_removes_residual_nfos(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """Movie with 2 NFOs: keep the correct one, delete residual."""
        movie_dir = tmp_path / "Avatar De feu et de cendres (2025)"
        movie_dir.mkdir()
        good_nfo = movie_dir / "Avatar De feu et de cendres.nfo"
        good_nfo.write_text('<movie><title>Avatar</title><uniqueid type="tmdb">83533</uniqueid></movie>')
        bad_nfo = movie_dir / "Avatar de feu et de cendres 7 1 neostark (2025).nfo"
        bad_nfo.write_text("<movie/>")
        (movie_dir / "Avatar De feu et de cendres.mkv").write_bytes(b"\x00")

        repaired = scraper._repair_movie_dir(movie_dir, "Avatar De feu et de cendres")
        assert repaired is True
        assert good_nfo.exists()
        assert not bad_nfo.exists()

    def test_repair_movie_dir_noop_when_clean(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """Movie with exactly 1 NFO → no repair needed."""
        movie_dir = tmp_path / "Scream 7 (2026)"
        movie_dir.mkdir()
        (movie_dir / "Scream 7.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
        (movie_dir / "Scream 7.mkv").write_bytes(b"\x00")
        (movie_dir / "Scream 7-poster.jpg").write_bytes(b"\x00")

        repaired = scraper._repair_movie_dir(movie_dir, "Scream 7")
        assert repaired is False


# ---------------------------------------------------------------------------
# _repair_tvshow_dir — residual NFO + root MKV duplicate removal
# ---------------------------------------------------------------------------


class TestRepairTvshowDir:
    """Tests for Scraper._repair_tvshow_dir."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_removes_root_nfo_residuals(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """tvshow.nfo is kept, other .nfo at root are removed."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        tvshow_nfo = show_dir / "tvshow.nfo"
        tvshow_nfo.write_text('<tvshow><uniqueid type="tmdb">123</uniqueid></tvshow>')
        residual = show_dir / "random.nfo"
        residual.write_text("<movie/>")

        repaired = scraper._repair_tvshow_dir(show_dir)
        assert repaired is True
        assert tvshow_nfo.exists()
        assert not residual.exists()

    def test_removes_root_mkv_duplicates(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """MKV at root matching SxxExx in Saison XX/ is deleted."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
        s02 = show_dir / "Saison 02"
        s02.mkdir()
        (s02 / "S02E01 - Episode Title.mkv").write_bytes(b"\x00" * 100)
        root_dup = show_dir / "Show.S02E01.1080p.mkv"
        root_dup.write_bytes(b"\x00" * 50)

        repaired = scraper._repair_tvshow_dir(show_dir)
        assert repaired is True
        assert not root_dup.exists()
        assert (s02 / "S02E01 - Episode Title.mkv").exists()

    def test_noop_when_clean(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """Clean show dir with no issues returns False."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
        (show_dir / "poster.jpg").write_bytes(b"\x00")
        s01 = show_dir / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - Ep.mkv").write_bytes(b"\x00")

        repaired = scraper._repair_tvshow_dir(show_dir)
        assert repaired is False

    def test_removes_multiple_residual_nfos(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """Multiple residual NFOs at root are all removed."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
        (show_dir / "S01E01.nfo").write_text("<episodedetails/>")
        (show_dir / "S01E02.nfo").write_text("<episodedetails/>")

        repaired = scraper._repair_tvshow_dir(show_dir)
        assert repaired is True
        assert (show_dir / "tvshow.nfo").exists()
        assert not (show_dir / "S01E01.nfo").exists()
        assert not (show_dir / "S01E02.nfo").exists()

    def test_root_video_not_matching_season_organized(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """Root video for new episode (not in any Saison XX/) is organized via TMDB.

        S01E05 at root while S01E01 is already organized — the new episode should
        be renamed and moved to Saison 01/ when TMDB data is available.
        """
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
        s01 = show_dir / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - Episode.mkv").write_bytes(b"\x00")
        # Root video with different episode number — new episode, should be organized
        orphan = show_dir / "Show.S01E05.mkv"
        orphan.write_bytes(b"\x00" * 50)

        show_data = {"id": 1, "name": "Show"}
        season_data = SeasonDetails(
            provider="tmdb",
            tv_id="1",
            season_number=1,
            episodes=[EpisodeInfo(episode_number=5, title="Episode 5")],
        )

        with (
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(scraper._tmdb, "get_tv_season", return_value=season_data),
            patch.object(scraper, "_generate_episode_nfos"),
        ):
            repaired = scraper._repair_tvshow_dir(show_dir)

        # New root episode should have been organized (moved out of root)
        assert repaired is True
        assert not orphan.exists(), "Root new episode should have been moved to Saison 01/"
        organized = list(s01.glob("S01E05*"))
        assert len(organized) >= 1

    def test_root_new_episode_organized_into_season_dir(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """Root MKV for a NEW episode (not yet in Saison XX/) is renamed and moved.

        Reproduces Bug 1: show has valid tvshow.nfo + Saison 05/ with S05E01-E02,
        then S05E03.mkv lands at root. The repair should move it to Saison 05/
        with the proper canonical name.
        """
        show_dir = tmp_path / "The Boys (2019)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">76479</uniqueid></tvshow>')
        s05 = show_dir / "Saison 05"
        s05.mkdir()
        (s05 / "S05E01 - Episode 1.mkv").write_bytes(b"\x00" * 100)
        (s05 / "S05E02 - Episode 2.mkv").write_bytes(b"\x00" * 100)
        # New episode at root — NOT yet organized
        root_new = show_dir / "The.Boys.S05E03.2160p.mkv"
        root_new.write_bytes(b"\x00" * 200)

        show_data = {
            "id": 76479,
            "name": "The Boys",
        }
        season_data = SeasonDetails(
            provider="tmdb",
            tv_id="76479",
            season_number=5,
            episodes=[EpisodeInfo(episode_number=3, title="Episode 3")],
        )

        with (
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(scraper._tmdb, "get_tv_season", return_value=season_data),
            patch.object(scraper, "_generate_episode_nfos"),
        ):
            repaired = scraper._repair_tvshow_dir(show_dir)

        assert repaired is True
        # The original root file should be gone (moved)
        assert not root_new.exists()
        # A file for S05E03 should now exist somewhere under Saison 05/
        organized = list(s05.glob("S05E03*"))
        assert len(organized) >= 1, f"Expected S05E03 in Saison 05/, got: {list(s05.iterdir())}"

    def test_root_new_episode_dedup_keeps_newest(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """When multiple root files match same SxxExx, only the newest is kept.

        Reproduces the dedup rule: two qualities (4K DV HDR + 1080p) for S05E03
        at root — the newer file wins, the older one is deleted before organizing.
        """
        show_dir = tmp_path / "The Boys (2019)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">76479</uniqueid></tvshow>')
        s05 = show_dir / "Saison 05"
        s05.mkdir()
        (s05 / "S05E01 - Episode 1.mkv").write_bytes(b"\x00" * 100)

        # Two qualities for S05E03 at root — older and newer
        older = show_dir / "The.Boys.S05E03.1080p.mkv"
        older.write_bytes(b"\x00" * 100)
        # Ensure mtime differs
        import os

        os.utime(older, (older.stat().st_atime, older.stat().st_mtime - 60))
        newer = show_dir / "The.Boys.S05E03.2160p.DV.HDR.mkv"
        newer.write_bytes(b"\x00" * 200)

        show_data = {
            "id": 76479,
            "name": "The Boys",
        }
        season_data = SeasonDetails(
            provider="tmdb",
            tv_id="76479",
            season_number=5,
            episodes=[EpisodeInfo(episode_number=3, title="Episode 3")],
        )

        with (
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(scraper._tmdb, "get_tv_season", return_value=season_data),
            patch.object(scraper, "_generate_episode_nfos"),
        ):
            repaired = scraper._repair_tvshow_dir(show_dir)

        assert repaired is True
        # Older duplicate at root must be deleted
        assert not older.exists(), "Older duplicate should have been deleted"
        # Newer was moved to Saison 05/, root must be clear
        assert not newer.exists(), "Newer should have been moved (not at root)"
        # One episode in Saison 05/ for S05E03
        organized = list(s05.glob("S05E03*"))
        assert len(organized) >= 1

    def test_root_new_episode_skipped_when_no_id(
        self,
        tmp_path: Path,
        scraper: Scraper,
    ) -> None:
        """Root new episodes are left intact only when the NFO has no usable id.

        With the TVDB-primary repair fix, a TVDB id alone is sufficient to
        organize the episode (via the TVDB API path) — TMDB id is no longer
        required. The bail-out path now triggers only when both ids are
        missing from the NFO.
        """
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        # NFO without ANY id (neither TMDB nor TVDB) — repair has nothing to query
        (show_dir / "tvshow.nfo").write_text("<tvshow><title>Show</title></tvshow>")
        s01 = show_dir / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * 100)
        # New episode at root
        root_new = show_dir / "Show.S01E02.mkv"
        root_new.write_bytes(b"\x00" * 200)

        scraper._repair_tvshow_dir(show_dir)

        # Nothing should be done for new root episodes without any id
        assert root_new.exists(), "Root new episode should NOT be moved when NFO has no usable id"


class TestStripTrailingYear:
    """Tests for Scraper._strip_trailing_year — removes trailing (YYYY)."""

    def test_strips_trailing_year(self) -> None:
        """Should remove trailing (YYYY) from title."""
        assert Scraper._strip_trailing_year("Invincible (2021)") == "Invincible"

    def test_no_year_unchanged(self) -> None:
        """Title without year suffix should be unchanged."""
        assert Scraper._strip_trailing_year("The Matrix") == "The Matrix"

    def test_year_in_middle_kept(self) -> None:
        """Year in the middle should not be stripped."""
        assert Scraper._strip_trailing_year("2001 A Space Odyssey (1968)") == "2001 A Space Odyssey"

    def test_double_year_strips_only_trailing(self) -> None:
        """Only the trailing year should be stripped."""
        assert Scraper._strip_trailing_year("Show (2020) (2021)") == "Show (2020)"

    def test_empty_string(self) -> None:
        """Empty string should be handled without error."""
        assert Scraper._strip_trailing_year("") == ""

    def test_non_year_parenthetical_kept(self) -> None:
        """Non-year parenthetical should not be stripped."""
        assert Scraper._strip_trailing_year("Title (Director's Cut)") == "Title (Director's Cut)"

    def test_trailing_whitespace_after_year(self) -> None:
        """Trailing whitespace after year should be handled."""
        assert Scraper._strip_trailing_year("Title (2020) ") == "Title"


# ---------------------------------------------------------------------------
# media_path updated after folder rename (bug #17)
# ---------------------------------------------------------------------------


class TestMediaPathUpdatedAfterRename:
    """Tests that result.media_path points to the new path after folder rename."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        return s

    def test_tvshow_media_path_updated_after_rename(
        self,
        scraper: Scraper,
        tmp_path: Path,
    ) -> None:
        """After renaming 'Show' → 'Show (2024)', result.media_path must be the new path."""
        show_dir = tmp_path / "Fallout"
        show_dir.mkdir()

        match = MatchResult(
            api_id=106379,
            api_title="Fallout",
            api_year=2024,
            confidence=0.95,
            source="tmdb",
        )
        show_data = {
            "id": 106379,
            "name": "Fallout",
            "original_name": "Fallout",
            "overview": "Test",
            "vote_average": 8.1,
            "vote_count": 2000,
            "genres": [],
            "first_air_date": "2024-04-10",
            "status": "Returning Series",
            "networks": [{"name": "Prime Video"}],
            "origin_country": ["US"],
            "number_of_episodes": 8,
            "number_of_seasons": 1,
            "external_ids": {"imdb_id": "tt12637874", "tvdb_id": 416744},
            "aggregate_credits": {"cast": []},
            "images": {"posters": [], "backdrops": []},
            "content_ratings": {"results": []},
            "seasons": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_tvshow", return_value=match),
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(scraper._artwork, "download_tvshow_artwork", return_value=[]),
        ):
            result = scraper.scrape_tvshow(show_dir)

        expected_path = tmp_path / "Fallout (2024)"
        assert result.media_path == expected_path
        assert expected_path.exists()
        assert not show_dir.exists()


# ---------------------------------------------------------------------------
# Classifier integration (Phase 7.3)
# ---------------------------------------------------------------------------


class TestClassifierIntegration:
    """Tests for Scraper classifier.classify() wiring."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings with required attributes."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        settings.circuit_breaker_threshold = 5
        settings.circuit_breaker_cooldown = 300
        settings.artwork_language = "fr"
        return settings

    @pytest.fixture
    def test_config(self, tmp_path: Path):
        """Build a minimal Config for classification tests."""
        # test_config is a pytest fixture — call it via the fixture system
        # Here we replicate its logic directly for isolation
        from personalscraper.conf import ids as CID
        from personalscraper.conf.models.categories import (
            AnimeRule,
            CategoryConfig,
            GenreMapping,
        )
        from personalscraper.conf.models.config import Config
        from personalscraper.conf.models.disks import DiskConfig
        from personalscraper.conf.models.paths import PathConfig
        from tests.fixtures.config import CANONICAL_STAGING_DIRS

        return Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[
                DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.MOVIES, CID.TV_SHOWS, CID.ANIME]),
                DiskConfig(id="drive_b", path=tmp_path / "drive_b", categories=[CID.MOVIES_ANIMATION]),
                DiskConfig(
                    id="drive_c",
                    path=tmp_path / "drive_c",
                    categories=[
                        CID.MOVIES_DOCUMENTARY,
                        CID.TV_SHOWS_DOCUMENTARY,
                        CID.STANDUP,
                        CID.TV_PROGRAMS,
                        CID.AUDIOBOOKS,
                        CID.THEATER,
                        CID.TV_SHOWS_ANIMATION,
                    ],
                ),
            ],
            categories={cid: CategoryConfig(folder_name=f"cat_{cid}") for cid in CID.BUILTIN_CATEGORY_IDS},
            genre_mapping=GenreMapping(
                tmdb_movies={16: CID.MOVIES_ANIMATION, 99: CID.MOVIES_DOCUMENTARY},
                tmdb_tv={16: CID.TV_SHOWS_ANIMATION, 99: CID.TV_SHOWS_DOCUMENTARY},
                default_movies_category=CID.MOVIES,
                default_tv_category=CID.TV_SHOWS,
            ),
            anime_rule=AnimeRule(
                enabled=True,
                requires_genre_id=16,
                requires_origin_country=["JP"],
                maps_to=CID.ANIME,
                applies_to="tv",
            ),
            staging_dirs=CANONICAL_STAGING_DIRS,
        )

    def test_classify_called_for_movie(self, mock_settings: MagicMock, test_config, tmp_path: Path) -> None:
        """classify() is called and category_id is set on ScrapeResult."""
        from personalscraper.conf import ids as CID

        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            scraper = Scraper(mock_settings, NamingPatterns(), config=test_config, event_bus=EventBus())

        movie_dir = tmp_path / "Spirited Away (2001)"
        movie_dir.mkdir()
        (movie_dir / "Spirited Away.mkv").write_text("video")

        match = MatchResult(api_id=129, api_title="Spirited Away", api_year=2001, confidence=0.97, source="tmdb")
        # Animation (genre_id=16) + JP origin → movies_animation via genre_mapping
        movie_data = {
            "id": 129,
            "title": "Spirited Away",
            "overview": "...",
            "vote_average": 8.5,
            "vote_count": 5000,
            "genres": [{"id": 16, "name": "Animation"}],
            "origin_country": ["JP"],
            "release_date": "2001-07-20",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0245429"},
            "release_dates": {"results": []},
            "production_countries": [{"iso_3166_1": "JP", "name": "Japan"}],
            "production_companies": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        # Animation genre_id=16 → movies_animation via genre_mapping
        assert result.category_id == CID.MOVIES_ANIMATION

    def test_classify_called_for_tvshow(self, mock_settings: MagicMock, test_config, tmp_path: Path) -> None:
        """classify() is called for TV shows and sets category_id."""
        from personalscraper.conf import ids as CID

        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            scraper = Scraper(mock_settings, NamingPatterns(), config=test_config, event_bus=EventBus())

        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()

        match = MatchResult(api_id=1396, api_title="Breaking Bad", api_year=2008, confidence=0.99, source="tmdb")
        show_data = {
            "id": 1396,
            "name": "Breaking Bad",
            "original_name": "Breaking Bad",
            "overview": "...",
            "vote_average": 9.5,
            "vote_count": 11000,
            "genres": [{"id": 18, "name": "Drama"}],  # Drama → tv_shows default
            "first_air_date": "2008-01-20",
            "number_of_episodes": 62,
            "number_of_seasons": 5,
            "status": "Ended",
            "networks": [{"name": "AMC"}],
            "aggregate_credits": {"cast": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0903747", "tvdb_id": 81189},
            "content_ratings": {"results": []},
            "origin_country": ["US"],
        }

        with (
            patch("personalscraper.scraper.scraper.match_tvshow", return_value=match),
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(scraper._artwork, "download_tvshow_artwork", return_value=[]),
        ):
            result = scraper.scrape_tvshow(show_dir)

        assert result.action == "scraped"
        assert result.category_id == CID.TV_SHOWS  # default for non-matching TV genres

    def test_keywords_not_fetched_when_no_keyword_rules(
        self, mock_settings: MagicMock, test_config, tmp_path: Path
    ) -> None:
        """When no category_rules use tmdb_keyword, keywords API is never called."""
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            scraper = Scraper(mock_settings, NamingPatterns(), config=test_config, event_bus=EventBus())

        # Ensure no keyword rules are configured (test_config has none)
        assert scraper._needs_keywords is False

        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("v")

        match = MatchResult(api_id=603, api_title="The Matrix", api_year=1999, confidence=0.95, source="tmdb")
        movie_data = {
            "id": 603,
            "title": "The Matrix",
            "overview": "...",
            "vote_average": 8.2,
            "vote_count": 20000,
            "genres": [{"id": 28, "name": "Action"}],
            "release_date": "1999-03-31",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0133093"},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        get_keywords_called = []
        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch.object(
                scraper._tmdb,
                "get_keywords",
                side_effect=lambda *a, **k: get_keywords_called.append(True) or [],
            ),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            scraper.scrape_movie(movie_dir)

        assert get_keywords_called == [], "get_keywords() should not be called when no keyword rules exist"

    def test_keywords_fetched_when_keyword_rules_configured(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        """When a category_rule uses tmdb_keyword, keywords are fetched via cache."""
        from personalscraper.conf import ids as CID
        from personalscraper.conf.models.categories import (
            AnimeRule,
            CategoryConfig,
            CategoryRule,
            GenreMapping,
        )
        from personalscraper.conf.models.config import Config
        from personalscraper.conf.models.disks import DiskConfig
        from personalscraper.conf.models.paths import PathConfig
        from tests.fixtures.config import CANONICAL_STAGING_DIRS

        config_with_kw = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[
                DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.MOVIES, CID.STANDUP]),
            ],
            categories={cid: CategoryConfig(folder_name=f"cat_{cid}") for cid in CID.BUILTIN_CATEGORY_IDS},
            category_rules=[
                CategoryRule(tmdb_keyword=["stand-up-comedy"], category=CID.STANDUP, applies_to="movie"),
            ],
            genre_mapping=GenreMapping(default_movies_category=CID.MOVIES, default_tv_category=CID.TV_SHOWS),
            anime_rule=AnimeRule(
                enabled=False,
                requires_genre_id=16,
                requires_origin_country=["JP"],
                maps_to=CID.ANIME,
            ),
            staging_dirs=CANONICAL_STAGING_DIRS,
        )

        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            scraper = Scraper(mock_settings, NamingPatterns(), config=config_with_kw, event_bus=EventBus())

        assert scraper._needs_keywords is True

        movie_dir = tmp_path / "Dave Chappelle (2024)"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("v")

        match = MatchResult(api_id=999, api_title="Dave Chappelle", api_year=2024, confidence=0.92, source="tmdb")
        movie_data = {
            "id": 999,
            "title": "Dave Chappelle",
            "overview": "...",
            "vote_average": 7.5,
            "vote_count": 500,
            "genres": [{"id": 35, "name": "Comedy"}],
            "release_date": "2024-01-01",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt1234567"},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        get_keywords_called = []

        def fake_get_keywords(tmdb_id: int, media_type: str) -> list[str]:
            get_keywords_called.append((tmdb_id, media_type))
            return ["stand-up-comedy"]

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch.object(scraper._tmdb, "get_keywords", side_effect=fake_get_keywords),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert get_keywords_called == [("999", "movie")], "get_keywords() should be called once"
        assert result.category_id == CID.STANDUP

    def test_skip_no_category_when_config_present(self, mock_settings: MagicMock, test_config, tmp_path: Path) -> None:
        """When config is set but classify() returns None, action is skipped_no_category."""
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            scraper = Scraper(mock_settings, NamingPatterns(), config=test_config, event_bus=EventBus())

        movie_dir = tmp_path / "Unknown (2024)"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("v")

        match = MatchResult(api_id=1, api_title="Unknown", api_year=2024, confidence=0.95, source="tmdb")
        movie_data = {
            "id": 1,
            "title": "Unknown",
            "overview": "...",
            "vote_average": 5.0,
            "vote_count": 10,
            "genres": [],
            "release_date": "2024-01-01",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
            patch("personalscraper.scraper.scraper._classifier.classify", return_value=(None, "no_match")),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "skipped_no_category"
        assert result.category_id is None

    def test_no_config_skips_classification(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        """Without config, classify() is never called and category_id stays None."""
        with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
            scraper = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())  # no config

        assert scraper.config is None
        assert scraper._needs_keywords is False

        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("v")

        match = MatchResult(api_id=603, api_title="The Matrix", api_year=1999, confidence=0.95, source="tmdb")
        movie_data = {
            "id": 603,
            "title": "The Matrix",
            "overview": "...",
            "vote_average": 8.2,
            "vote_count": 20000,
            "genres": [{"id": 28, "name": "Action"}],
            "release_date": "1999-03-31",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0133093"},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        assert result.category_id is None  # classification skipped


# ---------------------------------------------------------------------------
# Narrowed exception arm regression tests (SP6.5 + SP7.1)
# ---------------------------------------------------------------------------


class TestParseFolderNameNarrowedExceptions:
    """Regression tests for the narrowed exception arms in _parse_folder_name.

    Covers the TypeError arm added in SP6.5 and the GuessitException arm added
    in SP7.1. Each test verifies that:
    - The function does NOT raise.
    - The ``folder_name_clean_failed`` warning event is emitted via structlog.
    - The return value is ``(name.strip(), None)``.
    """

    def test_parse_folder_name_handles_guessit_exception(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """GuessitException from NameCleaner.clean is caught and logged gracefully.

        Patches NameCleaner.clean with side_effect=GuessitException so the
        narrowed except arm introduced in SP7.1 is exercised without crashing.

        Args:
            caplog: Pytest log capture fixture.
        """
        raw_name = "Some.Malformed.Release.Name.2024"

        with (
            patch(
                "personalscraper.sorter.cleaner.NameCleaner.clean",
                side_effect=GuessitException("bad name", {}),
            ),
            caplog.at_level(logging.WARNING, logger="scraper"),
        ):
            title, year = _parse_folder_name(raw_name)

        assert title == raw_name.strip()
        assert year is None
        assert any(
            isinstance(r.msg, dict) and r.msg.get("event") == "folder_name_clean_failed" for r in caplog.records
        ), "expected 'folder_name_clean_failed' warning event in caplog"

    def test_parse_folder_name_handles_type_error(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TypeError from NameCleaner.clean is caught and logged gracefully.

        Patches NameCleaner.clean with side_effect=TypeError to exercise the
        TypeError arm of the narrowed except tuple introduced in SP6.5.

        Args:
            caplog: Pytest log capture fixture.
        """
        raw_name = "Another.Bad.Release.2023"

        with (
            patch(
                "personalscraper.sorter.cleaner.NameCleaner.clean",
                side_effect=TypeError("unexpected type"),
            ),
            caplog.at_level(logging.WARNING, logger="scraper"),
        ):
            title, year = _parse_folder_name(raw_name)

        assert title == raw_name.strip()
        assert year is None
        assert any(
            isinstance(r.msg, dict) and r.msg.get("event") == "folder_name_clean_failed" for r in caplog.records
        ), "expected 'folder_name_clean_failed' warning event in caplog"


class TestMovieArtworkFailedNarrowedExceptions:
    """Regression tests for the narrowed artwork exception arm in scrape_movie.

    Covers the KeyError/AttributeError arms added to the artwork download
    try/except in SP7.1 (scraper.py line 1239). Verifies that:
    - Processing continues (action == "scraped", no propagated exception).
    - The ``movie_artwork_failed`` warning event is emitted via structlog.
    - A warning string is appended to ScrapeResult.warnings.
    """

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings with minimal API key attributes.

        Returns:
            MagicMock with tmdb_api_key and tvdb_api_key set.
        """
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with a patched TMDBClient.

        Args:
            mock_settings: Mock Settings fixture.

        Returns:
            Scraper instance with patched TMDBClient.
        """
        with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
            return Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())

    def test_movie_artwork_failed_on_key_error(
        self,
        scraper: Scraper,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """KeyError from download_movie_artwork is caught, logged, and added to warnings.

        Patches ArtworkDownloader.download_movie_artwork with
        side_effect=KeyError("missing_template_var") so the narrowed except arm
        covering KeyError (added in SP7.1) is exercised inside scrape_movie.
        Processing must continue — no exception propagates, action stays "scraped".

        Args:
            scraper: Scraper fixture with mocked clients.
            tmp_path: Pytest temporary directory fixture.
            caplog: Pytest log capture fixture.
        """
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.mkv").write_bytes(b"\x00" * 100)

        match = MatchResult(
            api_id=603,
            api_title="The Matrix",
            api_year=1999,
            confidence=0.95,
            source="tmdb",
        )
        movie_data = {
            "id": 603,
            "title": "The Matrix",
            "overview": "A computer hacker...",
            "vote_average": 8.2,
            "vote_count": 20000,
            "genres": [{"name": "Action"}],
            "release_date": "1999-03-31",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0133093"},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(
                scraper._artwork,
                "download_movie_artwork",
                side_effect=KeyError("missing_template_var"),
            ),
            caplog.at_level(logging.WARNING, logger="scraper"),
        ):
            result = scraper.scrape_movie(movie_dir)

        # Processing must continue — action must be "scraped", not "error"
        assert result.action == "scraped", f"Expected 'scraped', got '{result.action}' ({result.error})"
        # Warning must be appended to the result
        assert any("Artwork failed" in w for w in result.warnings), (
            f"Expected 'Artwork failed' in result.warnings, got: {result.warnings}"
        )
        # movie_artwork_failed event must be emitted
        assert any(isinstance(r.msg, dict) and r.msg.get("event") == "movie_artwork_failed" for r in caplog.records), (
            "expected 'movie_artwork_failed' warning event in caplog"
        )

    def test_movie_artwork_failed_on_attribute_error(
        self,
        scraper: Scraper,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AttributeError from download_movie_artwork is caught, logged, and added to warnings.

        Patches ArtworkDownloader.download_movie_artwork with
        side_effect=AttributeError("missing_attr") so the narrowed except arm
        covering AttributeError (added in SP7.1) is exercised inside scrape_movie.
        Processing must continue — no exception propagates, action stays "scraped".

        Args:
            scraper: Scraper fixture with mocked clients.
            tmp_path: Pytest temporary directory fixture.
            caplog: Pytest log capture fixture.
        """
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.mkv").write_bytes(b"\x00" * 100)

        match = MatchResult(
            api_id=603,
            api_title="The Matrix",
            api_year=1999,
            confidence=0.95,
            source="tmdb",
        )
        movie_data = {
            "id": 603,
            "title": "The Matrix",
            "overview": "A computer hacker...",
            "vote_average": 8.2,
            "vote_count": 20000,
            "genres": [{"name": "Action"}],
            "release_date": "1999-03-31",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0133093"},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(
                scraper._artwork,
                "download_movie_artwork",
                side_effect=AttributeError("missing_attr"),
            ),
            caplog.at_level(logging.WARNING, logger="scraper"),
        ):
            result = scraper.scrape_movie(movie_dir)

        # Processing must continue — action must be "scraped", not "error"
        assert result.action == "scraped", f"Expected 'scraped', got '{result.action}' ({result.error})"
        # Warning must be appended to the result
        assert any("Artwork failed" in w for w in result.warnings), (
            f"Expected 'Artwork failed' in result.warnings, got: {result.warnings}"
        )
        # movie_artwork_failed event must be emitted
        assert any(isinstance(r.msg, dict) and r.msg.get("event") == "movie_artwork_failed" for r in caplog.records), (
            "expected 'movie_artwork_failed' warning event in caplog"
        )


class TestShowArtworkFailedNarrowedExceptions:
    """Regression tests for the narrowed artwork exception arm in scrape_tvshow.

    Covers the KeyError/AttributeError arms added to the artwork download
    try/except in SP7.1 (scraper.py line 1501). Verifies that:
    - Processing continues (action == "scraped", no propagated exception).
    - The ``show_artwork_failed`` warning event is emitted via structlog.
    - A warning string is appended to ScrapeResult.warnings.
    """

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings with minimal API key attributes.

        Returns:
            MagicMock with tmdb_api_key and tvdb_api_key set.
        """
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with patched TMDBClient and TVDBClient.

        Args:
            mock_settings: Mock Settings fixture.

        Returns:
            Scraper instance with patched API clients.
        """
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            return Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())

    def test_show_artwork_failed_on_key_error(
        self,
        scraper: Scraper,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """KeyError from download_tvshow_artwork is caught, logged, and added to warnings.

        Patches ArtworkDownloader.download_tvshow_artwork with
        side_effect=KeyError("missing_template_var") so the narrowed except arm
        covering KeyError (added in SP7.1) is exercised inside scrape_tvshow.
        Processing must continue — no exception propagates, action stays "scraped".

        Args:
            scraper: Scraper fixture with mocked clients.
            tmp_path: Pytest temporary directory fixture.
            caplog: Pytest log capture fixture.
        """
        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        match = MatchResult(
            api_id=106379,
            api_title="Fallout",
            api_year=2024,
            confidence=0.95,
            source="tmdb",
        )
        show_data = {
            "id": 106379,
            "name": "Fallout",
            "original_name": "Fallout",
            "overview": "Test",
            "vote_average": 8.1,
            "vote_count": 2000,
            "genres": [],
            "first_air_date": "2024-04-10",
            "status": "Returning Series",
            "networks": [{"name": "Prime Video"}],
            "origin_country": ["US"],
            "number_of_episodes": 8,
            "number_of_seasons": 1,
            "external_ids": {"imdb_id": "tt12637874", "tvdb_id": 416744},
            "aggregate_credits": {"cast": []},
            "images": {"posters": [], "backdrops": []},
            "content_ratings": {"results": []},
            "seasons": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_tvshow", return_value=match),
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(
                scraper._artwork,
                "download_tvshow_artwork",
                side_effect=KeyError("missing_template_var"),
            ),
            caplog.at_level(logging.WARNING, logger="scraper"),
        ):
            result = scraper.scrape_tvshow(show_dir)

        # Processing must continue — action must be "scraped", not "error"
        assert result.action == "scraped", f"Expected 'scraped', got '{result.action}' ({result.error})"
        # Warning must be appended to the result
        assert any("Artwork failed" in w for w in result.warnings), (
            f"Expected 'Artwork failed' in result.warnings, got: {result.warnings}"
        )
        # show_artwork_failed event must be emitted
        assert any(isinstance(r.msg, dict) and r.msg.get("event") == "show_artwork_failed" for r in caplog.records), (
            "expected 'show_artwork_failed' warning event in caplog"
        )

    def test_show_artwork_failed_on_attribute_error(
        self,
        scraper: Scraper,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AttributeError from download_tvshow_artwork is caught, logged, and added to warnings.

        Patches ArtworkDownloader.download_tvshow_artwork with
        side_effect=AttributeError("missing_attr") so the narrowed except arm
        covering AttributeError (added in SP7.1) is exercised inside scrape_tvshow.
        Processing must continue — no exception propagates, action stays "scraped".

        Args:
            scraper: Scraper fixture with mocked clients.
            tmp_path: Pytest temporary directory fixture.
            caplog: Pytest log capture fixture.
        """
        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        match = MatchResult(
            api_id=106379,
            api_title="Fallout",
            api_year=2024,
            confidence=0.95,
            source="tmdb",
        )
        show_data = {
            "id": 106379,
            "name": "Fallout",
            "original_name": "Fallout",
            "overview": "Test",
            "vote_average": 8.1,
            "vote_count": 2000,
            "genres": [],
            "first_air_date": "2024-04-10",
            "status": "Returning Series",
            "networks": [{"name": "Prime Video"}],
            "origin_country": ["US"],
            "number_of_episodes": 8,
            "number_of_seasons": 1,
            "external_ids": {"imdb_id": "tt12637874", "tvdb_id": 416744},
            "aggregate_credits": {"cast": []},
            "images": {"posters": [], "backdrops": []},
            "content_ratings": {"results": []},
            "seasons": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_tvshow", return_value=match),
            patch.object(scraper._tmdb, "get_tv", return_value=show_data),
            patch.object(
                scraper._artwork,
                "download_tvshow_artwork",
                side_effect=AttributeError("missing_attr"),
            ),
            caplog.at_level(logging.WARNING, logger="scraper"),
        ):
            result = scraper.scrape_tvshow(show_dir)

        # Processing must continue — action must be "scraped", not "error"
        assert result.action == "scraped", f"Expected 'scraped', got '{result.action}' ({result.error})"
        # Warning must be appended to the result
        assert any("Artwork failed" in w for w in result.warnings), (
            f"Expected 'Artwork failed' in result.warnings, got: {result.warnings}"
        )
        # show_artwork_failed event must be emitted
        assert any(isinstance(r.msg, dict) and r.msg.get("event") == "show_artwork_failed" for r in caplog.records), (
            "expected 'show_artwork_failed' warning event in caplog"
        )


# ---------------------------------------------------------------------------
# _to_step_report — unmatched counter (10.1)
# ---------------------------------------------------------------------------


class TestToStepReportUnmatched:
    """Tests for unmatched counter surfacing in _to_step_report.

    Items with action ``skipped_low_confidence`` must be counted in both
    ``skip_count`` (backward compat) and ``counts["unmatched"]`` (new
    distinct observable for diagnosis).
    """

    def _make_result(self, action: str, path: Path) -> ScrapeResult:
        """Build a minimal ScrapeResult with the given action.

        Args:
            action: ScrapeResult action string.
            path: Media path for the result.

        Returns:
            Minimal ScrapeResult with the given action.
        """
        return ScrapeResult(media_path=path, media_type="movie", action=action)

    def test_no_unmatched_produces_no_counts_entry(self, tmp_path: Path) -> None:
        """When no skipped_low_confidence results exist, counts is empty."""
        from personalscraper.scraper.run import _to_step_report

        results = [
            self._make_result("scraped", tmp_path / "Movie A (2020)"),
            self._make_result("skipped_already_done", tmp_path / "Movie B (2021)"),
        ]
        report = _to_step_report(results)

        assert report.success_count == 1
        assert report.skip_count == 1
        assert report.error_count == 0
        assert "unmatched" not in report.counts

    def test_one_unmatched_increments_counter(self, tmp_path: Path) -> None:
        """Single skipped_low_confidence item → unmatched=1 in counts."""
        from personalscraper.scraper.run import _to_step_report

        results = [
            self._make_result("scraped", tmp_path / "The Matrix (1999)"),
            self._make_result("skipped_low_confidence", tmp_path / "The Butterfly Effect (2004)"),
        ]
        report = _to_step_report(results)

        assert report.success_count == 1
        # skipped_low_confidence is still counted in skip_count for backward compat
        assert report.skip_count == 1
        assert report.counts.get("unmatched") == 1

    def test_multiple_unmatched_all_counted(self, tmp_path: Path) -> None:
        """Multiple skipped_low_confidence items accumulate in unmatched."""
        from personalscraper.scraper.run import _to_step_report

        results = [
            self._make_result("skipped_low_confidence", tmp_path / "Film A (2000)"),
            self._make_result("skipped_low_confidence", tmp_path / "Film B (2001)"),
            self._make_result("error", tmp_path / "Film C (2002)"),
        ]
        results[2].error = "API timeout"
        report = _to_step_report(results)

        assert report.skip_count == 2
        assert report.error_count == 1
        assert report.counts.get("unmatched") == 2

    def test_unmatched_detail_label_is_unmatched(self, tmp_path: Path) -> None:
        """Detail line for skipped_low_confidence uses [unmatched] prefix."""
        from personalscraper.scraper.run import _to_step_report

        item_path = tmp_path / "The Butterfly Effect (2004)"
        results = [self._make_result("skipped_low_confidence", item_path)]
        report = _to_step_report(results)

        assert any("[unmatched]" in d for d in report.details), f"Expected [unmatched] detail, got: {report.details}"
