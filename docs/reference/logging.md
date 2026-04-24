# Logging convention

## Why

The codebase historically had three parallel mechanisms for producing output from
production modules: `structlog` (via `get_logger`), stdlib `logging.getLogger`, and
raw `print()`. This created drift in the JSON log file (mix of key/value structlog
events and formatted strings), made context binding inconsistent, and left reviewers
guessing which style to use in new code. The convention below defines one canonical
call site per channel so that every new logging call lands in the right place
automatically.

## Event naming guideline

Event names are part of the **observability contract** — renames break log aggregation dashboards and regression pins in `tests/test_event_names.py`.

Rules:

- **Snake_case throughout** — no camelCase, no hyphens.
- **Prefix by module concern** — e.g. `ingest_*`, `dispatch_*`, `scrape_*`, `tvdb_*`, `tmdb_*`, `circuit_*`, `verify_*` (illustrative; many other prefixes exist).
- **Past-tense preferred for state changes** (`_moved_ok`, `_login_failed`, `_opened`, `_closed`, `_started`, `_completed`). Noun phrases are acceptable for recognized error states (e.g. `_lockout`, `_unexpected_error`) where past tense would be awkward.
- **Stability** — treat event names as public API: a rename is a breaking change.

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
log.info("rsync_start", source=src, dest=dst)
log.warning("ffprobe_failed", path=str(path), error=str(exc))
log.error("nfo_generation_failed", title=title, error=str(exc))
log.exception("ingest_qbit_login_failed", host=host)
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

| Pattern (legacy)                                         | Replacement                                                                                                                  |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `logger = logging.getLogger(__name__)`                   | `log = get_logger("<short-tag>")`                                                                                            |
| `logger.info("moved %s to %s", src, dst)`                | `log.info("moved", source=src, dest=dst)`                                                                                    |
| `logger.warning("disk low: %s GB free", free)`           | `log.warning("disk_usage_failed", free_gb=free)`                                                                             |
| `logger.exception("fail")`                               | `log.exception("event_name", **context)` — `exc_info` implicit, never pass it                                                |
| `logger.error(f"Dispatch failed for {title}")`           | `log.error("replace_swap_failed", title=title)`                                                                              |
| `print(...)` in CLI commands                             | `state["console"].print(...)`                                                                                                |
| `print(...)` next to `input(...)`                        | `typer.echo(...)`                                                                                                            |
| `before_sleep=before_sleep_log(logger, logging.WARNING)` | `build_retry_logger(log, "event_name")` from `personalscraper.scraper.http_retry` (see `scraper/tmdb_client.py` as template) |

## exc_info rules

Three rules apply to every structlog call site in the codebase:

**Rule A — `log.exception()` never takes `exc_info=...`.**
`exc_info` is implicit for `.exception()`. Passing it is redundant and confusing.

```python
# correct
log.exception("nfo_generation_failed", title=title)

# wrong — do not do this
log.exception("nfo_generation_failed", exc_info=True, title=title)
```

**Rule B — Non-exception levels inside `except` use `exc_info=True, error=str(exc)`.**
For `log.warning()`, `log.error()`, `log.info()` inside an `except` block, attach the
traceback explicitly with `exc_info=True` and include the message via `error=str(exc)`.

```python
except OSError as exc:
    log.warning("disk_usage_failed", disk=disk.id, exc_info=True, error=str(exc))
```

**Rule C — Never pass an exception instance as `exc_info` inside an active `except` block.**
`exc_info=exc` is banned inside `except` blocks project-wide. Always use `exc_info=True`. If the
exception message is useful, add `error=str(exc)` alongside.

```python
# correct
log.error("nfo_generation_failed", title=title, exc_info=True, error=str(exc))

# wrong — do not do this
log.error("nfo_generation_failed", title=title, exc_info=exc)
```

**RULE D — Callbacks outside active `except` blocks.**

For loggers invoked OUTSIDE an active `except` block (e.g. tenacity `before_sleep` callbacks,
signal handlers, async result handlers), `exc_info=True` does not work because `sys.exc_info()`
is empty. Pass the exception INSTANCE directly so structlog can render the traceback from it.

```python
# In a tenacity before_sleep callback
def _cb(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    log.warning("tmdb_retry", attempt=..., exc_info=exc if exc is not None else False, error=str(exc) if exc is not None else None)
```

Wrong:

```python
exc_info=True   # sys.exc_info() is empty outside an active except — no traceback will render
```

See `personalscraper/scraper/http_retry.py` (`build_retry_logger`) for the canonical implementation.

## Enforcement

The convention is enforced by `scripts/check_logging.py` (AST walker) and surfaced
via `make lint-logging` (also included in the default `make lint` target).

Four rules:

| Rule                  | Violation                                                                                                                                                                                           | Severity |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `no-print`            | `print(` in `personalscraper/`                                                                                                                                                                      | error    |
| `no-stdlib-logger`    | `logging.getLogger` in `personalscraper/` (except `personalscraper/logger.py`); also catches aliased imports (`import logging as lg`) and bare imports (`from logging import getLogger [as alias]`) | error    |
| `no-structlog-direct` | `structlog.get_logger(...)` / `structlog.getLogger(...)` called directly — always go through `personalscraper.logger.get_logger`                                                                    | error    |
| `no-fstring-log`      | `log.info(f"…")` — f-string as event arg (indicates string-mode logging)                                                                                                                            | warning  |

Run manually:

```bash
python scripts/check_logging.py          # report only
make lint-logging                        # exit non-zero on errors
make lint                                # includes lint-logging
```

## Broad exception handling convention

When catching `except Exception` is unavoidable (e.g. wrapping third-party adapters with
unpredictable exception hierarchies, or safety catch-alls that must preserve pipeline
continuation), annotate the line with `# noqa: BLE001 — <rationale>` explaining why
narrowing is not feasible.

```python
# Correct — best-effort fallback where narrowing would suppress legitimate unknowns
except Exception as exc:  # noqa: BLE001 — best-effort fallback; notification must not mask the underlying operation
    log.exception("telegram_unexpected_error", error=str(exc))

# Also correct — cross-module exception set makes narrowing impractical
except Exception as e:  # noqa: BLE001 — catches TVDBError, requests.ConnectionError, CircuitOpenError; narrowing requires 3 cross-module imports
    log.warning("show_tvdb_fallback_tmdb", title=title, exc_info=True, error=str(e))
```

Reference templates: `personalscraper/notifier.py:73`, `personalscraper/scraper/confidence.py:241`.

**Scope**: this is mandatory for **new code** added during review. A sweep of the 20+ pre-existing
broad-except sites is out of scope per DESIGN §2 (only new/touched code is in scope).

## Pointers

- `personalscraper/logger.py` — structlog factory, `configure_logging()`, `get_logger()`.
- `scripts/check_logging.py` — AST walker enforcing the convention above.
- `docs/features/logging/DESIGN.md` — original design document (archived post-merge).
