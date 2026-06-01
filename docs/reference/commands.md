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

### Pipeline (steps 1–9, in `DEFAULT_STEPS` execution order)

1. [`ingest`](#personalscraper-ingest) — copy completed torrents into staging
2. [`sort`](#personalscraper-sort) — sort media into category folders, clean filenames
3. [`clean`](#personalscraper-clean) — reclean folder names + fuzzy dedup
4. [`scrape`](#personalscraper-scrape) — fetch metadata + artwork from TMDB/TVDB
5. [`cleanup`](#personalscraper-cleanup) — remove empty dirs after scrape
6. [`enforce`](#personalscraper-enforce) — sanitize filenames, validate structure
7. [`verify`](#personalscraper-verify) — quality gate before dispatch
8. [`trailers`](#personalscraper-trailers) — download trailers (runs as a pipeline step; standalone surface = the `trailers` subcommands)
9. [`dispatch`](#personalscraper-dispatch) — move media to storage disks

### Composite / orchestration (not pipeline steps)

- [`process`](#personalscraper-process) — composite: clean + scrape + cleanup
- [`run`](#personalscraper-run) — full pipeline (ingest → … → dispatch)

### Meta / system

10. [`info`](#personalscraper-info) — version, config paths, disk status
11. [`init-config`](#personalscraper-init-config) — bootstrap config/ from template
12. [`torrents-list`](#personalscraper-torrents-list) — list completed torrents
13. [`config`](#personalscraper-config) — configuration management (parent command)

### Library — indexer & maintenance (→ 6.2.b)

14. [`library-index`](#personalscraper-library-index) — scan disks into the indexer DB
15. [`library-scan`](#personalscraper-library-scan) — visible alias of `library-index --mode full`
16. [`library-init-canonical`](#personalscraper-library-init-canonical) — bootstrap canonical_provider from NFOs
17. [`library-status`](#personalscraper-library-status) — latest scan run summary
18. [`library-verify`](#personalscraper-library-verify) — re-stat indexed files, enqueue mismatches
19. [`library-repair`](#personalscraper-library-repair) — drain repair queue within budget
20. [`library-reconcile`](#personalscraper-library-reconcile) — detect index ↔ FS divergences
21. [`library-ghost-audit`](#personalscraper-library-ghost-audit) — audit NTFS ghost dirents
22. [`library-relink`](#personalscraper-library-relink) — relink NULL release_id rows
23. [`library-clean`](#personalscraper-library-clean) — remove .actors/, junk files on storage disks
24. [`library-fix-canonical-provider`](#personalscraper-library-fix-canonical-provider) — repair `canonical_provider` drift in `media_item` rows (DEVIATION #7, ACC #4)
25. [`library-fix-nfo`](#personalscraper-library-fix-nfo) — repair malformed NFO files with trailing URLs
26. [`library-fix-orphan-files`](#personalscraper-library-fix-orphan-files) — repair `media_file` rows with `release_id IS NULL` (DEVIATION #8, invariant AO)
27. [`library-fix-season-counts`](#personalscraper-library-fix-season-counts) — repair `season.episode_count` drift (DEVIATION #9, invariant AP)
28. [`library-validate`](#personalscraper-library-validate) — validate NFO/artwork/naming conformity
29. [`library-gc`](#personalscraper-library-gc) — GC old index_outbox done rows

### Library — analysis & query

30. [`library-analyze`](#personalscraper-library-analyze) — deep ffprobe scan
31. [`library-recommend`](#personalscraper-library-recommend) — re-download recommendations
32. [`library-rescrape`](#personalscraper-library-rescrape) — targeted re-scraping
33. [`library-report`](#personalscraper-library-report) — health statistics
34. [`library-doctor`](#personalscraper-library-doctor) — health checks on live DB
35. [`library-search`](#personalscraper-library-search) — flex-attr query
36. [`library-show`](#personalscraper-library-show) — pretty-print one item
37. [`library-backfill-ids`](#personalscraper-library-backfill-ids) — backfill provider IDs across releases

### Trailers

38. [`trailers`](#personalscraper-trailers) — trailer management (parent command)
39. [`trailers scan`](#personalscraper-trailers-scan) — discover media missing trailers
40. [`trailers download`](#personalscraper-trailers-download) — download trailers from YouTube
41. [`trailers audit`](#personalscraper-trailers-audit) — audit trailer files on disk
42. [`trailers purge`](#personalscraper-trailers-purge) — remove unwanted trailers

### Config — sub-commands

43. [`config migrate-category`](#personalscraper-config-migrate-category) — rename a category across config + paths

### Make targets + scheduling (appendix)

- `make` targets — test, lint, format, install-dev
- launchd scheduling — plist install / load / unload

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

## `personalscraper clean`

**Purpose**: Re-cleans raw folder names (re-sanitize) and removes fuzzy duplicate
files in staging — the reclean + dedup sub-step of `process`. Useful for
debugging the clean pass in isolation or composing it into operator workflows.
The full pipeline still runs this internally via `process` / `run`.

**Side effects**: `mutate FS` (renames polluted folders, deletes fuzzy-duplicate files)

**Pipeline position**: step 3 (after sort, before scrape)

**Args**:

- `--dry-run` : preview without modifying

**Examples**:

    personalscraper clean
    personalscraper clean --dry-run

**Related**: `sort`, `cleanup`, `process`, `run`

---

## `personalscraper cleanup`

**Purpose**: Removes empty directories left behind by earlier steps — the
empty-directory cleanup sub-step of `process` (distinct from `clean`, which does
reclean + dedup). Invocable standalone for tidying staging between manual
operator interventions; the full pipeline also runs it internally via
`process` / `run`.

**Side effects**: `mutate FS` (removes empty directories)

**Pipeline position**: step 5 (after scrape, before enforce)

**Args**:

- `--dry-run` : preview without deleting

**Examples**:

    personalscraper cleanup
    personalscraper cleanup --dry-run

**Related**: `clean`, `scrape`, `process`, `run`

---

## `personalscraper scrape`

**Purpose**: Fetches metadata (title, year, genres, cast, ratings, artwork URLs)
and downloads artwork (poster, fanart, landscape, logo, etc.) from TMDB and
TVDB for each media item in staging. Writes `.nfo` files (Kodi-compatible XML)
and downloads artwork into each item's folder. Supports interactive mode for
ambiguous matches.

**Side effects**: `mutate FS` (writes NFO + artwork files), `network` (TMDB / TVDB APIs)

**Pipeline position**: step 4

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
`.DS_Store` cleanup performed by this step runs across **all items in staging
in a single recursive pass** over the staging category dirs — the boundary is
staging vs storage disks, so it is **not** disk-wide. Use `library-clean` for
whole-disk sweeps.

**Side effects**: `mutate FS` (renames files/folders, deletes `.DS_Store` across all staging items)

**Pipeline position**: step 6

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

**Pipeline position**: step 7

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

**Pipeline position**: step 9

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

**Pipeline position**: composite (runs clean + scrape + cleanup — steps 3–5)

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

## `personalscraper info providers`

**Purpose**: Prints a per-provider circuit-state snapshot from the provider
registry. Each configured provider is listed on its own line with its current
circuit-breaker state and recent failure count.

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**:

- `--config PATH` : Override default `config/providers.json5` for boot validation

**Expected output sample**:

    tmdb  circuit=closed  failures=0
    tvdb  circuit=closed  failures=0

**Exit codes**: 0 on success, 1 on `RegistryConfigError` (missing credentials or
broken config).

**Examples**:

    personalscraper info providers
    personalscraper info providers --config config.example/providers.json5

**Related**: `info`, `init-config`

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

> `library-clean` (disk cleaning) is backed by the `maintenance/` package — see [`maintenance.md`](maintenance.md) for its internals and safety constraints.

> Every `library-*` command also accepts its own `--config / -c PATH` option placed AFTER the subcommand (e.g. `personalscraper library-status -c ./config`), in addition to the global `--config` flag which must precede the subcommand.

## `personalscraper library-index`

**Purpose**: Runs a full or quick media indexer scan. Walks all configured storage
disks (or a single disk with `--disk`), records every file in the indexer
database, and prints a JSON summary. Supports multiple scan modes: `full`
(complete re-index with file hashing), `quick` (fast Merkle + dir-mtime
short-circuit), `incremental` (only new or modified files), and `enrich`
(metadata enrichment from NFOs, artwork, and media streams).

`library-index --mode full` is **self-sufficient** — it runs the item-stage
pass (rich `media_item` rows: title, canonical provider, seasons, artwork
status, `item_issue` flags) as **pass 1**, then the recursive file walk
(`media_file` / `media_stream` / `path` rows) as **pass 2**, inside a single
invocation. No prior `library-scan` step is required (the legacy two-step
"scan then index" workflow is gone).

**Side effects**: `mutate BDD` (writes media_item, season, episode, item_attribute, media_file, path, scan_run, scan_event rows)

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

**Purpose**: Visible alias of `library-index --mode full`, kept in `--help` for
backwards compatibility. It delegates to the very same indexer command that
backs `library-index`, fixing `mode="full"`: the item-stage pass writes the
rich `media_item` / `season` / `episode` / `item_attribute` rows, and the file
walk populates the `media_file` / `path` rows — both in a single invocation. It
no longer exposes `--mode` (always equivalent to `--mode full`). New scripts
should call `library-index --mode full` directly.

**Side effects**: `mutate BDD` (writes media_item, season, episode, item_attribute, media_file, path rows)

**Pipeline position**: n/a (alias of `library-index --mode full`, runs independently)

**Args**:

- `--disk / -d TEXT` : Restrict scan to this disk label
- `--dry-run` : Simulate scan without persisting any DB rows

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

**Args**:

- `--config / -c PATH` : Path to `config.json5` or config dir, placed after the subcommand (overrides the global `--config`)

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

## `personalscraper library-fix-canonical-provider`

**Purpose**: Repairs incorrect `canonical_provider` values in `media_item` rows.
Two corruption patterns are addressed: TV shows wrongly marked
`canonical_provider='tmdb'` when a valid `tvdb.series_id` exists in
`external_ids_json`, and movies with `canonical_provider IS NULL` when a valid
`tmdb.id` exists. The command runs two idempotent SQL UPDATE statements inside a
single transaction — re-running produces zero additional fixes because the WHERE
clauses only target rows still in the wrong state.

Dry-run by default — use `--apply` to execute the UPDATE.

**Side effects**: `read-only` (default), `mutate DB` (with `--apply`)

**Pipeline position**: n/a (utility — run on-demand when DEVIATION #7 is detected)

**Args**:

- `--apply` : Execute UPDATE statements (default: dry-run preview)
- `--config / -c PATH` : Path to config.json5 or config dir
- `--db PATH` : Path to library.db (overrides config)

**JSON output keys**:

- `apply` (bool)
- `would_fix_shows` / `fixed_shows` (int) — TV show rows with canonical_provider corrected
- `would_fix_movies` / `fixed_movies` (int) — movie rows with canonical_provider corrected

**Examples**:

    personalscraper library-fix-canonical-provider
    personalscraper library-fix-canonical-provider --apply
    personalscraper library-fix-canonical-provider --db /custom/path/library.db --apply

**Related**: `library-init-canonical`, `library-backfill-ids`, DEVIATION #7, ACC #4

---

## `personalscraper library-fix-nfo`

**Purpose**: Repairs NFO files that have trailing content after the XML root close
tag (`</tvshow>` or `</movie>`). When legacy scrapers (MediaElch, older
Emby/Jellyfin versions, or manually-authored NFOs) appended metadata URLs after
the root close tag, the resulting NFO becomes XML-ill-formed. `library-fix-nfo`
detects these cases, validates that the trailing content is safe to truncate
(whitelisted media-domain URLs only — typically redundant TVDB series-page links),
and truncates the file after the last root close tag.

Dry-run by default — use `--apply` to mutate files. When `--apply` is active,
the original file is preserved as `.nfo.bak` alongside the fixed NFO.

**Safety guarantees**:

- Trailing content is only removed when it consists exclusively of HTTP(S) URLs
  pointing to `thetvdb.com`, `themoviedb.org`, `imdb.com`, `omdbapi.com`,
  or `trakt.tv`. Any other trailing content (XML fragments, comments, arbitrary
  text) is skipped with an `unsafe_trailing` count.
- After truncation, the remaining content is re-parsed with
  `xml.etree.ElementTree`; if it still fails, the file is skipped
  (`still_malformed`).
- AppleDouble files (`._` prefix) are skipped.

Prerequisites: `library.db` must exist and have `media_item` rows with
`item_attribute(key='dispatch_path')` populated.

**Side effects**: `read-only` (default), `mutate FS` (with `--apply`)

**Pipeline position**: n/a (utility — run on-demand when NFO parse errors are detected)

**Args**:

- `--apply` : Actually truncate (default: dry-run preview)
- `--config / -c PATH` : Path to config.json5 or config dir
- `--db PATH` : Path to library.db (overrides config)

**Examples**:

    personalscraper library-fix-nfo
    personalscraper library-fix-nfo --apply
    personalscraper library-fix-nfo --db /custom/path/library.db --apply

**Related**: `library-init-canonical`, `library-backfill-ids`, `library-rescrape`

## `personalscraper library-fix-orphan-files`

**Purpose**: Repairs `media_file` rows with `release_id IS NULL` caused by
incomplete ingest/dispatch or DB recovery. For each orphan file, resolves the
owning `media_item` via the `item_attribute.dispatch_path` registry by
reconstructing the absolute path from `disk.mount_path` and `path.rel_path`, then
walks up parent directories (up to 6 levels) to handle files inside `Saison NN`
subdirectories. Links the orphan to its `media_release` when exactly one candidate
exists; files with zero or multiple candidate releases are counted but not repaired.

Dry-run by default — use `--apply` to execute the UPDATE statements.

**Side effects**: `read-only` (default), `mutate DB` (with `--apply`)

**Pipeline position**: n/a (utility — run on-demand when DEVIATION #8 or invariant AO is detected)

**Args**:

- `--apply` : Execute UPDATE statements (default: dry-run preview)
- `--config / -c PATH` : Path to config.json5 or config dir
- `--db PATH` : Path to library.db (overrides config)

**JSON output keys**:

- `apply` (bool)
- `items_scanned` (int) — total orphan `media_file` rows examined
- `would_fix` / `fixed` (int) — files successfully linked
- `no_release` (int) — files where no owning item or release was found
- `ambiguous` (int) — files with multiple candidate releases

**Examples**:

    personalscraper library-fix-orphan-files
    personalscraper library-fix-orphan-files --apply
    personalscraper library-fix-orphan-files --db /custom/path/library.db --apply

**Related**: `library-relink`, DEVIATION #8, invariant AO

---

## `personalscraper library-fix-season-counts`

**Purpose**: Repairs `season.episode_count` drift where the cached count in the
`season` table does not match the actual `COUNT(*)` of rows in the `episode` table.
This drift can occur after manual DB edits, incomplete ingests, or edge cases in
the indexing code paths. The UPDATE statement is predicate-guarded (`WHERE
episode_count != actual`) so re-running the command is a no-op — it only touches
seasons where a mismatch exists.

Dry-run by default — use `--apply` to execute the UPDATE. In dry-run mode, a
`details` list with per-season drift data (item_id, season number, old vs actual
count) is emitted for operator inspection.

**Side effects**: `read-only` (default), `mutate DB` (with `--apply`)

**Pipeline position**: n/a (utility — run on-demand when DEVIATION #9 or invariant AP is detected)

**Args**:

- `--apply` : Execute UPDATE statement (default: dry-run preview)
- `--config / -c PATH` : Path to config.json5 or config dir
- `--db PATH` : Path to library.db (overrides config)

**JSON output keys**:

- `apply` (bool)
- `seasons_scanned` (int) — total rows in `season` table
- `would_fix` / `fixed` (int) — seasons corrected
- `details` (list[dict]) — per-season drift data, dry-run only

**Examples**:

    personalscraper library-fix-season-counts
    personalscraper library-fix-season-counts --apply
    personalscraper library-fix-season-counts --db /custom/path/library.db --apply

**Related**: DEVIATION #9, invariant AP

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

## Library — analysis & query

> `library-analyze` / `library-recommend` / `library-report` surface the read-only `insights/` package — see [`insights.md`](insights.md). `library-rescrape` is backed by `maintenance/` — see [`maintenance.md`](maintenance.md).

> Every `library-*` command also accepts its own `--config / -c PATH` option placed AFTER the subcommand (e.g. `personalscraper library-status -c ./config`), in addition to the global `--config` flag which must precede the subcommand.

## `personalscraper library-analyze`

**Purpose**: Print a codec / audio / subtitle summary read **from the indexer
DB** (no inline ffprobe, no filesystem walk — the legacy ffprobe re-scan was
removed). Requires a prior `library-index --mode enrich` pass to populate the
`media_stream` rows. The `--from-index` flag is accepted for backwards
compatibility but ignored: the DB is always the sole source. HDR / Atmos
detection is approximated from the enriched columns (see the
`analyze_from_index` docstring for the per-field caveats).

**Side effects**: `read-only` (DB query only — no ffprobe subprocess)

**Pipeline position**: n/a

**Args**:

- `--disk TEXT` : Analyze only this disk
- `--category TEXT` : Analyze only this category
- `--max-items INTEGER` : Limit number of items to analyze
- `--from-index` : Accepted but ignored — the indexer DB is always the sole
  source. Kept for backwards compatibility.

**Examples**:

    personalscraper library-analyze
    personalscraper library-analyze --disk Disk1 --category movies
    personalscraper library-analyze --max-items 50
    personalscraper library-analyze --from-index

**Related**: `library-recommend`, `library-report`, `library-index`

---

## `personalscraper library-recommend`

**Purpose**: Generate re-download recommendations from an analysis read **from
the indexer DB** (no inline ffprobe, no filesystem walk — the legacy ffprobe
re-scan was removed). Requires a prior `library-index --mode enrich` pass to
populate the `media_stream` rows. Preferences come from `config.library`.
Output is written to `library_recommendations.json`. The `--from-index` flag is
accepted for backwards compatibility but ignored: the DB is always the sole
source.

**Side effects**: `mutate FS` (writes `library_recommendations.json`) — no
ffprobe subprocess

**Pipeline position**: n/a

**Args**:

- `--sort TEXT` : Sort by: `priority`, `size`, `codec` [default: priority]
- `--export TEXT` : Export format: `csv`
- `--disk TEXT` : Filter to this disk
- `--category TEXT` : Filter to this category
- `--from-index` : Accepted but ignored — the indexer DB is always the sole
  source. Kept for backwards compatibility.

**Examples**:

    personalscraper library-recommend
    personalscraper library-recommend --sort size
    personalscraper library-recommend --export csv
    personalscraper library-recommend --from-index

**Related**: `library-analyze`, `library-report`

---

## `personalscraper library-rescrape`

**Purpose**: Targeted re-scrape of library items via TMDB/TVDB. Only repairs
what is broken per item: missing NFO, missing artwork, unrenamed episodes. Items
already conforming are skipped. Use `--only` to restrict to specific repair
types, `--interactive` for ambiguous matches, and `--max-items` to limit the
batch size.

**Side effects**: `mutate FS` (writes NFO + artwork files), `network` (TMDB / TVDB APIs)

**Pipeline position**: n/a

**Args**:

- `--only TEXT` : Only fix: `nfo`, `artwork`, `episodes`
- `--disk TEXT` : Rescrape only this disk
- `--category TEXT` : Rescrape only this category
- `--interactive` : Confirm low-confidence matches
- `--dry-run` : Preview without modifying files
- `--max-items INTEGER` : Limit number of items to process

**Examples**:

    personalscraper library-rescrape --dry-run
    personalscraper library-rescrape --only artwork
    personalscraper library-rescrape --disk Disk1 --max-items 50
    personalscraper library-rescrape --interactive

**Related**: `scrape`, `library-validate`, `library-report`

---

## `personalscraper library-report`

**Purpose**: Display library statistics and health report. Aggregates data from
the indexer DB (totals, NFO / artwork health, disk distribution, per-item sizes)
and supplementary JSON outputs from `library-validate`, `library-recommend`, and
`library-rescrape`. Output format respects the global `--format` flag (`rich` by
default, `json` for machine-parseable output).

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**: none beyond global flags

**Examples**:

    personalscraper library-report
    personalscraper --format json library-report

**Related**: `library-analyze`, `library-recommend`, `library-rescrape`,
`library-doctor`

---

## `personalscraper library-doctor`

**Purpose**: Run health checks on the library indexer database. Executes a suite
of targeted checks covering database integrity, schema coherence, scan-run
lifecycle, outbox lag, Merkle drift, canonical-provider coverage, and phantom
paths. Output format respects the global `--format` flag. Exit code is 0 when
all checks pass (status ok or skip), non-zero when any check is WARN or FAIL.

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**:

- `--repair-queue-threshold INTEGER` : Max pending `repair_queue` rows before
  WARN [default: 100]
- `--outbox-lag-threshold-s INTEGER` : Max age in seconds for oldest pending
  `index_outbox` row before WARN [default: 3600]
- `--canonical-threshold-pct FLOAT` : Min % of `media_item` rows that must have
  `canonical_provider` set before WARN [default: 50.0]
- `--stuck-scan-threshold-s INTEGER` : Seconds after which a running `scan_run`
  is considered stuck [default: 3600]
- `--config / -c PATH` : Path to config.json5 or config dir

**Examples**:

    personalscraper library-doctor
    personalscraper --format json library-doctor
    personalscraper library-doctor --repair-queue-threshold 50
    personalscraper library-doctor --outbox-lag-threshold-s 7200

**Related**: `library-report`, `library-reconcile`, `library-status`

---

## `personalscraper library-search`

**Purpose**: Search indexed media items with the flex-attr query language. Field
syntax: `field:value`, `-field:value` (negation), `year:>=2020`, `title:"Exact
Title"`. Unknown fields cause an exit code 2 (caller can branch on it). Use
`--limit` to cap the result set.

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**:

- `QUERY` _(required)_ : Query string, e.g. `'year:2024 disk:Disk1 -nfo:valid'`
- `--limit INTEGER` : Maximum number of results to return [default: 50]
- `--config / -c PATH` : Path to config.json5 or config dir

**Examples**:

    personalscraper library-search "year:2024 disk:Disk1 -nfo:valid"
    personalscraper library-search "kind:show codec:hevc -trailer"
    personalscraper library-search 'title:"Lost Highway"'

**Related**: `library-show`, `library-index`

---

## `personalscraper library-show`

**Purpose**: Pretty-print all stored data for a single media item. Prints
`media_item` fields, season / episode rows, `media_file` rows with streams,
`item_attribute` rows, and `deleted_item` history. Exits 2 for unknown ids.

**Side effects**: `read-only`

**Pipeline position**: n/a

**Args**:

- `ITEM_ID` _(required)_ : `media_item.id` to display
- `--config / -c PATH` : Path to config.json5 or config dir

**Examples**:

    personalscraper library-show 42

**Related**: `library-search`, `library-status`

---

## `personalscraper library-backfill-ids`

**Purpose**: Backfill missing cross-provider IDs and multi-source ratings on
library items. Walks every `media_item` row (or a single show with `--show`),
detects missing provider IDs and rating sources, fetches the missing data from
TMDB, TVDB, IMDb (via OMDb), and Rotten Tomatoes (via OMDb), and merges the
results additively — never overwriting the canonical provider anchor or
already-present values.

Prerequisites (in order):

1. Run `personalscraper library-init-canonical` to seed `canonical_provider` on
   rows that pre-date the provider-ids feature. Backfill cannot resolve
   cross-provider IDs without a canonical anchor.
2. Ensure API credentials are set in `.env`: `TMDB_API_KEY` (TMDB-canonical
   rows), `TVDB_API_KEY` (TVDB-canonical rows), `OMDB_API_KEY` (IMDb and
   Rotten Tomatoes ratings).

Use `--dry-run` to preview what would be backfilled without touching the
database. Use `--ids-only` or `--ratings-only` to restrict the pass to one
dimension.

**Side effects**: `mutate BDD` (updates `external_ids_json`, `ratings_json` on
`media_item` rows), `network` (TMDB, TVDB, OMDb APIs)

**Pipeline position**: n/a

**Args**:

- `--show TEXT` : Restrict pass to a single show title
- `--ids-only` : Only backfill provider IDs, skip ratings
- `--ratings-only` : Only backfill ratings, skip provider IDs
- `--dry-run` : Simulate without writing to DB
- `--config / -c PATH` : Path to config.json5 or config dir

**Examples**:

    personalscraper library-backfill-ids --dry-run
    personalscraper library-backfill-ids --show "Breaking Bad"
    personalscraper library-backfill-ids --ids-only
    personalscraper library-backfill-ids --ratings-only

**Related**: `library-init-canonical`, `library-index --mode enrich`,
`library-reconcile`

---

## Trailers

## `personalscraper trailers`

**Purpose**: Parent command for trailer acquisition and management. Does nothing
on its own — run `personalscraper trailers --help` to list the four subcommands.
Trailers are discovered via TMDB `/videos` then downloaded from YouTube via
yt-dlp. The trailer pipeline step is disabled by default (`trailers.enabled =
false` in config); set `YOUTUBE_API_KEY` in `.env` to enable it. Trailer files
are placed according to Plex conventions: flat in the media folder for movies,
in a `Trailers/` subfolder for TV shows.

**Side effects**: none (delegates to subcommands)

**Pipeline position**: step 8 (within `run`)

**Args**: none beyond global flags

**Examples**:

    personalscraper trailers --help
    personalscraper trailers scan
    personalscraper trailers download

**Related**: `trailers scan`, `trailers download`, `trailers audit`, `trailers
purge`, `run`

---

## `personalscraper trailers scan`

**Purpose**: Dry-run: list media items missing trailers. Scans the library for
items that should have trailers but don't, printing a report of candidates
without downloading anything. Use `--level` to filter by trailer type (`show`,
`season`, or `both`). Season-level trailers are silently ignored when
`seasons.enabled` is `false` in config.

**Side effects**: `read-only`

**Pipeline position**: step 8 (within `run` — invoked automatically before download)

**Args**:

- `--disk TEXT` : Restrict to one disk by ID (e.g. `Disk1`)
- `--category TEXT` : Restrict to one category ID
- `--since TEXT` : Only items added/modified after `YYYY-MM-DD`
- `--limit INTEGER` : Max items to scan
- `--no-refresh` : Use cached library scan even if stale
- `--level TEXT` : Which trailer levels to list: `show`, `season`, `both`
  [default: both]
- `--season INTEGER` : Target a specific season number (1-indexed). Implies
  `--level=season`.

**Examples**:

    personalscraper trailers scan
    personalscraper trailers scan --disk Disk1
    personalscraper trailers scan --limit 20
    personalscraper trailers scan --level season --season 1

**Related**: `trailers download`, `trailers audit`, `trailers`

---

## `personalscraper trailers download`

**Purpose**: Discover and download missing trailers. Finds media items without
trailers, searches YouTube for matching trailers via TMDB video metadata
(two-tier: TMDB `/videos` → YouTube API v3 → yt-dlp fallback), and downloads
them. Trailer files are placed according to Plex conventions: flat in the media
folder for movies, in a `Trailers/` subfolder for TV shows. Use `--dry-run` to
preview candidates without downloading.

**Side effects**: `mutate FS` (writes trailer files), `network` (YouTube API, yt-dlp)

**Pipeline position**: step 8 (within `run`)

**Args**:

- `--disk TEXT` : Restrict to one disk by ID (e.g. `Disk1`)
- `--category TEXT` : Restrict to one category ID
- `--since TEXT` : Only items added/modified after `YYYY-MM-DD`
- `--limit INTEGER` : Max items to process
- `--dry-run` : Show what would be downloaded without doing it
- `--no-refresh` : Skip library cache refresh
- `--level TEXT` : Which trailer levels to process: `show`, `season`, `both`
  [default: both]
- `--season INTEGER` : Target a specific season number (1-indexed). Implies
  `--level=season`.

**Examples**:

    personalscraper trailers download --dry-run
    personalscraper trailers download --limit 5
    personalscraper trailers download --disk Disk1
    personalscraper trailers download --level season --season 2

**Related**: `trailers scan`, `trailers audit`, `trailers`

---

## `personalscraper trailers audit`

**Purpose**: Audit existing trailers. Runs four checks per trailer:

1. **Existence** — trailer file present at the expected placement path.
2. **Size** — file size >= `config.trailers.filters.min_file_size_bytes`.
3. **Extension** — file suffix in `config.trailers.filters.allowed_extensions`.
4. **Playable** (opt-in, `--deep`) — ffprobe returns non-zero duration.

Failure categories: `missing`, `undersized`, `wrong_extension`, `unplayable`.
Exit codes: 0 if all pass, 2 if any functional check fails, 4 if a `--deep`
ffprobe call errors out (probe itself broken).

**Side effects**: `read-only` (ffprobe subprocess spawns with `--deep`)

**Pipeline position**: n/a (manual audit — not part of the automated pipeline)

**Args**:

- `--disk TEXT` : Restrict to one disk by ID (e.g. `Disk1`)
- `--category TEXT` : Restrict to one category ID
- `--since TEXT` : Only items added/modified after `YYYY-MM-DD`
- `--deep` : Run ffprobe playability probe (expensive)
- `--level TEXT` : Which trailer levels to audit: `show`, `season`, `both`
  [default: both]
- `--season INTEGER` : Target a specific season number (1-indexed). Implies
  `--level=season`.

**Examples**:

    personalscraper trailers audit
    personalscraper trailers audit --disk Disk1
    personalscraper trailers audit --deep
    personalscraper trailers audit --level season

**Related**: `trailers scan`, `trailers download`, `trailers purge`, `trailers`

---

## `personalscraper trailers purge`

**Purpose**: Remove orphan trailers whose media parent is absent. Walks storage
disks and deletes trailer files that no longer have a corresponding media item
(or whose media folder has been removed). Use `--dry-run` to preview without
deleting. When `--include-state` is set, also calls `state_store.purge_orphans()`
to clean orphan entries from the trailer state tracking file.

**Side effects**: `mutate FS` (deletes trailer files), `mutate BDD` (with
`--include-state` — cleans state store entries)

**Pipeline position**: n/a (maintenance — not part of the automated pipeline)

**Args**:

- `--disk TEXT` : Restrict to one disk by ID (e.g. `Disk1`)
- `--since TEXT` : Only items added/modified after `YYYY-MM-DD`
- `--dry-run` : Show what would be purged without doing it
- `--include-state` : Also wipe orphan state entries via
  `state_store.purge_orphans()`
- `--level TEXT` : Which trailer levels to purge: `show`, `season`, `both`
  [default: both]
- `--season INTEGER` : Target a specific season number (1-indexed). Implies
  `--level=season`.

**Examples**:

    personalscraper trailers purge --dry-run
    personalscraper trailers purge --disk Disk1
    personalscraper trailers purge --include-state
    personalscraper trailers purge

**Related**: `trailers audit`, `trailers`

---

## Config — sub-commands

## `personalscraper config migrate-category`

**Purpose**: Rewrites `media_item.category_id` for renamed categories. Rewrites
every `media_item` row whose `category_id` equals `--from` to `--to`. Run this
after renaming a category in `categories.json5` (e.g. splitting or merging
content types) to clear orphan-tagged rows. The target `--to` must already be a
declared category ID in the current config — the rename must be applied first.
The operation is idempotent: running it twice with the same arguments has no
additional effect.

**Side effects**: `mutate BDD` (updates `category_id` on `media_item` rows)

**Pipeline position**: n/a

**Args**:

- `--from TEXT` _(required)_ : Old `category_id` to replace
- `--to TEXT` _(required)_ : New `category_id` to write (must be declared in config)
- `--config / -c PATH` : Path to config.json5 or config dir

**Examples**:

    personalscraper config migrate-category --from old_cat --to new_cat

**Related**: `config`, `init-config`, `library-status`
