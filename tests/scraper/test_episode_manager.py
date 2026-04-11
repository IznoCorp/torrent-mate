"""Tests for episode management: season dirs, file matching, and renaming.

Tests cover season directory creation, S/E extraction from filenames,
episode-to-API matching, renaming with proper titles, subtitle handling,
and dry-run mode. Uses tmp_path for filesystem operations.
"""

from pathlib import Path

import pytest

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.episode_manager import (
    _extract_season_episode,
    create_season_dirs,
    match_episode_files,
    rename_episodes,
)


@pytest.fixture
def patterns() -> NamingPatterns:
    """Create a NamingPatterns instance."""
    return NamingPatterns()


# ---------------------------------------------------------------------------
# S/E extraction tests
# ---------------------------------------------------------------------------

class TestExtractSeasonEpisode:
    """Tests for _extract_season_episode regex parsing."""

    def test_standard_format(self) -> None:
        """Should parse S01E04."""
        assert _extract_season_episode("Show.S01E04.720p.mkv") == (1, 4)

    def test_lowercase(self) -> None:
        """Should parse s03e12."""
        assert _extract_season_episode("show.s03e12.hdtv.avi") == (3, 12)

    def test_x_format(self) -> None:
        """Should parse 2x05."""
        assert _extract_season_episode("Show.2x05.avi") == (2, 5)

    def test_double_episode(self) -> None:
        """Should return first episode from S02E01E02."""
        assert _extract_season_episode("Show.S02E01E02.mkv") == (2, 1)

    def test_no_match(self) -> None:
        """Should return (None, None) for non-episodic names."""
        assert _extract_season_episode("Movie.2024.1080p.mkv") == (None, None)

    def test_high_episode_number(self) -> None:
        """Should handle high episode numbers."""
        assert _extract_season_episode("Show.S01E100.mkv") == (1, 100)

    def test_already_renamed(self) -> None:
        """Should parse already-renamed format: S01E01 - Title."""
        assert _extract_season_episode("S01E01 - La Fin.mkv") == (1, 1)


# ---------------------------------------------------------------------------
# Season directory creation tests
# ---------------------------------------------------------------------------

class TestCreateSeasonDirs:
    """Tests for create_season_dirs."""

    def test_creates_season_dirs(self, tmp_path: Path, patterns: NamingPatterns) -> None:
        """Should create Saison XX/ directories."""
        episodes = [
            {"season_number": 1, "episode_number": 1},
            {"season_number": 1, "episode_number": 2},
            {"season_number": 2, "episode_number": 1},
        ]
        result = create_season_dirs(tmp_path, episodes, patterns)

        assert len(result) == 2
        assert (tmp_path / "Saison 01").exists()
        assert (tmp_path / "Saison 02").exists()

    def test_skips_existing(self, tmp_path: Path, patterns: NamingPatterns) -> None:
        """Should not fail on existing directories."""
        (tmp_path / "Saison 01").mkdir()
        episodes = [{"season_number": 1, "episode_number": 1}]

        result = create_season_dirs(tmp_path, episodes, patterns)
        assert len(result) == 1

    def test_skips_specials(self, tmp_path: Path, patterns: NamingPatterns) -> None:
        """Should skip season 0 (specials)."""
        episodes = [
            {"season_number": 0, "episode_number": 1},
            {"season_number": 1, "episode_number": 1},
        ]
        result = create_season_dirs(tmp_path, episodes, patterns)

        assert len(result) == 1
        assert not (tmp_path / "Saison 00").exists()

    def test_dry_run(self, tmp_path: Path, patterns: NamingPatterns) -> None:
        """Dry run should not create directories."""
        episodes = [{"season_number": 1, "episode_number": 1}]

        result = create_season_dirs(tmp_path, episodes, patterns, dry_run=True)
        assert len(result) == 1
        assert not (tmp_path / "Saison 01").exists()


# ---------------------------------------------------------------------------
# Episode file matching tests
# ---------------------------------------------------------------------------

