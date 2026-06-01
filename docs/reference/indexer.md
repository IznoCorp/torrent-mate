# Indexer Reference

The media indexer (`personalscraper/indexer/`) is a SQLite-backed subsystem that
maintains a single queryable mirror of the configured storage disks.

Cross-references: DESIGN §6, §8, §11, §12, §13, §14, §17.

---

## Schema Overview

The database lives at `paths.data_dir / "library.db"` by default (configurable
via `indexer.db_path` in `config/indexer.json5`; WAL mode; must reside on any
WAL-safe filesystem — i.e. not NTFS-via-macFUSE and not an `unknown`-typed
volume — which includes an APFS volume mounted under `/Volumes/`. The
`db_path` validator rejects only WAL-unsafe filesystem types, not a bare
`/Volumes/` prefix).
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

> **Filesystem-aware tier-1 (v0.18.0+):** the tier-1 comparison is
> capability-gated. The scan orchestrator (`scanner/_scan_orchestrator.py`)
> resolves the disk's `FilesystemCapability` once per disk via the shared
> `resolve_capability(path, override)` resolver — the **same** resolver the
> transfer layer uses, so scan and dispatch never diverge — and threads it down
> into the scan modes. The live modes `scanner/_modes/incremental.py` and
> `scanner/_modes/quick.py` consume `fingerprint.normalize_tier1` /
> `round_mtime_ns` for the **per-file** compare, and the **gating** layer (the
> Merkle root short-circuit, the `compute_merkle_delta` bulk-change freeze
> guard, and the dir-mtime subtree skip) buckets mtime per the disk capability
> too — via `_walker.py`'s `_build_disk_fingerprints` / `_sample_fresh_fingerprints`
> and the dir-mtime compares. The **other** Merkle-root consumers bucket through
> the very same `_build_disk_fingerprints` helper so every stored vs computed
> comparison is consistent: `reconcile.detect_merkle_drift` (the
> `library-doctor` drift check) resolves the per-disk capability the same way
> the scanner does and is fed the operator override from the doctor caller, and
> `repair._refresh_disk_merkle` (the `library-repair` post-cascade rewrite)
> auto-detects the capability from the disk mount so the root it writes is the
> one the next scan recomputes. Coarse filesystems are therefore consistent
> end-to-end — store, short-circuit, drift check, and repair rewrite all bucket
> identically. On exFAT, ctime is dropped from the tuple and mtime is floored to
> a 2-second bucket; on HFS+, mtime is floored to a 1-second bucket; NTFS / APFS
> / ext4 keep the exact `(size, mtime_ns, ctime_ns)` 3-tuple unchanged
> (bucketing is the identity transform → byte-identical Merkle root). See
> [`docs/reference/storage.md`](storage.md) — "Filesystem capability layer" for
> the full table.

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

If two distinct physical files hash to the same `oshash`, both files are
kept with distinct `media_file` rows; the collision is logged as
`indexer.drift.oshash_collision` at WARNING level.

### N-strikes soft-delete policy

A file that is not found on disk across **N consecutive scan generations** (N is
configurable via `indexer.json5: scan.n_strikes_for_softdelete`, default 3)
receives a soft-delete tombstone (`deleted_at` set, `deleted_item` row inserted).
The `media_item` and `media_release` rows are **never automatically deleted**;
only `media_file` rows are soft-deleted. A human-readable `reason` is stored in
`deleted_item.reason`.

### Hard-delete exceptions (SH-4 audit — 2026-05-23)

The only two `DELETE FROM media_item` sites in production code are both justified:

1. **`item_repo.delete()`** — Test-only utility (zero production callers). Used
   exclusively by test fixtures that insert rows and must clean them up.
   `media_item` has no `deleted_at` column, so schema-level soft-delete is not
   available; adding it purely for tests would add unnecessary complexity.

2. **`item_repo.remove_by_id()`** — Called by `MediaIndex.rebuild()` and
   `MediaIndex.remove_stale()` in `dispatch/media_index.py`. These operate on
   **dispatch-attributed** rows that serve as a transient filesystem cache: they
   carry no independently scraped metadata (no seasons, no episodes, no NFO data)
   and are fully rebuilt by walking the disk. Hard-delete is correct because:
   - A clean-slate rebuild (`rebuild()`) requires removing stale entries completely,
     not tombstoning them — soft-deleted rows would still appear as candidates
     and require filtering in every dispatch lookup.
   - `ON DELETE CASCADE` propagates to `item_attribute` child rows automatically.

   Soft-delete would require a schema migration adding `deleted_at` to
   `media_item` **and** `AND deleted_at IS NULL` guards in every dispatch query,
   for no benefit on a cache rebuilt on demand from the filesystem.

