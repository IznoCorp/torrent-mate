# Phase 8 — CLI + Cron + Query Language

## Gate

**Prerequisite (Phase 7 exit gate):**

> Full `personalscraper trailers scan` run produces the same result set as v0.7 on a fixture FS.

**This phase's exit gate (verbatim from DESIGN §16):**

> README updated; CLI golden tests pass; documentation complete; all three plists install cleanly via `launchctl bootstrap` in a CI container.

---

## Scope

Complete the CLI surface (`library index|status|verify|search|repair|show` + `config migrate-to-v2`), implement the minimal flex-attr query parser, ship three launchd plist templates, and write the documentation pass (`docs/reference/indexer.md`, updates to `architecture.md` and `storage.md`). This is the finishing phase — the indexer is fully operational after Phase 7; Phase 8 adds discoverability, scheduling, and documentation.

---

## Sub-phases

### 8.1 — Complete CLI command family

**Files touched:**

- `personalscraper/indexer/cli.py` _(modify — add `verify`, `search`, `repair`, `show`; complete `index` and `status`)_
- `tests/indexer/test_cli.py` _(extend — full 14-case golden test suite)_

**Deliverable:**

All commands from DESIGN §12:

- `library index [--mode {quick|incremental|enrich|full}] [--disk DISK] [--budget SECONDS] [--dry-run] [--wait-for-lock SECONDS] [--rebuild] [--confirm-bulk-change]` — already partially implemented; complete `--dry-run` semantics (suppress all `INSERT`/`UPDATE` on `media_*` tables; write synthetic `scan_run(status='dry-run')`; `scan_event` rows still written); complete `--mode full --disk D` scoping.
  - `--rebuild` (DESIGN §17.1, corrupt DB recovery): bypasses the corrupt-DB refusal from Phase 1.1; quarantines the existing DB if any, creates a fresh one, runs full Stage-A rescan from scratch.
  - `--confirm-bulk-change` (DESIGN §17.1, disk-swap edge case): bypasses the Merkle-delta freeze from Phase 3.6 for that single invocation.

- `library status` — complete output: disk inventory, last scan time per disk, generation, mounted/unmounted, pending outbox depth, repair queue depth, deleted_item counts, Spotlight availability per disk, enrich-pending count, **category-orphan count** (DESIGN §17.2 — items with `category_id` not in current config). WARN exit if repair queue oldest > 7 days OR depth > 1 000 OR any category orphans exist.

- `library verify [--disk DISK]` — verify scan: re-stat every file, escalate to tier-2 on mismatch, no soft-delete (only marks for repair). Wraps `scan(mode='verify')`.

- `library search QUERY [--limit N]` — delegates to `indexer.query.execute(conn, query_str, limit)` (implemented in 8.2). Examples from DESIGN §12: `year:2024 disk:Disk1 -nfo:valid`, `kind:show codec:hevc -trailer`, `title:"Lost Highway"`. Outputs one row per item: `id | title | year | disk | nfo | trailer`.

- `library repair [--budget SECONDS]` — drains repair queue with custom budget. Calls `repair.drain(conn, budget)`.

- `library show ITEM_ID` — pretty-prints all stored data for one item: `media_item` fields, `season`/`episode` rows, `media_file` rows with `media_stream`, `item_attribute` rows, `deleted_item` history.

- `config migrate-to-v2 [--dry-run]` — already implemented in Phase 0; confirm it is wired into the top-level CLI entry point.

- **`config migrate-category --from OLD --to NEW`** _(new, DESIGN §17.2)_: rewrites every `media_item` row's `category_id` from `OLD` to `NEW`. The user runs this after renaming a category in `categories.json5` to clear orphan-tagged rows. Issues `UPDATE media_item SET category_id = ? WHERE category_id = ?` inside a transaction. Refuses if `NEW` is not a declared category id (looked up in current `Config.categories`). Idempotent: running twice with the same args is a no-op the second time.

**Full 14-case golden test suite** (DESIGN §15.5.2):

