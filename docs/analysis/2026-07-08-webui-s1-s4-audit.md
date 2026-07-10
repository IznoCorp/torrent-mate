## TorrentMate Web-UI (S1–S4) Audit — Synthesis Report

Read-only audit of the shipped web-UI waves S1–S4, compared against the binding `docs/reference/web-ui.md` conventions and the per-wave DESIGN/ACCEPTANCE docs. All 28 items below survived adversarial verification (0 refuted, 0 uncertain). Every finding cites concrete file:line and quoted code.

### Executive Summary

**28 confirmed findings.** No `blocker` survived verification (the staging-write finding was correctly downgraded to `high` because the child subprocess still holds the O_CREAT|O_EXCL lock and there is no *double*-execution/corruption — but it lets staging mutate real prod data, which is severe).

**By severity:**
| severity | count |
|---|---|
| blocker | 0 |
| high | 5 |
| medium | 12 |
| low | 11 |
| improvement (as severity) | 0 |

(Note: `improvement` appears as a *kind* on 3 low-severity items; no item carries `improvement` severity after verification.)

**By wave:**
| wave | count |
|---|---|
| S1 | 4 |
| S2 | 10 |
| S3 | 5 |
| S4 | 6 |
| cross | 3 |

**Highest-signal themes:**
1. **Staging is not isolated from prod (ranks 1, 3).** Both apps share config dir → same data_dir/library.db/disks, and share the same Redis stream. The S4 read-only role gate covers only `config.py`, so S2/S3 write endpoints on `tm-staging` mutate/delete real media, and event streams cross-bleed. These two compound each other.
2. **A UI safety lever that does nothing (rank 2).** The `watcher.paused` sentinel is written and shown as "paused" but the daemon never reads it — auto-runs keep firing.
3. **Typed-contract convention broken at the two most important write endpoints (rank 4)** plus scattered/contradictory auth wiring (ranks 14, 24) and un-typed parameterized fetchers (rank 15).
4. **A monotonic-vs-epoch clock confusion (ranks 12, 22)** producing ~1970 timestamps in the RunDetail API contract.
5. **A provably-failing documented acceptance criterion (rank 5, S3 ACC-05).**

**Deduplication applied:**
- `step-timings-monotonic-rendered-as-epoch` + `step-timestamps-monotonic-epoch-mismatch` → **merged into rank 12** (same defect: monotonic clock written, epoch reader for per-step timings).
- `run-toctou-no-lock-acquire` + `run-toctou-not-hardened-like-maintenance` → **merged into rank 9** (same TOCTOU race on POST /pipeline/run).
- Ranks 14 (scattered guard) and 24 (contradictory docstrings) are kept separate — distinct artifacts (redundant code vs contradictory docs) — but 24 is the documentation root-cause of 14; cross-noted.

---

### Findings Table (severity-sorted)

