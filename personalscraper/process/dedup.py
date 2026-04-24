"""Fuzzy duplicate folder detection and merging.

Compares folder pairs within a category directory using fuzzy matching.
When duplicates are found (e.g. "Shrinking" + "Shrinking (2023)"),
merges the less-complete folder into the more-complete one.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.text_utils import fuzzy_match_score

if TYPE_CHECKING:
    from personalscraper.conf.models import FuzzyMatchConfig

log = get_logger("process.dedup")

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
    fuzzy_config: FuzzyMatchConfig | None = None,
) -> tuple[int, int]:
    """Find and merge fuzzy duplicate folders within a category.

    Compares all folder pairs using fuzzy_match_score (with year guard,
    length ratio guard, and adaptive threshold). When duplicates are
    found, merges the less-complete folder into the more-complete one.

    Args:
        category_dir: Path to {movies_dir}/ or {tvshows_dir}/.
        dry_run: If True, log without merging.
        fuzzy_config: Optional thresholds from ``Config.fuzzy_match``.
            Defaults applied when None.

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
                config=fuzzy_config,
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
                log.info(
                    "process_dedup_would_merge",
                    source=source.name,
                    target=target.name,
                    score=round(score),
                )
            else:
                try:
                    moved, merge_failed = _merge_dirs(source, target)
                    log.info(
                        "process_dedup_merged",
                        source=source.name,
                        target=target.name,
                        moved=moved,
                        score=round(score),
                    )
                    if merge_failed:
                        failed += 1
                        log.warning(
                            "process_dedup_partial_merge",
                            source=source.name,
                            target=target.name,
                            failed_count=merge_failed,
                        )
                except OSError as exc:
                    log.warning(
                        "process_dedup_merge_failed",
                        source=source.name,
                        target=target.name,
                        exc_info=True,
                        error=str(exc),
                    )
                    failed += 1
                    continue

            removed.add(source.name)
            merged += 1
            break  # folder_a was merged, move to next

    return merged, failed
