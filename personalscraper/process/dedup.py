"""Fuzzy duplicate folder detection and merging.

Compares folder pairs within a category directory using fuzzy matching.
When duplicates are found (e.g. "Shrinking" + "Shrinking (2023)"),
merges the less-complete folder into the more-complete one.
"""

import logging
import re
from pathlib import Path

from personalscraper.text_utils import fuzzy_match_score

logger = logging.getLogger(__name__)

# Extract year from "Title (YYYY)" pattern
_YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


def _extract_year(name: str) -> int | None:
    """Extract year from folder name if present.

    Args:
        name: Folder name, e.g. "Shrinking (2023)".

    Returns:
        Year as int, or None.
    """
    m = _YEAR_RE.search(name)
    return int(m.group(1)) if m else None


def _completeness_score(folder: Path) -> tuple[int, int, int]:
    """Score a folder's completeness for merge priority.

    Higher score = more complete = should be the merge target.
    Returns a tuple for lexicographic comparison:
    (has_nfo, file_count, has_poster).

    Args:
        folder: Path to a media folder.

    Returns:
        Tuple of (has_nfo, file_count, has_poster) for comparison.
    """
    has_nfo = 1 if any(folder.glob("*.nfo")) else 0
    file_count = sum(1 for _ in folder.rglob("*") if _.is_file())
    has_poster = 1 if any(folder.glob("*poster*")) else 0
    return (has_nfo, file_count, has_poster)


def dedup_folders(
    category_dir: Path,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Find and merge fuzzy duplicate folders within a category.

    Compares all folder pairs using fuzzy_match_score (with year guard,
    length ratio guard, and adaptive threshold). When duplicates are
    found, merges the less-complete folder into the more-complete one.

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.
        dry_run: If True, log without merging.

    Returns:
        Tuple of (merged_count, failed_count).
    """
    from personalscraper.scraper.scraper import _merge_dirs

    if not category_dir.exists():
        return 0, 0

    folders = sorted(
        [f for f in category_dir.iterdir() if f.is_dir() and not f.name.startswith(".")],
        key=lambda f: f.name,
    )

    merged = 0
    failed = 0
    # Track folders that have been merged away
    removed: set[str] = set()

    for i, folder_a in enumerate(folders):
        if folder_a.name in removed:
            continue
        year_a = _extract_year(folder_a.name)

        for folder_b in folders[i + 1 :]:
            if folder_b.name in removed:
                continue
            year_b = _extract_year(folder_b.name)

            score = fuzzy_match_score(
                folder_a.name,
                folder_b.name,
                query_year=year_a,
                candidate_year=year_b,
            )
            if score is None:
                continue

            # Determine which folder is more complete
            score_a = _completeness_score(folder_a)
            score_b = _completeness_score(folder_b)

            if score_b >= score_a:
                source, target = folder_a, folder_b
            else:
                source, target = folder_b, folder_a

            if dry_run:
                logger.info(
                    "[DRY-RUN] Would merge duplicate: %s → %s (score=%.0f)",
                    source.name,
                    target.name,
                    score,
                )
            else:
                try:
                    moved, merge_failed = _merge_dirs(source, target)
                    logger.info(
                        "Dedup merge: %s → %s (%d items, score=%.0f)",
                        source.name,
                        target.name,
                        moved,
                        score,
                    )
                    if merge_failed:
                        failed += 1
                        logger.warning(
                            "Dedup partial merge: %s → %s: %d items failed",
                            source.name,
                            target.name,
                            merge_failed,
                        )
                except OSError as exc:
                    logger.warning(
                        "Dedup merge failed: %s → %s: %s",
                        source.name,
                        target.name,
                        exc,
                    )
                    failed += 1
                    continue

            removed.add(source.name)
            merged += 1
            break  # folder_a was merged, move to next

    return merged, failed
