# Library / Indexer Consolidation

> **Metadata** — Date: 2026-05-28 · Project version: 0.16.0 · Branch context: `feat/registry` (analysis only; implementation work happens on its own `feat/{codename}` branch) · Project status: pre-1.0, single mono-user instance, **not in production** (no migration scripts allowed) · Report scope: ROADMAP **P1 — Library / Indexer Consolidation** (`ROADMAP.md:39-58`) · Confidence: **high** (every LOC count, call-site, and line anchor below was re-verified against the working tree; the fact-check corrections are incorporated).

---

## 1. Executive summary (TL;DR)

- **The ROADMAP P1 premise is wrong on its central claim.** `ROADMAP.md:41` says `library/scanner.py` is "duplicating walk logic that the indexer scanner already has." It is not. `library/scanner.py:902` `scan_library()` walks only at **media-directory granularity** (`sorted(category_dir.iterdir())`, `scanner.py:965`) and then **delegates** the recursive file-level walk to `indexer.scanner.scan(mode=ScanMode.full)` at `scanner.py:996-1003`. The two walks are at orthogonal granularities. A plan written against the ROADMAP wording would mis-scope the work.
- **The ROADMAP LOC numbers are stale.** It states `library/scanner.py` "726 LOC" and "`library/` ... totals 4565 LOC" (`ROADMAP.md:41`). Actual: `scanner.py` is **1003 LOC**; `library/` is **4888 LOC**. The entry has drifted since it was authored — another reason to rewrite it (Phase 1).
- **`library/scanner.py` is a load-bearing creator, but NOT the *sole* creator of `media_item` rows.** There are **two** non-backfill `item_repo.upsert` call sites against the indexer DB: `library/scanner.py:691` (rich, NFO-derived rows with seasons/episodes + `canonical_provider`) and `dispatch/media_index.py:406` inside `MediaIndex.rebuild()` (minimal rows, `canonical_provider=None`, no seasons, `find_by_normalized_name` dedup first at `media_index.py:397`). The dispatch path auto-rebuilds on an empty DB (`dispatch/run.py:128`, `MediaIndex(..., auto_rebuild=...)`). The consolidation must reconcile **both** writers.
- **Genuine duplication is narrower than the ROADMAP claims.** Real overlaps: (a) two MediaInfo backends — ffprobe (`library/analyzer.py:44`) vs pymediainfo (`indexer/scanner/_modes/enrich.py:13`); (b) **five** independently-compiled season-dir regexes that diverge subtly; (c) canonical-provider extraction logic exists in BOTH `library/scanner.py:69` and `indexer/scanner/_modes/backfill_ids_canonical.py`. The ROADMAP's "reconciliation overlap" and "cleaner vs dedup" are **false / overstated**: `reconcile.py`/`drift.py` live only in `indexer/` with no `library/` counterpart, and `disk_cleaner.py` does real FS `rmtree` that has no indexer analog (`repair.py:382` `soft_delete_subtree` is DB-only).
- **Blast radius is small but test surface is large.** Only `trailers/scanner.py:16` imports `library.*` from outside the package (2 helpers). But test re-homing is **~9773 LOC across 16 importing test files** (verified by `rg -ln 'personalscraper.library' tests/ | xargs wc -l`), not the ~7549 implied earlier.

**Verdict:** P1 is a legitimate, high-value cleanup, but it **must be re-scoped before any code moves**. The canonical subsystem is the indexer. `library/scanner.py`'s `media_item` creation must be **moved into a new indexer scan stage**, not deleted; `dispatch/media_index.py` rebuild must be folded into or superseded by that same stage. Proceed as a **minor** SemVer feature delivered in sequenced phases, each independently green under `make check`.

---

## 2. Current state (evidence-backed)

### 2.1 The two subsystems and their actual relationship

