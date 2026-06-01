# DESIGN — Unified Check Plugin Framework (verify + enforce)

> Status: **approved (brainstorm)** — 2026-06-01. Awaiting branch + plan.
> ROADMAP item: P2 "Verify Checker Plugin System" (scope expanded to also unify `enforce/coherence_checker.py`, per operator decision).
> SemVer: **minor** (additive plugin framework + CLI flags + Web-UI enumeration API; the only behavior change is gated behind a final dedicated phase). Proposed bump: `0.19.0 → 0.20.0`.

---

## 1. Purpose

`verify/checker.py` (716 non-blank LOC) is a monolith: `MediaChecker.check_movie()` / `check_tvshow()` are two long imperative methods, each appending ~13–18 `CheckResult`s inline. Adding a check, testing one in isolation, or letting a UI enumerate them all requires reading/editing the whole file. A second, separate checker — `enforce/coherence_checker.py` — duplicates the same NFO-parse + per-item-loop shape with its own `CoherenceResult` type.

This feature introduces **one unified Check plugin framework** that both subsystems consume:

- A `Check` Protocol + a `CheckRegistry` (decorator-registered, enumerable).
- A shared `CheckContext` (parse-once NFO cache, config, patterns, stage, media-type).
- Each existing check becomes its own small plugin under `verify/checks/`.
- Fix logic is **co-located** with its check (consolidating `verify/fixer.py` and the duplicated `_fix_*` helpers in `library_checks.py`).
- DB-mode (`validate_from_index`) is unified via an optional `from_index()` capability per check.
- Granular CLI (`--check <name>`, `--list-checks`) and a Python enumeration API for the future Web Management UI.

The end state is a single source of truth for "what checks exist, on which stage, for which media type, how to run/fix/derive-them" — testable, extensible, and discoverable.

## 2. Goals / Non-goals

### Goals

1. `Check` Protocol with declared metadata (`name`, `group`, `stages`, `media_types`, `default_severity`, `description`) and a `run(ctx) -> list[CheckResult]` method.
2. Optional capabilities via structural sub-protocols: `FixableCheck.fix(ctx)`, `IndexableCheck.from_index(row, ctx)`.
3. `CheckRegistry` — decorator registration, `checks_for(stage, media_type)` (deterministic order), `get(stage, name)`, `list_specs()`.
4. Migrate **every** existing check (verify DISPATCH + enforce STAGING coherence) into `verify/checks/` plugins.
5. The four orchestrators (`MediaChecker` facade, `Verifier`, `validate_library`, `validate_from_index`, `check_coherence`) become registry-driven loops while **keeping their public signatures**.
6. Consolidate fix logic into co-located `fix()` methods; delete `MediaFixer`.
7. Granular CLI `--check`/`--list-checks` on `verify`, `enforce`, `library validate`.
8. Python enumeration API (`catalog.list_checks()`, `catalog.run_check()`) for the future Web UI.
9. **No behavior change** for the structural refactor, proven by a characterization golden over all public entry points.
10. As a **final, dedicated, deliberate** phase: unify verify's auto-fix policy to match library's (`dir_naming + no_empty_dirs + ntfs_safe_names`) — separately tested, with an explicit golden update.

### Non-goals

- No HTTP/REST endpoint (`GET /api/checks`) — that belongs to the Web Management UI feature; we only ship the Python API + CLI it will consume.
- No change to check **logic** beyond the extraction itself (except the gated fix-policy unification in the final phase).
- No migration of enforce's `file_sanitizer` / `structure_validator` steps — those are mutation steps, not "checks". Only `coherence_checker` (the true checker) joins the framework.
- No per-check exception isolation (would change which items are blocked — see §7).
- No new indexer schema, no migration scripts (pre-1.0, evolve in place).

## 3. Core abstractions

