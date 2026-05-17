# Implementation Progress — event-bus

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `event-bus`
**Feature**: Event Bus (minor)
**Version bump**: 0.13.0 → 0.14.0
**Branch**: feat/event-bus
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/22
**Design**: docs/features/event-bus/DESIGN.md
**Master plan**: docs/features/event-bus/plan/INDEX.md

## Scope discipline — see INDEX.md Invariant 1

Every step is adapted, every test is written, nothing is skipped, and every
sub-phase verifies design + plan compliance. The exhaustive enumeration of
banned vocabulary, the rationale, and the gate-time grep all live in
[`INDEX.md`](docs/features/event-bus/plan/INDEX.md) Invariant 1 + Invariant
3 §10 and [`DESIGN.md`](docs/features/event-bus/DESIGN.md). Keeping the
enumeration there (and out of this file) means the Phase 5.6 gate-time grep
on IMPLEMENTATION.md returns zero matches without weakening the rule.

Paraphrasing the rule is itself a violation; new evasive vocabulary
surfaced in review extends the canonical list in the same fix commit (per
the protocol in INDEX.md Invariant 3 §10).

## Phases

| #   | Phase                                  | Type    | File                                                                                                        | Status |
| --- | -------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------- | ------ |
| 1   | Foundation (standalone)                | core    | [phase-01-foundation.md](docs/features/event-bus/plan/phase-01-foundation.md)                               | [x]    |
| 2   | AppContext + StepContext slim          | core    | [phase-02-app-context-step-context.md](docs/features/event-bus/plan/phase-02-app-context-step-context.md)   | [x]    |
| 3   | Pipeline event migration + subscribers | migrate | [phase-03-pipeline-events-migration.md](docs/features/event-bus/plan/phase-03-pipeline-events-migration.md) | [x]    |
| 4   | Cross-cutting events                   | core    | [phase-04-cross-cutting-events.md](docs/features/event-bus/plan/phase-04-cross-cutting-events.md)           | [x]    |
| 5   | Required-bus tightening + CLI polish   | polish  | [phase-05-required-bus-cli-polish.md](docs/features/event-bus/plan/phase-05-required-bus-cli-polish.md)     | [x]    |
| 6   | PR review cycle 1 fixes                | fix     | [phase-06-pr-fixes-cycle-1.md](docs/features/event-bus/plan/phase-06-pr-fixes-cycle-1.md)                   | [x]    |
| 7   | PR review cycle 2 fixes                | fix     | (inline — five reviewer agents; see commit body)                                                            | [x]    |

Total sub-phases: **42** (per INDEX.md). Estimated commits: **42–49**.

## Phase 7 — PR review cycle 2 fixes (W1-W3 + I1-I14)

Five reviewer agents (code-reviewer, silent-failure-hunter, pr-test-analyzer,
comment-analyzer, type-design-analyzer) produced findings against PR #22.
Cycle 2 implements all critical (W1-W3) and important (I1-I14) corrections:

- **W1 — bus-detached emit sites**: every production command path now threads
  the AppContext bus (or accepts an explicit `event_bus`). Sites fixed:
  `trailers/step.py:75`, `library_index_command` (open_db × 2 + scan),
  `MediaIndex.__init__`, `library_reconcile_command`, the seven per-step
  Typer subcommands in `commands/pipeline.py`, the indexer command surface
  (`{diagnose, query, repair}.py`), library tooling (`scan_library`,
  `rescrape_library`, library-analyze / -recommend / -report / -validate),
  and `trailers/cli.py verify`. Regression tests pin the pass-through
  contract (`test_orchestrator_receives_caller_bus`,
  `test_library_index_command_forwards_bus_to_scan_and_open_db`).
- **W1/C2 — global disk-breaker rebinding**: `bind_global_disk_breaker_to_bus`
  added to `indexer/breaker.py` and called from `indexer/scanner/__init__.py`
  so the import-time singleton's per-disk emits reach the run's bus.
- **W3 — CircuitBreaker thread safety**: `threading.Lock` added to both
  `core/circuit.py` (state property + record_success/record_failure) and
  `indexer/breaker.py` (DiskCircuitBreaker.record_failure direct-mutation
  path). Regression test pins single emit under 16 concurrent state reads.