| Subsystem | Granularity | Creates `media_item`? | Entry point |
| --- | --- | --- | --- |
| `library/scanner.py` `scan_library()` | category → media-dir (`sorted(category_dir.iterdir())`, `scanner.py:965`) | **YES** — `item_repo.upsert` at `scanner.py:691`, plus seasons/episodes, `canonical_provider`, `dispatch_path`/`disk`/`norm_title` attrs, `item_issue` rows | `commands/library/scan.py:255` `library-scan` → `scan_library()` (`scan.py:352`) |
| `indexer/scanner/` `scan()` | recursive file tree (`os.scandir` in `_walker.py:273,433,673`) | **NO** — `enrich.py` only `UPDATE`s existing rows (`enrich.py:417,422,427`); `release_linker.py` only `SELECT`s (`:144,163,173`) | `commands/library/scan.py:19` `library-index` → `personalscraper.indexer.cli.library_index_command` (`scan.py:81,104`) |
| `dispatch/media_index.py` `MediaIndex.rebuild()` | disk dir scan via `dispatch/disk_scanner.py` | **YES (second creator)** — `item_repo.upsert` at `media_index.py:406`, minimal rows, dedup via `find_by_normalized_name` (`media_index.py:397`) | `dispatch/run.py:128` (auto-rebuild on empty DB) |

`scan_library()` delegates the heavy walk explicitly:

```python
# personalscraper/library/scanner.py:996-1003
_indexer_scan(
    disks=disk_rows,
    mode=ScanMode.full,
    generation=next_generation,
    conn=conn,
    event_bus=event_bus,
)
```

**Implicit run-order dependency:** to fully populate the DB today a user runs `library-scan` (creates rows) *then* `library-index` (populates files/streams). This ordering is *partially* documented at `docs/reference/commands.md:46-47` (`library-index` = "scan disks into the indexer DB", `library-scan` = "NFO-based row creation") with a cross-link at `commands.md:499`. It is not stated in the CLI `--help` strings.

### 2.2 Module inventory (verified LOC, `wc -l`)

`personalscraper/library/` — **4888 LOC** total:

| Module | LOC | Role |
| --- | --- | --- |
| `scanner.py` | 1003 | media-dir walk; SOLE `library` `media_item` creator (`:691`); `_normalize_canonical_provider` (`:69`); delegates file walk (`:996`); disk-row reconciliation (`:851`); exports `extract_nfo_ids`/`extract_nfo_metadata`/`parse_title_year` |
| `analyzer.py` | 824 | `analyze()` DB aggregate (`:143`); `analyze_library()` ffprobe deep-scan (`:690`, imports `scraper.mediainfo.extract_stream_info` at `:44`); `analyze_from_index()` reads `media_stream` (`:436`) — the duplication bridge; also imports `parse_title_year` from `library.scanner` (`:42`) |
| `rescraper.py` | 677 | targeted TMDB/TVDB repairs; imports `SEASON_DIR_RE` locally (`:397`) |
| `models.py` | 597 | dataclasses (`MediaFileAnalysis`, `VideoInfo`, etc.) |
| `disk_cleaner.py` | 571 | real FS `rmtree` (`_scandir_rmtree:165`) + NTFS ghost-dirent handling + outbox write-through (`_publish_deleted:118`); local `_VIDEO_EXTENSIONS` (`:42`) + `_TV_SEASON_DIR_RE` (`:68`) |
| `reporter.py` | 519 | read-only report rendering |
| `validator.py` | 395 | wraps `verify.checker.MediaChecker` + `verify.fixer.MediaFixer` (`:31`) |
| `recommender.py` | 295 | read-only recommendations |
| `__init__.py` | 7 | |

`personalscraper/indexer/scanner/` — **7055 LOC** total: **11 top-level files** (3517 LOC: `__init__.py` 679, `_walker.py` 777, plus `_checkpoint`, `_concurrency`, `_db_writes`, `_exclusions`, `_index_ddl`, `_scan_orchestrator`, `_shutdown`, `_spotlight`, `_types`) + `_modes/` with **8 mode implementations**: `full`, `quick`, `incremental`, `enrich` (707), `verify`, `backfill`, `backfill_ids`, **`backfill_ids_canonical`**.

Other indexer pieces: `reconcile.py` (578, DB-only structural drift, complements `ScanMode.verify`), `drift.py` (635, per-file in-scan reconciliation engine), `fingerprint.py` (237, tier1/OSHash/xxh3 SSOT — consumed by `_walker.py`, `_modes/enrich.py`, `_db_writes.py`, `drift.py`, *not* solely `drift.py`), `repair.py` (499, DB-only `soft_delete_subtree:382`).