New module `verify/checks/base.py` — canonical home for `Severity`, `CheckResult`, `FixAction`, the protocols, `CheckStage`, `CheckContext`, `CheckSpec`. `Severity` + `CheckResult` **move here** from `checker.py`; internal importers are repointed (no re-export shim — single source of truth, pre-1.0).

```python
class CheckStage(Enum):
    STAGING  = "staging"    # enforce: post-sort coherence, pre-scrape, read-only
    DISPATCH = "dispatch"   # verify: post-scrape, pre-dispatch, may fix/block

@runtime_checkable
class Check(Protocol):
    name: str                       # stable id, e.g. "nfo_present"
    group: str                      # family, e.g. "nfo"
    stages: frozenset[CheckStage]
    media_types: frozenset[str]     # {"movie","tvshow"}
    default_severity: Severity      # DECLARED (docs / Web-UI). Actual severity is per-result.
    description: str
    def run(self, ctx: "CheckContext") -> list[CheckResult]: ...   # [] when precondition unmet

class FixableCheck(Protocol):
    def fix(self, ctx: "CheckContext") -> list[FixAction]: ...

class IndexableCheck(Protocol):
    def from_index(self, row: Mapping, ctx: "IndexContext") -> list[CheckResult] | None: ...
```

Two properties fall directly out of the current code:

- **`run()` returns a list.** Conditional checks (`nfo_valid`, `category`, `root_video_files`, `streamdetails`, `nfo_ids`) return `[]` when their precondition is unmet — faithfully reproducing "not appended" today. Multi-result checks (`season_posters`: one per missing season) return N. Dynamic severity (`nfo_ids` movie: ERROR if neither tmdb/imdb, WARNING if one) is computed inside `run()` and lives on the `CheckResult`, not on `default_severity`.
- **`CheckContext` carries a parse-once, cached NFO root** — kills the re-parse perf trap (today the NFO is parsed once and threaded; naive per-check parsing would be O(checks)). A sentinel distinguishes "not yet parsed" from "parsed → None (parse failure)".

```python
@dataclass
class CheckContext:
    media_dir: Path
    media_type: str                 # "movie" | "tvshow"
    stage: CheckStage
    config: Config
    patterns: NamingPatterns
    dry_run: bool = False
    expected_file_type: FileType | None = None   # enforce wrong-category needs the bucket it was found in
    resolved_category: str | None = None          # category check stashes its resolution here → no double classify
    def nfo_root(self) -> ET.Element | None: ...   # lazy, cached (sentinel-guarded)
    def nfo_path(self) -> Path | None: ...
```

`IndexContext` is the DB-mode analogue: it carries the SQLite `row`, `media_type`, and `category` instead of a filesystem dir.

## 4. Module layout

```
verify/
  checks/
    __init__.py      # imports every check module once → registration; re-exports the registry singleton
    base.py          # CheckStage, Severity, CheckResult, CheckSpec, FixAction, CheckContext, IndexContext, Protocols
    registry.py      # CheckRegistry, @register_check, the _ORDER table, apply_fixes(), singleton
    catalog.py       # Web-UI enumeration API: list_checks(), run_check()
    nfo.py           # nfo_present, nfo_valid, nfo_ids
    artwork.py       # poster_present, artwork_landscape, season_posters
    naming.py        # dir_naming (+ fix)
    structure.py     # video_present, not_sample, no_empty_dirs (+ fix), season_structure, episode_renamed, root_video_files
    streams.py       # streamdetails
    dedup.py         # no_duplicate_videos
    ntfs.py          # ntfs_safe_names (+ fix)
    category.py      # category (dual-purpose → stashes resolved_category)
    provider_ids.py  # episode_nfo, episode_canonical_uniqueid_present, episode_xref_secondary_id_present, episode_xref_imdb_id_present
    coherence.py     # STAGING: sort_process_coherence, nfo_ids (coherence variant), genre_coherence
  checker.py         # SHRINKS — MediaChecker becomes a thin DISPATCH facade (check_movie/check_tvshow loop the registry); signatures unchanged
  verifier.py        # orchestrator → drives the registry; public surface unchanged
  fixer.py           # SHRINKS — MediaFixer deleted; FixAction moved to base.py; fix helper lives in registry.apply_fixes()
  library_checks.py  # validate_library / validate_from_index → registry loops; own _fix_* deleted (now check.fix())
  run.py, events.py  # unchanged
enforce/
  coherence_checker.py  # SHRINKS — check_coherence loops registry.checks_for(STAGING, …); CoherenceResult adapted from CheckResult at the boundary
```

