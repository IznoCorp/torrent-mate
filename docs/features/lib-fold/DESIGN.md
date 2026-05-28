# Design — Library / Indexer Consolidation (`lib-fold`)

> **Status**: Draft (DESIGN authoring) — pending user review then `/implement:plan`.
> **Date**: 2026-05-28
> **Roadmap item**: P1 — Library / Indexer Consolidation (`ROADMAP.md:32-62`)
> **Version bump target**: 0.16.0 → 0.17.0 (minor — new internal scan stage + package moves; no public CLI removed)
> **Branch**: `feat/lib-fold` · **Merge**: squash
> **Source analysis**: `docs/analysis/01-library-indexer-consolidation.md` (read in full; this DESIGN supersedes its phasing with implementation-grade detail)

---

## 1. Purpose & Motivation

The `personalscraper/library/` package (8 modules, **4888 total LOC**) grew as a
parallel media-introspection subsystem alongside the canonical `indexer/`. Over
time the two subsystems accumulated genuine duplication and, worse, **two
uncoordinated writers of the `media_item` table** with different row richness.
The result is an operator workflow that depends on an undocumented run-order
(`library-scan` to create rich rows, _then_ `library-index` to populate
files/streams) and a latent data-quality cliff: if the dispatch path
auto-rebuilds the DB on an empty database, it produces minimal rows
(`canonical_provider=None`, no seasons) that silently degrade everything
downstream.

This feature folds the surviving, load-bearing parts of `library/` into the
indexer (the canonical subsystem), unifies four duplicated concepts onto single
sources of truth, re-homes the read-only/maintenance pieces into purpose-built
packages, and deletes the `library/` package. The end state is one media model,
one scan command, one canonical-provider extractor, one season-dir regex, one
MediaInfo backend.

**Premise correction (verified 2026-05-28, against HEAD).** The ROADMAP's
original central claim — that `library/scanner.py` "duplicates the indexer walk"
— is **false**. `scan_library()` (`library/scanner.py:902`) walks only at
media-directory granularity and then _delegates_ the recursive file walk to
`indexer.scanner.scan(mode=ScanMode.full)` (`library/scanner.py:997-1003`,
import at `:39`). This DESIGN must not claim "remove duplicate walk"; the real
work is reconciling the two `media_item` writers and four duplicated concepts.

---

## 2. Goals / Non-goals

### Goals

1. Fold the rich `media_item` / `season` / `episode` creation in
   `library/scanner.py:691` (`_item_repo.upsert`) into a **unified indexer scan
   stage** invoked by `ScanMode.full`, so `library-index --mode full` is
   self-sufficient (no prior `library-scan` step required).
2. Reconcile the **second `media_item` writer** — `dispatch/media_index.py`
   `MediaIndex.rebuild()` (`:406`, minimal rows, `canonical_provider=None` at
   `:418`) — so there is no third independent write pattern.
3. Unify `canonical_provider` extraction: `_normalize_canonical_provider`
   (`library/scanner.py:69`) and `init_canonical_from_nfo`
   (`indexer/scanner/_modes/backfill_ids_canonical.py`) collapse into **one
   SSOT** that carries the 194-show regression guard forward verbatim.
4. Merge the ffprobe stream backend (`library/analyzer.py:44`
   `extract_stream_info`) into the pymediainfo enrich path
   (`indexer/scanner/_modes/enrich.py`, `MediaInfoWrapper`), resolving or
   explicitly accepting the HDR/Atmos fidelity gap (OQ-2) — **no migration
   script** (re-index in place).
5. Collapse the **five divergent season-dir regexes** onto
   `naming_patterns.SEASON_DIR_RE`.
6. Re-home read-only modules (`reporter.py`, `recommender.py`, plus the
   DB-aggregate query layer) into a new `insights/` package.
7. Re-home `validator.py` as a **`verify/` check plugin** (not inlined into
   `verify/checker.py`).
8. Re-home `disk_cleaner.py` (FS `rmtree`) into a new `maintenance/` package
   (not `indexer/repair.py`, which is DB-only).
9. **Delete the `library/` package.** Residual-import grep gate:
   `rg -t py 'personalscraper.library' personalscraper/ tests/` returns zero.

### Non-goals

- **Removing any CLI command.** `library-index`, `library-scan`,
  `library-analyze`, `library-report`, `library-maintenance` keep working from
  their new locations (ROADMAP non-goal, `ROADMAP.md:60`).
- **Changing the indexer schema in a breaking way.** OQ-2 may _add_ nullable
  columns to `media_stream` in place (re-index, no migration script) — that is
  additive, not a breaking change.
- **Migration scripts.** Pre-1.0, single mono-user instance, not in production
  (`feedback_no_backcompat_before_v1`). DB/NFO/config evolve in place; the DB is
  re-populated by re-running `library-index`.
- **Touching the indexer file-level walk** (`_walker.py`) — it is the canonical
  walk and stays as-is.
