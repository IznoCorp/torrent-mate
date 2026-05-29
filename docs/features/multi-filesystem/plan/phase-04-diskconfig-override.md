# Phase 4 — Optional `DiskConfig.fs_type` override + plumb capabilities

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give operators an escape hatch for unrecognised driver tokens (e.g.
`fuse-t` variants, Paragon NTFS) by adding an optional `fs_type` field to
`DiskConfig`. When set, the override beats auto-detection. Also replace the
blunt `/Volumes/` string-prefix reject in `IndexerConfig.db_path` with a
capability-aware check that correctly accepts an APFS volume mounted under
`/Volumes/`.

**NTFS invariant:** No change to NTFS transfer behaviour. `Dispatcher`'s
capability resolution from Phase 3 gains one branch: `disk.fs_type` (if set)
overrides `probe_mount`. The NTFS-safe `"unknown"` fallback is unchanged.

**Architecture:** `DiskConfig` gains `fs_type: str | None = None`. `Dispatcher`
reads it in `_resolve_capability`. `IndexerConfig._reject_external_mount`
replaces the `/Volumes/` prefix check with a capability lookup. No migration
script — `config/disks.json5` evolves in place.

**Tech Stack:** Pydantic `Field`, `field_validator`, `_fs_probe`, `_fs_capability`.

---

## Gate (prerequisites from Phase 3)

Phase 3 produced:

- `_transfer.py` using `FilesystemCapability` — no literal `--no-perms` in the file.
- `Dispatcher._disk_capabilities` dict resolved per disk.
- Golden argv tests green.

Verify:

```bash
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py | wc -l | tr -d ' '
# expected: 0

make check
# expected: exit 0
```

---

## Files

| Action | Path                                     |
| ------ | ---------------------------------------- |
| Modify | `personalscraper/conf/models/disks.py`   |
| Modify | `personalscraper/conf/models/indexer.py` |
| Modify | `personalscraper/dispatch/dispatcher.py` |
| Modify | `config.example/disks.json5`             |
| Create | `tests/conf/test_disk_config_fs_type.py` |

---

## Task 1 — Add `fs_type` to `DiskConfig`

**Files:**

- Modify: `personalscraper/conf/models/disks.py`

- [ ] **Step 1.1: Read current `DiskConfig` in `personalscraper/conf/models/disks.py`**

Current fields: `id`, `path`, `categories`. No `fs_type`.

- [ ] **Step 1.2: Add the optional `fs_type` field**

```python
"""Disk storage config model."""

from pathlib import Path
from typing import Annotated

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel


class DiskConfig(_StrictModel):
    """Disque de stockage avec ses catégories acceptées.

    Attributes:
        id: Free-form disk identifier (must match ``^[a-z][a-z0-9_]*$``).
        path: Absolute mounted path.
        categories: Category IDs accepted on this disk.
        fs_type: Optional canonical filesystem-type override.  When set,
            overrides auto-detection via ``FsProbe`` (useful for unrecognised
            driver tokens such as ``fuse-t`` variants).  Must be one of the
            canonical keys: ``"ntfs_macfuse"``, ``"apfs"``, ``"hfsplus"``,
            ``"exfat"``, ``"ext4"``, ``"unknown"``.  When ``None`` (default),
            the filesystem type is detected at runtime via ``probe_mount``.
    """

    id: str = Field(
        ...,
        min_length=1,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Identifiant libre (disk_a, nas_main, ...).",
    )
    path: Path = Field(..., description="Chemin monté absolu.")
    categories: Annotated[list[str], Field(min_length=1)] = Field(
        ..., description="IDs acceptés sur ce disque."
    )
    fs_type: str | None = Field(
        default=None,
        description=(
            "Optional canonical fs-type override (e.g. 'apfs', 'hfsplus', 'ntfs_macfuse'). "
            "When None, auto-detected via FsProbe at runtime. "
            "Use as escape hatch for unrecognised driver tokens."
        ),
    )
```

- [ ] **Step 1.3: Verify the model round-trips**

