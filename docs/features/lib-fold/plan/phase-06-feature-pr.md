# Phase 6 — Feature PR + review (auto-invoked)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the four reference docs that must reflect the new architecture, then invoke `/implement:feature-pr` (which auto-invokes `/implement:pr-review`) to run the local quality gate, push the branch, create the PR, poll CI to green, and squash-merge.

**Architecture:** Documentation-only changes in this phase — no source code edits. The PR is created on `feat/lib-fold` and targets `main`. Squash merge (chosen at feature start).

**Tech Stack:** git, gh CLI, `make check`.

---

## Gate

Phase 5 must be complete:

- `test ! -d personalscraper/library` passes.
- `rg -t py 'personalscraper\.library' personalscraper/ tests/` returns zero matches.
- `python3 scripts/check-module-size.py` exits `rc=0`.
- `make lint && make test && make check` green.
- `python -c "import personalscraper; print('import-ok')"` prints `import-ok`.

---

## Objective

1. Update `docs/reference/commands.md` — remove the implicit run-order note that said `library-scan` must run before `library-index`; document that `library-index --mode full` is now self-sufficient.
2. Update `docs/reference/architecture.md` — module map: remove `library/` entry, add `insights/` and `maintenance/` entries with their responsibilities.
3. Update `docs/reference/indexer.md` — add a section describing the item stage (pass 1 in `ScanMode.full`): what it does, which functions are public, how it relates to the file walk (pass 2).
4. Update `CHANGELOG.md` — add a `## [0.19.0]` entry.
5. Verify `VERSION` reads `0.19.0` (set at `create-branch`).
6. Run the full quality gate, then invoke `/implement:feature-pr`.

---

## Files to create / modify

| Action | File                             |
| ------ | -------------------------------- |
| Modify | `docs/reference/commands.md`     |
| Modify | `docs/reference/architecture.md` |
| Modify | `docs/reference/indexer.md`      |
| Modify | `CHANGELOG.md`                   |

---

## Sub-tasks

### Task 1: Update `docs/reference/commands.md`

- [ ] **Step 1.1: Find the run-order note**

```bash
grep -n 'library-scan\|run.*order\|before.*library-index\|library-index.*after' /Users/izno/dev/PersonnalScaper/docs/reference/commands.md | head -20
```

- [ ] **Step 1.2: Remove / replace the note**

Locate the paragraph or callout that says something like "run `library-scan` before `library-index`" or describes a two-step workflow. Replace it with:

```markdown
`library-index --mode full` is self-sufficient — it runs the item-stage pass
(rich `media_item` rows: title, canonical provider, seasons, artwork status,
`item_issue` flags) as pass 1, then the file walk as pass 2. No prior
`library-scan` step is required.

`library-scan` is a visible alias for `library-index --mode full` (kept in
`--help` for backwards compatibility).
```

- [ ] **Step 1.3: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add docs/reference/commands.md && git commit -m "docs(lib-fold): update commands.md — library-index --mode full is self-sufficient"
```

---

### Task 2: Update `docs/reference/architecture.md`

- [ ] **Step 2.1: Find the module map section**

```bash
grep -n 'library/\|module map\|package layout\|insights\|maintenance' /Users/izno/dev/PersonnalScaper/docs/reference/architecture.md | head -20
```

- [ ] **Step 2.2: Update the module map**

Remove the `library/` package entry. Add entries for `insights/` and `maintenance/`:

```markdown
### `personalscraper/insights/` (new in 0.19.0)

Read-only analytics layer over the indexer DB. Modules:

- `analytics.py` — `analyze()` (DB aggregates) + `analyze_from_index()` (stream-level stats)
- `reporter.py` — `generate_report()` / `format_report_text()`
- `recommender.py` — `generate_recommendations()`
- `models.py` — analysis + recommender dataclasses (`VideoInfo`, `MediaFileAnalysis`,
  `LibraryAnalysisResult`, `Recommendation`, `LibraryRecommendationResult`, etc.)

### `personalscraper/maintenance/` (new in 0.19.0)

Operator-upkeep package for filesystem and re-scrape maintenance (distinct from
`indexer/repair.py`, which is DB-only):

- `disk_cleaner.py` — `rmtree`-based deletion + NTFS ghost-dirent handling + outbox events
- `rescraper.py` — targeted TMDB/TVDB re-scrapes (`rescrape_library`, `_detect_needs`)
```

Add a note that `verify/library_checks.py` (new in 0.19.0) is the standalone re-home of the former `library/validator.py`.

- [ ] **Step 2.3: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add docs/reference/architecture.md && git commit -m "docs(lib-fold): update architecture.md — remove library/, add insights/ + maintenance/ entries"
```

---

### Task 3: Update `docs/reference/indexer.md` — item stage section

- [ ] **Step 3.1: Find the ScanMode.full section**

