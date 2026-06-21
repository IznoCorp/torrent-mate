# Phase 03 — Wiring + registry + daemon switch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

## Gate

Phase 02 must be complete and `make check` green:
- `src/kanbanmate/adapters/board/native.py` exists with `NativeBoardBackend`.
- `tests/adapters/test_native_backend.py` passes.

## Goal

Wire the `board_backend` switch into `WiringConfig`/`build_deps`, add `ProjectEntry.board_backend` to the registry loader, and thread `board_backend` through `daemon/registry_wiring.py`. After this phase: setting `board_backend: native` in `projects.json` routes to `NativeBoardBackend`; omitting it keeps every existing daemon byte-identical (the default `"github"` path).

## Files

- **Modify:** `src/kanbanmate/app/wiring.py` — add `board_backend: str = "github"` + `board_mirror: bool = True` to `WiringConfig`; add the switch in `build_deps`
- **Modify:** `src/kanbanmate/cli/init.py` — add `board_backend: str = "github"` to `ProjectEntry`; add `.get("board_backend", "github")` in `_load_registry`
- **Modify:** `src/kanbanmate/daemon/registry_wiring.py` — thread `board_backend` onto `WiringConfig` in `wiring_for_entry`
- **Create:** `tests/app/test_wiring_board_backend.py` — engine integration + back-compat tests

## Key design facts (grounded)

- `WiringConfig` is `@dataclass(frozen=True)` at `wiring.py:31`. New fields use defaults so existing callers are byte-identical.
- `build_deps` constructs `GithubClient` at `wiring.py:126` and wires it into `Deps` at `wiring.py:144-185`.
- The per-project store sub-root is computed as `config.state_root or config.kanban_root` at `wiring.py:130`. `FsBoardStateStore` uses this same path.
- `wiring_for_entry` at `registry_wiring.py:39-94` constructs the `WiringConfig` — `board_backend` follows the same `entry.ingress` pattern at `:93`.
- `ProjectEntry` is `@dataclass(frozen=True)` at `cli/init.py:87`. New field must have a default.
- `_load_registry` at `cli/init.py:194-227` uses `.get("ingress", "webhook")` pattern at `:223`. `board_backend` follows identically.
- The `option_name_for_key` function for the native backend: derive from `load_columns(config.columns_yaml)` — `Column.key` → `Column.name` mapping.

---

### Task 1: `WiringConfig` + `build_deps` switch (`app/wiring.py`)

**Files:**
- Modify: `src/kanbanmate/app/wiring.py`

- [ ] **Step 1: Write failing test**

In `tests/app/test_wiring_board_backend.py`:

```python
"""Tests for the board_backend switch in build_deps + back-compat (anchor §12.5, §12.6)."""

from __future__ import annotations

def test_wiring_config_has_board_backend_default() -> None:
    from kanbanmate.app.wiring import WiringConfig
    wc = WiringConfig(
        token="t", project_id="pid", repo="o/r",
        clone_dir="/tmp/clone", columns_yaml="columns: []",
    )
    assert wc.board_backend == "github"
    assert wc.board_mirror is True
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/app/test_wiring_board_backend.py::test_wiring_config_has_board_backend_default -v
```

Expected: `AttributeError` — `WiringConfig has no attribute 'board_backend'`.

- [ ] **Step 3: Add two defaulted fields to `WiringConfig` in `app/wiring.py`**

In `src/kanbanmate/app/wiring.py`, inside the `WiringConfig` dataclass, append after the `ingress: str = "polling"` field (line 93):

```python
    # anchor §4.2: the per-project board backend. ``"github"`` (default) keeps every live
    # daemon byte-identical until the operator opts in. ``"native"`` routes to
    # ``NativeBoardBackend`` (the decorator, anchor §4.3).
    board_backend: str = "github"
    # anchor §5: one-way GitHub mirror under native — default on so the GitHub Projects
    # board + status pill + Health field keep reflecting native placement after cutover.
    board_mirror: bool = True
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/app/test_wiring_board_backend.py::test_wiring_config_has_board_backend_default -v
```

- [ ] **Step 5: Add the `board_backend` switch to `build_deps` in `app/wiring.py`**

In `src/kanbanmate/app/wiring.py`, in `build_deps`, replace the lines that set up `board` and the Deps construction. Currently `wiring.py:126` starts with `board = GithubClient(...)`.

