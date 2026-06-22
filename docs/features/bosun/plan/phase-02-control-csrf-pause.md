# Phase 2 — Daemon control + PM2 logs + PAUSE + CSRF middleware + persistent secret

## Gate

Phase 1 complete (jobs primitive + read surface green). `make check` green on phase-1 HEAD. This
phase introduces the **first writes**, so the **app-wide CSRF middleware** lands here and must be in
place before any mutating route ships (DESIGN §6, §14.2).

## Overview

Add the pure `core/pm2_allowlist.py` validator, the generalised `app/audit.py` sink, the app-wide
`http/csrf_mw.py` double-submit middleware, the daemon-control + PM2-logs + PAUSE routes in
`http/admin_routes.py`, and the **persistent-session-secret** detection/enforcement (DESIGN §12).
Satisfies **ACC-03, ACC-04, ACC-09, ACC-11**, and the CSRF/allowlist parts of **ACC-10**. Seven
sub-phases.

---

## Sub-phase 2.1 — Pure `core/pm2_allowlist.py`

**Commit:** `feat(bosun): pure PM2 allowlist validator (core/pm2_allowlist.py)`

**Files touched:**

- Create: `src/kanbanmate/core/pm2_allowlist.py`
- Create: `tests/core/test_pm2_allowlist.py`

**What to implement** (DESIGN §5.1, D1) — pure, no I/O, stdlib only (matches `core/webhook_sig.py`):

```python
"""Pure PM2 daemon-control allowlist (bosun §5.1, decision D1).

Enforces lockout safety: daemon-control may act on an allowlisted PM2 app, but a STANDALONE
start/stop/restart of a UI app (the config server) is refused — a UI app is only ever bounced as the
tail of a redeploy job (§8). ``status`` is permitted on any allowlisted app including UI apps.
No I/O — the app layer runs ``pm2`` and calls this for the decision.
"""
from __future__ import annotations

PM2_ALLOWLIST: frozenset[str] = frozenset(
    {"kanban-km", "kanban-km-serve", "kanban-km-config", "kanban-staging-config"}
)
UI_APP_NAMES: frozenset[str] = frozenset({"kanban-km-config", "kanban-staging-config"})
_DAEMON_ACTIONS: frozenset[str] = frozenset({"start", "stop", "restart", "status"})


def validate_daemon_action(app: str, action: str) -> str | None:
    """Return ``None`` if ``(app, action)`` is permitted, else a refusal reason (DESIGN §5.1).

    Args:
        app: The PM2 app name.
        action: One of ``start``/``stop``/``restart``/``status``.

    Returns:
        ``None`` when permitted; otherwise a human-readable refusal string (the HTTP layer maps a
        non-``None`` return to a 422).
    """
    if action not in _DAEMON_ACTIONS:
        return f"unknown action '{action}'"
    if app not in PM2_ALLOWLIST:
        return f"app '{app}' is not in the PM2 allowlist"
    if app in UI_APP_NAMES and action in {"start", "stop", "restart"}:
        return f"standalone '{action}' of UI app '{app}' is refused (bounce only via redeploy)"
    return None
```

**Tests** (`tests/core/test_pm2_allowlist.py`) — exhaustive over every app × every action (DESIGN
§15):

```python
"""Tests for core/pm2_allowlist (bosun §5.1)."""
from __future__ import annotations
import pytest
from kanbanmate.core.pm2_allowlist import (
    PM2_ALLOWLIST, UI_APP_NAMES, validate_daemon_action,
)

NON_UI = sorted(PM2_ALLOWLIST - UI_APP_NAMES)   # ["kanban-km", "kanban-km-serve"]
UI = sorted(UI_APP_NAMES)                        # ["kanban-km-config", "kanban-staging-config"]


@pytest.mark.parametrize("app", NON_UI)
@pytest.mark.parametrize("action", ["start", "stop", "restart", "status"])
def test_non_ui_app_all_actions_permitted(app, action) -> None:
    assert validate_daemon_action(app, action) is None


@pytest.mark.parametrize("app", UI)
def test_ui_app_status_permitted(app) -> None:
    assert validate_daemon_action(app, "status") is None


@pytest.mark.parametrize("app", UI)
@pytest.mark.parametrize("action", ["start", "stop", "restart"])
def test_ui_app_standalone_mutation_refused(app, action) -> None:
    reason = validate_daemon_action(app, action)
    assert reason is not None and "refused" in reason


def test_out_of_allowlist_refused() -> None:
    assert validate_daemon_action("kanban-autodeploy", "restart") is not None
    assert validate_daemon_action("rm-rf", "start") is not None


def test_unknown_action_refused() -> None:
    assert validate_daemon_action("kanban-km", "destroy") is not None
```