Shrinking `checker.py` below the soft ceiling and keeping each plugin small also serves the module-size discipline.

## 5. Check inventory

`Sev.` = severity (dynamic = computed in `run()`); `Fix` = implements `fix()`; `Idx` = implements `from_index()`; `MT` = media types.

### Stage DISPATCH (verify)

| Check                                | Group        | MT       | Sev.    | Fix | Idx | Fidelity notes                                                                                                                  |
| ------------------------------------ | ------------ | -------- | ------- | --- | --- | ------------------------------------------------------------------------------------------------------------------------------- |
| `video_present`                      | structure    | movie+tv | ERROR   | —   | —   | movie = non-recursive, tv = recursive → branch on `ctx.media_type`                                                              |
| `not_sample`                         | structure    | movie    | WARNING | —   | —   | conditional: `[]` if no video                                                                                                   |
| `no_empty_dirs`                      | structure    | movie+tv | ERROR   | ✅  | —   | `fix()` = former `_fix_empty_dirs`                                                                                              |
| `season_structure`                   | structure    | tv       | ERROR   | —   | —   |                                                                                                                                 |
| `episode_renamed`                    | structure    | tv       | ERROR   | —   | —   |                                                                                                                                 |
| `root_video_files`                   | structure    | tv       | ERROR   | —   | —   | conditional: `[]` if no `tvshow.nfo`                                                                                            |
| `dir_naming`                         | naming       | movie+tv | ERROR   | ✅  | —   | `fix()` = former `_fix_dir_naming_from_nfo`                                                                                     |
| `nfo_present`                        | nfo          | movie+tv | ERROR   | —   | ✅  | `from_index` ← `nfo_status=="missing"`                                                                                          |
| `nfo_valid`                          | nfo          | movie+tv | ERROR   | —   | ✅  | branch: movie = title+year, tv = title; conditional `[]` if no NFO; `from_index` ← `nfo_status=="invalid"`                      |
| `nfo_ids`                            | nfo          | movie+tv | dynamic | —   | —   | branch: movie = tmdb+imdb (ERROR if none / WARNING if one), tv = tvdb\|tmdb (static ERROR); conditional `[]` if `nfo_root` None |
| `poster_present`                     | artwork      | movie+tv | ERROR   | —   | ✅  | branch on naming; `from_index` ← `artwork_json.poster`                                                                          |
| `artwork_landscape`                  | artwork      | movie+tv | WARNING | —   | ✅  | `from_index` ← `artwork_json.landscape` (movie-only in DB-mode today — preserved)                                               |
| `season_posters`                     | artwork      | tv       | WARNING | —   | —   | **multi-result**: one per missing season, or one `passed=True` if none                                                          |
| `streamdetails`                      | streams      | movie    | WARNING | —   | —   | conditional: `[]` if `nfo_root` None                                                                                            |
| `no_duplicate_videos`                | dedup        | movie    | ERROR   | —   | —   | movie-only (Phase 30)                                                                                                           |
| `ntfs_safe_names`                    | ntfs         | movie+tv | ERROR   | ✅  | —   | `fix()` = former `_fix_ntfs_names`                                                                                              |
| `category`                           | category     | movie+tv | ERROR   | —   | —   | **dual-purpose**: validates + stashes `ctx.resolved_category`; conditional `[]` if no NFO                                       |
| `episode_nfo`                        | provider_ids | tv       | WARNING | —   | —   |                                                                                                                                 |
| `episode_canonical_uniqueid_present` | provider_ids | tv       | ERROR   | —   | —   | no-op (`passed=True`) if no canonical family / no episode NFO                                                                   |
| `episode_xref_secondary_id_present`  | provider_ids | tv       | WARNING | —   | —   | suggests `backfill-ids`                                                                                                         |
| `episode_xref_imdb_id_present`       | provider_ids | tv       | WARNING | —   | —   |                                                                                                                                 |

