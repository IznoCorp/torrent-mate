"""Tests for personalscraper.naming_patterns — MediaElch-compatible naming."""

import pytest

from personalscraper.naming_patterns import PATTERNS, SEASON_DIR_RE, NamingPatterns

# --- NamingPatterns dataclass ---


class TestNamingPatterns:
    """NamingPatterns dataclass structure and defaults."""

    def test_frozen(self):
        """NamingPatterns is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            PATTERNS.movie_dir = "changed"  # type: ignore[misc]

    def test_singleton_patterns(self):
        """PATTERNS is a module-level singleton."""
        assert isinstance(PATTERNS, NamingPatterns)


# --- format() templating ---


class TestFormat:
    """NamingPatterns.format() — pattern templating."""

    def test_movie_dir(self):
        """Movie directory: 'Title (Year)'."""
        assert PATTERNS.format("movie_dir", Title="The Matrix", Year=1999) == "The Matrix (1999)"

    def test_movie_nfo(self):
        """Movie NFO: 'Title.nfo'."""
        assert PATTERNS.format("movie_nfo", Title="The Matrix") == "The Matrix.nfo"

    def test_movie_poster(self):
        """Movie poster: 'Title-poster.jpg'."""
        assert PATTERNS.format("movie_poster", Title="The Matrix") == "The Matrix-poster.jpg"

    def test_movie_fanart(self):
        """Movie fanart: 'Title-fanart.jpg'."""
        assert PATTERNS.format("movie_fanart", Title="The Matrix") == "The Matrix-fanart.jpg"

    @pytest.mark.parametrize("pattern_name,suffix", [
        ("movie_banner", "-banner.jpg"),
        ("movie_clearlogo", "-clearlogo.png"),
        ("movie_clearart", "-clearart.png"),
        ("movie_discart", "-discart.png"),
        ("movie_landscape", "-landscape.jpg"),
    ])
    def test_movie_artwork_patterns(self, pattern_name, suffix):
        """All movie artwork uses Title-suffix format."""
        result = PATTERNS.format(pattern_name, Title="Test Movie")
        assert result == f"Test Movie{suffix}"

    def test_tvshow_nfo(self):
        """TV show NFO is a fixed name."""
        assert PATTERNS.tvshow_nfo == "tvshow.nfo"

    @pytest.mark.parametrize("pattern_name,expected", [
        ("tvshow_poster", "poster.jpg"),
        ("tvshow_fanart", "fanart.jpg"),
        ("tvshow_banner", "banner.jpg"),
        ("tvshow_clearlogo", "clearlogo.png"),
        ("tvshow_clearart", "clearart.png"),
        ("tvshow_characterart", "characterart.png"),
        ("tvshow_landscape", "landscape.jpg"),
    ])
    def test_tvshow_fixed_names(self, pattern_name, expected):
        """TV show artwork uses fixed names (no title prefix)."""
        assert getattr(PATTERNS, pattern_name) == expected

    def test_season_dir_french(self):
        """Season directories use French naming: 'Saison 01'."""
        assert PATTERNS.format("season_dir", Season=1) == "Saison 01"
        assert PATTERNS.format("season_dir", Season=3) == "Saison 03"
        assert PATTERNS.format("season_dir", Season=12) == "Saison 12"

    def test_season_poster(self):
        """Season poster: 'season01-poster.jpg'."""
        assert PATTERNS.format("season_poster", Season=1) == "season01-poster.jpg"
        assert PATTERNS.format("season_poster", Season=3) == "season03-poster.jpg"

    def test_episode_video(self):
        """Episode video: 'S01E01 - Episode Title'."""
        result = PATTERNS.format("episode_video", Season=1, Episode=1, EpisodeTitle="Pilot")
        assert result == "S01E01 - Pilot"

    def test_episode_nfo(self):
        """Episode NFO: 'S01E01 - Episode Title.nfo'."""
        result = PATTERNS.format("episode_nfo", Season=3, Episode=7, EpisodeTitle="Title Here")
        assert result == "S03E07 - Title Here.nfo"

    def test_episode_thumb(self):
        """Episode thumb: 'S01E01 - Episode Title-thumb.jpg'."""
        result = PATTERNS.format("episode_thumb", Season=1, Episode=4, EpisodeTitle="Pilot")
        assert result == "S01E04 - Pilot-thumb.jpg"

    def test_format_base_filename_movie(self):
        """Base filename for movies is just the title."""
        assert PATTERNS.format_base_filename(is_episode=False, Title="The Matrix") == "The Matrix"

    def test_format_base_filename_episode(self):
        """Base filename for episodes is S01E01 - Title."""
        result = PATTERNS.format_base_filename(
            is_episode=True, Season=3, Episode=7, EpisodeTitle="Test"
        )
        assert result == "S03E07 - Test"

    def test_invalid_pattern_raises(self):
        """Accessing non-existent pattern raises AttributeError."""
        with pytest.raises(AttributeError):
            PATTERNS.format("nonexistent_pattern", Title="X")


# --- MediaElch conformity tests ---


class TestMediaElchConformity:
    """Verify patterns match real MediaElch output from 001-MOVIES/ and 002-TVSHOWS/."""

    def test_real_movie_the_piano_lesson(self):
        """Matches real files in '001-MOVIES/The Piano Lesson (2024)/'."""
        title = "The Piano Lesson"
        assert PATTERNS.format("movie_dir", Title=title, Year=2024) == "The Piano Lesson (2024)"
        assert PATTERNS.format("movie_nfo", Title=title) == "The Piano Lesson.nfo"
        assert PATTERNS.format("movie_poster", Title=title) == "The Piano Lesson-poster.jpg"
        assert PATTERNS.format("movie_fanart", Title=title) == "The Piano Lesson-fanart.jpg"

    def test_real_movie_french_title(self):
        """Matches real files for French movie titles with accents."""
        title = "Gérald le Conquérant"
        assert PATTERNS.format("movie_nfo", Title=title) == "Gérald le Conquérant.nfo"
        assert PATTERNS.format("movie_poster", Title=title) == "Gérald le Conquérant-poster.jpg"
        assert PATTERNS.format("movie_clearlogo", Title=title) == "Gérald le Conquérant-clearlogo.png"
        assert PATTERNS.format("movie_landscape", Title=title) == "Gérald le Conquérant-landscape.jpg"

    def test_real_tvshow_shrinking(self):
        """Matches real files in '002-TVSHOWS/Shrinking (2023)/'."""
        assert PATTERNS.tvshow_nfo == "tvshow.nfo"
        assert PATTERNS.tvshow_poster == "poster.jpg"
        assert PATTERNS.tvshow_fanart == "fanart.jpg"
        assert PATTERNS.format("season_poster", Season=3) == "season03-poster.jpg"
        assert PATTERNS.format("season_dir", Season=3) == "Saison 03"

    def test_real_tvshow_fallout(self):
        """Matches real files in '002-TVSHOWS/Fallout (2024)/' (full artwork set)."""
        assert PATTERNS.tvshow_banner == "banner.jpg"
        assert PATTERNS.tvshow_clearlogo == "clearlogo.png"
        assert PATTERNS.tvshow_clearart == "clearart.png"
        assert PATTERNS.tvshow_characterart == "characterart.png"
        assert PATTERNS.tvshow_landscape == "landscape.jpg"
        assert PATTERNS.format("season_poster", Season=1) == "season01-poster.jpg"

    def test_real_episode_shrinking(self):
        """Matches real episode files from Shrinking S03."""
        # Real file: "S03E07 - « I will be grape ».nfo"
        result = PATTERNS.format(
            "episode_nfo", Season=3, Episode=7, EpisodeTitle="« I will be grape »"
        )
        assert result == "S03E07 - « I will be grape ».nfo"

        # Real file: "S03E08 - Régime dépression-thumb.jpg"
        result = PATTERNS.format(
            "episode_thumb", Season=3, Episode=8, EpisodeTitle="Régime dépression"
        )
        assert result == "S03E08 - Régime dépression-thumb.jpg"


# --- SEASON_DIR_RE regex ---


class TestSeasonDirRegex:
    """Tests for SEASON_DIR_RE — Saison directory matching with any digit count."""

    def test_single_digit_saison(self):
        """'Saison 1' (single digit) should match."""
        assert SEASON_DIR_RE.match("Saison 1")

    def test_two_digit_saison(self):
        """'Saison 01' (standard two digits) should match."""
        assert SEASON_DIR_RE.match("Saison 01")

    def test_three_digit_saison(self):
        """'Saison 100' (three digits, e.g. long-running anime) should match."""
        assert SEASON_DIR_RE.match("Saison 100")

    def test_non_saison_dir_rejected(self):
        """Random directory names should not match."""
        assert not SEASON_DIR_RE.match("Season 01")
        assert not SEASON_DIR_RE.match("S01")
        assert not SEASON_DIR_RE.match("Extras")

    def test_saison_without_number_rejected(self):
        """'Saison' alone (no number) should not match."""
        assert not SEASON_DIR_RE.match("Saison")
        assert not SEASON_DIR_RE.match("Saison ")