```bash
grep -n 'ScanMode\|full\|item.stage\|scan_library\|pass 1\|pass 2' /Users/izno/dev/PersonnalScaper/docs/reference/indexer.md | head -20
```

- [ ] **Step 3.2: Add the item stage description**

Find the `ScanMode.full` description and add (or replace) a subsection:

```markdown
#### Item stage (pass 1 of `ScanMode.full`)

`indexer/scanner/_modes/_item_stage.py` performs the directory-metadata
pass before the recursive file walk:

| Public function                                                                | Purpose                                                                                                                                                                               |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `build_item_row(*, title, kind, year, category_id, tvdb_id, tmdb_id, …)`       | Build a `media_item` **column dict** (real post-005 columns; IDs → `external_ids_json`) from parsed NFO inputs; sets `canonical_provider` via `_canonical.derive_canonical_provider`. |
| `upsert_item_with_attrs(conn, row, attrs, issues=None, *, now_s=None)`         | Write `media_item` (via `item_repo.upsert`) + `item_attribute` + `item_issue` (with `detected_at`) rows; idempotent on **`(kind, title)`** (the `item_repo.upsert` conflict key).     |
| `scan_and_stage_dir(conn, media_dir, disk_cfg, category_id, kind, now_s=None)` | High-level: read the NFO, build the row, upsert. No-NFO dirs are indexed (folder-name fallback) and flagged (`nfo_missing`/`nfo_incomplete` in `item_issue`).                         |
| `_ensure_disk_row(conn, disk_cfg, now_s) -> DiskRow`                           | DEV #50: SELECT-by-label then insert the disk row if absent before FK writes (ports `library.scanner._ensure_disk_row`).                                                              |

Pass 2 is the existing recursive file walk (`_walker.py`) that populates
`media_file` and `media_stream` rows. Both passes run inside a single
`library-index --mode full` invocation — no prior `library-scan` needed.

`dispatch/media_index.rebuild()` also calls `upsert_item_with_attrs`
directly (single creator — no `canonical_provider=None` degradation).
```

- [ ] **Step 3.3: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add docs/reference/indexer.md && git commit -m "docs(lib-fold): document item stage in indexer.md"
```

---

### Task 4: Update `CHANGELOG.md` and verify `VERSION`

- [ ] **Step 4.1: Verify VERSION**

```bash
cat /Users/izno/dev/PersonnalScaper/VERSION
```

Expected: `0.19.0` (set at `create-branch`). If it reads something else, update it:

```bash
echo "0.19.0" > /Users/izno/dev/PersonnalScaper/VERSION
```

- [ ] **Step 4.2: Add `[0.19.0]` entry to `CHANGELOG.md`**

Insert at the top of the changelog (below the `# Changelog` header):

```markdown
## [0.19.0] — 2026-05-31

### Changed

- **Library / Indexer Consolidation (lib-fold)**: `library/` package deleted.
  - `library-index --mode full` is now self-sufficient (item stage as pass 1).
  - `library-scan` is a visible alias of `library-index --mode full`.
  - Single `media_item` creator: `dispatch/media_index.rebuild()` now produces
    rich rows via the shared `upsert_item_with_attrs` (no more `canonical_provider=None`).
  - Canonical-provider derivation unified onto the kind-deterministic rule
    (`_canonical.derive_canonical_provider`): show→tvdb if tvdb_id, movie→tmdb if tmdb_id.
  - Season-dir regex consolidated onto `naming_patterns.SEASON_DIR_RE`
    (widened to FR+EN+Specials union); `season_number_from_dir()` helper added.
  - NFO helpers (`parse_title_year`, `extract_nfo_ids`, `extract_nfo_metadata`)
    moved to `personalscraper.nfo_utils`.
  - `library/analyzer.analyze_library` (redundant ffprobe re-scan) dropped;
    `enrich` populates `media_stream.hdr_format`/`is_atmos` (columns pre-existed).

### Added

- `personalscraper/insights/` — read-only analytics package (`analytics.py`,
  `reporter.py`, `recommender.py`, `models.py`).
- `personalscraper/maintenance/` — operator-upkeep package (`disk_cleaner.py`,
  `rescraper.py`).
- `personalscraper/verify/library_checks.py` — standalone validator (formerly
  `library/validator.py`); registerable in the future Check plugin system.
- `library doctor` / `library audit` now report items without a valid NFO with
  a `library-rescrape --target nfo_missing` repair hint.
- `personalscraper/naming_patterns.season_number_from_dir()` helper.

### Removed

- `personalscraper/library/` package (all 8 modules).
```

- [ ] **Step 4.3: Verify ACC-07**

```bash
cat /Users/izno/dev/PersonnalScaper/VERSION ; grep -c '^## \[0.19.0\]' /Users/izno/dev/PersonnalScaper/CHANGELOG.md
```

Expected: `0.19.0` then `1`.

