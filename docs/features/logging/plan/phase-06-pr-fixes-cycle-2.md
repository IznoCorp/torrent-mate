# Phase 06 — PR Review Fixes (cycle 2)

**Goal**: address all cycle-2 review findings — 1 critical, 4 major, 6 medium, and (per user directive) minor polish. Organized in 6 sub-phases.

## Sub-phase 6.1 — CRITICAL: restore retry traceback in `build_retry_logger`

**Finding (silent-failure-hunter C1)**: `personalscraper/scraper/http_retry.py:39` passes `exc_info=exc is not None` (a bool). In tenacity's `before_sleep` callback the exception is NOT active, so `sys.exc_info()` returns `(None, None, None)` and structlog's `format_exc_info` cannot render a traceback. The pre-refactor code (`exc_info=<exception instance>`) DID render it. Tracebacks are silently dropped on every TMDB/TVDB/artwork retry.

Targets:

- `personalscraper/scraper/http_retry.py:33-41` — change `exc_info=exc is not None` → `exc_info=exc if exc is not None else False`; drop the `**({"error": ...} if exc is not None else {})` conditional and always pass `error=str(exc) if exc is not None else None` (or just omit `error` when None using the same idiom, but prefer the explicit version for clarity).
- `tests/scraper/test_retry_logging.py` — update 4 assertions to match the new shape: `exc_info` is the exception instance (not `True`/`False`), `error` key present when exception present.
- `docs/reference/logging.md` — add **RULE D**: "Outside active `except` blocks (e.g. tenacity `before_sleep`/`after` callbacks, signal handlers, async callbacks), pass the exception **instance** as `exc_info` to preserve the traceback. `exc_info=True` only works inside an active `except`."

Commit: `fix(logging): preserve traceback in retry before_sleep callback`

## Sub-phase 6.2 — MAJOR: documentation drift in `logging.md` and `check_logging.py`

**Findings (comment-analyzer + code-reviewer M1)**: several docs reference dead symbols or contradict shipped code.

Targets:

- `docs/reference/logging.md:44-46, 77, 79, 93, 96, 105, 114, 117` — replace fabricated events (`disk_low`, `scrape_failed`, `dispatch_failed`, `nfo_failed`, `disk_scan_failed`) with real shipped events. Use `grep -rhE 'log\.\w+\("[a-z_]+"' personalscraper/ | sed 's/.*log\.\w\+("\([a-z_]*\)".*/\1/' | sort -u` to pick real candidates. Good real examples: `ingest_qbit_login_failed`, `nfo_write_failed`, `ffprobe_failed`, `rsync_start`.
- `docs/reference/logging.md:82` — migration recipe row: change `_log_retry_warning("event_name")` / `scraper/artwork.py` template to `build_retry_logger(log, "event_name")` from `personalscraper.scraper.http_retry` with `scraper/tmdb_client.py` as call-site template.
- `docs/reference/logging.md:125-131` — "Three rules" enforcement table is stale: `check_logging.py` now has 4 rules (no-print, no-stdlib-logger with aliased-import coverage, no-structlog-direct NEW, no-fstring-log). Update the table and note aliased-import coverage.
- `docs/reference/logging.md:20-21` — mark event prefix/suffix lists as illustrative (`e.g.`), verifying each suffix example appears somewhere in the 305 shipped events or dropping it.
- `scripts/check_logging.py:3` — module docstring says "five categories" but only 4 bullets. Fix to "four".
- `scripts/check_logging.py:152-154, 193-195` — rename `# First pass: ...` / `# Second pass: ...` banners to `# Binding tracking` / `# Violation flagging` (single-pass reality).
- `scripts/check_logging.py:353-356` — "avoid false negatives" → "avoid false positives" (the suffix match PROTECTS against false positives on non-project `logger.py` files).

Commit: `docs(logging): fix fabricated events and enforcement table drift`

## Sub-phase 6.3 — MAJOR: complete exc_info/kwargs coverage on error paths

**Findings (silent-failure-hunter M1, M3, M4, Med2, Med3)**: specific call sites missed during SP5.2/5.4 normalization sweep.

Targets:

- `personalscraper/dispatch/dispatcher.py:506` — `replace_swap_failed` `log.error`: add `exc_info=True` (data-loss path).
- `personalscraper/dispatch/dispatcher.py:513` — `replace_restore_failed` `log.error`: add `exc_info=True`.
- `personalscraper/scraper/tmdb_client.py:456-463` — second fallback arm in `get_keywords` (for `requests.RequestException, json.JSONDecodeError, _CircuitOpenError`): add `fallback="empty_list"` kwarg and `exc_info=True`, matching the first TMDBError arm at line 447.
- `personalscraper/notifier.py:70-72` — `requests.RequestException` arm `log.warning`: add `exc_info=True` (already inside an active `except`).
- `personalscraper/scraper/scraper.py:992` — inner season-fetch `except (OSError, ConnectionError, TimeoutError)` arm: add `exc_info=True`.
- `personalscraper/ingest/ingest.py:364` — final `except Exception` catch-all: add `# noqa: BLE001 — safety catch-all for tracker I/O and unexpected qbittorrentapi changes; preserves pipeline continuation on unknown failures` to match the `notifier.py:73` / `confidence.py:241` precedent.

