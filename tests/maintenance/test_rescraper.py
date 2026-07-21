"""Tests for personalscraper.maintenance.rescraper — targeted API repairs."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.scraper import ScraperConfig
from personalscraper.core.event_bus import EventBus
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _mock_registry(tmdb=None, tvdb=None):
    """Build a MagicMock ProviderRegistry that returns the given clients from get()."""
    registry = MagicMock(spec=ProviderRegistry)
    clients = {}
    if tmdb is not None:
        clients["tmdb"] = tmdb
    if tvdb is not None:
        clients["tvdb"] = tvdb
    registry.get.side_effect = lambda name: clients[name]
    return registry


class TestDetectNeeds:
    """Tests for _detect_needs — what needs repair per item."""

    def test_missing_nfo_needs_nfo(self, tmp_path: Path) -> None:
        """Item without NFO should need NFO regeneration."""
        from personalscraper.maintenance.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is True

    def test_missing_poster_needs_artwork(self, tmp_path: Path) -> None:
        """Item with valid NFO but no poster should need artwork."""
        from personalscraper.maintenance.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is False
        assert needs_artwork is True

    def test_complete_movie_needs_nothing(self, tmp_path: Path) -> None:
        """Complete movie should need nothing."""
        from personalscraper.maintenance.rescraper import _detect_needs

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
        from personalscraper.maintenance.rescraper import _detect_needs

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
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">12345</uniqueid></movie>')

        tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
            movie,
            "movie",
            "Movie",
            2024,
            registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            interactive=False,
        )

        assert tmdb_id == "12345"
        assert id_source == "nfo"
        assert confidence is None

    def test_rematch_when_no_nfo(self, tmp_path: Path) -> None:
        """Should re-match via API when no NFO exists."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        mock_match = MatchResult(api_id=999, api_title="Movie", api_year=2024, confidence=0.95, source="tmdb")

        with patch("personalscraper.maintenance.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=False,
            )

        assert tmdb_id == "999"
        assert id_source == "api_match"
        assert confidence == 0.95

    def test_low_confidence_skipped(self, tmp_path: Path) -> None:
        """Low confidence match without --interactive should return None."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        mock_match = MatchResult(api_id=999, api_title="Movie?", api_year=2024, confidence=0.4, source="tmdb")

        with patch("personalscraper.maintenance.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=False,
            )

        assert tmdb_id is None

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        """No API match should return None."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        with patch("personalscraper.maintenance.rescraper.match_movie", return_value=None):
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=False,
            )

        assert tmdb_id is None
        assert confidence is None


class TestRescrapeItem:
    """Tests for _rescrape_item — single item orchestrator."""

    def test_already_ok_returns_none(self, tmp_path: Path) -> None:
        """Item needing nothing should return None."""
        from personalscraper.maintenance.rescraper import _rescrape_item
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
            registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
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
        from personalscraper.maintenance.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        # No NFO, no poster — needs repair but no match possible

        with patch("personalscraper.maintenance.rescraper.match_movie", return_value=None):
            result = _rescrape_item(
                media_dir=movie,
                media_type="movie",
                disk="Disk1",
                category="films",
                title="Movie",
                year=2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                nfo_gen=MagicMock(),
                artwork_dl=MagicMock(),
                patterns=NamingPatterns(),
                only=None,
                interactive=False,
                dry_run=True,
            )

        assert result is not None
        from personalscraper.maintenance.rescraper import SKIP_NO_MATCH

        assert SKIP_NO_MATCH in result.actions_skipped
        assert result.tmdb_id is None

    def test_nfo_regenerated_in_dry_run(self, tmp_path: Path) -> None:
        """Dry-run should report NFO regeneration without writing."""
        from personalscraper.maintenance.rescraper import _rescrape_item
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
            registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            nfo_gen=MagicMock(),
            artwork_dl=mock_artwork,
            patterns=NamingPatterns(),
            only=None,
            interactive=False,
            dry_run=True,
        )

        assert result is not None
        from personalscraper.maintenance.rescraper import ACTION_ARTWORK_DOWNLOADED

        assert ACTION_ARTWORK_DOWNLOADED in result.actions_taken
        assert result.tmdb_id == "123"
        assert result.id_source == "nfo"
        # Dry-run: artwork_dl methods should NOT have been called
        mock_artwork.download_movie_artwork.assert_not_called()

    def test_tvdb_only_show_scrapes_via_tvdb_not_tmdb(self, tmp_path: Path) -> None:
        """A TVDB-matched show fetches from TVDB, never ``tmdb.get_tv(tvdb_id)``.

        Regression: the rescraper resolved the TVDB match id but fed it to
        ``tmdb.get_tv`` → 404 → the whole item aborted (Hey Arnold!, Tintin,
        Famille Pirate — old TVDB-only French / classic shows). It must route
        through TVDB, the SAME source-of-match discipline as the initial
        ``tv_service`` scrape (now both via the shared ``fetch_show_data``).
        """
        from personalscraper.api._contracts import ApiError
        from personalscraper.maintenance.rescraper import (
            ACTION_NFO_REGENERATED,
            _rescrape_item,
        )
        from personalscraper.naming_patterns import NamingPatterns
        from personalscraper.scraper.confidence import MatchResult

        show = tmp_path / "Hey Arnold ! (1996)"
        (show / "Saison 01").mkdir(parents=True)
        (show / "Saison 01" / "S01E01 - Ep.mkv").write_bytes(b"\x00" * 1000)
        # No tvshow.nfo → needs_nfo.

        tvdb = MagicMock()
        tvdb_series = MagicMock()
        tvdb_series.external_ids = {}  # TVDB-only: no tmdb cross-ref.
        tvdb.get_series.return_value = tvdb_series

        tmdb = MagicMock()
        # The bug surface: feeding the TVDB id to tmdb.get_tv 404s.
        tmdb.get_tv.side_effect = ApiError("tvdb", 404, 34)

        match = MatchResult(api_id=255968, api_title="Hey Arnold!", api_year=1996, confidence=0.99, source="tvdb")

        with (
            patch("personalscraper.maintenance.rescraper.match_tvshow", return_value=match),
            patch(
                "personalscraper.scraper._tvdb_convert._tvdb_series_to_show_data",
                return_value={"name": "Hey Arnold!", "genres": []},
            ),
        ):
            result = _rescrape_item(
                media_dir=show,
                media_type="tvshow",
                disk="Disk1",
                category="anime",
                title="Hey Arnold !",
                year=1996,
                registry=_mock_registry(tmdb=tmdb, tvdb=tvdb),
                nfo_gen=MagicMock(),
                artwork_dl=MagicMock(),
                patterns=NamingPatterns(),
                only="nfo",
                interactive=False,
                dry_run=True,
            )

        assert result is not None
        assert result.errors == []  # no 404 abort
        assert ACTION_NFO_REGENERATED in result.actions_taken
        tvdb.get_series.assert_called_once_with(255968)  # fetched from TVDB
        tmdb.get_tv.assert_not_called()  # never feed a TVDB id to tmdb.get_tv
        assert result.tmdb_id is None  # TVDB-only: no cross-ref tmdb


