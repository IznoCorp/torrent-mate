# Phase 1 — Jobs primitive + read-only health dashboard + version badge

## Gate

First phase. Branch `feat/bosun` must exist (created by `/implement:create-branch`), `make check`
green on the base commit. No writes land in this phase → **no CSRF yet** (DESIGN §14.1).

## Overview

Build the async **jobs** primitive (`app/ops.py`) with a **detached** runner invoked through a
hidden `ops-exec` CLI command (`cli/app.py`), expose it read-only via `http/ops_routes.py`, and add
the authed read-only surface: per-project **health dashboard** (`app/health_dashboard.py` +
`GET /api/admin/health`) and the **version badge** (`GET /api/admin/version`). Six sub-phases, one
commit each. Satisfies **ACC-01** (existing `/api/health` unchanged) and **ACC-02** (new authed
dashboard).

New modules: `app/ops.py`, `app/health_dashboard.py`, `http/ops_routes.py`, `http/admin_routes.py`.
Modified: `cli/app.py` (hidden `ops-exec` command), `http/config_api.py` (one side-effect import to
load `admin_routes` + `ops_routes` — appended at the bottom, no endpoint added there).

---

## Sub-phase 1.1 — Jobs primitive `app/ops.py` (record + lifecycle, no detachment yet)

**Commit:** `feat(bosun): jobs record + lifecycle primitive (app/ops.py)`

**Files touched:**

- Create: `src/kanbanmate/app/ops.py`
- Create: `tests/app/test_ops.py`

**What to implement** (DESIGN §11.1–§11.2). The job record is the on-disk audit trail under
`<root>/ops/<id>.json`; `<root>/ops/<id>.log` holds the runner's stdout:

```python
"""Async jobs primitive for privileged/long ops (bosun §11).

A privileged or long-running op runs as a DETACHED process (own session/process group, §11.3) that
writes a JSON status file under ``<root>/ops/<id>.json``; the UI polls ``GET /api/ops/{id}``. The
record IS the per-op audit trail (who/when/what/exit), durable on disk. Quick reads never use a job.

Layering: ``app`` imperative shell — filesystem writes + ``subprocess`` spawn; imports ``core`` only.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

_OPS_DIRNAME = "ops"
_GC_KEEP = 50          # keep the newest N records (DESIGN §11.2 / open-question 1)
_GC_MAX_AGE_DAYS = 14  # prune anything older than this
_STDOUT_TAIL_BYTES = 4096  # last ~4 KiB of stdout copied into the record (DESIGN §11.1)

_JOB_TYPES = frozenset({"redeploy", "daemon", "project_add", "wizard_bootstrap"})


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 ``...Z`` string (timezone-aware)."""
    return datetime.datetime.now(datetime.UTC).isoformat()


def _ops_dir(root: Path) -> Path:
    """Return ``<root>/ops`` (created on demand by writers)."""
    return root / _OPS_DIRNAME


def _record_path(root: Path, job_id: str) -> Path:
    return _ops_dir(root) / f"{job_id}.json"


def _log_path(root: Path, job_id: str) -> Path:
    return _ops_dir(root) / f"{job_id}.log"
```

`create_job` writes the queued spec then (1.2) spawns the detached runner; `read_job`/`list_jobs`
parse records; `gc_jobs` enforces retention; `run_job` is the runner body. Exact signatures (match
these — DESIGN §11.2):

```python
def create_job(root: Path, *, type: str, actor: str, argv: list[str],
               args_summary: str, cwd: str | None = None) -> str:
    """Write the queued job spec, spawn the detached runner, return the job id.

    Args:
        root: The kanban runtime root (``<root>/ops/`` holds the records).
        type: One of ``_JOB_TYPES``.
        actor: The authenticated operator login (for the audit trail).
        argv: The server-constructed command to exec (never client-supplied — DESIGN §11.4).
        args_summary: A short, sanitised description of the args (e.g. ``"target=prod"``).
        cwd: Working directory for the spawned process, or ``None`` for the current one.

    Returns:
        The generated job id ``<UTCstamp>-<type>-<rand4>``.
    """


def read_job(root: Path, job_id: str) -> dict:
    """Return the parsed job record, or raise ``FileNotFoundError`` if unknown."""


def list_jobs(root: Path, *, type: str | None = None, limit: int = 50) -> list[dict]:
    """Return records newest-first, optionally filtered by ``type``, capped at ``limit``."""


def gc_jobs(root: Path) -> None:
    """Keep the newest 50 records + prune those older than 14 days; fail-soft (DESIGN §11.2)."""


def run_job(root: Path, job_id: str) -> int:
    """Runner body: mark running → exec argv → tail stdout → mark succeeded/failed; return exit code."""
```

