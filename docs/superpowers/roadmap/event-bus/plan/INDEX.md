# Event Bus Implementation Plan — INDEX

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Feature**: Event Bus
**Codename**: event-bus
**SemVer bump**: minor (Y+1)
**Date**: 2026-05-11
**Status**: spec (preparation — not yet implemented)
**Design**: [`../specs/DESIGN.md`](../specs/DESIGN.md)
**Goal**: Replace `PipelineObserver` Protocol with a single application-wide `EventBus` that serves as the only substrate for cross-component asynchronous communication.
**Architecture**: In-process typed pub/sub with type-indexed `subscribe`, MRO-walking dispatch, frozen dataclass events inheriting a common `Event` base, JSON-serializable with split `event_to_dict` / `event_to_envelope` contracts, `correlation_id` captured at event construction via `current_correlation_id` `ContextVar`. Owned by an `AppContext` that lives at process boundaries only.
**Tech stack**: Python 3.11+, `dataclasses` (frozen), `contextvars`, `structlog`, `rich` (subscriber), `pytest`.

---

## Phase summary

| Phase | Name                                   | Sub-phases | Depends on | File                                                                             |
| ----- | -------------------------------------- | ---------- | ---------- | -------------------------------------------------------------------------------- |
| 1     | Foundation (standalone)                | 9          | —          | [`phase-01-foundation.md`](phase-01-foundation.md)                               |
| 2     | AppContext + StepContext slim          | 8          | Phase 1    | [`phase-02-app-context-step-context.md`](phase-02-app-context-step-context.md)   |
| 3     | Pipeline event migration + subscribers | 11         | Phase 2    | [`phase-03-pipeline-events-migration.md`](phase-03-pipeline-events-migration.md) |
| 4     | Cross-cutting events                   | 6          | Phase 3    | [`phase-04-cross-cutting-events.md`](phase-04-cross-cutting-events.md)           |
| 5     | Required-bus tightening + CLI polish   | 7          | Phase 4    | [`phase-05-required-bus-cli-polish.md`](phase-05-required-bus-cli-polish.md)     |

Total sub-phases: **41**. Total commits (estimate): **45–50** (each sub-phase ≥ 1 commit; a few sub-phases produce 2 atomic commits when test setup + integration land in separate steps).

---

## Cross-phase invariants (read before EVERY sub-phase)

### Invariant 1 — NO DEFERRAL (absolute, user-imposed)

**Every step is adapted. Every test is written. Nothing is skipped, nothing is deferred, nothing is left for "later".** This applies to every phase and every sub-phase.

Concretely:

- A sub-phase ships its **full intended behavior + tests + docs**, or it does not ship. There is no "partial implementation now, complete later".
- Tests for an integration land in the **same sub-phase as the integration**, never in a "test polish" sub-phase later.
- A sub-phase that introduces an event MUST land its `make_<event_name>()` factory in `tests/fixtures/event_samples.py` **in the same sub-phase**. `test_every_event_has_factory` enforces this at every phase gate ≥ Phase 3.
- A sub-phase that adds a new authorized boundary site for `AppContext` MUST update `tests/architecture/test_app_context_boundary.py` allowlist **in the same sub-phase**.
- A sub-phase that removes a symbol MUST sweep all callers (production + tests + docs) **in the same sub-phase**.

If a verification gate fails, the offending sub-phase is **fixed in place**, never split into a "now-and-later" remediation.

### Invariant 2 — Commit convention

- **Format**: Conventional Commits with `(event-bus)` scope.
- **Examples**:
  - `feat(event-bus): introduce EventBus core dispatch + subscribe`
  - `refactor(event-bus): slim StepContext to app + run-scope flags`
  - `chore(event-bus): phase 3 gate — pipeline events migration`
- **No AI attribution**: never include `Co-Authored-By`, `Claude`, `Anthropic` (enforced by `hooks/block_ai_attribution.py`).
- **No version prefix**: version traceability lives in `IMPLEMENTATION.md`, not in commit messages.
- **Phase-gate commit**: at the end of every phase, the final commit message is `chore(event-bus): phase N gate — <short label>`.

### Invariant 3 — Hard verification gate template

Every phase gate MUST pass ALL of the following before the phase is considered complete:

