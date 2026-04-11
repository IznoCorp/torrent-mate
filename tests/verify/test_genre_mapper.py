"""Tests for the genre-to-category mapper.

Covers movie and TV show categorization using both ID-based and
string-based genre matching, anime detection, .category file override,
and NFO-based categorization.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from personalscraper.genre_mapper import KNOWN_CATEGORIES, GenreMapper


@pytest.fixture
def mapper() -> GenreMapper:
    """Create a GenreMapper instance."""
    return GenreMapper()


# ---------------------------------------------------------------------------
# Movie categorization — ID-based
# ---------------------------------------------------------------------------

class TestCategorizeMovieIds:
    """Tests for categorize_movie with genre IDs."""

    def test_animation_id(self, mapper: GenreMapper) -> None:
        """Animation genre ID should return 'films animations'."""
        assert mapper.categorize_movie([], genre_ids=[16, 28]) == "films animations"

    def test_documentary_id(self, mapper: GenreMapper) -> None:
        """Documentary genre ID should return 'films documentaires'."""
        assert mapper.categorize_movie([], genre_ids=[99]) == "films documentaires"

    def test_default_films(self, mapper: GenreMapper) -> None:
        """Other genre IDs should return 'films'."""
        assert mapper.categorize_movie([], genre_ids=[28, 18]) == "films"

    def test_animation_takes_priority(self, mapper: GenreMapper) -> None:
        """Animation should take priority over documentary."""
        assert mapper.categorize_movie([], genre_ids=[16, 99]) == "films animations"


# ---------------------------------------------------------------------------
# Movie categorization — string fallback
# ---------------------------------------------------------------------------

class TestCategorizeMovieStrings:
    """Tests for categorize_movie with genre name strings."""

    def test_animation_string_en(self, mapper: GenreMapper) -> None:
        """English 'Animation' should match."""
        assert mapper.categorize_movie(["Animation", "Comedy"]) == "films animations"

    def test_documentary_string_fr(self, mapper: GenreMapper) -> None:
        """French 'Documentaire' should match."""
        assert mapper.categorize_movie(["Documentaire"]) == "films documentaires"

    def test_documentary_string_en(self, mapper: GenreMapper) -> None:
        """English 'Documentary' should match."""
        assert mapper.categorize_movie(["Documentary"]) == "films documentaires"

    def test_default_string(self, mapper: GenreMapper) -> None:
        """Unknown genre strings should return 'films'."""
        assert mapper.categorize_movie(["Drame", "Action"]) == "films"

    def test_empty_genres(self, mapper: GenreMapper) -> None:
        """Empty genres should return 'films'."""
        assert mapper.categorize_movie([]) == "films"


# ---------------------------------------------------------------------------
# TV show categorization — TMDB IDs
# ---------------------------------------------------------------------------

class TestCategorizeTvshowTMDB:
    """Tests for categorize_tvshow with TMDB genre IDs."""

    def test_animation_jp(self, mapper: GenreMapper) -> None:
        """Animation + JP origin → 'series animes'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[16], origin_country="JP", source="tmdb",
        ) == "series animes"

    def test_animation_non_jp(self, mapper: GenreMapper) -> None:
        """Animation without JP → 'series animations'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[16], origin_country="US", source="tmdb",
        ) == "series animations"

    def test_documentary(self, mapper: GenreMapper) -> None:
        """Documentary → 'series documentaires'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[99], source="tmdb",
        ) == "series documentaires"

    def test_reality(self, mapper: GenreMapper) -> None:
        """Reality → 'emissions'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[10764], source="tmdb",
        ) == "emissions"

    def test_talk(self, mapper: GenreMapper) -> None:
        """Talk → 'emissions'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[10767], source="tmdb",
        ) == "emissions"

    def test_news(self, mapper: GenreMapper) -> None:
        """News → 'emissions'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[10763], source="tmdb",
        ) == "emissions"

    def test_default(self, mapper: GenreMapper) -> None:
        """Other genres → 'series'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[18, 80], source="tmdb",
        ) == "series"


# ---------------------------------------------------------------------------
# TV show categorization — TVDB IDs
# ---------------------------------------------------------------------------

