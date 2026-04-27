-- Schema migration 002 — make media_file.release_id and media_file.oshash nullable
--
-- Rationale: Stage A (scanner walk) inserts media_file rows before any release exists
-- and before OSHash is computed for non-video / symlink files.  The previous schema
-- declared both columns NOT NULL, which forced workaround sentinels (release_id=0 and
-- oshash='') that violated FK integrity and introduced hidden technical debt.
--
-- SQLite does not support ALTER COLUMN ... DROP NOT NULL, so we recreate the table.
-- Steps:
--   a. PRAGMA foreign_keys=OFF (defensive; already off during migration)
--   b. CREATE TABLE media_file_new without NOT NULL on release_id and oshash
--   c. INSERT existing rows, converting sentinel values to NULL
--   d. DROP TABLE media_file
--   e. ALTER TABLE media_file_new RENAME TO media_file
--   f. Recreate all secondary indexes from 001_init.sql
--   g. INSERT INTO schema_version(version) VALUES (2)
--   h. PRAGMA user_version = 2

PRAGMA foreign_keys = OFF;

-- ---------------------------------------------------------------------------
-- Step b: Create the replacement table
-- release_id is nullable (NULL during Stage A before release linkage).
-- ON DELETE SET NULL because release deletion should not cascade-delete the
-- file record — we want to keep the file row even if its release is removed.
-- oshash is nullable: NULL during Stage A before fingerprinting, and for
-- symlinks which are never fingerprinted.
-- ---------------------------------------------------------------------------
CREATE TABLE media_file_new (
  id              INTEGER PRIMARY KEY,
  release_id      INTEGER REFERENCES media_release(id) ON DELETE SET NULL,
  path_id         INTEGER NOT NULL REFERENCES path(id) ON DELETE RESTRICT,
  filename        TEXT NOT NULL,
  size_bytes      INTEGER NOT NULL CHECK(size_bytes >= 0),
  mtime_ns        INTEGER NOT NULL CHECK(mtime_ns >= 0),
  ctime_ns        INTEGER,
  oshash          TEXT,                      -- 16-char hex; NULL during Stage A before fingerprinting and for symlinks
  xxh3_partial    TEXT,                      -- 16-char hex; only when racy/conflict
  xxh3_full       TEXT,                      -- 16-char hex; rare manual repair only
  scan_generation INTEGER NOT NULL,
  last_verified_at INTEGER NOT NULL,         -- epoch seconds
  enriched_at     INTEGER,                   -- epoch seconds; NULL = never enriched
  miss_strikes    INTEGER NOT NULL DEFAULT 0,
  deleted_at      INTEGER,                   -- soft-delete tombstone
  UNIQUE(path_id, filename)
);

-- ---------------------------------------------------------------------------
-- Step c: Migrate existing rows, converting sentinel values to NULL
-- release_id=0 → NULL, oshash='' → NULL
-- (In a fresh DB there should be no sentinel rows, but be defensive.)
-- ---------------------------------------------------------------------------
INSERT INTO media_file_new(
    id, release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
    oshash, xxh3_partial, xxh3_full, scan_generation, last_verified_at,
    enriched_at, miss_strikes, deleted_at
)
SELECT
    id,
    NULLIF(release_id, 0),
    path_id,
    filename,
    size_bytes,
    mtime_ns,
    ctime_ns,
    NULLIF(oshash, ''),
    xxh3_partial,
    xxh3_full,
    scan_generation,
    last_verified_at,
    enriched_at,
    miss_strikes,
    deleted_at
FROM media_file;

-- ---------------------------------------------------------------------------
-- Step d+e: Replace old table with new
-- ---------------------------------------------------------------------------
DROP TABLE media_file;
ALTER TABLE media_file_new RENAME TO media_file;

-- ---------------------------------------------------------------------------
-- Step f: Recreate all secondary indexes (from 001_init.sql)
-- ---------------------------------------------------------------------------
CREATE INDEX idx_file_release ON media_file(release_id);
CREATE INDEX idx_file_oshash ON media_file(oshash);
CREATE INDEX idx_file_scan_gen ON media_file(scan_generation);
CREATE INDEX idx_file_deleted ON media_file(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_file_enrich_pending ON media_file(enriched_at) WHERE enriched_at IS NULL AND deleted_at IS NULL;

-- ---------------------------------------------------------------------------
-- Step g+h: Bump schema version
-- ---------------------------------------------------------------------------
INSERT INTO schema_version(version) VALUES (2);
PRAGMA user_version = 2;

-- Re-enable FK enforcement that was suspended at the top of this migration.
-- SQLite requires FK=OFF when recreating tables, but we restore the session
-- state so callers are not left with FK enforcement disabled.
PRAGMA foreign_keys = ON;
