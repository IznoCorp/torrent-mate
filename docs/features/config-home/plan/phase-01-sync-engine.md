# Phase 01 — Sync Engine (additive JSON5 deep-merge + `init-config --sync` CLI)

**Goal:** Build the additive deep-merge engine that copies missing files and merges missing keys from `config.example/` into a target config directory, without ever modifying or deleting existing values.

**Design ref:** §3.3 `init-config --sync` (D4), DESIGN §6 test plan (golden pairs).

## Gate (entry conditions)

- DESIGN.md approved and operator-validated (D1–D4).
- `config.example/` exists at repo root with 19 files (master + 18 overlays).
- Existing `init-config` command in `personalscraper/commands/init_config.py` understood.
- Branch `feat/config-home` exists with clean working tree.

---

## Sub-phase 1.1 — Sync engine core (test-first)

**Commit:** `feat(config-home): add additive JSON5 deep-merge sync engine with golden tests`

**Files:**

- Create: `personalscraper/conf/sync.py`
- Create: `tests/conf/test_sync.py`

**Interfaces:**

- Produces: `sync_config_dir(example: Path, target: Path, *, dry_run: bool = False) -> list[str]` — returns list of human-readable descriptions of every addition made (empty list if nothing to add).
- Produces: `_deep_merge_additive(example_dict: dict, target_dict: dict) -> tuple[dict, list[str]]` — returns `(merged_dict, additions_descriptions)`.
- Produces: `_files_to_sync(example: Path, target: Path) -> list[tuple[Path, Path, str]]` — returns list of `(example_path, target_path, action)` tuples where action is `"copy"` or `"merge"`.

### Task 1.1.1: Write golden test fixtures

Create golden test pairs in `tests/conf/` (inline or tempdir-based):

