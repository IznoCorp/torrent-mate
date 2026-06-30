# index-sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically run index-maintenance (per-disk incremental scan → relink → fix-season-counts) at the end of `personalscraper dispatch`, scoped to disks touched by that dispatch.

**Architecture:** A reusable `run_post_dispatch_maintenance()` function in a new `personalscraper/dispatch/post_maintenance.py` module composes the existing indexer entry points (`library_index_command`, the relink SQL logic, `FixSeasonCountsStats` path). The `dispatch` CLI command extracts touched disks from `DispatchResult` objects returned by `run_dispatch` and calls the function only when ≥1 item was actually dispatched and the feature is enabled.

**Tech Stack:** Python 3.12+, sqlite3, typer, pytest, unittest.mock

## Global Constraints

- Google-style docstrings mandatory on all modules, classes, functions, and methods.
- Use `personalscraper.logger.get_logger` (NOT `structlog.get_logger` directly).
- Per-disk scan only — sequential, NEVER parallel (parallel scan dies on SQLite writer lock).
- Incremental mode for post-maintenance scan — NOT quick (quick trips bulk-restore guard).
- One regression test per observed bug (2026-06-29 `items_without_files=6` symptom).
- Commit format: `{type}(index-sync): description`. Each sub-phase = 1 commit.
- Config key follows config-overlay-layout: owned by `indexer.json5`.

## Phases

| #   | Phase                                        | File                                                           | Status |
| --- | -------------------------------------------- | -------------------------------------------------------------- | ------ |
| 1   | Core function + config + flag + unit tests   | [phase-01-core-function.md](phase-01-core-function.md)         | [ ]    |
| 2   | Wiring + integration + regression + ACC gate | [phase-02-wiring-acceptance.md](phase-02-wiring-acceptance.md) | [ ]    |
