-- Schema migration 017 — three media_item facts read from the NFO.
--
-- The library's read services need each medium's overview, poster and the date
-- its provider data was read; the index held none of them. The scanner's item
-- stage fills them from the NFO the scraper already writes: ``overview`` from
-- ``<plot>``, ``poster_url`` from the first ``<thumb aspect="poster">``, and
-- ``date_provider_read`` from the NFO file's mtime (epoch seconds) — the NFO is
-- written when the providers are read, so its mtime is the honest « metadata
-- refreshed ». ``date_metadata_refreshed`` keeps its meaning (« last scanned »).
--
-- Additive: existing rows keep every value and read NULL until their next scan.
-- Applied at web boot by the lifespan migration pass as well as by the CLI.

-- One transaction: a crash mid-script leaves the store as it was before it, so the
-- next attempt snapshots a whole store into its .bak, never a half-applied one.
BEGIN TRANSACTION;

ALTER TABLE media_item ADD COLUMN overview TEXT;
ALTER TABLE media_item ADD COLUMN poster_url TEXT;
ALTER TABLE media_item ADD COLUMN date_provider_read REAL;

INSERT INTO schema_version (version) VALUES (17);
PRAGMA user_version = 17;

COMMIT;