Replace the `board = GithubClient(...)` line and the `return Deps(board_writer=board, board_reader=board, ...)` block with:

```python
    github = GithubClient(config.token, project_id=config.project_id, repo=config.repo)
    # anchor §4.2: the board_backend switch — the ONLY place concrete adapter classes are named
    # (CLAUDE.md hexagonal rule). Default "github" keeps every live daemon byte-identical.
    if config.board_backend == "native":
        from kanbanmate.adapters.board.native import NativeBoardBackend  # noqa: PLC0415
        from kanbanmate.adapters.store.fs_board import FsBoardStateStore  # noqa: PLC0415
        from kanbanmate.core.columns import load_columns  # noqa: PLC0415

        board_store = FsBoardStateStore(
            Path(store_root) if store_root else Path(config.kanban_root or "~/.kanban").expanduser()
        )
        col_map = load_columns(config.columns_yaml)
        columns = [col.key for col in col_map.values()]
        # Map column key → GitHub Status display name (used by the mirror to call move_card
        # with the option NAME, not the key — see GithubClient.move_card / field.options).
        _col_name_map: dict[str, str] = {col.key: col.name for col in col_map.values()}
        board_reader = board_writer = NativeBoardBackend(
            forge=github,
            store=board_store,
            columns=columns,
            option_name_for_key=lambda key: _col_name_map.get(key, key),
            mirror=github if config.board_mirror else None,
        )
    else:
        board_reader = board_writer = github
```

Then update the `return Deps(...)` call to use `board_writer=board_writer, board_reader=board_reader` instead of `board_writer=board, board_reader=board`.

- [ ] **Step 6: Add integration test for the native wiring path**

Append to `tests/app/test_wiring_board_backend.py`:

```python
import pathlib
from unittest.mock import MagicMock, patch


_MINIMAL_COLUMNS_YAML = """
columns:
  Backlog:
    name: Backlog
    class: inert
  InProgress:
    name: In Progress
    class: reactive
"""


def test_build_deps_native_backend_routes_to_native(tmp_path: pathlib.Path) -> None:
    """build_deps with board_backend='native' wires NativeBoardBackend into both slots."""
    from kanbanmate.adapters.board.native import NativeBoardBackend
    from kanbanmate.app.wiring import WiringConfig, build_deps

    clone = tmp_path / "clone"
    clone.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = WiringConfig(
        token="tok",
        project_id="pid",
        repo="o/r",
        clone_dir=str(clone),
        columns_yaml=_MINIMAL_COLUMNS_YAML,
        kanban_root=str(root),
        board_backend="native",
        board_mirror=False,
    )
    deps = build_deps(wc)
    assert isinstance(deps.board_reader, NativeBoardBackend)
    assert isinstance(deps.board_writer, NativeBoardBackend)


def test_build_deps_github_default_byte_identical(tmp_path: pathlib.Path) -> None:
    """build_deps with board_backend='github' (default) wires GithubClient — back-compat."""
    from kanbanmate.adapters.github.client import GithubClient
    from kanbanmate.app.wiring import WiringConfig, build_deps

    clone = tmp_path / "clone"
    clone.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = WiringConfig(
        token="tok",
        project_id="pid",
        repo="o/r",
        clone_dir=str(clone),
        columns_yaml=_MINIMAL_COLUMNS_YAML,
        kanban_root=str(root),
        # NO board_backend set → defaults to "github"
    )
    deps = build_deps(wc)
    assert isinstance(deps.board_reader, GithubClient)
    assert isinstance(deps.board_writer, GithubClient)
```

- [ ] **Step 7: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/app/test_wiring_board_backend.py -v
```

Expected: all PASS.

- [ ] **Step 8: Run make check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make check
```

Expected: green.

- [ ] **Step 9: Commit**

```bash
git add src/kanbanmate/app/wiring.py tests/app/test_wiring_board_backend.py
git commit -m "feat(anchor): board_backend switch in WiringConfig + build_deps"
```

---

### Task 2: Registry — `ProjectEntry.board_backend` + `_load_registry` (`cli/init.py`)

**Files:**
- Modify: `src/kanbanmate/cli/init.py`

- [ ] **Step 1: Write failing test**

In `tests/cli/test_init.py` (append):

