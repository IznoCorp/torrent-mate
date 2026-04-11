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

class TestRunVerify:
    """Tests for run_verify."""

    def test_processes_both_dirs(self, tmp_path: Path) -> None:
        """Should process both movies and tvshows."""
        settings = MagicMock()
        settings.staging_dir = str(tmp_path)

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