- **W2 / I7 / I6 — `docs/reference/event-bus.md`**: JSON contract rows
  rewritten to match the fail-loud `TypeError` reality (no `str()` coercion,
  no `repr` fallback). `Event` base fields described as `default_factory`
  rather than `__post_init__`. `LibraryScanCompleted` producer location
  corrected to `scanner.scan` finally block.
- **I1-I5, I8 — docstring rot**: `--headless` CLI help, `_run_step`
  docstring, `_disk_guard` "optional", `TelegramSubscriber.close`
  "both tokens", `DebugLogSubscriber` "envelope", `state` property side
  effect — all scrubbed.
- **I9-I12 — error logging context**: scanner OSError warnings gain
  `errno` + `strerror` + `exc_info=True`; `_disk_guard` secondary checkpoint
  - DB-path lookup log at DEBUG; `dispatcher` disk iterdir logs structured
    context; `PipelineEnded` emit failure demoted to WARNING.
- **I13 — `indexer/scanner/__init__.py` over 1000 LOC**: the file is at
  1029 non-blank lines but is currently exempted by
  `scripts/check-module-size.py` (the script excludes every `__init__.py`).
  Treated as a project-policy decision outside this PR's scope — keep the
  current exemption. A dedicated refactor to extract the orchestrator body
  to `scanner/_orchestrator.py` would also touch hot paths and is deferred
  to a follow-up issue.
- **I14 — orphan `if TYPE_CHECKING: pass`** in `indexer/breaker.py` removed.

## Quality gate (every commit)

```bash
make check
python3 scripts/check-module-size.py
python3 scripts/check-typed-api.py
```

Every milestone commit (`chore(event-bus): phase N gate — <summary>`) must pass:

1. `make lint` — ruff + mypy clean.
2. `make test` — all tests pass.
3. `make check` — composite gate.
4. Skip / xfail baseline unchanged (see INDEX.md Pre-flight #9).
5. Per-phase targeted greps (see each phase file).
6. Module size budget respected (per DESIGN.md).
7. Smoke import: `python -c "import personalscraper"`.

See CLAUDE.md "Phase Gate Checklist (MANDATORY)" and INDEX.md Invariant 3 for the full protocol.

## Sub-phase → SHA mapping

### Phase 1 — Foundation

| Sub-phase | SHA       | Description                                                           |
| --------- | --------- | --------------------------------------------------------------------- |
| pre-1.1   | `505596c` | Pre-flight baselines (tests=3738, skip=6, notify_progress=46/8 files) |
| 1.1       | `08616a3` | Event base + current_correlation_id ContextVar (10 tests)             |
| 1.2       | `28e4121` | EventBus.subscribe/unsubscribe + SubscriptionToken (COW) (7 tests)    |
| 1.3       | `f694070` | EventBus.emit + MRO cache + zero-alloc fast path (10 tests)           |
| 1.4       | `492ac24` | Error isolation + re-entrant emit safety (6 tests)                    |
| 1.5       | `6acfa18` | event_to_dict pure-payload JSON encoder (12 tests)                    |
| 1.6       | `92fad12` | event_to_envelope/from_envelope + class registry (12 tests)           |
| 1.7       | `a1e7d4c` | correlation_id ContextVar capture semantics (8 tests)                 |
| 1.8       | `026fda6` | CollectingSubscriber + factories registry mechanism (9 tests)         |
| 1.9       | `aae849e` | Phase 1 gate (no new code, all 10 verification items green)           |

### Phase 2 — AppContext + StepContext slim

| Sub-phase | SHA       | Description                                                              |
| --------- | --------- | ------------------------------------------------------------------------ |
| 2.1       | `343001f` | AppContext frozen dataclass at core/app_context.py (3 tests)             |
| 2.2a      | `fcc68dd` | StepContext gains app + run_id, legacy mirrors via **post_init** (6)     |
| 2.2b      | `4b90106` | Sweep ctx.config/settings → ctx.app.config/settings (27 sites)           |
| 2.2c      | `be8a52e` | Drop legacy mirrors from StepContext; final 2.2 shape                    |
| pre-2.4   | `248f29d` | Pre-flight #7 — canonical Rich Console snapshot baseline                 |
| 2.3       | `879cda8` | Pipeline.\_\_init\_\_(app), per-run run_id, ContextVar bind (9 tests)    |
| 2.4       | `e1b4a17` | CLI entry builds AppContext via `_build_app_context` (3 tests)           |
| 2.5       | `5969555` | launchd scan + 4 trailers commands rewired; bus to orchestrators (12 t.) |
| 2.6       | `28d4d9a` | tests/architecture/test_app_context_boundary.py (AST allowlist, 5 t.)    |
| 2.7       | `51a4bae` | Phase 2 gate (10 verification items)                                     |

### Phase 3 — Pipeline event migration + subscribers

| Sub-phase | SHA                                           | Description                                                                                       |
| --------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 3.1       | `050bfd0` / `05e2dea` / `0ebf080` / `bfda5f6` | pipeline event catalog + factories + Report JSON-safety (4 commits, see "Notes on 3.1" below)     |
| 3.2       | `59697ef`                                     | Pipeline emits `PipelineStarted` / `PipelineEnded`                                                |
| 3.3       | `f3841c6`                                     | Pipeline emits `StepStarted` / `StepCompleted` / `StepErrored` around each of the 9 steps         |
| 3.4       | `27f85a8`                                     | Step emit migration: 46 sites migrated, `event_bus` kwarg threaded into all 9 `run_*` entries (9) |
| 3.5       | `16471eb`                                     | `RichConsoleSubscriber` rewrite; baseline byte-identity locked vs canonical snapshot              |
| 3.6       | `d893d12`                                     | `TelegramSubscriber` rewrite (PipelineEnded + StepErrored); cassette via `responses`              |
| 3.7a      | `2202364`                                     | Migrate every test off the legacy Observer API; 4 legacy test files deleted                       |
| 3.7b      | `7cff5db`                                     | Delete legacy infrastructure: `pipeline_observer.py`, `observers/`, `StepContext.observers`       |
| 3.7c      | `4bdb695`                                     | Docs sweep + new bus reference section in `docs/reference/pipeline-internals.md`                  |
| 3.8       | `14d530e`                                     | structlog dedup audit at emit sites (1 removed, 5 kept); parametrized AST audit (227 files)       |
| 3.9       | `e6b8290`                                     | Phase 3 gate                                                                                      |
| post-3.9  | `dba9ed0` / `4b13497`                         | Post-gate cleanup: scrub residual docstring + pin resumption HEAD                                 |

**Notes on 3.1**: `bfda5f6` lands the catalog + factories + envelope round-trip; `050bfd0`, `05e2dea`, and `0ebf080` are the three Report JSON-safety coercion fixes surfaced by the round-trip test (StepReport.failed_items, StepReport.details_payload, PEP 604 union decoding).

### Phase 4 — Cross-cutting events

| Sub-phase | SHA       | Description                                                                                  |
| --------- | --------- | -------------------------------------------------------------------------------------------- |
| 4.1       | `ad99051` | `CircuitBreakerOpened` / `Closed` / `HalfOpened`; Telegram subscription #3 (13 tests)        |
| 4.2a      | `bedb7cc` | Locator probe Case A → extract `handle_disk_full` to `indexer/_disk_guard.py` (2 tests)      |
| 4.2b      | `f04da92` | `DiskFullWarning` emit (both check_free_space + handle_disk_full); Telegram sub #4 (8 tests) |
| 4.3       | `1011e41` | `ItemDispatched` emit from `_movie.dispatch_movie` + `_tv.dispatch_tvshow` (9 tests)         |
| 4.4       | `90ffdec` | `TrailerDownloaded` emit from `TrailersOrchestrator` success branch (8 tests)                |
| 4.5       | `3420dca` | `LibraryScanCompleted` emit in `scan()` finally block (all 6 modes covered) (10 tests)       |
| 4.6       | `8ff7014` | Phase 4 gate                                                                                 |

**Phase 4 audit (recorded in gate commit body for Phase 5.2 baseline)**:

```
event_bus_optional_sites_count: 20
circuit_breaker_calls_without_event_bus_count: 4
```

The 4 `CircuitBreaker(` matches without `event_bus=` on the same line are
all multi-line constructor calls — 3 production sites already pass
`event_bus=` on a subsequent line (`api/transport/_http.py`,
`indexer/breaker.py`, `trailers/orchestrator.py`) plus the module-level
`_GLOBAL_DISK_BREAKER = DiskCircuitBreaker()` singleton init. Phase 5.2
removes the `| None` from `CircuitBreaker.__init__(event_bus=...)` and
forces every site to pass `event_bus` explicitly.

### Phase 6 — PR review cycle 1 fixes

| Sub-phase | SHA       | Description                                                                                                                                                                                             |
| --------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6.1       | `6857be7` | Scrub regex-sweep contaminations from docstrings + comments (58 lines across 23 files)                                                                                                                  |
| 6.2       | `ea1f1a3` | Drop stale `dispatcher._event_bus is not None` compound guards in `dispatch/_movie.py` + `_tv.py`                                                                                                       |
| 6.3       | `cbcc730` | Sweep stale "Optional" / phase-milestone wording across 19 docstrings (production)                                                                                                                      |
| 6.4–6.12  | `84ac67d` | Bundle: doc corrections in `event-bus.md` (envelope shape, KeyError, CLI bootstrap, catalog rows, callback order, perf wording, LOC drift), drop `has_event_bus` log field, add CLI exception-path test |
| 6.13      | _(this)_  | Phase 6 gate                                                                                                                                                                                            |

### Phase 5 — Required-bus tightening + CLI polish

| Sub-phase | SHA       | Description                                                                                  |
| --------- | --------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| 5.1       | `849b56e` | Make `CircuitBreaker.event_bus` required; drop emit guards; +2 signature tests               |
| 5.2       | `67b5dc1` | Tighten remaining 20 Phase-4 `                                                               | None` sites; AST signature suite; ~50 emit guards dropped |
| 5.3       | `15c48bb` | `DebugLogSubscriber` (29 LOC) + 16 tests over all 13 v1 events                               |
| 5.4       | `d728a16` | Wire `personalscraper run --verbose` to register `DebugLogSubscriber` (2 integration tests)  |
| 5.5       | `b62f6ab` | `docs/reference/event-bus.md` (11 sections, ≥ 20 LOC each); CLAUDE.md Reference Index update |
| 5.6       | _(this)_  | Phase 5 gate + feature acceptance audit                                                      |

## Review cycles

### Cycle 1

- Findings received: 4 agents (code-reviewer, pr-test-analyzer, silent-failure-hunter, comment-analyzer) — 26 raw findings.
- Retained: 13 (0 critical, 8 major, 4 medium, 1 minor — full classification in `docs/features/event-bus/plan/phase-06-pr-fixes-cycle-1.md`).
- Ignored: 13 (out of Phase 5 scope, documented decisions, or positive observations). Notably:
  - `_GLOBAL_DISK_BREAKER` silent drops: pre-existing architectural decision; module docstring acknowledges "effectively dropped" via the AppContext-wired path; scanner restructure is scope-expansion.
  - Step CLI commands silently drop events: design did not specify per-step subscriber wiring; only `personalscraper run` is the operator-facing entry.
- Fix phase created: `phase-06-pr-fixes-cycle-1.md`.
- Status: clean — fix phase executed across SHAs `6857be7`, `ea1f1a3`, `cbcc730`, `84ac67d`; Phase 6 gate at `1567089`. CI green on the fix commits.

### Cycle 2

- Findings received: focused verification run (1 `pr-review-toolkit:code-reviewer` agent against the Phase 6 commit range `fe6163e..1567089`).
- Retained: 0 (zero new findings; all 12 Cycle 1 retained items confirmed resolved with file:line evidence — see agent report).
- Ignored: 0.
- Fix phase created: none.
- Status: **clean — proceeding to merge** (manual mode per IMPLEMENTATION.md header). All audit greps zero; targeted test slices (`tests/dispatch tests/trailers tests/integration tests/indexer tests/ingest`) → 1049 passed, 2 skipped; lint + mypy + format clean on the full repo.

## Resumption snapshot — read FIRST when resuming

**HEAD SHA**: _(this commit)_ — `chore(event-bus): phase 6 gate — PR review cycle 1 fixes applied`.
**Branch**: `feat/event-bus` — pushed to origin (CI passing on Phase 5 gate; this Phase 6 gate awaits a re-poll).
**Working tree**: clean.
**Last successful gate**: Phase 6 gate (PR review cycle 1 fixes).

- `make lint` clean (ruff + mypy strict + ruff format + logging audit; 231 source files; 548 files formatted).
- `make test` green: **4232 passed, 3 skipped** under `-n auto` (no coverage; +1 vs Phase 5 for the CLI exception-path `DebugLogSubscriber.close` regression guard).
- `make check` green: 4074 unit tests at 91.24% coverage; only pre-existing `personalscraper/scraper/tv_service.py: 819 non-blank lines` advisory warning.
- Module sizes within Phase 5 budgets:
  - `core/event_bus.py` 376/400
  - `core/app_context.py` 43/80
  - `pipeline_events.py` 101/150
  - `dispatch/events.py` 34/50
  - `core/circuit.py` 264/350
  - `indexer/events.py` 60/60
  - `trailers/events.py` 24/30
  - `events/__init__.py` 66/100
  - `subscribers/rich_console.py` 175/200
  - `subscribers/telegram.py` 117/200
  - `subscribers/debug_log.py` 29/40
  - `tests/fixtures/event_bus.py` 66/80
  - `tests/fixtures/event_samples.py` 147/150
  - `tests/architecture/test_app_context_boundary.py` 97/100

**Captured baselines (locked at feature start)**:

- `make test` baseline: **3738 passed, 3 skipped** at commit `55f758a` (feature activation).
- Current `make test`: **4232 passed, 3 skipped** (= **+494 new event-bus tests** vs feature baseline; well above the Phase 5.6 minimum of +175).
- Skip / xfail decorator count: **6** (matches SKIP_BASELINE locked at Pre-flight #9; no growth — Invariant 1 honored).

**Event registry (Phase 4 gate target reached)**: 13 production events.

```
CircuitBreakerClosed, CircuitBreakerHalfOpened, CircuitBreakerOpened,
DiskFullWarning, ItemDispatched, ItemProgressed, LibraryScanCompleted,
PipelineEnded, PipelineStarted, StepCompleted, StepErrored, StepStarted,
TrailerDownloaded
```

Eagerly imported by `personalscraper.events` so every class is registered
before any `event_from_envelope` call. The `Event` base does not register
itself (Phase 1.6 module-path filter; verified at gate time).

**TelegramSubscriber subscriptions**: 4 (PipelineEnded, StepErrored,
CircuitBreakerOpened, DiskFullWarning). Pinned by
`test_telegram_subscriber_has_four_subscriptions_after_phase4`.

## Next action — concrete resumption protocol

All five phases are complete. Run `/implement:feature-pr` (auto-chained by
`/implement:phase` after this gate commit): it runs the local quality gate,
pushes `feat/event-bus`, opens the PR, and polls CI to green. Then
`/implement:pr-review` runs the toolkit + fix-cycle loop (max 5 cycles) and
performs the squash merge.

## Push convention (user-imposed)

`git push` to `origin/feat/event-bus` after **each phase-gate commit**
(`chore(event-bus): phase N gate — …`). Do NOT push between sub-phases.
The pre-push hook runs ruff + format + logging audit + mypy + pytest before
allowing the push — keep all 5 green at every phase gate. (Mid-phase pushes
are allowed only as a backup measure when ending a session.) Phase 1 / 2 / 3
gates pushed at their respective milestones. Phase 4 gate (`8ff7014`) is
local-only at HEAD; the push happens at the Phase 5 feature-pr step per the
chained workflow above (`/implement:feature-pr` invokes `git push` as its
first action after the local quality gate).