### Stage STAGING (enforce/coherence) — all WARNING, read-only

| Check                    | Group     | MT       | Notes                                                                                                     |
| ------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------- |
| `sort_process_coherence` | coherence | movie+tv | wrong-category detection (`tvshow.nfo` in MOVIES / movie NFO in TVSHOWS) — needs `ctx.expected_file_type` |
| `nfo_ids`                | coherence | movie+tv | **name collision** with DISPATCH `nfo_ids` (see §6.1); own logic (tmdb\|imdb, warning only)               |
| `genre_coherence`        | coherence | tv       | classifier → warning if genre implies `TV_PROGRAMS`                                                       |

## 6. Three structural subtleties

### 6.1 `(stage, name)` registry key

`nfo_ids` exists on **both** stages as two genuinely different checks (severity, logic, stage). To keep persisted names unchanged (the golden and `test_coherence_checker` assert on them), **the registry is keyed by `(stage, name)`**, not `name` alone. `get(stage, name)`; CLI `--check <name>` is scoped per command (each command has a fixed stage); `list_specs()` returns the `(stage, name)` pair.

### 6.2 Shared-name, media-type-branching checks

`video_present`, `nfo_valid`, `nfo_ids`, `poster_present`, `artwork_landscape` have the **same name** but media-type-dependent logic. → **one plugin per name**, `media_types={"movie","tvshow"}`, branching on `ctx.media_type`. Not two classes — the golden requires identical names.

### 6.3 Fix-policy asymmetry (resolved: refactor-then-unify)

Today verify auto-fixes only `{dir_naming}`; library validate --fix fixes `{dir_naming, no_empty_dirs, ntfs_safe_names}`. Co-locating `fix()` must NOT make verify start fixing empty-dirs/NTFS (that would be a behavior change). → each orchestrator carries an explicit **fix policy** (allow-set of names). The structural refactor preserves the asymmetry exactly (pinned by the golden); a **final dedicated phase** then unifies verify's policy to the 3-check set as a deliberate, separately-tested change with an explicit golden update. `CheckResult.fixable` stays as the per-result "fixable in principle" signal.

## 7. Data flow

### Central fix helper

```python
# verify/checks/registry.py
def apply_fixes(ctx, failed: list[CheckResult], policy: frozenset[str]) -> list[FixAction]:
    actions = []
    for r in failed:
        if r.name in policy:
            check = registry.get(ctx.stage, r.name)
            if isinstance(check, FixableCheck):
                actions.extend(check.fix(ctx))   # respects ctx.dry_run
    return actions
```

### The four orchestrators (all registry-driven)

1. **Verify pipeline (`Verifier`, DISPATCH)** — `MediaChecker.check_movie/check_tvshow` become the loop, signatures unchanged:
   `results = [r for check in registry.checks_for(DISPATCH, mt) for r in check.run(ctx)]`.
   Fix policy `{"dir_naming"}` (today's exact behavior). check → `apply_fixes` → on rename, **fresh ctx** (new path, fresh NFO cache) → re-check. `_classify` reads `ctx.resolved_category` (set by the category check on the final pass) instead of re-running `classify_from_nfo`. errors = ERROR messages, warnings = WARNING messages (verify's extraction unchanged).

