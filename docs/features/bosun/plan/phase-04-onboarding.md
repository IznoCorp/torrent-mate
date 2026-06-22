# Phase 4 — Project onboarding (add local / add clone / remove) + directory browser

## Gate

Phases 1–3 complete (jobs + CSRF + audit + redeploy green). `make check` green on phase-3 HEAD. This
phase adds the two pure path/URL validators and the project create/delete + browse routes (DESIGN
§9, §5.2, §5.3). Satisfies **ACC-07, ACC-08**, and the path/git-URL parts of **ACC-10**.

## Overview

Add `core/git_url.py` (git-URL allowlist validator) and `core/onboard_paths.py` (pure containment
check), a small `_delete_project` registry helper in `cli/init.py` (the registry has no delete
today), and the onboarding routes in a new `http/projects_routes.py`: `POST /api/projects` (job:
add-from-local | add-from-clone), `DELETE /api/projects/{id}` (sync, refuse while a live agent
exists), and `GET /api/admin/browse` (dir-browser confined to `ONBOARD_BASE_DIRS`). Six sub-phases.

---

## Sub-phase 4.1 — Pure `core/git_url.py`

**Commit:** `feat(bosun): pure git-URL allowlist validator (core/git_url.py)`

**Files touched:**

- Create: `src/kanbanmate/core/git_url.py`
- Create: `tests/core/test_git_url.py`

**What to implement** (DESIGN §5.2) — accept only `https://<host>/<owner>/<repo>(.git)` with host ∈
allowlist; reject `file://`, `ssh://`, `git://`, scp-style `git@host:path`, any other scheme/host.
Pure, stdlib `urllib.parse` only:

```python
"""Pure git-clone-URL allowlist validator (bosun §5.2).

Accepts only ``https://<host>/<owner>/<repo>(.git)`` where ``host`` is in the allowlist. Rejects
file://, ssh://, git://, scp-style ``git@host:path``, and any other scheme/host — defense-in-depth
because the UI is internet-fronted via Caddy. No I/O (no network, no clock) → lives in ``core``.
"""
from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_GIT_HOSTS: frozenset[str] = frozenset({"github.com"})


def validate_git_url(url: str, *, allowed_hosts: frozenset[str] = ALLOWED_GIT_HOSTS) -> str | None:
    """Return ``None`` if ``url`` is a permitted clone source, else a refusal reason (DESIGN §5.2).

    Args:
        url: The candidate git clone URL.
        allowed_hosts: The host allowlist (default ``github.com`` only).

    Returns:
        ``None`` when permitted; otherwise a human-readable refusal string (HTTP → 422).
    """
    if not url or "://" not in url:
        # scp-style git@host:path has no scheme separator → reject here.
        return "git URL must be https://<host>/<owner>/<repo>"
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return f"scheme '{parsed.scheme}' not allowed (https only)"
    if parsed.hostname not in allowed_hosts:
        return f"host '{parsed.hostname}' not in allowlist"
    # Require a /<owner>/<repo> path (at least two non-empty segments).
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        return "git URL must include <owner>/<repo>"
    return None
```

**Tests** (`tests/core/test_git_url.py`) — accept the canonical github https; reject file/ssh/git/scp
(DESIGN §15):

```python
import pytest
from kanbanmate.core.git_url import validate_git_url


@pytest.mark.parametrize("url", [
    "https://github.com/LounisBou/KanbanMate",
    "https://github.com/LounisBou/KanbanMate.git",
])
def test_https_github_accepted(url) -> None:
    assert validate_git_url(url) is None


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ssh://git@github.com/o/r.git",
    "git://github.com/o/r.git",
    "git@github.com:o/r.git",                 # scp-style — no scheme separator
    "https://evil.example.com/o/r.git",       # host not allowlisted
    "https://github.com/onlyowner",           # missing repo segment
    "",
])
def test_disallowed_rejected(url) -> None:
    assert validate_git_url(url) is not None
```

Run: `pytest tests/core/test_git_url.py -v` → all PASS.

---

## Sub-phase 4.2 — Pure `core/onboard_paths.py`

**Commit:** `feat(bosun): pure path-confinement check (core/onboard_paths.py)`