Commit: `fix(logging): complete exc_info and fallback kwargs on error paths`

## Sub-phase 6.4 — MAJOR: test coverage expansion for renamed ingest events

**Findings (pr-test-analyzer Imp1 + Imp2, code-reviewer Md3)**: `ingest_unexpected_error` has no test at all; `ingest_qbit_auth_lockout` is only a direct-emit pin; 4 renamed ingest events have no regression pins.

Targets:

- `tests/test_event_names.py`:
  - Add pins for `ingest_qbit_login_failed`, `ingest_qbit_forbidden`, `ingest_qbit_unreachable` (already covered by real-path tests in `tests/ingest/test_ingest.py`, so direct-emit pins are acceptable as a belt-and-braces guard).
  - Add pin for `ingest_unexpected_error`.
  - Convert `ingest_qbit_auth_lockout` pin to trigger the real code path via `side_effect=QBitAuthLockoutError(...)` on the qBittorrent client mock (matching the pattern at `tests/ingest/test_ingest.py:678-747`).
- `tests/ingest/test_ingest.py` — add an "unknown exception" test case that injects `side_effect=OSError("disk full")` on the qBittorrent client and asserts the `ingest_unexpected_error` event is emitted with `error_type="OSError"`.
- Module docstring on `tests/test_event_names.py` — clarify: "event-name PINS (regression guards on the literal string); real-path coverage lives in the per-module tests (`tests/ingest/`, `tests/scraper/`, etc.)".

Commit: `test(logging): expand coverage for renamed ingest events and unexpected-error arm`

## Sub-phase 6.5 — MEDIUM: narrow remaining broad excepts + confidence comment

**Findings (silent-failure-hunter M2 + Med1)**: 6 sites in `scraper.py` and `confidence.py` noqa under-states risk.

Targets:

- `personalscraper/scraper/scraper.py` — audit and narrow (or annotate with noqa + justification) these broad `except Exception` arms:
  - `_parse_folder_name` (~line 174)
  - `artwork_recovery_failed` (~line 690, ~line 724)
  - `movie_artwork_failed` (~line 1232)
  - `show_artwork_failed` (~line 1494)
  - `show_season_fetch_failed` (~line 1534)
    For each: grep the immediately-enclosed call to identify the concrete exceptions raised. Narrow to a tuple `(requests.RequestException, OSError, KeyError, TMDBError, TVDBError)` where appropriate, or retain the broad catch with `# noqa: BLE001 — <explicit justification referencing specific third-party lib or contract>` on the `except` line.
- `personalscraper/scraper/confidence.py:241` — update the broad-catch justification comment to acknowledge that programming bugs in the TVDB path are masked, and argue why that is acceptable ("TVDB is optional; TMDB is authoritative and the circuit breaker protects against cascading TVDB adapter bugs").

Commit: `refactor(logging): narrow or justify remaining broad excepts in scraper and confidence`

## Sub-phase 6.6 — MINOR: naming alignment + docstring/comment polish

**Findings (code-reviewer Md2 + Mn2 + Mn3, comment-analyzer Important/Minor, pr-test-analyzer 9)**: past-tense alignment, fixture polish, docstring enhancements.

Targets:

- **Naming alignment** (code-reviewer Md2): weaken the past-tense guideline wording in `docs/reference/logging.md:21` to "past-tense preferred for state changes, noun phrases acceptable for recognized error states (e.g. `_lockout`, `_unexpected_error`)". Rationale: renaming `ingest_qbit_auth_lockout` and `ingest_unexpected_error` just-introduced events carries more cost than benefit; soften the rule instead.
- `tests/conftest.py:48-51` — either wrap the `MonkeyPatch().setattr` in a `yield` fixture with `mp.undo()` teardown, or leave it and add a one-line comment documenting that the monkeypatch intentionally lives for the full session.
- `personalscraper/scraper/http_retry.py:19-31` — extend `build_retry_logger` docstring: document the `outcome is None` branch explicitly, note the `event` convention (snake_case, link to `docs/reference/logging.md#event-naming-guideline`).
- `personalscraper/logger.py:85-86` — expand the qbittorrentapi INFO comment: "qbittorrentapi INFO surfaces session lifecycle events (login, logout, cookie refresh) that aid ingest debugging without DEBUG-level request traces."

Commit: `docs(logging): polish docstrings comments and naming guideline wording`

## Quality gate (after 6.6)

- `python -m ruff check .` exit 0
- `python -m ruff format --check .` exit 0
- `python -m mypy personalscraper/` exit 0
- `python scripts/check_logging.py personalscraper/` exit 0 with 0 findings
- `python -m pytest tests/` exit 0 (expected count ≥ 1585 after new tests)
- All cycle 2 critical + major + medium findings addressed in IMPLEMENTATION.md Cycle 2 summary
