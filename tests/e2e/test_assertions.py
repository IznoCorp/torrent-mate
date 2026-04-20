"""Tests for E2E assertions — verify assertion functions work correctly."""

from unittest.mock import MagicMock

import pytest

from tests.e2e.assertions import (
    assert_cleanup_complete,
    assert_dispatch_complete,
    assert_dispatch_golden,
    assert_ingest_complete,
    assert_pipeline_report,
    assert_scrape_complete,
    assert_scrape_golden,
    assert_sort_complete,
    assert_structure_golden,
    assert_verify_complete,
)
from tests.e2e.golden import GoldenFile
from tests.e2e.markers import place_marker
from tests.e2e.registry import TestRegistry

# Keep golden imports accessible to test classes below
__all_golden = [assert_scrape_golden, assert_dispatch_golden, assert_structure_golden, GoldenFile]


class TestAssertIngestComplete:
    """Tests for assert_ingest_complete()."""

    def test_passes_when_items_present(self, tmp_path):
        """No assertion error when expected items exist in staging."""
        (tmp_path / "The.Matrix.1999").mkdir()
        expected = [{"name": "Matrix"}]
        assert_ingest_complete(tmp_path, expected)  # Should not raise

    def test_fails_when_item_missing(self, tmp_path):
        """Raises AssertionError when expected item is not found."""
        expected = [{"name": "NonExistent"}]
        with pytest.raises(AssertionError, match="not found in staging"):
            assert_ingest_complete(tmp_path, expected)


class TestAssertSortComplete:
    """Tests for assert_sort_complete()."""

    def test_passes_movies_in_correct_dir(self, tmp_path):
        """No error when movie is in 001-MOVIES."""
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        (movies / "The Matrix (1999)").mkdir()
        expected = [{"name": "Matrix", "type": "movie"}]
        assert_sort_complete(movies, tmp_path / "002-TVSHOWS", expected)

    def test_fails_movie_in_wrong_dir(self, tmp_path):
        """Raises when movie is not in 001-MOVIES."""
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        expected = [{"name": "Missing", "type": "movie"}]
        with pytest.raises(AssertionError, match="not found"):
            assert_sort_complete(movies, tmp_path / "002-TVSHOWS", expected)


class TestAssertScrapeComplete:
    """Tests for assert_scrape_complete()."""

    def test_passes_with_valid_nfo(self, tmp_path):
        """No error when movie has valid NFO and poster."""
        movies = tmp_path / "001-MOVIES"
        movie_dir = movies / "The Matrix (1999)"
        movie_dir.mkdir(parents=True)
        (movie_dir / "The Matrix.nfo").write_text(
            '<?xml version="1.0"?><movie><title>The Matrix</title><year>1999</year></movie>'
        )
        (movie_dir / "The Matrix-poster.jpg").write_text("fake")

        expected = [{"name": "Matrix", "type": "movie", "verify_nfo_fields": ["title", "year"]}]
        assert_scrape_complete(movies, tmp_path, expected)

    def test_fails_missing_nfo(self, tmp_path):
        """Raises when movie has no NFO."""
        movies = tmp_path / "001-MOVIES"
        (movies / "The Matrix (1999)").mkdir(parents=True)
        expected = [{"name": "Matrix", "type": "movie", "verify_nfo_fields": []}]
        with pytest.raises(AssertionError, match="no .nfo"):
            assert_scrape_complete(movies, tmp_path, expected)


class TestAssertVerifyComplete:
    """Tests for assert_verify_complete()."""

    def test_passes_valid_results(self):
        """No error when all results are valid/fixed."""
        r1 = MagicMock(status="valid", category="films", media_path=MagicMock(name="Movie"))
        r2 = MagicMock(status="fixed", category="series", media_path=MagicMock(name="Show"))
        assert_verify_complete([r1, r2])

    def test_fails_blocked_result(self):
        """Raises when a result is blocked."""
        r = MagicMock(status="blocked", media_path=MagicMock(name="Bad"), issues=["missing nfo"])
        with pytest.raises(AssertionError, match="blocked"):
            assert_verify_complete([r])


