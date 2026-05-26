-- 008 — Auto-maintain season.episode_count via triggers + one-shot backfill of pre-trigger drift.

-- Step 1 — one-shot backfill: correct any existing drift before triggers take over.
-- Mirrors the logic in ``personalscraper commands library fix-season-counts``
-- but runs once at migration time so that the triggers start from a clean state.
UPDATE season
SET episode_count = (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
WHERE episode_count != (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id);

-- Step 2 — AFTER INSERT on episode: recompute the parent season's episode_count.
-- Uses COUNT(*) over all episode rows for the season, making the trigger
-- idempotent regardless of the season's prior episode_count value (the
-- scanner pre-populates episode_count=video_file_count before inserting
-- episode stubs — an inc/dec trigger would double-count).
CREATE TRIGGER trg_season_episode_count_after_insert
AFTER INSERT ON episode
BEGIN
  UPDATE season
  SET episode_count = (SELECT COUNT(*) FROM episode WHERE season_id = NEW.season_id)
  WHERE id = NEW.season_id;
END;

-- Step 3 — AFTER DELETE on episode: recompute the affected season's episode_count.
CREATE TRIGGER trg_season_episode_count_after_delete
AFTER DELETE ON episode
BEGIN
  UPDATE season
  SET episode_count = (SELECT COUNT(*) FROM episode WHERE season_id = OLD.season_id)
  WHERE id = OLD.season_id;
END;

-- Step 4 — AFTER UPDATE OF season_id on episode: recompute BOTH the old and new
-- season (rare — episode re-parenting — but must not drift).
CREATE TRIGGER trg_season_episode_count_after_update
AFTER UPDATE OF season_id ON episode
WHEN NEW.season_id != OLD.season_id
BEGIN
  UPDATE season
  SET episode_count = (SELECT COUNT(*) FROM episode WHERE season_id = OLD.season_id)
  WHERE id = OLD.season_id;
  UPDATE season
  SET episode_count = (SELECT COUNT(*) FROM episode WHERE season_id = NEW.season_id)
  WHERE id = NEW.season_id;
END;

-- Step 5 — version bump.
INSERT INTO schema_version (version) VALUES (8);
PRAGMA user_version = 8;
