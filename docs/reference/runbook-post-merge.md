# Post-Merge Runbook

Operator checklist for actions required after merging a feature that touches the
database schema, configuration layout, or CLI surface. Each section maps to a
feature or version milestone.

Automated quality gates (`make check`) verify code correctness but cannot
exercise live state (real DB, real API calls, real filesystem). This runbook
covers the **manual steps** that must follow every merge.

---

## How to use this runbook

1. Identify the feature just merged (version label or codename).
2. Execute **every numbered step** in the corresponding section in order.
3. If a step fails: stop, diagnose, create a fix sub-phase — do not skip forward.
4. Mark each step ✅ in your notes; do not rely on memory across steps.

**Dry-run first rule**: any `personalscraper` mutating command must be run with
`--dry-run` first, output reviewed, then re-run without the flag.

---

## Indexer / provider-ids merge checklist

This is the canonical checklist for any feature that touches the indexer DB
schema, the `canonical_provider` / `external_ids_json` columns, or the
cross-provider backfill pipeline. The steps below were first written for the
tech-debt 0.16.0 merge (archived at `docs/archive/features/tech-debt/`); they
remain the reference procedure for the indexer/backfill surface.

For a freshly merged feature, also consult the current feature's
`docs/features/<codename>/ACCEPTANCE.md` (if present) for any feature-specific
criteria, and re-exercise those in addition to the generic steps here.

### Prerequisites

```bash
cd /Users/izno/dev/PersonnalScaper
git log --oneline -1   # confirm merge commit is on main
python -c "import personalscraper"   # exit 0 — smoke test
make check             # exit 0 — lint + test + module-size + typed-api guardrails
```

---

### Step 1 — Database integrity baseline

Run before any migration or write command.

```bash
sqlite3 .data/library.db "PRAGMA integrity_check;"
# Expected: ok

sqlite3 .data/library.db "PRAGMA foreign_keys;"
# Expected: 1  (activated at boot by open_db() since Phase 1.2)

sqlite3 .data/library.db "PRAGMA foreign_key_check;"
# Expected: zero rows (no FK violations)

sqlite3 .data/library.db "SELECT version FROM schema_version ORDER BY version;"
# Expected: 1, 2, 3, 4, 5, 6
# If 3 is missing: Phase 1.5 migration did not run — see step 2.
```

---

### Step 2 — Apply schema migrations (if not auto-applied at boot)

Migrations run automatically when the DB is opened by `open_db()`. Verify they
completed:

```bash
sqlite3 .data/library.db "PRAGMA user_version;"
# Expected: 6  (matches highest migration number)

sqlite3 .data/library.db "SELECT version FROM schema_version ORDER BY version;"
# Expected: 1, 2, 3, 4, 5, 6
```

If `user_version` is below 6, or `schema_version` is missing a row, open the
DB manually to trigger migration:

```bash
personalscraper library-status
# Forces open_db() → migrations auto-apply
sqlite3 .data/library.db "PRAGMA user_version;"   # recheck
```

---

### Step 3 — FK orphan check (post-migration)

Run after migrations to confirm no orphan rows were introduced.

```bash
sqlite3 .data/library.db "PRAGMA foreign_key_check;"
# Expected: zero rows
```

If rows are returned, **stop** — do not proceed. The DB has referential
integrity violations. Investigate with:

```bash
sqlite3 .data/library.db "PRAGMA foreign_key_check;" | head -20
# Format: (table, row_id, parent_table, fk_index)
```

---

### Step 4 — Verify CLI surface

Confirm every new command added in 0.16.0 is present and responsive.

```bash
# Library maintenance commands
personalscraper library-scan --help              # exit 0 (DEV #16)
personalscraper library-gc --help               # exit 0 (SH-7)
personalscraper library-doctor --help           # exit 0 (SH-8)

# Dry-run flags on mutators
personalscraper library-repair --dry-run --help   # exit 0 (DEV #21)
personalscraper library-relink --dry-run --help   # exit 0 (DEV #21)
personalscraper library-clean --dry-run --help    # exit 0 (DEV #21)
personalscraper init-config --dry-run --help      # exit 0 (DEV #21)

# Run pipeline help includes all steps
personalscraper run --help | grep -E "enforce|trailers"
# Expected: both keywords present (DEV #7)

# init-canonical bootstrap command
personalscraper library init-canonical --help   # exit 0 (DEV #54)
```

