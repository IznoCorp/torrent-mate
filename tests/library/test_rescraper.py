"""Tests for personalscraper.library.rescraper — targeted API repairs."""

from pathlib import Path
from unittest.mock import MagicMock, patch


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
        (movie / "Movie.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid></movie>'
        )

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is False
        assert needs_artwork is True

    def test_complete_movie_needs_nothing(self, tmp_path: Path) -> None:
        """Complete movie should need nothing."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid></movie>'
        )
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
        (movie / "Movie.nfo").write_text(
            '<movie><uniqueid type="tmdb">12345</uniqueid></movie>'
        )

        tmdb_id, id_source, confidence = _resolve_tmdb_id(
            movie, "movie", "Movie", 2024,
            tmdb_client=MagicMock(), tvdb_client=MagicMock(), interactive=False,
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

        mock_match = MatchResult(api_id=999, api_title="Movie", api_year=2024,
                                  confidence=0.95, source="tmdb")

        with patch("personalscraper.library.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie, "movie", "Movie", 2024,
                tmdb_client=MagicMock(), tvdb_client=MagicMock(), interactive=False,
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

        mock_match = MatchResult(api_id=999, api_title="Movie?", api_year=2024,
                                  confidence=0.4, source="tmdb")

        with patch("personalscraper.library.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie, "movie", "Movie", 2024,
                tmdb_client=MagicMock(), tvdb_client=MagicMock(), interactive=False,
            )

        assert tmdb_id is None

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        """No API match should return None."""
        from personalscraper.library.rescraper import _resolve_tmdb_id

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        with patch("personalscraper.library.rescraper.match_movie", return_value=None):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie, "movie", "Movie", 2024,
                tmdb_client=MagicMock(), tvdb_client=MagicMock(), interactive=False,
            )

        assert tmdb_id is None
        assert confidence is None