class TestRescrapeLibraryConfig:
    """Tests for config-backed library rescraper wiring."""

    def test_registry_accepted_and_returns_empty(self, tmp_path: Path) -> None:
        """library-rescrape should accept a ProviderRegistry and return empty result."""
        from personalscraper.maintenance.rescraper import rescrape_library

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

        with (
            patch("personalscraper.maintenance.rescraper._collect_rescrape_candidates", return_value=[]),
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(
                config,
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        assert result.items == []


# ---------------------------------------------------------------------------
# Additional coverage suite — added to lift coverage from 34% → ≥80%.
# ---------------------------------------------------------------------------


class TestDetectNeedsAdditional:
    """Cover the remaining branches of _detect_needs."""

    def test_tvshow_missing_nfo_and_poster(self, tmp_path: Path) -> None:
        """TV show directory: missing tvshow.nfo and poster.jpg should both flag."""
        from personalscraper.maintenance.rescraper import _detect_needs

        show = tmp_path / "Show (2024)"
        show.mkdir()
        (show / "Show.mkv").write_bytes(b"\x00" * 100)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(show, "tvshow", None)
        assert needs_nfo is True
        assert needs_artwork is True

    def test_tvshow_with_unmatched_episode_filename(self, tmp_path: Path) -> None:
        """A video file without SxxExx pattern should set needs_episodes=True."""
        from personalscraper.maintenance.rescraper import _detect_needs

        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        # Video file without S01E01-style numbering
        (season / "random_episode.mkv").write_bytes(b"\x00" * 100)

        _, _, needs_episodes = _detect_needs(show, "tvshow", None)
        assert needs_episodes is True

    def test_tvshow_with_named_episodes_no_rename(self, tmp_path: Path) -> None:
        """Files matching SxxExx don't trigger needs_episodes."""
        from personalscraper.maintenance.rescraper import _detect_needs

        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        (season / "Show S01E01 - Pilot.mkv").write_bytes(b"\x00" * 100)
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">10</uniqueid></tvshow>')
        (show / "poster.jpg").write_bytes(b"\x00" * 10)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(show, "tvshow", None)
        assert needs_nfo is False
        assert needs_artwork is False
        assert needs_episodes is False

    def test_only_filter_nfo(self, tmp_path: Path) -> None:
        """--only nfo should suppress artwork and episodes flags."""
        from personalscraper.maintenance.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()  # no NFO, no poster

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", "nfo")
        assert needs_nfo is True
        assert needs_artwork is False
        assert needs_episodes is False

    def test_only_filter_episodes(self, tmp_path: Path) -> None:
        """--only episodes should isolate episode flag."""
        from personalscraper.maintenance.rescraper import _detect_needs

        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        (season / "no_pattern.mkv").write_bytes(b"\x00" * 50)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(show, "tvshow", "episodes")
        assert needs_nfo is False
        assert needs_artwork is False
        assert needs_episodes is True


class TestResolveIdAdditional:
    """Extra coverage for _resolve_tmdb_id branches."""

    def test_match_exception_returns_none(self, tmp_path: Path) -> None:
        """Exception raised by match_movie should be swallowed and return all-None."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        with patch(
            "personalscraper.maintenance.rescraper.match_movie",
            side_effect=RuntimeError("API down"),
        ):
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=False,
            )

        assert tmdb_id is None
        assert id_source is None
        assert confidence is None

    def test_tvshow_match_path(self, tmp_path: Path) -> None:
        """TV show resolution should call match_tvshow and return api_match source."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        show = tmp_path / "Show (2024)"
        show.mkdir()

        mock_match = MatchResult(api_id=4242, api_title="Show", api_year=2024, confidence=0.99, source="tmdb")
        with patch("personalscraper.maintenance.rescraper.match_tvshow", return_value=mock_match) as mtv:
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                show,
                "tvshow",
                "Show",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=False,
            )
        assert tmdb_id == "4242"
        assert id_source == "api_match"
        assert confidence == 0.99
        mtv.assert_called_once()

    def test_low_confidence_interactive_accept(self, tmp_path: Path) -> None:
        """Interactive 'y' answer accepts low-confidence match."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        mock_match = MatchResult(api_id=7, api_title="Movie?", api_year=2024, confidence=0.5, source="tmdb")

        with (
            patch("personalscraper.maintenance.rescraper.match_movie", return_value=mock_match),
            patch("builtins.input", return_value="y"),
        ):
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=True,
            )

        assert tmdb_id == "7"
        assert id_source == "api_match"
        assert confidence == 0.5

    def test_low_confidence_interactive_reject(self, tmp_path: Path) -> None:
        """Interactive 'n' answer rejects low-confidence match."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        mock_match = MatchResult(api_id=7, api_title="Movie?", api_year=2024, confidence=0.5, source="tmdb")

        with (
            patch("personalscraper.maintenance.rescraper.match_movie", return_value=mock_match),
            patch("builtins.input", return_value="n"),
        ):
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=True,
            )

        assert tmdb_id is None
        assert id_source is None
        assert confidence == 0.5

    def test_invalid_nfo_falls_back_to_api(self, tmp_path: Path) -> None:
        """An NFO without a valid uniqueid should fall through to API match."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        # NFO present but no uniqueid → extract_nfo_ids returns (None, None)
        (movie / "Movie.nfo").write_text("<movie><title>Movie</title></movie>")

        mock_match = MatchResult(api_id=33, api_title="Movie", api_year=2024, confidence=0.95, source="tmdb")
        with patch("personalscraper.maintenance.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence, _source = _resolve_tmdb_id(
                movie,
                "movie",
                "Movie",
                2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                interactive=False,
            )
        assert tmdb_id == "33"
        assert id_source == "api_match"


class TestFindLargestVideo:
    """Tests for _find_largest_video helper."""

    def test_returns_largest_among_multiple(self, tmp_path: Path) -> None:
        """Should return the largest video file by size."""
        from personalscraper.maintenance.rescraper import _find_largest_video

        d = tmp_path / "Movie (2024)"
        d.mkdir()
        (d / "small.mkv").write_bytes(b"\x00" * 100)
        (d / "big.mp4").write_bytes(b"\x00" * 5000)
        (d / "ignore.txt").write_bytes(b"\x00" * 9999)

        result = _find_largest_video(d)
        assert result is not None
        assert result.name == "big.mp4"

    def test_skips_macos_dotfiles(self, tmp_path: Path) -> None:
        """Should skip ._-prefixed AppleDouble files."""
        from personalscraper.maintenance.rescraper import _find_largest_video

        d = tmp_path / "Movie"
        d.mkdir()
        (d / "._huge.mkv").write_bytes(b"\x00" * 99999)
        (d / "real.mkv").write_bytes(b"\x00" * 200)

        result = _find_largest_video(d)
        assert result is not None
        assert result.name == "real.mkv"

    def test_returns_none_when_no_videos(self, tmp_path: Path) -> None:
        """Should return None when no video files exist."""
        from personalscraper.maintenance.rescraper import _find_largest_video

        d = tmp_path / "Empty"
        d.mkdir()
        (d / "readme.txt").write_text("nothing here")

        assert _find_largest_video(d) is None

    def test_handles_oserror_on_stat(self, tmp_path: Path) -> None:
        """OSError during stat() should skip the file rather than crash."""
        from personalscraper.maintenance.rescraper import _find_largest_video

        d = tmp_path / "Movie"
        d.mkdir()
        # Create a broken symlink that points nowhere — .stat() will raise OSError.
        broken_link = d / "broken.mkv"
        broken_link.symlink_to(tmp_path / "nonexistent_target.mkv")
        (d / "good.mkv").write_bytes(b"\x00" * 50)

        result = _find_largest_video(d)
        assert result is not None
        assert result.name == "good.mkv"


class TestRescrapeItemErrors:
    """Cover _rescrape_item NFO/artwork/API failure branches."""

    def _movie_dir(self, tmp_path: Path) -> Path:
        """Create a movie dir with a video, valid NFO (for ID), no poster.

        Args:
            tmp_path: pytest tmp_path fixture.

        Returns:
            Path to the prepared movie directory.
        """
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">42</uniqueid></movie>')
        return movie

    def test_api_error_records_error(self, tmp_path: Path) -> None:
        """tmdb.get_movie raising should produce an errors entry, not crash."""
        from personalscraper.maintenance.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = self._movie_dir(tmp_path)
        tmdb = MagicMock()
        tmdb.get_movie.side_effect = RuntimeError("boom")

        result = _rescrape_item(
            media_dir=movie,
            media_type="movie",
            disk="Disk1",
            category="films",
            title="Movie",
            year=2024,
            registry=_mock_registry(tmdb=tmdb, tvdb=MagicMock()),
            nfo_gen=MagicMock(),
            artwork_dl=MagicMock(),
            patterns=NamingPatterns(),
            only=None,
            interactive=False,
            dry_run=True,
        )

        assert result is not None
        assert any("API error" in e for e in result.errors)
        assert result.actions_taken == []

    def test_nfo_generation_error_is_captured(self, tmp_path: Path) -> None:
        """Errors raised by nfo_gen should be appended to errors list."""
        from personalscraper.maintenance.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        # Movie missing both NFO and poster — needs both
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)

        tmdb = MagicMock()
        tmdb.get_movie.return_value = {"id": 42, "title": "Movie"}
        nfo_gen = MagicMock()
        nfo_gen.generate_movie_nfo.side_effect = ValueError("bad nfo")

        from personalscraper.scraper.confidence import MatchResult

        match = MatchResult(api_id=42, api_title="Movie", api_year=2024, confidence=0.95, source="tmdb")
        with (
            patch("personalscraper.maintenance.rescraper.match_movie", return_value=match),
            patch(
                "personalscraper.scraper.mediainfo.extract_stream_info",
                return_value=None,
            ),
        ):
            result = _rescrape_item(
                media_dir=movie,
                media_type="movie",
                disk="Disk1",
                category="films",
                title="Movie",
                year=2024,
                registry=_mock_registry(tmdb=tmdb, tvdb=MagicMock()),
                nfo_gen=nfo_gen,
                artwork_dl=MagicMock(),
                patterns=NamingPatterns(),
                only="nfo",
                interactive=False,
                dry_run=True,
            )

        assert result is not None
        assert any("NFO generation failed" in e for e in result.errors)

    def test_artwork_download_error_is_captured(self, tmp_path: Path) -> None:
        """Errors raised by artwork_dl should be appended to errors list."""
        from personalscraper.maintenance.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = self._movie_dir(tmp_path)  # has valid NFO, no poster

        tmdb = MagicMock()
        tmdb.get_movie.return_value = {"id": 42, "title": "Movie"}
        artwork_dl = MagicMock()
        artwork_dl.download_movie_artwork.side_effect = OSError("disk full")

        result = _rescrape_item(
            media_dir=movie,
            media_type="movie",
            disk="Disk1",
            category="films",
            title="Movie",
            year=2024,
            registry=_mock_registry(tmdb=tmdb, tvdb=MagicMock()),
            nfo_gen=MagicMock(),
            artwork_dl=artwork_dl,
            patterns=NamingPatterns(),
            only=None,
            interactive=False,
            dry_run=False,  # so the artwork branch actually invokes download
        )

        assert result is not None
        assert any("Artwork download failed" in e for e in result.errors)

    def test_artwork_download_dry_run_skips_call(self, tmp_path: Path) -> None:
        """In dry-run mode, artwork_dl.download_* must not be called even when needed."""
        from personalscraper.maintenance.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = self._movie_dir(tmp_path)
        tmdb = MagicMock()
        tmdb.get_movie.return_value = {"id": 42, "title": "Movie"}
        artwork_dl = MagicMock()

        from personalscraper.maintenance.rescraper import ACTION_ARTWORK_DOWNLOADED

        result = _rescrape_item(
            media_dir=movie,
            media_type="movie",
            disk="Disk1",
            category="films",
            title="Movie",
            year=2024,
            registry=_mock_registry(tmdb=tmdb, tvdb=MagicMock()),
            nfo_gen=MagicMock(),
            artwork_dl=artwork_dl,
            patterns=NamingPatterns(),
            only=None,
            interactive=False,
            dry_run=True,
        )

        assert result is not None
        assert ACTION_ARTWORK_DOWNLOADED in result.actions_taken
        artwork_dl.download_movie_artwork.assert_not_called()

    def test_tvshow_artwork_branch(self, tmp_path: Path) -> None:
        """TV show needing artwork should call download_tvshow_artwork (apply mode)."""
        from personalscraper.maintenance.rescraper import ACTION_ARTWORK_DOWNLOADED, _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        show = tmp_path / "Show (2024)"
        show.mkdir()
        # Valid tvshow.nfo so we don't need NFO regen, but no poster.jpg
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">42</uniqueid></tvshow>')
        # Add an episode that already follows SxxExx so episodes branch is False
        season = show / "Saison 01"
        season.mkdir()
        (season / "Show S01E01 - Pilot.mkv").write_bytes(b"\x00" * 100)

        tmdb = MagicMock()
        tmdb.get_tv.return_value = {"id": 42, "name": "Show"}
        artwork_dl = MagicMock()

        result = _rescrape_item(
            media_dir=show,
            media_type="tvshow",
            disk="Disk1",
            category="series",
            title="Show",
            year=2024,
            registry=_mock_registry(tmdb=tmdb, tvdb=MagicMock()),
            nfo_gen=MagicMock(),
            artwork_dl=artwork_dl,
            patterns=NamingPatterns(),
            only=None,
            interactive=False,
            dry_run=False,
        )

        assert result is not None
        assert ACTION_ARTWORK_DOWNLOADED in result.actions_taken
        artwork_dl.download_tvshow_artwork.assert_called_once()


class TestRescrapeEpisodes:
    """Tests for _rescrape_episodes.

    Historically the production regex ``SEASON_DIR_RE`` had no capturing
    group while ``_rescrape_episodes`` called ``m.group(1)`` on it —
    raising ``IndexError`` on any real ``Saison NN/`` directory. The
    regex now exposes the season number via ``group(1)`` (see
    ``tests/test_naming_patterns.py::TestSeasonDirRegex
    ::test_capture_group_yields_season_number``); the legacy tests below
    keep the explicit ``_CAPTURING_RE`` patch for historical reasons —
    it is now equivalent to the production regex but documents the
    contract relied upon by this code path.
    """

    _CAPTURING_RE = __import__("re").compile(r"^Saison (\d+)$")

    def test_real_season_dir_re_does_not_raise_indexerror(self, tmp_path: Path) -> None:
        """Regression: real ``Saison NN/`` dirs no longer raise IndexError.

        Before fix: ``int(m.group(1))`` on ``SEASON_DIR_RE`` raised
        ``IndexError: no such group`` because the production regex had
        no capturing group. This test exercises the iteration without
        patching the regex, proving the fix is end-to-end.
        """
        from personalscraper.maintenance.rescraper import _rescrape_episodes
        from personalscraper.naming_patterns import NamingPatterns

        show = tmp_path / "Show (2024)"
        show.mkdir()
        (show / "Saison 01").mkdir()
        (show / "Saison 02").mkdir()
        (show / "Extras").mkdir()  # Non-season dir, must be ignored.

        tmdb = MagicMock()
        empty_season = MagicMock()
        empty_season.episodes = []
        tmdb.get_tv_season.return_value = empty_season

        # No patch on SEASON_DIR_RE — uses production regex.
        _rescrape_episodes(
            show, {"id": 1}, "tmdb", 1, _mock_registry(tmdb=tmdb, tvdb=MagicMock()), NamingPatterns(), dry_run=True
        )

        # Both real season dirs were discovered (no IndexError from the production
        # regex) and passed through to the shared episode fetcher.
        assert tmdb.get_tv_season.call_count == 2

    def test_no_seasons_returns_early(self, tmp_path: Path) -> None:
        """When no Saison NN dirs exist, function returns without API calls."""
        from personalscraper.maintenance.rescraper import _rescrape_episodes
        from personalscraper.naming_patterns import NamingPatterns

        show = tmp_path / "Show (2024)"
        show.mkdir()
        tmdb = MagicMock()

        with patch("personalscraper.naming_patterns.SEASON_DIR_RE", self._CAPTURING_RE):
            _rescrape_episodes(
                show, {"id": 1}, "tmdb", 1, _mock_registry(tmdb=tmdb, tvdb=MagicMock()), NamingPatterns(), dry_run=True
            )
        tmdb.get_tv_season.assert_not_called()

    def test_season_fetch_failure_continues(self, tmp_path: Path) -> None:
        """Per-season exceptions should be logged and not propagate."""
        from personalscraper.maintenance.rescraper import _rescrape_episodes
        from personalscraper.naming_patterns import NamingPatterns

        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        (season / "ep.mkv").write_bytes(b"\x00" * 50)

        tmdb = MagicMock()
        tmdb.get_tv_season.side_effect = RuntimeError("api fail")

        with patch("personalscraper.naming_patterns.SEASON_DIR_RE", self._CAPTURING_RE):
            _rescrape_episodes(
                show, {"id": 1}, "tmdb", 1, _mock_registry(tmdb=tmdb, tvdb=MagicMock()), NamingPatterns(), dry_run=True
            )
        tmdb.get_tv_season.assert_called()

    def test_dry_run_renames_when_matched(self, tmp_path: Path) -> None:
        """Successful season + episode match should call create_season_dirs + rename_episodes."""
        from personalscraper.maintenance.rescraper import _rescrape_episodes
        from personalscraper.naming_patterns import NamingPatterns

        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        (season / "Show.S01E01.mkv").write_bytes(b"\x00" * 100)

        tmdb = MagicMock()
        ep = MagicMock()
        ep.episode_number = 1
        ep.title = "Pilot"
        season_data = MagicMock()
        season_data.episodes = [ep]
        tmdb.get_tv_season.return_value = season_data

        with (
            patch("personalscraper.naming_patterns.SEASON_DIR_RE", self._CAPTURING_RE),
            patch("personalscraper.scraper.episode_manager.create_season_dirs") as csd,
            patch("personalscraper.scraper.episode_manager.rename_episodes") as ren,
        ):
            _rescrape_episodes(
                show, {"id": 1}, "tmdb", 1, _mock_registry(tmdb=tmdb, tvdb=MagicMock()), NamingPatterns(), dry_run=True
            )

        csd.assert_called_once()
        ren.assert_called_once()

    def test_no_matched_episodes_skips_rename(self, tmp_path: Path) -> None:
        """If match_episode_files returns empty, rename_episodes is NOT called."""
        from personalscraper.maintenance.rescraper import _rescrape_episodes
        from personalscraper.naming_patterns import NamingPatterns

        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        (season / "weird-name.mkv").write_bytes(b"\x00" * 100)

        tmdb = MagicMock()
        ep = MagicMock()
        ep.episode_number = 1
        ep.title = None  # exercises default-name branch
        season_data = MagicMock()
        season_data.episodes = [ep]
        tmdb.get_tv_season.return_value = season_data

        with (
            patch("personalscraper.naming_patterns.SEASON_DIR_RE", self._CAPTURING_RE),
            patch(
                "personalscraper.scraper.episode_manager.match_episode_files",
                return_value={},
            ),
            patch("personalscraper.scraper.episode_manager.create_season_dirs") as csd,
            patch("personalscraper.scraper.episode_manager.rename_episodes") as ren,
        ):
            _rescrape_episodes(
                show, {"id": 1}, "tmdb", 1, _mock_registry(tmdb=tmdb, tvdb=MagicMock()), NamingPatterns(), dry_run=True
            )

        csd.assert_not_called()
        ren.assert_not_called()

    def test_no_episodes_returned_returns_early(self, tmp_path: Path) -> None:
        """All seasons fetch returning empty episodes should short-circuit before walk."""
        from personalscraper.maintenance.rescraper import _rescrape_episodes
        from personalscraper.naming_patterns import NamingPatterns

        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        (season / "ep.mkv").write_bytes(b"\x00" * 50)

        tmdb = MagicMock()
        season_data = MagicMock()
        season_data.episodes = []
        tmdb.get_tv_season.return_value = season_data

        with (
            patch("personalscraper.naming_patterns.SEASON_DIR_RE", self._CAPTURING_RE),
            patch("personalscraper.scraper.episode_manager.match_episode_files") as mef,
        ):
            _rescrape_episodes(
                show, {"id": 1}, "tmdb", 1, _mock_registry(tmdb=tmdb, tvdb=MagicMock()), NamingPatterns(), dry_run=True
            )
        mef.assert_not_called()


class TestCollectRescrapeCandidates:
    """Tests for _collect_rescrape_candidates (filesystem walk + DB path)."""

    def _make_config(self, tmp_path: Path) -> Config:
        """Build a minimal Config with one disk/category for walk testing.

        Args:
            tmp_path: pytest tmp_path fixture.

        Returns:
            A populated Config instance.
        """
        return Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[DiskConfig(id="disk1", path=tmp_path / "disk1", categories=["movies"])],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
            scraper=ScraperConfig(),
        )

    def test_walk_disk_not_mounted_logs_and_skips(self, tmp_path: Path) -> None:
        """Disk path missing on filesystem should be skipped without errors."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        # Don't create disk1 dir
        candidates = _collect_rescrape_candidates(config, None, None, None)
        assert candidates == []

    def test_walk_category_dir_missing(self, tmp_path: Path) -> None:
        """Category dir missing on disk should be skipped quietly."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        (tmp_path / "disk1").mkdir()
        # No "films" subdir
        candidates = _collect_rescrape_candidates(config, None, None, None)
        assert candidates == []

    def test_walk_returns_movie_dirs(self, tmp_path: Path) -> None:
        """Filesystem walk should return discovered media directories."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        category_dir = tmp_path / "disk1" / "films"
        category_dir.mkdir(parents=True)
        (category_dir / "Movie A (2024)").mkdir()
        (category_dir / "Movie B (2023)").mkdir()
        # Hidden dir should be skipped
        (category_dir / ".hidden").mkdir()
        # File at category root (not a dir) should be skipped
        (category_dir / "stray.txt").write_text("x")

        candidates = _collect_rescrape_candidates(config, None, None, None)
        names = sorted(p.name for p, *_ in candidates)
        assert names == ["Movie A (2024)", "Movie B (2023)"]
        for _path, media_type, disk_id, cat_id, _eids in candidates:
            assert media_type == "movie"
            assert disk_id == "disk1"
            assert cat_id == "movies"

    def test_walk_disk_filter_excludes(self, tmp_path: Path) -> None:
        """disk_filter not matching any disk yields empty list."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        category_dir = tmp_path / "disk1" / "films"
        category_dir.mkdir(parents=True)
        (category_dir / "Movie (2024)").mkdir()

        result = _collect_rescrape_candidates(config, None, "other-disk", None)
        assert result == []

    def test_walk_category_filter_excludes(self, tmp_path: Path) -> None:
        """category_filter not matching skips iteration."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        category_dir = tmp_path / "disk1" / "films"
        category_dir.mkdir(parents=True)
        (category_dir / "Movie (2024)").mkdir()

        result = _collect_rescrape_candidates(config, None, None, "tv_shows")
        assert result == []

    def test_db_path_skips_missing_mount(self, tmp_path: Path) -> None:
        """DB results lacking mount_path/rel_path should be filtered."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        item_row = MagicMock()
        item_row.kind = "movie"
        item_row.category_id = "movies"

        with patch(
            "personalscraper.indexer.repos.item_repo.find_items_needing_rescrape",
            return_value=[(item_row, "", "")],
        ):
            result = _collect_rescrape_candidates(config, MagicMock(), None, None)
        assert result == []

    def test_db_path_skips_nonexistent_dir(self, tmp_path: Path) -> None:
        """DB hit pointing to non-existent dir is filtered out."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        item_row = MagicMock()
        item_row.kind = "movie"
        item_row.category_id = "movies"

        with patch(
            "personalscraper.indexer.repos.item_repo.find_items_needing_rescrape",
            return_value=[(item_row, str(tmp_path / "nope"), "Movie (2024)")],
        ):
            result = _collect_rescrape_candidates(config, MagicMock(), None, None)
        assert result == []

    def test_db_path_returns_show_with_disk_id(self, tmp_path: Path) -> None:
        """Valid DB row should resolve to a (Path, 'tvshow', disk_id, category) tuple."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[DiskConfig(id="disk1", path=tmp_path / "disk1", categories=["tv_shows"])],
            categories={"tv_shows": CategoryConfig(folder_name="series")},
            staging_dirs=CANONICAL_STAGING_DIRS,
            scraper=ScraperConfig(),
        )
        media_dir = tmp_path / "disk1" / "series" / "Show (2024)"
        media_dir.mkdir(parents=True)

        item_row = MagicMock()
        item_row.kind = "show"
        item_row.category_id = "tv_shows"

        with patch(
            "personalscraper.indexer.repos.item_repo.find_items_needing_rescrape",
            return_value=[(item_row, str(tmp_path / "disk1"), "series/Show (2024)")],
        ):
            result = _collect_rescrape_candidates(cfg, MagicMock(), None, None)

        assert len(result) == 1
        path, media_type, disk_id, cat_id, _eids = result[0]
        assert path == media_dir
        assert media_type == "tvshow"
        assert disk_id == "disk1"
        assert cat_id == "tv_shows"

    def test_db_path_no_matching_disk_filtered(self, tmp_path: Path) -> None:
        """When item.category_id is not in any disk's categories, row is dropped."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        media_dir = tmp_path / "disk1" / "films" / "Movie (2024)"
        media_dir.mkdir(parents=True)
        item_row = MagicMock()
        item_row.kind = "movie"
        item_row.category_id = "unknown_category"

        with patch(
            "personalscraper.indexer.repos.item_repo.find_items_needing_rescrape",
            return_value=[(item_row, str(tmp_path / "disk1"), "films/Movie (2024)")],
        ):
            result = _collect_rescrape_candidates(config, MagicMock(), None, None)
        assert result == []

    def test_db_path_category_filter_drops(self, tmp_path: Path) -> None:
        """Category filter mismatch should drop the candidate."""
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        media_dir = tmp_path / "disk1" / "films" / "Movie (2024)"
        media_dir.mkdir(parents=True)

        item_row = MagicMock()
        item_row.kind = "movie"
        item_row.category_id = "movies"

        with patch(
            "personalscraper.indexer.repos.item_repo.find_items_needing_rescrape",
            return_value=[(item_row, str(tmp_path / "disk1"), "films/Movie (2024)")],
        ):
            result = _collect_rescrape_candidates(config, MagicMock(), None, "other_cat")
        assert result == []


