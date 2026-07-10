-- Schema migration 013 — scrape_decision table for interactive scraping queue (S5, scrape-arbiter).
--
-- Background:
--
-- The batch scraper auto-picks TMDB/TVDB matches. Three situations produce silent bad
-- outcomes today: scores below LOW_CONFIDENCE (0.5) are skipped forever, mid-band matches
-- (0.5–0.8) are auto-accepted blindly, and ambiguous matches (two candidates within
-- AMBIGUITY_DELTA) resolve silently.  The scrape-arbiter feature (#184) introduces a
-- decision queue filled by batch runs plus a web surface to drain it — the batch never
-- blocks; the seam is an async queue + immediate targeted re-drive, not a mid-run pause.
--
-- One row per staging item awaiting an identity decision.  Columns:
--
--   id              — auto-increment primary key
--   staging_path    — absolute path, NFC-normalized by the writer (macFUSE NFD gotcha)
--   media_kind      — 'movie' | 'tvshow'
--   extracted_title — title guessed from the folder name
--   extracted_year  — year guessed, NULL if none
--   "trigger"       — 'below_threshold' | 'mid_band' | 'ambiguous'
--   candidates_json — snapshot: top-5 scored candidates as a JSON array
--   status          — 'pending' | 'resolved' | 'dismissed' | 'superseded'
--   resolution_json — {provider, provider_id, via: 'pick'|'search_override', …}
--   run_uid         — run that enqueued (or last refreshed) the row
--   created_at      — epoch seconds (time.time())
--   updated_at      — epoch seconds (time.time())
--   resolved_at     — epoch seconds (time.time()), NULL until resolved
--
-- Upsert semantics (by staging_path, NFC): a batch run refreshes candidates_json,
-- "trigger", run_uid, updated_at of a pending row; it never resurrects resolved /
-- dismissed / superseded rows.  Timestamps are Unix-epoch REAL (time.time()).

-- ---------------------------------------------------------------------------
-- Step 1 — create the scrape_decision table.
-- ---------------------------------------------------------------------------

CREATE TABLE scrape_decision (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    staging_path    TEXT    UNIQUE NOT NULL,   -- NFC-normalized by the writer
    media_kind      TEXT    NOT NULL,           -- 'movie' | 'tvshow'
    extracted_title TEXT    NOT NULL,           -- title guessed from the folder name
    extracted_year  INTEGER,                    -- year guessed, NULL if none
    "trigger"       TEXT    NOT NULL,           -- 'below_threshold' | 'mid_band' | 'ambiguous'
    candidates_json TEXT    NOT NULL,           -- snapshot: top-5 scored candidates (JSON array)
    status          TEXT    NOT NULL DEFAULT 'pending',  -- 'pending' | 'resolved' | 'dismissed' | 'superseded'
    resolution_json TEXT,                       -- {provider, provider_id, via, ...}
    run_uid         TEXT,                       -- run that enqueued (or last refreshed) the row
    created_at      REAL    NOT NULL,           -- epoch seconds (time.time())
    updated_at      REAL    NOT NULL,           -- epoch seconds (time.time())
    resolved_at     REAL                        -- epoch seconds (time.time()), NULL until resolved
);

-- ---------------------------------------------------------------------------
-- Step 2 — index on status for the web-UI queue filter queries.
-- ---------------------------------------------------------------------------

CREATE INDEX idx_scrape_decision_status ON scrape_decision(status);

-- ---------------------------------------------------------------------------
-- Step 3 — version bump.
-- ---------------------------------------------------------------------------

INSERT INTO schema_version (version) VALUES (13);
PRAGMA user_version = 13;
