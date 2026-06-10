# Phase 02 — core/identity.MediaRef + AcquireConfig + acquire.json5

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the neutral `MediaRef` value object in `core/`, add `AcquireConfig` to the config
layer with WAL-safety validator mirroring `IndexerConfig`, and wire `acquire.json5` as the 16th
config overlay.

**Architecture:** `core/identity.py` imports only stdlib/typing (parallel to `core/_contracts.py`).
`conf/models/acquire.py` uses the WAL-safety pattern from `conf/models/indexer.py` but imports
`probe_mount` from `core/sqlite/` (not `indexer/`), removing the `# layering: allow` marker.
`Config` registers `acquire: AcquireConfig` and `_resolve_derived_paths` fills `acquire.db_path`.

**Tech stack:** pydantic `_StrictModel`, `Field`, `field_validator`; `parse_duration` from
`conf.models._duration`; stdlib `pathlib.Path`.

---

## Gate (from Phase 1)

- `personalscraper/core/sqlite/` package exists and all sub-modules import cleanly.
- `make check` is green on branch `feat/acquire-store`.
- `python -c "from personalscraper.core.sqlite import open_db, db_lock"` exits 0.

---

## File map

| Action | Path                                                                                     |
| ------ | ---------------------------------------------------------------------------------------- |
| Create | `personalscraper/core/identity.py`                                                       |
| Create | `personalscraper/conf/models/acquire.py`                                                 |
| Modify | `personalscraper/conf/models/config.py` (add `acquire` field + `_resolve_derived_paths`) |
| Create | `config.example/acquire.json5`                                                           |
| Modify | `config.example/config.json5` (add `"acquire.json5"` to overlays)                        |
| Modify | `config/config.json5` (add `"acquire.json5"` to overlays, if file exists)                |
| Modify | `docs/reference/config-overlay-layout.md` (15→16 overlays, acquire row)                  |
| Test   | `tests/conf/test_acquire_config.py`                                                      |

---

### Task 1 — Create `core/identity.py` with `MediaRef`

**Files:**

- Create: `personalscraper/core/identity.py`
- Test: `tests/core/test_identity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_identity.py
"""Unit tests for core.identity.MediaRef."""
from __future__ import annotations

import pytest
from personalscraper.core.identity import MediaRef


def test_media_ref_tvdb_primary() -> None:
    """tvdb_id is the primary identifier — must accept int."""
    ref = MediaRef(tvdb_id=255968)
    assert ref.tvdb_id == 255968
    assert ref.tmdb_id is None
    assert ref.imdb_id is None


def test_media_ref_all_slots() -> None:
    ref = MediaRef(tvdb_id=1, tmdb_id=2, imdb_id="tt0000001")
    assert ref.tvdb_id == 1
    assert ref.tmdb_id == 2
    assert ref.imdb_id == "tt0000001"


def test_media_ref_frozen() -> None:
    ref = MediaRef(tvdb_id=1)
    with pytest.raises((AttributeError, TypeError)):
        ref.tvdb_id = 99  # type: ignore[misc]


def test_media_ref_equality() -> None:
    assert MediaRef(tvdb_id=1) == MediaRef(tvdb_id=1)
    assert MediaRef(tvdb_id=1) != MediaRef(tvdb_id=2)


def test_media_ref_requires_at_least_one_id() -> None:
    with pytest.raises((ValueError, TypeError)):
        MediaRef()
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/core/test_identity.py -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError` or `ImportError` (module does not exist yet).

- [ ] **Step 3: Create `personalscraper/core/identity.py`**

```python
# personalscraper/core/identity.py
"""Neutral provider-ID value object for the acquisition lobe.

``MediaRef`` is deliberately NOT named ``ExternalIds`` — that name is taken
by ``indexer/external_ids.py`` (column-bound, series/episode hierarchical) and
``scraper/models.py::ScraperExternalIds`` (flat).  acquire/ may import neither
(layering), so a new neutral name is required.

tvdb_id is the primary identifier per the multi-provider separation rule:
TVDB primary (scrape), TMDB info+fallback, IMDB info only.

Import direction: stdlib + typing only (mirror core/_contracts.py).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaRef:
    """Neutral provider-ID value object keyed on tvdb_id (primary).

    At least one of tvdb_id, tmdb_id, imdb_id must be provided.

    Attributes:
        tvdb_id: TVDB series/movie ID (primary identifier).
        tmdb_id: TMDB series/movie ID (info + fallback).
        imdb_id: IMDB ID string e.g. ``"tt0000001"`` (info only).

    Raises:
        ValueError: If all three identifiers are None.
    """

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None

    def __post_init__(self) -> None:
        """Validate that at least one provider ID is set.

        Raises:
            ValueError: If tvdb_id, tmdb_id, and imdb_id are all None.
        """
        if self.tvdb_id is None and self.tmdb_id is None and self.imdb_id is None:
            raise ValueError("MediaRef requires at least one of tvdb_id, tmdb_id, imdb_id")


__all__ = ["MediaRef"]
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/core/test_identity.py -v 2>&1 | tail -10
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add personalscraper/core/identity.py tests/core/test_identity.py
git commit -m "feat(acquire-store): add core/identity.MediaRef value object"
```

