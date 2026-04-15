"""Tests for the artwork downloader module.

Tests image selection logic, download behavior (with mocked HTTP),
skip-existing behavior, dry-run mode, and movie/tvshow artwork methods.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.artwork import (
    ArtworkDownloader,
    build_lang_priority,
    select_best_image,
)

# ---------------------------------------------------------------------------
# Language priority tests
# ---------------------------------------------------------------------------


class TestBuildLangPriority:
    """Tests for build_lang_priority — configurable artwork language."""

    def test_default_english(self) -> None:
        """Default should prefer English over French."""
        result = build_lang_priority("en")
        assert result == {"en": 0, "fr": 1}

    def test_french_preferred(self) -> None:
        """French preferred should put French first."""
        result = build_lang_priority("fr")
        assert result == {"fr": 0, "en": 1}

    def test_third_language_keeps_both_fallbacks(self) -> None:
        """Non-en/fr language should keep both en and fr as fallbacks."""
        result = build_lang_priority("de")
        assert result == {"de": 0, "en": 1, "fr": 2}

    def test_integration_with_select_best_image(self) -> None:
        """build_lang_priority result should work with select_best_image."""
        images = [
            {"file_path": "/en.jpg", "iso_639_1": "en", "vote_average": 8.0},
            {"file_path": "/fr.jpg", "iso_639_1": "fr", "vote_average": 5.0},
        ]
        priority = build_lang_priority("fr")
        assert select_best_image(images, priority) == "/fr.jpg"


# ---------------------------------------------------------------------------
# Image selection tests
# ---------------------------------------------------------------------------


class TestSelectBestImage:
    """Tests for select_best_image language priority logic."""

    def test_empty_list(self) -> None:
        """Should return None for empty list."""
        assert select_best_image([]) is None

    def test_single_image(self) -> None:
        """Should return the only image."""
        images = [{"file_path": "/poster.jpg", "iso_639_1": "en", "vote_average": 5.0}]
        assert select_best_image(images) == "/poster.jpg"

    def test_english_preferred_over_french_by_default(self) -> None:
        """Default artwork_language=en prefers English over French."""
        images = [
            {"file_path": "/fr.jpg", "iso_639_1": "fr", "vote_average": 8.0},
            {"file_path": "/en.jpg", "iso_639_1": "en", "vote_average": 5.0},
        ]
        assert select_best_image(images) == "/en.jpg"

    def test_french_preferred_with_fr_priority(self) -> None:
        """French priority map prefers French over English."""
        images = [
            {"file_path": "/en.jpg", "iso_639_1": "en", "vote_average": 8.0},
            {"file_path": "/fr.jpg", "iso_639_1": "fr", "vote_average": 5.0},
        ]
        assert select_best_image(images, {"fr": 0, "en": 1}) == "/fr.jpg"

    def test_english_preferred_over_null(self) -> None:
        """English image should be selected over null/textless."""
        images = [
            {"file_path": "/null.jpg", "iso_639_1": None, "vote_average": 9.0},
            {"file_path": "/en.jpg", "iso_639_1": "en", "vote_average": 3.0},
        ]
        assert select_best_image(images) == "/en.jpg"

    def test_higher_vote_wins_same_language(self) -> None:
        """Higher vote_average should win within same language."""
        images = [
            {"file_path": "/low.jpg", "iso_639_1": "fr", "vote_average": 3.0},
            {"file_path": "/high.jpg", "iso_639_1": "fr", "vote_average": 8.0},
        ]
        assert select_best_image(images) == "/high.jpg"

    def test_null_language_accepted(self) -> None:
        """Null/textless images should be usable."""
        images = [
            {"file_path": "/null.jpg", "iso_639_1": None, "vote_average": 5.0},
        ]
        assert select_best_image(images) == "/null.jpg"


# ---------------------------------------------------------------------------
# Download image tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestDownloadImage:
    """Tests for download_image with mocked HTTP."""

    def test_download_success(self, tmp_path: Path) -> None:
        """Should download and write file on success."""
        downloader = ArtworkDownloader()
        dest = tmp_path / "poster.jpg"
        fake_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Fake JPEG

        with patch.object(downloader, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.content = fake_content
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp

            result = downloader.download_image("https://example.com/img.jpg", dest)

        assert result is True
        assert dest.exists()
        assert dest.read_bytes() == fake_content

    def test_skip_existing_file(self, tmp_path: Path) -> None:
        """Should skip download if file already exists."""
        downloader = ArtworkDownloader()
        dest = tmp_path / "poster.jpg"
        dest.write_bytes(b"existing")

        result = downloader.download_image("https://example.com/img.jpg", dest)
        assert result is False

    def test_dry_run_no_write(self, tmp_path: Path) -> None:
        """Dry run should not write any file."""
        downloader = ArtworkDownloader(dry_run=True)
        dest = tmp_path / "poster.jpg"

        result = downloader.download_image("https://example.com/img.jpg", dest)
        assert result is False
        assert not dest.exists()

    def test_empty_content_rejected(self, tmp_path: Path) -> None:
        """Should reject downloads with empty content."""
        downloader = ArtworkDownloader()
        dest = tmp_path / "poster.jpg"

        with patch.object(downloader, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.content = b""
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp

            result = downloader.download_image("https://example.com/img.jpg", dest)

        assert result is False
        assert not dest.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Should create parent directories if needed."""
        downloader = ArtworkDownloader()
        dest = tmp_path / "subdir" / "poster.jpg"

        with patch.object(downloader, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.content = b"\xff" * 50
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp

            result = downloader.download_image("https://example.com/img.jpg", dest)

        assert result is True
        assert dest.exists()

    def test_timeout_30s(self, tmp_path: Path) -> None:
        """Should use 30s timeout for HTTP requests."""
        downloader = ArtworkDownloader()
        dest = tmp_path / "poster.jpg"

        with patch.object(downloader, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.content = b"\xff" * 50
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp

            downloader.download_image("https://example.com/img.jpg", dest)
            mock_session.get.assert_called_once_with(
                "https://example.com/img.jpg", timeout=30,
            )


# ---------------------------------------------------------------------------
# Movie artwork tests
# ---------------------------------------------------------------------------

SAMPLE_MOVIE_DATA = {
    "title": "The Matrix",
    "images": {
        "posters": [
            {"file_path": "/matrix-poster.jpg", "iso_639_1": "fr", "vote_average": 7.0},
        ],
        "backdrops": [
            {"file_path": "/matrix-backdrop.jpg", "iso_639_1": None, "vote_average": 8.0},
        ],
    },
}


class TestDownloadMovieArtwork:
    """Tests for download_movie_artwork."""

    def test_downloads_poster_and_landscape(self, tmp_path: Path) -> None:
        """Should download both poster and landscape."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()

        with patch.object(downloader, "download_image", return_value=True) as mock_dl:
            result = downloader.download_movie_artwork(
                SAMPLE_MOVIE_DATA, tmp_path, patterns,
            )

        assert len(result) == 2
        assert mock_dl.call_count == 2
        # Check poster call
        poster_call = mock_dl.call_args_list[0]
        assert "matrix-poster.jpg" in poster_call.args[0]
        assert poster_call.args[1].name == "The Matrix-poster.jpg"
        # Check landscape call
        landscape_call = mock_dl.call_args_list[1]
        assert "matrix-backdrop.jpg" in landscape_call.args[0]
        assert landscape_call.args[1].name == "The Matrix-landscape.jpg"

    def test_handles_no_images(self, tmp_path: Path) -> None:
        """Should return empty list when no images available."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()
        data = {"title": "No Images", "images": {"posters": [], "backdrops": []}}

        result = downloader.download_movie_artwork(data, tmp_path, patterns)
        assert result == []

    def test_continues_on_download_failure(self, tmp_path: Path) -> None:
        """Should continue downloading other images if one fails."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()

        with patch.object(downloader, "download_image") as mock_dl:
            # Poster fails, landscape succeeds
            mock_dl.side_effect = [
                requests.exceptions.ConnectionError("timeout"),
                True,
            ]
            result = downloader.download_movie_artwork(
                SAMPLE_MOVIE_DATA, tmp_path, patterns,
            )

        # Only landscape succeeded
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TV show artwork tests
# ---------------------------------------------------------------------------

SAMPLE_TVSHOW_DATA = {
    "name": "Fallout",
    "images": {
        "posters": [
            {"file_path": "/fallout-poster.jpg", "iso_639_1": "fr", "vote_average": 6.0},
        ],
        "backdrops": [
            {"file_path": "/fallout-backdrop.jpg", "iso_639_1": None, "vote_average": 7.0},
        ],
    },
    "seasons": [
        {"season_number": 0, "poster_path": "/specials.jpg"},  # Should be skipped
        {"season_number": 1, "poster_path": "/s1-poster.jpg"},
        {"season_number": 2, "poster_path": "/s2-poster.jpg"},
    ],
}


class TestDownloadTvshowArtwork:
    """Tests for download_tvshow_artwork."""

    def test_downloads_poster_landscape_and_season_posters(
        self, tmp_path: Path,
    ) -> None:
        """Should download show poster + landscape + season posters for present seasons."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()

        # Create season dirs — season posters only downloaded for present seasons
        (tmp_path / "Saison 01").mkdir()
        (tmp_path / "Saison 02").mkdir()

        with patch.object(downloader, "download_image", return_value=True) as mock_dl:
            result = downloader.download_tvshow_artwork(
                SAMPLE_TVSHOW_DATA, tmp_path, patterns,
            )

        # poster + landscape + 2 season posters (season 0 skipped, S01+S02 present)
        assert len(result) == 4
        assert mock_dl.call_count == 4

    def test_show_poster_fixed_name(self, tmp_path: Path) -> None:
        """Show poster should use fixed name poster.jpg."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()

        with patch.object(downloader, "download_image", return_value=True) as mock_dl:
            downloader.download_tvshow_artwork(SAMPLE_TVSHOW_DATA, tmp_path, patterns)

        poster_dest = mock_dl.call_args_list[0].args[1]
        assert poster_dest.name == "poster.jpg"

    def test_show_landscape_fixed_name(self, tmp_path: Path) -> None:
        """Show landscape should use fixed name landscape.jpg."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()

        with patch.object(downloader, "download_image", return_value=True) as mock_dl:
            downloader.download_tvshow_artwork(SAMPLE_TVSHOW_DATA, tmp_path, patterns)

        landscape_dest = mock_dl.call_args_list[1].args[1]
        assert landscape_dest.name == "landscape.jpg"

    def test_season_poster_naming(self, tmp_path: Path) -> None:
        """Season posters should use season{NN}-poster.jpg format."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()

        # Create season dirs so posters are downloaded
        (tmp_path / "Saison 01").mkdir()
        (tmp_path / "Saison 02").mkdir()

        with patch.object(downloader, "download_image", return_value=True) as mock_dl:
            downloader.download_tvshow_artwork(SAMPLE_TVSHOW_DATA, tmp_path, patterns)

        season_names = [call.args[1].name for call in mock_dl.call_args_list[2:]]
        assert "season01-poster.jpg" in season_names
        assert "season02-poster.jpg" in season_names

    def test_skips_specials_season(self, tmp_path: Path) -> None:
        """Season 0 (specials) should not get a poster."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()

        # Create non-special season dirs
        (tmp_path / "Saison 01").mkdir()
        (tmp_path / "Saison 02").mkdir()

        with patch.object(downloader, "download_image", return_value=True) as mock_dl:
            downloader.download_tvshow_artwork(SAMPLE_TVSHOW_DATA, tmp_path, patterns)

        all_urls = [call.args[0] for call in mock_dl.call_args_list]
        assert not any("specials.jpg" in url for url in all_urls)

    def test_no_season_posters_if_no_seasons(self, tmp_path: Path) -> None:
        """Should handle shows with no seasons data."""
        downloader = ArtworkDownloader()
        patterns = NamingPatterns()
        data = {
            "name": "NoSeasons",
            "images": {"posters": [], "backdrops": []},
            "seasons": [],
        }

        result = downloader.download_tvshow_artwork(data, tmp_path, patterns)
        assert result == []
