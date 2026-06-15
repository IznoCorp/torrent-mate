# follow-detect — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement phase-by-phase. Each phase file opens with a **Gate** section — verify it before starting.

**Goal:** Wire the first production consumer of `poll_aired` (RP9) and `OwnershipChecker` (RP6): a `follow detect` CLI command that enqueues un-owned aired episodes as `WantedItem` rows, plus a cadence-aware (Hot/Warm/Cold backoff + cutoff) search loop in `AcquisitionService._process_item`.

**Architecture:** Two cooperating stages share the `wanted` table as seam. Stage A (DETECT CLI) enumerates aired episodes via `poll_aired`, skips owned/dup, and enqueues via `store.wanted.add` + emits `WantedEnqueued`. Stage B (cadence-aware loop) inserts `is_past_cutoff` + `is_due_by_cadence` checks BEFORE `claim_for_search` in `_process_item`, replacing the flat `_STALE_THRESHOLD_S` cadence decision with a tier-based policy.

**Design doc:** `docs/features/follow-detect/DESIGN.md`
**Branch:** `feat/follow-detect`
**Commit scope:** `follow-detect`
**Version bump:** 0.31.0 → 0.32.0 (minor)

---

## Phases

| #   | Phase                              | File                                    | Status |
| --- | ---------------------------------- | --------------------------------------- | ------ |
| 1   | Cadence module + config + codec    | phase-01-cadence-module-config-codec.md | [ ]    |
| 2   | Wanted dedup (`find`)              | phase-02-wanted-dedup.md                | [ ]    |
| 3   | DETECT logic + `follow detect` CLI | phase-03-detect-cli.md                  | [ ]    |
| 4   | Cadence-aware run loop             | phase-04-cadence-aware-run-loop.md      | [ ]    |
| 5   | Docs + ACCEPTANCE + gate           | phase-05-docs-acceptance-gate.md        | [ ]    |

---

## File map

| File                                        | Action | Purpose                                                                                                          |
| ------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------- |
| `personalscraper/acquire/cadence.py`        | CREATE | `Cadence`/`CadenceTier` VOs + `is_due_by_cadence` + `is_past_cutoff` (pure; phase 1)                             |
| `personalscraper/conf/models/acquire.py`    | MODIFY | Add `CadenceTierConfig` + `CadenceConfig` + `cadence` field on `AcquireConfig` (phase 1)                         |
| `config/acquire.json5`                      | MODIFY | Add `cadence` block with Hot/Warm/Cold/30d defaults (phase 1)                                                    |
| `config.example/acquire.json5`              | MODIFY | Mirror of config/acquire.json5 (phase 1)                                                                         |
| `personalscraper/acquire/desired.py`        | MODIFY | Add `cadence_to_json`/`cadence_from_json`/`cadence_from_config`/`effective_cadence` + update `__all__` (phase 1) |
| `tests/acquire/test_cadence.py`             | CREATE | All cadence unit tests: tiers, boundaries, config, codec (phase 1)                                               |
| `personalscraper/acquire/_ports.py`         | MODIFY | Add `find(...)` to `WantedSubStore` protocol (phase 2)                                                           |
| `personalscraper/acquire/store.py`          | MODIFY | Add `find(...)` impl on `_WantedSubStore` (phase 2)                                                              |
| `tests/acquire/test_store_wanted_find.py`   | CREATE | Round-trip tests for `find` (phase 2)                                                                            |
| `personalscraper/commands/follow.py`        | MODIFY | Add `@follow_app.command("detect")` + update `__all__` (phase 3)                                                 |
| `tests/commands/test_follow_detect.py`      | CREATE | Golden + dry-run + boundary + layering tests (phase 3)                                                           |
| `personalscraper/acquire/service.py`        | MODIFY | Insert cutoff/cadence checks in `_process_item`; add `FollowedSeries` map in `run` (phase 4)                     |
| `tests/acquire/test_service_cadence.py`     | CREATE | Cadence-aware loop unit tests (phase 4)                                                                          |
| `docs/reference/architecture.md`            | MODIFY | Add `acquire/cadence.py` + Follow D2 boundary note (phase 5)                                                     |
| `docs/features/follow-detect/ACCEPTANCE.md` | CREATE | ACC-01..ACC-10 executable shell commands (phase 5)                                                               |

---

## Key symbols

| Symbol                                                                             | Location                                 | Phase |
| ---------------------------------------------------------------------------------- | ---------------------------------------- | ----- |
| `CadenceTier`, `Cadence`                                                           | `personalscraper/acquire/cadence.py`     | 1     |
| `is_due_by_cadence(cadence, *, now, enqueued_at, last_search_at)`                  | `personalscraper/acquire/cadence.py`     | 1     |
| `is_past_cutoff(cadence, *, now, enqueued_at)`                                     | `personalscraper/acquire/cadence.py`     | 1     |
| `CadenceTierConfig`, `CadenceConfig`                                               | `personalscraper/conf/models/acquire.py` | 1     |
| `cadence_to_json`, `cadence_from_json`, `cadence_from_config`, `effective_cadence` | `personalscraper/acquire/desired.py`     | 1     |
| `WantedSubStore.find`                                                              | `personalscraper/acquire/_ports.py`      | 2     |
| `_WantedSubStore.find`                                                             | `personalscraper/acquire/store.py`       | 2     |
| `follow_detect`                                                                    | `personalscraper/commands/follow.py`     | 3     |
| cutoff + cadence checks in `_process_item`                                         | `personalscraper/acquire/service.py`     | 4     |

---

## Repo rules (enforced throughout)

- Every `rg` command MUST carry `--type py` / `-g '*.py'` / `-g '*.md'` — the repo has a 14 GB fixture dir.
- Logging: `personalscraper.logger.get_logger` (NEVER `structlog.get_logger`).
- Google-style docstrings on all modules, classes, and functions.
- Commit scope = `follow-detect`. No AI attribution.
- Phase gate before each phase: run the Gate verification commands listed at the top of each phase file.
- Final gate: `make check` exits 0 + `python3 scripts/audit_design_coverage.py --strict` exits 0 + `python3 scripts/update_feature_map.py --check` exits 0.
