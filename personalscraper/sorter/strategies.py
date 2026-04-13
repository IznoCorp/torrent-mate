"""Sorting strategies for placing media items into destination directories.

Each strategy determines the target subdirectory based on media type:
- MovieStrategy: 001-MOVIES/Title (Year)/
- TVShowStrategy: 002-TVSHOWS/Show Name/
- DefaultStrategy: type-specific directory (003-EBOOKS, 004-AUDIO, etc.)

Strategies use fuzzy matching to find existing folders and prevent duplicates.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType
from personalscraper.sorter.matcher import find_matching_directory

# Default mapping FileType → staging subdirectory name
TYPE_DIR_MAP: dict[FileType, str] = {
    FileType.MOVIE: "001-MOVIES",
    FileType.TVSHOW: "002-TVSHOWS",
    FileType.EBOOK: "003-EBOOKS",
    FileType.AUDIO: "004-AUDIO",
    FileType.APP: "005-APPS",
    FileType.OTHER: "098-AUTRES",
}


def get_type_dir_map() -> dict[FileType, str]:
    """Return the FileType → directory name mapping, using settings if available.

    Falls back to TYPE_DIR_MAP defaults only when settings are genuinely
    unavailable (e.g. tests without .env). Logs a warning for unexpected
    errors so that configuration mistakes are not silently ignored.

    Returns:
        Dict mapping FileType to directory name string.
    """
    try:
        from personalscraper.config import get_settings

        s = get_settings()
        return {
            FileType.MOVIE: s.movies_dir_name,
            FileType.TVSHOW: s.tvshows_dir_name,
            FileType.EBOOK: s.ebooks_dir_name,
            FileType.AUDIO: s.audio_dir_name,
            FileType.APP: s.apps_dir_name,
            FileType.OTHER: s.other_dir_name,
        }
    except (ImportError, FileNotFoundError):
        # Settings not available (tests without .env) — use defaults silently
        return TYPE_DIR_MAP
    except Exception:
        import logging

        logging.getLogger(__name__).error(
            "Settings configuration error — using default directory mapping. "
            "Check .env file for validation errors.",
            exc_info=True,
        )
        return TYPE_DIR_MAP


class SortingStrategy(ABC):
    """Base class for sorting strategies.

    Each strategy computes a destination path for a media item based on
    its cleaned name and the staging directory structure.
    """

    @abstractmethod
    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner) -> Path:
        """Compute the destination path for a media item.

        Args:
            name: Raw filename or directory name of the item being sorted.
            staging_dir: Root staging directory (A TRIER/).
            cleaner: NameCleaner for title/year extraction.

        Returns:
            The destination Path where the item should be moved.
        """


class MovieStrategy(SortingStrategy):
    """Place movies in 001-MOVIES/Title (Year)/ subfolders.

    Uses fuzzy matching to find existing movie folders and prevent
    duplicates. If a match is found, returns the existing folder.
    Otherwise creates a new folder named 'Title (Year)' or 'Title'.
    """

    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner) -> Path:
        """Return 001-MOVIES/Title (Year)/ or existing matching folder.

        Args:
            name: Raw movie filename or directory name.
            staging_dir: Root staging directory.
            cleaner: NameCleaner for title/year extraction.

        Returns:
            Destination path inside 001-MOVIES/.
        """
        movies_dir = staging_dir / get_type_dir_map()[FileType.MOVIE]
        folder_name = cleaner.clean_for_folder(name)

        # Check for existing matching folder
        if movies_dir.is_dir():
            candidates = [d for d in movies_dir.iterdir() if d.is_dir()]
            match = find_matching_directory(folder_name, candidates, respect_year=True)
            if match is not None:
                return match

        return movies_dir / folder_name


class TVShowStrategy(SortingStrategy):
    """Place TV shows in 002-TVSHOWS/Show Name/ subfolders.

    V2 creates folders WITHOUT year (e.g. 'Shrinking/', not 'Shrinking (2023)/').
    V3 adds the year after API matching. Uses fuzzy matching to merge
    new episodes into existing show folders.
    """

    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner) -> Path:
        """Return 002-TVSHOWS/Show Name/ or existing matching folder.

        Args:
            name: Raw TV show filename or directory name.
            staging_dir: Root staging directory.
            cleaner: NameCleaner for title extraction.

        Returns:
            Destination path inside 002-TVSHOWS/.
        """
        tvshows_dir = staging_dir / get_type_dir_map()[FileType.TVSHOW]

        # Extract show name without season/episode info and without year
        # V2 creates "Show Name/" — V3 will rename to "Show Name (Year)/"
        cleaned = cleaner.clean(name)
        # Remove season/episode suffix to get just the show name
        # clean() returns "Show S01E04" or "Show S03" — we want just "Show"
        parts = cleaned.split()
        show_parts = []
        for part in parts:
            # Stop at season/episode marker
            if part.upper().startswith("S") and len(part) >= 3 and part[1:].replace("E", "").isdigit():
                break
            show_parts.append(part)
        show_name = " ".join(show_parts) if show_parts else cleaned

        # Check for existing matching folder (no year check for TV shows)
        if tvshows_dir.is_dir():
            candidates = [d for d in tvshows_dir.iterdir() if d.is_dir()]
            match = find_matching_directory(show_name, candidates, respect_year=False)
            if match is not None:
                return match

        return tvshows_dir / show_name


class DefaultStrategy(SortingStrategy):
    """Place items in their type-specific directory (flat).

    Used for ebooks (003-EBOOKS/), audio (004-AUDIO/), apps (005-APPS/),
    and other (098-AUTRES/).
    """

    def __init__(self, file_type: FileType) -> None:
        """Initialize with the target file type.

        Args:
            file_type: The FileType determining the destination directory.
        """
        self.file_type = file_type

    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner) -> Path:
        """Return the type-specific directory path.

        Args:
            name: Raw filename or directory name (unused for default).
            staging_dir: Root staging directory.
            cleaner: NameCleaner (unused for default strategy).

        Returns:
            The type-specific directory path.
        """
        dir_map = get_type_dir_map()
        return staging_dir / dir_map.get(self.file_type, dir_map[FileType.OTHER])
