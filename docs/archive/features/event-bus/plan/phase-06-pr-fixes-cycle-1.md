# Phase 6 — PR review cycle 1 fixes

## Context

PR #22 review cycle 1 surfaced 13 retained findings (after filtering against
DESIGN.md + the phase plan). No findings are critical (no correctness bugs,
no design contradictions). The retained set splits into one mechanical
cleanup (regex-sweep contamination), one stale-code cleanup (dead `is not
None` guards in dispatch), one structural docstring sweep (stale "Optional"
wording across 14+ sites), six factual corrections in
`docs/reference/event-bus.md`, two medium-severity doc/code drifts, and one
test coverage gap.

The findings come from the four pr-review-toolkit agents launched against
the branch diff (`code-reviewer`, `pr-test-analyzer`, `silent-failure-hunter`,
`comment-analyzer`). Two findings are explicitly **ignored** as out of
Phase 5 scope and documented in the cycle record:
`_GLOBAL_DISK_BREAKER` silent drops (pre-existing global path; commit body
acknowledges) and step CLI commands silently dropping events (design did
not specify subscriber wiring on per-step commands; only
`personalscraper run` is the operator-facing entry).

## Sub-phases

### 6.1 — Sweep regex-contaminated docstrings + comments

**Finding**: code-reviewer I-1. The Phase 5.2 regex script that added
`event_bus=EventBus()` to ~452 test call sites also rewrote text inside
docstrings and inline comments where the function name appeared, leaving
strings like
`"""Tests for ingest orchestration — run_ingest(event_bus=EventBus()) entry point."""`.

**Severity**: Major (impacts readability across 33+ files; CLAUDE.md
mandates Google-style docstrings).

**Files** (incomplete list — full grep `rg -n '"""[^"]*event_bus=EventBus|#[^!].*event_bus=EventBus' --type py tests/`):

- `tests/ingest/test_ingest.py:1`
- `tests/indexer/test_scanner.py:235,239,244,271,306,336,417,544,2592,2670`
- `tests/trailers/test_step.py:28,31,48,55,60,78,94,132,135,188`
- `tests/process/test_run.py:32`
- `tests/indexer/test_cli.py:162,648,681`
- `tests/sorter/test_e2e.py:174`
- `tests/e2e/test_pipeline_signatures.py:31,37,43`
- `tests/e2e/test_pipeline_movies.py:166`
- `tests/e2e/test_indexer_budget_resume.py:151`
- `tests/integration/test_outbox_paranoia_branch.py:126`
- `tests/integration/conftest.py:673`

**Acceptance**: `rg -n '"""[^"]*event_bus=EventBus|#[^!].*event_bus=EventBus' --type py tests/` → zero matches. Function/identifier mentions inside docstrings and comments should read `run_ingest`, `scan`, etc. — without the kwarg literal.

### 6.2 — Drop stale `is not None` guards on tightened dispatch sites

**Finding**: silent-failure-hunter C1. Dead branches that look defensive:

- `personalscraper/dispatch/_movie.py:154` — `and dispatcher._event_bus is not None`
- `personalscraper/dispatch/_tv.py:153` — same pattern

Since `Dispatcher.__init__` is now `event_bus: EventBus` (no `| None`), these
guards cannot evaluate False. Worse, their presence implies the bus may be
absent — misleading future maintainers.

**Severity**: Major (dead defensive code; my Phase 5.2 grep
`event_bus is not None` missed both sites because they're compound `and`
expressions, not standalone `if` guards).

**Acceptance**:

- The `_event_bus is not None` clause is dropped from both lines.
- `rg --type py 'dispatcher\._event_bus is not None|self\._event_bus is not None' personalscraper/` → zero matches (whitelist any remaining intentional guards in subscribers if applicable).
- All dispatch tests still pass.

### 6.3 — Sweep stale "Optional" / phase-milestone wording in docstrings

**Finding**: silent-failure-hunter I1 + comment-analyzer #7 + #8. ~14+
production sites still describe `event_bus` as "Optional" or reference
"Phase 4 / Phase 5.2" as a future event, even though Phase 5.2 IS this
phase and the parameter IS required. Concrete examples:

- `personalscraper/sorter/run.py:49`
- `personalscraper/verify/run.py:68`
- `personalscraper/enforce/run.py:39`
- `personalscraper/scraper/run.py:165`
- `personalscraper/dispatch/run.py:92`
- `personalscraper/ingest/ingest.py:276`
- `personalscraper/process/run.py:132,202,256`
- `personalscraper/scraper/orchestrator.py:60`
- `personalscraper/trailers/step.py:45`
- `personalscraper/api/metadata/tvdb.py:78`
- `personalscraper/indexer/db.py:202,264`
- `personalscraper/indexer/breaker.py:63`
- `personalscraper/indexer/_disk_guard.py:46`
- `personalscraper/indexer/commands/scan.py:71`
- `personalscraper/dispatch/dispatcher.py:68`
- `personalscraper/api/transport/_http.py:46-54` (still references "Sub-phase 5.2 tightened the Phase 4 | None migration contract")
- `personalscraper/core/circuit.py:17-23` (module docstring still has Phase 4 migration narrative)
- `personalscraper/commands/library/scan.py:94`

**Severity**: Major (docs lie about behaviour; a future maintainer reading
"Optional" will write a `None`-passing call and hit `AttributeError`).

**Acceptance**:

- Every `event_bus` docstring entry in production reads "Required …", with no "Optional" / "Phase 4" / "Phase 5.2" parenthetical.
- `rg -n --type py '(Optional :class:`EventBus`|Optional in Phase 4|Phase 5\.2 tighten|required in Phase 5)' personalscraper/` → zero matches.
- A short note explaining what the bus does for the caller (emit / forward to breaker / etc.) remains.

### 6.4 — Fix `event_to_envelope` JSON shape in reference doc

**Finding**: comment-analyzer #1. `docs/reference/event-bus.md:114-118 + 213-222`
claims the envelope is a flat dict with `_type` plus payload fields at the
top level. Actual code at `personalscraper/core/event_bus.py:100` returns
`{"_type": type_name, "data": event_to_dict(event)}` — payload is **nested
under `"data"`**. A reader copying the doc's snippet will break round-trip.

**Severity**: Major (doc lies about the wire shape).

**Acceptance**: §JSON serialization contract describes the actual `{"_type": ..., "data": {...}}` shape. The sample JSON example shows the nested shape. A round-trip test referenced in the doc must produce that exact shape.

### 6.5 — Fix `event_from_envelope` exception type in reference doc

**Finding**: comment-analyzer #2. `docs/reference/event-bus.md:125` says it
raises `ValueError`. Actual code at `personalscraper/core/event_bus.py:111`
raises `KeyError`.

**Severity**: Major (doc lies; subscribers catching `ValueError` will leak the error).

**Acceptance**: Doc says `KeyError` (matching the implementation), or the implementation is changed to `ValueError` (decision: keep `KeyError`, fix doc).

### 6.6 — Fix CLI bootstrap example to match real code

**Finding**: comment-analyzer #3. `docs/reference/event-bus.md:256-270`
shows `current_correlation_id.set(run_id) → pipeline.run(...) → reset(token)`
inside the CLI command body. Actual bind/reset lives inside `Pipeline.run`
at `personalscraper/pipeline.py:225,370` — the CLI command does NOT call
`current_correlation_id.set/reset`.

