# Design — Library / Indexer Consolidation (`lib-fold`)

> **Status**: Design (pre-implementation) — brainstormed + adversarially validated against HEAD; pending `/implement:plan`.
> **Date**: 2026-05-31 (merges the 2026-05-28 draft authored in #27 with the 2026-05-31 brainstorm decisions + HEAD-grounded corrections).
> **Roadmap item**: P1 — Library / Indexer Consolidation (`ROADMAP.md`).
> **Version bump target**: **0.18.0 → 0.19.0** (minor — new internal scan stage + package moves; no public CLI removed).
> **Branch**: `feat/lib-fold` · **Merge**: squash · Pre-1.0, single mono-user instance, not in production — **no migration scripts** (DB/NFO/config evolve in place; re-index by re-running `library-index`).
> **Source analysis**: `docs/analysis/01-library-indexer-consolidation.md` (read in full). This DESIGN supersedes its phasing with implementation-grade detail, **re-grounded against HEAD `c85410fe` / v0.18.0** and validated by a 3-lens adversarial sweep (corrections folded in — see §3 notes).

---

## 1. Purpose & Motivation

The `personalscraper/library/` package (8 modules, **≈4888 total LOC**) grew as a parallel
media-introspection subsystem alongside the canonical `indexer/`. Over time the two accumulated genuine
duplication and, worse, **two uncoordinated writers of the `media_item` table** with different row
richness. The result is an operator workflow that depends on an undocumented run-order (`library-scan`
to create rich rows, _then_ `library-index` to populate files/streams) and a latent data-quality cliff:
when the dispatch path auto-rebuilds the DB on an empty database it produces minimal rows
(`canonical_provider=None`, no seasons) that silently degrade everything downstream.

This feature folds the surviving, load-bearing parts of `library/` into the indexer (the canonical
subsystem), unifies duplicated concepts onto single sources of truth, re-homes the read-only/maintenance
pieces into purpose-built packages, and deletes the `library/` package. End state: **one media model,
one scan command, one canonical-provider extractor, one season-dir regex.**

Three non-negotiable drivers (co-equal — nothing sacrificed):

- **Correctness** — eliminate the two structurally-divergent risks: the two `media_item` creators, and
  the two `canonical_provider` derivations that can contradict each other (the 194-show regression class).
- **Cleanliness** — one SSOT per responsibility; `library/` no longer exists; residual-import grep = 0;
  no module breaches the 1000-LOC hard ceiling.
- **Enablement** — a clean read-only `insights/` layer over the indexer DB, directly callable by the
  future Web UI (P2 roadmap).

**Premise correction (verified against HEAD).** The ROADMAP's original central claim — that
`library/scanner.py` "duplicates the indexer walk" — is **false**. `scan_library()`
(`library/scanner.py:902`) walks only at media-directory granularity, then _delegates_ the recursive
file walk to `indexer.scanner.scan(mode=ScanMode.full)`. The real work is reconciling the two
`media_item` writers and the duplicated concepts, not removing a duplicate walk.

---

## 2. Goals / Non-goals

### Goals

1. Fold the rich `media_item`/`season`/`episode` creation in `library/scanner.py:691`
   (`_item_repo.upsert`) into a **unified indexer scan stage** invoked by `ScanMode.full`, so
   `library-index --mode full` is self-sufficient (no prior `library-scan` step required).
2. Reconcile the **second `media_item` writer** — `dispatch/media_index.py` (`upsert` at `:406`, reached
   via `MediaIndex.rebuild()`, minimal rows, `canonical_provider=None`) — to the same shared builder, so
   there is **one creator** and no third write pattern (decision #4).
3. Unify `canonical_provider` extraction: `_normalize_canonical_provider` (`library/scanner.py:69`) and
   `init_canonical_from_nfo` (`backfill_ids_canonical.py`) collapse into **one SSOT** on the
   **kind-deterministic rule** (decision #5), carrying the 194-show regression guard forward verbatim.
4. Drop the redundant library ffprobe re-scan (`analyzer.analyze_library`); ensure the surviving
   pymediainfo `enrich` path populates the **existing** `media_stream.hdr_format`/`is_atmos` columns at
   parity (decision #8) — **no migration script**.
5. Collapse the **five divergent season-dir regexes** onto `naming_patterns.SEASON_DIR_RE` — **after
   first widening it** to the French/English/Specials union (decision below; §3.4).
6. Re-home read-only modules (`reporter.py`, `recommender.py`, `analyze`/`analyze_from_index`) into a new
   read-only `insights/` package over the indexer DB.
7. Re-home `validator.py` as a **standalone `verify/library_checks.py`** (not inlined into
   `verify/checker.py`).
8. Re-home `disk_cleaner.py` (FS `rmtree`) **and** `rescraper.py` (re-scrape repairs) into a new
   `maintenance/` package (not `indexer/repair.py`, which is DB-only).
9. **Delete the `library/` package.** Gate: `rg -t py 'personalscraper.library' personalscraper/ tests/`
   returns zero.
10. **Proactive no-NFO visibility** (decision #3): NFO-less dirs are indexed (folder-name fallback) AND
    flagged (`item_issue`/`nfo_missing`); `library doctor`/`audit` gains a dedicated "N items without a
    valid NFO → run `library-rescrape`" line.

### Non-goals

- **Removing any CLI command.** `library-index`, `library-scan`, `library-analyze`, `library-report`,
  `library-rescrape`, `library-maintenance` keep working from their new homes. `library-scan` becomes a
  **visible re-pointed alias** of `library-index --mode full` (decision #4/OQ-4 — kept in `--help`).
- **Changing the indexer schema.** The `media_stream` HDR/Atmos columns (`hdr_format`, `is_atmos`)
  **already exist** (migration 004) — this feature **populates** them, it does not add columns.
- **Migration scripts.** Pre-1.0, single instance, not in production. DB re-populated by re-running
  `library-index`.
- **Touching the indexer file-level walk** (`_walker.py`) — canonical, stays as-is.
- **Verify Checker Plugin System full delivery** (separate P2 item). `validator.py` lands as a standalone
  `verify/library_checks.py` the future plugin system can register; we do not build the `Check` Protocol /
  `CheckRegistry` here.
- **A Web UI API surface for `insights/`** — move-only (decision #6); the data functions already return
  dataclasses, so the future Web UI feature designs its own API atop them.

---

## 3. Current state (evidence-backed, re-grounded + adversarially validated against HEAD c85410fe / v0.18.0)

### 3.1 The two subsystems and their actual relationship

| Subsystem                                                                | Granularity                        | Creates `media_item`?                                                                                                                                        | Entry                                       |
| ------------------------------------------------------------------------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| `library/scanner.py` `scan_library()` (`:902`)                           | category → media-dir               | **YES** — `_item_repo.upsert` (`:691`) + seasons/episodes + `canonical_provider` (`:665`) + attrs (`upsert_attr` `:708`) + `item_issue` rows; **reads NFOs** | `library-scan` (`commands/library/scan.py`) |
| `indexer/scanner/` `scan()`                                              | recursive file tree (`_walker.py`) | **NO** — `enrich.py` only UPDATEs existing rows; `release_linker.py` only SELECTs                                                                            | `library-index`                             |
| `dispatch/media_index.py` (`:406`, via `MediaIndex.rebuild()` → `add()`) | disk dir scan                      | **YES (second creator)** — minimal rows, `canonical_provider=None`, dedup via `find_by_normalized_name` (`:397`); **folder names only, no NFO read**         | `dispatch/run.py` auto-rebuild on empty DB  |

### 3.2 Module inventory (verified `wc -l`)

`personalscraper/library/` — **4888 total LOC**:

| Module            | LOC  | Role / key anchors                                                                                                                                                                                                                                                                                                              | Destination                                                               |
| ----------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `scanner.py`      | 1003 | `scan_library` (`:902`); SOLE library `media_item` creator (`:691`); `_normalize_canonical_provider` (`:69`); `parse_title_year` (`:159`); `extract_nfo_ids` (`:211`); `extract_nfo_metadata` (`:228`); `_ensure_disk_row` (`:851`, DEV #50); delegates file walk; already imports `core.media_types.VIDEO_EXTENSIONS` (`:155`) | helpers → `nfo_utils.py`; creation → new `_item_stage`; **delete**        |
| `analyzer.py`     | 824  | `analyze()` DB aggregate (`:143`); `analyze_library()` ffprobe deep-scan (via `extract_stream_info`, import `:44`); `analyze_from_index()` (`:436`, reads `media_stream`)                                                                                                                                                       | `analyze`/`analyze_from_index` → `insights/`; ffprobe re-scan **deleted** |
| `rescraper.py`    | 677  | targeted TMDB/TVDB repairs (`rescrape_library` `:545`, `_detect_needs` `:53`: `needs_nfo = not is_nfo_complete`); imports `extract_nfo_ids`/`parse_title_year` from `scanner` + `models`; imports canonical `SEASON_DIR_RE` (`:397`)                                                                                            | → **`maintenance/`** (decision #7)                                        |
| `models.py`       | 597  | 18 dataclasses (`MediaFileAnalysis`, `VideoInfo`, `NfoStatus`, `ArtworkStatus`, `LibraryAnalysis*`, `Recommendation`, `RescrapeAction`, …)                                                                                                                                                                                      | **split by producer/consumer** (§4.6)                                     |
| `disk_cleaner.py` | 571  | FS `rmtree` (`_scandir_rmtree` `:165`) + NTFS ghost-dirent + outbox write-through (`_publish_deleted` `:118`); local `_VIDEO_EXTENSIONS` (`:42`) + `_TV_SEASON_DIR_RE` (`:68`)                                                                                                                                                  | → **`maintenance/disk_cleaner.py`**                                       |
| `reporter.py`     | 519  | read-only rendering (`generate_report`, `format_report_text`)                                                                                                                                                                                                                                                                   | → `insights/reporter.py`                                                  |
| `validator.py`    | 395  | wraps `verify.checker.MediaChecker` (`:31`) + `verify.fixer.MediaFixer`                                                                                                                                                                                                                                                         | → `verify/library_checks.py`                                              |
| `recommender.py`  | 295  | read-only (`generate_recommendations`)                                                                                                                                                                                                                                                                                          | → `insights/recommender.py`                                               |
| `__init__.py`     | 7    | marker                                                                                                                                                                                                                                                                                                                          | **delete**                                                                |

### 3.3 The `canonical_provider` divergence (the 194-show landmine)

- `library/scanner.py:69` `_normalize_canonical_provider(kind, tvdb_id, tmdb_id, nfo_declared)` —
  **deterministic**: derives from `kind` + IDs, **ignores** the NFO `default` flag (uses it only for a
  WARN). The 194-show fix (Phase 14.1 / reopen 12.1).
- `backfill_ids_canonical.py` `_parse_canonical_from_nfo`/`init_canonical_from_nfo` —
  **NFO-default-driven**: reads `<uniqueid default="true">`; on an unsupported default, falls back to the
  **first supported uniqueid in NFO XML order** — _not_ kind-preferred. The code documents (`~:104-110`)
  it "may pick `tmdb` even though `tvdb` would be the more semantically correct canonical anchor."
- **Trigger (validated correction):** `init_canonical_from_nfo` runs **only via the manual
  `library-init-canonical` command** — **not** any scheduled job. The recurring `library-backfill-ids`
  launchd job runs `run_backfill_ids`, which **reads but never overwrites** `canonical_provider`. So the
  two derivations contradict for the same item when the operator runs `library-init-canonical` after
  `library-scan` — a real divergence (two semantics), even if not on a cron. The regression test is
  `tests/indexer/scanner/test_init_canonical.py` (carry forward verbatim).

### 3.4 Season-dir regexes (SSOT violation — silent-regression trap)

Canonical: `naming_patterns.SEASON_DIR_RE` (`naming_patterns.py:172`), built from
`season_dir = "Saison {Season:02d}"` → `^Saison (\d+)$` — **French-only, single form**. Five ad-hoc copies:

| Location                                    | Pattern (verbatim)                        | Note                                |
| ------------------------------------------- | ----------------------------------------- | ----------------------------------- |
| `library/disk_cleaner.py:68`                | `^(?:saison\|season)\s*\d+$\|^specials?$` | **also matches English + Specials** |
| `indexer/scanner/_modes/enrich.py:122`      | `^(?:saison\|season)\s*\d+$\|^specials?$` | **also matches English + Specials** |
| `indexer/scanner/_modes/incremental.py:667` | `^(?:saison\|season)\s*\d+$\|^specials?$` | **also matches English + Specials** |
| `indexer/release_linker.py:34`              | `^Sa[ie]son\s+(\d+)$\|^Season\s+(\d+)$`   | capture groups, no `Specials`       |
| `trailers/scanner.py:27`                    | `^Saison (\d{2})$`                        | 2-digit French only                 |

**Critical (validated):** the three `(?:saison|season)…specials?` copies match `Season N`/`Specials` that
the canonical does **not**. Naively folding them into the current canonical would **silently lose** those
matches. Phase 0 must therefore **first widen** `naming_patterns.season_dir`/`SEASON_DIR_RE` to the
**union** (French `Saison N` + English `Season N` + `Specials`), add a numbered
`season_number_from_dir(name) -> int | None` helper (for `release_linker`), guard it with a
**no-regression test** (every form each copy matched still matches), **then** replace the copies.

### 3.5 `VIDEO_EXTENSIONS` SSOT (validated correction)

arch-cleanup-2 (#28) promoted `VIDEO_EXTENSIONS` to **`core.media_types.VIDEO_EXTENSIONS:26`**;
`sorter.file_type` now re-exports it, and `library/scanner.py:155` already imports the canonical one. So
Phase 0's target is **`core.media_types`** (not `sorter.file_type`). Pin the exact remaining local
**re-definitions** (vs harmless re-imports) per file before editing — do not assume every grep hit is a
violation.

### 3.6 Consumer / blast-radius map

- **External `library.*` importers (outside the package):** only `trailers/scanner.py:16` →
  `from personalscraper.library.scanner import extract_nfo_ids, parse_title_year`.
- **CLI wiring (expected; repoint):** `commands/library/analyze.py` → `analyzer`/`models`/`recommender`/
  `rescraper`/`reporter`; `commands/library/maintenance.py` → `disk_cleaner`/`models`/`validator`.
- **Internal cross-coupling (resolves on deletion):** `analyzer.py`/`rescraper.py` import
  `parse_title_year`/`extract_nfo_ids` from `library.scanner`.
- **Tests:** ~9773 LOC across 16 files import `personalscraper.library`. Re-homing test coverage is the
  dominant non-code effort; under-migration drops branch coverage below the 90% `make check` gate.
- **No cron/launchd job runs `library-scan` or the canonical NFO derivation** (§3.3).

### 3.7 Module-size + landing zones

- `scripts/check-module-size.py`: soft-warn 800, hard-block 1000 non-blank, **excludes all `__init__.py`**.
  `verify/checker.py` = **716 non-blank** (825 total) — under soft ceiling, but +`validator.py` (395)
  would breach 1000 → must be a standalone `verify/library_checks.py`. **Blind-spot caution:** never dump
  a re-homed body into a package `__init__.py` to dodge the guardrail.
- `personalscraper/insights/` — **absent** (create). `personalscraper/maintenance/` — **absent** (create).
- `personalscraper/nfo_utils.py` — **exists** (`glob_nfo_candidates`, `is_nfo_complete`) — the home for
  `parse_title_year`/`extract_nfo_ids`/`extract_nfo_metadata` (append).
- `backfill_ids_canonical.py` — exists — home for the unified canonical helper (or a sibling `_canonical.py`).
- `media_stream` — **already has** `hdr_format` (TEXT) + `is_atmos` (INTEGER) (migration 004); `enrich.py:360-376`
  already persists them.

---

## 4. Proposed design

### 4.1 Target architecture

```
personalscraper/
├── nfo_utils.py                  (MODIFIED — gains parse_title_year, extract_nfo_ids, extract_nfo_metadata)
├── naming_patterns.py            (MODIFIED — SEASON_DIR_RE widened FR+EN+Specials; season_number_from_dir())
├── core/media_types.py           (SSOT for VIDEO_EXTENSIONS — already canonical, just point call-sites here)
├── indexer/
│   └── scanner/
│       ├── _modes/
│       │   ├── full.py           (MODIFIED — invokes _item_stage before the file walk)
│       │   ├── _item_stage.py    (NEW — folds media_item/season/episode/issue creation + _ensure_disk_row;
│       │   │                       exports build_item_row() + upsert_item_with_attrs() shared with dispatch)
│       │   ├── _canonical.py     (NEW — single kind-deterministic canonical SSOT; absorbs
│       │   │                       _normalize_canonical_provider + init_canonical_from_nfo extraction)
│       │   ├── backfill_ids_canonical.py (MODIFIED — delegates to _canonical.py)
│       │   ├── enrich.py         (MODIFIED — season regex → SSOT; ensure hdr_format/is_atmos parity)
│       │   └── incremental.py    (MODIFIED — season regex → SSOT)
│       └── release_linker.py     (MODIFIED — season regex → numbered SSOT helper)
├── dispatch/media_index.py       (MODIFIED — rebuild() delegates to upsert_item_with_attrs; no own upsert)
├── verify/library_checks.py      (NEW — re-home of validator.py; standalone, NOT inlined into checker.py)
├── insights/                     (NEW read-only package over the indexer DB)
│   ├── __init__.py
│   ├── models.py                 (analysis + recommender dataclasses — see §4.6)
│   ├── analytics.py              (analyze() / analyze_from_index())
│   ├── reporter.py
│   └── recommender.py
├── maintenance/                  (NEW operator-upkeep package)
│   ├── __init__.py
│   ├── disk_cleaner.py           (FS rmtree + NTFS ghost + outbox write-through)
│   └── rescraper.py              (re-scrape repairs; backs library-rescrape)
├── trailers/scanner.py           (MODIFIED — season regex → SSOT; NFO helper imports → nfo_utils)
├── commands/library/             (CLI namespace STAYS, repointed: scan/analyze/maintenance/doctor/audit/…)
└── library/                      (DELETED at end state)
```

### 4.2 Public import paths to preserve

- `extract_nfo_ids`, `extract_nfo_metadata`, `parse_title_year` → `personalscraper.nfo_utils` (consumed by
  `trailers/scanner.py`, `rescraper.py`, `analytics.py`). This is the only cross-package import surface;
  everything else is CLI wiring.
- `naming_patterns.SEASON_DIR_RE` stays the SSOT (widened); `release_linker` uses the new
  `season_number_from_dir()` helper rather than a divergent capture-group regex.

### 4.3 The unified item stage (the crux — decision #4)

`indexer/scanner/_modes/_item_stage.py` performs the directory-metadata pass that today lives in
`library/scanner.py`: for each media dir under each category, read the NFO, build the rich `media_item`
row (seasons, episodes, `canonical_provider`, `dispatch_path`/`disk`/`norm_title` attrs), upsert via
`item_repo.upsert` + `upsert_attr`, persist `item_issue` rows. `full.py` invokes it **before** the file
walk (pass 1), so a single `library-index --mode full` reaches the same DB end-state as today's
`library-scan` + `library-index`.

- **Stage inside `ScanMode.full`, not a new mode.** A `--mode items` would re-introduce a two-step run.
- **Shared row-builder, single creator.** The row-construction logic is extracted into reusable
  `build_item_row(nfo, dir, …)` + `upsert_item_with_attrs(conn, row, …)` that BOTH `_item_stage` and
  `dispatch/media_index.rebuild` call — eliminating the third write pattern. Dispatch auto-rebuild now
  produces rich rows (resolves the `canonical_provider=None`/no-seasons degradation).
- **No-NFO handling (decision #2):** NFO missing/incomplete → minimal fallback row from the folder name +
  `item_issue` (`nfo_missing`/`nfo_incomplete`) + bump the `nfo_missing` stat. Never dropped, never silent.
  This upgrades the dispatch path, which today produces minimal rows **silently**.
- **Behaviour to preserve (regression-tested):** `dispatch_path`/`disk`/`norm_title` attrs (trailers +
  `release_linker` INNER JOINs depend on them); `item_issue` persistence; DEV #50 disk-row reconciliation
  (`_ensure_disk_row`); identical `media_item` count + content vs the legacy two-step.

### 4.4 Canonical-provider SSOT (decision #5)

`_canonical.py` exposes one extractor consumed by `_item_stage` and `backfill_ids_canonical`. The
**kind-deterministic rule** (`_normalize_canonical_provider`: show→`tvdb` if a tvdb_id exists, movie→`tmdb`
if a tmdb_id exists) **fait autorité**; the NFO `<uniqueid default>` flag is demoted to a WARN/audit
signal; the indexer's NFO-XML-order fallback is **discarded**. `external_ids_json` seeding from all
uniqueids is **kept**. The 194-show regression test is carried forward verbatim; a new test pins
"kind beats NFO XML order". Net effect: the fold also **fixes** the manual-command backfill↔scan
contradiction (§3.3).

### 4.5 ffprobe → enrich fold (decision #8)

The `media_stream` HDR/Atmos columns (`hdr_format`, `is_atmos`) **already exist** (migration 004) and
`enrich.py:360-376` already persists them. Phase 4 deletes the redundant library ffprobe re-scan
(`analyzer.analyze_library` → `scraper.mediainfo.extract_stream_info`) and makes `analyze_from_index()`
(reads `media_stream`) the sole stream reader. The real risk is a **granularity gap**: the dropped ffprobe
path distinguishes HDR10/HDR10+/Dolby Vision/HLG (`scraper/mediainfo.py`). Phase 4 verifies the surviving
`enrich`/pymediainfo path populates `hdr_format` at the same granularity (close the gap by improving
enrich population, or accept + document it). `scraper/mediainfo.extract_stream_info` itself **stays** —
NFO generation still uses it; only the library deep-scan caller is removed.

### 4.6 `models.py` split (explicit per-consumer routing)

The old draft kept all dataclasses in one `insights/models.py`; we **split by producer/consumer** instead
(layering: `verify`/indexer must not depend on `insights/`).

| Dataclasses                                                                                                     | Destination                                                              | Consumer               |
| --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------- |
| `SeasonInfo`, `LibraryScanItem`                                                                                 | indexer `_item_stage` types                                              | scan stage             |
| `NfoStatus`, `ArtworkStatus` (cross-consumer)                                                                   | **with the producer** — `_item_stage` types; `verify` imports from there | scan + verify          |
| `ValidationItem`, `LibraryValidationResult`                                                                     | `verify/library_checks.py`                                               | verify                 |
| `VideoInfo`, `AudioTrack`, `SubtitleTrack`, `MediaFileAnalysis`, `LibraryAnalysisItem`, `LibraryAnalysisResult` | `insights/models.py`                                                     | analyze                |
| `CurrentState`, `TargetState`, `Recommendation`, `LibraryRecommendationResult`                                  | `insights/models.py`                                                     | recommender + reporter |
| `RescrapeAction`, `LibraryRescrapeResult`                                                                       | `maintenance/rescraper.py`                                               | rescrape               |

(Any dataclass a precise grep finds shared across destinations lands with its **producer**; no orphan
models module is created.)

---

## 5. Phasing

Lifecycle: `feat/lib-fold`; SemVer **minor** (0.18.0 → 0.19.0) at `create-branch`; Conventional Commits
scoped `(lib-fold)`; each phase ends on `chore(lib-fold): phase N gate — …` with `make lint && make test
&& make check` green; squash merge. **Strict order 0 → 6.** No migration scripts. Regression-test-per-bug.
Module-size hard ceiling 1000 non-blank (never dodge via `__init__.py`).

### Phase 0 — Season-dir SSOT (widen-first) + `VIDEO_EXTENSIONS` cleanup [low]

- **Widen** `naming_patterns.season_dir`/`SEASON_DIR_RE` to the union (French `Saison N` + English
  `Season N` + `Specials`); add `season_number_from_dir()`; **no-regression test** (every form the 5 copies
  matched still matches). **Then** replace the 5 ad-hoc copies (`disk_cleaner:68`, `enrich:122`,
  `incremental:667`, `release_linker:34` → numbered helper, `trailers:27`). Kill local `VIDEO_EXTENSIONS`
  re-definitions → `core.media_types.VIDEO_EXTENSIONS` (pin exact re-defs first).
- **Gate:** ACC-00 + ACC-00b + ACC-00c + ACC-00d green.

### Phase 1 — Extract NFO helpers → `nfo_utils` [low]

- Move `extract_nfo_ids`/`extract_nfo_metadata`/`parse_title_year` out of `scanner.py` into the existing
  `personalscraper/nfo_utils.py`; repoint importers (`trailers/scanner.py`, `analyzer.py`, `rescraper.py`).
  No back-compat shim (pre-1.0). Tests: one per moved function.
- **Gate:** ACC-02 + ACC-02b green.

### Phase 2 — Build `_item_stage` + `_canonical`; rewire `scan_library` to it (3a) [XL, high — the crux]

- Create `_item_stage.py` (`build_item_row`, `upsert_item_with_attrs`, season/episode upsert,
  `_detect_issues` incl. no-NFO fallback+flag, `_ensure_disk_row`) and `_canonical.py` (kind-deterministic
  SSOT). `full.py` invokes the stage as pass 1; `scan_library` is rewired to call the **same** stage
  (parallel path — every gate stays green before any deletion). `backfill_ids_canonical` delegates to
  `_canonical.py`.
- Tests: **characterization golden** — `library-index --mode full` DB end-state == legacy `library-scan`
  on a fixture (strict, baseline = `library-scan`); canonical 194-show guard carried forward; "kind beats
  NFO XML order"; DEV #50 disk-row dedup.
- **Gate:** ACC-03 (golden equality) green.

### Phase 3 — Single creator + cutover: redirect dispatch, alias `library-scan`, delete `scanner.py` (3b+4) [high]

- `dispatch/media_index.rebuild` delegates to `upsert_item_with_attrs` (rich rows; remove the standalone
  minimal-row upsert — no `canonical_provider=None`). `library-scan` → **visible** re-pointed alias of
  `library-index --mode full`. **Delete `library/scanner.py`**; re-home its unique tests.
- Tests: dispatch auto-rebuild now yields rich rows (pin as a bug-reproducer for the prior degradation).
- **Gate:** ACC-04 + ACC-04b green.

### Phase 4 — ffprobe fold + `insights/` [med]

- Delete `analyzer.analyze_library` (library ffprobe re-scan); ensure `enrich` populates the existing
  `media_stream.hdr_format`/`is_atmos` at ffprobe parity (close/accept the gap, §4.5). Create `insights/`
  (`models.py`, `analytics.py`, `reporter.py`, `recommender.py`); repoint `commands/library/analyze.py`.
  Delete `library/analyzer.py`, `library/reporter.py`, `library/recommender.py`.
- **Gate:** ACC-05 + ACC-05b green.

### Phase 5 — `verify`/`maintenance` re-home + proactive no-NFO + delete `library/` [med]

- `validator.py` → `verify/library_checks.py` (standalone). `disk_cleaner.py` + `rescraper.py` →
  `maintenance/`. Split `models.py` (§4.6). Add the proactive no-NFO line to `library doctor`/`audit`
  (decision #3); confirm `library-rescrape` targets `nfo_missing` items. Delete `library/__init__.py` →
  the whole package.
- **Gate:** ACC-06 + ACC-06b + ACC-06c green.

### Phase 6 — Feature PR + review (auto-invoked)

- `/implement:feature-pr` → `/implement:pr-review`. Docs updated: `docs/reference/commands.md` (remove the
  implicit run-order note — `library-index --mode full` self-sufficient), `architecture.md` (module map:
  `library/` removed, `insights/` + `maintenance/` added), `indexer.md` (item stage), `CHANGELOG.md` 0.19.0.

---

## 6. Acceptance criteria (SH-16 — executable commands + documented expected output)

```bash
# ACC-00  Phase 0 — no ad-hoc season-dir regex constant left in the migrated files
rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/library/ personalscraper/indexer/ personalscraper/trailers/ ; echo "rc=$?"
# Expected: no output, then rc=1

# ACC-00b Phase 0 — the WIDENED canonical pattern matches French + English + Specials
python -c "from personalscraper.naming_patterns import SEASON_DIR_RE as r; assert all(r.match(s) for s in ['Saison 1','Saison 01','Season 1','Specials']); print('OK')"
# Expected: OK   (passes only AFTER Phase 0 widens; today it is French-only and fails — by design)

# ACC-00c Phase 0 — numbered helper extracts the season number
python -c "from personalscraper.naming_patterns import season_number_from_dir as f; assert f('Saison 3')==3 and f('Season 12')==12 and f('Specials') in (0,None); print('OK')"
# Expected: OK

# ACC-00d Phase 0 — VIDEO_EXTENSIONS SSOT is core.media_types (no library re-definition)
rg -t py 'VIDEO_EXTENSIONS\s*[:=]\s*frozenset|VIDEO_EXTENSIONS\s*=\s*\{' personalscraper/library/ ; echo "rc=$?"
# Expected: no output, then rc=1

# ACC-02  Phase 1 — no importer reaches into library.scanner for NFO helpers; helpers callable from new home
# Scoped to the three NFO helpers: scan_library/scan_movie_dir/scan_tvshow_dir/_ensure_disk_row imports
# legitimately remain until Phase 3 deletes scanner.py (the broad form is a post-Phase-3 state, not a
# Phase-1 criterion — it is unsatisfiable while scan_library is the live legacy path and is still tested).
rg -t py 'from personalscraper.library.scanner import (parse_title_year|extract_nfo_ids|extract_nfo_metadata)' personalscraper/ tests/ ; echo "rc=$?"
# Expected: no output, then rc=1
# ACC-02b
python -c "from personalscraper.nfo_utils import parse_title_year, extract_nfo_ids, extract_nfo_metadata; print('OK')"
# Expected: OK

# ACC-03  Phase 2 — unified item stage + canonical SSOT exist; golden DB-equality holds
python -c "import personalscraper.indexer.scanner._modes._item_stage, personalscraper.indexer.scanner._modes._canonical; print('OK')"
# Expected: OK   (the golden equality vs legacy library-scan is asserted in the phase-2 characterization test)

# ACC-03b Phase 2 — no NFO-less dir is dropped; it is flagged
DB=$(python -c "from personalscraper.conf.loader import load_config as L; print(L().indexer.db_path)")
sqlite3 "$DB" "SELECT COUNT(*) FROM item_issue WHERE type IN ('nfo_missing','nfo_incomplete');"
# Expected: integer >= 0 (rows exist iff NFO-less dirs exist; none silently absent from media_item)

# ACC-04  Phase 3 — library/scanner.py + scan_library removed; dispatch makes rich rows (no canonical_provider=None)
test ! -f personalscraper/library/scanner.py && echo "deleted"
rg -t py 'library.scanner|scan_library' personalscraper/ tests/ ; echo "rc=$?"
# Expected: deleted   then no output, then rc=1
# ACC-04b
rg -t py 'canonical_provider=None' personalscraper/dispatch/media_index.py ; echo "rc=$?"
# Expected: no output, then rc=1

# ACC-05  Phase 4 — library ffprobe re-scan gone; insights package importable
rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/ ; echo "rc=$?"
# Expected: no output, then rc=1   (helper survives only under scraper/ for NFO gen)
# ACC-05b existing HDR/Atmos columns populated by enrich (parity, not just presence)
python -c "import sqlite3; from personalscraper.conf.loader import load_config as L; c=sqlite3.connect(L().indexer.db_path); cols=[r[1] for r in c.execute('PRAGMA table_info(media_stream)')]; assert {'hdr_format','is_atmos'} <= set(cols), cols; n=c.execute(\"SELECT COUNT(*) FROM media_stream WHERE hdr_format IS NOT NULL\").fetchone()[0]; print('cols-ok hdr_rows=', n)"
# Expected: cols-ok hdr_rows=<int>  (>0 on an HDR-containing enriched fixture — proves enrich parity)

# ACC-06  Phase 5 — validator in verify (not inlined); disk_cleaner+rescraper in maintenance; library/ gone
test -f personalscraper/verify/library_checks.py && test -f personalscraper/maintenance/disk_cleaner.py && test -f personalscraper/maintenance/rescraper.py && echo "rehomed"
rg -t py 'personalscraper.library' personalscraper/ tests/ ; echo "rc=$?"
test ! -d personalscraper/library && echo "package removed"
# Expected: rehomed ; then no output, then rc=1 ; then package removed
# ACC-06b proactive no-NFO visibility line exists in doctor/audit output
personalscraper library-doctor 2>&1 | rg -i 'nfo' ; echo "rc=$?"
# Expected: a line mentioning items without a valid NFO; rc=0
# ACC-06c module-size hard ceiling respected (no module >= 1000 non-blank)
python3 scripts/check-module-size.py ; echo "rc=$?"
# Expected: rc=0

# ACC-07  Version bump + CHANGELOG
cat VERSION ; grep -c '^## \[0.19.0\]' CHANGELOG.md
# Expected: 0.19.0   then   1

# ACC-GATE  every phase gate
make lint && make test && make check ; echo "rc=$?"
# Expected: ruff+mypy clean, "NNNN passed" 0 failed/errors, coverage >= 90%; rc=0

# ACC-SMOKE
python -c "import personalscraper; print('import-ok')"
# Expected: import-ok
```

---

## 7. Risks & mitigations

| Risk                                                                              | Sev      | Mitigation                                                                                                                                         |
| --------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Folding `media_item` creation half-breaks the DB end-state vs the legacy two-step | High     | Phase 2 ships a characterization golden asserting DB-row equality vs `library-scan` BEFORE any deletion; Phase 3 deletes only once equality holds. |
| `canonical_provider` SSOT merge re-opens the 194-show regression                  | High     | Carry `test_init_canonical.py` forward verbatim; add a "kind beats NFO XML order" test; treat any failure as stop-the-line.                        |
| Dispatch auto-rebuild diverges (third write pattern)                              | High     | Single shared `upsert_item_with_attrs`; ACC-04b grep forbids `canonical_provider=None` reappearing.                                                |
| **Season-regex consolidation silently loses English/Specials matches**            | **High** | **Widen the canonical (FR+EN+Specials) with a no-regression test BEFORE deleting any ad-hoc copy** (§3.4).                                         |
| HDR/Atmos granularity lost when the library ffprobe re-scan is dropped            | Medium   | Columns already exist + populated; Phase 4 verifies `enrich` parity (HDR10/HDR10+/DV/HLG) or documents the gap (ACC-05b).                          |
| Season-regex change in `trailers`/`release_linker` alters placement behaviour     | Medium   | Phase 0 regression tests assert the NEW correct behaviour (1/3-digit + English + Specials), not mere equality.                                     |
| Test re-homing (~9773 LOC / 16 files) drops branch coverage below 90%             | Medium   | Each gate runs `make check` (coverage included); migrate unique coverage, don't just delete.                                                       |
| Module-size guardrail dodge via `__init__.py`                                     | Low      | Re-homed bodies go in named non-`__init__` files; ACC-06c gate.                                                                                    |

---

## 8. Resolved decisions (were open questions in the draft)

| OQ                          | Resolution                                                                                                                                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| OQ-1 dispatch second writer | **Single creator** — `rebuild()` delegates to the shared `upsert_item_with_attrs`; no degraded fast-path (decision #4).                          |
| OQ-2 HDR/Atmos              | Columns **already exist** (`hdr_format`/`is_atmos`); **no new columns** — Phase 4 ensures `enrich` parity, else documents the gap (decision #8). |
| OQ-3 delivery               | **One `feat/lib-fold` minor**; the crux is split internally Phase 2 (build, parallel) → Phase 3 (cutover+delete).                                |
| OQ-4 `library-scan`         | **Visible** re-pointed alias of `library-index --mode full` (kept in `--help`).                                                                  |
| OQ-5 `rescraper` home       | **`maintenance/`** (mutation semantics; CLI import trivially repointed) (decision #7).                                                           |
| (new) no-NFO behaviour      | Index with folder-name fallback + `item_issue` flag; correction loop preserved + proactive `doctor`/`audit` visibility (decisions #2/#3).        |
| (new) canonical authority   | **Kind-deterministic** rule wins; NFO `default` demoted to WARN (decision #5).                                                                   |
| (new) `models.py`           | **Split by producer/consumer** (§4.6), not one `insights/models.py` — keeps `verify`/indexer off an `insights/` dependency.                      |

---

## 9. References

- **Source analysis:** `docs/analysis/01-library-indexer-consolidation.md`.
- **ROADMAP entry:** P1 — Library / Indexer Consolidation (refreshed; the shipped arch-cleanup-2 +
  multi-filesystem entries removed via the `roadmap-refresh-fold` commit folded onto this branch).
- **Structural template:** `docs/archive/features/registry/DESIGN.md` (section style + ACCEPTANCE format).
- **Project rules (CLAUDE.md):** SH-16 ACCEPTANCE; module-size soft 800 / hard 1000 non-blank
  (excludes `__init__.py`); regression-test-per-bug.
- **Memory:** `feedback_no_backcompat_before_v1` (no migration scripts — re-index in place);
  `feedback_multi_provider_ids_separation` (canonical family separation — 194-show guard);
  `feedback_regression_test_per_bug`; `feedback_validate_plans_against_code` (this DESIGN was re-grounded
  - adversarially validated against HEAD, correcting the draft's HDR-columns and season-regex claims).
- **Reference docs (lazy-load):** `docs/reference/indexer.md`, `docs/reference/indexer-json-shapes.md`,
  `docs/reference/scraping.md`, `docs/reference/storage.md`.

```

```
