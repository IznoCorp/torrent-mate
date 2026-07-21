# Design — solidify: Architecture Consolidation (SOLID/DRY, backend + frontend)

**Date**: 2026-07-16
**Codename**: `solidify`
**Branch**: `refactor/solidify` (isolated git worktree; single long-lived branch, ONE PR)
**Type**: refactor · **SemVer**: minor (0.49.13 → 0.50.0)
**Merge**: manual squash by operator, after reintegrating `origin/main` into the branch
**Evidence base**: `docs/analysis/2026-07-16-architecture-audit.md` (192 findings, 17 subsystem
audits + adversarial verification + memtrace graph corroboration; 0 findings refuted)

---

## 1. Context and problem statement

The codebase (~105K LOC Python, ~44K LOC TS) has sound bones — Protocol-based pipeline steps,
EventBus with symmetric lifecycle guarantees, capability-keyed provider registry, AST-enforced
core/ layering, single-writer DB discipline, typed REST chain. The debt is **policy
duplication**: the same decision logic re-implemented in 2–6 places. This is not cosmetic —
it has already produced **behavioral drift in production paths**:

- The full pipeline run never reverts unmatched recleans, while the CLI path does
  (PIPELINE-CORE-01).
- Standalone `dispatch` bypasses the seed-obligation delete permit that the full run injects
  (PIPELINE-CORE-01, §7-adjacent).
- The destructive-operations journal (§7) exists only on the movie dispatch branch; TV
  merge-overwrites are not journaled (PIPELINE-CORE-02).
- Verify's dispatch gate and the rescraper disagree on what "poster present" means
  (ARTWORK-POSTER-02); six artwork-presence implementations coexist (ARTWORK-POSTER-01).
- The scanner's five near-identical walkers have already diverged on SIGTERM handling
  (INDEXER-01).
- `grab --dry-run` re-implements the grab chain and skips `rank()` — its output is not the
  real candidate (TORRENT-TRACKERS-05/ACQUIRE-01), violating the operator's dry-run-first
  workflow assumption.

Every future feature pays this tax: a scrape fix must be applied twice (movie/TV), a new
pipeline step touches ≥5 registries, a new web runner copies a fourth lifecycle harness.

## 2. Goals

1. **One owner per policy.** Every architectural decision (step policy, artwork presence,
   NFO validity, run lifecycle, walk skeleton, 202-run polling) has exactly one home; all
   consumers call it.
2. **Eliminate the four operator-named duplication clusters** — pipeline, scraping,
   poster/artwork, trailer — plus the six structural clusters the audit added (web runners,
   CLI boundary, scanner walkers, frontend data layer, frontend god components, docs/gates).
3. **Close the confirmed drift gaps** listed above as explicit, regression-tested conformity
   fixes (each gets a test that reproduces the gap first — operator rule).
4. **Restore honesty of contracts**: no vacuously-true Protocols, no dead typed contracts,
   no dry-run that lies.
5. **Evolutivity headroom**: no module >800 non-blank LOC in refactored areas (hard ceiling
   1000 everywhere); adding a pipeline step / provider / tracker / web runner / frontend
   domain becomes a one-seam change.

## 3. Non-goals

- **No behavior change** outside the enumerated conformity fixes (§6). Scrape results, NFO
  content, dispatch destinations, UI screens: byte-identical where not explicitly fixed.
