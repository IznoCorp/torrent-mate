# Phase 05 — PR fixes cycle 1

## Gate

- [ ] PR #230 open, CI green on HEAD, review cycle 1 findings consolidated (4 agents:
      code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer).

Findings are cited as F* (code-reviewer), SF-* (silent-failure), TC-* (test-analyzer),
CE-* (comment-analyzer). Every code-bug fix ships its failing-first regression test
(project rule: test de régression par bug).

## Sub-phases

### 5.1 — Backend write-path correctness (R2, R6, R8 + pin tests)

**Files**: `personalscraper/web/routes/config.py`, `tests/web/test_config_routes_write.py`

1. **TOCTOU (F1/SF-06/TC-01, MAJOR)**: move the sha256 precondition (lines ~651-659) AND the
   `validate_candidate` call INSIDE `with _write_lock:` so the compare-and-write is atomic.
   Regression test: two threads PUT the same file with the same valid `base_sha256`, a
   `threading.Barrier` inside a patched `validate_candidate` forcing overlap → exactly one 200
   and one 412, file content = the 200 writer's. Replace the vacuous
   `test_writes_are_serialized` (`hasattr(lock, "acquire")`) with this behavioral test.
2. **ConfigConflictError → 500 (F2/SF-11/TC-02, MAJOR)**: `except ConfigConflictError` → 422
   with the conflict message, in BOTH `validate_file` and `put_file` (it is a sibling of
   `ConfigValidationError`, import from `personalscraper.conf.overlay`). Tests: unit
   (validate_candidate propagates it) + route tests (validate + PUT return 422 not 500 when the
   candidate introduces a key owned by another overlay).
3. **ConfigLoadError misattribution (SF-03, MEDIUM)**: in `put_file`, `name` is already
   whitelist-checked — a `ConfigLoadError` there can only mean another declared overlay is
   missing on disk. Return 409 with `str(exc)` (and log it) instead of the false
   404 "Unknown config file". Keep 404 for the validate_file unknown-name case (where the name
   is NOT pre-checked). Tests for both.
4. **Path traversal pin tests (TC-07, MEDIUM)**: parametrized GET+PUT with `../x.json5`,
   `/etc/passwd`, `.backups/paths.json5.x.json5` → 404, nothing written outside config_dir.
5. **local.json5 contract tests (TC-08, MEDIUM)**: GET absent local.json5 → 404; PUT absent
   local.json5 with non-empty sha → 412 (the "" convention converse).
6. **Prune-order assertion (TC-09)**: strengthen `test_backup_prune_keeps_10` — survivors are
   exactly the 10 most recent timestamps.

**Commit**: `fix(config-editor): atomic sha precondition + conflict/load error mapping`

### 5.2 — Backend error surfacing + secrets hardening (R3, R9, R11-13, SF-15/16/19, TC-10)

**Files**: `personalscraper/web/routes/config.py`, `personalscraper/conf/envfile.py`,
`personalscraper/conf/loader.py`, `personalscraper/web/models/config.py`,
`tests/web/test_config_routes_write.py`, `tests/web/test_config_routes_read.py`,
`tests/conf/test_envfile.py`

1. **.env newline injection (F3/SF-05/TC-03, MAJOR — security)**: reject values containing
   `\r`/`\n` with 422 in `put_secrets` (or a field_validator on `SecretsPutRequest`), AND make
   `write_env_keys` raise `ValueError` on such values (defense in depth). Tests: PUT with
   `"x\nWEB_PASSWORD_HASH=evil"` → 422, `.env` untouched, injected key NOT present; envfile
   unit test.
2. **Secrets empty dict (TC-10)**: PUT `{}` → 422 "no keys provided" (pin the contract); test.
3. **envfile fsync (SF-12, MEDIUM)**: add flush+fsync before `os.replace` (parity with
   put_file); adapt the atomicity test if needed.
4. **get_files silent local.json5 failure (SF-04, MEDIUM)**: log
   `local_json5_unreadable` (same event as `_local_keys`) in the bare `except` at ~383-386.
5. **\_build_config over-broad relabel (SF-10, MEDIUM)**: catch
   `pydantic.ValidationError` specifically for the ConfigValidationError wrap; let other
   exceptions propagate (server bugs must be 500, not "invalid config"). Loader tests stay green.
