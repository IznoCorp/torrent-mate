# Implementation Progress — tracker-wiring

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP5a — Wire the tracker registry into the composition root (minor)
**Version bump**: 0.23.0 → 0.24.0
**Branch**: feat/tracker-wiring
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/tracker-wiring/DESIGN.md
**Master plan**: docs/features/tracker-wiring/plan/INDEX.md

## Phases

| #   | Phase                                                                      | File                                     | Status |
| --- | -------------------------------------------------------------------------- | ---------------------------------------- | ------ |
| 1   | Error types — `TrackerError` + `TrackerConfigIssue` + `TrackerConfigError` | phase-01-error-types.md                  | [x]    |
| 2   | Factory — `build_tracker_registry` implementation                          | phase-02-factory-impl.md                 | [ ]    |
| 3a  | Factory unit tests — error cases + silent boot                             | phase-03a-factory-tests-error-cases.md   | [ ]    |
| 3b  | Factory unit tests — warning, severity split, happy path                   | phase-03b-factory-tests-warning-happy.md | [ ]    |
| 4   | `TrackerRegistry.close()` + regression guard                               | phase-04-registry-close.md               | [ ]    |
| 5a  | `AppContext.tracker_registry` field                                        | phase-05a-appcontext-field.md            | [ ]    |
| 5b  | Composition-root wiring + integration tests                                | phase-05b-composition-root-wiring.md     | [ ]    |
| 6   | ACCEPTANCE.md + `make check` gate                                          | phase-06-acceptance.md                   | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

Phase 1 done (`fa423a16`). Phase 2 (factory `build_tracker_registry`) next.