```bash
cd /Users/izno/dev/PersonnalScaper
python -c "
from personalscraper.conf.models.disks import DiskConfig
d = DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs')
print(d.fs_type)
d2 = DiskConfig(id='y', path='/tmp', categories=['movies'])
print(d2.fs_type)
"
# expected:
# apfs
# None
```

---

## Task 2 — Update `config.example/disks.json5` with a commented example

**Files:**

- Modify: `config.example/disks.json5`

- [ ] **Step 2.1: Read current `config.example/disks.json5`**

Current content has `id`, `path`, `categories` per disk entry.

- [ ] **Step 2.2: Add a commented `fs_type` example**

After the `categories` line in the first disk entry, add:

```json5
{
  // Storage disks (variable count).
  // id: free-form identifier used in CLI --disk and logs.
  // path: absolute mounted path.
  // categories: IDs accepted on this disk (builtin + custom_categories).
  // fs_type (optional): canonical filesystem-type override. Omit for auto-detection.
  //   Valid values: "ntfs_macfuse", "apfs", "hfsplus", "exfat", "ext4", "unknown".
  //   Use when the driver token is not auto-recognised (e.g. Paragon NTFS, fuse-t variants).
  disks: [
    {
      id: "drive_a",
      path: "/path/to/drive_a",
      categories: ["movies", "tv_shows", "anime", "audiobooks"],
      // fs_type: "ntfs_macfuse",  // uncomment to force NTFS-safe flags
    },
    // Example second disk:
    // {
    //   id: "drive_b",
    //   path: "/path/to/drive_b",
    //   categories: ["movies_animation", "tv_shows_animation", "movies_documentary", "tv_shows_documentary"],
    //   // fs_type: "hfsplus",  // HFS+ on AppleRAID — unlocks Unix perms
    // },
  ],
}
```

---

## Task 3 — Update `Dispatcher` to honour the `fs_type` override

**Files:**

- Modify: `personalscraper/dispatch/dispatcher.py`

- [ ] **Step 3.1: Replace `_resolve_capability` with `_resolve_disk_capability` in `Dispatcher.__init__`**

Phase 3 introduced `_resolve_capability(disk_path: str)`. Replace it with
`_resolve_disk_capability(disk: DiskConfig)` — the new signature takes the full
`DiskConfig` so it can read `disk.fs_type` before falling back to auto-detection:

```python
from personalscraper.indexer._fs_capability import FilesystemCapability, capability_for, NTFS_MACFUSE
from personalscraper.indexer._fs_probe import probe_mount


def _resolve_disk_capability(disk: "DiskConfig") -> FilesystemCapability:
    """Resolve FilesystemCapability for a disk.

    Args:
        disk: DiskConfig whose capability is needed.

    Returns:
        Capability from explicit override, or auto-detected via FsProbe,
        or NTFS-safe fallback when detection fails.
    """
    # Explicit operator override beats auto-detection.
    if disk.fs_type is not None:
        return capability_for(disk.fs_type)
    # Auto-detect via FsProbe (cached mount shell-out).
    info = probe_mount(str(disk.path))
    return capability_for(info.fs_type if info is not None else "unknown")
```

In `__init__`, replace the inline dict comprehension with:

```python
self._disk_capabilities: dict[str, FilesystemCapability] = {
    disk.id: _resolve_disk_capability(disk)
    for disk in self._disk_configs
}
```

---

## Task 4 — Replace `/Volumes/` prefix check in `IndexerConfig` with capability-aware check

**Files:**

- Modify: `personalscraper/conf/models/indexer.py`

- [ ] **Step 4.1: Read current `_reject_external_mount` validator**

The current check rejects any path starting with `/Volumes/`. This incorrectly
rejects a legitimate APFS DB path at e.g. `/Volumes/Data/library.db`.

- [ ] **Step 4.2: Replace the blunt prefix check with a capability-aware check**

