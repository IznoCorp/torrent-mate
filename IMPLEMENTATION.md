# Implementation Progress — arch-cleanup

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `arch-cleanup`
**Feature title**: Architectural Consolidation
**Type**: refactor (minor SemVer bump)
**Bump**: 0.8.0 → 0.9.0
**Branch**: refactor/arch-cleanup
**Design**: docs/features/arch-cleanup/DESIGN.md
**Master plan**: docs/features/arch-cleanup/plan/INDEX.md
**PR**: _(to be created)_
**Merge strategy**: squash (manual)

## Phases

| #   | Phase                                       | File                                                                                                               | Status |
| --- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------ |
| 1   | Foundation                                  | [phase-01-foundation.md](docs/features/arch-cleanup/plan/phase-01-foundation.md)                                   | [x]    |
| 2   | CLI decomposition                           | [phase-02-cli-decompose.md](docs/features/arch-cleanup/plan/phase-02-cli-decompose.md)                             | [x]    |
| 3   | Indexer CLI decomposition                   | [phase-03-indexer-cli-decompose.md](docs/features/arch-cleanup/plan/phase-03-indexer-cli-decompose.md)             | [x]    |
| 4   | Indexer scanner modes split                 | [phase-04-indexer-scanner-modes-split.md](docs/features/arch-cleanup/plan/phase-04-indexer-scanner-modes-split.md) | [x]    |
| 5   | Scraper decomposition                       | [phase-05-scraper-decompose.md](docs/features/arch-cleanup/plan/phase-05-scraper-decompose.md)                     | [x]    |
| 6   | PipelineStep Protocol + StepContext         | [phase-06-pipeline-step-protocol.md](docs/features/arch-cleanup/plan/phase-06-pipeline-step-protocol.md)           | [x]    |
| 7   | StepReport Tier A typed details             | [phase-07-stepreport-tier-a.md](docs/features/arch-cleanup/plan/phase-07-stepreport-tier-a.md)                     | [x]    |
| 8   | Legacy deprecation + doc realignment + bump | [phase-08-legacy-deprecation-and-bump.md](docs/features/arch-cleanup/plan/phase-08-legacy-deprecation-and-bump.md) | [x]    |

## Quality gate (every commit)

```bash
make check
python3 scripts/check-module-size.py
```

A commit is acceptable when `make lint test` exits 0, the size script exits 0 (advisory in 0.9.0), no new file > 1000 LOC, and coverage delta ≥ 0.

## Conventional Commits scope

All commits use scope `arch-cleanup`:

- `feat(arch-cleanup): ...`
- `refactor(arch-cleanup): ...`
- `docs(arch-cleanup): ...`
- `test(arch-cleanup): ...`
- `chore(arch-cleanup): ...`

Phase milestone commits:

- `chore(arch-cleanup): phase N gate — <phase summary>`

## Sub-phase → SHA mapping

| Phase | Sub-phase                                     | SHA       | Date       |
| ----- | --------------------------------------------- | --------- | ---------- |
| —     | Design + plan introduction                    | `ecca23a` | 2026-05-02 |
| 1     | Module-size advisory script                   | `0ea43c9` | 2026-05-02 |
| 1     | `make check` target                           | `3d34b06` | 2026-05-02 |
| 1     | Pipeline step count doc audit (8 → 9)         | `1b25aa1` | 2026-05-02 |
| 1     | `pipeline_protocol` stub (phase 6 prep)       | `62854d5` | 2026-05-02 |
| 1     | `reports/` package stub (phase 7 prep)        | `3f654e4` | 2026-05-02 |
| 1     | Module-size guardrail documentation           | `95f53c9` | 2026-05-02 |
| 1     | Phase 1 gate — foundation complete            | `bb099bb` | 2026-05-02 |
| 2     | Split top-level CLI into command modules      | `49676b9` | 2026-05-02 |
| 3     | Split indexer CLI into command modules        | `0519104` | 2026-05-02 |
| 4     | Inventory scanner modes (pre-split)           | `aada461` | 2026-05-02 |
| 4     | Split scanner modes into `_modes/` package    | `1065048` | 2026-05-02 |
| 5     | Inventory scraper symbols (pre-split)         | `cc2eab5` | 2026-05-02 |
| 5     | Split scraper into orchestrator + services    | `5135837` | 2026-05-03 |
| 6     | Pipeline step protocol registry               | `b2c9f9a` | 2026-05-03 |
| 7     | Typed step report payload contracts           | `a15a467` | 2026-05-03 |
| 8     | Legacy consumer audit results                 | `9afedd0` | 2026-05-03 |
| 8     | Deprecate legacy paths + VERSION bump 0.9.0   | `46c1b1d` | 2026-05-03 |
| 8     | Phase 8 gate — legacy deprecation + bump done | `95839d2` | 2026-05-03 |

## Open issues / deferrals

- **`personalscraper/conf/models.py` is 1187 LOC**, above the 1000-line hard ceiling defined by `scripts/check-module-size.py`. Acceptable in 0.9.0 (size script is advisory this version) but must be split before 0.10.0 promotes the guardrail to a hard block. Tracked for the next feature.
- Three `[WARN]` modules within range of the 1000 ceiling: `commands/library.py` (936), `dispatch/dispatcher.py` (899), `indexer/outbox.py` (898). Watch for growth.

## References

- DESIGN.md: docs/features/arch-cleanup/DESIGN.md
- ROADMAP.md entry: removed (now active feature, no longer "Future Ideas")
- Previous feature archive: docs/archive/features/media-indexer/

## Next action

All phases complete — push branch and run `/implement:feature-pr` (or open PR manually).
