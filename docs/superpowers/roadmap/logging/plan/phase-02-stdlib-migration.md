# Phase 02 — stdlib `logging` → `structlog` Migration

**Goal**: every module in `personalscraper/` uses `get_logger(...)` with snake_case event names and keyword-argument context.

## Sub-phase 2.1 — Migrate the dispatch + ingest packages

Scope :

- `personalscraper/dispatch/**.py` (~7 files)
- `personalscraper/ingest/**.py` (~4 files)

Per file :

- Replace `import logging` + `logger = logging.getLogger(__name__)` with `from personalscraper.logger import get_logger` + `log = get_logger("<tag>")` where `<tag>` is the module's short name (e.g. `dispatcher`, `media_index`, `ingest`, `tracker`).
- Rewrite every `logger.<level>(msg, ...)` call :
  - Human-readable one-liners → `log.<level>("event_name", message=msg, **context_kwargs)`.
  - Format-string calls `logger.info("moved %s to %s", src, dst)` → `log.info("dispatch_moved", source=src, dest=dst)`.
  - Exception blocks → `log.exception("event_name", exc_info=True, **context)` preserving the existing exception-chain semantics.

Tests : run the dispatch + ingest suites after each file; they assert behaviour, not message formatting, so they should be untouched.

### Commit

`refactor(dispatch,ingest): migrate to structlog get_logger`

## Sub-phase 2.2 — Migrate scraper package

Scope : `personalscraper/scraper/**.py` (~8 files).

Same migration steps as 2.1. Special cases :

- `scraper/scraper.py` has many `logger.debug(...)` trace statements — keep them, just rewrite.
- `scraper/circuit_breaker.py` already emits event-style strings — trivial to rename.

### Commit

`refactor(scraper): migrate to structlog get_logger`

## Sub-phase 2.3 — Migrate remaining pipeline modules

Scope : `personalscraper/sorter/**.py`, `personalscraper/process/**.py`, `personalscraper/verify/**.py`, `personalscraper/enforce/**.py`, `personalscraper/library/**.py` (~15 files total).

### Commit

`refactor(pipeline): migrate sorter/process/verify/enforce/library to structlog`

## Sub-phase 2.4 — Migrate top-level modules

Scope : `personalscraper/cli.py`, `personalscraper/pipeline.py`, `personalscraper/config.py`, `personalscraper/notifier.py`, `personalscraper/lock.py`, `personalscraper/commands/**.py`, `personalscraper/conf/**.py`.

Notes :

- `lock.py` already uses `get_logger` — skip.
- `conf/classifier.py` uses stdlib logging — migrate.

### Commit

`refactor(core): migrate top-level modules to structlog`

### Quality gate (after 2.4)

- Full test suite green.
- `scripts/check_logging.py` shows zero stdlib-logging findings.
- Manual smoke : `personalscraper --help` still prints the usage banner; `personalscraper run --dry-run` logs to console and JSON file as before.