```python
# tests/conf/test_sync.py
import json5
from pathlib import Path

from personalscraper.conf.sync import sync_config_dir, _deep_merge_additive

# ── Golden: deep-merge additive ──

def test_deep_merge_adds_missing_top_level_key():
    """A key present in example but absent from target is added."""
    example = {"paths": {"staging_dir": "/s"}, "disks": [{"id": "d1"}]}
    target = {"paths": {"staging_dir": "/s"}}
    merged, additions = _deep_merge_additive(example, target)
    assert "disks" in merged
    assert merged["disks"] == [{"id": "d1"}]
    assert len(additions) == 1
    assert "disks" in additions[0]

def test_deep_merge_adds_missing_nested_key():
    """A nested key in example but absent from target is added."""
    example = {"paths": {"staging_dir": "/s", "data_dir": "/d"}}
    target = {"paths": {"staging_dir": "/s"}}
    merged, additions = _deep_merge_additive(example, target)
    assert merged["paths"]["data_dir"] == "/d"
    assert merged["paths"]["staging_dir"] == "/s"  # existing preserved

def test_deep_merge_preserves_existing_values():
    """Existing target values are NEVER modified."""
    example = {"paths": {"staging_dir": "/new"}}
    target = {"paths": {"staging_dir": "/old"}}
    merged, additions = _deep_merge_additive(example, target)
    assert merged["paths"]["staging_dir"] == "/old"  # preserved
    assert len(additions) == 0

def test_deep_merge_preserves_target_extra_keys():
    """Keys in target but NOT in example are preserved."""
    example = {"paths": {"staging_dir": "/s"}}
    target = {"paths": {"staging_dir": "/s", "custom_key": "val"}}
    merged, additions = _deep_merge_additive(example, target)
    assert merged["paths"]["custom_key"] == "val"

def test_deep_merge_handles_list_values():
    """List-type values from example are added as whole units when the key is missing."""
    example = {"disks": [{"id": "d1"}]}
    target = {}
    merged, _ = _deep_merge_additive(example, target)
    assert merged["disks"] == [{"id": "d1"}]

def test_deep_merge_nested_dicts_merge_recursively():
    """Nested dicts are merged recursively, not replaced."""
    example = {"a": {"b": {"c": 1, "d": 2}}}
    target = {"a": {"b": {"c": 0}}}  # c exists, d missing
    merged, additions = _deep_merge_additive(example, target)
    assert merged["a"]["b"]["c"] == 0  # preserved
    assert merged["a"]["b"]["d"] == 2  # added
    assert len(additions) == 1
    assert "a.b.d" in additions[0] or "d" in additions[0]

# ── Golden: sync_config_dir idempotence + dry-run ──

def test_sync_on_empty_target_copies_all_files(tmp_path: Path):
    """Syncing onto an empty target copies every config.example file."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)  # helper below
    result = sync_config_dir(example, target, dry_run=False)
    assert len(result) > 0
    # Every example file exists in target
    for f in example.iterdir():
        assert (target / f.name).exists()

def test_sync_second_run_is_idempotent(tmp_path: Path):
    """A second sync with no example changes produces zero additions."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir(); target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)
    result2 = sync_config_dir(example, target, dry_run=False)
    assert len(result2) == 0

def test_sync_preserves_user_edits_in_target(tmp_path: Path):
    """After sync, a user-edited value in target remains unchanged."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir(); target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)
    # Simulate user edit
    paths_file = target / "paths.json5"
    paths_data = json5.loads(paths_file.read_text())
    paths_data["paths"]["staging_dir"] = "/user/custom/path"
    paths_file.write_text(json5.dumps(paths_data, indent=2))
    # Add a new key to example
    ex_paths = json5.loads((example / "paths.json5").read_text())
    ex_paths["paths"]["data_dir"] = "/new/data"
    (example / "paths.json5").write_text(json5.dumps(ex_paths, indent=2))
    # Sync again
    result = sync_config_dir(example, target, dry_run=False)
    # User edit preserved, new key added
    final = json5.loads((target / "paths.json5").read_text())
    assert final["paths"]["staging_dir"] == "/user/custom/path"
    assert final["paths"]["data_dir"] == "/new/data"

def test_dry_run_reports_but_does_not_write(tmp_path: Path):
    """--dry-run reports additions but touches no files."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir(); target.mkdir()
    _make_minimal_example(example)
    result = sync_config_dir(example, target, dry_run=True)
    assert len(result) > 0
    # No files written
    assert list(target.iterdir()) == []

def test_sync_never_removes_target_key(tmp_path: Path):
    """A key present in target but absent in example is NEVER removed."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir(); target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)
    # Add a key to target that example doesn't have
    paths_file = target / "paths.json5"
    data = json5.loads(paths_file.read_text())
    data["paths"]["operator_only_key"] = "keep_me"
    paths_file.write_text(json5.dumps(data, indent=2))
    # Remove that key from example
    ex_data = json5.loads((example / "paths.json5").read_text())
    if "operator_only_key" in ex_data.get("paths", {}):
        del ex_data["paths"]["operator_only_key"]
    (example / "paths.json5").write_text(json5.dumps(ex_data, indent=2))
    # Sync again
    sync_config_dir(example, target, dry_run=False)
    final = json5.loads((target / "paths.json5").read_text())
    assert final["paths"]["operator_only_key"] == "keep_me"


def _make_minimal_example(d: Path) -> None:
    """Create a minimal config.example structure for testing."""
    (d / "config.json5").write_text(json5.dumps({
        "config_version": 1,
        "overlays": ["paths.json5", "disks.json5"],
    }, indent=2))
    (d / "paths.json5").write_text(json5.dumps({
        "paths": {"staging_dir": "/tmp/staging", "torrent_complete_dir": "/tmp/torrents"},
    }, indent=2))
    (d / "disks.json5").write_text(json5.dumps({
        "disks": [{"id": "disk1", "path": "/Volumes/disk1", "categories": ["movies"]}],
    }, indent=2))
```

