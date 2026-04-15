# Phase 7: Reporter — library-report command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `personalscraper library-report` — aggregate stats from all JSON files into a human-readable report. Supports `--format json`.

**Architecture:** `reporter.py` loads scan, analysis, validation, and recommendation JSON files from `.personalscraper/`. Produces summary stats using Rich tables for terminal output and JSON for machine consumption.

**Tech Stack:** Python, Typer, Rich (tables, panels), pytest

---

## Task 1: Implement reporter core logic

**Files:**

- Create: `personalscraper/library/reporter.py`
- Create: `tests/library/test_reporter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_reporter.py
"""Tests for personalscraper.library.reporter — library statistics."""

from personalscraper.library.reporter import generate_report, LibraryReport


class TestGenerateReport:
    """Tests for report generation from JSON data."""

    def test_empty_report(self) -> None:
        """Report with no data should have zero counts."""
        report = generate_report(scan_data=None, analysis_data=None,
                                  validation_data=None, recommendation_data=None)
        assert report.total_items == 0
        assert report.total_size_gb == 0.0

    def test_report_from_scan(self) -> None:
        """Report should aggregate scan data."""
        scan_data = {
            "scanned_at": "2026-04-15T12:00:00",
            "item_count": 3,
            "items": [
                {"disk": "Disk1", "category": "films", "media_type": "movie",
                 "folder_size_gb": 2.0, "actors_dir": True, "issues": ["actors_dir_present"],
                 "nfo": {"present": True, "valid": True}, "artwork": {"poster": True}},
                {"disk": "Disk1", "category": "films", "media_type": "movie",
                 "folder_size_gb": 3.5, "actors_dir": False, "issues": [],
                 "nfo": {"present": True, "valid": True}, "artwork": {"poster": True}},
                {"disk": "Disk2", "category": "series", "media_type": "tvshow",
                 "folder_size_gb": 15.0, "actors_dir": True, "issues": ["actors_dir_present"],
                 "nfo": {"present": True, "valid": False}, "artwork": {"poster": False}},
            ],
        }
        report = generate_report(scan_data=scan_data)
        assert report.total_items == 3
        assert report.total_size_gb == 20.5
        assert report.items_per_disk["Disk1"] == 2
        assert report.items_per_disk["Disk2"] == 1
        assert report.items_per_category["films"] == 2
        assert report.actors_dir_count == 2
        assert report.nfo_valid_count == 2
        assert report.nfo_invalid_count == 1

    def test_report_from_analysis(self) -> None:
        """Report should aggregate codec distribution from analysis."""
        analysis_data = {
            "item_count": 2, "file_count": 3,
            "items": [
                {"files": [
                    {"video": {"codec": "hevc"}, "audio_profile": "multi", "size_gb": 2.0},
                ]},
                {"files": [
                    {"video": {"codec": "h264"}, "audio_profile": "vf", "size_gb": 5.0},
                    {"video": {"codec": "h264"}, "audio_profile": "vo", "size_gb": 4.0},
                ]},
            ],
        }
        report = generate_report(analysis_data=analysis_data)
        assert report.codec_distribution["hevc"] == 1
        assert report.codec_distribution["h264"] == 2
        assert report.audio_distribution["multi"] == 1
        assert report.audio_distribution["vf"] == 1
        assert report.audio_distribution["vo"] == 1

    def test_report_from_recommendations(self) -> None:
        """Report should include recommendation summary."""
        rec_data = {
            "total_recommendations": 5,
            "estimated_total_savings_gb": 12.5,
            "items": [
                {"priority": "high"}, {"priority": "high"},
                {"priority": "medium"}, {"priority": "medium"}, {"priority": "low"},
            ],
        }
        report = generate_report(recommendation_data=rec_data)
        assert report.recommendation_count == 5
        assert report.estimated_savings_gb == 12.5
        assert report.recommendations_by_priority["high"] == 2
        assert report.recommendations_by_priority["medium"] == 2
        assert report.recommendations_by_priority["low"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_reporter.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement reporter.py**

```python
# personalscraper/library/reporter.py
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
        validation_blocked: Items failing validation.
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
    validation_blocked: int = 0


def generate_report(
    scan_data: dict | None = None,
    analysis_data: dict | None = None,
    validation_data: dict | None = None,
    recommendation_data: dict | None = None,
) -> LibraryReport:
    """Generate a library health report from JSON data.

    Each parameter is optional — report includes whatever data is available.

    Args:
        scan_data: Parsed library_scan.json.
        analysis_data: Parsed library_analysis.json.
        validation_data: Parsed library_validation.json.
        recommendation_data: Parsed library_recommendations.json.

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
            elif nfo.get("present") and not nfo.get("valid"):
                report.nfo_invalid_count += 1
            elif not nfo.get("present"):
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

    # --- Validation data ---
    if validation_data:
        report.validation_valid = validation_data.get("valid_count", 0)
        report.validation_blocked = validation_data.get("blocked_count", 0)

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

    if report.validation_valid or report.validation_blocked:
        total = report.validation_valid + report.validation_blocked
        pct = (report.validation_valid / total * 100) if total else 0
        lines.append("--- Validation ---")
        lines.append(f"  Valid: {report.validation_valid} ({pct:.0f}%)")
        lines.append(f"  Blocked: {report.validation_blocked}")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_reporter.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/reporter.py tests/library/test_reporter.py
git commit -m "v14.7.1: Implement reporter with scan/analysis/validation/recommendation aggregation"
```

---

## Task 2: Add library-report CLI command

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryReport:
    def test_help(self, runner) -> None:
        result = runner.invoke(app, ["library-report", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
```

- [ ] **Step 2: Add command to cli.py**

```python
@app.command()
@handle_cli_errors
def library_report(
    format: str = typer.Option("text", "--format", help="Output format: text or json"),
) -> None:
    """Display library statistics and health report.

    Aggregates data from scan, analysis, validation, and recommendations.
    Run other library commands first to populate the data.

    Examples:
        personalscraper library-report
        personalscraper library-report --format json
    """
    from personalscraper.library.models import read_json, write_json
    from personalscraper.library.reporter import format_report_text, generate_report

    console = state["console"]
    settings = get_settings()

    # Load available data
    def _load(name: str) -> dict | None:
        path = settings.data_dir / name
        if path.exists():
            try:
                return read_json(path)
            except (OSError, ValueError):
                return None
        return None

    scan_data = _load("library_scan.json")
    analysis_data = _load("library_analysis.json")
    validation_data = _load("library_validation.json")
    recommendation_data = _load("library_recommendations.json")

    if not any([scan_data, analysis_data, validation_data, recommendation_data]):
        console.print("[yellow]No library data found. Run library-scan or library-analyze first.[/yellow]")
        raise typer.Exit(1)

    report = generate_report(scan_data, analysis_data, validation_data, recommendation_data)

    if format == "json":
        output_path = settings.data_dir / "library_report.json"
        write_json(report, output_path)
        console.print(f"[green]Report written to {output_path}[/green]")
    else:
        console.print(format_report_text(report))
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_cli.py::TestLibraryReport tests/library/test_reporter.py -v`
Expected: ALL PASS

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "v14.7.2: Add library-report CLI with text and JSON output"
```

---

## Acceptance Criteria — Phase 7

- [ ] Report aggregates scan, analysis, validation, and recommendation data
- [ ] Items per disk/category, codec/audio distribution, top 20 largest
- [ ] Validation summary (% valid, % blocked)
- [ ] Recommendation summary with savings estimate
- [ ] `--format json` writes to `library_report.json`
- [ ] Graceful handling when some data files don't exist yet
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
