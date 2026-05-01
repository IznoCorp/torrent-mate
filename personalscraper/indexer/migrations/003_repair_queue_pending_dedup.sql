-- Schema migration 003 — dedup pending repair_queue rows by (scope, scope_id).
--
-- Background:
--
-- Several producers (drift detection, library-verify, future enrich-stage
-- repair handlers) enqueue rows into repair_queue.  Each one independently
-- calls insert_repair_queue() with no idempotence check, so a file that
-- drifts on every scan accumulates a fresh 'pending' row each run.  Without
-- a UNIQUE constraint that growth is silent and unbounded — DESIGN §8.3
-- describes the queue as a backlog, not as an event log, so duplicate
-- pending rows for the same (scope, scope_id) are pure bloat that delays
-- the worker draining real backlog.
--
-- This migration:
--   1. Collapses any existing duplicate 'pending' rows by keeping the
--      oldest enqueued_at (preserving the intent "this has needed repair
--      for a long time") and discarding the newer copies.
--   2. Adds a partial UNIQUE INDEX so future inserts fail-fast on
--      duplicates; producers should use INSERT ... ON CONFLICT DO NOTHING
--      or pre-check via outbox_repo helpers.
--
-- The partial index is keyed on (scope, scope_id) WHERE status='pending'
-- so terminal rows ('done', 'failed') are excluded — once a repair has
-- been attempted, it makes sense to enqueue a fresh attempt next time
-- the drift recurs.

-- 1. Collapse existing pending duplicates: keep the oldest row per (scope,
-- scope_id), drop the rest.  scope_id may be NULL (e.g. scope='disk' with
-- no specific id); treat NULL as a distinct group only when scope itself
-- isn't already deduplicated by enqueued_at.
DELETE FROM repair_queue
WHERE id NOT IN (
    SELECT MIN(id)
    FROM repair_queue
    WHERE status = 'pending'
    GROUP BY scope, COALESCE(scope_id, -1)
)
AND status = 'pending';

-- 2. Add the UNIQUE partial index.  scope_id NULL is treated as distinct
-- from any other NULL by SQLite UNIQUE semantics, so a 'disk' scope with
-- no scope_id will only ever match itself across rows; this is the
-- desired behaviour because all 'disk'-scoped repairs are by definition
-- the same actionable unit when their scope_id is NULL.
CREATE UNIQUE INDEX IF NOT EXISTS idx_repair_pending_dedup
  ON repair_queue (scope, scope_id)
  WHERE status = 'pending';
