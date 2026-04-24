# Phase 05 — PR Review Fixes (cycle 1)

**Goal**: address every finding from the 4 review agents, including items filtered as out-of-scope. Groups findings into 6 sub-phases by theme for safe incremental dispatch.

## Sub-phase 5.1 — DRY: extract `_log_retry_warning` + add unit test

Target files:

- `personalscraper/scraper/http_retry.py` — add factory
- `personalscraper/scraper/artwork.py:47-66` — remove local definition, import from http_retry
- `personalscraper/scraper/tmdb_client.py:38-57` — same
- `personalscraper/scraper/tvdb_client.py:42-61` — same
- `tests/scraper/test_retry_logging.py` — NEW, at least 3 tests: outcome with exception / outcome with result / next_action None

Commit: `refactor(logging): extract retry_warning callback to scraper/http_retry`

## Sub-phase 5.2 — Normalize exc_info idiom

Canonical rule (enforce everywhere):

- `log.exception("event", **ctx)` — `exc_info` is implicit, never pass `exc_info=True` here
- `log.warning("event", exc_info=True, error=str(exc), **ctx)` — explicit exc_info for non-exception levels
- Passing exception instance (`exc_info=exc`) is banned — always `exc_info=True` inside an `except` block

Sweep sites:

- `personalscraper/notifier.py:74` — drop redundant `exc_info=True`
- `personalscraper/pipeline.py:413` — drop redundant `exc_info=True`
- `personalscraper/library/rescraper.py:146, 317, 322, 326, 331, 335, 392, 503` — convert `exc_info=exc` → `exc_info=True, error=str(exc)`
- `personalscraper/process/reclean.py:63, 105, 269, 272` — same
- `personalscraper/process/run.py:130, 140, 150` — same
- `personalscraper/scraper/scraper.py` — `log.warning("folder_name_clean_failed", ..., exc_info=True)` rename `_exc` → `exc`
- `docs/reference/logging.md` — update "Migration recipes" section with the three clarified rules

Commit: `refactor(logging): normalize exc_info idiom across structlog call sites`

## Sub-phase 5.3 — Harden `check_logging.py` linter

Targets:

- `scripts/check_logging.py`:
  - Remove unused `_LOG_LEVELS` constant (inline at call site or keep as the single source)
  - Fix docstring wording for `(except tests/)` — clarify scan-root behavior, not filter
  - Tighten `_LOGGER_MODULE` to full relative path `personalscraper/logger.py`
  - Add `visit_ImportFrom` to track `from logging import getLogger` / aliased `from logging import getLogger as gl`
  - Add detection for aliased `import logging as lg; lg.getLogger()`
  - Add detection for direct `structlog.get_logger(...)` (project rule: always through `personalscraper.logger.get_logger`)
  - Ensure `analyze_paths` tolerates `SyntaxError` on malformed file and continues
- `tests/tools/test_check_logging.py` — new tests:
  - `from logging import getLogger` → flagged
  - `from logging import getLogger as gl` → flagged
  - `import logging as lg; lg.getLogger()` → flagged
  - `import structlog; structlog.get_logger("x")` → flagged
  - `print()` inside nested function → flagged
  - `print()` inside decorator → flagged
  - walrus operator `(log := get_logger("x"))` → tracked
  - `analyze_paths` with a file containing `def f(:\n` → continues
  - Mixed file+dir path args → both scanned

Commit: `feat(logging): harden check_logging AST walker against import aliases and structlog direct`

## Sub-phase 5.4 — Error handling hardening

Targets:

- `personalscraper/ingest/ingest.py:343-368` — distinct event per arm:
  - `ingest_qbit_auth_lockout` (LoginFailed + lockout msg)
  - `ingest_qbit_login_failed` (other LoginFailed)
  - `ingest_qbit_forbidden` (Forbidden403Error)
  - `ingest_qbit_unreachable` (APIConnectionError)
  - `ingest_unexpected_error` (generic Exception + `exc_info=True, error_type=type(e).__name__`)
- `personalscraper/scraper/scraper.py` — add `exc_info=True` to `except Exception` arms:
  - `artwork_recovery_failed` (2 sites, ~688, ~722)
  - `repair_root_episodes_failed` (~953)
  - `repair_organize_episodes_failed` (~1021)
  - `movie_artwork_failed` (~1232)
  - `show_artwork_failed` (~1492)
  - `show_season_fetch_failed` (~1532)
- `personalscraper/notifier.py:73` — add `# noqa: BLE001` with explanation comment documenting the intentional broad catch
- `personalscraper/scraper/confidence.py` — narrow TVDB→TMDB fallback to typed excepts (keep behavior but add `exc_info=True`)
- `personalscraper/dispatch/dispatcher.py:513` — add `tmp_old`, `dest` kwargs to `replace_restore_failed`
- `personalscraper/scraper/mediainfo.py:193` — rename `message=` kwarg → `remediation=`
- `personalscraper/scraper/tmdb_client.py` — add `fallback="empty_list"` to `tmdb_keywords_failed_http` event

Commit: `fix(logging): narrow broad excepts and preserve exception diagnostics`

## Sub-phase 5.5 — Test coverage + infrastructure

Targets:

- `tests/conftest.py` — wrap `configure_logging()` call in try/except, `pytest.fail` on error with clear message; point to `tmp_path_factory` based LOGS_DIR to avoid touching repo root
- `tests/tools/test_check_logging.py`:
  - Remove redundant `sys.path.insert` (rely on pyproject.toml pythonpath)
  - Pin line numbers for all 3 rules (not just the print one)
- `tests/test_logger_cli.py::test_cli_creates_log_file` — convert soft `if exists` to `assert exists`
- Add event-name regression pins in a new file `tests/test_event_names.py`:
  - Capture via caplog + configure_logging: 5-8 representative events across modules
  - At minimum: `dispatch_moved_ok`, `ingest_torrent_marked`, `tvdb_login_ok`, `circuit_opened`, `scrape_fast_skip`, `ingest_qbit_auth_lockout`

Commit: `test(logging): add event-name regression tests and harden logging fixtures`

## Sub-phase 5.6 — Documentation + CLAUDE.md polish

Targets:

- `docs/reference/logging.md`:
  - Update canonical exc_info rule with the 3 sub-rules from 5.2
  - Replace fabricated `dispatch_moved` example with a real shipped event
  - Add "Event naming guideline" section (prefix by module concern, snake_case, past-tense for state changes)
- `CLAUDE.md:119` — fix Reference Index row grammar: "Logging conventions, event-name style, structlog vs CLI vs typer channels" (noun-phrase style consistent with siblings)
- `personalscraper/logger.py:85` — fix comment about third-party loggers (accurate statement about qbittorrentapi INFO vs WARNING for others)

Commit: `docs(logging): clarify exception idiom, naming guideline, CLAUDE.md grammar`

## Quality gate (after 5.6)

- `make lint` exit 0 (including new linter rules must pass against whole tree)
- `make test` exit 0 (new regression tests must pass)
- `scripts/check_logging.py personalscraper/` exit 0 with 0 findings (including the new aliased-import rules)
- All retained findings from Review cycle 1 addressed in IMPLEMENTATION.md Cycle 1 summary