2. **Library validate FS (`validate_library`, DISPATCH)** — same loop; fix policy `{"dir_naming","no_empty_dirs","ntfs_safe_names"}` (today's exact behavior). Extraction by **name** (`errors = [c.name …]`) — different from verify (by message), preserved.

3. **Library validate DB (`validate_from_index`, DISPATCH)** — SQL unchanged, then per row build `IndexContext` and collect `check.from_index(row, ictx)` for `IndexableCheck` plugins; `None` → skipped. Only `{nfo_present, nfo_valid, poster_present, artwork_landscape}` respond → reproduces today's subset exactly. `nfo_status` NULL → `[]` (unflagged), as today.

4. **Enforce coherence (`check_coherence`, STAGING)** — loop, then adapt to `CoherenceResult` at the boundary:
   `CoherenceResult(path, checks=[r.name for r in results], warnings=[r.message for r in results if not r.passed and r.message])`.
   The public `CoherenceResult` type is preserved. The per-media-type order of the `checks` list is reproduced via the `_ORDER` table and pinned by the golden.

### CLI surface (additive — no change when absent)

| Command            | Additions                                      | Stage    |
| ------------------ | ---------------------------------------------- | -------- |
| `verify`           | `--check <name>` (repeatable), `--list-checks` | DISPATCH |
| `enforce`          | `--check <name>` (repeatable), `--list-checks` | STAGING  |
| `library validate` | `--check <name>` (repeatable), `--list-checks` | DISPATCH |

`--check` ⇒ `checks_for(stage, mt)` filtered to the requested names (unknown name → error + list available, exit ≠ 0). `--list-checks` ⇒ print specs (name/group/severity/fixable/idx/description) and exit.

### Web-UI enumeration API (Python only)

`verify/checks/catalog.py` — read-only, JSON-serializable, consumed by the future Web Management UI:

```python
def list_checks() -> list[CheckSpec]   # {stage, name, group, media_types, default_severity, fixable, indexable, description}
def run_check(stage, name, ctx) -> list[CheckResult]
```

## 8. No-behavior-change strategy & testing

### Deterministic order — explicit `_ORDER` table

The registry holds an explicit per-`(stage, media_type)` ordering list, **calibrated from the baseline captured on `main`**, reproducing the current `append` sequence to the character. `checks_for` returns checks in that order. (Single `order` ints can't satisfy movie vs tvshow simultaneously; an explicit table is the auditable solution. `season_posters` emits duplicate names, so ordered comparison — not key-by-name — is mandatory.)

```python
_ORDER = {
  (DISPATCH,"movie"):  ["video_present","not_sample","dir_naming","nfo_present","nfo_valid","nfo_ids",
                        "poster_present","artwork_landscape","streamdetails","no_empty_dirs","category",
                        "no_duplicate_videos","ntfs_safe_names"],
  (DISPATCH,"tvshow"): ["video_present","dir_naming","nfo_present","nfo_valid","nfo_ids","poster_present",
                        "artwork_landscape","season_structure","season_posters","episode_renamed","episode_nfo",
                        "no_empty_dirs","category","root_video_files","episode_canonical_uniqueid_present",
                        "episode_xref_secondary_id_present","episode_xref_imdb_id_present","ntfs_safe_names"],
  (STAGING,"movie"):   ["sort_process_coherence","nfo_ids"],
  (STAGING,"tvshow"):  ["nfo_ids","genre_coherence","sort_process_coherence"],
}
```

### Characterization golden (capture-before / assert-after)

1. **Fixture corpus** covering every branch of every check (most exist in `tests/verify`/`tests/enforce`; fill the gaps: sample, duplicate video, NTFS-illegal, empty-dir, fixable dir-name, root-videos, provider-ids gaps, missing season poster, mis-sort coherence, genre→TV_PROGRAMS).
2. **Baseline capture** (on `main`, BEFORE any extraction — the very first sub-phase): run the **6 public entry points** on the corpus, serialize to golden JSON under `tests/verify/golden/`, commit:
   - `MediaChecker.check_movie` / `check_tvshow` → `list[CheckResult]`
   - `Verifier.verify_movie` / `verify_tvshow` → `VerifyResult` (incl. check→fix→reclassify, dry-run + apply)
   - `validate_library` → `LibraryValidationResult` (FS, incl. `--fix --apply` and dry-run)
   - `validate_from_index` → `LibraryValidationResult` (DB)
   - `check_coherence` → `list[CoherenceResult]` (STAGING)
3. **Post-refactor assertion**: `test_characterization_golden.py` loads the golden and asserts ordered-identical output. This is the formal proof of "no behavior change".

### Test migration

- **Existing tests** (~1900 LOC `tests/verify`, ~97 LOC `tests/enforce/test_coherence_checker`) exercise the public facades (signatures unchanged) → they **keep passing as-is** — the second proof the public contract held.
- **New tests** (the whole point):
  - `tests/verify/checks/test_<group>.py` — each plugin in isolation via `check.run(ctx)` (+ `fix()` / `from_index()`).
  - `tests/verify/checks/test_registry.py` — registration, `checks_for` filtering+ordering, `list_specs`, `get`, unknown name, `(stage, name)` collision.
  - `tests/verify/test_characterization_golden.py` — parity proof.
  - CLI tests for `--check`/`--list-checks` on the 3 commands; `catalog` tests.
- **Regression-test-per-bug**: any defect found during extraction gets a test reproducing it, with the fix.

### Single source & residual-import gate (pre-1.0, no shim)

`Severity`/`CheckResult`/`FixAction` canonical in `base.py`; internal importers repointed, **no re-export** in `checker.py`; `MediaFixer` deleted. Gate: `rg -t py 'from personalscraper\.verify\.checker import.*\b(Severity|CheckResult)\b'` and `rg -t py 'MediaFixer'` → **0** in `personalscraper/` AND `tests/`.

### Per-gate guardrails (CLAUDE.md)

`make lint` (0) · `make test` (all pass, 0 collection ERROR) · `make check` (coverage ≥ 90 %, module-size — each plugin << 800, typed-api/registry guardrails) · residual-import grep = 0 · `python -c "import personalscraper"`. The `CheckContext` NFO cache guards perf (no O(checks) re-parse).

## 9. Error handling & edge cases (all preserved)

| Case                           | Preserved behavior                                                                                                                                                                                                                                                                                                |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFO parse failure              | `ctx.nfo_root()` parses once, catches `ParseError/OSError` → warns + caches `None` (sentinel distinguishes "not parsed" from "parse failed"). Checks see `None` and behave as today. Provider-ids episode checks treat an unparseable episode NFO as "missing canonical" (ERROR).                                 |
| OSError during FS walk         | Orchestrators' **per-item** guard stays (lib-fold M1): `validate_library` → `ValidationItem(status="issues", errors=["os_error: …"])`; `verify_all_*` → `VerifyResult(status="blocked")`.                                                                                                                         |
| A check raises                 | **Propagation, NOT per-check isolation.** Today one raising block aborts the whole `check_movie` → item blocked. The registry loop propagates to the orchestrator's per-item handler (identical). Adding per-check try/except would change which items are blocked → excluded (future enhancement, out of scope). |
| `--check <unknown>`            | error + list available, exit ≠ 0 (additive; only when the flag is used).                                                                                                                                                                                                                                          |
| `from_index` `None` vs `[]`    | `None` = not derivable (skipped in DB-mode); `[]` = derivable, no finding. `nfo_status` NULL → `[]` (unflagged).                                                                                                                                                                                                  |
| `dry_run`                      | carried by `ctx.dry_run`; verify `dry_run` → `ctx.dry_run`; library `apply` → `ctx.dry_run = not apply`. `fix()` respects it.                                                                                                                                                                                     |
| `category` dual-purpose        | check stashes `ctx.resolved_category` on the final pass; `_classify` reads it → one `classify_from_nfo` call instead of two. `classify_from_nfo` is pure → identical output (golden compares output, not call count).                                                                                             |
| Registry order vs import order | the `_ORDER` table governs output order, not import order in `checks/__init__.py` → robust.                                                                                                                                                                                                                       |
| DB-mode landscape quirk        | `artwork_landscape.from_index` is movie-only today — preserved (branches on `media_type`).                                                                                                                                                                                                                        |

## 10. ACCEPTANCE criteria (executable; expanded in the plan)

Per project convention, every criterion is an executable shell command with documented expected output. Indicative set (final ACC-NN numbering assigned in the plan):

- **ACC — characterization parity**: `pytest tests/verify/test_characterization_golden.py -q` → all pass (the 6 entry points byte-identical to the golden).
- **ACC — existing suites intact**: `pytest tests/verify tests/enforce -q` → all pass (public facades unchanged).
- **ACC — registry enumerates all checks**: `python -c "from personalscraper.verify.checks.catalog import list_checks; s=list_checks(); print(len(s))"` → count equals the migrated-check total (≥ 23 across both stages).
- **ACC — granular CLI**: `personalscraper verify --list-checks` → prints the DISPATCH specs; `personalscraper verify --check nfo_present` → runs only that check.
- **ACC — `(stage,name)` collision resolved**: `python -c "from personalscraper.verify.checks.registry import registry, CheckStage as S; print(registry.get(S.DISPATCH,'nfo_ids') is not registry.get(S.STAGING,'nfo_ids'))"` → `True`.
- **ACC — MediaFixer gone / single source**: `rg -t py 'MediaFixer' personalscraper/ tests/` → rc=1; `rg -t py 'from personalscraper\.verify\.checker import.*\b(Severity|CheckResult)\b' personalscraper/ tests/` → rc=1.
- **ACC — module size**: `python3 scripts/check-module-size.py` → rc=0; `verify/checker.py` and every `verify/checks/*.py` under the 800 soft ceiling.
- **ACC — gate**: `make check` → rc=0, coverage ≥ 90 %.
- **ACC — fix-policy unification (final phase)**: a dedicated test proves the verify pipeline now auto-fixes `no_empty_dirs` + `ntfs_safe_names` (deliberate change; golden updated in the same phase).

## 11. Phasing (high level — detailed by the plan)

0. **Baseline golden capture** (on current code, before any extraction) — corpus + serialize the 6 entry points + commit. Gate: golden green on `main`-equivalent code.
1. **Core framework** — `base.py` (types/protocols/context), `registry.py` (registry + `_ORDER` + `apply_fixes`), `catalog.py`. Tests: registry + catalog.
2. **Migrate DISPATCH checks** into `verify/checks/` (by group); `MediaChecker` becomes the facade loop. Per-plugin unit tests. Gate: characterization golden + existing verify suites green.
3. **Consolidate fixes** — co-locate `fix()`; delete `MediaFixer`; `validate_library` uses `apply_fixes`. Gate: golden + library suites green; residual-import grep = 0.
4. **DB-mode unification** — `from_index()` on the 4 indexable checks; `validate_from_index` becomes the loop. Gate: golden (DB entry point) green.
5. **Migrate STAGING (enforce) checks** — `coherence.py`; `check_coherence` becomes the loop with the `CoherenceResult` adapter. Gate: golden (coherence) + `test_coherence_checker` green.
6. **Granular CLI** — `--check`/`--list-checks` on the 3 commands. Tests.
7. **Fix-policy unification (deliberate)** — unify verify's policy to the 3-check set; explicit golden update + dedicated tests.
8. **Feature PR + review** (auto-invoked).

Each phase opens with a Gate and ends with `make check`; strict 0→8 order; the golden is the running parity guard from Phase 0 onward.
