# Phase 03 — Verify Check + Ecosystem Test Pins + Worktree Invariant

**Goal:** Add a `config_home` verify check that warns when the resolved config directory is inside a git working tree, update ecosystem test pins to the new canonical path, add a new invariant test, and write integration tests for the sync engine.

**Design ref:** §3.4 Migration + guard tests, §6 Test plan.

## Gate (entry conditions)

- [ ] Phase 01 complete — `personalscraper/conf/sync.py` exists with `sync_config_dir()` working.
- [ ] `tests/indexer/test_ecosystem.py` understood — `_CANONICAL_CONFIG` on line 54, 4 assertions reference it.
- [ ] `personalscraper/verify/checks/` structure understood — `Check` protocol, `@register_check` decorator, `CheckContext`.

---

## Sub-phase 3.1 — `config_home` verify check (test-first)

**Commit:** `feat(config-home): add config_home verify check — warn when config lives inside a git worktree`

**Files:**

- Create: `personalscraper/verify/config_home.py`
- Create: `tests/verify/test_config_home.py`

**Interfaces:**

- Produces: `check_config_home(config_dir: Path) -> list[str]` — returns list of warning strings (empty if config is NOT inside a git working tree).
- Produces: `_is_inside_worktree(path: Path) -> bool` — walks up from _path_ looking for a `.git` file or directory.

**Note:** This check does NOT use the `Check`/`CheckContext` plugin framework — it's a system-level check (no media directory), invoked at startup or via a CLI sub-command, not during staging/dispatch verification.

### Task 3.1.1: Write tests

```python
# tests/verify/test_config_home.py
from pathlib import Path

from personalscraper.verify.config_home import (
    check_config_home,
    _is_inside_worktree,
)


def test_is_inside_worktree_true_when_git_dir_present(tmp_path: Path):
    """A path with a .git subdirectory is inside a worktree."""
    (tmp_path / ".git").mkdir()
    assert _is_inside_worktree(tmp_path) is True


def test_is_inside_worktree_true_when_git_file_present(tmp_path: Path):
    """A path whose parent has .git (git worktree) is inside a worktree."""
    (tmp_path / ".git").write_text("gitdir: /some/path")
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    assert _is_inside_worktree(sub) is True


def test_is_inside_worktree_false_outside_any_worktree(tmp_path: Path):
    """A path with no .git anywhere up to root is NOT inside a worktree."""
    assert _is_inside_worktree(tmp_path) is False


def test_is_inside_worktree_stops_at_root(tmp_path: Path):
    """The walk stops at filesystem root and returns False."""
    result = _is_inside_worktree(Path("/tmp"))
    # /tmp may or may not have .git — but the walk won't crash
    assert isinstance(result, bool)


def test_check_config_home_warns_inside_worktree(tmp_path: Path):
    """check_config_home returns a warning when config is inside a worktree."""
    (tmp_path / ".git").mkdir()
    cfg = tmp_path / "config"
    cfg.mkdir()
    warnings = check_config_home(cfg)
    assert len(warnings) >= 1
    assert any("inside a git working tree" in w for w in warnings)


def test_check_config_home_silent_outside_worktree(tmp_path: Path):
    """check_config_home returns empty list when config is NOT inside a worktree."""
    cfg = tmp_path / "isolated" / "config"
    cfg.mkdir(parents=True)
    warnings = check_config_home(cfg)
    assert warnings == []


def test_check_config_home_handles_nonexistent_dir():
    """check_config_home handles a nonexistent directory gracefully."""
    warnings = check_config_home(Path("/nonexistent/path/to/config"))
    assert len(warnings) >= 1  # should warn about missing dir, not crash
```

- [ ] Run: `pytest tests/verify/test_config_home.py -v` — expect FAIL

### Task 3.1.2: Implement

