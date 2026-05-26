"""Media filename cleaner powered by guessit.

Replaces FileMate's regex-based NodeNameCleaner with guessit, which handles
140+ streaming services, French conventions (VFF, VOSTFR, TRUEFRENCH, MULTi,
Saison), titles with embedded years (Blade Runner 2049), double episodes,
and season packs natively.

See docs/guessit-evaluation.md for the full evaluation.
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

from guessit import guessit as guess

# Fields whose values can appear as tokens in the filename AFTER the title.
# Used to locate the title/metadata boundary when no year anchor is present.
_METADATA_FIELDS = (
    "screen_size",
    "source",
    "video_codec",
    "audio_codec",
    "release_group",
    "language",
    "subtitle_language",
    "alternative_title",
    "other",
    "audio_channels",
    "streaming_service",
    "container",
)


# Tokens guessit only classifies as alternative_title when a year anchor is
# present. Without a year, they leak into the title. We supplement the
# metadata extraction so the boundary detector can see them.
_ALT_TITLE_TOKENS = frozenset({"VOF", "VO", "AD", "NOST", "VF2", "VFI"})


def _extract_metadata_values(result: dict[str, Any]) -> set[str]:
    """Extract and normalize metadata values from a guessit result.

    Collects string representations of all non-title metadata fields,
    normalizing them for token matching: uppercase, no dots/hyphens/underscores.

    Args:
        result: Raw guessit result dictionary.

    Returns:
        Set of normalized metadata strings.
    """
    tokens: set[str] = set()
    for field in _METADATA_FIELDS:
        value = result.get(field)
        if value is None:
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            raw = str(item).upper()
            # Normalize: strip dots/hyphens/underscores (H.265 → H265, DTS-HD → DTSHD)
            clean = raw.replace(".", "").replace("-", "").replace("_", "")
            tokens.add(clean)
            if " " in clean:
                tokens.add(clean.replace(" ", ""))
    tokens.update(_ALT_TITLE_TOKENS)
    return tokens


def _find_boundary_index(parts: list[str], metadata: set[str]) -> int | None:
    """Locate the first metadata token in a dot-split filename.

    Scans left to right; the first token that matches a known metadata
    value marks the end of the title portion.

    Args:
        parts: Filename split on dots.
        metadata: Normalized metadata tokens from guessit.

    Returns:
        Index of the first metadata token, or None if no boundary found.
    """
    for i, part in enumerate(parts):
        clean = part.upper().replace(".", "").replace("-", "").replace("_", "")
        if clean in metadata:
            return i
    return None


@lru_cache(maxsize=512)
def _guess_cached(name: str) -> dict[str, Any]:
    """Run guessit on a name, caching the result.

    When no year is detected, inserts a synthetic year at the title/metadata
    boundary and re-runs guessit so the parser can separate title from noise
    tokens (VOF, AD, NOST, etc.) that would otherwise be absorbed.

    Args:
        name: Raw media filename or directory name.

    Returns:
        Dictionary of guessit results (title, year, season, episode, type, etc.).
    """
    result = dict(guess(name))

    if result.get("year") is not None:
        return result

    # No year → title may be polluted. Locate boundary via metadata fields.
    metadata = _extract_metadata_values(result)
    if not metadata:
        return result

    parts = name.replace(" ", ".").split(".")
    boundary = _find_boundary_index(parts, metadata)
    if boundary is None or boundary == 0:
        return result

    fake_year = str(datetime.now().year)
    modified = ".".join(parts[:boundary] + [fake_year] + parts[boundary:])
    recovered = dict(guess(modified))
    result["title"] = recovered.get("title", result["title"])

    return result


class NameCleaner:
    """Media filename cleaner powered by guessit.

    Thin wrapper that parses media filenames/directory names via guessit
    and exposes cleaned title, year, season/episode, and media type.
    All methods use a shared cached guessit call per name.
    """

    def clean(self, name: str) -> str:
        """Clean a media filename, returning title with season/episode preserved.

        Examples:
            'Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX' -> 'Shrinking S03'
            'The.Boys.S05E01.MULTi.1080p-R3MiX' -> 'The Boys S05E01'
            'Your.Friends...H265-TFA.mkv' -> 'Your Friends'

        Args:
            name: Raw media filename or directory name.

        Returns:
            Cleaned string: title only, or title + season/episode code.
        """
        r = _guess_cached(name)
        title: str = r.get("title", name)
        season = r.get("season")
        episode = r.get("episode")

        # Handle lists (double episodes, season packs)
        if isinstance(season, list):
            season = season[0]
        if isinstance(episode, list):
            episode = episode[0]

        if season is not None and episode is not None:
            return f"{title} S{season:02d}E{episode:02d}"
        if season is not None:
            return f"{title} S{season:02d}"
        return title

    def extract_year(self, name: str) -> int | None:
        """Extract year from a media name via guessit.

        Correctly handles titles containing years like "2001: A Space Odyssey"
        or "Blade Runner 2049" where the year is part of the title vs. the
        release year.

        Args:
            name: Raw media filename or directory name.

        Returns:
            The release year as int, or None if not detected.
        """
        return _guess_cached(name).get("year")

    def extract_season_episode(self, name: str) -> tuple[int | None, int | None]:
        """Extract season and episode numbers from a media name.

        Supports: S01E04, s01e04, 1x04, Saison 1 Episode 4, S03 (season only),
        double episodes (S02E01E02 returns first episode), season packs
        (S01-S08 returns first season).

        Args:
            name: Raw media filename or directory name.

        Returns:
            Tuple of (season, episode). Either may be None.
        """
        r = _guess_cached(name)
        season = r.get("season")
        episode = r.get("episode")

        # guessit returns lists for multi-values (packs, doubles)
        if isinstance(season, list):
            season = season[0]
        if isinstance(episode, list):
            episode = episode[0]

        return season, episode

    def clean_for_folder(self, name: str) -> str:
        """Clean a name for folder creation: 'Title (Year)' or 'Title'.

        Used when creating destination directories for movies.
        TV shows get folders without year at sort time;
        year is added after API matching in the scraping step.

        Args:
            name: Raw media filename or directory name.

        Returns:
            Cleaned folder name.
        """
        r = _guess_cached(name)
        title = r.get("title", name)
        year = r.get("year")
        return f"{title} ({year})" if year else title

    def get_media_type(self, name: str) -> str | None:
        """Return guessit media type: 'movie' or 'episode', or None.

        Used by file_type.py to reinforce movie vs tvshow detection
        when extension-only detection is ambiguous.

        Args:
            name: Raw media filename or directory name.

        Returns:
            'movie', 'episode', or None if guessit can't determine the type.
        """
        return _guess_cached(name).get("type")
