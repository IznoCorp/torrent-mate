-- personalscraper/acquire/migrations/006_followed_kind.sql
-- §5 film follows (product-intent Phase 2).
-- The follow table was series-shaped: nothing recorded WHAT is followed, so a
-- film added via search was stored indistinguishably from a series and no film
-- acquisition flow could exist (the sole wanted producer hardcoded
-- kind='episode'). Record the kind at follow time: 'show' (default — every
-- legacy row is a series) or 'movie'. The wanted table already carries a
-- movie/episode kind; this aligns the follow side so detect can produce
-- WantedItem(kind='movie') rows and the dispatch reconciliation can
-- auto-unfollow an acquired film (§5: a film leaves the follow list once
-- acquired; a series never does).
PRAGMA user_version = 6;

ALTER TABLE followed_series ADD COLUMN kind TEXT NOT NULL DEFAULT 'show' CHECK (kind IN ('movie', 'show'));

INSERT INTO schema_version(version) VALUES (6);
