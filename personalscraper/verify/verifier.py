"""Verify orchestrator: check → fix → re-check → categorize.

Runs the DISPATCH-stage check plugins (via the singleton registry) and
``apply_fixes`` to validate media directories before dispatch. Produces
VerifyResult for each media item with status (valid/fixed/blocked) and
category assignment.
"""

from dataclasses import dataclass, field
from pathlib import Path

import personalscraper.verify.checks  # noqa: F401 — trigger plugin registration
from personalscraper.conf.classifier import classify_from_nfo
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.nfo_utils import glob_nfo_candidates
from personalscraper.verify.checks.base import CheckContext, CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import apply_fixes, registry

log = get_logger("verify.verifier")

# Module-level single source of truth for the verify fix policy (mirrors
# ``_LIBRARY_FIX_POLICY`` in library_checks.py). Phase 7 flips THIS one
# constant for both verify_movie AND verify_tvshow — do NOT inline it as a
# method-local variable.
_VERIFY_FIX_POLICY = frozenset({"dir_naming"})


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
        checks_passed: Number of checks that passed (set by ``_classify``).
        checks_total: Total number of checks run (set by ``_classify``).
    """

    media_path: Path
    media_type: str
    category: str | None = None
    status: str = "blocked"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)
    checks_passed: int = 0
    checks_total: int = 0


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
        config: Config,
        dry_run: bool = False,
        fix: bool = True,
        only: frozenset[str] | None = None,
    ):
        """Initialize the verifier with patterns and classifier config.

        Args:
            settings: Pipeline configuration.
            patterns: Naming patterns for verification.
            config: Config with category IDs and classification rules.
            dry_run: If True, preview without modifying files.
            fix: If True, attempt to fix correctable issues.
            only: Optional allow-set of check names to restrict every verify
                run to. ``None`` (default) runs every DISPATCH-stage check —
                byte-identical to the pre-filter behavior.
        """
        self.fix = fix
        self.dry_run = dry_run
        self._config = config
        self._patterns = patterns
        self._only = only

    def _new_ctx(self, media_dir: Path, media_type: str) -> CheckContext:
        """Build a DISPATCH-stage CheckContext for ``media_dir``.

        Args:
            media_dir: Path to the media directory.
            media_type: "movie" or "tvshow".

        Returns:
            A fresh CheckContext (the ``category`` plugin writes
            ``resolved_category`` onto it during the check loop, which
            ``_classify`` later reads).
        """
        return CheckContext(
            media_dir=media_dir,
            media_type=media_type,
            stage=CheckStage.DISPATCH,
            config=self._config,
            patterns=self._patterns,
            dry_run=self.dry_run,
        )

    def _run_checks(self, ctx: CheckContext) -> list[CheckResult]:
        """Run all DISPATCH-stage check plugins for ``ctx``'s media type.

        Mirrors ``MediaChecker.check_movie``/``check_tvshow`` exactly (same
        registry loop, same order). ``run()`` is read-only, so re-running
        after fixes is side-effect-free aside from ``resolved_category``.

        Honors ``self._only`` — when it is ``None`` (the default) the loop is
        byte-identical to the unfiltered ``checks_for`` output.

        Args:
            ctx: Shared check context (drives the registry loop and carries
                ``resolved_category`` for ``_classify``).

        Returns:
            Ordered list of CheckResult for this stage/media type.
        """
        return [
            r for check in registry.checks_for_filtered(ctx.stage, ctx.media_type, self._only) for r in check.run(ctx)
        ]

    def verify_movie(self, movie_dir: Path) -> VerifyResult:
        """Verify a single movie directory.

        Flow: check → fix (if enabled) → re-check → categorize.

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            VerifyResult with status and category.
        """
        result = VerifyResult(media_path=movie_dir, media_type="movie")

        # First check — run the registry loop with verify's OWN ctx so the
        # ``category`` plugin writes resolved_category onto the ctx we later
        # pass to _classify (CMP-3: classify_from_nfo called once per verify).
        ctx = self._new_ctx(movie_dir, "movie")
        checks = self._run_checks(ctx)

        # Fix if enabled and fixable issues exist
        if self.fix:
            fixable_fails = [c for c in checks if not c.passed and c.fixable]
            if fixable_fails:
                actions = apply_fixes(ctx, fixable_fails, _VERIFY_FIX_POLICY)
                result.fixes_applied = [a.description for a in actions]
                # Update movie_dir if renamed; rebuild ctx on the new path
                for a in actions:
                    if a.new_path and not self.dry_run:
                        movie_dir = a.new_path
                        result.media_path = movie_dir
                        ctx = self._new_ctx(movie_dir, "movie")
                # Re-check after fixes (re-populates ctx.resolved_category)
                checks = self._run_checks(ctx)

        # Classify results — ctx carries resolved_category
        self._classify(result, checks, movie_dir, "movie", ctx)
        return result

    def verify_tvshow(self, show_dir: Path) -> VerifyResult:
        """Verify a single TV show directory.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            VerifyResult with status and category.
        """
        result = VerifyResult(media_path=show_dir, media_type="tvshow")

        ctx = self._new_ctx(show_dir, "tvshow")
        checks = self._run_checks(ctx)

        if self.fix:
            fixable_fails = [c for c in checks if not c.passed and c.fixable]
            if fixable_fails:
                actions = apply_fixes(ctx, fixable_fails, _VERIFY_FIX_POLICY)
                result.fixes_applied = [a.description for a in actions]
                for a in actions:
                    if a.new_path and not self.dry_run:
                        show_dir = a.new_path
                        result.media_path = show_dir
                        ctx = self._new_ctx(show_dir, "tvshow")
                checks = self._run_checks(ctx)

        self._classify(result, checks, show_dir, "tvshow", ctx)
        return result

    def verify_all_movies(self, movies_dir: Path) -> list[VerifyResult]:
        """Verify all movie subdirectories.

        Args:
            movies_dir: Path to the movies root (e.g. {movies_dir}/).

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
            except Exception as exc:
                log.error("verify_movie_error", movie=d.name, exc_info=True, error=str(exc))
                results.append(
                    VerifyResult(
                        media_path=d,
                        media_type="movie",
                        status="blocked",
                        errors=[str(exc)],
                    )
                )

        return results

    def verify_all_tvshows(self, tvshows_dir: Path) -> list[VerifyResult]:
        """Verify all TV show subdirectories.

        Args:
            tvshows_dir: Path to the TV shows root (e.g. {tvshows_dir}/).

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
            except Exception as exc:
                log.error("verify_tvshow_error", show=d.name, exc_info=True, error=str(exc))
                results.append(
                    VerifyResult(
                        media_path=d,
                        media_type="tvshow",
                        status="blocked",
                        errors=[str(exc)],
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
        ctx: CheckContext,
    ) -> None:
        """Classify a VerifyResult based on check results.

        Sets status, errors, warnings, and category.

        Args:
            result: VerifyResult to populate.
            checks: Final check results (after any fixes).
            media_dir: Current media directory path.
            media_type: "movie" or "tvshow".
            ctx: The check context whose ``category`` plugin already resolved
                the category (CMP-3: reused instead of re-classifying).
        """
        result.errors = [c.message for c in checks if not c.passed and c.severity == Severity.ERROR]
        result.warnings = [c.message for c in checks if not c.passed and c.severity == Severity.WARNING]

        # Record check counts for structured telemetry (verify_item_done events).
        result.checks_total = len(checks)
        result.checks_passed = sum(1 for c in checks if c.passed)

        # Determine category. Reuse ctx.resolved_category (set by the ``category``
        # plugin during the check loop) so classify_from_nfo runs once per verify;
        # fall back to a fresh classify only if the plugin left it None (e.g. a
        # pre-built ctx that never ran the loop).
        cat_check = next((c for c in checks if c.name == "category"), None)
        if cat_check and cat_check.passed:
            if ctx.resolved_category is not None:
                result.category = ctx.resolved_category
            else:
                nfo_path = self._find_nfo(media_dir, media_type)
                if nfo_path:
                    category_id, _reason = classify_from_nfo(self._config, nfo_path, media_type)
                    result.category = category_id

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
        # Movie: find first .nfo file (deterministic sort, AppleDouble-safe)
        nfo_files = glob_nfo_candidates(media_dir)
        return nfo_files[0] if nfo_files else None