6. **/status 500 on missing master (SF-13, MEDIUM)**: guard `_boot_hashes`' master load — on
   ConfigLoadError/ConfigValidationError raise HTTPException 500 with an explicit
   "config dir unreadable" detail + warning log (not a bare traceback). Test with a removed
   config.json5.
7. **secrets GET fail-soft mismatch (SF-15)**: log a warning when `.env.example` is absent in
   `get_secrets` (GET stays 200-empty; PUT stays 404 — document the asymmetry in docstrings).
8. **Corrupt json5 on GET file (SF-16)**: catch the parse error in `get_file` → 422 with
   "JSON5 parse error…" detail; test.
9. **422 detail path leak (SF-19)**: strip the absolute config-dir prefix from
   ConfigValidationError fallback details before returning them.

**Commit**: `fix(config-editor): secrets value hardening + error surfacing in config routes`

### 5.3 — Status/restart contract (R4 backend, R5 + CE-03)

**Files**: `personalscraper/web/routes/config.py`, `personalscraper/web/models/config.py`,
`personalscraper/web/app.py`, `tests/web/test_config_routes_read.py`,
`tests/web/test_config_routes_write.py`

1. **Eager boot snapshot (F4/SF-08/CE-03, MAJOR)**: capture the config hash snapshot at app
   creation (in `create_app`, storing on `app.state.config_boot_hashes`) instead of lazily on
   first /status. Keep `_boot_hashes` as the accessor (idempotent). On PUT of a file ABSENT
   from the snapshot (e.g. local.json5 created post-boot), add its pre-write hash ("" for
   created files) so it becomes stale-tracked. A snapshot-listed file now MISSING on disk
   counts as stale. Tests: PUT-before-any-status flags stale; created local.json5 flags stale;
   deleted overlay flags stale.
2. **restart_configured in status (TC-06/CE-04, MAJOR)**: add `restart_configured: bool`
   (PERSONALSCRAPER_PM2_NAME set) to `ConfigStatusResponse` so the UI can hide the restart
   button per DESIGN §4.2/§5. Test both values.
3. **Restart spawn logging (SF-02, MAJOR — backend half)**: log the spawn
   (`config_restart_spawned`, pm2 name) and redirect the shell's output to a log file under
   data_dir (e.g. `data_dir/restart-web.log`, truncate per spawn) instead of DEVNULL, so a
   failed pm2 invocation leaves a trace. Test asserts Popen called with the log file handle.

**Commit**: `fix(config-editor): eager boot snapshot + restart_configured + restart spawn trace`

### 5.4 — Runner logging + test-quality fixes (R19, R14)

**Files**: `personalscraper/web/maintenance/runner.py`,
`tests/unit/web/maintenance/test_runner.py`, `tests/conf/test_validate_candidate.py`

1. **\_terminate_quietly silent swallow (SF-09, MEDIUM)**: log
   `maintenance_runner_terminate_failed` (warning, with pid when available) in the except
   before `pass`; `_kill_child_group` fallback paths keep working. Test: terminate raising →
   warning logged.
2. **Vacuous ContextVar thread test (TC-04, MEDIUM)**: rewrite
   `test_concurrent_calls_no_cross_contamination` with RELATIVE `data_dir` values per config
   dir + a barrier forcing overlap, asserting each thread's `config.paths.data_dir` resolved
   under its own project root (would fail on cross-contamination).

**Commit**: `fix(config-editor): log terminate failures + real ContextVar isolation test`

### 5.5 — OpenAPI regeneration

`make openapi` after 5.3's model change; commit `frontend/openapi.json` +
`frontend/src/api/schema.d.ts`.

**Commit**: `chore(config-editor): regenerate OpenAPI after status contract change`

### 5.6 — Frontend: 422 detail transport (R1/SF-01, CRITICAL + SF-14)

**Files**: `frontend/src/api/client.ts`, `frontend/src/pages/Config.tsx`,
`frontend/src/components/config/SchemaForm.tsx` (only if summary rendering lands there),
`frontend/src/pages/Config.test.tsx`, `frontend/src/hooks/useConfig.test.tsx`

