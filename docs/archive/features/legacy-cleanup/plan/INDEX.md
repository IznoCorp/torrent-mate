# Legacy Cleanup Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all V0-V15 alpha versioning references from every live file (docs + Python code) while preserving history in the git log and a consolidated archive directory.

**Architecture:** 5 sequential phases with explicit gate checks. Phases 1-3 are doc-only (safe to run without tests). Phase 4 sweeps 41 Python files by module, one commit per module, with `make test && make lint` after each. Phase 5 is a global validation pass.

**Tech Stack:** git (mv, rm), grep, Python 3.10+, make (test/lint targets).

---

## Phases

| #   | Phase                | File                                                                 | Status |
| --- | -------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Archive legacy docs  | [phase-01-archive-legacy-docs.md](phase-01-archive-legacy-docs.md)   | [ ]    |
| 2   | Rewrite root docs    | [phase-02-rewrite-root-docs.md](phase-02-rewrite-root-docs.md)       | [ ]    |
| 3   | Clean reference docs | [phase-03-clean-reference-docs.md](phase-03-clean-reference-docs.md) | [ ]    |
| 4   | Clean source code    | [phase-04-clean-source-code.md](phase-04-clean-source-code.md)       | [ ]    |
| 5   | Final validation     | [phase-05-final-validation.md](phase-05-final-validation.md)         | [ ]    |

## Detection Rules (global reference)

Copy of the DESIGN.md detection table — used verbatim in each phase gate.

| Pattern                       | Meaning                     | Action                         |
| ----------------------------- | --------------------------- | ------------------------------ |
| `\bV[0-9]+\b`                 | "V3", "V12", "V14" isolated | remove                         |
| `\bv[0-9]+\b`                 | "v3", "v12" lowercase       | remove (context check)         |
| `V[0-9]+\.x`                  | "V7.x"                      | remove                         |
| `V[0-9]+\+V[0-9]+`            | "V9+V10+V13" composition    | reformulate                    |
| `V15 \(config-driven\)`       | explicit feature title      | remove label, keep description |
| `\.v14\.bak`                  | runtime backup filename     | **KEEP** (runtime contract)    |
| `\.personalscraper\.v14\.bak` | runtime backup              | **KEEP**                       |
| `Python 3\.10\+`, `V3\.10`    | Python version              | **KEEP**                       |
| `TMDB v3 API`, `TVDB v4 API`  | external API version        | **KEEP**                       |
| CI badges, `VERSION=0.x.y`    | semver reference            | **KEEP**                       |

## Commit Convention

All commits on branch `feat/legacy-cleanup`.
Format: `{type}(legacy-cleanup): {description}`

| Phase | Commits                                                    |
| ----- | ---------------------------------------------------------- |
| 1     | `chore(legacy-cleanup): archive v0-v15 alpha docs`         |
| 2     | `chore(legacy-cleanup): rewrite root docs without VX refs` |
| 3     | `chore(legacy-cleanup): clean reference docs of VX refs`   |
| 4     | 10 per-module commits (see list below)                     |
| 5     | `chore(legacy-cleanup): final sweep and validation`        |

**Phase 4 commit list (10 commits, one per sub-phase):**

1. `chore(legacy-cleanup): strip VX refs from top-level modules`
2. `chore(legacy-cleanup): strip VX refs from commands module`
3. `chore(legacy-cleanup): strip VX refs from conf module`
4. `chore(legacy-cleanup): strip VX refs from ingest module`
5. `chore(legacy-cleanup): strip VX refs from sorter module`
6. `chore(legacy-cleanup): strip VX refs from scraper module`
7. `chore(legacy-cleanup): strip VX refs from verify module`
8. `chore(legacy-cleanup): strip VX refs from enforce module`
9. `chore(legacy-cleanup): strip VX refs from dispatch module`
10. `chore(legacy-cleanup): strip VX refs from library module`

Total expected commits on `feat/legacy-cleanup`: **14** (1 + 1 + 1 + 10 + 1).