**Files touched:**

- Create: `src/kanbanmate/core/onboard_paths.py`
- Create: `tests/core/test_onboard_paths.py`

**What to implement** (DESIGN §5.3) — a pure containment check; the **caller** (app layer) does the
`expanduser` + `Path.resolve()` (follows symlinks) I/O and passes resolved paths in:

```python
"""Pure path-confinement check for onboarding (bosun §5.3, decision D2).

The CALLER (app layer) does the I/O: ``expanduser`` + ``Path.resolve()`` (follows symlinks) on both
the candidate and each ``ONBOARD_BASE_DIRS`` entry, then passes the resolved paths here. This module
does NO I/O — it only decides containment, so it lives in ``core``.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Sequence


def is_within_base_dirs(resolved: PurePosixPath, resolved_bases: Sequence[PurePosixPath]) -> bool:
    """Return ``True`` iff ``resolved`` equals or is under one of ``resolved_bases`` (DESIGN §5.3).

    Args:
        resolved: The already-resolved (symlink-followed) candidate path.
        resolved_bases: The already-resolved ``ONBOARD_BASE_DIRS`` entries.

    Returns:
        ``True`` when the candidate is contained in (or equals) a base dir, else ``False``.
    """
    for base in resolved_bases:
        if resolved == base or base in resolved.parents:
            return True
    return False
```

The `ONBOARD_BASE_DIRS` default `["~/dev", "~/deploy", "~/staging"]` is an **app-layer constant**
(it expands `~`, which is environment I/O) — DESIGN §5.3. Define it in `app/onboard.py` (sub-phase
4.4), not in `core`.

**Tests** (`tests/core/test_onboard_paths.py`) — under/equal/outside/symlink-escape; real non-trivial
paths on both sides:

```python
from pathlib import PurePosixPath
from kanbanmate.core.onboard_paths import is_within_base_dirs

BASES = [PurePosixPath("/home/izno/dev"), PurePosixPath("/home/izno/deploy")]


def test_under_base_accepted() -> None:
    assert is_within_base_dirs(PurePosixPath("/home/izno/dev/KanbanMate"), BASES) is True


def test_equal_base_accepted() -> None:
    assert is_within_base_dirs(PurePosixPath("/home/izno/dev"), BASES) is True


def test_outside_rejected() -> None:
    assert is_within_base_dirs(PurePosixPath("/etc/passwd"), BASES) is False


def test_sibling_prefix_not_a_match() -> None:
    # /home/izno/development must NOT match base /home/izno/dev (parents check, not str-prefix).
    assert is_within_base_dirs(PurePosixPath("/home/izno/development/x"), BASES) is False
```

> The symlink-escape case is exercised at the **app** layer (where `Path.resolve()` runs); this pure
> module only sees already-resolved paths, so `test_sibling_prefix_not_a_match` proves the
> containment uses `.parents` (real semantics) rather than a naive string prefix.

Run: `pytest tests/core/test_onboard_paths.py -v` → all PASS.

---

## Sub-phase 4.3 — Registry delete helper `cli/init._delete_project`

**Commit:** `feat(bosun): registry delete helper (cli/init._delete_project)`

**Files touched:**

- Modify: `src/kanbanmate/cli/init.py` — add `_delete_project` next to `_upsert_project`
  (`cli/init.py:301`).
- Create: `tests/cli/test_init_delete_project.py`

**What to implement** — mirror `_upsert_project` (`cli/init.py:301-317`): load registry, drop the
key, write back with the same serialisation (`json.dumps(..., indent=2, sort_keys=True)`):

```python
def _delete_project(path: Path, project_node_id: str) -> bool:
    """Remove the registry entry keyed by ``project_node_id``; return whether it existed.

    Mirrors :func:`_upsert_project` (the registry has no delete today — removal was manual JSON
    editing). The clone on disk is NOT touched (bosun §9 leaves it).

    Args:
        path: The ``projects.json`` path.
        project_node_id: The registry key to remove.

    Returns:
        ``True`` if an entry was removed, ``False`` if the key was absent.
    """
    registry = _load_registry(path)
    if project_node_id not in registry:
        return False
    del registry[project_node_id]
    serialisable = {key: asdict(val) for key, val in registry.items()}
    path.write_text(json.dumps(serialisable, indent=2, sort_keys=True), encoding="utf-8")
    return True
```

