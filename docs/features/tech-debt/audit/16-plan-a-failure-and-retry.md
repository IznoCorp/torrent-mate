# Audit — Plan A failure + retry runbook (DEV #27, #54)

> **Sub-phase**: 8.10 (phase-08-polish.md)
> **Acceptance criterion**: ACC-34
> **Date**: 2026-05-24
> **Baseline SHA**: addab31035ee23ab53b97c1b58472f71fdb6771e

## TL;DR

Plan A (`library-backfill-ids`) was launched 2026-05-23 10:16 by the operator per the
phase-01 post-commit action. It **failed immediately** because the wrong CLI was invoked:
`library-index --mode backfill-ids` instead of `library-backfill-ids`. This is the same
plan-drift root cause as §8.1: the plan body originally specified the wrong command.

The correct command (`personalscraper library-backfill-ids`) is verified present and
ready. This audit documents the failure, captures current DB coverage stats, and
provides a 5-step retry runbook for the operator.

## 1. Failure timeline

| Event             | Timestamp           | Detail                                                                         |
| ----------------- | ------------------- | ------------------------------------------------------------------------------ |
| Plan A launch     | 2026-05-23 10:16:40 | `nohup personalscraper library-index --mode backfill-ids --no-budget ...`      |
| Immediate failure | 2026-05-23 10:16:40 | `Invalid mode 'backfill-ids'. Valid: quick, incremental, enrich, full, verify` |
| PID               | 41931               | Process exited immediately, no retry attempted                                 |

Evidence: `.data/plan-a-backfill.log` (3 lines total) + `.data/plan-a-backfill.pid` ("41931\n").

### Root cause

**Plan-drift propagation from §8.1 audit**. The original plan (§8.10, pre-audit) specified:

```
personalscraper library-index --mode backfill-ids --budget-seconds 1800
```

Three errors in that invocation:

1. `library-index` has no `backfill-ids` mode — valid modes: `quick`, `incremental`, `enrich`, `full`, `verify`
2. No `--no-budget` / `--budget-seconds` flag exists on any `personalscraper` command
3. The dedicated command is `library-backfill-ids` (shipped commit `7391529`, Phase 2.6)

This is the **same class of drift** caught in §8.1 (launchd plist) — the plan body used
fictional CLI flags. The launchd plist was corrected in `5426826` (Phase 8.1), but the
operator's manual launch followed the **original** §8.10 plan text, which still contained
the incorrect invocation at launch time.

The operator launched Plan A between Phase 1.9 and 1.10 (per phase-01 post-commit action),
before the Phase 8 plan corrections were applied.

## 2. Current coverage stats (2026-05-24)

### 2.1 Queries + results

```bash
sqlite3 .data/library.db "SELECT COUNT(*) AS total FROM media_item;"
# 1937

sqlite3 .data/library.db "SELECT COUNT(*) AS empty_ext_ids FROM media_item WHERE external_ids_json = '{}';"
# 1935  (99.9% empty)

sqlite3 .data/library.db "SELECT COUNT(*) AS null_canonical FROM media_item WHERE canonical_provider IS NULL;"
# 395  (20.4% NULL)

sqlite3 .data/library.db "SELECT canonical_provider, COUNT(*) AS cnt FROM media_item GROUP BY canonical_provider ORDER BY cnt DESC;"
# tmdb|1304
# |395
# tvdb|238
```

### 2.2 Analysis

| Metric                       | Value        | Target (ACC-34) |
| ---------------------------- | ------------ | --------------- |
| Total `media_item`           | 1937         | —               |
| `external_ids_json = '{}'`   | 1935 (99.9%) | < 10%           |
| `canonical_provider IS NULL` | 395 (20.4%)  | < 10%           |
| `canonical_provider = tmdb`  | 1304 (67.3%) | —               |
| `canonical_provider = tvdb`  | 238 (12.3%)  | —               |

The 1304 tmdb + 238 tvdb rows were populated by `library-init-canonical` (Phase 1.9,
commit `224eaea` + `c83888d`). The 395 NULL rows are items without a resolvable
canonical provider from the NFO bootstrap — these need the full cross-provider walk
that `library-backfill-ids` performs.

The `init_canonical` fix shipped in Phase 5.12 (BDD-3, commit `3df78e0`) improved
the fallback path (imdb → tmdb sibling), so a re-run of `init-canonical` would likely
reduce the 395 NULL rows further. However, the proper fix is the Plan A retry.

## 3. Retry runbook (operator action)

