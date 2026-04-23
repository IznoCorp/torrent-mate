"""Automatic media fixer for correctable quality issues.

Attempts to fix issues identified by MediaChecker, primarily:
- Directory renaming to match "Title (Year)" format (from NFO data)
- Artwork file renaming to match NamingPatterns

Each fix produces a FixAction describing what was done. In dry-run mode,
FixActions are created but no filesystem changes are made.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import CheckResult

log = get_logger("verify.fixer")


@dataclass
class FixAction:
    """Description of a correction applied to a media directory.

    Attributes:
        description: Human-readable description of the fix.
        old_path: Original path before the fix.
        new_path: New path after the fix (None if not a rename).
    """

    description: str
    old_path: Path
    new_path: Path | None = None


class MediaFixer:
    """Attempt automatic corrections for fixable quality issues.

    Processes CheckResult lists from MediaChecker and applies fixes
    where possible (fixable=True). Supports dry-run mode.

    Attributes:
        patterns: Naming patterns for correct filenames.
        dry_run: If True, describe fixes without applying them.
    """

    def __init__(self, patterns: NamingPatterns, dry_run: bool = False):
        """Initialize the fixer.

        Args:
            patterns: MediaElch naming patterns.
            dry_run: If True, log fixes without applying them.
        """
        self.patterns = patterns
        self.dry_run = dry_run

    def fix_movie(self, movie_dir: Path, checks: list[CheckResult]) -> list[FixAction]:
        """Fix correctable issues in a movie directory.

        Supported fixes:
        - dir_naming: Rename directory from NFO title/year
        - artwork: Rename misnamed artwork files

        Args:
            movie_dir: Path to the movie directory.
            checks: CheckResult list from MediaChecker.check_movie().

        Returns:
            List of FixAction for each correction applied.
        """
        actions: list[FixAction] = []
        failed_names = {c.name for c in checks if not c.passed and c.fixable}

        # Fix directory naming from NFO
        if "dir_naming" in failed_names:
            action = self._fix_dir_naming_from_nfo(movie_dir, "movie")
            if action:
                actions.append(action)
                # Update movie_dir reference if renamed
                if action.new_path and not self.dry_run:
                    movie_dir = action.new_path

        return actions

    def fix_tvshow(self, show_dir: Path, checks: list[CheckResult]) -> list[FixAction]:
        """Fix correctable issues in a TV show directory.

        Supported fixes:
        - dir_naming: Rename directory from NFO title/year

        Args:
            show_dir: Path to the TV show directory.
            checks: CheckResult list from MediaChecker.check_tvshow().

        Returns:
            List of FixAction for each correction applied.
        """
        actions: list[FixAction] = []
        failed_names = {c.name for c in checks if not c.passed and c.fixable}

        if "dir_naming" in failed_names:
            action = self._fix_dir_naming_from_nfo(show_dir, "tvshow")
            if action:
                actions.append(action)

        return actions

    def _fix_dir_naming_from_nfo(self, media_dir: Path, media_type: str) -> FixAction | None:
        """Rename a directory using title and year from its NFO file.

        Args:
            media_dir: Current directory path.
            media_type: "movie" or "tvshow".

        Returns:
            FixAction if renamed, None if NFO not found or parse fails.
        """
        # Find NFO file
        if media_type == "movie":
            nfo_files = list(media_dir.glob("*.nfo"))
        else:
            nfo_files = [media_dir / "tvshow.nfo"]

        nfo_path = None
        for f in nfo_files:
            if f.exists():
                nfo_path = f
                break

        if not nfo_path:
            return None

        # Parse NFO for title and year
        try:
            tree = ET.parse(nfo_path)  # noqa: S314
            root = tree.getroot()
        except (ET.ParseError, OSError) as exc:
            log.warning("verify_fixer_nfo_parse_error", nfo=nfo_path.name, exc_info=exc)
            return None

        title = root.findtext("title", "").strip()
        year = root.findtext("year", "").strip()

        if not title:
            return None

        # Build canonical name
        if year:
            canonical = f"{title} ({year})"
        else:
            canonical = title

        if media_dir.name == canonical:
            return None

        new_dir = media_dir.parent / canonical
        if new_dir.exists():
            log.warning("verify_fixer_target_exists", canonical=canonical)
            return None

        description = f"Renamed '{media_dir.name}' → '{canonical}'"

        if not self.dry_run:
            try:
                media_dir.rename(new_dir)
                log.info("verify_fixer_dir_renamed", description=description)
            except OSError as e:
                log.error("verify_fixer_rename_failed", exc_info=e)
                return None

        return FixAction(
            description=description,
            old_path=media_dir,
            new_path=new_dir,
        )
