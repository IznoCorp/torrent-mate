"""Tests for personalscraper.sorter.cleaner — NameCleaner via guessit."""

import pytest

from personalscraper.sorter.cleaner import NameCleaner


@pytest.fixture
def cleaner():
    """Provide a NameCleaner instance."""
    return NameCleaner()


# --- clean() ---


class TestClean:
    """NameCleaner.clean() — title extraction with season/episode preserved."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Real torrent names from torrents/complete/
            ("Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX", "Shrinking S03"),
            ("The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP.DDP5.1.x265-R3MiX", "The Boys S05E01"),
            ("The.Boys.S05E02.MULTi.DV.HDR.2160p.AMZN.WEBRiP.DDP5.1.x265-R3MiX", "The Boys S05E02"),
            (
                "Your.Friends.and.Neighbours.S02E01.MULTi.VFF.1080p.WEB.EAC3.5.1.Atmos.H265-TFA.mkv",
                "Your Friends and Neighbours S02E01",
            ),
            (
                "Jury.Duty.Presents.Company.Retreat.S01.MULTi.1080p.WEB.H264-FW",
                "Jury Duty Presents Company Retreat S01",
            ),
        ],
    )
    def test_real_torrent_names(self, cleaner, raw, expected):
        """Clean real torrent names from torrents/complete/."""
        assert cleaner.clean(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Movie with no season/episode
            ("Movie.Title.2024.1080p.BluRay.x264-GROUP", "Movie Title"),
            # Simple title
            ("Some.Movie.mkv", "Some Movie"),
        ],
    )
    def test_movie_names(self, cleaner, raw, expected):
        """Movies return title only (no S/E code)."""
        assert cleaner.clean(raw) == expected

    def test_unknown_name_returns_as_is(self, cleaner):
        """If guessit can't parse, returns original name as title."""
        result = cleaner.clean("xyz")
        assert isinstance(result, str)
        assert len(result) > 0


# --- extract_year() ---


class TestExtractYear:
    """NameCleaner.extract_year() — year detection via guessit."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Movie.Title.2024.1080p.BluRay", 2024),
            ("Blade.Runner.2049.2017.1080p", 2017),
            ("The.Piano.Lesson.2024.mkv", 2024),
            ("La.Femme.de.menage.2025.FRENCH", 2025),
        ],
    )
    def test_year_extraction(self, cleaner, raw, expected):
        """Extracts release year from various naming formats."""
        assert cleaner.extract_year(raw) == expected

    def test_no_year(self, cleaner):
        """Returns None when no year is present."""
        assert cleaner.extract_year("Shrinking.S03.MULTi.1080p") is None

    def test_title_with_embedded_year(self, cleaner):
        """Titles containing years (2001, Se7en) should extract release year, not title year."""
        # guessit handles "2001 A Space Odyssey" — year is part of the title
        result = cleaner.extract_year("2001.A.Space.Odyssey.1968.BluRay")
        assert result == 1968


# --- extract_season_episode() ---


class TestExtractSeasonEpisode:
    """NameCleaner.extract_season_episode() — S/E detection."""

    @pytest.mark.parametrize(
        "raw,expected_season,expected_episode",
        [
            ("Show.S01E04.1080p.mkv", 1, 4),
            ("Show.s03e12.mkv", 3, 12),
            ("Show.1x04.mkv", 1, 4),
            ("Show.S03.MULTi.1080p", 3, None),
        ],
    )
    def test_standard_patterns(self, cleaner, raw, expected_season, expected_episode):
        """Detects standard S01E04, 1x04, and S03 patterns."""
        season, episode = cleaner.extract_season_episode(raw)
        assert season == expected_season
        assert episode == expected_episode

    def test_no_season_episode(self, cleaner):
        """Returns (None, None) for movies."""
        season, episode = cleaner.extract_season_episode("Movie.2024.1080p.mkv")
        assert season is None
        assert episode is None

    def test_double_episode(self, cleaner):
        """Double episodes return first episode number."""
        season, episode = cleaner.extract_season_episode("Show.S02E01E02.1080p.mkv")
        assert season == 2
        assert episode == 1

    def test_season_pack(self, cleaner):
        """Season packs return first season number."""
        season, episode = cleaner.extract_season_episode("Show.S01-S08.Complete.1080p")
        assert season == 1
        assert episode is None


# --- clean_for_folder() ---


class TestCleanForFolder:
    """NameCleaner.clean_for_folder() — folder name creation."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Movie.Title.2024.1080p.BluRay.x264-GROUP", "Movie Title (2024)"),
            ("Shrinking.S03.MULTi.1080p", "Shrinking"),
            ("Some.Movie.Without.Year.1080p", "Some Movie Without Year"),
        ],
    )
    def test_folder_names(self, cleaner, raw, expected):
        """Creates 'Title (Year)' for movies, 'Title' for shows."""
        assert cleaner.clean_for_folder(raw) == expected

    def test_blade_runner_2049(self, cleaner):
        """Titles with embedded years get correct folder name."""
        result = cleaner.clean_for_folder("Blade.Runner.2049.2017.1080p.BluRay")
        assert "Blade Runner 2049" in result
        assert "(2017)" in result


