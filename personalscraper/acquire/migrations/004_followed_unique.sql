-- personalscraper/acquire/migrations/004_followed_unique.sql
-- followed_series dedup + UNIQUE index on media_ref_json (webui-ux Phase 6).
--
-- `media_ref_json` is canonical fixed-key JSON ({"tvdb_id":..,"tmdb_id":..,
-- "imdb_id":..}) emitted by _media_ref_to_json → stable text, so a UNIQUE
-- index on the raw column reliably enforces "one followed row per provider-ID
-- tuple".  Before the index can be created, existing duplicate rows (which the
-- old plain-INSERT add() could accumulate under the racy app-level dedup) must
-- be collapsed, or CREATE UNIQUE INDEX would fail with a constraint violation.
--
-- Dedup strategy: keep the LOWEST id per media_ref_json (the survivor), reattach
-- any wanted.followed_id pointing at a loser to that survivor, then delete the
-- losers.  Deleting (rather than deactivating) the losers is safe here because:
--   * pre-1.0, single instance, no external consumers of loser ids;
--   * every dependent FK (wanted.followed_id) is reattached first;
--   * a leftover inactive duplicate would still violate the UNIQUE index.
--
-- Active-flag preservation: collapsing to MIN(id) alone would silently DROP a
-- re-follow when the low-id survivor was unfollowed (active=0) and a higher-id
-- duplicate re-followed it (active=1) — the survivor would keep active=0 and the
-- active row would be deleted.  So BEFORE deleting the losers, promote the
-- survivor to active=1 whenever ANY row in its media_ref_json group is active.
-- This keeps the survivor id stable (MIN) while never dropping an active follow.
PRAGMA user_version = 4;

-- Step 0: preserve active-ness — set each survivor (MIN(id) per media_ref_json)
-- active=1 when ANY duplicate in its group is active, so a re-follow on a
-- higher-id row is not lost when the losers are deleted in Step 2.
UPDATE followed_series
SET active = 1
WHERE id IN (
    SELECT MIN(id) FROM followed_series GROUP BY media_ref_json HAVING MAX(active) = 1
);

-- Step 1: reattach dependent wanted rows from each loser to its survivor.
-- The survivor is the MIN(id) row sharing the same media_ref_json.
UPDATE wanted
SET followed_id = (
    SELECT MIN(fs2.id)
    FROM followed_series fs2
    JOIN followed_series fs1 ON fs1.media_ref_json = fs2.media_ref_json
    WHERE fs1.id = wanted.followed_id
)
WHERE followed_id IS NOT NULL
  AND followed_id <> (
    SELECT MIN(fs2.id)
    FROM followed_series fs2
    JOIN followed_series fs1 ON fs1.media_ref_json = fs2.media_ref_json
    WHERE fs1.id = wanted.followed_id
  );

-- Step 2: delete the loser rows (every id that is not the MIN(id) for its
-- media_ref_json).  After Step 1 no wanted row references a loser.
DELETE FROM followed_series
WHERE id NOT IN (
    SELECT MIN(id) FROM followed_series GROUP BY media_ref_json
);

-- Step 3: enforce uniqueness so future duplicate inserts conflict instead of
-- accumulating (store.add uses ON CONFLICT(media_ref_json) DO UPDATE).
CREATE UNIQUE INDEX IF NOT EXISTS ux_followed_media_ref
    ON followed_series (media_ref_json);

INSERT INTO schema_version(version) VALUES (4);
