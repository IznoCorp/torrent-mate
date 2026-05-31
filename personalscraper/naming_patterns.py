"""Naming patterns for MediaElch-compatible file naming.

Defines all file naming conventions used by Kodi/MediaElch for movies,
TV shows, seasons, and episodes. Each pattern uses Python format string
syntax with named placeholders ({Title}, {Year}, {Season:02d}, etc.).

Shared across the scraper (NFO/artwork generation), verifier, and dispatcher modules.
Patterns are MediaElch defaults — no config file needed (YAGNI).
"""

import re
from dataclasses import dataclass

from personalscraper.text_utils import sanitize_filename


@dataclass(frozen=True)
class NamingPatterns:
    """MediaElch-compatible naming patterns for media files.

    All patterns use Python format string syntax. Available variables:
    - {Title}: Media title (e.g. "The Matrix", "Shrinking")
    - {Year}: Release year (e.g. 2024)
    - {Season:02d}: Zero-padded season number (e.g. 01, 03)
    - {Episode:02d}: Zero-padded episode number (e.g. 01, 12)
    - {EpisodeTitle}: Episode title (e.g. "Pilot")
    - {BaseFileName}: Resolved filename stem (Title for movies,
      S01E01 - EpisodeTitle for episodes)

    Attributes:
        movie_dir: Movie folder pattern.
        movie_video: Movie video file pattern (stem only, no extension).
        movie_nfo: Movie NFO file pattern.
        movie_poster: Movie poster pattern.
        movie_fanart: Movie fanart/backdrop pattern.
        movie_banner: Movie banner pattern.
        movie_clearlogo: Movie clearlogo pattern.
        movie_clearart: Movie clearart pattern.
        movie_discart: Movie disc art pattern.
        movie_landscape: Movie landscape/thumb pattern.
        tvshow_nfo: TV show NFO pattern (fixed name).
        tvshow_poster: TV show poster pattern (fixed name).
        tvshow_fanart: TV show fanart pattern (fixed name).
        tvshow_banner: TV show banner pattern (fixed name).
        tvshow_clearlogo: TV show clearlogo pattern (fixed name).
        tvshow_clearart: TV show clearart pattern (fixed name).
        tvshow_characterart: TV show character art pattern (fixed name).
        tvshow_landscape: TV show landscape pattern (fixed name).
        season_dir: Season directory pattern (French: "Saison 01").
        season_poster: Season poster pattern.
        season_fanart: Season fanart pattern.
        season_banner: Season banner pattern.
        season_landscape: Season landscape pattern.
        episode_video: Episode video pattern (stem only, no extension).
        episode_nfo: Episode NFO pattern.
        episode_thumb: Episode thumbnail pattern.
    """

    # --- Movie patterns ---
    # Movie files use {Title} as prefix (the base filename)
    movie_dir: str = "{Title} ({Year})"
    movie_video: str = "{Title}"
    movie_nfo: str = "{Title}.nfo"
    movie_poster: str = "{Title}-poster.jpg"
    movie_fanart: str = "{Title}-fanart.jpg"
    movie_banner: str = "{Title}-banner.jpg"
    movie_clearlogo: str = "{Title}-clearlogo.png"
    movie_clearart: str = "{Title}-clearart.png"
    movie_discart: str = "{Title}-discart.png"
    movie_landscape: str = "{Title}-landscape.jpg"

    # --- TV show patterns (show-level, fixed names) ---
    tvshow_nfo: str = "tvshow.nfo"
    tvshow_poster: str = "poster.jpg"
    tvshow_fanart: str = "fanart.jpg"
    tvshow_banner: str = "banner.jpg"
    tvshow_clearlogo: str = "clearlogo.png"
    tvshow_clearart: str = "clearart.png"
    tvshow_characterart: str = "characterart.png"
    tvshow_landscape: str = "landscape.jpg"

    # --- Season patterns ---
    season_dir: str = "Saison {Season:02d}"
    season_poster: str = "season{Season:02d}-poster.jpg"
    season_fanart: str = "season{Season:02d}-fanart.jpg"
    season_banner: str = "season{Season:02d}-banner.jpg"
    season_landscape: str = "season{Season:02d}-landscape.jpg"

    # --- Episode patterns ---
    # Episode files use S01E01 - Title as the base filename
    episode_video: str = "S{Season:02d}E{Episode:02d} - {EpisodeTitle}"
    episode_nfo: str = "S{Season:02d}E{Episode:02d} - {EpisodeTitle}.nfo"
    episode_thumb: str = "S{Season:02d}E{Episode:02d} - {EpisodeTitle}-thumb.jpg"

    def format(self, pattern_name: str, **kwargs: object) -> str:
        """Format a pattern by name with the given variables.

        Args:
            pattern_name: Name of the pattern attribute (e.g. "movie_poster").
            **kwargs: Template variables (Title, Year, Season, Episode, EpisodeTitle).

        Returns:
            The formatted filename string.

        Raises:
            AttributeError: If pattern_name is not a valid pattern.
            KeyError: If a required template variable is missing.
        """
        pattern = getattr(self, pattern_name)
        return sanitize_filename(pattern.format(**kwargs))

    def format_base_filename(self, is_episode: bool = False, **kwargs: object) -> str:
        """Resolve the base filename for a media item.

        For movies: returns {Title}
        For episodes: returns 'S01E01 - EpisodeTitle'

        Args:
            is_episode: True for episode files, False for movies.
            **kwargs: Template variables.

        Returns:
            The resolved base filename (without extension).
        """
        if is_episode:
            return sanitize_filename(self.episode_video.format(**kwargs))
        return sanitize_filename(str(kwargs.get("Title", "")))