### 2.3 The canonical_provider overlap (Phase-3 landmine)

`library/scanner.py:69` `_normalize_canonical_provider()` exists specifically to guard the **194-show regression** (Phase 14.1, reopen 12.1 — see docstring `scanner.py:82-84`): NFOs may carry a `<uniqueid default="true">` whose family disagrees with the SSOT (TV → TVDB primary, movies → TMDB primary). **The same concept already exists in the indexer**: `indexer/scanner/_modes/backfill_ids_canonical.py` (`init_canonical_from_nfo`) extracts a canonical anchor from `<uniqueid default="true">` with a documented fallback when the default is unsupported. These two implementations are not currently shared; any Phase 3 move MUST reconcile them into one SSOT.

### 2.4 Five divergent season-dir regexes (SSOT violation)

The canonical pattern is `naming_patterns.SEASON_DIR_RE` (`naming_patterns.py:172`). It is correctly imported by `verify/checker.py`, `scraper/*`, `enforce/structure_validator.py`, `library/scanner.py:63`, `library/rescraper.py:397`. But **five** ad-hoc copies exist:

| Location | Pattern (verbatim) |
| --- | --- |
| `library/disk_cleaner.py:68` | `^(?:saison|season)\s*\d+$|^specials?$` |
| `indexer/scanner/_modes/incremental.py:635` | `^(?:saison|season)\s*\d+$|^specials?$` |
| `indexer/scanner/_modes/enrich.py:122` | `^(?:saison|season)\s*\d+$|^specials?$` |
| `indexer/release_linker.py:34` | `^Sa[ie]son\s+(\d+)$|^Season\s+(\d+)$` (capture groups; no `specials`) |
| `trailers/scanner.py:27` | `^Saison (\d{2})$` (**2-digit only**, no `specials`, no `Season`) |

`release_linker.py:34` (capture groups + no `Specials`) and `trailers/scanner.py:27` (2-digit-only) are functionally divergent — a latent bug for single-digit / 3-digit / `Specials` season folders.

### 2.5 Consumer / blast-radius map

- **External `library.*` importers (outside the package):** only `trailers/scanner.py:16` → `from personalscraper.library.scanner import extract_nfo_ids, parse_title_year`. (CLI modules `commands/library/{analyze,maintenance,scan}.py` are the wiring layer, expected.)
- **Internal cross-coupling to delete-later modules:** `library/analyzer.py:42` imports `parse_title_year` from `library.scanner`; `library/rescraper.py` imports `extract_nfo_ids`/`parse_title_year` from `library.scanner`.
- **Tests:** **16** test files import `personalscraper.library` (**9773 LOC**); **103** import `personalscraper.indexer` (**43419 LOC**).
- **No cron/launchd job runs `library-scan`.** `launchd-plists/com.personalscraper.backfill-ids.plist` runs `library-backfill-ids`; `docs/reference/launchd/*.plist` run index quick/enrich/rotate. The pipeline-monitor matrix does not reference `library-scan`/`scan_library`. So Phases 3/4 update no scheduled job — only the operator's manual workflow and `commands.md`.

---

## 3. Problems & risks (prioritised)

