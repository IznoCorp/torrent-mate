"""Shared dataclass models used across multiple pipeline versions.

Convention: only models shared between 2+ versions live here.
Version-specific models (ScrapeResult, VerifyResult, DispatchResult)
are defined in their respective modules.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class SortResult:
    """Result of sorting a single media file/directory.

    Attributes:
        source: Source path in staging area (A TRIER/).
        destination: Target path (001-MOVIES/, 002-TVSHOWS/, etc.).
        media_type: Detected type ("movie", "episode", "audio", "ebook", etc.).
        title: Extracted title.
        year: Detected year, if any.
        season: Detected season number, if any (V2 cleaner).
        episode: Detected episode number, if any (V2 cleaner).
        status: Result status ("moved", "skipped", "error").
        message: Error message or additional info.
    """

    source: Path
    destination: Path
    media_type: str
    title: str
    year: int | None
    season: int | None
    episode: int | None
    status: str
    message: str | None


@dataclass
class StepReport:
    """Execution report for a single pipeline step.

    Each run_*() function (V1-V5) converts its internal results
    into a StepReport before returning.

    Attributes:
        name: Step identifier ("ingest", "sort", "scrape", "verify", "dispatch").
        success_count: Number of successfully processed items.
        skip_count: Number of skipped items.
        error_count: Number of failed items.
        warnings: Warning messages collected during execution.
        details: Per-item detail strings for reporting.
    """

    name: str
    success_count: int = 0
    skip_count: int = 0
    error_count: int = 0
    warnings: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


@dataclass
class PipelineReport:
    """Aggregated report for a full pipeline run (V6).

    Collects StepReports from each pipeline step and provides
    summary methods for notifications and console display.

    Attributes:
        started_at: Pipeline start timestamp.
        steps: Ordered dict of step name to StepReport.
        finished_at: Pipeline end timestamp (None if still running).
    """

    started_at: datetime
    steps: dict[str, StepReport] = field(default_factory=dict)
    finished_at: datetime | None = None

    def add_step(self, name: str, step: StepReport) -> None:
        """Add a completed StepReport to the pipeline report.

        Args:
            name: Step identifier (e.g. "ingest", "sort").
            step: The completed StepReport to add.
        """
        self.steps[name] = step

    def duration(self) -> timedelta:
        """Calculate total pipeline duration.

        Returns:
            Time elapsed between started_at and finished_at,
            or zero if finished_at is not set.
        """
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        return timedelta()

    def has_errors(self) -> bool:
        """Check if any step reported errors.

        Returns:
            True if at least one step has error_count > 0.
        """
        return any(s.error_count > 0 for s in self.steps.values())

    def to_html(self) -> str:
        """Format report as Telegram HTML message.

        Produces a compact, emoji-rich summary suitable for
        Telegram's parse_mode="HTML" (supports b, i, code, a tags).

        Returns:
            HTML string suitable for Telegram's parse_mode="HTML".
        """
        # Step name → emoji mapping for visual identification (7 steps)
        step_icons = {
            "ingest": "\U0001f4e5",    # 📥
            "sort": "\U0001f4c2",      # 📂
            "clean": "\U0001f9f9",     # 🧹
            "scrape": "\U0001f50d",    # 🔍
            "cleanup": "\U0001f5d1",   # 🗑
            "verify": "\u2705",        # ✅
            "dispatch": "\U0001f4be",  # 💾
        }

        header_emoji = "\u2705" if not self.has_errors() else "\u274c"
        lines = [f"\U0001f4ca <b>PersonalScraper \u2014 Rapport</b> {header_emoji}"]

        for name, step in self.steps.items():
            icon = step_icons.get(name, "\u2022")
            parts = []
            if step.success_count:
                parts.append(f"{step.success_count} OK")
            if step.skip_count:
                parts.append(f"{step.skip_count} skip")
            if step.error_count:
                parts.append(f"{step.error_count} err")
            summary = ", ".join(parts) if parts else "aucun item"

            lines.append(f"{icon} <b>{name.capitalize()}</b>: {summary}")

            # Include details (first 5 per step to avoid message bloat)
            for detail in step.details[:5]:
                lines.append(f"  \u2022 {detail}")
            if len(step.details) > 5:
                lines.append(f"  \u2026 +{len(step.details) - 5} autres")

            # Show warnings inline
            for warning in step.warnings[:3]:
                lines.append(f"  \u26a0\ufe0f {warning}")

        # Duration and timestamp footer
        dur = self.duration()
        minutes = int(dur.total_seconds()) // 60
        seconds = int(dur.total_seconds()) % 60
        dur_str = f"{minutes}min {seconds:02d}s" if minutes else f"{seconds}s"
        lines.append(f"\u23f1\ufe0f Dur\u00e9e : {dur_str}")

        if self.finished_at:
            lines.append(
                f"\U0001f4c5 {self.finished_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        return "\n".join(lines)