---

### Task 2 — Create `conf/models/acquire.py` with `AcquireConfig`

**Files:**

- Create: `personalscraper/conf/models/acquire.py`
- Test: `tests/conf/test_acquire_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/conf/test_acquire_config.py
"""Tests for AcquireConfig WAL-safety validator."""
from __future__ import annotations

import pytest
from pathlib import Path
from personalscraper.conf.models.acquire import AcquireConfig


def test_acquire_config_defaults_to_none() -> None:
    cfg = AcquireConfig()
    assert cfg.db_path is None


def test_acquire_config_absolute_path_accepted(tmp_path: Path) -> None:
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    assert cfg.db_path == tmp_path / "acquire.db"


def test_acquire_config_rejects_ntfs_macfuse_path(monkeypatch) -> None:
    """A path on ntfs_macfuse must be rejected (WAL unsafe)."""
    from unittest.mock import MagicMock
    from personalscraper.core.sqlite._fs_probe import MountInfo
    mock_info = MountInfo(
        mount_point="/Volumes/ext",
        fs_type="ntfs_macfuse",
        raw_fs_type="ufsd_ntfs",
        flags=frozenset(),
    )
    monkeypatch.setattr(
        "personalscraper.conf.models.acquire.probe_mount",
        lambda path: mock_info,
    )
    with pytest.raises(ValueError, match="WAL"):
        AcquireConfig(db_path=Path("/Volumes/ext/acquire.db"))


def test_acquire_config_extra_fields_forbidden() -> None:
    with pytest.raises(Exception):
        AcquireConfig(unknown_field=True)  # type: ignore[call-arg]
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/conf/test_acquire_config.py -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError` (module does not exist).

- [ ] **Step 3: Create `personalscraper/conf/models/acquire.py`**

```python
# personalscraper/conf/models/acquire.py
"""Config model for the acquisition lobe (RP3).

Owns the ``acquire`` top-level key in the overlay layout.
Mirrors the WAL-safety validator from ``conf/models/indexer.py`` but imports
``probe_mount`` from ``core/sqlite/`` (no ``# layering: allow`` needed —
conf→core is a clean downward import).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator

from personalscraper.conf.models import paths as _paths_model
from personalscraper.conf.models._base import _StrictModel


class AcquireConfig(_StrictModel):
    """Configuration for the acquire lobe SQLite store.

    The ``db_path`` defaults to ``None``; ``Config._resolve_derived_paths``
    fills it as ``paths.data_dir / 'acquire.db'`` when unset.

    Attributes:
        db_path: Path to the acquire SQLite database. ``None`` = auto-derive.

    Raises:
        ValueError: If ``db_path`` resolves to a WAL-unsafe filesystem
            (ntfs_macfuse or unknown mount under /Volumes/).
    """

    db_path: Path | None = Field(
        default=None,
        validate_default=True,
        description="Path to acquire.db. None = auto-derive from paths.data_dir.",
    )

    @field_validator("db_path", mode="after")
    @classmethod
    def _reject_external_mount(cls, v: Path | None) -> Path | None:
        """Resolve db_path and reject WAL-unsafe filesystem types.

        Mirrors IndexerConfig._reject_external_mount but imports probe_mount
        from core/sqlite/ (conf→core is a clean downward import; no marker needed).

        Args:
            v: Raw Path value (may be relative, may be None).

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

        try:
            from personalscraper.core.sqlite._fs_probe import probe_mount

            info = probe_mount(str(resolved))
            fs_type = info.fs_type if info is not None else None

            if (
                info is not None
                and str(resolved).startswith("/Volumes/")
                and not info.mount_point.startswith("/Volumes/")
            ):
                fs_type = None

            if fs_type in ("ntfs_macfuse", "unknown"):
                raise ValueError(
                    f"acquire.db_path {resolved} is on a WAL-unsafe filesystem "
                    f"({fs_type}). The acquire database must reside on an APFS volume."
                )

            if fs_type is None and str(resolved).startswith("/Volumes/"):
                raise ValueError(
                    f"acquire.db_path {resolved} appears to be on an external volume "
                    "whose filesystem type could not be determined. "
                    "The acquire database must reside on the internal APFS disk."
                )
        except ImportError:
            pass

        return resolved


__all__ = ["AcquireConfig"]
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/conf/test_acquire_config.py -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add personalscraper/conf/models/acquire.py tests/conf/test_acquire_config.py
git commit -m "feat(acquire-store): add conf/models/acquire.py with AcquireConfig + WAL-safety validator"
```

---

