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
| 0   | Season-dir SSOT (widen-first) + VIDEO_EXTENSIONS                 | phase-00-season-ssot.md               | [x]    |
| 1   | Extract NFO helpers → nfo_utils                                  | phase-01-nfo-helpers.md               | [ ]    |
| 2   | Build \_item_stage + \_canonical; rewire scan_library (parallel) | phase-02-item-stage.md                | [ ]    |
| 3   | Single-creator cutover: dispatch + alias + delete scanner.py     | phase-03-single-creator-cutover.md    | [ ]    |
| 4   | ffprobe fold + insights/                                         | phase-04-ffprobe-insights.md          | [ ]    |
| 5   | verify/maintenance re-home + no-NFO + delete library/            | phase-05-verify-maintenance-delete.md | [ ]    |
| 6   | Feature PR + review (auto-invoked)                               | phase-06-feature-pr.md                | [ ]    |

## Design & plan review (2026-05-31, pre-implementation)

Design + plan were reviewed collaboratively before Phase 0 — more rigorous than the default flow.

**DESIGN review:**

- Interactive brainstorm → **8 decisions** resolved, each user-approved: single `media_item` creator; kind-deterministic canonical SSOT; NFO-less dirs indexed (folder-name fallback) + flagged (`item_issue`/`nfo_missing`) + proactive `doctor`/`audit` visibility; HDR/Atmos via the **existing** `media_stream` columns; `insights/` move-only; `maintenance/` = `disk_cleaner` + `rescraper`; `library-scan` visible re-pointed alias; `models.py` split by producer/consumer.
- **Adversarial self-review** (3 lenses: grounding / consistency / ACC executability) caught **2 real errors** + 8 grounding fixes:
  - HDR/Atmos columns (`hdr_format`/`is_atmos`) **already exist** (migration 004, populated by `enrich`) → decision reframed from "add columns" to "ensure enrich parity with the dropped ffprobe granularity".
  - Canonical `SEASON_DIR_RE` is **French-only** `^Saison (\d+)$`; three ad-hoc copies also match English `Season N` + `Specials` → **Phase 0 must widen before replacing** (silent-regression trap).
  - Also: `load_config` import path (`conf.loader`), `incremental.py:667` anchor, canonical trigger = manual `library-init-canonical` (not a scheduled job), completed `models.py` routing, existing `nfo_utils.py` path.
- Merged the pre-existing 619-line draft (committed in #27, v0.16→0.17, which carried the same HDR/regex errors) — best of both: its implementation-grade detail + the validated corrections.

**PLAN review:**

- 7 phases (0→6) generated, then verified for fidelity: strict 0→6 order; Phase 0 widen-first; Phase 2 parallel + characterization golden (no deletion); Phase 3 cutover (single creator, visible alias, delete `scanner.py`); Phase 4 no-new-columns + `hdr_format` parity; every phase opens with a Gate. All 16 ACC mapped.

**Outcome:** design + plan **approved**, ready for implementation. Invariants carried forward: DB end-state equality vs `library-scan` (Phase 2), 194-show + DEV#50 guards verbatim, residual-import grep = 0, `make check` per gate.

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to continue with Phase 1 (Extract NFO helpers → nfo_utils).
