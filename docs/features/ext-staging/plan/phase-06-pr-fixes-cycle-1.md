# Phase 6 — PR fixes cycle 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement these fixes sub-phase by sub-phase.

## Context

PR #9 (cycle 1) review surfaced 4 critical wiring gaps + 4 major issues that make the `staging_dirs` refactor effectively dead in production. All findings are coherent with DESIGN.md scope (they reveal incomplete implementation of stated design, not new requirements).

**Production bug summary**: every code path that derives the staging root via `Path(getattr(settings, "staging_dir", "."))` resolves to CWD because `Settings.staging_dir` was removed in Phase 2. Every Sorter strategy invocation falls into the hardcoded fallback because `Sorter.sort_item()` doesn't pass `config`. The `run_scrape` fast-skip and Scraper classification are dead because callers don't forward `config`. CI green is misleading: tests bypass production paths via MagicMock attribute injection.

## Goal

Make the `staging_dirs` refactor actually take effect in production. Remove every hardcoded `001-MOVIES`/`002-TVSHOWS` literal and every `getattr(settings, "*_dir*", ...)` fallback. Wire `Config` through all step functions so they derive paths from `config.paths.staging_dir` + `config.staging_dirs`.

## Tech Stack

Python 3.11+, pydantic v2, ruff, mypy, pytest.

---

## Sub-phase 6.1 — Wire `config` through Sorter to strategies

**Findings addressed**: F1 (critical), F6 (major), F18 (TODO leak in tests)

**Files**:

- Modify: `personalscraper/sorter/sorter.py`
- Modify: `personalscraper/sorter/strategies.py`
- Modify: `tests/sorter/test_sorter.py`
- Modify: `tests/sorter/test_strategies.py` (if existing fixture needs adjustment)

### Steps

- [ ] In `Sorter.__init__`, accept and store `config: Config` (required). Update CLI/pipeline call sites to pass `config`.
- [ ] In `Sorter.sort_item`, forward `self.config` to `strategy.get_destination(item.name, dest_root, self.cleaner, self.config)`.
- [ ] In `Sorter.process`, derive `skip_dirs` from `self.config.staging_dirs` (not hardcoded set). Drop the hardcoded fallback that omits `006-ANDROID`.
- [ ] In `MovieStrategy.get_destination`, `TVShowStrategy.get_destination`, `DefaultStrategy.get_destination`: change `config: Config | None = None` → `config: Config` (required). Remove every `if config is None:` branch and the hardcoded `001-MOVIES`/`002-TVSHOWS`/etc fallbacks.
- [ ] Update `tests/sorter/test_sorter.py`: remove the `_STAGING_DIR_NAMES` hardcoded fixture, replace with `config` fixture using `CANONICAL_STAGING_DIRS`. Drop the `# TODO(ext-staging 2.6)` comment.
- [ ] Update `tests/sorter/test_strategies.py` if needed (it should already be passing config).

### Acceptance

- `grep -n "config: Config | None = None" personalscraper/sorter/strategies.py` → 0 matches.
- `grep -n "001-MOVIES\|002-TVSHOWS\|003-EBOOKS\|004-AUDIO\|005-APPS\|006-ANDROID\|097-TEMP\|098-AUTRES" personalscraper/sorter/` → 0 matches outside string-literal docstring placeholders.
- `make lint && make test` green.

### Commit

```
fix(ext-staging): wire config through Sorter to strategies (F1, F6)
```

---

## Sub-phase 6.2 — Replace `getattr(settings, "staging_dir", ".")` with `config.paths.staging_dir`

**Findings addressed**: F2 (critical)

**Files** (10 call sites):

- Modify: `personalscraper/process/run.py` (lines 40, 90)
- Modify: `personalscraper/verify/run.py` (lines 34, 84)
- Modify: `personalscraper/scraper/run.py` (lines 49, 163)
- Modify: `personalscraper/enforce/file_sanitizer.py` (line 65)
- Modify: `personalscraper/enforce/coherence_checker.py` (line 59)
- Modify: `personalscraper/enforce/structure_validator.py` (line 73)
- Modify: `personalscraper/ingest/ingest.py` (line 253)
- Modify: every test that previously set `mock_settings.staging_dir = tmp_path` to instead set `mock_config.paths.staging_dir = tmp_path` (search `tests/process/`, `tests/verify/`, `tests/scraper/`, `tests/enforce/`, `tests/ingest/`).