### Step 1: Verify the correct command

```bash
personalscraper library-backfill-ids --help
```

Expected: exit 0, lists `--dry-run`, `--ids-only`, `--ratings-only`, `--show`, `--config`.
The command was shipped in Phase 2.6 (commit `7391529`) and is verified present on
the current branch.

**Note**: There is no `--budget-seconds` or `--no-budget` flag. The backfill is
naturally bounded by the number of remaining rows with empty IDs plus API rate limits.
The operator can re-run it idempotently — already-populated rows are skipped.

### Step 2: Backup

```bash
cp .data/library.db .data/library.db.bak.plan-a-retry-2026-05-24
```

### Step 3: Foreground retry with log

```bash
personalscraper library-backfill-ids 2>&1 | tee .data/plan-a-backfill-retry.log
```

The command walks every `media_item` row, detects missing provider IDs and ratings,
fetches from TMDB / TVDB / IMDb (via OMDb) / Rotten Tomatoes (via OMDb), and merges
additively — never overwriting already-present values.

Prerequisites (already met):

- `canonical_provider` seeded by `init-canonical` (Phase 1.9) — 1542/1937 rows have a value
- API credentials in `.env`: `TMDB_API_KEY`, `TVDB_API_KEY`, `OMDB_API_KEY`

If the operator only wants IDs (not ratings), add `--ids-only`. If only ratings,
`--ratings-only`. Both can be run separately.

### Step 4: Post-run measurement

```bash
sqlite3 .data/library.db "SELECT COUNT(*) AS empty_ext_ids FROM media_item WHERE external_ids_json = '{}';"
# Expected: < 194 (10% of 1937), ideally 0-10

sqlite3 .data/library.db "SELECT COUNT(*) AS null_canonical FROM media_item WHERE canonical_provider IS NULL;"
# Expected: < 194 (10% of 1937), ideally 0-10

personalscraper library-doctor | grep "canonical_provider populated"
# Expected: > 90%
```

Target: `canonical_provider populated > 90%` (ACC-34 threshold).

### Step 5: If incomplete (rate-limited, partial, or persistent failures)

**If rate-limited / partial** (< 90% canonical_provider after first run):

- Simply re-run `personalscraper library-backfill-ids` — it's idempotent and skips
  already-populated rows.
- Consider running with `--ids-only` first (faster, no OMDb calls), then `--ratings-only`
  separately.

**If persistent failures** (same items fail every retry):

- Escalate to `library-rescrape` with a focused filter:
  ```bash
  personalscraper library-rescrape --apply --filter "canonical_provider IS NULL"
  ```
  This performs a full TMDB scrape for items without a canonical provider. It is
  significantly slower than `library-backfill-ids` because it hits the TMDB search
  API per item, but can resolve items where the backfill path fails (e.g. items
  with no NFO uniqueid at all, or items whose NFO IDs don't resolve to a TMDB/TVDB
  cross-reference).

**If still below threshold after rescrape**: the remaining items truly lack resolvable
cross-provider metadata. Flag in a follow-up issue for manual triage. ACC-34 threshold
uses "> 90%" rather than 100% specifically to account for this class of items.

## 4. Acceptance link

This document constitutes the audit portion of **ACC-34** (Plan A reset+rescrape executed).

**ACC-34 closure condition**: `canonical_provider populated > 90%` measured by
`personalscraper library-doctor` after the operator completes the retry runbook above.

Current state: 🟡 PARTIAL — audit done, runbook ready, operator action pending.

## 5. Cross-references

- **Phase 1.9 post-commit action** (phase-01-foundations.md, § "Post-commit action") —
  the spec that instructed the operator to launch Plan A in background
- **Phase 2.6** (phase-02-cli-gaps.md) — shipped `library-backfill-ids` CLI (commit `7391529`)
- **Phase 8.1** (phase-08-polish.md §8.1) — same plan-drift root cause (fictional CLI flags),
  corrected in commit `5426826` for the launchd plist
- **Phase 8.10** (phase-08-polish.md §8.10) — this sub-phase
- **ACC-34** (ACCEPTANCE.md) — the criterion this audit serves
- **DEV #27** — Plan A executed (tracked by this retry)
- **DEV #54** — chicken-and-egg unblocked by `init-canonical`
- **BDD-3** (commit `3df78e0`, Phase 5.12) — `init_canonical` imdb→tmdb fallback fix,
  which will improve the baseline for a re-run of `init-canonical` before backfill
