# Event Bus Implementation Plan — INDEX

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Feature**: Event Bus
**Codename**: event-bus
**SemVer bump**: minor (Y+1)
**Date**: 2026-05-11
**Status**: spec (preparation — not yet implemented)
**Design**: [`../DESIGN.md`](../DESIGN.md)
**Goal**: Replace `PipelineObserver` Protocol with a single application-wide `EventBus` that serves as the only substrate for cross-component asynchronous communication.
**Architecture**: In-process typed pub/sub with type-indexed `subscribe`, MRO-walking dispatch, frozen dataclass events inheriting a common `Event` base, JSON-serializable with split `event_to_dict` / `event_to_envelope` contracts, `correlation_id` captured at event construction via `current_correlation_id` `ContextVar`. Owned by an `AppContext` that lives at process boundaries only.
**Layout note**: `personalscraper/pipeline.py` is a **single flat module** today, not a package. Pipeline events live at `personalscraper/pipeline_events.py` (sibling flat module), NOT at `personalscraper/pipeline/events.py` (which would require converting `pipeline.py` to a package — explicitly **out of scope** for this feature per DESIGN). The same convention applies to `personalscraper/dispatch/events.py` (dispatch IS a package), `personalscraper/indexer/events.py`, `personalscraper/trailers/events.py` (each is a package), and `personalscraper/core/circuit.py` (events embedded, single flat module).
**Tech stack**: Python ≥ 3.10 (per `pyproject.toml` `requires-python = ">=3.10"`; pyenv 3.11.9 is the dev shell but the code targets 3.10+), `dataclasses` (frozen), `contextvars`, `structlog`, `rich` (subscriber), `pytest`.

---

## Phase summary

| Phase | Name                                   | Sub-phases | Depends on | File                                                                             |
| ----- | -------------------------------------- | ---------- | ---------- | -------------------------------------------------------------------------------- |
| 1     | Foundation (standalone)                | 9          | —          | [`phase-01-foundation.md`](phase-01-foundation.md)                               |
| 2     | AppContext + StepContext slim          | 9          | Phase 1    | [`phase-02-app-context-step-context.md`](phase-02-app-context-step-context.md)   |
| 3     | Pipeline event migration + subscribers | 11         | Phase 2    | [`phase-03-pipeline-events-migration.md`](phase-03-pipeline-events-migration.md) |
| 4     | Cross-cutting events                   | 7          | Phase 3    | [`phase-04-cross-cutting-events.md`](phase-04-cross-cutting-events.md)           |
| 5     | Required-bus tightening + CLI polish   | 6          | Phase 4    | [`phase-05-required-bus-cli-polish.md`](phase-05-required-bus-cli-polish.md)     |

