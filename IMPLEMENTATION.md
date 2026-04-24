# Implementation Progress — logging

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Logging Convention Unification (minor)
**Version bump**: 0.4.0 → 0.5.0
**Branch**: feat/logging
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/10
**Design**: docs/features/logging/DESIGN.md
**Master plan**: docs/features/logging/plan/INDEX.md

## Phases

| #   | Phase                        | File                         | Status |
| --- | ---------------------------- | ---------------------------- | ------ |
| 1   | Audit & enforcement tooling  | phase-01-audit-tooling.md    | [x]    |
| 2   | stdlib → structlog migration | phase-02-stdlib-migration.md | [x]    |
| 3   | print() cleanup              | phase-03-print-cleanup.md    | [x]    |
| 4   | Enforcement + docs           | phase-04-enforcement-docs.md | [x]    |
| 5   | PR fixes cycle 1             | phase-05-pr-fixes-cycle-1.md | [x]    |
| 6   | PR fixes cycle 2             | phase-06-pr-fixes-cycle-2.md | [x]    |
| 7   | PR fixes cycle 3             | phase-07-pr-fixes-cycle-3.md | [x]    |
| 8   | PR fixes cycle 4             | phase-08-pr-fixes-cycle-4.md | [x]    |

## Review cycles

### Cycle 1

- Findings received: 4 agents (code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer)
- Retained: 6 (0 critical, 0 major, 2 medium, 4 minor)
- Ignored: many (out of DESIGN §7 scope — pre-existing behaviors preserved faithfully per DESIGN §2 non-goals)
- Fix phase created: phase-05-pr-fixes-cycle-1.md (6 sub-phases, all DONE)
- Status: all 6 retained findings + project-wide sweep addressed across 6 commits (SP5.1–5.6)

**Retained findings (tracked as follow-up, non-blocking for merge)**:

- **Medium** — `_log_retry_warning` callback is byte-identical across `scraper/artwork.py`, `tmdb_client.py`, `tvdb_client.py`. DRY opportunity: extract to `scraper/http_retry.py`.
- **Medium** — Inconsistent exception-context idiom: some call sites use `exc_info=exc` (rescraper, reclean, process/run, pipeline) while `docs/reference/logging.md` canonical snippet shows `exc_info=True`. Normalize or update doc.
- **Minor** — Unused `_LOG_LEVELS` frozenset in `scripts/check_logging.py:226`; log-level set is inlined at line 163. Remove or use the constant.
- **Minor** — `scripts/check_logging.py` module docstring claims `(except tests/)` exclusion; actual exclusion is via default scan root (`personalscraper/`), not an `is_in_tests()` filter. Rephrase.
- **Minor** — `scripts/check_logging.py` does not catch `from logging import getLogger` bypass. DESIGN §4 specifies literal `logging.getLogger` detection — current codebase has zero violations either way. Hardening opportunity.
- **Minor** — CLAUDE.md Reference Index row grammar ("writing new logging call" → "writing new logging calls") and style (noun phrase vs "When…" clause) inconsistent with sibling rows.

### Cycle 2

- Findings received: 4 agents (code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer)
- Retained: 11 (1 critical, 4 major, 6 medium, ~8 minor per user directive "fix all findings")
- Critical: `build_retry_logger` loses retry tracebacks (`exc_info=bool` in tenacity `before_sleep` is empty outside active `except`)
- Major: stale migration recipe + fabricated events in `logging.md`; dispatcher data-loss paths missing `exc_info`; tmdb_client second fallback arm missing kwargs; `ingest_unexpected_error` no test
- Fix phase created: phase-06-pr-fixes-cycle-2.md (6 sub-phases, all DONE)
- Status: all cycle-2 findings addressed across 7 commits (SP6.1 traceback + SP6.2–6.6)

### Cycle 3

- Findings received: 4 agents (code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer)
- Retained: 14 (0 critical, 2 major, 4 medium, 8 minor) — user overrode spec ceiling to fix all
- Major: SP6.5 narrowing dropped real raise sites — `_parse_folder_name` misses `GuessitException`; `movie_artwork_failed`/`show_artwork_failed` miss `KeyError`/`AttributeError` from `NamingPatterns.format()` and malformed TMDB/TVDB responses
- Medium: `tmdb_keywords_failed_http` missing `exc_info`; 3 dispatcher cleanup arms missing `exc_info`; `scraper.py:1540` noqa understates catch surface; narrowed arms lack regression tests
- Fix phase created: phase-07-pr-fixes-cycle-3.md (4 sub-phases)
- Status: all cycle-3 findings addressed across 4 commits (SP7.1–7.4)

### Cycle 4

- Findings received: 4 agents (code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer)
- Retained: 8 (1 critical, 1 major, 4 medium, 2 minor) — user overrode spec ceiling a second time
- Critical: `docs/reference/logging.md` Telegram example cites `python-telegram-bot` (not a dependency); `notifier.py` uses `requests`
- Major: `scraper.py:1541` noqa cites `KeyError`/`ep["number"]` but try-body uses exclusively `.get()` — `KeyError` is unreachable
- Medium: missing regression tests for `show_artwork_failed` narrowed arm and AttributeError sides; dangling `(tracked: TODO)` in `confidence.py:244`; brittle line-pin in `logging.md:180`
- Fix phase created: phase-08-pr-fixes-cycle-4.md (4 sub-phases)
- Status: all cycle-4 findings addressed across 4 commits (SP8.1–8.4)

## Next action

Phase 8 complete — run `/implement:feature-pr` to push and verify CI, then cycle 5 review (ceiling raised to 5).
