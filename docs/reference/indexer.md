# Indexer Reference

The media indexer (`personalscraper/indexer/`) is a SQLite-backed subsystem that
replaces the three legacy JSON sources of truth (`media_index.json`,
`library_scan.json`, `library_analysis.json`) with a single queryable mirror of
the four storage disks.

Cross-references: DESIGN §6, §8, §11, §12, §13, §14, §17.

---

## Schema Overview

The database lives at `.personalscraper/library.db` by default (configurable
via `indexer.db_path`; WAL mode; must reside on the internal APFS disk).
Full DDL is in `personalscraper/indexer/migrations/001_init.sql`; the table list
below gives a one-line description of each table's role.

| Table            | Role                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------- |
| `disk`           | Stable disk identity by volume UUID; tracks mount path and unreachable-strike count.  |
| `path`           | Deduplicates `(disk_id, rel_path)` directory prefixes; holds `dir_mtime_ns` for skip. |
| `media_item`     | One row per work (movie or show); carries metadata, `category_id`, `nfo_status`.      |
| `item_attribute` | Flex-attribute table (beets pattern) — arbitrary `key/value` pairs per item.          |
| `season`         | TV-only hierarchy; one row per season number of a `kind='show'` item.                 |
| `episode`        | One row per episode within a season; title optional.                                  |
| `media_release`  | A specific version of a work (quality, edition, primary language).                    |
| `media_file`     | Physical file; drift signal via `(size_bytes, mtime_ns, ctime_ns, oshash)`.           |
| `media_stream`   | One row per video/audio/subtitle stream inside a `media_file` (from pymediainfo).     |
| `item_issue`     | Scanner-detected quality issues per item (`junk_files`, `ntfs_unsafe`, …).            |
| `index_outbox`   | Write-through events from dispatch/scraper/trailers; drained by the indexer.          |
| `pending_op`     | Hinted-handoff writes for unmounted disks; replayed on remount.                       |
| `repair_queue`   | Drift discovered during scan is enqueued here; drained by the repair worker.          |
| `scan_run`       | Audit log of every scan invocation; stores mode, generation, `stats_json`.            |
| `scan_event`     | High-frequency per-file/per-item events within a scan run.                            |
| `deleted_item`   | Soft-delete tombstone for items, files, or releases that were removed.                |
| `schema_version` | Singleton; mirrors `PRAGMA user_version`.                                             |

JSON columns (`artwork_json`, `payload_json`, `stats_json`) are validated by
Pydantic models in `personalscraper/indexer/schema.py`; see
`docs/reference/indexer-json-shapes.md` for the canonical shape of each.

---

## Drift Policy

The indexer uses a multi-tier reconciliation strategy to detect and repair
divergence between the database and the disks without ever wiping live entries.

### Tier 1 — stat-only check (quick and incremental modes)

On each scan the walker calls `os.stat()` on every media file and compares
`(size_bytes, mtime_ns, ctime_ns)` against the stored row. If all three match
the file is unchanged; the `scan_generation` counter is bumped and the row is
left alone.

### Tier 2 — racy-mtime escalation

A file whose `mtime_ns` changed within the last two seconds of the scan start is
considered **racy** (`indexer/fingerprint.py: is_racy()`). Racy files are
re-hashed with `xxh3_partial` (first + last 64 KB) and the result is compared to
the stored `xxh3_partial`. A mismatch enqueues a repair.

### Tier 3 — OSHash rename detection

When a file disappears on disk but a file with the same `oshash` appears at a
new path, the indexer applies a rename rather than a delete+insert. This
preserves the `media_item` row and all linked metadata.

### OSHash collision handling

If two distinct physical files hash to the same `oshash`, the indexer escalates
to `xxh3_full` (full file content) to disambiguate. Both files are kept with
distinct `media_file` rows; the collision is logged as
`indexer.drift.oshash_collision` at WARNING level.

### N-strikes soft-delete policy

A file that is not found on disk across **N consecutive scan generations** (N is
configurable via `indexer.json5: drift.miss_strikes_threshold`, default 3)
receives a soft-delete tombstone (`deleted_at` set, `deleted_item` row inserted).
The `media_item` and `media_release` rows are **never automatically deleted**;
only `media_file` rows are soft-deleted. A human-readable `reason` is stored in
`deleted_item.reason`.

### Repair queue

Any tier-2 mismatch, rename ambiguity, or manual `library verify` finding is
inserted into `repair_queue`. The repair worker (`indexer/repair.py:
drain(conn, budget_seconds)`) processes rows oldest-first within a configurable
time budget. Items in the queue that have not been processed in 7 days trigger a
WARN exit from `library status`.

---

## Scan Modes