| rank | severity | wave | kind | title | file:line | status |
|---|---|---|---|---|---|---|
| 1 | high | cross | security | S2/S3 write endpoints have no staging role guard | pipeline.py:146-181,219-254; maintenance.py:794-874 | confirmed |
| 2 | high | S2 | bug | Web /watcher pause lever is a no-op | commands/watch.py:246-256 | confirmed |
| 3 | high | S1 | bug | Prod/staging share Redis stream → cross-bleed | config/web.json5:9-10 | confirmed |
| 4 | high | S2 | incoherence | /run endpoints bypass response_model (untyped OpenAPI) | pipeline.py:146-180; maintenance.py:794-877 | confirmed |
| 5 | high | S3 | test-gap | S3 ACC-05 fails as written (422 not 202) | maintenance.py:832-836 | confirmed |
| 6 | medium | S3 | missing-feature | Maintenance history never filters kind=maintenance | RunHistoryTable.tsx:196-221 | confirmed |
| 7 | medium | S2 | bug | PipelineControls swallows all mutation errors | PipelineControls.tsx:68-97 | confirmed |
| 8 | medium | S3 | incoherence | RunDetail shows pipeline stepper for maintenance runs | RunDetail.tsx:136-231 | confirmed |
| 9 | medium | S2 | bug | POST /pipeline/run TOCTOU → orphan 202/run_uid | pipeline.py:146-180 | confirmed |
| 10 | medium | S4 | bug | PUT /config/secrets unlocked read-modify-write of .env | config.py:846-896 | confirmed |
| 11 | medium | S3 | bug | Maint pipeline-lock check non-atomic; actions never hold lock | maintenance.py:844-869 | confirmed |
| 12 | medium | S2 | bug | RunDetail per-step timestamps ~1970 (monotonic→epoch) | pipeline.py:709,742-745,766-769 | confirmed |
| 13 | medium | S1 | security | Login rate-limiter bypassable via XFF spoofing | auth/routes.py:45-64 | confirmed |
| 14 | medium | cross | incoherence | Auth guard scattered per-route (13 double-adds) | pipeline.py + maintenance.py | confirmed |
| 15 | medium | cross | design-gap | 5 parameterized routes bypass typed apiFetch | client.ts:357-412,489-513,593-663 | confirmed |
| 16 | medium | S2 | test-gap | /kill stale-PID branches untested | test_pipeline_routes.py:268-340 | confirmed |
| 17 | medium | S4 | test-gap | Restart-web O_NOFOLLOW guard untested | test_config_routes_write.py:899-1016 | confirmed |
| 18 | low | S2 | incoherence | getPipelineStatus mislabelled 'Public read' | client.ts:316 | confirmed |
| 19 | low | S2 | bug | GET /pipeline/status leaks SQLite conn (lock held) | pipeline.py:92-110 | confirmed |
| 20 | low | S4 | design-gap | POST /validate 409 undocumented | config.py:635-637 | confirmed |
| 21 | low | S3 | improvement | Maint run launch doesn't refresh history table | ActionForm.tsx:310-341 | confirmed |
| 22 | low | S2 | incoherence | Migration 011 comment wrong (julian/monotonic vs epoch) | 011_pipeline_run.sql:12-15 | confirmed |
| 23 | low | S3 | incoherence | output_tail docstring '2000 chars' vs 64 KiB | models/pipeline.py:188-189 | confirmed |
| 24 | low | S4 | incoherence | config.py/maintenance.py auth docstrings contradict | config.py:22-25 | confirmed |
| 25 | low | S4 | test-gap | fsync-before-replace ordering not verified | test_envfile.py:216-234 | confirmed |
| 26 | low | S4 | test-gap | Declared-missing-overlay 404 untested | test_config_routes_read.py:225-228 | confirmed |
| 27 | low | S1 | improvement | deploy.sh doesn't verify served BUILD_COMMIT | scripts/deploy.sh:89-108 | confirmed |
| 28 | low | S4 | improvement | restart-web log O_TRUNC erases prior failure trace | config.py:938-961 | confirmed |

---

### Detail

#### Rank 1 — [high][security] S2/S3 write endpoints have no staging role guard
**Where:** `personalscraper/web/routes/pipeline.py:146-181,219-254`; `personalscraper/web/routes/maintenance.py:794-874`
**Evidence:** `PERSONALSCRAPER_WEB_ROLE`/`_is_staging` appear only in `config.py` (called at 703-704, 869-870, 931-932). `pipeline_run()` does `subprocess.Popen(cmd, ...)`, `pipeline_kill()` does `os.kill(pid, SIGTERM)`, `action_run()` spawns `_spawn_runner(...)` for `risk=destructive` actions — none with a staging check. `ecosystem.config.js` sets `PERSONALSCRAPER_CONFIG=/Users/izno/dev/PersonalScraper/config` for both prod (line 56) and staging (line 77).
**Why:** Both apps read the same data_dir/pipeline.lock/library.db/real disks. A POST to `tm-staging.../api/pipeline/run` launches a real run; `library-clean/run {dry_run:false}` DELETES real files; `/pipeline/kill` SIGTERMs the real prod pid. `web-ui.md:678` falsely claims WEB_ROLE "gates all write endpoints" and `:321` still asserts "S1 is read-only, so staging against real data is safe" — an assumption S2/S3 invalidated.
**Fix:** Extract `require_not_staging` into `web/deps.py` (reads `PERSONALSCRAPER_WEB_ROLE`) and apply to every mutating POST in `pipeline.py` and `maintenance.py`, returning 403 on staging. Or point staging at a separate data_dir + library.db + redis DB. Fix the false doc claims.

