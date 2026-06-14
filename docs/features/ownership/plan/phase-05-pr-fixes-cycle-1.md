# Phase 05 — PR review cycle 1 fixes

**Feature**: ownership (RP6)
**PR**: [#198](https://github.com/LounisBou/PersonnalScaper/pull/198)
**Branch**: feat/ownership
**Date**: 2026-06-14

## Findings addressed

- **M1 (MEDIUM)** — same-tvdb_id movie+show collision regression test.
  Added `TestIsOwnedCrossKindCollision` in `tests/indexer/test_ownership_predicate.py`.
  Seeds a show (S01E03 with live file) and a movie (no file) with the same tvdb_id.
  Asserts `is_owned(kind='movie', tvdb_id=X)` → False (kind disambiguation works),
  `is_owned(kind='episode', tvdb_id=X, season=1, episode=3)` → True.

- **m1 (MINOR)** — connection leak on PRAGMA failure in `_ensure_open`.
  Wrapped `PRAGMA query_only=ON` in try/except; `conn.close()` before re-raise
  so a failed PRAGMA doesn't leak a handle.

- **m2 (MINOR)** — close() verification test.
  Added `test_close_releases_connection` in `tests/indexer/test_ownership_adapter.py`.
  Captures `_conn` after `owns()`, calls `close()`, then asserts `conn.execute("SELECT 1")`
  raises `sqlite3.ProgrammingError` (proves the handle is released). Double-close
  idempotent test already existed.

## Commit

`a44a9cc8` fix(ownership): cycle-1 PR review fixes — conn leak + collision test + close-verification
