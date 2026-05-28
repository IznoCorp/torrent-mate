# Design — Tech-Debt Round 2 (God-Modules + Broad Debt Sweep)

> **Status**: Draft (brainstorm output) — pending user review then plan generation.
> **Date**: 2026-05-28
> **Roadmap item**: P3 — Tech-Debt Round 2 (`tech-debt-2`)
> **Codename**: `tech-debt-2`
> **Version bump target**: 0.16.0 → 0.17.0 (**minor** / Y+1)
> **Branch**: `feat/tech-debt-2`
> **Source analysis**: `docs/analysis/03-god-modules-debt-audit.md` + the broad debt inventory folded inline below.

---

## 1. Purpose & Motivation

This is the **second** dedicated tech-debt remediation cycle (the first was `arch-cleanup`,
v0.9.0). It pursues two distinct but complementary goals:

1. **Defuse the highest-risk god-module.** `scraper/movie_service.py` is **958 non-blank
   LOC** (verified `python3 scripts/check-module-size.py 2>&1`, HEAD `feat/registry`) — it
   grew from 927 to 958 since the audit via the Phase 30 orphan-unlink fix and now sits
   **42 lines from the 1000 hard-block ceiling**. The next time any feature touches
   `scrape_movie`, the module-size gate flips `make check` RED and blocks unrelated work.
   This is a _latent landmine_, not an emergency, but it is the single highest-value
   structural action available.

2. **Sweep the broad debt inventory** surfaced by seven category scanners — dead code,
   prose `deferred`/`TODO` markers, `type: ignore` / `noqa` / `pragma: no cover` debt, and
   one genuine functional gap (a silent no-op encoding rule). Most of these are small,
   surgical, and behaviour-preserving; the few that are behavioural changes get a
   regression test per the project's regression-test-per-bug rule.

The animating principle (validated against `docs/analysis/03-god-modules-debt-audit.md` §1):
**the god-module "crisis" the old ROADMAP described no longer exists.** Only two files breach
the 800 soft-warn ceiling (`movie_service.py` 958, `library/scanner.py` 855) and zero breach 1000. So this cycle is _targeted remediation + documentation hygiene + a hidden-debt policy
decision_, not a rewrite.

## 2. Goals / Non-goals

### Goals

- Extract `scraper/movie_service.py` along its **restore vs. scrape** seam so the module
  drops below the 800 soft-warn ceiling and well away from the 1000 hard ceiling — with
  **zero behaviour change** and all public/private import paths preserved via re-exports.
- Decide and implement the `__init__.py` guardrail policy: the checker excludes **all**
  `__init__.py` (`scripts/check-module-size.py:22,37`), hiding two facade modules carrying
  heavy logic (`api/metadata/registry/__init__.py` = **689** non-blank, the largest module
  in the package by this metric; `indexer/scanner/__init__.py` = **621**).
- Remove **genuine dead code**: `resolve_provider_class` (registry `_factory.py`), the dead
  Retry-After tenacity cluster in `core/http_helpers.py`, and resolve the orphaned
  `indexer/repos/release_repo.py` (either wire it live or delete it + its test island).
- Collapse two copy-pasted suppression clusters into single typed helpers: the 18
  `cursor.lastrowid # type: ignore[assignment]` sites and the 10 `registry.chain(...)
  # type: ignore[type-abstract]` sites.
- Make the inert-`noqa` debt explicit: 370 of 371 `# noqa` reference rule families not in
  ruff's active `select` (`["E","F","I","W","D"]`, `pyproject.toml:91`), so `ruff check
--select RUF100` flags all 370 as unused.
- Close the one **genuine functional gap**: the `genre` encoding-rule criterion is a silent
  no-op (`library/recommender.py:75-76`).
- Re-baseline `ROADMAP.md` P3 with verified numbers and mark already-landed work DONE.

### Non-goals

- **Behaviour changes during structural extraction** — moves only; the restore/scrape split
  must be byte-identical in behaviour, verified by `make test`.
- **Splitting `library/scanner.py` (855)** — explicitly **deferred to `lib-fold`** (P1
  ROADMAP). That feature removes the `library/` package entirely; splitting it here would be
  thrown-away work. We only ensure this feature does not _grow_ it.
- **Switching the size metric** from non-blank LOC to cyclomatic complexity / function count
  — logged as an open question (§8), not in scope.
- **Adopting `defusedxml`** — the 16 `# noqa: S314` sites parse self-generated NFOs from
  trusted storage; XXE/billion-laughs does not apply to a single-user pipeline.