#### Rank 2 — [high][bug] Web /watcher pause lever is a no-op
**Where:** `personalscraper/commands/watch.py:246-256`
**Evidence:** The web route writes/removes `data_dir/watcher.paused` (routes/pipeline.py:279-283) and reports `watcher_enabled` from it. But `rg "watcher.paused" -g '*.py'` matches only under `web/*`. The watch loop builds `WatcherInput` from `watch.trigger` and `pipeline.lock` only; `WatcherInput` has no paused field; `WatcherService.evaluate` gates solely on `self._enabled` (static `config.watch.enabled` loaded at boot).
**Why:** Binding contract in web-ui.md:448, pipe-control DESIGN:106/181, ACCEPTANCE:99 all say the loop no-ops while the sentinel exists. It doesn't — the daemon keeps firing FIRE_RUN/FIRE_CROSS_SEED and spawning subprocesses while the UI shows "paused". ACC-04 is vacuous (only `test -f`).
**Fix:** At the top of each cycle, if `(data_dir/'watcher.paused').exists()` skip evaluation/spawning, OR thread a `paused` field into `WatcherInput` with an early IDLE branch. Add a regression test asserting no FIRE_RUN/FIRE_CROSS_SEED while the sentinel exists.

#### Rank 3 — [high][bug] Prod/staging share Redis stream → cross-bleed
**Where:** `config/web.json5:9-10`
**Evidence:** `redis_url: "redis://127.0.0.1:6379/0"`, `stream_key: "personalscraper:events"`; both apps point at the same config. `WebConfig` (conf/models/web.py) has no role awareness. Producers XADD to the shared key (redis_stream.py:214, maintenance/runner.py:351); consumers read it and broadcast to all WS clients (relay.py:160, ws/routes.py:98).
**Why:** Every prod event and every staging `maintenance.run_log` envelope fan out to BOTH prod and staging WebSocket clients. Combined with rank 1, a staging-triggered run's logs stream into the prod UI, misrepresenting what prod is doing. No per-role namespacing anywhere.
**Fix:** Namespace the stream per role (`personalscraper:events:staging`) or use a distinct redis DB for staging (`.../6379/1`), plumbed off `PERSONALSCRAPER_WEB_ROLE` at WebConfig load or a staging-only override.

#### Rank 4 — [high][incoherence] /run endpoints bypass response_model (untyped OpenAPI)
**Where:** `personalscraper/web/routes/pipeline.py:146-180`; `maintenance.py:794-877`
**Evidence:** `@router.post("/run")` with no `response_model`/`status_code=202`, returning `JSONResponse(status_code=202, content=RunResponse(...).model_dump())`. Committed `frontend/openapi.json` documents both as `['200','422']` with empty 200 schema. `client.ts:260` hand-declares `interface RunResponse { run_uid: string }` and casts `as Promise<RunResponse>`. `RunResponse`/`ActionRunResponse` models exist but are unwired.
**Why:** web-ui.md §REST conventions 1 & 7 (binding every wave) mandate the typed Pydantic→OpenAPI→schema.d.ts pipeline with no `any` at any call site — violated at the two primary write endpoints, reintroducing the exact hand-cast anti-pattern the contract exists to prevent. OpenAPI advertises 200 while runtime returns 202. `config.py:902` proves the correct pattern was known.
**Fix:** Set `response_model=RunResponse/ActionRunResponse, status_code=202`, return the model, run `make openapi`, delete the hand-declared interface + casts.