```python
# personalscraper/verify/config_home.py
"""Config-home safety check — warns when the resolved config directory lives
inside a git working tree (defense-in-depth against the pre-relocation vector
that made a dev branch checkout crash prod at boot — DESIGN §1, §3.4).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("verify.config_home")


def _is_inside_worktree(path: Path) -> bool:
    """Walk up from *path* to the filesystem root looking for ``.git``.

    A ``.git`` entry (file or directory) at any ancestor means *path* is
    inside a git working tree.  This is the REAL invariant: the canonical
    config must NOT live inside any git checkout.

    Args:
        path: Absolute path to check.

    Returns:
        ``True`` if a ``.git`` file or directory is found at *path* or any
        of its ancestors up to the filesystem root.
    """
    current = path.resolve()
    root = Path(current.anchor)  # "/" on Unix
    while current != root:
        if (current / ".git").exists():
            return True
        current = current.parent
    # Check root itself (unlikely but complete).
    return (root / ".git").exists()


def check_config_home(config_dir: Path) -> list[str]:
    """Verify that *config_dir* is NOT inside any git working tree.

    This is a lightweight startup guard.  After relocation (§3.1), the
    canonical config lives at ``~/.torrentmate/config`` which is NOT inside
    any working tree by construction.  If this check fires, someone (or a
    stale env var) is still pointing at the old in-repo location.

    Args:
        config_dir: Resolved path to the active config directory.

    Returns:
        List of warning strings.  Empty if the config is safely outside all
        working trees.
    """
    warnings: list[str] = []

    if not config_dir.is_dir():
        warnings.append(
            f"config_home: directory not found: {config_dir} — "
            "run 'personalscraper init-config' to create one."
        )
        return warnings

    if _is_inside_worktree(config_dir):
        warnings.append(
            f"config_home: config directory {config_dir} is inside a git "
            f"working tree. This is a boot-break hazard (DESIGN §1). "
            f"After migration, the canonical config lives at "
            f"~/.torrentmate/config — update PERSONALSCRAPER_CONFIG."
        )

    return warnings
```

- [ ] Run: `pytest tests/verify/test_config_home.py -v` — expect all PASS
- [ ] Commit: `git add personalscraper/verify/config_home.py tests/verify/test_config_home.py && git commit -m "feat(config-home): add config_home verify check — warn when config lives inside a git worktree"`

---

## Sub-phase 3.2 — Ecosystem test pins + worktree invariant

**Commit:** `feat(config-home): update ecosystem test pins to canonical config path + add worktree-invariant test`

**Files:**

- Modify: `tests/indexer/test_ecosystem.py` — update `_CANONICAL_CONFIG`, add invariant test

### Task 3.2.1: Update `_CANONICAL_CONFIG`

In `tests/indexer/test_ecosystem.py`, change line 54:

```python
# Before:
_CANONICAL_CONFIG = "/Users/izno/dev/PersonalScraper/config"

# After:
_CANONICAL_CONFIG = "/Users/izno/.torrentmate/config"
```

This single constant change updates all 4 assertions that reference it (lines 262-265 in `test_python_daemons_run_from_prod_clone`, lines 520-524 in `test_web_apps_run_from_their_deploy_clones`).

### Task 3.2.2: Add worktree-invariant test

Add to `tests/indexer/test_ecosystem.py`, after the existing `test_no_app_runs_from_the_dev_checkout`:

```python
def test_no_app_config_points_inside_a_git_worktree() -> None:
    """Invariant: no PM2 app's PERSONALSCRAPER_CONFIG may point inside a git working tree.

    This is the REAL invariant (DESIGN §3.4) — after relocation, the canonical
    config at ~/.torrentmate/config is outside every working tree by construction.
    If any app still points at a path inside a checkout, the pre-relocation
    boot-break vector is still active for that app.
    """
    from personalscraper.verify.config_home import _is_inside_worktree

    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    violations: list[tuple[str, str]] = []
    for app in apps:
        config_path = app.get("PERSONALSCRAPER_CONFIG")
        if config_path is None:
            continue
        path = Path(str(config_path))
        if _is_inside_worktree(path):
            violations.append((str(app["name"]), str(path)))
    assert violations == [], (
        f"{len(violations)} app(s) have PERSONALSCRAPER_CONFIG inside a git working tree: {violations}"
    )
```

- [ ] Run: `pytest tests/indexer/test_ecosystem.py -v` — expect PASS (constants updated, new invariant test passes once ecosystem.config.js updated — which happens in Phase 04; for now, this test will FAIL, confirming it catches the pre-migration state)
- [ ] Commit: `git add tests/indexer/test_ecosystem.py && git commit -m "feat(config-home): update ecosystem test pins to canonical config path + add worktree-invariant test"`

---

## Sub-phase 3.3 — Integration test: `init-config --sync` end-to-end

**Commit:** `test(config-home): add integration test for init-config --sync on tmp canonical`

**Files:**

- Create: `tests/integration/test_init_config_sync.py`

### Task 3.3.1: Write integration test