- **Verify Checker Plugin System full delivery** (separate P2 roadmap item).
  This feature lands `validator.py` as a _standalone_ `verify/library_checks.py`
  module that the future plugin system can register; it does not build the
  `Check` Protocol / `CheckRegistry` here.

---

## 3. Current state (evidence-backed ground-truth map)

All anchors below re-verified against the working tree on 2026-05-28.

### 3.1 The two subsystems and their actual relationship

| Subsystem                                                 | Granularity                        | Creates `media_item`?                                                                                                                                  | Entry point                                                    |
| --------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| `library/scanner.py` `scan_library()` (`:902`)            | category → media-dir               | **YES** — `_item_repo.upsert` (`:691`) + seasons/episodes + `canonical_provider` (`:665`) + attrs (`upsert_attr` `:708`) + issue rows                  | `library-scan` command (`commands/library/scan.py`)            |
| `indexer/scanner/` `scan()`                               | recursive file tree (`_walker.py`) | **NO** — `enrich.py` only UPDATEs existing rows; `release_linker.py` only SELECTs                                                                      | `library-index` command                                        |
| `dispatch/media_index.py` `MediaIndex.rebuild()` (`:437`) | disk dir scan                      | **YES (second creator)** — `item_repo.upsert` (`:406`), minimal rows, `canonical_provider=None` (`:418`), dedup via `find_by_normalized_name` (`:397`) | `dispatch/run.py:112` (`auto_rebuild=not dry_run` on empty DB) |

`scan_library()` delegates the heavy walk explicitly (`library/scanner.py:997-1003`):

```python
_indexer_scan(            # from personalscraper.indexer.scanner import scan as _indexer_scan  (:39)
    ...,
    mode=ScanMode.full,  # :999
    ...,
)
```

### 3.2 Module inventory (verified `wc -l`)

`personalscraper/library/` — **4888 total LOC**:

