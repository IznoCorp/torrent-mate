# Implementation Progress — lib-fold

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Library / Indexer Consolidation (minor)
**Version bump**: 0.18.0 → 0.19.0
**Branch**: feat/lib-fold
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/lib-fold/DESIGN.md
**Master plan**: docs/features/lib-fold/plan/INDEX.md

## Phases

| #   | Phase                                                            | File                                  | Status |
| --- | ---------------------------------------------------------------- | ------------------------------------- | ------ |
| 0   | Season-dir SSOT (widen-first) + VIDEO_EXTENSIONS                 | phase-00-season-ssot.md               | [ ]    |
| 1   | Extract NFO helpers → nfo_utils                                  | phase-01-nfo-helpers.md               | [ ]    |
| 2   | Build \_item_stage + \_canonical; rewire scan_library (parallel) | phase-02-item-stage.md                | [ ]    |
| 3   | Single-creator cutover: dispatch + alias + delete scanner.py     | phase-03-single-creator-cutover.md    | [ ]    |
| 4   | ffprobe fold + insights/                                         | phase-04-ffprobe-insights.md          | [ ]    |
| 5   | verify/maintenance re-home + no-NFO + delete library/            | phase-05-verify-maintenance-delete.md | [ ]    |
| 6   | Feature PR + review (auto-invoked)                               | phase-06-feature-pr.md                | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 0.