> `asdict` and `json` are already imported in `cli/init.py` (used by `_upsert_project`,
> `cli/init.py:315-316`). Confirm before adding imports.

**Tests** (`tests/cli/test_init_delete_project.py`):

```python
import json
from pathlib import Path
from kanbanmate.cli.init import (
    ProjectEntry, _delete_project, _load_registry, _projects_path, _upsert_project,
)


def test_delete_existing_removes_entry(tmp_path: Path) -> None:
    path = _projects_path(tmp_path)
    entry = ProjectEntry(repo="O/r", clone=str(tmp_path / "c"), project_id="PVT_x",
                         status_field_node_id="FLD")
    _upsert_project(path, "PVT_x", entry)
    assert "PVT_x" in _load_registry(path)
    assert _delete_project(path, "PVT_x") is True
    assert "PVT_x" not in _load_registry(path)


def test_delete_absent_returns_false(tmp_path: Path) -> None:
    path = _projects_path(tmp_path)
    _upsert_project(path, "PVT_x", ProjectEntry(repo="O/r", clone="c", project_id="PVT_x",
                                                status_field_node_id="FLD"))
    assert _delete_project(path, "PVT_missing") is False
    assert "PVT_x" in _load_registry(path)  # untouched
```

> Confirm `ProjectEntry`'s required positional/keyword fields before constructing it: `repo`,
> `clone`, `project_id`, `status_field_node_id` are mandatory (`cli/init.py:132-135`); the rest have
> defaults (`cli/init.py:136-156`). Real values on both sides (entry created, then asserted absent).

Run: `pytest tests/cli/test_init_delete_project.py -v` → 2 PASS.

---

## Sub-phase 4.4 — Onboarding app helpers `app/onboard.py`

**Commit:** `feat(bosun): onboarding app helpers (resolve + confine + clone+init job body)`

**Files touched:**

- Create: `src/kanbanmate/app/onboard.py`
- Create: `tests/app/test_onboard.py`

**What to implement** — the imperative shell that does the I/O the pure validators can't: expand +
resolve `ONBOARD_BASE_DIRS` and candidates, call `is_within_base_dirs`, list a directory for the
browser, and the clone+`init` job body:

```python
"""Onboarding imperative shell (bosun §9): path resolution, dir listing, clone+init.

Holds the app-layer constant ONBOARD_BASE_DIRS (expands ``~`` → environment I/O, so NOT in core),
resolves candidate paths (follows symlinks via Path.resolve) and calls the pure
``core.onboard_paths.is_within_base_dirs`` for the decision, lists directories for the UI browser,
and runs the add-from-clone / add-from-local registration (calling ``cli.init.init``).
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from kanbanmate.core.onboard_paths import is_within_base_dirs

ONBOARD_BASE_DIRS: tuple[str, ...] = ("~/dev", "~/deploy", "~/staging")


def _resolved_bases() -> list[PurePosixPath]:
    return [PurePosixPath(str(Path(b).expanduser().resolve())) for b in ONBOARD_BASE_DIRS]


def path_is_confined(candidate: str) -> bool:
    """True iff ``candidate`` (after expanduser+resolve) is under an ONBOARD_BASE_DIRS root."""
    resolved = PurePosixPath(str(Path(candidate).expanduser().resolve()))
    return is_within_base_dirs(resolved, _resolved_bases())


def list_dir(candidate: str) -> dict:
    """Return ``{"path", "entries":[{"name","is_dir"}]}`` for a confined directory (DESIGN §7.1).

    Raises ``PermissionError`` when the path is outside ONBOARD_BASE_DIRS (HTTP → 422).
    """
    if not path_is_confined(candidate):
        raise PermissionError("path outside allowed roots")
    base = Path(candidate).expanduser().resolve()
    entries = [{"name": p.name, "is_dir": p.is_dir()} for p in sorted(base.iterdir())]
    return {"path": str(base), "entries": entries}
```