| Module            | Total LOC                                       | Role / key anchors                                                                                                                                                                                                                                                                                 | Destination                                                                                           |
| ----------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `scanner.py`      | 1003 (855 non-blank — `check-module-size` WARN) | `scan_library` (`:902`); SOLE library `media_item` creator (`:691`); `_normalize_canonical_provider` (`:69`); `parse_title_year` (`:159`); `extract_nfo_ids` (`:211`); `extract_nfo_metadata` (`:228`); `_ensure_disk_row` (`:851`, DEV #50 disk-row reconciliation); delegates file walk (`:997`) | helpers → `nfo_utils.py`; creation logic → new indexer stage; **delete**                              |
| `analyzer.py`     | 824                                             | `analyze()` DB aggregate (`:143`); `analyze_library()` ffprobe deep-scan (`:366` via `extract_stream_info`, import `:44`); `analyze_from_index()` (`:436`, reads `media_stream`); imports `parse_title_year` from `library.scanner` (`:42`); HDR/Atmos gap documented at `:451-453`                | `analyze()`/`analyze_from_index()` → `insights/`; ffprobe path → folded into `enrich.py` then deleted |
| `rescraper.py`    | 677                                             | targeted TMDB/TVDB repairs; imports `extract_nfo_ids`/`parse_title_year` from `library.scanner` (`:36-38`) + `library.models` (`:27`); already imports canonical `SEASON_DIR_RE` (`:397`)                                                                                                          | → `insights/` or `maintenance/` (OQ-5); rewire helper imports                                         |
| `models.py`       | 597                                             | dataclasses (`MediaFileAnalysis`, `VideoInfo`, …) + `write_json`/`read_json`; consumed by analyze.py AND maintenance.py                                                                                                                                                                            | → `insights/models.py` (shared read-only model home)                                                  |
| `disk_cleaner.py` | 571                                             | FS `rmtree` (`_scandir_rmtree` `:165`) + NTFS ghost-dirent handling + outbox write-through (`_publish_deleted` `:118`); local `_VIDEO_EXTENSIONS` (`:42`) + `_TV_SEASON_DIR_RE` (`:68`); `clean_library` entry                                                                                     | → new `maintenance/disk_cleaner.py`                                                                   |
| `reporter.py`     | 519                                             | read-only report rendering (`format_report_text`, `generate_report`)                                                                                                                                                                                                                               | → `insights/reporter.py`                                                                              |
| `validator.py`    | 395                                             | wraps `verify.checker.MediaChecker` (`:31`) + `verify.fixer.MediaFixer` (`:32`); `validate_library`/`validate_from_index`                                                                                                                                                                          | → `verify/library_checks.py`                                                                          |
| `recommender.py`  | 295                                             | read-only recommendations (`generate_recommendations`)                                                                                                                                                                                                                                             | → `insights/recommender.py`                                                                           |
| `__init__.py`     | 7                                               | package marker                                                                                                                                                                                                                                                                                     | **delete** (package removal)                                                                          |

### 3.3 The canonical_provider overlap (the Phase-landmine)

`library/scanner.py:69` `_normalize_canonical_provider()` exists to guard the
**194-show regression** (Phase 14.1 / reopen 12.1): NFOs may carry a
`<uniqueid default="true">` whose family disagrees with the SSOT (TV → TVDB
primary, movies → TMDB primary). The **same concept already lives in the
indexer**: `indexer/scanner/_modes/backfill_ids_canonical.py`
`init_canonical_from_nfo` extracts a canonical anchor from
`<uniqueid default="true">` with a documented fallback when the default is
unsupported (helpers: `_parse_canonical_from_nfo`, `_resolve_nfo_path`,
`InitCanonicalStats`). These are not currently shared. The regression test lives
at `tests/indexer/scanner/test_init_canonical.py`. Any fold MUST reconcile both
into one helper and carry the regression test forward.

### 3.4 Five divergent season-dir regexes (SSOT violation)

Canonical: `naming_patterns.SEASON_DIR_RE` (`naming_patterns.py:172`). Five
ad-hoc copies exist (all re-verified verbatim 2026-05-28):

| Location                                        | Pattern (verbatim)   | Divergence                                                                                |
| ----------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------- |
| `library/disk_cleaner.py:68-69`                 | `^(?:saison          | season)\s\*\d+$                                                                           | ^specials?$`                                               | equivalent but local copy |
| `indexer/scanner/_modes/enrich.py:122-123`      | `^(?:saison          | season)\s\*\d+$                                                                           | ^specials?$`                                               | equivalent but local copy |
| `indexer/scanner/_modes/incremental.py:635-636` | `^(?:saison          | season)\s\*\d+$                                                                           | ^specials?$`                                               | equivalent but local copy |
| `indexer/release_linker.py:34`                  | `^Sa[ie]son\s+(\d+)$ | ^Season\s+(\d+)$` (re.IGNORECASE)                                                         | **capture groups; no `Specials`** — functionally divergent |
| `trailers/scanner.py:27`                        | `^Saison (\d{2})$`   | **2-digit only; no `Season`; no `Specials`** — latent bug for 1/3-digit folders + English |

`release_linker.py:49` uses the capture group to extract the season number;
`trailers/scanner.py:354` uses its match. Switching these to canonical changes
behaviour — requires regression tests proving correctness, not just equality.

### 3.5 Consumer / blast-radius map

- **External `library.*` importers (outside the package):** only
  `trailers/scanner.py:16` →
  `from personalscraper.library.scanner import extract_nfo_ids, parse_title_year`
  (used at `:315` and `:320`).
- **CLI wiring layer (expected; must be repointed):**
  - `commands/library/analyze.py` imports `analyzer` (`analyze`,
    `analyze_from_index`, `analyze_library` — `:52,142,342`), `models`
    (`write_json`, `read_json` — `:143,269,343`), `recommender`
    (`generate_recommendations` — `:144`), `rescraper` (`rescrape_library` —
    `:270`), `reporter` (`format_report_text`, `generate_report` — `:344`).
  - `commands/library/maintenance.py` imports `disk_cleaner` (`clean_library` —
    `:188`), `models` (`write_json` — `:286`), `validator`
    (`validate_from_index`, `validate_library` — `:287`).
- **Internal cross-coupling (resolves on deletion):** `analyzer.py:42` and
  `rescraper.py:36-38` import `parse_title_year`/`extract_nfo_ids` from
  `library.scanner`.
- **Tests:** ~9773 LOC across 16 files import `personalscraper.library`;
  ~43419 LOC across ~103 files import `personalscraper.indexer`. Re-homing test
  coverage is the dominant non-code effort; under-migration drops branch
  coverage below the 90% `make check` gate.
- **No cron/launchd job runs `library-scan`** — only the operator's manual
  workflow + `docs/reference/commands.md` reference the run-order. Scheduled
  jobs run index quick/enrich/rotate + backfill-ids only.

### 3.6 Module-size constraints (guardrail blind spot)

`scripts/check-module-size.py`: soft warn 800 non-blank, hard block 1000
non-blank, **excludes all `__init__.py`**. Current WARN list (verified):
`scraper/movie_service.py` 954, `library/scanner.py` 855. `verify/checker.py` is
**716 non-blank** (825 total) — under the soft ceiling but adding `validator.py`'s
395 LOC would breach the 1000 hard block. **Blind-spot caution:** because
`__init__.py` is excluded, do NOT dump a re-homed module's body into a package
`__init__.py` to dodge the guardrail — that defeats it. Re-homed modules get
their own non-`__init__` files.

### 3.7 Target landing zones (verified absent / present)

- `personalscraper/insights/` — **does not exist** (to create).
- `personalscraper/maintenance/` — **does not exist** (to create).
- `personalscraper/nfo_utils.py` — **exists**, hosts `is_nfo_complete` (`:44`) —
  natural home for `parse_title_year` / `extract_nfo_ids` /
  `extract_nfo_metadata`.
- `indexer/scanner/_modes/backfill_ids_canonical.py` — **exists** — natural home
  for the unified canonical helper (or a new sibling `_canonical.py`).

---

## 4. Proposed design

### 4.1 Target architecture

```
personalscraper/
├── nfo_utils.py                         (MODIFIED — gains parse_title_year,
│                                          extract_nfo_ids, extract_nfo_metadata)
├── indexer/
│   └── scanner/
│       ├── _modes/
│       │   ├── full.py                  (MODIFIED — invokes new item stage before walk)
│       │   ├── _item_stage.py           (NEW — folds library media_item/season/
│       │   │                             episode/issue creation + _ensure_disk_row)
│       │   ├── _canonical.py            (NEW — single canonical_provider SSOT;
│       │   │                             absorbs _normalize_canonical_provider +
│       │   │                             init_canonical_from_nfo extraction)
│       │   ├── backfill_ids_canonical.py(MODIFIED — delegates to _canonical.py)
│       │   ├── enrich.py                (MODIFIED — gains HDR/Atmos fields OQ-2;
│       │   │                             season regex → naming_patterns SSOT)
│       │   └── incremental.py           (MODIFIED — season regex → SSOT)
│       └── release_linker.py            (MODIFIED — season regex → numbered SSOT helper)
├── dispatch/
│   └── media_index.py                   (MODIFIED — rebuild() delegates row creation
│                                          to the unified stage / shared helper; no
│                                          independent minimal-row upsert)
├── verify/
│   └── library_checks.py                (NEW — re-home of validator.py; standalone,
│                                          NOT inlined into checker.py)
├── insights/                            (NEW package)
│   ├── __init__.py
│   ├── models.py                        (re-home of library/models.py)
│   ├── analytics.py                     (re-home of analyze()/analyze_from_index())
│   ├── reporter.py                      (re-home of library/reporter.py)
│   ├── recommender.py                   (re-home of library/recommender.py)
│   └── rescraper.py                     (re-home of library/rescraper.py — OQ-5)
├── maintenance/                         (NEW package)
│   ├── __init__.py
│   └── disk_cleaner.py                  (re-home of library/disk_cleaner.py)
├── trailers/scanner.py                  (MODIFIED — season regex → SSOT;
│                                          NFO helper imports → nfo_utils)
├── commands/library/
│   ├── analyze.py                       (MODIFIED — importers repointed to insights/)
│   ├── maintenance.py                   (MODIFIED — importers repointed to
│   │                                      maintenance/ + verify/library_checks)
│   └── scan.py                          (MODIFIED — library-scan repoints to the
│                                          unified library-index --mode full stage)
└── library/                             (DELETED at end state)
```

### 4.2 Public import paths to preserve

CLI command names are non-goals to remove, but the **internal import surface
that external callers reach** is small and must be re-homed cleanly:

- `extract_nfo_ids`, `extract_nfo_metadata`, `parse_title_year` → new home
  `personalscraper.nfo_utils` (consumed by `trailers/scanner.py`,
  `rescraper.py`, `analyzer.py`/`analytics.py`). This is the only cross-package
  import surface; everything else is CLI wiring.
- `naming_patterns.SEASON_DIR_RE` stays the SSOT; `release_linker` needs a
  **numbered** variant — add a `season_number_from_dir(name) -> int | None`
  helper to `naming_patterns` rather than re-introducing a divergent
  capture-group regex.

### 4.3 The unified item stage (the crux)

`indexer/scanner/_modes/_item_stage.py` performs the directory-metadata pass
that today lives in `library/scanner.py`: for each media directory under each
category, read the NFO, build the `media_item` row (rich: seasons, episodes,
`canonical_provider`, `dispatch_path`/`disk`/`norm_title` attrs), upsert via
`item_repo.upsert` + `upsert_attr`, and persist `item_issue` rows. `full.py`
invokes this stage **before** the file walk so a single `library-index --mode
full` reaches the same DB end-state as today's `library-scan` + `library-index`
sequence.

**Decision — stage inside `ScanMode.full`, not a new mode.** A new `--mode
items` would re-introduce a two-step run, defeating the consolidation. The stage
inside `full` keeps one self-sufficient command. Rationale matches the source
analysis §6.

**Decision — `dispatch/media_index.rebuild()` delegates to a shared row-builder,
not its own upsert.** The `_item_stage` row-construction logic is extracted into
a reusable function (e.g. `build_item_row(nfo, dir, …)` +
`upsert_item_with_attrs(conn, row, …)`) that BOTH `_item_stage` and
`MediaIndex.rebuild()` call, eliminating the third write pattern. The dispatch
auto-rebuild thus produces rich rows (resolves the
`canonical_provider=None`/no-seasons degradation). See OQ-1 for the alternative
(keep rebuild as a degraded fast-path).

**Behaviour to preserve (regression-tested):**

- `dispatch_path` / `disk` / `norm_title` attrs — trailers + `release_linker`
  INNER JOINs depend on them.
- `item_issue` persistence.
- DEV #50 disk-row label/uuid reconciliation (`_ensure_disk_row`,
  `scanner.py:851`).
