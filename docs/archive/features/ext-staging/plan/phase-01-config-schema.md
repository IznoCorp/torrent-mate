# Phase 1 — Config Schema (Additive)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `StagingDirConfig` Pydantic model and add an optional `staging_dirs` field to `Config`. Existing `config.json5` files (without `staging_dirs`) continue to load. No consumer changes yet.

**Architecture:** Pure additive change to `personalscraper/conf/models.py` + `config.example.json5`. Keeps `TYPE_DIR_MAP` and `*_dir_name` Settings fields untouched — Phase 2 removes them.

**Tech Stack:** Pydantic v2, Python 3.11+, json5, pytest

---

## Gate (entry)

No prior phase. Starting state assertions:

- [ ] `grep -n "TYPE_DIR_MAP" personalscraper/sorter/strategies.py` returns matches (it must still exist — this phase does NOT remove it)
- [ ] `make test` is currently green on `main` / branch base

---

## Task 1: Add `StagingDirConfig` model to `personalscraper/conf/models.py`

**Files:**

- Modify: `personalscraper/conf/models.py` (add model before `Config` class)
- Test: `tests/conf/test_models_staging.py` (create)

### Step 1.1 — Write the failing tests first

- [ ] Create `tests/conf/test_models_staging.py`:

```python
"""Tests for StagingDirConfig model validation."""

import pytest
from pydantic import ValidationError

from personalscraper.conf.models import Config, StagingDirConfig


# ---------------------------------------------------------------------------
# StagingDirConfig unit tests
# ---------------------------------------------------------------------------


def _make_entry(**kwargs) -> dict:
    """Return a minimal valid StagingDirConfig dict, overridable via kwargs."""
    base = {"id": 1, "name": "movies", "file_type": "movie"}
    base.update(kwargs)
    return base


class TestStagingDirConfigValid:
    """Valid configurations must parse without error."""

    def test_minimal_entry(self):
        entry = StagingDirConfig(**_make_entry())
        assert entry.id == 1
        assert entry.name == "movies"
        assert entry.file_type == "movie"
        assert entry.role is None

    def test_with_role_ingest(self):
        entry = StagingDirConfig(**_make_entry(id=97, name="temp", file_type=None, role="ingest"))
        assert entry.role == "ingest"

    def test_name_kebab_case(self):
        entry = StagingDirConfig(**_make_entry(name="tv-shows"))
        assert entry.name == "tv-shows"

    def test_id_boundary_zero(self):
        StagingDirConfig(**_make_entry(id=0))

    def test_id_boundary_999(self):
        StagingDirConfig(**_make_entry(id=999))

    def test_no_file_type(self):
        """file_type is optional."""
        entry = StagingDirConfig(**_make_entry(file_type=None))
        assert entry.file_type is None


class TestStagingDirConfigInvalid:
    """Invalid configurations must raise ValidationError."""

    def test_id_below_zero(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            StagingDirConfig(**_make_entry(id=-1))

    def test_id_above_999(self):
        with pytest.raises(ValidationError, match="less than or equal to 999"):
            StagingDirConfig(**_make_entry(id=1000))

    def test_name_uppercase(self):
        with pytest.raises(ValidationError):
            StagingDirConfig(**_make_entry(name="MOVIES"))

    def test_name_with_underscore(self):
        with pytest.raises(ValidationError):
            StagingDirConfig(**_make_entry(name="tv_shows"))

    def test_name_with_special_char(self):
        with pytest.raises(ValidationError):
            StagingDirConfig(**_make_entry(name="tv shows"))

    def test_invalid_file_type(self):
        with pytest.raises(ValidationError, match="file_type"):
            StagingDirConfig(**_make_entry(file_type="bogus"))


# ---------------------------------------------------------------------------
# Config-level validators (require a full Config — use a minimal fixture)
# ---------------------------------------------------------------------------


def _minimal_config_dict(staging_dirs: list[dict]) -> dict:
    """Build a minimal Config dict with the given staging_dirs."""
    return {
        "paths": {
            "torrent_complete_dir": "/tmp/torrents",
            "staging_dir": "/tmp/staging",
            "data_dir": "/tmp/.data",
        },
        "disks": [{"id": "disk_a", "path": "/tmp/disk_a", "categories": ["movies"]}],
        "staging_dirs": staging_dirs,
    }


class TestConfigStagingDirsValidators:
    """Root-level Config validators for staging_dirs."""

    def test_valid_staging_dirs(self):
        Config.model_validate(
            _minimal_config_dict(
                [
                    {"id": 1, "name": "movies", "file_type": "movie"},
                    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
                ]
            )
        )

    def test_duplicate_id_fails(self):
        with pytest.raises(ValidationError, match="[Dd]uplicate"):
            Config.model_validate(
                _minimal_config_dict(
                    [
                        {"id": 1, "name": "movies", "file_type": "movie"},
                        {"id": 1, "name": "tvshows", "file_type": "tvshow"},
                    ]
                )
            )

    def test_zero_ingest_role_fails(self):
        with pytest.raises(ValidationError, match="[Ii]ngest"):
            Config.model_validate(
                _minimal_config_dict(
                    [
                        {"id": 1, "name": "movies", "file_type": "movie"},
                    ]
                )
            )

    def test_two_ingest_roles_fail(self):
        with pytest.raises(ValidationError, match="[Ii]ngest"):
            Config.model_validate(
                _minimal_config_dict(
                    [
                        {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
                        {"id": 98, "name": "autres", "file_type": None, "role": "ingest"},
                    ]
                )
            )

    def test_config_without_staging_dirs_still_loads(self):
        """staging_dirs is Optional in Phase 1 — missing key must not raise."""
        cfg = _minimal_config_dict([])
        del cfg["staging_dirs"]
        Config.model_validate(cfg)
```

