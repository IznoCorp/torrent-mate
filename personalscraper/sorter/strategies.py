"""Sorting strategies for placing media items into destination directories.

Each strategy determines the target subdirectory based on media type:
- MovieStrategy: {dirname}/Title (Year)/
- TVShowStrategy: {dirname}/Show Name/
- DefaultStrategy: type-specific directory ({dirname}/)

Strategies use fuzzy matching to find existing folders and prevent duplicates.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, staging_path
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType
from personalscraper.sorter.matcher import find_matching_directory

_log = logging.getLogger(__name__)


class SortingStrategy(ABC):
    """Base class for sorting strategies.

    Each strategy computes a destination path for a media item based on
    its cleaned name and the staging directory structure.
    """

    @abstractmethod
    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config: Config) -> Path:
        """Compute the destination path for a media item.

        Args:
            name: Raw filename or directory name of the item being sorted.
            staging_dir: Root staging directory (staging/).
            cleaner: NameCleaner for title/year extraction.
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            The destination Path where the item should be moved.
        """


class MovieStrategy(SortingStrategy):
    """Place movies in {dirname}/Title (Year)/ subfolders.

    Uses fuzzy matching to find existing movie folders and prevent
    duplicates. If a match is found, returns the existing folder.
    Otherwise creates a new folder named 'Title (Year)' or 'Title'.
    """

    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config: Config) -> Path:
        """Return {dirname}/Title (Year)/ or existing matching folder.

        Args:
            name: Raw movie filename or directory name.
            staging_dir: Root staging directory.
            cleaner: NameCleaner for title/year extraction.
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            Destination path inside the movies staging directory.
        """
        entry = find_by_file_type(config, FileType.MOVIE)
        movies_dir = staging_path(config, entry)
        clean_name = cleaner.clean_for_folder(name)

        # Check for existing matching folder
        if movies_dir.is_dir():
            candidates = [d for d in movies_dir.iterdir() if d.is_dir()]
            match = find_matching_directory(clean_name, candidates, respect_year=True)
            if match is not None:
                return match

        return movies_dir / clean_name


class TVShowStrategy(SortingStrategy):
    """Place TV shows in {dirname}/Show Name/ subfolders.

    Sort creates folders WITHOUT year (e.g. 'Shrinking/', not 'Shrinking (2023)/');
    year is added after API matching in the scraping step. Uses fuzzy matching
    to merge new episodes into existing show folders.
    """

    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config: Config) -> Path:
        """Return {dirname}/Show Name/ or existing matching folder.

        Args:
            name: Raw TV show filename or directory name.
            staging_dir: Root staging directory.
            cleaner: NameCleaner for title extraction.
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            Destination path inside the TV shows staging directory.
        """
        entry = find_by_file_type(config, FileType.TVSHOW)
        tvshows_dir = staging_path(config, entry)

        # Extract show name without season/episode info and without year.
        # Sort creates "Show Name/"; the scraping step renames to "Show Name (Year)/".
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

    Used for ebooks, audio, apps, and other types.
    """

    def __init__(self, file_type: FileType) -> None:
        """Initialize with the target file type.

        Args:
            file_type: The FileType determining the destination directory.
        """
        self.file_type = file_type

    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config: Config) -> Path:
        """Return the type-specific directory path.

        Args:
            name: Raw filename or directory name (unused for default strategy).
            staging_dir: Root staging directory.
            cleaner: NameCleaner (unused for default strategy).
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            The type-specific directory path.
        """
        try:
            entry = find_by_file_type(config, self.file_type)
        except KeyError:
            # Warn operator: this file_type has no dedicated staging dir.
            # Log available types so the config gap is immediately actionable.
            available = [e.file_type for e in config.staging_dirs if e.file_type is not None]
            _log.warning(
                "No staging entry for file_type=%r — falling back to FileType.OTHER. "
                "Available types: %r",
                self.file_type.value,
                available,
            )
            entry = find_by_file_type(config, FileType.OTHER)
        return staging_path(config, entry)
