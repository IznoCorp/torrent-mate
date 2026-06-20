# Phase 5 — HTTP API (`[ui]` extra) + CLI + JSON Schema + ACCEPTANCE

**Goal:** expose the config service over a **local, loopback** HTTP API (the contract the
PR-2 Vue UI consumes), a thin `kanban config` CLI, and a JSON Schema for editor-guided
editing (DESIGN §7, §12). FastAPI ships as an **optional `[ui]` extra**; the daemon must
never import it.

**Files:** `src/kanbanmate/http/__init__.py` + `app.py` (new — a top-level **entrypoint**, NOT
under `adapters/`: it imports `app.config_service`, and the layering guard forbids
`adapters → app`), `src/kanbanmate/cli/config.py` (new — a Typer **sub-app** registered via
`add_typer`), `src/kanbanmate/assets/pipeline.schema.json` (new), `pyproject.toml` (add `[ui]`
extra + `assets/*.json` package-data), `ACCEPTANCE.md` (new for this feature),
`tests/http/test_http_config.py` (new), `tests/cli/test_config_cli.py` (new),
`tests/test_no_fastapi_in_daemon.py` (new — a runtime check, distinct from the static
`tests/test_layering.py`).

### 5.1 — `[ui]` optional extra + the daemon-no-FastAPI runtime guard

Add `fastapi` + `uvicorn` to a `[project.optional-dependencies] ui = [...]` group. Add a
**runtime** test (NOT the static `tests/test_layering.py`, which only checks import direction):
import `kanbanmate.daemon`, then assert `"fastapi" not in sys.modules` (DESIGN §7, §8). Guard the
`http/app.py` import of FastAPI behind a clear error if the extra is missing. (The static
layering guard separately confirms `http/` is an entrypoint — it may import `app`, and nothing
imports `http`.)

**Acceptance:** `python -c "import kanbanmate.daemon"` works without the extra installed and
leaves `fastapi` un-imported (the runtime test passes); importing `kanbanmate.http.app` without
FastAPI raises a clear `RuntimeError("install kanbanmate[ui]")`.

### 5.2 — FastAPI app

Implement the §7 endpoints in `http/app.py` over `app.config_service`: `GET /api/config`,
`POST /api/config/validate`, `POST /api/config` (validate-then-atomic-write),
`GET /api/config/render`, `POST /api/config/resolve`, `GET /api/schema`, `GET /api/health`.
The entrypoint resolves the clone config paths (it may import `cli.init`'s `CLONE_*_RELPATH`)
and injects them into the service calls (per phase-04's layering note). Bind `127.0.0.1` only.
**Server re-runs validation before any write** (the client cannot bypass §5). Launched via the
CLI: `kanban config serve [--port N]`.

**Acceptance:** FastAPI `TestClient` tests — `GET /api/config` returns the default; a bad
draft to `/validate` returns `valid=false` with non-empty `errors`; `POST /api/config` with a
bad draft returns 4xx and writes nothing; `/resolve` returns the right transition for a known
pair. A test asserts the app refuses to bind non-loopback.

### 5.3 — `kanban config` CLI (a Typer sub-app)

`cli/config.py` defines a Typer **sub-app** registered on the root app via `add_typer(config_app,
name="config")` (the root `cli/app.py` currently uses flat `@app.command()`s — this is the first
sub-app). Subcommands over `config_service`: `kanban config get` (print current as JSON/YAML),
`kanban config validate <file|->` (exit 0/non-0 + findings), `kanban config render <draft.json>`
(emit YAML), `kanban config serve [--port N]` (launch the `http/` entrypoint). The CLI resolves
the clone config paths (importing `cli.init`'s `CLONE_*_RELPATH`) and injects them into the
service. No new I/O paths beyond the service.

**Acceptance:** `kanban config validate` exits 0 on the default, non-0 on a malformed draft
and names the offending field; `kanban config render` output re-`load`s cleanly; `kanban config`
is registered as a sub-app (a test asserts the `config` group is present). CLI tests.

### 5.4 — JSON Schema

Author `assets/pipeline.schema.json` (Draft 2020-12) describing `transitions.yml` +
`columns.yml`: enums for `profile`/`permission_mode`, the `from`/`to` `string|array|"*"`
shapes, behavior patterns (`auto:<col>`, `move:<col>`, `rollback`). Served at `GET /api/schema`.
Document the `# yaml-language-server: $schema=` editor hook in the README. **Packaging:** add
`assets/*.json` to `[tool.setuptools.package-data] kanbanmate` (currently only `*.tmpl`/`*.yml`)
so the schema ships in the wheel.

**Acceptance:** the shipped default + the **purpose-built** fixture (phase-02 2.2, NOT the live
`personal-scraper` config — it equals the default) both validate against the schema
(`jsonschema` test); a malformed doc fails; the schema is reachable as packaged data. Test.

### 5.5 — ACCEPTANCE.md + docs

Write `ACCEPTANCE.md` with each criterion as an **executable shell command + expected output**
(DESIGN §12): CLI validate exit codes, render→load, the `curl` validate example, the
round-trip test invocation (against the purpose-built fixture), and the daemon-no-FastAPI
**runtime** check (`python -c "import kanbanmate.daemon, sys; assert 'fastapi' not in
sys.modules"`). Add a README/docs note for `pip install -e ".[ui]"` and `kanban config serve`.

**Acceptance:** every `ACC-NN` is a runnable command; running them all passes on the finished
PR. Docs build/lint clean.

### Phase gate (PR-1 final)

`rm -rf .mypy_cache && make check` green; HTTP + CLI + schema + static-layering + the
daemon-no-FastAPI **runtime** test pass; `python -c "import kanbanmate"` smoke test; every
`ACC-NN` re-exercised; no residual imports. This is the last phase of PR 1 →
`/implement:feature-pr` would follow at implementation time.