class TestAssertDispatchComplete:
    """Tests for assert_dispatch_complete()."""

    def test_passes_item_on_disk(self, tmp_path):
        """No error when item is on disk with marker."""
        disk = tmp_path / "Disk1" / "medias"
        film_dir = disk / "films" / "The Matrix (1999)"
        film_dir.mkdir(parents=True)
        place_marker(film_dir, "test-session")

        expected = [{"name": "Matrix", "expected_category": "films"}]
        assert_dispatch_complete([disk], expected)

    def test_fails_missing_marker(self, tmp_path):
        """Raises when item is on disk but marker is missing."""
        disk = tmp_path / "Disk1" / "medias"
        (disk / "films" / "The Matrix (1999)").mkdir(parents=True)

        expected = [{"name": "Matrix", "expected_category": "films"}]
        with pytest.raises(AssertionError, match="marker missing"):
            assert_dispatch_complete([disk], expected)


class TestAssertPipelineReport:
    """Tests for assert_pipeline_report()."""

    def test_passes_complete_report(self):
        """No error when report has all steps."""
        from datetime import datetime

        from personalscraper.models import PipelineReport, StepReport

        report = PipelineReport(started_at=datetime.now())
        for step in ("ingest", "sort", "scrape", "verify", "dispatch"):
            report.add_step(step, StepReport(name=step))
        report.finished_at = datetime.now()
        assert_pipeline_report(report)

    def test_fails_missing_steps(self):
        """Raises when steps are missing."""
        from datetime import datetime

        from personalscraper.models import PipelineReport, StepReport

        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest"))
        report.finished_at = datetime.now()
        with pytest.raises(AssertionError, match="missing steps"):
            assert_pipeline_report(report)


class TestAssertCleanupComplete:
    """Tests for assert_cleanup_complete()."""

    def test_passes_clean_state(self, tmp_path):
        """No error when all paths are gone."""
        reg = TestRegistry(session_id="clean", base_dir=tmp_path)
        reg.created_paths = [str(tmp_path / "gone")]  # Path doesn't exist
        assert_cleanup_complete(reg, base_paths=[tmp_path])

    def test_fails_path_still_exists(self, tmp_path):
        """Raises when a registered path still exists."""
        reg = TestRegistry(session_id="dirty", base_dir=tmp_path)
        leftover = tmp_path / "still_here"
        leftover.mkdir()
        reg.created_paths = [str(leftover)]
        with pytest.raises(AssertionError, match="still exists"):
            assert_cleanup_complete(reg)


# ---------------------------------------------------------------------------
# Golden file assertions (V7.x)
# ---------------------------------------------------------------------------


def _make_golden_movie(tmp_path, title="Movie", year=2024, tmdb_id="123"):
    """Create a valid movie dir + matching golden file."""
    import xml.etree.ElementTree as ET

    media_dir = tmp_path / f"{title} ({year})"
    media_dir.mkdir()
    (media_dir / f"{title}.mkv").write_bytes(b"\x00" * 1024)

    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    ET.SubElement(root, "tmdbid").text = tmdb_id
    ET.ElementTree(root).write(media_dir / f"{title}.nfo", encoding="unicode")

    (media_dir / f"{title}-poster.jpg").write_bytes(b"\xff" * 20000)

    golden = GoldenFile(
        name=f"{title.lower()}_{year}",
        nfo={
            "media_type": "movie",
            "folder_name_pattern": f"{title} ({year})",
            "required_nfo_tags": ["title", "year", "tmdbid"],
            "nfo_invariants": {"title": title, "year": str(year), "tmdbid": tmdb_id},
        },
        artwork={
            "required": [f"{title}-poster.jpg"],
            "min_poster_size_bytes": 10000,
        },
        structure={
            "required_files": ["*.mkv", "*.nfo"],
            "required_dirs": [],
            "forbidden_patterns": ["*.txt", "*.url"],
        },
        dispatch={
            "action": "moved",
            "eligible_disks": ["Disk1", "Disk3"],
            "destination_contains": f"films/{title} ({year})",
        },
    )
    return media_dir, golden


