"""Verify orchestrator: check → fix → re-check → categorize.

Coordinates MediaChecker and MediaFixer to validate media directories
before dispatch. Produces VerifyResult for each media item with
status (valid/fixed/blocked) and category assignment.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.genre_mapper import GenreMapper
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import CheckResult, MediaChecker, Severity
from personalscraper.verify.fixer import MediaFixer

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """Result of verifying a single media directory.

    Attributes:
        media_path: Path to the media directory.
        media_type: "movie" or "tvshow".
        category: Dispatch category ID (e.g. ``"movies"``, ``"anime"``).
        status: "valid" (no issues), "fixed" (issues corrected),
            or "blocked" (unresolvable errors).
        errors: Remaining blocking error messages.
        warnings: Non-blocking warning messages.
        fixes_applied: Descriptions of corrections made.
    """

    media_path: Path
    media_type: str
    category: str | None = None
    status: str = "blocked"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)


class Verifier:
    """Orchestrate media verification: check → fix → re-check → categorize.

    Attributes:
        fix: Whether to attempt automatic fixes.
        dry_run: Whether to preview without modifying files.
    """

    def __init__(
        self,
        settings: Settings,
        patterns: NamingPatterns,
        dry_run: bool = False,
        fix: bool = True,
    ):
        """Initialize the verifier with checker, fixer, and mapper.

        Args:
            settings: Pipeline configuration.
            patterns: Naming patterns for verification.
            dry_run: If True, preview without modifying files.
            fix: If True, attempt to fix correctable issues.
        """
        self.fix = fix
        self.dry_run = dry_run
        self._mapper = GenreMapper()
        self._checker = MediaChecker(patterns, self._mapper)
        self._fixer = MediaFixer(patterns, dry_run=dry_run)

    def verify_movie(self, movie_dir: Path) -> VerifyResult:
        """Verify a single movie directory.

        Flow: check → fix (if enabled) → re-check → categorize.

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            VerifyResult with status and category.
        """
        result = VerifyResult(media_path=movie_dir, media_type="movie")

        # First check
        checks = self._checker.check_movie(movie_dir)

        # Fix if enabled and fixable issues exist
        if self.fix:
            fixable_fails = [c for c in checks if not c.passed and c.fixable]
            if fixable_fails:
                actions = self._fixer.fix_movie(movie_dir, checks)
                result.fixes_applied = [a.description for a in actions]
                # Update movie_dir if renamed
                for a in actions:
                    if a.new_path and not self.dry_run:
                        movie_dir = a.new_path
                        result.media_path = movie_dir
                # Re-check after fixes
                checks = self._checker.check_movie(movie_dir)

        # Classify results
        self._classify(result, checks, movie_dir, "movie")
        return result

    def verify_tvshow(self, show_dir: Path) -> VerifyResult:
        """Verify a single TV show directory.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            VerifyResult with status and category.
        """
        result = VerifyResult(media_path=show_dir, media_type="tvshow")

        checks = self._checker.check_tvshow(show_dir)

        if self.fix:
            fixable_fails = [c for c in checks if not c.passed and c.fixable]
            if fixable_fails:
                actions = self._fixer.fix_tvshow(show_dir, checks)
                result.fixes_applied = [a.description for a in actions]
                for a in actions:
                    if a.new_path and not self.dry_run:
                        show_dir = a.new_path
                        result.media_path = show_dir
                checks = self._checker.check_tvshow(show_dir)

        self._classify(result, checks, show_dir, "tvshow")
        return result

    def verify_all_movies(self, movies_dir: Path) -> list[VerifyResult]:
        """Verify all movie subdirectories.

        Args:
            movies_dir: Path to the movies root (e.g. 001-MOVIES/).

        Returns:
            List of VerifyResult for each movie.
        """
        results: list[VerifyResult] = []
        if not movies_dir.exists():
            return results

        subdirs = sorted(d for d in movies_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

        for d in subdirs:
            try:
                results.append(self.verify_movie(d))
            except Exception as e:
                logger.error("Error verifying movie %s: %s", d.name, e)
                results.append(
                    VerifyResult(
                        media_path=d,
                        media_type="movie",
                        status="blocked",
                        errors=[str(e)],
                    )
                )

        return results

    def verify_all_tvshows(self, tvshows_dir: Path) -> list[VerifyResult]:
        """Verify all TV show subdirectories.

        Args:
            tvshows_dir: Path to the TV shows root (e.g. 002-TVSHOWS/).

        Returns:
            List of VerifyResult for each show.
        """
        results: list[VerifyResult] = []
        if not tvshows_dir.exists():
            return results

        subdirs = sorted(d for d in tvshows_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

        for d in subdirs:
            try:
                results.append(self.verify_tvshow(d))
            except Exception as e:
                logger.error("Error verifying show %s: %s", d.name, e)
                results.append(
                    VerifyResult(
                        media_path=d,
                        media_type="tvshow",
                        status="blocked",
                        errors=[str(e)],
                    )
                )

        return results

    @staticmethod
    def get_dispatchable(results: list[VerifyResult]) -> list[VerifyResult]:
        """Filter results to only dispatchable items.

        Returns items with status "valid" or "fixed" (not "blocked").

        Args:
            results: Full list of VerifyResult.

        Returns:
            Filtered list of dispatchable results.
        """
        return [r for r in results if r.status in ("valid", "fixed")]

    def _classify(
        self,
        result: VerifyResult,
        checks: list[CheckResult],
        media_dir: Path,
        media_type: str,
    ) -> None:
        """Classify a VerifyResult based on check results.

        Sets status, errors, warnings, and category.

        Args:
            result: VerifyResult to populate.
            checks: Final check results (after any fixes).
            media_dir: Current media directory path.
            media_type: "movie" or "tvshow".
        """
        result.errors = [c.message for c in checks if not c.passed and c.severity == Severity.ERROR]
        result.warnings = [c.message for c in checks if not c.passed and c.severity == Severity.WARNING]

        # Determine category
        cat_check = next((c for c in checks if c.name == "category"), None)
        if cat_check and cat_check.passed:
            # Get category from NFO
            nfo_path = self._find_nfo(media_dir, media_type)
            if nfo_path:
                result.category = self._mapper.categorize_from_nfo(nfo_path, media_type)

        # Determine status
        if result.errors:
            result.status = "blocked"
        elif result.fixes_applied:
            result.status = "fixed"
        else:
            result.status = "valid"

    @staticmethod
    def _find_nfo(media_dir: Path, media_type: str) -> Path | None:
        """Find the main NFO file in a media directory.

        Args:
            media_dir: Media directory path.
            media_type: "movie" or "tvshow".

        Returns:
            Path to NFO file, or None.
        """
        if media_type == "tvshow":
            nfo = media_dir / "tvshow.nfo"
            return nfo if nfo.exists() else None
        # Movie: find first .nfo file
        nfo_files = list(media_dir.glob("*.nfo"))
        return nfo_files[0] if nfo_files else None
