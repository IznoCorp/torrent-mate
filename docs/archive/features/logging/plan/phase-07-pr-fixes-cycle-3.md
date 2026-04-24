# Phase 07 — PR Review Fixes (cycle 3, ceiling override)

**Goal**: address cycle-3 findings — 2 major narrowing regressions introduced by SP6.5, 4 medium consistency gaps, and minor doc polish. User explicitly overrode the 3-cycle ceiling to fix all findings.

## Sub-phase 7.1 — MAJOR: complete narrowed exception tuples

**Findings (silent-failure-hunter cycle 3)**: SP6.5 narrowed exceptions drop real raise sites, regressing from the pre-SP6.5 broad catch.

Targets:

- `personalscraper/scraper/scraper.py:174` `_parse_folder_name` — extend `(ValueError, AttributeError, TypeError)` to include `guessit.api.GuessitException`. Use a lazy import: `from guessit.api import GuessitException`. The try body already loads guessit-backed helpers; adding this type is tractable.
- `personalscraper/scraper/scraper.py:1238` `movie_artwork_failed` — extend `(requests.RequestException, OSError)` to `(requests.RequestException, OSError, KeyError, AttributeError)`. `NamingPatterns.format()` documents `Raises: AttributeError, KeyError`; malformed TMDB responses produce `AttributeError` during `data.get(...)` on non-dict elements.
- `personalscraper/scraper/scraper.py:1500` `show_artwork_failed` — same extension `(requests.RequestException, OSError, KeyError, AttributeError)` for the same reasons.

Commit: `fix(logging): complete narrowed exception tuples to cover real raise sites`

## Sub-phase 7.2 — MEDIUM: extend exc_info and noqa precision

**Findings (silent-failure-hunter cycle 3)**: sibling arms have `exc_info=True`, these lack it.

Targets:

- `personalscraper/scraper/tmdb_client.py:447-454` `tmdb_keywords_failed_http`: add `exc_info=True` (TMDBError carries `__cause__` chain).
- `personalscraper/dispatch/dispatcher.py:497` `replace_tmp_cleanup_failed`: add `exc_info=True`.
- `personalscraper/dispatch/dispatcher.py:527` `replace_old_copy_cleanup_failed`: add `exc_info=True`.
- `personalscraper/dispatch/dispatcher.py:531` `replace_source_cleanup_failed`: add `exc_info=True`.
- `personalscraper/scraper/scraper.py:1540`: replace noqa justification with enumeration: `# noqa: BLE001 — mixed API + data-shape path: TMDB and TVDB paths raise TMDBError, TVDBError, requests.RequestException, CircuitOpenError (lazy imports), plus KeyError/TypeError on malformed episode payloads (ep["number"]/ep.get())`.

Commit: `fix(logging): extend exc_info and precision of noqa justifications`

## Sub-phase 7.3 — MEDIUM: cover narrowed arms with tests

**Findings (pr-test-analyzer cycle 3)**: narrowed arms lack regression coverage.

Targets:

- `tests/scraper/test_scraper.py` — add 3 tests:
  - `test_parse_folder_name_handles_guessit_exception`: patch `sorter.cleaner.NameCleaner` (or equivalent) so that `clean()`/`extract_year()` raises `GuessitException("bad")`; assert the log captures `folder_name_clean_failed` and the return is `(name, None)`.
  - `test_parse_folder_name_handles_type_error`: feed a pathological input triggering TypeError; same assertions.
  - `test_movie_artwork_failed_on_key_error`: patch `NamingPatterns.format` to raise `KeyError("missing_template_var")`; assert `movie_artwork_failed` event and a warning is appended (no crash).

Use the existing test patterns in `tests/scraper/test_scraper.py` for fixture setup.

Commit: `test(logging): cover narrowed exception arms in scraper`

## Sub-phase 7.4 — MINOR: doc polish and final consistency

**Findings (comment-analyzer cycle 3 + pr-test-analyzer minor + code-reviewer minor)**:

Targets:

- `docs/reference/logging.md` RULE D code example: change `exc_info=exc if exc else False` → `exc_info=exc if exc is not None else False` to match `http_retry.py` idiom. Drop the closing "This is the ONLY case…" sentence — RULE C/D already partition the space.
- `docs/reference/logging.md` "Broad exception handling convention" example: remove the generic "best-effort fallback" phrasing; replace with a specific enumeration example.
- `personalscraper/scraper/http_retry.py:38-46` `build_retry_logger` docstring: remove the duplicated sentence "exc_info is the exception that triggered the retry..." — keep only the Note rationale; move the behavior contract into the Returns/Args section.
- `personalscraper/scraper/confidence.py:244` noqa comment: shorten to `# noqa: BLE001 — see block comment above; narrowing requires 3 cross-module imports including lazy CircuitOpenError`. Drop the "silently masks programming bugs" + "dashboards can monitor" speculative claims (move to a TODO if desired).
- `personalscraper/scraper/scraper.py:693` noqa: replace the duplicated enumeration with `# noqa: BLE001 — see block comment above` (match the pattern at line 727).
- `scripts/check_logging.py:25` module docstring: remove the dated `Baseline (as of 2026-04-23): 0 ERROR offenders, 0 WARN offenders.` line — baselines drift; move to `IMPLEMENTATION.md` if needed.
- `tests/test_event_names.py` `TestIngestQbitAuthLockoutEvent`: add a negative assertion `assert not _has_event(caplog, "ingest_unexpected_error")` to make the test strictly branch-discriminating.
- `tests/ingest/test_ingest.py` unexpected-error test: switch `OSError("disk full")` → `RuntimeError("boom")` to lock the catch-all's role as last-resort (OSError is I/O-shaped and could drift into a new explicit arm).

Commit: `docs(logging): polish noqa justifications RULE D and test discrimination`

## Quality gate (after 7.4)

- `python -m ruff check .` exit 0
- `python -m ruff format --check .` exit 0
- `python -m mypy personalscraper/` exit 0
- `python scripts/check_logging.py personalscraper/` exit 0 with 0 findings
- `python -m pytest tests/` exit 0 (expected count ≥ 1588 after new tests)
- All cycle 3 major + medium + minor findings addressed
