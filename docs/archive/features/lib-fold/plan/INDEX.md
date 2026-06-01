# lib-fold Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold the load-bearing parts of `personalscraper/library/` into the canonical `indexer/` subsystem, eliminate the two uncoordinated `media_item` writers, unify all season-dir regexes and canonical-provider extraction onto single sources of truth, re-home read-only and maintenance modules, and delete the `library/` package entirely.

**Architecture:** A widen-first sequence (Phase 0) ensures the canonical season-dir regex subsumes all ad-hoc copies before any are removed. Phases 1–3 handle the crux: NFO helpers move to `nfo_utils`, a new `_item_stage.py` builds rich rows (parallel path, no deletions), then a cutover removes the legacy scanner and redirects dispatch. Phases 4–5 clean up the remaining library modules (ffprobe re-scan, insights, maintenance, verify) and delete `library/`. Phase 6 is the automated feature PR.

**Tech Stack:** Python 3.11, SQLite (via `indexer/repos/`), pytest, ruff, mypy, `make lint && make test && make check`.

---

## Phases

| #   | Phase                                                                                | File                                                                           | Status |
| --- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ | ------ |
| 0   | Season-dir SSOT (widen-first) + VIDEO_EXTENSIONS                                     | [phase-00-season-ssot.md](phase-00-season-ssot.md)                             | [ ]    |
| 1   | Extract NFO helpers → `nfo_utils`                                                    | [phase-01-nfo-helpers.md](phase-01-nfo-helpers.md)                             | [ ]    |
| 2   | Build `_item_stage` + `_canonical`; rewire `scan_library` (parallel path)            | [phase-02-item-stage.md](phase-02-item-stage.md)                               | [ ]    |
| 3   | Single creator cutover: redirect dispatch, alias `library-scan`, delete `scanner.py` | [phase-03-single-creator-cutover.md](phase-03-single-creator-cutover.md)       | [ ]    |
| 4   | ffprobe fold + `insights/` package                                                   | [phase-04-ffprobe-insights.md](phase-04-ffprobe-insights.md)                   | [ ]    |
| 5   | `verify`/`maintenance` re-home + proactive no-NFO + delete `library/`                | [phase-05-verify-maintenance-delete.md](phase-05-verify-maintenance-delete.md) | [ ]    |
| 6   | Feature PR + review (auto-invoked)                                                   | [phase-06-feature-pr.md](phase-06-feature-pr.md)                               | [ ]    |

## Gate commit format

Every phase ends on:

```
chore(lib-fold): phase N gate — <short description>
```

preceded by `make lint && make test && make check` green (ruff+mypy clean, all tests pass, coverage ≥ 90 %, no module ≥ 1000 non-blank LOC).

## Residual-import grep (run after every phase)

```bash
rg -t py 'personalscraper\.library' personalscraper/ tests/
```

Expected: growing toward zero; must be zero at Phase 5 gate.

## Key file map

| New / modified file                                                | Purpose                                                                |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| `personalscraper/naming_patterns.py`                               | SEASON_DIR_RE widened FR+EN+Specials; `season_number_from_dir()` added |
| `personalscraper/nfo_utils.py`                                     | Gains `parse_title_year`, `extract_nfo_ids`, `extract_nfo_metadata`    |
| `personalscraper/indexer/scanner/_modes/_item_stage.py`            | NEW — unified item/season/episode/issue upsert                         |
| `personalscraper/indexer/scanner/_modes/_canonical.py`             | NEW — kind-deterministic canonical SSOT                                |
| `personalscraper/indexer/scanner/_modes/full.py`                   | Invokes `_item_stage` as pass 1                                        |
| `personalscraper/indexer/scanner/_modes/backfill_ids_canonical.py` | Delegates to `_canonical.py`                                           |
| `personalscraper/dispatch/media_index.py`                          | `rebuild()` delegates to `upsert_item_with_attrs`                      |
| `personalscraper/verify/library_checks.py`                         | NEW — re-home of `validator.py`                                        |
| `personalscraper/insights/`                                        | NEW read-only package (analytics, reporter, recommender, models)       |
| `personalscraper/maintenance/`                                     | NEW operator-upkeep package (disk_cleaner, rescraper)                  |
| `personalscraper/library/`                                         | DELETED at Phase 5 gate                                                |