Total sub-phases: **42**. Total commits (estimate): **42–49** (most sub-phases = 1 commit each; Phase 2 split the StepContext refactor across 2.2a/2.2b/2.2c, Phase 3 split the legacy deletion across 3.7a/3.7b/3.7c, Phase 4 split the conditional DiskGuard extraction at 4.2a from the emit at 4.2b, Phase 5 folded its audit-only step into the gate; sub-phase 3.1 may produce 1 commit (happy path) OR 2+ commits (if Report JSON-safety pre-investigation surfaces non-JSON-safe fields, each coerced via its own `fix(event-bus): ...` commit). The upper bound 49 accommodates 2 coercion commits in 3.1, 4 atomic commits in 5.2 if multiple `| None` sites exist, and one optional `fix(event-bus): legitimate skip — <justification>` commit allowed by Pre-flight #9 (rare, exceptional).

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
- **No AI attribution**: never include `Co-Authored-By`, `Claude`, `Anthropic` (enforced by `.claude/hooks/block_ai_attribution.py`).
- **No version prefix**: version traceability lives in `IMPLEMENTATION.md`, not in commit messages.
- **Phase-gate commit**: at the end of every phase, the final commit message is `chore(event-bus): phase N gate — <short label>`.

### Invariant 3 — Hard verification gate template

Every phase gate MUST pass ALL of the following before the phase is considered complete:

1. **`make lint`** → zero errors (ruff + mypy).
2. **`make test`** → all tests pass; check the summary line `NNNN passed` with **zero failed / zero errors**. If any ERROR appears (vs FAILED), test COLLECTION crashed — fix imports immediately, the count after the error is meaningless.
3. **Skip / xfail baseline must NOT grow** — `rg -c '@pytest\.mark\.(skip|xfail|skipif)' tests/ -g '*.py'` MUST equal the baseline locked in Pre-flight #9 below. A new skip / xfail is a silent deferral and a gate failure. To honour Invariant 1, no agent may add `@pytest.mark.skip`, `@pytest.mark.xfail`, or `@pytest.mark.skipif` during this feature. If a hard test cannot pass, the underlying bug is fixed, not the test silenced.
4. **`make check`** → green (lint + test + module-size + typed-api). This is the canonical gate.
5. **Targeted greps** — the per-phase list (see each phase file). Each pattern's expected match count is **explicit**; deviations fail the gate.
6. **Module size budget** — every file under the `personalscraper/` tree obeys the DESIGN.md "Module size budget" table. Run `python3 scripts/check-module-size.py` (also part of `make check`).
7. **AST boundary test** — `pytest tests/architecture/test_app_context_boundary.py` green (from Phase 2 onwards once `AppContext` and the test exist).
8. **Smoke import** — `python -c "import personalscraper"` succeeds (catches circular imports introduced by event class registry).
9. **No unresolved placeholders** — `rg -F '<N_CALLS>' docs/features/event-bus/` and `rg -F '<TBD-by-4.2a>' docs/features/event-bus/` MUST each return zero matches by the relevant phase (3.4 / 4.2b respectively). A literal placeholder reaching its consumer sub-phase is an unfilled Pre-flight step and a gate failure.
10. **No deferred work in IMPLEMENTATION.md** — the canonical banned-token grep (re-used identically at Phase 5.6 §16):

    ```bash
    rg -i 'TODO|deferred|follow-?up|next phase|next sub-phase|TBD|to be done|to be implemented|parked|revisit|will be done|forthcoming|pending|out of scope|later' IMPLEMENTATION.md
    ```

    MUST return zero matches at every phase gate. The token list is intentionally exhaustive — common evasive paraphrases (`parked`, `revisit`, `pending`, `later`, etc.) are explicit banned tokens. An agent that rephrases deferral language to evade this grep is acting in bad faith; the PR review checklist explicitly looks for paraphrased deferrals AND for new evasive vocabulary not yet in this list (in which case the list itself is bumped, in the same commit, as a `fix(event-bus): extend banned-token list — <new token>` commit).

11. **No-deferral audit (mechanical)** — for each DESIGN section listed in the phase's "Scope", grep the section's keywords against the phase file. Every keyword MUST appear in at least one sub-phase heading or behavior bullet. The mapping table (DESIGN section → phase sub-phase) is captured in each phase file's "Scope" block and re-asserted by an INDEX-level cross-check at the feature gate (Phase 5.6 §14 — the DESIGN Acceptance criteria audit sub-bullet list).

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

### Invariant 9 — Event class registry hygiene for test stubs

`Event.__init_subclass__` registers every subclass in `_EVENT_CLASS_REGISTRY` at import time. Test files that define ad-hoc Event subclasses (e.g. `class Foo(Event): pass` in a test module) would otherwise pollute the registry permanently, breaking the Phase 4 / Phase 5 gate assertion that registry size equals exactly the count of production events.

The registry MUST filter by module path:

```python
# in personalscraper/core/event_bus.py
class Event:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only register production events. Test stubs (under tests/*) are
        # excluded so the registry size stays equal to the v1 catalog count.
        if cls.__module__.startswith("personalscraper."):
            _EVENT_CLASS_REGISTRY[cls.__name__] = cls
```

`test_every_event_has_factory` (Phase 1.8) iterates only this filtered registry, so test stubs do not need to provide factories. The Phase 4.6 / Phase 5.6 gate assertions over `len(_EVENT_CLASS_REGISTRY)` are deterministic regardless of pytest collection order.

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

6. **Design + plan in place, no leftover prep artifacts**:

   ```bash
   ls docs/features/event-bus/DESIGN.md            # exists (moved by /implement:feature)
   ls docs/features/event-bus/plan/INDEX.md        # exists (moved by /implement:feature)
   ls docs/superpowers/roadmap/event-bus 2>&1 | grep -q 'No such' && echo "OK"   # MUST be absent
   ```

7. **Record canonical Rich Console snapshot baseline** (used by Sub-phases 2.4 visual smoke, 3.5 RichConsoleSubscriber rewrite, and 3.9 Phase 3 gate visual regression):

   The baseline is a **byte-identical capture** of `RichConsoleObserver`'s output for a **hand-crafted synthetic event sequence** — NOT a real pipeline run (real runs depend on TMDB, disk state, system clock, file ordering, and are non-deterministic).

   Create `tests/snapshots/_canonical_sequence.py` with a hand-crafted `CANONICAL_SEQUENCE: list[tuple[str, tuple]]` — a list of `(callback_name, args_tuple)` pairs replayed in order through the observer. The sequence MUST exercise every code path of `RichConsoleObserver`:
   - `on_pipeline_start` with `dry_run=False` (LIVE label) AND a separate run with `dry_run=True` (DRY-RUN label) — both produce baseline artefacts.
   - `on_step_start` + `on_step_end` for each of the 9 steps (`ingest`, `sorter`, `process`, `scraper`, `enforce`, `verify`, `cleanup` if present, `trailers`, `dispatch`).
   - `on_progress` with `StepEvent` covering every status value used by the codebase: `"started"`, `"completed"`, `"skipped"`, `"failed"`, `"moved"`, `"copied"`, `"fixed"`, `"blocked"`, `"cleaned"`, `"error"` (the full list per `pipeline_observer.py::StepEvent` docstring).
   - One `on_step_error` for a stub step name.
   - `on_pipeline_end` with mixed success/skip/error counts.

   All `StepReport` and `PipelineReport` payload values are concrete literals (no `MagicMock`). Timestamps are fixed: `datetime(2026, 5, 11, 10, 0, 0, tzinfo=UTC)` for start, `+5 minutes` for end. Run-IDs are fixed strings (e.g. `"canonical-live"`, `"canonical-dry"`). This locks every variable that could drift across machines.

   Coverage gate: the recording test MUST achieve **100% line coverage of `personalscraper/observers/rich_console.py`** — verify by `coverage run -m pytest tests/snapshots/test_record_baseline.py && coverage report --include='personalscraper/observers/rich_console.py'`. If any line is uncovered, the sequence is incomplete and must be extended before recording.

   Record the baseline once:

   ```python
   # tests/snapshots/test_record_baseline.py — one-shot recorder, then deleted
   from io import StringIO
   from pathlib import Path
   from rich.console import Console
   from personalscraper.observers.rich_console import RichConsoleObserver
   from tests.snapshots._canonical_sequence import CANONICAL_SEQUENCE


   def test_record_baseline() -> None:
       console = Console(width=120, color_system=None, force_terminal=False,
                         file=StringIO(), record=True)
       observer = RichConsoleObserver(console=console, dry_run=False, run_id="canonical-live")
       for callback_name, args in CANONICAL_SEQUENCE:
           getattr(observer, callback_name)(*args)
       Path("tests/snapshots/rich_console_canonical.txt").write_text(
           console.export_text()
       )
   ```

   Run it ONCE here, commit the .txt (verify with `git check-ignore -v tests/snapshots/rich_console_canonical.txt` returning nothing — `tests/` is NOT blocked by global `~/.gitignore`). Then **delete `test_record_baseline.py`** in the same commit (it ran once, recorded, done — keeping it would re-record on every CI run and defeat immutability). Keep `_canonical_sequence.py` (Phase 2 and Phase 3 tests replay it through Observer/Subscriber respectively).

   This .txt file is the **single immutable baseline** referenced by Phase 2 §2.4 (CLI output unchanged after Pipeline refactor — replay `CANONICAL_SEQUENCE` through legacy `RichConsoleObserver` and compare), Phase 3 §3.5 (RichConsoleSubscriber matches legacy — replay through new subscriber via bus emit and compare), and Phase 3 §3.9 gate (visual regression check). Bytes-identical rendering is the invariant.

8. **Enumerate `notify_progress` sites and lock the exact counts in this INDEX** (used by Phase 3 sub-phase 3.4 mechanical sweep + Phase 3.7b/3.7c gate audits):

   ```bash
   rg 'notify_progress\(' --type py personalscraper/ > /tmp/notify_progress_calls.txt
   rg 'notify_progress\(' --type py personalscraper/ -l | sort > /tmp/notify_progress_files.txt
   wc -l /tmp/notify_progress_calls.txt    # total call-line count
   wc -l /tmp/notify_progress_files.txt    # file count
   cat /tmp/notify_progress_files.txt      # the actual file list
   ```

   Record the captured numbers HERE in this INDEX before starting Phase 1, replacing the placeholders below:
   - **Total `notify_progress(` call-lines in `personalscraper/` (production code)**: `<N_CALLS>` (to fill at Pre-flight)
   - **Files containing `notify_progress(` (excluding `pipeline_observer.py` which defines the helper)**: `<N_FILES>` (to fill at Pre-flight)
   - **File list** (verbatim from the grep output, alphabetical): `<paste-list-here>`

   These exact numbers are the **gate targets**:
   - Phase 3.4 gate: after the mechanical sweep, `rg 'event_bus\.emit\(ItemProgressed' --type py personalscraper/ | wc -l` MUST equal `<N_CALLS>` (every legacy site has a paired bus emit alongside).
   - Phase 3.4 gate: `rg 'notify_progress\(' --type py personalscraper/ | wc -l` MUST still equal `<N_CALLS>` (legacy NOT removed yet — that's 3.7b's job).
   - Phase 3.7b gate: `rg 'notify_progress\(' --type py personalscraper/ | wc -l` MUST equal `0`.
   - Phase 3.7b gate: `rg 'event_bus\.emit\(ItemProgressed' --type py personalscraper/ | wc -l` MUST still equal `<N_CALLS>` (only legacy removed; bus emit preserved).

   Phase 3 sub-phase 3.4 migrates EVERY site in a single mechanical sweep (one commit). The invariant is "every legacy site has a paired bus emit by end of 3.4, and zero legacy sites by end of 3.7b".

9. **Capture skip / xfail baseline** (used by Invariant 3 gate item 3):

   ```bash
   rg -c '@pytest\.mark\.(skip|xfail|skipif)' tests/ -g '*.py' | awk -F: '{s+=$2} END{print s}' > /tmp/skip_baseline.txt
   cat /tmp/skip_baseline.txt
   ```

   Record the integer HERE before starting Phase 1:
   - **Skip / xfail count at feature start**: `<SKIP_BASELINE>` (to fill at Pre-flight)

   Every phase gate re-runs the same `rg | awk` command and asserts equality with `<SKIP_BASELINE>`. ANY growth means a new `@pytest.mark.skip` or `@pytest.mark.xfail` was added during the feature — that is a banned form of deferral per Invariant 1. The PR reviewer cross-checks this number against the gate-commit body.

   If a legitimate skip is required (e.g. a platform-conditional that the feature doesn't introduce but discovers), the change MUST be its own `fix(event-bus): legitimate skip — <justification>` commit BEFORE the gate, and `<SKIP_BASELINE>` is bumped explicitly in the same commit with a one-paragraph justification. No silent baseline drift.

10. **`docs/reference/event-bus.md` outline locked** (Phase 5.5 target — captured here so the doc-completeness gate at Phase 5.6 §14 (the "Reference doc complete" sub-bullet of the Acceptance criteria audit) can grep section headings mechanically):

    The reference doc MUST contain exactly these top-level section headings, each followed by ≥ 20 LOC of body content:
    - `## Purpose & high-level architecture`
    - `## API reference`
    - `## Event catalog (v1)`
    - `## Boundary-only AppContext rule`
    - `## JSON serialization contract`
    - `## current_correlation_id ContextVar convention`
    - `## Writing a new event`
    - `## Writing a new subscriber`
    - `## Testing patterns`
    - `## Performance notes`
    - `## Future evolution`

    Phase 5.6 §14's "Reference doc complete" sub-bullet is the bash loop in this INDEX Pre-flight #10 converted into a gate command. Locked here so renumbering of sections requires an INDEX edit, not silent drift.

---

## Final acceptance pointer

This plan is complete when every sub-phase is checked **AND** the DESIGN.md "Acceptance criteria" section (last section of `../DESIGN.md`) is fully satisfied:

- All five phases gate-green.
- `rg --type py 'PipelineObserver|notify_progress|StepEvent|from personalscraper\.observers' personalscraper/ tests/` returns zero matches. (Use `rg --type py`, NOT bare `grep -r` — the latter would scan `tests/e2e/perf/.fixture/` 14 GB and crash the machine per CLAUDE.md "Search Safety".)
- Every concrete event has a factory in `tests/fixtures/event_samples.py` (`test_every_event_has_factory` green) and passes the envelope round-trip test.
- `tests/architecture/test_app_context_boundary.py` green.
- `RichConsoleSubscriber` visually matches the removed `RichConsoleObserver` on the canonical pipeline-run snapshot test (deterministic Console setup).
- `TelegramSubscriber` alerts on `PipelineEnded`, `StepErrored`, `CircuitBreakerOpened`, `DiskFullWarning` (manual smoke test documented in PR description).
- `personalscraper run --verbose` produces a structured event log via `DebugLogSubscriber`.
- `docs/reference/event-bus.md` documents the full API, event catalog, boundary-only rule, ContextVar convention, and JSON contract split.