| Sev | Problem | Evidence |
| --- | --- | --- |
| **Critical** | Two uncoordinated `media_item` creators with different richness. Deleting `library/scanner.py` before folding its creation into the indexer degrades row quality (dispatch rebuild creates rows with `canonical_provider=None`, no seasons). | `library/scanner.py:691` vs `dispatch/media_index.py:406`; `dispatch/run.py:128` auto-rebuild |
| **Critical** | `canonical_provider` SSOT split: `_normalize_canonical_provider` (library) vs `init_canonical_from_nfo` (indexer). Divergence re-opens the 194-show regression. | `library/scanner.py:69`, `indexer/scanner/_modes/backfill_ids_canonical.py` |
| **High** | ROADMAP P1 premise inaccurate + LOC stale. Implementing literally would mis-scope and risk deleting the rich row creator. | `ROADMAP.md:41` ("726 LOC", "4565 LOC", "duplicating walk logic") |
| **High** | Duplicate MediaInfo backends (ffprobe vs pymediainfo) with near-identical output shapes; merging risks HDR/Atmos fidelity loss — `analyze_from_index` already documents missing fields. | `library/analyzer.py:44,690`, `enrich.py:13`, `analyzer.py:447-457` (HDR not stored; Atmos approximated) |
| **High** | `trailers/scanner.py:16` imports `extract_nfo_ids`/`parse_title_year` from a module slated for deletion — silent runtime break if removed first. | `trailers/scanner.py:16` |
| **Medium** | Five divergent season-dir regexes (two functionally different). | §2.4 |
| **Medium** | `disk_cleaner.py` is destructive FS code; ROADMAP suggests merging into `repair.py` (DB-only) — would mix FS-mutation with DB-mutation. | `disk_cleaner.py:165`, `repair.py:382` |
| **Medium** | Module-size hard ceiling. `verify/checker.py` is already **788 LOC** (over the 800 soft-warn imminently); merging `validator.py` (395) into it would blow the 1000 hard ceiling. | `wc -l verify/checker.py` = 788; `scripts/check-module-size.py` |
| **Medium** | Test re-homing burden ~9773 LOC across 16 files; under-migration drops branch coverage below the 90% `make check` gate. | §2.5 |

---

## 4. Implementation plan

**Suggested codename:** `lib-fold` · **SemVer bump:** **minor** (Y+1; new internal scan stage + package moves, no public CLI removed) · **Branch:** `feat/lib-fold` · **Merge:** squash. Each phase ends on a `chore(lib-fold): phase N gate — …` commit with `make lint && make test && make check` all green.

Pre-1.0 rules apply throughout: **no migration scripts** — DB/NFO/config evolve in place; the single instance is re-indexed by re-running `library-index`.

### Phase 0 — SSOT cleanup of season-dir regex + VIDEO_EXTENSIONS (warm-up)

- **Objective:** Eliminate the five ad-hoc season-dir regexes and the local `_VIDEO_EXTENSIONS`; single source = `naming_patterns.SEASON_DIR_RE` and `sorter.file_type.VIDEO_EXTENSIONS`.
- **Modify:** `library/disk_cleaner.py` (drop `:42` `_VIDEO_EXTENSIONS`, drop `:68` `_TV_SEASON_DIR_RE`, use canonical imports), `indexer/scanner/_modes/incremental.py:635`, `indexer/scanner/_modes/enrich.py:122`, `indexer/release_linker.py:34`, `trailers/scanner.py:27`. **Caution:** `release_linker.py` uses *capture groups* to extract the season number — replace with a numbered helper from `naming_patterns` (add one if absent rather than re-diverging). `trailers/scanner.py:27` is 2-digit-only — switching to the canonical regex changes behaviour for 1/3-digit folders; add a regression test asserting the new behaviour is correct for trailer placement.
- **Create:** `tests/.../test_season_dir_regex_ssot.py` — regression test pinning that `Saison 1`, `Saison 01`, `Season 1`, `Specials` all match the canonical pattern and that each migrated call site behaves identically (or correctly, for trailers).
- **Effort:** S · **Risk:** low · **Deps:** none.

### Phase 1 — Rewrite the ROADMAP P1 entry + author DESIGN before any code moves

- **Objective:** Ground the plan in reality before `/implement:feature`.
- **Modify:** `ROADMAP.md:39-58` — remove "duplicating walk logic that the indexer scanner already has"; remove stale LOC ("726"/"4565"); add the **two-creator** fact (`library/scanner.py:691` + `dispatch/media_index.py:406`); reframe goals as: (a) fold `library` `media_item`/season/episode creation into a new indexer scan stage AND reconcile with `dispatch/media_index.rebuild`; (b) merge `analyzer` ffprobe into `enrich`; (c) move `reporter`+`recommender` to `insights/`; (d) move `validator` checks into `verify/`; (e) re-home `disk_cleaner` to `maintenance/` (NOT `repair.py`); (f) reconcile `_normalize_canonical_provider` with `backfill_ids_canonical`. Note the ROADMAP non-goal "Removing any CLI commands" (`ROADMAP.md:55`) — `library-scan` stays as a command name.
- **Create:** `docs/features/lib-fold/DESIGN.md` via `/implement:brainstorm`.
- **Effort:** S · **Risk:** low · **Deps:** Phase 0.

