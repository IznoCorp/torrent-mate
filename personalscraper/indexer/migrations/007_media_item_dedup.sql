-- Schema migration 007 — canonical title lookup + dedup + UNIQUE constraint (DEV #53).
--
-- Background:
--
-- ``_upsert_media_item`` (in ``library/scanner.py``) calls
-- ``item_repo.get_by_title_and_kind(title, kind)`` which does an exact-match
-- ``WHERE title = ?``.  When the on-disk directory name includes a release year
-- (e.g. ``Inception (2010)``) the ``title`` field is set to the raw directory
-- name, but earlier rows stored a cleaned ``"Inception"`` (no year suffix).
-- Exact-match fails → a new row is inserted → duplicate ``media_item`` rows
-- accumulate on every ``scan_library()`` call (1863 observed in one incident).
--
-- The code fix ships in the same commit (``item_repo._canonical_title`` strips
-- the `` (YYYY)`` suffix at lookup AND write time), but the DB must be cleaned
-- first so that canonicalised lookups match canonicalised stored titles.
--
-- This migration:
--   1. Canonicalises every stored ``title`` by stripping a trailing
--      `` (YYYY)`` suffix where present (SQLite GLOB + SUBSTR, no regex
--      extension available).
--   2. Deduplicates: for each ``(title, kind)`` group with >1 row after
--      canonicalisation, keeps the row with the lowest ``id`` (oldest),
--      reparents child FKs where safe, then deletes the higher-id rows.
--      ``date_modified`` on the keeper is bumped to the MAX of the group.
--   3. Adds a ``UNIQUE(title, kind)`` index to prevent future duplicates
--      at the DB layer (the upsert code path now canonicalises, but a
--      direct INSERT would still bypass it).
--   4. Bumps ``user_version`` to 7 and inserts the tracking row.
--
-- This migration is written for a single operator instance (pre-1.0,
-- ``feedback_no_backcompat_before_v1.md``).  No attempt is made to be a
-- generic downstream-safe migration.
--
-- Edge case documented: ``"Year (2020) (2020)"`` — a movie titled "Year (2020)"
-- whose directory already includes the year, then the scraper appends another
-- `` (2020)``.  Canonicalisation strips only the LAST occurrence (one pass of
-- SUBSTR), leaving ``"Year (2020)"``.  This is acceptable: the title genuinely
-- contains a year-like phrase and further stripping would be destructive.
-- In real data this pattern is extremely unlikely (no instance observed).
--
-- Edge case: ``"1984 (1984)"`` — a movie whose base title IS a year AND its
-- directory carries the release year suffix.  Canonicalisation strips the
-- suffix leaving ``"1984"``, which is correct (the official title is "1984").
-- ``"2001 (2001)"`` (2001: A Space Odyssey) is similar.  These titles are
-- logged in ``_migration_007_changes`` for operator review.

-- ---------------------------------------------------------------------------
-- Step 0 — log canonicalised titles for operator review (SF-M6).
-- Kept as a persistent real table so the operator can inspect it after
-- the migration completes.  Drop it manually once reviewed.
-- ---------------------------------------------------------------------------

CREATE TABLE _migration_007_changes (
    id INTEGER PRIMARY KEY,
    old_title TEXT NOT NULL,
    new_title TEXT NOT NULL
);

-- LENGTH(title) > 7 guards against a degenerate case where the title is
-- literally ' (YYYY)' (8 chars: space + paren + 4 digits + paren) or a
-- 7-char ' (YYY)' that would slip through GLOB but produce an empty
-- title after SUBSTR(title, 1, LENGTH(title) - 7). The GLOB itself
-- already forces the trailing ' (NNNN)' shape; the SUBSTR offset checks
-- are redundant once that's true but kept for defence-in-depth.
INSERT INTO _migration_007_changes (old_title, new_title)
SELECT title, TRIM(SUBSTR(title, 1, LENGTH(title) - 7))
  FROM media_item
 WHERE title GLOB '* ([0-9][0-9][0-9][0-9])'
   AND LENGTH(title) > 7
   AND SUBSTR(title, -6, 1) = '('
   AND SUBSTR(title, -1, 1) = ')';

-- ---------------------------------------------------------------------------
-- Step 1 — canonicalise stored titles
-- ---------------------------------------------------------------------------

UPDATE media_item
SET title = TRIM(SUBSTR(title, 1, LENGTH(title) - 7))
WHERE title GLOB '* ([0-9][0-9][0-9][0-9])'
  AND LENGTH(title) > 7
  AND SUBSTR(title, -6, 1) = '('
  AND SUBSTR(title, -1, 1) = ')';

-- ---------------------------------------------------------------------------
-- Step 2 — build a dedup map: for every (title, kind) group with >1 row,
-- keep the lowest ``id``.  All other rows in the group are duplicates.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE _dedup_map AS
SELECT m.id AS dup_id,
       (SELECT MIN(m2.id)
          FROM media_item m2
         WHERE m2.title = m.title
           AND m2.kind  = m.kind) AS keeper_id
  FROM media_item m
 WHERE EXISTS (
         SELECT 1
           FROM media_item m2
          WHERE m2.title = m.title
            AND m2.kind  = m.kind
            AND m2.id    < m.id
       );

-- ---------------------------------------------------------------------------
-- Step 3 — reparent child FKs to the keeper so CASCADE does not wipe useful
-- data.  We process the simplest FKs first (no composite-key risks).
-- ---------------------------------------------------------------------------

-- 3a. media_release.item_id → FK with UNIQUE(item_id, episode_id, quality,
--     edition, primary_lang).  Only reparent releases that do NOT collide
--     with a release the keeper already has for the same signature.
--     NOTE: IS operator is stricter than SQLite UNIQUE — UNIQUE treats
--     NULLs as distinct, IS treats them as equal.  This guard is therefore
--     over-conservative on NULL-NULL pairs (releases with all-NULL
--     signatures on both duplicate AND keeper get marked as conflict →
--     duplicate's release gets CASCADE-deleted at step 5 instead of
--     reparented).  Acceptable: prefers data deletion over UNIQUE-violation
--     abort.
--     Colliding releases stay with the duplicate and get CASCADE-deleted
--     (keeper's version already covers that tuple).
UPDATE media_release
   SET item_id = (
         SELECT keeper_id FROM _dedup_map WHERE dup_id = media_release.item_id
       )
 WHERE item_id IN (SELECT dup_id FROM _dedup_map)
   AND NOT EXISTS (
         SELECT 1
           FROM media_release mr2
          WHERE mr2.item_id = (
                  SELECT keeper_id FROM _dedup_map WHERE dup_id = media_release.item_id
                )
            AND mr2.episode_id IS media_release.episode_id
            AND mr2.quality IS media_release.quality
            AND mr2.edition IS media_release.edition
            AND mr2.primary_lang IS media_release.primary_lang
       );

-- 3b. item_issue has composite PK (item_id, type) but the (type) alone is not
--     UNIQUE — a direct UPDATE is safe.
UPDATE item_issue
   SET item_id = (
         SELECT keeper_id FROM _dedup_map WHERE dup_id = item_issue.item_id
       )
 WHERE item_id IN (SELECT dup_id FROM _dedup_map);

-- 3c. scan_event.item_id is ON DELETE SET NULL, but we'd rather keep the link
--     alive.  Reparent to the keeper.
UPDATE scan_event
   SET item_id = (
         SELECT keeper_id FROM _dedup_map WHERE dup_id = scan_event.item_id
       )
 WHERE item_id IN (SELECT dup_id FROM _dedup_map);

-- 3d. season.item_id — has UNIQUE(item_id, number).  Only reparent seasons
--     that do NOT collide with a season the keeper already has for the same
--     number.  Colliding seasons stay with the duplicate and get CASCADE-
--     deleted (keeper's version already covers that season number).
UPDATE season
   SET item_id = (
         SELECT keeper_id FROM _dedup_map WHERE dup_id = season.item_id
       )
 WHERE item_id IN (SELECT dup_id FROM _dedup_map)
   AND NOT EXISTS (
         SELECT 1
           FROM season s2
          WHERE s2.item_id = (
                  SELECT keeper_id FROM _dedup_map WHERE dup_id = season.item_id
                )
            AND s2.number = season.number
       );

-- 3e. item_attribute(key, value) — composite PK (item_id, key).
--     Copy non-conflicting attrs to the keeper via INSERT OR IGNORE.
--     Conflicting attrs (same key) stay with the duplicate (CASCADE-deleted).
INSERT OR IGNORE INTO item_attribute (item_id, key, value)
SELECT d.keeper_id, a.key, a.value
  FROM item_attribute a
  JOIN _dedup_map d ON d.dup_id = a.item_id;

-- ---------------------------------------------------------------------------
-- Step 4 — merge date_modified: the keeper gets the most recent timestamp
-- from the whole duplicate group.
-- ---------------------------------------------------------------------------

UPDATE media_item
   SET date_modified = (
         SELECT MAX(m2.date_modified)
           FROM media_item m2
           JOIN _dedup_map d ON d.dup_id = m2.id
          WHERE d.keeper_id = media_item.id
       )
 WHERE id IN (SELECT DISTINCT keeper_id FROM _dedup_map);

UPDATE media_item
   SET date_modified = MAX(
         date_modified,
         (SELECT m2.date_modified
            FROM media_item m2
            JOIN _dedup_map d ON d.dup_id = m2.id
           WHERE d.keeper_id = media_item.id
           LIMIT 1)
       )
 WHERE EXISTS (
         SELECT 1 FROM _dedup_map d WHERE d.keeper_id = media_item.id
       );

-- ---------------------------------------------------------------------------
-- Step 5 — delete the duplicate rows.  ON DELETE CASCADE cleans up remaining
-- child rows that were not reparented above (conflicting seasons, conflicting
-- item_attribute keys, any remaining media_release / item_issue rows).
-- ---------------------------------------------------------------------------

DELETE FROM media_item WHERE id IN (SELECT dup_id FROM _dedup_map);

-- ---------------------------------------------------------------------------
-- Step 6 — add UNIQUE constraint so the DB itself rejects future duplicates.
-- SQLite implements UNIQUE via a unique index.
-- ---------------------------------------------------------------------------

CREATE UNIQUE INDEX idx_item_title_kind ON media_item(title, kind);

-- ---------------------------------------------------------------------------
-- Step 7 — version bump.
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS _dedup_map;

INSERT INTO schema_version (version) VALUES (7);
PRAGMA user_version = 7;
