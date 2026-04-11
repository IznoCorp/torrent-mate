from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class SortResult:
    """Résultat du tri d'un fichier/dossier média."""
    source: Path
    destination: Path
    media_type: str       # "movie", "episode", "audio", "ebook", etc.
    title: str
    year: int | None
    season: int | None
    episode: int | None
    status: str           # "moved", "skipped", "error"
    message: str | None


@dataclass
class StepReport:
    """Rapport d'exécution d'une étape du pipeline.
    Chaque run_*() (V1-V5) convertit ses résultats internes en StepReport."""
    name: str             # "ingest", "sort", "scrape", "verify", "dispatch"
    success_count: int = 0
    skip_count: int = 0
    error_count: int = 0
    warnings: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


@dataclass
class PipelineReport:
    """Aggregated report for a full pipeline run (V6)."""
    started_at: datetime
    steps: dict[str, StepReport] = field(default_factory=dict)
    finished_at: datetime | None = None

    def add_step(self, name: str, step: StepReport) -> None:
        """Add a completed StepReport to the pipeline report."""
        self.steps[name] = step

    def duration(self) -> timedelta:
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        return timedelta()

    def has_errors(self) -> bool:
        return any(s.error_count > 0 for s in self.steps.values())

    def to_html(self) -> str:
        """Format report as Telegram HTML message."""
        lines = ["<b>PersonalScraper — Rapport</b>"]
        for name, step in self.steps.items():
            status = "\u2705" if step.error_count == 0 else "\u274c"
            lines.append(
                f"{status} <b>{name}</b>: {step.success_count} OK, {step.error_count} err, {step.skip_count} skip"
            )
        lines.append(f"\u23f1\ufe0f Dur\u00e9e : {self.duration()}")
        return "\n".join(lines)