- Identical `media_item` count and content vs the legacy two-step.

### 4.4 Canonical-provider SSOT

`_canonical.py` exposes one extractor consumed by `_item_stage` and
`backfill_ids_canonical`. It absorbs `_normalize_canonical_provider`
(`scanner.py:69`) and the `<uniqueid default="true">` extraction with
unsupported-default fallback from `init_canonical_from_nfo`. The 194-show
regression test (`tests/indexer/scanner/test_init_canonical.py`) is carried
forward verbatim and a new test pins the unified helper's TV→TVDB / movie→TMDB
family rule.

### 4.5 ffprobe → enrich fold

`enrich.py` already persists to `media_stream` via `MediaInfoWrapper`
(pymediainfo). The ffprobe path in `analyzer.py` (`extract_stream_info`,
`scraper/mediainfo.py`) carries HDR (`analyzer.py:412-414`) and Atmos
(`is_atmos`) fidelity that the enrich path does not persist
(`analyzer.py:451-453` documents the gap). **Decision deferred to OQ-2:** either
add nullable `hdr` / `hdr_type` / `is_atmos` columns to `media_stream` (in place,
re-index, no migration script) and populate them in `enrich.py`, OR accept the
documented loss. Either way, `analyze_from_index()` becomes the sole stream
reader after the fold; `analyze_library()`/`extract_stream_info` are deleted from
the library path. (`scraper/mediainfo.extract_stream_info` itself stays — NFO
generation still uses it; only the library deep-scan caller is removed.)

