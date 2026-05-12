"""Rich-console subscriber for the in-process EventBus.

Self-subscribes to the six pipeline-lifecycle events on construction and
renders progress to a ``rich.Console``. Output is locked by the canonical
snapshot ``tests/snapshots/rich_console_canonical.txt``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.pipeline_events import (
    ItemProgressed,
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


class RichConsoleSubscriber:
    """Pipeline subscriber that renders progress to a rich Console.

    The class self-subscribes to ``PipelineStarted``, ``PipelineEnded``,
    ``StepStarted``, ``StepCompleted``, ``StepErrored`` and ``ItemProgressed``
    in ``__init__``. ``close()`` unsubscribes every stored token so test
    fixtures can dispose of the subscriber cleanly.
    """

    name = "rich-console"

    def __init__(
        self,
        bus: EventBus,
        console: Console | None = None,
        *,
        verbose: bool = False,
        dry_run: bool = False,
        run_id: str = "",
    ) -> None:
        """Initialize the subscriber and register six bus subscriptions.

        Args:
            bus: The :class:`EventBus` instance to subscribe to.
            console: Rich console instance. Created if not provided.
            verbose: If True, emit per-item detail output.
            dry_run: If True, label the banner as DRY-RUN.
            run_id: Pipeline run identifier for the banner.
        """
        self.console = console or Console()
        self._verbose = verbose
        self._dry_run = dry_run
        self._run_id: str | None = run_id if run_id else None
        self._bus = bus
        self._tokens: list[SubscriptionToken] = [
            bus.subscribe(PipelineStarted, self._on_pipeline_started),
            bus.subscribe(PipelineEnded, self._on_pipeline_ended),
            bus.subscribe(StepStarted, self._on_step_started),
            bus.subscribe(StepCompleted, self._on_step_completed),
            bus.subscribe(StepErrored, self._on_step_errored),
            bus.subscribe(ItemProgressed, self._on_item_progressed),
        ]

    def close(self) -> None:
        """Unsubscribe every stored token. Safe to call multiple times."""
        for token in self._tokens:
            self._bus.unsubscribe(token)
        self._tokens = []

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

    def _render_pipeline_start(self, report: PipelineReport) -> None:
        """Print the pipeline banner.

        Args:
            report: Freshly created ``PipelineReport`` with ``started_at``.
        """
        run_id = self._run_id or report.started_at.isoformat(timespec="seconds")
        mode = "[yellow]DRY-RUN[/yellow]" if self._dry_run else "[green]LIVE[/green]"
        self.console.print(
            f"[bold]PersonalScraper Pipeline[/bold] {mode}  [dim]{run_id}[/dim]",
            highlight=False,
        )

    def _render_pipeline_end(self, report: PipelineReport) -> None:
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

    def _render_step_start(self, step: str) -> None:
        """Print step header."""
        icon = self._icon(step)
        self.console.print(f"\n{icon} [bold]{step.upper()}[/bold]", highlight=False)

    def _render_step_end(self, step: str, report: StepReport, elapsed: float) -> None:  # noqa: ARG002
        """Print step summary line and verbose details."""
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

        if self._verbose:
            for detail in report.details:
                if "skipped_already_done" in detail:
                    continue
                self.console.print(f"   [dim]{detail}[/dim]", highlight=False)
            for warning in report.warnings:
                self.console.print(f"   [yellow]! {warning}[/yellow]", highlight=False)

    def _render_step_error(self, error_class: str, error_message: str) -> None:
        """Print fatal error message."""
        self.console.print(f"   [red]FATAL: {error_class}: {error_message}[/red]", highlight=False)

    def _render_item_progress(self, step: str, item: str, status: str) -> None:
        """Print per-item detail in verbose mode."""
        if not self._verbose:
            return
        self.console.print(
            f"   [dim]{step}: {item} — {status}[/dim]",
            highlight=False,
        )

    # ----- Bus callbacks --------------------------------------------------

    def _on_pipeline_started(self, event: PipelineStarted) -> None:
        """Handle :class:`PipelineStarted` — render the banner."""
        self._render_pipeline_start(event.report)

    def _on_pipeline_ended(self, event: PipelineEnded) -> None:
        """Handle :class:`PipelineEnded` — render the summary panel."""
        self._render_pipeline_end(event.report)

    def _on_step_started(self, event: StepStarted) -> None:
        """Handle :class:`StepStarted` — render the step header."""
        self._render_step_start(event.step)

    def _on_step_completed(self, event: StepCompleted) -> None:
        """Handle :class:`StepCompleted` — render the step summary line."""
        self._render_step_end(event.step, event.report, event.elapsed_s)

    def _on_step_errored(self, event: StepErrored) -> None:
        """Handle :class:`StepErrored` — render the FATAL line."""
        self._render_step_error(event.error_class, event.error_message)

    def _on_item_progressed(self, event: ItemProgressed) -> None:
        """Handle :class:`ItemProgressed` — render per-item progress."""
        self._render_item_progress(event.step, event.item, event.status)
