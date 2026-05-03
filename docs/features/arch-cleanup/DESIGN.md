# Architectural Consolidation — Design (`arch-cleanup`)

**Status**: Fully implemented (all 8 phases complete). Version bumped to 0.9.0. Merged on branch `refactor/arch-cleanup`.
**Codename**: `arch-cleanup`
**Version bump**: 0.8.0 → 0.9.0 (minor)
**Prepared on**: 2026-05-02
**Trigger**: static analysis showing 4 modules > 1200 LOC, implicit `StepReport` contract across heterogeneous steps, persistent legacy/new tension (library-scan vs library-index, media_index.json), documentation drift (8 vs 9 pipeline steps).

## 1. Goals & Non-goals

### 1.1 Goals

- **Cognitive load**: every module under `personalscraper/` ≤ 1000 LOC (target ≤ 700) for the four current god modules.
- **Pipeline interface**: formalise step orchestration through a `PipelineStep` Protocol so `pipeline.py` no longer depends on the concrete `run_*` signatures of each domain.
- **Report typing (Tier A)**: make the `StepReport` contract explicit per step via typed `*Details` payloads documented in a single registry. Generic `StepReport[TDetails]` is deferred.
- **Legacy retirement**: deprecate (or remove if no consumers) the dual mental models that have accumulated: `library-scan`, `media_index.json`, v1 config read path, deprecated CLI flags.
- **Documentation realignment**: close the gap between code reality (9 pipeline steps, current trailers/verify semantics, indexer modes) and inline comments / `docs/reference/`.
- **Complexity guardrail**: introduce a soft-warning module-size check, advisory in 0.9.0, hard block in 0.10.0.

### 1.2 Non-goals (explicit deferrals)

- No new pipeline features, no new indexer modes, no new scraper providers, no new trailer sources.
- No cross-step consolidation (trailers stays its own step; process keeps its 3 sub-steps).
- No Generic `StepReport[TDetails]` migration removing the untyped `details: list[str]` field — Tier B, deferred to next minor.
- No public API rename for stable surfaces (`personalscraper run`, `personalscraper ingest`, etc.).
- No performance work unless a free side-effect of decomposition.
- No removal of currently-undeprecated paths in this minor bump.

### 1.3 Success criteria

| Metric                                   | Target                                                                                       |
| ---------------------------------------- | -------------------------------------------------------------------------------------------- |
| `cli.py` LOC                             | ≤ 400 (Typer wiring + global options + version + exception shell only)                       |
| `scraper/scraper.py` LOC                 | ≤ 400 (orchestrator only); services each ≤ 700                                               |
| `indexer/scanner/_modes.py`              | replaced by `_modes/` package, each file ≤ 700                                               |
| `indexer/cli.py` LOC                     | ≤ 400 (Typer wiring); `indexer/commands/*` files each ≤ 700                                  |
| `personalscraper/commands/`              | hosts pipeline, library, config, info, diagnose command implementations                      |
| `PipelineStep` Protocol                  | declared; all 9 steps adapted; `step_overrides` still functional (zero test changes)         |
| `personalscraper/reports/`               | typed `*Details` dataclasses for each of the 9 steps; `STEP_REPORT_CONTRACT` registry exists |
| `media_index.json`                       | zero references outside a single compat shim, OR shim removed if grep finds zero consumers   |
| Pipeline step count strings in code/docs | "9" everywhere; zero remaining "8 steps" mentions                                            |
| `scripts/check-module-size.py`           | exists, hooked into `make check`, exit code 0 with warnings (advisory)                       |
| Test suite                               | green at every phase; coverage diff ≥ 0 per extraction                                       |

## 2. Per-axis approach

### 2.1 Axis 1 — God-module decomposition

Decompose by responsibility, not by line count. Each split must be **behaviour-preserving**: extract methods, move imports, no logic edits in the same commit as the move.

#### `personalscraper/cli.py` (1648 LOC) → `personalscraper/commands/`

The file currently contains: Typer app + global options + 50+ command bodies + helper functions + presentation logic + legacy compatibility branches.

| Extraction target          | Contents                                                                                                                                                                              |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `commands/pipeline.py`     | `run`, `ingest`, `sort`, `process`, `clean`, `scrape`, `cleanup`, `enforce`, `verify`, `trailers`, `dispatch` (each as a Typer command function delegating to its domain entry point) |
| `commands/library.py`      | `library-scan` (legacy, deprecation warning), `library-index`, `library-search`, `library-clean`, `library-report`, `library-analyze`                                                 |
| `commands/config.py`       | `init-config`, `validate-config`, `migrate-config`, `show-config`                                                                                                                     |
| `commands/info.py`         | `info` (paths/disks/version available via CLI global options)                                                                                                                         |
| ~~`commands/diagnose.py`~~ | Skipped — no `diagnose` (or doctor-style) commands existed in `cli.py` at extraction time                                                                                             |
| `cli.py`                   | Typer app instance + global options + exception handler shell + sub-app mounting                                                                                                      |