---

## 5. Phasing

Lifecycle: `/implement:feature` → branch `feat/lib-fold`; SemVer **minor** (Y+1:
0.16.0 → 0.17.0) bumped at `create-branch`; Conventional Commits scoped
`(lib-fold)`; each phase ends on `chore(lib-fold): phase N gate — …` with
`make lint && make test && make check` all green; squash merge. Strict order:
**0 → 1 → 2 → 3(a→b) → 4 → 5 → 6**. No migration scripts (re-index in place).
Regression-test-per-bug throughout. Module-size hard ceiling 1000 non-blank
(never dodge via `__init__.py`).

### Phase 0 — Season-dir regex SSOT + `_VIDEO_EXTENSIONS` cleanup (warm-up)

- **Objective:** Collapse the five season-dir regexes onto
  `naming_patterns.SEASON_DIR_RE`; drop the local `_VIDEO_EXTENSIONS` in
  `disk_cleaner.py:42` in favour of `sorter.file_type.VIDEO_EXTENSIONS`.
- **Create:** `naming_patterns.season_number_from_dir()` (numbered helper for
  `release_linker`); `tests/.../test_season_dir_regex_ssot.py`.
- **Modify:** `library/disk_cleaner.py:42,68-69`,
  `indexer/scanner/_modes/enrich.py:122-123`,
  `indexer/scanner/_modes/incremental.py:635-636`,
  `indexer/release_linker.py:34,49` (use numbered helper),
  `trailers/scanner.py:27,354` (canonical regex changes behaviour for
  1/3-digit + English folders — regression test must assert the _new correct_
  behaviour, not equality).
- **Sub-tasks:** add numbered helper + tests; migrate each call site; pin a test
  asserting `Saison 1`, `Saison 01`, `Season 1`, `Specials` all match.
- **Effort:** S · **Risk:** low (trailers/release_linker behaviour change is the
  only non-trivial bit) · **Deps:** none.
- **Gate:** `make lint && make test && make check` green;
  `rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/` returns
  zero.

### Phase 1 — Extract NFO helpers to `nfo_utils` (unblock deletion)

- **Objective:** Move `extract_nfo_ids`, `extract_nfo_metadata`,
  `parse_title_year` out of `library/scanner.py` so external/internal importers
  stop depending on the to-be-deleted module.
- **Modify:** `nfo_utils.py` (add three functions + docstrings);
  `trailers/scanner.py:16`, `library/analyzer.py:42`, `library/rescraper.py:36-38`
  (repoint imports). Leave thin re-export shims in `library/scanner.py` ONLY if
  needed mid-phase — preferred is direct repoint (no back-compat shim, per
  `feedback_no_backcompat_before_v1`).
- **Create:** `tests/.../test_nfo_helpers_rehome.py` (one test per moved
  function).
- **Effort:** M · **Risk:** low · **Deps:** Phase 0.
- **Gate:** `make ... ` green;
  `rg -t py 'from personalscraper.library.scanner import (extract_nfo|parse_title)' personalscraper/ tests/`
  returns zero.

