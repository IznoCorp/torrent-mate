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

## Next action

All phases complete — run `/implement:feature-pr` to push and wait for CI green, then `/implement:pr-review` for cycle 2 verification.
