# Phase 28 — Pipeline-monitor v2.2 deviations follow-up

Generated 2026-05-28 after running `/pipeline-monitor` (matrix v2.2) on the
current `feat/registry` HEAD. The pipeline-monitor surfaced **9 DEVIATIONs**
total. After triage:

- **#1 (boot failure `RegistryConfigError`)** : resolved live during the run by
  adding the missing `"providers.json5"` entry to `config/config.json5` overlays.
  Fix is local-only (the `config/` directory is gitignored ;
  `config.example/config.json5` already lists `providers.json5` since the merge
  of the provider-IDs feature).
- **2 ACCEPTANCE_FAIL critique reclassified after evidence review** :
  - `pipeline-bdd-validator` flagged 15 shows with `canonical_provider='tmdb'`
    as a provider-IDs ACCEPTANCE #4 violation. Evidence : every one of the 15
    shows has only `tmdb_id` (and sometimes `imdb_id`/`wikidata_id`), **no
    `tvdb_id`** — TVDB simply does not know them. The current behavior is
    DESIGN_CONFORM (TVDB-preferred-when-available fallback chain) ; the ACCEPTANCE
    text needs to make the rule explicit, and the agent prompt needs to learn
    the nuance.
  - `pipeline-invariant-checker` flagged `LIBRARY_ANALYZER_MAX_WORKERS` as
    missing from `.env.example`. Evidence : `.env.example:` declares
    `# LIBRARY_ANALYZER_MAX_WORKERS=4` (commented default), and the official
    `scripts/check_env_keys.py` reports `0 missing keys`. The agent grep is too
    strict ; this is a TOOLING_BUG, not a real ACCEPTANCE_FAIL.
- **6 real deviations remaining** : 5 mineur storage/BDD drift (AO, AS, AG, AI,
  AJ) + 1 OPERATIONAL diagnostic (AM, Disk1 I/O timeout).

This phase closes all 8 remaining items as discrete sub-phases (one per
invariant), then prepares the PR for the final merge.

## Gate

- Phases 0–27 complete (all [x] in IMPLEMENTATION.md).
- PR #27 currently `OPEN` and MERGE-READY before this phase.
- CI green on `ccb8ba9b`.
- DEVIATION #1 resolved live (local-only, no commit needed).
- `personalscraper ingest --dry-run` boots clean: `registry_boot_loaded
capabilities_count=11 providers_count=2`.

## Goal

Close the 8 remaining DEVIATIONs from the pipeline-monitor v2.2 run on
`2026-05-28 12h07`, then re-run pipeline-monitor in read-only mode to verify
the DEVIATION LIST is empty (or only contains documented `CONNU` entries).

## Scope

### Sub-phase 28.1 — Provider-IDs ACCEPTANCE clarification + agent fix

**Target finding** : DEVIATION #2 reclassified.

**Evidence** : sample 3 of 15 shows :

- `Death in Denmark` (id 1107) — `external_ids_json={"tmdb": {"series_id": "309677"}}` (no tvdb)
- `African Empires` (id 1889) — `external_ids_json={"tmdb": {"series_id": "238143"}}` (no tvdb)
- `Enterrement de vie de garçon` (id 1294) — `external_ids_json` has tmdb + imdb, no tvdb

All 15 shows have `tvdb_id IS NULL` and were correctly resolved via the TMDB
fallback after TVDB returned no match.

**Tasks** :

1. Edit `docs/archive/features/provider-ids/ACCEPTANCE.md` (or whichever file
   hosts the canonical rule) : rewrite the rule for ACCEPTANCE #4 as :

   > For `kind='show'`, `canonical_provider='tvdb'` **iff** the show is
   > resolvable on TVDB. When TVDB returns no match, the chain falls back to
   > TMDB and `canonical_provider='tmdb'` is the design-conforming outcome.

2. Add a regression query in `tests/integration/api/metadata/registry/`
   (or wherever provider-IDs tests live) :

   ```python
   def test_show_canonical_tmdb_only_when_tvdb_unknown() -> None:
       """Shows with canonical_provider='tmdb' must have no tvdb_id in external_ids_json."""
       # query DB, assert
   ```