1. **`make lint`** → zero errors (ruff + mypy).
2. **`make test`** → all tests pass; check the summary line `NNNN passed` with **zero failed / zero errors**. If any ERROR appears (vs FAILED), test COLLECTION crashed — fix imports immediately, the count after the error is meaningless.
3. **`make check`** → green (lint + test + module-size + typed-api). This is the canonical gate.
4. **Targeted greps** — the per-phase list (see each phase file). Each pattern's expected match count is **explicit**; deviations fail the gate.
5. **Module size budget** — every file under the `personalscraper/` tree obeys the DESIGN.md "Module size budget" table. Run `python3 scripts/check-module-size.py` (also part of `make check`).
6. **AST boundary test** — `pytest tests/architecture/test_app_context_boundary.py` green (from Phase 2 onwards once `AppContext` and the test exist).
7. **Smoke import** — `python -c "import personalscraper"` succeeds (catches circular imports introduced by event class registry).
8. **No-deferral audit** — re-read the phase's "Sub-phases" list; every box checked. Re-read the DESIGN sections covered by this phase; every feature listed has a sub-phase that delivered it AND a test that asserts it.

A phase that fails ANY gate item is NOT mergeable. The gate is not negotiable.

### Invariant 4 — Sweep-grep convention

When a sub-phase removes or renames a symbol, the sweep grep is **immediate**, not deferred. Sweep targets:

- `personalscraper/` (production code)
- `tests/` (unit + integration + E2E)
- `docs/reference/` (technical reference)
- `docs/features/` (in-progress feature docs, if any)
- Top-level scripts and `Makefile` if applicable

Use `rg <pattern> --type py personalscraper/ tests/` (always with `--type py` or `-g '*.py'` — see CLAUDE.md "Search Safety" rule, `tests/e2e/perf/.fixture/` is 14 GB of binary).

### Invariant 5 — Regression test per bug

Any bug discovered during implementation MUST have a regression test landed in the same sub-phase as the fix. This is a hard project rule. If the bug fix and the regression test cannot be co-located in a single commit, split the sub-phase to add a remediation sub-phase **immediately after** — never push the regression test to a later phase.

### Invariant 6 — `make check` between every sub-phase

Run `make check` at the **end of every sub-phase**, not just at phase gates. Sub-phases that fail their local `make check` are not committed.

### Invariant 7 — Tests use REAL data, never `MagicMock`

For sub-phases that introduce events, the `make_<event_name>()` factory MUST construct realistic, type-correct payload values. `MagicMock` defeats the purpose of the JSON round-trip test (which exists to catch non-serializable real shapes). This is enforced by code review and by the round-trip test failing loud on any non-serializable real shape that slips in.

### Invariant 8 — Determinism setup for snapshot tests

Any test that snapshots Rich Console output MUST use:

```python
Console(width=120, color_system=None, force_terminal=False, file=StringIO(), record=True)
```

Without this setup, terminal width/color detection makes the snapshot non-portable across dev/CI environments.

---

## Pre-flight checks (before starting Phase 1)

Execute these BEFORE creating any code:

1. **Clean working tree**:

   ```bash
   git status --porcelain
   ```

   Must be empty. If not, stash or commit existing work.

2. **On the feature branch**:

   ```bash
   git branch --show-current
   ```

   Must be `feat/event-bus`. (Created by `/implement:create-branch`, not by this plan.)

3. **Baseline test count**:

   ```bash
   make test 2>&1 | tail -20 | grep "passed"
   ```

   Record the baseline number — every phase gate compares against it.

4. **Baseline `make check` green on `main` merged into the branch**:

   ```bash
   make check
   ```

   Must be green. If it is red on the branch starting point, fix `main` first; do NOT inherit red gates.

5. **CLAUDE.md "Search Safety" rule loaded**:
   `rg` MUST always include `--type py` or `-g '*.py'`. `tests/e2e/perf/.fixture/` is 14 GB; a wildcard `rg` will crash the machine.

6. **No leftover prep artifacts in production paths**:
   ```bash
   ls docs/superpowers/roadmap/event-bus/specs/DESIGN.md  # exists
   ls docs/features/event-bus/  # should NOT exist yet on this branch — /implement:feature creates it
   ```

---

## Final acceptance pointer

This plan is complete when every sub-phase is checked **AND** the DESIGN.md "Acceptance criteria" section (last section of `../specs/DESIGN.md`) is fully satisfied:

- All five phases gate-green.
- `grep -r "PipelineObserver\|notify_progress\|StepEvent\|from personalscraper.observers" personalscraper/ tests/` returns zero matches.
- Every concrete event has a factory in `tests/fixtures/event_samples.py` (`test_every_event_has_factory` green) and passes the envelope round-trip test.
- `tests/architecture/test_app_context_boundary.py` green.
- `RichConsoleSubscriber` visually matches the removed `RichConsoleObserver` on the canonical pipeline-run snapshot test (deterministic Console setup).
- `TelegramSubscriber` alerts on `PipelineEnded`, `StepErrored`, `CircuitBreakerOpened`, `DiskFullWarning` (manual smoke test documented in PR description).
- `personalscraper run --verbose` produces a structured event log via `DebugLogSubscriber`.
- `docs/reference/event-bus.md` documents the full API, event catalog, boundary-only rule, ContextVar convention, and JSON contract split.
