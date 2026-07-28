"""Tests for personalscraper.sorter.game — game (disc-image) release detection.

Precision-first: ``is_game_release`` must return True for a genuine game release
(a disc image plus a game signal) and False for ANY media — especially a movie
disc image (BluRay/DVD .iso rip), which must never be mistaken for a game.
"""

from pathlib import Path

from personalscraper.sorter.game import is_game_release


def _mkdir_with(tmp_path: Path, folder: str, files: list[str]) -> Path:
    """Create ``folder`` under tmp_path holding empty ``files``; return its path."""
    d = tmp_path / folder
    d.mkdir()
    for name in files:
        (d / name).write_bytes(b"")
    return d


class TestIsGameRelease:
    """is_game_release — the precision-first game predicate."""

    def test_marvels_spiderman_iso_repack_group_is_game(self, tmp_path: Path):
        """ACC-01: the real terrain item (iso + repack group) is a game."""
        d = _mkdir_with(
            tmp_path,
            "Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto",
            ["Marvels.Spider-Man.2-Mephisto.iso", "msm2.nfo"],
        )
        assert is_game_release(d) is True

    def test_movie_bluray_iso_is_not_game(self, tmp_path: Path):
        """ACC-02: a movie disc image is never a game (anti-false-positive).

        A movie/TV disc image carries a video-release token (1080p/BluRay), which
        vetoes the game verdict.
        """
        d = _mkdir_with(
            tmp_path,
            "The.Matrix.1999.1080p.BluRay.x264-GROUP",
            ["The.Matrix.1999.1080p.BluRay.x264-GROUP.iso"],
        )
        assert is_game_release(d) is False

    def test_tvshow_folder_is_not_game(self, tmp_path: Path):
        """A TV release (season/episode markers + video child) is not a game."""
        d = _mkdir_with(
            tmp_path,
            "Show.S01.1080p.WEB-DL",
            ["Show.S01E01.mkv", "Show.S01E02.mkv"],
        )
        assert is_game_release(d) is False

    def test_ebook_folder_is_not_game(self, tmp_path: Path):
        """A folder with no disc image (an ebook) is not a game."""
        d = _mkdir_with(tmp_path, "Some.Book", ["book.pdf"])
        assert is_game_release(d) is False

    def test_bare_disc_image_without_game_signal_is_not_game(self, tmp_path: Path):
        """Precision: a disc image with NO game signal is not a game.

        No group/version/platform token → leave it visible for triage rather than
        hide it.
        """
        d = _mkdir_with(tmp_path, "backup", ["disc.iso"])
        assert is_game_release(d) is False

    def test_game_iso_with_trailing_repack_group_is_game(self, tmp_path: Path):
        """A known repack group in trailing release-group position is a game."""
        d = _mkdir_with(
            tmp_path,
            "Cyberpunk.2077.v2.1.0-RUNE",
            ["setup.iso"],
        )
        assert is_game_release(d) is True

    def test_version_token_alone_is_not_a_game(self, tmp_path: Path):
        """Precision: a bare vX.Y token is NOT a signal.

        Fan-edit disc rips are versioned; requiring a group/platform (not a bare
        version) keeps them visible.
        """
        d = _mkdir_with(tmp_path, "Cyberpunk.2077.v2.1.0.MULTi", ["setup.iso"])
        assert is_game_release(d) is False

    def test_game_iso_with_platform_token_is_game(self, tmp_path: Path):
        """A console-platform token is a sufficient game signal."""
        d = _mkdir_with(
            tmp_path,
            "Some.Game.PS4.FRENCH",
            ["game.iso"],
        )
        assert is_game_release(d) is True

    def test_playstation_token_not_read_as_tv_season(self, tmp_path: Path):
        """Regression: a PlayStation token is not read as a TV season.

        ``PS5`` embeds ``S5``; the season-pack TV-marker regex must not veto a
        PlayStation game as if it were TV Season 5 (platform tokens are stripped
        before the media vetoes).
        """
        d = _mkdir_with(
            tmp_path,
            "Spider-Man.Remastered.PS5.v1.002",
            ["spiderman.iso"],
        )
        assert is_game_release(d) is True

    def test_video_child_beats_disc_image(self, tmp_path: Path):
        """A video child vetoes the game verdict.

        A folder holding a real video file (even alongside an iso) is a media rip,
        not a game.
        """
        d = _mkdir_with(
            tmp_path,
            "Concert.2020-Mephisto",
            ["concert.mkv", "extras.iso"],
        )
        assert is_game_release(d) is False

    def test_missing_directory_is_not_game(self, tmp_path: Path):
        """Fail-soft: an unreadable/absent directory yields False, never raises."""
        assert is_game_release(tmp_path / "does-not-exist") is False


class TestPrecisionRegressions:
    """Real films whose TITLE contains a scene-group word must NOT be hidden.

    Regression for the PR #335 review BLOCKER: matching group tokens anywhere in
    the name misclassified title-only disc rips of real films (whose titles are
    also scene-group names) as games. Group tokens are now matched only in the
    trailing release-group position, so a title word is never a signal.
    """

    def test_the_matrix_reloaded_title_only_iso_is_not_game(self, tmp_path: Path):
        """`The Matrix Reloaded` (title word 'reloaded') is a film, not a game."""
        d = _mkdir_with(tmp_path, "The Matrix Reloaded", ["The Matrix Reloaded.iso"])
        assert is_game_release(d) is False

    def test_the_switch_title_only_iso_is_not_game(self, tmp_path: Path):
        """`The Switch` (2010) — 'switch' is no longer a platform token."""
        d = _mkdir_with(tmp_path, "The.Switch", ["The.Switch.iso"])
        assert is_game_release(d) is False

    def test_a_prophet_title_only_iso_is_not_game(self, tmp_path: Path):
        """`A Prophet` (title word 'prophet') is a film, not a game."""
        d = _mkdir_with(tmp_path, "A.Prophet", ["A.Prophet.iso"])
        assert is_game_release(d) is False

    def test_plaza_suite_title_only_iso_is_not_game(self, tmp_path: Path):
        """`Plaza Suite` (title word 'plaza') is a film, not a game."""
        d = _mkdir_with(tmp_path, "Plaza.Suite", ["Plaza.Suite.iso"])
        assert is_game_release(d) is False

    def test_fan_edit_versioned_disc_is_not_game(self, tmp_path: Path):
        """A versioned fan-edit disc rip (bare vX.Y, no group) stays visible."""
        d = _mkdir_with(tmp_path, "Blade.Runner.Final.Cut.v2.0", ["br.iso"])
        assert is_game_release(d) is False

    def test_despecialized_fan_edit_is_not_game(self, tmp_path: Path):
        """`Star Wars Despecialized v2.7` (fan edit, bare version) stays visible."""
        d = _mkdir_with(tmp_path, "Star.Wars.Despecialized.v2.7", ["sw.iso"])
        assert is_game_release(d) is False

    def test_group_word_in_trailing_position_is_a_game(self, tmp_path: Path):
        """The same word (RELOADED) IS a signal when it is the trailing group."""
        d = _mkdir_with(tmp_path, "Some.Game.2024-RELOADED", ["game.iso"])
        assert is_game_release(d) is True