### Repair queue

Any tier-2 mismatch, rename ambiguity, or manual `library verify` finding is
inserted into `repair_queue`. The repair worker (`indexer/repair.py:
drain(conn, budget_seconds)`) processes rows oldest-first within a configurable
time budget. Items in the queue that have not been processed in 7 days trigger a
WARN exit from `library status`.

---

## Scan Modes

The scanner (`personalscraper/indexer/scanner/`) supports four production modes
plus one utility mode. The mode is chosen with `--mode` on the CLI.

| Mode          | What it reads                                                       | Typical use                                      |
| ------------- | ------------------------------------------------------------------- | ------------------------------------------------ |
| `quick`       | Only directories whose `dir_mtime_ns` changed since last walk.      | Nightly nightly — fastest; O(changed dirs).      |
| `incremental` | All directories; stat every file; skip content-hash unless racy.    | Weekly maintenance; catches slow drift.          |
| `enrich`      | Only files where `enriched_at IS NULL` or `enriched_at` is stale.   | Back-fill mediainfo + NFO + artwork after add.   |
| `full`        | Every file on every disk, regardless of cached mtimes.              | Cold rebuild; after disk replacement.            |
| `verify`      | Re-stat every file; escalate to tier-2 on mismatch; no soft-delete. | On-demand quality gate (wraps `library verify`). |

`--disk LABEL` narrows any mode to a single disk and forces `max_workers=1` to
prevent accidental parallel I/O on the USB hub.

`--budget SECONDS` caps wall-clock time; when exhausted the scanner writes a
checkpoint and exits cleanly. The next invocation resumes from the checkpoint.

### Item stage (pass 1 of `ScanMode.full`)

`library-index --mode full` is a **two-pass, single-invocation** scan. Pass 1 is
the _item stage_ (`personalscraper/indexer/scanner/_modes/_item_stage.py`): a
directory-metadata pass that writes the rich `media_item` rows (title, canonical
provider, seasons/episodes, artwork inventory, `item_issue` flags) before any
file is walked. Pass 2 is the recursive file walk (`_walker.py`) that populates
`media_file` and `media_stream` rows. No prior `library-scan` is required — the
legacy two-step "scan then index" workflow was folded into this single mode in
0.19.0 (lib-fold).

| Public function                                                                                                                                    | Purpose                                                                                                                                                                                                                                   |
| -------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `build_item_row(*, title, kind, year, category_id, tvdb_id, tmdb_id, imdb_id=None, nfo_default=None, nfo_status, artwork_json="{}", ratings=None)` | Build a `media_item` **column dict** from parsed NFO inputs (provider IDs → `external_ids_json`); resolves `canonical_provider` via the kind-deterministic SSOT `_canonical.derive_canonical_provider`.                                   |
| `upsert_item_with_attrs(conn, row, attrs, issues=None, *, now_s=None)`                                                                             | Write `media_item` (via `item_repo.upsert`) + `item_attribute` + `item_issue` (each with `detected_at`) rows; idempotent on `(kind, title)` (the `item_repo.upsert` conflict key); replaces the whole issue set each scan.                |
| `scan_and_stage_dir(conn, media_dir, disk_cfg, category_id, kind, now_s=None)`                                                                     | High-level: parse the dir name, resolve the NFO, detect hygiene issues, build the row, upsert. No-NFO dirs are still indexed (folder-name fallback) and flagged (`nfo_missing` / `nfo_incomplete` in `item_issue`).                       |
| `_ensure_disk_row(conn, disk_cfg, now_s) -> DiskRow`                                                                                               | DEV #50: SELECT-by-label, then insert the `disk` row if absent before any FK-bearing write (lives in `personalscraper/indexer/scanner/_modes/_item_stage.py` as `_ensure_disk_row`; ported from the legacy scanner in 0.19.0 / lib-fold). |

The library-wide pass-1 driver is `stage_library_items(conn, config, now_s=None)`,
which iterates disks × categories × media dirs and delegates each directory to
`scan_and_stage_dir`.

