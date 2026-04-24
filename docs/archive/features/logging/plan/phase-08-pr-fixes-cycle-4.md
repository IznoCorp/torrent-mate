# Phase 08 — PR Review Fixes (cycle 4, ceiling override)

**Goal**: address cycle-4 findings — 1 critical doc accuracy issue, 1 major noqa inaccuracy, 4 medium gaps (2 test, 2 doc/noqa), 2 minor polish items. User explicitly overrode the 3-cycle ceiling for a second time.

## Sub-phase 8.1 — CRITICAL: fix Telegram doc example (non-existent library)

**Finding (comment-analyzer cycle 4)**: `docs/reference/logging.md:170-180` shows an `except Exception` example citing `python-telegram-bot` exception classes (`NetworkError`, `RetryAfter`, `TimedOut`, `BadRequest`, `Unauthorized`). This library is NOT a dependency — `personalscraper/notifier.py` uses `requests`. The example is fabricated and the "Reference template" pointer at line 180 to `notifier.py:73` points to a noqa line that says something entirely different (`best-effort fallback; notification must not mask the underlying operation`).

Targets:

- `docs/reference/logging.md:170-178` — replace the Telegram example with the real `notifier.py:73` rationale. Use: `# noqa: BLE001 — best-effort fallback; notification must not mask the underlying operation`, paired with `log.exception("telegram_unexpected_error", error=str(exc))`.
- Keep the second example (`except Exception as e` with TVDBError/ConnectionError/CircuitOpenError) — it accurately describes `confidence.py`.
- Verify the "Reference templates" pointer at line 180 still makes sense after the edit (both referenced lines should match the doc examples).

Commit: `fix(logging): correct telegram example in logging doc to match notifier.py`

## Sub-phase 8.2 — MAJOR: correct scraper.py:1541 noqa justification

**Finding (comment-analyzer cycle 4)**: the noqa at `scraper.py:1541` claims the catch covers `KeyError/TypeError on malformed episode payloads (ep["number"]/ep.get())` but the try-body (lines 1517-1540) uses exclusively `.get()` — no bracket indexing, so `KeyError` is unreachable from this code.

Targets:

- `personalscraper/scraper/scraper.py:1541` — rewrite the noqa justification to accurately describe the data-shape failure modes: `AttributeError` (when `ep` or `s_detail` is not a dict, so `.get` is missing) and `TypeError` (when `seasons`/`episodes` is not iterable). Drop `KeyError` and the `ep["number"]` parenthetical.

Proposed: `# noqa: BLE001 — mixed API + data-shape path: TMDB/TVDB paths raise TMDBError, TVDBError, requests.RequestException, CircuitOpenError (lazy imports); plus AttributeError/TypeError on malformed payloads (non-dict ep; non-iterable seasons/episodes)`.

Commit: `fix(logging): correct scraper season-fetch noqa to match actual data-shape failures`

## Sub-phase 8.3 — MEDIUM: symmetric test for show_artwork_failed narrowed arm

**Finding (silent-failure-hunter M1 + pr-test-analyzer M1 cycle 4)**: `scraper.py:1501` `show_artwork_failed` has the same `(KeyError, AttributeError)` narrowing as `movie_artwork_failed` at line 1239, but only the movie path has a regression test. A future narrowing revert on the show side would silently regress the TV pipeline.

Targets:

- `tests/scraper/test_scraper.py` — add `TestShowArtworkFailedNarrowedExceptions` class with `test_show_artwork_failed_on_key_error`. Mirror `TestMovieArtworkFailedNarrowedExceptions.test_movie_artwork_failed_on_key_error` (tests/scraper/test_scraper.py:1857). Patch `scraper._artwork.download_tvshow_artwork` (or the module boundary actually invoked by `scrape_show`) with `side_effect=KeyError("missing_template_var")`. Assert (a) `action == "scraped"` or equivalent non-crash outcome, (b) `"Artwork failed"` (or the project's canonical show-artwork warning substring) in `result.warnings`, (c) `show_artwork_failed` event captured via caplog.
- Add `test_show_artwork_failed_on_attribute_error` mirroring the KeyError test with `side_effect=AttributeError("missing_attr")`. Same assertions.
- Add `test_movie_artwork_failed_on_attribute_error` to close the AttributeError gap on the movie side too (the existing movie test covers KeyError only). Pattern it after the existing movie KeyError test.

Use existing fixture setup patterns. Overall `pytest tests/` count should be ≥1591 after these additions.

Commit: `test(logging): cover show_artwork_failed narrowed arm and attribute-error paths`

## Sub-phase 8.4 — MINOR: doc/noqa polish

**Findings (comment-analyzer cycle 4 + silent-failure-hunter m1)**:

Targets:

- `personalscraper/scraper/confidence.py:244` — drop the dangling `(tracked: TODO)` parenthetical. There is no actual tracker entry; the placeholder is noqa-rot. Keep the rest of the justification (`see block comment above; narrowing requires 3 cross-module imports including lazy CircuitOpenError`).
- `docs/reference/logging.md:180` — replace the brittle line-pin `personalscraper/scraper/confidence.py:241` with a symbolic reference: use the function or method name (e.g. `personalscraper/scraper/confidence.py::match_tvshow` or whatever the actual enclosing function is — verify by reading the file). Also re-verify the `notifier.py:73` pointer still resolves after SP8.1.
- `personalscraper/scraper/http_retry.py:25-27` — broaden the docstring note describing the `exc is None` path. Current wording covers only the "outcome is None" case, but `retry_state.outcome.exception()` also returns `None` on successful outcomes (unusual for tenacity `before_sleep` but possible). Change "When no exception is available" to "When no exception is available (outcome absent, or outcome was a non-exception result)".

Commit: `docs(logging): polish noqa and retry-logger docstring edge cases`

## Quality gate (after 8.4)

- `python -m ruff check .` exit 0
- `python -m ruff format --check .` exit 0
- `python -m mypy personalscraper/` exit 0
- `python scripts/check_logging.py personalscraper/` exit 0 with 0 findings
- `python -m pytest tests/` exit 0 (expected count ≥ 1591 after new tests)
- All cycle 4 critical + major + medium + minor findings addressed
