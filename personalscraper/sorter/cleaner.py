"""Media filename cleaner powered by guessit.

Replaces FileMate's regex-based NodeNameCleaner with guessit, which handles
140+ streaming services, French conventions (VFF, VOSTFR, TRUEFRENCH, MULTi,
Saison), titles with embedded years (Blade Runner 2049), double episodes,
and season packs natively.

See docs/guessit-evaluation.md for the full evaluation.
"""

from functools import lru_cache
from typing import Any

from guessit import guessit as guess


@lru_cache(maxsize=512)
def _guess_cached(name: str) -> dict[str, Any]:
    """Run guessit on a name, caching the result.

    guessit does significant work (regex chains, rebulk matching),
    so we cache to avoid calling it multiple times for the same name
    across different NameCleaner methods.

    Args:
        name: Raw media filename or directory name.

    Returns:
        Dictionary of guessit results (title, year, season, episode, type, etc.).
    """
    return dict(guess(name))


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
