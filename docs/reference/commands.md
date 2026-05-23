# Commands Reference

Complete CLI reference for `personalscraper`. Each section documents one
command: its purpose, side effects, arguments, examples, and the commands it
relates to. The canonical source for flag names is `personalscraper <cmd>
--help`; this document supersedes the legacy cheat-sheet style.

**Global flags** (apply to every command):

- `--verbose / -v` — enable DEBUG logging
- `--quiet / -q` — suppress console output
- `--version` — print version and exit
- `--config / -c PATH` — override config directory (must precede the subcommand)
- `--format / -f rich|plain|json` — output format (default: `rich`) — see DEV #22 / SH-13

**Side-effect taxonomy**:

- `read-only` — touches nothing on disk or in the database
- `mutate FS` — modifies files / directories under staging or storage
- `mutate BDD` — writes to the indexer SQLite DB (`.data/library.db`)
- `network` — calls external APIs (TMDB / TVDB / qBittorrent / Telegram / ...)

## Table of contents

### Pipeline (steps 1–9)

1. [`ingest`](#personalscraper-ingest) — copy completed torrents into staging
2. [`sort`](#personalscraper-sort) — sort media into category folders, clean filenames
3. [`cleanup`](#personalscraper-cleanup) — pipeline-internal: remove empty dirs + junk after scrape
4. [`scrape`](#personalscraper-scrape) — fetch metadata + artwork from TMDB/TVDB
5. [`enforce`](#personalscraper-enforce) — sanitize filenames, validate structure
6. [`verify`](#personalscraper-verify) — quality gate before dispatch
7. [`dispatch`](#personalscraper-dispatch) — move media to storage disks
8. [`process`](#personalscraper-process) — composite: reclean + dedup + scrape + cleanup
9. [`run`](#personalscraper-run) — full pipeline (ingest → dispatch)

### Meta / system

10. [`info`](#personalscraper-info) — version, config paths, disk status
11. [`init-config`](#personalscraper-init-config) — bootstrap config/ from template
12. [`torrents-list`](#personalscraper-torrents-list) — list completed torrents
13. [`config`](#personalscraper-config) — configuration management (parent command)

### Library — indexer & maintenance (→ 6.2.b)

14. [`library-index`](#personalscraper-library-index) — scan disks into the indexer DB
15. [`library-scan`](#personalscraper-library-scan) — NFO-based row creation
16. [`library-init-canonical`](#personalscraper-library-init-canonical) — bootstrap canonical_provider from NFOs
17. [`library-status`](#personalscraper-library-status) — latest scan run summary
18. [`library-verify`](#personalscraper-library-verify) — re-stat indexed files, enqueue mismatches
19. [`library-repair`](#personalscraper-library-repair) — drain repair queue within budget
20. [`library-reconcile`](#personalscraper-library-reconcile) — detect index ↔ FS divergences
21. [`library-ghost-audit`](#personalscraper-library-ghost-audit) — audit NTFS ghost dirents
22. [`library-relink`](#personalscraper-library-relink) — relink NULL release_id rows
23. [`library-clean`](#personalscraper-library-clean) — remove .actors/, junk files on storage disks
24. [`library-validate`](#personalscraper-library-validate) — validate NFO/artwork/naming conformity
25. [`library-gc`](#personalscraper-library-gc) — GC old index_outbox done rows

### Library — analysis (→ 6.2.c)

26. `library-analyze` — deep ffprobe scan
27. `library-recommend` — re-download recommendations
28. `library-rescrape` — targeted re-scraping
29. `library-report` — health statistics
30. `library-search` — flex-attr query
31. `library-show` — pretty-print one item
32. `library-doctor` — health checks on live DB
33. `library-backfill-ids` — backfill provider IDs across releases

### Trailers (→ 6.2.c)

34. `trailers scan` — discover media missing trailers
35. `trailers download` — download trailers from YouTube
36. `trailers verify` — audit trailer files on disk
37. `trailers purge` — remove unwanted trailers

### Config subcommands (→ 6.2.c)

38. `config migrate-category` — rename a category across config + paths

### Make targets + scheduling (appendix)

39. `make` targets — test, lint, format, install-dev
40. launchd scheduling — plist install / load / unload

> **Note**: Entries 26–40 are placeholders. Full content will be added by
> dispatch 6.2.c (analysis + trailers + config subcommands).

---

## `personalscraper ingest`

**Purpose**: Copies completed torrents from qBittorrent into the staging area.
Each torrent's content is copied (not moved) into a flat directory under the
staging root, preserving the source folder name. Already-ingested torrents are
tracked in `ingested_torrents.json` and skipped on subsequent runs.

**Side effects**: `mutate FS` (writes to staging), `network` (qBittorrent API)

**Pipeline position**: step 1

**Args**:

- `--dry-run` : preview without copying — lists what would be ingested

**Examples**:

    personalscraper ingest
    personalscraper ingest --dry-run

**Related**: `torrents-list`, `run`

---

## `personalscraper sort`

**Purpose**: Sorts media files from the flat ingest directory into category
folders under staging (e.g. `001-MOVIES/`, `002-TVSHOWS/`). Identifies each
item's type (movie vs TV show) using folder-name heuristics and the configured
`staging_dirs` mapping in `config/patterns.json5`, then moves files into the
correct category subdirectory. Also performs initial filename sanitization.

**Side effects**: `mutate FS` (reorganizes staging directory)

**Pipeline position**: step 2

**Args**:

- `--dry-run` : preview without moving

**Examples**:

    personalscraper sort
    personalscraper sort --dry-run

**Related**: `ingest`, `enforce`, `run`

---

## `personalscraper cleanup`

**Purpose**: Removes empty directories and residual junk files left behind after
the scrape step completes. This is a pipeline-internal step — it is **not**
invocable as a standalone CLI command. It runs automatically as part of
`process` (after scrape) and `run` (between scrape and enforce).

**Side effects**: `mutate FS` (deletes empty dirs, `.actors/` folders, and
transient files under each media item's directory)

**Pipeline position**: step 4 (internal only — runs after scrape, before enforce)

**Args**: none (not a standalone command)

**Examples**:

    # cleanup runs automatically inside these commands:
    personalscraper process
    personalscraper run

**Related**: `process`, `run`

---

## `personalscraper scrape`

**Purpose**: Fetches metadata (title, year, genres, cast, ratings, artwork URLs)
and downloads artwork (poster, fanart, landscape, logo, etc.) from TMDB and
TVDB for each media item in staging. Writes `.nfo` files (Kodi-compatible XML)
and downloads artwork into each item's folder. Supports interactive mode for
ambiguous matches.

**Side effects**: `mutate FS` (writes NFO + artwork files), `network` (TMDB / TVDB APIs)

**Pipeline position**: step 3

**Args**:

- `--dry-run` : preview without writing
- `--interactive / -i` : prompt for ambiguous matches
- `--movies-only` : process only movies
- `--tvshows-only` : process only TV shows

**Examples**:

    personalscraper scrape
    personalscraper scrape --interactive
    personalscraper scrape --movies-only --dry-run
    personalscraper scrape --tvshows-only

**Related**: `enforce`, `verify`, `process`, `run`

---

## `personalscraper enforce`

**Purpose**: Enforces staging conventions on media items before scrape. Sanitizes
filenames (removes special characters, normalizes spacing), validates directory
structure, and checks naming coherence against expected patterns. The
`.DS_Store` cleanup performed by this step is **per-item only** (only within the
folder being enforced), not disk-wide — use `library-clean` for whole-disk
sweeps.

**Side effects**: `mutate FS` (renames files/folders, deletes `.DS_Store` per-item)

**Pipeline position**: step 5

**Args**:

- `--dry-run` : preview without modifying

**Examples**:

    personalscraper enforce
    personalscraper enforce --dry-run

**Related**: `sort`, `scrape`, `verify`, `run`

---

## `personalscraper verify`

**Purpose**: Quality gate before dispatch. Verifies that every scraped item in
staging has valid NFO files, required artwork (poster + landscape minimum), and
correct folder naming. Reports errors and warnings for items that fail
validation. Use `--movies-only` or `--tvshows-only` to scope the check.

**Side effects**: `read-only` (inspects files, does not modify)

**Pipeline position**: step 6

**Args**:

- `--dry-run` : preview without modifying files
- `--movies-only` : process only movies
- `--tvshows-only` : process only TV shows

**Examples**:

    personalscraper verify
    personalscraper verify --dry-run
    personalscraper verify --movies-only

**Related**: `scrape`, `enforce`, `dispatch`, `run`

---

## `personalscraper dispatch`

**Purpose**: Moves verified media from staging to permanent storage disks.
Selects the target disk based on free space (new items go to the disk with the
most available space). Movies replace any existing folder with the same name;
TV shows merge new episode files into the existing folder. After dispatch, the
staging directory for that item is removed.

**Side effects**: `mutate FS` (moves media to storage, deletes from staging)

**Pipeline position**: step 7

**Args**:

- `--dry-run` : preview without moving

**Examples**:

    personalscraper dispatch
    personalscraper dispatch --dry-run

**Related**: `verify`, `process`, `run`

---

## `personalscraper process`

**Purpose**: Composite command that runs the processing phase end-to-end:
reclean (re-sanitize filenames), dedup (remove duplicate files), scrape
(metadata + artwork from TMDB/TVDB), and cleanup (remove empty dirs and
residual junk). Equivalent to running those steps individually but as a single
operation. Supports `--interactive` for ambiguous scrape matches.

**Side effects**: `mutate FS` (writes NFO + artwork, cleans junk), `network` (TMDB / TVDB APIs)

**Pipeline position**: composite (covers steps 3–4 equivalent)

**Args**:

- `--dry-run` : preview without modifying
- `--interactive / -i` : prompt for ambiguous matches

**Examples**:

    personalscraper process
    personalscraper process --dry-run
    personalscraper process --interactive

**Related**: `scrape`, `cleanup`, `enforce`, `run`

---

## `personalscraper run`

**Purpose**: Runs the full pipeline from start to finish: ingest → sort → clean
→ scrape → cleanup → enforce → verify → trailers → dispatch. This is the main
orchestration command for unattended/automated runs (e.g. via launchd). Each
step reports its own summary, and the pipeline stops on the first fatal error
unless `--continue-on-trailer-error` is set (for trailer-specific failures).

**Side effects**: `mutate FS` (all staging + storage operations), `mutate BDD`
(indexer updates during scan), `network` (qBittorrent, TMDB, TVDB, YouTube,
Telegram)

**Pipeline position**: n/a (runs all steps 1–9)

**Args**:

- `--dry-run` : preview full pipeline without modifying anything
- `--interactive / -i` : prompt for ambiguous scrape matches
- `--skip-trailers` : skip the trailers pipeline step for this invocation
- `--continue-on-trailer-error` : do not abort dispatch when the trailers step crashes
- `--headless` : run with no subscribers (silent mode for cron / CI) — disables Rich console output and Telegram notifications

**Examples**:

    personalscraper run
    personalscraper run --dry-run
    personalscraper run --skip-trailers
    personalscraper run --continue-on-trailer-error
    personalscraper run --headless

**Related**: `ingest`, `sort`, `scrape`, `enforce`, `verify`, `dispatch`, `process`

---

## `personalscraper info`

**Purpose**: Displays version information, config directory paths, and disk
status (mounted volumes, free space, total capacity). Respects the global
`--format` flag: `rich` (default, with colors and tables), `plain`
(human-readable text), or `json` (machine-parseable).

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**: none beyond global flags

**Examples**:

    personalscraper info
    personalscraper --format json info

**Related**: `init-config`, `config`

---

## `personalscraper init-config`

**Purpose**: Creates a `config/` directory from the `config.example/` template
shipped with the package. In interactive mode (default), prompts for key values
like API keys and paths. Use `--yes` to skip prompts and accept all defaults.
Use `--dry-run` to preview the operation without writing any files.

**Side effects**: `mutate FS` (creates config directory and files)

**Pipeline position**: n/a

**Args**:

- `--example PATH` : path to the example template directory (default: `config.example`)
- `--output PATH` : destination path for the new config directory (default: `config`)
- `--yes` : skip interactive prompts, accept all defaults
- `--force` : overwrite output directory if it already exists (backs up to `.bak`)
- `--dry-run` : preview what would be created without writing

**Examples**:

    personalscraper init-config
    personalscraper init-config --yes
    personalscraper init-config --output /custom/path/config --force
    personalscraper init-config --dry-run

**Related**: `info`, `config`

---

## `personalscraper torrents-list`

**Purpose**: Lists completed torrents from the configured qBittorrent client.
Prints one line per torrent (state, progress, size, seeding status, name) and a
summary count at the end. Exits with code 2 when the torrent client is
unreachable (auth lockout, IP ban, daemon down), allowing monitoring tools to
branch on the exit code. Used by the `pipeline-monitor` skill's GATE 0
inventory check.

**Side effects**: `network` (qBittorrent API)

**Pipeline position**: n/a

**Args**: none beyond global flags

**Examples**:

    personalscraper torrents-list

**Related**: `ingest`, `info`

---

## `personalscraper config`

**Purpose**: Parent command for configuration management subcommands. Does
nothing on its own — run `personalscraper config --help` to list available
subcommands. Currently the only subcommand is `migrate-category`, which renames
a category ID across config files and on-disk paths.

**Side effects**: none (delegates to subcommands)

**Pipeline position**: n/a

**Args**: none beyond global flags (subcommands have their own flags)

**Examples**:

    personalscraper config --help
    personalscraper config migrate-category --from OLD --to NEW

**Related**: `init-config`, `info`

---

## Library — indexer & maintenance

## `personalscraper library-index`

**Purpose**: Runs a full or quick media indexer scan. Walks all configured storage
disks (or a single disk with `--disk`), records every file in the indexer
database, and prints a JSON summary. Supports multiple scan modes: `full`
(complete re-index with file hashing), `quick` (fast Merkle + dir-mtime
short-circuit), `incremental` (only new or modified files), and `enrich`
(metadata enrichment from NFOs, artwork, and media streams).

**Side effects**: `mutate BDD` (writes media_file, path, scan_run, scan_event rows)

**Pipeline position**: n/a (indexer maintenance, runs independently from the pipeline)

**Args**:

- `--mode TEXT` : Scan mode: `full`, `quick`, `incremental`, or `enrich` [default: full]
- `--disk TEXT` : Restrict scan to this disk label
- `--budget INTEGER` : Budget in seconds (overrides config)
- `--no-budget` : Disable the wall-clock budget for this run. Use for manual full enrich passes that must drain every pending file.
- `--backfill-streams` : Enrich-only: target already-enriched files whose media_stream rows are missing migration-004 columns (hdr_format / is_atmos / is_default / forced / format) and UPDATE only those columns in place. Much faster than re-running the full enrich.
- `--dry-run` : Simulate scan without persisting any DB rows
- `--wait-for-lock INTEGER` : Seconds to wait for the writer lock [default: 0]
- `--confirm-bulk-change` : Bypass bulk-restore freeze guard (use after `--mode quick` reports a high Merkle delta)
- `--rebuild` : Quarantine corrupt DB and create a fresh one, then run full Stage-A scan

**Examples**:

    personalscraper library-index
    personalscraper library-index --mode quick
    personalscraper library-index --disk MyDisk --mode full
    personalscraper library-index --dry-run --mode full
    personalscraper library-index --mode quick --confirm-bulk-change
    personalscraper library-index --rebuild

**Related**: `library-scan`, `library-status`, `library-reconcile`

---

## `personalscraper library-scan`

**Purpose**: Scans media directories on disks and creates `media_item` rows from
NFO files. Walks all configured storage disks (or a single disk with `--disk`),
scans movie / TV show directories, reads NFO files, and writes `media_item`,
`season`, `episode`, and `item_attribute` rows to the indexer DB. Delegates
file-level indexing to the underlying indexer scanner so `media_file` / `path`
rows are also populated.

**Side effects**: `mutate BDD` (writes media_item, season, episode, item_attribute, media_file, path rows)

**Pipeline position**: n/a (NFO-based DB population, runs independently)

**Args**:

- `--disk / -d TEXT` : Restrict scan to this disk label
- `--mode TEXT` : Scan mode (currently only `full` is supported) [default: full]
- `--dry-run` : Count media dirs without writing to DB

**Examples**:

    personalscraper library-scan
    personalscraper library-scan --disk disk_1
    personalscraper library-scan --dry-run
    personalscraper library-scan --disk disk_1 --dry-run

**Related**: `library-index`, `library-reconcile`

---

## `personalscraper library-init-canonical`

**Purpose**: Bootstraps the `canonical_provider` column on library items from their
NFO files. Walks every `media_item` row where `canonical_provider IS NULL`,
resolves its NFO via the `dispatch_path` attribute, and reads the
`<uniqueid default="true">` element's `type` attribute. When found, sets
`canonical_provider` accordingly so that a subsequent
`library-index --mode enrich` can use it as the anchor for cross-provider ID
and rating enrichment.

This is the bootstrap step for databases that pre-date the provider-ids feature
(DEV #54): the enrich pass requires `canonical_provider` to be set, but nothing
populates it on a DB that was indexed before the scraper wrote the field. Items
without a `dispatch_path` attribute or without a readable NFO are silently
skipped — the pass is best-effort by design.

**Side effects**: `mutate BDD` (updates canonical_provider column on media_item rows)

**Pipeline position**: n/a (one-shot bootstrap — run once after upgrading from a pre-provider-ids version)

**Args**:

- `--dry-run` : Report counts without writing to DB

**Examples**:

    personalscraper library-init-canonical
    personalscraper library-init-canonical --dry-run

**Related**: `library-index --mode enrich`, `library-reconcile`

---

## `personalscraper library-status`

**Purpose**: Shows the latest completed indexer scan run summary. Queries the
indexer database for the most recently completed scan run and prints a one-line
summary with mode, generation, elapsed time, and file counts. Prints "no scans
yet" when the database has no completed scan runs. Output format respects the
global `--format` flag (`rich` for formatted table, `json` for machine-parseable
output).

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**: none beyond global flags

**Examples**:

    personalscraper library-status
    personalscraper --format json library-status
    personalscraper library-status --config /path/to/config.json5

**Related**: `library-index`, `library-reconcile`

---

## `personalscraper library-verify`

**Purpose**: Re-stats every indexed file and marks mismatches for repair. Runs a
verify-mode scan that re-checks every file's stat metadata `(size_bytes,
mtime_ns, ctime_ns)` against the stored snapshot. Files that no longer match
are escalated to the repair queue — they are NOT soft-deleted. Use this command
to identify drift before deciding whether to accept or revert changes.

With `--budget` the verify pass exits cleanly when the wall-clock limit is
reached; the next invocation continues from where it stopped (every file commits
`last_verified_at` individually so partial progress is preserved across runs).
With `--no-enqueue` the scan reports mismatches but does not insert any rows
into the repair queue (read-only audit mode).

**Side effects**: `mutate BDD` (updates last_verified_at, optionally writes repair_queue rows)

**Pipeline position**: n/a

**Args**:

- `--disk TEXT` : Restrict verification to this disk label
- `--budget INTEGER` : Wall-clock budget in seconds; partial verifies are safe to resume
- `--no-enqueue` : Read-only mode: walk and compare files but do NOT write to repair_queue

**Examples**:

    personalscraper library-verify
    personalscraper library-verify --disk Disk2
    personalscraper library-verify --budget 300
    personalscraper library-verify --no-enqueue

**Related**: `library-repair`, `library-reconcile`, `library-index`

---

## `personalscraper library-repair`

**Purpose**: Drains the repair queue within a time budget. Processes pending
repair rows in FIFO order, stopping cleanly when the budget is exhausted. Prints
a JSON summary of processed / succeeded / failed counts.

With `--dry-run` the command inspects the queue depth and reports what would be
drained without modifying any rows (no-op on the database).

**Side effects**: `mutate BDD` (processes repair_queue rows, updates media_file / path rows)

**Pipeline position**: n/a

**Args**:

- `--budget INTEGER` : Maximum seconds to spend draining the repair queue [default: 60]
- `--dry-run` : Preview mode: show how many repair_queue rows would be processed without actually draining them. No DB writes occur.

**Examples**:

    personalscraper library-repair
    personalscraper library-repair --budget 120
    personalscraper library-repair --dry-run

**Related**: `library-verify`, `library-reconcile`

---

## `personalscraper library-reconcile`

**Purpose**: Detects index ↔ filesystem divergences without a full rescan.
Read-only by default — runs DB-only checks across multiple detector scopes and
prints a JSON report of findings. Optionally enqueues each finding into
`repair_queue` so `library-repair` can fix them within a bounded budget (opt-in
via `--enqueue-repairs`).

Mode summary:

- Default (no flags) — read-only: report divergences, no writes.
- `--read-only` — explicit alias for the default read-only mode.
- `--dry-run` — alias for `--read-only` (same behaviour).
- `--enqueue-repairs` — opt-in write mode; pushes findings into `repair_queue`.

Detector scopes:

- `merkle` — disk Merkle drift between stored and computed roots.
- `dispatch_path` — items whose dispatch_path attribute is gone from FS.
- `enrich` — files whose enriched_at is older than mtime.
- `release` — orphan media_release rows + null-release files.
- `season` — denormalised season.episode_count drift.
- `item` — media_item rows with no file evidence.
- `path_missing` — path rows whose resolved absolute path no longer exists (mounted disks only).

**Side effects**: `read-only` (default), `mutate BDD` (with `--enqueue-repairs`)

**Pipeline position**: n/a

**Args**:

- `--scope TEXT` : Restrict to a detector scope (repeatable). Choices: `merkle`, `dispatch_path`, `enrich`, `release`, `season`, `item`, `path_missing`. Omit to run every detector.
- `--read-only` : Explicit read-only mode (default behaviour). Mutually exclusive with `--enqueue-repairs`.
- `--dry-run` : Alias for `--read-only`. Preview findings without enqueuing repairs.
- `--enqueue-repairs` : Opt-in: push every divergence into repair_queue. Mutually exclusive with `--read-only` / `--dry-run`.

**Examples**:

    personalscraper library-reconcile
    personalscraper library-reconcile --read-only
    personalscraper library-reconcile --dry-run
    personalscraper library-reconcile --scope enrich --scope release
    personalscraper library-reconcile --scope path_missing
    personalscraper library-reconcile --enqueue-repairs

**Related**: `library-verify`, `library-repair`, `library-index`

---

## `personalscraper library-ghost-audit`

**Purpose**: Audits storage disks for NTFS-via-macFUSE ghost directory entries.
Walks every directory on each storage disk and lists every entry that
`os.scandir` reports but `os.stat` cannot reach. These "ghost" entries are
produced by macFUSE-NTFS when the directory listing returns a filename in one
Unicode normalisation form (NFD) while the kernel inode is keyed under the
other (NFC). Once a ghost exists, the directory cannot be emptied — neither
`rm -rf` nor the project's own `_scandir_rmtree` walker can remove it.

The audit is read-only: it only reports the paths. Recovery requires unmounting
the affected NTFS volume and either running fsck on it or mounting it on a
Windows host that can repair the directory entry. Output: per-disk count and a
sample list of ghost paths.

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**:

- `--disk TEXT` : Audit only this disk (id from config)

**Examples**:

    personalscraper library-ghost-audit
    personalscraper library-ghost-audit --disk Disk1

**Related**: `library-clean`

---

## `personalscraper library-relink`

**Purpose**: Relinks `media_file` rows whose `release_id` is NULL. Walks every
`media_file` row with `release_id IS NULL AND deleted_at IS NULL` and replays
the release linker against the file's absolute path. The function resolves the
owning item via the same dispatch_path / title / title-year strategies the
enrich pass uses, so this is a self-healing recovery for files that were
inserted before their item was dispatched (cold Stage-A scan) or after a
release_linker bug left the link behind.

Output is the count of (linked, unmatched, errored) files. Default is dry-run;
use `--apply` to commit changes to the database.

**Side effects**: `read-only` (default), `mutate BDD` (with `--apply` — sets release_id on media_file rows)

**Pipeline position**: n/a

**Args**:

- `--apply` : Persist link updates (default: dry-run)
- `--dry-run` : Preview mode (explicit alias for the default behaviour). Report what would be linked without writing to the database. Mutually exclusive with `--apply`.

**Examples**:

    personalscraper library-relink
    personalscraper library-relink --dry-run
    personalscraper library-relink --apply

**Related**: `library-scan`, `library-reconcile`

---

## `personalscraper library-clean`

**Purpose**: Removes `.actors/` directories, empty dirs, and junk files from
storage disks. Dry-run by default — shows what would be deleted without
deleting. Use `--apply` to execute deletions. Use `--only` to target specific
cleanup types (`actors`, `empty`, `junk`, `release`, `orphans`).

The `orphans` mode targets stale release directories that no longer contain a
main video file — typically `.actors/` + trailer + NFO + artwork left behind
after a manual video delete. It is opt-in (never part of the default "all" run)
because the deletion granularity is the entire release directory.

**Side effects**: `read-only` (default), `mutate FS` (with `--apply`)

**Pipeline position**: n/a

**Args**:

- `--apply` : Actually delete (default: dry-run)
- `--dry-run` : Preview mode (explicit alias for the default behaviour). Show what would be deleted without deleting. Mutually exclusive with `--apply`.
- `--only TEXT` : Only clean: `actors`, `empty`, `junk`, `release`, `orphans`
- `--disk TEXT` : Clean only this disk (id from config)
- `--category TEXT` : Clean only this category

**Examples**:

    personalscraper library-clean
    personalscraper library-clean --dry-run
    personalscraper library-clean --apply
    personalscraper library-clean --apply --only actors
    personalscraper library-clean --only orphans                # dry-run
    personalscraper library-clean --only orphans --apply        # delete
    personalscraper library-clean --disk Disk1

**Related**: `library-ghost-audit`, `enforce`

---

## `personalscraper library-validate`

**Purpose**: Validates NFO, artwork, and naming conformity of library items on
storage disks. Checks each media item against quality rules: NFO presence and
validity, required artwork (poster + landscape minimum), folder naming
conventions, and structural integrity. Use `--fix --apply` to attempt automatic
corrections.

Use `--from-index` for a fast pre-screen that reads NFO + artwork status from
the indexer DB (NFO presence + poster/landscape only; no structural checks; no
`--fix` support). See the `validate_from_index` docstring for the full trade-off
list between filesystem and index-based validation.

**Side effects**: `read-only` (default), `mutate FS` (with `--fix --apply`)

**Pipeline position**: n/a

**Args**:

- `--disk TEXT` : Validate only this disk
- `--category TEXT` : Validate only this category
- `--fix` : Attempt automatic fixes
- `--apply` : Apply fixes (requires `--fix`)
- `--from-index` : Read NFO + artwork status from the indexer DB instead of walking the filesystem. Skips structural checks (empty dirs, NTFS chars, dir naming) and does not support `--fix`.

**Examples**:

    personalscraper library-validate
    personalscraper library-validate --disk Disk1
    personalscraper library-validate --fix --apply
    personalscraper library-validate --from-index

**Related**: `library-clean`, `enforce`, `verify`

---

## `personalscraper library-gc`

**Purpose**: Garbage-collects old `index_outbox` rows (status=done,
processed_at < cutoff). Removes stale `index_outbox` rows that have been fully
processed and whose `processed_at` timestamp is older than `--older-than-days`
days. These rows accumulate over time as the pipeline emits dispatch / scraper /
trailer events — without periodic GC the table grows without bound and degrades
query performance.

The cutoff is computed as `now() - older_than_days * 86400` seconds (UTC). Only
rows with `status='done'` are targeted — pending, failed, and deferred rows are
never touched.

With `--dry-run` the command counts matching rows and prints a JSON summary
without deleting anything. Without `--dry-run` the matching rows are hard-deleted
and the count is reported.

**Side effects**: `read-only` (with `--dry-run`), `mutate BDD` (default, hard-deletes index_outbox rows)

**Pipeline position**: n/a

**Args**:

- `--older-than-days INTEGER` : Delete `index_outbox` rows with status=done whose `processed_at` timestamp is older than this many days [default: 30]
- `--dry-run` : Preview mode: count how many rows would be deleted without actually deleting them. No DB writes occur.

**Examples**:

    personalscraper library-gc --dry-run
    personalscraper library-gc --older-than-days 7
    personalscraper library-gc

**Related**: `library-reconcile`, `library-repair`

---