```python
# tests/integration/test_init_config_sync.py
"""Integration test: init-config --sync on a tmp canonical dir — end-to-end
exercise of the additive merge, idempotence, value preservation, and --dry-run
non-write guarantees (DESIGN §6).
"""

import json5
from pathlib import Path

from personalscraper.commands.init_config import init_config_sync
from personalscraper.conf.sync import sync_config_dir


def test_sync_end_to_end_additive_and_idempotent(tmp_path: Path):
    """Full cycle: sync onto empty target → sync again (idempotent) → modify target → sync again → values preserved."""
    example = tmp_path / "config.example"
    target = tmp_path / "canonical"
    example.mkdir(); target.mkdir()

    # Build a realistic example
    (example / "config.json5").write_text(json5.dumps({
        "config_version": 1,
        "overlays": ["paths.json5", "disks.json5", "categories.json5"],
    }, indent=2))
    (example / "paths.json5").write_text(json5.dumps({
        "paths": {"staging_dir": "/example/staging", "torrent_complete_dir": "/example/torrents"},
    }, indent=2))
    (example / "disks.json5").write_text(json5.dumps({
        "disks": [{"id": "disk1", "path": "/Volumes/disk1", "categories": ["movies"]}],
    }, indent=2))
    (example / "categories.json5").write_text(json5.dumps({
        "categories": {"movies": {"label": "Movies", "icon": "🎬"}},
    }, indent=2))

    # Step 1: first sync copies all files
    result1 = sync_config_dir(example, target, dry_run=False)
    assert len(result1) >= 3  # at least 3 files copied
    for name in ["config.json5", "paths.json5", "disks.json5", "categories.json5"]:
        assert (target / name).exists()

    # Step 2: second sync is idempotent
    result2 = sync_config_dir(example, target, dry_run=False)
    assert len(result2) == 0  # nothing to add

    # Step 3: user edits a value in target, then a new key is added to example
    paths_file = target / "paths.json5"
    paths_data = json5.loads(paths_file.read_text())
    paths_data["paths"]["staging_dir"] = "/operator/custom/staging"
    paths_data["paths"]["custom_operator_key"] = "keep_me"
    paths_file.write_text(json5.dumps(paths_data, indent=2))

    # Add new key to example
    ex_paths = json5.loads((example / "paths.json5").read_text())
    ex_paths["paths"]["data_dir"] = "/example/.data"
    (example / "paths.json5").write_text(json5.dumps(ex_paths, indent=2))

    # Step 4: sync again — user edits preserved, new key added
    result3 = sync_config_dir(example, target, dry_run=False)
    final = json5.loads((target / "paths.json5").read_text())
    assert final["paths"]["staging_dir"] == "/operator/custom/staging"  # preserved
    assert final["paths"]["custom_operator_key"] == "keep_me"           # preserved
    assert final["paths"]["data_dir"] == "/example/.data"               # added
    assert any("data_dir" in r for r in result3)


def test_init_config_sync_dry_run_does_not_write(tmp_path: Path):
    """init_config_sync --dry-run reports additions but writes nothing."""
    example = tmp_path / "config.example"
    target = tmp_path / "canonical"
    example.mkdir(); target.mkdir()
    (example / "config.json5").write_text('{"key": "val"}')

    # Dry-run should report files to copy but not write them
    from io import StringIO
    import sys
    old_stdout = sys.stdout
    sys.stdout = StringIO()  # suppress init_config_sync's typer.echo
    try:
        init_config_sync(example, target, dry_run=True)
    finally:
        sys.stdout = old_stdout

    # Nothing written
    assert not list(target.iterdir())
```

- [ ] Run: `pytest tests/integration/test_init_config_sync.py -v` — expect all PASS
- [ ] Commit: `git add tests/integration/test_init_config_sync.py && git commit -m "test(config-home): add integration test for init-config --sync on tmp canonical"`

---

## Gate (exit conditions)

- [ ] `pytest tests/verify/test_config_home.py -v` — all tests pass
- [ ] `pytest tests/indexer/test_ecosystem.py -v` — all tests pass (new invariant test will FAIL pre-migration — expected; re-check after Phase 04)
- [ ] `pytest tests/integration/test_init_config_sync.py -v` — all tests pass
- [ ] `python -c "from personalscraper.verify.config_home import check_config_home; print(check_config_home(Path('~/.torrentmate/config').expanduser()))"` — smoke test against real path (passes even if dir doesn't exist yet)
- [ ] `make lint` — zero errors