> `kanban-autodeploy` is a real PM2 app (`scripts/autodeploy-poll.sh`) deliberately **out** of the
> allowlist — a real, non-trivial negative case (DESIGN §4 PM2-app row).

Run: `pytest tests/core/test_pm2_allowlist.py -v` → all PASS.

---

## Sub-phase 2.2 — Generalised audit sink `app/audit.py`

**Commit:** `feat(bosun): shared audit sink (app/audit.py)`

**Files touched:**

- Create: `src/kanbanmate/app/audit.py`
- Create: `tests/app/test_audit.py`

**What to implement** (DESIGN §4 audit row, §13) — extract the exact file/format
`agent_terminal._audit` writes (`http/agent_terminal.py:158-185`): `<root>/control/audit.log`,
one ISO-8601-UTC line per event, fail-soft:

```python
"""Shared audit sink (bosun §13) — one audit story across #47 and bosun.

Generalises the line shape ``agent_terminal._audit`` writes (``http/agent_terminal.py:158``):
``<ISO-8601Z> audit: operator <login> <action>: <summary>`` appended to ``<root>/control/audit.log``.
Fail-soft — a file error must never interrupt the privileged op.
"""
from __future__ import annotations

import datetime
from pathlib import Path


def append_audit(root: Path, login: str, action: str, summary: str) -> None:
    """Append one audit line to ``<root>/control/audit.log`` (fail-soft, DESIGN §13).

    Args:
        root: The kanban runtime root.
        login: The authenticated operator login.
        action: The action verb (e.g. ``pause_on``, ``daemon_restart``).
        summary: A short, sanitised description of the args.
    """
    try:
        log_path = root / "control" / "audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} audit: operator {login} {action}: {summary}\n")
    except Exception:
        pass  # fail-soft: audit file errors must never interrupt a privileged op
```