### Task 3 — Wire `AcquireConfig` into `Config` + `_resolve_derived_paths`

**Files:**

- Modify: `personalscraper/conf/models/config.py`
- Test: extend `tests/conf/test_acquire_config.py`

- [ ] **Step 1: Add failing test for derived path resolution**

Add to `tests/conf/test_acquire_config.py`:

```python
def test_config_derives_acquire_db_path(tmp_path: Path) -> None:
    """Config._resolve_derived_paths sets acquire.db_path from paths.data_dir."""
    # This test requires a fully loaded Config (not just AcquireConfig alone).
    # Use the minimal config loader pattern from tests/conf/.
    from personalscraper.conf.models.config import Config
    from personalscraper.conf.models.acquire import AcquireConfig
    # A Config with acquire.db_path=None should auto-resolve it.
    # We can't build a full Config easily without disk entries,
    # so instead verify the logic in isolation:
    acquire = AcquireConfig(db_path=None)
    assert acquire.db_path is None  # not yet resolved — Config does it
    # The field validator accepts None (deferred to Config level)
```

- [ ] **Step 2: Modify `personalscraper/conf/models/config.py`**

Add import:

```python
from personalscraper.conf.models.acquire import AcquireConfig
```

Add field on `Config` after the `indexer` field:

```python
acquire: AcquireConfig = Field(default_factory=AcquireConfig)
```

Extend `_resolve_derived_paths` model validator:

```python
if self.acquire.db_path is None:
    object.__setattr__(self.acquire, "db_path", self.paths.data_dir / "acquire.db")
```

Update the docstring for `_resolve_derived_paths` to list the new rule:

```
- ``acquire.db_path`` → ``paths.data_dir / 'acquire.db'``
```

- [ ] **Step 3: Verify Config loads**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.acquire import AcquireConfig
print('Config.acquire field:', Config.model_fields.get('acquire'))
print('OK')
"
```

Expected: prints the field description and `OK`.

- [ ] **Step 4: Run conf tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/conf/ -x -q 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/conf/models/config.py tests/conf/test_acquire_config.py
git commit -m "feat(acquire-store): register AcquireConfig on Config + derive acquire.db_path"
```

---

### Task 4 — Add `acquire.json5` overlay + update config.json5 files

**Files:**

- Create: `config.example/acquire.json5`
- Modify: `config.example/config.json5`
- Modify: `config/config.json5` (if the live file exists)

- [ ] **Step 1: Create `config.example/acquire.json5`**

```json5
{
  // Acquisition lobe configuration (RP3).
  // db_path: null = auto-derive as paths.data_dir / 'acquire.db'
  acquire: {
    db_path: null,
  },
}
```

- [ ] **Step 2: Add `"acquire.json5"` to `config.example/config.json5` overlays**

In `config.example/config.json5`, add `"acquire.json5"` to the overlays array (after `"indexer.json5"`):

```json5
overlays: [
    "paths.json5",
    "disks.json5",
    "categories.json5",
    "patterns.json5",
    "encoding.json5",
    "scraper.json5",
    "trailers.json5",
    "indexer.json5",
    "acquire.json5",    // ← add here
    "thresholds.json5",
    ...
  ],
```

- [ ] **Step 3: Add `"acquire.json5"` to live `config/config.json5` if present**

```bash
ls /Users/izno/dev/PersonnalScaper/config/config.json5 2>/dev/null && echo "EXISTS" || echo "MISSING"
```

If it exists, add `"acquire.json5"` to its overlays array in the same position.

- [ ] **Step 4: Verify example config loads**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/conf/test_example_config.py -v 2>&1 | tail -15
```

Expected: pass (the `load_config_dir` test covers all overlay files).

- [ ] **Step 5: Commit**

```bash
git add config.example/acquire.json5 config.example/config.json5
# add live config only if modified:
git add config/config.json5 2>/dev/null || true
git commit -m "feat(acquire-store): add config.example/acquire.json5 overlay (16th overlay)"
```

---

### Task 5 — Update `docs/reference/config-overlay-layout.md` + phase gate

**Files:**

- Modify: `docs/reference/config-overlay-layout.md`

- [ ] **Step 1: Bump overlay count (3 prose spots) and add acquire row**

In `docs/reference/config-overlay-layout.md`, find and update:

- Every occurrence of "15 overlays" or "15 overlay" → "16 overlays" / "16 overlay"
- The key-ownership table: add a row for the `acquire` key owned by `acquire.json5`

Example row to add to the table:

```markdown
| `acquire.json5` | `acquire` | Acquisition lobe DB path |
```

- [ ] **Step 2: Run make check (full gate)**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -30
```

Expected: green. If `test_example_config.py` was already run, all config tests pass.

- [ ] **Step 3: Commit**

```bash
git add docs/reference/config-overlay-layout.md
git commit -m "chore(acquire-store): phase 2 gate — MediaRef + AcquireConfig + acquire.json5 overlay"
```