- **Migration scripts** — pre-1.0, single mono-user instance; config/DB/NFO evolve in place.
- **Purging `.data/*.bak` / `__rescue__/`** as code work — these are gitignored/untracked
  disk hygiene, noted but not part of any commit.

## 3. Current state (evidence-backed ground truth)

All figures verified against the working tree on HEAD (branch `feat/registry`), 2026-05-28.

### 3.1 The module-size guardrail

- `scripts/check-module-size.py:19-20` — `WARN_LOC = 800`, `BLOCK_LOC = 1000`.
- `scripts/check-module-size.py:22,37` — `EXCLUDED_FILENAMES = {"__init__.py"}` applied in
  `_is_excluded`. **This is the blind spot.**
- Exit code 0 today; current output (`python3 scripts/check-module-size.py 2>&1`):

  ```
    [WARN] personalscraper/library/scanner.py: 855 non-blank lines
    [WARN] personalscraper/scraper/movie_service.py: 958 non-blank lines
  check-module-size: 2 finding(s) (root=personalscraper)
  ```

- **CRITICAL stderr caveat**: WARN findings print to **stderr** (`check-module-size.py:69`).
  Any acceptance criterion grepping for a module name MUST use `2>&1`; piping stdout only is
  tautological (returns 0 whether or not the WARN exists).

### 3.2 `movie_service.py` — the extraction target (958 non-blank, 1080 total)

Module map (verified `rg -n -t py "^(class |def |@dataclass)|^    def "`):

