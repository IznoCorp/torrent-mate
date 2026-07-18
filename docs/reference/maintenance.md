# Maintenance Reference

Operator-upkeep layer over the permanent media library: targeted re-scrape
repairs plus filesystem cleaning.

## Overview

The `maintenance/` package (`personalscraper/maintenance/`) hosts the two
read/write upkeep modules that operate directly on the permanent library on the
storage disks (and, where useful, the indexer SQLite DB):

- `rescraper.py` — targeted, API-based per-item repairs (regenerate a missing
  NFO, download missing artwork, rename unrenamed episodes).
- `disk_cleaner.py` — filesystem cleaning (remove `.actors/`, empty dirs, junk
  files, release-group artifacts, and stale "orphan" release directories).

Both modules were re-homed here from the deleted top-level `library/` package
during the lib-fold 0.19.0 consolidation. They are surfaced by the
`library-rescrape` and `library-clean` CLI commands.

### Distinction from `indexer/repair.py`

The maintenance package operates on the **filesystem** (and calls metadata
APIs). It is separate from `personalscraper/indexer/repair.py`, which is a
**DB-only** repair-queue worker:

| Layer               | Operates on                             | Surfaced by                         |
| ------------------- | --------------------------------------- | ----------------------------------- |
| `maintenance/`      | Permanent library files + metadata APIs | `library-rescrape`, `library-clean` |
| `indexer/repair.py` | `repair_queue` rows in the indexer DB   | `library-verify`, `library-repair`  |

`indexer/repair.py` enqueues drift (`enqueue_repair`), drains pending rows in
FIFO order within a wall-clock budget (`drain`), reports queue health
(`get_queue_health`), and soft-deletes subtrees (`soft_delete_subtree`) — it
never touches files on disk. The maintenance package is the converse: it edits
files (writing NFOs/artwork, renaming episodes, deleting directories) and only
_notifies_ the indexer of the resulting drift through best-effort outbox events.
See `docs/reference/indexer.md` for the repair queue and outbox details.

## Package layout

| Module            | Purpose                                                                      |
| ----------------- | ---------------------------------------------------------------------------- |
| `rescraper.py`    | Targeted re-scrape repairs (NFO / artwork / episodes) via TMDB/TVDB.         |
| `disk_cleaner.py` | Filesystem cleanup of the media library with NTFS-via-macFUSE rmtree safety. |

---

## disk_cleaner.py

Filesystem-level cleanup of the media library across all configured storage
disks. **Dry-run by default** — nothing is deleted unless the caller passes
`apply=True` (CLI: `--apply`).

### `clean_library(config, apply=False, only=None, disk_filter=None, category_filter=None) -> CleanResult`

Iterates `config.disks`, and for each disk iterates its `disk.categories`,
resolving the physical folder name from `config.category(id).folder_name`. Disks
that are not mounted (`disk.path` does not exist) are logged and skipped;
category folders that do not exist are skipped quietly.

Within each category folder it visits every immediate sub-directory (skipping
dot-directories) and applies the selected cleanup modes:

- `actors` — remove the `.actors/` thumbnail directory.
- `junk` — remove junk files (names in `text_utils.JUNK_FILE_NAMES`, plus macOS
  AppleDouble `._*` resource forks).
- `empty` — remove directories that are empty or contain only junk files
  (`_is_effectively_empty`).
- `release` — remove empty release-group artifact directories (dotted names with
  an upper-cased group suffix, e.g. `Some.Release.GROUP`).
- `orphans` — remove an entire **stale release directory** that contains no main
  video file (typical residue: `.actors/` + a `-trailer.mp4` + the `.nfo` +
  artwork left behind after a manual video delete).

The `only` argument selects a single mode by name (`"actors"`, `"empty"`,
`"junk"`, `"release"`, `"orphans"`); `None` runs all of them **except**
`orphans`.

**Filters:** `disk_filter` restricts to one disk by `disk.id`; `category_filter`
restricts to one `category_id`.

Returns a `CleanResult` with `dry_run`, `deleted_count`, `error_count`,
`freed_bytes`, and per-item `details` / `errors` lists.

### Orphan mode — safety constraints