---

### Step 5 — Health check

Run `library-doctor` to confirm the database is in a healthy state.

```bash
personalscraper library-doctor
# Expected: exit 0, all checks green
```

If any check is red, `library-doctor` exits non-zero and prints which check
failed. Address each failure before proceeding.

---

### Step 6 — Library reconcile baseline

Establish the post-merge reconciliation baseline. Compare to the known
pre-merge baselines:

| Metric                  | Expected post-0.16.0 merge     |
| ----------------------- | ------------------------------ |
| `merkle_drift`          | `[]` (empty)                   |
| `dispatch_path_missing` | `0`                            |
| `enrich_stale`          | `0`                            |
| `release_orphans`       | `0`                            |
| `items_without_files`   | `0`                            |
| `files_without_release` | ≤ 5,376 (legit sidecars only)  |
| `season_count_drift`    | ≤ 3 (known pre-existing delta) |

```bash
personalscraper library-reconcile
# Review JSON output; merkle_drift must be []
```

If `merkle_drift` is non-empty, run a full index scan:

```bash
personalscraper library-index --mode full --dry-run
# Review plan output
personalscraper library-index --mode full
```

---

### Step 7 — Garbage-collect stale outbox rows (library-gc)

Remove `index_outbox` rows that are older than 30 days and already processed.

```bash
# Dry-run first
personalscraper library-gc --older-than-days 30 --dry-run
# Review count logged

# Real run
personalscraper library-gc --older-than-days 30
```

---

### Step 8 — init-canonical bootstrap (DEV #54 / Plan A prerequisite)

This step populates `canonical_provider` from existing NFO files. It is
required before running `backfill-ids`. Skip if already run on this instance.

```bash
# Verify current state
sqlite3 .data/library.db \
  "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NOT NULL;"
# If > 0: already bootstrapped, skip to step 9.

# Dry-run first
personalscraper library init-canonical --dry-run
# Shows which items would be populated

# Real run
personalscraper library init-canonical
# Populates canonical_provider from NFOs

# Verify
sqlite3 .data/library.db \
  "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NOT NULL;"
# Expected: > 0 (depends on NFO coverage)
```

---

### Step 9 — Plan A: backfill external IDs (DEV #27)

This is the provider-ids ACCEPTANCE #3 closure step. Requires `canonical_provider`
populated (step 8) and the API credentials from `.env` (`TMDB_API_KEY`,
`TVDB_API_KEY`, `OMDB_API_KEY`). Estimated duration: 1–2 hours (API rate limiting).

The backfill is its own top-level command, **not** a `library-index` mode
(`library-index` modes are `full`, `quick`, `incremental`, `enrich`). The command
walks every `media_item` row (or one show with `--show`), merges missing
cross-provider IDs and multi-source ratings additively, and prints a JSON summary.

```bash
# Verify prerequisite
sqlite3 .data/library.db \
  "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL;"
# Expected: near 0 (items without NFOs will stay NULL — acceptable)

# Dry-run first (read-only — no DB writes, only logs projected actions)
personalscraper library-backfill-ids --dry-run
# Review the JSON summary (items_scanned / items_updated / ids_added_count / ...)

# Real run (long — do not background; use timeout=600000 if via Claude)
personalscraper library-backfill-ids
# Optional scoping: --show "<title>", --ids-only, or --ratings-only

# Verify outcome
sqlite3 .data/library.db \
  "SELECT COUNT(*) FROM media_item WHERE external_ids_json != '{}';"
# Expected: > 90% of total items

personalscraper library-doctor | grep "canonical_provider populated"
# Expected: > 90%
```

---

### Step 10 — ACCEPTANCE re-exercise

Re-run the executable ACCEPTANCE criteria for the merged feature. For a feature
with a live `docs/features/<codename>/ACCEPTANCE.md`, run each `ACC-NN` command
in order and compare to its `Expected:` annotation (see
`docs/reference/feature-lifecycle.md` §3 for the re-exercise protocol).

For the indexer/provider-ids surface, the criteria that must still hold post-merge
include:

```bash
# Monolithic Protocols are gone
rg "^class MetadataProvider\b|^class TorrentClientFull\b" personalscraper/ --type py
# Expected: zero matches

# Atomic Protocol tests
make test -k "test_metadata_client_supports"

# Pydantic ratings boundary
make test -k test_scraper_uses_externalids_pydantic

# library-gc + library-doctor present and healthy
personalscraper library-gc --help && personalscraper library-doctor --help
personalscraper library-doctor   # exit 0 on healthy DB
```

If the current feature ships an executable acceptance script under
`docs/features/<codename>/`, run it; otherwise iterate the `ACC-NN` criteria by
hand. There is no repo-wide acceptance-check script — re-exercise is per-feature.

---

### Step 11 — Install launchd cron for weekly backfill-ids (SH-3)

Required to keep `external_ids_json` current as new items are indexed.

The plist invokes `personalscraper library-backfill-ids` every Sunday at 03:00.
Before installing, edit the copied plist to replace the `REPLACE_ME` placeholder
in the working-directory and log paths with the real home directory (see
`launchd-plists/README.md`).

```bash
ls launchd-plists/ | grep "backfill-ids"
# Expected: com.personalscraper.backfill-ids.plist

cp launchd-plists/com.personalscraper.backfill-ids.plist \
   ~/Library/LaunchAgents/
# Edit ~/Library/LaunchAgents/com.personalscraper.backfill-ids.plist:
# replace REPLACE_ME in WorkingDirectory and log paths with your home dir.
launchctl bootstrap gui/$(id -u) \
   ~/Library/LaunchAgents/com.personalscraper.backfill-ids.plist

# Verify loaded
launchctl list | grep "backfill-ids"
# Expected: one line, exit status 0
```

---

### Step 12 — Final library-doctor confirmation

Re-run after all steps above to confirm the system is clean.

```bash
personalscraper library-doctor
# Expected: exit 0, all checks green
```

---

## Generic post-merge checklist (any feature)

Use this checklist for features not listed above. Adapt each step to the
specific changes in the feature.

### Schema changes

If the feature adds a migration:

1. Verify `PRAGMA user_version` matches the expected new version.
2. Run `PRAGMA foreign_key_check;` — zero rows required.
3. Confirm `schema_version` table has the new version row.
4. Run `personalscraper library-doctor` — exit 0.
5. Run `personalscraper library-reconcile` — compare to pre-merge baseline.

### Configuration changes

If the feature adds or renames config keys:

1. Run `personalscraper init-config --dry-run` and review delta.
2. Manually merge new keys into `config/` (or re-run `init-config --force`
   with backup if the change is structural).
3. Run `personalscraper info` — exit 0 with correct version shown.

### CLI additions or renames

If the feature adds commands or changes flags:

1. Run `--help` on every new command — exit 0.
2. Run `python3 scripts/audit-cli-coverage.py` — exit 0 (each command has
   a `commands.md` entry).
3. If a command was renamed with a deprecation alias, confirm the old command
   still works and emits a deprecation warning.

### Monitoring

After any merge that changes the pipeline steps or event catalog:

1. Verify the matrix version in `.claude/skills/pipeline-monitor/SKILL.md`
   matches the current matrix file.
2. Run a dry-run pipeline pass:
   ```bash
   personalscraper run --dry-run
   ```
   Confirm all expected steps appear in output.

---

## Rollback procedure

If any step above fails and cannot be resolved in-place:

1. **Stop** — do not run further mutating commands.
2. Identify the last known-good DB backup in `.data/`:
   ```bash
   ls -lt .data/*.bak* | head -10
   ```
3. Restore the backup:
   ```bash
   cp .data/library.db .data/library.db.rollback-$(date +%Y%m%d)
   cp .data/library.db.bak.<name> .data/library.db
   ```
4. Re-run `PRAGMA integrity_check` and `PRAGMA foreign_key_check` on the
   restored file.
5. Open a fix sub-phase in the relevant feature plan before retrying.

---

## See also

- `docs/reference/indexer.md` — DB schema, drift policy, scan modes
- `docs/reference/commands.md` — full CLI reference
- `docs/reference/feature-lifecycle.md` — ACCEPTANCE format and re-exercise protocol
- `docs/features/<codename>/ACCEPTANCE.md` — per-feature executable criteria (when a feature is active)
- `docs/archive/features/tech-debt/ACCEPTANCE.md` — archived 0.16.0 criteria (historical)
- `docs/reference/storage.md` — disk layout, rsync flags, NTFS/macFUSE notes
