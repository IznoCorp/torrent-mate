# seed-pure — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement phase-by-phase. Each phase file opens with a **Gate** section — verify it before starting.

**Goal:** Introduce the `seed-pure` tag vocabulary + tagger capability (qBittorrent + Transmission), a manual `seed` CLI group, an always-on ingest skip, an opt-in sort/process guard, and a Watcher-ready skip contract.

**Architecture:** Five cooperating layers share `core/tags.SEED_PURE` as the single source of truth. The `api/torrent` layer gains the `TorrentTagger` protocol + implementations. The `commands/seed` CLI is the operator-facing write path. The `ingest` always-on skip is the primary guardrail. The opt-in sort/process guard (default off) is a defensive second layer for full-pipeline runs.

**Design doc:** `docs/features/seed-pure/DESIGN.md`
**Branch:** `feat/seed-pure`
**Commit scope:** `seed-pure`
**Version bump:** 0.32.0 → 0.33.0 (minor)

---

## Phases

| #   | Phase                         | File                             | Status |
| --- | ----------------------------- | -------------------------------- | ------ |
| 1   | Tag vocab + tagger capability | phase-01-tag-vocab-tagger.md     | [ ]    |
| 2   | `seed` CLI group              | phase-02-seed-cli.md             | [ ]    |
| 3   | Ingest skip (always-on)       | phase-03-ingest-skip.md          | [ ]    |
| 4   | Opt-in sort/process guard     | phase-04-optional-guard.md       | [ ]    |
| 5   | Docs + ACCEPTANCE + gate      | phase-05-docs-acceptance-gate.md | [ ]    |

---

## File map

| File                                          | Action | Purpose                                                                                           |
| --------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------- |
| `personalscraper/core/tags.py`                | CREATE | `SEED_PURE = "seed-pure"` constant — bottom-layer vocabulary (phase 1)                            |
| `personalscraper/api/torrent/_contracts.py`   | MODIFY | Add `TorrentTagger` protocol + update `__all__` (phase 1)                                         |
| `personalscraper/api/torrent/qbittorrent.py`  | MODIFY | `QBitClient.add_tags` / `remove_tags` via `torrents_addTags`/`removeTags` (phase 1)               |
| `personalscraper/api/torrent/transmission.py` | MODIFY | `TransmissionClient.add_tags` / `remove_tags` read-first preserving category (phase 1)            |
| `tests/api/torrent/test_tagger.py`            | CREATE | Unit tests for qBit + Transmission tagger (phase 1)                                               |
| `personalscraper/commands/seed.py`            | CREATE | `seed_app` Typer group: `mark` / `unmark` / `list` (phase 2)                                      |
| `personalscraper/cli.py`                      | MODIFY | Import `personalscraper.commands.seed` as side-effect (phase 2)                                   |
| `tests/commands/test_seed.py`                 | CREATE | Unit tests for `mark` / `unmark` / `list` CLI commands (phase 2)                                  |
| `personalscraper/ingest/ingest.py`            | MODIFY | Always-on `SEED_PURE` skip after ratio check (phase 3)                                            |
| `tests/ingest/test_ingest_seed_pure.py`       | CREATE | Ingest skip golden: tagged skipped, non-tagged not skipped, ordering (phase 3)                    |
| `personalscraper/conf/models/scraper.py`      | MODIFY | Add `SortConfig(verify_seed_pure=False)` + `ProcessCleanConfig(verify_seed_pure=False)` (phase 4) |
| `personalscraper/conf/models/config.py`       | MODIFY | Add `sort: SortConfig` and `process_clean: ProcessCleanConfig` fields (phase 4)                   |
| `personalscraper/sorter/run.py`               | MODIFY | Accept optional `torrent_client` + per-item seed-pure skip when guard enabled (phase 4)           |
| `personalscraper/process/run.py`              | MODIFY | `run_clean` accepts optional `torrent_client` + per-item skip when guard enabled (phase 4)        |
| `personalscraper/pipeline_steps.py`           | MODIFY | `SortStep` + `CleanStep` thread `ctx.app.torrent_client` when flag enabled (phase 4)              |
| `tests/sorter/test_sort_seed_pure_guard.py`   | CREATE | Guard off = no client query; guard on = seed-pure item skipped (phase 4)                          |
| `tests/process/test_clean_seed_pure_guard.py` | CREATE | Guard off = no client query; guard on = seed-pure item skipped (phase 4)                          |
| `docs/reference/architecture.md`              | MODIFY | Add `core/tags.py` + seed-pure skip-contract note (phase 5)                                       |
| `docs/features/seed-pure/ACCEPTANCE.md`       | CREATE | ACC-01..ACC-09 executable shell commands (SH-16) (phase 5)                                        |

---

## Key symbols

| Symbol                                              | Location                                                          | Phase |
| --------------------------------------------------- | ----------------------------------------------------------------- | ----- |
| `SEED_PURE`                                         | `personalscraper/core/tags.py`                                    | 1     |
| `TorrentTagger`                                     | `personalscraper/api/torrent/_contracts.py`                       | 1     |
| `QBitClient.add_tags` / `remove_tags`               | `personalscraper/api/torrent/qbittorrent.py`                      | 1     |
| `TransmissionClient.add_tags` / `remove_tags`       | `personalscraper/api/torrent/transmission.py`                     | 1     |
| `seed_app`, `seed_mark`, `seed_unmark`, `seed_list` | `personalscraper/commands/seed.py`                                | 2     |
| ingest seed-pure skip block                         | `personalscraper/ingest/ingest.py`                                | 3     |
| `SortConfig.verify_seed_pure`                       | `personalscraper/conf/models/scraper.py`                          | 4     |
| `ProcessCleanConfig.verify_seed_pure`               | `personalscraper/conf/models/scraper.py`                          | 4     |
| seed-pure guard in `run_sort` / `run_clean`         | `personalscraper/sorter/run.py`, `personalscraper/process/run.py` | 4     |

---

## Repo rules (enforced throughout)

- Every `rg` command MUST carry `--type py` / `-g '*.py'` / `-g '*.md'` — the repo has a 14 GB fixture dir.
- Logging: `personalscraper.logger.get_logger` (NEVER `structlog.get_logger`).
- Google-style docstrings on all modules, classes, and functions.
- Commit scope = `seed-pure`. No AI attribution.
- Phase gate before each phase: run the Gate verification commands listed at the top of each phase file.
- Final gate: `make check` exits 0 + `python3 scripts/audit_design_coverage.py --strict` exits 0 + `python3 scripts/update_feature_map.py --check` exits 0.