| Symbol                                      | Line    | Concern                                                                                                                                                                                        |
| ------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_media_details_to_movie_data`              | 41      | scrape helper                                                                                                                                                                                  |
| `_coerce_to_movie_data`                     | 120     | scrape helper                                                                                                                                                                                  |
| `_media_details_to_show_data`               | 131     | scrape helper (TV-adjacent, imported by tv tests)                                                                                                                                              |
| `_coerce_to_show_data`                      | 161     | scrape helper (imported by tv tests)                                                                                                                                                           |
| `RestoreOutcome` (+ 7 subclasses)           | 168–221 | **restore** dataclasses                                                                                                                                                                        |
| `_restore_from_db`                          | 228     | **restore** (self-contained, ~195 LOC)                                                                                                                                                         |
| `MovieServiceMixin`                         | 423     | scrape mixin                                                                                                                                                                                   |
| `MovieServiceMixin._resolve_external_ids`   | 445     | scrape                                                                                                                                                                                         |
| `MovieServiceMixin._family_to_client`       | 472     | scrape                                                                                                                                                                                         |
| `MovieServiceMixin._match_movie_candidates` | 504     | scrape (registry chain)                                                                                                                                                                        |
| `MovieServiceMixin._select_best_candidate`  | 687     | scrape                                                                                                                                                                                         |
| `MovieServiceMixin.scrape_movie`            | 725     | scrape — **the ~355-line method** holding the dedup/rename/orphan-unlink logic that grew the file (lines 963–1021: `movie_folder_would_rename`, `movie_video_renamed`, `movie_video_orphan_*`) |

**Verified extraction fact**: `_restore_from_db` (228–421, with its 8 dataclasses 168–221)
is **self-contained**. It depends only on `Path`, `sqlite3`, `log`, the `RestoreOutcome`
hierarchy, and a deferred import of `personalscraper.indexer.db._apply_pragmas`
(`movie_service.py:280`). It does **NOT** call the module-level `_media_details_to_*`
helpers. This is a clean ~205-line seam.

**Consumers (16)** import `MovieServiceMixin` from `scraper.movie_service`. Tests import the
restore symbols directly: `tests/integration/test_bdd_restore.py:18,26` does
`from personalscraper.scraper.movie_service import (... _restore_from_db ...)` and calls it
17 times; `tests/scraper/test_media_details_to_movie_data.py`,
`tests/scraper/test_chain_fallback_unclassified.py:40` (imports `MovieServiceMixin`),
`tests/commands/test_library_rescrape_e2e.py:373`, and
`tests/scraper/test_tv_service_tmdb_show_data_coercion.py:48` import the helpers. **All must
keep working via re-export from `movie_service`.**

### 3.3 The `__init__.py` blind spot (verified non-blank LOC via `awk 'NF{c++}'`)

| Excluded module                     | Non-blank | Logic it holds                                            |
| ----------------------------------- | --------- | --------------------------------------------------------- |
| `api/metadata/registry/__init__.py` | **689**   | `Mode`, `ProviderMatch`, `ProviderRegistry`               |
| `indexer/scanner/__init__.py`       | **621**   | `scan()`, `filter_disks()`, `_finalize_disk_after_walk()` |

Namespace check (`test -e`): `_registry.py` and `_scan_facade.py` are **free**. Caveat from
the audit (§2.8): `indexer/scanner/_scan_orchestrator.py` already exists — do **not** reuse
`_orchestrator.py` for the scanner facade.

### 3.4 Dead-code findings (re-verified `rg -t py`)

- **`resolve_provider_class`** (`api/metadata/registry/_factory.py:40`) — **zero** callers in
  `personalscraper/` or `tests/`. Genuinely dead. The `PROVIDER_CLASSES` dict it reads IS
  used elsewhere via `.get`, so only the function is dead.
- **Retry-After cluster** (`core/http_helpers.py`): `wait_with_retry_after` (line 81),
  `_retry_after_from_exception` (58), `_parse_retry_after` (22) form a closed dead chain —
  `_http.py` wires `wait_exponential_jitter` directly. **Correction to the source report**:
  `_RETRYABLE_STATUS_CODES` (line 19) is **NOT** dead — it is used live at
  `http_helpers.py:180,182` by `make_retryable_predicate`. **Keep it.** Delete only the three
  functions/class.
- **`release_repo.py`** (`indexer/repos/release_repo.py`, 98 non-blank) — imported **only**
  by tests (`tests/indexer/test_schema.py:25`, `tests/indexer/test_repos_file.py:18`,
  `tests/scripts/test_audit_fk_orphans.py`). Production writes `media_release` via raw SQL in
  `release_linker.py`. A self-justifying test island. Decision required (§4 / §8).
- **`has_cached_search`** (`scraper/trailers_cache.py:185`) — deprecated alias for
  `contains_search`; still used by `tests/scraper/test_trailers_cache.py:75,81,85` and
  referenced (as old behaviour) in `trailer_finder.py:24,257` comments. Contradicts the
  no-back-compat-before-v1.0 policy.

### 3.5 Suppression debt (re-verified counts)

- **370 `# noqa`** total; `ruff check --select RUF100 --output-format=concise personalscraper/`
  reports **370** unused-noqa findings — because `pyproject.toml:91` is
  `select = ["E","F","I","W","D"]`, which excludes `PLC0415` (×251), `BLE001` (×57),
  `S314` (×16), `S608`, etc. The directives suppress nothing today and would activate en
  masse if anyone tightened `select`.
- **75 `# type: ignore`** (all carry explicit codes; mypy `strict=true` ⇒ each is live). Two
  clusters: **18** `cursor.lastrowid # type: ignore[assignment]` across the `indexer/repos/*`
  modules, and **10** `registry.chain(SomeProtocol) # type: ignore[type-abstract]` across
  scraper/indexer call sites.
- **6 `# pragma: no cover`** — all legitimate (import guards + unreachable defensive sinks);
  no action.

### 3.6 Functional / marker debt (verified)

- **Genre no-op** (`library/recommender.py:75-76`): `elif c.genre: pass  # Genre matching
deferred`. The `genre` criterion is a user-configurable encoding-rule field
  (`conf/models/preferences.py` `RuleCriteria.genre`; `config.example/encoding.json5`). A
  user who sets it gets silent no-op behaviour — confirmed locked by
  `tests/library/test_recommender.py`.
- **c411 → lacale private coupling** (`api/tracker/c411.py:246`): `LaCaleClient._parse_title`
  reached across into another client's private static method
  (`lacale.py:205 def _parse_title`). `_base.py` already exists in `api/tracker/` as a clean
  landing zone for extraction.

### 3.7 Adjacent ceiling pressure (do NOT inline into these)

