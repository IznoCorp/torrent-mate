# Phase 3 — Redeploy from main (prod + staging)

## Gate

Phases 1–2 complete (detached jobs primitive + CSRF + audit green). `make check` green on phase-2
HEAD. The detached-job primitive (phase 1.2, `start_new_session=True`) is the **hard prerequisite**:
redeploy bounces the very config server handling the request, so only a detached job survives the
restart (DESIGN §3.2, §8).

## Overview

Add `POST /api/admin/redeploy` — a **detached job** that shells the existing audited deploy scripts
(`scripts/deploy.sh` for prod, `scripts/deploy-staging.sh` for staging, D4) and streams their stdout
into the job record/log. bosun **does not** re-implement the deploy steps/guards. Verify the scripts'
`set -euo pipefail` so a `pip` failure aborts **before** any restart. UI reconnects post-bounce by
polling `/api/health` until the version flips. Satisfies **ACC-05, ACC-06**. Three sub-phases.

---

## Sub-phase 3.1 — Verify deploy-script guard ordering (no code, a grounded assertion + safety test)

**Commit:** `test(bosun): assert deploy scripts fail-fast before restart (set -euo pipefail)`

**Files touched:**

- Create: `tests/test_deploy_scripts.py` (a repo-level guard test, alongside
  `tests/test_check_scripts.py`).
- (Conditional) Modify: `scripts/deploy.sh` / `scripts/deploy-staging.sh` — **only if** the guards
  are missing (they are not — see grounding).

**Grounding (verified at HEAD `d394522`):**

- `scripts/deploy.sh:20` is `set -euo pipefail` ✓.
- `scripts/deploy.sh:53` runs `pip install -e . >/dev/null` ✓ **before** the restart loop.
- `scripts/deploy.sh:54-56` is `for app in kanban kanban-km kanban-km-serve kanban-km-config; do pm2
  restart "$app" …; done` ✓ — pip precedes restart, so under `set -e` a failed `pip` aborts the
  script **before** any `pm2 restart` (no half-deployed serve) — **ACC-06** holds at the script level.
- `scripts/deploy-staging.sh:18` is `set -euo pipefail` ✓; `:38` restarts `kanban-staging-config`.

