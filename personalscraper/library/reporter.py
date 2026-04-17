"""Library reporter — aggregate statistics from all JSON data files.

Reads scan, analysis, validation, and recommendation JSON files from
.personalscraper/ and produces a comprehensive library health report.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class LibraryReport:
    """Aggregated library health report.

    Attributes:
        generated_at: ISO 8601 timestamp.
        total_items: Total media items across all disks.
        total_size_gb: Total library size in GB.
        items_per_disk: Item count per disk.
        items_per_category: Item count per category.
        size_per_disk_gb: Total size per disk in GB.
        actors_dir_count: Number of items with .actors/ directories.
        nfo_valid_count: Items with valid NFOs.
        nfo_invalid_count: Items with missing or invalid NFOs.
        poster_missing_count: Items without poster artwork.
        codec_distribution: File count per video codec.
        audio_distribution: File count per audio profile.
        top_largest: Top 20 largest items (path, size_gb).
        recommendation_count: Total recommendations.
        estimated_savings_gb: Estimated savings from all recommendations.
        recommendations_by_priority: Recommendation count per priority.
        validation_valid: Items passing validation.
        validation_fixable: Items that can be auto-fixed.
        validation_issues: Items failing validation.
        disk_free_gb: Free space per disk in GB.
    """

    generated_at: str = ""
    total_items: int = 0
    total_size_gb: float = 0.0
    items_per_disk: dict[str, int] = field(default_factory=dict)
    items_per_category: dict[str, int] = field(default_factory=dict)
    size_per_disk_gb: dict[str, float] = field(default_factory=dict)
    actors_dir_count: int = 0
    nfo_valid_count: int = 0
    nfo_invalid_count: int = 0
    poster_missing_count: int = 0
    codec_distribution: dict[str, int] = field(default_factory=dict)
    audio_distribution: dict[str, int] = field(default_factory=dict)
    top_largest: list[tuple[str, float]] = field(default_factory=list)
    recommendation_count: int = 0
    estimated_savings_gb: float = 0.0
    recommendations_by_priority: dict[str, int] = field(default_factory=dict)
    validation_valid: int = 0
    validation_fixable: int = 0
    validation_issues: int = 0
    disk_free_gb: dict[str, float] = field(default_factory=dict)


def generate_report(
    scan_data: dict | None = None,
    analysis_data: dict | None = None,
    validation_data: dict | None = None,
    recommendation_data: dict | None = None,
    disk_statuses: list | None = None,
) -> LibraryReport:
    """Generate a library health report from JSON data.

    Each parameter is optional — report includes whatever data is available.

    Args:
        scan_data: Parsed library_scan.json.
        analysis_data: Parsed library_analysis.json.
        validation_data: Parsed library_validation.json.
        recommendation_data: Parsed library_recommendations.json.
        disk_statuses: List of DiskStatus objects for live free space.

    Returns:
        LibraryReport with aggregated statistics.
    """
    report = LibraryReport(generated_at=datetime.now(tz=timezone.utc).isoformat())

    # --- Scan data ---
    if scan_data:
        items = scan_data.get("items", [])
        report.total_items = len(items)

        disk_counter: Counter[str] = Counter()
        category_counter: Counter[str] = Counter()
        disk_size: dict[str, float] = {}
        size_list: list[tuple[str, float]] = []

        for item in items:
            disk = item.get("disk", "unknown")
            category = item.get("category", "unknown")
            size = item.get("folder_size_gb", 0.0)

            disk_counter[disk] += 1
            category_counter[category] += 1
            disk_size[disk] = disk_size.get(disk, 0.0) + size
            report.total_size_gb += size

            if item.get("actors_dir"):
                report.actors_dir_count += 1

            nfo = item.get("nfo", {})
            if nfo.get("valid"):
                report.nfo_valid_count += 1
            else:
                report.nfo_invalid_count += 1

            artwork = item.get("artwork", {})
            if not artwork.get("poster"):
                report.poster_missing_count += 1

            title = item.get("title", item.get("path", "unknown"))
            size_list.append((title, size))

        report.items_per_disk = dict(disk_counter)
        report.items_per_category = dict(category_counter)
        report.size_per_disk_gb = {k: round(v, 1) for k, v in disk_size.items()}
        report.total_size_gb = round(report.total_size_gb, 1)

        # Top 20 largest
        size_list.sort(key=lambda x: -x[1])
        report.top_largest = size_list[:20]

    # --- Analysis data ---
    if analysis_data:
        codec_counter: Counter[str] = Counter()
        audio_counter: Counter[str] = Counter()

        for item in analysis_data.get("items", []):
            for f in item.get("files", []):
                video = f.get("video", {})
                codec = video.get("codec", "unknown")
                codec_counter[codec] += 1

                profile = f.get("audio_profile", "unknown")
                audio_counter[profile] += 1

        report.codec_distribution = dict(codec_counter)
        report.audio_distribution = dict(audio_counter)

    # --- Disk free space (from live DiskStatus objects) ---
    if disk_statuses:
        for ds in disk_statuses:
            if hasattr(ds, "config") and hasattr(ds, "free_space_gb"):
                report.disk_free_gb[ds.config.name] = round(ds.free_space_gb, 1)

    # --- Validation data ---
    if validation_data:
        report.validation_valid = validation_data.get("valid_count", 0)
        report.validation_fixable = validation_data.get("fixed_count", 0)
        report.validation_issues = validation_data.get("issues_count", 0)

    # --- Recommendation data ---
    if recommendation_data:
        report.recommendation_count = recommendation_data.get("total_recommendations", 0)
        report.estimated_savings_gb = recommendation_data.get("estimated_total_savings_gb", 0.0)

        priority_counter: Counter[str] = Counter()
        for rec in recommendation_data.get("items", []):
            priority_counter[rec.get("priority", "unknown")] += 1
        report.recommendations_by_priority = dict(priority_counter)

    return report


def format_report_text(report: LibraryReport) -> str:
    """Format a LibraryReport as human-readable text.

    Args:
        report: Report to format.

    Returns:
        Formatted multi-line string.
    """
    lines = [
        "=" * 60,
        "LIBRARY HEALTH REPORT",
        f"Generated: {report.generated_at}",
        "=" * 60,
        "",
        f"Total items: {report.total_items}",
        f"Total size: {report.total_size_gb:.1f} GB",
        "",
    ]

    if report.items_per_disk:
        lines.append("--- Items per disk ---")
        for disk, count in sorted(report.items_per_disk.items()):
            size = report.size_per_disk_gb.get(disk, 0)
            lines.append(f"  {disk}: {count} items ({size:.1f} GB)")
        lines.append("")

    if report.items_per_category:
        lines.append("--- Items per category ---")
        for cat, count in sorted(report.items_per_category.items()):
            lines.append(f"  {cat}: {count}")
        lines.append("")

    lines.append("--- Health ---")
    lines.append(f"  NFO valid: {report.nfo_valid_count}")
    lines.append(f"  NFO invalid/missing: {report.nfo_invalid_count}")
    lines.append(f"  Poster missing: {report.poster_missing_count}")
    lines.append(f"  .actors/ present: {report.actors_dir_count}")
    lines.append("")

    if report.codec_distribution:
        lines.append("--- Codec distribution ---")
        for codec, count in sorted(report.codec_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"  {codec}: {count} files")
        lines.append("")

    if report.audio_distribution:
        lines.append("--- Audio profile distribution ---")
        for profile, count in sorted(report.audio_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"  {profile}: {count} files")
        lines.append("")

    if report.recommendation_count:
        lines.append("--- Recommendations ---")
        lines.append(f"  Total: {report.recommendation_count}")
        lines.append(f"  Estimated savings: {report.estimated_savings_gb:.1f} GB")
        for prio, count in sorted(report.recommendations_by_priority.items()):
            lines.append(f"  {prio}: {count}")
        lines.append("")

    if report.top_largest:
        lines.append("--- Top 20 largest items ---")
        for title, size in report.top_largest:
            lines.append(f"  {size:>7.1f} GB  {title}")
        lines.append("")

    if report.validation_valid or report.validation_issues:
        total = report.validation_valid + report.validation_issues
        pct = (report.validation_valid / total * 100) if total else 0
        lines.append("--- Validation ---")
        lines.append(f"  Valid: {report.validation_valid} ({pct:.0f}%)")
        lines.append(f"  Issues: {report.validation_issues}")
        lines.append("")

    return "\n".join(lines)