```python
@field_validator("db_path", mode="after")
@classmethod
def _reject_external_mount(cls, v: Path | None) -> Path | None:
    """Resolve ``db_path`` and reject WAL-unsafe filesystem types.

    Invariants:

    1. **Absolute path.** Relative paths resolved against project root.
    2. **No WAL-unsafe mount.** SQLite WAL mode is unreliable on macFUSE-NTFS
       and network mounts.  Detection: probe the mount point and reject only
       ``ntfs_macfuse`` (and ``unknown`` as a conservative fallback).  A
       legitimate APFS volume under ``/Volumes/`` is accepted — the old
       ``/Volumes/`` prefix check was overly broad.

    Args:
        v: Raw Path value for db_path (may be relative, may be None).

    Returns:
        Absolute Path with ``~`` expanded, or None if not set.

    Raises:
        ValueError: If the resolved path is on a WAL-unsafe filesystem.
    """
    if v is None:
        return v
    resolved = v.expanduser()
    if not resolved.is_absolute():
        project_root = _paths_model._PROJECT_ROOT
        base = project_root if project_root is not None else Path.cwd()
        resolved = (base / resolved).resolve()

    # Capability-aware WAL-safety check.
    # Import here to avoid circular at module level (conf → indexer → conf).
    try:
        from personalscraper.indexer._fs_probe import probe_mount
        from personalscraper.indexer._fs_capability import capability_for

        info = probe_mount(str(resolved))
        fs_type = info.fs_type if info is not None else None
        # Only reject known WAL-unsafe types. Unknown → conservative reject.
        WAL_UNSAFE = {"ntfs_macfuse", "unknown"}
        if fs_type in WAL_UNSAFE:
            raise ValueError(
                f"db_path '{v}' resolves to a {fs_type} mount, which is WAL-unsafe. "
                "SQLite WAL mode is unreliable on macFUSE-NTFS filesystems. "
                "Move the database to an APFS or HFS+ volume."
            )
    except ImportError:
        # FsProbe not yet available (bootstrap scenario) — fall back to
        # the legacy /Volumes/ heuristic as defence-in-depth.
        if str(resolved).startswith("/Volumes/"):
            raise ValueError(
                f"db_path '{v}' resolves under /Volumes/ which may indicate an external or macFUSE mount. "
                "SQLite WAL mode is unreliable on such filesystems."
            )

    return resolved
```

Note: The `ImportError` fallback preserves backward-compatibility during bootstrap.
`db.py::open_db` still calls `_find_ntfs_mount` as defence-in-depth — keep it.

- [ ] **Step 4.3: Run config model tests**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/conf/ -v 2>/dev/null || pytest tests/ -k "indexer_config or disk_config" -v
# expected: all tests PASS
```

---

## Task 5 — Write config + capability override tests

**Files:**

- Create: `tests/conf/test_disk_config_fs_type.py`

- [ ] **Step 5.1: Check if `tests/conf/` directory exists, create if needed**

```bash
ls /Users/izno/dev/PersonnalScaper/tests/conf/ 2>/dev/null || mkdir -p /Users/izno/dev/PersonnalScaper/tests/conf/
ls /Users/izno/dev/PersonnalScaper/tests/conf/__init__.py 2>/dev/null || touch /Users/izno/dev/PersonnalScaper/tests/conf/__init__.py
```

- [ ] **Step 5.2: Create `tests/conf/test_disk_config_fs_type.py`**

```python
"""Tests for DiskConfig.fs_type field and Dispatcher override-beats-autodetect."""

import pytest
from pathlib import Path
from unittest.mock import patch

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.indexer._fs_capability import APFS, NTFS_MACFUSE, capability_for


class TestDiskConfigFsType:
    """AC-13: DiskConfig accepts an optional fs_type override."""

    def test_fs_type_none_by_default(self) -> None:
        d = DiskConfig(id="x", path="/tmp", categories=["movies"])
        assert d.fs_type is None

    def test_fs_type_apfs_override(self) -> None:
        d = DiskConfig(id="x", path="/tmp", categories=["movies"], fs_type="apfs")
        assert d.fs_type == "apfs"

    def test_fs_type_ntfs_macfuse_override(self) -> None:
        d = DiskConfig(id="x", path="/tmp", categories=["movies"], fs_type="ntfs_macfuse")
        assert d.fs_type == "ntfs_macfuse"

    def test_fs_type_hfsplus_override(self) -> None:
        d = DiskConfig(id="x", path="/tmp", categories=["movies"], fs_type="hfsplus")
        assert d.fs_type == "hfsplus"