> Because the guards already exist, the DESIGN §8 "one-line script edit if missing" path is **NOT
> taken** — record that in the phase report. The deliverable here is a **regression test** that the
> ordering/guards stay intact (so a future edit can't silently move `pip` after the restart).

**Test** (`tests/test_deploy_scripts.py`) — a pure text assertion on the script files (no execution):

```python
"""Guard: deploy scripts must fail-fast (set -euo pipefail) with pip BEFORE restart (bosun §8/ACC-06)."""
from __future__ import annotations
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_deploy_sh_has_strict_mode_and_pip_before_restart() -> None:
    text = (_ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    pip_idx = text.index("pip install -e .")
    restart_idx = text.index("pm2 restart")
    assert pip_idx < restart_idx, "pip install must precede pm2 restart (no half-deployed serve)"


def test_deploy_staging_sh_has_strict_mode() -> None:
    text = (_ROOT / "scripts" / "deploy-staging.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "kanban-staging-config" in text
```

> Both sides are non-trivial real strings drawn from the actual scripts (`deploy.sh:20`,`:53`,`:54`).
> Run: `pytest tests/test_deploy_scripts.py -v` → 2 PASS.

---

## Sub-phase 3.2 — Redeploy route `POST /api/admin/redeploy` (detached job)

**Commit:** `feat(bosun): redeploy-from-main route (prod + staging) as detached job`

**Files touched:**

- Modify: `src/kanbanmate/http/admin_routes.py` — add `POST /api/admin/redeploy`.
- Create: `src/kanbanmate/core/redeploy_target.py` — a tiny pure validator mapping `target` →
  `(script, cwd)` so the HTTP layer never trusts a client path.
- Create: `tests/core/test_redeploy_target.py`
- Create: `tests/http/test_admin_redeploy.py`

**What to implement** — the pure target validator (no I/O; the app layer resolves the actual paths):

```python
"""Pure redeploy-target validator (bosun §8, decision D4).

Maps the operator-chosen target to the audited deploy script + the clone it runs in. The HTTP layer
NEVER takes a client-supplied script path — only the fixed ``prod``/``staging`` enum (DESIGN §8).
"""
from __future__ import annotations

# (script_relpath, clone_dir) per target. clone_dir is expanded by the app layer (it is ``~``-based,
# i.e. environment I/O, so it is NOT a core constant — passed in by the caller).
REDEPLOY_TARGETS: frozenset[str] = frozenset({"prod", "staging"})


def script_for_target(target: str) -> str | None:
    """Return the deploy script relpath for ``target``, or ``None`` if the target is unknown."""
    return {"prod": "scripts/deploy.sh", "staging": "scripts/deploy-staging.sh"}.get(target)
```

The route (the clone dirs `~/deploy/kanban-mate` / `~/staging/kanban-mate` are expanded in the app
layer per DESIGN §8):

```python
from kanbanmate.core.redeploy_target import script_for_target

_CLONE_FOR_TARGET = {"prod": "~/deploy/kanban-mate", "staging": "~/staging/kanban-mate"}


@app.post("/api/admin/redeploy")
async def admin_redeploy(request: fastapi.Request) -> JSONResponse:
    """Spawn a detached job shelling the audited deploy script for ``target`` (DESIGN §8)."""
    body = await _read_json_object(request)
    target = str(body.get("target", ""))
    script = script_for_target(target)
    if script is None:
        raise HTTPException(status_code=422, detail=f"unknown redeploy target '{target}'")
    clone = str(Path(_CLONE_FOR_TARGET[target]).expanduser())
    login = _actor_login(request)
    job_id = ops.create_job(
        _kanban_root(), type="redeploy", actor=login,
        argv=["bash", script], args_summary=f"target={target}", cwd=clone,
    )
    append_audit(_kanban_root(), login, "redeploy", f"target={target}")
    return JSONResponse(content={"job_id": job_id})
```

> The job's `argv` is `["bash", "scripts/deploy.sh"]` with `cwd` the prod/staging clone — server
> constructed from the validated enum, never a client path (DESIGN §11.4). The detached runner
> (phase 1.2) survives the `pm2 restart kanban-km-config` the script triggers (DESIGN §3.2).

**Tests:**

`tests/core/test_redeploy_target.py`:

```python
from kanbanmate.core.redeploy_target import script_for_target, REDEPLOY_TARGETS


def test_prod_maps_to_deploy_sh() -> None:
    assert script_for_target("prod") == "scripts/deploy.sh"


def test_staging_maps_to_deploy_staging_sh() -> None:
    assert script_for_target("staging") == "scripts/deploy-staging.sh"


def test_unknown_target_none() -> None:
    assert script_for_target("nope") is None
    assert "prod" in REDEPLOY_TARGETS and "staging" in REDEPLOY_TARGETS
```

`tests/http/test_admin_redeploy.py` — monkeypatch `ops.create_job` (no real deploy runs):

```python
def test_redeploy_unknown_target_422(tmp_path) -> None:
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health"); token = client.cookies.get("km_csrf")
        r = client.post("/api/admin/redeploy", json={"target": "moon"},
                        headers={"X-KM-CSRF": token})
        assert r.status_code == 422


def test_redeploy_prod_creates_job(tmp_path, monkeypatch) -> None:
    api_mod = _setup(tmp_path)
    from kanbanmate.app import ops
    seen = {}
    def _fake(root, **k):
        seen.update(k); return "job-redeploy-1"
    monkeypatch.setattr(ops, "create_job", _fake)
    with TestClient(api_mod.app) as client:
        client.get("/api/health"); token = client.cookies.get("km_csrf")
        r = client.post("/api/admin/redeploy", json={"target": "prod"},
                        headers={"X-KM-CSRF": token})
        assert r.status_code == 200 and r.json()["job_id"] == "job-redeploy-1"
        assert seen["type"] == "redeploy" and seen["args_summary"] == "target=prod"
        assert seen["argv"] == ["bash", "scripts/deploy.sh"]
```

Run: `pytest tests/core/test_redeploy_target.py tests/http/test_admin_redeploy.py -v` → all PASS.
(**ACC-05**, **ACC-06** at the script level.)

---

## Sub-phase 3.3 — UI: redeploy button + reconnect-on-bounce

**Commit:** `feat(bosun): UI redeploy (prod/staging) with post-bounce reconnect`

**Files touched:**

- Modify: `web/src/panels/AdminPanel.jsx` — Redeploy (prod) / Redeploy (staging) buttons behind a
  confirm modal; after POST, poll `GET /api/ops/{job_id}` for progress AND `GET /api/admin/version`
  until `local` matches `remote` (the bounce completed), then reconnect.
- Reuse: `web/src/components/SyncBoardDialog.jsx` for the confirm.

**What to implement** (DESIGN §8 reconnect): on redeploy, the SPA shows the streaming job log
(`GET /api/ops/{id}` → `stdout_tail`), tolerates the config server's restart (fetch errors during the
bounce are expected — show "redeploying, reconnecting…"), and resumes when `/api/health` answers
again with the new version. Run `cd web && npm run build` → succeeds.

> Live verification of the actual bounce is post-merge on the deployed build (DESIGN §17, ACC-05) —
> it cannot be exercised in CI (no PM2 there). The CI gate is the route + job wiring tests above.

---

## Definition of Done

- [ ] `pytest tests/test_deploy_scripts.py tests/core/test_redeploy_target.py tests/http/test_admin_redeploy.py -v` — all PASS.
- [ ] `make check` → green.
- [ ] Recorded in the phase report: deploy scripts **already** carry `set -euo pipefail` with `pip`
  before restart (`deploy.sh:20`,`:53`,`:54`; `deploy-staging.sh:18`,`:38`) — no script edit needed,
  guarded by the new regression test.
- [ ] `cd web && npm run build` → succeeds.
- [ ] **ACC-05** (redeploy route → job, prod + staging), **ACC-06** (pip-failure-before-restart,
  guarded) hold; live-bounce reconnect deferred to post-merge verification (DESIGN §17).
