"""Tests for personalscraper.library.rescraper — targeted API repairs."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.scraper import ScraperConfig
from tests.fixtures.config import CANONICAL_STAGING_DIRS


class TestDetectNeeds:
    """Tests for _detect_needs — what needs repair per item."""

    def test_missing_nfo_needs_nfo(self, tmp_path: Path) -> None:
        """Item without NFO should need NFO regeneration."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is True

    def test_missing_poster_needs_artwork(self, tmp_path: Path) -> None:
        """Item with valid NFO but no poster should need artwork."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is False
        assert needs_artwork is True

    def test_complete_movie_needs_nothing(self, tmp_path: Path) -> None:
        """Complete movie should need nothing."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
        (movie / "Movie-poster.jpg").write_bytes(b"\x00" * 100)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is False
        assert needs_artwork is False

    def test_only_filter_restricts(self, tmp_path: Path) -> None:
        """--only artwork should only flag artwork needs."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        # No NFO, no poster — but only=artwork

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", "artwork")
        assert needs_nfo is False  # Filtered out
        assert needs_artwork is True


class TestResolveId:
    """Tests for _resolve_tmdb_id — ID extraction and matching."""

    def test_id_from_valid_nfo(self, tmp_path: Path) -> None:
        """Should extract TMDB ID from valid NFO without API calls."""
        from personalscraper.library.rescraper import _resolve_tmdb_id

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">12345</uniqueid></movie>')

        tmdb_id, id_source, confidence = _resolve_tmdb_id(
            movie,
            "movie",
            "Movie",
            2024,
            tmdb_client=MagicMock(),
            tvdb_client=MagicMock(),
            interactive=False,
        )

        assert tmdb_id == "12345"
        assert id_source == "nfo"
        assert confidence is None

    def test_rematch_when_no_nfo(self, tmp_path: Path) -> None:
        """Should re-match via API when no NFO exists."""
        from personalscraper.library.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        mock_match = MatchResult(api_id=999, api_title="Movie", api_year=2024, confidence=0.95, source="tmdb")

        with patch("personalscraper.library.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                tmdb_client=MagicMock(),
                tvdb_client=MagicMock(),
                interactive=False,
            )

        assert tmdb_id == "999"
        assert id_source == "api_match"
        assert confidence == 0.95

    def test_low_confidence_skipped(self, tmp_path: Path) -> None:
        """Low confidence match without --interactive should return None."""
        from personalscraper.library.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        mock_match = MatchResult(api_id=999, api_title="Movie?", api_year=2024, confidence=0.4, source="tmdb")

        with patch("personalscraper.library.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                tmdb_client=MagicMock(),
                tvdb_client=MagicMock(),
                interactive=False,
            )

        assert tmdb_id is None

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        """No API match should return None."""
        from personalscraper.library.rescraper import _resolve_tmdb_id

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        with patch("personalscraper.library.rescraper.match_movie", return_value=None):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                tmdb_client=MagicMock(),
                tvdb_client=MagicMock(),
                interactive=False,
            )

        assert tmdb_id is None
        assert confidence is None


class TestRescrapeItem:
    """Tests for _rescrape_item — single item orchestrator."""

    def test_already_ok_returns_none(self, tmp_path: Path) -> None:
        """Item needing nothing should return None."""
        from personalscraper.library.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
        (movie / "Movie-poster.jpg").write_bytes(b"\x00" * 100)

        result = _rescrape_item(
            media_dir=movie,
            media_type="movie",
            disk="Disk1",
            category="films",
            title="Movie",
            year=2024,
            tmdb_client=MagicMock(),
            tvdb_client=MagicMock(),
            nfo_gen=MagicMock(),
            artwork_dl=MagicMock(),
            patterns=NamingPatterns(),
            only=None,
            interactive=False,
            dry_run=True,
        )

        assert result is None

    def test_no_match_returns_skipped(self, tmp_path: Path) -> None:
        """Item with no API match should be skipped."""
        from personalscraper.library.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        # No NFO, no poster — needs repair but no match possible

        with patch("personalscraper.library.rescraper.match_movie", return_value=None):
            result = _rescrape_item(
                media_dir=movie,
                media_type="movie",
                disk="Disk1",
                category="films",
                title="Movie",
                year=2024,
                tmdb_client=MagicMock(),
                tvdb_client=MagicMock(),
                nfo_gen=MagicMock(),
                artwork_dl=MagicMock(),
                patterns=NamingPatterns(),
                only=None,
                interactive=False,
                dry_run=True,
            )

        assert result is not None
        from personalscraper.library.models import SKIP_NO_MATCH

        assert SKIP_NO_MATCH in result.actions_skipped
        assert result.tmdb_id is None

    def test_nfo_regenerated_in_dry_run(self, tmp_path: Path) -> None:
        """Dry-run should report NFO regeneration without writing."""
        from personalscraper.library.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">123</uniqueid></movie>')
        # Has NFO (valid) but no poster — needs artwork

        mock_artwork = MagicMock()
        result = _rescrape_item(
            media_dir=movie,
            media_type="movie",
            disk="Disk1",
            category="films",
            title="Movie",
            year=2024,
            tmdb_client=MagicMock(),
            tvdb_client=MagicMock(),
            nfo_gen=MagicMock(),
            artwork_dl=mock_artwork,
            patterns=NamingPatterns(),
            only=None,
            interactive=False,
            dry_run=True,
        )

        assert result is not None
        from personalscraper.library.models import ACTION_ARTWORK_DOWNLOADED

        assert ACTION_ARTWORK_DOWNLOADED in result.actions_taken
        assert result.tmdb_id == "123"
        assert result.id_source == "nfo"
        # Dry-run: artwork_dl methods should NOT have been called
        mock_artwork.download_movie_artwork.assert_not_called()


class TestRescrapeLibraryConfig:
    """Tests for config-backed library rescraper wiring."""

    def test_uses_configured_scraper_language_for_tmdb(self, tmp_path: Path) -> None:
        """library-rescrape must not read scraper language from .env settings."""
        from personalscraper.library.rescraper import rescrape_library

        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[DiskConfig(id="disk1", path=tmp_path / "disk1", categories=["movies"])],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
            scraper=ScraperConfig(language="fr-FR", fallback_language="en-US", prefer_local_title=True),
        )
        settings = MagicMock()
        settings.tmdb_api_key = "tmdb-key"
        settings.tvdb_api_key = "tvdb-key"
        settings.artwork_language = "en"

        with (
            patch("personalscraper.library.rescraper._collect_rescrape_candidates", return_value=[]),
            patch("personalscraper.api.transport._http.HttpTransport"),
            patch("personalscraper.api.metadata.tmdb.TMDBClient") as tmdb_client_cls,
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(config, settings, dry_run=True)

        assert result.items == []
        assert tmdb_client_cls.call_count == 1
        assert tmdb_client_cls.call_args[1]["language"] == "fr-FR"