The add job body (`mode:"local"` registers an existing clone via `init(..., ensure_clone=...)`;
`mode:"clone"` git-clones then `init`s) is invoked from the HTTP route through `ops.create_job` with
a server-built argv into a hidden CLI command OR called directly inside a job — for v1, route the add
through a small `kanban` hidden command `onboard-exec` that the job runs, so the long clone/`init`
streams progress (mirror `ops-exec`, phase 1.2). Match `init`'s real signature
(`cli/init.py:343-355`): `init(repo, *, root, clone, project_title, seeder, template_path,
dev_repo_path, config_dir, ingress, ensure_clone)`.

**Tests** (`tests/app/test_onboard.py`) — point `ONBOARD_BASE_DIRS` at a tmp root via monkeypatch and
prove confinement + listing on real dirs:

```python
from pathlib import Path
import kanbanmate.app.onboard as onboard


def test_path_confined_true_under_base(tmp_path, monkeypatch) -> None:
    (tmp_path / "dev" / "Proj").mkdir(parents=True)
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    assert onboard.path_is_confined(str(tmp_path / "dev" / "Proj")) is True


def test_path_confined_false_outside(tmp_path, monkeypatch) -> None:
    (tmp_path / "dev").mkdir()
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    assert onboard.path_is_confined("/etc") is False


def test_list_dir_outside_raises(tmp_path, monkeypatch) -> None:
    (tmp_path / "dev").mkdir()
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    import pytest
    with pytest.raises(PermissionError):
        onboard.list_dir("/etc")


def test_list_dir_lists_entries(tmp_path, monkeypatch) -> None:
    base = tmp_path / "dev"
    (base / "ProjA").mkdir(parents=True)
    (base / "file.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(base),))
    out = onboard.list_dir(str(base))
    names = {e["name"]: e["is_dir"] for e in out["entries"]}
    assert names["ProjA"] is True and names["file.txt"] is False
```

Run: `pytest tests/app/test_onboard.py -v` → 4 PASS.

---

## Sub-phase 4.5 — Onboarding HTTP routes `http/projects_routes.py`

**Commit:** `feat(bosun): project create/delete + dir-browser routes`

**Files touched:**

- Create: `src/kanbanmate/http/projects_routes.py`
- Modify: `src/kanbanmate/http/config_api.py` — append the side-effect import (bottom).
- Modify: `src/kanbanmate/http/admin_routes.py` — add `GET /api/admin/browse`.
- Create: `tests/http/test_projects_routes.py`

**What to implement** (DESIGN §9):

```python
"""Project onboarding HTTP routes (bosun §9) — create/delete on the shared app.

Auth-gated by ``_auth_guard``, CSRF-protected by ``csrf_mw`` (mutating). POST /api/projects is a JOB
(clone/init are long); DELETE is sync + audited and REFUSES (409) while the project has a live agent.
"""
from __future__ import annotations

import fastapi
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate.app import ops
from kanbanmate.app.audit import append_audit
from kanbanmate.app.onboard import path_is_confined
from kanbanmate.core.git_url import validate_git_url
from kanbanmate.http.config_api import _kanban_root, app


@app.post("/api/projects")
async def create_project(request: fastapi.Request) -> JSONResponse:
    """Add a project (mode:local|clone) as a job (DESIGN §9). 422 on bad path/URL."""
    body = await _read_json_object(request)
    mode = str(body.get("mode", ""))
    root = str(_kanban_root())
    repo = str(body.get("repo", ""))            # "owner/name" for the registry entry
    if mode == "local":
        path = str(body.get("path", ""))
        if not path_is_confined(path):
            raise HTTPException(status_code=422, detail="path outside allowed roots")
        argv = ["kanban", "onboard-exec", "--mode", "local", "--root", root,
                "--repo", repo, "--path", path]
    elif mode == "clone":
        git_url = str(body.get("git_url", ""))
        reason = validate_git_url(git_url)
        if reason is not None:
            raise HTTPException(status_code=422, detail=reason)
        argv = ["kanban", "onboard-exec", "--mode", "clone", "--root", root,
                "--repo", repo, "--git-url", git_url]
    else:
        raise HTTPException(status_code=422, detail="mode must be 'local' or 'clone'")
    login = _actor_login(request)
    job_id = ops.create_job(_kanban_root(), type="project_add", actor=login, argv=argv,
                            args_summary=f"mode={mode}")
    append_audit(_kanban_root(), login, "project_add", f"mode={mode}")
    return JSONResponse(content={"job_id": job_id})


@app.delete("/api/projects/{project_id}")
async def delete_project_route(project_id: str, request: fastapi.Request) -> JSONResponse:
    """Deregister a project (clone left on disk). 409 while a live agent exists (DESIGN §9)."""
    if _project_has_live_agent(project_id):
        raise HTTPException(status_code=409, detail="project has a live agent — cannot remove")
    from kanbanmate.cli.init import _delete_project, _projects_path  # noqa: PLC0415
    removed = _delete_project(_projects_path(_kanban_root()), project_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"unknown project '{project_id}'")
    append_audit(_kanban_root(), _actor_login(request), "project_delete", project_id)
    return JSONResponse(content={"deleted": project_id})
```