class TestDispatcherCapabilityOverride:
    """Override beats autodetect: when fs_type is set, FsProbe is not used."""

    def test_override_beats_autodetect(self) -> None:
        """When DiskConfig.fs_type='apfs', capability is APFS regardless of probe."""
        from personalscraper.dispatch.dispatcher import _resolve_disk_capability

        disk = DiskConfig(id="raid", path="/Volumes/AppleRAID", categories=["movies"], fs_type="apfs")

        # Even if probe_mount would return ntfs_macfuse, the override wins.
        with patch("personalscraper.dispatch.dispatcher.probe_mount") as mock_probe:
            mock_probe.return_value = None  # probe would say "unknown"
            cap = _resolve_disk_capability(disk)

        assert cap == APFS
        mock_probe.assert_not_called()  # override skips the probe entirely

    def test_autodetect_used_when_no_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When fs_type is None, FsProbe result is used."""
        import personalscraper.dispatch.dispatcher as mod
        from personalscraper.indexer._fs_probe import MountInfo

        fake_info = MountInfo(
            mount_point="/Volumes/Disk1",
            fs_type="ntfs_macfuse",
            raw_fs_type="ufsd_ntfs",
            flags=frozenset({"local", "noatime"}),
        )
        monkeypatch.setattr(mod, "probe_mount", lambda _: fake_info)

        disk = DiskConfig(id="disk1", path="/Volumes/Disk1", categories=["movies"])
        cap = mod._resolve_disk_capability(disk)
        assert cap == NTFS_MACFUSE


class TestIndexerConfigDbPathValidator:
    """The db_path validator accepts APFS-under-/Volumes, rejects NTFS."""

    def test_apfs_under_volumes_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A legitimate APFS DB path at /Volumes/Data/library.db must be accepted."""
        import personalscraper.indexer._fs_probe as probe_mod
        from personalscraper.indexer._fs_probe import MountInfo

        apfs_info = MountInfo(
            mount_point="/Volumes/Data",
            fs_type="apfs",
            raw_fs_type="apfs",
            flags=frozenset(),
        )
        monkeypatch.setattr(probe_mod, "_run_mount", lambda: "")

        # Patch probe_mount to return APFS info for this path.
        import personalscraper.conf.models.indexer as idx_mod
        monkeypatch.setattr(
            "personalscraper.indexer._fs_probe.probe_mount",
            lambda p: apfs_info if "/Volumes/Data" in p else None,
        )

        from personalscraper.conf.models.indexer import IndexerConfig

        # Should not raise
        cfg = IndexerConfig(db_path=Path("/Volumes/Data/library.db"))
        assert cfg.db_path == Path("/Volumes/Data/library.db")
```

- [ ] **Step 5.3: Run the new tests**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/conf/test_disk_config_fs_type.py -v
# expected: all tests PASS
```

- [ ] **Step 5.4: Commit everything in this phase**

```bash
git add personalscraper/conf/models/disks.py \
        personalscraper/conf/models/indexer.py \
        personalscraper/dispatch/dispatcher.py \
        config.example/disks.json5 \
        tests/conf/test_disk_config_fs_type.py
git commit -m "feat(multi-filesystem): DiskConfig.fs_type override; capability-aware db_path validator"
```

---

## Task 6 — Phase gate + milestone commit

- [ ] **Step 6.1: Full quality gate**

```bash
make lint && make test && make check
# expected: exit 0, all green
```

- [ ] **Step 6.2: AC-13 spot check**

```bash
python -c "
from personalscraper.conf.models.disks import DiskConfig
d = DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs')
print(d.fs_type)
"
# expected: apfs
```

- [ ] **Step 6.3: Milestone commit**

```bash
git add -u
git commit -m "chore(multi-filesystem): phase 4 gate — DiskConfig.fs_type override, capability-aware db_path validator"
```

---

## Acceptance criteria for this phase

```bash
# AC-13
python -c "from personalscraper.conf.models.disks import DiskConfig; d=DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs'); print(d.fs_type)"
# expected: apfs

# AC-14
make check
# expected: exit 0

# AC-17
python -c "import personalscraper; print('ok')"
# expected: ok
```