`commands/init_config.py` (already present) is folded into `commands/config.py` or kept as a delegate target — decided during phase 2 based on actual structure.

#### `personalscraper/scraper/scraper.py` (2159 LOC) → service split

| Extraction target               | Contents                                                                                       |
| ------------------------------- | ---------------------------------------------------------------------------------------------- |
| `scraper/orchestrator.py`       | top-level `run_scrape` entry, batch loop, dispatch to movie/tv services, `StepReport` assembly |
| `scraper/movie_service.py`      | TMDB lookup, candidate selection, NFO emission for movies                                      |
| `scraper/tv_service.py`         | TVDB lookup, season/episode resolution, show-level NFO, episode NFO                            |
| `scraper/rename_service.py`     | filesystem rename + merge logic, conflict resolution                                           |
| `scraper/existing_validator.py` | re-validation of already-scraped folders (existing-NFO branch)                                 |
| `scraper/classifier.py`         | media-type classification (movie / tv / standup / theater / etc.)                              |

#### `personalscraper/indexer/scanner/_modes.py` (1900 LOC) → per-mode files

| Extraction target       | Contents                                         |
| ----------------------- | ------------------------------------------------ |
| `_modes/__init__.py`    | mode registry, dispatcher, shared mode utilities |
| `_modes/full.py`        | full-scan logic                                  |
| `_modes/quick.py`       | quick scan (partial / surface-level check)       |
| `_modes/incremental.py` | incremental / drift-driven scan                  |
| `_modes/enrich.py`      | enrich scan (fill gaps in existing metadata)     |
| `_modes/verify.py`      | verify-scan (integrity check)                    |
| `_modes/backfill.py`    | backfill scan (retroactive data population)      |

If the file contains a 5th mode (e.g., spotlight-driven), it gets its own module. Inventory at start of phase 4.

#### `personalscraper/indexer/cli.py` (1389 LOC) → `indexer/commands/`

| Extraction target              | Contents                                       |
| ------------------------------ | ---------------------------------------------- |
| `indexer/commands/scan.py`     | `scan`, `scan-disk`, mode flags                |
| `indexer/commands/query.py`    | `search`, `list`, `stats`, `info`              |
| `indexer/commands/repair.py`   | `repair`, `verify-integrity`, `rebuild-merkle` |
| `indexer/commands/diagnose.py` | `diagnose`, `config_migrate_category_command`  |
| `indexer/cli.py`               | Typer sub-app + wiring shell                   |

### 2.2 Axis 2 — `PipelineStep` Protocol + `StepContext`

```python
# personalscraper/pipeline_protocol.py
from collections.abc import MutableMapping
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class PipelineStep(Protocol):
    name: str
    def __call__(self, ctx: StepContext) -> "StepReport | tuple[StepReport, Any]": ...
```

```python
# personalscraper/pipeline_protocol.py
@dataclass(frozen=True)
class StepContext:
    config: Config
    settings: Settings
    dry_run: bool
    interactive: bool
    verbose: bool
    console: Console
    upstream: Mapping[str, StepReport]      # previous steps' reports for dependency resolution
    extras: MutableMapping[str, Any]        # step artifacts (e.g., verify -> dispatchable list)
```

**Wrapping strategy**: each existing `run_*(...)` function gets a thin Step class:

```python
class IngestStep:
    name = "ingest"
    def __call__(self, ctx: StepContext) -> "StepReport | tuple[StepReport, Any]":
        return run_ingest(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)
```

`Pipeline.__init__` accepts an optional `steps: Mapping[str, PipelineStep]`. Existing `step_overrides: Mapping[str, Callable[..., Any]]` is **kept** as a compatibility parameter; internally it wraps callables into anonymous `PipelineStep` instances. **Tests that pass `step_overrides=` continue to work unchanged.**

The 9 default steps live in `personalscraper/pipeline_steps.py` as a registry:

```python
DEFAULT_STEPS: dict[str, PipelineStep] = {
    "ingest": IngestStep(), "sort": SortStep(), "clean": CleanStep(),
    "scrape": ScrapeStep(), "cleanup": CleanupStep(), "enforce": EnforceStep(),
    "verify": VerifyStep(), "trailers": TrailersStep(), "dispatch": DispatchStep(),
}
```

`pipeline.py:run()` becomes a loop over the registry with per-step gates (the existing critical/non-critical split), losing none of its current control-flow logic.

### 2.3 Axis 3 — `StepReport` typing (Tier A)