- [ ] Run: `pytest tests/conf/test_sync.py -v` — expect FAIL (module doesn't exist yet)

### Task 1.1.2: Implement `_deep_merge_additive`

```python
# personalscraper/conf/sync.py
"""Config sync engine — additive deep-merge from config.example to canonical.

Never modifies or removes existing keys.  Reports every addition made.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import json5

from personalscraper.logger import get_logger

log = get_logger("conf.sync")


def _deep_merge_additive(
    example_dict: dict[str, Any],
    target_dict: dict[str, Any],
    *,
    prefix: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Deep-merge *example_dict* into *target_dict* additively.

    For every key in *example_dict*:
    - If the key is absent from *target_dict*, add it (with example value).
    - If both values are dicts, recurse.
    - Otherwise, keep the target value (never overwrite).

    Args:
        example_dict: Source dict (from config.example).
        target_dict: Destination dict (the canonical config).
        prefix: Dot-separated key path for reporting (e.g. ``"paths"``).

    Returns:
        ``(merged_dict, additions)`` where *merged_dict* is the result and
        *additions* is a list of human-readable descriptions.
    """
    result = dict(target_dict)  # shallow copy — recursive calls re-copy
    additions: list[str] = []

    for key, example_val in example_dict.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if key not in result:
            result[key] = example_val
            additions.append(f"add key: {full_key}")
        elif isinstance(example_val, dict) and isinstance(result[key], dict):
            merged_sub, sub_additions = _deep_merge_additive(
                example_val, result[key], prefix=full_key
            )
            result[key] = merged_sub
            additions.extend(sub_additions)
        # else: target value exists and is not a dict-to-dict — preserve as-is

    return result, additions


def _files_to_sync(
    example: Path, target: Path
) -> list[tuple[Path, Path, str]]:
    """Enumerate files to sync from *example* to *target*.

    Args:
        example: Source config.example directory.
        target: Destination canonical config directory.

    Returns:
        List of ``(example_path, target_path, action)`` tuples where
        *action* is ``"copy"`` (file missing from target) or ``"merge"``
        (file exists in both — JSON5 deep-merge needed).
    """
    pairs: list[tuple[Path, Path, str]] = []
    for ex_file in sorted(example.iterdir()):
        if not ex_file.is_file():
            continue
        if ex_file.suffix not in (".json5", ".json"):
            continue
        target_file = target / ex_file.name
        if target_file.exists():
            pairs.append((ex_file, target_file, "merge"))
        else:
            pairs.append((ex_file, target_file, "copy"))
    return pairs


def sync_config_dir(
    example: Path,
    target: Path,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Sync config.example into the canonical config directory.

    Additive only: copies missing files, merges missing keys into existing
    files.  Never modifies or removes an existing key/value.

    Args:
        example: Path to ``config.example/``.
        target: Path to the canonical config directory.
        dry_run: If ``True``, report would-be additions without writing.

    Returns:
        List of human-readable descriptions of every addition.
        Empty if the target is already fully in sync.

    Raises:
        FileNotFoundError: If *example* is not a directory.
    """
    if not example.is_dir():
        raise FileNotFoundError(f"Example directory not found: {example}")

    target.mkdir(parents=True, exist_ok=True)
    pairs = _files_to_sync(example, target)
    all_additions: list[str] = []

    for ex_path, tgt_path, action in pairs:
        if action == "copy":
            msg = f"copy new file: {tgt_path.name}"
            all_additions.append(msg)
            if not dry_run:
                tgt_path.write_text(ex_path.read_text(), encoding="utf-8")
        elif action == "merge":
            ex_data = json5.loads(ex_path.read_text(encoding="utf-8"))
            tgt_data = json5.loads(tgt_path.read_text(encoding="utf-8"))
            merged, additions = _deep_merge_additive(ex_data, tgt_data)
            if additions:
                for a in additions:
                    all_additions.append(f"{tgt_path.name}: {a}")
                if not dry_run:
                    tgt_path.write_text(
                        json5.dumps(merged, indent=2), encoding="utf-8"
                    )
            # else: no new keys to add — skip write (preserves comments in
            # untouched sections, but a rewritten file loses hand-written
            # comments in the merged sections — documented in DESIGN §3.3).

    return all_additions
```

- [ ] Run: `pytest tests/conf/test_sync.py -v` — expect all PASS
- [ ] Commit: `git add personalscraper/conf/sync.py tests/conf/test_sync.py && git commit -m "feat(config-home): add additive JSON5 deep-merge sync engine with golden tests"`

---

## Sub-phase 1.2 — `init-config --sync` CLI integration

**Commit:** `feat(config-home): add --sync flag to init-config CLI`

**Files:**

- Modify: `personalscraper/commands/init_config.py`
- Modify: `personalscraper/commands/config.py`

**Interfaces:**

- Consumes: `sync_config_dir(example, target, *, dry_run) -> list[str]` from Phase 1.1
- Produces: `init_config_sync(example: Path, target: Path, *, dry_run: bool) -> None` — entry point for the `--sync` CLI flag

### Task 1.2.1: Add `init_config_sync` function

Add to `personalscraper/commands/init_config.py`:

```python
def init_config_sync(
    example: Path,
    target: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Sync missing keys and files from *example* to *target* additively.

    Non-destructive: never modifies or removes an existing key or value.
    Reports every addition via stdout.

    Args:
        example: Path to ``config.example/`` directory.
        target: Path to the canonical config directory (e.g.
            ``~/.torrentmate/config``).
        dry_run: If ``True``, report would-be additions without writing.
    """
    from personalscraper.conf.sync import sync_config_dir

    if dry_run:
        typer.echo(f"[DRY-RUN] Would sync {example} → {target}")
    else:
        typer.echo(f"Syncing {example} → {target}")

    additions = sync_config_dir(example, target, dry_run=dry_run)

    if not additions:
        typer.echo("No new keys or files to add — config is up to date.")
        return

    for msg in additions:
        typer.echo(f"  {msg}")

    typer.echo(f"\n{dry_run and 'Would add' or 'Added'} {len(additions)} item(s).")
    if not dry_run:
        typer.echo(
            "Tip: the canonical config is a local git repo "
            "(~/.torrentmate/config/.git). Review changes with:\n"
            "  git -C ~/.torrentmate/config diff"
        )
```

### Task 1.2.2: Wire `--sync` flag into CLI

Modify `personalscraper/commands/config.py` `init_config_cmd`:

In the existing `init_config_cmd` function signature (line 57), add:

```python
sync: bool = typer.Option(False, "--sync", help="Additive sync from config.example to canonical (D4)."),
```

And in the function body, before the existing `dry_run` check, add:

```python
# --sync mode: additive merge into existing config (non-destructive).
# Mutually exclusive with --force (which overwrites entirely).
if sync:
    if force:
        typer.echo("Error: --sync and --force are mutually exclusive.", err=True)
        raise typer.Exit(code=2)
    init_config_sync(example=example.resolve(), target=output.resolve(), dry_run=dry_run)
    return
```

- [ ] Run: `python -c "import personalscraper.commands.init_config"` — smoke test
- [ ] Run: `pytest tests/commands/test_init_config.py -v -k "sync or init"` — verify no regressions
- [ ] Run: `pytest tests/commands/test_init_config_e2e.py -v` — verify e2e still pass
- [ ] Commit: `git add personalscraper/commands/init_config.py personalscraper/commands/config.py && git commit -m "feat(config-home): add --sync flag to init-config CLI"`

---

## Gate (exit conditions)

- [ ] `pytest tests/conf/test_sync.py -v` — all golden tests pass
- [ ] `pytest tests/commands/test_init_config.py tests/commands/test_init_config_e2e.py -v` — no regressions
- [ ] `personalscraper init-config --sync --dry-run` against live `config/` — reports additions (or "up to date") without errors
- [ ] `personalscraper init-config --sync` against a temp copy — additively merges without destroying
- [ ] `python -c "import personalscraper.conf.sync"` — smoke test
