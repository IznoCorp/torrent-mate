"""Main sorting orchestrator for the V2 pipeline step.

Processes all items at the root of the staging directory, detects their
type, cleans their names, and moves them into the correct subdirectory
(001-MOVIES/, 002-TVSHOWS/, etc.). Returns a list of SortResult for
reporting and downstream pipeline steps.
"""

import logging
import shutil
from pathlib import Path

from personalscraper.models import SortResult
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType, detect_dir_type, detect_file_type
from personalscraper.sorter.strategies import (
    TYPE_DIR_MAP,
    DefaultStrategy,
    MovieStrategy,
    SortingStrategy,
    TVShowStrategy,
)

logger = logging.getLogger(__name__)

# Directories that are sorting destinations — skip them during processing
_SKIP_DIRS: frozenset[str] = frozenset(TYPE_DIR_MAP.values())


def _get_strategy(file_type: FileType) -> SortingStrategy:
    """Return the appropriate strategy for a file type.

    Args:
        file_type: The detected media type.

    Returns:
        A SortingStrategy instance for the given type.
    """
    if file_type == FileType.MOVIE:
        return MovieStrategy()
    if file_type == FileType.TVSHOW:
        return TVShowStrategy()
    return DefaultStrategy(file_type)


class Sorter:
    """Main sorting orchestrator.

    Processes all items at the root of a staging directory, detecting
    their type, cleaning names, and sorting them into subdirectories.

    Attributes:
        cleaner: NameCleaner instance for filename parsing.
        dry_run: If True, log actions without moving files.
    """

    def __init__(self, cleaner: NameCleaner | None = None, dry_run: bool = False) -> None:
        """Initialize the sorter.

        Args:
            cleaner: NameCleaner instance. Created if not provided.
            dry_run: If True, simulate moves without actually moving.
        """
        self.cleaner = cleaner or NameCleaner()
        self.dry_run = dry_run

    def process(self, staging_dir: Path) -> list[SortResult]:
        """Sort all items at the root of staging_dir into type subdirectories.

        Iterates over direct children of staging_dir (files and directories),
        skipping known sorted directories (001-MOVIES, 002-TVSHOWS, etc.).
        Each item is processed independently — errors on one item don't
        stop processing of others.

        Args:
            staging_dir: Root staging directory (A TRIER/).

        Returns:
            List of SortResult for each processed item.
        """
        results: list[SortResult] = []

        # Sort the items list to get deterministic ordering
        items = sorted(staging_dir.iterdir(), key=lambda p: p.name)

        for item in items:
            # Skip sorted directories and hidden files
            if item.name in _SKIP_DIRS or item.name.startswith("."):
                continue
            result = self.sort_item(item, staging_dir)
            results.append(result)

        return results

    def sort_item(self, item: Path, staging_dir: Path) -> SortResult:
        """Sort a single file or directory.

        Detects type, determines destination via strategy, then moves
        the item (or logs in dry-run mode).

        Args:
            item: Path to the file or directory to sort.
            staging_dir: Root staging directory for strategy resolution.

        Returns:
            SortResult with source, destination, type, and status.
        """
        try:
            # Detect type
            if item.is_dir():
                file_type = detect_dir_type(item)
            else:
                file_type = detect_file_type(item)

            # Get destination via strategy
            strategy = _get_strategy(file_type)
            dest_dir = strategy.get_destination(item.name, staging_dir, self.cleaner)

            # Extract metadata for the SortResult
            title = self.cleaner.clean(item.name)
            year = self.cleaner.extract_year(item.name)
            season, episode = self.cleaner.extract_season_episode(item.name)

            # Compute final destination path
            dest_path = dest_dir / item.name if file_type not in (FileType.MOVIE,) else dest_dir
            # For movies: item goes INTO the folder (dest_dir IS the movie folder)
            # For TV shows: item goes INTO the show folder
            # For others: item goes INTO the type directory
            if file_type == FileType.MOVIE:
                if item.is_dir():
                    # Directory movies: move the whole dir into 001-MOVIES/
                    dest_path = dest_dir
                else:
                    # File movies: move into 001-MOVIES/Title (Year)/
                    dest_path = dest_dir / item.name
            elif file_type == FileType.TVSHOW:
                # TV items go into the show folder
                dest_path = dest_dir / item.name
            else:
                # Default: flat into type directory
                dest_path = dest_dir / item.name

            # Check if already at destination
            if dest_path.exists():
                logger.warning("Already exists at destination: %s", dest_path)
                return SortResult(
                    source=item,
                    destination=dest_path,
                    media_type=file_type.value,
                    title=title,
                    year=year,
                    season=season,
                    episode=episode,
                    status="skipped",
                    message="Already exists at destination",
                )

            # Move or dry-run
            if self.dry_run:
                logger.info("[DRY-RUN] Would move %s -> %s", item, dest_path)
                return SortResult(
                    source=item,
                    destination=dest_path,
                    media_type=file_type.value,
                    title=title,
                    year=year,
                    season=season,
                    episode=episode,
                    status="dry-run",
                    message=None,
                )

            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if item.is_dir() and file_type == FileType.MOVIE:
                # Movie directories: move into the movies folder
                # dest_path is 001-MOVIES/Title (Year)/
                if dest_path.exists():
                    # Replace existing movie folder
                    shutil.rmtree(dest_path)
                shutil.move(str(item), str(dest_path))
            else:
                shutil.move(str(item), str(dest_path))

            logger.info("Moved %s -> %s", item, dest_path)
            return SortResult(
                source=item,
                destination=dest_path,
                media_type=file_type.value,
                title=title,
                year=year,
                season=season,
                episode=episode,
                status="moved",
                message=None,
            )

        except Exception as exc:
            logger.error("Error sorting %s: %s", item, exc)
            return SortResult(
                source=item,
                destination=Path(),
                media_type="unknown",
                title=item.name,
                year=None,
                season=None,
                episode=None,
                status="error",
                message=str(exc),
            )
