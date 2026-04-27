# Design — Media Indexer + Config Overhaul

**Date**: 2026-04-27
**Codename**: `media-indexer`
**Type**: refactor (minor SemVer — pre-1.0)
**Version bump**: 0.7.0 → 0.8.0 (applied at `implement:create-branch` once `feat/trailer` merges)
**Branch (planned)**: `feat/media-indexer`

## 1. Context

The project currently maintains **three parallel sources of truth** about its media library:

1. **`personalscraper/dispatch/media_index.py`** — `MediaIndex`, a JSON file (`.data/media_index.json`) keyed by normalized name, used by the dispatcher to figure out which disk holds an existing item before moving a new copy in. Lightweight: name, disk, category, path, media_type, last_updated.

2. **`personalscraper/library/scanner.py`** — produces `.data/library_scan.json` (≈2 MB, 2 075 items today). Heavy: NFO presence/validity/IDs, artwork inventory, seasons, issues, sizes. Consumed by `library/analyzer.py` (which produces `.data/library_analysis.json`), `library/reporter.py`, and `library/rescraper.py`.

3. **`personalscraper/trailers/scanner.py`** — wraps `library/scanner.scan_library()` with a TTL based on `config.trailers.library_scan_max_age_hours`. Effectively a third cache layer on top of the second.

These three sources duplicate work, drift independently, and have no shared schema. The library scan walks all four disks every time it is invoked, with no incremental support — slow on USB. There is no drift detection: a file removed on disk stays in the JSON until the next manual `personalscraper library-scan`. There is no auto-repair: if a disk is unmounted at scan time, items vanish from the JSON and consumers see them as deleted.

In parallel, the project's configuration is a single monolithic `config.json5` that mixes paths, disk topology, category definitions, naming patterns, encoding rules, scraper toggles, and trailer settings. As the project grew (legacy-cleanup → ext-staging → logging → test-realism → trailer), this file became hard to navigate, hard to validate per-section, and impossible to ship as multiple environment-specific overlays. The ROADMAP item _Config System Overhaul_ has been planned for several minor versions but always deferred.

This feature **bundles both refactors** in a single PR because the indexer's configuration surface (per-disk indexer settings, per-category scan policies, fingerprint thresholds, scan budgets) is large enough that doing it within the monolith would only deepen the technical debt the overhaul is meant to remove.

## 2. Goals

1. **Single source of truth, in code, against the disks.** One SQLite database (`.data/library.db`) replaces `media_index.json`, `library_scan.json`, and `library_analysis.json`. The disks remain the SSOT — the database is a queryable mirror that detects and self-repairs divergence.

2. **Drift detection + auto-repair without ever wiping live entries.** Combine `git`'s racy-index escalation rule, OpenSubtitles `OSHash` for rename-survival, per-disk Merkle roots for fast "did anything change here" gating, mountpoint sentinels to block "USB unplugged → library wiped" disasters, and an N-strikes soft-delete policy with `deleted_at` audit.

3. **Fast incremental rescans.** Persistent dir-mtime cache that lets unchanged subtrees be skipped entirely. Target: a no-op rescan completes in seconds, a typical incremental rescan in under one minute, a full cold rescan in under three minutes.

4. **Write-through from internal mutations.** Dispatcher moves, scraper writes, trailer downloads — every internal mutation enqueues a row in a transactional outbox so the index is never out of date with its own actions. External drift (manual `rm`, USB remount with newer files) caught on next nightly scan or on-demand `verify`.

5. **Configurable everything, in a structured `.personalscraper/config/` directory.** Split the current `config.json5` into one file per concern (`paths.json5`, `disks.json5`, `categories.json5`, `patterns.json5`, `encoding.json5`, `scraper.json5`, `trailers.json5`, `indexer.json5`, plus a master `config.json5` that lists overlays). Loader unified. Migration script bundled. Behavioural parity with current monolith proven by golden tests.

6. **Reusable query layer.** A small CLI on top of the index — `personalscraper library index|status|verify|search|repair` — that lets the user (and future Web UI) ask questions like "TV shows on Disk2 without valid NFO" without walking the disks.

7. **Replace all consumers in a single PR.** No coexistence period. `dispatch/media_index.py`, `library/scanner.py`, `library/analyzer.py`, `trailers/scanner.py` all migrate to the indexer; the legacy JSON files are removed; the trailer feature continues to work end-to-end after the swap.

## 3. Non-Goals

