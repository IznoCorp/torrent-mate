-- Schema migration 001 — initial indexer database

-- ---------------------------------------------------------------------------
-- Disks: stable identity by volume UUID, never by mount path.
-- A disk row exists per known volume; mount_path is the *current* mount, NULL
-- when unmounted. last_seen_at is updated whenever the disk is observed mounted.
-- merkle_root is a 16-char hex (xxh3_64) over sorted (path_id, size, mtime_ns,
-- oshash) of every file on the disk; cheap to recompute, lets the scanner
-- fast-skip an entire disk if unchanged.
-- ---------------------------------------------------------------------------
CREATE TABLE disk (
  id           INTEGER PRIMARY KEY,
  uuid         TEXT NOT NULL UNIQUE,        -- volume UUID (from `diskutil info -plist`)
  label        TEXT NOT NULL,               -- display label (e.g. "Disk1")
  mount_path   TEXT,                        -- current mount, may change
  last_seen_at INTEGER,                     -- unix epoch seconds; NULL = never
  merkle_root  TEXT,                        -- xxh3_64 hex; NULL until first scan
  is_mounted   INTEGER NOT NULL DEFAULT 0 CHECK(is_mounted IN (0,1)),
  unreachable_strikes INTEGER NOT NULL DEFAULT 0,
  CHECK ((is_mounted = 0 AND mount_path IS NULL) OR (is_mounted = 1 AND mount_path IS NOT NULL))
);
-- UNIQUE(uuid) already implies an index; no separate idx_disk_uuid needed.

-- ---------------------------------------------------------------------------
-- Path: deduplicates the (disk_id, rel_path) prefix shared by many files.
-- rel_path is the directory portion relative to the disk mount, e.g.
-- "001-MOVIES/Inception (2010)". A media_file references path_id + filename.
-- ---------------------------------------------------------------------------
CREATE TABLE path (
  id        INTEGER PRIMARY KEY,
  disk_id   INTEGER NOT NULL REFERENCES disk(id) ON DELETE RESTRICT,
  rel_path  TEXT NOT NULL,
  dir_mtime_ns INTEGER,                     -- for subtree skip optimization
  last_walked_at INTEGER,                   -- epoch s; used by `library status` to display
                                            -- per-subtree freshness; also feeds the "paranoia
                                            -- branch" in §17.1 (paths walked < 24 h ago short-
                                            -- circuit on dir-mtime, paths older are always re-stat'd)
  UNIQUE(disk_id, rel_path)
);
CREATE INDEX idx_path_disk_rel ON path(disk_id, rel_path);

-- ---------------------------------------------------------------------------
-- Media item: a single work — one movie, one TV show. kind disambiguates.
-- title_sort strips French articles ("Le ", "La ", "Les ") for sorting.
-- artwork_json is a small object (poster:bool, fanart:bool, ...) — querying
-- happens via JSON1; replacing it never grows the table.
-- ---------------------------------------------------------------------------
CREATE TABLE media_item (
  id            INTEGER PRIMARY KEY,
  kind          TEXT NOT NULL CHECK(kind IN ('movie','show')),
  title         TEXT NOT NULL,
  title_sort    TEXT NOT NULL,
  original_title TEXT,
  year          INTEGER,
  category_id   TEXT NOT NULL,              -- ref logical category from config
  tmdb_id       INTEGER,
  imdb_id       TEXT,
  tvdb_id       INTEGER,
  nfo_status    TEXT CHECK(nfo_status IN ('missing','invalid','valid')),
  artwork_json  TEXT,                       -- {"poster":1,"fanart":1,...}
  date_created           INTEGER NOT NULL,  -- unix s
  date_modified          INTEGER NOT NULL,  -- last index update
  date_metadata_refreshed INTEGER,          -- last TMDB/TVDB scrape
  is_locked     INTEGER NOT NULL DEFAULT 0, -- skip auto-rescrape if 1
  preferred_lang TEXT NOT NULL DEFAULT 'fr'
);
CREATE INDEX idx_item_tmdb ON media_item(tmdb_id) WHERE tmdb_id IS NOT NULL;
CREATE INDEX idx_item_imdb ON media_item(imdb_id) WHERE imdb_id IS NOT NULL;
CREATE INDEX idx_item_tvdb ON media_item(tvdb_id) WHERE tvdb_id IS NOT NULL;
CREATE INDEX idx_item_kind_sort ON media_item(kind, title_sort);
CREATE INDEX idx_item_category ON media_item(category_id);