> Match the existing format at `agent_terminal.py:174-181` (ISO timestamp + `audit: operator …`).
> `agent_terminal._audit` may later be refactored to call this; that refactor is **out of scope** for
> bosun (no behaviour change to #47) — bosun only adds the shared sink and uses it for its sync ops.

**Tests** (`tests/app/test_audit.py`):

```python
"""Tests for app/audit (bosun §13)."""
from __future__ import annotations
from pathlib import Path
from kanbanmate.app.audit import append_audit


def test_append_writes_expected_line(tmp_path: Path) -> None:
    append_audit(tmp_path, "operator", "pause_on", "active=true")
    log = (tmp_path / "control" / "audit.log").read_text(encoding="utf-8")
    assert "audit: operator operator pause_on: active=true" in log
    assert log.endswith("\n")


def test_append_is_additive(tmp_path: Path) -> None:
    append_audit(tmp_path, "op", "a", "1")
    append_audit(tmp_path, "op", "b", "2")
    lines = (tmp_path / "control" / "audit.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
```

Run: `pytest tests/app/test_audit.py -v` → 2 PASS.

---

## Sub-phase 2.3 — App-wide CSRF middleware `http/csrf_mw.py`

**Commit:** `feat(bosun): app-wide double-submit CSRF middleware`

**Files touched:**

- Create: `src/kanbanmate/http/csrf_mw.py`
- Modify: `src/kanbanmate/http/config_api.py` — append a side-effect import (bottom) to register it.
- Create: `tests/http/test_csrf.py`

> **Design refinement (2.3 gate):** the literal middleware below enforces CSRF on every mutating
> `/api/` request regardless of auth state — but that would retroactively 403 the ~34 existing
> mutating-endpoint tests (which run with auth disabled) and is semantically wrong (CSRF only
> protects an AUTHENTICATED session). **Implemented version:** enforcement is **gated on auth being
> enabled** (`_auth_config()` is not None AND `.enabled`), mirroring `_auth_guard`. When auth is
> disabled the server is open loopback dev — no session to forge against — so enforcement is skipped.
> **Both** `/api/login` AND `/api/logout` are exempt (logout must not wedge on a missing token). The
> `km_csrf` cookie is **always** minted (regardless of auth state) so the SPA can read + echo it.
> Import `_auth_config` alongside `_request_is_secure, app`; register the side-effect import WITH the
> other bosun route-module imports (before `install_spa_mount`), not at the very bottom. The test
> drives the REAL enforcement context (auth ENABLED + a logged-in session) and a control with auth
> disabled.

**What to implement** (DESIGN §6) — a non-HttpOnly `km_csrf` cookie minted on any response lacking
it; every mutating `/api/` request must echo it in `X-KM-CSRF` (constant-time compare) else 403.
GET/HEAD/OPTIONS exempt; login exempt:

```python
"""App-wide double-submit CSRF middleware (bosun §6).

Closes the pre-existing gap (no CSRF anywhere today — DESIGN §4 CSRF row) and protects every mutating
request, including the pre-existing unprotected writes (POST /api/config, POST /api/board/provision,
PATCH /api/projects/{id}). Double-submit needs no server-side state: the non-HttpOnly ``km_csrf``
cookie value need only match the ``X-KM-CSRF`` header (an attacker cannot read the cookie cross-site
under SOP, so cannot forge the header).
"""
from __future__ import annotations

import hmac
import secrets

import fastapi

from kanbanmate.http.config_api import _request_is_secure, app

_CSRF_COOKIE = "km_csrf"
_CSRF_HEADER = "x-km-csrf"
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_EXEMPT_PATHS = frozenset({"/api/login"})  # login has no prior cookie; it only SETS the session


@app.middleware("http")
async def _csrf_guard(request: fastapi.Request, call_next):  # type: ignore[no-untyped-def]
    """Reject mutating /api/ requests whose X-KM-CSRF header != km_csrf cookie (DESIGN §6)."""
    method = request.method.upper()
    path = request.url.path
    enforce = (
        method in _MUTATING
        and path.startswith("/api/")
        and path not in _EXEMPT_PATHS
    )
    if enforce:
        cookie = request.cookies.get(_CSRF_COOKIE, "")
        header = request.headers.get(_CSRF_HEADER, "")
        if not cookie or not header or not hmac.compare_digest(cookie, header):
            return fastapi.responses.JSONResponse(
                status_code=403, content={"detail": "CSRF token missing or mismatched"}
            )
    response = await call_next(request)
    # Mint the cookie when absent so the SPA can read + echo it (double-submit).
    if _CSRF_COOKIE not in request.cookies:
        response.set_cookie(
            _CSRF_COOKIE, secrets.token_urlsafe(32),
            samesite="lax", secure=_request_is_secure(request), path="/", httponly=False,
        )
    return response
```

> **Middleware ordering (read before finalising):** Starlette runs `@app.middleware("http")` in
> reverse registration order. `_auth_guard` is registered at `config_api.py:84`; the CSRF guard
> registers later (side-effect import at the bottom of `config_api.py`). Confirm both run for a
> mutating request and that a request needs **both** a valid session cookie (auth) **and** a matching
> CSRF header to mutate. The two guards are independent (DESIGN §6). Verify the actual run order with
> the test below rather than assuming.

Append at the **bottom** of `http/config_api.py` (after the phase-1 imports):

```python
import kanbanmate.http.csrf_mw as _bosun_csrf_mw  # noqa: F401, E402
```

**Tests** (`tests/http/test_csrf.py`) — drive a real mutating route (reuse the existing
`PATCH /api/projects/{id}`, `config_api.py:664`, which now falls under CSRF) with auth disabled so
only CSRF is under test:

```python
"""Tests for the app-wide CSRF middleware (bosun §6)."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path):
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.csrf_mw  # noqa: F401
    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text(json.dumps({
        "PVT_x": {"repo": "O/r", "clone": str(tmp_path / "clone"), "project_id": "PVT_x",
                  "status_field_node_id": "FLD"}}), encoding="utf-8")
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None  # auth disabled → isolate CSRF
    return api_mod


def test_get_is_exempt_and_mints_cookie(tmp_path) -> None:
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        r = client.get("/api/projects")
        assert r.status_code == 200
        assert "km_csrf" in r.cookies  # cookie minted on a GET that lacked it


def test_mutating_without_csrf_header_rejected_403(tmp_path) -> None:
    """A mutating call with the cookie but no matching X-KM-CSRF header is rejected (403)."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")                       # mint the km_csrf cookie
        token = client.cookies.get("km_csrf")
        assert token
        # No header → 403
        r = client.patch("/api/projects/PVT_x", json={"enabled": True})
        assert r.status_code == 403
        # Matching header == cookie → passes CSRF (200 or a non-403 domain code)
        r2 = client.patch("/api/projects/PVT_x", json={"enabled": True},
                          headers={"X-KM-CSRF": token})
        assert r2.status_code != 403
```

Run: `pytest tests/http/test_csrf.py -v` → PASS.

---

## Sub-phase 2.4 — Daemon read + control routes

**Commit:** `feat(bosun): daemon status read + control routes (allowlist-guarded)`

**Files touched:**

- Modify: `src/kanbanmate/http/admin_routes.py` — add `GET /api/admin/daemon`,
  `POST /api/admin/daemon/{app}/{action}`.
- Create: `tests/http/test_admin_daemon.py`

**What to implement** (DESIGN §7.1 daemon row, §7.2). `GET` parses `pm2 jlist` filtered to
`PM2_ALLOWLIST`; `POST` validates via `core.pm2_allowlist.validate_daemon_action` (422 on refusal)
then spawns a **job** running `pm2 <action> <app>`:

```python
from kanbanmate.core.pm2_allowlist import PM2_ALLOWLIST, validate_daemon_action
from kanbanmate.app import ops
from kanbanmate.app.audit import append_audit


@app.get("/api/admin/daemon")
async def admin_daemon() -> JSONResponse:
    """Return ``[{app,status,pid,uptime_s,restarts}]`` for allowlisted apps (pm2 jlist filtered)."""


@app.post("/api/admin/daemon/{app_name}/{action}")
async def admin_daemon_action(app_name: str, action: str, request: fastapi.Request) -> JSONResponse:
    """Spawn a job running ``pm2 <action> <app>``; 422 on allowlist/UI-app refusal (D1)."""
    reason = validate_daemon_action(app_name, action)
    if reason is not None:
        raise HTTPException(status_code=422, detail=reason)
    login = _actor_login(request)  # resolve from the session cookie; "operator" in open mode
    job_id = ops.create_job(
        _kanban_root(), type="daemon", actor=login,
        argv=["pm2", action, app_name], args_summary=f"{action} {app_name}",
    )
    append_audit(_kanban_root(), login, f"daemon_{action}", app_name)
    return JSONResponse(content={"job_id": job_id})
```

> Add a small `_actor_login(request)` helper in `admin_routes.py` that reads `COOKIE_NAME`
> (`auth.py:31`) + `verify_token` (`auth.py:97`) against `_auth_config()` (`config_api.py:68`),
> returning the login or `"operator"` when auth is disabled — mirror the in-handler check
> `agent_terminal.py:243-252`.

**Tests** (`tests/http/test_admin_daemon.py`) — monkeypatch `ops.create_job` so no real `pm2` runs;
assert the 422 refusals use **real** app/action values:

```python
def test_daemon_restart_ui_app_refused_422(tmp_path) -> None:
    api_mod = _setup(tmp_path)  # auth off; csrf cookie minted via a GET first
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post("/api/admin/daemon/kanban-km-config/restart",
                        headers={"X-KM-CSRF": token})
        assert r.status_code == 422  # D1: standalone UI-app restart refused


def test_daemon_restart_allowed_app_creates_job(tmp_path, monkeypatch) -> None:
    api_mod = _setup(tmp_path)
    from kanbanmate.app import ops
    monkeypatch.setattr(ops, "create_job", lambda *a, **k: "job-xyz")
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post("/api/admin/daemon/kanban-km/restart", headers={"X-KM-CSRF": token})
        assert r.status_code == 200 and r.json()["job_id"] == "job-xyz"
```

Run: `pytest tests/http/test_admin_daemon.py -v` → PASS. (**ACC-03, ACC-04**.)

---

## Sub-phase 2.5 — PM2 logs tail route

**Commit:** `feat(bosun): bounded PM2 log tail route (poll-based)`

**Files touched:**

- Modify: `src/kanbanmate/http/admin_routes.py` — add `GET /api/admin/daemon/{app}/logs?lines=N`.
- Modify: `tests/http/test_admin_daemon.py` — add a logs test (monkeypatch the subprocess).

**What to implement** (DESIGN §7.1 logs row) — bounded tail, default 200, cap 1000; app must be
allowlisted (422 otherwise); poll-based (no WS) for v1:

```python
@app.get("/api/admin/daemon/{app_name}/logs")
async def admin_daemon_logs(app_name: str, lines: int = 200) -> JSONResponse:
    """Return ``{"lines": [...]}`` — bounded ``pm2 logs --nostream --lines N`` (cap 1000)."""
    if app_name not in PM2_ALLOWLIST:
        raise HTTPException(status_code=422, detail=f"app '{app_name}' is not allowlisted")
    n = max(1, min(int(lines), 1000))
    out = subprocess.run(["pm2", "logs", app_name, "--nostream", "--lines", str(n)],
                         capture_output=True, text=True, timeout=15).stdout
    return JSONResponse(content={"lines": out.splitlines()})
```

**Test:** monkeypatch `subprocess.run` to return a fake `CompletedProcess` with 3 lines; assert the
parsed `lines` list has 3 entries and an out-of-allowlist app → 422. Run targeted pytest → PASS.

---

## Sub-phase 2.6 — PAUSE toggle (sync + CSRF + audit)

**Commit:** `feat(bosun): PAUSE kill-switch toggle route (sync + audit)`

**Files touched:**

- Modify: `src/kanbanmate/http/admin_routes.py` — add `GET /api/admin/pause`,
  `POST /api/admin/pause`.
- Create: `tests/http/test_admin_pause.py`

**What to implement** (DESIGN §7.1, §7.3) — `GET` reports `(root/"PAUSE").exists()`; `POST` with
`{active:bool}` creates/unlinks `<root>/PAUSE` (idempotent) and appends to the audit log. The daemon
consumes it on its next tick (`fs_store.kill_switch_active`, `adapters/store/fs_store.py:379`;
read fresh each tick, `app/tick.py:541`):

```python
@app.get("/api/admin/pause")
async def admin_pause_get() -> JSONResponse:
    return JSONResponse(content={"active": (_kanban_root() / "PAUSE").exists()})


@app.post("/api/admin/pause")
async def admin_pause_set(request: fastapi.Request) -> JSONResponse:
    body = await _read_json_object(request)   # reuse config_api's helper, or json.loads(await body)
    active = bool(body.get("active"))
    pause = _kanban_root() / "PAUSE"
    if active:
        pause.parent.mkdir(parents=True, exist_ok=True)
        pause.touch()
    else:
        pause.unlink(missing_ok=True)
    append_audit(_kanban_root(), _actor_login(request), "pause", f"active={active}")
    return JSONResponse(content={"active": pause.exists()})
```

> `_read_json_object` exists in `config_api.py` (used by `patch_project`, `config_api.py:688`). Import
> it or inline a minimal `json` parse — confirm its name/signature before importing.

**Tests** (`tests/http/test_admin_pause.py`) — toggle on then off, assert the sentinel file appears
and disappears AND `kill_switch_active` agrees (real cross-check against the store reader):

```python
def test_pause_on_creates_sentinel_and_store_sees_it(tmp_path) -> None:
    api_mod = _setup(tmp_path)
    from kanbanmate.adapters.store.fs_store import FsStore  # confirm class name before using
    with TestClient(api_mod.app) as client:
        client.get("/api/health"); token = client.cookies.get("km_csrf")
        r = client.post("/api/admin/pause", json={"active": True}, headers={"X-KM-CSRF": token})
        assert r.status_code == 200 and r.json()["active"] is True
        assert (api_mod.app.state.kanban_root / "PAUSE").exists()
        # cross-check the daemon's own reader agrees
        store = FsStore(api_mod.app.state.kanban_root)
        assert store.kill_switch_active() is True
        r2 = client.post("/api/admin/pause", json={"active": False}, headers={"X-KM-CSRF": token})
        assert r2.json()["active"] is False
        assert not (api_mod.app.state.kanban_root / "PAUSE").exists()
```

> Confirm the store class name/constructor (`grep -n "^class .*Store" adapters/store/fs_store.py`)
> before importing — the design refers to it as `fs_store` with `kill_switch_active` at
> `fs_store.py:379`. (**ACC-09**.)

Run: `pytest tests/http/test_admin_pause.py -v` → PASS.

---

## Sub-phase 2.7 — Persistent session secret detection + enforcement

**Commit:** `feat(bosun): warn + surface unpinned session secret (bosun §12)`

**Files touched:**

- Modify: `src/kanbanmate/cli/config.py` — at serve build, if auth enabled but the secret fell back
  to random, log a **fail-loud WARNING** and record the pinned flag.
- Modify: `src/kanbanmate/app/health_dashboard.py` — `session_secret_pinned` already reads the env
  (phase 1.4); confirm it reflects the real pinned/unpinned state.
- Create: `tests/cli/test_config_secret.py`

**What to implement** (DESIGN §12). At `cli/config.py:133` the secret is
`ui_env.get(_ENV_SECRET, "") or secrets.token_hex(32)` — random per start when unset. Detect that
exact fallback **without** hard-failing (hard-fail would break dev):

```python
# bosun §12: a random per-start secret logs the operator out on every restart/redeploy, defeating
# in-UI redeploy. Warn loudly when auth is on but the secret is unpinned; surface it in the dashboard.
_pinned = bool(ui_env.get(_ENV_SECRET, ""))
secret = ui_env.get(_ENV_SECRET, "") or secrets.token_hex(32)
if password and not _pinned:   # auth enabled (non-empty password) + no pinned secret
    logger.warning(
        "KANBAN_MATE_UI_SESSION_SECRET is not set — the session secret is random per start, so a "
        "restart/redeploy will log the operator out. Set it in the UI .env to persist sessions."
    )
```

The dashboard's `session_secret_pinned` (phase 1.4) reads `os.environ.get(_ENV_SECRET)`; the env-var
name is the same `_ENV_SECRET` constant (`cli/config.py:40`). The regression test (**ACC-11**) proves
a token survives a "restart" when the secret is pinned:

```python
"""Tests for the persistent session secret (bosun §12)."""
from __future__ import annotations
from kanbanmate.http.auth import AuthConfig, make_token, verify_token


def test_token_survives_restart_with_pinned_secret() -> None:
    """A token minted under one AuthConfig verifies under a fresh one built from the SAME secret."""
    secret = "pinned-deadbeef-cafef00d"
    cfg_a = AuthConfig(login="op", password="pw", secret=secret)
    token = make_token("op", cfg_a.secret)
    # Simulate a process restart: a brand-new AuthConfig from the SAME pinned secret.
    cfg_b = AuthConfig(login="op", password="pw", secret=secret)
    assert verify_token(token, cfg_b.secret) == "op"


def test_token_dies_across_restart_with_random_secret() -> None:
    """Control: distinct random secrets (the unpinned bug) invalidate the token."""
    import secrets
    token = make_token("op", secrets.token_hex(32))
    assert verify_token(token, secrets.token_hex(32)) is None
```

> Confirm `make_token`/`verify_token` signatures before writing: `make_token(login, secret, ttl, *,
> now)` (`auth.py:76`) — `ttl` may be a positional/keyword with a default; call it with the real
> default. `verify_token(token, secret, *, now)` (`auth.py:97`). Read `auth.py:76-100` and match
> exactly (the second positional is `secret`). (**ACC-11**.)

Run: `pytest tests/cli/test_config_secret.py -v` → 2 PASS.

---

## Sub-phase 2.8 — UI: control + CSRF wiring + confirm modals

**Commit:** `feat(bosun): UI daemon control, PAUSE, logs + CSRF header + confirm modals`

**Files touched:**

- Modify: `web/src/lib/api.js` — attach `X-KM-CSRF` (read the `km_csrf` cookie) to every mutating
  call, once (DESIGN §6).
- Modify/Create: `web/src/panels/AdminPanel.jsx` (or `DaemonPanel.jsx`) — start/stop/restart buttons
  (UI-app standalone disabled per D1), PAUSE toggle, bounded log tail viewer.
- Reuse: the existing confirm dialog primitive (`web/src/components/SyncBoardDialog.jsx`) for
  restart/PAUSE-on (DESIGN §6 confirm UX).

**What to implement:** the `api.js` helper reads `document.cookie` for `km_csrf` and sets the header
on POST/PATCH/DELETE. Destructive actions open the confirm modal before sending. Run
`cd web && npm run build` → succeeds.

---

## Definition of Done

- [ ] `pytest tests/core/test_pm2_allowlist.py tests/app/test_audit.py tests/http/test_csrf.py tests/http/test_admin_daemon.py tests/http/test_admin_pause.py tests/cli/test_config_secret.py -v` — all PASS.
- [ ] `make check` → green; no module over 1000 LOC (new routes live in `admin_routes.py`, not
  `config_api.py`).
- [ ] Layering guard green: `core/pm2_allowlist.py` imports nothing from `app`/`adapters`/`cli`/
  `daemon` (`tests/test_layering.py` full-AST walk).
- [ ] CSRF retro-coverage verified: an existing write (`PATCH /api/projects/{id}`) is now rejected
  without `X-KM-CSRF` (DESIGN §6 retro-coverage).
- [ ] **ACC-03** (restart → job), **ACC-04** (UI-app standalone refused 422), **ACC-09** (PAUSE
  toggle observed by the store reader), **ACC-11** (token survives pinned-secret restart), and the
  CSRF/allowlist parts of **ACC-10** hold.
- [ ] `cd web && npm run build` → succeeds.
