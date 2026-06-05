-- Schema migration 010 — year-aware media_item dedup (dispatch_path collision fix).
--
-- Background:
--
-- Migration 007 added ``UNIQUE(title, kind)`` and ``item_repo._canonical_title``
-- strips a trailing `` (YYYY)`` before dedup. That correctly merges
-- ``Inception (2010)`` with ``Inception`` (same movie, year-in-folder vs not),
-- but it ALSO collapses distinct same-base-title *different-year* remakes /
-- revivals into ONE ``media_item`` row: ``Scrubs (2001)`` (tvdb 76156) and
-- ``Scrubs (2026)`` (tvdb 465690) both canonicalise to ``Scrubs``. The surviving
-- row keeps one show's identity while its denormalised ``dispatch_path``
-- attribute ends up pointing at the OTHER show's folder, so a dispatch would
-- merge the revival into the original (15 library items affected: Scrubs,
-- RoboCop, Superman, Mulan, Pinocchio, Doctor Who, Dark Matter, ...).
--
-- This migration replaces the year-blind ``UNIQUE(title, kind)`` index with a
-- year-aware ``UNIQUE(title, kind, year)`` index so a remake and its original
-- can coexist as two rows. The code fix ships in the same commit
-- (``item_repo.get_by_title_kind_year`` + ``upsert``) and dedups
-- *year-compatibly*: it merges when the years are equal or either side is NULL
-- (preserving the DEV #53 merge) and inserts a new row only when both years are
-- present and differ. The collapsed live rows are repaired by a full re-index
-- after this migration (pre-1.0, single instance,
-- ``feedback_no_backcompat_before_v1``).
--
-- NULL year: SQLite treats NULL as distinct in a UNIQUE index, so two NULL-year
-- same-title rows would not violate the constraint. That is acceptable — the
-- ``upsert`` code path deduplicates them via a SELECT-first lookup
-- (``year IS NULL`` compatibility), and this index is only a backstop against
-- direct INSERTs. Migration 007 already deduped to one row per (title, kind),
-- so no existing (title, kind, year) duplicate exists when this index is built.

-- ---------------------------------------------------------------------------
-- Step 1 — replace the year-blind UNIQUE index with a year-aware one.
-- ---------------------------------------------------------------------------

DROP INDEX IF EXISTS idx_item_title_kind;

CREATE UNIQUE INDEX idx_item_title_kind_year ON media_item(title, kind, year);

-- ---------------------------------------------------------------------------
-- Step 2 — version bump.
-- ---------------------------------------------------------------------------

INSERT INTO schema_version (version) VALUES (10);
PRAGMA user_version = 10;