### Phase 2 — Build the unified item stage; keep `scan_library` calling it (Phase 3a)

- **Objective:** Stand up `_item_stage.py` + `_canonical.py` with full tests
  WITHOUT yet deleting the library path — `scan_library` is rewired to call the
  new stage so behaviour is identical and every gate stays green.
- **Create:** `indexer/scanner/_modes/_item_stage.py`
  (`build_item_row`, `upsert_item_with_attrs`, season/episode upsert,
  `_detect_issues`, `_ensure_disk_row` moved from `scanner.py:851`);
  `indexer/scanner/_modes/_canonical.py` (unified canonical extractor);
  characterization test capturing legacy `media_item` DB end-state on a fixture;
  canonical 194-show guard carried forward; DEV #50 disk-row dedup test.
- **Modify:** `library/scanner.py` `scan_library` to call `_item_stage`;
  `backfill_ids_canonical.py` to delegate to `_canonical.py`; `full.py` to invoke
  `_item_stage` before the walk (behind a flag if needed so legacy path still
  exercisable for the equivalence test).
- **Effort:** XL · **Risk:** high (the crux) · **Deps:** Phase 1.
- **Gate:** `make ...` green; characterization test proves
  `library-index --mode full` DB end-state == legacy two-step on the fixture.

### Phase 3 — Reconcile the dispatch second-writer; wire `library-scan` to the stage; delete the old path (Phase 3b + 4)

- **Objective:** Make `MediaIndex.rebuild()` delegate to the shared row-builder
  (rich rows, no minimal `canonical_provider=None` upsert); repoint
  `library-scan` to `library-index --mode full`; delete `library/scanner.py`.
- **Modify:** `dispatch/media_index.py:397-435,437` (delegate to
  `upsert_item_with_attrs`); `dispatch/run.py` auto-rebuild path unchanged in
  signature; `commands/library/scan.py` (`library-scan` → unified entry, command
  name preserved); **delete** `library/scanner.py`.
- **Create regression tests:** dispatch auto-rebuild now yields rich rows
  (non-null `canonical_provider`, seasons present) — pin this as a bug-reproducer
  for the prior degradation; re-home unique `scanner` test coverage to the new
  stage.
- **Effort:** L · **Risk:** high · **Deps:** Phase 2.
- **Gate (mandatory residual grep):**
  `rg -t py 'library.scanner|scan_library' personalscraper/ tests/` returns zero;
  `make ...` green.

### Phase 4 — ffprobe fold into enrich; `insights/` package

- **Objective:** One stream backend; read-only analytics/report/recommender
  re-homed.
- **Create:** `insights/__init__.py`, `insights/models.py` (from
  `library/models.py`), `insights/analytics.py` (`analyze`/`analyze_from_index`),
  `insights/reporter.py`, `insights/recommender.py`; OQ-2 columns in
  `media_stream` + enrich population (if chosen).
- **Modify:** `library/analyzer.py` → delete `analyze_library` (ffprobe);
  `enrich.py` (HDR/Atmos population if OQ-2=extend); `commands/library/analyze.py`
  importers → `insights/`.
- **Delete:** `library/analyzer.py`, `library/models.py`, `library/reporter.py`,
  `library/recommender.py`.
- **Effort:** L · **Risk:** medium (HDR/Atmos fidelity — OQ-2) · **Deps:** Phase 3.
- **Gate:** `rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/`
  returns zero; `make ...` green.

### Phase 5 — `validator` → `verify/library_checks`; `disk_cleaner` → `maintenance/`; `rescraper` re-home; delete `library/`

- **Objective:** Empty and remove the `library/` package.
- **Create:** `verify/library_checks.py` (standalone module, NOT inlined into
  `checker.py` — guards the 1000 hard ceiling); `maintenance/__init__.py`,
  `maintenance/disk_cleaner.py` (FS `rmtree` + NTFS ghost + outbox
  write-through); `insights/rescraper.py` (or `maintenance/` — OQ-5).
- **Modify:** `commands/library/maintenance.py` importers; any remaining
  importers.
- **Delete:** `library/validator.py`, `library/disk_cleaner.py`,
  `library/rescraper.py`, `library/__init__.py` → the whole `library/` package.
- **Effort:** L · **Risk:** medium · **Deps:** Phase 4.
- **Gate:** `rg -t py 'personalscraper.library' personalscraper/ tests/` returns
  zero; `test ! -d personalscraper/library`;
  `python3 scripts/check-module-size.py` exit 0 (no module ≥ 1000 non-blank);
  `make ...` green.

### Phase 6 — Feature PR + review (auto-invoked)

- `/implement:feature-pr` (local gate + push + PR + CI poll) then
  `/implement:pr-review` (review + fix cycles + squash merge) per the standard
  lifecycle. Docs updated: `docs/reference/commands.md` (remove the implicit
  run-order note; `library-index --mode full` is self-sufficient),
  `docs/reference/architecture.md` (module map: `library/` removed, `insights/` +
  `maintenance/` added), `docs/reference/indexer.md` (item stage),
  `CHANGELOG.md` 0.17.0 entry.