`dispatch/media_index.py` is the **single `media_item` creator** on the dispatch
side: both of its write paths share the `_item_stage` primitives, so dispatch
never re-introduces the prior `canonical_provider=None` degradation (the provider
is always derived deterministically from the on-disk NFO's provider IDs):

- `rebuild()` (empty-DB auto-rebuild) delegates each media dir to
  `scan_and_stage_dir` — the **full** stage (rich row + seasons + episodes +
  `item_issue`), byte-identical to `library-index --mode full`.
- `add()` (per-dispatch incremental, called from `dispatch/_movie.py` /
  `dispatch/_tv.py` on every move into permanent storage) builds the row via the
  shared `build_item_row` (+ `_nfo_metadata_for_dir`) — rich `canonical_provider`,
  no seasons/issues (those are added by the next `--mode full` walk) — plus the
  three `dispatch_*` flex attributes that trailers / `release_linker` join on.

---

## Query Language

`personalscraper library-search QUERY` delegates to `indexer/query.py: execute()`.

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
personalscraper library-search "kind:show disk:Disk2 -nfo:valid"

# Movies from 2024 missing a trailer
personalscraper library-search "kind:movie year:2024 -trailer_found"

# All HEVC files
personalscraper library-search "codec:hevc"

# Title fragment (case-insensitive)
personalscraper library-search "Lost Highway"

# Unknown field → treated as flex attr
personalscraper library-search "plex_watched:true"
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
#    (paths.data_dir defaults to .data/)
mv .data/library.db .data/library.db.bak

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

## State machine: media_file lifecycle

A `media_file` row transitions through 6 states from discovery to tombstoning.
Each transition is triggered by a specific scanner mode or maintenance command.

    discovered  (oshash=NULL, Stage A — created by walker on first sighting)
        |
        | enrich step computes oshash + extracts metadata
        v
    enriched    (oshash set, Stage B — full mediainfo + NFO + artwork available)
        |
        | release_linker matches file → media_release on oshash + provider IDs
        v
    linked      (release_id set; the file is bound to a known release)
        |
        | verify / full scan re-stats and bumps last_verified_at
        v
    verified    (last_verified_at = current scan epoch)
        |
        | (file disappears from FS, but oshash is still in BDD)
        v
    missed      (miss_strikes++ each scan where the file is not seen)
        |
        | after N strikes (default 3, configurable per-disk)
        v
    tombstoned  (deleted_at set; deleted_item row inserted; file row kept for audit)

Sites in code:

- `discovered` → `enriched` : `personalscraper/indexer/scanner/_modes/enrich.py`
- `enriched` → `linked` : `personalscraper/indexer/release_linker.py`
- `linked` → `verified` : `personalscraper/indexer/scanner/_walker.py` (mode=full)
- `verified` → `missed` : `personalscraper/indexer/drift.py::mark_missed_files`
- `missed` → `tombstoned` : `personalscraper/indexer/drift.py::apply_soft_deletes`

A `library-reconcile` run inspects the entire chain and flags inconsistencies
(e.g. a `linked` row whose `release_id` no longer exists in `media_release`).

The `media_file.miss_strikes` counter is a soft-delete guard: a single missed
scan must not tombstone, since macFUSE / NTFS can briefly hide files during a
remount or directory listing. The counter is reset to 0 the moment the file
is observed again.

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
`<db_path>.corrupt-<unix_ts>` (e.g. `library.db.corrupt-1714567890` inside the configured `data_dir`)
and runs a full Stage-A rescan from scratch.

### Stale lock

Symptom: `library index` exits 1 with `"indexer locked by PID <n>"` and the PID
does not exist in the process table.

Recovery:

```bash
# Manually remove the stale SQLite lock file (resides next to library.db)
rm .data/library.db.lock
personalscraper library-index
```

The lock file path is derived from the database path as `<indexer.db_path>.lock`
(default `.data/library.db.lock`); it is not separately configurable.

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

## Registry integration

The indexer's `backfill_ids` driver is the indexer's main consumer of the
`ProviderRegistry`. Since 0.16.0 Phase 11 the driver receives a
`ProviderRegistry` instance directly — it no longer extracts typed
`TMDBClient` / `TVDBClient` / `OmdbClient` instances via `try/except
UnknownProviderError`.

### What `backfill_ids` does with the registry

`personalscraper/indexer/backfill_ids.py` resolves two distinct needs through
two distinct registry operations:

1. **Ratings aggregation — `ProviderRegistry.fan_out(RatingProvider)`**

   Every rating-capable provider contributes its own notations (e.g. IMDb +
   OMDb + RottenTomatoes), so the only correct semantic is `fan_out`. The
   driver iterates `registry.fan_out(RatingProvider).values`, filters by
   `gap.missing_rating_sources` (skip providers whose source the row already
   has), and serialises each provider call into the
   `media_item.ratings_json` payload (`backfill_ids.py:625`).

2. **Canonical details lookup — `ProviderRegistry.chain(MovieDetailsProvider |
TvDetailsProvider)`**

   When the row is missing the canonical id for a media type, the driver
   iterates the appropriate chain capability and filters to the canonical
   provider name (TVDB for shows, TMDB for movies). This preserves the
   per-family canonical-source invariant while still benefiting from the
   chain's circuit-eligibility filtering and fallback-event emission
   (`backfill_ids.py:453` and `:456`).

### CLI wiring

`personalscraper library backfill-ids` (driver in
`personalscraper/indexer/scanner/_modes/backfill_ids.py`) constructs its
runtime context from `AppContext.provider_registry` and passes the
`ProviderRegistry` to `run_backfill_ids()`. The old code path that extracted
typed clients via `registry.get("tmdb")` + `isinstance(..., TMDBClient)`
checks has been removed — the registry is the only consumer-visible
metadata-dispatch entry point.

### Failure semantics

- `fan_out` returns an empty `FanOutResult.values` when every rating provider
  is circuit-OPEN — this is treated as **partial success** (no error,
  `attempted` carries the `circuit_open` reasons for telemetry). The
  registry's `RegistryFanOutCompleted` event fires unconditionally.
- `chain` raises `ProviderExhausted` when every chain provider failed for a
  classified reason (`circuit_open` / `network`). The driver catches this
  and records the row as a partial backfill, preserving the
  `last_exception` message in the audit trail.
- Per-call `CircuitOpenError` raised between the `fan_out` eligibility check
  and the actual provider call is caught locally and treated as an empty
  contribution — see `_call_rating_provider` in `backfill_ids.py:635`.

### See also

- `docs/reference/scraping.md#capability-cookbook` — Examples 2 and 3 give
  minimal snippets of the `chain(MovieDetailsProvider)` and
  `fan_out(RatingProvider)` shapes used here.
- `docs/reference/external-ids-flow.md` — cross-provider id flow at the
  pipeline level (the source of truth for which provider is canonical per
  media type).
- `docs/reference/architecture.md#provider-registry` — registry module
  layout and boot sequence.

---

## CLI Reference Summary

Full option documentation is in `docs/reference/commands.md`.

| Command                                             | Exit codes                                      | Notes                                     |
| --------------------------------------------------- | ----------------------------------------------- | ----------------------------------------- |
| `library index [--mode M] [--disk D] [--budget S]`  | 0 ok / 1 err / 2 bad arg / 3 bulk change frozen | Main scan command.                        |
| `library index --dry-run`                           | 0                                               | Suppresses all media\_\* mutations.       |
| `library index --rebuild`                           | 0 ok / 1 err                                    | Quarantines old DB, fresh Stage-A scan.   |
| `library index --confirm-bulk-change`               | 0 ok / 1 err                                    | Bypasses Merkle-delta freeze.             |
| `library status`                                    | 0 healthy / 1 warn                              | WARN on old/deep repair queue or orphans. |
| `library verify [--disk D]`                         | 0 ok / 1 err / 2 unknown disk                   | No soft-deletes; marks for repair only.   |
| `library search QUERY [--limit N]`                  | 0 ok / 2 bad query                              | Uses flex-attr parser.                    |
| `library repair [--budget S]`                       | 0 ok / 1 err                                    | Drains repair queue within budget.        |
| `library reconcile [--scope S] [--enqueue-repairs]` | 0 ok / 1 err                                    | DB-only divergence detection.             |
| `library show ITEM_ID`                              | 0 ok / 2 not found                              | Pretty-prints all stored data.            |
| `config migrate-category --from OLD --to NEW`       | 0 ok / 2 unknown NEW                            | Rewrites category_id in bulk.             |
