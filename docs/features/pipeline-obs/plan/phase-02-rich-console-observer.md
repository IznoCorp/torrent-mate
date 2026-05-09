# Phase 2 — RichConsoleObserver

**Type**: core
**Codename**: pipeline-obs

## NO DEFERRAL

Every sub-phase fully implemented. Every callback produces exact parity with current
console output. No output difference tolerated.

## Gate (pre-phase)

- [x] Phase 1 complete — `PipelineObserver`, `PipelineObserverBase`, `StepEvent`, `notify_progress` exist
- [x] `pipeline_observer.py` imports clean

## Sub-phases

### Sub-phase 2.1 — `observers/` package init

**Files:**

- Create: `personalscraper/observers/__init__.py`

```python
"""Pipeline observer implementations."""

from personalscraper.observers.rich_console import RichConsoleObserver

__all__ = ["RichConsoleObserver"]
```

### Sub-phase 2.2 — RichConsoleObserver

**Files:**

- Create: `personalscraper/observers/rich_console.py`
- Create: `tests/unit/test_rich_console_observer.py`

**`personalscraper/observers/rich_console.py`:**

This observer absorbs ALL console output currently in `pipeline.py`'s `_run_step` and
`commands/pipeline.py`'s `run` command. Every callback reproduces the exact rich markup
that exists today.

```python
"""Rich-console observer — CLI output extracted from the pipeline core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from personalscraper.pipeline_observer import PipelineObserver, StepEvent

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


class RichConsoleObserver:
    """Pipeline observer that renders progress to a rich Console.

    Extracts all console output from ``pipeline.py`` so the pipeline
    itself has zero dependency on ``rich.Console``.
    """

    name = "rich-console"

    def __init__(self, console: Console | None = None, *, verbose: bool = False) -> None:
        self.console = console or Console()
        self.verbose = verbose

    # -- step icons (identical to pipeline.py:_step_icon) --------------------

    def _icon(self, step: str) -> str:
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

    # -- PipelineObserver callbacks ------------------------------------------

    def on_pipeline_start(self, report: PipelineReport) -> None:
        """Print the pipeline banner (from commands/pipeline.py)."""
        # Called from CLI which adds mode + run_id before creating observers,
        # so this is a no-op — banner is printed by CLI before Pipeline.run().
        pass

    def on_pipeline_end(self, report: PipelineReport) -> None:
        """Print the final summary table (from commands/pipeline.py)."""
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
        self.console.print(
            Panel(table, title=f"Pipeline {status_text} — {dur_str}", border_style="bold")
        )

    def on_step_start(self, step: str) -> None:
        """Print step header (from pipeline.py:_run_step)."""
        icon = self._icon(step)
        self.console.print(f"\n{icon} [bold]{step.upper()}[/bold]", highlight=False)

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:
        """Print step summary line + verbose details (from pipeline.py:_run_step)."""
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

    def on_step_error(self, step: str, error: Exception) -> None:
        """Print fatal error (from pipeline.py:_run_step)."""
        error_msg = f"{type(error).__name__}: {error}"
        self.console.print(f"   [red]FATAL: {error_msg}[/red]", highlight=False)

    def on_progress(self, event: StepEvent) -> None:
        """Print per-item detail in verbose mode."""
        if not self.verbose:
            return
        detail = event.details.get("detail", event.item)
        self.console.print(f"   [dim]{event.step}: {event.item} — {event.status}[/dim]", highlight=False)
```

### Sub-phase 2.3 — Tests

**`tests/unit/test_rich_console_observer.py`:**

```python
"""Tests for RichConsoleObserver."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from rich.console import Console

from personalscraper.models import PipelineReport, StepReport
from personalscraper.observers.rich_console import RichConsoleObserver
from personalscraper.pipeline_observer import StepEvent


class TestRichConsoleObserver:
    """RichConsoleObserver tests."""

    def test_name(self):
        obs = RichConsoleObserver()
        assert obs.name == "rich-console"

    def test_on_step_start_prints_header(self):
        console = Console(force_terminal=True, width=120, color_system="truecolor")
        console.print = MagicMock()
        obs = RichConsoleObserver(console=console)
        obs.on_step_start("ingest")
        console.print.assert_called_once()

    def test_on_step_end_prints_summary(self):
        console = Console(force_terminal=True, width=120, color_system="truecolor")
        console.print = MagicMock()
        obs = RichConsoleObserver(console=console)
        report = StepReport(name="ingest", success_count=3, skip_count=1)
        obs.on_step_end("ingest", report, 2.1)
        assert console.print.call_count >= 1

    def test_on_step_end_skips_already_done_in_verbose(self):
        console = Console(force_terminal=True, width=120, color_system="truecolor")
        console.print = MagicMock()
        obs = RichConsoleObserver(console=console, verbose=True)
        report = StepReport(
            name="ingest",
            success_count=1,
            details=["skipped_already_done: foo"],
        )
        obs.on_step_end("ingest", report, 0.5)
        # The "skipped_already_done" detail should be filtered
        printed_args = [str(call) for call in console.print.call_args_list]
        assert not any("skipped_already_done" in arg for arg in printed_args)

    def test_on_step_error_prints_fatal(self):
        console = Console(force_terminal=True, width=120, color_system="truecolor")
        console.print = MagicMock()
        obs = RichConsoleObserver(console=console)
        obs.on_step_error("ingest", ValueError("bad data"))
        console.print.assert_called_once()

    def test_on_progress_noop_when_not_verbose(self):
        console = Console(force_terminal=True, width=120, color_system="truecolor")
        console.print = MagicMock()
        obs = RichConsoleObserver(console=console, verbose=False)
        obs.on_progress(StepEvent(step="sort", item="x.mkv", status="moved"))
        console.print.assert_not_called()

    def test_on_progress_prints_in_verbose_mode(self):
        console = Console(force_terminal=True, width=120, color_system="truecolor")
        console.print = MagicMock()
        obs = RichConsoleObserver(console=console, verbose=True)
        obs.on_progress(StepEvent(step="sort", item="x.mkv", status="moved"))
        console.print.assert_called_once()

    def test_on_pipeline_end_prints_table(self):
        console = Console(force_terminal=True, width=120, color_system="truecolor")
        console.print = MagicMock()
        obs = RichConsoleObserver(console=console)
        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest", success_count=2))
        report.finished_at = datetime.now()
        obs.on_pipeline_end(report)
        assert console.print.call_count >= 1

    def test_icon_mapping(self):
        obs = RichConsoleObserver()
        assert "1/9" in obs._icon("ingest")
        assert "9/9" in obs._icon("dispatch")
        assert obs._icon("unknown") == ""
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] Manual check: `RichConsoleObserver` output matches current pipeline output format
- [ ] Commit: `feat(pipeline-obs): add RichConsoleObserver`
