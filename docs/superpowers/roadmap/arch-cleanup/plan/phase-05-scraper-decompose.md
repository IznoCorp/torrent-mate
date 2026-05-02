# Phase 5 — Scraper decomposition

**Goal:** Split `personalscraper/scraper/scraper.py` (2159 LOC, the largest single source file in the codebase) into an orchestrator + 5 service modules under `personalscraper/scraper/`. Each new module has a single responsibility and ≤ 700 LOC.

**Risk:** High. Touches the scrape execution path which integrates TMDB / TVDB / IMDB clients, NFO emission, filesystem rename/merge, and the existing-scrape branch. Mitigated by: (1) symbol inventory first, (2) extraction-only commits (no logic edits), (3) the `tests/scraper/` suite covers each service path.

**Files affected (estimate):**

- Create: `personalscraper/scraper/orchestrator.py`, `movie_service.py`, `tv_service.py`, `rename_service.py`, `existing_validator.py`, `classifier.py`
- Modify: `personalscraper/scraper/scraper.py` (shrink), `personalscraper/scraper/run.py` (re-import path), test imports
- Possibly delete: `personalscraper/scraper/scraper.py` if reduced to a re-export shell

## Pre-flight inventory

`scraper.py` at 2159 LOC needs the same inventory-first treatment as `_modes.py`. Produce `phase-05-inventory.md` with:

- Every public function/class with target module
- Shared private helpers (used by ≥ 2 services)
- All external consumers

```bash
grep -nE '^(def |class )' personalscraper/scraper/scraper.py | head -100
grep -rn "from personalscraper.scraper.scraper" personalscraper/ tests/
grep -rn "from personalscraper.scraper import scraper" personalscraper/ tests/
```

Service classification rubric:

- `movie_service` → TMDB / IMDB lookup, candidate selection, movie NFO assembly
- `tv_service` → TVDB lookup (canonical), TMDB-for-TV fallback, season/episode resolution, show + episode NFO assembly
- `rename_service` → folder rename, merge logic, conflict resolution, atomic temp/rename
- `existing_validator` → re-validation of pre-scraped folders (NFO present + IDs valid path)
- `classifier` → media-type classification (movie / tv / standup / theater / etc.)
- `orchestrator` → top-level `run_scrape`, batch loop, dispatch, `StepReport` assembly
- `_shared` → common helpers if any

## Sub-phases

### 5.0 — Symbol inventory

**Files:**

- Create: `docs/superpowers/roadmap/arch-cleanup/plan/phase-05-inventory.md`

- [ ] **Step 1: Run greps + classify each function**.
- [ ] **Step 2: Identify cyclic risks** (e.g., `tv_service` calling `rename_service` calling back into `tv_service` for episode merge — must break the cycle by passing dependency-injected callables).
- [ ] **Step 3: Commit**

```bash
git commit -m "docs(arch-cleanup): scraper symbol inventory before split"
```

### 5.1 — Extract `classifier.py` (lowest-risk)

Classification logic has no upstream dependencies on other scraper internals — extract first to validate the import pattern.

- [ ] **Step 1: Create `personalscraper/scraper/classifier.py`**, move classification functions verbatim.
- [ ] **Step 2: Declare `__all__`**.
- [ ] **Step 3: In `scraper.py`, replace bodies with `from personalscraper.scraper.classifier import <names>` re-exports**.
- [ ] **Step 4: Test**

```bash
pytest tests/scraper/ -v -k "classif"
```

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): extract scraper classifier"
```

### 5.2 — Extract `existing_validator.py`

Re-validation of pre-scraped folders — minimal coupling.

- [ ] **Step 1-5**: Same pattern as 5.1.

```bash
git commit -m "refactor(arch-cleanup): extract existing-scrape validator"
```

### 5.3 — Extract `rename_service.py`

Filesystem rename / merge / conflict resolution.

- [ ] **Step 1-5**: Same pattern. Pay particular attention to the atomic-rename code paths — preserve them byte-for-byte.

```bash
git commit -m "refactor(arch-cleanup): extract scraper rename service"
```

### 5.4 — Extract `movie_service.py`

TMDB / IMDB lookup + candidate selection + movie NFO emission.

- [ ] **Step 1: Verify movie service is independent of TV service** (movie code should not import TV code, and vice versa). If a shared helper exists, leave it in `scraper.py` for now (will move to `_shared.py` in 5.6).
- [ ] **Step 2-5**: Same extraction pattern.

```bash
git commit -m "refactor(arch-cleanup): extract movie scraper service"
```

### 5.5 — Extract `tv_service.py`

TVDB-canonical lookup + TMDB-for-TV fallback + season/episode resolution + show/episode NFO.

> **Important precedent**: The recent fix `dcd365e fix(scraper): TMDB-for-TV is permitted only when TVDB has no match` and `bf42223 fix(scraper): use TVDB as canonical id for TV-show NFOs` enshrine the TVDB-primary contract. The extraction MUST preserve this exactly. Add a smoke test before extracting:

- [ ] **Step 1: Add a regression assertion in `tests/scraper/test_api_guardrails.py`** verifying the TVDB-primary rule is honoured by the post-extraction `tv_service`.
- [ ] **Step 2: Run that test, confirm it passes pre-extraction**.
- [ ] **Step 3: Extract `tv_service.py`** following 5.4 pattern.
- [ ] **Step 4: Re-run the test, confirm it still passes**.
- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): extract TV scraper service (preserves TVDB-primary contract)"
```

