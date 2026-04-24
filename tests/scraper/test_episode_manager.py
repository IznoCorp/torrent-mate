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
            (1, 1): {"title": "La Fin", "still_path": "/abc123.jpg"},
            (1, 2): {"title": "La Cible", "still_path": ""},
        }

        result = match_episode_files([video1, video2], api_episodes)

        assert len(result) == 2
        assert result[video1]["season"] == 1
        assert result[video1]["episode"] == 1
        assert result[video1]["api_title"] == "La Fin"
        assert result[video1]["still_path"] == "/abc123.jpg"
        assert result[video2]["still_path"] == ""

    def test_unmatched_episode_gets_synthetic_title(self, tmp_path: Path) -> None:
        """Parseable S/E absent from API → synthetic "Episode N" title + fallback flag.

        The season exists in the catalog but the specific episode does not
        (e.g. provider lags a freshly-aired E99). File is still moved under
        the labeled season, named with the configured default prefix.
        """
        video = tmp_path / "Show.S01E99.mkv"
        video.touch()

        api_episodes = {(1, 1): {"title": "La Fin", "still_path": ""}}
        result = match_episode_files([video], api_episodes)

        assert len(result) == 1
        assert result[video]["api_title"] == "Episode 99"
        assert result[video]["season"] == 1
        assert result[video]["episode"] == 99
        assert result[video]["fallback"] is True

    def test_unmatched_episode_uses_configured_default_name(self, tmp_path: Path) -> None:
        """episode_default_name overrides the "Episode" prefix in synthetic titles."""
        video = tmp_path / "Show.S01E99.mkv"
        video.touch()

        api_episodes = {(1, 1): {"title": "La Fin", "still_path": ""}}
        result = match_episode_files([video], api_episodes, episode_default_name="Épisode")

        assert result[video]["api_title"] == "Épisode 99"
        assert result[video]["fallback"] is True

    def test_phantom_season_remaps_to_max_season(self, tmp_path: Path) -> None:
        """Phantom labeled season + episode exists in max_season → remap with title.

        Covers parallel-numbering spin-offs: a torrent tagged S17E08 against
        a show whose catalog is S01..S04 is remapped to (S04, E08) when the
        provider actually has an episode 8 in its latest season. Metadata
        (title) from the provider is preserved.
        """
        video = tmp_path / "Show.S17E08.mkv"
        video.touch()

        # Catalog: S01..S04, each with E01..E08; labeled S17 is phantom.
        api_episodes = {
            (s, e): {"title": f"Ep S{s:02d}E{e:02d}", "still_path": ""} for s in range(1, 5) for e in range(1, 9)
        }
        result = match_episode_files([video], api_episodes)

        assert len(result) == 1
        # File is remapped to the max season (4), keeping the episode number.
        assert result[video]["season"] == 4
        assert result[video]["episode"] == 8
        assert result[video]["api_title"] == "Ep S04E08"
        assert result[video]["fallback"] is False

    def test_phantom_season_no_remap_uses_synthetic_title(self, tmp_path: Path) -> None:
        """Phantom season + episode not in max_season → synthetic title, keeps labeled season."""
        video = tmp_path / "Show.S17E08.mkv"
        video.touch()

        # Catalog only has S04 with E01..E07 (E08 hasn't aired yet per the API).
        api_episodes = {(4, e): {"title": f"Ep E{e:02d}", "still_path": ""} for e in range(1, 8)}
        result = match_episode_files([video], api_episodes)

        assert len(result) == 1
        # No remap possible → keep the labeled season, synthesize a title.
        assert result[video]["season"] == 17
        assert result[video]["episode"] == 8
        assert result[video]["api_title"] == "Episode 8"
        assert result[video]["fallback"] is True

    def test_direct_match_wins_over_phantom_heuristic(self, tmp_path: Path) -> None:
        """When the labeled (S, E) exists in the catalog, don't trigger remap."""
        video = tmp_path / "Show.S01E01.mkv"
        video.touch()

        api_episodes = {
            (1, 1): {"title": "Pilot S01", "still_path": ""},
            # S04E01 also exists — must NOT be chosen since S01E01 is a direct match.
            (4, 1): {"title": "S04 opener", "still_path": ""},
        }
        result = match_episode_files([video], api_episodes)

        assert result[video]["season"] == 1
        assert result[video]["api_title"] == "Pilot S01"
        assert result[video]["fallback"] is False

    def test_empty_api_episodes_triggers_plain_fallback(self, tmp_path: Path) -> None:
        """No catalog at all → synthetic title, labeled season preserved."""
        video = tmp_path / "Show.S03E05.mkv"
        video.touch()

        result = match_episode_files([video], {})

        assert result[video]["season"] == 3
        assert result[video]["episode"] == 5
        assert result[video]["api_title"] == "Episode 5"
        assert result[video]["fallback"] is True

    def test_unparseable_filename_excluded(self, tmp_path: Path) -> None:
        """Files without S/E pattern should be excluded."""
        video = tmp_path / "Movie.2024.mkv"
        video.touch()

        api_episodes = {(1, 1): {"title": "La Fin", "still_path": ""}}
        result = match_episode_files([video], api_episodes)

        assert len(result) == 0