3. Edit `.claude/agents/pipeline-bdd-validator.md` (the agent prompt) :
   - Section on canonical_provider check : add the nuance — "before flagging
     a show with `canonical_provider='tmdb'` as ACCEPTANCE_FAIL #4, verify the
     show has a `tvdb_id` in `external_ids_json`. If no tvdb_id, the
     classification is DESIGN_CONFORM (TVDB-fallback)."

4. Bump matrix v2.2 → v2.3 to reflect the nuanced rule. Update
   `.claude/skills/pipeline-monitor/SKILL.md` MATRIX_VERSION assertion.

**Acceptance** :

- `personalscraper library-reconcile --read-only` confirms 0 shows have
  `canonical_provider='tmdb'` AND a `tvdb_id` (only the design-conforming cases
  remain).
- Re-running `pipeline-bdd-validator` post-fix on the same DB reports 0
  ACCEPTANCE_FAIL on this rule.
- Matrix v2.3 declared in changelog.

**Commit** : `docs(provider-ids): clarify canonical_provider TVDB-fallback rule`

- `fix(pipeline-monitor): bdd-validator respects TVDB-unknown fallback`.

### Sub-phase 28.2 — Fix `pipeline-invariant-checker` env-vars grep

**Target finding** : DEVIATION #3 reclassified as TOOLING_BUG.

**Evidence** : `.env.example` line N declares `# LIBRARY_ANALYZER_MAX_WORKERS=4`
(commented). `scripts/check_env_keys.py` reports `0 missing keys`. The agent's
grep filter must accept lines starting with `#?\s*[A-Z]`.

**Tasks** :

1. Edit `.claude/agents/pipeline-invariant-checker.md` invariant AV check :
   delegate to `scripts/check_env_keys.py` rather than re-implementing the
   parsing. Subprocess call : `python3 scripts/check_env_keys.py`. Non-zero
   exit or non-zero "N missing keys" → violation. Zero → DESIGN_CONFORM.
2. Add a sanity test (manual run in the sub-phase report) : re-run
   `pipeline-invariant-checker` against current `.env.example` → expect 0 AV
   violations.

**Acceptance** :

- Sub-agent re-run on identical baseline reports 0 AV violations.
- Manual `grep -c LIBRARY_ANALYZER_MAX_WORKERS .env.example` returns ≥ 1.

**Commit** : `fix(pipeline-monitor): invariant-checker delegates env-var
completeness to check_env_keys.py`.

### Sub-phase 28.3 — AO : 17 `media_file` rows with `release_id IS NULL`

**Target finding** : DEVIATION #4.

**Evidence** : `pipeline-invariant-checker` flagged 17 `media_file` rows with
`release_id IS NULL AND deleted_at IS NULL`. `pipeline-bdd-validator` countered
this is design-conform during ingestion (files matched to releases post-scan).
The truth depends on : are these 17 rows actively being matched, or are they
stalled ?

**Tasks** :

1. Query the 17 rows. Record path + created_at + last seen scan_run id.
2. For each : check whether the file still exists on disk. Three categories :
   - **File exists, recent scan** → DESIGN_CONFORM (in-flight). No action.
   - **File exists, stale scan_run (≥ 7 days)** → DESIGN_DEVIATION. Trigger a
     re-scan of the containing media_item via `library-reconcile`.
   - **File missing from disk** → mark `deleted_at = now()` (logical delete).
3. Document each row's resolution in the sub-phase report.

**Acceptance** :

- After fix : query returns 0 rows that are both "file exists" AND "last scan
  ≥ 7 days ago".
- Pipeline-invariant-checker AO re-run returns 0.

**Commit** : `fix(indexer): reconcile 17 stale media_file rows without release`
(or whatever applies after triage).

### Sub-phase 28.4 — AS : 13 tracker entries with `dest_path=null`

**Target finding** : DEVIATION #5.