Job id is generated **without** `Math.random`/`Date.now` constraints (this is Python — use
`os.urandom`-backed `secrets.token_hex(2)` for the `rand4` suffix and `_now_iso()` compacted for the
stamp). The record state machine: `queued → running → succeeded|failed`.

**Tests** (`tests/app/test_ops.py`) — exercise the lifecycle with a **fast injected command** so no
detachment is needed yet (call `run_job` directly on a pre-written queued spec):

```python
"""Tests for app/ops jobs primitive (bosun §11)."""
from __future__ import annotations
import json
from pathlib import Path
from kanbanmate.app import ops


def _seed_queued(root: Path, argv: list[str]) -> str:
    # Write a queued spec WITHOUT spawning (test run_job in isolation).
    job_id = "20260621T120000-daemon-ab12"
    rec = {"id": job_id, "type": "daemon", "actor": "op", "args_summary": "x",
           "state": "queued", "created_at": ops._now_iso(), "started_at": None,
           "ended_at": None, "exit_code": None, "stdout_tail": "", "error": None,
           "argv": argv, "cwd": None}
    p = ops._record_path(root, job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec), encoding="utf-8")
    return job_id


def test_run_job_success_marks_succeeded(tmp_path: Path) -> None:
    job_id = _seed_queued(tmp_path, ["python", "-c", "print('hello-from-job')"])
    code = ops.run_job(tmp_path, job_id)
    assert code == 0
    rec = ops.read_job(tmp_path, job_id)
    assert rec["state"] == "succeeded"
    assert rec["exit_code"] == 0
    assert "hello-from-job" in rec["stdout_tail"]
    assert rec["started_at"] and rec["ended_at"]


def test_run_job_failure_marks_failed(tmp_path: Path) -> None:
    job_id = _seed_queued(tmp_path, ["python", "-c", "import sys; sys.exit(3)"])
    code = ops.run_job(tmp_path, job_id)
    assert code == 3
    rec = ops.read_job(tmp_path, job_id)
    assert rec["state"] == "failed"
    assert rec["exit_code"] == 3


def test_list_jobs_newest_first_and_filtered(tmp_path: Path) -> None:
    a = _seed_queued(tmp_path, ["true"])
    # second record, different id/type
    rec = {"id": "20260621T130000-redeploy-cd34", "type": "redeploy", "actor": "op",
           "args_summary": "target=prod", "state": "queued", "created_at": ops._now_iso(),
           "started_at": None, "ended_at": None, "exit_code": None, "stdout_tail": "",
           "error": None, "argv": ["true"], "cwd": None}
    ops._record_path(tmp_path, rec["id"]).write_text(json.dumps(rec), encoding="utf-8")
    all_jobs = ops.list_jobs(tmp_path)
    assert [j["id"] for j in all_jobs][0] == "20260621T130000-redeploy-cd34"  # newest first
    only_daemon = ops.list_jobs(tmp_path, type="daemon")
    assert {j["type"] for j in only_daemon} == {"daemon"}


def test_read_job_unknown_raises(tmp_path: Path) -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        ops.read_job(tmp_path, "nope")
```

Run: `pytest tests/app/test_ops.py -v` → 4 PASS.

---

## Sub-phase 1.2 — Detached execution + hidden `ops-exec` CLI command

**Commit:** `feat(bosun): detached job runner + hidden ops-exec CLI command`

**Files touched:**

- Modify: `src/kanbanmate/app/ops.py` — `create_job` spawns the detached runner.
- Modify: `src/kanbanmate/cli/app.py` — register a **hidden** `ops-exec` Typer command.
- Modify: `tests/app/test_ops.py` — add a detachment test (record readable after spawner returns).

**What to implement** (DESIGN §11.3). `create_job` spawns:

```python
proc = subprocess.Popen(
    [sys.executable, "-m", "kanbanmate.cli.app", "ops-exec", job_id, "--root", str(root)],
    start_new_session=True,          # own session/process group → survives `pm2 restart` of the UI app
    stdout=open(_log_path(root, job_id), "wb"),
    stderr=subprocess.STDOUT,
    cwd=cwd,
)
```

`start_new_session=True` is the crux: a `pm2 restart kanban-km-config` (redeploy's tail, phase 3)
signals only the config app's process group — the detached runner is in its **own** group and
survives (DESIGN §3.2, §11.3).

The hidden CLI command in `cli/app.py` (the Typer app is `app = typer.Typer(...)` at `cli/app.py:43`;
commands use `@app.command()` as at `cli/app.py:84`). Add, mirroring the existing hidden-command
convention (`hidden=True` keyword):

```python
@app.command(hidden=True)
def ops_exec(job_id: str, root: str = typer.Option(..., "--root")) -> None:
    """Hidden runner for a detached job (bosun §11.3 — NOT operator-facing).

    Invoked only by ``app.ops.create_job`` via ``python -m kanbanmate.cli.app ops-exec``.
    """
    from kanbanmate.app.ops import run_job  # noqa: PLC0415
    raise SystemExit(run_job(Path(root), job_id))
```

> Note: Typer maps the function name `ops_exec` to the CLI command `ops-exec` (underscore→hyphen),
> matching the `python -m kanbanmate.cli.app ops-exec ...` argv in `create_job`. Confirm `Path` is
> imported in `cli/app.py` (it is used elsewhere there); add the import if absent.
>
> **Drift fix (2026-06-22):** `cli/app.py` had no ``if __name__ == "__main__": main()`` guard,
> so ``python -m kanbanmate.cli.app`` loaded the module and silently exited 0 without calling
> ``app()`` — the detached runner never executed. Added the guard at end of file.

**Tests** (add to `tests/app/test_ops.py`):

```python
def test_create_job_record_readable_after_spawn(tmp_path: Path) -> None:
    """create_job returns immediately; the record is readable (detached runner owns completion)."""
    job_id = ops.create_job(
        tmp_path, type="daemon", actor="op",
        argv=[sys.executable, "-c", "print('detached-ok')"], args_summary="probe",
    )
    rec = ops.read_job(tmp_path, job_id)               # readable straight away (queued or running)
    assert rec["id"] == job_id
    assert rec["state"] in {"queued", "running", "succeeded"}
    # Poll briefly for completion without a wall-clock sleep dependency in CI:
    import time
    for _ in range(50):
        rec = ops.read_job(tmp_path, job_id)
        if rec["state"] in {"succeeded", "failed"}:
            break
        time.sleep(0.1)
    assert rec["state"] == "succeeded"
    assert "detached-ok" in rec["stdout_tail"]
```

`import sys` at the top of the test module. Run: `pytest tests/app/test_ops.py -v` → 5 PASS.

---

## Sub-phase 1.3 — Jobs HTTP read surface `http/ops_routes.py`

**Commit:** `feat(bosun): read-only jobs HTTP surface (http/ops_routes.py)`

**Files touched:**

- Create: `src/kanbanmate/http/ops_routes.py`
- Create: `tests/http/test_ops_routes.py`

**What to implement** (DESIGN §11.4) — register on the shared `app` by side-effect import; reuse
`_kanban_root` for the root:

```python
"""Read-only jobs HTTP surface (bosun §11.4).

Registered on the shared config-API ``app`` via side-effect import. Auth-gated by the existing
``_auth_guard`` middleware (these paths are NOT in ``_AUTH_OPEN_PATHS``). There is NO generic job
creation here — jobs are created only by the privileged endpoints (phases 2-5), so every argv is
server-constructed (DESIGN §11.4).
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate.app import ops
from kanbanmate.http.config_api import _kanban_root, app


@app.get("/api/ops")
async def list_ops(type: str | None = None, limit: int = 50) -> JSONResponse:
    """Return job records newest-first (optionally filtered by ``type``)."""
    return JSONResponse(content={"jobs": ops.list_jobs(_kanban_root(), type=type, limit=limit)})


@app.get("/api/ops/{job_id}")
async def get_op(job_id: str) -> JSONResponse:
    """Return one job record; 404 when unknown."""
    try:
        return JSONResponse(content=ops.read_job(_kanban_root(), job_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_id}'") from exc
```

**Tests** (`tests/http/test_ops_routes.py`) — set the root on `app.state`, seed a record, assert on
parsed JSON (auth disabled so the middleware passes through):

```python
"""Tests for the read-only jobs HTTP surface (bosun §11.4)."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path):
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.ops_routes  # noqa: F401  (registers routes)
    from kanbanmate.app import ops
    root = tmp_path / "root"
    root.mkdir()
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None  # auth disabled → middleware passes through
    rec = {"id": "20260621T120000-daemon-ab12", "type": "daemon", "actor": "op",
           "args_summary": "x", "state": "succeeded", "created_at": ops._now_iso(),
           "started_at": ops._now_iso(), "ended_at": ops._now_iso(), "exit_code": 0,
           "stdout_tail": "ok", "error": None}
    ops._record_path(root, rec["id"]).parent.mkdir(parents=True, exist_ok=True)
    ops._record_path(root, rec["id"]).write_text(json.dumps(rec), encoding="utf-8")
    return rec["id"]


def test_list_ops_returns_seeded_record(tmp_path) -> None:
    job_id = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod
    with TestClient(api_mod.app) as client:
        r = client.get("/api/ops")
        assert r.status_code == 200
        ids = [j["id"] for j in r.json()["jobs"]]
        assert job_id in ids


def test_get_op_unknown_404(tmp_path) -> None:
    _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod
    with TestClient(api_mod.app) as client:
        assert client.get("/api/ops/nope").status_code == 404
```

> The test reads `_kanban_root()` via `app.state.kanban_root`; confirm `_kanban_root`
> (`config_api.py:108`) reads `app.state.kanban_root` and adjust the attribute name if the real
> resolver differs (it is the same seam `tests/http/test_agent_terminal.py:420` uses).

Run: `pytest tests/http/test_ops_routes.py -v` → 2 PASS.

---

## Sub-phase 1.4 — Health dashboard data `app/health_dashboard.py`

**Commit:** `feat(bosun): per-project health dashboard data (app/health_dashboard.py)`

**Files touched:**

- Create: `src/kanbanmate/app/health_dashboard.py`
- Create: `tests/app/test_health_dashboard.py`

**What to implement** (DESIGN §7.1 health row). A pure-ish reporter that, given the runtime root,
returns per-project rows + global flags. It reads heartbeat files and does a cheap probe; it imports
`cli.init._load_registry`/`_projects_path` for the registry (the same helpers `config_api` uses) and
checks the PAUSE sentinel and the session-secret-pinned flag:

```python
"""Per-project health dashboard data (bosun §7.1).

Computes the authed dashboard payload: one row per registered project plus global flags. Reads
heartbeat files + a cheap probe; never the public ``/api/health`` data. Imperative shell (fs reads).
"""
from __future__ import annotations

import os
from pathlib import Path

from kanbanmate.cli.init import _load_registry, _projects_path


def build_health(root: Path) -> dict:
    """Return ``{"projects": [row, ...], "pause_active": bool,
    "session_secret_pinned": bool, "agents_waiting": int}`` (DESIGN §7.1).

    Each row: ``{project_id, repo, daemon_alive, heartbeat_age_s, github_api_ok,
    board_ok, token_present}``. Probe failures degrade the per-row flag to ``False``
    rather than raising (the dashboard must always render).
    """
```

Per-row fields map to: `daemon_alive`/`heartbeat_age_s` from the per-project heartbeat file
mtime/freshness; `token_present` from the resolved token path existence; `github_api_ok`/`board_ok`
from a cheap reachability probe (fail-soft → `False`). `pause_active` = `(root / "PAUSE").exists()`
(matches `fs_store.kill_switch_active`, `adapters/store/fs_store.py:379`). `session_secret_pinned` =
`bool(os.environ.get("KANBAN_MATE_UI_SESSION_SECRET"))` (the env var name is `_ENV_SECRET`,
`cli/config.py:40`). `agents_waiting` counts tracked tickets whose status ∈ `LIVE_STATUSES` and is
WAITING (`ports/store.py:78`).

> Reuse existing data where available: `app/health_reporter.py` (`apply_health`,
> `health_reporter.py:109`) maintains the GitHub Health **field** — it is NOT a per-project liveness
> reporter, so this module computes liveness fresh. Cite it in the docstring so the two are not
> confused.

**Tests** (`tests/app/test_health_dashboard.py`) — seed a `projects.json` + a fresh heartbeat file
and assert the row is genuinely populated (both sides non-trivial):

```python
"""Tests for app/health_dashboard (bosun §7.1)."""
from __future__ import annotations
import json
from pathlib import Path
from kanbanmate.app.health_dashboard import build_health


def _seed_project(root: Path) -> None:
    (root).mkdir(parents=True, exist_ok=True)
    (_p := root / "projects.json").write_text(json.dumps({
        "PVT_x": {"repo": "O/r", "clone": str(root / "clone"), "project_id": "PVT_x",
                  "status_field_node_id": "FLD"}
    }), encoding="utf-8")


def test_build_health_reports_project_row(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _seed_project(root)
    out = build_health(root)
    assert "projects" in out
    rows = out["projects"]
    assert len(rows) == 1
    row = rows[0]
    assert row["project_id"] == "PVT_x"
    assert row["repo"] == "O/r"
    assert "daemon_alive" in row and "heartbeat_age_s" in row and "token_present" in row
    assert out["pause_active"] is False  # no PAUSE sentinel seeded


def test_pause_active_reflects_sentinel(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _seed_project(root)
    (root / "PAUSE").write_text("", encoding="utf-8")
    assert build_health(root)["pause_active"] is True
```

Run: `pytest tests/app/test_health_dashboard.py -v` → 2 PASS.

---

## Sub-phase 1.5 — Admin read routes: `GET /api/admin/health` + `GET /api/admin/version`

**Commit:** `feat(bosun): authed health dashboard + version badge routes`

**Files touched:**

- Create: `src/kanbanmate/http/admin_routes.py`
- Create: `tests/http/test_admin_health_version.py`

**What to implement** (DESIGN §7.1). New module registered on the shared `app`:

```python
"""Authed admin read surface: health dashboard + version badge (bosun §7.1).

Registered on the shared config-API ``app`` by side-effect import. Auth-gated by ``_auth_guard``
(these paths are NOT in ``_AUTH_OPEN_PATHS``). Privileged data NEVER rides the public ``/api/health``.
"""
from __future__ import annotations

import subprocess

from fastapi.responses import JSONResponse

from kanbanmate import __version__
from kanbanmate.app.health_dashboard import build_health
from kanbanmate.http.config_api import _kanban_root, app


@app.get("/api/admin/health")
async def admin_health() -> JSONResponse:
    """Per-project health rows + global flags (DESIGN §7.1)."""
    return JSONResponse(content=build_health(_kanban_root()))


@app.get("/api/admin/version")
async def admin_version() -> JSONResponse:
    """Local ``__version__`` vs ``origin/main``; degraded ``remote:"unknown"`` on fetch failure."""
    local = __version__
    try:
        out = subprocess.run(
            ["git", "ls-remote", "origin", "refs/heads/main"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        remote = out.split()[0][:12] if out else "unknown"
        update_available = bool(remote) and remote != "unknown"  # refined below
    except Exception:
        remote, update_available = "unknown", False
    return JSONResponse(content={"local": local, "remote": remote,
                                 "update_available": update_available})
```

> The version badge's `update_available` is a best-effort signal: `local` is the package
> `__version__` (`__init__.py:11`), `remote` is the `origin/main` head sha (or `webui/BUILD_COMMIT`
> when comparing builds — DESIGN §7.1). The exact comparison is refined to "remote head ≠ the
> committed `webui/BUILD_COMMIT`" if a build stamp is present; on any `git` failure the route
> degrades to `remote:"unknown", update_available:false` and **never errors** (DESIGN open-question 3).

Append the side-effect imports at the **bottom** of `http/config_api.py` (NOT new endpoints there —
just `import` lines, mirroring `monitor_routes.py:353`):

```python
# Side-effect imports: register bosun's read-only admin/ops routes on `app` (bosun §1).
import kanbanmate.http.ops_routes as _bosun_ops_routes  # noqa: F401, E402
import kanbanmate.http.admin_routes as _bosun_admin_routes  # noqa: F401, E402
```

**Tests** (`tests/http/test_admin_health_version.py`):

```python
"""Tests for /api/admin/health + /api/admin/version (bosun §7.1)."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path, *, auth_enabled: bool = False):
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.admin_routes  # noqa: F401
    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text(json.dumps({
        "PVT_x": {"repo": "O/r", "clone": str(tmp_path / "clone"), "project_id": "PVT_x",
                  "status_field_node_id": "FLD"}}), encoding="utf-8")
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None
    return api_mod


def test_admin_health_authed_returns_rows(tmp_path) -> None:
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/health")
        assert r.status_code == 200
        body = r.json()
        assert body["projects"][0]["project_id"] == "PVT_x"
        assert "pause_active" in body and "session_secret_pinned" in body


def test_admin_version_has_local(tmp_path) -> None:
    from kanbanmate import __version__
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        body = client.get("/api/admin/version").json()
        assert body["local"] == __version__
        assert "remote" in body and "update_available" in body


def test_admin_health_requires_auth_when_enabled(tmp_path) -> None:
    """With auth enabled and no cookie, the dashboard is rejected (401) — NOT public."""
    from kanbanmate.http.auth import AuthConfig
    api_mod = _setup(tmp_path)
    api_mod.app.state.auth = AuthConfig(login="op", password="secret", secret="s3cr3t")
    with TestClient(api_mod.app) as client:
        assert client.get("/api/admin/health").status_code == 401
```

> Confirm the auth-failure status the `_auth_guard` middleware returns (`config_api.py:84-102`) —
> the design says **401** for unauthenticated (DESIGN ACC-10). If the middleware returns 403/redirect
> instead, assert the real code (read `config_api.py:84-102` before writing this assertion).

Run: `pytest tests/http/test_admin_health_version.py -v` → 3 PASS.

---

## Sub-phase 1.6 — UI: read-only Admin/Ops panel

**Commit:** `feat(bosun): KanbanMateUI admin panel — health + version (read-only)`

**Files touched:**

- Create: `web/src/panels/AdminPanel.jsx` (health dashboard + version badge; polls
  `GET /api/admin/health` + `GET /api/admin/version` + `GET /api/ops`).
- Modify: `web/src/` nav/registry to surface the new panel (mirror how `DaemonPanel.jsx` /
  `MonitoringPanel` are registered — read the existing panel-registration file first and match it).
- Reuse: `web/src/lib/api.js` GET helper (no CSRF needed for reads).

**What to implement:** a read-only panel rendering one card per project from `/api/admin/health`
(daemon/heartbeat/github/board/token chips), a version badge from `/api/admin/version`
(`update_available` → "Update available" pill; `remote:"unknown"` → muted "offline" state), and a
recent-jobs list from `/api/ops`. No mutating calls in this phase. Match the existing
`kanbanmate-design` tokens/components (shadcn/ui).

> UI verification is visual + via the live build (DESIGN §17); the gate here is that the panel
> builds (`npm run build` under `web/`) and renders against the three read endpoints. No new JS test
> framework is introduced (the repo has none for `web/`).

Run: `cd web && npm run build` → succeeds (SPA built into `src/kanbanmate/webui/`).

---

## Definition of Done

- [ ] `pytest tests/app/test_ops.py tests/http/test_ops_routes.py tests/app/test_health_dashboard.py tests/http/test_admin_health_version.py -v` — all PASS.
- [ ] `make check` → zero ruff/mypy errors, all tests green, module-size guards pass (no file over
  1000 LOC; `http/config_api.py` only gained two import lines).
- [ ] `python -c "import kanbanmate.http.ops_routes, kanbanmate.http.admin_routes, kanbanmate.app.ops, kanbanmate.app.health_dashboard"` → no import error.
- [ ] `python -m kanbanmate.cli.ops_exec --help` runs. **Drift fix (phase-1 gate, 2026-06-22):** the
  detached runner moved out of `cli/app.py` into its own standalone module `cli/ops_exec.py` (spawned
  via `python -m kanbanmate.cli.ops_exec`) — inline it pushed `cli/app.py` to 1005 LOC (over the 1000
  hard ceiling) and a `@app.command` re-run under `python -m kanbanmate.cli.app` hits the double-import
  trap. `create_job` spawns the new module; `cli/app.py` reverted to 990 LOC.
- [ ] `cd web && npm run build` → succeeds.
- [ ] **ACC-01** holds (`GET /api/health` unchanged, unauthenticated — `config_api.py:241`).
- [ ] **ACC-02** holds (`GET /api/admin/health` authed, returns per-project rows + flags).
