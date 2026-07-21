"""Cross-step coherence checker for staging media.

Read-only checker that parses NFOs, verifies classifier-based genre
consistency, and checks sort↔process coherence. Produces
warnings, never modifies the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import personalscraper.verify.checks  # trigger registration  # noqa: F401
from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.core.media_types import FileType
from personalscraper.naming_patterns import PATTERNS
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.verify.checks.base import CheckContext, CheckStage
from personalscraper.verify.checks.registry import registry


def _coherence_for(
    media_dir: Path,
    media_type: str,
    config: Config,
    only: frozenset[str] | None = None,
) -> CoherenceResult:
    """Build a CoherenceResult by running all STAGING checks for media_type.

    Args:
        media_dir: Path to the media directory.
        media_type: "movie" or "tvshow" — the bucket the item was found under.
        config: Config for classifier rules.
        only: Optional allow-set of check names restricting the run to the
            named STAGING-stage checks. ``None`` (default) runs every check —
            byte-identical to the pre-filter behavior.

    Returns:
        CoherenceResult aggregating check names and warning messages.
    """
    ctx = CheckContext(
        media_dir=media_dir,
        media_type=media_type,
        stage=CheckStage.STAGING,
        config=config,
        patterns=PATTERNS,
    )
    results = [
        r for check in registry.checks_for_filtered(CheckStage.STAGING, media_type, only) for r in check.run(ctx)
    ]
    return CoherenceResult(
        path=media_dir,
        checks=[r.name for r in results],
        warnings=[r.message for r in results if not r.passed and r.message],
    )


@dataclass
class CoherenceResult:
    """Result of coherence check for one media item.

    Attributes:
        path: Absolute path to the media directory.
        checks: List of check names that were performed.
        warnings: Human-readable non-fatal issues found.
    """

    path: Path
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_coherence(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    only: frozenset[str] | None = None,
    *,
    bus: EventBus,
) -> list[CoherenceResult]:
    """Check cross-step coherence for all staging items.

    Iterates over every media directory in {movies_dir} and {tvshows_dir},
    verifying sort/process coherence and NFO metadata consistency.
    This function is read-only — it never modifies the filesystem.

    F8 real lifecycle: an ``ItemProgressed(status="started")`` is emitted on
    *bus* for each media directory BEFORE its coherence checks run. The terminal
    ``ItemProgressed`` is recorded by ``run_enforce`` from the returned results.

    Args:
        settings: Pipeline configuration (reserved for future use).
        config: Config used to resolve staging_dir and by the classifier for genre coherence.
        dry_run: No effect (coherence check is always read-only).
        only: Optional allow-set of check names restricting the run to the
            named STAGING-stage checks. ``None`` (default) runs every check —
            byte-identical to the pre-filter behavior.
        bus: Required in-process EventBus for the per-item ``started`` events.

    Returns:
        List of CoherenceResult, one per media directory found.
    """
    _ = dry_run  # coherence is always read-only
    results: list[CoherenceResult] = []
    staging = config.paths.staging_dir

    movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
    if movies_dir.exists():
        for folder in sorted(movies_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                bus.emit(ItemProgressed(step="enforce", item=folder.name, status="started"))
                results.append(_coherence_for(folder, "movie", config, only))

    tvshows_dir = staging / folder_name(find_by_file_type(config, FileType.TVSHOW))
    if tvshows_dir.exists():
        for folder in sorted(tvshows_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                bus.emit(ItemProgressed(step="enforce", item=folder.name, status="started"))
                results.append(_coherence_for(folder, "tvshow", config, only))

    return results