class TestCategorizeTvshowTVDB:
    """Tests for categorize_tvshow with TVDB genre IDs."""

    def test_anime_tvdb(self, mapper: GenreMapper) -> None:
        """TVDB Anime genre (27) → 'series animes'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[27], source="tvdb",
        ) == "series animes"

    def test_animation_tvdb(self, mapper: GenreMapper) -> None:
        """TVDB Animation (17) → 'series animations'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[17], source="tvdb",
        ) == "series animations"

    def test_documentary_tvdb(self, mapper: GenreMapper) -> None:
        """TVDB Documentary (3) → 'series documentaires'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[3], source="tvdb",
        ) == "series documentaires"

    def test_reality_tvdb(self, mapper: GenreMapper) -> None:
        """TVDB Reality (8) → 'emissions'."""
        assert mapper.categorize_tvshow(
            [], genre_ids=[8], source="tvdb",
        ) == "emissions"


# ---------------------------------------------------------------------------
# TV show categorization — string fallback
# ---------------------------------------------------------------------------

class TestCategorizeTvshowStrings:
    """Tests for categorize_tvshow with genre name strings."""

    def test_anime_string(self, mapper: GenreMapper) -> None:
        """'Anime' string → 'series animes'."""
        assert mapper.categorize_tvshow(["Anime"]) == "series animes"

    def test_animation_jp_string(self, mapper: GenreMapper) -> None:
        """'Animation' + JP → 'series animes'."""
        assert mapper.categorize_tvshow(
            ["Animation"], origin_country="JP",
        ) == "series animes"

    def test_animation_non_jp_string(self, mapper: GenreMapper) -> None:
        """'Animation' without JP → 'series animations'."""
        assert mapper.categorize_tvshow(["Animation"]) == "series animations"


# ---------------------------------------------------------------------------
# NFO-based categorization
# ---------------------------------------------------------------------------

class TestCategorizeFromNFO:
    """Tests for categorize_from_nfo."""

    def _write_movie_nfo(self, tmp_path: Path, genres: list[str]) -> Path:
        """Helper to write a simple movie NFO."""
        root = ET.Element("movie")
        for g in genres:
            genre = ET.SubElement(root, "genre")
            genre.text = g
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tmdb")
        uid.text = "12345"
        nfo_path = tmp_path / "Movie.nfo"
        tree = ET.ElementTree(root)
        tree.write(nfo_path, encoding="unicode")
        return nfo_path

    def test_movie_from_nfo(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Should categorize movie from NFO genres."""
        nfo = self._write_movie_nfo(tmp_path, ["Animation", "Comédie"])
        assert mapper.categorize_from_nfo(nfo, "movie") == "films animations"

    def test_documentary_from_nfo(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Should detect documentary from FR genre string."""
        nfo = self._write_movie_nfo(tmp_path, ["Documentaire"])
        assert mapper.categorize_from_nfo(nfo, "movie") == "films documentaires"

    def test_no_genres_returns_none(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Should return None when no genres in NFO."""
        nfo = self._write_movie_nfo(tmp_path, [])
        assert mapper.categorize_from_nfo(nfo, "movie") is None

    def test_category_file_override(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Should use .category file when present."""
        nfo = self._write_movie_nfo(tmp_path, ["Drame"])
        (tmp_path / ".category").write_text("spectacles")
        assert mapper.categorize_from_nfo(nfo, "movie") == "spectacles"

    def test_category_file_theatres(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Should accept 'theatres' from .category."""
        nfo = self._write_movie_nfo(tmp_path, ["Drame"])
        (tmp_path / ".category").write_text("theatres\n")
        assert mapper.categorize_from_nfo(nfo, "movie") == "theatres"

    def test_invalid_category_file(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Invalid .category content should fall back to NFO parsing."""
        nfo = self._write_movie_nfo(tmp_path, ["Animation"])
        (tmp_path / ".category").write_text("invalid_category")
        assert mapper.categorize_from_nfo(nfo, "movie") == "films animations"

    def test_malformed_nfo(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Should return None for malformed XML."""
        nfo = tmp_path / "bad.nfo"
        nfo.write_text("not xml at all <><>")
        assert mapper.categorize_from_nfo(nfo, "movie") is None

    def test_tvshow_with_tvdb_source(self, mapper: GenreMapper, tmp_path: Path) -> None:
        """Should detect TVDB source from uniqueid and categorize."""
        root = ET.Element("tvshow")
        genre = ET.SubElement(root, "genre")
        genre.text = "Animation"
        uid_tvdb = ET.SubElement(root, "uniqueid")
        uid_tvdb.set("type", "tvdb")
        uid_tvdb.text = "12345"
        uid_tmdb = ET.SubElement(root, "uniqueid")
        uid_tmdb.set("type", "tmdb")
        uid_tmdb.text = "67890"
        nfo = tmp_path / "tvshow.nfo"
        ET.ElementTree(root).write(nfo, encoding="unicode")

        # TVDB source + Animation string → "series animations"
        assert mapper.categorize_from_nfo(nfo, "tvshow") == "series animations"


# ---------------------------------------------------------------------------
# KNOWN_CATEGORIES validation
# ---------------------------------------------------------------------------

class TestKnownCategories:
    """Tests for KNOWN_CATEGORIES constant."""

    def test_all_disk_categories_present(self) -> None:
        """All categories from storage disks should be in KNOWN_CATEGORIES."""
        disk_categories = {
            "films", "films animations", "films documentaires",
            "livres audios", "series", "series animations",
            "series documentaires", "spectacles", "theatres",
            "emissions", "series animes",
        }
        assert disk_categories <= KNOWN_CATEGORIES

    def test_is_frozenset(self) -> None:
        """KNOWN_CATEGORIES should be immutable."""
        assert isinstance(KNOWN_CATEGORIES, frozenset)