# Singleton — patterns are constants, no need for multiple instances
PATTERNS = NamingPatterns()


def _build_dir_regex(pattern: str) -> "re.Pattern[str]":
    r"""Build a regex from a Python format string pattern.

    Replaces all ``{placeholder}`` and ``{placeholder:format}`` tokens
    with the capturing group ``(\\d+)`` (assumes numeric placeholders),
    so callers can recover the matched number via ``m.group(N)``.
    Literal portions are escaped for safe regex use.

    Example::

        >>> _build_dir_regex("Saison {Season:02d}")
        re.compile('^Saison (\\\\d+)$')

    Args:
        pattern: A Python format string (e.g. ``"Saison {Season:02d}"``).

    Returns:
        Compiled regex matching any string produced by *pattern*. Each
        ``{placeholder}`` becomes one capturing group, in order.

    Note:
        The returned pattern is intended for ``match``/``fullmatch`` +
        ``group(N)`` use. Callers using ``findall`` / ``re.sub`` should
        be aware that the capturing group changes ``findall`` return
        shape (returns the captured digits, not the whole match).
    """
    import re

    parts = re.split(r"(\{[^}]+\})", pattern)
    regex_str = ""
    for part in parts:
        if re.match(r"^\{[^}]+\}$", part):
            regex_str += r"(\d+)"
        else:
            regex_str += re.escape(part)
    return re.compile(f"^{regex_str}$")


# Widened to FR+EN+Specials union — the authoritative SSOT used by all callers.
# Matches: "Saison N", "Season N" (any digit count, case-insensitive keyword),
# "Specials", "Special" (case-insensitive).
SEASON_DIR_RE: re.Pattern[str] = re.compile(
    r"^(?:saison|season)\s+(\d+)$|^specials?$",
    re.IGNORECASE,
)


def season_number_from_dir(name: str) -> int | None:
    """Return the season number from a season directory name.

    Args:
        name: Directory name, e.g. ``"Saison 3"``, ``"Season 12"``,
            ``"Specials"``.

    Returns:
        Season number as int (0 for Specials/Special, positive int for
        numbered seasons), or ``None`` when ``name`` does not match any
        known season-directory form.
    """
    m = SEASON_DIR_RE.match(name)
    if m is None:
        return None
    # Group 1 is present for "Saison N" / "Season N"; absent for "Specials".
    return int(m.group(1)) if m.lastindex and m.group(1) else 0