class TestAssertScrapeGolden:
    """Tests for assert_scrape_golden."""

    def test_valid_passes(self, tmp_path):
        """All checks pass on valid movie."""
        media_dir, golden = _make_golden_movie(tmp_path)
        assert_scrape_golden(media_dir, golden)

    def test_missing_nfo_tag(self, tmp_path):
        """Missing required NFO tag raises AssertionError."""
        media_dir, golden = _make_golden_movie(tmp_path)
        golden.nfo["required_nfo_tags"].append("imdbid")
        with pytest.raises(AssertionError, match="imdbid"):
            assert_scrape_golden(media_dir, golden)

    def test_wrong_invariant(self, tmp_path):
        """Wrong NFO invariant value raises AssertionError."""
        media_dir, golden = _make_golden_movie(tmp_path)
        golden.nfo["nfo_invariants"]["title"] = "WrongTitle"
        with pytest.raises(AssertionError, match="WrongTitle"):
            assert_scrape_golden(media_dir, golden)

    def test_missing_artwork(self, tmp_path):
        """Missing required artwork raises AssertionError."""
        media_dir, golden = _make_golden_movie(tmp_path)
        golden.artwork["required"].append("fanart.jpg")
        with pytest.raises(AssertionError, match="fanart.jpg"):
            assert_scrape_golden(media_dir, golden)

    def test_empty_golden_skips(self, tmp_path):
        """Empty golden nfo/artwork should not raise."""
        media_dir = tmp_path / "Empty (2024)"
        media_dir.mkdir()
        golden = GoldenFile(name="empty", nfo={}, artwork={}, structure={}, dispatch={})
        assert_scrape_golden(media_dir, golden)


class TestAssertDispatchGolden:
    """Tests for assert_dispatch_golden."""

    def test_correct_dispatch(self):
        """Matching dispatch result passes."""
        result = MagicMock()
        result.action = "moved"
        result.disk = "Disk1"
        result.destination = "/Volumes/Disk1/medias/films/Movie (2024)"
        result.reason = None

        golden = GoldenFile(
            name="test",
            nfo={},
            artwork={},
            structure={},
            dispatch={
                "action": "moved",
                "eligible_disks": ["Disk1", "Disk3"],
                "destination_contains": "films/Movie (2024)",
            },
        )
        assert_dispatch_golden(result, golden)

    def test_wrong_action(self):
        """Wrong action raises AssertionError."""
        result = MagicMock()
        result.action = "replaced"
        result.disk = "Disk1"
        result.destination = "/some/path"
        result.reason = None

        golden = GoldenFile(
            name="test",
            nfo={},
            artwork={},
            structure={},
            dispatch={"action": "moved"},
        )
        with pytest.raises(AssertionError, match="moved"):
            assert_dispatch_golden(result, golden)

    def test_wrong_disk(self):
        """Disk not in eligible list raises AssertionError."""
        result = MagicMock()
        result.action = "moved"
        result.disk = "Disk4"
        result.destination = "/some/path"
        result.reason = None

        golden = GoldenFile(
            name="test",
            nfo={},
            artwork={},
            structure={},
            dispatch={"eligible_disks": ["Disk1", "Disk3"]},
        )
        with pytest.raises(AssertionError, match="Disk4"):
            assert_dispatch_golden(result, golden)

    def test_error_action_fails(self):
        """Error action always raises."""
        result = MagicMock()
        result.action = "error"
        result.disk = None
        result.destination = None
        result.reason = "rsync failed"

        golden = GoldenFile(
            name="test",
            nfo={},
            artwork={},
            structure={},
            dispatch={"action": "moved"},
        )
        with pytest.raises(AssertionError, match="error"):
            assert_dispatch_golden(result, golden)