### 5.6 — Extract `orchestrator.py` + cleanup

After 5.1-5.5, `scraper.py` should contain only:

- The top-level `run_scrape(...)` entry point
- Re-exports of all extracted symbols

Move `run_scrape` to `orchestrator.py`:

- [ ] **Step 1: `git mv personalscraper/scraper/scraper.py personalscraper/scraper/orchestrator.py`** — wait, this won't work since the file currently still has re-exports. Instead:
- [ ] **Step 1 (corrected): Create `orchestrator.py` with `run_scrape` and any orchestration helpers.**
- [ ] **Step 2: In `scraper.py`, replace the `run_scrape` body with `from personalscraper.scraper.orchestrator import run_scrape  # noqa: F401`**.
- [ ] **Step 3: Verify `scraper.py` is now ≤ 100 LOC of re-exports**.
- [ ] **Step 4: Optional**: rename `scraper.py` to `__init__.py` re-export shell, OR leave `scraper.py` as-is since `from personalscraper.scraper.scraper import X` still resolves.
- [ ] **Step 5: Test**

```bash
pytest tests/scraper/ -v
```

- [ ] **Step 6: Commit**

```bash
git commit -m "refactor(arch-cleanup): extract scrape orchestrator; scraper.py is now a re-export shell"
```

### 5.7 — Extract shared helpers (if any)

If 5.0 inventory identified helpers used by ≥ 2 services and they currently live in `scraper.py`:

- [ ] **Step 1: Create `personalscraper/scraper/_shared.py`**, move them there.
- [ ] **Step 2: Update services to import from `_shared`**.
- [ ] **Step 3: Test + commit**

```bash
git commit -m "refactor(arch-cleanup): extract shared scraper helpers into _shared.py"
```

### 5.8 — Phase gate

- [ ] **Step 1: Verify per-file LOC**

```bash
wc -l personalscraper/scraper/orchestrator.py personalscraper/scraper/movie_service.py personalscraper/scraper/tv_service.py personalscraper/scraper/rename_service.py personalscraper/scraper/existing_validator.py personalscraper/scraper/classifier.py
```

Expected: each ≤ 700 LOC.

- [ ] **Step 2: Module-size script**

```bash
python3 scripts/check-module-size.py
```

Expected: no scraper file flagged.

- [ ] **Step 3: Full scraper integration tests**

```bash
pytest tests/scraper/ -v
pytest tests/integration -v -k "scrape"  # if that pattern exists
```

- [ ] **Step 4: Phase milestone commit**

```bash
git commit --allow-empty -m "chore(arch-cleanup): phase 5 gate — scraper decomposition complete"
```

## Quality gate

```bash
make check
pytest tests/scraper/ -v
# and an integration smoke run if a fixture is available:
pytest tests/integration/ -v -k "scrape or pipeline"
```

## Success criteria

- `scraper/scraper.py` ≤ 100 LOC of re-exports (or removed entirely with imports re-pointed)
- Every service file ≤ 700 LOC
- All scraper tests pass; coverage delta ≥ 0
- TVDB-primary contract preserved (verified by the regression test added in 5.5)
- TMDB-for-TV fallback rule preserved
- `personalscraper scrape` end-to-end on a test fixture produces an identical NFO byte-for-byte vs pre-phase 5

## Rollback plan

Each sub-phase is one commit. The orchestrator extraction in 5.6 is the riskiest because it touches `run_scrape` itself — keep the previous re-export shell in place during the transition so any consumer reading `from personalscraper.scraper.scraper import run_scrape` still works after revert.

## Estimated effort

6-8 commits (plus 5.0 inventory = 7-9 total), ~10 hours. Largest phase by effort, second-largest by risk after phase 4.
