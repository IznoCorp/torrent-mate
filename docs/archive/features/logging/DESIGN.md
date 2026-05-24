# DESIGN — Logging Convention Unification

> **⚠ STATUS** : This DESIGN.md is an archived as-designed snapshot. Some claims are
> superseded by later features. Module paths in this archive reference pre-`api-unify` layout.
> See `docs/reference/logging.md` for current paths (already fixed via `329afbc`).
>
> **Old → New mapping** :
>
> | Old (DESIGN.md)                                         | New (current)                                          | Replaced by              |
> | ------------------------------------------------------- | ------------------------------------------------------ | ------------------------ |
> | `personalscraper.scraper.http_retry.build_retry_logger` | `personalscraper.core.http_helpers.build_retry_logger` | `feat/api-unify` v0.11.0 |
> | `scraper/tmdb_client.py` (canonical template)           | `personalscraper/api/metadata/tmdb.py`                 | `feat/api-unify` v0.11.0 |

**Codename**: `logging`
**Type**: refactor (minor SemVer bump)
**Status**: preparation — not yet implemented
**Target version**: next minor after `ext-staging` merges

## 1. Problem

The codebase has three parallel mechanisms for producing output from production modules:

1. **`structlog`** (canonical) — `personalscraper/logger.py` configures `structlog.stdlib.BoundLogger` with dual output (colored console + JSON Lines file). Exposed via `get_logger(name)`.
2. **stdlib `logging`** — 44 files use `logger = logging.getLogger(__name__)` and emit messages via `logger.info/.warning/.error`. These go through structlog's `foreign_pre_chain` when `configure_logging()` has run, but the call sites differ stylistically and do not bind context.
3. **Raw `print()`** in 2 production files (`scraper/confidence.py`, `cli.py:1020`) mixed with the preferred `Console.print` from Rich.

Consequences :

- Context (category, disk, torrent hash, ...) is only bound in files using `get_logger`; stdlib-logging files emit flat strings that are harder to grep in JSON logs.
- The JSON log file receives a mix of key/value events (structlog) and formatted strings (stdlib) — parsers have to handle both shapes.
- Reviewers have to decide per-file which style to use; new code inherits the randomness of the neighbourhood.
- `print()` for interactive prompts is correct (stdin-bound TTY), but it is indistinguishable in review from leftover debug prints.

## 2. Non-goals

- **No change to log destinations.** JSON file path, rotation, and console output keep their current behaviour.
- **No performance work.** Structlog is already fast enough and the call volume is modest.
- **No new log levels.** DEBUG/INFO/WARNING/ERROR stay.
- **No remote log shipping.** The existing file + console output remain the only sinks.
- **No restructuring of the `logger.py` configuration**, beyond cosmetic cleanups.

## 3. Target convention

Three explicit output channels, each with a single call site style :

| Channel                | Use for                                                                                                   | API                                                                       | Where it lands                |
| ---------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ----------------------------- |
| **Structured log**     | Everything a developer or operator may want to grep/aggregate — errors, progress, decisions, side-effects | `log = get_logger("<module>")` + `log.info("event_name", key=value, ...)` | Console (colored) + JSON file |
| **CLI UI**             | User-facing output in CLI commands — headers, tables, prompts rendering, summaries                        | `state["console"].print(...)` (Rich)                                      | TTY only                      |
| **Interactive prompt** | Read user input                                                                                           | `typer.prompt(...)` / `typer.confirm(...)`                                | TTY only                      |

### Rules

1. **`print()` is banned** in `personalscraper/` except in `scraper/confidence.py` where `input()` is used — and those prints must be replaced by `typer.echo` (which respects the console + test runner isolation).
2. **stdlib `logging.getLogger(__name__)` is banned** in `personalscraper/` — every module that logs must use `get_logger`.
3. **Event names are snake_case, stable, grep-friendly** — e.g. `torrent_marked`, `dispatch_skipped`, not `"Skipped torrent because disk was full"`.
4. **Context goes in kwargs**, not in the event string — `log.info("dispatch_moved", source=source, dest=dest)` beats `log.info(f"Moved {source} to {dest}")`.
5. **Third-party library loggers** (`urllib3`, `guessit`, `qbittorrentapi`, ...) stay on stdlib `logging.getLogger("<name>")` — those are intercepted by structlog's `foreign_pre_chain`.
6. **Tests are exempt.** Production code runs under the convention; tests may still use `caplog` / assertions on stdlib logs as they do today.