#### Rank 5 — [high][test-gap] S3 ACC-05 fails as written (422 not 202)
**Where:** `personalscraper/web/routes/maintenance.py:832-836`
**Evidence:** Guard: `if action.dry_run == "unsupported" and body.dry_run: raise HTTPException(422, ...)`. Registry: `library-status` is `risk=ro, dry_run=unsupported`. ACC-05 POSTs `{"options":{},"dry_run":true}` and expects a run_uid + history `.kind=="maintenance"`. It gets 422 → `jq` yields null → `GET /history/null` 404s. The project's own `test_maintenance_actions_run.py:488` sends `dry_run:False` for this action, proving the devs knew.
**Why:** A documented acceptance command that provably cannot pass undermines the wave's acceptance evidence.
**Fix:** Change ACC-05 to `dry_run:false` for the read-only action, OR relax the guard so `risk=='ro'` accepts `dry_run:true` as a no-op. Re-exercise ACC-05.

#### Rank 6 — [medium][missing-feature] Maintenance history never filters kind=maintenance
**Where:** `frontend/src/components/pipeline/RunHistoryTable.tsx:196-221`
**Evidence:** `RunHistoryTableProps` has only `onSelect`; query is `{ limit, offset, sort }` — `kind` never set. `Maintenance.tsx:44` renders `<RunHistoryTable onSelect={...} />` with comment `kind filter chips → 5.2`. `HistoryParams.kind` exists and is serialized, but unused here.
**Why:** web-ui.md §S3 + maint-dash DESIGN require `?kind=maintenance` with chips. Backend default is `all`, so the maintenance dashboard intermixes pipeline and maintenance runs — defeating migration 012's unified-store purpose.
**Fix:** Add a `kind?: string` prop, thread into `HistoryParams` and query key, render chips, pass `kind='maintenance'` from Maintenance.tsx.

#### Rank 7 — [medium][bug] PipelineControls swallows all mutation errors
**Where:** `frontend/src/components/pipeline/PipelineControls.tsx:68-97`
**Evidence:** All five mutations define only `onSuccess`; no `onError`/`toast`/`isError`. Global `mutationCache.onError` (client.ts:826-835) handles only 401. Backend raises `HTTPException(409, "Pipeline is already running")` (pipeline.py:159).
**Why:** On a 409 the button re-enables, the run dialog (closed only in `runMutation.onSuccess`) stays open, and nothing indicates the run did not start. Config.tsx implements the full onError/toast/ApiError.detail convention this diverges from.
**Fix:** Add `onError` to each mutation surfacing `error instanceof ApiError ? error.detail : 'Échec…'` via `toast.error`; keep the run/kill dialog open on failure with the 409 detail inline.

#### Rank 8 — [medium][incoherence] RunDetail shows pipeline stepper for maintenance runs
**Where:** `frontend/src/components/pipeline/RunDetail.tsx:136-231`
**Evidence:** RunDetail never references `kind`/`command`/`options_json`/`output_tail`; unconditionally renders `<PipelineStepper steps={data.steps} />` (line 215). For maintenance runs `steps===[]` (steps_json NULL), and `PipelineStepper` treats empty as LIVE → all 9 steps "queued". Reached from `Maintenance.tsx:44-54`.
**Why:** Opening a maintenance run shows a misleading 9-stage pipeline stepper and hides the executed `library-*` command, its options, and the captured 64 KiB `output_tail`. Coherence defect vs the S3 unified run-detail contract; `RunDetail.test.tsx` only tests `kind:'pipeline'`.
**Fix:** Branch on `data.kind`: for `maintenance` render command + parsed `options_json` + `output_tail` log block; keep the stepper only for `pipeline`. Guard PipelineStepper so empty `steps` doesn't fall into all-queued LIVE mode.

#### Rank 9 — [medium][bug] POST /pipeline/run TOCTOU → orphan 202/run_uid *(merged: run-toctou-no-lock-acquire + run-toctou-not-hardened-like-maintenance)*
**Where:** `personalscraper/web/routes/pipeline.py:146-180`
**Evidence:** Route only probes `is_lock_held(...)` then `subprocess.Popen(...)` and returns 202 with `run_uid`. The child acquires the lock (commands/pipeline.py:556) and the loser exits at :557-558 BEFORE writing any history row (pipeline.py:386-394). So the loser's run_uid never gets a `pipeline_run` row → `GET /history/{uid}` 404s forever (pipeline.py:469-480), RunLogFeed dead.
**Why:** Two rapid POSTs, or POST racing a Watcher run, both observe lock-free and get distinct 202s. `O_CREAT|O_EXCL` prevents double execution/corruption, so harm is a client-visible contract violation, not data loss. The SAME feature's maintenance /run closed this identical race with a `BEGIN IMMEDIATE` reservation ("Finding C", maintenance.py:664-672) — the pipeline route was left inconsistent.
**Fix:** Reserve a `pipeline_run` 'running' row for run_uid under `BEGIN IMMEDIATE` before returning 202 (mirroring maintenance); a failed acquire finalizes the reserved row 'error'. At minimum don't return a run_uid the caller can never resolve.

