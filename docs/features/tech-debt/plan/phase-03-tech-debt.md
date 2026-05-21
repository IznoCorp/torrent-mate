# Phase 3 — Cross-feature tech debt

**Goal** : Address the systemic debt the codebase has carried for multiple versions. Module-size splits (5 versions overdue), exception-handling narrowing, legacy ID migration in recommender, integration-test scaffold to prevent recurrence.

## Gate (in)

- Phase 2 complete
- `make check` green
- Q5 resolved : module-size hard-block status decided (advisory continuation vs hard-block promotion)

## Gate (out)

- `tv_service.py` < 800 LOC AND `existing_validator.py` < 800 LOC
- `indexer/scanner/__init__.py` actual non-blank LOC verified ≤ 1000 (or split if over)
- Zero unjustified `except Exception` in `rescraper.py`, `movie_service.py`, `tv_service.py`, `process/run.py`, `ingest/ingest.py`
- `library/recommender.py` reads from `external_ids_json` exclusively
- `tests/integration/test_full_scrape_then_scan.py` exists and asserts end-to-end column population
- `tests/integration/test_cli_subprocess.py` exists and asserts `personalscraper run --dry-run` exit code + report

## Sub-phases

### 3.1 — Split `tv_service.py` (986 LOC → ≤ 800)

**Extraction targets** :

- `_episode_nfo_writer.py` — `_generate_episode_nfos` + payload builders (`_episode_payload`, `_tvdb_series_to_show_data` already external)
- Optionally `_drift_rescrape.py` — the `drift_rescrape_episode_nfo` path + `_match_seasons` orchestration

**Validation** : `python -c "import personalscraper"` smoke + `make check` after each extraction.

**Commit** : `refactor(tech-debt): split tv_service into focused modules`

### 3.2 — Split `existing_validator.py` (888 LOC → ≤ 800)

**Extraction targets** :

- `_drift_validator.py` — `verify_tvshow_scrape_drift` + helpers
- Keep `_repair_*` functions and `ExistingValidatorMixin` in the main file

**Commit** : `refactor(tech-debt): split existing_validator drift logic`

### 3.3 — Verify `indexer/scanner/__init__.py` non-blank LOC

**Action** : run `python3 scripts/check-module-size.py personalscraper/indexer/scanner/__init__.py` ; if over the hard ceiling, split the parallel-worker orchestration into a sibling module.

**Commit** : `refactor(tech-debt): split indexer scanner orchestration` (only if needed)

### 3.4 — Narrow / justify 44 broad `except Exception`

**Files** (priority hot spots) :

- `personalscraper/library/rescraper.py` (6 occurrences)
- `personalscraper/scraper/movie_service.py` (3)
- `personalscraper/scraper/tv_service.py` (3)
- `personalscraper/process/run.py` (3)
- `personalscraper/ingest/ingest.py` (3)
- Remaining 29 across other modules

**Per-occurrence** : either narrow to the actual exception types (preferred) OR add `# noqa: BLE001 — reason` with a one-sentence justification.

**Commit** : `refactor(tech-debt): narrow / justify broad except Exception across hot-spot modules`

### 3.5 — `library/recommender.py` legacy ID migration

**File** : `personalscraper/library/recommender.py` (597 LOC)

**Migration** : replace `rec.tmdb_id` / `rec.imdb_id` model attributes with reads from `external_ids_json` via the indexer's `ExternalIds` model (`personalscraper/indexer/external_ids.py`).

**Tests** : update `tests/library/test_recommender.py` to seed `external_ids_json` instead of flat columns ; remove any `tmdb_id=` kwarg from the model construction.

**Commit** : `refactor(tech-debt): migrate library/recommender off legacy flat IDs`

### 3.6 — `tests/integration/test_full_scrape_then_scan.py`

**Goal** : single end-to-end test that catches the entire class of "library scanner ignores X" bugs.

**Shape** :

1. Seed a temp staging tree with 2 shows + 1 movie
2. Run `personalscraper scrape` against the real `NFOGenerator` (no mocks on the writer side)
3. Mock provider HTTP via `responses` library (use existing fixture data)
4. Run `personalscraper library-index` against the result
5. Assert : DB columns `external_ids_json` (all 3 families when present), `ratings_json`, `canonical_provider`, `episode.title`, `season.has_poster`, `season.episodes_with_nfo`

**Commit** : `test(tech-debt): add full-scrape-then-scan integration test`

### 3.7 — `tests/integration/test_cli_subprocess.py`

**Goal** : catch import / wiring bugs that pass unit tests but break the CLI.

**Shape** :

1. Build a minimal temp config
2. `subprocess.run([python, "-m", "personalscraper", "run", "--dry-run"], env=temp_env)`
3. Assert exit code 0, no traceback in stderr, StepReport JSON shape valid

**Commit** : `test(tech-debt): add CLI subprocess smoke test`

### 3.8 — Mock realism sweep

**Files** : `tests/test_cli.py`, `tests/test_pipeline.py`, `tests/scraper/test_scraper.py`, `tests/scraper/test_run_extra.py`, `tests/scraper/test_artwork.py`, `tests/scraper/test_augment_episode_nfo_xref.py`

**Action** : convert raw `MagicMock()` instantiations of project classes to `MagicMock(spec=ClassName)`. Mechanical pass — ~50-80 sites. Catches API drift on the next refactor.

**Commit** : `test(tech-debt): convert raw MagicMock to spec= in pipeline + scraper tests`

## Definition of done

- 8 commits on `fix/tech-debt`
- `make check` green after every commit
- `python3 scripts/check-module-size.py` reports zero warnings
- Coverage delta ≥ 0 (integration tests add behavioral coverage)
- `make test` passes with the new integration tests in non-e2e tier