---

## 6. Acceptance criteria (SH-16 — executable commands + documented expected output)

```bash
# ACC-00  Phase 0 — no ad-hoc season-dir regex constant left in the migrated files
rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/ ; echo "rc=$?"
# Expected: no output, then  rc=1   (rg exit 1 = no matches)

# ACC-00b Phase 0 — canonical pattern matches every season form
python -c "from personalscraper.naming_patterns import SEASON_DIR_RE as r; assert all(r.match(s) for s in ['Saison 1','Saison 01','Season 1','Specials']); print('OK')"
# Expected: OK

# ACC-00c Phase 0 — numbered helper extracts the season number
python -c "from personalscraper.naming_patterns import season_number_from_dir as f; assert f('Saison 3')==3 and f('Season 12')==12 and f('Specials') in (0,None); print('OK')"
# Expected: OK

# ACC-01  Phase 1 — no importer reaches into library.scanner for NFO helpers
rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/ ; echo "rc=$?"
# Expected: no output, then  rc=1

# ACC-01b Phase 1 — helpers callable from the new home
python -c "from personalscraper.nfo_utils import parse_title_year, extract_nfo_ids, extract_nfo_metadata; print('OK')"
# Expected: OK

# ACC-02  Phase 2 — unified item stage module exists and is importable
python -c "import personalscraper.indexer.scanner._modes._item_stage as s; print('OK')"
# Expected: OK

# ACC-02b Phase 2 — canonical SSOT module exists; backfill delegates to it
python -c "import personalscraper.indexer.scanner._modes._canonical; print('OK')"
rg -t py '_normalize_canonical_provider' personalscraper/ ; echo "rc=$?"
# Expected: OK ; then (after Phase 3 deletes scanner.py) no output, rc=1

# ACC-03  Phase 3 — library/scanner.py and scan_library fully removed
test ! -f personalscraper/library/scanner.py && echo "deleted"
rg -t py 'library.scanner|scan_library' personalscraper/ tests/ ; echo "rc=$?"
# Expected: deleted    then no output, then  rc=1

# ACC-03b Phase 3 — dispatch auto-rebuild produces rich rows (no canonical_provider=None default)
rg -t py 'canonical_provider=None' personalscraper/dispatch/media_index.py ; echo "rc=$?"
# Expected: no output, then  rc=1

# ACC-04  Phase 4 — ffprobe stream extraction removed from library/insights
rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/ ; echo "rc=$?"
# Expected: no output, then  rc=1   (the helper survives only under scraper/ for NFO gen)

# ACC-04b Phase 4 — insights package importable; library-analyze still works on an enriched fixture
python -c "from personalscraper.insights import analytics, reporter, recommender, models; print('OK')"
# Expected: OK

# ACC-05  Phase 5 — validator landed in verify, not inlined into checker.py
test -f personalscraper/verify/library_checks.py && echo "present"
python3 scripts/check-module-size.py | rg -i 'checker.py' ; echo "rc=$?"
# Expected: present ; then no output (checker.py not over ceiling), rc=1

# ACC-05b Phase 5 — disk_cleaner re-homed to maintenance/, not repair.py
test -f personalscraper/maintenance/disk_cleaner.py && echo "present"
rg -t py 'rmtree|_scandir_rmtree' personalscraper/indexer/repair.py ; echo "rc=$?"
# Expected: present ; then no output (no FS rmtree leaked into DB-only repair), rc=1

# ACC-06  End state — library/ package fully gone
rg -t py 'personalscraper.library' personalscraper/ tests/ ; echo "rc=$?"
test ! -d personalscraper/library && echo "package removed"
# Expected: no output, then rc=1 ; then  package removed

# ACC-06b Module-size hard ceiling respected (no module >= 1000 non-blank)
python3 scripts/check-module-size.py ; echo "rc=$?"
# Expected: rc=0

# ACC-07  Version bump
cat VERSION ; echo "rc=$?"
# Expected: 0.17.0 ; rc=0

# ACC-08  CHANGELOG entry
grep -c '^## \[0.17.0\]' CHANGELOG.md
# Expected: 1

# ACC-GATE  every phase gate
make lint && make test && make check ; echo "rc=$?"
# Expected: ruff+mypy clean, "NNNN passed" with 0 failed/errors, branch coverage >= 90%; rc=0

# ACC-SMOKE
python -c "import personalscraper; print('import-ok')"
# Expected: import-ok
```

---

## 7. Risks & mitigations