Two changes, both additive:

**(a) Typed `*Details` payloads** — one dataclass per step under `personalscraper/reports/`:

```python
# personalscraper/reports/trailers.py
@dataclass
class TrailersDetails:
    downloaded: list[str]
    bot_detected: list[str]
    skipped_existing: list[str]
    failed: list[tuple[str, str]]
```

Each step's `*Details` payload is auto-created (empty) by `Pipeline._with_details_payload()` after execution. Domain modules do not populate typed payloads yet (deferred to Tier B).

**(b) Contract registry**:

```python
# personalscraper/reports/__init__.py
STEP_REPORT_CONTRACT: dict[str, type] = {
    "ingest": IngestDetails, "sort": SortDetails, "clean": CleanDetails,
    "scrape": ScrapeDetails, "cleanup": CleanupDetails, "enforce": EnforceDetails,
    "verify": VerifyDetails, "trailers": TrailersDetails, "dispatch": DispatchDetails,
}
```

**(c) `StepReport.details_payload`** added as `Any | None = None` — additive, default `None`, no consumer break.

**Tier B deferred**: Generic `StepReport[TDetails]` parameterisation (and removal of the untyped `details: list[str]`) waits until all consumers (HTML report, CLI display, notifier) read from the typed payload exclusively. Out of scope here.

### 2.4 Axis 4 — Legacy cleanup

Pre-1.0 minor-bump policy: **deprecate now, remove next minor**, except where grep proves zero consumers.

| Item                          | 0.9.0 action                                                                                                                                                 | 0.10.0 plan                 |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------- |
| `library-scan` command        | Emit `DeprecationWarning` (rich console + `warnings`); document in `docs/reference/commands.md`; keep code-path                                              | Remove command + its module |
| `media_index.json` write/read | Grep all consumers (production + tests + scripts + launchd plists). If zero outside compat shim → **remove now**. Otherwise: deprecation log line + doc note | Remove shim                 |
| v1 config read path           | Keep, add `DeprecationWarning` on every load                                                                                                                 | Remove; require v2          |
| Already-deprecated CLI flags  | Audit, normalise warnings, document removal target                                                                                                           | Remove                      |
| Currently-undeprecated paths  | Untouched                                                                                                                                                    | Untouched                   |

A grep audit at the start of phase 8 produces the actual removal list. Anything found to have a real consumer (e.g., Home Assistant cron, launchd plist, Makefile target) is downgraded from `remove` to `deprecate`.

### 2.5 Axis 5 — Documentation realignment

| Doc                                           | Update                                                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/models.py:140` (and similar) | `# 9 steps` instead of `# 8 steps`                                                                                  |
| `personalscraper/pipeline.py` docstring       | Confirm "9 StepReports" everywhere; describe trailers placement                                                     |
| `docs/reference/architecture.md`              | Refresh module map post-decomposition (commands/, reports/, scraper services, indexer modes)                        |
| `docs/reference/pipeline-internals.md`        | Add `PipelineStep` Protocol section; `StepContext`; step registry                                                   |
| `docs/reference/trailers.md`                  | Document placement (before dispatch, after verify), non-blocking semantics, skip flags, `continue_on_trailer_error` |
| `docs/reference/indexer.md`                   | Reflect current scanner modes inventory                                                                             |
| `docs/reference/commands.md`                  | Document deprecated commands, deprecation-to-removal schedule                                                       |
| `CLAUDE.md`                                   | Add module-size rule (≤ 800 LOC advisory, ≤ 1000 LOC hard ceiling next minor)                                       |

Audit method (phase 1): grep `8 step`, `eight steps`, `8 StepReport`, `library_scan` in code+docs, then per-doc review.

### 2.6 Axis 6 — Complexity guardrail

`scripts/check-module-size.py`:

- Walks `personalscraper/` (excludes `__init__.py`, `tests/`, generated migration files under `indexer/migrations/`).
- Counts non-blank, non-comment lines via Python tokenize (or simple `wc -l` if simpler — finalise during phase 1).
- WARN ≥ 800 LOC, REPORT ≥ 1000 LOC.
- 0.9.0: exit code 0 always (advisory).
- 0.10.0: exit code 1 on REPORT level (hard block in `make check`).

Wired into `Makefile`'s `check` target after `pyright` / `ruff`. Output is plain text + a colour-aware summary if running in a TTY.

## 3. Migration / rollout strategy

Each phase is an **atomic, behaviour-preserving** change with these guarantees:

1. `make check && make test` green before and after.
2. Coverage diff ≥ 0 per phase (no test loss).
3. Decomposition phases use `git mv`-equivalent extraction: move text, rewrite imports, no logic edits.
4. Each phase is independently revertable (one phase = one PR-sized chunk; sub-phases when needed).
5. The `step_overrides` parameter and signature stay stable until at least 0.10.0.