class TestAssertStructureGolden:
    """Tests for assert_structure_golden."""

    def test_valid_structure(self, tmp_path):
        """Valid structure passes all checks."""
        media_dir, golden = _make_golden_movie(tmp_path)
        assert_structure_golden(media_dir, golden)

    def test_forbidden_file_fails(self, tmp_path):
        """Forbidden file pattern raises AssertionError."""
        media_dir, golden = _make_golden_movie(tmp_path)
        (media_dir / "readme.txt").write_text("junk")
        with pytest.raises(AssertionError, match="forbidden"):
            assert_structure_golden(media_dir, golden)

    def test_missing_required_file(self, tmp_path):
        """Missing required file pattern raises AssertionError."""
        media_dir = tmp_path / "Empty (2024)"
        media_dir.mkdir()
        golden = GoldenFile(
            name="test",
            nfo={},
            artwork={},
            structure={"required_files": ["*.mkv"]},
            dispatch={},
        )
        with pytest.raises(AssertionError, match="\\*.mkv"):
            assert_structure_golden(media_dir, golden)

    def test_missing_required_dir(self, tmp_path):
        """Missing required directory raises AssertionError."""
        media_dir = tmp_path / "Show (2024)"
        media_dir.mkdir()
        golden = GoldenFile(
            name="test",
            nfo={},
            artwork={},
            structure={"required_dirs": ["Saison 01"]},
            dispatch={},
        )
        with pytest.raises(AssertionError, match="Saison 01"):
            assert_structure_golden(media_dir, golden)

    def test_empty_golden_skips(self, tmp_path):
        """Empty structure golden should not raise."""
        media_dir = tmp_path / "Empty (2024)"
        media_dir.mkdir()
        golden = GoldenFile(name="test", nfo={}, artwork={}, structure={}, dispatch={})
        assert_structure_golden(media_dir, golden)


# ---------------------------------------------------------------------------
# Helper functions (V7.x)
# ---------------------------------------------------------------------------


class TestFindMediaDir:
    """Tests for find_media_dir helper."""

    def test_finds_matching_dir(self, tmp_path):
        """Should find directory by pattern."""
        from tests.e2e.assertions import find_media_dir

        (tmp_path / "Jumanji (1995)").mkdir()
        (tmp_path / "Matrix (1999)").mkdir()

        result = find_media_dir(tmp_path, "Jumanji (1995)")
        assert result.name == "Jumanji (1995)"

    def test_case_insensitive(self, tmp_path):
        """Should match case-insensitively."""
        from tests.e2e.assertions import find_media_dir

        (tmp_path / "The Matrix (1999)").mkdir()

        result = find_media_dir(tmp_path, "matrix")
        assert "Matrix" in result.name

    def test_not_found_raises(self, tmp_path):
        """Should raise AssertionError when not found."""
        from tests.e2e.assertions import find_media_dir

        (tmp_path / "SomeMovie (2024)").mkdir()

        with pytest.raises(AssertionError, match="no directory"):
            find_media_dir(tmp_path, "Nonexistent")

    def test_parent_not_exists_raises(self, tmp_path):
        """Should raise AssertionError when parent doesn't exist."""
        from tests.e2e.assertions import find_media_dir

        with pytest.raises(AssertionError, match="does not exist"):
            find_media_dir(tmp_path / "nonexistent", "Movie")


class TestFindDispatchResult:
    """Tests for find_dispatch_result helper."""

    def test_finds_matching_result(self):
        """Should find result by torrent name."""
        from pathlib import Path

        from tests.e2e.assertions import find_dispatch_result

        r1 = MagicMock()
        r1.source = Path("/staging/Jumanji (1995)")
        r2 = MagicMock()
        r2.source = Path("/staging/Matrix (1999)")

        result = find_dispatch_result([r1, r2], "Jumanji")
        assert result is r1

    def test_reverse_match(self):
        """Should match when torrent name contains source name."""
        from pathlib import Path

        from tests.e2e.assertions import find_dispatch_result

        r1 = MagicMock()
        r1.source = Path("/staging/Jumanji")

        result = find_dispatch_result([r1], "[LaCale]-Jumanji.1995.BluRay")
        assert result is r1

    def test_not_found_returns_none(self):
        """Should return None when no match."""
        from pathlib import Path

        from tests.e2e.assertions import find_dispatch_result

        r1 = MagicMock()
        r1.source = Path("/staging/Matrix (1999)")

        result = find_dispatch_result([r1], "Jumanji")
        assert result is None