- **Multi-process concurrent indexing.** Single-writer/multi-reader via SQLite WAL is enough for a CLI on one host. No daemon, no service.
- **Real-time filesystem watching on storage disks.** macFUSE-NTFS does not propagate FSEvents reliably (confirmed by `watchdog` issue #429 and the macFUSE FAQ). The nightly scan + on-demand verify model replaces real-time.
- **Network replication / Litestream.** Out of scope. Index is regenerable from disks in minutes; offsite replication adds operational cost without obvious payoff at one-host scale.
- **An ORM.** Raw `sqlite3` + dataclasses + a thin `Repository` per entity is what `beets` does after 15 years and what we will do.
- **Cryptographic content hashing for change detection.** `OSHash` and `xxh3_64` partial fingerprint are sufficient. SHA-256 / BLAKE3 of full files is left to backup tools.
- **Distributed reconciliation patterns** beyond what fits a single-node indexer. Vector clocks, full Merkle trees per folder, content-defined chunking — all rejected as overkill at the 2 k–10 k item scale.
- **Schema-validated user-facing API.** The indexer is internal infrastructure for now; the future Web UI will own its API surface separately.
- **Replacing `pydantic-settings`.** The Config Overhaul is a structural split of the JSON5 files, not a migration to a different validation library.

## 4. Architecture

### 4.1 High-level

```
                                                ┌──────────────────────────────────┐
                                                │  4 storage disks (NTFS/macFUSE)  │
                                                │           SSOT — always           │
                                                └──────────────┬───────────────────┘
                                                               │ scan / verify (read)
                                                               │ write-through (write)
                                                               ▼
┌──────────────────────────────────┐         ┌──────────────────────────────────────┐
│  CLI consumers                   │         │  Indexer subsystem                   │
│  - personalscraper library       │  reads  │  - DB layer (sqlite3 + WAL)          │
│  - personalscraper info          │◀────────│  - Scanner (os.scandir + pymediainfo)│
│  - personalscraper run           │         │  - Drift / reconciliation engine     │
│  - dispatch / process / trailers │  writes │  - Outbox drainer                    │
└──────────────────────────────────┘────────▶│  - Repair queue worker               │
                                              │  - Per-disk circuit breaker          │
                                              └──────────────────────┬───────────────┘
                                                                     │
                                                       .data/library.db (WAL on internal disk)
```

### 4.2 Package layout

```
personalscraper/
  conf/                           # CONFIG OVERHAUL
    loader.py                     # NEW — unified loader for split files
    overlay.py                    # NEW — overlay/merge logic for multi-file config
    migration.py                  # NEW — one-shot migration of legacy config.json5
    models.py                     # EXISTING — pydantic Config, IndexerConfig added
    ids.py                        # EXISTING — unchanged
  indexer/                        # NEW — entire subsystem
    __init__.py
    db.py                         # connection, PRAGMAs, transactions
    migrations/                   # numbered .sql files + applier
      001_init.sql                # only migration in V1; subsequent ones added per change
    schema.py                     # dataclass row types + repository protocols
    repos/
      disk_repo.py                # disk + path tables
      item_repo.py                # media_item + item_attribute (flex attrs)
      release_repo.py             # media_release
      file_repo.py                # media_file + media_stream
      tv_repo.py                  # season + episode
      log_repo.py                 # scan_run + scan_event + deleted_item
      outbox_repo.py              # index_outbox + pending_ops + repair_queue
    scanner.py                    # scan engine — walks disks via ThreadPool, calls fingerprinter
    fingerprint.py                # OSHash + xxh3_64 partial + (size, mtime_ns, ctime_ns) tier
    mediainfo.py                  # pymediainfo wrapper, normalised stream extraction
    drift.py                      # racy-mtime rule, N-strikes, scan-generation comparisons
    merkle.py                     # per-disk Merkle root, mountpoint+sentinel guard
    repair.py                     # repair queue worker + budget
    outbox.py                     # outbox drainer + write-through helpers
    cli.py                        # personalscraper library {index|status|verify|search|repair}
    query.py                      # minimal flex-attr query parser
    config.py                     # IndexerConfig pydantic submodel
    breaker.py                    # per-disk circuit breaker (delegates to scraper.circuit_breaker)
  dispatch/
    media_index.py                # REWRITTEN — wraps indexer.repos.item_repo (compat shim)
    dispatcher.py                 # MODIFIED — emits write-through to outbox
  library/                        # MIGRATED to consume indexer
    scanner.py                    # REWRITTEN — populates indexer.repos, no more JSON output
    analyzer.py                   # REWRITTEN — queries indexer instead of parsing JSON
    rescraper.py                  # MODIFIED — drives via indexer
    reporter.py                   # MODIFIED — reads indexer
    validator.py                  # unchanged
    disk_cleaner.py               # MODIFIED — uses indexer write-through
    recommender.py                # unchanged
  trailers/
    scanner.py                    # MODIFIED — replaces TTL-cached lib scan with indexer query
    orchestrator.py               # MODIFIED — write-through on trailer download
  scraper/
    nfo_generator.py              # MODIFIED — write-through on NFO write (NOT process/nfo_writer.py)
    artwork.py                    # MODIFIED — write-through on artwork download
.personalscraper/                  # CONFIG OVERHAUL — now a directory
  config/
    config.json5                  # MASTER — lists overlays, env-specific points
    paths.json5
    disks.json5
    categories.json5
    patterns.json5
    encoding.json5
    scraper.json5
    trailers.json5
    indexer.json5                 # NEW — indexer subsystem config
.data/
  library.db                      # NEW — single source
  library.db-wal, library.db-shm  # WAL companions
  # REMOVED: media_index.json, library_scan.json, library_analysis.json
tests/
  indexer/                        # NEW — unit + property tests
    test_db.py
    test_migrations.py
    test_schema.py
    test_repos_*.py
    test_scanner.py
    test_fingerprint.py            # OSHash known-vector tests + xxh3 cases
    test_mediainfo.py
    test_drift.py                  # property-based via hypothesis
    test_merkle.py
    test_repair.py
    test_outbox.py
    test_cli.py
    test_query.py
  conf/
    test_loader.py                # NEW — multi-file loader (happy path + missing-file + conflicting-key)
    test_overlay.py               # NEW — local.json5 deep-merge, env-var interpolation
    test_migration.py             # NEW — golden parity test (v1 → v2 → Config equality)
    test_migration_malformed.py   # NEW — extra unknown keys, missing staging_dirs, comments-only,
                                  #       trailing-comma JSON5, "version: 2 already" — each fails closed
                                  #       or migrates without losing data; .v1.bak always written
  dispatch/
    test_dispatcher.py            # SURGICAL EDITS ONLY — kept post-PR-#14 trim;
                                  #   outbox assertions live in tests/integration/, not here
  library/
    test_scanner.py               # REWRITTEN — populates DB, asserts rows
    test_analyzer.py
    test_reporter.py
  trailers/
    test_scanner.py               # MODIFIED — replaces TTL-cache assertions with indexer-query assertions
  integration/                    # NEW — outbox write-through assertions, real tmp_path, no mocks
    test_outbox_writethrough_dispatch.py
    test_outbox_writethrough_nfo.py
    test_outbox_writethrough_artwork.py
    test_outbox_writethrough_trailer.py
    test_consumer_parity.py       # NEW — v0.7 parity contract (see §15.4.1)
  e2e/                            # NEW — full pipeline + indexer cold-to-warm + failure modes
    test_pipeline_indexer.py
    test_indexer_cold_to_warm.py
    test_indexer_unplug_disk.py
    test_indexer_unplug_during_scan.py
    test_indexer_budget_resume.py
    test_indexer_writer_lock_contention.py
    test_indexer_disk_swap.py
    test_indexer_oshash_collision.py
    test_indexer_db_corrupt_recovery.py
    test_indexer_partial_migration.py
    test_indexer_spotlight_unavailable.py
    test_indexer_spotlight_partial.py
    test_indexer_racy_mtime.py
    test_indexer_cross_dst.py
    perf/
      build_fixture.py            # deterministic 1k-item fixture builder
      FIXTURE_VERSION
      baseline.json               # checked-in perf baseline
      test_indexer_perf.py        # @pytest.mark.slow, scheduled CI
```

## 5. Configuration overhaul (Phase 0)

### 5.1 Target layout

```
.personalscraper/config/
  config.json5                # master: lists overlays, env-specific entry points
  paths.json5                 # staging_dir, data_dir, log_dir, cache_dir
  disks.json5                 # array of disks: id, uuid, label, mount_path, categories
  categories.json5            # per-category: id, folder_name, kind (movie|tv), …
  patterns.json5              # episode regex, junk-file lists, NFC rules
  encoding.json5              # ffprobe languages, audio fallbacks (existing encoding_rules.json prototype)
  scraper.json5               # TMDB/TVDB toggles, fuzzy thresholds, retry/circuit settings
  trailers.json5              # all current `trailers.*` config
  indexer.json5               # NEW — see §5.3
```

### 5.2 Loader

`personalscraper/conf/loader.py` exposes:

```python
def load_config(config_dir: Path | None = None) -> Config:
    """Load and merge all *.json5 files in the config directory.

    Resolution order:
      1. <config_dir>/config.json5            — master, may declare overlays
      2. Each file referenced by the master (in declared order)
      3. Optional <config_dir>/local.json5    — gitignored, last-wins overrides

    Returns:
        Validated Config pydantic model (existing type, extended with IndexerConfig).
    """
```

The master `config.json5` is intentionally short:

```json5
{
  overlays: [
    "paths.json5",
    "disks.json5",
    "categories.json5",
    "patterns.json5",
    "encoding.json5",
    "scraper.json5",
    "trailers.json5",
    "indexer.json5",
  ],
  version: 2,
}
```

Behind the scenes the loader merges all files into a single dict, validates via the pydantic `Config` model, and exposes the result. The merge is **shallow per-key**: each overlay is expected to own a top-level key (e.g. `paths.json5` owns `"paths": {...}`). Conflicts at the same top-level key are an error (prevents accidental ambiguity). The optional `local.json5` is the only file allowed deep-merge semantics, and it is the user's escape hatch for machine-specific overrides.

### 5.3 IndexerConfig

```json5
// indexer.json5
{
  indexer: {
    db_path: "${data_dir}/library.db",
    scan: {
      nightly_mode: "quick", // quick | incremental | enrich | full
      budget_seconds: 1800, // hard cap per scan run (any mode)
      checkpoint_every_n_files: 100, // for crash-resume
      max_workers_total: 4, // capped at len(mounted_disks)
      racy_window_seconds: 2.0, // git-style mtime-collision window
      n_strikes_for_softdelete: 3, // missed scans before deleted_at
      read_rate_mb_per_sec: null, // null = unlimited; set e.g. 80 to throttle
      sequential_read_hint: true, // macOS F_RDADVISE; no-op elsewhere
      drop_indexes_during_full_scan: true, // bulk-insert optimization
    },
    fingerprint: {
      oshash: true, // store OSHash on every file
      xxh3_partial_bytes: 1048576, // 1 MB head + 1 MB tail
      compute_xxh3_on_racy: true,
    },
    mediainfo: {
      library_path: null, // null = auto-detect via brew
      extract_streams: true,
      min_size_mb: 50, // skip mediainfo on files smaller than this
      parse_speed: 1.0, // libmediainfo flag; 0.5 = fast, 1.0 = full
      defer_to_enrich: true, // cold/quick/incremental skip mediainfo entirely
    },
    drift: {
      merkle_per_disk: true,
      verify_disks_each_scan: true, // run mountpoint + sentinel checks
      sentinel_filename: ".personalscraper-disk-id",
    },
    spotlight: {
      probe_at_startup: true, // run mdutil -s on each disk
      use_when_available: true, // delegate change detection to Spotlight
    },
    repair: {
      queue_drain_on_scan_finish: true,
      max_repair_seconds_per_drain: 300,
    },
    log: {
      scan_event_retention_days: 90,
      deleted_item_retention_days: 365,
    },
  },
}
```

Per-disk overrides live in `disks.json5`:

```json5
// disks.json5 (excerpt)
{
  disks: [
    {
      id: "Disk1",
      uuid: "...",
      mount_path: "/Volumes/Disk1",
      categories: [...],
      spotlight_enabled: false,              // user opts in after `mdutil -i on`
    },
    // ...
  ],
}
```

### 5.4 Migration of the existing monolith

`personalscraper/conf/migration.py` exposes a one-shot `migrate_v1_to_v2(legacy_path, target_dir)` that reads the old `config.json5`, splits it across the new files, and writes them out. A CLI wrapper `personalscraper config migrate-to-v2 [--dry-run]` calls it. Behavioural parity is enforced by a **golden test**: load v1 directly, load v2 via migration + new loader, assert the resulting `Config` objects are equal field-by-field.

### 5.5 Loader behaviour during the transition

The loader auto-detects whether `.personalscraper/config/` is a directory (v2) or whether the legacy `config.json5` exists alongside (v1). v1 detection logs a deprecation warning at startup with the exact CLI invocation to migrate. After this PR merges, the project ships v2; v1 detection lasts **one minor release** (0.9.x will remove it).

## 6. Database

### 6.1 Connection & PRAGMAs

```python
def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-65536")        # 64 MB
    conn.execute("PRAGMA mmap_size=268435456")      # 256 MB
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

The DB lives on `path` which is **always** `.data/library.db` on the internal APFS disk. The loader rejects any `db_path` that resolves to a mounted external volume (WAL is unreliable on macFUSE-NTFS).

### 6.2 Schema (final)

```sql
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
--
-- `release_id` and `oshash` are NULLABLE to support the Stage A/Stage B
-- split (§11): Stage A inserts file rows before any release exists or any
-- content hash is computed. Both columns are populated by Stage B (`enrich`
-- mode) once NFOs are parsed and OSHash is computed for non-symlink files.
-- ---------------------------------------------------------------------------
CREATE TABLE media_file (
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
  enriched_at     INTEGER,                   -- epoch seconds; NULL = never enriched. Set by `enrich` mode after pymediainfo + NFO + artwork. enrich criterion is `enriched_at IS NULL OR enriched_at < (SELECT MAX(mtime_ns)/1000000000 FROM media_file f2 WHERE f2.id=media_file.id)`.
  miss_strikes    INTEGER NOT NULL DEFAULT 0,
  deleted_at      INTEGER,                   -- soft-delete tombstone
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
```

### 6.3 Migrations

`personalscraper/indexer/migrations/` holds numbered files: `001_init.sql`, `002_add_<col>.sql`, etc. The applier:

```python
def apply_migrations(conn: sqlite3.Connection, dir_: Path) -> None:
    """Apply all *.sql files whose number > current PRAGMA user_version.

    Each file is executed in a single transaction; if it succeeds, user_version
    is bumped to the file's number. The applier is idempotent and re-runnable.
    """
```

Each script must be **re-runnable defensively** (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN` guarded by introspection if the SQLite version forbids `IF NOT EXISTS` on columns). This pattern is the same one beets, fava, and Datasette use; no Alembic, no migration framework.

### 6.4 Concurrency model

- **Single writer at a time.** `personalscraper/indexer/db.py` exposes an `indexer_lock()` context manager backed by `filelock` on `.data/library.db.lock`. The lockfile content is `{pid, started_at_unix_s, hostname}`. The lock prevents _logical_ races (two scans running in parallel) — SQLite WAL itself protects DB-level integrity across processes, so this lock is additive, not strictly required for correctness. Any CLI command that mutates (scan, repair, write-through drain) acquires this lock with a short timeout. Reads do not need the lock — WAL gives them snapshot isolation.
- **`BEGIN IMMEDIATE`** at the start of every write transaction → fail fast on contention rather than deadlock mid-transaction.
- **Per-disk transactions** during a scan: each disk is one transaction. A crash on Disk3 does not roll back Disk1's progress.
- **Outbox drain** runs in its own short transaction per outbox row, _outside_ the indexer_lock — outbox publishers (dispatch/scraper/trailers) must be able to write while a scan holds the lock. Concurrent outbox inserts rely on `BEGIN IMMEDIATE` + `busy_timeout=5000` for safety; collisions are absorbed by the retry-with-backoff policy in §17.1.

### 6.5 Naming and JSON-shape conventions

**Timestamp columns** follow a strict suffix convention:

| Suffix | Unit                   | Used for                                                                                                                                                                                                                                                                                                     |
| ------ | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `_at`  | unix epoch seconds     | All audit timestamps (`created_at`, `processed_at`, `enqueued_at`, `attempted_at`, `started_at`, `finished_at`, `detected_at`, `last_walked_at`, `last_verified_at`, `last_seen_at`, `enriched_at`, `replayed_at`, `deleted_at`, `attempted_at`, `date_metadata_refreshed`, `date_created`, `date_modified`) |
| `_ns`  | unix epoch nanoseconds | File-system mtime / ctime / dir mtime — must match `os.stat_result.st_mtime_ns` precision                                                                                                                                                                                                                    |
| `ts`   | unix epoch seconds     | High-frequency event timestamps (`scan_event.ts`)                                                                                                                                                                                                                                                            |

A reviewer that finds a timestamp column without one of these suffixes should flag it.

**JSON-column shapes** are documented in `docs/reference/indexer-json-shapes.md` (created in Phase 8); pydantic models in `personalscraper/indexer/schema.py` enforce the shape at write time.

| Column                      | Pydantic model             | Shape (abbreviated)                                                                                                                |
| --------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `media_item.artwork_json`   | `ArtworkInventory`         | `{"poster":bool,"fanart":bool,"landscape":bool,"banner":bool,"clearlogo":bool,"clearart":bool,"discart":bool,"characterart":bool}` |
| `index_outbox.payload_json` | `OutboxPayload` (per `op`) | See §9.3 per-`op` contract                                                                                                         |
| `pending_op.payload_json`   | same                       | Same as outbox payloads                                                                                                            |
| `repair_queue.payload_json` | `RepairPayload`            | `{"context":str, "discovered_at":int, "evidence":dict}`                                                                            |
| `scan_run.stats_json`       | `ScanStats`                | `{"items_added":int, "items_updated":int, "items_deleted":int, "files_walked":int, "bytes_read":int, "budget_exhausted":bool}`     |
| `scan_event.payload_json`   | `ScanEventPayload`         | Free-form by `event` value; documented per event in `indexer-json-shapes.md`                                                       |
| `deleted_item.payload_json` | `DeletedSnapshot`          | Snapshot of the deleted row's columns at delete time                                                                               |

**Generated columns for queryable JSON fields** — adopted for the most common queries to avoid `json_extract()` in every WHERE clause:

```sql
ALTER TABLE media_item ADD COLUMN has_poster INTEGER
  GENERATED ALWAYS AS (json_extract(artwork_json, '$.poster')) VIRTUAL;
CREATE INDEX idx_item_has_poster ON media_item(has_poster) WHERE has_poster = 1;

ALTER TABLE media_item ADD COLUMN has_fanart INTEGER
  GENERATED ALWAYS AS (json_extract(artwork_json, '$.fanart')) VIRTUAL;
CREATE INDEX idx_item_has_fanart ON media_item(has_fanart) WHERE has_fanart = 1;
```

These run as part of `001_init.sql` after the base table is created.

### 6.6 Logging event-name convention

Following the project's logging convention (PR #10, `docs/archive/features/logging/DESIGN.md`), every structlog event emitted from the indexer subsystem follows the pattern:

```
indexer.{component}.{action}[_{qualifier}]
```

| Component    | Examples                                                                                                                                               |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `db`         | `indexer.db.outbox_lost`, `indexer.db.corrupt`, `indexer.db.disk_full`                                                                                 |
| `lock`       | `indexer.lock.stale_recovered`, `indexer.lock.live_pid`                                                                                                |
| `disk`       | `indexer.disk.bootstrapped`, `indexer.disk.skipped_unmounted`, `indexer.disk.uuid_mismatch`, `indexer.disk.io_error`, `indexer.disk.suspected_restore` |
| `file`       | `indexer.file.permission_denied`                                                                                                                       |
| `fs`         | `indexer.fs.invalid_mtime`                                                                                                                             |
| `outbox`     | `indexer.outbox.row_failed`, `indexer.outbox.deferred`, `indexer.outbox.drained`                                                                       |
| `pending_op` | `indexer.pending_op.replayed`, `indexer.pending_op.ttl_expired`                                                                                        |
| `repair`     | `indexer.repair.enqueued`, `indexer.repair.budget_exhausted`                                                                                           |
| `merkle`     | `indexer.merkle.recomputed`, `indexer.merkle.delta_freeze`                                                                                             |
| `scan`       | `indexer.scan.started`, `indexer.scan.checkpoint`, `indexer.scan.budget_exhausted`, `indexer.scan.resumed`                                             |
| `spotlight`  | `indexer.spotlight.available`, `indexer.spotlight.unavailable`, `indexer.spotlight.skipped_macfuse`, `indexer.spotlight.divergence`                    |
| `migration`  | `indexer.migration.applied`, `indexer.migration.failed`, `indexer.migration.restored_backup`                                                           |
| `config`     | `indexer.config.category_orphan`, `indexer.config.unknown_keys`, `indexer.config.no_index`                                                             |

Underscored qualifiers separate snake_case multi-word actions; component and action are dot-separated. Reviewers must reject any new event name that does not match this pattern.

## 7. Scanner

### 7.1 Walk strategy

```python
def scan(disks: list[Disk], mode: ScanMode, generation: int) -> ScanRunResult:
    """Walk the configured disks and reconcile the index.

    - Mountpoint+sentinel verification per disk before any read.
    - Per-disk Merkle root recomputed at start; if unchanged AND mode == incremental,
      skip the whole disk.
    - Per-directory dir_mtime check; if unchanged AND mode == incremental, skip
      the subtree (POSIX semantics: dir mtime moves on add/remove/rename of a
      direct child).
    - Each visited file → fingerprint tier 1 (size+mtime+ctime). On mismatch
      with index OR racy mtime → tier 2 (xxh3_partial). On mismatch with stored
      xxh3_partial → tier 3 (full re-fingerprint + media stream re-extraction).
    - All visited rows get scan_generation = current generation.
    - At end: rows with scan_generation < current AND disk.is_mounted → strike
      counter incremented. Strikes >= n_strikes_for_softdelete → deleted_at set.
    - Disks unreachable (mountpoint check failed) → all their rows frozen, no
      strike change.
    """
```

### 7.2 Parallelism

`ThreadPoolExecutor(max_workers=len(mounted_disks))` — one worker per physical disk, configurable via `indexer.scan.max_workers_per_disk` (default 1, capped at 4 even for many-disk setups since macFUSE serializes per FUSE daemon). Within a disk: sequential walk to avoid thrashing the FUSE request queue.

### 7.3 Fingerprint tiers

```python
def fingerprint_tier1(stat_result: os.stat_result) -> Tier1Fingerprint:
    return (stat_result.st_size, stat_result.st_mtime_ns, stat_result.st_ctime_ns)

def is_racy(file_mtime_ns: int, scan_started_at_ns: int, window_ns: int) -> bool:
    """Git-style racy-mtime rule: mtime within ±window of scan start is suspect."""
    return abs(file_mtime_ns - scan_started_at_ns) <= window_ns

def oshash(path: Path) -> str:
    """OpenSubtitles hash: filesize + sum(first 64KB u64) + sum(last 64KB u64),
    truncated to 16 hex chars (u64). 128 KB read regardless of file size.
    """

def xxh3_partial(path: Path, partial_bytes: int) -> str:
    """xxh3_64 of the first partial_bytes + last partial_bytes (default 1 MB each).
    Used as drift-detection fallback when tier 1 is racy or contradictory.
    """
```

### 7.4 Disk identity bootstrap and mountpoint sentinel guard

#### 7.4.1 First-scan bootstrap

When the scanner encounters a disk for the first time (no `disk` row, or `disk.uuid` is NULL), the bootstrap path runs:

```python
def bootstrap_disk_identity(mount_path: Path) -> str:
    """Resolve a stable volume UUID for a freshly-mounted disk.

    Calls `diskutil info -plist <mount_path>` and parses the `VolumeUUID` key.
    On macOS, this returns a UUID that survives unmount/remount/relabel and is
    distinct per filesystem (NTFS-via-macFUSE volumes expose it).
    Raises BootstrapError if diskutil is unavailable or returns no UUID.
    """
```

After UUID resolution:

1. INSERT a new `disk` row with `(uuid, label, mount_path, is_mounted=1)` — `label` defaults to `mount_path.name`.
2. Write `<mount_path>/.personalscraper-disk-id` containing the UUID (single line, plain text).
3. Log `indexer.disk.bootstrapped` with the UUID and mount path.

This bootstrap happens lazily during scan startup — there is no separate "register disk" CLI step. Sentinel files are therefore never created without a paired `disk` row in the DB.

#### 7.4.2 Mountpoint sentinel guard

```python
def verify_disk_mounted(disk: DiskRow) -> DiskMountStatus:
    """Block the whole 'USB unplugged → library wiped' class.

    Returns one of:
      MOUNTED_AND_VERIFIED — os.path.ismount(disk.mount_path) AND sentinel file
                              <mount>/.personalscraper-disk-id contains disk.uuid.
      MOUNTED_WRONG_DISK   — sentinel UUID mismatch (different disk inserted on
                              same mount). NEVER strike, NEVER delete; warn user.
      UNMOUNTED            — os.path.ismount() false. Freeze strikes for this disk.
      NO_SENTINEL          — mount looks right but sentinel missing (first scan
                              after upgrade, or sentinel manually deleted).
                              Re-derive UUID via diskutil; if matches disk.uuid,
                              re-create sentinel and proceed; if differs, treat
                              as MOUNTED_WRONG_DISK.
    """
```

### 7.5 Per-disk Merkle root

```python
def compute_merkle_root(files: Iterable[FileFingerprint]) -> str:
    """xxh3_64 hex over deterministically-sorted concatenation of
    f"{path_id}|{size}|{mtime_ns}|{oshash}\n" for every file on the disk.

    Stored on disk.merkle_root. If new root == old root after enumerating,
    no further work needed for this disk.
    """
```

This is computed **after** the file list is enumerated for the disk; it does not avoid the enumeration but does avoid all the per-file work (fingerprint tier 2/3, mediainfo, DB writes) for disks that are byte-identical to the last scan. On 4 disks with one disk frequently changing, this saves ~75 % of work per nightly scan.

## 8. Drift detection & reconciliation

### 8.1 Reconciliation loop

```
for each disk D in scan order:
    status = verify_disk_mounted(D)
    if status == UNMOUNTED:
        log "indexer.disk.skipped_unmounted"; continue (no strike)
    if status == MOUNTED_WRONG_DISK:
        log "indexer.disk.uuid_mismatch"; continue (no strike, alert)
    if status == NO_SENTINEL:
        write sentinel; treat as MOUNTED_AND_VERIFIED

    open transaction(D)
    for each file F walked on D:
        idx = index.lookup_by_path(F)
        if idx is None:
            INSERT new row (after release/item/path resolution)
        else:
            t1 = fingerprint_tier1(F)
            if t1 == idx.tier1 and not is_racy(F, scan_start):
                # cheap skip
                idx.scan_generation = current
            else:
                # escalate to tier 2
                t2 = xxh3_partial(F, partial_bytes)
                if t2 == idx.xxh3_partial:
                    idx.tier1 = t1; idx.scan_generation = current
                else:
                    enqueue_repair(file=F, reason='content_drift')
                    idx.tier1 = t1; idx.xxh3_partial = t2; ...
    # mark missing
    for each row R on D where R.scan_generation < current:
        R.miss_strikes += 1
        if R.miss_strikes >= n_strikes_for_softdelete:
            R.deleted_at = now
            INSERT deleted_item(...)
    commit transaction(D)
```

### 8.2 Hinted handoff for unmounted disks

When `dispatch.move(file, disk)` runs while the target disk is unmounted, the move itself fails before reaching the indexer. But the inverse case — `dispatch.move()` succeeds via macFUSE NTFS but the next scan finds the disk unmounted — is handled by **freezing strike counters** for that disk, not by hinted handoff. `pending_op` is reserved for the rare case where the scanner discovers an internal write-through that targets an unreachable disk and parks it.

### 8.3 Repair queue

Drift detected during a scan never repairs inline. Instead it `INSERT INTO repair_queue` with a scope and a reason, and the scanner moves on. After the scan finishes, `repair.drain(budget_seconds=300)` runs, processing items in FIFO order until the budget elapses. Unprocessed items survive to the next scan. This guarantees scans terminate within the configured budget.

### 8.4 Resumable scans

`scan_run.last_path` is updated every `checkpoint_every_n_files` files. On startup, if the most recent `scan_run.status == 'running'` and started > 2 h ago, the scanner treats it as crashed and resumes from `last_path` instead of starting over.

## 9. Best-effort write-through log

### 9.1 Pattern (and divergence from canonical outbox)

The pipeline mutates the filesystem in three places: `dispatch/dispatcher.py` (rsync moves), `scraper/nfo_generator.py` and `scraper/artwork.py` (NFO + artwork writes), `trailers/orchestrator.py` (trailer downloads). Each of these, **immediately after the FS operation succeeds**, opens a short SQLite transaction on `library.db` and inserts one row in `index_outbox` describing the change. The outbox insert is decoupled from the FS operation (no two-phase commit, no XA): the disks remain SSOT, and the table records _intent that has just become reality on disk_. If the outbox insert fails (DB locked, disk full), the FS operation is not rolled back — the next scan will reconcile the missed mutation as ordinary external drift.

**This is NOT the canonical transactional outbox pattern** (Microservices.io / Debezium / Chris Richardson). The canonical pattern requires the outbox row insert and the business mutation to share a single transaction — the entire point is at-least-once delivery without distributed transactions. This design relaxes that guarantee on purpose: the FS itself is the SSOT and the periodic scan is the reconciliation backstop, so a missed outbox row produces _latency in the index reflecting reality_, not data loss. Calling this an "outbox" is a name-only borrowing; the right mental model is **"best-effort write-through change log with periodic reconciliation"** (closer in spirit to write-ahead intent logs in CRDT systems than to transactional outbox).

### 9.2 Drainer behaviour

The drainer runs:

- After every pipeline step that wrote to the outbox (synchronous, short).
- On every `personalscraper library index` invocation (synchronous).
- On its own short cadence if the daemon were ever to exist (out of scope here).

Drainer rules:

- Process rows in `id ASC` order (FIFO). For multiple rows targeting the same `(disk_id, rel_path, filename)` tuple, only the latest one wins (older rows are marked `done` without applying).
- A row is processed in its own short transaction; `processed_at` is set under the same transaction; on `OperationalError: database is locked`, retry up to 3× with backoff (50 ms, 200 ms, 1 s), then mark `failed` and log `indexer.outbox.row_failed` with the row id.
- A row whose target disk is unreachable at drain time is moved to `pending_op` (status `deferred`); replayed when the disk is observed mounted in a subsequent scan.

### 9.3 Drain idempotence contract (per `op` value)

Every `op` is replay-safe:

- `move` payload `{disk_id, src_rel_path, dst_rel_path, filename, size_bytes, mtime_ns}` — UPSERT into `media_file` keyed by `(path_id, filename)` resolved from `(disk_id, dst_rel_path)`. Replaying yields the same row.
- `nfo_write` payload `{disk_id, rel_path, item_kind, tmdb_id, imdb_id}` — UPDATE `media_item.nfo_status` and `tmdb_id`/`imdb_id` for the matched item. Replaying is a no-op when current values equal payload.
- `artwork_write` payload `{disk_id, rel_path, kind}` — flip the corresponding boolean in `media_item.artwork_json`. Replay is a no-op once the bit is set.
- `trailer_download` payload `{disk_id, rel_path, trailer_path}` — set `item_attribute(item_id, key='trailer_found', value=trailer_path)`. UPSERT pattern.

### 9.4 Why write-through over scan-only reconciliation

Direct writes from dispatch into the indexer would tightly couple the dispatcher to the indexer schema and risk transaction ordering bugs (FS commit happens, then indexer write fails, leaving silent drift). The change log: pipeline writes only the operation type and payload; the indexer reconciles intent against FS at drain time, with full retry/error semantics. Beets, Sonarr, and Radarr each implement variants of this same shape (a small in-DB log of recent operations the indexer must apply).

## 10. Migration of consumers

### 10.1 dispatch/media_index

`personalscraper/dispatch/media_index.py` becomes a thin wrapper. The `MediaIndex` class API actually exposed today is `__init__(index_path)`, `load()`, `save()`, `find()`, `add()`, `rebuild()`, `remove_stale(disk_configs)` — confirmed by reading the current source. The wrapper preserves the **public-facing** subset used by callers (`find`, `add`, `rebuild`, `remove_stale`) and delegates each to `indexer.repos.item_repo` / `file_repo`. `load()` and `save()` become no-ops (the indexer DB has its own lifecycle); they remain on the class signature so internal callers do not break. The `IndexEntry` dataclass is preserved at module level for callers; internally it is built from indexer rows.

Consumers (`dispatch/dispatcher.py`, `dispatch/run.py`) need **zero behavioural change**, only an import path adjustment if any. `media_index.json` is removed; first invocation of the new dispatcher detects the missing JSON and triggers an indexer rebuild for the affected disks.

### 10.2 library/scanner + library/analyzer

`library/scanner.py:scan_library()` is rewritten to **populate the indexer** instead of returning a `LibraryScanResult` dataclass tree. Callers of the old API (now: `library/rescraper.py`, `library/reporter.py`, `library/disk_cleaner.py`, `library/recommender.py`, `library/validator.py`, `trailers/scanner.py`) are migrated to query the indexer directly via `indexer.query` helpers.

`library/analyzer.py` is rewritten to compute analyses by querying the indexer (e.g., "show me all items on Disk1 with `nfo_status='invalid'`") instead of parsing JSON.

`library_scan.json` and `library_analysis.json` are removed.

### 10.3 trailers/scanner

The TTL-cached library scan in `trailers/scanner.py` (the `library_scan_max_age_hours` mechanism) is replaced by a single-call `indexer.query.find_items_without_trailer()`. The `library_scan_max_age_hours` config knob is removed (with a deprecation pass in `conf/migration.py`). The deliverable is the API swap and the removal of the TTL cache layer; an expected (not required) outcome is that the file is significantly shorter, since the entire cache-warming path goes away.

### 10.4 trailers/orchestrator + scraper

These add `outbox.publish(...)` calls at the points where they mutate the filesystem (`scraper/nfo_generator.py`, `scraper/artwork.py`, `trailers/orchestrator.py`). Tests assert that the outbox contains the expected row after each operation — see §15.5 for placement.

## 11. Performance strategy at 24 TB scale

The library is large (24 TB across 4 NTFS-via-macFUSE disks, estimated 20–100 k files). The disks are USB-attached and operationally fragile — minimising read I/O and avoiding spurious wake-ups matters as much as raw speed.

**Design rule**: a typical nightly run must complete in **seconds**, not minutes. A full reindex must be **avoidable in normal operation** and **splittable across multiple nights** when forced.

### 11.1 Stratified scan modes

The scanner exposes four modes with sharply different I/O profiles. The CLI default for the nightly cron is `quick`; `incremental`, `enrich`, and `full` are opt-in for heavier work.

| Mode          | What it does                                                                                                                                                                                                                     | I/O per file (steady state)                                           | Typical use            |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------- |
| `quick`       | **Per-disk Merkle short-circuit first** (compare DB-stored Merkle root against a fresh recomputation from existing rows — sub-second, no FS reads). On Merkle miss only: `dir_mtime` skip + tier-1 fingerprint on changed files. | 0 if Merkle hits; else 1 stat per directory + 1 stat per changed file | nightly cron (default) |
| `incremental` | `quick` + compute OSHash on every new or changed file; resolve renames against existing OSHash index.                                                                                                                            | + ~128 KB read per new/changed file                                   | manual / weekly        |
| `enrich`      | `incremental` + pymediainfo + NFO parse + artwork inventory on rows missing those columns.                                                                                                                                       | + ~64 KB-1 MB header read + CPU per missing-data file                 | budget-bounded fill-in |
| `full`        | Ignore all caches: walk every disk, fingerprint every file, recompute everything. Cold rebuild.                                                                                                                                  | ~500 KB-1 MB per file across the whole disk                           | one-shot, manual       |

`quick` is the answer to "I want a nightly that doesn't stress disks": on a stable library, the per-disk Merkle root short-circuit makes every disk a no-op (zero FS reads). The Merkle root is recomputed from rows already in `media_file` (`size`, `mtime_ns`, `oshash`); only when the freshly-computed root differs from `disk.merkle_root` does the dir-mtime walk run.

### 11.2 Disk-by-disk rotation for cold scans

A `--full` cold scan is **scoped to one disk by default**. The launchd plist template ships in two flavours:

- `personalscraper-index-quick.plist` — runs `library index --quick` every night.
- `personalscraper-index-rotate.plist` — runs `library index --full --disk DiskN` once per night, rotating across the four disks (Mon=Disk1, Tue=Disk2, Wed=Disk3, Thu=Disk4, Fri/Sat/Sun=quick). One disk per night ensures no single night exceeds ~15-30 min and no disk is double-touched within four days.

Manual override: `personalscraper library index --full --disk Disk1` triggers an immediate full scan of one disk; resumes from `scan_run.last_path` if previously interrupted.

### 11.3 Two-stage scan: fingerprint then enrich

Even a cold rescan **does not run pymediainfo synchronously**. The cold pass is structured in two stages:

1. **Stage A — fingerprint** (read ~128 KB per file): walk + stat + OSHash. Populates `media_file` rows. Index becomes usable.
2. **Stage B — enrich** (read ~64 KB-1 MB header per file + CPU): pymediainfo, NFO, artwork. Populates `media_stream`, `nfo_status`, `artwork_json`. Run as `library index --enrich [--budget SECONDS]` separately, possibly across several nights.

Consequences for 24 TB:

- Cold rebuild (Stage A on one disk): ~6 GB read, ~10-15 min — fits inside a single night's budget.
- Cold enrich (Stage B): runs on demand at controlled budget. Index is queryable for path/disk/title queries before enrich completes; codec/audio queries return `unknown` until enriched.

### 11.4 Container fast-path (deferred to a follow-up minor)

`pymediainfo` works well but reads a sizeable container header per file. At full library scale this is ~12 GB of header I/O. Two pure-Python alternatives — `enzyme` (MKV) and `mutagen.MP4` — read only 64 KB and are ~5-10× faster on their target containers. We **do not add them in V1** to keep the dependency surface small, but the abstraction in `indexer/mediainfo.py` is shaped so they can be plugged in as a fast-path in V1.1 (try enzyme/mutagen on known containers, fall back to pymediainfo). The risk that the V1 enrich pass is too slow at full library scale is bounded: it is splittable across nights and budget-capped.

### 11.5 Spotlight change-detection on APFS only (NOT macFUSE)

**Important constraint**: macFUSE-mounted volumes (i.e. all four NTFS storage disks) are **excluded from Spotlight indexing** by macOS — even after `mdutil -i on /Volumes/Disk1`, `mds_stores` is not populated for FUSE-backed mounts and `NSMetadataQuery` returns empty. Confirmed by macFUSE FAQ and verified on the target host. The indexer therefore **does not use Spotlight on the four storage disks**.

Spotlight is only useful for the **staging APFS directory** (the personalscraper triage area, normally on the internal disk). When the staging dir is on APFS and Spotlight is enabled, the indexer can use `NSMetadataQuery` for fast detection of newly-arrived items — useful for the optional pre-indexing watcher mentioned in §17 (deferred to V1.x).

V1 implementation:

- At scan startup: probe `mdutil -s <mount>` for every disk and the staging dir. Log `indexer.spotlight.{available|unavailable}` per path.
- `SpotlightChangeDetector` is implemented for **APFS paths only**. On macFUSE paths the class refuses to attach and logs `indexer.spotlight.skipped_macfuse` (one-time per session) — the dir-mtime walk runs unconditionally on storage disks.
- `disks.json5` retains a `spotlight_enabled: bool` field (default false) but it is ignored for any disk whose mount is macFUSE; the indexer warns at scan time if a user sets it true on such a disk.

Spotlight remains an orthogonal optimisation, not a correctness requirement. Storage-disk change detection is **always** dir-mtime walk + per-disk Merkle root, independent of Spotlight availability.

### 11.6 Read-traffic minimisation

- **Mount flags**: `/Volumes/Disk*` should be mounted with `noappledouble,noapplexattr,defer_permissions,allow_other,noatime`. The `noatime` flag eliminates atime metadata writes from the disks during reads (the indexer never writes to the disks itself; the pipeline does, separately). Note: `nodiratime` is a Linux-specific flag that ntfs-3g on macOS _silently ignores_ — `noatime` on NTFS already covers directory access times, so omitting `nodiratime` is correct. The indexer parses `mount` output at scan start and warns if any _recognised_ flag is missing.
- **macOS read-ahead hint**: every file opened for fingerprint or mediainfo gets a sequential read hint via `fcntl(fd, F_RDADVISE, struct.pack('qi', offset, length))` — `os.posix_fadvise` does **not exist on Darwin**, but Darwin exposes `F_RDADVISE` via `fcntl`. The wrapper is encapsulated in `indexer/_macos_io.py::sequential_hint(fd)` and is a no-op outside Darwin. Encourages kernel read-ahead, reduces head-seek overhead on HDDs.
- **File-extension allowlist for OSHash**: only files whose extension is in `indexer.fingerprint.oshash_extensions` (default: video extensions from `patterns.json5` — `mkv,mp4,avi,mov,wmv,flv,mpg,mpeg,m4v,webm,ts,m2ts,mts,3gp,vob,ogv,rmvb`) are OSHashed. Sidecars (`.nfo`, `.srt`, `.jpg`, `.png`, `.txt`) get a tier-1 fingerprint only — they are usually small enough that mtime+size alone is sufficient, and avoiding the 128 KB read on thousands of sidecars saves a meaningful chunk of cold-scan I/O.
- **Read-rate throttle (optional)**: `indexer.scan.read_rate_mb_per_sec` (default `null` = unlimited). When set, fingerprint and mediainfo reads pass through a token bucket. Useful on low-end USB enclosures or shared root hubs.
- **Skip media-info on small files**: files < `indexer.mediainfo.min_size_mb` (default 50 MB) skip pymediainfo entirely (NFO, artwork, sample files, subtitles — none of them benefit from stream extraction).
- **Skip media-info on tight budget**: when `enrich` mode is invoked with `--budget SECONDS`, the worker prioritises files whose `release.item_id` has been most recently touched (newest `media_item.date_modified` first). When the budget is exhausted, remaining files retain `enriched_at = NULL` and are picked up by the next pass. The `library status` command surfaces enrich-pending count.
- **Open files with `O_RDONLY`** explicitly via `os.open()` rather than relying on default `Path.open()` mode. Trivial but signals intent and avoids any future regression.

### 11.7 Ingest-side optimisations (within Python)

- **`os.scandir` reuses dirent stat data** — never call `Path.stat()` after `scandir`; use `entry.stat(follow_symlinks=False)` which is cached when the FS supports it.
- **Bulk insert during cold scan**: at the start of a `--full` run on a disk, the scanner drops the secondary indexes on `media_file`/`media_stream`, runs `executemany` in batches of 5 000 inside one `BEGIN IMMEDIATE` transaction, then recreates the indexes. Empirically ~3-5× faster than incremental inserts. `incremental`/`enrich`/`quick` keep indexes intact (their write volume is small).
- **Mediainfo "fast parse" mode**: `enrich --quick` runs pymediainfo with `parse_speed=0.5` (libmediainfo flag), trading marginal precision for ~1.5× speedup. Default `enrich` uses `parse_speed=1.0`.

### 11.8 Parallelism

`ThreadPoolExecutor(max_workers=len(mounted_disks))` at top level; sequential walk per disk; mediainfo calls **inside the same worker** (the bottleneck is macFUSE syscalls and disk seeks, not Python CPU). Configurable cap: `indexer.scan.max_workers_total` (default `4`, never more than `len(mounted_disks)`).

For `--full --disk D` runs, parallelism degrades to a single worker — disk-friendliness over speed.

### 11.9 Crash safety and clean shutdown

- **`scan_run.last_path` checkpointing** every `checkpoint_every_n_files` files (default 100) lets a crashed scan resume.
- **SIGTERM handler**: when launchd sends SIGTERM (system going to sleep, manual cron interrupt), the scanner finishes the current file, commits the disk's transaction, updates `scan_run.last_path`, exits 0. Next run resumes transparently.
- **`scan_run.status` recovery**: at startup, if the most recent run has `status='running'` and `started_at > 2 h ago`, the next scan treats it as crashed and resumes; if `< 2 h ago`, it errors out (another instance might be running).

### 11.10 Subtree skip via dir-mtime

The `path.dir_mtime_ns` column lets the scanner skip every directory whose recorded mtime equals the current one (POSIX-correct: directory mtime moves on add/remove/rename of any direct child). On NTFS-via-macFUSE this semantic is preserved by ntfs-3g — verified by Plex/Jellyfin/Lightroom on the same stack. This is the single biggest perf win for `quick`/`incremental` and is what makes a no-op nightly run fast. Verified at startup: a one-time test writes a file in a temp subdir, reads dir mtime before/after, asserts the change; if the assertion fails (broken FS semantics), the indexer logs a warning and falls back to per-file fingerprinting.

### 11.11 Performance budget (V1 acceptance criteria)

These are the numbers the V1 must hit on a 50 k-file fixture filesystem (1 TB representative subset, on a real NTFS-via-macFUSE mount). The `quick` mode applies the **per-disk Merkle short-circuit first**: each disk computes its Merkle root from the lightweight `(path_id, size, mtime_ns, oshash)` rows already in the DB; if the freshly-recomputed root equals the stored `disk.merkle_root`, the disk is fully skipped — zero stat calls on the FS.

| Mode                                                               | Target time | Hard ceiling |
| ------------------------------------------------------------------ | ----------- | ------------ |
| `quick`, no FS changes (Merkle short-circuit hits all disks)       | < 5 s       | 30 s         |
| `quick`, no FS changes (Merkle hits 0 disks → full dir-mtime walk) | < 90 s      | 5 min        |
| `quick`, 100 changed files                                         | < 90 s      | 5 min        |
| `incremental`, 100 new files                                       | < 2 min     | 8 min        |
| `enrich`, 1 000 missing-data files                                 | < 5 min     | 15 min       |
| `full --disk D` (one 6 TB disk, ~12 k files)                       | < 30 min    | 2 h          |

The Merkle root is itself just a hash over rows already in SQLite, so the "did anything change" check costs ~50 ms regardless of disk size. Cache hit rate is what determines whether `quick` is sub-second or sub-minute. Empirically, on a stable library, hit rate should be 100 % on most nights.

`tests/e2e/test_indexer_perf.py` (markered `@pytest.mark.slow`, run on schedule) measures these; any regression > 50 % vs the previous baseline blocks merge.

## 12. CLI surface

```
personalscraper library index [--mode {quick|incremental|enrich|full}] [--disk DISK]
                              [--budget SECONDS] [--dry-run]
    Run a scan in the chosen mode. Defaults to indexer.scan.nightly_mode (quick).
    Acquires the writer lock. Prints summary + scan_run id. --disk scopes to one
    disk; --full --disk D is the standard "rebuild one disk per night" pattern.

personalscraper library status
    Prints: disk inventory, last scan time per disk, generation, mounted/unmounted,
    pending outbox/repair queue depths, deleted_item counts, Spotlight availability
    per disk, time since last enrich pass.

personalscraper library verify [--disk DISK]
    Runs a verify scan: re-stat every file, escalate to tier 2 on mismatch, no
    soft-delete (only marks for repair).

personalscraper library search QUERY [--limit N]
    Flex-attr query language (see §13). Examples:
      year:2024 disk:Disk1 -nfo:valid
      kind:show codec:hevc -trailer
      title:"Lost Highway"

personalscraper library repair [--budget SECONDS]
    Drains the repair queue with a custom time budget.

personalscraper library show ITEM_ID
    Pretty-prints all stored data for one item.

personalscraper config migrate-to-v2 [--dry-run]
    One-shot migration of legacy config.json5 → split files.
```

## 13. Query language (minimal flex-attr parser)

Inspired by beets' `dbcore/query.py`, scoped down. Tokens:

- `field:value` — equality
- `field:value*` — prefix match
- `-field:value` — negation
- `field:>=N`, `field:<=N`, `field:>N`, `field:<N` — numeric comparisons
- `"quoted phrase"` — exact title fragment
- Implicit `AND` between tokens

### 13.1 Field → table mapping

Every recognized field maps to one of three resolution paths. The parser registry (`indexer/query.py::FIELD_REGISTRY`) declares each field's column, its target table, and its value coercion. Unknown fields are treated as flex-attribute lookups.

| Field         | Resolution                         | SQL fragment                                                                                                                                                                         |
| ------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `kind`        | column `media_item.kind`           | `media_item.kind = ?` (str)                                                                                                                                                          |
| `title`       | column `media_item.title` LIKE     | `media_item.title LIKE ?` (str, % auto-wrapped unless quoted)                                                                                                                        |
| `year`        | column `media_item.year` (int)     | `media_item.year op ?`                                                                                                                                                               |
| `disk`        | join `disk.label`                  | `disk.label = ?` (str)                                                                                                                                                               |
| `category`    | column `media_item.category_id`    | `media_item.category_id = ?` (str)                                                                                                                                                   |
| `tmdb_id`     | column `media_item.tmdb_id` (int)  | `media_item.tmdb_id op ?`                                                                                                                                                            |
| `imdb_id`     | column `media_item.imdb_id`        | `media_item.imdb_id = ?` (str)                                                                                                                                                       |
| `nfo`         | column `media_item.nfo_status`     | `media_item.nfo_status = ?` ∈ `{missing,invalid,valid}`                                                                                                                              |
| `codec`       | join `media_stream.codec`          | `EXISTS (SELECT 1 FROM media_stream s JOIN media_file f ON s.file_id=f.id JOIN media_release r ON f.release_id=r.id WHERE r.item_id=media_item.id AND s.kind='video' AND s.codec=?)` |
| `lang`        | join `media_stream.lang`           | similar EXISTS, `s.kind='audio' AND s.lang=?`                                                                                                                                        |
| `quality`     | join `media_release.quality`       | `EXISTS (SELECT 1 FROM media_release WHERE item_id=media_item.id AND quality=?)`                                                                                                     |
| any other key | flex attribute on `item_attribute` | value: `EXISTS (SELECT 1 FROM item_attribute WHERE item_id=media_item.id AND key=? AND value=?)` ; presence: `EXISTS (... key=?)`                                                    |

**Flex-attr type coercion**: values are stored TEXT-only. Numeric comparisons (`field:>=N`) on a flex-attr key require the field to be declared with a `numeric` type in the registry; otherwise the parser raises an explicit `QueryError("flex attribute X has no declared type; can only test equality and presence")`. This matches beets' contract (typed fields list at registration time).

**Negation** (`-field:value`) compiles to `NOT (...)` of the same fragment; for `EXISTS` joins, the negation becomes `NOT EXISTS (...)`. Bare-key negation on flex attrs (`-trailer_found`) is presence-negation: `NOT EXISTS (SELECT 1 FROM item_attribute WHERE item_id=media_item.id AND key='trailer_found')`.

**Implicit AND** between tokens compiles as conjunction in a single `WHERE` clause, not via `INTERSECT` (which was the spec's earlier shorthand — concrete implementation uses AND).

The parser is one ~250-LOC module covering tokenisation, registry lookup, SQL fragment composition, and parameter binding. Tests cover each registry path.

## 14. Cron / scheduling

Two launchd plist templates ship under `docs/reference/launchd/`:

- **`personalscraper-index-quick.plist`** — runs `personalscraper library index --mode quick` every night at 03:30 (right after `personalscraper run` at 03:00). Sub-minute when no FS changes; never reads more than tier-1 fingerprint per file. **Default recommended cron.**
- **`personalscraper-index-rotate.plist`** — runs `personalscraper library index --mode full --disk DiskN` once per night, rotating across disks (Mon=Disk1, Tue=Disk2, Wed=Disk3, Thu=Disk4); falls back to `quick` on Fri/Sat/Sun. Use this in addition to the daily `quick` if you want a guaranteed full-rebuild cadence (one disk per night, never more).
- **`personalscraper-index-enrich.plist`** _(optional)_ — runs `personalscraper library index --mode enrich --budget 1800` weekly to fill in `media_stream`/NFO/artwork data deferred during normal runs.

Logs land in `__logit__/index.YYYY-MM-DD.log`.

All cron entries are **opt-in** (user installs plists manually). The indexer also keeps itself current via outbox write-through during pipeline operations, so a missed cron night does not introduce silent drift — only delays catching _external_ changes (manual `rm`, `mv`, USB swap).

## 15. Testing strategy

### 15.1 Unit tests

Per-module under `tests/indexer/`. Each repo has an in-memory SQLite fixture (`:memory:`) seeded from a small fixture SQL file. Each scanner / fingerprint / drift function is tested in isolation.

### 15.2 Property-based tests

`hypothesis` for:

- **Idempotence**: scanning the same FS twice produces the same DB state.
- **Generation monotonicity**: scan generation is strictly increasing.
- **Soft-delete correctness**: a row with `miss_strikes < N` is never `deleted_at`-set; a row with `miss_strikes ≥ N` always is.
- **Outbox drain idempotence**: replaying a drained outbox row is a no-op.
- **Hash determinism**: `oshash(f) == oshash(f)` for unchanged file; `oshash(f) ≠ oshash(g)` for any non-trivial content edit.

#### 15.2.1 Hypothesis generators (concrete strategies)

Strategies live in `tests/indexer/strategies.py`:

```python
@composite
def valid_file(draw):
    """Generate a single fixture file: size 0..10 GiB, mtime within ±10 days
    of a fixed test epoch, ASCII+UTF-8 path leaf, depth 1..6, content seeded
    pseudo-random. Returns (relpath, size, mtime_ns, content_seed).
    """

@composite
def valid_disk_layout(draw):
    """1..4 disks; each disk has 0..1000 valid_file() entries grouped under
    1..3 category folders (movies/, tv_shows/) with 1..50 items per category.
    Returns DiskLayout dataclass.
    """

@composite
def mutation(draw):
    """One of: rename(file), delete(file), size_edit(file, delta_bytes),
    mtime_touch(file, delta_seconds), no_op(). Returns Mutation dataclass
    that can be applied to a DiskLayout to produce a successor layout.
    """
```

Property tests then compose these:

```python
@given(layout=valid_disk_layout(), mutations=lists(mutation(), max_size=20))
def test_idempotence_under_random_mutations(layout, mutations):
    fs = build_fs(layout)
    db = scan(fs)
    for m in mutations:
        m.apply(fs)
    db_after = scan(fs)
    db_after_repeat = scan(fs)        # idempotence: second scan = first
    assert db_after == db_after_repeat
```

Each property in §15.2 must be expressed via `@given` over these strategies, not example-based. CI requires `@given` decorator count ≥ 5 in `tests/indexer/test_drift.py`.

### 15.3 Filesystem tests

`pyfakefs` for tests that need a fabricated FS tree without `tmp_path` plumbing. Used heavily in `test_scanner.py` and `test_drift.py`.

### 15.4 Golden tests

- **Config migration**: load monolithic `config.json5` → `Config_v1`. Run `migrate_v1_to_v2` → load split files → `Config_v2`. Assert `Config_v1 == Config_v2` field-by-field. Required to pass before merging.
- **Indexer schema migration**: empty DB → `apply_migrations` → assert pragma `user_version` matches expected. Add a row using v1 schema, apply v2 migration, assert row is preserved.
- **Consumer parity**: see §15.4.1 for the concrete fixture + assertion contract.

#### 15.4.1 Consumer parity contract

The parity test is committed under `tests/fixtures/parity/`:

- `tests/fixtures/parity/v0.7-fs/` — a tarball-extracted minimal FS tree (~30 items spanning movies, TV shows w/ seasons, audiobooks). Pinned to commit `<v0.7 SHA>` of personalscraper.
- `tests/fixtures/parity/v0.7-library_scan.json` — the snapshot produced by running v0.7's `library scan` against `v0.7-fs/`. Generated once, checked in, never regenerated.
- `tests/fixtures/parity/v0.7-media_index.json` — same snapshot for `MediaIndex.rebuild()`.

Assertion shape (in `tests/integration/test_consumer_parity.py`):

```python
def test_indexer_matches_v07_library_scan(parity_fs, parity_v07_snapshot):
    db = scan(parity_fs, mode='full')
    indexer_items = {(r.disk_label, r.rel_path) for r in db.query_items()}
    v07_items = {(item['disk'], item['path']) for item in parity_v07_snapshot['items']}
    assert indexer_items == v07_items                     # 1:1 set match
    for v07_item in parity_v07_snapshot['items']:
        idx_item = db.find_by_path(v07_item['disk'], v07_item['path'])
        assert idx_item.nfo_status == v07_item['nfo']['status']
        assert idx_item.artwork_present == v07_item['artwork']
        if v07_item['media_type'] == 'tvshow':
            assert {s.number for s in idx_item.seasons} == {s['number'] for s in v07_item['seasons']}
```

Required to pass before Phase 7 closes (consumer migration is what this test verifies).

### 15.5 E2E and integration tests

**E2E suite** (`tests/e2e/`):

- `test_pipeline_indexer.py` — full pipeline run (ingest → sort → process → verify → dispatch) on a fabricated 50-item filesystem fixture, asserts the indexer reflects the final state and the outbox is empty at end.
- `test_indexer_cold_to_warm.py` — cold scan → mutate FS (rename folder, delete file, add file) → incremental scan → assert generations, strikes, `deleted_at`, and renamed files survive via OSHash.
- `test_indexer_unplug_disk.py` — scan all disks → unmount one → scan again → no strike, no soft-delete, only `indexer.disk.skipped_unmounted` event.
- `test_indexer_unplug_during_scan.py` — start scan; monkey-patch `os.path.ismount` to flip false at file 50/100 of Disk2; assert per-disk transaction rolled back, Disk1 progress committed, sentinel intact, `indexer.disk.io_error` logged, `disk.unreachable_strikes += 1`.
- `test_indexer_budget_resume.py` — start scan with `--budget 5`; monkey-patch clock to exceed budget mid-walk; assert checkpoint commit, `scan_run.status='ok'` with `stats_json.budget_exhausted=true`, `last_path` populated; next invocation resumes from `last_path` and produces same final state as uninterrupted run.
- `test_indexer_writer_lock_contention.py` — spawn two subprocesses racing on `library.db.lock`; first acquires; second with `--wait-for-lock 0` fails fast with the holding PID in error; second with `--wait-for-lock 60` waits until first releases then succeeds; no DB corruption.
- `test_indexer_disk_swap.py` — scan a disk, then swap its content (same UUID, different filesystem state) and rescan; assert Merkle delta exceeds `merkle_delta_freeze_threshold`, scanner halts that disk, logs `indexer.disk.suspected_restore`; `--confirm-bulk-change` allows proceeding.
- `test_indexer_oshash_collision.py` — fabricate two files with crafted identical OSHash and different content; rescan; assert `repair_queue(reason='oshash_collision')` row exists, no auto-rename applied.
- `test_indexer_db_corrupt_recovery.py` — corrupt `library.db` mid-byte, restart indexer; assert quarantine to `library.db.corrupt-<ts>`, refusal to start without `--rebuild`; `--rebuild` triggers full Stage-A rescan.
- `test_indexer_partial_migration.py` — invoke `config migrate-to-v2`, kill mid-execution; assert `.personalscraper/config.in-progress/` exists; next loader invocation refuses to load and prints actionable message; resolve by `rm -rf` and rerun migration.
- `test_indexer_spotlight_unavailable.py` / `test_indexer_spotlight_partial.py` — patch `mdutil -s` to return `off` / `Indexing enabled but rebuilding` / timeout; assert dir-mtime walk fallback runs in each case; logs `indexer.spotlight.skipped_*` event with reason.
- `test_indexer_racy_mtime.py` — write file with mtime exactly `scan_started_at`; assert tier-1 fingerprint flagged racy → tier-2 (xxh3_partial) computed; mtime in the future → clamped + `indexer.fs.invalid_mtime` logged.
- `test_indexer_cross_dst.py` — scan crossing a DST or leap-second boundary (mock `time.time()` jumping ±3600 s); assert no spurious racy flags, no double-count.

**Integration suite** (`tests/integration/`) — these tests run real `tmp_path` filesystem fixtures and DO NOT use the heavily-mocked unit-test patterns from pre-PR-#14:

- `test_outbox_writethrough_dispatch.py` — `dispatch.move(file)` writes one row to `index_outbox` with `op='move'` and matching payload; drainer consumes it; indexer reflects new path.
- `test_outbox_writethrough_nfo.py` — `scraper/nfo_generator.write_nfo(...)` writes an `op='nfo_write'` outbox row; drainer updates `media_item.nfo_status` and IDs.
- `test_outbox_writethrough_artwork.py` — same pattern for `scraper/artwork.download(...)` → `op='artwork_write'` → `media_item.artwork_json` flag flipped.
- `test_outbox_writethrough_trailer.py` — `trailers/orchestrator.download_trailer(...)` → `op='trailer_download'` → `item_attribute(key='trailer_found')` upserted.

**Outbox tests live in `tests/integration/`, NOT in the existing `tests/dispatch/test_dispatcher.py`** — that file was trimmed during the `test-realism` refactor (PR #14) from 37 `@patch` calls; we must not regrow it. Existing dispatcher unit tests stay focused on dispatcher invariants, integration tests own the cross-module outbox assertions.

#### 15.5.1 Migration chain replay test (`tests/indexer/test_migrations.py`)

Phase 1 ships only `001_init.sql` but the indexer DB will accumulate migrations 002, 003... over years. To guard against drift between hand-edited migrations and the conceptual schema, every migration PR must add a fixture in `tests/indexer/migration_fixtures/v<N>.sql` representing a v<N> DB; the test:

```python
def test_chain_replay_matches_init_sql(tmp_path):
    """Apply every migration in order against a v1 fixture and assert the
    resulting schema matches a fresh apply of all migrations starting from
    an empty DB. Catches the case where someone fixes init.sql but forgets
    to write a migration script.
    """
    # Path A: load v1 fixture, apply 002..NNN
    db_a = open_db(tmp_path / "a.db")
    apply_sql_file(db_a, FIXTURES / "v1.sql")
    apply_migrations(db_a, MIGRATIONS_DIR, start_from=2)

    # Path B: empty DB, apply all migrations 001..NNN
    db_b = open_db(tmp_path / "b.db")
    apply_migrations(db_b, MIGRATIONS_DIR, start_from=1)

    assert dump_schema(db_a) == dump_schema(db_b)
```

#### 15.5.2 CLI golden tests (`tests/indexer/test_cli.py`)

Click/Typer `runner.invoke()` based; minimum 12 cases:

| Test                                                          | Asserts                                                                           |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `library index --mode quick` no changes                       | exit 0; stdout JSON summary `{"mode":"quick","items_unchanged":N}`                |
| `library index --mode quick` with 5 changed files             | exit 0; summary lists `items_updated:5`                                           |
| `library index --mode full --disk Disk1`                      | exit 0; only Disk1 columns updated; `scan_run.disk_filter='Disk1'`                |
| `library index --mode full --disk UnknownDisk`                | exit 2; stderr "no disk with label 'UnknownDisk'"                                 |
| `library index` while another instance holds the lock         | exit 1; stderr "indexer locked by PID <n>"                                        |
| `library index --wait-for-lock 5` lock released within budget | exit 0                                                                            |
| `library index --dry-run --mode full`                         | exit 0; summary marked `dry_run:true`; assert no UPSERT touched any media\_\* row |
| `library status`                                              | exit 0; tabular output of disks, last scan, generation, queue depths              |
| `library search "year:2024 disk:Disk1 -nfo:valid"`            | exit 0; valid result rows                                                         |
| `library search "field_does_not_exist:foo"`                   | exit 2; "unknown field"                                                           |
| `library show <unknown_id>`                                   | exit 2; "no item with id"                                                         |
| `library repair --budget 10`                                  | exit 0; drains up to 10 s of repair queue; stops cleanly                          |
| `library verify --disk Disk2`                                 | exit 0; no soft-deletes; repair queue grows on tier-2 mismatches                  |
| `config migrate-to-v2 --dry-run` with malformed v1            | exit 2; stderr lists offending keys; no files written                             |

### 15.6 Performance regression tests

A `tests/e2e/test_indexer_perf.py` (markered `@pytest.mark.slow`, off by default) measures all four scan modes — see §11.11 for the full target table. CI runs it on a schedule, not per-PR. Any regression > 50 % vs the previous baseline blocks merge. The tests also exercise:

- `quick` mode dir-mtime fast path (no I/O on unchanged subtrees).
- Splittable cold scan: `--full --disk D1` then `--full --disk D2` produces the same final state as `--full` over both.
- Two-stage path: cold `quick` then `enrich` produces the same DB state as a single `full`.

#### 15.6.1 Fixture builder + baseline storage

- **Fixture builder**: `tests/e2e/perf/build_fixture.py` generates a deterministic 1 000-item / ~1 TB virtual FS using a pinned random seed. File-size distribution: 5 % > 50 GB (sparse files via `truncate(2)` to avoid actually writing TB), 70 % 1–5 GB (sparse), 25 % < 100 MB (real content, fixed pseudo-random). Output goes under `tests/e2e/perf/.fixture/` (gitignored). Fixture version pinned in `tests/e2e/perf/FIXTURE_VERSION` (one integer); changing it forces a baseline reset.
- **Baseline file**: `tests/e2e/perf/baseline.json` — checked in. Schema: `{fixture_version, mode, target_seconds, last_measured_seconds, last_measured_at}` per row. Test compares `current_run` against `last_measured_seconds * 1.5` (the 50 % regression rule).
- **Baseline regeneration**: a `make perf-rebaseline` target runs the test, writes new measurements, and a CI job on `main` (scheduled, not per-PR) commits the new file with a `[bot] perf baseline` message. Per-PR CI compares only.

## 16. Phasing

### Phase 0 — Config Overhaul (sub-phases 0.0–0.5)

- 0.0 Add runtime + dev dependencies to `pyproject.toml` (pymediainfo, xxhash, filelock; sqlite-utils, pyfakefs, hypothesis); document `brew install media-info`.
- 0.1 `conf/loader.py` + `conf/overlay.py` skeleton with multi-file merge.
- 0.2 Split `config.json5` into the target files (no schema change yet).
- 0.3 `conf/migration.py` + `personalscraper config migrate-to-v2` CLI.
- 0.4 Pydantic `IndexerConfig` submodel + integration in `Config`.
- 0.5 Golden tests + behavioural-parity assertions; existing tests pass unchanged.

Gate: full test suite green on v2 config; `config migrate-to-v2` produces an exactly-equivalent `Config`.

### Phase 1 — Indexer Core: DB layer (sub-phases 1.1–1.5)

- 1.1 `indexer/db.py` + connection PRAGMAs + `filelock` lock.
- 1.2 `indexer/migrations/001_init.sql` with the full schema.
- 1.3 `indexer/migrations` applier (`apply_migrations`) + `PRAGMA user_version` lockstep.
- 1.4 `indexer/schema.py` dataclasses + per-table `Repository` skeletons (raw SQL).
- 1.5 Per-repo unit tests (`test_repos_disk.py`, `test_repos_item.py`, …).

Gate: `personalscraper library status` runs on a fresh DB and prints "no scans yet".

### Phase 2 — Indexer Core: Scanner (modes `full` and `quick`)

- 2.1 `indexer/fingerprint.py` (OSHash with known-vector tests, xxh3_partial, tier1 helpers; extension allowlist for OSHash).
- 2.2 `indexer/mediainfo.py` (pymediainfo wrapper, `min_size_mb` skip, `parse_speed` toggle, library-load fail-fast). NOT called from scanner yet — wired in Phase 4.
- 2.3 `indexer/merkle.py` (per-disk Merkle root + `verify_disk_mounted` minimal guard: UNMOUNTED → raise; `MOUNTED_AND_VERIFIED` → proceed; `NO_SENTINEL` → bootstrap via `diskutil info -plist` and write sentinel; `MOUNTED_WRONG_DISK` → raise). The full state-machine + `pending_op`/strike logic lands in Phase 3.5.
- 2.4 `indexer/scanner.py` core walk: stat + OSHash + `path.dir_mtime_ns` write-through.
- 2.5 **Stage A (fingerprint-only)** `--mode full` path: stat + OSHash, no mediainfo. `--disk D` scoping.
- 2.6 **`--mode quick`** path: per-disk Merkle short-circuit first; on miss, dir-mtime subtree-skip; tier-1 fingerprint only on changed files.
- 2.7 `personalscraper library index --mode {full|quick} [--disk D]` populates the DB. **No outbox integration in this phase** — write-through hooks land in Phase 5 (5.5 wires the drainer into this CLI). The CLI built here calls a no-op `outbox.drain_if_present()` stub that is replaced in Phase 5.

Gate: full scan of fixture FS (Stage A) populates `media_file` rows; subsequent `quick` run with no FS changes reads only directory mtimes (asserted via fs_usage trace or syscall counter); `BootstrapError` raised when `diskutil` cannot resolve a UUID.

### Phase 3 — Indexer Core: Drift + Reconciliation

- 3.1 `indexer/drift.py` (racy-mtime, scan_generation comparisons, miss_strikes).
- 3.2 N-strikes soft-delete + `deleted_item` writes.
- 3.3 Repair queue + worker (`indexer/repair.py`) with budget.
- 3.4 Resumable scan via `scan_run.last_path`.
- 3.5 Per-disk circuit breaker delegating to `scraper/circuit_breaker.py`.

Gate: cold→FS-mutate→incremental sequence reproduces expected drift events; soft-delete only after N strikes; rename survives via OSHash; unmounted disk = no strikes.

### Phase 4 — Performance + scan modes (`incremental`, `enrich`)

- 4.1 `--mode incremental` path: `quick` + OSHash recompute on changed files + rename resolution via OSHash lookup.
- 4.2 `--mode enrich`: pymediainfo + NFO + artwork inventory on rows missing those columns; budget-bounded; per-file commits.
- 4.3 ThreadPoolExecutor parallel disk walk (one worker per mounted disk; capped by `max_workers_total`).
- 4.4 Mount-flag detection (parses `mount` output) + warn-at-scan if `noatime,nodiratime,noappledouble,noapplexattr,defer_permissions,allow_other` are not all set + README/`docs/reference/storage.md` update.
- 4.5 `indexer/_macos_io.py::sequential_hint(fd)` (Darwin: `fcntl(fd, F_RDADVISE, ...)`; elsewhere: no-op) on every fingerprint/mediainfo open.
- 4.6 Read-rate token bucket (`indexer.scan.read_rate_mb_per_sec`) + tests.
- 4.7 Bulk-insert path during `--full`: drop secondary indexes → `executemany` batches of 5 000 → recreate indexes.
- 4.8 Spotlight integration **scoped to APFS staging dir only** (not macFUSE storage disks): `mdutil -s` probe per path; `SpotlightChangeDetector` attaches only on APFS, refuses macFUSE; storage disks always use dir-mtime walk regardless of Spotlight state.
- 4.9 SIGTERM clean-shutdown handler (`signal.signal(SIGTERM, ...)`) → commit current disk transaction + checkpoint + exit 0.
- 4.10 Performance regression test fixture (1 000-item / 1 TB representative subset) + threshold assertions per §11.11.

Gate: all four modes hit their target times in §11.11; SIGTERM during a `--full` scan results in resumable state on next run; Spotlight detection is exercised on a real APFS volume in CI when available, dir-mtime fallback path covered by pyfakefs tests.

### Phase 5 — Outbox + write-through

- 5.1 `index_outbox` + `pending_op` repos.
- 5.2 `indexer/outbox.py` drainer.
- 5.3 Hooks in `dispatch/dispatcher.py`, `scraper/nfo_generator.py`, `scraper/artwork.py`, `trailers/orchestrator.py`.
- 5.4 Tests asserting outbox row presence after each pipeline mutation.
- 5.5 Drainer integration into `personalscraper library index`.

Gate: a pipeline run leaves an empty outbox at end (drained) and the indexer reflects every mutation.

### Phase 6 — Consumer migration: dispatch

- 6.1 Rewrite `MediaIndex` as a thin wrapper over `indexer.repos`.
- 6.2 Remove `media_index.json` writes/reads.
- 6.3 First-run detection: missing JSON triggers indexer rebuild for affected disks.
- 6.4 All `tests/dispatch/*` pass unchanged or with surgical edits.

Gate: full pipeline run end-to-end with no `media_index.json` on disk; dispatch decisions identical to v0.7 on a fixture FS.

### Phase 7 — Consumer migration: library + trailers

- 7.1 Rewrite `library/scanner.py` to populate the indexer.
- 7.2 Rewrite `library/analyzer.py` to query the indexer.
- 7.3 Rewrite `library/reporter.py` to query the indexer.
- 7.4 Migrate `library/rescraper.py`, `disk_cleaner.py`, `recommender.py`.
- 7.5 Migrate `trailers/scanner.py` to `indexer.query.find_items_without_trailer()`.
- 7.6 Remove `library_scan.json`, `library_analysis.json`, the `library_scan_max_age_hours` config knob, and the in-memory TTL cache layer.

Gate: full `personalscraper trailers scan` run produces the same result set as v0.7 on a fixture FS.

### Phase 8 — CLI + cron + query language

- 8.1 `personalscraper library index --mode {quick|incremental|enrich|full} [--disk D] [--budget S] [--dry-run]` + the rest of the family (`status/verify/search/repair/show`).
- 8.2 `indexer/query.py` minimal flex-attr parser.
- 8.3 Three launchd plist templates: `personalscraper-index-quick.plist` (daily quick), `personalscraper-index-rotate.plist` (weekly rotation full per disk), `personalscraper-index-enrich.plist` (weekly enrich pass).
- 8.4 Documentation pass: `docs/reference/architecture.md`, `docs/reference/storage.md` (mount flags + 24 TB ops guide), new `docs/reference/indexer.md` covering schema, drift policy, scan modes, query language, cold-rebuild playbook.

Gate: README updated; CLI golden tests pass; documentation complete; all three plists install cleanly via `launchctl bootstrap` in a CI container.

## 17. Risks, failure modes & deferred items

### 17.1 Failure-mode policies (mandatory behaviour)

These are the policies an implementer must follow when each named failure occurs. Each item maps to a structured log event so the operator can diagnose afterwards.

**DB layer**:

- **`OperationalError: database is locked` after `busy_timeout=5000`** — retry up to 3× with backoff (50 ms, 200 ms, 1 s). For outbox publishers, after exhaustion, log `indexer.db.outbox_lost` with payload and continue (FS op already succeeded; next scan reconciles). For scanner transactions, abort the disk's transaction, mark `scan_run.status='aborted'`, exit non-zero.
- **`sqlite3.DatabaseError: database disk image is malformed` on open** — quarantine the file as `library.db.corrupt-<unix_ts>`, refuse to start unless `--rebuild` is passed (a flag on `library index` that triggers a full Stage-A rescan from scratch), log `indexer.db.corrupt`.
- **Stale `library.db.lock` (PID exists but zombie / no longer holds DB)** — the lockfile contents are `{pid, started_at, hostname}`. On acquire-timeout, `os.kill(pid, 0)` checks liveness; if the PID is dead or belongs to another binary, log `indexer.lock.stale_recovered` and break the lock. If alive, fail with the holding PID in the error.
- **Disk full / WAL bloat during cold scan** — pre-scan `os.statvfs` check refuses to start if free space < `2 × estimated_wal_growth` (estimated as `expected_rows × 4 KB`). Mid-scan `disk I/O error` triggers an explicit `PRAGMA wal_checkpoint(TRUNCATE)` then commit current disk transaction and exit non-zero with `indexer.db.disk_full`.
- **Migration script fails mid-execution** — every `apply_migrations` run takes a `library.db.pre-migration-<ver>.bak` snapshot before applying. Failure → restore from snapshot, log `indexer.migration.failed`, exit non-zero. Migration scripts must be transactional DDL only; non-transactional ops (`VACUUM`) are forbidden in migrations.

**Filesystem**:

- **macFUSE crash mid-scan (`OSError(EIO)` on `os.scandir`)** — `try/except OSError` per disk: roll back that disk's transaction, mark `disk.is_mounted=0`, increment `disk.unreachable_strikes`, log `indexer.disk.io_error`, fire per-disk circuit breaker, continue with remaining disks.
- **`OSError: Permission denied` on a single file** — log `indexer.file.permission_denied` at WARNING, leave the existing row untouched (no strike, no soft-delete), continue.
- **Symlinks** — `os.scandir` is called with `follow_symlinks=False` implicitly (default). Symlinks are recorded as `media_file` rows with `oshash=NULL` and `enriched_at=NULL` and **never** fingerprinted. The scanner never crosses disk boundaries via symlink.
- **Hidden / system files** — explicit exclusion list maintained in `patterns.json5` (`.fseventsd`, `$Recycle.Bin`, `.Spotlight-V100`, `.Trashes`, `System Volume Information`, files with `._` prefix on NTFS, `.DS_Store`). Skipped before stat.
- **mtime in the future or pre-1970** — clamp to `[unix_epoch, scan_started_at]`; mtimes outside this range trigger `indexer.fs.invalid_mtime` and store `mtime_ns = scan_started_at_ns`. Never causes `racy=true` based on raw value.

**Pipeline integration**:

- **Outbox drainer crashes mid-row** — every row's `processed_at` is set in the same transaction as the row's effect on indexer tables. A crashed drainer leaves the row in `pending` state; replay is idempotent per the §9.3 contract.
- **Outbox row references unmounted disk** — drainer detects and moves the row to `pending_op` with `status='deferred'`; row is replayed on next scan that finds the disk mounted. `pending_op.replayed_at` set at replay time. TTL: rows older than 30 days are dropped with `indexer.pending_op.ttl_expired`.
- **Pipeline crashes between FS mutation and outbox insert** — silent miss; reconciled by next scan via dir-mtime walk. To shorten the gap, the scanner's `quick` mode also re-walks any path mentioned in the last 24 h of `scan_event` rows of type `outbox.move`/`outbox.nfo_write`/`outbox.artwork_write`/`outbox.trailer_download`, regardless of dir mtime (the "paranoia branch").

**Scan lifecycle**:

- **Two `library index` invocations race** — second one fails fast (`filelock` `Timeout(0)` by default). User can pass `--wait-for-lock SECONDS` to wait. Cron entries always pass `--wait-for-lock 0` so a stuck scan never blocks the next slot.
- **Machine sleeps mid-scan (SIGTERM from launchd)** — handler commits current disk's transaction, updates `scan_run.last_path`, exits 0. Next invocation reads `scan_run` and resumes from `last_path`.
- **SIGKILL or panic** — no clean shutdown; recovery on next start: if the most recent `scan_run.status='running'` and `started_at > 2 h ago` AND the recorded PID is no longer alive, treat as crashed and resume; if started < 2 h ago AND PID alive, fail-fast with `indexer.lock.live_pid`.
- **`scan_budget_seconds` overrun** — at every checkpoint, compare `now - started_at` against budget; on overrun, finish current file, commit, set `scan_run.status='ok'` with `stats_json.budget_exhausted=true`, exit 0. Resume next run from `last_path`.

**Drift edge cases**:

- **OSHash collision (two paths same hash)** — only treated as a rename if (a) hashes match AND (b) `size_bytes` match AND (c) the existing row's path is no longer present this scan. Otherwise enqueue `repair_queue(reason='oshash_collision')` and skip auto-rename.
- **Disk swapped: same UUID, different content (e.g. user restored from backup)** — sentinel passes (UUID matches), but the freshly-computed Merkle root differs from `disk.merkle_root` by more than `merkle_delta_freeze_threshold` (default 50% of files). Scanner halts that disk, logs `indexer.disk.suspected_restore`, requires `library index --confirm-bulk-change --disk D` to proceed.
- **Strikes after long unmount + remount** — strike counter is monotonic per row but only increments on a scan where `is_mounted=1` and the row's path is missing. A 30-day unmount with no in-between scans = no strike change. After remount, if the file is back, the next scan resets strikes to 0 (existing behaviour).
- **Repair queue grows unboundedly** — `library status` flags WARN (non-zero exit code) if `(oldest pending > 7 days)` OR `(depth > 1000)`. The user is the actor who must investigate.

**Migration**:

- **Partial config v1 → v2 failure** — migration writes to `.personalscraper/config.in-progress/`, then `os.rename()` atomically to `.personalscraper/config/` only on full success. On startup, if `.in-progress/` exists, refuse to load and log instructions to manually rename or delete it.
- **Unknown legacy keys in v1 config** — every key in `config.json5` v1 not consumed by `migrate_v1_to_v2` is appended to `.personalscraper/config/local.json5` under a `_migration_unknown_keys` block AND emitted to `.personalscraper/migration-warnings.txt`. User reviews and integrates.
- **`--dry-run` semantics** — the flag suppresses: all `INSERT`/`UPDATE` against `media_*` tables, sentinel creation, and outbox drains. `scan_event` rows are still written under a synthetic `scan_run(mode=…, status='dry-run')` so the user can inspect what _would_ have changed.

### 17.2 Risks (residual, post-mitigation)

- **Schema rigidity in year 3.** Mitigated by the flex-attr table — new fields go there before they earn a column.
- **macFUSE NTFS quirks discovered in production.** Mitigated by mountpoint+sentinel guard, UUID bootstrap, N-strikes, per-disk circuit breaker.
- **Cold scan duration on 24 TB.** Mitigated by Stage A/Stage B split (cold rebuild reads ~6-12 GB per disk, not ~25), `--full --disk D` rotation, hard `budget_seconds` cap with crash-resume. Worst-case cold rebuild of all four disks = 4 nights, fully under user control.
- **Disk wear from over-aggressive nightlies.** Mitigated by `quick` mode default (zero file reads on Merkle hit), `noatime` mount flag, `read_rate_mb_per_sec` throttle, F_RDADVISE sequential hint, SIGTERM clean-shutdown.
- **Spotlight delegation skipped on storage disks.** macFUSE volumes are not Spotlight-indexable; the design explicitly does not rely on Spotlight for storage-disk change detection. Spotlight is only used for the APFS staging directory.
- **Category renaming breaks `media_item.category_id` references.** `category_id` is a soft FK to a logical category declared in `categories.json5`; SQLite has no row-level constraint pointing at config. If a user renames `movies_animation` → `animated_movies` in the config, every `media_item` row referencing the old id becomes orphan-tagged. **Mitigation**: the loader compares the union of declared category ids against `SELECT DISTINCT category_id FROM media_item` at startup; on mismatch it logs `indexer.config.category_orphan` listing affected ids and refuses to scan until the user runs `personalscraper config migrate-category --from old --to new` (a small CLI that issues `UPDATE media_item SET category_id = new WHERE category_id = old`). `library status` also surfaces the orphan count.

### 17.3 Deferred to a later minor

- `enzyme`/`mutagen.MP4` container fast-path (V1.1 if the `enrich` pass is too slow on the real 24 TB library; the `indexer/mediainfo.py` abstraction is shaped for it).
- `getattrlistbulk` ctypes wrapper (note: macFUSE does NOT bridge bulk attribute syscalls, so this only helps APFS staging — V1.1 if profiled as worth it).
- Watchdog on staging APFS dir for opportunistic pre-indexing of incoming items.
- Multi-process safe writer (current model is single-process).
- Litestream offsite replication.
- Per-folder Merkle (per-disk is enough at our scale).
- Web UI consuming the indexer.

## 18. Dependencies

### Runtime additions to `pyproject.toml`

```toml
"pymediainfo>=6.1.0",     # libmediainfo wrapper, codec/audio/duration/resolution
"xxhash>=3.4.0",          # xxh3_64 partial-file fingerprint
"filelock>=3.13.0",       # cross-platform writer lock
```

### Dev additions

```toml
"sqlite-utils>=3.36",     # debug/inspection CLI, NOT runtime
"pyfakefs>=5.4.0",        # in-memory FS for indexer tests
"hypothesis>=6.100.0",    # property tests for idempotence / drift state machine
```

### System dependency (documented in README)

```
brew install media-info
```

`pymediainfo` fails fast at import time if `libmediainfo.dylib` is not found, with a clear error message pointing at this command.

### Explicitly NOT added

`apsw`, `aiosqlite`, `peewee`, `SQLModel`, `Pony`, `dataset`, `alembic`, `yoyo-migrations`, `pyfilesystem2`, `xattr`, `pyav`, `enzyme`, `mutagen`, `ffmpeg-python`, `pyblake3`, `portalocker`, `loguru`, `prometheus-client`, `opentelemetry-api`, `freezegun`, `diskcache`, `watchdog`.

## 19. Glossary

| Term                      | Definition                                                                                                                                                                                                                                                                |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SSOT**                  | Single Source of Truth — the disks themselves. The indexer is a queryable mirror, never authoritative.                                                                                                                                                                    |
| **OSHash**                | OpenSubtitles hash spec: `(filesize + sum(first 64KB u64) + sum(last 64KB u64)) mod 2^64`. Survives renames; ~128 KB read regardless of file size.                                                                                                                        |
| **xxh3_partial**          | xxh3_64 of the first N bytes + last N bytes (default 1 MB each). Drift-detection fallback when tier-1 fingerprint is racy.                                                                                                                                                |
| **Racy mtime**            | Per `git`'s racy-index, an mtime within ±2 s of the scan's start time is suspect because in-flight writes can produce identical mtime values undetectable at 1-second resolution. Forces escalation to xxh3_partial.                                                      |
| **N-strikes soft-delete** | A file missing for one scan is suspect, missing for N scans (default 3) is `deleted_at`-marked. Hard delete only on explicit purge or 365-day retention. Prevents "USB unplug → library wipe" disasters.                                                                  |
| **Mountpoint sentinel**   | A small file (`.personalscraper-disk-id`) on each disk root containing the disk's volume UUID. The scanner only proceeds if `os.path.ismount()` is true AND the sentinel matches; mismatched sentinel = different physical disk on the same mount = freeze, never delete. |
| **Per-disk Merkle root**  | A single hash over sorted `(path_id, size, mtime_ns, oshash)` of every file on a disk. Stored on `disk.merkle_root`. Lets a no-op rescan of a disk skip all per-file work in one comparison.                                                                              |
| **Outbox**                | A SQLite table where pipeline mutations (move, NFO write, trailer download) record their intent. The indexer drains the outbox in a separate transaction, reconciling intent against FS reality. Pattern from Microservices.io / Debezium.                                |
| **Hinted handoff**        | Borrowed from Cassandra: writes targeting an unreachable replica (here: an unmounted disk) are parked in `pending_op` and replayed when the replica is back.                                                                                                              |
| **Scan generation**       | Integer bumped at the start of every scan run. Rows with old generation are candidates for soft-delete or repair.                                                                                                                                                         |
| **Repair queue**          | A SQLite table holding drift-resolution work deferred from a scan. Drained by `repair.drain()` with a time budget; uncompleted items survive to next scan.                                                                                                                |
| **Flex attribute**        | A `(item_id, key, value)` row in `item_attribute`. Pattern from beets: extends the schema without `ALTER TABLE`.                                                                                                                                                          |