`orphans` is the only destructive-at-directory-granularity mode and is treated
with extra caution:

- **Opt-in only.** It is _never_ part of the default "all" run; it triggers only
  when `only == "orphans"` is passed explicitly.
- **Video-centric.** A directory is an orphan when it is non-empty
  (`_is_orphan_release_dir`) yet has no "main" video. A main video is a file
  whose extension is in `core.media_types.VIDEO_EXTENSIONS`, whose size is at
  least 50 MB (`_MAIN_VIDEO_MIN_BYTES`, filters trailers/clips), and whose
  basename contains no `trailer` / `teaser` / `sample` / `extra` marker. TV-show
  `Saison NN/` / `Season NN/` sub-folders (matched via
  `naming_patterns.SEASON_DIR_RE`) are descended one level so episodes count.
- **Non-video categories are skipped.** Categories whose main content is not a
  video file (`_ORPHAN_NON_VIDEO_CATEGORIES`, currently `audiobooks`) are skipped
  in orphan mode, because "no main video" is meaningless for them.
- **Conservative on read errors.** `_has_main_video` returns `True` (i.e. "not an
  orphan") whenever a directory cannot be listed, so an unreadable directory is
  never deleted.

### Filesystem deletion safety (`_scandir_rmtree`)

Real deletions use a custom recursive remover (`_scandir_rmtree`) rather than
`shutil.rmtree`, to survive NTFS-via-macFUSE NFC/NFD filename quirks:

- It walks via `os.scandir` `DirEntry.path` (no decode/re-encode round-trip that
  `shutil.rmtree` performs), bottom-up so directories are emptied before removal.
- Symlinks are unlinked, not descended into.
- **Ghost dirents** — entries that `scandir` lists but the kernel cannot
  `stat`/`unlink` (the known macFUSE/NTFS NFC vs NFD inconsistency) — are
  collected into a `ghosts` list and skipped rather than aborting the whole
  delete, so freeable content is still freed.

When a ghost dirent blocks the final `os.rmdir` (`ENOTEMPTY`), `_delete_dir`
records a precise per-item error naming the ghost files and the required manual
fix (unmount + `ntfsfix`/fsck), increments `error_count`, and continues with the
next directory. This matches the known "macFUSE/NTFS ghost-inodes on Disk1" issue
documented in project memory. All other `OSError`s are similarly captured
per-item and reported, never propagated.

### Write-through to the indexer

On every **real** deletion (not dry-run), the deletion helpers
(`_delete_dir`, `_delete_file`) publish a best-effort outbox event via
`indexer.outbox._publish.publish_event` (`_publish_deleted`). The event uses
`op="move"` with a populated `src_rel_path` and an **empty** `dst_rel_path` as
the drainer's convention for "this path was removed", so the indexer can
reconcile the removed content at its next drain cycle. The configured
`Config.indexer.db_path` is threaded through so the event lands in the correct
DB. Any outbox failure is swallowed — the filesystem delete already succeeded and
the indexer will reconcile the drift at the next scan.

---

## rescraper.py

Targeted, API-based repairs for items already in the permanent library. It
detects what each item needs (NFO, artwork, episode renames), resolves a
TMDB/TVDB ID, fetches the API data **once**, then applies only the fixes that are
needed. It reuses the existing scraper components (`NFOGenerator`,
`ArtworkDownloader`, `episode_manager`, `confidence` matchers) rather than
duplicating that logic. **Dry-run by default** (`dry_run=True`).

### `rescrape_library(config, conn=None, disk_filter=None, category_filter=None, only=None, interactive=False, dry_run=True, max_items=None, *, event_bus, registry) -> LibraryRescrapeResult`

Builds a candidate list (`_collect_rescrape_candidates`), then rescrapes each
item, capping at `max_items` when set.

**Candidate discovery — two sources:**

- **DB query (`conn` provided).** Queries the indexer DB via
  `item_repo.find_items_needing_rescrape`, i.e. items where
  `nfo_status != 'valid'` **or** `date_metadata_refreshed IS NULL`. Absolute
  paths are reconstructed from `disk.mount_path` + `path.rel_path`, with
  `disk_filter` / `category_filter` applied.
- **Filesystem walk (`conn=None`).** Falls back to walking `config.disks` →
  category folders → media directories, classifying TV vs movie via
  `conf.ids.TV_CATEGORY_IDS`.

> Note: the `library-rescrape` CLI command does **not** currently pass a `conn`,
> so it uses the filesystem-walk path. The DB-query path is wired into the
> function signature for callers (and future CLI use) that hold an open
> connection.

**Per-item flow (`_rescrape_item`):**

1. `_detect_needs` decides `needs_nfo` (NFO missing/incomplete via
   `nfo_utils.is_nfo_complete`), `needs_artwork` (no poster file), and
   `needs_episodes` (TV only — a video file with no `SxxExx` marker). The `only`
   filter narrows this to a single dimension.
2. If nothing is needed, the item is skipped silently (returns `None`, "already
   conforming").
3. `_resolve_tmdb_id` resolves the provider ID: first from an existing NFO
   (`nfo_utils.extract_nfo_ids`), else by re-matching via the
   `scraper.confidence` matchers (`match_movie` / `match_tvshow`) using the
   `ProviderRegistry`-resolved TMDB/TVDB clients.
4. API data is fetched once (`tmdb.get_movie` / `tmdb.get_tv`), then NFO,
   artwork, and episode fixes are applied independently. Episode rescrape fetches
   per-season data and reuses `episode_manager` (`match_episode_files`,
   `create_season_dirs`, `rename_episodes`), only creating season directories for
   seasons that actually receive a local file.

**Confidence gate (`_resolve_tmdb_id`):** a re-match below
`scraper.confidence.HIGH_CONFIDENCE` is rejected (skip reason
`low_confidence_match`) unless `interactive=True`, in which case the operator is
prompted to accept. IDs read from an existing NFO bypass the gate (no confidence
is recorded).

**Circuit-breaker integration:** the required `event_bus` is propagated to the
TMDB/TVDB transports so that circuit-breaker trips during a long rescrape reach
the run's Telegram / RichConsole subscribers (the breaker itself lives in the
transport layer — see `docs/reference/pipeline-internals.md`). The
`ProviderRegistry` (`registry`) resolves the metadata clients.

**Result.** Returns a `LibraryRescrapeResult` with `fixed_count`,
`skipped_count`, `error_count`, the applied filters, `dry_run`, and a per-item
`items` list of `RescrapeAction` records. Each `RescrapeAction` carries the
path/title/type/disk/category, `actions_taken` (`nfo_regenerated`,
`artwork_downloaded`, `episodes_renamed`), `actions_skipped`, per-item `errors`,
the `tmdb_id`, `id_source` (`nfo` / `api_match`), `match_confidence`, and an ISO
timestamp. Per-item exceptions (API failure, NTFS write error) are captured into
the record's `errors` and counted, never propagated — one bad item does not abort
the run.

### Repair vs. clean — what is destructive

- `disk_cleaner` **deletes** files and directories (irreversibly on
  `--apply`); orphan mode deletes whole release directories.
- `rescraper` **writes** NFO/artwork files and **renames** episode files; it does
  not delete media. The destructive surface is overwriting an existing NFO or
  renaming a video into the canonical `SxxExx` form.

Both default to dry-run; verify the preview before re-running with the live flag.

---

## Dataclasses

| Dataclass               | Module            | Role                                                                   |
| ----------------------- | ----------------- | ---------------------------------------------------------------------- |
| `CleanResult`           | `disk_cleaner.py` | Counts + `details`/`errors` for a cleanup run.                         |
| `RescrapeAction`        | `rescraper.py`    | One per-item repair record (actions taken/skipped, IDs, errors).       |
| `LibraryRescrapeResult` | `rescraper.py`    | Top-level rescrape container (also the `library_rescrape.json` shape). |

Action / skip constants in `rescraper.py`: `ACTION_NFO_REGENERATED`,
`ACTION_ARTWORK_DOWNLOADED`, `ACTION_EPISODES_RENAMED`, `SKIP_LOW_CONFIDENCE`,
`SKIP_NO_MATCH`, `SKIP_ALREADY_OK`.

---

## CLI commands

The package is surfaced by two Typer commands (Typer maps the function name's
underscores to hyphens):

| Command            | Defined in                        | Backed by                    | Default |
| ------------------ | --------------------------------- | ---------------------------- | ------- |
| `library-clean`    | `commands/library/maintenance.py` | `disk_cleaner.clean_library` | dry-run |
| `library-rescrape` | `commands/library/analyze.py`     | `rescraper.rescrape_library` | dry-run |

### `library-clean`

```
personalscraper library-clean
personalscraper library-clean --dry-run
personalscraper library-clean --apply
personalscraper library-clean --apply --only actors
personalscraper library-clean --only orphans            # dry-run preview
personalscraper library-clean --only orphans --apply    # actually delete
personalscraper library-clean --disk Disk1
```

Options: `--apply` (actually delete), `--dry-run` (explicit alias for the
default, mutually exclusive with `--apply`), `--only`
(`actors` / `empty` / `junk` / `release` / `orphans`), `--disk` (disk id),
`--category`. An invalid `--only` value exits non-zero. The instance lock is
acquired only when `--apply` is set. For `--only orphans` dry-runs the command
prints a preview (first 20 paths) so the high blast-radius can be sanity-checked
before applying.

### `library-rescrape`

```
personalscraper library-rescrape --dry-run
personalscraper library-rescrape --only artwork
personalscraper library-rescrape --disk <disk_id> --max-items 50
personalscraper library-rescrape --interactive
```

Options: `--only` (`nfo` / `artwork` / `episodes`), `--disk`, `--category`,
`--interactive` (confirm low-confidence matches), `--dry-run` (preview without
modifying files), `--max-items`. The instance lock is acquired only for a live
(non-dry-run) run. Results are written to `library_rescrape.json` under
`paths.data_dir`, and the report (`library-report`) folds those counts in. The
command runs inside a `per_step_boundary`, supplying the `event_bus` and
`provider_registry` from the `AppContext`.

See `docs/reference/commands.md` for the full command catalog,
`docs/reference/indexer.md` for the repair-queue / outbox layers, and
`docs/reference/scraping.md` for the NFO/artwork/confidence components reused by
the rescraper.

---

## Web-UI maintenance actions (S3)

The TorrentMate web UI exposes all ~20 `library-*` CLI commands as a catalog of
maintenance actions (`docs/reference/web-ui.md` § Maintenance dashboard (S3)).
This section describes how they are wired — the registry, the runner, and the
safety guarantees — from the backend perspective.

### Registry — CLI → web-form mapping

`personalscraper/web/maintenance/registry.py` holds a `REGISTRY` dict of 25
`MaintenanceAction` entries, one per registered `library-*` Typer command. Each
entry carries an `id` (matching the CLI name), a French `title` and
`description`, a `category` (`query` / `scan` / `repair` / `clean` / `analyze` /
`fix`), a `risk` level (`ro` / `write` / `destructive`), a `long_running` flag,
a `dry_run` capability (`supported` / `unsupported`), and a curated `options`
list of `ActionOption` typed fields (text, number, select, bool).

The result is a **registry-driven form generator**: the frontend reads
`GET /api/maintenance/actions` (which returns the full catalog + per-category
counts) and renders one form per action purely from its `options` list, with no
per-action frontend code needed. A test asserts that the set of registry keys
equals the set of registered `library-*` commands, guaranteeing the catalog
stays in sync with the CLI surface.

### Runner — detached subprocess model

When the operator submits an action form, `POST /api/maintenance/actions/{action_id}/run`
spawns a **detached subprocess** that survives the web process restart:

```
python -m personalscraper.web.maintenance.runner
```

Environment variables carry the payload: `PERSONALSCRAPER_RUN_UID` (uuid4 hex),
`PERSONALSCRAPER_MAINT_COMMAND` (the `library-*` command name),
`PERSONALSCRAPER_MAINT_OPTIONS_JSON` (the canonical form of the submitted options),
and `PERSONALSCRAPER_MAINT_DRY_RUN` (`"1"` or `"0"`).

The runner lifecycle:

1. **Inserts a `pipeline_run` row** with `kind='maintenance'`, `command`, and
   `options_json` (this is the same table that S2's pipeline history uses —
   migration `012` added the `kind`, `command`, `options_json`, and `output_tail`
   columns).
2. **Runs the real `library-*` CLI** as a child process (the same code path as
   the terminal command, not a re-implementation).
3. **Streams output** — each stdout/stderr line is pushed to the Redis stream as
   a `maintenance.run_log` envelope keyed by `run_uid`. The existing S1
   WebSocket relay forwards it to connected clients; no protocol change is
   needed.
4. **Keeps a 64 KiB `output_tail`** ring buffer.
5. **Finalizes the row** — sets `ended_at`, `outcome` (`success` / `error`), and
   `output_tail` (the last 64 KiB of output, persisted for durable access after
   the WebSocket stream ends).

The unified `pipeline_run` table means the frontend's `RunHistoryTable`
(reused from S2, now on the `/systeme?tab=maintenance` tab) filters by
`?kind=maintenance`.
`GET /api/pipeline/history?kind=pipeline|maintenance|all` and
`GET /api/pipeline/history/{run_uid}` (now returning `kind`, `command`,
`options_json`, `output_tail` in the detail view) serve both pipeline and
maintenance history from the same endpoints.

### Safety guarantees

**Pipeline lock.** Write/destructive actions hold the same `pipeline.lock` as
the Watcher and S2's `/api/pipeline/run` for their whole subprocess lifetime
(R11). Since constitution v2 §6 a held lock is **never a refusal**: the POST
always accepts (`202`, `queued: true` hint when the lock is held at spawn
time) and the **runner** waits in the shared visible queue
(`web/run_queue.py` — `queue` step on the run row, status
`waiting_pipeline_lock`, default budget 1800 s via
`PERSONALSCRAPER_MAINT_QUEUE_TIMEOUT`, French `error` finalize on timeout)
until its atomic `acquire_pipeline_lock` claim succeeds. It releases the lock
on every exit path (success, error, spawn failure, SIGTERM). Four CLIs
self-acquire in their live mode and are exempt from runner-side acquisition
(`_CLI_SELF_LOCKING`): `library-clean` (`--apply`), `library-validate`
(`--fix --apply`), `library-rescrape` (non-dry-run), and `scrape-resolve`
(always live; it writes into staging). For those the runner waits on a
read-only lock probe before spawning (visibility + pacing only — the child's
claim-first-then-verify acquisition stays the sole safety authority) and
re-queues PACED when the child exits **3** (the uniform lock-busy exit code)
under the same deadline. Net effect: no two writers can run concurrently, the
wait is a first-class visible state, and `POST /pipeline/kill` still refuses
to SIGTERM a maintenance holder (its own surface owns that).

**Duplicate guard (the only 409 left).** The handler refuses only the strict
duplicate: a `pipeline_run` row with `kind='maintenance'`,
`outcome='running'`, the **same `command`**, byte-identical `options_json`
AND the same `dry_run` mode, whose PID is alive (`os.kill(pid, 0)`). A
DIFFERENT action (or the same action with different options/mode) reserves
its row and queues on the lock instead of being refused — serialization is
the lock's job, not the route's.

**Dry-run-first for destructive actions.** Actions with `risk='destructive'`
(or, more broadly, those whose `dry_run` is `'supported'` and are being
submitted with `dry_run: false`) require a **matching successful dry-run** (same
`action_id` and `options_json`, `outcome='success'`, `dry_run=1`) no older than
30 minutes. Absent or stale → `428 Precondition Required`. The frontend
enforces this synchronously: the Apply button is disabled until a matching
dry-run completes, and any edit to the form options re-locks it.

**CLI convention bridging.** Some `library-*` commands expose `--dry-run`,
others use `--apply` (where absence = dry-run). The runner's per-command
`_DRY_RUN_STYLE` table encodes the convention so the subprocess is invoked
correctly regardless.

These guarantees mean that the web UI is as safe as the terminal: every action
can be previewed, destructive actions are gated on a verified preview, and the
same lock that serialises Watcher-driven pipeline runs also serialises
maintenance actions.