| Risk                                                                              | Sev    | Mitigation                                                                                                                                                                         |
| --------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Folding `media_item` creation half-breaks the DB end-state vs the legacy two-step | High   | Phase 2 ships a characterization test asserting DB-row equality on a fixture BEFORE deleting the legacy path; Phase 3 only deletes once equality holds.                            |
| `canonical_provider` SSOT merge re-opens the 194-show regression                  | High   | Carry `tests/indexer/scanner/test_init_canonical.py` forward verbatim; add a unified-helper test pinning TV→TVDB / movie→TMDB. Treat any failure as a stop-the-line bug.           |
| Dispatch auto-rebuild diverges (third write pattern)                              | High   | Single shared `upsert_item_with_attrs`; ACC-03b grep gate forbids `canonical_provider=None` reappearing.                                                                           |
| HDR/Atmos fidelity silently lost when ffprobe is dropped                          | Medium | OQ-2 decided BEFORE Phase 4. If "extend", add nullable columns in place + populate in enrich + a test asserting HDR/Atmos round-trip. If "accept", document in CHANGELOG + DESIGN. |
| Season-regex change in `trailers`/`release_linker` alters placement behaviour     | Medium | Phase 0 regression tests assert the NEW correct behaviour for 1/3-digit + English + Specials, not mere equality.                                                                   |
| Test re-homing (~9773 LOC / 16 files) drops branch coverage below 90%             | Medium | Each phase's gate runs `make check` (coverage included); migrate unique coverage, don't just delete.                                                                               |
| `models.py` is consumed by two CLI surfaces — wrong home splits importers         | Low    | Land in `insights/models.py` (read-only model home); both analyze.py and maintenance.py repoint there.                                                                             |
| Module-size guardrail dodge via `__init__.py`                                     | Low    | Convention: re-homed bodies go in named non-`__init__` files; ACC-06b gate.                                                                                                        |

---

## 8. Open questions (for the user)

- **OQ-1:** Should `dispatch/media_index.rebuild()` be fully replaced by the
  shared row-builder (one creation path, rich rows always), or kept as a
  degraded fast-path for the empty-DB auto-rebuild so dispatch can run without a
  prior `library-index`? (Recommended: shared builder — eliminates the
  degradation; the fast-path "speed" benefit is marginal pre-1.0.)
- **OQ-2:** Extend `media_stream` with nullable `hdr` / `hdr_type` / `is_atmos`
  columns (re-index in place, no migration script) to preserve HDR/Atmos
  fidelity, OR accept the documented loss when ffprobe is dropped?
  (`analyzer.py:451-453`.) (Recommended: extend — cheap pre-1.0, avoids a silent
  metadata regression.)
- **OQ-3:** Deliver as one `feat/lib-fold` minor, or split Phase 0–1 into a
  preliminary `fix/` first? (Recommended: single minor — 0/1 naturally precede
  the heavy lift; splitting adds release overhead for no real benefit.)
- **OQ-4:** Keep `library-scan` as a re-pointed alias of
  `library-index --mode full` (ROADMAP non-goal forbids removing commands), or
  hide it from `--help` while keeping it callable? (Recommended: keep callable;
  hide from help to discourage the now-redundant two-step.)
- **OQ-5:** `rescraper.py` (targeted TMDB/TVDB repairs — a _write_ operation) —
  land in `insights/` (read-mostly) or `maintenance/` (mutation)? It performs
  scraping repairs, not pure reads, which argues for `maintenance/`; but it is
  invoked from `library-analyze`, which argues for `insights/`. (Recommended:
  `maintenance/rescraper.py` — its semantics are mutation, and the CLI import is
  trivially repointed.)

---

## 9. References

- **Source analysis:** `docs/analysis/01-library-indexer-consolidation.md`
  (full evidence base; this DESIGN supersedes its phasing §4 with
  implementation-grade detail).
- **ROADMAP entry:** `ROADMAP.md:32-62` (P1 — Library / Indexer Consolidation,
  with the verified premise correction).
- **Structural template:** `docs/features/registry/DESIGN.md` (section style +
  ACCEPTANCE format mirrored here).
- **Sibling designs / dependencies:**
  - `ROADMAP.md` P2 — Verify Checker Plugin System (the eventual registry for
    `verify/library_checks.py`).
  - `ROADMAP.md` arch-cleanup-2 — `sorter.file_type` SSOT move (eases the
    `_VIDEO_EXTENSIONS` cleanup in Phase 0).
- **Project rules (CLAUDE.md):** SH-16 ACCEPTANCE format; module-size soft 800 /
  hard 1000 non-blank (excludes `__init__.py`); regression-test-per-bug.
- **Memory:** `feedback_no_backcompat_before_v1` (no migration scripts, no
  façades — re-index in place); `feedback_multi_provider_ids_separation` (canonical
  family separation — guards the 194-show regression);
  `feedback_regression_test_per_bug`.
- **Reference docs (lazy-load):** `docs/reference/indexer.md`,
  `docs/reference/indexer-json-shapes.md`, `docs/reference/scraping.md`,
  `docs/reference/storage.md`.