-- ---------------------------------------------------------------------------
-- Flex attributes (beets pattern): extend the schema without ALTER TABLE.
-- Used for trailer_found, plex_watched, user tags, future-unknown columns.
-- ---------------------------------------------------------------------------
CREATE TABLE item_attribute (
  item_id INTEGER NOT NULL REFERENCES media_item(id) ON DELETE CASCADE,
  key     TEXT NOT NULL,
  value   TEXT,
  PRIMARY KEY(item_id, key)
);
CREATE INDEX idx_attr_key_value ON item_attribute(key, value);

-- ---------------------------------------------------------------------------
-- TV hierarchy.
-- ---------------------------------------------------------------------------
CREATE TABLE season (
  id            INTEGER PRIMARY KEY,
  item_id       INTEGER NOT NULL REFERENCES media_item(id) ON DELETE CASCADE,
  number        INTEGER NOT NULL CHECK(number >= 0),
  episode_count INTEGER NOT NULL DEFAULT 0,
  has_poster    INTEGER NOT NULL DEFAULT 0 CHECK(has_poster IN (0,1)),
  episodes_with_nfo INTEGER NOT NULL DEFAULT 0,
  UNIQUE(item_id, number)
);

-- Cross-table invariant: a season can only attach to a media_item with kind='show'.
-- Enforced by trigger because SQLite CHECK cannot reference other tables.
CREATE TRIGGER trg_season_requires_show
BEFORE INSERT ON season
BEGIN
  SELECT RAISE(ABORT, 'season.item_id must reference a media_item with kind=''show''')
  WHERE (SELECT kind FROM media_item WHERE id = NEW.item_id) <> 'show';
END;

CREATE TABLE episode (
  id        INTEGER PRIMARY KEY,
  season_id INTEGER NOT NULL REFERENCES season(id) ON DELETE CASCADE,
  number    INTEGER NOT NULL CHECK(number >= 0),
  title     TEXT,
  UNIQUE(season_id, number)
);
-- episode → season → media_item invariant is transitive: episode is implicitly
-- show-only via its FK chain, no separate trigger needed.

