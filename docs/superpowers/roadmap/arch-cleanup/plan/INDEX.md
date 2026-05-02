# Architectural Consolidation — Implementation Plan (`arch-cleanup`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific lifecycle:** This plan is consumed by `/implement:phase` (which dispatches `/implement:sub-phase` per sub-phase and verifies via `/implement:check`). Each sub-phase = one commit minimum.

**Goal:** Consolidate the codebase: shrink 4 god modules, formalise pipeline orchestration via a `PipelineStep` Protocol, type the `StepReport` payload per step (Tier A), retire legacy compatibility paths, realign documentation with code reality, add a soft module-size guardrail. Behaviour-preserving throughout.

**Architecture:** 8 sequential phases, each behaviour-preserving and atomic. Decomposition phases (2-5) use git-mv-equivalent extraction with import rewrites and zero logic edits in the move commit. New-code phases (1, 6, 7) follow strict TDD. Phase 8 audits and removes/deprecates legacy paths and bumps `VERSION` to 0.9.0.

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, structlog, rich, SQLite (indexer), pytest. No new runtime dependencies.

**Version bump:** 0.8.0 → 0.9.0 (minor).

**Scope locked.** See `../specs/DESIGN.md` for goals/non-goals, success criteria, risk register, deferrals.

---

## Phases

| #   | Phase                                                                                                   | Codename                               | Estimated commits | Risk                               | Reverts cleanly?                         |
| --- | ------------------------------------------------------------------------------------------------------- | -------------------------------------- | ----------------- | ---------------------------------- | ---------------------------------------- |
| 1   | Foundation: complexity script, `make check`, doc audit pass, stub `reports/` and `pipeline_protocol.py` | `phase-01-foundation`                  | 4-6               | Low                                | Yes                                      |
| 2   | CLI decomposition: `cli.py` 1648 LOC → `commands/{pipeline,library,config,info,diagnose}.py`            | `phase-02-cli-decompose`               | 6-8               | Medium                             | Yes (revert per-commit)                  |
| 3   | Indexer CLI decomposition: `indexer/cli.py` 1389 LOC → `indexer/commands/`                              | `phase-03-indexer-cli-decompose`       | 4-6               | Medium                             | Yes                                      |
| 4   | Indexer scanner modes split: `indexer/scanner/_modes.py` 1900 LOC → `_modes/` package                   | `phase-04-indexer-scanner-modes-split` | 5-7               | High (touches scan execution path) | Yes (each mode independently revertable) |
| 5   | Scraper decomposition: `scraper/scraper.py` 2159 LOC → orchestrator + 5 services                        | `phase-05-scraper-decompose`           | 6-8               | High (touches scrape path)         | Yes                                      |
| 6   | `PipelineStep` Protocol + `StepContext` + step wrappers; `step_overrides` shim                          | `phase-06-pipeline-step-protocol`      | 4-6               | Medium                             | Yes                                      |
| 7   | `StepReport` Tier A: per-step typed `*Details` payloads + `STEP_REPORT_CONTRACT` registry               | `phase-07-stepreport-tier-a`           | 5-7               | Low                                | Yes                                      |
| 8   | Legacy deprecation pass + final doc realignment + version bump to 0.9.0                                 | `phase-08-legacy-deprecation-and-bump` | 3-5               | Medium                             | Yes                                      |

**Total estimate**: 37-53 commits across 8 phases. Subagent-driven execution recommended (one sub-phase = one Sonnet dispatch = one commit).

## Quality gate (every commit)

```bash
make lint test
# and once phase 1 lands check-module-size:
python3 scripts/check-module-size.py
```

A commit is acceptable when:

- `make lint test` exit code 0
- `python3 scripts/check-module-size.py` exit code 0 (advisory warnings are OK in 0.9.0)
- No new file > 1000 LOC (hard ceiling, this plan)
- Coverage delta ≥ 0 vs. previous commit (`pytest --cov` snapshot)

## Conventional Commits scope

All commits in this feature use scope `arch-cleanup`:

```
refactor(arch-cleanup): split cli.py into commands/pipeline.py
docs(arch-cleanup): correct pipeline step count to 9
test(arch-cleanup): add PipelineStep Protocol contract tests
chore(arch-cleanup): bump VERSION to 0.9.0
```

Phase milestone commits (created by `/implement:phase`):

```
chore(arch-cleanup): phase 2 gate — CLI decomposition complete
```

## Per-phase files

- [`phase-01-foundation.md`](phase-01-foundation.md)
- [`phase-02-cli-decompose.md`](phase-02-cli-decompose.md)
- [`phase-03-indexer-cli-decompose.md`](phase-03-indexer-cli-decompose.md)
- [`phase-04-indexer-scanner-modes-split.md`](phase-04-indexer-scanner-modes-split.md)
- [`phase-05-scraper-decompose.md`](phase-05-scraper-decompose.md)
- [`phase-06-pipeline-step-protocol.md`](phase-06-pipeline-step-protocol.md)
- [`phase-07-stepreport-tier-a.md`](phase-07-stepreport-tier-a.md)
- [`phase-08-legacy-deprecation-and-bump.md`](phase-08-legacy-deprecation-and-bump.md)

## Phase dependencies

```
1 (foundation) → 2 (cli) → 3 (indexer cli) → 4 (modes) → 5 (scraper) → 6 (protocol) → 7 (reports) → 8 (legacy + bump)
```

Strict order: phase 6 (Protocol) needs the new `commands/` layout from phase 2 to wire entry points cleanly; phase 7 (typed reports) needs the Protocol from phase 6; phase 8 needs everything to audit cleanly. Phases 3, 4, 5 are independent of each other in principle but ordered by risk (lower-risk first to build confidence).