# ---------------------------------------------------------------------------
# Episode renaming tests
# ---------------------------------------------------------------------------


class TestRenameEpisodes:
    """Tests for rename_episodes."""

    def test_renames_and_moves_to_season_dir(
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
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

    def test_moves_synthetic_title_fallback_to_season_dir(
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
    ) -> None:
        """Fallback entries (synthetic "Episode N" title) are moved like real ones.

        The file must land in Saison XX/ as "SxxExx - Episode N.ext" so verify
        doesn't block dispatch. The synthetic title is produced by
        ``match_episode_files`` from the configured ``episode_default_name``.
        """
        video = tmp_path / "Show.S17E08.FRENCH.1080p.mkv"
        video.write_text("video content")

        matched = {
            video: {"season": 17, "episode": 8, "api_title": "Episode 8", "fallback": True},
        }

        count = rename_episodes(matched, tmp_path, patterns)

        assert count == 1
        expected = tmp_path / "Saison 17" / "S17E08 - Episode 8.mkv"
        assert expected.exists()
        assert not video.exists()

    def test_renames_subtitles(
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
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
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
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
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
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
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
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
            (1, 1): {"title": "La Fin", "still_path": ""},
            (1, 2): {"title": "La Cible", "still_path": ""},
            (1, 3): {"title": "La Tête", "still_path": ""},
            (1, 4): {"title": "Les Goules", "still_path": ""},
        }

        # Step 1: Create season directories
        episodes = [{"season_number": 1, "episode_number": i} for i in range(1, 5)]
        season_dirs = create_season_dirs(show_dir, episodes, patterns)
        assert len(season_dirs) == 1
        assert (show_dir / "Saison 01").exists()

        # Step 2: Collect video files
        video_files = sorted(f for f in show_dir.iterdir() if f.is_file() and f.suffix.lower() == ".mkv")
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
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
    ) -> None:
        """Dry run should leave everything untouched."""
        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        video = show_dir / "Show.S01E01.720p.mkv"
        video.write_text("video")

        episodes = [{"season_number": 1, "episode_number": 1}]
        create_season_dirs(show_dir, episodes, patterns, dry_run=True)

        api_episodes = {(1, 1): {"title": "Pilot", "still_path": ""}}
        video_files = [video]
        matched = match_episode_files(video_files, api_episodes)

        count = rename_episodes(matched, show_dir, patterns, dry_run=True)

        assert count == 1
        assert video.exists()  # Not moved
        assert not (show_dir / "Saison 01").exists()  # Not created

    def test_missing_api_episode_moved_with_synthetic_title(
        self,
        tmp_path: Path,
        patterns: NamingPatterns,
    ) -> None:
        """Episode with S/E in filename but absent from API is still moved.

        Gets a synthetic "Episode N" title (configurable prefix) and is flagged
        as fallback so NFO generation can skip it. The file lands under its
        labeled season — verify/dispatch don't block on a stranded root mkv.
        """
        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        video_found = show_dir / "Show.S01E01.mkv"
        video_found.write_text("ep1")
        video_missing = show_dir / "Show.S01E99.mkv"
        video_missing.write_text("ep99")

        api_episodes = {(1, 1): {"title": "Pilot", "still_path": ""}}  # No S01E99
        matched = match_episode_files([video_found, video_missing], api_episodes)

        # Both files are included — the missing one with a synthetic title.
        assert len(matched) == 2
        assert matched[video_missing]["api_title"] == "Episode 99"
        assert matched[video_missing]["fallback"] is True
        assert matched[video_found]["api_title"] == "Pilot"
        assert matched[video_found]["fallback"] is False

        rename_episodes(matched, show_dir, patterns)

        # Matched file: renamed with real title.
        assert (show_dir / "Saison 01" / "S01E01 - Pilot.mkv").exists()
        # Fallback file: moved to Saison 01/ with synthetic title.
        assert (show_dir / "Saison 01" / "S01E99 - Episode 99.mkv").exists()
        # Original root files are gone.
        assert not video_found.exists()
        assert not video_missing.exists()
