# Phase 06 — PR fixes cycle 2

## Gate

- [ ] Phase 5 merged into the branch, CI green on HEAD (fa0758e3), cycle-2 review done
      (code-reviewer + silent-failure-hunter, adversarial re-review of the phase-5 fixes).

Cycle 2 verified all 19 cycle-1 findings RESOLVED. Retained new/residual findings below
(F* = code-reviewer, NEW-* = silent-failure). Every code-bug fix ships a failing-first
regression test.

## Sub-phases

### 6.1 — Backend: complete control-char guard + harden restart spawn

**Files**: `personalscraper/web/models/config.py`, `personalscraper/conf/envfile.py`,
`personalscraper/web/routes/config.py`, `tests/conf/test_envfile.py`,
`tests/web/test_config_routes_write.py`

1. **Second-order .env injection (F1, MEDIUM — security)**: the control-char guard rejects only
   `\r`/`\n`, but `write_env_keys` re-parses with `str.splitlines()`, which ALSO splits on
   `\x0b \x0c \x1c \x1d \x1e \x85    `. A value `"v\x0bINJ=evil"` passes both guards,
   is written as one line, then a LATER upsert re-splits it → `INJ=evil` becomes a real `.env`
   line. Fix BOTH layers: reject any character in the full `str.splitlines()` separator set (or
   simplest robust rule: reject any C0 control char except `\t`, plus `\x85    `) in
   `SecretsPutRequest._reject_control_chars` AND `write_env_keys`. ALSO switch `write_env_keys`'
   existing-file re-parse from `.splitlines()` to `.split("\n")` (defense in depth — only real
   newlines delimit .env lines). Regression tests: PUT `/secrets` with `"v\x0bINJ=evil"` → 422,
   `.env` untouched, `INJ` never appears after a second upsert; envfile unit test over the full
   separator set.
2. **restart_web log open unguarded + unlogged 500 (NEW-01, MEDIUM)**: `open(log_path, "w")`
   before `Popen` can raise `OSError`/`PermissionError` → unhandled 500 with no server trace
   (a NEW failure mode the DEVNULL version could not hit). Wrap in try/except:
   `logger.error("config_restart_log_open_failed", path=..., error=...)` then fall back to
   `subprocess.DEVNULL` so the restart still proceeds (don't fail the restart because logging
   failed). Close `log_fh` in the parent after `Popen` (child keeps its dup) — fixes the FD
   leak (F2). Test: monkeypatch `open` to raise → endpoint still 202, DEVNULL used, error
   logged.
3. **Predictable shared temp log (F3, MINOR — CWE-377)**: open the log with
   `os.open(path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW, 0o600)` wrapped to a file
   object (refuse to follow a pre-planted symlink) instead of a bare `open(..., "w")`. Keep the
   fixed filename (single-user host) but O_NOFOLLOW closes the truncation-via-symlink vector.
4. **Restart log level (NEW-03 partial)**: log the spawn + log-file path at `logger.warning`
   (was `info`) so a failed async restart surfaces in default operator log views. (The full
   "poll /status after 202" enhancement is recorded as an open item for the operator in the
   cycle record — not built here, per the DESIGN's write-only+restart-badge model.)

**Commit**: `fix(config-editor): close .env control-char injection + harden restart spawn`

### 6.2 — Frontend: surface backend error detail on string-detail failures

**Files**: `frontend/src/pages/Config.tsx`,
`frontend/src/components/config/SecretsTab.tsx`, `frontend/src/pages/Config.test.tsx`,
`frontend/src/components/config/SecretsTab.test.tsx` (create if absent)

1. **String-detail save/validate errors discard the message (NEW-02 / F4, MEDIUM)**: phase 5
   made `put_file` return string-detail 422 (ConfigConflictError / non-pydantic
   ConfigValidationError), 409 (ConfigLoadError), plus 403 — the backend deliberately sanitized
   these to name the conflicting key / missing overlay, but `handleSave`/`handleValidate` fall
   through to the generic `toast.error("Échec de l'enregistrement.")` and drop `err.detail`. In
   the fall-through (after the 412 dialog + parseable-422 field mapping), surface
   `err.detail` when it is a non-empty string:
   `toast.error(err instanceof ApiError && err.detail ? err.detail : "Échec de l'enregistrement.")`.
   Apply to both handlers. Tests: 409/422-string/403 → toast carries the backend detail.
2. **SecretsTab blanket catch (NEW-04 / SF-17, LOW-MEDIUM)**: `catch { toast.error("…") }`
   discards the new backend 422 details (control-char rejection echoes the offending key;
   "no keys provided"). Change to
   `catch (err: unknown) { toast.error(err instanceof ApiError ? err.detail : "Échec de l'enregistrement des secrets."); }`
   (import ApiError). Test: PUT rejected 422 → toast shows the backend detail; network error →
   generic message.

**Commit**: `fix(config-editor): surface backend error detail on config + secrets save`

### 6.3 — Docs: record the async-restart limitation

**Files**: `docs/reference/web-ui.md`, `docs/features/config-editor/ACCEPTANCE.md` (only if a
criterion references restart detection)

1. Document (web-ui.md S4 restart section) that `POST /restart-web` answers 202 BEFORE the
   detached pm2 restart runs, so a failed restart (pm2 not on PATH, wrong name) is not surfaced
   to the caller — the trace is the `torrentmate-restart-web.log` file + the warning log line.
   Note the "poll /status after 202" enhancement as a future improvement (not implemented).

**Commit**: `docs(config-editor): document async restart 202-before-spawn semantics`

## Coherence gate → cycle-3 re-review (or merge)

- [ ] `make check` exit 0; frontend typecheck + lint + vitest green; `make openapi` drift zero
      (no model change in this phase — expect zero regen)
- [ ] Every regression test fails on the pre-fix code path
- [ ] Push → CI green → re-review cycle 3 (expected clean → merge)