### Steps

- [ ] In each production file, replace `staging = Path(getattr(settings, "staging_dir", "."))` with `staging = config.paths.staging_dir` (assuming `config: Config` is now required and present in the function signature — add to signature if missing).
- [ ] Make `config` required (no `Config | None`) in every affected function. Update the function's `Args:` docstring.
- [ ] Update every test fixture / mock that uses `settings.staging_dir = tmp_path`. Build a real or mock `Config` whose `paths.staging_dir` equals `tmp_path`. Use `tests/fixtures/config.py::CANONICAL_STAGING_DIRS`.
- [ ] If a function previously had a `staging_dir: Path | None` parameter (used by tests for direct injection), keep it as an override but make `config` required.

### Acceptance

- `grep -rn 'getattr(settings, "staging_dir"' personalscraper/` → 0 matches.
- `grep -rn 'getattr(settings, "ingest_dir"' personalscraper/` → 0 matches.
- All affected functions require `config: Config` (no `| None`).
- `make lint && make test` green; `python -m mypy personalscraper/` clean.

### Commit

```
fix(ext-staging): replace settings.staging_dir fallback with config.paths.staging_dir (F2)
```

---

## Sub-phase 6.3 — Pass `config` to every `run_scrape` and `run_ingest` call site

**Findings addressed**: F3 (critical), F9 (major), F12 (medium)

**Files**:

- Modify: `personalscraper/cli.py` (lines ~199 ingest cmd, ~261 scrape cmd)
- Modify: `personalscraper/pipeline.py` (run_scrape lambda)
- Modify: `personalscraper/process/run.py` (run_scrape call inside run_process)
- Modify: `personalscraper/ingest/ingest.py` — make `config: Config` required (drop `Config | None`), remove the hardcoded `_movies_dir = "001-MOVIES"` fallback.
- Modify: `personalscraper/scraper/run.py` — make `config: Config` required in `run_scrape` and `_has_unscraped_items`. Remove the `if config is not None:` branch.
- Modify: tests for `run_ingest` and `run_scrape` that pass `settings` only.

### Steps

- [ ] CLI `ingest` command: `report = run_ingest(settings, dry_run=dry_run, ingest_dir=ingest_dir, staging_dir=staging_dir, config=ctx.obj.config)`.
- [ ] CLI `scrape` command (and any other run_scrape callers): pass `config=ctx.obj.config`.
- [ ] Pipeline `_run_process_phase`: pass `config=self.config` to `run_scrape`.
- [ ] `process/run.py:run_process`: forward `config` to `run_scrape`.
- [ ] Make `config: Config` required in `run_ingest` and `run_scrape` signatures. Remove fallback branches and hardcoded literals.
- [ ] Update affected tests to pass `config=` parameter (use the `_make_config()` / `CANONICAL_STAGING_DIRS` pattern from earlier sub-phases).

### Acceptance

- `grep -rn "run_scrape(.*settings.*dry_run" personalscraper/` → every call site now passes `config=`.
- `grep -rn "run_ingest(.*settings" personalscraper/` → every call site now passes `config=`.
- No `if config is None` branches remain in `ingest/ingest.py` or `scraper/run.py`.
- `make lint && make test` green.

### Commit

```
fix(ext-staging): pass config to run_scrape and run_ingest call sites (F3, F9, F12)
```

---

## Sub-phase 6.4 — Replace `"MOVIE" in name.upper()` heuristic with explicit `FileType`

**Findings addressed**: F4 (critical)

**Files**:

- Modify: `personalscraper/scraper/run.py` (line 97 `_needs_repair`)
- Modify: callers of `_needs_repair` to pass `FileType` (or look it up from the `category_dir` via config + find_by_file_type — whichever is the smaller diff).

### Steps

- [ ] Identify all callers of `_needs_repair(category_dir, ...)`. For each, the caller must already know whether it iterates movies or tvshows (since the loop is `for category_dir in (movies_dir, tvshows_dir):`). Pass an explicit `FileType` enum value.
- [ ] Change `_needs_repair` signature: `def _needs_repair(category_dir: Path, file_type: FileType, ...)`. Use `file_type == FileType.MOVIE` instead of substring match.
- [ ] Update unit tests for `_needs_repair`.