- **No re-litigation** of settled decisions: stage-catalog single source, serial resolve
  queue (#287), canonical write path (#260), `guarded_api` single auth dependency,
  single-writer DBs + `_build_app_context` composition root, product-intent constitution
  (UI ratified — realign, never raze), typed-API chain (`make openapi`), EventBus/AppContext
  boundary, registry naming conventions, anti-decisions in architecture.md (no
  microservices, no plugin loader…).
- **No new features.** No new endpoints, no new screens, no new CLI commands (except thin
  aliases where a consolidation renames an internal seam).
- **No compat shims** (pre-1.0 rule): internal APIs, helpers and module paths may change
  freely; config/DB/NFO shapes change only if a conformity fix requires it (none currently
  does).

## 4. Constraints

- Work happens in an **isolated git worktree** on `refactor/solidify` (off `origin/main`);
  the main checkout stays untouched (parallel agents + open PR #300).
- **One PR** at the end; before opening it, merge `origin/main` into the branch (merge, not
  rebase — squash PR) and re-run the full gate.
- Every phase ends green: `make lint && make test && make check` + phase-targeted greps
  (Phase Gate Checklist). Frontend phases additionally: `npm run lint && npm run typecheck
&& vitest run` (CI parity), `make openapi` on any route/model change.
- Every `rg` in any phase uses type filters (14 GB fixture rule).
- memtrace `get_impact` is consulted before touching bridge symbols (`_StrictModel`,
  `run_enforce`, `TransportPolicy`, `_build_app_context`, `extract_stream_info`, `classify`).

## 5. Target architecture — the ten seams

### T1 — Unified scrape flow (`scraper/`) [SCRAPER-01..11, MECHANICAL-DUP-05]

**Current**: `movie_service.py` (983 LOC) and `tv_service.py` (812) + `tv_service_write.py`
are parallel near-clones: duplicated `_resolve_external_ids`, `_family_to_client`,
registry-chain fallback loop (×3), folder rename/merge block (inverted `NamingPatterns`
usage), NFO id/title guards, TMDB-hardwired artwork recovery (×2). TV's registry
chain-matching path is dead code; the live path bypasses fallback events.

**Target**:

- `scraper/_match.py` — ONE registry-chain matcher: candidate search → confidence scoring →
  fallback-event emission → exhaustion taxonomy. Parameterized by capability
  (`Searchable`/`MovieDetailsProvider`/`TvDetailsProvider`). Kills the dead TV path; the
  live TV match goes through the chain and emits the same events as movies.
- `scraper/_ids.py` — ONE `resolve_external_ids` + `family_to_client` (used by both
  services + `tv_service_write`).
- `scraper/_writeback.py` — ONE folder rename/merge/case-safe block; ONE artwork-recovery
  helper taking the provider from the item's canonical family (fixes TVDB-only recovery).
- `nfo_generator.py` — shared skeleton builder + per-type sections; id/title guards defined
  once.
- `movie_service.py` / `tv_service.py` shrink to type-specific strategies (target ≤400 LOC
  each): candidate filtering rules, episode mapping (TV), write orchestration order.
- The 6-mixin `Scraper` god-object keeps its public surface (`scrape_movie`,
  `scrape_tvshow`, `scrape_movie_forced`, …) — internals re-wired to the shared modules;
  cross-mixin `Any`-typed contracts replaced by explicit constructor-injected collaborators.

**Provider-separation rule preserved**: TVDB primary for TV, TMDB info+fallback, IMDB info —
the template changes WHO calls, never the provider ORDER (config-driven via registry).

### T2 — Pipeline step-spec + single-owner step policy [PIPELINE-CORE-01/03/04/05, COMMANDS-CLI-01]

**Current**: per-step policy re-decided in three layers (Pipeline adapter / `run_*` module /
CLI command) with two confirmed drift gaps; `Pipeline.run()` special-cases steps inline;
adding a step touches ≥5 registries; every `run_*` hand-rolls results→StepReport +
`ItemProgressed` (emitted post-hoc — fake lifecycle — on sort/dispatch/enforce).

**Target**:

- `pipeline_steps.py` gains a declarative **StepSpec** list: `(name, adapter, critical,
extras_key, skip_when, payload_type)` — validated at import against the web stage catalog
  (catalog stays the SoT, constraint honored). `Pipeline.run()` iterates specs; the
  no-verified-items dispatch skip becomes a `skip_when` predicate returning a skip report
  through the normal `_run_step` path.
- **Step policy single-owner**: revert-unmatched-recleans moves into the process/scrape
  domain flow (one shared phase function used by BOTH `Pipeline._run_process_phase` and
  `run_process`); delete-permit/recorder resolution + post-dispatch maintenance move into
  `run_dispatch` itself (it already receives config + event_bus — NOT AppContext, boundary
  rule honored). Step adapters and CLI commands become thin callers of the same functions.
- **Shared step reporter** (`pipeline_protocol.py`): `StepReport.merge()` +
  `record(report, bus, step, item, status, …)` — increments counters, appends details, emits
  the `ItemProgressed` pair with a normalized status enum. Emission moves INTO the
  processing loops (real "started" before work). The 9 `reports/*Details` payloads become
  REAL: `record()`/finalizers populate `details_payload`; `STEP_REPORT_CONTRACT` validation
  becomes load-bearing (fixes CROSS-CUTTING-01).
- CLI: ONE `per_step_boundary` decorator (extending the existing seed-CLI pattern) owns the
  ~30-line lock/journal/staging/context scaffold for the 9 pipeline commands.

### T3 — Dispatch item template [PIPELINE-CORE-02/07]

**Current**: `dispatch_movie`/`dispatch_tvshow` ~85% duplicated; journal only on movie
replace; four orphan-cleanup implementations run twice per run.

**Target**: one `_dispatch_item(dispatcher, src, category_id, spec)` template with a
`DispatchSpec` per media family: `existing_action` (replace/merge), `transfer_fn`,
`identity_guard` (provider-ID check — §7), `canonical_name_rule`. **Both** destruction paths
(movie replace AND TV merge-overwrite) journal through the shared append-only path (§7 fix,
regression-tested). Orphan cleanup: ONE sweep implementation, invoked once per run at a
defined point (start), parameterized by patterns (`_tmp_dispatch_*`, `_tmp_ingest_*`, stale
locks).

### T4 — Completeness read-model (artwork + NFO + rename) [ARTWORK-POSTER-01/02/03, INDEXER-03, VERIFY-MAINTENANCE-02/03/04, SCRAPER-09]

**Current**: six artwork-presence implementations (verify strict exact-name vs rescraper
canonical vs indexer ×2 divergent scan modes vs web read-model vs scraper), three "NFO
valid" definitions, movie-video-renamed check bolted outside the check catalog. §9 makes
executable completeness THE definition of "acquired" — it must have one implementation.

**Target**:

- `core/artwork_naming.py` becomes ENFORCED canonical: `artwork_status(dir, media_type) ->
ArtworkStatus` (poster/fanart/landscape presence via canonical detection). All six sites
  import it. A layering/AST test forbids new local artwork-glob logic (same mechanism as
  `test_layering.py`).
- `core/completeness.py` (new, stdlib+core only): `nfo_status(nfo_path) -> NfoStatus` (ONE
  validity definition — the strictest currently live: parseable + uniqueids + title),
  `media_completeness(dir, media_type) -> Completeness` composing artwork + NFO +
  renamed-video + trailer presence. Verify checks, indexer enrich/item stages, rescraper
  `_detect_needs`, and the web staging read-model consume it. Scan modes write ONE
  `artwork_json` truth.
- Movie-video-renamed becomes a catalog check (verify), not a bolt-on.

### T5 — Trailer state + download-infra ownership [TRAILERS-01..06, DOCS-ARCH-DRIFT-07]

**Current**: three unreconciled truths (state JSON / indexer `trailer_found` attr /
filesystem); `trailers audit` built on the items-WITHOUT-trailer query (cannot audit
existing trailers); 455-line `TrailersOrchestrator.run()` repeating TrailerState
construction per outcome; the yt-dlp/YouTube stack lives in `scraper/` but is consumed by
`trailers/`.

**Target**:

- **Ownership**: move `youtube_search.py`, `trailer_finder.py`, `ytdlp_downloader.py`,
  `trailers_cache.py`, `json_ttl_cache.py` from `scraper/` into `trailers/discovery/`
  (trailers/ owns its stack; scraper/ keeps only its TMDB-video capability call).
  `keywords_cache` re-uses `json_ttl_cache` (kills the verbatim copy, MECHANICAL-DUP-03) —
  the shared TTL cache moves to `core/` since both scraper and trailers consume it.
- **Single truth**: filesystem is truth for trailer existence (constitution P26: FS = files
  truth); the indexer `trailer_found` attribute is the derived index (refreshed by scan
  enrich via T4 `media_completeness`); the state JSON shrinks to a download-attempt ledger
  (cooldowns, failures) — never a presence claim. `trailers audit` re-built on FS probe (can
  now see existing trailers).
- **Orchestrator decomposition**: `run()` becomes select→resolve→download→place→record
  stages (≤80 LOC each); the 6-outcome ladder collapses into one `TrailerOutcome` factory.
  Placement rules (movies flat / TV `Trailers/`) stay in `placement.py` — already single-home.

### T6 — Web runner engine [WEB-BACKEND-01/02, ACQUIRE-04, MECHANICAL-DUP-04]

**Current**: four detached-runner lifecycles (maintenance / decisions / acquisition /
pipeline-queue) each re-implement spawn→stream→requeue→finalize; atomic run-row reservation
(BEGIN IMMEDIATE + pid-alive guard + INSERT) ×3.

**Target**: `web/_runner_engine.py` — ONE engine owning: run-row reservation, subprocess
spawn + stream capture, heartbeat, requeue on busy (202 + queue step — §6 pattern
generalized from the resolve queue), finalize + terminal status, pipeline.lock tenure for
destructive actions (constraint honored). The four runners become thin configs (command
builder + row table + event names). The resolve queue keeps its SERIAL semantics — the
engine parameterizes concurrency=1 there; nothing about #287 is re-opened.

### T7 — CLI boundary + composition root [COMMANDS-CLI-01..08, INDEXER-08, MECHANICAL-DUP-01]

**Target**: `cli_helpers.boundary()` decorator (lock/journal/staging/context, config/db
resolution) for pipeline + library commands; indexer CLI open_db+migrations ceremony becomes
one context manager; commands that hand-wire dependencies route through
`_build_app_context` (composition-root re-enforcement); `import personalscraper.cli as
cli_compat` facade cycle dissolved (helpers move to `cli_helpers/`); telemetry hooks into
the boundary decorator (covers the ~30 uninstrumented sub-app commands for free);
`commands/watch.py::watch` (cc 131, 339 lines) decomposes into poll/decide/trigger units.
Read-only commands stop paying AppContext construction where a narrower bundle suffices
(COMMANDS-CLI-06) — same boundary decorator gains a `needs=` parameter.

### T8 — Scanner walk skeleton [INDEXER-01/02/05/06, MECHANICAL-DUP-02]

**Target**: ONE `walk(root, visitor, *, budget, shutdown, checkpoint)` in
`_walker.py`; quick/incremental/enrich/full modes become visitors (per-dir + per-file
callbacks). SIGTERM/budget/checkpoint handled once (closes the drift gap). Merkle
short-circuit + bulk-freeze + root-recompute: one implementation. `scan()`'s 22-parameter
signature collapses into a frozen `ScanRequest` dataclass; mode dispatch via a registry
dict. Mock-patch-target hostages in `__init__.py` move to real modules (tests patch the new
seams).

### T9 — Frontend data kit + component decomposition [FRONTEND-DATA-01..07, FRONTEND-COMPONENTS-01..06, MECHANICAL-DUP-11]

**Target** (UI pixels unchanged — realign, never raze):

- `api/` split into per-domain modules (pipeline/staging/acquisition/maintenance/decisions/
  config/registry) behind the generated `schema.d.ts`; ONE copy of the OpenAPI
  type-extraction helpers (`SuccessBody`/`QueryParamsOf`/`RequestBodyOf`); `client.ts`
  shrinks to fetch core + auth + error normalization.
- `hooks/` gains the four shared machines: `useRunToCompletion` (launch-202 → poll →
  terminal outcome — replaces 4 divergent copies), query-key factories per domain, ONE
  WS-event → invalidation map (the 6-name event enum imported from ONE module), shared
  decision mutations (resolve/dismiss/search-override) with one invalidation set.
- `lib/format.ts` — single `relativeTime`/`formatDate`/`formatSize`/outcome-tone maps
  (French labels defined once, §2).
- God components decomposed (layout untouched): `SchemaForm.tsx` (1,611) → schema engine +
  field kit + recursive renderer modules; `Config.tsx` (718, hotspot #1) → page shell +
  `useConfigEditor` hook + panels; the 4 remaining 569-639-line components split
  data-machine/presentation.

### T10 — Docs, gates, packaging [DOCS-ARCH-DRIFT-01..09, MEMTRACE-GRAPH-05]

**Target**: `architecture.md` gains the web/ + acquire/ chapters and drops "no web UI
in-tree" (critical drift); module map refreshed; event-catalog count corrected;
`make check` gains the CI-only gates (openapi drift, version-bump vs main, feature-map,
design-coverage, frontend lint/typecheck/test) so local green == CI green; broken rg flag in
the make gate fixed; package-data declared (22 .sql migrations + web/static); the 6 modules
within 3% of the 1000-LOC ceiling get relief via their theme phases (T1 movie_service,
T7 commands/pipeline, T6 web routes…) — `check-module-size` returns 0 findings at the end.

### Standalone majors folded into phases

- **API family honesty** (API-TRANSPORT-01/03/04): remove NotImplementedError stubs from
  capability Protocols (a client composes a Protocol only if it implements it — registry
  eligibility already handles absence); delete the zero-implementation IDCrossRef machinery
  (YAGNI; the cross-ref flow uses `external_ids`); collapse the dual legacy+capability
  method surfaces (pre-1.0, no shims).
- **Torrent/tracker layer** (TORRENT-TRACKERS-01/03/04/05/08): one provider-error mapping
  table per family; title-quality parsing symmetric across trackers (torr9 included);
  Transmission adder honesty (explicit `UnsupportedCapabilityError` paths, no silent label
  munging); ingest decoupled from qbittorrentapi exceptions via family-level errors;
  `grab --dry-run` runs the REAL chain (search→filter→dedup→rank) with grab suppressed.
- **Acquire hygiene** (ACQUIRE-02/03/05/07/09): dispatch-time reconciliation moves out of
  DeleteAuthority into an explicit post-dispatch acquire subscriber; DETECT logic moves from
  the CLI into the service layer (grab parity); web followed-metadata raw SQL routes through
  store methods (single-writer discipline); QualityProfile dead fields dropped;
  `CrossSeedService.check()` decomposed with one reject-bookkeeping helper.
- **Cross-cutting utils** (CROSS-CUTTING-02/03): ONE durable atomic-write in `io_utils`
  (all 8 sites import it; weaker legacy writer deleted); `lock.py` stops loading config at
  import-default time (path injected by the boundary decorator).

## 6. Conformity fixes (explicit behavior changes — each with a regression test FIRST)

| #   | Fix                                                                            | Constitution / rule served                   |
| --- | ------------------------------------------------------------------------------ | -------------------------------------------- |
| F1  | TV merge-overwrites journaled in the destructive log                           | §7 (append-only trace for every destruction) |
| F2  | Standalone `dispatch` resolves the same delete permit as the full run          | §7 / seed-obligation integrity               |
| F3  | Full run reverts unmatched recleans (parity with CLI path)                     | §2/§8 (no silent divergence)                 |
| F4  | `grab --dry-run` shows the real top-ranked candidate                           | operator dry-run-first rule                  |
| F5  | Verify gate and rescraper agree on artwork presence (canonical detection)      | §9 executable completeness                   |
| F6  | `trailers audit` can audit existing trailers (FS-probe based)                  | §8 (nothing silent)                          |
| F7  | TVDB-only shows can recover artwork (recovery de-hardwired from TMDB)          | §9                                           |
| F8  | Real `ItemProgressed` lifecycle (started before work) on sort/dispatch/enforce | §2 UI truthfulness                           |

Each F# lands in the phase that refactors its seam; the failing test is written before the fix.

## 7. Phasing (dependency-correct; each phase gate-green and committed)

| Phase | Content                                                                                                                                                                                                     | Themes       |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| P0    | Worktree + safety net: characterization tests on scrape/dispatch/verify goldens where refactor targets are thin; gate parity (make == CI, fixes broken rg flag); memtrace impact snapshot of bridge symbols | T10 (gates)  |
| P1    | Step-spec + shared reporter + real Details payloads + in-loop events (F8) + step-policy single-owner (F2, F3)                                                                                               | T2           |
| P2    | Dispatch template + journal both paths (F1) + single orphan sweep                                                                                                                                           | T3           |
| P3    | CLI boundary decorator + composition-root re-enforcement + watch() decomposition + cli_compat cycle                                                                                                         | T7           |
| P4    | Scrape-flow unification (match/ids/writeback/NFO) + module-size relief (F7)                                                                                                                                 | T1           |
| P5    | Completeness read-model (artwork/NFO/renamed) + all six sites aligned (F5)                                                                                                                                  | T4           |
| P6    | Trailers: infra ownership move + single truth + orchestrator decomposition (F6)                                                                                                                             | T5           |
| P7    | Scanner walk skeleton + ScanRequest + merkle single-impl                                                                                                                                                    | T8           |
| P8    | API family honesty + torrent/tracker symmetry + ingest decoupling (F4)                                                                                                                                      | standalone   |
| P9    | Web runner engine + steps_json parser + routes layering + acquire hygiene                                                                                                                                   | T6 + acquire |
| P10   | Frontend data kit (api split, hooks, formatters)                                                                                                                                                            | T9a          |
| P11   | Frontend god-component decomposition (SchemaForm, Config, 4 others)                                                                                                                                         | T9b          |
| P12   | Tests-arch consolidation (web harness ×10→1, registry doubles, fake-TMDB, unit-dir convention) + feature_map refresh                                                                                        | tests        |
| P13   | Docs sweep (architecture.md web chapter, counts, packaging) + module-size zero-findings + `origin/main` reintegration merge + full gate + PR                                                                | T10          |

Phases keep the branch releasable: every phase-gate commit passes the full gate (a
mid-branch merge of main is possible at any phase boundary if PR #300 or others land).

## 8. Testing strategy

- **Characterization first** (P0): where a refactor target lacks behavioral pins (dispatch
  template, scrape write-back, trailer outcomes), goldens/characterization tests pin
  current behavior BEFORE the move; they must cover all entry points and normalize
  non-deterministic fields (operator rule on complete goldens).
- **Regression test per conformity fix** (F1–F8): failing test first, then fix, same phase.
- **Behaviour-preserving phases** (pure consolidation): existing 6000+ tests are the net;
  phase gate = full `make check` + zero-residual-import greps + smoke import. Tests are
  UPDATED to new seams only where they patched internals (mock-target moves are listed per
  phase in the plan).
- **Frontend**: vitest + lint + typecheck per phase; UI snapshots unchanged (realign rule);
  the 390px iframe mobile audit re-run once after P11 (memory rule) — no visual change
  expected.
- **No deferral**: every phase's scope executes fully (event-bus lesson); deviations require
  documented anomaly + operator sign-off.

## 9. Risks and mitigations

| Risk                                                                                                | Mitigation                                                                                                                                        |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Long-lived branch vs moving main (PR #300+)                                                         | Merge `origin/main` into the branch at every phase boundary where main moved; final reintegration merge in P13 (operator instruction).            |
| Blast radius on bridge symbols (`classify`, `run_enforce`, `TransportPolicy`, `_build_app_context`) | `get_impact` before each such phase; characterization pins; these symbols keep signatures unless the phase's plan explicitly says otherwise.      |
| Mock-patch-target breakage across ~679 test files                                                   | Each phase's plan lists the patch-target moves (`rg "patch\(.*<old.path>" -g '*.py' tests/` = 0 at gate).                                         |
| Hidden consumers of "dead" code (IDCrossRef, legacy methods)                                        | Deletion phases start with a repo-wide typed grep + memtrace caller check; anything with a live caller is refactored, not deleted.                |
| Session/API limits mid-fleet (observed during audit)                                                | Phases are independently committable; `/implement:phase` resumes from IMPLEMENTATION.md state.                                                    |
| One giant PR review load                                                                            | Operator's explicit choice; mitigated by per-phase commits with conventional messages + the findings-traceability matrix (§10) as the review map. |

## 10. Acceptance criteria (executable — SH-16)

Run from the worktree root; every ACC must pass before the PR opens.

```bash
# ACC-01 — full gate green
make check && echo ACC-01-OK

# ACC-02 — module-size: zero findings (was 8)
python3 scripts/check-module-size.py && echo ACC-02-OK

# ACC-03 — scraper duplication gone: single definition of the shared helpers
test "$(rg -c 'def _?resolve_external_ids' -t py personalscraper/ | wc -l)" = "1" \
 && test "$(rg -c 'def _?family_to_client' -t py personalscraper/ | wc -l)" = "1" && echo ACC-03-OK

# ACC-04 — one artwork-presence implementation: no local artwork globbing outside core
test "$(rg -l 'poster\.(jpg|png)' -t py personalscraper/ -g '!core/*' | wc -l)" -le 2 && echo ACC-04-OK
# (allowed: NamingPatterns formatting + tests; exact allowlist pinned by the AST guard test)

# ACC-05 — reports contract is load-bearing: every step populates its Details payload
command python3 - <<'EOF' && echo ACC-05-OK
import subprocess, sys
out = subprocess.run(["rg", r"Details\(", "-t", "py", "personalscraper/",
                      "-g", "!api/**", "--count-matches"], capture_output=True, text=True).stdout
assert sum(int(l.rsplit(":",1)[1]) for l in out.strip().splitlines() if l) >= 9, out
EOF

# ACC-06 — TV merge journaled (F1): regression test exists and passes
command python -m pytest tests -k "journal and (merge or tv)" -q --no-header | grep -E "passed" && echo ACC-06-OK

# ACC-07 — dry-run truthfulness (F4): regression test passes
command python -m pytest tests -k "dry_run and rank" -q --no-header | grep -E "passed" && echo ACC-07-OK

# ACC-08 — one walker: scandir walking exists only in _walker.py within scanner/
test "$(rg -l 'scandir' -t py personalscraper/indexer/scanner/ | wc -l)" = "1" && echo ACC-08-OK

# ACC-09 — one atomic write: os.replace confined to io_utils (+ core sqlite)
test "$(rg -l 'os\.replace' -t py personalscraper/ -g '!io_utils.py' -g '!core/**' | wc -l)" = "0" && echo ACC-09-OK

# ACC-10 — frontend: no duplicated format helpers; one poll-202 hook
test "$(rg -c 'function relativeTime|const relativeTime' -g '*.ts*' frontend/src/ | wc -l)" = "1" \
 && test "$(rg -l 'useRunToCompletion' -g '*.ts*' frontend/src/hooks/ | wc -l)" -ge 1 && echo ACC-10-OK

# ACC-11 — frontend gates green (CI parity)
cd frontend && npm run lint && npm run typecheck && npx vitest run --reporter=dot && cd .. && echo ACC-11-OK

# ACC-12 — architecture.md documents web/ and no longer denies it
rg -q "web/" -g 'architecture.md' docs/reference/ && ! rg -q "No network server / web UI" docs/reference/architecture.md && echo ACC-12-OK

# ACC-13 — openapi drift zero
make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts && echo ACC-13-OK

# ACC-14 — no residual imports of moved modules (list finalized per phase; representative)
test "$(rg -c 'from personalscraper.scraper.(youtube_search|trailer_finder|ytdlp_downloader)' -t py personalscraper/ tests/ | wc -l)" = "0" && echo ACC-14-OK

# ACC-15 — version bumped vs main
command python3 scripts/check_version_bump.py --base origin/main && echo ACC-15-OK
```

(ACC greps whose exact allowlists depend on implementation details are finalized — command
included — in each phase file; the list above is the binding minimum.)

## 11. Findings traceability

Theme → audit findings mapping lives in §2 of
`docs/analysis/2026-07-16-architecture-audit.md` (T1–T10 table + standalone majors list).
The PR body will cite: constitution §2/§6/§7/§8/§9 (conformity fixes F1–F8), and the audit
report as evidence. Unverified-status findings are re-confirmed against the code at the
start of their phase (guarantor rule); a finding that fails re-confirmation is dropped with
a note in IMPLEMENTATION.md — never silently.