**Severity**: Major (the doc invents a code pattern that doesn't exist).

**Acceptance**: The example either (a) shows the real CLI fragment with a code-citation comment, or (b) is rewritten around `Pipeline.run` where the bind actually happens, with a comment noting the real boundary.

### 6.7 — Fix `ItemDispatched` and `TrailerDownloaded` catalog rows

**Finding**: comment-analyzer #5 + #6. The event catalog table in
`docs/reference/event-bus.md:157,162` lists fields that do not exist:

- `ItemDispatched` doc says `source: Path, destination: Path, disk: str, action: str`. Actual class at `personalscraper/dispatch/events.py:39-42`: `item: str`, `target_disk: Path`, `category_id: str`, `action: Literal["moved", "merged", "replaced"]`.
- `TrailerDownloaded` doc says `media_path: Path, youtube_url: str, quality: str | None`. Actual class at `personalscraper/trailers/events.py:29-31`: `media_path: Path`, `trailer_path: Path`, `source_url: str`.

Also: `ItemDispatched` producer column says `Dispatcher._move_*` — no such method exists; actual sites are `personalscraper/dispatch/_movie.py:158` and `_tv.py:157`.

**Severity**: Major (the catalog is the canonical reference and is wrong for 2/13 events).

**Acceptance**: The catalog table fields and producer columns match the actual class definitions and emit sites for every row (spot-check 5+ rows). Ideally, the table values are taken directly from the dataclass field names.

### 6.8 — Drop the `has_event_bus` log field that is now always True

**Finding**: silent-failure-hunter I2.
`personalscraper/indexer/commands/scan.py:123` logs
`has_event_bus=event_bus is not None`. Since `event_bus: "EventBus"` is now
required, this is always `True` — dead observability.

**Severity**: Medium.

**Acceptance**: The log call drops the field entirely (or replaces it with a meaningful one). `rg 'has_event_bus' --type py personalscraper/` → zero matches.

### 6.9 — Replace fictional `tests/perf/test_event_bus_overhead.py` reference

**Finding**: comment-analyzer #4. `docs/reference/event-bus.md:477` cites
this test as the perf measurement source. The file does not exist.

**Severity**: Medium (factual lie; low impact because the surrounding paragraph is informational).

**Acceptance**: The paragraph either (a) drops the test citation entirely with a softer "measured anecdotally" framing, or (b) references an existing perf test, or (c) the test is created.

### 6.10 — Fix "subscription order" semantics in reference doc

**Finding**: comment-analyzer #13. `docs/reference/event-bus.md:90` says
"Callbacks run in subscription order". Actual semantics at
`personalscraper/core/event_bus.py:402-426` (`_resolve_mro_chain`):
concrete-class-first, then FIFO within each class.

**Severity**: Medium.

**Acceptance**: §API reference describes the actual MRO-walk order (concrete class first, then ancestors, FIFO within each class). A subscriber author reading this must come away with the correct mental model.

### 6.11 — Add `DebugLogSubscriber.close()` finally-path coverage

**Finding**: pr-test-analyzer Important. The CLI's `finally` block
(`personalscraper/commands/pipeline.py:384-385`) calls
`debug_subscriber.close()` even when `pipeline.run()` raises, but no test
verifies this happens. Combined with the missing exception-path closure
test for `rich_subscriber` and `telegram_subscriber`.

**Severity**: Medium.

**Acceptance**:

- A new test in `tests/integration/test_run_verbose_debug_log.py` stubs the Pipeline to `raise` mid-run, then emits one more event on the bus after the `runner.invoke` returns, and asserts the `DebugLogSubscriber` no longer receives it (proving `close()` was called on the exception path).
- The test runs in the existing CI test suite.

### 6.12 — Fix minor wording drift in `docs/reference/event-bus.md`

**Finding**: comment-analyzer #11 + #12. The doc claims:

- "29 LOC total" for `DebugLogSubscriber` — actual file is 39 LOC counting blanks (29 non-blank).
- "~4200-test suite" — CLAUDE.md says "2642+ tests". Both are accurate at different counting moments, but they look inconsistent.

**Severity**: Minor.

**Acceptance**: The doc clarifies "non-blank LOC" vs "total" and avoids absolute test-count assertions; or simply removes the LOC count entirely and lets readers `wc -l` the file themselves.

### 6.13 — Phase 6 gate

Re-run the Phase 5.6 gate items 1-17 (lint + tests + audit greps + module sizes + smoke imports). Commit `chore(event-bus): phase 6 gate — PR review cycle 1 fixes applied`.

**Acceptance**:

- `make check` → green.
- All audit greps still zero.
- Test count: ≥ 4232 (4231 baseline + 1 new finally-path test).
- The four agent findings classified as "Retained" above are demonstrably resolved (re-grep, re-read the doc).