The live-agent guard (DESIGN §9, §4 live-agent row) — LIVE = any ticket RUNNING/WAITING
(`LIVE_STATUSES`, `ports/store.py:78`; used at `app/drain.py:108`) **or** a tmux session
`Sessions.is_alive` true (`ports/workspace.py:317`). Implement `_project_has_live_agent` reading the
project's store sub-root for any tracked state in `LIVE_STATUSES`:

```python
def _project_has_live_agent(project_id: str) -> bool:
    """True if the project has any RUNNING/WAITING ticket (DESIGN §9 live-agent guard).

    Resolves the project's store sub-root, loads tracked states via the store's ``list_running``
    reader, and returns True if any state's status is in ``LIVE_STATUSES`` (RUNNING/WAITING).
    """
    from kanbanmate.adapters.store.fs_store import FsStore  # noqa: PLC0415
    from kanbanmate.ports.store import LIVE_STATUSES         # noqa: PLC0415
    sub_root = _project_store_root(_kanban_root(), project_id)   # <root>/projects/<safe(id)>
    store = FsStore(sub_root)
    return any(s.status in LIVE_STATUSES for s in store.list_running())
```

> Ground each symbol before implementing: confirm the store class name + constructor
> (`grep -n "^class .*Store" adapters/store/fs_store.py`), `list_running` (`fs_store.py:399`), and
> the per-project sub-root layout `<root>/projects/<safe(project_id)>/` (the daemon's per-project
> store root — registry memory; locate the existing `safe(project_id)` slug helper rather than
> re-deriving it). If you additionally probe tmux, match `Sessions.is_alive`'s real signature
> (`ports/workspace.py:317`). Add `GET /api/admin/browse` in `admin_routes.py` calling
> `onboard.list_dir` (maps `PermissionError` → 422).

**Tests** (`tests/http/test_projects_routes.py`) — assert 422 on a non-confined path and a
non-allowlisted git URL (real values), 409 with a stubbed live agent, and a successful delete via
`_delete_project`:

```python
def test_create_local_path_outside_roots_422(tmp_path, monkeypatch) -> None:
    api_mod = _setup(tmp_path)
    import kanbanmate.app.onboard as onboard
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    with TestClient(api_mod.app) as client:
        client.get("/api/health"); token = client.cookies.get("km_csrf")
        r = client.post("/api/projects", json={"mode": "local", "path": "/etc"},
                        headers={"X-KM-CSRF": token})
        assert r.status_code == 422


def test_create_clone_bad_url_422(tmp_path) -> None:
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health"); token = client.cookies.get("km_csrf")
        r = client.post("/api/projects", json={"mode": "clone", "git_url": "git@github.com:o/r.git"},
                        headers={"X-KM-CSRF": token})
        assert r.status_code == 422


def test_delete_refused_409_with_live_agent(tmp_path, monkeypatch) -> None:
    api_mod = _setup(tmp_path)   # seeds projects.json with PVT_x
    import kanbanmate.http.projects_routes as pr
    monkeypatch.setattr(pr, "_project_has_live_agent", lambda pid: True)
    with TestClient(api_mod.app) as client:
        client.get("/api/health"); token = client.cookies.get("km_csrf")
        r = client.delete("/api/projects/PVT_x", headers={"X-KM-CSRF": token})
        assert r.status_code == 409


def test_delete_removes_entry(tmp_path, monkeypatch) -> None:
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr
    monkeypatch.setattr(pr, "_project_has_live_agent", lambda pid: False)
    with TestClient(api_mod.app) as client:
        client.get("/api/health"); token = client.cookies.get("km_csrf")
        r = client.delete("/api/projects/PVT_x", headers={"X-KM-CSRF": token})
        assert r.status_code == 200 and r.json()["deleted"] == "PVT_x"
```

