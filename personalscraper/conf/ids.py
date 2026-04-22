"""Abstract category IDs — stable identifiers used throughout the codebase.

Never user-facing labels. Folder names are in config.json5. Code uses only these
constants for routing, logging, filtering, validation.

Users may add custom IDs via Config.custom_categories.
"""

from typing import Final

MOVIES: Final[str] = "movies"
MOVIES_ANIMATION: Final[str] = "movies_animation"
MOVIES_DOCUMENTARY: Final[str] = "movies_documentary"
TV_SHOWS: Final[str] = "tv_shows"
TV_SHOWS_ANIMATION: Final[str] = "tv_shows_animation"
TV_SHOWS_DOCUMENTARY: Final[str] = "tv_shows_documentary"
ANIME: Final[str] = "anime"
AUDIOBOOKS: Final[str] = "audiobooks"
STANDUP: Final[str] = "standup"
THEATER: Final[str] = "theater"
TV_PROGRAMS: Final[str] = "tv_programs"

MOVIE_CATEGORY_IDS: Final[frozenset[str]] = frozenset(
    {
        MOVIES,
        MOVIES_ANIMATION,
        MOVIES_DOCUMENTARY,
        STANDUP,
        THEATER,
    }
)
"""Category IDs that contain movie-type media (one video file per item)."""

TV_CATEGORY_IDS: Final[frozenset[str]] = frozenset(
    {
        TV_SHOWS,
        TV_SHOWS_ANIMATION,
        TV_SHOWS_DOCUMENTARY,
        ANIME,
        TV_PROGRAMS,
    }
)
"""Category IDs that contain TV show-type media (season/episode structure)."""

BUILTIN_CATEGORY_IDS: Final[frozenset[str]] = frozenset(
    {
        MOVIES,
        MOVIES_ANIMATION,
        MOVIES_DOCUMENTARY,
        TV_SHOWS,
        TV_SHOWS_ANIMATION,
        TV_SHOWS_DOCUMENTARY,
        ANIME,
        AUDIOBOOKS,
        STANDUP,
        THEATER,
        TV_PROGRAMS,
    }
)


def default_label(category_id: str) -> str:
    """Return the default human-readable label for a category ID.

    Converts underscores to spaces (e.g. "movies_animation" → "movies animation").

    Args:
        category_id: A builtin or custom category ID string.

    Returns:
        A human-readable label derived from the ID.
    """
    return category_id.replace("_", " ")
