# Implementation Progress — seed-pure

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Seed Safety O1: seed-pure tag + pipeline skip (+ manual tagger) (minor)
**Version bump**: 0.32.0 → 0.33.0
**Branch**: feat/seed-pure
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/201
**Design**: docs/features/seed-pure/DESIGN.md
**Master plan**: docs/features/seed-pure/plan/INDEX.md

## Phases

| #   | Phase                         | File                             | Status |
| --- | ----------------------------- | -------------------------------- | ------ |
| 1   | Tag vocab + tagger capability | phase-01-tag-vocab-tagger.md     | [x]    |
| 2   | `seed` CLI group              | phase-02-seed-cli.md             | [x]    |
| 3   | Ingest skip (always-on)       | phase-03-ingest-skip.md          | [x]    |
| 4   | Opt-in sort-side guard        | phase-04-optional-guard.md       | [x]    |
| 5   | Docs + ACCEPTANCE + gate      | phase-05-docs-acceptance-gate.md | [x]    |
| 6   | PR fixes cycle 1              | phase-06-pr-fixes-cycle-1.md     | [ ]    |

## Review cycles

### Cycle 1

- Toolkit: 5 lenses on PR #201 (CI green) — code-reviewer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer, comment-analyzer. (3 hit a transient rate-limit on the first pass; re-dispatched.)
- **Convergent MAJOR finding (4 lenses):** Transmission tagger silently corrupts on **category-less torrents** (the feature's headline use case). `seed mark` on a Transmission torrent with `labels=[]` writes `labels=["seed-pure"]`; `_torrent_item` reads `labels[0]` as the **category** → `tags=[]` → the ingest skip (`SEED_PURE in tags`) NEVER fires → the seed-only torrent is ingested anyway. `add()` already rejects this ambiguity; the tagger had no guard + no test.
- Retained: **F-A** (MAJOR — no-category sentinel fix + regression tests) · **F-B** (MEDIUM — `ProcessCleanConfig.verify_seed_pure` is a flag that lies → validator rejects `True`) · **F-C** (type `run_sort` against `TorrentLister`, drop `type: ignore`) · **F-D** (`seed list` defensive `getattr`) · **F-E** (`run_sort` docstring: standalone-sort guard is pipeline-only) · **F-F** (sort-guard log `error_type`+consequence).
- Ignored: namespace-collision doc note, seed-list completed-only note, list-column assertion (cosmetic).
- Decision: **Case B**. Fix phase 6 created (6.1 Transmission no-category fix, 6.2 reserved-flag validator + typing/consistency/docs).

## Next action

Execute phase 6 (`/implement:phase`), then re-poll CI + cycle-2 re-review.
