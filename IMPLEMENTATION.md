# Implementation Progress — multi-filesystem

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Multi-Filesystem Support (FilesystemCapability Layer) (minor)
**Version bump**: 0.17.0 → 0.18.0
**Branch**: feat/multi-filesystem
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/multi-filesystem/DESIGN.md
**Master plan**: docs/features/multi-filesystem/plan/INDEX.md

## Phases

| #   | Phase                                                       | File                            | Status |
| --- | ----------------------------------------------------------- | ------------------------------- | ------ |
| 1   | Consolidate 3 mount-parsers into one cached FsProbe         | phase-01-fs-probe.md            | [ ]    |
| 2   | Define the FilesystemCapability strategy table              | phase-02-fs-capability.md       | [ ]    |
| 3   | Make \_transfer rsync/rsync_merge consume the capability    | phase-03-transfer-capability.md | [ ]    |
| 4   | Optional DiskConfig.fs_type override + plumb capabilities   | phase-04-diskconfig-override.md | [ ]    |
| 5   | Make indexer tier-1 drift FS-aware (higher risk, deferable) | phase-05-drift-fs-aware.md      | [ ]    |
| 6   | Multi-FS test harness + SH-16 ACCEPTANCE + docs             | phase-06-test-harness-docs.md   | [ ]    |
| 7   | Feature PR + review                                         | phase-07-feature-pr.md          | [ ]    |

## Review cycles

_(filled by implement:pr-review)_

## Next action

Run `/implement:phase` to start Phase 1 (Consolidate 3 mount-parsers into one cached FsProbe).