The scanner (`personalscraper/indexer/scanner/`) supports four production modes
plus two utility modes. The mode is chosen with `--mode` on the CLI or via
`indexer.json5: scan.default_mode`.

| Mode          | What it reads                                                       | Typical use                                      |
| ------------- | ------------------------------------------------------------------- | ------------------------------------------------ |
| `quick`       | Only directories whose `dir_mtime_ns` changed since last walk.      | Nightly nightly — fastest; O(changed dirs).      |
| `incremental` | All directories; stat every file; skip content-hash unless racy.    | Weekly maintenance; catches slow drift.          |
| `enrich`      | Only files where `enriched_at IS NULL` or `enriched_at` is stale.   | Back-fill mediainfo + NFO + artwork after add.   |
| `full`        | Every file on every disk, regardless of cached mtimes.              | Cold rebuild; after disk replacement.            |
| `verify`      | Re-stat every file; escalate to tier-2 on mismatch; no soft-delete. | On-demand quality gate (wraps `library verify`). |
| `repair`      | Only `repair_queue` rows with status `'pending'`.                   | Internal; driven by `library repair`.            |

`--disk LABEL` narrows any mode to a single disk and forces `max_workers=1` to
prevent accidental parallel I/O on the USB hub.

`--budget SECONDS` caps wall-clock time; when exhausted the scanner writes a
checkpoint and exits cleanly. The next invocation resumes from the checkpoint.

---

## Query Language

`personalscraper library search QUERY` delegates to `indexer/query.py: execute()`.

### Token syntax

| Form                              | Meaning                                         |
| --------------------------------- | ----------------------------------------------- |
| `field:value`                     | Equality (or LIKE for `title`).                 |
| `field:value*`                    | Prefix match (`LIKE 'value%'`).                 |
| `-field:value`                    | Negation of the above.                          |
| `field:>=N` / `<=N` / `>N` / `<N` | Numeric comparison (INT fields only).           |
| `"quoted phrase"`                 | Bare title fragment, exact LIKE (no auto-`%`).  |
| `bare term`                       | Title fragment, auto-wrapped with `%` for LIKE. |
| `-bare_key`                       | Flex-attr presence negation.                    |

Multiple tokens are combined with `AND`.

### Field registry

| Field      | Maps to                                | Operators                                  |
| ---------- | -------------------------------------- | ------------------------------------------ |
| `kind`     | `media_item.kind`                      | equality                                   |
| `title`    | `media_item.title` (LIKE)              | equality, prefix                           |
| `year`     | `media_item.year`                      | equality, comparison                       |
| `disk`     | JOIN `disk.label`                      | equality                                   |
| `category` | `media_item.category_id`               | equality                                   |
| `tmdb_id`  | `media_item.tmdb_id`                   | equality, comparison                       |
| `imdb_id`  | `media_item.imdb_id`                   | equality                                   |
| `nfo`      | `media_item.nfo_status`                | equality (`missing` / `invalid` / `valid`) |
| `codec`    | EXISTS on `media_stream.codec` (video) | equality                                   |
| `lang`     | EXISTS on `media_stream.lang` (audio)  | equality                                   |
| `quality`  | EXISTS on `media_release.quality`      | equality                                   |
| any other  | Flex attr `item_attribute(key, value)` | equality, presence                         |

### Examples

```bash
# TV shows on Disk2 without a valid NFO
personalscraper library search "kind:show disk:Disk2 -nfo:valid"

# Movies from 2024 missing a trailer
personalscraper library search "kind:movie year:2024 -trailer_found"

# All HEVC files
personalscraper library search "codec:hevc"

# Title fragment (case-insensitive)
personalscraper library search "Lost Highway"

# Unknown field → treated as flex attr
personalscraper library search "plex_watched:true"
```

`QueryError` is raised (exit 2) for unknown _native_ fields used with comparison
operators, for `nfo` values outside `{missing, invalid, valid}`, and for syntax
errors such as unclosed quotes.

---

## Cold-Rebuild Playbook

Use this procedure after a disk replacement, after `library.db` corruption, or
after an unclean unmount that left the index inconsistent.

### Full fresh rebuild (all disks)

```bash
# 1. Quarantine the corrupt database (if any)
mv .personalscraper/library.db .personalscraper/library.db.bak

# 2. Run a full scan — rebuilds from scratch
personalscraper library-index --mode full

# 3. Verify the result
personalscraper library-status
```

### Single-disk rebuild (--rebuild flag)

The `--rebuild` flag quarantines the existing database and runs a full Stage-A
rescan from scratch without requiring manual `mv`:

```bash
personalscraper library-index --rebuild
```

This is the recommended path after DB corruption detected by `library status`
(exit 1 with `IndexerCorruptError` in stderr).

