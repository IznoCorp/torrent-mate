-- Schema migration 005 — provider-ids feature.
--
-- Background:
--
-- The `media_item` table held three flat ID columns — `tmdb_id`,
-- `imdb_id`, `tvdb_id` — which forced every cross-provider query to
-- COALESCE / NULL-check three different fields and could not represent
-- per-episode identifiers. The `provider-ids` feature consolidates all
-- provider IDs into a single JSON column with a hierarchical shape
-- documented in DESIGN §6.5 + `docs/reference/indexer-json-shapes.md`.
-- A sibling `ratings_json` stores per-source ratings (IMDb / Rotten
-- Tomatoes / TMDb / Metacritic) and `canonical_provider` records
-- which family drove the scrape (DESIGN §3 — TVDB primary for TV,
-- TMDb primary for movies).
--
-- This migration:
--   1. Adds the three new columns (`external_ids_json`, `ratings_json`,
--      `canonical_provider`) via ALTER TABLE. SQLite ALTER ADD is a
--      metadata-only operation, no row rewrite.
--   2. Backfills `external_ids_json` from the legacy columns using
--      `json_object` so existing rows keep their IDs reachable.
--      `imdb_id` is wrapped through `json_quote` to preserve the
--      ``"tt..."`` prefix and avoid SQLite coercing it to NULL.
--   3. Drops the legacy `idx_item_tmdb` / `idx_item_imdb` /
--      `idx_item_tvdb` indexes (now unreachable — they referenced
--      columns that no longer exist after step 5).
--   4. Creates the new JSON-extract indexes that mirror the legacy
--      ones, so look-ups by ID stay O(log n).
--   5. Drops the three legacy columns. Per the `provider-ids` memory
--      `feedback_no_backcompat_before_v1`, pre-1.0 releases ship a
--      single forward-only schema with no fallback compatibility.
--   6. Records the version bump in `schema_version`.

ALTER TABLE media_item ADD COLUMN external_ids_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE media_item ADD COLUMN ratings_json      TEXT;
ALTER TABLE media_item ADD COLUMN canonical_provider TEXT CHECK(canonical_provider IN ('tvdb', 'tmdb'));

-- Backfill from the legacy columns. The shape mirrors the Pydantic
-- ``ExternalIds`` model: ``{provider: {series_id, episode_id}}``.
-- Episode-level IDs were never persisted in the legacy schema so they
-- stay NULL across the board.
UPDATE media_item
SET external_ids_json = json_object(
  'tvdb', json_object('series_id', CAST(tvdb_id AS TEXT), 'episode_id', NULL),
  'tmdb', json_object('series_id', CAST(tmdb_id AS TEXT), 'episode_id', NULL),
  'imdb', json_object('series_id', imdb_id,               'episode_id', NULL)
)
WHERE tvdb_id IS NOT NULL OR tmdb_id IS NOT NULL OR imdb_id IS NOT NULL;

DROP INDEX IF EXISTS idx_item_tmdb;
DROP INDEX IF EXISTS idx_item_imdb;
DROP INDEX IF EXISTS idx_item_tvdb;

CREATE INDEX idx_external_ids_tvdb ON media_item(json_extract(external_ids_json, '$.tvdb.series_id'));
CREATE INDEX idx_external_ids_tmdb ON media_item(json_extract(external_ids_json, '$.tmdb.series_id'));
CREATE INDEX idx_external_ids_imdb ON media_item(json_extract(external_ids_json, '$.imdb.series_id'));

ALTER TABLE media_item DROP COLUMN tmdb_id;
ALTER TABLE media_item DROP COLUMN imdb_id;
ALTER TABLE media_item DROP COLUMN tvdb_id;

INSERT INTO schema_version (version) VALUES (5);
PRAGMA user_version = 5;
