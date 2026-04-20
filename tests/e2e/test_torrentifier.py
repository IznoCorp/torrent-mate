"""Unit tests for the torrentifier utility module.

Tests folder name parsing, dot-conversion, deterministic seeding,
and torrent name generation for both movies and TV shows.
"""

from tests.e2e.torrentifier import (
    _deterministic_seed,
    _to_dots,
    parse_folder_name,
    torrentify_movie,
    torrentify_tvshow,
)


class TestParseFolderName:
    """Tests for parse_folder_name()."""

    def test_standard_title_year(self) -> None:
        """Should parse 'Title (Year)' format."""
        assert parse_folder_name("The Matrix (1999)") == ("The Matrix", 1999)

    def test_title_with_comma(self) -> None:
        """Should parse titles containing commas."""
        assert parse_folder_name("13 jours, 13 nuits (2025)") == ("13 jours, 13 nuits", 2025)

    def test_title_with_apostrophe(self) -> None:
        """Should preserve apostrophes in the parsed title."""
        result = parse_folder_name("L'Odyssée de l'espace (2001)")
        assert result == ("L'Odyssée de l'espace", 2001)

    def test_title_without_year_returns_none(self) -> None:
        """Should return None when no (Year) is present."""
        assert parse_folder_name("Title Without Year") is None

    def test_empty_string(self) -> None:
        """Should return None for empty string."""
        assert parse_folder_name("") is None

    def test_extra_whitespace(self) -> None:
        """Should handle extra whitespace around the folder name."""
        assert parse_folder_name("  Aladdin (1992)  ") == ("Aladdin", 1992)

    def test_year_only(self) -> None:
        """Should return None for a bare year."""
        assert parse_folder_name("(2024)") is None


class TestToDots:
    """Tests for _to_dots() dot-conversion."""

    def test_simple_title(self) -> None:
        """Should replace spaces with dots."""
        assert _to_dots("The Matrix") == "The.Matrix"

    def test_french_apostrophe(self) -> None:
        """Should strip straight apostrophes."""
        assert _to_dots("L'Odyssee de l'espace") == "LOdyssee.de.lespace"

    def test_curly_apostrophe(self) -> None:
        """Should strip curly/typographic apostrophes."""
        assert _to_dots("L\u2019Odyss\u00e9e") == "LOdyss\u00e9e"

    def test_colon_in_title(self) -> None:
        """Should replace colons with dots."""
        assert _to_dots("Title: Subtitle") == "Title.Subtitle"

    def test_consecutive_spaces(self) -> None:
        """Should collapse consecutive dots."""
        assert _to_dots("Title   Subtitle") == "Title.Subtitle"

    def test_comma_handling(self) -> None:
        """Should replace commas with dots."""
        assert _to_dots("Jours, Nuits") == "Jours.Nuits"

    def test_empty_string(self) -> None:
        """Should return empty string for empty input."""
        assert _to_dots("") == ""


class TestDeterministicSeed:
    """Tests for _deterministic_seed()."""

    def test_same_input_same_seed(self) -> None:
        """Should return identical seed for identical input."""
        assert _deterministic_seed("test") == _deterministic_seed("test")

    def test_different_input_different_seed(self) -> None:
        """Should return different seeds for different inputs."""
        assert _deterministic_seed("movie A") != _deterministic_seed("movie B")

    def test_returns_int(self) -> None:
        """Should return an integer."""
        assert isinstance(_deterministic_seed("test"), int)


class TestTorrentifyMovie:
    """Tests for torrentify_movie()."""

    def test_deterministic_output(self) -> None:
        """Should produce identical output for identical input."""
        a = torrentify_movie("The Matrix", 1999)
        b = torrentify_movie("The Matrix", 1999)
        assert a == b

    def test_contains_title_and_year(self) -> None:
        """Should include dotted title and year in output."""
        name = torrentify_movie("The Matrix", 1999)
        assert "The.Matrix" in name
        assert "1999" in name

    def test_ends_with_group(self) -> None:
        """Should end with a -GROUP suffix."""
        name = torrentify_movie("Aladdin", 1992)
        assert "-" in name
        # Group name is after the last dash
        group = name.split("-")[-1]
        assert group.isalpha() or group.replace("i", "").isalpha()

    def test_explicit_seed(self) -> None:
        """Should use explicit seed for reproducibility."""
        a = torrentify_movie("Test", 2024, seed=42)
        b = torrentify_movie("Test", 2024, seed=42)
        assert a == b

    def test_different_seeds_different_tags(self) -> None:
        """Different seeds should produce different tag combinations."""
        a = torrentify_movie("Test", 2024, seed=1)
        b = torrentify_movie("Test", 2024, seed=999)
        assert a != b


class TestTorrentifyTVShow:
    """Tests for torrentify_tvshow()."""

    def test_deterministic_output(self) -> None:
        """Should produce identical output for identical input."""
        a = torrentify_tvshow("Breaking Bad", 2008)
        b = torrentify_tvshow("Breaking Bad", 2008)
        assert a == b

    def test_contains_season_code(self) -> None:
        """Should include S01 season marker."""
        name = torrentify_tvshow("Breaking Bad", 2008)
        assert ".S01." in name

    def test_custom_season(self) -> None:
        """Should use the provided season number."""
        name = torrentify_tvshow("Breaking Bad", 2008, season=3)
        assert ".S03." in name

    def test_no_year_in_output(self) -> None:
        """Year should NOT appear in the torrent name (realistic)."""
        name = torrentify_tvshow("Ahsoka", 2023)
        assert "2023" not in name

    def test_contains_dotted_title(self) -> None:
        """Should include the dotted title."""
        name = torrentify_tvshow("Breaking Bad", 2008)
        assert "Breaking.Bad" in name