`verify/checker.py` is **716 non-blank** (825 total) — near the 800 ceiling and grew since
the audit's 713. Any new helper introduced by this feature must NOT land there.

## 4. Proposed design

### 4.1 movie_service split (the structural core)

Create **`personalscraper/scraper/_movie_restore.py`** holding the entire restore concern:

```
personalscraper/scraper/
├── movie_service.py          (modified — keeps MovieServiceMixin + scrape helpers; re-exports restore symbols)
└── _movie_restore.py         (NEW — RestoreOutcome hierarchy + _restore_from_db)
```

**What moves** (`movie_service.py:168-421`, ~205 non-blank LOC): `RestoreOutcome` (168) +
`Restored`/`NoDb`/`NoMatch`/`NoDispatchPath`/`NoNfoAtDispatch`/`AmbiguousNfo`/`CopyFailed`
(175-221) + `_restore_from_db` (228-421). After extraction `movie_service.py` drops to
**~753 non-blank** (958 − 205), clearing the 800 WARN with ~47 lines of margin and ~247 from
the hard ceiling.

**Public import paths that MUST be preserved** (via re-export at the top of `movie_service.py`):

```python
from personalscraper.scraper._movie_restore import (
    RestoreOutcome, Restored, NoDb, NoMatch, NoDispatchPath,
    NoNfoAtDispatch, AmbiguousNfo, CopyFailed, _restore_from_db,
)
```

This keeps `tests/integration/test_bdd_restore.py` (17 calls) and `MovieServiceMixin`'s own
call site (`movie_service.py:799`) green without touching them. `MovieServiceMixin` and the
`_media_details_to_*` / `_coerce_to_*` helpers stay in `movie_service.py` (the latter are
imported by TV-service tests at their current path).

**Rationale**: the split follows a **concern boundary** (restore-from-DB vs. live scrape),
not an arbitrary line budget. `_restore_from_db` is provably self-contained (§3.2), making
this the lowest-risk seam.

### 4.2 `__init__.py` guardrail policy — refactor-then-tighten (Option A)

**Decision (recommended):** convert the two heavy facades into re-export shims, then tighten
the checker. This is the only safe sequence: tightening the rule first turns `make check` RED
immediately (audit §4 Phase 4 sequencing hazard).

1. `api/metadata/registry/__init__.py` (689) → move `Mode`, `ProviderMatch`,
   `ProviderRegistry` into **`api/metadata/registry/_registry.py`**; `__init__.py` becomes a
   pure re-export shim. **Preserve** `from personalscraper.api.metadata.registry import
ProviderRegistry, Mode, ProviderMatch`.
2. `indexer/scanner/__init__.py` (621) → move `scan`, `filter_disks`,
   `_finalize_disk_after_walk` into **`indexer/scanner/_scan_facade.py`** (NOT
   `_orchestrator.py` — collides with existing `_scan_orchestrator.py`); `__init__.py`
   re-exports. **Preserve** `from personalscraper.indexer.scanner import scan, filter_disks`
   (59 importers).
3. Tighten `scripts/check-module-size.py`: replace the blanket `__init__.py` exclusion with a
   policy that counts `__init__.py` above a floor (e.g. only exclude `__init__.py` ≤ 400
   non-blank, so genuine shims stay quiet but accreting facades get flagged). After the
   refactors both facades fall well under 400, so the gate stays GREEN. Add a regression test
   for the checker (`tests/scripts/test_check_module_size.py` — pass an `__init__.py` over the
   floor, assert it is reported).

### 4.3 Dead-code removal

- Delete `resolve_provider_class` from `_factory.py` (keep `PROVIDER_CLASSES`).
- Delete `wait_with_retry_after`, `_retry_after_from_exception`, `_parse_retry_after` from
  `core/http_helpers.py`. **Keep** `_RETRYABLE_STATUS_CODES`, `build_retry_logger`,
  `make_retryable_predicate`.
- `release_repo.py`: **delete** the module and prune the 3 test files' round-trip cases
  (recommended — production already writes `media_release` via raw SQL, and the
  no-back-compat policy disfavours keeping a parallel unused abstraction). Wiring it live
  (option b) is the alternative — left as an open question (§8).
- Delete `has_cached_search`; repoint `tests/scraper/test_trailers_cache.py:75,81,85` to
  `contains_search`; drop the stale comment references in `trailer_finder.py:24,257`.

