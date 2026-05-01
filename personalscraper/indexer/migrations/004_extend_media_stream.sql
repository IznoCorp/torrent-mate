-- Schema migration 004 — extend media_stream with HDR / Atmos / default / forced / format flags.
--
-- Background:
--
-- Stage B (`library-index --mode enrich`) extracts media stream rows via
-- pymediainfo and persists codec, language, channel count, dimensions,
-- duration, and bitrate.  Five fields that pymediainfo also exposes were
-- not stored, so the index-aware library tooling
-- (`analyze_from_index` / `validate_from_index`) had to either skip them
-- or fall back to coarse heuristics:
--
--   * HDR detection (HDR10, HDR10+, Dolby Vision, HLG)
--   * Dolby Atmos detection (Atmos / TrueHD-Atmos)
--   * Default-track flag (audio + subtitle)
--   * Forced-subtitle flag
--   * Subtitle format normalisation (srt, pgs, ass, dvd_subtitle, ...)
--
-- Without these fields, `library-recommend --from-index` cannot recommend
-- 4K HDR upgrades (the recommender path that uses `f.video.hdr`) and
-- audio-profile detection silently downgrades Atmos releases to plain
-- E-AC-3.  Adding them as nullable columns keeps the migration cheap
-- (no row rewrite) and forward-compatible: pre-existing rows keep
-- ``NULL`` until re-enriched.
--
-- This migration:
--   1. Adds five nullable columns to ``media_stream`` via ``ALTER TABLE``
--      (cheap, no row rewrite — SQLite ALTER TABLE ADD COLUMN is metadata-only).
--   2. Records the version bump in ``schema_version``.

ALTER TABLE media_stream ADD COLUMN hdr_format TEXT;       -- HDR standard ("HDR10", "HDR10+", "Dolby Vision", "HLG"), NULL when SDR
ALTER TABLE media_stream ADD COLUMN is_atmos   INTEGER;    -- 0 / 1 boolean; NULL = unknown (pre-migration row)
ALTER TABLE media_stream ADD COLUMN is_default INTEGER;    -- 0 / 1 boolean; NULL = unknown (pre-migration row)
ALTER TABLE media_stream ADD COLUMN forced     INTEGER;    -- 0 / 1 boolean; NULL = unknown / not a subtitle
ALTER TABLE media_stream ADD COLUMN format     TEXT;       -- subtitle format ("srt", "pgs", "ass", "dvd_subtitle", ...)

INSERT INTO schema_version (version) VALUES (4);
PRAGMA user_version = 4;
