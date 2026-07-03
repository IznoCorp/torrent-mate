"""Tests for whole-season single-file ("Intégrale"/"Complete") handling.

Covers the 4-gate detection (marker, season-only/no-episode, exactly one video
for the season, provider has that season's episodes), the regression guarantees
(a file failing ANY gate keeps the pre-existing skip behavior), the SxxE01-Eyy
range rename, and that verify's widened episode regex accepts the range name.
"""

import re
from pathlib import Path

import pytest

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.episode_manager import (
    _extract_season_episode_range,
    _extract_season_only,
    _file_season,
    _has_season_pack_marker,
    _try_season_pack_match,
    match_episode_files,
    rename_episodes,
)

MARKERS = ["integrale", "integral", "complete", "complet", "coffret"]
# Provider episode map for a 2-episode season 1.
API_S1_2EP = {(1, 1): {"title": "Ep1"}, (1, 2): {"title": "Ep2"}}


# ---------------------------------------------------------------------------
# Marker + season-only extraction
# ---------------------------------------------------------------------------


class TestMarkerAndSeasonExtraction:
    """Marker detection (accent/case) + season-only extraction."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("SAV.Integrale.S01.mkv", True),
            ("SAV.Intégrale.S01.mkv", True),  # accent
            ("Show.COMPLETE.S02.mkv", True),  # case
            ("Show.Coffret.S01.mkv", True),
            ("Show.S01E01 - Title.mkv", False),  # normal episode, no marker
            ("Show.S01.mkv", False),  # season, no marker
            ("Show.S01.Sample.mkv", False),  # sample, no marker
        ],
    )
    def test_has_season_pack_marker(self, name: str, expected: bool) -> None:
        """Marker is matched accent/case-insensitively as a delimited token."""
        assert _has_season_pack_marker(name, MARKERS) is expected

    def test_extract_season_only_ignores_real_episode(self) -> None:
        """A normal SxxExx name yields no season-only number (that's the ep matcher's job)."""
        assert _extract_season_only("Show.S01E01.mkv") is None

    def test_extract_season_only_finds_bare_season(self) -> None:
        """A season-without-episode name yields the season number."""
        assert _extract_season_only("SAV.Integrale.S01.FRENCH.mkv") == 1
        assert _extract_season_only("Show.Saison.3.mkv") == 3

    def test_file_season_prefers_episode_path(self) -> None:
        """_file_season resolves via SxxExx first, else the season-only token."""
        assert _file_season("Show.S02E05.mkv") == 2
        assert _file_season("Show.Integrale.S04.mkv") == 4


# ---------------------------------------------------------------------------
# 4-gate detection + regression
# ---------------------------------------------------------------------------


class TestSeasonPackDetection:
    """_try_season_pack_match applies all four gates; any failure => None."""

    def test_all_gates_pass_yields_range(self) -> None:
        """Genuine Intégrale single file with provider episodes -> range match."""
        f = Path("SAV.des.emissions.Integrale.S01.FRENCH.DVDRiP.x264-Duc_hesse.mkv")
        m = _try_season_pack_match(f, [f], API_S1_2EP, MARKERS)
        assert m is not None
        assert m["season"] == 1
        assert m["episode"] == 1
        assert m["episode_end"] == 2
        assert m["is_season_pack"] is True
        assert m["covered_episodes"] == [1, 2]
        assert len(m["covered_episode_infos"]) == 2

    def test_gate1_no_marker_skipped(self) -> None:
        """No complete-season marker -> None (a plain Show.S01.mkv is untouched)."""
        f = Path("Show.S01.mkv")
        assert _try_season_pack_match(f, [f], API_S1_2EP, MARKERS) is None

    def test_gate1_sample_skipped(self) -> None:
        """A sample file (no marker) -> None."""
        f = Path("Show.S01.Sample.mkv")
        assert _try_season_pack_match(f, [f], API_S1_2EP, MARKERS) is None

    def test_gate2_real_episode_not_a_pack(self) -> None:
        """A normal SxxExx file is not a season pack (has an episode number)."""
        f = Path("Show.Integrale.S01E01.mkv")  # marker present but real episode
        assert _try_season_pack_match(f, [f], API_S1_2EP, MARKERS) is None

    def test_gate3_multiple_videos_for_season_skipped(self) -> None:
        """More than one video for the season -> not a pack (they're episodes)."""
        files = [Path("Show.Integrale.S01.part1.mkv"), Path("Show.Integrale.S01.part2.mkv")]
        assert _try_season_pack_match(files[0], files, API_S1_2EP, MARKERS) is None

    def test_gate4_no_provider_episodes_skipped(self) -> None:
        """Provider has no episodes for the season -> cannot derive range -> None."""
        f = Path("Show.Integrale.S01.mkv")
        assert _try_season_pack_match(f, [f], {}, MARKERS) is None

    def test_range_derives_from_provider_episode_count(self) -> None:
        """The range end follows the provider's last episode number."""
        f = Path("Show.Integrale.S02.mkv")
        api = {(2, e): {"title": f"E{e}"} for e in range(1, 7)}  # 6 episodes
        m = _try_season_pack_match(f, [f], api, MARKERS)
        assert m is not None
        assert (m["episode"], m["episode_end"]) == (1, 6)


# ---------------------------------------------------------------------------
# match_episode_files integration + regression
# ---------------------------------------------------------------------------


class TestMatchEpisodeFilesSeasonPack:
    """The season-pack path only fires when markers are provided (policy on)."""

    def test_disabled_when_markers_none(self) -> None:
        """season_pack_markers=None -> the Intégrale file is skipped (pre-existing)."""
        f = Path("Show.Integrale.S01.mkv")
        matched = match_episode_files([f], API_S1_2EP, season_pack_markers=None)
        assert f not in matched

    def test_enabled_matches_season_pack(self) -> None:
        """With markers, a genuine season pack is range-matched."""
        f = Path("Show.Integrale.S01.mkv")
        matched = match_episode_files([f], API_S1_2EP, season_pack_markers=MARKERS)
        assert f in matched
        assert matched[f]["episode_end"] == 2

    def test_normal_episode_unaffected_by_markers(self) -> None:
        """A normal SxxExx file matches identically whether or not markers are set."""
        f = Path("Show.S01E01.mkv")
        without = match_episode_files([f], API_S1_2EP, season_pack_markers=None)
        with_markers = match_episode_files([f], API_S1_2EP, season_pack_markers=MARKERS)
        assert without[f]["episode"] == 1 and "episode_end" not in without[f]
        assert with_markers[f]["episode"] == 1 and "episode_end" not in with_markers[f]


# ---------------------------------------------------------------------------
# Range rename + verify pattern
# ---------------------------------------------------------------------------


class TestRangeRename:
    """rename_episodes places the pack in Saison XX/ with the SxxE01-Eyy name."""

    def test_rename_produces_range_name(self, tmp_path: Path) -> None:
        """A season-pack match renames to 'S01E01-E02 - Title.mkv' under Saison 01/."""
        show_dir = tmp_path / "SAV des émissions (2006)"
        show_dir.mkdir()
        video = show_dir / "SAV.Integrale.S01.mkv"
        video.write_bytes(b"x")
        matched = {
            video: {
                "season": 1,
                "episode": 1,
                "episode_end": 2,
                "api_title": "Intégrale",
                "is_season_pack": True,
            }
        }
        count = rename_episodes(matched, show_dir, NamingPatterns(), dry_run=False)
        assert count == 1
        dest = show_dir / "Saison 01" / "S01E01-E02 - Intégrale.mkv"
        assert dest.exists()

    def test_verify_pattern_accepts_range(self) -> None:
        """The widened verify episode regex accepts the range filename."""
        pattern = re.compile(r"^S\d{2}E\d{2}(?:-E\d{2,})?(?: - .+)?\.\w+$")
        assert pattern.match("S01E01-E02 - Intégrale.mkv")
        assert pattern.match("S02E01-E151 - Episode 1.mkv")  # 3-digit range end (daily show)
        assert pattern.match("S01E01 - Normal.mkv")  # normal still matches
        assert not pattern.match("S01E01-blah.mkv")  # malformed range rejected


# ---------------------------------------------------------------------------
# Idempotence: an already-ranged file must not collapse on re-scrape
# ---------------------------------------------------------------------------


class TestRangeReaffirmation:
    """A file already named SxxE01-Eyy is preserved as a range on re-scrape."""

    def test_extract_range_with_title(self) -> None:
        """Parse season, start, end, and title from a range stem."""
        assert _extract_season_episode_range("S02E01-E151 - Episode 1") == (2, 1, 151, "Episode 1")
        assert _extract_season_episode_range("S01E01-E02 - DVD.1") == (1, 1, 2, "DVD.1")

    def test_extract_range_none_for_single(self) -> None:
        """A normal single-episode stem is not a range."""
        assert _extract_season_episode_range("S02E01 - Foo") is None

    def test_reaffirm_preserves_range_even_when_disabled(self) -> None:
        """An already-ranged file stays a range even with markers=None (feature off)."""
        api = {(2, e): {"title": f"E{e}"} for e in range(1, 152)}
        f = Path("S02E01-E151 - Episode 1.mkv")
        matched = match_episode_files([f], api, season_pack_markers=None)
        assert f in matched
        assert matched[f]["episode"] == 1
        assert matched[f]["episode_end"] == 151
        assert matched[f]["is_season_pack"] is True

    def test_reaffirm_is_rename_noop(self, tmp_path: Path) -> None:
        """Re-affirming a range file already in Saison XX/ does not rename it."""
        show_dir = tmp_path / "Show (2006)"
        (show_dir / "Saison 02").mkdir(parents=True)
        video = show_dir / "Saison 02" / "S02E01-E151 - Episode 1.mkv"
        video.write_bytes(b"x")
        matched = {
            video: {
                "season": 2,
                "episode": 1,
                "episode_end": 151,
                "api_title": "Episode 1",
                "is_season_pack": True,
            }
        }
        rename_episodes(matched, show_dir, NamingPatterns(), dry_run=False)
        # Same name, same place — no collapse to S02E01.
        assert video.exists()
        assert not (show_dir / "Saison 02" / "S02E01 - Episode 1.mkv").exists()

    def test_normal_episode_not_reaffirmed_as_range(self) -> None:
        """A plain S02E01 file matches normally (no episode_end)."""
        api = {(2, 1): {"title": "Foo"}}
        f = Path("S02E01 - Foo.mkv")
        matched = match_episode_files([f], api, season_pack_markers=None)
        assert "episode_end" not in matched[f]