| Test case                                                     | Assert                                                                 |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `library index --mode quick` no changes                       | exit 0; JSON summary `{"mode":"quick","items_unchanged":N}`            |
| `library index --mode quick` 5 changed files                  | exit 0; `items_updated:5`                                              |
| `library index --mode full --disk Disk1`                      | exit 0; only Disk1 columns updated; `scan_run.disk_filter='Disk1'`     |
| `library index --mode full --disk UnknownDisk`                | exit 2; stderr `"no disk with label 'UnknownDisk'"`                    |
| `library index` while another instance holds lock             | exit 1; stderr `"indexer locked by PID <n>"`                           |
| `library index --wait-for-lock 5` lock released within budget | exit 0                                                                 |
| `library index --dry-run --mode full`                         | exit 0; summary `dry_run:true`; no `media_*` row touched               |
| `library status`                                              | exit 0; tabular output of disks, last scan, generation, queue depths   |
| `library search "year:2024 disk:Disk1 -nfo:valid"`            | exit 0; valid result rows                                              |
| `library search "field_does_not_exist:foo"`                   | exit 2; `"unknown field"`                                              |
| `library show <unknown_id>`                                   | exit 2; `"no item with id"`                                            |
| `library repair --budget 10`                                  | exit 0; drains up to 10 s; stops cleanly                               |
| `library verify --disk Disk2`                                 | exit 0; no soft-deletes; repair queue grows on tier-2 mismatches       |
| `config migrate-to-v2 --dry-run` with malformed v1            | exit 2; stderr lists offending keys; no files written                  |
| `library index --rebuild` after DB corruption                 | exit 0; quarantines old DB, runs full Stage-A scan, populates fresh DB |
| `library index --mode full --disk D --confirm-bulk-change`    | exit 0; bypasses Merkle-delta freeze; reconciles drift normally        |
| `config migrate-category --from old --to new`                 | exit 0; UPDATE issued; second run is no-op; unknown `--to` exits 2     |

**Tests added:** extend `tests/indexer/test_cli.py` to 14 cases

**Commit:** `feat(media-indexer): 8.1 complete library CLI command family`

---

### 8.2 — `indexer/query.py` flex-attr parser

**Files touched:**

- `personalscraper/indexer/query.py` _(implement — replaces stub from Phase 7)_
- `tests/indexer/test_query.py` _(new)_

**Deliverable:**

~250-LOC module (DESIGN §13) covering:

- **Tokeniser**: splits query string into `Token` objects: `field:value`, `field:value*`, `-field:value`, `field:>=N`, `field:<=N`, `field:>N`, `field:<N`, `"quoted phrase"`, bare term (title fragment).
- **`FIELD_REGISTRY`**: maps each recognised field to its column, table, and value coercion per DESIGN §13.1:
  - `kind` → `media_item.kind` (str equality)
  - `title` → `media_item.title LIKE ?` (% auto-wrapped unless quoted)
  - `year` → `media_item.year` (int, supports comparison operators)
  - `disk` → JOIN `disk.label` (str equality)
  - `category` → `media_item.category_id` (str equality)
  - `tmdb_id` → `media_item.tmdb_id` (int, comparison)
  - `imdb_id` → `media_item.imdb_id` (str equality)
  - `nfo` → `media_item.nfo_status` ∈ `{missing,invalid,valid}`
  - `codec` → EXISTS on `media_stream.codec` (video streams only)
  - `lang` → EXISTS on `media_stream.lang` (audio streams only)
  - `quality` → EXISTS on `media_release.quality`
  - Any other key → flex attribute `item_attribute(key=?, value=?)`
- **SQL fragment composer**: builds a single `WHERE` clause via `AND` conjunction (not `INTERSECT`). Negation (`-field`) compiles to `NOT (...)` / `NOT EXISTS (...)`. Bare-key flex-attr negation (`-trailer_found`) → `NOT EXISTS (... key='trailer_found')`.
- **`QueryError`**: raised for unknown fields, invalid operator on untyped flex attr, syntax errors. Message actionable: `"unknown field 'foo'; recognised fields: kind, title, year, ..."`.
- **`execute(conn, query_str, limit=50) -> list[MediaItemRow]`**: tokenise → compile → execute SQL → return rows. `find_items_without_trailer(conn)` (from Phase 7 stub) implemented here as a named query using `FIELD_REGISTRY`.
- Tests: each `FIELD_REGISTRY` path has at least one test; negation; prefix match; quoted phrase; numeric comparison; unknown field raises `QueryError`; flex-attr presence test (`-trailer_found`); numeric comparison on untyped flex attr raises `QueryError`.