### 4.4 Suppression consolidation

- Add `_last_rowid(cursor: sqlite3.Cursor) -> int` (asserts non-None) to
  `personalscraper/indexer/repos/__init__.py` or `indexer/db.py`. Replace all 18
  `lastrowid # type: ignore[assignment]` sites; delete the ignores; add a regression test for
  the None-branch (raises). Net: a real runtime guard replaces 18 silenced sites.
- Collapse the 10 `chain(...) # type: ignore[type-abstract]` ignores. Preferred: a single
  ignore inside the registry overload/impl, or a typed accessor; failing that, replace the 10
  bare ignores with 10 carrying an identical rationale referencing the registry DESIGN.
- `noqa` policy: add the enforced families (`PLC0415`, `BLE001`, `S314`, `S608`) **and**
  `RUF100` to `pyproject.toml` `select`, making existing noqa live and future stale ones
  caught by `make lint`. Backfill rationales on bare `BLE001`/`S314` sites to satisfy the
  `docs/reference/logging.md:167` convention (`# noqa: BLE001 — <rationale>`). Add a
  `make check` step asserting `ruff check --select RUF100 personalscraper/` exits 0.

### 4.5 Functional fix — genre criterion

Make the silent no-op **loud**: thread NFO genres into the recommender comparison and
implement case-insensitive substring matching (item already carries analysis metadata), OR —
if implementation stays deferred — emit a one-time `log.warning("recommender.
genre_criterion_unsupported")` and add a validator note so users know their rule is inert.
Either path updates `tests/library/test_recommender.py` per regression-test-per-bug.

### 4.6 c411 title-parser extraction

Extract the shared quality-marker title parser into a public helper in
`api/tracker/_base.py` (or a new `_title_parse.py`); have both `LaCaleClient` and `c411` call
it. Verify `_base.py` stays under 800 non-blank after the move. Add/extend a parser unit test
covering both trackers' sample titles.

## 5. Phasing

> **Codename** `tech-debt-2` · **SemVer** minor (0.16.0 → 0.17.0) · **Branch** `feat/tech-debt-2`
> · Conventional Commits scoped `(tech-debt-2)` · **No migration scripts** (pre-1.0) ·
> **Phase gate** = `make lint` + `make test` + `make check` all GREEN + residual-import grep
> per moved symbol + `python -c "import personalscraper"`. Squash merge at the end.

Recommended order: Phase 1 (docs, do first) → Phase 2 (movie split) → Phase 3 (dead code) →
Phase 4 (suppressions) → Phase 5 (functional fixes) → Phase 6 (facade policy).

### Phase 1 — Re-baseline `ROADMAP.md` P3 (docs only)

- **Objective**: stop future agents chasing phantom debt; record verified reality.
- **Modify**: `ROADMAP.md` (P3 `tech-debt-2` block, lines ~187-214).
- **Sub-tasks**: update `movie_service.py` to 958, note the 42-line hard-ceiling margin; mark
  the already-landed splits DONE; confirm `library/scanner.py` (855) is owned by `lib-fold`;
  document the two excluded facades (689/621) with the `__init__.py` exclusion note.
- **Commit**: `docs(tech-debt-2): re-baseline ROADMAP P3 god-module inventory` (use
  `git add -f ROADMAP.md` only if blocked by the global `docs/` ignore — verify tracked first).
- **Effort**: S · **Risk**: low · **Dependencies**: none.

### Phase 2 — Split `movie_service.py` (958 → ~753): extract restore concern

- **Objective**: clear the WARN and retreat from the hard ceiling; zero behaviour change.
- **Create**: `personalscraper/scraper/_movie_restore.py`.
- **Modify**: `personalscraper/scraper/movie_service.py` (add re-export block).
- **Sub-tasks**: move lines 168-421 verbatim; add the re-export; run residual-import grep on
  every moved symbol; confirm `make test-cov` branch coverage stays ≥90% (extraction
  re-attributes coverage — add the missing branch test in `_movie_restore.py` if it drops).
- **Commit**: `refactor(tech-debt-2): extract movie restore concern to _movie_restore.py`.
- **Effort**: M · **Risk**: low · **Dependencies**: after Phase 1.

### Phase 3 — Remove dead code