class TestMatchEpisodeFiles:
    """Tests for match_episode_files."""

    def test_matches_standard_filenames(self, tmp_path: Path) -> None:
        """Should match S01E01 files to API data."""
        video1 = tmp_path / "Show.S01E01.720p.mkv"
        video2 = tmp_path / "Show.S01E02.720p.mkv"
        video1.touch()
        video2.touch()

        api_episodes = {
            (1, 1): "La Fin",
            (1, 2): "La Cible",
        }

        result = match_episode_files([video1, video2], api_episodes)

        assert len(result) == 2
        assert result[video1]["season"] == 1
        assert result[video1]["episode"] == 1
        assert result[video1]["api_title"] == "La Fin"

    def test_unmatched_episode_excluded(self, tmp_path: Path) -> None:
        """Episodes not in API should be excluded from results."""
        video = tmp_path / "Show.S01E99.mkv"
        video.touch()

        api_episodes = {(1, 1): "La Fin"}
        result = match_episode_files([video], api_episodes)

        assert len(result) == 0

    def test_unparseable_filename_excluded(self, tmp_path: Path) -> None:
        """Files without S/E pattern should be excluded."""
        video = tmp_path / "Movie.2024.mkv"
        video.touch()

        api_episodes = {(1, 1): "La Fin"}
        result = match_episode_files([video], api_episodes)

        assert len(result) == 0


# ---------------------------------------------------------------------------
# Episode renaming tests
# ---------------------------------------------------------------------------

class TestRenameEpisodes:
    """Tests for rename_episodes."""

    def test_renames_and_moves_to_season_dir(
        self, tmp_path: Path, patterns: NamingPatterns,
    ) -> None:
        """Should rename and move file to Saison XX/."""
        video = tmp_path / "Show.S01E01.720p.mkv"
        video.write_text("video content")

        matched = {
            video: {"season": 1, "episode": 1, "api_title": "La Fin"},
        }

        count = rename_episodes(matched, tmp_path, patterns)

        assert count == 1
        expected = tmp_path / "Saison 01" / "S01E01 - La Fin.mkv"
        assert expected.exists()
        assert not video.exists()

    def test_renames_subtitles(
        self, tmp_path: Path, patterns: NamingPatterns,
    ) -> None:
        """Should rename associated subtitle files."""
        video = tmp_path / "Show.S01E01.720p.mkv"
        video.write_text("video")
        sub_fr = tmp_path / "Show.S01E01.720p.fra.srt"
        sub_fr.write_text("subtitle fr")
        sub_en = tmp_path / "Show.S01E01.720p.en.srt"
        sub_en.write_text("subtitle en")

        matched = {
            video: {"season": 1, "episode": 1, "api_title": "La Fin"},
        }

        rename_episodes(matched, tmp_path, patterns)

        season_dir = tmp_path / "Saison 01"
        # Subtitles should be renamed with the same base name
        expected_fr = season_dir / "S01E01 - La Fin.fra.srt"
        expected_en = season_dir / "S01E01 - La Fin.en.srt"
        assert expected_fr.exists()
        assert expected_en.exists()

    def test_dry_run_no_rename(
        self, tmp_path: Path, patterns: NamingPatterns,
    ) -> None:
        """Dry run should not move or rename files."""
        video = tmp_path / "Show.S01E01.720p.mkv"
        video.write_text("video")

        matched = {
            video: {"season": 1, "episode": 1, "api_title": "La Fin"},
        }

        count = rename_episodes(matched, tmp_path, patterns, dry_run=True)

        assert count == 1  # Counted but not moved
        assert video.exists()  # Still in original location
        assert not (tmp_path / "Saison 01").exists()

    def test_already_correctly_named(
        self, tmp_path: Path, patterns: NamingPatterns,
    ) -> None:
        """Should count already-renamed episodes without moving them."""
        season_dir = tmp_path / "Saison 01"
        season_dir.mkdir()
        video = season_dir / "S01E01 - La Fin.mkv"
        video.write_text("video")

        matched = {
            video: {"season": 1, "episode": 1, "api_title": "La Fin"},
        }

        count = rename_episodes(matched, tmp_path, patterns)
        assert count == 1
        assert video.exists()


