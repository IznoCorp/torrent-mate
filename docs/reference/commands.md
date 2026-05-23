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

### Library — indexer (→ 6.2.b)

14. `library-index` — scan disks into the indexer DB
15. `library-status` — latest scan run summary
16. `library-verify` — re-stat indexed files, enqueue mismatches
17. `library-search` — flex-attr query
18. `library-show` — pretty-print one item
19. `library-repair` — drain repair queue
20. `library-reconcile` — detect index ↔ FS divergences
21. `library-ghost-audit` — audit NTFS ghost directory entries
22. `library-relink` — repair broken release links
23. `library-clean` — delete junk files from disks
24. `library-doctor` — health checks on live DB
25. `library-init-canonical` — bootstrap canonical_provider column

### Library — maintenance (→ 6.2.b)

26. `library-backfill-ids` — backfill provider IDs across releases
27. `library-gc` — garbage-collect stale DB rows

### Library — analysis (→ 6.2.c)

28. `library-validate` — validate NFO/artwork/naming
29. `library-analyze` — deep ffprobe scan
30. `library-recommend` — re-download recommendations
31. `library-rescrape` — targeted re-scraping
32. `library-report` — health statistics

### Trailers (→ 6.2.c)

33. `trailers scan` — discover media missing trailers
34. `trailers download` — download trailers from YouTube
35. `trailers verify` — audit trailer files on disk
36. `trailers purge` — remove unwanted trailers

### Config subcommands (→ 6.2.c)

37. `config migrate-category` — rename a category across config + paths

### Make targets + scheduling (appendix)

38. `make` targets — test, lint, format, install-dev
39. launchd scheduling — plist install / load / unload

> **Note**: Entries 14–39 are placeholders. Full content will be added by
> dispatch 6.2.b (library indexer/maintenance) and 6.2.c (analysis + trailers
>
> - config subcommands).

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
