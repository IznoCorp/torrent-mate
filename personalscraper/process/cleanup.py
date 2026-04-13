"""Recursive empty directory cleanup.

Bottom-up traversal removes leaf empty directories first, then checks
if parents became empty. Treats directories containing only .DS_Store
as empty. Never removes the category root directory itself.
"""

import logging
from pathlib import Path

from personalscraper.models import StepReport

logger = logging.getLogger(__name__)

# Files that don't count as "content" (macOS metadata)
_JUNK_FILES = frozenset({".DS_Store", "Thumbs.db"})


def _is_effectively_empty(directory: Path) -> bool:
    """Check if a directory is empty or contains only junk files.

    Args:
        directory: Path to check.

    Returns:
        True if the directory has no meaningful content.
    """
    for item in directory.iterdir():
        if item.name not in _JUNK_FILES:
            return False
    return True


def cleanup_empty_dirs(
    category_dir: Path,
    dry_run: bool = False,
) -> StepReport:
    """Recursively remove empty directories within a category.

    Bottom-up traversal: removes leaf empty dirs first, then checks
    if parent became empty. Directories containing only .DS_Store
    are treated as empty. The category_dir root is never removed.

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.
        dry_run: If True, log without deleting.

    Returns:
        StepReport with success_count = dirs removed.
    """
    report = StepReport(name="cleanup")
    if not category_dir.exists():
        return report

    # Bottom-up: walk deepest directories first
    # sorted(reverse=True) by path length gives bottom-up order
    all_dirs = sorted(
        [d for d in category_dir.rglob("*") if d.is_dir()],
        key=lambda d: len(d.parts),
        reverse=True,
    )

    for directory in all_dirs:
        # Never remove the category root
        if directory == category_dir:
            continue

        if not directory.exists():
            continue

        try:
            if not _is_effectively_empty(directory):
                continue
        except OSError as exc:
            logger.warning("Cannot access dir %s: %s", directory.name, exc)
            continue

        rel_path = directory.relative_to(category_dir)
        if dry_run:
            logger.info("[DRY-RUN] Would remove empty dir: %s", rel_path)
            report.success_count += 1
            report.details.append(f"[DRY-RUN] {rel_path}")
        else:
            try:
                # Remove junk files first, then the directory
                for junk in directory.iterdir():
                    junk.unlink()
                directory.rmdir()
                logger.info("Removed empty dir: %s", rel_path)
                report.success_count += 1
                report.details.append(str(rel_path))
            except OSError as exc:
                logger.warning("Failed to remove dir %s: %s", rel_path, exc)
                report.error_count += 1
                report.warnings.append(f"Failed to remove {rel_path}: {exc}")

    return report
