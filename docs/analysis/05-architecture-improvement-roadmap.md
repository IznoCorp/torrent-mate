# Architecture Improvement Roadmap

> **Metadata** — Date: 2026-05-28 · Version: 0.16.0 · Branch: `feat/registry` · Project status: pre-1.0, single mono-user instance, **not in production** (no back-compat / no migration scripts allowed) · Scope: cross-axis architecture evolution synthesizing the four sibling reports (`01-library-indexer-consolidation.md`, `02-registry merge readiness`, `03-godmodules`, `04-filesystem-decoupling-macfuse-ntfs.md`) into one sequenced plan · Confidence: **High** — every load-bearing claim re-verified against live code; fact-check corrections incorporated (LOC re-measured with the project's own `scripts/check-module-size.py`, layering leaks and event anchors confirmed at exact `file:line`).

---

## 1. Executive summary (TL;DR)

- **The codebase is structurally healthier than `ROADMAP.md` and `docs/reference/architecture.md` claim.** No `make check` module-size breach exists (only two advisory WARNs), `api/` has zero upward leaks, no sibling import cycle exists, and `ProviderRegistry` (P1 of the old roadmap) is already shipped and consumed. **The documentation is stale, not the code.**
- **Three concrete architectural defects block the planned web-facing future** (Web UI / Watcher / Auto-Download consumers): (1) the 5 registry events bypass the `Event` contract and are invisible to envelope serialization and base-`Event` subscribers; (2) `core/` and `conf/` leak imports into `api/` + `logger`, inverting the documented dependency direction; (3) no `schema_version` on the `Event` envelope, making the first cross-process consumer fragile.
- **One near-zero-risk cleanup collapses most horizontal coupling**: `sorter.file_type.VIDEO_EXTENSIONS`/`FileType` is imported by **11 non-sorter subpackages across 23 import lines** — promoting it to a neutral home turns `sorter` back into a pure pipeline step.
- **The big consolidation (library/indexer, sibling report 01) is real but mis-scoped in ROADMAP**: `library/scanner.py` does **not** duplicate the indexer walk (it delegates), but there genuinely are **two `media_item` creators** (`library/scanner.py:691`, `dispatch/media_index.py:406`) and five divergent season-dir regexes to unify.
- **Sequencing verdict**: do the cheap docs re-baseline + three architectural enablers FIRST, then the FilesystemCapability + ServiceContainer layers, then the heavy library/indexer fold, and only AFTER all of that re-open the `architecture.md:381` "no web UI" anti-decision for the P2 Web UI. `feat/registry` (PR #27) must merge first — every plan here assumes a clean post-#27 `main`.

**Verdict**: Proceed with a docs-first re-baseline and three small enablers as the immediate next feature(s); they are the prerequisites that unblock every larger axis and carry low risk.

---

## 2. Current state (evidence-backed)

### 2.1 Package census (non-blank LOC, re-verified)

`indexer/` 16250 · `scraper/` 9312 · `api/` 7434 · `commands/` 4208 · `library/` 4167 · `trailers/` 2953 · `conf/` 2107 · `dispatch/` 2014 · `verify/` **1277** (not 1249) · `sorter/` 904 · `core/` 891. 403 test files. `make check` chains lint(ruff+mypy+logging)+test-cov+module-size+no-broad-registry-catch+typed-api+pragma-discipline+cli-coverage (`Makefile:62-72`).

### 2.2 Layering — NOT acyclic as documented

`docs/reference/architecture.md:304` asserts "core/ and conf/ … depend on nothing in the project." **This is FALSE**, verified:
- `core/circuit.py:35` → `from personalscraper.api._contracts import CircuitOpenError`; `:37` → `personalscraper.logger`.
- `conf/models/api_config.py:11` → `from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry`.
- `conf/classifier.py:22` → `from personalscraper.api._contracts import MediaType`.

So `core/` and `conf/` both depend on `api/`. The dependency direction is inverted: `api/` consumes `core/`'s `CircuitBreaker`, yet `core/` imports `api/`'s `CircuitOpenError`. No sibling-to-sibling cycle exists (`indexer` never imports `library`; `api/` never imports up — confirmed), but the documented invariant is wrong.

### 2.3 The dominant horizontal-coupling edge

`sorter.file_type` exports `VIDEO_EXTENSIONS` + `FileType`, imported by **11 non-sorter subpackages across 23 import lines** (26 total incl. `sorter` itself): `scraper`(7 files), `enforce`(3), `library`(3), `conf`(2), `indexer`(2), `verify`(2), `dispatch`(1), `ingest`(1), `process`(1), `trailers`(1). `sorter` is a pipeline-step package, not a utils package — this makes it an undeclared utility dependency of nearly the whole system.

### 2.4 EventBus & the registry-event inconsistency

`core/event_bus.py`: synchronous in-process bus, frozen `Event` base (`timestamp`/`source`/`event_id`/`correlation_id` via `ContextVar`, **no `version`/`schema_version` field** — grep confirms), MRO-walking dispatch + cache, `_EVENT_CLASS_REGISTRY` auto-populated by `Event.__init_subclass__` for envelope round-trip. 18 `Event` subclasses. **The 5 registry events break the contract**:
- `api/metadata/registry/_events.py:13,40,57,72,90` — `@dataclass(frozen=True)` classes (`ProviderFallbackTriggered`, `ProviderExhaustedEvent`, `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated`) that **do NOT subclass `Event`**.
- `registry/__init__.py:706` — `self._event_bus.emit(event)  # type: ignore[arg-type]`.
- `subscribers/debug_log.py:25` — `bus.subscribe(Event, self.on_event)` never receives them (their MRO is `[dataclass, object]`).
- `events/__init__.py` eager-imports every producer **except** `_events`.

Consequence: registry events carry no `correlation_id`/`timestamp`/`event_id`, cannot be serialized via `event_to_envelope`, and are dropped by base-`Event` subscribers. **This directly blocks the planned P2 Web UI registry consumer.**

### 2.5 AppContext & partial DI

`core/app_context.py`: frozen dataclass `{config, settings, event_bus, provider_registry}`, boundary-only rule enforced by `tests/architecture/test_app_context_boundary.py`. Single true construction site: `cli_helpers/__init__.py:25` `_build_app_context` (invoked `:93`). The pipeline routes the registry to steps via `ctx.extras["registry"]` (`pipeline.py:326`, with an in-code comment calling it an avoid-widening workaround) even though `StepContext.app` already exposes `provider_registry` with full typing. DI is partial: `scraper/orchestrator.py:101/103/113` self-instantiate `NFOGenerator`/`ArtworkDownloader`/`KeywordsCache`; `commands/info.py:59-80` re-builds its own `ProviderRegistry`+`EventBus`+`CircuitPolicy` instead of reading `ctx.obj`.

### 2.6 Two media_item creators + delegating scanner

`library/scanner.py:691` (`_item_repo.upsert`, rich NFO rows w/ seasons/canonical_provider) and `dispatch/media_index.py:406` (`item_repo.upsert`, minimal rows, auto-rebuild via `dispatch/run.py:128`). `library/scanner.py` walks at media-dir granularity then **delegates** the recursive walk to `indexer.scanner.scan(ScanMode.full)` — so the ROADMAP P1 "duplicate walk logic" premise is false. `library/scanner.py` (855 non-blank) has two external consumers blocking naive deletion: `trailers/scanner.py:16` (`extract_nfo_ids`, `parse_title_year`) **and** `commands/library/scan.py:290` (`scan_library`).

### 2.7 Filesystem coupling

No `FilesystemCapability` layer. `dispatch/_transfer.py` `rsync()` (flags at `:106`) and `rsync_merge()` (flags at `:166`) share an **identical 11-flag prefix** but diverge in the tail (`rsync_merge` adds `--backup` + `f"--backup-dir={backup_dir}"` at `:176`; `rsync` adds conditional `--delete`) — they are **NOT byte-identical**; the cleanup is to hoist the shared prefix to a constant. FS-type detection is implemented 3× with divergent timeouts and a `ufsd_NTFS` dead-branch asymmetry (sibling report 04: `indexer/db.py:176`, `scanner/_spotlight.py:89`, `scanner/__init__.py:225`).

### 2.8 Module-size ground truth

`python3 scripts/check-module-size.py` exits 0, only 2 advisory WARNs: `scraper/movie_service.py` **954** (not 927) and `library/scanner.py` 855. The blanket `__init__.py` exclusion (`scripts/check-module-size.py:22`) hides `api/metadata/registry/__init__.py` (689) and `indexer/scanner/__init__.py` (621). ROADMAP P3's "god-module crisis" is largely already resolved.

### 2.9 Strengths to preserve

`PipelineStep` protocol + typed `StepReport` (`reports/` has **9** `*Details` dataclasses, not 10), `STEP_REPORT_CONTRACT`, feature-map JSON design tests, the `tests/architecture/test_app_context_boundary.py` AST test, clean `api/`.

---

## 3. Problems & risks

| # | Severity | Problem | Evidence |
|---|----------|---------|----------|
| P-1 | **Critical** | Registry events bypass the `Event` contract → no envelope, no correlation_id, dropped by base subscribers. Blocks P2 Web UI. | `_events.py:13/40/57/72/90`; `registry/__init__.py:706`; `subscribers/debug_log.py:25`; `events/__init__.py` (omits `_events`) |
| P-2 | **High** | Documented acyclic-layering invariant is false; `core/`/`conf/` leak into `api/`+`logger`. Blocks a clean service/HTTP layer. | `core/circuit.py:35,37`; `conf/models/api_config.py:11`; `conf/classifier.py:22`; vs `architecture.md:304` |
| P-3 | **High** | `sorter.file_type.VIDEO_EXTENSIONS`/`FileType` is a misplaced shared constant pulled by 11 subpackages / 23 lines. | `rg "from personalscraper.sorter.file_type import" -g '*.py'` → 23 non-sorter lines |
| P-4 | **High** | No event `schema_version` → first cross-process/persisted consumer silently breaks on the next event-shape change. | grep `schema_version` in `event_bus.py`/`pipeline_events.py` → 0 hits |
| P-5 | **High** | Two `media_item` creators + a delegating scanner = the dual mental model; ROADMAP P1 wording mis-scopes it. | `library/scanner.py:691`; `dispatch/media_index.py:406`; `library/scanner.py` delegates `scan(ScanMode.full)` |
| P-6 | Medium | No `FilesystemCapability`; NTFS/macFUSE hardcoded; 3 mount-parsers + `ufsd_NTFS` dead-branch; rsync prefix duplicated. | `dispatch/_transfer.py:106,166,176`; `indexer/db.py:176`; `scanner/_spotlight.py:89`; `scanner/__init__.py:225` |
| P-7 | Medium | Partial DI: services self-instantiate; `commands/info.py` re-builds registry. Forces monkeypatch tests; blocks headless container. | `scraper/orchestrator.py:101,103,113`; `commands/info.py:59-80` |
| P-8 | Low | Registry passed via stringly-typed `ctx.extras["registry"]` instead of the typed `ctx.app.provider_registry`. | `pipeline.py:326` |
| P-9 | Low | `__init__.py` blanket size exclusion hides the two largest logic modules. | `scripts/check-module-size.py:22`; `registry/__init__.py` 689; `indexer/scanner/__init__.py` 621 |
| P-10 | Low (docs) | `ROADMAP.md` P1/P3 LOC + premises and `architecture.md:304` are materially stale. | `movie_service.py` 954 (ROADMAP says 927); `scraper/tmdb_client.py` row references a deleted file |

---

## 4. Implementation plan

Sequenced into discrete features compatible with `/implement:feature`. Each respects: **no migration scripts** (pre-1.0, evolve in place), module-size hard ceiling 1000 LOC, regression-test-per-bug, Conventional Commits with `{codename}` scope, phase gates green (`make lint`+`make test`+`make check`), squash merge. **Every phase that moves or deletes a symbol MUST run the mandatory residual-import grep across BOTH `personalscraper/` AND `tests/`** — moving a 23-site constant (Feature B) and deleting `library/scanner.py` (Feature E) will churn many test fixtures; effort estimates account for this.

> **Prerequisite gate**: merge `feat/registry` (PR #27) first — sibling report 02 verdict is CONDITIONAL (Phase 30 open, branch unpushed). Branch all features below off a clean post-#27 `main`.

### Feature A — `docs-rebaseline` (fix, Z+1, branch `fix/docs-rebaseline`)
**Objective**: stop every downstream plan inheriting stale premises. Docs only, no code.
- **Modify**: `docs/reference/architecture.md` (correct `:304` to state `core/`+`conf/` currently leak into `api/`+`logger`, OR add a forward-pointer that Feature C fixes it); `ROADMAP.md` (P1: replace "duplicating walk logic" with "two `media_item` creators + helper re-home" per sibling 01; P3: replace LOC table with `check-module-size.py` output — only `movie_service.py` 954 + `library/scanner.py` 855 exceed 800; delete the `scraper/tmdb_client.py` row — file deleted).
- **Effort**: S · **Risk**: low · **Dependencies**: none.

### Feature B — `media-types` (refactor → minor, Y+1, branch `feat/media-types`)
**Objective**: promote `VIDEO_EXTENSIONS`/`FileType` out of `sorter` to collapse the dominant horizontal edge.
- **Create**: `personalscraper/core/media_types.py` (or extend `text_utils`/`naming_patterns` — choose the existing shared family to minimize new modules). Houses `VIDEO_EXTENSIONS` + `FileType`.
- **Modify**: keep `sorter/file_type.py` re-exporting from the new home for one transitional commit, then rewrite the 23 non-sorter import sites to import from the new home; finally drop the re-export. Preserve public path `personalscraper.sorter.file_type` only if external tests rely on it (verify first).
- **Sub-tasks**: (1) create module + move symbols; (2) update all 23 import lines (`scraper`,`enforce`,`library`,`conf`,`indexer`,`verify`,`dispatch`,`ingest`,`process`,`trailers`); (3) residual-import grep in `personalscraper/` AND `tests/`; (4) regression test asserting `VIDEO_EXTENSIONS` identity from the new path.
- **Effort**: M (S logic, M test-fixture churn) · **Risk**: low · **Dependencies**: Feature A.

### Feature C — `layer-contracts` (refactor → minor, Y+1, branch `feat/layer-contracts`)
**Objective**: invert the `core`/`conf` → `api` leak by moving shared primitives DOWN.
- **Create**: `personalscraper/core/_contracts.py` housing `CircuitOpenError`, `MediaType`, and the `Ranking*` config models (`RankingBonuses`, `RankingConfig`, `RankingCriterion`, `ThresholdEntry`). Add `tests/architecture/test_layering.py` (AST guardrail asserting `core/` and `conf/` never import `api`/`scraper`/`pipeline`/`dispatch`/`verify`/`library`/`indexer`/`trailers`).
- **Modify**: `core/circuit.py:35`, `conf/classifier.py:22`, `conf/models/api_config.py:11` to import from `core._contracts`; have `api/_contracts.py` and `api/tracker/_ranking.py` re-export from `core._contracts` to preserve `api`-side public paths.
- **Sub-tasks**: (1) move definitions; (2) re-point `core`+`conf`; (3) re-export from `api` to keep `api`-consumers working; (4) author the layering AST test; (5) residual grep.
- **Effort**: M · **Risk**: low · **Dependencies**: Feature A. **Note**: check whether any existing test already encodes the false invariant — if a passing layering test exists it must be updated, not just added.

### Feature D — `event-unify` (refactor → minor, Y+1, branch `feat/event-unify`)
**Objective**: unify the event substrate; unblock P2.
- **Modify**: rebase the 5 `_events.py` classes onto `Event` (frozen, `kw_only`); remove `# type: ignore[arg-type]` at `registry/__init__.py:706`; register them in `events/__init__.py`; add `schema_version: int` (default = current version) to the `Event` base (`core/event_bus.py`) and include it in `event_to_envelope`/`event_from_envelope`.
- **Regression tests** (one per bug): (a) every emitted event `isinstance Event`; (b) a base-`Event` subscriber receives a `ProviderFallbackTriggered` emit; (c) `event_from_envelope(event_to_envelope(ProviderFallbackTriggered(...)))` equals the original; (d) `tests/architecture` asserts all `_events.py` classes subclass `Event`.
- **Caveat (missing-angle)**: the indexer outbox persists serialized events — adding `schema_version` and re-shaping the 5 events may require a coordinated in-place rewrite of any stored/outbox rows. Pre-1.0 permits destructive in-place change (no migration script); the phase must verify the outbox table tolerates / is cleared for the new shape rather than silently failing on read.
- **Effort**: M · **Risk**: medium · **Dependencies**: none (do early — P2 depends on it). Can run in parallel with B/C.

### Feature E — `lib-fold` (feature → minor, Y+1, branch `feat/lib-fold`)
**Objective**: single `media_item` creator (sibling report 01's re-scoped P1). The largest dual-mental-model removal.
- **Phased (per sibling 01)**: Phase 0 — unify the 5 season-dir regexes onto `naming_patterns.SEASON_DIR_RE` (+ regression test); Phase 1 — done by Feature A docs; Phase 2 — move `extract_nfo_ids`/`extract_nfo_metadata`/`parse_title_year` out of `library/scanner.py` into `nfo_utils` (unblocks `trailers/scanner.py:16` AND must keep `commands/library/scan.py:290`'s `scan_library` working); Phase 3 (XL, crux) — fold rich `media_item`/season/episode creation into a new indexer scan stage inside `ScanMode.full`, reconcile `dispatch/media_index.py:406` as the second writer, unify canonical-provider extraction with `backfill_ids_canonical` (preserve the 194-show regression guard); Phase 4 — delete `library/scanner.py`; Phase 5 — merge ffprobe into `enrich.py` (resolve OQ HDR/Atmos: add `hdr`/`hdr_type`/`is_atmos` columns in-place or accept documented loss); Phase 6 — re-home validator into a `verify/library_checks.py` plugin (NOT inline — `verify/checker.py` is 788 LOC) and `disk_cleaner` into a `maintenance/` module.
- **Side effect**: shrinks `library/scanner.py` below 800, subsuming its god-module split.
- **Effort**: XL · **Risk**: medium (touches the single-writer DB invariant) · **Dependencies**: Features B (shared constants) + C (layering).

### Feature F — `fs-capability` (feature → minor, Y+1, branch `feat/fs-capability`)
**Objective**: `FilesystemCapability` layer (sibling report 04).
- **Create**: `personalscraper/indexer/_fs_probe.py` (one cached `probe_mount()`/`canonical_fs_type()`, fixes the `ufsd_NTFS` dead-branch) and `personalscraper/indexer/_fs_capability.py` (frozen capability table; `ntfs_macfuse` entry + `unknown` fallback byte-identical to today's rsync flags).
- **Modify**: `db.py:176`, `_spotlight.py:89`, `scanner/__init__.py:225` to delegate to `_fs_probe`; `dispatch/_transfer.py` to consume `capability.rsync_flags` (hoist the shared 11-flag prefix). Author a golden-argv test against the CURRENT code FIRST. Defer the FS-aware drift mtime/ctime knob (high risk) behind a capability defaulting to current NTFS behaviour.
- **Effort**: L · **Risk**: medium · **Dependencies**: none (parallel-able). Prerequisite for headless/dry-run Web UI ops.

### Feature G — `service-container` (refactor → minor, Y+1, branch `feat/service-container`)
**Objective**: complete DI (P3), no framework.
- **Modify**: `scraper/orchestrator.py:101/103/113` to accept `NFOGenerator`/`ArtworkDownloader`/`KeywordsCache` via `__init__`; add production/test/headless factories; fix `commands/info.py:59-80` to read `ctx.obj`; replace `pipeline.py:326` `ctx.extras["registry"]` with `ctx.app.provider_registry`.
- **Effort**: L · **Risk**: medium · **Dependencies**: Feature C.

### Feature H — `service-api` + `web-ui` (feature → minor/major, branch `feat/service-api`)
**Objective**: freeze a read-only service facade, THEN P2 Web UI as a thin WebSocket+REST adapter. **Requires re-opening `architecture.md:381` "no network server / web UI" anti-decision with a new DESIGN doc** before any FastAPI/Flask code.
- **Facade**: `registry.status()`/`operations()` (exist), a `PipelineController` (reuse `pipeline.py` `request_shutdown`), event subscription over the unified substrate + versioned envelope, a read-only config view.
- **Effort**: XL · **Risk**: high · **Dependencies**: D, C, B, F, G all landed.

---

## 5. Acceptance criteria (SH-16 — executable, with expected output)

```bash
# Feature A — ROADMAP matches the size tool exactly
python3 scripts/check-module-size.py 2>&1 | grep -E 'movie_service|library/scanner'
# EXPECT: exactly two WARN lines — movie_service.py 954, library/scanner.py 855

# Feature B — sorter.file_type no longer imported outside sorter/
rg -t py 'from personalscraper.sorter.file_type import' personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: (no output, exit 1)

# Feature C — core/ and conf/ no longer import upward
rg -t py '^from personalscraper\.(api|scraper|pipeline|dispatch|verify|library|indexer|trailers)' personalscraper/core/ personalscraper/conf/
# EXPECT: (no output, exit 1)
python -m pytest tests/architecture/test_layering.py -q
# EXPECT: passed

# Feature D — registry events are real Events, round-trip through envelope
python -m pytest tests/architecture -k 'registry_events_subclass_event' -q
# EXPECT: passed
rg -t py 'type: ignore\[arg-type\]' personalscraper/api/metadata/registry/__init__.py
# EXPECT: (no output, exit 1)
python -c "from personalscraper.core.event_bus import Event; assert hasattr(Event, 'schema_version')"
# EXPECT: (no output, exit 0)

# Feature E — media_item creators reduced to the indexer stage + reconciled dispatch path
rg -c 'item_repo.*upsert' -g '*.py' personalscraper/ | rg -v ':0$'
# EXPECT: the indexer scan stage + one dispatch path only (no library/scanner.py creator)

# Feature F — NTFS rsync flags unchanged; ufsd dead-branch fixed
python -m pytest tests -k 'rsync_argv_golden or canonical_fs_type_ufsd' -q
# EXPECT: passed

# Feature G — orchestrator no longer self-instantiates services
rg 'NFOGenerator\(|ArtworkDownloader\(' -g '*.py' personalscraper/scraper/orchestrator.py
# EXPECT: (no output, exit 1)

# All features — global gate
make check
# EXPECT: exit 0 (lint + test-cov >=90% + module-size + typed-api + pragma + cli-coverage + no-broad-registry-catch all green)
```

---

## 6. Trade-offs & alternatives

- **Fix the layering leak (Feature C) vs. just document it (Feature A)**: documenting is honest but leaves the inverted dependency that a service/HTTP layer would transitively re-pull. Chose to fix because it is M/low-risk and is a hard prerequisite for a clean facade. Rejected: leaving `CircuitOpenError`/`MediaType` in `api/` and having `core/` import them — that is the current broken state.
- **`schema_version` placement (Feature D)**: added to the `Event` base with a default rather than per-event, so all 18+5 events inherit it for free and the envelope is uniformly versioned. Rejected: a separate envelope-only version field — would not survive in-process subscribers reasoning about event shape.
- **Move `VIDEO_EXTENSIONS` to `core/media_types.py` vs. `text_utils`/`naming_patterns` (Feature B)**: prefer an existing shared family to avoid module proliferation, but `core/media_types.py` keeps it discoverable next to the future capability work. Either satisfies the acceptance grep; owner picks.
- **Re-scope vs. delete `library/scanner.py` (Feature E)**: a verbatim delete would break `commands/library/scan.py:290` and `trailers/scanner.py:16`. Chose phased helper re-home then fold — the only safe path given two external consumers.
- **FS drift mtime knob (Feature F)**: deferred. Touching tier-1 fingerprinting (`fingerprint.py:81`) risks perpetual re-hashing; defaulting to current NTFS behaviour keeps Phases 1-4 byte-identical and isolates the high-risk change.
- **Facade `__init__.py` size policy (P-9)**: deferred to an owner decision (see Open Questions) rather than forced — tightening the checker without first refactoring `registry/__init__.py` (689) / `indexer/scanner/__init__.py` (621) into shims would turn the gate red.

---

## 7. Effort & sequencing

**Quick wins (do first, low risk):** A (docs, S) → B (media-types, M) and C (layer-contracts, M) and D (event-unify, M) — B/C/D are independent and can be parallelized after A. These four remove the stale-premise trap and the two enablers (event substrate + layering) that everything web-facing needs.

**Mid-tier:** F (fs-capability, L) and G (service-container, L) — independent of each other; F has no dependencies, G depends on C. Both improve testability/headless readiness.

**Heavy lifts:** E (lib-fold, XL — depends on B+C) is the single largest piece and should run after the enablers stabilize; it also subsumes the `library/scanner.py` god-module split. H (service-api + web-ui, XL/high) is last and gated on D+C+B+F+G plus the formal anti-decision reversal.

**Recommended order:** PR #27 merge → A → (B ∥ C ∥ D) → (F ∥ G) → E → H.

**Note on god-modules (sibling 03):** `movie_service.py` (954) is only 46 lines from the 1000 hard ceiling — extract its `:167-421` `_restore_from_db` block to `scraper/_movie_restore.py` (re-export to preserve `MovieServiceMixin`) as a standalone S/M quick win if a feature is about to grow it; otherwise monitor.

---

## 8. Open questions

1. **Web UI anti-decision** (`architecture.md:381`): will the owner formally reverse "no network server / web UI" with a new DESIGN doc? P2 cannot proceed conformantly until then.
2. **Facade `__init__.py` size policy** (`scripts/check-module-size.py:22`): subject `registry/__init__.py` (689) and `indexer/scanner/__init__.py` (621) to the guard (requires refactoring them into shims first), or keep the exclusion by policy?
3. **EventBus transport**: stays strictly in-process (Web UI polls via REST + process-local WebSocket bridge), or does the Watcher service eventually need a cross-process bus? The versioned envelope (Feature D) is needed either way, but the answer affects H's transport design.
4. **`dispatch/media_index.py:406`**: permanent second `media_item` creator, or fully subsumed by the consolidated indexer scan stage in Feature E? Affects the single-writer invariant (`architecture.md:238`) and E's Phase 3 scope.
5. **HDR/Atmos fidelity** (Feature E Phase 5): add `hdr`/`hdr_type`/`is_atmos` columns to `media_stream` in-place and populate in `enrich.py`, or accept the documented fidelity loss when dropping the ffprobe `analyze_library` path?
