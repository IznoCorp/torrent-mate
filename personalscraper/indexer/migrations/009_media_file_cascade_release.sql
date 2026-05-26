-- Schema migration 009 — change media_file.release_id FK action from
-- ``ON DELETE SET NULL`` to ``ON DELETE CASCADE``.
--
-- Rationale (Phase 14.4 — reopen of 12.7): the previous behaviour set
-- ``media_file.release_id = NULL`` when the parent ``media_release`` row was
-- deleted, producing unrecoverable orphans (102 such rows observed at re-run
-- 2026-05-25-23h49). A media_file is intrinsically owned by its release —
-- when the release disappears, the file row should disappear with it. The
-- "orphan recovery" CLI cannot reattach these files (their parent has been
-- deleted), so the only correct behaviour is to cascade the deletion.
--
-- SQLite does not support ALTER COLUMN ... ON DELETE, so the table is
-- recreated. Steps mirror migration 002 (the previous ``media_file``
-- recreation), with the FK action changed.
--
-- The migration is idempotent at the version-gate level (apply_migrations
-- skips when ``PRAGMA user_version >= 9``).  Existing orphan rows
-- (``release_id IS NULL``) are preserved verbatim — they are cleaned up
-- separately by ``library-fix-orphan-files --purge-unrecoverable``.

PRAGMA foreign_keys = OFF;

-- ---------------------------------------------------------------------------
-- Step 1: create replacement table with the CASCADE FK action.
-- All other columns / constraints / indexes are identical to migration 002.
-- ---------------------------------------------------------------------------
CREATE TABLE media_file_new (
  id              INTEGER PRIMARY KEY,
  release_id      INTEGER REFERENCES media_release(id) ON DELETE CASCADE,
  path_id         INTEGER NOT NULL REFERENCES path(id) ON DELETE RESTRICT,
  filename        TEXT NOT NULL,
  size_bytes      INTEGER NOT NULL CHECK(size_bytes >= 0),
  mtime_ns        INTEGER NOT NULL CHECK(mtime_ns >= 0),
  ctime_ns        INTEGER,
  oshash          TEXT,
  xxh3_partial    TEXT,
  xxh3_full       TEXT,
  scan_generation INTEGER NOT NULL,
  last_verified_at INTEGER NOT NULL,
  enriched_at     INTEGER,
  miss_strikes    INTEGER NOT NULL DEFAULT 0,
  deleted_at      INTEGER,
  UNIQUE(path_id, filename)
);

-- ---------------------------------------------------------------------------
-- Step 2: copy existing rows verbatim (orphans with NULL release_id are kept;
-- they are cleaned up by the CLI purge step, not by this migration).
-- ---------------------------------------------------------------------------
INSERT INTO media_file_new(
    id, release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
    oshash, xxh3_partial, xxh3_full, scan_generation, last_verified_at,
    enriched_at, miss_strikes, deleted_at
)
SELECT
    id, release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
    oshash, xxh3_partial, xxh3_full, scan_generation, last_verified_at,
    enriched_at, miss_strikes, deleted_at
FROM media_file;

-- ---------------------------------------------------------------------------
-- Step 3: swap tables.
-- ---------------------------------------------------------------------------
DROP TABLE media_file;
ALTER TABLE media_file_new RENAME TO media_file;

-- ---------------------------------------------------------------------------
-- Step 4: recreate the secondary indexes (identical to migration 002).
-- ---------------------------------------------------------------------------
CREATE INDEX idx_file_release ON media_file(release_id);
CREATE INDEX idx_file_oshash ON media_file(oshash);
CREATE INDEX idx_file_scan_gen ON media_file(scan_generation);
CREATE INDEX idx_file_deleted ON media_file(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_file_enrich_pending ON media_file(enriched_at) WHERE enriched_at IS NULL AND deleted_at IS NULL;

-- ---------------------------------------------------------------------------
-- Step 5: bump schema version.
-- ---------------------------------------------------------------------------
INSERT INTO schema_version(version) VALUES (9);
PRAGMA user_version = 9;

-- Restore FK enforcement so callers are not left with FK=OFF.
PRAGMA foreign_keys = ON;
