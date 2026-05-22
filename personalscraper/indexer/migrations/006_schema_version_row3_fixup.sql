-- Schema migration 006 — backfill missing schema_version row 3 (DEV #15).
--
-- Background:
--
-- DEV #15 (tech-debt 0.16.0 audit, sub-phase 1.5) observed an inconsistency
-- on the live BDD: `PRAGMA user_version` returned 5 (correct, all migrations
-- through 005 applied), but the `schema_version` audit table contained
-- rows {1, 2, 4, 5} — row 3 was missing. The migration 003 SQL itself was
-- correctly applied (the `idx_repair_pending_dedup` index exists), but an
-- earlier buggy build of `apply_migrations` did not insert the
-- `schema_version` row for migration 003 while still bumping
-- `user_version`. Subsequent migration runs short-circuit on
-- `version <= user_version`, so migration 003 — even if re-attempted —
-- would never re-insert its row.
--
-- Impact runtime: nil. The runner uses `user_version` (5), not the
-- `schema_version` table which is informative only. The gap is cosmetic
-- but signals a class of bug ("re-apply pattern in migrations"); leaving
-- it would also produce noisy reports from any future `library-doctor`
-- coherence check that asserts
-- `set(schema_version) == set(range(1, user_version+1))`.
--
-- Fix shape:
--   1. `INSERT OR IGNORE` the missing row 3 (no-op on a fresh DB built
--      from scratch where 003 inserted its row normally).
--   2. Insert row 6 + bump `user_version` to 6 per the standard tail
--      pattern of every migration file in this directory.
--
-- This migration touches NO schema definitions — it is purely an audit
-- record fixup. It can be safely re-run (the INSERT OR IGNORE) and is
-- idempotent across re-applies.

INSERT OR IGNORE INTO schema_version (version) VALUES (3);
INSERT INTO schema_version (version) VALUES (6);
PRAGMA user_version = 6;