class TestRescrapeLibraryOrchestrator:
    """End-to-end orchestrator tests for rescrape_library, using mocked components."""

    def _config(self, tmp_path: Path) -> Config:
        """Build a Config used across orchestrator tests."""
        return Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[DiskConfig(id="disk1", path=tmp_path / "disk1", categories=["movies"])],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
            scraper=ScraperConfig(),
        )

    def test_max_items_caps_processing(self, tmp_path: Path) -> None:
        """max_items should stop the loop after N candidates."""
        from personalscraper.maintenance.rescraper import rescrape_library

        movie1 = tmp_path / "Movie A (2024)"
        movie1.mkdir()
        movie2 = tmp_path / "Movie B (2024)"
        movie2.mkdir()

        cands = [
            (movie1, "movie", "disk1", "movies", None),
            (movie2, "movie", "disk1", "movies", None),
        ]

        with (
            patch(
                "personalscraper.maintenance.rescraper._collect_rescrape_candidates",
                return_value=cands,
            ),
            patch("personalscraper.maintenance.rescraper._rescrape_item", return_value=None) as ri,
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(
                self._config(tmp_path),
                max_items=1,
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        assert ri.call_count == 1
        assert result.fixed_count == 0  # all None → not tracked

    def test_action_with_errors_increments_error_count(self, tmp_path: Path) -> None:
        """RescrapeAction with non-empty errors should bump error_count."""
        from personalscraper.maintenance.rescraper import RescrapeAction, rescrape_library

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        cands = [(movie, "movie", "disk1", "movies", None)]
        action = RescrapeAction(
            path=str(movie),
            title="Movie",
            media_type="movie",
            disk="disk1",
            category="movies",
            actions_taken=[],
            actions_skipped=[],
            errors=["NFO generation failed"],
            tmdb_id="42",
            id_source="api_match",
            match_confidence=0.9,
            rescraped_at="2024-01-01T00:00:00+00:00",
        )

        with (
            patch(
                "personalscraper.maintenance.rescraper._collect_rescrape_candidates",
                return_value=cands,
            ),
            patch("personalscraper.maintenance.rescraper._rescrape_item", return_value=action),
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(
                self._config(tmp_path),
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        assert result.error_count == 1
        assert result.fixed_count == 0

    def test_action_with_skipped_increments_skipped_count(self, tmp_path: Path) -> None:
        """RescrapeAction with actions_skipped should bump skipped_count."""
        from personalscraper.maintenance.rescraper import SKIP_NO_MATCH, RescrapeAction, rescrape_library

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        cands = [(movie, "movie", "disk1", "movies", None)]
        action = RescrapeAction(
            path=str(movie),
            title="Movie",
            media_type="movie",
            disk="disk1",
            category="movies",
            actions_taken=[],
            actions_skipped=[SKIP_NO_MATCH],
            errors=[],
            tmdb_id=None,
            id_source=None,
            match_confidence=None,
            rescraped_at="2024-01-01T00:00:00+00:00",
        )

        with (
            patch(
                "personalscraper.maintenance.rescraper._collect_rescrape_candidates",
                return_value=cands,
            ),
            patch("personalscraper.maintenance.rescraper._rescrape_item", return_value=action),
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(
                self._config(tmp_path),
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        assert result.skipped_count == 1

    def test_action_success_increments_fixed_count(self, tmp_path: Path) -> None:
        """RescrapeAction with actions_taken and no errors bumps fixed_count."""
        from personalscraper.maintenance.rescraper import ACTION_NFO_REGENERATED, RescrapeAction, rescrape_library

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        cands = [(movie, "movie", "disk1", "movies", None)]
        action = RescrapeAction(
            path=str(movie),
            title="Movie",
            media_type="movie",
            disk="disk1",
            category="movies",
            actions_taken=[ACTION_NFO_REGENERATED],
            actions_skipped=[],
            errors=[],
            tmdb_id="42",
            id_source="api_match",
            match_confidence=0.9,
            rescraped_at="2024-01-01T00:00:00+00:00",
        )

        with (
            patch(
                "personalscraper.maintenance.rescraper._collect_rescrape_candidates",
                return_value=cands,
            ),
            patch("personalscraper.maintenance.rescraper._rescrape_item", return_value=action),
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(
                self._config(tmp_path),
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        assert result.fixed_count == 1
        assert result.error_count == 0
        assert result.skipped_count == 0
        assert len(result.items) == 1

    def test_unhandled_exception_recorded_as_error(self, tmp_path: Path) -> None:
        """An exception inside _rescrape_item should be caught and recorded."""
        from personalscraper.maintenance.rescraper import rescrape_library

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        cands = [(movie, "movie", "disk1", "movies", None)]

        with (
            patch(
                "personalscraper.maintenance.rescraper._collect_rescrape_candidates",
                return_value=cands,
            ),
            patch(
                "personalscraper.maintenance.rescraper._rescrape_item",
                side_effect=RuntimeError("crash"),
            ),
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(
                self._config(tmp_path),
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        assert result.error_count == 1
        assert len(result.items) == 1
        assert "crash" in result.items[0].errors[0]

    def test_action_none_not_tracked(self, tmp_path: Path) -> None:
        """When _rescrape_item returns None (already OK), nothing is appended."""
        from personalscraper.maintenance.rescraper import rescrape_library

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        cands = [(movie, "movie", "disk1", "movies", None)]

        with (
            patch(
                "personalscraper.maintenance.rescraper._collect_rescrape_candidates",
                return_value=cands,
            ),
            patch("personalscraper.maintenance.rescraper._rescrape_item", return_value=None),
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            result = rescrape_library(
                self._config(tmp_path),
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        assert result.fixed_count == 0
        assert result.skipped_count == 0
        assert result.error_count == 0
        assert result.items == []


class TestRescrapeAction:
    """Tests for RescrapeAction model."""

    def test_valid_action(self) -> None:
        """Action with valid fields should work."""
        from personalscraper.maintenance.rescraper import ACTION_NFO_REGENERATED, RescrapeAction

        action = RescrapeAction(
            path="/tmp/Movie (2024)",
            title="Movie",
            media_type="movie",
            disk="Disk1",
            category="films",
            actions_taken=[ACTION_NFO_REGENERATED],
            actions_skipped=[],
            errors=[],
            tmdb_id="123",
            id_source="nfo",
            match_confidence=None,
            rescraped_at="2026-04-17T12:00:00",
        )
        assert action.tmdb_id == "123"
        assert action.id_source == "nfo"

    def test_invalid_media_type_raises(self) -> None:
        """Invalid media_type should raise ValueError."""
        import pytest

        from personalscraper.maintenance.rescraper import RescrapeAction

        with pytest.raises(ValueError, match="media_type"):
            RescrapeAction(
                path="/tmp/X",
                title="X",
                media_type="audiobook",
                disk="Disk1",
                category="films",
                actions_taken=["test"],
                actions_skipped=[],
                errors=[],
                tmdb_id=None,
                id_source=None,
                match_confidence=None,
            )

    def test_confidence_out_of_range_raises(self) -> None:
        """Confidence > 1.0 should raise ValueError."""
        import pytest

        from personalscraper.maintenance.rescraper import RescrapeAction

        with pytest.raises(ValueError, match="match_confidence"):
            RescrapeAction(
                path="/tmp/X",
                title="X",
                media_type="movie",
                disk="Disk1",
                category="films",
                actions_taken=["test"],
                actions_skipped=[],
                errors=[],
                tmdb_id="1",
                id_source="api_match",
                match_confidence=95.0,
            )

    def test_no_tmdb_clears_confidence(self) -> None:
        """If tmdb_id is None, confidence should be cleared."""
        from personalscraper.maintenance.rescraper import SKIP_NO_MATCH, RescrapeAction

        action = RescrapeAction(
            path="/tmp/X",
            title="X",
            media_type="movie",
            disk="Disk1",
            category="films",
            actions_taken=[],
            actions_skipped=[SKIP_NO_MATCH],
            errors=[],
            tmdb_id=None,
            id_source=None,
            match_confidence=0.5,
        )
        assert action.match_confidence is None

    def test_artwork_action_constant(self) -> None:
        """ACTION_ARTWORK_DOWNLOADED and ACTION_EPISODES_RENAMED should be usable."""
        from personalscraper.maintenance.rescraper import (
            ACTION_ARTWORK_DOWNLOADED,
            ACTION_EPISODES_RENAMED,
            RescrapeAction,
        )

        action = RescrapeAction(
            path="/tmp/X",
            title="X",
            media_type="tvshow",
            disk="Disk1",
            category="series",
            actions_taken=[ACTION_ARTWORK_DOWNLOADED, ACTION_EPISODES_RENAMED],
            actions_skipped=[],
            errors=[],
            tmdb_id="1",
            id_source="nfo",
            match_confidence=None,
        )
        assert ACTION_ARTWORK_DOWNLOADED in action.actions_taken
        assert ACTION_EPISODES_RENAMED in action.actions_taken

    def test_invalid_id_source_raises(self) -> None:
        """Invalid id_source should raise ValueError."""
        import pytest

        from personalscraper.maintenance.rescraper import RescrapeAction

        with pytest.raises(ValueError, match="id_source"):
            RescrapeAction(
                path="/tmp/X",
                title="X",
                media_type="movie",
                disk="Disk1",
                category="films",
                actions_taken=[],
                actions_skipped=[],
                errors=[],
                tmdb_id="1",
                id_source="api",
                match_confidence=0.9,
            )

    def test_none_id_source_accepted(self) -> None:
        """id_source=None should be accepted."""
        from personalscraper.maintenance.rescraper import SKIP_NO_MATCH, RescrapeAction

        action = RescrapeAction(
            path="/tmp/X",
            title="X",
            media_type="movie",
            disk="Disk1",
            category="films",
            actions_taken=[],
            actions_skipped=[SKIP_NO_MATCH],
            errors=[],
            tmdb_id=None,
            id_source=None,
            match_confidence=None,
        )
        assert action.id_source is None


class TestLibraryRescrapeResult:
    """Tests for LibraryRescrapeResult container."""

    def test_valid_result(self) -> None:
        """Result with valid fields."""
        from personalscraper.maintenance.rescraper import LibraryRescrapeResult

        result = LibraryRescrapeResult(
            rescraped_at="2026-04-17T12:00:00",
            disk_filter=None,
            category_filter=None,
            only_filter=None,
            dry_run=True,
            fixed_count=0,
            skipped_count=0,
            error_count=0,
        )
        assert result.dry_run is True

    def test_invalid_only_filter_raises(self) -> None:
        """Invalid only_filter should raise ValueError."""
        import pytest

        from personalscraper.maintenance.rescraper import LibraryRescrapeResult

        with pytest.raises(ValueError, match="only_filter"):
            LibraryRescrapeResult(
                rescraped_at="2026-04-17T12:00:00",
                disk_filter=None,
                category_filter=None,
                only_filter="invalid",
                dry_run=True,
                fixed_count=0,
                skipped_count=0,
                error_count=0,
            )

    def test_valid_only_filters(self) -> None:
        """Valid only_filter values should be accepted."""
        from personalscraper.maintenance.rescraper import LibraryRescrapeResult

        for val in ("nfo", "artwork", "episodes"):
            result = LibraryRescrapeResult(
                rescraped_at="2026-04-17T12:00:00",
                disk_filter=None,
                category_filter=None,
                only_filter=val,
                dry_run=False,
                fixed_count=0,
                skipped_count=0,
                error_count=0,
            )
            assert result.only_filter == val


class TestCollectRescrapeCandidatesItemId:
    """Tests for the item_id fast-path in _collect_rescrape_candidates."""

    def _make_config(self, tmp_path: Path) -> Config:
        """Build a minimal Config with one disk/category.

        Args:
            tmp_path: pytest tmp_path fixture.

        Returns:
            A populated Config instance.
        """
        return Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[DiskConfig(id="disk1", path=tmp_path / "disk1", categories=["movies"])],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
            scraper=ScraperConfig(),
        )

    def test_collect_candidates_item_id_returns_single_candidate(self, tmp_path: Path) -> None:
        """item_id fast-path returns exactly one candidate and bypasses find_items_needing_rescrape.

        A valid item with nfo_status='valid' must still be returned when item_id
        is supplied — the predicate is bypassed entirely so force-rescrape works.
        find_items_needing_rescrape must NOT be called.
        """
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)
        media_dir = tmp_path / "disk1" / "films" / "Movie (2024)"
        media_dir.mkdir(parents=True)

        item_row = MagicMock()
        item_row.kind = "movie"
        item_row.category_id = "movies"
        item_row.nfo_status = "valid"

        attr_disk = MagicMock()
        attr_disk.value = "disk1"

        attr_path = MagicMock()
        attr_path.value = str(media_dir)

        def _get_attr_side_effect(conn, item_id, key):
            if key == "dispatch_disk":
                return attr_disk
            if key == "dispatch_path":
                return attr_path
            return None

        with (
            patch(
                "personalscraper.indexer.repos.item_repo.get_by_id",
                return_value=item_row,
            ) as mock_get_by_id,
            patch(
                "personalscraper.indexer.repos.item_repo.get_attr",
                side_effect=_get_attr_side_effect,
            ),
            patch(
                "personalscraper.indexer.repos.item_repo.find_items_needing_rescrape",
            ) as mock_find,
        ):
            result = _collect_rescrape_candidates(config, MagicMock(), None, None, item_id=42)

        assert len(result) == 1
        path, media_type, disk_id, cat_id, _eids = result[0]
        assert path == media_dir
        assert media_type == "movie"
        assert disk_id == "disk1"
        assert cat_id == "movies"
        mock_get_by_id.assert_called_once()
        mock_find.assert_not_called()

    def test_collect_candidates_item_id_missing_item(self, tmp_path: Path) -> None:
        """When get_by_id returns None, the fast-path returns an empty list.

        A warning must be logged; no exception must propagate.
        """
        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)

        with patch(
            "personalscraper.indexer.repos.item_repo.get_by_id",
            return_value=None,
        ):
            result = _collect_rescrape_candidates(config, MagicMock(), None, None, item_id=99)

        assert result == []

    def test_collect_candidates_item_id_mutual_exclusion(self, tmp_path: Path) -> None:
        """Combining item_id with disk_filter must raise ValueError immediately."""
        import pytest

        from personalscraper.maintenance.rescraper import _collect_rescrape_candidates

        config = self._make_config(tmp_path)

        with pytest.raises(ValueError, match="item_id"):
            _collect_rescrape_candidates(config, MagicMock(), "disk1", None, item_id=42)


class TestRescrapeLibraryItemIdThreading:
    """Tests that rescrape_library properly threads item_id through to _collect_rescrape_candidates."""

    def _config(self, tmp_path: Path) -> Config:
        """Build a minimal Config for threading tests.

        Args:
            tmp_path: pytest tmp_path fixture.

        Returns:
            A populated Config instance.
        """
        return Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[DiskConfig(id="disk1", path=tmp_path / "disk1", categories=["movies"])],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
            scraper=ScraperConfig(),
        )

    def test_rescrape_library_item_id_threads_through(self, tmp_path: Path) -> None:
        """rescrape_library must forward item_id to _collect_rescrape_candidates.

        Spy on _collect_rescrape_candidates and assert it is called with
        item_id=42.  The spy returns an empty list so the processing loop is a
        no-op — the assertion is solely about argument forwarding.
        """
        from personalscraper.maintenance.rescraper import rescrape_library

        with (
            patch(
                "personalscraper.maintenance.rescraper._collect_rescrape_candidates",
                return_value=[],
            ) as mock_collect,
            patch("personalscraper.scraper.nfo_generator.NFOGenerator"),
            patch("personalscraper.scraper.artwork.ArtworkDownloader"),
        ):
            rescrape_library(
                self._config(tmp_path),
                item_id=42,
                dry_run=True,
                event_bus=EventBus(),
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
            )

        mock_collect.assert_called_once()
        _call_kwargs = mock_collect.call_args
        # item_id must have been forwarded — check keyword or positional
        assert _call_kwargs.kwargs.get("item_id") == 42 or (len(_call_kwargs.args) >= 5 and _call_kwargs.args[4] == 42)


class TestArtworkTruthfulness:
    """`artwork_downloaded` must reflect files actually written (2026-07-15).

    Live incident: a legacy NFO carried a wrong tmdb id (New Girl → Rabe Rudi,
    a show with zero artwork on TMDB). The downloader returned an empty list,
    yet the rescraper still recorded ``artwork_downloaded`` and the report
    claimed ``Fixed: 1`` — a silent false success that poisons the §2
    « Posters récupérés » maintenance counter.
    """

    def _run_live(self, tmp_path: Path, downloaded: list[Path]):
        """Run a live (non-dry) needs-artwork rescrape with a stubbed downloader."""
        from personalscraper.maintenance.rescraper import _rescrape_item
        from personalscraper.naming_patterns import NamingPatterns

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">123</uniqueid></movie>')
        # Valid NFO, no poster → needs_artwork only.

        mock_artwork = MagicMock()
        mock_artwork.download_movie_artwork.return_value = downloaded

        with patch(
            "personalscraper.scraper._movie_convert._coerce_to_movie_data",
            return_value={"title": "Movie"},
        ):
            return _rescrape_item(
                media_dir=movie,
                media_type="movie",
                disk="Disk1",
                category="films",
                title="Movie",
                year=2024,
                registry=_mock_registry(tmdb=MagicMock(), tvdb=MagicMock()),
                nfo_gen=MagicMock(),
                artwork_dl=mock_artwork,
                patterns=NamingPatterns(),
                only="artwork",
                interactive=False,
                dry_run=False,
            )

    def test_empty_download_is_not_a_success(self, tmp_path: Path) -> None:
        """Downloader wrote nothing → no artwork_downloaded action, an error instead."""
        from personalscraper.maintenance.rescraper import ACTION_ARTWORK_DOWNLOADED

        result = self._run_live(tmp_path, downloaded=[])

        assert result is not None
        assert ACTION_ARTWORK_DOWNLOADED not in result.actions_taken, (
            "an empty download must not be reported as artwork_downloaded"
        )
        assert result.errors, "the report must surface WHY no artwork landed"

    def test_real_download_still_counts(self, tmp_path: Path) -> None:
        """Downloader wrote a poster → artwork_downloaded recorded, no error."""
        from personalscraper.maintenance.rescraper import ACTION_ARTWORK_DOWNLOADED

        result = self._run_live(tmp_path, downloaded=[tmp_path / "Movie (2024)" / "Movie-poster.jpg"])

        assert result is not None
        assert ACTION_ARTWORK_DOWNLOADED in result.actions_taken
        assert result.errors == []


# ---------------------------------------------------------------------------
# Regression — indexer id families honoured when the NFO is absent
# (live incident 2026-07-17: item 3279 « Gone Girls » regenerated its
# tvshow.nfo WITHOUT the tvdb uniqueid because _resolve_tmdb_id fell back
# to an API title-match while the DB row carried the full id family.)
# ---------------------------------------------------------------------------


class TestResolveFromDbExternalIds:
    """_resolve_tmdb_id consults media_item.external_ids_json before the API."""

    _EIDS = (
        '{"tvdb": {"series_id": "459609", "episode_id": null},'
        ' "tmdb": {"series_id": "285084", "episode_id": null},'
        ' "imdb": {"series_id": "tt35629774", "episode_id": null}}'
    )

    def test_tvshow_prefers_db_tvdb_id_when_nfo_absent(self, tmp_path: Path) -> None:
        """No NFO on disk + DB ids → tvdb id with the ``db`` source, no API call."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id

        registry = MagicMock()
        provider_id, id_source, confidence, source = _resolve_tmdb_id(
            tmp_path,
            "tvshow",
            "Gone Girls The Long Island Serial Killer",
            2025,
            registry,
            False,
            external_ids_json=self._EIDS,
        )
        assert (provider_id, id_source, source) == ("459609", "db", "tvdb")
        assert confidence is None
        registry.get.return_value.search.assert_not_called()

    def test_movie_uses_db_tmdb_id_when_nfo_absent(self, tmp_path: Path) -> None:
        """Movies read the tmdb family from the DB ids."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id

        registry = MagicMock()
        provider_id, id_source, _confidence, source = _resolve_tmdb_id(
            tmp_path,
            "movie",
            "Some Movie",
            2024,
            registry,
            False,
            external_ids_json=self._EIDS,
        )
        assert (provider_id, id_source, source) == ("285084", "db", "tmdb")

    def test_malformed_json_falls_through_to_api(self, tmp_path: Path) -> None:
        """A corrupt external_ids_json never crashes — API title-match runs."""
        from personalscraper.maintenance.rescraper import _resolve_tmdb_id

        registry = MagicMock()
        registry.get.return_value = MagicMock()
        with patch(
            "personalscraper.maintenance.rescraper.match_movie",
            return_value=None,
        ):
            provider_id, _source, _conf, _prov = _resolve_tmdb_id(
                tmp_path,
                "movie",
                "Broken",
                2024,
                registry,
                False,
                external_ids_json="{not json",
            )
        assert provider_id is None


class TestInjectDbExternalIds:
    """_inject_db_external_ids merges DB families into the NFO data dict."""

    _EIDS = TestResolveFromDbExternalIds._EIDS

    def test_injects_missing_tvdb_and_imdb(self) -> None:
        """API data without tvdb/imdb gains both; existing keys are kept."""
        from personalscraper.maintenance.rescraper import _inject_db_external_ids

        data: dict = {"id": 285084, "external_ids": {}}
        _inject_db_external_ids(data, self._EIDS)
        assert data["external_ids"]["tvdb_id"] == "459609"
        assert data["external_ids"]["imdb_id"] == "tt35629774"

    def test_api_families_win_over_db(self) -> None:
        """A family already present in the API data is never overwritten."""
        from personalscraper.maintenance.rescraper import _inject_db_external_ids

        data: dict = {"external_ids": {"tvdb_id": "111"}}
        _inject_db_external_ids(data, self._EIDS)
        assert data["external_ids"]["tvdb_id"] == "111"

    def test_malformed_json_is_a_noop(self) -> None:
        """Corrupt JSON leaves the dict untouched (fail-soft)."""
        from personalscraper.maintenance.rescraper import _inject_db_external_ids

        data: dict = {"external_ids": {}}
        _inject_db_external_ids(data, "{broken")
        assert data["external_ids"] == {}

    def test_regenerated_tvshow_nfo_carries_all_families(self) -> None:
        """End-to-end: injected dict → generate_tvshow_nfo → tvdb default + all ids."""
        from personalscraper.maintenance.rescraper import _inject_db_external_ids
        from personalscraper.scraper.nfo_generator import NFOGenerator

        show: dict = {
            "id": 285084,
            "name": "Disparues : Le tueur de Long Island",
            "overview": "",
            "external_ids": {},
        }
        _inject_db_external_ids(show, self._EIDS)
        xml = NFOGenerator().generate_tvshow_nfo(show)
        # Attribute order follows the shared _write_uniqueids writer
        # (SCRAPER-05): type first, then the default flag.
        assert '<uniqueid type="tvdb" default="true">459609</uniqueid>' in xml
        assert 'type="tmdb">285084</uniqueid>' in xml
        assert 'type="imdb">tt35629774</uniqueid>' in xml
