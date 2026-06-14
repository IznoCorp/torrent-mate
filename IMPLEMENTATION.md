# Implementation Progress — ownership

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP6 — "do I already own this?" ownership predicate (port + indexer predicate + wiring) (minor)
**Version bump**: 0.29.0 → 0.30.0
**Branch**: feat/ownership
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/ownership/DESIGN.md
**Master plan**: docs/features/ownership/plan/INDEX.md

## Phases

| #   | Phase                                                        | File                   | Status |
| --- | ------------------------------------------------------------ | ---------------------- | ------ |
| 1   | Core port (OwnershipChecker Protocol + NullOwnershipChecker) | phase-01-port.md       | [x]    |
| 2   | Indexer predicate (is_owned SELECT-only + golden)            | phase-02-predicate.md  | [ ]    |
| 3   | Adapter + composition-root wiring + integration test         | phase-03-wiring.md     | [ ]    |
| 4   | Docs + ACCEPTANCE + gate                                     | phase-04-gate.md       | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

Run `/implement:phase` to start Phase 2 (indexer predicate).