#### Rank 10 — [medium][bug] PUT /config/secrets unlocked read-modify-write of .env
**Where:** `personalscraper/web/routes/config.py:846-896`
**Evidence:** `put_file` runs under module `_write_lock` (config.py:714); `put_secrets` calls `write_env_keys(...)` (line 894) with no lock. `write_env_keys` reads .env → modifies → `os.replace` (envfile.py:60-90). Both handlers are sync `def` (threadpool). `SecretsPutRequest` has no base_sha256/ETag precondition.
**Why:** Two concurrent PUT /secrets each read the same pre-write .env; the second `os.replace` silently drops the first's upserted key (lost update). Realistic cross-tab (PWA mobile-first) collision. `os.replace` atomicity means the loss is silent.
**Fix:** Wrap `write_env_keys` in `put_secrets` with the same `_write_lock` (or a dedicated env lock) spanning the whole read-modify-write.

#### Rank 11 — [medium][bug] Maint pipeline-lock check non-atomic; actions never hold the lock
**Where:** `personalscraper/web/routes/maintenance.py:844-869`
**Evidence:** `is_lock_held(pipeline.lock)` (line 847) is a bare filesystem probe outside `_reserve_run_row`'s `BEGIN IMMEDIATE` and never re-checked before `_spawn_runner` (line 869). Worse: the runner acquires no lock (grep: 0 refs), and write/destructive `library-relink/fix-nfo/dedup-titles/gc/fix-season-counts` acquire none either — only `library-clean --apply`/`validate`/`analyze` do.
**Why:** A pipeline run can grab `pipeline.lock` between the check and the spawn, so a destructive `library-*` action mutates the library/disks concurrently with a pipeline run. DESIGN:173-176 mandates write/destructive actions hold the lock for their whole subprocess lifetime — violated both in the window AND unconditionally.
**Fix:** Re-probe `is_lock_held` immediately before `_spawn_runner` for write/destructive actions and 409 if it appeared; better, have the runner acquire `pipeline.lock` for its whole lifetime per DESIGN.

#### Rank 12 — [medium][bug] RunDetail per-step timestamps ~1970 (monotonic→epoch) *(merged: step-timings-monotonic-rendered-as-epoch + step-timestamps-monotonic-epoch-mismatch)*
**Where:** `personalscraper/pipeline.py:709,742-745,766-769`
**Evidence:** `t0 = time.monotonic()` passed to `update_step` (error + success paths), persisted verbatim to steps_json (pipeline_history.py:191-196, docstring "Monotonic timestamp"). `routes/pipeline.py:498,500` render with `datetime.fromtimestamp(float(s_start), tz=utc)`. Empirically on this host `fromtimestamp(monotonic())` = 1970-01-17. Run-level times and the skipped-dispatch step use `time.time()` (correct) → internal inconsistency.
**Why:** Every non-skipped step reports ~1970 in the typed `GET /history/{run_uid}` StepTiming contract. `elapsed_s` survives (delta of monotonics) and the UI renders only elapsed_s, masking it — but any API consumer of the step timestamps gets garbage.
**Fix:** Record per-step start/end with `time.time()`; keep a separate monotonic delta only for elapsed. Regression test asserting `RunDetail.steps[0].started_at` is post-2020.

