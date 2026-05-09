"""Rich-console observer — CLI output extracted from the pipeline core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from personalscraper.pipeline_observer import StepEvent

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


class RichConsoleObserver:
    """Pipeline observer that renders progress to a rich Console.

    Extracts all console output from ``pipeline.py`` so the pipeline
    itself has zero dependency on ``rich.Console``.
    """

    name = "rich-console"

    def __init__(self, console: Console | None = None, *, verbose: bool = False) -> None:
        """Initialize the observer.

        Args:
            console: Rich console instance. Created if not provided.
            verbose: If True, emit per-item detail output.
        """
        self.console = console or Console()
        self.verbose = verbose

    @staticmethod
    def _icon(step: str) -> str:
        """Return the step number indicator for console output.

        Args:
            step: Step name.

        Returns:
            Formatted step number string (e.g. ``"[cyan]1/9[/cyan]"``).
        """
        icons = {
            "ingest": "[cyan]1/9[/cyan]",
            "sort": "[cyan]2/9[/cyan]",
            "clean": "[cyan]3/9[/cyan]",
            "scrape": "[cyan]4/9[/cyan]",
            "cleanup": "[cyan]5/9[/cyan]",
            "enforce": "[cyan]6/9[/cyan]",
            "verify": "[cyan]7/9[/cyan]",
            "trailers": "[cyan]8/9[/cyan]",
            "dispatch": "[cyan]9/9[/cyan]",
        }
        return icons.get(step, "")

    def on_pipeline_start(self, report: PipelineReport) -> None:  # noqa: ARG002
        """No-op — banner is printed by CLI before ``Pipeline.run()``."""

    def on_pipeline_end(self, report: PipelineReport) -> None:
        """Print the final summary table.

        Args:
            report: The completed ``PipelineReport`` with all step results.
        """
        dur = report.duration()
        minutes = int(dur.total_seconds()) // 60
        seconds = int(dur.total_seconds()) % 60
        dur_str = f"{minutes}min {seconds:02d}s" if minutes else f"{seconds}s"

        table = Table(show_header=True, header_style="bold")
        table.add_column("Step")
        table.add_column("OK", justify="right")
        table.add_column("Skip", justify="right")
        table.add_column("Err", justify="right")
        for name, step in report.steps.items():
            err_style = "red" if step.error_count else ""
            table.add_row(
                name.capitalize(),
                str(step.success_count),
                str(step.skip_count),
                f"[{err_style}]{step.error_count}[/{err_style}]" if err_style else str(step.error_count),
            )
        status_text = "[green]OK[/green]" if not report.has_errors() else "[red]ERRORS[/red]"
        self.console.print(Panel(table, title=f"Pipeline {status_text} — {dur_str}", border_style="bold"))

    def on_step_start(self, step: str) -> None:
        """Print step header.

        Args:
            step: Step name for display.
        """
        icon = self._icon(step)
        self.console.print(f"\n{icon} [bold]{step.upper()}[/bold]", highlight=False)

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:  # noqa: ARG002
        """Print step summary line and verbose details.

        Args:
            step: Step name.
            report: The completed ``StepReport``.
            elapsed: Step duration in seconds.
        """
        elapsed_str = f"{elapsed:.1f}s"
        ok = report.success_count
        skip = report.skip_count
        err = report.error_count
        parts = []
        if ok:
            parts.append(f"[green]{ok} OK[/green]")
        if skip:
            parts.append(f"[yellow]{skip} skip[/yellow]")
        if err:
            parts.append(f"[red]{err} err[/red]")
        summary = ", ".join(parts) if parts else "[dim]nothing to do[/dim]"
        self.console.print(f"   {summary} ({elapsed_str})", highlight=False)

        if self.verbose:
            for detail in report.details:
                if "skipped_already_done" in detail:
                    continue
                self.console.print(f"   [dim]{detail}[/dim]", highlight=False)
            for warning in report.warnings:
                self.console.print(f"   [yellow]! {warning}[/yellow]", highlight=False)

    def on_step_error(self, step: str, error: Exception) -> None:  # noqa: ARG002
        """Print fatal error message.

        Args:
            step: Step name.
            error: The exception that was raised.
        """
        error_msg = f"{type(error).__name__}: {error}"
        self.console.print(f"   [red]FATAL: {error_msg}[/red]", highlight=False)

    def on_progress(self, event: StepEvent) -> None:
        """Print per-item detail in verbose mode.

        Args:
            event: The progress event to render.
        """
        if not self.verbose:
            return
        self.console.print(
            f"   [dim]{event.step}: {event.item} — {event.status}[/dim]",
            highlight=False,
        )

    # Interface compliance — these are already covered above.
    # PipelineObserver is structural (Protocol), not nominal (ABC),
    # so runtime_checkable works without explicit inheritance.
