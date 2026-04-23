# Logging convention

## Why

The codebase historically had three parallel mechanisms for producing output from
production modules: `structlog` (via `get_logger`), stdlib `logging.getLogger`, and
raw `print()`. This created drift in the JSON log file (mix of key/value structlog
events and formatted strings), made context binding inconsistent, and left reviewers
guessing which style to use in new code. The convention below defines one canonical
call site per channel so that every new logging call lands in the right place
automatically.

## Channels

| Channel                | Use for                                                                                                   | API                                                                                 | Where it lands                |
| ---------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------- |
| **Structured log**     | Everything a developer or operator may want to grep/aggregate — errors, progress, decisions, side-effects | `log = get_logger("<module>")` + `log.info("event_name", key=value, ...)`           | Console (colored) + JSON file |
| **CLI UI**             | User-facing output in CLI commands — headers, tables, prompts rendering, summaries                        | `state["console"].print(...)` (Rich)                                                | TTY only                      |
| **Interactive prompt** | Read user input                                                                                           | `typer.prompt(...)` / `typer.confirm(...)`, `typer.echo(...)` for simple TTY output | TTY only                      |

## Canonical snippets

### Structured log

```python
from personalscraper.logger import get_logger

log = get_logger("my_module")

# Event name: snake_case, stable, grep-friendly.
# Context goes in kwargs — never in the event string.
log.info("dispatch_moved", source=src, dest=dst)
log.warning("disk_low", free_gb=free, threshold_gb=threshold)
log.error("scrape_failed", title=title, reason=str(exc))
log.exception("scrape_failed", exc_info=True, title=title)
```

### CLI UI

```python
# Rich console passed through Typer context state.
# Use for headers, tables, progress summaries — anything user-facing.
state["console"].print("[bold green]Done.[/bold green]")
state["console"].print(table)  # rich.table.Table
```

### Interactive prompt

```python
import typer

# Structured yes/no or free-text input.
confirmed = typer.confirm("Move 42 files?", default=True)
value = typer.prompt("Enter target disk", default="disk1")

# Simple plain-text TTY output (no Rich formatting needed).
typer.echo("Processing…")
```

## Migration recipes

| Pattern (legacy)                                         | Replacement                                                                               |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `logger = logging.getLogger(__name__)`                   | `log = get_logger("<short-tag>")`                                                         |
| `logger.info("moved %s to %s", src, dst)`                | `log.info("moved", source=src, dest=dst)`                                                 |
| `logger.warning("disk low: %s GB free", free)`           | `log.warning("disk_low", free_gb=free)`                                                   |
| `logger.exception("fail")`                               | `log.exception("event_name", exc_info=True, **context)`                                   |
| `logger.error(f"Dispatch failed for {title}")`           | `log.error("dispatch_failed", title=title)`                                               |
| `print(...)` in CLI commands                             | `state["console"].print(...)`                                                             |
| `print(...)` next to `input(...)`                        | `typer.echo(...)`                                                                         |
| `before_sleep=before_sleep_log(logger, logging.WARNING)` | custom `_log_retry_warning("event_name")` callback (see `scraper/artwork.py` as template) |

## Enforcement

The convention is enforced by `scripts/check_logging.py` (AST walker) and surfaced
via `make lint-logging` (also included in the default `make lint` target).

Three rules:

| Violation                                                                      | Severity |
| ------------------------------------------------------------------------------ | -------- |
| `logging.getLogger` in `personalscraper/` (except `personalscraper/logger.py`) | error    |
| `print(` in `personalscraper/`                                                 | error    |
| `log.info(f"…")` — f-string as event arg (indicates string-mode logging)       | warning  |

Run manually:

```bash
python scripts/check_logging.py          # report only
make lint-logging                        # exit non-zero on errors
make lint                                # includes lint-logging
```

## Pointers

- `personalscraper/logger.py` — structlog factory, `configure_logging()`, `get_logger()`.
- `scripts/check_logging.py` — AST walker enforcing the convention above.
- `docs/features/logging/DESIGN.md` — original design document (archived post-merge).