```python
def test_project_entry_board_backend_defaults_to_github() -> None:
    from kanbanmate.cli.init import ProjectEntry
    entry = ProjectEntry(
        repo="o/r", clone="/tmp/c", project_id="pid",
        status_field_node_id="sfid",
    )
    assert entry.board_backend == "github"


def test_load_registry_board_backend_back_compat(tmp_path) -> None:
    """An OLD-shaped projects.json without board_backend loads with default 'github'."""
    import json
    from kanbanmate.cli.init import _load_registry
    path = tmp_path / "projects.json"
    path.write_text(json.dumps({
        "pid": {
            "repo": "o/r",
            "clone": "/tmp/c",
            "project_id": "pid",
            "status_field_node_id": "sfid",
        }
    }))
    reg = _load_registry(path)
    assert reg["pid"].board_backend == "github"


def test_load_registry_board_backend_explicit(tmp_path) -> None:
    import json
    from kanbanmate.cli.init import _load_registry
    path = tmp_path / "projects.json"
    path.write_text(json.dumps({
        "pid": {
            "repo": "o/r",
            "clone": "/tmp/c",
            "project_id": "pid",
            "status_field_node_id": "sfid",
            "board_backend": "native",
        }
    }))
    reg = _load_registry(path)
    assert reg["pid"].board_backend == "native"
```

- [ ] **Step 2: Run to confirm failures**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/cli/test_init.py -k "board_backend" -v
```

- [ ] **Step 3: Add `board_backend` field to `ProjectEntry` in `cli/init.py`**

In `src/kanbanmate/cli/init.py`, inside the `ProjectEntry` dataclass, append after `token_ref: str = ""` (line 147):

```python
    # anchor §9: the per-project board backend switch — ``"github"`` (default) keeps all
    # existing projects byte-identical until an explicit opt-in. ``"native"`` routes the
    # daemon's board slots to ``NativeBoardBackend`` (anchor §4.2).
    board_backend: str = "github"
```

- [ ] **Step 4: Add `.get("board_backend", "github")` to `_load_registry` in `cli/init.py`**

In `_load_registry` (around line 224), after `token_ref=val.get("token_ref", ""),`, add:

```python
            board_backend=val.get("board_backend", "github"),
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/cli/test_init.py -k "board_backend" -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/kanbanmate/cli/init.py
git commit -m "feat(anchor): ProjectEntry.board_backend field + _load_registry back-compat"
```

---

### Task 3: Thread `board_backend` through `daemon/registry_wiring.py`

**Files:**
- Modify: `src/kanbanmate/daemon/registry_wiring.py`

- [ ] **Step 1: Write failing test**

Append to `tests/app/test_wiring_board_backend.py`:

```python
def test_wiring_for_entry_threads_board_backend(tmp_path: pathlib.Path) -> None:
    """wiring_for_entry threads board_backend from the registry entry onto WiringConfig."""
    from kanbanmate.cli.init import ProjectEntry
    from kanbanmate.daemon.registry_wiring import wiring_for_entry

    clone = tmp_path / "clone"
    clone.mkdir()
    columns_path = clone / ".claude" / "kanban"
    columns_path.mkdir(parents=True)
    (columns_path / "columns.yml").write_text(_MINIMAL_COLUMNS_YAML)

    entry = ProjectEntry(
        repo="o/r",
        clone=str(clone),
        project_id="pid",
        status_field_node_id="sfid",
        board_backend="native",
    )
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = wiring_for_entry(root, entry, multi=False, kill_switch=False)
    assert wc.board_backend == "native"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/app/test_wiring_board_backend.py::test_wiring_for_entry_threads_board_backend -v
```

Expected: assertion error — `wc.board_backend == "github"` (the default, not threaded yet).

- [ ] **Step 3: Thread `board_backend` in `wiring_for_entry`**

In `src/kanbanmate/daemon/registry_wiring.py`, in `wiring_for_entry` (the `return WiringConfig(...)` block at line 81-94), add after `ingress=entry.ingress or "webhook"`:

```python
        board_backend=getattr(entry, "board_backend", "github"),  # anchor §9
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/app/test_wiring_board_backend.py -v
```

Expected: all PASS.

- [ ] **Step 5: Run make check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make check
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/kanbanmate/daemon/registry_wiring.py
git commit -m "feat(anchor): thread board_backend from registry entry onto WiringConfig"
```