#### Rank 13 — [medium][security] Login rate-limiter bypassable via XFF spoofing
**Where:** `personalscraper/web/auth/routes.py:45-64`
**Evidence:** `_client_key` returns `forwarded.split(",")[0].strip()` (LEFTMOST XFF) when the peer is loopback. `conf/models/web.py:28` defaults host to 127.0.0.1; web-ui.md:372 documents a bare `reverse_proxy localhost:8710`, so the peer is always loopback and Caddy appends the real IP → leftmost is attacker-controlled. No ProxyHeadersMiddleware/forwarded_allow_ips/TrustedHost anywhere.
**Why:** The 5-failures/60s login cap is the sole documented brute-force mitigation. Rotating the fake leftmost XFF gives a fresh limiter key per POST → lockout never trips. scrypt still gates each attempt (not full bypass), but the cap is unenforceable.
**Fix:** Trust the RIGHTMOST XFF entry (`split(",")[-1]`), or run uvicorn with `--forwarded-allow-ips=127.0.0.1` and read `request.client.host` after ProxyHeaders resolves it. Add a regression test.

#### Rank 14 — [medium][incoherence] Auth guard scattered per-route (13 double-adds)
**Where:** `personalscraper/web/routes/pipeline.py:150,186,206,222,261,291,371,442`; `maintenance.py:108,302,387,799,885`
**Evidence:** 8 pipeline + 5 maintenance handlers carry redundant `_session: Session = Depends(require_session)` (never referenced) despite all routers mounting inside `guarded_api = APIRouter(dependencies=[Depends(require_session)])` (app.py:118). config.py + version.py have 0 double-adds.
**Why:** web-ui.md §6 (binding S2-S7): "the auth perimeter is a single dependency, not scattered per-route." The coexisting styles make the perimeter non-obvious and invite a future handler that forgets the per-route Depends to ship unauthenticated. No live hole today.
**Fix:** Remove the redundant `_session` params from all 13 handlers, relying on the parent guard as config.py/version.py do. *(Root cause is the contradictory docstrings in rank 24.)*

#### Rank 15 — [medium][design-gap] 5 parameterized routes bypass typed apiFetch
**Where:** `frontend/src/api/client.ts:357-412,489-513,593-609,639-663`
**Evidence:** `apiFetch` (line 155) is typed on generated `paths` but its docstring admits params were deferred to "S2+". `getPipelineHistory`, `getPipelineRunDetail`, `runMaintenanceAction`, `getConfigFile`, `putConfigFile` each use raw `fetch(...)` with interpolated string URLs and a copy-pasted 9-line ApiError block (6 total instances).
**Why:** web-ui.md §7 requires a typed `fetcher<Path>`. A mistyped path is a runtime 404, not a compile error; the 401-detail-extraction logic is duplicated in 6 places. `schema.d.ts` already carries path parameters, so the promised extension is buildable but was never delivered.
**Fix:** Extend `apiFetch` with `params` derived from `paths[P][M]["parameters"]`, route all five helpers through it.

#### Rank 16 — [medium][test-gap] /kill stale-PID branches untested
**Where:** `tests/web/test_pipeline_routes.py:268-340`
**Evidence:** `pipeline_kill` (routes/pipeline.py:243-249) wraps `os.kill` with `except ProcessLookupError`/`except PermissionError`. `TestKillRoute`'s 3 tests never patch `os.kill` to raise (plain MagicMock or short-circuit via is_lock_held). The route reads the PID directly and does not gate on is_lock_held, so a stale lock reaches ProcessLookupError.
**Why:** The dead-PID (stale lock) case — the kill endpoint's whole reason to exist — is the least tested. A regression (500 on dead PID instead of clean idle status) ships unnoticed.
**Fix:** Test writing a stale PID + `os.kill` raising ProcessLookupError → assert 200 + idle + sentinel cleared + `pipeline_kill_process_gone` logged; parallel PermissionError test.