Run: `pytest tests/http/test_projects_routes.py -v` → all PASS. (**ACC-07**, **ACC-08**, path/URL
parts of **ACC-10**.)

> **Implementation drift (recorded at build time):**
> - **Job argv mechanism** — the sketch's `["kanban", "onboard-exec", …]` argv was NOT used. There is
>   no `onboard-exec` command on the `kanban` Typer app (adding one would bloat `cli/app.py` over the
>   1000-LOC ceiling). Instead a NEW standalone runner `src/kanbanmate/cli/onboard_exec.py` mirrors
>   `cli/ops_exec.py`, and the route builds the argv as
>   `[sys.executable, "-m", "kanbanmate.cli.onboard_exec", "--mode", …, "--root", …, "--repo", …, …]`
>   (server-constructed, never a client path). The runner re-validates path/git-URL before any I/O and
>   exits non-zero on failure so the job records `failed`. `mode=clone` `git clone --depth 1`s into
>   `<first ONBOARD_BASE_DIRS root>/<repo-name>` (re-confined) then `init(repo, root=…, clone=…)`.
> - **Live-agent guard** — the store class is `FsStateStore` (the plan sketch's `FsStore` does not
>   exist), at `adapters/store/fs_store.py`. `list_running()` already returns ONLY live states
>   (`LIVE_STATUSES` = RUNNING/WAITING, `ports/store.py:78`), so `_project_has_live_agent` resolves
>   the per-project sub-root `<root>/projects/<safe_project_id(project_id)>/` (the exact layout
>   `daemon/registry_wiring.py:80` + `health_dashboard.py:147` build; `safe_project_id` from
>   `core/registry_resolve.py`), short-circuits `False` when the sub-root is absent, else returns
>   `any(s.status in LIVE_STATUSES for s in store.list_running())`. tmux probing was NOT added (the
>   store states are the authoritative liveness source for the deregister guard).
> - **`_actor_login` reuse** — imported from `http.admin_routes` (defined there), `_read_json_object`
>   from `http.config_api`; `append_audit` from `app.audit`.

---

## Sub-phase 4.6 — UI: onboarding panel + dir-browser

**Commit:** `feat(bosun): UI project onboarding (add local/clone, remove, browser)`

**Files touched:**

- Modify: `web/src/panels/AdminPanel.jsx` — add-from-folder (uses `GET /api/admin/browse`),
  add-from-git-URL, and a guarded remove (confirm modal; surfaces the 409 live-agent refusal).
- Reuse: `web/src/components/SyncBoardDialog.jsx` for the remove confirm.

Run `cd web && npm run build` → succeeds.

---

## Definition of Done

- [ ] `pytest tests/core/test_git_url.py tests/core/test_onboard_paths.py tests/cli/test_init_delete_project.py tests/app/test_onboard.py tests/http/test_projects_routes.py -v` — all PASS.
- [ ] `make check` → green; layering guard accepts `core/git_url.py` + `core/onboard_paths.py`
  (no `app`/`adapters`/`cli`/`daemon` imports).
- [ ] `python -c "import kanbanmate.http.projects_routes, kanbanmate.app.onboard"` → no import error.
- [ ] `cd web && npm run build` → succeeds.
- [ ] **ACC-07** (add local/clone registers + daemon picks up), **ACC-08** (remove deregisters,
  refused 409 with live agent), and the path/git-URL parts of **ACC-10** hold.
