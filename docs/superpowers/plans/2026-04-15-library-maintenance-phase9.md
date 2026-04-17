# Phase 9: E2E Tests — Integration tests across all 6 commands

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** End-to-end integration tests verifying the full library maintenance workflow: scan → clean → validate → analyze → recommend → report. Tests use a realistic temporary filesystem with movies and TV shows.

**Architecture:** Single test file `tests/library/test_integration.py` with a shared fixture that builds a mini-library on disk. Each test verifies cross-command data flow (JSON files consumed by downstream commands).

**Tech Stack:** Python, pytest, tmp_path fixtures

---

## Task 1: Create shared fixture and scan integration test

**Files:**

- Create: `tests/library/test_integration.py`

- [ ] **Step 1: Write integration test fixture and scan test**

```python
# tests/library/test_integration.py
"""Integration tests for the full library maintenance workflow.

Tests the chain: scan → clean → validate → analyze → recommend → report.
Uses a realistic temporary filesystem with movies and TV shows.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mini_library(tmp_path: Path):
    """Build a realistic mini-library for integration testing.

    Structure:
        Disk1/medias/
            films/
                The Matrix (1999)/
                    The Matrix.mkv (200 MB fake)
                    The Matrix.nfo (valid, TMDB ID)
                    The Matrix-poster.jpg
                    The Matrix-landscape.jpg
                    .actors/Actor.jpg
                    .DS_Store
                Incomplete Movie/
                    movie.mkv (200 MB fake, no NFO, no year in name)
            series/
                Fallout (2024)/
                    tvshow.nfo (valid)
                    poster.jpg
                    season01-poster.jpg
                    Saison 01/
                        S01E01 - The Beginning.mkv (500 MB fake)
                        S01E01 - The Beginning.nfo
                        S01E02 - The End.mkv (500 MB fake)
                    .actors/
                    empty_release_dir/  (empty)
    """
    disk = tmp_path / "Disk1" / "medias"

    # --- Movie: complete ---
    matrix = disk / "films" / "The Matrix (1999)"
    matrix.mkdir(parents=True)
    (matrix / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
    (matrix / "The Matrix.nfo").write_text(
        '<movie><title>The Matrix</title><year>1999</year>'
        '<uniqueid type="tmdb">603</uniqueid>'
        '<uniqueid type="imdb">tt0133093</uniqueid></movie>'
    )
    (matrix / "The Matrix-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (matrix / "The Matrix-landscape.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    actors = matrix / ".actors"
    actors.mkdir()
    (actors / "Keanu Reeves.jpg").write_bytes(b"\x00" * 50)
    (matrix / ".DS_Store").write_bytes(b"\x00" * 10)

    # --- Movie: incomplete (no NFO, bad naming) ---
    incomplete = disk / "films" / "Incomplete Movie"
    incomplete.mkdir(parents=True)
    (incomplete / "movie.mkv").write_bytes(b"\x00" * 1000)

    # --- TV Show ---
    fallout = disk / "series" / "Fallout (2024)"
    fallout.mkdir(parents=True)
    (fallout / "tvshow.nfo").write_text(
        '<tvshow><title>Fallout</title>'
        '<uniqueid type="tmdb">106379</uniqueid></tvshow>'
    )
    (fallout / "poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (fallout / "season01-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    s01 = fallout / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 2000)
    (s01 / "S01E01 - The Beginning.nfo").write_text(
        "<episodedetails><title>The Beginning</title></episodedetails>"
    )
    (s01 / "S01E02 - The End.mkv").write_bytes(b"\x00" * 2000)
    show_actors = fallout / ".actors"
    show_actors.mkdir()
    (show_actors / "Ella Purnell.jpg").write_bytes(b"\x00" * 50)
    (fallout / "empty_release_dir").mkdir()

    # Build config
    config = MagicMock()
    config.path = disk
    config.name = "Disk1"
    config.categories = ["films", "series"]

    return {
        "disk": disk,
        "config": config,
        "matrix": matrix,
        "incomplete": incomplete,
        "fallout": fallout,
    }


class TestScanIntegration:
    """Integration test for library-scan."""

    def test_scan_finds_all_items(self, mini_library) -> None:
        """Scan should find 2 movies + 1 TV show = 3 items."""
        from personalscraper.library.scanner import scan_library

        result = scan_library([mini_library["config"]])

        assert result.item_count == 3
        titles = {i.title for i in result.items}
        assert "The Matrix" in titles
        assert "Incomplete Movie" in titles
        assert "Fallout" in titles

    def test_scan_detects_issues(self, mini_library) -> None:
        """Scan should detect .actors, junk files, bad naming."""
        from personalscraper.library.models import (
            ISSUE_ACTORS_DIR,
            ISSUE_BAD_DIR_NAME,
            ISSUE_JUNK_FILES,
        )
        from personalscraper.library.scanner import scan_library

        result = scan_library([mini_library["config"]])

        # Matrix: .actors + .DS_Store
        matrix_item = next(i for i in result.items if i.title == "The Matrix")
        assert ISSUE_ACTORS_DIR in matrix_item.issues
        assert ISSUE_JUNK_FILES in matrix_item.issues

        # Incomplete: bad naming (no year)
        incomplete_item = next(i for i in result.items if i.title == "Incomplete Movie")
        assert ISSUE_BAD_DIR_NAME in incomplete_item.issues

    def test_scan_detects_seasons(self, mini_library) -> None:
        """TV show scan should find season structure."""
        from personalscraper.library.scanner import scan_library

        result = scan_library([mini_library["config"]])

        fallout = next(i for i in result.items if i.title == "Fallout")
        assert fallout.seasons is not None
        assert len(fallout.seasons) == 1
        assert fallout.seasons[0].number == 1
        assert fallout.seasons[0].episode_count == 2
        assert fallout.seasons[0].episodes_with_nfo == 1  # only S01E01 has NFO

    def test_scan_json_roundtrip(self, mini_library, tmp_path) -> None:
        """Scan result should survive JSON serialization."""
        from personalscraper.library.models import read_json, write_json
        from personalscraper.library.scanner import scan_library

        result = scan_library([mini_library["config"]])
        json_path = tmp_path / "scan.json"
        write_json(result, json_path)
        data = read_json(json_path)

        assert data["item_count"] == 3
        assert len(data["items"]) == 3


class TestCleanIntegration:
    """Integration test for library-clean."""

    def test_clean_actors_apply(self, mini_library) -> None:
        """Clean should remove .actors/ directories."""
        from personalscraper.library.disk_cleaner import clean_library

        result = clean_library([mini_library["config"]], apply=True, only="actors")

        assert result.deleted_count == 2  # Matrix + Fallout .actors
        assert not (mini_library["matrix"] / ".actors").exists()
        assert not (mini_library["fallout"] / ".actors").exists()

    def test_clean_junk_apply(self, mini_library) -> None:
        """Clean should remove .DS_Store files."""
        from personalscraper.library.disk_cleaner import clean_library

        result = clean_library([mini_library["config"]], apply=True, only="junk")

        assert not (mini_library["matrix"] / ".DS_Store").exists()

    def test_clean_dry_run_preserves(self, mini_library) -> None:
        """Dry-run should not delete anything."""
        from personalscraper.library.disk_cleaner import clean_library

        result = clean_library([mini_library["config"]], apply=False)

        assert result.dry_run is True
        assert result.deleted_count > 0  # counted
        assert (mini_library["matrix"] / ".actors").exists()  # preserved
        assert (mini_library["matrix"] / ".DS_Store").exists()  # preserved


class TestValidateIntegration:
    """Integration test for library-validate."""

    def test_validate_complete_movie_valid(self, mini_library) -> None:
        """Complete movie should pass validation."""
        from personalscraper.library.validator import validate_library

        result = validate_library([mini_library["config"]])

        matrix = next(i for i in result.items if i.title == "The Matrix")
        assert matrix.status == "valid"

    def test_validate_incomplete_movie_blocked(self, mini_library) -> None:
        """Movie without NFO should be blocked."""
        from personalscraper.library.validator import validate_library

        result = validate_library([mini_library["config"]])

        incomplete = next(i for i in result.items if i.title == "Incomplete Movie")
        assert incomplete.status == "blocked"
        assert "nfo_present" in incomplete.errors


class TestRecommendIntegration:
    """Integration test for library-recommend."""

    def test_recommend_from_analysis(self) -> None:
        """Recommendations should be generated from analysis data."""
        from personalscraper.library.models import (
            AudioTrack,
            LibraryAnalysisItem,
            MediaFileAnalysis,
            SubtitleTrack,
            VideoInfo,
        )
        from personalscraper.library.preferences import LibraryPreferences, VideoPreferences
        from personalscraper.library.recommender import generate_recommendations

        # H.264 movie at 8 GB — should trigger codec + size recommendations
        items = [LibraryAnalysisItem(
            path="/tmp/BigMovie (2024)", disk="Disk1", category="films",
            media_type="movie", title="BigMovie", year=2024,
            files=[MediaFileAnalysis(
                path="/tmp/BigMovie (2024)/BigMovie.mkv",
                size_gb=8.0, duration_seconds=7200,
                video=VideoInfo(codec="h264", width=1920, height=1080,
                                bitrate_kbps=10000, hdr=False, hdr_type=None),
                audio_tracks=[AudioTrack(codec="ac3", language="fra", channels=6,
                                         is_atmos=False, is_default=True)],
                subtitle_tracks=[],
                audio_profile="vf", subtitle_languages=[],
                analyzed_at="2026-04-15T12:00:00",
            )],
        )]

        prefs = LibraryPreferences(video=VideoPreferences(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)

        assert result.total_recommendations == 1
        rec = result.items[0]
        assert rec.priority == "high"  # 8 GB > 2×4 GB
        assert rec.estimated_savings_gb is not None
        assert rec.estimated_savings_gb > 0


class TestReportIntegration:
    """Integration test for library-report."""

    def test_report_from_scan_data(self, mini_library, tmp_path) -> None:
        """Report should aggregate scan data correctly."""
        from personalscraper.library.models import read_json, write_json
        from personalscraper.library.reporter import generate_report
        from personalscraper.library.scanner import scan_library

        # Scan first
        scan_result = scan_library([mini_library["config"]])
        scan_path = tmp_path / "scan.json"
        write_json(scan_result, scan_path)
        scan_data = read_json(scan_path)

        # Generate report
        report = generate_report(scan_data=scan_data)

        assert report.total_items == 3
        assert report.items_per_disk["Disk1"] == 3
        assert report.actors_dir_count == 2  # Matrix + Fallout
        assert report.nfo_valid_count >= 2  # Matrix + Fallout have valid NFOs


class TestFullWorkflow:
    """Test the full scan → clean → validate chain."""

    def test_clean_then_rescan_shows_fewer_issues(self, mini_library, tmp_path) -> None:
        """After cleaning, a rescan should show fewer issues."""
        from personalscraper.library.disk_cleaner import clean_library
        from personalscraper.library.models import ISSUE_ACTORS_DIR, ISSUE_JUNK_FILES
        from personalscraper.library.scanner import scan_library

        # Initial scan
        scan1 = scan_library([mini_library["config"]])
        issues1 = sum(len(i.issues) for i in scan1.items)

        # Clean
        clean_library([mini_library["config"]], apply=True)

        # Rescan
        scan2 = scan_library([mini_library["config"]])
        issues2 = sum(len(i.issues) for i in scan2.items)

        # .actors and .DS_Store issues should be gone
        assert issues2 < issues1

        matrix = next(i for i in scan2.items if i.title == "The Matrix")
        assert ISSUE_ACTORS_DIR not in matrix.issues
        assert ISSUE_JUNK_FILES not in matrix.issues
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/library/test_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass, 0 regressions

- [ ] **Step 4: Commit**

```bash
git add tests/library/test_integration.py
git commit -m "v14.9.1: Add E2E integration tests — scan/clean/validate/recommend/report chain"
```

---

## Task 2: Verify final test count and acceptance

- [ ] **Step 1: Run full test suite with count**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -5`
Expected: All pass, count should be ~1130+ (1092 baseline + ~40 new V14 tests)

- [ ] **Step 2: Verify all 6 commands have --help**

```bash
personalscraper library-scan --help
personalscraper library-clean --help
personalscraper library-validate --help
personalscraper library-analyze --help
personalscraper library-recommend --help
personalscraper library-report --help
```

Expected: All display Rich-formatted help with options and examples.

- [ ] **Step 3: Final commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v14.9.2: V14 complete — 6 library commands, full test coverage"
```

---

## Acceptance Criteria — Phase 9 (and V14 overall)

- [ ] Integration tests verify: scan → clean → rescan shows fewer issues
- [ ] Integration tests verify: validate detects valid and blocked items
- [ ] Integration tests verify: recommend generates prioritized list from analysis
- [ ] Integration tests verify: report aggregates scan data correctly
- [ ] Integration tests verify: JSON roundtrip for all data files
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
- [ ] All 6 `library-*` commands functional with `--help`
- [ ] CLAUDE.md, MANUAL.md, ROADMAP.md up to date
- [ ] All V14 acceptance criteria from design spec met (14 criteria)
