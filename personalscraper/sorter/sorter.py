"""Main sorting orchestrator for the V2 pipeline step.

Processes all items from a source directory (typically 097-TEMP/), detects
their type, cleans their names, and moves them into the correct category
subdirectory (001-MOVIES/, 002-TVSHOWS/, etc.) under a destination root.
Returns a list of SortResult for reporting and downstream pipeline steps.
"""

import logging
import os
import shutil
from pathlib import Path

from personalscraper.models import SortResult
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType, detect_dir_type, detect_file_type
from personalscraper.sorter.strategies import (
    DefaultStrategy,
    MovieStrategy,
    SortingStrategy,
    TVShowStrategy,
    get_type_dir_map,
)

logger = logging.getLogger(__name__)


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

    Processes all items from a source directory, detecting their type,
    cleaning names, and sorting them into subdirectories under a
    destination root.

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

    def process(self, source_dir: Path, dest_root: Path | None = None) -> list[SortResult]:
        """Sort all items from source_dir into type subdirectories under dest_root.

        Iterates over direct children of source_dir (files and directories),
        skipping known sorted directories (001-MOVIES, 002-TVSHOWS, etc.)
        and hidden files. Each item is processed independently — errors on
        one item don't stop processing of others.

        Args:
            source_dir: Directory to scan for unsorted items (e.g. 097-TEMP/).
            dest_root: Root directory for category subdirectories (001-MOVIES/,
                002-TVSHOWS/, etc.). Defaults to source_dir for backward compat.

        Returns:
            List of SortResult for each processed item.
        """
        if dest_root is None:
            dest_root = source_dir

        results: list[SortResult] = []

        if not source_dir.exists():
            logger.warning("Source directory does not exist: %s", source_dir)
            return results

        # Sort the items list to get deterministic ordering
        items = sorted(source_dir.iterdir(), key=lambda p: p.name)

        # Directories that are sorting destinations — skip them during processing
        skip_dirs = frozenset(get_type_dir_map().values())

        for item in items:
            # Skip sorted directories and hidden files
            if item.name in skip_dirs or item.name.startswith("."):
                continue
            result = self.sort_item(item, dest_root)
            results.append(result)

        return results

    def sort_item(self, item: Path, dest_root: Path) -> SortResult:
        """Sort a single file or directory.

        Detects type, determines destination via strategy, then moves
        the item (or logs in dry-run mode).

        Args:
            item: Path to the file or directory to sort.
            dest_root: Root directory where category subdirectories live.

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
            dest_dir = strategy.get_destination(item.name, dest_root, self.cleaner)

            # Extract metadata for the SortResult
            title = self.cleaner.clean(item.name)
            year = self.cleaner.extract_year(item.name)
            season, episode = self.cleaner.extract_season_episode(item.name)

            # Compute final destination path
            if file_type == FileType.MOVIE and item.is_dir():
                # Directory movies: move the whole dir into 001-MOVIES/
                dest_path = dest_dir
            else:
                # Files, TV shows, and all other types go INTO the target dir
                dest_path = dest_dir / item.name

            # Movie dirs replace existing; everything else skips
            is_movie_dir_replace = item.is_dir() and file_type == FileType.MOVIE and dest_path.exists()
            if dest_path.exists() and not is_movie_dir_replace:
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

            if self.dry_run:
                action = "replace" if is_movie_dir_replace else "move"
                logger.info("[DRY-RUN] Would %s %s -> %s", action, item, dest_path)
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

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if is_movie_dir_replace:
                # Crash-safe replace: backup old, move new, cleanup
                backup = dest_path.parent / f"{dest_path.name}.old.tmp"
                try:
                    os.rename(dest_path, backup)
                    shutil.move(str(item), str(dest_path))
                    shutil.rmtree(backup)
                except OSError:
                    if backup.exists() and not dest_path.exists():
                        os.rename(backup, dest_path)
                    raise
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
            logger.error("Error sorting %s: %s", item, exc, exc_info=True)
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