**Tests added:** `tests/indexer/test_query.py`

**Commit:** `feat(media-indexer): 8.2 indexer/query.py flex-attr parser FIELD_REGISTRY`

---

### 8.3 — Three launchd plist templates

**Files touched:**

- `docs/reference/launchd/personalscraper-index-quick.plist` _(new)_
- `docs/reference/launchd/personalscraper-index-rotate.plist` _(new)_
- `docs/reference/launchd/personalscraper-index-enrich.plist` _(new)_
- `docs/reference/launchd/index-rotate.sh` _(new — shell wrapper for the rotate plist; computes today's disk via `date +%u`)_
- `tests/indexer/test_plists.py` _(new — Linux-safe `plistlib` validation)_

**Deliverable:**

Per DESIGN §14:

- `personalscraper-index-quick.plist` — runs `personalscraper library index --mode quick --wait-for-lock 0` every night at 03:30. `StandardOutPath`/`StandardErrorPath` → `__logit__/index.YYYY-MM-DD.log`. `RunAtLoad false`. `StartCalendarInterval` `{Hour:3,Minute:30}`.

- `personalscraper-index-rotate.plist` — runs `personalscraper library index --mode full --disk DiskN --wait-for-lock 0` once per night rotating across disks (Mon=Disk1, Tue=Disk2, Wed=Disk3, Thu=Disk4; Fri/Sat/Sun fall back to `quick`). Implemented via a shell wrapper script `docs/reference/launchd/index-rotate.sh` called from the plist (the rotation logic cannot be expressed in a plist directly).

- `personalscraper-index-enrich.plist` _(optional)_ — runs `personalscraper library index --mode enrich --budget 1800 --wait-for-lock 0` weekly (Sunday 04:00).

All three plists use `Label` `com.personalscraper.index-{quick|rotate|enrich}`. All are opt-in (manual `launchctl bootstrap` — not auto-installed by any setup script).

Installation instructions in `docs/reference/indexer.md` (8.4).

**Tests added:** Static-validation test (Linux-safe, runs on every CI): each plist is parsed via `plistlib.loads(path.read_bytes())` and asserted for required keys (`Label`, `ProgramArguments`, `StandardOutPath`, `StandardErrorPath`, `StartCalendarInterval`). Optional macOS-only smoke test: `launchctl bootstrap gui/$(id -u) <plist>` + `launchctl bootout` succeeds — gated by `@pytest.mark.darwin_only` (registered in `tests/conftest.py`); skipped on Linux runners. The Phase exit gate accepts either macOS smoke or Linux static-validation as proof of "plists install cleanly", since the project does not currently provide a macOS CI runner.

**Commit:** `chore(media-indexer): 8.3 launchd plist templates and rotate shell wrapper for nightly index cron`

---

### 8.4 — Documentation pass

**Files touched:**

- `docs/reference/indexer.md` _(new)_
- `docs/reference/indexer-json-shapes.md` _(new — DESIGN §6.5 commitment)_
- `docs/reference/architecture.md` _(modify — add indexer subsystem to module map)_
- `docs/reference/storage.md` _(modify — confirm mount flags section from Phase 4 is complete; add cold-rebuild playbook)_
- `README.md` _(modify — update feature list, add `brew install media-info` system dep)_
- `CLAUDE.md` _(modify — add `docs/reference/indexer.md` row to reference index table)_

**Deliverable:**

`docs/reference/indexer.md` covers:

- Schema overview (table descriptions, not the full DDL — cross-reference DESIGN §6.2).
- Drift policy: N-strikes, soft-delete, repair queue, OSHash collision handling.
- Scan modes table (from DESIGN §11.1): `quick`/`incremental`/`enrich`/`full` — what each reads, typical use.
- Query language: token syntax, field list, examples.
- Cold-rebuild playbook: step-by-step for a fresh install or full rebuild after disk replacement.
- Cron setup: how to install the three plists.
- Failure recovery: corrupted DB quarantine + `--rebuild`; stale lock recovery; partial migration recovery.

`docs/reference/indexer-json-shapes.md` covers the canonical shape (and pydantic model name) for every JSON column listed in DESIGN §6.5: `media_item.artwork_json`, `index_outbox.payload_json` (per `op` value), `pending_op.payload_json`, `repair_queue.payload_json`, `scan_run.stats_json`, `scan_event.payload_json`, `deleted_item.payload_json`. One section per column with a JSON example + the pydantic class definition reference.

`docs/reference/architecture.md` update: add `personalscraper/indexer/` to the module map with one-line descriptions per file, add `tests/indexer/`, `tests/integration/`, `tests/conf/`, `tests/e2e/perf/` to the test layout.

**Tests added:** None (doc-only).

**Commit:** `docs(media-indexer): 8.4 indexer reference docs architecture and storage updates`

---

## Acceptance criteria

- [ ] `pytest tests/indexer/test_cli.py` passes all 17 golden cases (14 from §15.5.2 + 3 new for `--rebuild`/`--confirm-bulk-change`/`migrate-category`).
- [ ] `pytest tests/indexer/test_query.py` passes — all `FIELD_REGISTRY` paths covered.
- [ ] `personalscraper library search "year:2024 disk:Disk1 -nfo:valid"` returns correct rows on seeded DB.
- [ ] `personalscraper library search "field_does_not_exist:foo"` exits 2 with `"unknown field"` in stderr.
- [ ] `personalscraper library status` exits 0 with tabular disk + queue output; exits non-zero when repair queue > 7 days old or category orphans exist.
- [ ] `personalscraper library verify --disk Disk2` exits 0; repair queue grows on tier-2 mismatch; no soft-deletes.
- [ ] `personalscraper library show <id>` prints all stored data; exits 2 for unknown id.
- [ ] `personalscraper library repair --budget 10` stops within budget + 5 s.
- [ ] `personalscraper library index --rebuild` quarantines a corrupt DB and runs full Stage-A scan to populate a fresh DB.
- [ ] `personalscraper library index --confirm-bulk-change --disk D` bypasses Merkle-delta freeze.
- [ ] `personalscraper config migrate-category --from old --to new` updates `media_item.category_id`; second run is a no-op; unknown `--to` exits 2.
- [ ] All three plists pass static `plistlib.loads` validation on Linux CI.
- [ ] On macOS runner (when available): `launchctl bootstrap` + `launchctl bootout` succeed for all three plists.
- [ ] `docs/reference/indexer.md` exists and covers all six sections listed above.
- [ ] `docs/reference/indexer-json-shapes.md` exists and documents every JSON column from DESIGN §6.5.
- [ ] `CLAUDE.md` reference index table has rows for `docs/reference/indexer.md` and `docs/reference/indexer-json-shapes.md`.
- [ ] `README.md` lists `brew install media-info` as a system dependency.
- [ ] `pytest` (full suite) passes — zero regressions introduced in this phase.

---

## DESIGN cross-references

Implements: §12 (CLI surface — all six commands + config migrate-to-v2), §13 (query language tokeniser + registry), §13.1 (field→table mapping, flex-attr coercion, negation compilation), §14 (cron/scheduling — three plist templates + rotation logic), §15.5.2 (CLI golden tests — 14 cases), §17.1 (`--dry-run` semantics: suppresses media\_\* mutations, writes synthetic scan_run).

---

## Out of scope for this phase

- `enzyme`/`mutagen` container fast-path — V1.1 (DESIGN §17.3).
- `getattrlistbulk` ctypes wrapper — V1.1 (DESIGN §17.3).
- Watchdog on staging APFS dir — V1.x (DESIGN §17.3).
- Web UI consuming the indexer — out of scope (DESIGN §3).
- Multi-process safe writer — V1.x (DESIGN §17.3).
- Litestream offsite replication — out of scope (DESIGN §3).
