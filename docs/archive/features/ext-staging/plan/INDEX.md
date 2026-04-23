# ext-staging Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple staging directory layout from the git repository by introducing a config-driven `staging_dirs` section, removing hardcoded `TYPE_DIR_MAP` and `*_dir_name` Settings fields, auto-creating the staging tree on first run, and removing staging directories from git tracking.

**Architecture:** New `StagingDirConfig` Pydantic model feeds a `personalscraper/conf/staging.py` helper module; all 20 files with hardcoded staging path literals are refactored to use config lookup; staging directories are untracked from git with a single `.gitignore` wildcard.

**Tech Stack:** Python 3.11+, Pydantic v2, pydantic-settings, structlog, typer, pytest, json5

**Version bump:** 0.3.0 → 0.4.0 (minor — breaking config schema change, pre-1.0 accepted)

**Commit scope:** `ext-staging` — all commits use `{type}(ext-staging): description`

---

## Phases

| #   | Phase                              | File                                                       | Status |
| --- | ---------------------------------- | ---------------------------------------------------------- | ------ |
| 1   | Config schema (additive)           | [phase-01-config-schema.md](phase-01-config-schema.md)     | [ ]    |
| 2   | Sorter refactor + Settings cleanup | [phase-02-sorter-refactor.md](phase-02-sorter-refactor.md) | [ ]    |
| 3   | Auto-create staging tree           | [phase-03-auto-create.md](phase-03-auto-create.md)         | [ ]    |
| 4   | Repo cleanup (git rm --cached)     | [phase-04-repo-cleanup.md](phase-04-repo-cleanup.md)       | [ ]    |
| 5   | Docs + E2E + final gate            | [phase-05-docs-e2e.md](phase-05-docs-e2e.md)               | [ ]    |

## Phase dependency chain

```
P1 (schema additive, Optional) → P2 (refactor + required) → P3 (auto-create) → P4 (git rm) → P5 (docs + E2E)
```

Each phase has an **entry gate** listing what must be true before it starts, and an **exit gate** that must be verified before the milestone commit.

## Invariant across all phases

`paths.data_dir` in `config.example.json5` must equal `/Volumes/IznoServer SSD/A TRIER/.data` at the end of every phase. Any accidental change fails the phase gate.

## Files created by this feature

| File                                      | Phase                                   |
| ----------------------------------------- | --------------------------------------- |
| `personalscraper/conf/staging.py`         | P2 (helpers) + P3 (ensure_staging_tree) |
| `tests/conf/test_models_staging.py`       | P1                                      |
| `tests/conf/test_staging_bootstrap.py`    | P3                                      |
| `tests/e2e/test_staging_bootstrap_e2e.py` | P5                                      |
