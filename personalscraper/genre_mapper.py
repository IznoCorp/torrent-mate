"""Genre-to-category mapper for media dispatch.

Maps TMDB and TVDB genre IDs/names to destination disk categories.
Shared between V4 (verify) and V5 (dispatch).

Three distinct genre ID systems are handled:
- TMDB movies: 19 genres (e.g. Animation=16, Documentary=99)
- TMDB TV: 16 genres (Animation=16, Documentary=99, Reality=10764, etc.)
- TVDB: 36 genres (Animation=17, Anime=27, Documentary=3, etc.)

Genre IDs are stable within each provider but DIFFERENT across providers.
"""

import logging
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

# All valid destination categories (used by V5 for validation)
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "films", "films animations", "films documentaires",
    "spectacles", "theatres",
    "series", "series animations", "series documentaires",
    "series animes", "emissions",
    "livres audios",
})


def _normalize(s: str) -> str:
    """Normalize a genre name for comparison.

    Lowercases and strips accents via NFD decomposition.
    Handles French genre names from TMDB (e.g. "Documentaire" → "documentaire").

    Args:
        s: Genre name string.

    Returns:
        Normalized lowercase string without accents.
    """
    s = s.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


class GenreMapper:
    """Map API genres to destination disk categories.

    Handles three genre ID systems (TMDB movies, TMDB TV, TVDB) and
    falls back to string-based matching when IDs are unavailable.
    Supports a `.category` override file for spectacles/theatres
    which have no API genre equivalent.

    Attributes:
        KNOWN_CATEGORIES: All valid destination categories.
    """

    # --- TMDB movie genre IDs ---
    TMDB_ANIMATION = 16
    TMDB_DOCUMENTARY = 99

    # --- TMDB TV genre IDs ---
    TMDB_TV_ANIMATION = 16
    TMDB_TV_DOCUMENTARY = 99
    TMDB_TV_REALITY = 10764
    TMDB_TV_TALK = 10767
    TMDB_TV_NEWS = 10763

    # --- TVDB genre IDs ---
    TVDB_ANIMATION = 17
    TVDB_ANIME = 27
    TVDB_DOCUMENTARY = 3
    TVDB_REALITY = 8
    TVDB_TALK_SHOW = 10
    TVDB_NEWS = 11

    # Genre name patterns for string-based fallback
    _ANIMATION_NAMES = {"animation"}
    _DOCUMENTARY_NAMES = {"documentary", "documentaire"}
    _ANIME_NAMES = {"anime"}
    _REALITY_NAMES = {"reality", "realite", "talk show", "talk", "news"}

    def categorize_movie(
        self,
        genres: list[str],
        genre_ids: list[int] | None = None,
    ) -> str:
        """Categorize a movie based on its genres.

        Priority: genre_ids (more reliable) > genre names (string fallback).

        Args:
            genres: Genre name strings (may be in French from TMDB).
            genre_ids: TMDB genre IDs if available.

        Returns:
            Category string: "films", "films animations", or
            "films documentaires".
        """
        # ID-based categorization (preferred)
        if genre_ids:
            if self.TMDB_ANIMATION in genre_ids:
                return "films animations"
            if self.TMDB_DOCUMENTARY in genre_ids:
                return "films documentaires"
            return "films"

        # String-based fallback
        normalized = {_normalize(g) for g in genres}
        if normalized & self._ANIMATION_NAMES:
            return "films animations"
        if normalized & self._DOCUMENTARY_NAMES:
            return "films documentaires"

        return "films"

    def categorize_tvshow(
        self,
        genres: list[str],
        genre_ids: list[int] | None = None,
        origin_country: str | None = None,
        source: str = "tmdb",
    ) -> str:
        """Categorize a TV show based on its genres and origin.

        Anime detection differs by provider:
        - TMDB: Animation genre + origin_country contains "JP"
        - TVDB: Dedicated Anime genre (ID 27)

        Args:
            genres: Genre name strings.
            genre_ids: Genre IDs from the matching provider.
            origin_country: Origin country code(s) for anime detection.
            source: Provider name ("tmdb" or "tvdb") to select correct IDs.

        Returns:
            Category string: "series", "series animations",
            "series documentaires", "series animes", or "emissions".
        """
        is_jp = bool(origin_country and "JP" in origin_country.upper())

        # ID-based categorization
        if genre_ids:
            if source == "tvdb":
                return self._categorize_tvshow_tvdb(genre_ids)
            return self._categorize_tvshow_tmdb(genre_ids, is_jp)

        # String-based fallback
        normalized = {_normalize(g) for g in genres}

        if normalized & self._ANIME_NAMES:
            return "series animes"
        if normalized & self._ANIMATION_NAMES:
            return "series animes" if is_jp else "series animations"
        if normalized & self._DOCUMENTARY_NAMES:
            return "series documentaires"
        if normalized & self._REALITY_NAMES:
            return "emissions"

        return "series"

    def categorize_from_nfo(self, nfo_path: Path, media_type: str) -> str | None:
        """Determine category from NFO file or .category override.

        Priority:
        1. `.category` file in parent dir (for spectacles/theatres)
        2. NFO XML parsing (genres + country for anime detection)

        Args:
            nfo_path: Path to the NFO file.
            media_type: "movie" or "tvshow".

        Returns:
            Category string, or None if undetermined.
        """
        parent = nfo_path.parent

        # Priority 1: .category file override
        category_file = parent / ".category"
        if category_file.exists():
            content = category_file.read_text(encoding="utf-8").strip().lower()
            if content in KNOWN_CATEGORIES:
                return content
            logger.warning(
                "Invalid .category content '%s' in %s", content, parent.name,
            )

        # Priority 2: parse NFO
        try:
            tree = ET.parse(nfo_path)  # noqa: S314
            root = tree.getroot()
        except (ET.ParseError, OSError):
            logger.warning("Failed to parse NFO: %s", nfo_path.name)
            return None

        genres = [g.text for g in root.findall("genre") if g.text]

        # Detect origin country for anime
        country = None
        country_elem = root.find("country")
        if country_elem is not None and country_elem.text:
            country = country_elem.text

        if media_type == "movie":
            return self.categorize_movie(genres) if genres else None
        if media_type == "tvshow":
            # Determine source from uniqueid types
            source = "tmdb"
            for uid in root.findall("uniqueid"):
                if uid.get("type") == "tvdb" and uid.text:
                    source = "tvdb"
                    break
            return self.categorize_tvshow(genres, origin_country=country, source=source) if genres else None

        return None

    # --- Private helpers ---

    def _categorize_tvshow_tmdb(self, genre_ids: list[int], is_jp: bool) -> str:
        """Categorize TV show using TMDB genre IDs.

        Args:
            genre_ids: TMDB TV genre IDs.
            is_jp: Whether origin country includes Japan.

        Returns:
            Category string.
        """
        if self.TMDB_TV_ANIMATION in genre_ids:
            return "series animes" if is_jp else "series animations"
        if self.TMDB_TV_DOCUMENTARY in genre_ids:
            return "series documentaires"
        if any(gid in genre_ids for gid in (
            self.TMDB_TV_REALITY, self.TMDB_TV_TALK, self.TMDB_TV_NEWS,
        )):
            return "emissions"
        return "series"

    def _categorize_tvshow_tvdb(self, genre_ids: list[int]) -> str:
        """Categorize TV show using TVDB genre IDs.

        TVDB has a dedicated Anime genre (27), unlike TMDB.

        Args:
            genre_ids: TVDB genre IDs.

        Returns:
            Category string.
        """
        if self.TVDB_ANIME in genre_ids:
            return "series animes"
        if self.TVDB_ANIMATION in genre_ids:
            return "series animations"
        if self.TVDB_DOCUMENTARY in genre_ids:
            return "series documentaires"
        if any(gid in genre_ids for gid in (
            self.TVDB_REALITY, self.TVDB_TALK_SHOW, self.TVDB_NEWS,
        )):
            return "emissions"
        return "series"