-- ---------------------------------------------------------------------------
-- Release: a specific version of a work (1080p-FR, 4K-EN, Director's Cut).
-- Either item_id or episode_id is set, never both, never neither.
-- ---------------------------------------------------------------------------
CREATE TABLE media_release (
  id           INTEGER PRIMARY KEY,
  item_id      INTEGER REFERENCES media_item(id) ON DELETE CASCADE,
  episode_id   INTEGER REFERENCES episode(id) ON DELETE CASCADE,
  quality      TEXT,                        -- '1080p','2160p','SD'
  edition      TEXT,                        -- 'Director Cut','Extended'
  primary_lang TEXT,
  CHECK ((item_id IS NULL) <> (episode_id IS NULL)),
  -- Two releases of the same work cannot share the same (quality, edition,
  -- primary_lang) triple. NULLs are distinct in SQLite UNIQUE, so a partial
  -- index handles the all-NULL "default release" case.
  UNIQUE(item_id, episode_id, quality, edition, primary_lang)
);
CREATE INDEX idx_release_item ON media_release(item_id);
CREATE INDEX idx_release_episode ON media_release(episode_id);

-- ---------------------------------------------------------------------------
-- Physical file: identified by (path_id, filename); cheap drift signal in
-- (size_bytes, mtime_ns, ctime_ns); rename-survival via oshash; full content
-- check via xxh3_full only on the rare collision path.
-- scan_generation: bumped at start of each scan; rows with old generation are
-- candidates for soft-delete or drift investigation.
-- ---------------------------------------------------------------------------
CREATE TABLE media_file (
  id              INTEGER PRIMARY KEY,
  release_id      INTEGER NOT NULL REFERENCES media_release(id) ON DELETE CASCADE,
  path_id         INTEGER NOT NULL REFERENCES path(id) ON DELETE RESTRICT,
  filename        TEXT NOT NULL,
  size_bytes      INTEGER NOT NULL CHECK(size_bytes >= 0),
  mtime_ns        INTEGER NOT NULL CHECK(mtime_ns >= 0),
  ctime_ns        INTEGER,
  oshash          TEXT NOT NULL,            -- 16-char hex; always computed
  xxh3_partial    TEXT,                     -- 16-char hex; only when racy/conflict
  xxh3_full       TEXT,                     -- 16-char hex; rare manual repair only
  scan_generation INTEGER NOT NULL,
  last_verified_at INTEGER NOT NULL,        -- epoch seconds
  enriched_at     INTEGER,                  -- epoch seconds; NULL = never enriched. Set by `enrich` mode after pymediainfo + NFO + artwork. enrich criterion is `enriched_at IS NULL OR enriched_at < (SELECT MAX(mtime_ns)/1000000000 FROM media_file f2 WHERE f2.id=media_file.id)`.
  miss_strikes    INTEGER NOT NULL DEFAULT 0,
  deleted_at      INTEGER,                  -- soft-delete tombstone
  UNIQUE(path_id, filename)
);
CREATE INDEX idx_file_release ON media_file(release_id);
CREATE INDEX idx_file_oshash ON media_file(oshash);
CREATE INDEX idx_file_scan_gen ON media_file(scan_generation);
CREATE INDEX idx_file_deleted ON media_file(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_file_enrich_pending ON media_file(enriched_at) WHERE enriched_at IS NULL AND deleted_at IS NULL;

-- ---------------------------------------------------------------------------
-- Stream metadata from pymediainfo (one row per video/audio/subtitle stream).
-- ---------------------------------------------------------------------------
CREATE TABLE media_stream (
  id        INTEGER PRIMARY KEY,
  file_id   INTEGER NOT NULL REFERENCES media_file(id) ON DELETE CASCADE,
  idx       INTEGER NOT NULL,
  kind      TEXT NOT NULL CHECK(kind IN ('video','audio','subtitle')),
  codec     TEXT,
  lang      TEXT,
  channels  INTEGER,
  width     INTEGER,
  height    INTEGER,
  duration_ms INTEGER,
  bitrate   INTEGER,
  UNIQUE(file_id, idx)
);
CREATE INDEX idx_stream_kind_codec ON media_stream(kind, codec);
CREATE INDEX idx_stream_lang ON media_stream(lang);

-- ---------------------------------------------------------------------------
-- Issue tags from scanner heuristics (junk files, ntfs_unsafe, etc.).
-- ---------------------------------------------------------------------------
CREATE TABLE item_issue (
  item_id INTEGER NOT NULL REFERENCES media_item(id) ON DELETE CASCADE,
  type    TEXT NOT NULL,                    -- 'junk_files','ntfs_unsafe',...
  detail  TEXT,
  detected_at INTEGER NOT NULL,
  PRIMARY KEY(item_id, type)
);

-- ---------------------------------------------------------------------------
-- Outbox: write-through events from dispatch/process/trailers; drained by
-- the indexer in a separate transaction.
-- ---------------------------------------------------------------------------
CREATE TABLE index_outbox (
  id           INTEGER PRIMARY KEY,
  source       TEXT NOT NULL CHECK(source IN ('dispatch','scraper','trailers','scanner')),
  op           TEXT NOT NULL CHECK(op IN ('move','nfo_write','artwork_write','trailer_download')),
  payload_json TEXT NOT NULL,
  created_at   INTEGER NOT NULL,
  processed_at INTEGER,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done','failed','deferred'))
);
CREATE INDEX idx_outbox_pending ON index_outbox(status, created_at) WHERE status='pending';

-- ---------------------------------------------------------------------------
-- Hinted handoff: writes against unmounted disks parked here, replayed on
-- remount.
-- ---------------------------------------------------------------------------
CREATE TABLE pending_op (
  id           INTEGER PRIMARY KEY,
  disk_id      INTEGER NOT NULL REFERENCES disk(id) ON DELETE CASCADE,
  op           TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at   INTEGER NOT NULL,
  replayed_at  INTEGER
);
CREATE INDEX idx_pending_disk ON pending_op(disk_id);

-- ---------------------------------------------------------------------------
-- Repair queue: drift detected during scan → enqueued, drained by repair worker.
-- ---------------------------------------------------------------------------
CREATE TABLE repair_queue (
  id           INTEGER PRIMARY KEY,
  scope        TEXT NOT NULL CHECK(scope IN ('file','item','release','subtree','path','disk')),
  scope_id     INTEGER,                     -- application-managed soft FK depending on scope
  reason       TEXT NOT NULL,
  payload_json TEXT,
  enqueued_at  INTEGER NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','done','failed')),
  attempted_at INTEGER,
  attempts     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_repair_pending ON repair_queue(status, enqueued_at) WHERE status='pending';

-- ---------------------------------------------------------------------------
-- Audit: scan runs and per-event log (Lightroom develop-history pattern).
-- ---------------------------------------------------------------------------
CREATE TABLE scan_run (
  id          INTEGER PRIMARY KEY,
  generation  INTEGER NOT NULL,
  mode        TEXT NOT NULL CHECK(mode IN ('quick','incremental','enrich','full','verify','repair')),
  disk_filter TEXT,                        -- NULL when scanning all disks; disk.label when scoped via --disk
  started_at  INTEGER NOT NULL,
  finished_at INTEGER,
  last_path   TEXT,                          -- for crash-resume
  status      TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','ok','failed','aborted')),
  stats_json  TEXT
);

CREATE TABLE scan_event (
  id        INTEGER PRIMARY KEY,
  scan_id   INTEGER NOT NULL REFERENCES scan_run(id) ON DELETE CASCADE,
  ts        INTEGER NOT NULL,
  item_id   INTEGER REFERENCES media_item(id) ON DELETE SET NULL,
  file_id   INTEGER REFERENCES media_file(id) ON DELETE SET NULL,
  event     TEXT NOT NULL,
  payload_json TEXT
);
CREATE INDEX idx_event_scan_event ON scan_event(scan_id, event);
CREATE INDEX idx_event_item_ts ON scan_event(item_id, ts);

-- ---------------------------------------------------------------------------
-- Tombstone: central soft-delete record.
-- ---------------------------------------------------------------------------
CREATE TABLE deleted_item (
  id          INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL CHECK(kind IN ('item','file','release')),
  original_id INTEGER NOT NULL,
  deleted_at  INTEGER NOT NULL,
  reason      TEXT,
  payload_json TEXT
);
CREATE INDEX idx_deleted_at ON deleted_item(deleted_at);

-- Schema-version singleton (PRAGMA user_version is also set in lockstep).
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version(version) VALUES (1);

-- ---------------------------------------------------------------------------
-- Generated columns for queryable JSON fields (§6.5).
-- Avoids json_extract() in WHERE clauses for the most common artwork queries.
-- ---------------------------------------------------------------------------
ALTER TABLE media_item ADD COLUMN has_poster INTEGER
  GENERATED ALWAYS AS (json_extract(artwork_json, '$.poster')) VIRTUAL;
CREATE INDEX idx_item_has_poster ON media_item(has_poster) WHERE has_poster = 1;

ALTER TABLE media_item ADD COLUMN has_fanart INTEGER
  GENERATED ALWAYS AS (json_extract(artwork_json, '$.fanart')) VIRTUAL;
CREATE INDEX idx_item_has_fanart ON media_item(has_fanart) WHERE has_fanart = 1;

PRAGMA user_version = 1;