### Per-disk rotation (avoiding USB saturation)

When only one disk needs rebuilding, scope the scan:

```bash
personalscraper library-index --mode full --disk Disk3
personalscraper library-status --disk Disk3
```

See `docs/reference/storage.md` §24 TB Operations Guide for estimated durations
and budget planning.

---

## Cron Setup (launchd)

Three plist templates are provided under `docs/reference/launchd/`. They are
**opt-in** — copy to `~/Library/LaunchAgents/` and bootstrap manually.

### Quick nightly scan (03:30 every day)

```bash
cp docs/reference/launchd/personalscraper-index-quick.plist \
   ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) \
   ~/Library/LaunchAgents/personalscraper-index-quick.plist
```

### Rotating full scan (Mon–Thu by disk)

```bash
cp docs/reference/launchd/personalscraper-index-rotate.plist \
   ~/Library/LaunchAgents/
cp docs/reference/launchd/index-rotate.sh ~/bin/   # or any dir on $PATH
chmod +x ~/bin/index-rotate.sh
launchctl bootstrap gui/$(id -u) \
   ~/Library/LaunchAgents/personalscraper-index-rotate.plist
```

The shell wrapper (`index-rotate.sh`) maps the weekday (`date +%u`) to a disk
label (Mon=Disk1, Tue=Disk2, Wed=Disk3, Thu=Disk4) and falls back to `--mode
quick` on Fri/Sat/Sun.

### Weekly enrich pass (Sunday 04:00)

```bash
cp docs/reference/launchd/personalscraper-index-enrich.plist \
   ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) \
   ~/Library/LaunchAgents/personalscraper-index-enrich.plist
```

### Uninstalling a job

```bash
launchctl bootout gui/$(id -u)/com.personalscraper.index-quick
```

---

## Failure Recovery

### Corrupted database

Symptom: `library status` or `library index` exits 1 with `IndexerCorruptError`
in stderr (`SQLITE_CORRUPT` or integrity-check failure).

Recovery:

```bash
personalscraper library-index --rebuild
```

The `--rebuild` flag renames the existing DB to
`<db_path>.corrupt-<unix_ts>` (default `.personalscraper/library.db.corrupt-<unix_ts>`)
and runs a full Stage-A rescan from scratch.

### Stale lock

Symptom: `library index` exits 1 with `"indexer locked by PID <n>"` and the PID
does not exist in the process table.

Recovery:

```bash
# Manually remove the stale lock file
rm .personalscraper/library.lock
personalscraper library-index
```

The lock file path is `indexer.lock_path` (default `.personalscraper/library.lock`).

### Partial migration recovery

Symptom: `library status` or `library index` exits 1 with
`IndexerMigrationError`; schema version is behind the expected version.

Recovery:

```bash
# Re-run migrations (idempotent — already-applied migrations are skipped)
personalscraper library-index --mode quick
```

If the schema is corrupt beyond migration recovery, use `--rebuild`.

### Disk-swap edge case (Merkle-delta freeze)

When a disk is swapped and the Merkle root delta exceeds the configured threshold,
the scanner freezes drift processing to prevent mass false-deletes. Bypass for a
single invocation:

```bash
personalscraper library-index --mode full --disk Disk2 --confirm-bulk-change
```

---

## CLI Reference Summary

Full option documentation is in `docs/reference/commands.md`.

| Command                                            | Exit codes               | Notes                                     |
| -------------------------------------------------- | ------------------------ | ----------------------------------------- |
| `library index [--mode M] [--disk D] [--budget S]` | 0 ok / 1 err / 2 bad arg | Main scan command.                        |
| `library index --dry-run`                          | 0                        | Suppresses all media\_\* mutations.       |
| `library index --rebuild`                          | 0 ok / 1 err             | Quarantines old DB, fresh Stage-A scan.   |
| `library index --confirm-bulk-change`              | 0 ok / 1 err             | Bypasses Merkle-delta freeze.             |
| `library status`                                   | 0 healthy / 1 warn       | WARN on old/deep repair queue or orphans. |
| `library verify [--disk D]`                        | 0 ok / 1 err             | No soft-deletes; marks for repair only.   |
| `library search QUERY [--limit N]`                 | 0 ok / 2 bad query       | Uses flex-attr parser.                    |
| `library repair [--budget S]`                      | 0 ok / 1 err             | Drains repair queue within budget.        |
| `library show ITEM_ID`                             | 0 ok / 2 not found       | Pretty-prints all stored data.            |
| `config migrate-category --from OLD --to NEW`      | 0 ok / 2 unknown NEW     | Rewrites category_id in bulk.             |
| `config migrate-to-v2 [--dry-run]`                 | 0 ok / 2 err             | One-shot v1 → v2 config migration.        |