# --- get_media_type() ---


class TestGetMediaType:
    """NameCleaner.get_media_type() — guessit type detection."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Show.S01E04.1080p.mkv", "episode"),
            ("Show.S03.MULTi.1080p", "episode"),
            ("Movie.2024.1080p.BluRay.mkv", "movie"),
        ],
    )
    def test_media_type_detection(self, cleaner, raw, expected):
        """Detects 'movie' vs 'episode' from filename patterns."""
        assert cleaner.get_media_type(raw) == expected


# --- French conventions ---


class TestFrenchConventions:
    """French-specific naming conventions handled by guessit."""

    @pytest.mark.parametrize(
        "raw",
        [
            "Show.S01E01.MULTi.VFF.1080p.mkv",
            "Movie.VOSTFR.1080p.mkv",
            "Movie.TRUEFRENCH.BluRay.mkv",
            "Show.MULTi.1080p.WEB.mkv",
        ],
    )
    def test_french_tags_stripped(self, cleaner, raw):
        """French audio tags (VFF, VOSTFR, TRUEFRENCH, MULTi) are stripped from title."""
        result = cleaner.clean(raw)
        for tag in ("VFF", "VOSTFR", "TRUEFRENCH", "MULTi"):
            assert tag not in result


# --- Edge cases ---


class TestEdgeCases:
    """Edge cases for the cleaner."""

    @pytest.mark.parametrize(
        "raw",
        [
            "24.S01E01.1080p.mkv",
            "300.2006.BluRay.mkv",
        ],
    )
    def test_numeric_titles(self, cleaner, raw):
        """Titles that are numbers are handled correctly."""
        result = cleaner.clean(raw)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_very_short_name(self, cleaner):
        """Very short names still produce output."""
        result = cleaner.clean("Up.2009.mkv")
        assert "Up" in result

    def test_clean_list_season_unpack(self, cleaner):
        """When guessit returns list of seasons, clean() picks first."""
        from unittest.mock import patch

        with patch(
            "personalscraper.sorter.cleaner._guess_cached",
            return_value={"title": "Show", "season": [1, 2, 3]},
        ):
            result = cleaner.clean("Show.S01-S03.1080p")
        assert result.startswith("Show")
        assert "S01" in result

    def test_clean_list_episode_unpack(self, cleaner):
        """When guessit returns list of episodes, clean() picks first."""
        from unittest.mock import patch

        with patch(
            "personalscraper.sorter.cleaner._guess_cached",
            return_value={"title": "Show", "season": 1, "episode": [6, 7]},
        ):
            result = cleaner.clean("Show.S01E06E07.1080p")
        assert result.startswith("Show")
        assert "E06" in result

    def test_caching_returns_same_result(self, cleaner):
        """Calling clean() twice with same input returns same result (cache test)."""
        name = "Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX"
        assert cleaner.clean(name) == cleaner.clean(name)


# --- Fake year fallback ---


class TestFakeYearFallback:
    """Fake-year injection recovers clean titles when guessit lacks a year anchor."""

    def test_vof_ad_stripped(self, cleaner):
        """VOF and AD absorbed into title without year are stripped."""
        result = cleaner.clean(
            "Le.Bus.Les.Bleus.En.Greve.VOF.AD.1080p.WEB.NF.DV.HDR.H265.EAC3.5.1-Amen.mkv"
        )
        assert result == "Le Bus Les Bleus En Greve"

    def test_nost_stripped(self, cleaner):
        """NOST absorbed into title without year is stripped."""
        result = cleaner.clean("Movie.Title.NOST.1080p.WEB.mkv")
        assert result == "Movie Title"

    def test_already_has_year_no_change(self, cleaner):
        """When year is already present, title is left untouched."""
        result = cleaner.clean(
            "De.Si.Remarquables.Créatures.2026.MULTi.VFF.1080p.WEBRip.x264.mkv"
        )
        assert result == "De Si Remarquables Créatures"

    def test_no_metadata_tokens_keeps_title(self, cleaner):
        """When no metadata tokens are found, original title is kept."""
        result = cleaner.clean("Some.Clean.Movie.Title.mkv")
        assert "Some Clean Movie Title" in result

    def test_clean_for_folder_also_fixed(self, cleaner):
        """clean_for_folder also benefits from the fake-year fallback."""
        result = cleaner.clean_for_folder(
            "Le.Bus.Les.Bleus.En.Greve.VOF.AD.1080p.WEB.mkv"
        )
        assert result == "Le Bus Les Bleus En Greve"