1. **ApiError drops non-string detail (SF-01, CRITICAL)**: in `apiFetch` (and the config
   wrappers' error paths), when `json.detail` is not a string, store `JSON.stringify(json.detail)`
   so `extractValidationErrors` receives the real array. Regression test at the TRANSPORT level:
   mock `fetch` returning a real 422 Response with an array detail body → assert the mapping
   reaches the form (NOT a hand-built ApiError — the vacuous pattern that masked this).
2. **Unmatched-error black hole (SF-14, MEDIUM)**: after mapping loc→path, any errors whose
   path matches no rendered field (or an empty mapped set) must surface: toast
   "Validation échouée — N erreur(s)" listing the unmatched messages. Test with a model-level
   error (`loc: []`).

**Commit**: `fix(config-editor): transport 422 detail arrays to the form + unmatched-error toast`

### 5.7 — Frontend UX honesty (R4 frontend, R10, R7)

**Files**: `frontend/src/pages/Config.tsx`, `frontend/src/components/config/SchemaForm.tsx`,
`frontend/src/components/config/FileList.tsx` (test only), `frontend/src/pages/Config.test.tsx`,
`frontend/src/components/config/SchemaForm.test.tsx`

1. **Restart button + toast honesty (SF-02/TC-06/CE-04, MAJOR)**: hide the restart button when
   `status.restart_configured === false` (per DESIGN); replace the "la page va se rafraîchir"
   promise with an honest toast ("Redémarrage programmé — la connexion va se couper puis se
   rétablir.") — no fake auto-refresh claim. Tests: button hidden when not configured; restart
   click flow success + 404 toast (first coverage of the restart flow, TC-06).
2. **Save discards warnings/restart_required (SF-07, MEDIUM)**: consume `PutFileResponse` —
   toast warnings when non-empty; if `restart_required`, show the info immediately (the eager
   snapshot + invalidated status query now backs the banner). Test.
3. **Shadowed-key warning chip (TC-05, MAJOR — DESIGN §5 promised)**: SchemaForm renders a
   warning chip/hint on top-level fields whose key is in the file's `shadowed_keys`
   ("écrasée par local.json5 — cette modification n'aura pas d'effet"). Config.tsx passes
   `fileQ.data.shadowed_keys` down. Tests: chip renders for a shadowed key; FileList "shadowed"
   badge assertion (currently unasserted).

**Commit**: `fix(config-editor): restart honesty + save warnings + shadowed-key chips`

### 5.8 — Docs + ACCEPTANCE corrections (CE-01/02/03 + minors)

**Files**: `docs/features/config-editor/ACCEPTANCE.md`, `docs/reference/web-ui.md`,
`docs/reference/runbook-post-merge.md`, `.env.example`, `ecosystem.config.js`,
`personalscraper/web/models/config.py`, `personalscraper/conf/loader.py`,
`personalscraper/conf/envfile.py`, `personalscraper/web/routes/config.py` (docstrings only)

1. **ACC-06 count (CE-01)**: expected ownership count 28 → 26, comment naming the two
   ownerless default-only keys (`process_clean`, `sort`). (Adding overlay files for them is a
   config-surface decision left open — see cycle report.)
2. **ACC-03 (CE-02)**: capture the PUT body to a file and jq that; drop the bogus follow-up GET.
3. **ACC-02 (CE-03)**: prime `GET /status` before the write (still correct after the eager
   snapshot — keeps the ACC deterministic on any daemon build).
4. **web-ui.md**: snapshot wording now "captured at app startup"; document the
   declared-but-missing-on-disk 404/omission behavior of the files endpoints; envfile
   section-rule ACCUMULATOR-RESET semantics; runbook: warn the 202-POST really restarts prod,
   assert read_only in the staging check.
5. **Docstring nits (CE improvements)**: FileInfo example "config.json5" not "master.json5";
   validate_candidate docstring (real differences: returns warnings, accepts replaced; "without
   writing" not "without touching"); module docstring GET /secrets grouping note +
   resolve_config_path 4-level fallback; `role` passthrough behavior documented.
6. **.env.example / ecosystem.config.js**: "hidden button" claim is now TRUE after 5.7 — keep,
   but reword to "404 + button hidden in the UI".

**Commit**: `docs(config-editor): correct ACCEPTANCE + reference docs per review cycle 1`

## Coherence gate → cycle re-review

- [ ] `make check` green; frontend typecheck + lint + vitest green; `make openapi` drift zero
- [ ] Every regression test above fails on the pre-fix code path (spot-verified during dev)
- [ ] Push → CI green → re-run review cycle 2
