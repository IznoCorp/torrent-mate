# Design — Tech-Debt (Global Cross-Feature Fixes)

**Codename** : `tech-debt`
**SemVer** : PATCH (0.15.0 → 0.15.1)
**Branch target** : `fix/tech-debt`
**Date** : 2026-05-21
**Status** : Design proposed — pending validation before `/implement:plan`

## 0. Origin

This feature is a **global cross-feature cleanup** triggered immediately after `feat/provider-ids` (merged into `main` at SHA `db106ac`). During the `/pipeline-monitor` run executed at the end of that PR's lifecycle, a wide-sweep audit of the _entire_ codebase + design surfaced gaps across **multiple previous features** — not just provider-ids. The audit examined:

- `feat/provider-ids` end-state (multi-provider IDs + capability composition)
- `feat/event-bus` (v0.14.0) integration boundaries
- `feat/api-unify` (v0.11.0) Protocol decomposition follow-through
- `feat/pipeline-obs` (v0.13.0) observer surface
- Pre-existing tech debt accumulated across all features (module size, exception handling, test infrastructure)

The audit report is at `docs/pipeline-runs/2026-05-18-20h23-audit-report.md`. This DESIGN consolidates the cross-feature findings into a single PATCH release.

## 1. Problem Statement

The audit revealed two systemic patterns the codebase must address before any new feature ships :

### Pattern A — ACCEPTANCE drift (provider-ids residue)

`feat/provider-ids` claimed delivery of several items via ACCEPTANCE.md ticks (✅) that the code does not actually implement :

1. **Library rescraper drops episode IDs** — the original DEV #2 bug (empty `<uniqueid>` on episode NFOs) was fixed in `tv_service.scrape_tvshow`'s drift path, but the SAME structural bug lives in `library/rescraper._rescrape_episodes`. Operators invoking the library-rescraper CLI silently regress on every show.
2. **CLI `backfill-ids` missing** — ACCEPTANCE #3 promises `personalscraper indexer --backfill-ids` ; the driver function exists but no Typer command exposes it.
3. **Monolithic Protocols not removed** — ACCEPTANCE #6 + DESIGN §4 claim `MetadataProvider` and `TorrentClientFull` are gone ; they're still alive and tested.
4. **Library scanner orphan rows** — dispatch inserts items with empty `external_ids_json` ; no auto-trigger to backfill them after scrape lands.
5. **Migration concurrent-apply race** — `personalscraper library-index` aborts with `idx_stream_kind_codec already exists` on multi-disk libraries (3+ workers). Predates provider-ids — likely from api-unify era.
6. **`.env.example` drift** — 5 env vars (`OMDB_API_KEY`, `LACALE_API_KEY`, `TRAKT_CLIENT_ID`, `TRANSMISSION_*`, `LIBRARY_ANALYZER_MAX_WORKERS`) are read by the code but missing from the template. Spans multiple features.

### Pattern B — Cross-feature tech debt accumulated across multiple releases

The audit also surfaced systemic debt the codebase has carried for several versions :

