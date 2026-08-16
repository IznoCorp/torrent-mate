# Phase 6 — Backend fold-in: followed_series dedup

Isolated backend migration + store change. The only backend fold-in in scope (quality_profile
editor is held — see DESIGN "Backend fold-in NOT taken").

## Gate

- `make check` green (unit + migration tests).
- New acquire.db migration applies cleanly on a populated db (incl. one with pre-existing dups);
  UNIQUE index present after; store add is idempotent + race-safe.

## 6.1 — Migration 002: dedup existing + UNIQUE index

**Current** (survey): `followed_series.media_ref_json` has no UNIQUE constraint
(`acquire/migrations/001_init.sql:8`); dedup is app-level (`find_by_ref ORDER BY id LIMIT 1`), racy.
`_media_ref_to_json` emits canonical fixed-key JSON (`{tvdb_id, tmdb_id, imdb_id}`) → stable text.

**Approach**: new `personalscraper/acquire/migrations/002_followed_unique.sql` (+ the migration
runner registration): (1) collapse existing dups — keep the lowest `id` per `media_ref_json`,
reassign/merge dependent `wanted.followed_id` to the survivor, deactivate/delete the losers; (2)
`CREATE UNIQUE INDEX ux_followed_media_ref ON followed_series(media_ref_json)`.
**Files**: new migration SQL, migration runner registry, `acquire/migrations/` index.
**Tests**: migration test — seed dups → migrate → exactly one row per ref, dependents reattached,
UNIQUE index enforced.

## 6.2 — Store INSERT … ON CONFLICT (idempotent add)

**Approach**: `_FollowSubStore.add` → `INSERT INTO followed_series(...) VALUES(...) ON
CONFLICT(media_ref_json) DO UPDATE SET active=1, title=excluded.title` (reactivate + refresh title),
returning the surviving row. Removes reliance on the racy app-level dedup for new inserts.
**Files**: `personalscraper/acquire/store.py`, `acquire/_store_rows.py` (if row mapping changes).
**Tests** (regression-per-bug): concurrent-add test — two adds of the same ref → one row, active,
no IntegrityError leak; re-add of an inactive ref reactivates it.