### Phase 2 — Extract leaked helpers to a shared home (unblock deletion)

- **Objective:** Move `extract_nfo_ids`, `extract_nfo_metadata`, `parse_title_year` out of `library/scanner.py` so external/internal importers no longer depend on the to-be-deleted module.
- **Target:** `personalscraper/nfo_utils.py` (already hosts `is_nfo_complete`) or a new `personalscraper/naming/title_year.py`. Update importers to the new path.
- **Modify:** `trailers/scanner.py:16`, `library/analyzer.py:42`, `library/rescraper.py`, plus any `library/*` internal users.
- **Create:** `tests/.../test_nfo_helpers_rehome.py` — one regression test per moved function.
- **Gate:** `rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/` returns zero.
- **Effort:** M · **Risk:** low · **Deps:** Phase 1.

### Phase 3 — Fold `media_item`/season/episode creation into a unified indexer scan stage (heavy lift)

- **Objective:** Make `library-index --mode full` self-sufficient: create rich `media_item`/season/episode rows + attrs + issues, then run the file walk. Reconcile the **second creator** (`dispatch/media_index.rebuild`) so it either calls the same stage or is reduced to a thin wrapper that no longer needs its own minimal-row upsert (avoid a *third* write pattern).
- **Create:** `personalscraper/indexer/scanner/_modes/_item_stage.py` (or a directory-metadata pass invoked by `_modes/full.py` before the walk). Move from `library/scanner.py`: `_upsert_media_item`, season/episode upsert, `_detect_issues`, `scan_movie_dir`/`scan_tvshow_dir`, `_ensure_disk_row` (DEV #50 disk-row label/uuid reconciliation, `scanner.py:851`).
- **Reconcile canonical_provider:** unify `_normalize_canonical_provider` (`scanner.py:69`) with `backfill_ids_canonical.init_canonical_from_nfo` into ONE helper (e.g. `indexer/canonical.py` or inside `backfill_ids_canonical.py`); carry the 194-show regression test forward verbatim.
- **Preserve behaviour:** `dispatch_path`/`disk`/`norm_title` attrs (trailers + `release_linker` INNER JOIN depend on them); `item_issue` persistence; identical DB end-state to today's `library-scan` + `library-index` sequence.
- **Modify:** `dispatch/media_index.py:397-435` to delegate row creation to the unified stage; `_modes/full.py` to invoke the new stage.
- **Create regression tests:** DB-end-state equality vs the legacy two-step; canonical_provider 194-show guard; DEV #50 disk-row dedup.
- **Effort:** XL · **Risk:** high · **Deps:** Phase 2. *Consider splitting into 3a (build stage + tests, keep `scan_library` calling it) and 3b (reconcile dispatch creator) to keep each gate green.*

### Phase 4 — Wire `library-scan` to the unified stage; delete the separate code path

- **Objective:** `library-scan` becomes a thin re-point of `library-index --mode full` (or is hidden), and `library/scanner.py` is deleted. **Do not remove the `library-scan` command name** — ROADMAP non-goal (`ROADMAP.md:55`).
- **Modify:** `commands/library/scan.py:255-352` to call the unified entry point; **delete** `library/scanner.py`.
- **Gate (mandatory residual-import grep per CLAUDE.md):** `rg -t py 'library.scanner|scan_library' personalscraper/ tests/` returns zero.
- **Tests:** re-home `tests/.../test_*scanner*` (part of the ~9773 LOC) to the new indexer stage; preserve unique coverage (canonical normalisation, NTFS-related paths).
- **Effort:** L · **Risk:** high · **Deps:** Phase 3.

### Phase 5 — Merge ffprobe path into enrich; move reporter/recommender to `insights/`

- **Objective:** One stream-extraction backend (pymediainfo → `media_stream`); `analyze_from_index` becomes the sole reader.
- **Modify:** `library/analyzer.py` — delete `analyze_library` (ffprobe via `scraper.mediainfo.extract_stream_info`); keep `analyze()` (DB aggregate) + `analyze_from_index()`. **Before deleting ffprobe**, address the HDR/Atmos gap (`analyzer.py:447-457`): either add `hdr`/`hdr_type`/`is_atmos` columns to `media_stream` (in place — no migration script, just re-index) and populate them in `enrich.py`, or explicitly accept the fidelity loss in DESIGN (OQ-2).
- **Create:** `personalscraper/insights/` package — move `reporter.py`, `recommender.py`, and `analyze()`/`analyze_from_index()` there as a read-only query layer over the indexer DB.
- **Modify:** `commands/library/analyze.py` importers.
- **Effort:** L · **Risk:** medium · **Deps:** Phase 4.

### Phase 6 — Re-home validator → `verify/`, disk_cleaner → `maintenance/`; delete `library/`

- **Objective:** Empty and remove the `library/` package.
- **Modify/Create:** Move `validator.py` checks into the verify plugin system (it already wraps `verify.checker.MediaChecker`). **Module-size guard:** `verify/checker.py` is **788 LOC** — DO NOT inline 395 LOC into it; create `verify/library_checks.py` instead. Move `disk_cleaner.py` into a NEW `personalscraper/maintenance/disk_cleaner.py` (FS `rmtree` + NTFS ghost handling + outbox write-through) — **NOT** `repair.py` (DB-only). Update `commands/library/maintenance.py`. Delete `library/__init__.py` and the now-empty package.
- **Gate:** `rg -t py 'personalscraper.library' personalscraper/ tests/` returns zero; `python3 scripts/check-module-size.py` shows no module ≥ 1000 LOC.
- **Effort:** L · **Risk:** medium · **Deps:** Phase 5.

---

## 5. Acceptance criteria (SH-16 — executable commands with expected output)

```bash
# ACC-00  Phase 0 — no ad-hoc season-dir regex left in library/disk_cleaner
rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/library/ ; echo "rc=$?"
# Expected: no output, then  rc=1   (rg exit 1 = no matches)

# ACC-00b Phase 0 — canonical pattern matches all season forms
python -c "from personalscraper.naming_patterns import SEASON_DIR_RE as r; assert all(r.match(s) for s in ['Saison 1','Saison 01','Season 1','Specials']); print('OK')"
# Expected: OK

# ACC-01  Phase 1 — stale/inaccurate ROADMAP text is gone
rg -n 'duplicating walk logic|726 LOC|4565 LOC' ROADMAP.md ; echo "rc=$?"
# Expected: no output, then  rc=1

# ACC-02  Phase 2 — no importer reaches into library.scanner
rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/ ; echo "rc=$?"
# Expected: no output, then  rc=1

# ACC-03  Phase 3 — library-index full yields the SAME media_item count as the legacy two-step
DB=$(python -c "from personalscraper.config import load_config as L; print(L().indexer.db_path)")
sqlite3 "$DB" 'SELECT COUNT(*) FROM media_item;'
# Expected: integer == count recorded after the legacy `library-scan` + `library-index` run (assert equal in the migration test)

# ACC-03b Phase 3 — canonical_provider regression guard still passes
make test 2>&1 | rg -i 'canonical_provider|194 ' | rg -i 'pass|ok' ; echo "rc=$?"
# Expected: the canonical_provider regression test(s) report passed; rc=0

# ACC-04  Phase 4 — library/scanner.py and scan_library are fully removed
test ! -f personalscraper/library/scanner.py && echo "deleted"
rg -t py 'library.scanner|scan_library' personalscraper/ tests/ ; echo "rc=$?"
# Expected: deleted    then no output, then  rc=1

# ACC-05  Phase 5 — ffprobe stream extraction removed from library/insights
rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/ ; echo "rc=$?"
# Expected: no output, then  rc=1
# ACC-05b library-analyze still produces a non-empty result on an enriched fixture
personalscraper library-analyze 2>&1 | rg -i 'file_count|files' | rg -v 'file_count[:= ]*0\b' ; echo "rc=$?"
# Expected: a line with file_count > 0; rc=0

# ACC-06  Phase 6 — library/ package fully gone
rg -t py 'personalscraper.library' personalscraper/ tests/ ; echo "rc=$?"
test ! -d personalscraper/library && echo "package removed"
# Expected: no output, then rc=1 ; then  package removed

# ACC-06b module-size hard ceiling respected
python3 scripts/check-module-size.py ; echo "rc=$?"
# Expected: rc=0 (no module >= 1000 non-blank LOC)

# ACC-GATE  every phase gate
make lint && make test && make check ; echo "rc=$?"
# Expected: ruff+mypy clean, "NNNN passed" with 0 failed/errors, branch coverage >= 90%; rc=0

# ACC-SMOKE
python -c "import personalscraper; print('import-ok')"
# Expected: import-ok
```

---

## 6. Trade-offs & alternatives

- **New scan stage vs new scan mode (Phase 3).** A *stage inside `ScanMode.full`* keeps `library-index --mode full` a single self-sufficient command (preferred — matches the ROADMAP goal of folding into "full mode + quick mode"). A *new mode* (`--mode items`) would re-introduce a two-step run, defeating the consolidation. **Chosen:** stage inside `full`.
- **disk_cleaner → `maintenance/` vs `repair.py` (rejected).** The ROADMAP suggests `repair.py`, but that module is DB-only (`soft_delete_subtree:382`); mixing destructive FS `rmtree` + NTFS ghost handling + outbox write-through with DB mutation violates single-responsibility and complicates the `repair` test surface. **Chosen:** dedicated `maintenance/`.
- **validator → inline in `verify/checker.py` (rejected).** `checker.py` is 788 LOC; inlining 395 LOC breaches the 1000 hard ceiling. **Chosen:** `verify/library_checks.py` plugin.
- **One mega-feature vs split minors.** Phase 3 is XL/high-risk; keeping every gate green mid-cutover is hard if `media_item` creation is half-moved. **Mitigation:** split Phase 3 into 3a/3b. Alternative (rejected): ship Phases 0-2 as a separate `fix/` first — adds release overhead for little benefit since 0-2 naturally precede 3.
- **HDR/Atmos fidelity (Phase 5).** Extend `media_stream` schema (in place — no migration script, just re-index) and populate in `enrich.py`, OR accept the documented loss. Extending is preferred to avoid a silent metadata regression; it is cheap pre-1.0.

---

## 7. Effort & sequencing

- **Quick wins (do first):** Phase 0 (S) and Phase 1 (S) — low risk, decouple SSOT/doc cleanup from the heavy refactor and ground the DESIGN.
- **Enabler:** Phase 2 (M) — must precede any deletion.
- **Heavy lift:** Phase 3 (XL, high) — the crux; split 3a/3b. Carry the canonical_provider (194-show) and DEV #50 regression tests forward verbatim.
- **Finish:** Phases 4 (L), 5 (L), 6 (L) — sequential, each unblocked by the prior.
- **Strict order:** 0 → 1 → 2 → 3(a→b) → 4 → 5 → 6. Total ≈ one minor feature; Phase 3 dominates the budget.

---

## 8. Open questions (for the user)

- **OQ-1:** Should `dispatch/media_index.rebuild` (`media_index.py:406`) be fully replaced by the unified Phase-3 stage (one creator), or kept as a degraded fast-path for the dispatch auto-rebuild on empty DB? (Affects whether dispatch can run without a prior `library-index`.)
- **OQ-2:** Extend `media_stream` with `hdr`/`hdr_type`/`is_atmos` columns (re-index in place, no migration script) to preserve HDR/Atmos fidelity, or accept the documented loss when ffprobe is dropped? (`analyzer.py:447-457`.)
- **OQ-3:** Deliver as one `feat/lib-fold` minor, or split Phases 0-2 into a preliminary `fix/` and 3-6 into the minor? (Phase-gate discipline vs release overhead.)
- **OQ-4:** Keep `library-scan` as a re-pointed alias of `library-index --mode full` (ROADMAP non-goal forbids removing commands) or hide it from `--help` while keeping it callable?