- **Module-size violations** (advisory in 0.9.0, was due for hard-block at 0.10.0 — we're now at 0.15.0, **5 versions overdue**). `scraper/tv_service.py` 986 LOC, `scraper/existing_validator.py` 888 LOC, plus 4 others within 50–200 LOC of the threshold.
- **44 unjustified `except Exception`** (out of 99 total) in `library/rescraper.py`, `scraper/movie_service.py`, `scraper/tv_service.py`, `process/run.py`, `ingest/ingest.py`. Each one is a potential silent failure.
- **Pipeline integration-test gap** : every bug found in the audit had >90% line coverage of the affected files but no E2E test that ran the pipeline phases in sequence against a realistic on-disk fixture. The pattern is systemic.
- **`library/recommender.py` still on legacy flat IDs** : the last caller outside compat shims still using the pre-migration-005 `(tmdb_id, imdb_id)` tuple shape.
- **Mock realism debt** : 779 raw `MagicMock()` vs 25 `MagicMock(spec=Class)` (~31× ratio) — most integration tests use specless mocks, hiding API drift.
- **Documentation references to retired versions** : `docs/reference/architecture.md`, `c411-api.md`, `lacale-api.md`, `event-bus.md` still mention "api-unify Phase 18/20" / "pre-0.13" historical artifacts.
- **`/implement:pr-review` doc inconsistency** : CLAUDE.md says "max-3 fix cycles" ; the skill file says "max 5". Process drift.

Addressing both patterns in the same PATCH avoids duplicating the audit cycle. The findings interlock — fixing one without the others would leave the codebase in an intermediate state where some claims hold and others don't.

## 2. Scope

### In-scope

- **Bug fixes** : the 6 critical findings (C1-C6) above
- **Design vs reality reconciliation** : delete or document the monolithic Protocols ; truth-up ACCEPTANCE.md
- **Tech debt** : module-size splits, exception-handling narrowing, integration-test scaffold
- **Polish** : docstring sweep, env var docs, retired-version refs cleanup

### Out of scope

- New features
- New providers / trackers / notify channels
- Major refactors (event-bus changes, transport rework, etc.)
- Anything requiring a MINOR or MAJOR bump

### Why a single PR (not split)

The findings share a common root cause : ACCEPTANCE.md became a "phases gated" report instead of a feature-completeness report. Splitting the fixes across multiple PRs would re-create the same problem — each PR would close some claims and leave others. One PR with a verifiable final ACCEPTANCE pass restores trust in the document.

## 3. Findings Detail

### C1 — Library rescraper drops episode IDs (DEV #2 regression vector)

**File** : `personalscraper/library/rescraper.py:419-425` (`_rescrape_episodes`)

**Symptom** : After `_rescrape_episodes` rebuilds `all_episodes` with only `{title, still_path}` and calls `match_episode_files` + `rename_episodes`, the sibling NFOs are never regenerated. They keep their pre-feature empty-uniqueid form.

**Fix** : after `rename_episodes`, call the same `_generate_episode_nfos` helper (or its library-side equivalent) with the full episode payload that carries `external_ids` from the TVDB/TMDB season response.

**Regression test** : mirror `tests/scraper/test_regression_dev2_episode_ids.py` but invoke `library.rescraper.run_rescrape()` on a fixture show. Assert that post-rescrape every episode NFO has the canonical `<uniqueid>`.

### C2 — `personalscraper indexer backfill-ids` CLI missing

**File** : `personalscraper/commands/library/` (new subcommand)

**Wiring** : `personalscraper/indexer/scanner/_modes/backfill_ids.py` already exports `run_backfill_ids(conn, *, event_bus, imdb_client, rt_client, tmdb_client, tvdb_client, show_filter, ids_only, ratings_only, dry_run)`. The follow-up adds a Typer command that :

1. Loads the config + DB + clients
2. Builds the EventBus
3. Calls `run_backfill_ids` with CLI flags mapped 1:1
4. Renders the `BackfillStats` summary

**CLI shape** :

```bash
personalscraper indexer backfill-ids [--show TITLE] [--ids-only|--ratings-only] [--dry-run]
```

### C3 — Monolithic Protocols not removed

**Files** :

- `personalscraper/api/metadata/_base.py:267` (`class MetadataProvider(Protocol)`)
- `personalscraper/api/torrent/_contracts.py:124` (`class TorrentClientFull(Protocol)`)

**Decision required** :

- **Option A — Drop them**. Update `tests/unit/test_api_metadata_base.py`, the factory in `api/torrent/_factory.py` (returns `TorrentClientFull`), and any external caller (`scraper/` mostly). High blast radius, restores design conformity.
- **Option B — Keep as compat shims**. Amend DESIGN §4 to call them "umbrella Protocols retained for callers that compose all atomic capabilities". Update ACCEPTANCE #6 to acknowledge. Stale module docstrings cleaned.

**Recommendation** : Option B (lower risk for a PATCH). Document the boundary clearly so future readers don't think it's incomplete migration.

### C4 — Drift validator dead-code defensive branch

Already fixed in `bddf70c` during the `feat/provider-ids` PR. Listed here as confirmation — no follow-up action needed.

### C5 — Concurrent migration re-apply race

**File** : `personalscraper/indexer/scanner/__init__.py:975` (the parallel-worker fan-out)

**Symptom** : 3 disk workers all try to apply migration 004's `CREATE INDEX idx_stream_kind_codec` simultaneously, race, fail.

**Fix options** :

- **A** — make all `CREATE INDEX` / `CREATE TABLE` in the migrations use `IF NOT EXISTS` (idempotent re-apply)
- **B** — apply migrations once on the writer connection BEFORE forking workers (single-application guarantee)
- **C** — file-lock the migration apply step

**Recommendation** : combination of A + B. A protects against any future migration re-apply pattern ; B is the correct architectural fix.

### C6 — `.env.example` drift

Add :

- `OMDB_API_KEY` (used by `api/_activation.py` + `omdb.py`, `imdb.py`, `rotten_tomatoes.py`)
- `LACALE_API_KEY` (used by `api/_activation.py`)
- `TRAKT_CLIENT_ID` + `TRAKT_CLIENT_SECRET` (per `api/_activation.py`)
- `TRANSMISSION_USERNAME` + `TRANSMISSION_PASSWORD`
- `LIBRARY_ANALYZER_MAX_WORKERS` (or migrate to `preferences.json5`)

## 4. Architecture impact

No architectural changes. All fixes are local to their respective modules :

| Subsystem         | Files touched                                                                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Library rescraper | `library/rescraper.py`                                                                                                                             |
| Indexer CLI       | `commands/library/backfill.py` (new) + `cli_app.py` registration                                                                                   |
| Migration race    | `indexer/scanner/__init__.py` + `indexer/migrations/004_*.sql`                                                                                     |
| Config docs       | `.env.example`                                                                                                                                     |
| Tech debt         | `scraper/tv_service.py`, `scraper/existing_validator.py`, `library/rescraper.py`, `scraper/movie_service.py`, `process/run.py`, `ingest/ingest.py` |
| Integration tests | `tests/integration/` (2-3 new files) + `pyproject.toml` markers                                                                                    |
| Doc cleanup       | `docs/features/provider-ids/ACCEPTANCE.md`, `docs/reference/*.md`, `CLAUDE.md`, `.claude/skills/implement:pr-review.md`                            |

## 5. Acceptance Criteria

The follow-up PR is complete when :

1. ✅ `personalscraper indexer backfill-ids --dry-run` runs without error on the live library and emits a `BackfillStats` summary
2. ✅ `personalscraper library-rescrape` on a fixture show with stripped episode NFOs produces NFOs with canonical `<uniqueid>` afterwards (new regression test)
3. ✅ `personalscraper library-index` succeeds on a 4-disk config (concurrent worker race fixed)
4. ✅ `.env.example` contains every key returned by `grep -rn "os.environ.get\|settings.*=" personalscraper/`
5. ✅ Decision applied on monolithic Protocols (Option A or B documented + executed)
6. ✅ ACCEPTANCE.md rows #3 / #6 / #9 rewritten with verifiable shell commands; each one re-run on the live instance
7. ✅ Module-size check: `tv_service.py` < 800 LOC, `existing_validator.py` < 800 LOC
8. ✅ Zero unjustified `except Exception` in the 5 hot-spot modules listed
9. ✅ `tests/integration/test_full_scrape_then_scan.py` exists and asserts that DB columns populate after a scrape→scan handoff
10. ✅ `tests/integration/test_cli_subprocess.py` runs `personalscraper run --dry-run` via subprocess and asserts exit code + report shape
11. ✅ All polish items (N1-N7) applied

## 6. Phases

Per the audit report's recommended scope (full text at `docs/pipeline-runs/2026-05-18-20h23-audit-report.md` §7) :

| Phase | Theme                                              | Effort   |
| ----- | -------------------------------------------------- | -------- |
| 1     | Critical bug fixes (C1, C2, C4-as-confirm, C5, C6) | 1-2 days |
| 2     | Design vs reality reconciliation (C3, I3, I5)      | 1-2 days |
| 3     | Tech debt (I1, I2, I4)                             | 2-3 days |
| 4     | Polish (N1-N7)                                     | ½-1 day  |

**Total** : 5-7 days.

## 7. Risk Assessment

- **C3 Option A (drop monolithic Protocols)** : high blast radius. Reverting is straightforward but the test suite churn is significant. Option B is the lower-risk default.
- **C5 migration fix** : modifying migration SQL after it's been applied to production. Use `IF NOT EXISTS` (safe) over `DROP+CREATE` patterns.
- **C4 polish** : module splits can introduce import cycles. Validate with `python -c "import personalscraper"` smoke after each split.
- **Integration tests** : the new `tests/integration/test_full_scrape_then_scan.py` is the highest-value addition but also the most fragile to write — it must mock provider HTTP calls realistically. Use `responses` library (already a dev dep) and the existing fixture data in `tests/fixtures/`.

## 8. Open questions to validate before /implement:plan

- [ ] **Q1 — Option A or B for monolithic Protocols** ? (recommendation : B)
- [ ] **Q2 — Auto-backfill trigger after process** : should the trigger fire on every `process` run (DESIGN §2-7 suggests yes) or only when a verify check signals a gap (less aggressive) ?
- [ ] **Q3 — `LIBRARY_ANALYZER_MAX_WORKERS`** : promote to config (`preferences.json5`) or stay env-var-only ?
- [ ] **Q4 — DEVIATIONS.md gitignore policy** : commit it (transparent audit trail) or move it under `~/.claude/projects/...` (private observer notes) ?
- [ ] **Q5 — Module-size hard-block** : promote to 0.16.0 (next MINOR) or keep advisory for the PATCH ?

Answers required before phase 3 (tech debt) starts so Q5 doesn't gate the lint.
