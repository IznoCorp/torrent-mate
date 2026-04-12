"""Tests for the Verifier orchestrator and run_verify runner.

Tests verify flow (check → fix → re-check), batch processing,
get_dispatchable filtering, and StepReport conversion.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.run import _to_step_report, run_verify
from personalscraper.verify.verifier import Verifier, VerifyResult


def _make_valid_movie(parent: Path, title: str = "Movie", year: int = 2024) -> Path:
    """Create a minimal valid movie directory."""
    d = parent / f"{title} ({year})"
    d.mkdir()
    (d / f"{title}.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid = ET.SubElement(root, "uniqueid")
    uid.set("type", "tmdb")
    uid.text = "123"
    uid2 = ET.SubElement(root, "uniqueid")
    uid2.set("type", "imdb")
    uid2.text = "tt123"
    ET.SubElement(root, "genre").text = "Drame"
    fi = ET.SubElement(root, "fileinfo")
    ET.SubElement(ET.SubElement(fi, "streamdetails"), "video")
    ET.ElementTree(root).write(d / f"{title}.nfo", encoding="unicode")
    (d / f"{title}-poster.jpg").write_bytes(b"\xff")
    (d / f"{title}-landscape.jpg").write_bytes(b"\xff")
    return d


# ---------------------------------------------------------------------------
# Verifier orchestrator
# ---------------------------------------------------------------------------

class TestVerifyMovie:
    """Tests for Verifier.verify_movie."""

    def test_valid_movie(self, tmp_path: Path) -> None:
        """Valid movie should have status='valid' with category."""
        d = _make_valid_movie(tmp_path)
        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_movie(d)
        assert result.status == "valid"
        assert result.category is not None

    def test_blocked_movie_no_video(self, tmp_path: Path) -> None:
        """Movie without video should be blocked."""
        d = tmp_path / "Empty (2024)"
        d.mkdir()
        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_movie(d)
        assert result.status == "blocked"
        assert len(result.errors) > 0

    def test_fixed_movie_dir_naming(self, tmp_path: Path) -> None:
        """Badly named movie with NFO should be fixed."""
        d = tmp_path / "bad.name"
        d.mkdir()
        (d / "Fight Club.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Fight Club"
        ET.SubElement(root, "year").text = "1999"
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tmdb")
        uid.text = "550"
        uid2 = ET.SubElement(root, "uniqueid")
        uid2.set("type", "imdb")
        uid2.text = "tt0137523"
        ET.SubElement(root, "genre").text = "Drame"
        fi = ET.SubElement(root, "fileinfo")
        ET.SubElement(ET.SubElement(fi, "streamdetails"), "video")
        ET.ElementTree(root).write(d / "Fight Club.nfo", encoding="unicode")
        (d / "Fight Club-poster.jpg").write_bytes(b"\xff")
        (d / "Fight Club-landscape.jpg").write_bytes(b"\xff")

        v = Verifier(MagicMock(), NamingPatterns(), fix=True)
        result = v.verify_movie(d)
        assert result.status == "fixed"
        assert len(result.fixes_applied) > 0
        assert (tmp_path / "Fight Club (1999)").exists()


class TestGetDispatchable:
    """Tests for get_dispatchable filtering."""

    def test_filters_blocked(self) -> None:
        """Should exclude blocked items."""
        results = [
            VerifyResult(Path("a"), "movie", status="valid", category="films"),
            VerifyResult(Path("b"), "movie", status="blocked"),
            VerifyResult(Path("c"), "movie", status="fixed", category="films"),
        ]
        dispatchable = Verifier.get_dispatchable(results)
        assert len(dispatchable) == 2
        assert all(r.status in ("valid", "fixed") for r in dispatchable)


# ---------------------------------------------------------------------------
# StepReport conversion
# ---------------------------------------------------------------------------

class TestToStepReport:
    """Tests for _to_step_report."""

    def test_counts(self) -> None:
        """Should count valid+fixed as success, blocked as error."""
        results = [
            VerifyResult(Path("a"), "movie", status="valid", category="films"),
            VerifyResult(Path("b"), "movie", status="fixed", category="films",
                         fixes_applied=["Fixed dir"]),
            VerifyResult(Path("c"), "movie", status="blocked",
                         errors=["No video"]),
        ]
        report = _to_step_report(results)
        assert report.success_count == 2
        assert report.error_count == 1


# ---------------------------------------------------------------------------
# run_verify integration
# ---------------------------------------------------------------------------

class TestVerifyCheckFixCycle:
    """Tests for the check → fix → re-check cycle."""

    def test_verify_check_fix_recheck_cycle(self, tmp_path: Path) -> None:
        """Item with fixable error should be fixed and re-checked."""
        # Create a movie with bad naming (fixable) but otherwise valid
        d = tmp_path / "bad.name"
        d.mkdir()
        (d / "GoodMovie.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "GoodMovie"
        ET.SubElement(root, "year").text = "2024"
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tmdb")
        uid.text = "999"
        uid2 = ET.SubElement(root, "uniqueid")
        uid2.set("type", "imdb")
        uid2.text = "tt9999"
        ET.SubElement(root, "genre").text = "Drame"
        fi = ET.SubElement(root, "fileinfo")
        ET.SubElement(ET.SubElement(fi, "streamdetails"), "video")
        ET.ElementTree(root).write(d / "GoodMovie.nfo", encoding="unicode")
        (d / "GoodMovie-poster.jpg").write_bytes(b"\xff")
        (d / "GoodMovie-landscape.jpg").write_bytes(b"\xff")

        v = Verifier(MagicMock(), NamingPatterns(), fix=True)
        result = v.verify_movie(d)

        assert result.status == "fixed"
        assert len(result.fixes_applied) > 0
        # After fix, directory should be renamed
        assert (tmp_path / "GoodMovie (2024)").exists()

    def test_verify_multiple_issues_all_fixed(self, tmp_path: Path) -> None:
        """Multiple fixable issues should all be corrected."""
        d = tmp_path / "bad.name.2024"
        d.mkdir()
        (d / "Movie.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Movie"
        ET.SubElement(root, "year").text = "2024"
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tmdb")
        uid.text = "111"
        uid2 = ET.SubElement(root, "uniqueid")
        uid2.set("type", "imdb")
        uid2.text = "tt111"
        ET.SubElement(root, "genre").text = "Drame"
        fi = ET.SubElement(root, "fileinfo")
        ET.SubElement(ET.SubElement(fi, "streamdetails"), "video")
        ET.ElementTree(root).write(d / "Movie.nfo", encoding="unicode")
        (d / "Movie-poster.jpg").write_bytes(b"\xff")
        (d / "Movie-landscape.jpg").write_bytes(b"\xff")

        v = Verifier(MagicMock(), NamingPatterns(), fix=True)
        result = v.verify_movie(d)

        # Should be fixed (dir rename is a fix)
        assert result.status in ("fixed", "valid")

    def test_verify_partial_fix_blocked(self, tmp_path: Path) -> None:
        """Non-fixable issues should leave status as blocked."""
        # Movie with no video file at all — unfixable
        d = tmp_path / "NoVideo (2024)"
        d.mkdir()
        (d / "readme.txt").write_text("no video")

        v = Verifier(MagicMock(), NamingPatterns(), fix=True)
        result = v.verify_movie(d)

        assert result.status == "blocked"
        assert len(result.errors) > 0

    def test_verify_category_correct(self, tmp_path: Path) -> None:
        """Genre 'Drame' should map to category 'films'."""
        d = _make_valid_movie(tmp_path, "Drama Movie", 2024)
        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_movie(d)

        assert result.category == "films"

    def test_verify_dispatchable_filter(self) -> None:
        """Only valid/fixed items with category should be dispatchable."""
        results = [
            VerifyResult(Path("a"), "movie", status="valid", category="films"),
            VerifyResult(Path("b"), "movie", status="fixed", category="series"),
            VerifyResult(Path("c"), "movie", status="blocked", category=None),
            VerifyResult(Path("d"), "movie", status="blocked", category="films"),
        ]
        dispatchable = Verifier.get_dispatchable(results)

        assert len(dispatchable) == 2
        assert all(r.status in ("valid", "fixed") for r in dispatchable)


class TestVerifyTvshow:
    """Tests for Verifier.verify_tvshow."""

    def test_valid_tvshow(self, tmp_path: Path) -> None:
        """Valid TV show should have status='valid'."""
        show_dir = tmp_path / "Show (2024)"
        show_dir.mkdir()
        season_dir = show_dir / "Saison 01"
        season_dir.mkdir()
        (season_dir / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        (season_dir / "S01E01 - Pilot.nfo").write_text("<episodedetails/>")

        # Create tvshow.nfo
        root = ET.Element("tvshow")
        ET.SubElement(root, "title").text = "Show"
        ET.SubElement(root, "year").text = "2024"
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tvdb")
        uid.text = "123"
        uid2 = ET.SubElement(root, "uniqueid")
        uid2.set("type", "imdb")
        uid2.text = "tt123"
        ET.SubElement(root, "genre").text = "Drame"
        ET.ElementTree(root).write(show_dir / "tvshow.nfo", encoding="unicode")
        (show_dir / "poster.jpg").write_bytes(b"\xff")
        (show_dir / "fanart.jpg").write_bytes(b"\xff")

        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_tvshow(show_dir)

        assert result.status in ("valid", "fixed")
        assert result.media_type == "tvshow"

    def test_verify_all_movies_empty(self, tmp_path: Path) -> None:
        """Empty movies directory should return empty results."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()

        v = Verifier(MagicMock(), NamingPatterns())
        results = v.verify_all_movies(movies_dir)

        assert results == []

    def test_verify_all_movies_nonexistent(self, tmp_path: Path) -> None:
        """Nonexistent movies directory should return empty results."""
        v = Verifier(MagicMock(), NamingPatterns())
        results = v.verify_all_movies(tmp_path / "nonexistent")
        assert results == []

    def test_verify_all_movies_with_error(self, tmp_path: Path) -> None:
        """Exception during verify should produce blocked result."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "Bad (2024)").mkdir()

        v = Verifier(MagicMock(), NamingPatterns())
        with patch.object(v, "verify_movie", side_effect=RuntimeError("crash")):
            results = v.verify_all_movies(movies_dir)

        assert len(results) == 1
        assert results[0].status == "blocked"


class TestReinforcedChecks:
    """Tests for V9 reinforced verify checks — poster, episodes, empty dirs."""

    def test_movie_no_poster_blocked(self, tmp_path: Path) -> None:
        """Movie without poster is blocked (poster_present check)."""
        d = _make_valid_movie(tmp_path)
        # Remove poster
        poster = d / "Movie-poster.jpg"
        poster.unlink()
        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_movie(d)
        assert result.status == "blocked"
        assert any("Poster not found" in e for e in result.errors)

    def test_movie_with_empty_subdir_blocked(self, tmp_path: Path) -> None:
        """Movie with empty subdirectory is blocked."""
        d = _make_valid_movie(tmp_path)
        (d / "empty_subdir").mkdir()
        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_movie(d)
        assert result.status == "blocked"
        assert any("Empty subdirs" in e for e in result.errors)

    def test_tvshow_unrenamed_episode_blocked(self, tmp_path: Path) -> None:
        """TV show with unrenamed episode file is blocked."""
        show = tmp_path / "Show (2024)"
        show.mkdir()
        season = show / "Saison 01"
        season.mkdir()
        # Properly named episode
        (season / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        (season / "S01E01 - Pilot.nfo").write_text("<episodedetails/>")
        # Unrenamed episode (raw release name)
        (season / "show.s01e02.1080p.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))

        root = ET.Element("tvshow")
        ET.SubElement(root, "title").text = "Show"
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tvdb")
        uid.text = "123"
        ET.SubElement(root, "genre").text = "Drame"
        ET.ElementTree(root).write(show / "tvshow.nfo", encoding="unicode")
        (show / "poster.jpg").write_bytes(b"\xff")
        (show / "fanart.jpg").write_bytes(b"\xff")

        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_tvshow(show)
        assert result.status == "blocked"
        assert any("Unrenamed episodes" in e for e in result.errors)

    def test_valid_movie_with_poster_passes(self, tmp_path: Path) -> None:
        """Movie with poster and no empty dirs passes all V9 checks."""
        d = _make_valid_movie(tmp_path)
        v = Verifier(MagicMock(), NamingPatterns())
        result = v.verify_movie(d)
        assert result.status == "valid"
        assert len(result.errors) == 0


class TestRunVerify:
    """Tests for run_verify."""

    def test_processes_both_dirs(self, tmp_path: Path) -> None:
        """Should process both movies and tvshows."""
        settings = MagicMock()
        settings.staging_dir = str(tmp_path)
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"

        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        tvshows = tmp_path / "002-TVSHOWS"
        tvshows.mkdir()

        with patch("personalscraper.verify.run.Verifier") as MockVerifier:
            mock_v = MockVerifier.return_value
            mock_v.verify_all_movies.return_value = []
            mock_v.verify_all_tvshows.return_value = []

            report, dispatchable = run_verify(settings)

        assert report.name == "verify"
        mock_v.verify_all_movies.assert_called_once()
        mock_v.verify_all_tvshows.assert_called_once()