#### Rank 17 — [medium][test-gap] Restart-web O_NOFOLLOW guard untested
**Where:** `tests/web/test_config_routes_write.py:899-1016`
**Evidence:** `config.py:941-945` opens the log with `...|os.O_NOFOLLOW, 0o600` (a shipped security control from PR-review NEW-01). `test_202_pm2_restart_called` uses real `os.open` but never inspects flags; `test_202_oserror_...` replaces `os.open` with a raising MagicMock. Deleting O_NOFOLLOW keeps both tests green.
**Why:** O_NOFOLLOW prevents a pre-planted symlink at the tmpdir log path from redirecting the write. Narrow (local attacker) but a present guard with zero coverage.
**Fix:** Spy on `os.open` (wrap, don't replace) and assert flags include `os.O_NOFOLLOW`; or plant a symlink and assert the OSError/DEVNULL fallback fires.

#### Rank 18 — [low][incoherence] getPipelineStatus mislabelled 'Public read'
**Where:** `frontend/src/api/client.ts:316`
**Evidence:** Docstring says "Public read"; web-ui.md lists `GET /status` under Guard=`session`. Sibling `getHistory` (client.ts:348, same guard) is correctly labelled "Read-only".
**Why:** Not a runtime bug (apiFetch always sends `credentials:'include'`), but contradicts the REST contract and could mislead a maintainer.
**Fix:** Reword to "Session-guarded read — no X-Requested-With header".

#### Rank 19 — [low][bug] GET /pipeline/status leaks SQLite conn (lock held)
**Where:** `personalscraper/web/routes/pipeline.py:92-110`
**Evidence:** `_build_status` does `conn = sqlite3.connect(...)`, one SELECT, returns with no `conn.close()`/`finally`/`with closing(...)` — unlike `pipeline_history` (410) and `pipeline_history_detail` (463) in the same file. `closing` is already imported.
**Why:** On CPython refcount finalization closes the FD/WAL lock near function exit, so practical impact is minimal — but it is fragile (relies on `__del__`, non-deterministic under exceptions/PyPy) and violates the file's own convention.
**Fix:** Wrap in `with closing(sqlite3.connect(str(db_path))) as conn:`.

#### Rank 20 — [low][design-gap] POST /validate 409 undocumented
**Where:** `personalscraper/web/routes/config.py:635-637`
**Evidence:** `except ConfigLoadError as exc: raise HTTPException(409, ...)`. web-ui.md:612 lists only 200/404/422 for /validate; DESIGN §4.2 omits it; schema.d.ts:381-386 documents only 404/422 (the PUT route does declare 409).
**Why:** Typed client has no 409 branch for /validate. Runtime degrades gracefully (Config.tsx generic-toast fallback), so it's a doc/OpenAPI gap.
**Fix:** Add 409 to the /validate row of web-ui.md, regenerate schema, treat 409 as validation-blocking in the frontend.

#### Rank 21 — [low][improvement] Maint run launch doesn't refresh history table
**Where:** `frontend/src/components/maintenance/ActionForm.tsx:310-341`
**Evidence:** Run mutation `onSuccess` sets local state only (no `invalidateQueries`); `RunHistoryTable` uses `useQuery` with no `refetchInterval`; app-wide QueryClient has no interval. `ActionForm` doesn't even import `useQueryClient`.
**Why:** After a 202 the new `pipeline_run` (kind='maintenance') row is absent until re-sort/paginate/reload. Freshness gap, not data loss.
**Fix:** `queryClient.invalidateQueries({ queryKey: ['pipeline','history'] })` in `onSuccess`, or a modest `refetchInterval` while a run is active.

#### Rank 22 — [low][incoherence] Migration 011 comment wrong (julian/monotonic vs epoch)
**Where:** `personalscraper/indexer/migrations/011_pipeline_run.sql:12-15`
**Evidence:** Comment says the columns are "REAL (julian-day float)" and the clock "uses time.monotonic()". Writer stores `time.time()` epoch (pipeline_history.py:105,259); reader treats epoch (routes/pipeline.py:333); web-ui.md:474 says "epoch seconds".
**Why:** Comment-only defect, but it encodes the same monotonic/epoch mental model that produced rank 12 and could lead a maintainer to reintroduce it.
**Fix:** Correct the comment to Unix-epoch seconds (`time.time()`), REAL for sub-second precision.

#### Rank 23 — [low][incoherence] output_tail docstring '2000 chars' vs 64 KiB
**Where:** `personalscraper/web/models/pipeline.py:188-189`
**Evidence:** Docstring "(last ~2000 characters)"; runner `RING_BUFFER_BYTES = 64*1024` (runner.py:52) and persists the full ring (`output_tail=ring.to_str()`). The `[-2000:]` slice (runner.py:620) is a separate `error` field. web-ui.md:561 says 64 KiB.
**Why:** Understates retained output ~32×; consumers size UI/log widgets wrong.
**Fix:** Update the docstring to "(last 64 KiB of subprocess output)".

#### Rank 24 — [low][incoherence] config.py/maintenance.py auth docstrings contradict
**Where:** `personalscraper/web/routes/config.py:22-25`
**Evidence:** config.py: "Auth dependencies are NOT added here — they are wired at registration time (mirroring maintenance.py)." maintenance.py:11-12: "double-added per pipeline.py convention" — and it DOES double-add on all 5 handlers.
**Why:** This documentation contradiction is the root cause of the split-brain guard pattern (rank 14) propagating — each wave copies whichever sibling it read. Both routes are functionally guarded.
**Fix:** Pick the web-ui.md §6 single-perimeter convention, make both docstrings consistent, remove the double-adds, reference web-ui.md §6 as the single authority.

#### Rank 25 — [low][test-gap] fsync-before-replace ordering not verified
**Where:** `tests/conf/test_envfile.py:216-234`
**Evidence:** Two independent `mock.patch` (os.fsync tracking, os.replace bare MagicMock) with no shared parent; assertions only check `len(fsync_calls)==1` and `mock_replace.called`. An implementation calling `os.replace` before `os.fsync` passes unchanged.
**Why:** The test name/docstring promise the crash-safety ordering invariant but don't enforce it. Production ordering (envfile.py:86-90) is correct → test-gap, not bug; same invariant backs config.py PUT.
**Fix:** Record a merged call log (shared list or single-parent MagicMock `.method_calls`) and assert the fsync index precedes the replace index.

#### Rank 26 — [low][test-gap] Declared-missing-overlay 404 untested
**Where:** `tests/web/test_config_routes_read.py:225-228`
**Evidence:** `get_file` has two 404 branches — unknown name (config.py:471-475) and declared-but-absent-on-disk (478-482). Only `test_returns_404_for_unknown_name` (unknown name) exists. The write-side analogue (409, `test_409_known_name_missing_dependency_overlay`) IS tested.
**Why:** web-ui.md:610 binds both 404 sub-cases. A regression returning 200/500 for a deleted declared overlay would escape CI. Production code correct today.
**Fix:** Test unlinking a declared overlay then GET → assert 404; also assert `GET /files` silently omits it.

#### Rank 27 — [low][improvement] deploy.sh doesn't verify served BUILD_COMMIT
**Where:** `scripts/deploy.sh:89-108`
**Evidence:** Health loop asserts only `/api/health == 200`; `local_sha` is used for build/stamp/printf but never compared against a running-process response. No curl of `/api/version`. pm2 restart is async (in-file comment).
**Why:** The OLD process can answer 200 while the new one fails to boot; the script prints "✅ Déployé" for a stale build, defeating the header's "what is live is always verifiable via GET /api/version" invariant. `pip install`/`pm2 start` failures are fail-soft.
**Fix:** After health 200, curl `/api/version`, parse `build_commit`, assert it equals `local_sha` within the retry window, else exit 1.

#### Rank 28 — [low][improvement] restart-web log O_TRUNC erases prior failure trace
**Where:** `personalscraper/web/routes/config.py:938-961`
**Evidence:** Log opened `os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW`; pm2 subprocess stdout/stderr → this truncated log. The `config_restart_spawned` WARNING logs only name+path, not pm2 stderr.
**Why:** web-ui.md §705-706 relies on this file as the only trace of a failed restart (a documented async-202 limitation). An operator retrying a silently-failed restart truncates the first attempt's pm2 error output before reading it — trace destroyed exactly when needed.
**Fix:** Open with O_APPEND (keep O_NOFOLLOW), or per-spawn timestamped filenames pruned to last N with a run marker line.