Phase ordering is chosen so that the riskiest (scraper service split, PipelineStep Protocol) come **after** the foundation and CLI passes — by then the test suite is exercising the moved code with its new boundaries.

## 4. Risk register

| #   | Risk                                                                                                 | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                                                           |
| --- | ---------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| R1  | Hidden coupling exposed by split (private state shared via module globals)                           | Medium     | High   | `ruff F401`, cycle detection, integration tests on every phase, no module deletes until consumer re-points                                                                                                                                                                                                                           |
| R2  | Test coverage drops on extracted code (tests still target old paths)                                 | Medium     | Medium | Coverage report before/after each phase; tests follow imports in same commit as the move                                                                                                                                                                                                                                             |
| R3  | `step_overrides` callable contract drift (new Protocol path diverges)                                | Low        | High   | Compat shim is a thin adapter; tests for both paths in phase 6                                                                                                                                                                                                                                                                       |
| R4  | Documentation drift returns post-merge                                                               | High       | Low    | Add doc anchors flagged by complexity script (deferred); add CONTRIBUTING note                                                                                                                                                                                                                                                       |
| R5  | Removed legacy still consumed by an external runtime (launchd, Home Assistant cron, Makefile target) | Medium     | High   | Grep audit at phase 8 covers `~/Library/LaunchAgents/`, `Makefile`, `README.md`, `CLAUDE.md`, `scripts/`, ecosystem.config.js; downgrade `remove` → `deprecate` on hit                                                                                                                                                               |
| R6  | Tier-A details payload bloat (per-step dataclass churn during phase 7)                               | Low        | Low    | Optional payload (`None` default); incremental adoption — a step skipping the typed payload is still valid                                                                                                                                                                                                                           |
| R7  | `pipeline.run` rewrite to use the registry introduces a control-flow regression                      | Medium     | High   | Phase 6 keeps the legacy `step_overrides=Mapping[str, Callable]` parameter accepted by wrapping callables into anonymous PipelineStep instances at runtime (compat shim, not a feature flag). Tests passing `step_overrides=` continue to work unchanged; integration tests assert per-step ordering. The shim is removed in 0.10.0. |
| R8  | `make test` runtime increases significantly                                                          | Low        | Medium | Run `make test --duration=10` before/after each phase, alert on >10% growth                                                                                                                                                                                                                                                          |

## 5. Phasing hints (writing-plans will refine into actual phases)

Suggested 8 phases, each landing a single PR-sized milestone:

| #   | Phase                                                              | Output                                                                                                                                                                                                            |
| --- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Foundation**                                                     | `scripts/check-module-size.py` + `make check` wiring; doc audit pass (step count, trailers, verify --fix); `personalscraper/reports/__init__.py` stub; `personalscraper/pipeline_protocol.py` declared but unused |
| 2   | **CLI decomposition**                                              | `cli.py` 1648 → ≤ 400 LOC; `commands/{pipeline,library,config,info,diagnose}.py` populated                                                                                                                        |
| 3   | **Indexer CLI decomposition**                                      | `indexer/cli.py` 1389 → ≤ 400 LOC; `indexer/commands/{scan,query,repair,diagnose}.py` populated                                                                                                                   |
| 4   | **Indexer scanner modes split**                                    | `_modes.py` 1900 → `_modes/` package                                                                                                                                                                              |
| 5   | **Scraper decomposition**                                          | `scraper/scraper.py` 2159 → orchestrator + 5 services                                                                                                                                                             |
| 6   | **PipelineStep Protocol + StepContext**                            | Protocol declared; 9 step wrappers; `Pipeline.run()` switched to registry; `step_overrides` shim                                                                                                                  |
| 7   | **StepReport Tier A**                                              | Per-step typed details payloads; `STEP_REPORT_CONTRACT` registry; `details_payload` field                                                                                                                         |
| 8   | **Legacy deprecation pass + final doc realignment + version bump** | Grep audit; deprecation warnings; doc final pass; `VERSION` 0.8.0 → 0.9.0                                                                                                                                         |

writing-plans will rebalance and refine sub-phase boundaries.

## 6. Out-of-scope / explicit deferrals (recap for next-minor backlog)

- **0.10.0 candidates**: hard block on size guardrail; remove deprecated `library-scan`, `media_index.json` shim, v1 config read path, deprecated CLI flags; Generic `StepReport[TDetails]` Tier B migration; remove untyped `details: list[str]` from `StepReport`.
- **Beyond 0.10.0**: cross-step consolidation evaluation (e.g., `enforce` vs `verify` overlap); indexer mode unification; doc-anchor automated checks.