- [ ] Run tests to confirm they all FAIL (module `StagingDirConfig` not yet imported):

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/test_models_staging.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — `StagingDirConfig` does not exist yet.

### Step 1.2 — Add `StagingDirConfig` to `personalscraper/conf/models.py`

- [ ] Open `personalscraper/conf/models.py`. Locate the `PathConfig` class (around line 212). **Insert the following block immediately before `PathConfig`**:

```python
class StagingDirConfig(_StrictModel):
    """Configuration for one staging subdirectory.

    Folder name on disk is derived as ``f"{id:03d}-{name.upper()}"``,
    e.g. ``{"id": 1, "name": "movies"}`` → ``"001-MOVIES"``.

    Attributes:
        id: Numeric directory prefix in [0, 999]. Must be unique across all entries.
        name: Kebab-case label (e.g. "movies", "tv-shows"). Used to build the folder name.
        file_type: Optional FileType enum value string this dir receives
            (e.g. "movie", "tvshow"). Duplicate values across entries are allowed —
            multiple dirs may share a FileType for domain-specific routing.
        role: Optional functional role. Currently only ``"ingest"`` is defined.
            Exactly one entry must declare ``role="ingest"`` when staging_dirs is present.
    """

    id: int = Field(..., ge=0, le=999, description="Numeric prefix [0-999]. Unique across entries.")
    name: str = Field(
        ...,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
        description="Kebab-case label. Used to compute folder name via f'{id:03d}-{name.upper()}'.",
    )
    file_type: str | None = Field(
        default=None,
        description="FileType enum member string this dir receives (e.g. 'movie', 'tvshow').",
    )
    role: str | None = Field(
        default=None,
        description="Functional role. Only 'ingest' defined. Exactly one entry must have this when staging_dirs present.",
    )

    @field_validator("file_type", mode="after")
    @classmethod
    def _validate_file_type(cls, v: str | None) -> str | None:
        """Validate file_type is a known FileType member.

        Args:
            v: The file_type string value, or None.

        Returns:
            The validated file_type string, or None.

        Raises:
            ValueError: If v is set but not a valid FileType member.
        """
        if v is None:
            return v
        from personalscraper.sorter.file_type import FileType  # local import avoids circular

        valid = {ft.value for ft in FileType}
        if v not in valid:
            raise ValueError(f"Invalid file_type '{v}'. Must be one of: {sorted(valid)}")
        return v
```

- [ ] Locate the `Config` class in `personalscraper/conf/models.py` and add `staging_dirs` as an **optional** field (do NOT make it required — that is Phase 2). Add it after the `library` field and before `all_category_ids`:

```python
    staging_dirs: list[StagingDirConfig] | None = Field(
        default=None,
        description=(
            "Staging subdirectory layout. Required from Phase 2 onward. "
            "See MANUAL.md §Staging layout for migration steps."
        ),
    )
```

- [ ] Add root-level validators on `Config` for `staging_dirs`. These validators only fire when `staging_dirs` is not None. Add them as a new `model_validator` after the existing `_validate_cross_references` validator:

```python
    @model_validator(mode="after")
    def _validate_staging_dirs(self) -> "Config":
        """Validate staging_dirs entries when present.

        Checks: unique IDs, exactly one role='ingest' entry, all file_type
        values reference valid FileType members (already checked at field level,
        but cross-entry uniqueness of IDs is checked here).

        Returns:
            self after validation.

        Raises:
            ValueError: If IDs are duplicated or ingest role count != 1.
        """
        if self.staging_dirs is None:
            return self

        # Unique IDs
        seen_ids: set[int] = set()
        for entry in self.staging_dirs:
            if entry.id in seen_ids:
                raise ValueError(
                    f"Duplicate staging_dirs id={entry.id}. Each entry must have a unique id."
                )
            seen_ids.add(entry.id)

        # Exactly one ingest role
        ingest_entries = [e for e in self.staging_dirs if e.role == "ingest"]
        if len(ingest_entries) != 1:
            raise ValueError(
                f"staging_dirs must have exactly one entry with role='ingest' "
                f"(found {len(ingest_entries)}). "
                "One entry (typically 097-TEMP) must declare role='ingest'."
            )

        return self
```

### Step 1.3 — Run the tests and verify they pass

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/test_models_staging.py -v
```

Expected: all tests PASS.

- [ ] If `test_config_without_staging_dirs_still_loads` fails, verify `staging_dirs` field default is `None` (not a required field).

---

## Task 2: Update `config.example.json5`

**Files:**

- Modify: `config.example.json5`

### Step 2.1 — Update `staging_dir` default and add `staging_dirs` section

- [ ] Open `config.example.json5`. Find the `paths` section. Change `staging_dir` to use a **portable relative path**:

```json5
paths: {
  torrent_complete_dir: "/path/to/qbittorrent/complete",
  staging_dir: "./staging/",   // portable relative default for CI and fresh clones
  data_dir: "/Volumes/IznoServer SSD/A TRIER/.data",
},
```

**IMPORTANT**: `data_dir` value must remain `/Volumes/IznoServer SSD/A TRIER/.data` — do NOT change it.

- [ ] Add the `staging_dirs` section **at the top level** of `config.example.json5` (after `paths`, before or after `disks` — consistency with other top-level keys):

```json5
staging_dirs: [
  {id: 1,  name: "movies",   file_type: "movie"},
  {id: 2,  name: "tvshows",  file_type: "tvshow"},
  {id: 3,  name: "ebooks",   file_type: "ebook"},
  {id: 4,  name: "audio",    file_type: "audio"},
  {id: 5,  name: "apps",     file_type: "app"},
  {id: 6,  name: "android",  file_type: "app"},
  {id: 97, name: "temp",     file_type: null,     role: "ingest"},
  {id: 98, name: "autres",   file_type: "other"},
],
```

### Step 2.2 — Verify the example config still loads

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/test_example_config.py -v
```

Expected: PASS (the example config loader test validates the example file).

### Step 2.3 — Assert `data_dir` is unchanged

- [ ] Run:

```bash
grep "data_dir" "/Volumes/IznoServer SSD/A TRIER/config.example.json5"
```

Expected output must contain `/Volumes/IznoServer SSD/A TRIER/.data`. If it does not, revert the `data_dir` line.

---

## Task 3: Full test suite gate

### Step 3.1 — Run full suite

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && make test
```

Expected: all tests PASS.

### Step 3.2 — Assert `TYPE_DIR_MAP` still present (Phase 1 must NOT remove it)

- [ ] Run:

```bash
grep -n "TYPE_DIR_MAP" "/Volumes/IznoServer SSD/A TRIER/personalscraper/sorter/strategies.py"
```

Expected: at least one match (line 19 defines the dict). If 0 matches, something went wrong — do not proceed.

---

## Task 4: Commit

- [ ] Stage files:

```bash
git add personalscraper/conf/models.py config.example.json5 tests/conf/test_models_staging.py
```

- [ ] Commit:

```bash
git commit -m "feat(ext-staging): add StagingDirConfig schema"
```

---

## Exit gate

Before marking this phase complete, verify all of the following:

- [ ] `make test` green
- [ ] `grep -n "TYPE_DIR_MAP" personalscraper/sorter/strategies.py` returns the existing occurrences (Phase 1 does **not** remove them)
- [ ] `grep "data_dir" config.example.json5` contains `/Volumes/IznoServer SSD/A TRIER/.data` (unchanged)
- [ ] `tests/conf/test_models_staging.py` exists and all tests pass
- [ ] `config.example.json5` contains a `staging_dirs` section with 8 entries
