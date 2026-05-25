-- 008 — Auto-maintain season.episode_count via triggers + one-shot backfill of pre-trigger drift.

-- Step 1 — one-shot backfill: correct any existing drift before triggers take over.
-- Mirrors the logic in ``personalscraper commands library fix-season-counts``
-- but runs once at migration time so that the triggers start from a clean state.
UPDATE season
SET episode_count = (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
WHERE episode_count != (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id);

-- Step 2 — AFTER INSERT on episode: increment the parent season's episode_count.
CREATE TRIGGER trg_season_episode_count_inc
AFTER INSERT ON episode
BEGIN
  UPDATE season SET episode_count = episode_count + 1 WHERE id = NEW.season_id;
END;

-- Step 3 — AFTER DELETE on episode: decrement the parent season's episode_count.
CREATE TRIGGER trg_season_episode_count_dec
AFTER DELETE ON episode
BEGIN
  UPDATE season SET episode_count = episode_count - 1 WHERE id = OLD.season_id;
END;

-- Step 4 — AFTER UPDATE OF season_id on episode: move the count from old season
-- to new season (rare — episode re-parenting — but must not drift).
CREATE TRIGGER trg_season_episode_count_move
AFTER UPDATE OF season_id ON episode
WHEN NEW.season_id != OLD.season_id
BEGIN
  UPDATE season SET episode_count = episode_count - 1 WHERE id = OLD.season_id;
  UPDATE season SET episode_count = episode_count + 1 WHERE id = NEW.season_id;
END;

-- Step 5 — version bump.
INSERT INTO schema_version (version) VALUES (8);
PRAGMA user_version = 8;