# ---------------------------------------------------------------------------
# End-to-end test with realistic structure
# ---------------------------------------------------------------------------

class TestEpisodeRenameE2E:
    """End-to-end test with realistic TV show directory structure."""

    def test_full_rename_workflow(
        self, tmp_path: Path, patterns: NamingPatterns,
    ) -> None:
        """Test complete workflow: season dirs → match → rename."""
        # Set up: show directory with torrent-named files
        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        # Create video files with typical torrent naming
        for i in range(1, 5):
            (show_dir / f"Fallout.S01E{i:02d}.2160p.WEB-DL.DDP5.1.Atmos.DV.H265.mkv").write_text(f"ep{i}")
            # Add a subtitle
            (show_dir / f"Fallout.S01E{i:02d}.2160p.WEB-DL.DDP5.1.Atmos.DV.H265.fra.srt").write_text(f"sub{i}")

        # API episode data
        api_episodes = {
            (1, 1): "La Fin",
            (1, 2): "La Cible",
            (1, 3): "La Tête",
            (1, 4): "Les Goules",
        }

        # Step 1: Create season directories
        episodes = [{"season_number": 1, "episode_number": i} for i in range(1, 5)]
        season_dirs = create_season_dirs(show_dir, episodes, patterns)
        assert len(season_dirs) == 1
        assert (show_dir / "Saison 01").exists()

        # Step 2: Collect video files
        video_files = sorted(
            f for f in show_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".mkv"
        )
        assert len(video_files) == 4

        # Step 3: Match files to API
        matched = match_episode_files(video_files, api_episodes)
        assert len(matched) == 4

        # Step 4: Rename
        count = rename_episodes(matched, show_dir, patterns)
        assert count == 4

        # Verify results
        season_dir = show_dir / "Saison 01"
        assert (season_dir / "S01E01 - La Fin.mkv").exists()
        assert (season_dir / "S01E02 - La Cible.mkv").exists()
        assert (season_dir / "S01E03 - La Tête.mkv").exists()
        assert (season_dir / "S01E04 - Les Goules.mkv").exists()

        # Subtitles renamed too
        assert (season_dir / "S01E01 - La Fin.fra.srt").exists()
        assert (season_dir / "S01E04 - Les Goules.fra.srt").exists()

        # Original files should be gone
        assert not any(f.suffix == ".mkv" for f in show_dir.iterdir() if f.is_file())

    def test_dry_run_no_changes(
        self, tmp_path: Path, patterns: NamingPatterns,
    ) -> None:
        """Dry run should leave everything untouched."""
        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        video = show_dir / "Show.S01E01.720p.mkv"
        video.write_text("video")

        episodes = [{"season_number": 1, "episode_number": 1}]
        create_season_dirs(show_dir, episodes, patterns, dry_run=True)

        api_episodes = {(1, 1): "Pilot"}
        video_files = [video]
        matched = match_episode_files(video_files, api_episodes)

        count = rename_episodes(matched, show_dir, patterns, dry_run=True)

        assert count == 1
        assert video.exists()  # Not moved
        assert not (show_dir / "Saison 01").exists()  # Not created

    def test_missing_api_episode_kept(
        self, tmp_path: Path, patterns: NamingPatterns,
    ) -> None:
        """Episode not in API should keep original name."""
        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        video_found = show_dir / "Show.S01E01.mkv"
        video_found.write_text("ep1")
        video_missing = show_dir / "Show.S01E99.mkv"
        video_missing.write_text("ep99")

        api_episodes = {(1, 1): "Pilot"}  # No S01E99
        matched = match_episode_files([video_found, video_missing], api_episodes)

        assert len(matched) == 1  # Only S01E01 matched
        assert video_missing not in matched

        # Rename only the matched one
        rename_episodes(matched, show_dir, patterns)

        # S01E99 still in original location
        assert video_missing.exists()