- **Objective**: delete genuinely unreferenced code; trim `core/`.
- **Modify**: `api/metadata/registry/_factory.py`, `core/http_helpers.py`,
  `scraper/trailers_cache.py`, `scraper/trailer_finder.py` (comments),
  `tests/scraper/test_trailers_cache.py`.
- **Delete**: `indexer/repos/release_repo.py` (if option-a chosen) +
  `tests/indexer/test_schema.py` / `test_repos_file.py` / `test_audit_fk_orphans.py`
  release_repo cases.
- **Sub-tasks**: delete `resolve_provider_class`; delete the 3 retry-after symbols (KEEP
  `_RETRYABLE_STATUS_CODES`); delete `has_cached_search` + repoint 3 tests; resolve
  `release_repo`; grep `personalscraper/` AND `tests/` for each deleted symbol → zero matches.
- **Commits**: one `refactor(tech-debt-2): ...` per logical deletion group.
- **Effort**: M · **Risk**: low · **Dependencies**: independent of Phase 2.

### Phase 4 — Suppression consolidation + noqa policy

- **Objective**: replace copy-pasted suppressions with typed helpers; make noqa enforceable.
- **Create**: `_last_rowid` helper (in `indexer/repos/__init__.py` or `indexer/db.py`).
- **Modify**: 18 `lastrowid` sites; 10 `type-abstract` sites; `pyproject.toml:91` select set;
  `Makefile` check chain; bare `BLE001`/`S314` rationales.
- **Sub-tasks**: add `_last_rowid` + None-branch regression test; replace 18 sites; collapse
  10 type-abstract ignores; add `PLC0415,BLE001,S314,S608,RUF100` to select; add a `make check`
  step `ruff check --select RUF100 personalscraper/`; backfill rationales; re-run full lint.