## 4. Enforcement

A custom ruff rule (`personalscraper-logging`) implemented as a pre-commit hook script would check :

| Violation                                                                                                         | Severity |
| ----------------------------------------------------------------------------------------------------------------- | -------- |
| `print(` in any file under `personalscraper/`                                                                     | error    |
| `logging.getLogger` in any file under `personalscraper/` (except `personalscraper/logger.py` itself)              | error    |
| `log.info(f"...")` / `log.warning(f"...")` / … with an f-string for the event arg (indicates string-mode logging) | warning  |

Implementation : AST walker (Python stdlib `ast`) executed as a ruff plugin is overkill for 3 patterns; a standalone `scripts/check_logging.py` invoked from CI and from the `make lint` target is simpler and good enough.

## 5. Migration strategy

Breadth-first, one category of offender at a time :

1. **Phase A — audit & scaffolding.**
   Produce a machine-readable inventory of every `import logging` / `logging.getLogger` / `print(` line in `personalscraper/`. Land the `scripts/check_logging.py` tool with the rules off by default; wire it into `make lint` with `--report-only` so CI keeps passing.

2. **Phase B — stdlib → structlog migration.**
   For each of the 44 files using `logger = logging.getLogger(__name__)` :
   - Replace the logger factory with `log = get_logger("<short-module-tag>")`.
   - Rewrite call sites to `log.event_name(key=value, ...)` form. Existing string messages are preserved verbatim as the event name (snake_cased) plus a single `message=` kwarg when the free-form text is informative beyond the event name.
   - Preserve exception propagation — `log.exception("event", exc_info=True)` replaces `logger.exception(msg)`.
   - Run the test suite after each batch of ~5 files.

3. **Phase C — print() cleanup.**
   - `scraper/confidence.py:364-369` : replace `print(...)` with `typer.echo(...)` (same stdout, but TyperCliRunner-aware).
   - `cli.py:1020` : already prints a Rich-formatted report; replace with `state["console"].print(...)` for consistency with other commands.

4. **Phase D — enforcement & docs.**
   - Flip `scripts/check_logging.py` from `--report-only` to hard failure.
   - Add a `make lint-logging` target and wire it into the CI pipeline (and `make lint`).
   - Write `docs/reference/logging.md` documenting the convention with examples.
   - Add a short pointer in `CLAUDE.md` and in the `norms.md` (if used) so new code follows the convention from the first commit.

## 6. Risks & mitigations

| Risk                                                                                                                                                | Mitigation                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Message drift when rewriting `logger.info("Moved %s to %s", a, b)` to `log.info("moved", source=a, dest=b)` breaks a downstream log parser or alert | Grep for consumers before the migration; we don't currently ship logs anywhere external, so the only consumer is the human operator. Log file format stays JSON. |
| `structlog` wrapping stdlib creates double entries when a module imports both                                                                       | Single convention prevents this by construction.                                                                                                                 |
| Migration touches many files → merge conflicts if other feature branches are active                                                                 | Schedule Phase B as a single-sitting migration on a dedicated branch; avoid overlap with in-flight features.                                                     |
| `typer.echo` rendering differs from Rich's colored output                                                                                           | `confidence.py` prompt only prints plain text; no Rich formatting is lost.                                                                                       |
| Custom lint rule false positives on strings containing the literal `print(`                                                                         | AST-based check (not regex) avoids this.                                                                                                                         |

## 7. Scope & file impact

- `personalscraper/logger.py` — unchanged API, minor docstring update.
- 44 `personalscraper/**/*.py` files — mechanical replacement.
- `personalscraper/scraper/confidence.py` — 4 `print()` → `typer.echo`.
- `personalscraper/cli.py` — 1 `print()` → `state["console"].print`.
- `scripts/check_logging.py` — NEW (~80 LOC).
- `docs/reference/logging.md` — NEW.
- `CLAUDE.md` / `norms.md` — short pointer.
- `Makefile` — add `lint-logging` target, extend `lint`.
- `.github/workflows/ci.yml` (or equivalent) — run the new lint step.

Zero production-behaviour changes expected — test suite should pass without modification, since no level/destination changes.
