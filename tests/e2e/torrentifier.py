"""Convert clean media folder names to realistic torrent-style names.

Used by roundtrip E2E tests to verify that the scraping pipeline can
correctly identify media from torrent-style filenames. Simulates the
naming conventions used by French torrent release groups.

Example:
    >>> torrentify_movie("The Matrix", 1999)
    'The.Matrix.1999.MULTi.1080p.BluRay.x264-FiDELiO'
    >>> torrentify_tvshow("Breaking Bad", 2008)
    'Breaking.Bad.S01.FRENCH.720p.WEB-DL.H265-SiGMA'
"""

import random
import re

# Regex for parsing "Title (Year)" folder names
_FOLDER_RE = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")

# Torrent release tags — drawn from real French scene releases
_RESOLUTIONS = ["720p", "1080p", "2160p"]
_SOURCES_MOVIE = ["BluRay", "WEB-DL", "WEBRip", "BDRip"]
_SOURCES_TV = ["WEB-DL", "WEBRip", "HDTV", "AMZN.WEB-DL", "NF.WEB-DL"]
_CODECS = ["x264", "x265", "H265", "H.264"]
_LANGS = ["MULTi", "FRENCH", "TRUEFRENCH", "VFF"]
_GROUPS = [
    "FiDELiO",
    "SiGMA",
    "EXTREME",
    "LOST",
    "FRATERNiTY",
    "CiELOS",
    "ALLDAYiN",
    "mHDgz",
    "VENUE",
    "QTZ",
]


def parse_folder_name(name: str) -> tuple[str, int] | None:
    """Parse a 'Title (Year)' folder name into (title, year).

    Args:
        name: Folder name to parse.

    Returns:
        (title, year) tuple, or None if it doesn't match the pattern.
    """
    m = _FOLDER_RE.match(name.strip())
    if not m:
        return None
    return m.group(1).strip(), int(m.group(2))


def _to_dots(title: str) -> str:
    """Convert a clean title to dot-separated torrent style.

    Strips apostrophes (common in French torrent names) and replaces
    spaces/colons with dots.

    Args:
        title: Clean media title (e.g. "L'Odyssée de l'espace").

    Returns:
        Dot-separated version (e.g. "LOdyssee.de.lespace").
    """
    # Strip French apostrophes (curly and straight)
    s = title.replace("\u2019", "").replace("'", "").replace("\u2018", "")
    s = re.sub(r"[\s:,]+", ".", s)
    s = re.sub(r"\.{2,}", ".", s)
    return s.strip(".")


def _deterministic_seed(name: str) -> int:
    """Create a deterministic seed from a string.

    Uses sum of char codes — stable across Python sessions
    (unlike hash() which is randomized by PYTHONHASHSEED).

    Args:
        name: Input string.

    Returns:
        Integer seed value.
    """
    return sum(ord(c) for c in name)


def torrentify_movie(title: str, year: int, seed: int | None = None) -> str:
    """Generate a realistic torrent name for a movie.

    Args:
        title: Clean movie title.
        year: Release year.
        seed: Random seed for reproducible tag selection.

    Returns:
        Torrent-style name (e.g. "The.Matrix.1999.MULTi.1080p.BluRay.x264-FiDELiO").
    """
    if seed is None:
        seed = _deterministic_seed(f"{title}{year}")
    rng = random.Random(seed)
    parts = [
        _to_dots(title),
        str(year),
        rng.choice(_LANGS),
        rng.choice(_RESOLUTIONS),
        rng.choice(_SOURCES_MOVIE),
        rng.choice(_CODECS),
    ]
    return ".".join(parts) + f"-{rng.choice(_GROUPS)}"


def torrentify_tvshow(
    title: str,
    year: int,
    season: int = 1,
    seed: int | None = None,
) -> str:
    """Generate a realistic torrent name for a TV show season pack.

    Does NOT include the year (realistic: TV show torrents rarely do).

    Args:
        title: Clean show title.
        year: First air date year (used for seed only, not in name).
        season: Season number (default 1).
        seed: Random seed for reproducible tag selection.

    Returns:
        Torrent-style name (e.g. "Breaking.Bad.S01.MULTi.1080p.WEB-DL.x264-SiGMA").
    """
    if seed is None:
        seed = _deterministic_seed(f"{title}{year}")
    rng = random.Random(seed)
    parts = [
        _to_dots(title),
        f"S{season:02d}",
        rng.choice(_LANGS),
        rng.choice(_RESOLUTIONS),
        rng.choice(_SOURCES_TV),
        rng.choice(_CODECS),
    ]
    return ".".join(parts) + f"-{rng.choice(_GROUPS)}"