- [ ] **Step 4.4: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add CHANGELOG.md VERSION && git commit -m "chore(lib-fold): CHANGELOG 0.19.0 + VERSION bump"
```

---

### Task 5: Final quality gate

- [ ] **Step 5.1: Run ACC-GATE**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test && make check ; echo "rc=$?"
```

Expected: ruff+mypy clean, `NNNN passed` 0 failed/errors, coverage ≥ 90 %, `rc=0`.

- [ ] **Step 5.2: Run ACC-SMOKE**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "import personalscraper; print('import-ok')"
```

Expected: `import-ok`.

- [ ] **Step 5.3: Run all ACC criteria in sequence**

```bash
# ACC-00
cd /Users/izno/dev/PersonnalScaper && rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/library/ personalscraper/indexer/ personalscraper/trailers/ 2>/dev/null ; echo "rc=$?"
# ACC-00b
python -c "from personalscraper.naming_patterns import SEASON_DIR_RE as r; assert all(r.match(s) for s in ['Saison 1','Saison 01','Season 1','Specials']); print('OK')"
# ACC-00c
python -c "from personalscraper.naming_patterns import season_number_from_dir as f; assert f('Saison 3')==3 and f('Season 12')==12 and f('Specials') in (0,None); print('OK')"
# ACC-02
rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/ ; echo "rc=$?"
# ACC-02b
python -c "from personalscraper.nfo_utils import parse_title_year, extract_nfo_ids, extract_nfo_metadata; print('OK')"
# ACC-03
python -c "import personalscraper.indexer.scanner._modes._item_stage, personalscraper.indexer.scanner._modes._canonical; print('OK')"
# ACC-04
test ! -f personalscraper/library/scanner.py && echo "deleted"
rg -t py 'library.scanner|scan_library' personalscraper/ tests/ ; echo "rc=$?"
# ACC-04b
rg -t py 'canonical_provider=None' personalscraper/dispatch/media_index.py ; echo "rc=$?"
# ACC-05
rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/ 2>/dev/null ; echo "rc=$?"
# ACC-06
test -f personalscraper/verify/library_checks.py && test -f personalscraper/maintenance/disk_cleaner.py && test -f personalscraper/maintenance/rescraper.py && echo "rehomed"
rg -t py 'personalscraper\.library' personalscraper/ tests/ ; echo "rc=$?"
test ! -d personalscraper/library && echo "package removed"
# ACC-06b
personalscraper library-doctor 2>&1 | rg -i 'nfo' ; echo "rc=$?"
# ACC-06c
python3 scripts/check-module-size.py ; echo "rc=$?"
# ACC-07
cat VERSION ; grep -c '^## \[0.19.0\]' CHANGELOG.md
```

---

### Task 6: Invoke `/implement:feature-pr` (auto-triggers `/implement:pr-review`)

- [ ] **Step 6.1: Invoke the feature-pr skill**

```
/implement:feature-pr
```

This skill will:

1. Run the local quality gate (Opus).
2. Push `feat/lib-fold` to the remote.
3. Create the PR with title and body summarising the consolidation.
4. Poll CI until green (Haiku).
5. Auto-invoke `/implement:pr-review` (max 5 fix cycles + squash merge).

- [ ] **Step 6.2: Address any PR review comments**

`/implement:pr-review` runs up to 5 fix cycles. Each cycle:

- Reads PR review comments.
- Filters against the DESIGN and plan.
- Dispatches a fix phase if warranted.
- Re-runs `make check` before pushing.

- [ ] **Step 6.3: Confirm squash merge**

After `/implement:pr-review` completes, verify the PR is merged on GitHub:

```bash
gh pr view --json state,mergeCommit 2>&1
```

Expected: `state: MERGED`.

---

## Acceptance

```bash
# ACC-07  Version bump + CHANGELOG
cat VERSION ; grep -c '^## \[0.19.0\]' CHANGELOG.md
# Expected: 0.19.0   then   1

# ACC-GATE  final gate
make lint && make test && make check ; echo "rc=$?"
# Expected: ruff+mypy clean, "NNNN passed" 0 failed/errors, coverage >= 90%; rc=0

# ACC-SMOKE
python -c "import personalscraper; print('import-ok')"
# Expected: import-ok
```

---

## Risks & mitigations

| Risk                                                                  | Mitigation                                                                                                              |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| CI catches a residual `personalscraper.library` import missed locally | Full `rg -t py 'personalscraper\.library'` grep run in Task 5.3 before push; CI is the final safety net, not the first. |
| PR review requests changes that conflict with DESIGN decisions        | `/implement:pr-review` filters comments against the DESIGN before actioning; resolved decisions (§8) are not re-opened. |
| `docs/` files blocked by global `.gitignore` `docs/` rule             | Use `git add -f docs/reference/commands.md` etc. if `git add` silently skips them.                                      |