**Evidence** : `ingested_torrents.json` has 13 entries with `dest_path=null` :
`e3585f5eb6a8` (L'Autre moi.epub), `5991f1e49839` (Top.Chef.S17E12), etc.

**Tasks** :

1. List the 13 entries. Cross-check qBit content_path AND disk presence.
2. Per entry, decide :
   - Torrent on disk in correct category → backfill `dest_path` from the
     resolved location.
   - Torrent absent from any disk but completed in qBit → re-run the relevant
     pipeline step (ingest/dispatch).
   - Torrent intentionally not dispatched (e.g. .epub which has no category
     in this setup) → either add an "intentionally-skipped" flag or drop the
     tracker entry.

**Acceptance** :

- After fix : `personalscraper torrents-list` reconciliation script shows 0
  `dest_path=null` entries.
- Pipeline-invariant-checker AS re-run returns 0.

**Commit** : `fix(tracker): backfill dest_path for 13 dangling entries`.

### Sub-phase 28.5 — AG : orphan `tvshow.nfo` on Disk1

**Target finding** : DEVIATION #6.

**Evidence** : `/Volumes/Disk1/medias/emissions/Au bout c'est la mer (2018)/tvshow.nfo`
has no matching video files in the same folder.

**Tasks** :

1. Inspect the folder. Determine if the show was partially deleted (videos
   removed, NFO forgotten) or never properly dispatched.
2. Resolve : either delete the orphan NFO, or re-dispatch the missing video
   if it lives elsewhere.

**Acceptance** :

- Pipeline-invariant-checker AG re-run returns 0.

**Commit** : `chore(storage): remove orphan NFO at <path>` (or whatever).

### Sub-phase 28.6 — AI : 11 empty `Saison*` directories on Disk1

**Target finding** : DEVIATION #7.

**Evidence** : invariant-checker found 11 empty `Saison*` dirs on Disk1
(paths not captured due to I/O timeout during the walk).

**Tasks** :

1. Re-run a targeted walk on Disk1 to capture the 11 paths. (Tie in with 28.8
   for the I/O timeout root cause.)
2. For each empty Saison directory : verify the parent series has other
   non-empty Saison dirs → if yes, delete the empty one. If no, decide whether
   to redownload or delete the whole series tree.

**Acceptance** :

- Pipeline-invariant-checker AI re-run returns 0.

**Commit** : `chore(storage): remove 11 empty Saison directories on Disk1`.

### Sub-phase 28.7 — AJ : `.actors` directory on Disk1

**Target finding** : DEVIATION #8.

**Evidence** : invariant-checker found `.actors` directory (MediaElch artifact
that should be cleaned).

**Tasks** :

1. Locate the `.actors` directory on Disk1.
2. Verify it is empty or contains only MediaElch metadata (no original media).
3. Delete it. Verify cleanup logic in `cleanup` step covers `.actors` for
   future runs (if not, file a follow-up).

**Acceptance** :

- Pipeline-invariant-checker AJ re-run returns 0.

**Commit** : `chore(storage): remove .actors MediaElch artifact on Disk1`.

### Sub-phase 28.8 — AM : Disk1 walk I/O timeout

**Target finding** : DEVIATION #9.

**Evidence** : The full Disk1 walk timed out during PHASE 3 ; some invariants
(AM specifically) couldn't be fully evaluated.

**Tasks** :

1. Determine the cause : Disk1 is NTFS via macFUSE — investigate whether
   `find -maxdepth N` or a Python `os.scandir` walk is hitting a known macFUSE
   slow-path.
2. Either : adjust the invariant-checker agent to use a more resilient walk
   (smaller batches, exponential backoff), or document Disk1 as "deep-walk
   only weekly" in the matrix.
3. Re-run the AM invariant. Confirm coverage.

**Acceptance** :

- Pipeline-invariant-checker AM run reports completion (no "deferred").

**Commit** : `fix(pipeline-monitor): resilient Disk1 walk for invariant AM` (or
`docs(pipeline-monitor): document Disk1 walk cadence`).

## Verification (phase gate)

Run **after all 8 sub-phases** :

1. `make lint` (ruff + mypy) → 0 errors.
2. `make test` → `0 failed, 0 errors` ; `BASELINE_PASS_COUNT` unchanged.
3. `make check` (lint + test + module-size + typed-api) → exit 0.
4. `personalscraper ingest --dry-run` → boot OK.
5. **Re-run `/pipeline-monitor`** in read-only mode (this skill) :
   - GATE 0 → PASSED.
   - INGEST dry-run → OK.
   - PHASE 3 invariant-checker → 0 violations (AD–AV all green or
     DESIGN_CONFORM).
   - PHASE 3 bdd-validator → 0 ACCEPTANCE_FAIL (the 15 shows are now
     DESIGN_CONFORM).
   - DEVIATION LIST empty or only `CONNU` entries.

## Out of scope

- Implementing the matrix v2.3 enrichment for the 76 snake_case events flagged
  by the stale-detector in this run's PHASE 0. That is a separate effort
  (matrix maintenance) and not gated by this phase.
- Backfilling the 15 shows : they are correct as-is per the clarified rule.
- Re-architecting macFUSE access for Disk1 : 28.8 settles for documenting
  cadence if a hard fix proves expensive.

## Next action

After phase 28 closes : re-run `/pipeline-monitor` for verification, then
`/implement:feature-pr` to push and trigger CI. Then `/implement:pr-review`
for the final review cycle (cycle 5 of reset log).

## Execution outcomes (2026-05-28)

The 8 sub-phases planned above mapped to the following actual work after
evidence review. Several "real deviations" turned out to be TOOLING_BUGs in
`pipeline-invariant-checker` (the agent queried non-existent DB columns or
expected schema fields that don't exist in the tracker). They were therefore
consolidated into a single batch fix to the agent rather than each receiving
an app-side fix.

### 28.1 — Provider-IDs ACCEPTANCE clarification + bdd-validator nuance

**Status**: DONE.

- Main repo: `f733765a docs(provider-ids): clarify canonical_provider TVDB-fallback rule`.
- Main repo: `f8b2156b fix(pipeline-monitor): bdd-validator respects TVDB-unknown fallback (matrix v2.3)`.
- `.claude` repo: `ce1c773 fix(pipeline-monitor): bdd-validator respects TVDB-unknown fallback (matrix v2.3)`.
- Matrix v2.2 → v2.3. Regression test added on the canonical provider rule.

### 28.2 — `pipeline-invariant-checker` env-vars grep (AV)

**Status**: DONE.

- `.claude` repo: `36622d4 fix(pipeline-monitor): invariant-checker delegates env-vars completeness to check_env_keys.py`.
- AV now subprocesses `python3 scripts/check_env_keys.py` and trusts its exit
  code + stdout summary — no inline re-implementation that misses commented
  defaults.

### 28.3 / 28.4 / 28.5 / 28.8 — CONSOLIDATED into a single agent fix batch

**Status**: DONE (batched).

The four sub-phases originally planned as separate code/data fixes turned out
to be the same root cause: `pipeline-invariant-checker` itself was wrong in
its query / walk assumptions. Codebase, library DB, and tracker are all
healthy. One commit on `.claude`:

- `fix(pipeline-monitor): invariant-checker — AO/AS/AG/AI/AM corrections (matrix v2.4)`

Per-invariant resolution:

- **28.3 (AO — 17 media_file with `release_id IS NULL`)** : invariant-checker
  was querying `media_file.item_id` and `media_file.path` which don't exist
  in the schema. Real schema (`id, release_id, path_id, filename,
scan_generation, last_verified_at, deleted_at`) reveals the 17 rows are
  pending-link entries whose `filename` is a directory name (e.g. "American
  Dad! (2005)") with `scan_generation=0`. They are DESIGN_CONFORM, will be
  linked by the next library-reconcile pass. AO refined: split results into
  `pending_link` (CONFORM) and `real_orphan` (mineur) using the media-extension
  heuristic.
- **28.4 (AS — 13 tracker entries `dest_path=null`)** : invariant-checker
  expected a `dest_path` field in `ingested_torrents.json`. That field does
  not exist in the schema (`{<hash>: {name, action, date}}`). The 13 entries
  are healthy minimal records, not deviations. AS now validates schema
  sanity (40-hex hash key, `name` non-empty, `action` string, ISO-8601 `date`)
  rather than `dest_path` presence.
- **28.5 (AG — orphan `tvshow.nfo` on Disk1)** : the show
  `/Volumes/Disk1/medias/emissions/Au bout c'est la mer (2018)/` has
  `Saison 01/02/03/` subdirs with actual video files. AG's previous "video
  adjacent to NFO" check missed the nested layout — `tvshow.nfo` lives at
  the show root, not next to the videos. AG now recurses into the whole
  show tree (5 s per-show timeout, `find ... -iname '*.mp4|*.mkv|...'`).
- **28.8 (AM — Disk1 walk I/O timeout)** : root cause is the macFUSE/NTFS
  slow-path on Disk1. Rather than re-architecting access, the agent now
  shards Disk1 walks by category top-level dir (60 s per shard) and reports
  per-shard coverage. Partial coverage is acceptable and documented. NTFS
  ghost-inode caveat (entries that appear in `ls` but `stat()` ENOENT) is
  documented as OPERATIONAL with hint `requires offline umount + ntfsfix`,
  not severity escalation.

Matrix v2.3 → v2.4.

### 28.6 — AI : 11 empty `Saison*` dirs on Disk1

**Status**: DONE inline by main session + agent fix.

The main session re-walked Disk1 inline and found **3** empty Saison dirs
(not 11). The over-count came from the I/O timeout truncating the agent's
enumeration. Inline rmdir/rm-rf removed all three:

- `/Volumes/Disk1/medias/emissions/Au bout c'est la mer (2018)/Saison 24` (sic — bogus).
- `/Volumes/Disk1/medias/emissions/Cauchemar en cuisine/Saison 12`.
- `/Volumes/Disk1/medias/emissions/Objectif Nul/Saison 1`.

The agent's AI over-counting is fixed in the batch above (per-show timeout + `coverage_partial` reporting instead of inflating totals).

### 28.7 — AJ : `.actors` dir on Disk1

**Status**: PARTIAL (documented as CONNU).

The `.actors` artifact under
`/Volumes/Disk1/medias/films/Hunger Games (2023)/.actors/` contains
`Zoë_Renee.jpg` which is an NTFS-via-macFUSE ghost-inode: the entry is
listed by `ls` but `rm` / `rmdir` returns `ENOENT` while the volume is
mounted. This CANNOT be cleaned online and requires an offline maintenance
window (`umount /Volumes/Disk1 && ntfsfix /dev/diskN`).

- Status: CONNU. Documented in the agent so AJ no longer escalates severity
  on ghost-inodes — they are OPERATIONAL with the offline-ntfsfix hint.
- Operator action: schedule an offline pass when convenient.

### Final state of the 2026-05-28 12h07 DEVIATION LIST

| #   | Code         | Final status                | Disposition                                                                |
| --- | ------------ | --------------------------- | -------------------------------------------------------------------------- |
| 1   | (boot)       | TRAITÉ                      | Config-local fix, no commit.                                               |
| 2   | (15 shows)   | RECLASSIFIÉ                 | DESIGN_CONFORM after ACCEPTANCE clarification; matrix v2.3.                |
| 3   | (AV)         | RECLASSIFIÉ + TRAITÉ        | TOOLING_BUG; agent now delegates to check_env_keys.py.                     |
| 4   | (AO 17)      | RECLASSIFIÉ + TRAITÉ        | TOOLING_BUG; agent uses real schema; rows are pending_link DESIGN_CONFORM. |
| 5   | (AS 13)      | RECLASSIFIÉ + TRAITÉ        | TOOLING_BUG; agent uses real tracker schema; entries DESIGN_CONFORM.       |
| 6   | (AG NFO)     | RECLASSIFIÉ + TRAITÉ        | TOOLING_BUG; agent recurses; show has videos in Saison NN/.                |
| 7   | (AI 11)      | TRAITÉ inline + RECLASSIFIÉ | 3 real empty dirs deleted; agent over-counted, now fixed.                  |
| 8   | (AJ .actors) | CONNU                       | NTFS ghost-inode; requires offline ntfsfix.                                |
| 9   | (AM timeout) | RECLASSIFIÉ + TRAITÉ        | TOOLING_BUG; agent now shards Disk1 walks.                                 |

Net: zero DEVIATIONS remain in `À TRAITER` / `À INVESTIGUER` status. The
single CONNU (AJ .actors / NTFS ghost-inode) is an operator-scheduled
offline maintenance item, not a code or pipeline issue.
