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
