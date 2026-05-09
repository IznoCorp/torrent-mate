"""Tests for the media fixer module.

Tests directory renaming from NFO data, dry-run mode, and the
fix-then-recheck integration cycle.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import CheckResult, MediaChecker, Severity
from personalscraper.verify.fixer import MediaFixer


@pytest.fixture
def fixer() -> MediaFixer:
    """Create a MediaFixer with default patterns."""
    return MediaFixer(NamingPatterns())


@pytest.fixture
def checker(test_config: Config) -> MediaChecker:
    """Create a MediaChecker for re-check tests."""
    return MediaChecker(NamingPatterns(), test_config)


def _make_nfo(directory: Path, title: str, year: str, filename: str = "") -> Path:
    """Write a simple NFO file with title and year."""
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = year
    nfo_name = filename or f"{title}.nfo"
    nfo_path = directory / nfo_name
    ET.ElementTree(root).write(nfo_path, encoding="unicode")
    return nfo_path


# ---------------------------------------------------------------------------
# Movie fixer
# ---------------------------------------------------------------------------


class TestFixMovieDirNaming:
    """Tests for movie directory rename fix."""

    def test_rename_from_nfo(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """Should rename directory using NFO title and year."""
        bad_dir = tmp_path / "fight.club.1999.bluray"
        bad_dir.mkdir()
        _make_nfo(bad_dir, "Fight Club", "1999")

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad name", fixable=True),
        ]
        actions = fixer.fix_movie(bad_dir, checks)

        assert len(actions) == 1
        assert "Fight Club (1999)" in actions[0].description
        assert (tmp_path / "Fight Club (1999)").exists()
        assert not bad_dir.exists()

    def test_no_fix_when_nfo_missing(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """Should not attempt fix when no NFO exists."""
        bad_dir = tmp_path / "NoNFO"
        bad_dir.mkdir()

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_movie(bad_dir, checks)
        assert actions == []

    def test_dry_run_no_rename(self, tmp_path: Path) -> None:
        """Dry run should create FixAction but not rename."""
        fixer = MediaFixer(NamingPatterns(), dry_run=True)
        bad_dir = tmp_path / "bad.name"
        bad_dir.mkdir()
        _make_nfo(bad_dir, "Good Name", "2024")

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_movie(bad_dir, checks)

        assert len(actions) == 1
        assert bad_dir.exists()  # Not renamed
        assert not (tmp_path / "Good Name (2024)").exists()

    def test_no_fix_when_check_passed(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """Should not attempt fix when dir_naming passed."""
        good_dir = tmp_path / "Movie (2024)"
        good_dir.mkdir()

        checks = [
            CheckResult("dir_naming", True, Severity.ERROR, "", fixable=True),
        ]
        actions = fixer.fix_movie(good_dir, checks)
        assert actions == []


# ---------------------------------------------------------------------------
# TV show fixer
# ---------------------------------------------------------------------------


class TestFixTvshowDirNaming:
    """Tests for TV show directory rename fix."""

    def test_rename_from_tvshow_nfo(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """Should rename using tvshow.nfo data."""
        bad_dir = tmp_path / "Fallout"
        bad_dir.mkdir()
        root = ET.Element("tvshow")
        ET.SubElement(root, "title").text = "Fallout"
        ET.SubElement(root, "year").text = "2024"
        ET.ElementTree(root).write(bad_dir / "tvshow.nfo", encoding="unicode")

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_tvshow(bad_dir, checks)

        assert len(actions) == 1
        assert (tmp_path / "Fallout (2024)").exists()


# ---------------------------------------------------------------------------
# Integration: fix → re-check
# ---------------------------------------------------------------------------


class TestFixThenRecheck:
    """Integration tests: fix a broken dir, then re-check."""

    def test_movie_fix_recheck(
        self,
        fixer: MediaFixer,
        checker: MediaChecker,
        tmp_path: Path,
    ) -> None:
        """Fixing a badly named movie should make dir_naming pass on re-check."""
        bad_dir = tmp_path / "fight.club"
        bad_dir.mkdir()
        _make_nfo(bad_dir, "Fight Club", "1999")
        (bad_dir / "Fight Club.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        # Add required artwork and IDs
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Fight Club"
        ET.SubElement(root, "year").text = "1999"
        uid_tmdb = ET.SubElement(root, "uniqueid")
        uid_tmdb.set("type", "tmdb")
        uid_tmdb.text = "550"
        uid_imdb = ET.SubElement(root, "uniqueid")
        uid_imdb.set("type", "imdb")
        uid_imdb.text = "tt0137523"
        ET.SubElement(root, "genre").text = "Drame"
        fileinfo = ET.SubElement(root, "fileinfo")
        ET.SubElement(ET.SubElement(fileinfo, "streamdetails"), "video")
        ET.ElementTree(root).write(bad_dir / "Fight Club.nfo", encoding="unicode")
        (bad_dir / "Fight Club-poster.jpg").write_bytes(b"\xff")
        (bad_dir / "Fight Club-landscape.jpg").write_bytes(b"\xff")

        # First check: dir_naming fails
        checks1 = checker.check_movie(bad_dir)
        naming1 = next(r for r in checks1 if r.name == "dir_naming")
        assert not naming1.passed

        # Fix
        actions = fixer.fix_movie(bad_dir, checks1)
        assert len(actions) == 1
        fixed_dir = actions[0].new_path
        assert fixed_dir is not None

        # Re-check: dir_naming now passes
        checks2 = checker.check_movie(fixed_dir)
        naming2 = next(r for r in checks2 if r.name == "dir_naming")
        assert naming2.passed

    def test_unfixable_stays_broken(
        self,
        fixer: MediaFixer,
        checker: MediaChecker,
        tmp_path: Path,
    ) -> None:
        """Non-fixable issues should remain after fix attempt."""
        empty_dir = tmp_path / "Empty (2024)"
        empty_dir.mkdir()

        checks = checker.check_movie(empty_dir)
        actions = fixer.fix_movie(empty_dir, checks)

        # No fixable issues (video_present is not fixable)
        assert actions == []

        # Re-check still fails
        checks2 = checker.check_movie(empty_dir)
        video_check = next(r for r in checks2 if r.name == "video_present")
        assert not video_check.passed


# ---------------------------------------------------------------------------
# Edge cases — missing-branch coverage
# ---------------------------------------------------------------------------


class TestFixerEdgeCases:
    """Edge-case branches in MediaFixer (parse errors, missing data, OS errors)."""

    def test_no_dir_naming_check_no_action(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """fix_tvshow returns [] when checks list contains no failing dir_naming entry."""
        d = tmp_path / "show"
        d.mkdir()
        checks = [
            CheckResult("other_check", False, Severity.ERROR, "x", fixable=True),
        ]
        assert fixer.fix_tvshow(d, checks) == []

    def test_tvshow_nfo_parse_error(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """Malformed tvshow.nfo: ET.ParseError → no action."""
        d = tmp_path / "show"
        d.mkdir()
        (d / "tvshow.nfo").write_text("<<<not xml>>>")

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_tvshow(d, checks)
        assert actions == []

    def test_movie_nfo_empty_title(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """NFO with empty title returns no action (title required)."""
        d = tmp_path / "bad"
        d.mkdir()
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = ""
        ET.SubElement(root, "year").text = "2024"
        ET.ElementTree(root).write(d / "movie.nfo", encoding="unicode")

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_movie(d, checks)
        assert actions == []

    def test_movie_nfo_no_year_uses_title_only(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """NFO with no year produces canonical = title (no year suffix)."""
        d = tmp_path / "bad"
        d.mkdir()
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Movie No Year"
        # No year sub-element
        ET.ElementTree(root).write(d / "movie.nfo", encoding="unicode")

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_movie(d, checks)
        assert len(actions) == 1
        assert actions[0].new_path is not None
        assert actions[0].new_path.name == "Movie No Year"

    def test_movie_already_canonical(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """If media_dir.name already equals canonical, no rename is needed."""
        d = tmp_path / "Movie (2024)"
        d.mkdir()
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Movie"
        ET.SubElement(root, "year").text = "2024"
        ET.ElementTree(root).write(d / "movie.nfo", encoding="unicode")

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_movie(d, checks)
        assert actions == []

    def test_movie_target_already_exists(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """If new_dir already exists, the fix is aborted."""
        d = tmp_path / "old.name"
        d.mkdir()
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Movie"
        ET.SubElement(root, "year").text = "2024"
        ET.ElementTree(root).write(d / "movie.nfo", encoding="unicode")

        # Create the target before the fix attempt
        (tmp_path / "Movie (2024)").mkdir()

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_movie(d, checks)
        assert actions == []

    def test_movie_rename_oserror(self, fixer: MediaFixer, tmp_path: Path, monkeypatch) -> None:
        """Rename raises OSError → no action returned, original dir still exists."""
        d = tmp_path / "bad"
        d.mkdir()
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Good"
        ET.SubElement(root, "year").text = "2024"
        ET.ElementTree(root).write(d / "movie.nfo", encoding="unicode")

        from pathlib import Path as _Path

        def _bad_rename(self, target):
            raise OSError("rename denied")

        monkeypatch.setattr(_Path, "rename", _bad_rename)

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_movie(d, checks)
        assert actions == []
        assert d.exists()

    def test_tvshow_nfo_missing_returns_none(self, fixer: MediaFixer, tmp_path: Path) -> None:
        """TV show without tvshow.nfo: no action."""
        d = tmp_path / "Show"
        d.mkdir()
        # No tvshow.nfo file written

        checks = [
            CheckResult("dir_naming", False, Severity.ERROR, "bad", fixable=True),
        ]
        actions = fixer.fix_tvshow(d, checks)
        assert actions == []