- **Commits**: `refactor(tech-debt-2): add _last_rowid helper`, `chore(tech-debt-2): enforce
noqa families + RUF100 in make check`.
- **Effort**: L · **Risk**: medium (enabling new ruff families may surface fresh findings —
  triage each). · **Dependencies**: after Phase 3 (so deleted code isn't re-annotated).

### Phase 5 — Functional fixes (genre criterion + c411 parser)

- **Objective**: close the one real functional gap; remove a fragile cross-client coupling.
- **Modify**: `library/recommender.py`, `tests/library/test_recommender.py`;
  `api/tracker/_base.py` (or new `_title_parse.py`), `api/tracker/c411.py`,
  `api/tracker/lacale.py`, tracker parser tests.
- **Sub-tasks**: implement genre matching (or loud warning) + regression test; extract shared
  title parser + dual-tracker test; verify `_base.py` < 800 non-blank.
- **Commits**: `fix(tech-debt-2): genre encoding criterion no longer silent no-op`,
  `refactor(tech-debt-2): extract shared tracker title parser`.
- **Effort**: M · **Risk**: low-medium (genre matching is the only behaviour change —
  guarded by regression test). · **Dependencies**: independent.

### Phase 6 — `__init__.py` facade policy (refactor-then-tighten)

- **Objective**: close the size blind spot for the two facades.
- **Create**: `api/metadata/registry/_registry.py`, `indexer/scanner/_scan_facade.py`,
  `tests/scripts/test_check_module_size.py` (if absent).
- **Modify**: both `__init__.py` → shims; `scripts/check-module-size.py` (floor policy).
- **Sub-tasks**: move facade logic; convert `__init__.py` to re-export shims; preserve the 59
  `indexer.scanner` importers + registry import surface; tighten checker with a floor; add the
  checker regression test; run residual-import grep.
- **Commits**: `refactor(tech-debt-2): demote registry/scanner facades to shims`,
  `feat(tech-debt-2): count oversized __init__.py in module-size guardrail`.
- **Effort**: L · **Risk**: medium (59 importers — re-export is mandatory). · **Dependencies**:
  last (the checker change must follow the refactors).

### Phase gate (every phase)

```bash
make lint && make test && make check && echo GATE_GREEN
python -c "import personalscraper" && echo IMPORT_OK
```

## 6. Acceptance criteria (SH-16 — executable, with expected output)

Run from repo root on `feat/tech-debt-2`. Every module-name grep uses `2>&1` (WARN → stderr).

**ACC-01 — Phase 1 re-baseline (no stale figures):**

```bash
rg -c -t md '927\b|tmdb_client' ROADMAP.md || echo 0
# expected: 0
```

**ACC-02 — Phase 2 movie split clears WARN:**

```bash
python3 scripts/check-module-size.py 2>&1 | grep -c movie_service
# expected: 0
```

**ACC-03 — Phase 2 new module present:**

```bash
test -f personalscraper/scraper/_movie_restore.py && echo PRESENT
# expected: PRESENT
```

**ACC-04 — Phase 2 restore symbols still importable from old path:**

```bash
python3 -c "from personalscraper.scraper.movie_service import RestoreOutcome, _restore_from_db, MovieServiceMixin; print('ok')"
# expected: ok
```

**ACC-05 — Phase 2 module under 800 non-blank:**

```bash
awk 'NF{c++} END{print (c < 800) ? "PASS" : "FAIL ("c")"}' personalscraper/scraper/movie_service.py
# expected: PASS
```

**ACC-06 — Phase 3 dead symbols gone:**

```bash
rg -c -t py 'resolve_provider_class|wait_with_retry_after|has_cached_search' personalscraper/ tests/ | awk -F: '{s+=$2} END{print s+0}'
# expected: 0
```

**ACC-07 — Phase 3 live constant kept:**

```bash
python3 -c "from personalscraper.core.http_helpers import _RETRYABLE_STATUS_CODES, build_retry_logger, make_retryable_predicate; print('ok')"
# expected: ok
```

**ACC-08 — Phase 3 release_repo resolved (deleted path):**

```bash
test -f personalscraper/indexer/repos/release_repo.py && echo STILL_PRESENT || echo DELETED
# expected: DELETED   (or STILL_PRESENT if option-b wire-live was chosen — see §8)
```

**ACC-09 — Phase 4 lastrowid ignores collapsed:**

```bash
rg -c -t py 'lastrowid.*type: ignore\[assignment\]' personalscraper/indexer/repos/ | awk -F: '{s+=$2} END{print s+0}'
# expected: 0
```

**ACC-10 — Phase 4 \_last_rowid helper present and importable:**

```bash
python3 -c "from personalscraper.indexer.db import _last_rowid; print('ok')" 2>/dev/null || python3 -c "from personalscraper.indexer.repos import _last_rowid; print('ok')"
# expected: ok
```

**ACC-11 — Phase 4 RUF100 clean (no unused noqa):**

```bash
ruff check --select RUF100 personalscraper/ >/dev/null 2>&1 && echo CLEAN || echo DIRTY
# expected: CLEAN
```

**ACC-12 — Phase 4 noqa families enforced in select:**

```bash
rg -n -t toml 'select = ' pyproject.toml | grep -q 'RUF100' && echo ENFORCED
# expected: ENFORCED
```

**ACC-13 — Phase 5 genre criterion no longer a bare pass:**

```bash
rg -c -t py 'Genre matching deferred' personalscraper/library/recommender.py || echo 0
# expected: 0
```

**ACC-14 — Phase 5 c411 no longer reaches into LaCale private:**

```bash
rg -c -t py 'LaCaleClient\._parse_title' personalscraper/api/tracker/c411.py || echo 0
# expected: 0
```

**ACC-15 — Phase 6 facade shims (logic moved out):**

```bash
test -f personalscraper/indexer/scanner/_scan_facade.py && test -f personalscraper/api/metadata/registry/_registry.py && echo PRESENT
# expected: PRESENT
python3 -c "from personalscraper.indexer.scanner import scan, filter_disks; from personalscraper.api.metadata.registry import ProviderRegistry, Mode, ProviderMatch; print('ok')"
# expected: ok
```

**ACC-16 — Phase 6 oversized **init**.py now counted:**

```bash
python3 -c "import ast,sys; sys.exit(0 if '400' in open('scripts/check-module-size.py').read() or '__init__' not in open('scripts/check-module-size.py').read().split('EXCLUDED_FILENAMES')[1][:60] else 1)" && echo POLICY_CHANGED
# expected: POLICY_CHANGED
```

**ACC-17 — whole-feature gate (every phase):**

```bash
make lint && make test && make check && echo GATE_GREEN
# expected: ... GATE_GREEN
python -c "import personalscraper" && echo IMPORT_OK
# expected: IMPORT_OK
```

**ACC-18 — branch coverage held (post-extraction):**

```bash
make test-cov 2>&1 | rg -o 'TOTAL.*[0-9]+%' | rg -o '[0-9]+%$'
# expected: a value >= 90%
```

## 7. Risks & mitigations

| Risk                                                                                                                           | Mitigation                                                                                                                              |
| ------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| Re-export omission breaks 16 `MovieServiceMixin` consumers / 17 `_restore_from_db` test calls                                  | Mandatory re-export block (§4.1) + residual-import grep on every moved symbol at the phase gate.                                        |
| Coverage re-attribution drops below 90% after extraction                                                                       | ACC-18 (`make test-cov`) is a gate criterion; add branch tests in the new module before the gate.                                       |
| Enabling `PLC0415`/`BLE001`/`S314`/`S608` in `select` surfaces NEW findings beyond the existing noqa                           | Triage each in Phase 4; either add a justified `noqa` or fix; do not blanket-suppress.                                                  |
| `_RETRYABLE_STATUS_CODES` mistakenly deleted as "dead" (source report erred)                                                   | Explicit KEEP note in §3.4/§4.3; ACC-07 imports it.                                                                                     |
| Scanner/registry facade demotion breaks 59 `indexer.scanner` importers                                                         | Re-export shim + residual-import grep + ACC-15 import smoke test.                                                                       |
| Genre matching introduces a behaviour change that mis-classifies                                                               | Regression test asserting both match and non-match (regression-test-per-bug); fall back to loud-warning if implementation is uncertain. |
| Checker floor policy accidentally flags legitimate shims                                                                       | Floor (≤400) chosen so both demoted facades pass; checker regression test pins the boundary.                                            |
| `make check` CLI-coverage steps (`audit-cli-coverage.py`, `cli-coverage-report.py --check`) trip if a CLI-bearing module moves | This feature moves no CLI commands; verify both stay green at each gate.                                                                |

## 8. Open questions (owner decisions)

1. **`release_repo.py`** — delete (recommended, §4.3 option-a; ACC-08 expects DELETED) or wire
   `release_linker.py`'s raw `INSERT INTO media_release` to call `release_repo.insert/upsert`
   (option-b, consolidating the abstraction)? Choosing option-b inverts ACC-08's expected
   output.
2. **Genre criterion** — implement real matching, or emit a loud warning and keep it deferred?
   (§4.5 / ACC-13 only checks the bare `pass` is gone, satisfied by either.)
3. **`__init__.py` checker policy** — floor-based counting (≤400 excluded, recommended) vs.
   "enforce re-exports-only" (forbid any logic in `__init__.py`)? The latter is stricter but
   needs an AST check rather than an LOC floor.
4. **type-abstract collapse shape** — single ignore inside the registry overload, a typed
   per-capability accessor, or 10 rationale-bearing ignores? Affects whether
   `api/metadata/registry/_registry.py` gains a small public accessor surface.
5. **Is the ≤700-LOC DESIGN target still active**, or fully superseded by the 800/1000
   guardrail? Determines whether `tv_service.py` (797) and `trailers/state.py` (767) count as
   debt at all (they pass the current rule).

## 9. References

- **Primary source analysis**: `docs/analysis/03-god-modules-debt-audit.md` (god-module
  inventory, seams, stderr caveat, namespace caveats).
- **ROADMAP entry**: `ROADMAP.md` §P3 — Tech-Debt Round 2 (`tech-debt-2`).
- **Structural template**: `docs/features/registry/DESIGN.md` (section style, capability
  Protocols, module-layout convention).
- **Sibling deferrals**: `ROADMAP.md` §P1 `lib-fold` (owns the `library/scanner.py` split and
  `library/` package removal), §P1 `arch-cleanup-2` (registry events on the base `Event`
  contract; `core`/`conf` upward-import leak), §P2 Verify Checker Plugin System (landing zone
  for `library/validator.py` — do not inline into `verify/checker.py`, 716 non-blank).
- **Conventions**: `CLAUDE.md` (module-size guardrail, regression-test-per-bug,
  no-back-compat-before-v1.0), `docs/reference/logging.md:167` (`# noqa: BLE001 — <rationale>`
  convention), `docs/reference/testing.md` (test markers, coverage).