### Acceptance

- `grep -n '"MOVIE" in.*upper\|"TVSHOW" in.*upper\|"MOVIES" in.*upper' personalscraper/` → 0 matches.
- `make lint && make test` green.

### Commit

```
fix(ext-staging): replace MOVIE substring heuristic with explicit FileType in scraper (F4)
```

---

## Sub-phase 6.5 — Cleanup remaining `001-MOVIES` / `002-TVSHOWS` literals in docstrings/comments

**Findings addressed**: F5 (major), F14 (medium)

**Files** (per F5 grep):

- `personalscraper/scraper/run.py` (lines 37, 89, 152, 153)
- `personalscraper/sorter/__init__.py` (line 5)
- `personalscraper/sorter/file_type.py` (lines 100-105)
- `personalscraper/verify/verifier.py` (lines 142, 173)
- `personalscraper/models.py` (line 19)
- `personalscraper/scraper/nfo_generator.py` (line 8)
- `personalscraper/scraper/scraper.py` (lines 1319, 1770)
- `personalscraper/process/dedup.py` (line 63)
- `personalscraper/process/cleanup.py` (line 45)
- `personalscraper/process/reclean.py` (lines 39, 103)

### Steps

- [ ] For each occurrence, replace the hardcoded literal in docstrings/comments with placeholder notation: `{movies_dir}/Title (Year)/`, `{tvshows_dir}/Show Name/Season XX/`, etc.
- [ ] Update obsolete `_has_unscraped_items` docstring (`scraper/run.py:37`) — drop reference to removed `movies_dir_name, tvshows_dir_name` Settings fields.

### Acceptance

- `grep -rn "001-MOVIES\|002-TVSHOWS\|003-EBOOKS\|004-AUDIO\|005-APPS\|006-ANDROID\|097-TEMP\|098-AUTRES" personalscraper/` → 0 matches (allow `099-SCRIPTS` not in personalscraper/).
- `make lint && make test` green.

### Commit

```
docs(ext-staging): replace remaining staging dir literals in docstrings/comments (F5, F14)
```

---

## Sub-phase 6.6 — Tighten validation: `role: Literal["ingest"]` + warn on `DefaultStrategy` fallback

**Findings addressed**: F8 (major), F11 (medium)

**Files**:

- Modify: `personalscraper/conf/models.py` (StagingDirConfig.role typing)
- Modify: `personalscraper/sorter/strategies.py` (DefaultStrategy)

### Steps

- [ ] In `StagingDirConfig`, change `role: str | None` to `role: Literal["ingest"] | None` (import from `typing`). Update field docstring.
- [ ] In `DefaultStrategy.get_destination`, when the requested `FileType` has no matching staging entry, log a warning via `logging.getLogger(__name__).warning(...)` before falling back to `FileType.OTHER`. Include the requested file_type and the available types in the message.
- [ ] Add a unit test asserting the warning is emitted (use `caplog`).

### Acceptance

- `grep -n 'role: Literal\["ingest"\]' personalscraper/conf/models.py` → 1 match.
- New caplog test passes.
- `make lint && make test` green.

### Commit

```
fix(ext-staging): tighten role typing + warn on DefaultStrategy fallback (F8, F11)
```

---

## Exit gate

- [ ] All sub-phases 6.1–6.6 committed with acceptance criteria met.
- [ ] `make lint && make test` green.
- [ ] `python -m mypy personalscraper/` clean.
- [ ] `grep -rn "getattr(settings,.*dir" personalscraper/` → 0 matches.
- [ ] `grep -rn "001-MOVIES\|002-TVSHOWS\|003-EBOOKS\|004-AUDIO\|005-APPS\|006-ANDROID\|097-TEMP\|098-AUTRES" personalscraper/` → 0 matches.
- [ ] No `if config is None` or `Config | None` defaults remain in pipeline step functions (`run_ingest`, `run_scrape`, `run_clean`, `run_cleanup`, `run_verify`, `run_enforce`).
