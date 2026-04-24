# Phase 2 — Sorter Refactor + Settings Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch every consumer from `TYPE_DIR_MAP` / `Settings.*_dir_name` to config-driven lookup. Make `staging_dirs` required. Create `personalscraper/conf/staging.py` with helper functions.

**Architecture:** Six sub-phases executed in order. Each sub-phase is independently committable. `conf/staging.py` is the new single point of truth for staging path computation.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest

---

## Gate (entry)

Phase 1 must be complete:

- [ ] `tests/conf/test_models_staging.py` exists and passes
- [ ] `config.example.json5` contains `staging_dirs` with 8 entries
- [ ] `grep -n "TYPE_DIR_MAP" personalscraper/sorter/strategies.py` returns matches (still present)
- [ ] `make test` green

---

## Sub-phase 2.1 — Create `conf/staging.py` helpers + make `staging_dirs` required

**Files:**

- Create: `personalscraper/conf/staging.py`
- Modify: `personalscraper/conf/models.py` (tighten `staging_dirs` from Optional to required)

### Step 2.1.1 — Create `personalscraper/conf/staging.py`

- [ ] Create the file:

```python
"""Staging directory helper functions.

Provides pure functions for computing staging paths from StagingDirConfig
entries. No I/O — filesystem operations live in ensure_staging_tree (Phase 3).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.conf.models import Config, StagingDirConfig
    from personalscraper.sorter.file_type import FileType


def folder_name(entry: "StagingDirConfig") -> str:
    """Compute the on-disk folder name for a staging entry.

    Format: ``f"{entry.id:03d}-{entry.name.upper()}"``.
    E.g. ``{id: 1, name: "movies"}`` → ``"001-MOVIES"``.

    Args:
        entry: A StagingDirConfig entry from config.staging_dirs.

    Returns:
        The folder name string (e.g. "001-MOVIES").
    """
    return f"{entry.id:03d}-{entry.name.upper()}"


def staging_path(config: "Config", entry: "StagingDirConfig") -> Path:
    """Compute the absolute path for a staging subdirectory.

    Args:
        config: The loaded Config instance.
        entry: A StagingDirConfig entry from config.staging_dirs.

    Returns:
        Absolute Path to the staging subdirectory.
    """
    return config.paths.staging_dir / folder_name(entry)


def find_by_file_type(config: "Config", file_type: "FileType") -> "StagingDirConfig":
    """Find the staging entry matching a FileType.

    Args:
        config: The loaded Config instance.
        file_type: The FileType enum member to look up.

    Returns:
        The first StagingDirConfig whose file_type matches.

    Raises:
        KeyError: If no staging entry matches the given file_type.
    """
    for entry in config.staging_dirs:
        if entry.file_type == file_type.value:
            return entry
    raise KeyError(
        f"No staging_dirs entry found for file_type={file_type.value!r}. "
        "Check your config.json5 staging_dirs section."
    )


def find_ingest_dir(config: "Config") -> "StagingDirConfig":
    """Return the staging entry designated as the ingest directory.

    The Phase 1 validator guarantees exactly one entry has role='ingest'.

    Args:
        config: The loaded Config instance.

    Returns:
        The StagingDirConfig entry with role='ingest'.

    Raises:
        KeyError: If no entry has role='ingest' (should not happen post-validation).
    """
    for entry in config.staging_dirs:
        if entry.role == "ingest":
            return entry
    raise KeyError(
        "No staging_dirs entry with role='ingest' found. "
        "Config validation should have caught this — check config.json5."
    )
```

### Step 2.1.2 — Write unit tests for `conf/staging.py` helpers

- [ ] Create `tests/conf/test_staging_helpers.py`:

```python
"""Tests for personalscraper.conf.staging helper functions."""

import pytest

from personalscraper.conf.staging import find_by_file_type, find_ingest_dir, folder_name, staging_path
from personalscraper.conf.models import Config, StagingDirConfig
from personalscraper.sorter.file_type import FileType


def _make_config(staging_dirs: list[dict]) -> Config:
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": "/tmp/torrents",
                "staging_dir": "/tmp/staging",
                "data_dir": "/tmp/.data",
            },
            "disks": [{"id": "disk_a", "path": "/tmp/disk_a", "categories": ["movies"]}],
            "staging_dirs": staging_dirs,
        }
    )


_DEFAULT_DIRS = [
    {"id": 1, "name": "movies", "file_type": "movie"},
    {"id": 2, "name": "tvshows", "file_type": "tvshow"},
    {"id": 3, "name": "ebooks", "file_type": "ebook"},
    {"id": 4, "name": "audio", "file_type": "audio"},
    {"id": 5, "name": "apps", "file_type": "app"},
    {"id": 6, "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres", "file_type": "other"},
]


class TestFolderName:
    def test_standard_movie(self):
        entry = StagingDirConfig(id=1, name="movies", file_type="movie")
        assert folder_name(entry) == "001-MOVIES"

    def test_tvshows(self):
        entry = StagingDirConfig(id=2, name="tvshows", file_type="tvshow")
        assert folder_name(entry) == "002-TVSHOWS"

    def test_temp_ingest(self):
        entry = StagingDirConfig(id=97, name="temp", role="ingest")
        assert folder_name(entry) == "097-TEMP"

    def test_custom_id_10(self):
        entry = StagingDirConfig(id=10, name="mega", file_type="movie")
        assert folder_name(entry) == "010-MEGA"

    def test_kebab_name_uppercased(self):
        entry = StagingDirConfig(id=2, name="tv-shows", file_type="tvshow")
        assert folder_name(entry) == "002-TV-SHOWS"


class TestStagingPath:
    def test_path_combines_staging_dir_and_folder_name(self):
        config = _make_config(_DEFAULT_DIRS)
        entry = config.staging_dirs[0]  # movies
        path = staging_path(config, entry)
        assert path == config.paths.staging_dir / "001-MOVIES"


class TestFindByFileType:
    def test_finds_movie(self):
        config = _make_config(_DEFAULT_DIRS)
        entry = find_by_file_type(config, FileType.MOVIE)
        assert entry.name == "movies"

    def test_finds_tvshow(self):
        config = _make_config(_DEFAULT_DIRS)
        entry = find_by_file_type(config, FileType.TVSHOW)
        assert entry.name == "tvshows"

    def test_missing_type_raises_key_error(self):
        config = _make_config(
            [{"id": 97, "name": "temp", "file_type": None, "role": "ingest"}]
        )
        with pytest.raises(KeyError, match="movie"):
            find_by_file_type(config, FileType.MOVIE)


class TestFindIngestDir:
    def test_finds_ingest_entry(self):
        config = _make_config(_DEFAULT_DIRS)
        entry = find_ingest_dir(config)
        assert entry.role == "ingest"
        assert folder_name(entry) == "097-TEMP"
```

- [ ] Run to confirm FAIL (module not yet importable or function missing):

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/test_staging_helpers.py -v 2>&1 | head -20
```

- [ ] After creating `conf/staging.py`, run again:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/test_staging_helpers.py -v
```

Expected: all PASS.

### Step 2.1.3 — Tighten `staging_dirs` to required in `Config`

- [ ] In `personalscraper/conf/models.py`, find the `staging_dirs` field added in Phase 1:

```python
    staging_dirs: list[StagingDirConfig] | None = Field(
        default=None,
        ...
    )
```

Replace it with:

```python
    staging_dirs: list[StagingDirConfig] = Field(
        ...,
        description=(
            "Staging subdirectory layout. Required. "
            "See MANUAL.md §Staging layout for migration steps."
        ),
    )
```

- [ ] Add a friendly error via `model_validator` **before** `_validate_staging_dirs` in `Config`:

The `staging_dirs` field is now required — Pydantic will raise `ValidationError` with a "Field required" message by default. To add a friendlier message, add this validator:

```python
    @model_validator(mode="before")
    @classmethod
    def _check_staging_dirs_present(cls, data: dict) -> dict:
        """Emit a friendly error when staging_dirs is missing.

        Args:
            data: Raw config dict before field validation.

        Returns:
            data unchanged (validation continues normally).

        Raises:
            ValueError: With a human-readable migration hint if staging_dirs is absent.
        """
        if isinstance(data, dict) and "staging_dirs" not in data:
            raise ValueError(
                "`staging_dirs` missing from config.json5 — "
                "see MANUAL.md §Staging layout for migration steps."
            )
        return data
```

- [ ] Update `tests/conf/test_models_staging.py` — the test `test_config_without_staging_dirs_still_loads` now must FAIL (staging_dirs is required). Change it to assert the friendly error message:

```python
    def test_config_without_staging_dirs_raises_friendly_error(self):
        """staging_dirs is required in Phase 2 — missing key must emit friendly message."""
        cfg = _minimal_config_dict([])
        del cfg["staging_dirs"]
        with pytest.raises(ValidationError, match="MANUAL.md"):
            Config.model_validate(cfg)
```

- [ ] Run the full conf test suite:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/ -v
```

Expected: all PASS (including the renamed test).

### Step 2.1.4 — Commit sub-phase 2.1

- [ ] Stage:

```bash
git add personalscraper/conf/staging.py personalscraper/conf/models.py tests/conf/test_staging_helpers.py tests/conf/test_models_staging.py
```

- [ ] Commit:

```bash
git commit -m "refactor(ext-staging): create conf/staging.py helpers + make staging_dirs required"
```

---

## Sub-phase 2.2 — Remove `TYPE_DIR_MAP` and `get_type_dir_map()` from `sorter/strategies.py`

**Files:**

- Modify: `personalscraper/sorter/strategies.py`
- Modify: `tests/sorter/test_strategies.py`

### Step 2.2.1 — Refactor `strategies.py`

The strategies currently receive only `staging_dir: Path`. They will now also need `config: Config` to call `find_by_file_type`. Update the base class signature and all three strategy classes.

- [ ] Replace the top of `personalscraper/sorter/strategies.py`. Remove `TYPE_DIR_MAP` dict (lines 19–26) and `get_type_dir_map()` function (lines 29–61). Add the config import:

New imports block:

```python
"""Sorting strategies for placing media items into destination directories.

Each strategy determines the target subdirectory based on media type:
- MovieStrategy: {dirname}/Title (Year)/
- TVShowStrategy: {dirname}/Show Name/
- DefaultStrategy: type-specific directory ({dirname}/)

Strategies use fuzzy matching to find existing folders and prevent duplicates.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from personalscraper.conf.staging import find_by_file_type, folder_name, staging_path
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType
from personalscraper.sorter.matcher import find_matching_directory
```

- [ ] Update `SortingStrategy` abstract base class — add `config` parameter:

```python
class SortingStrategy(ABC):
    """Base class for sorting strategies.

    Each strategy computes a destination path for a media item based on
    its cleaned name and the staging directory structure.
    """

    @abstractmethod
    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config=None) -> Path:
        """Compute the destination path for a media item.

        Args:
            name: Raw filename or directory name of the item being sorted.
            staging_dir: Root staging directory (staging/).
            cleaner: NameCleaner for title/year extraction.
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            The destination Path where the item should be moved.
        """
```

- [ ] Update `MovieStrategy.get_destination`:

```python
    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config=None) -> Path:
        """Return {dirname}/Title (Year)/ or existing matching folder.

        Args:
            name: Raw movie filename or directory name.
            staging_dir: Root staging directory.
            cleaner: NameCleaner for title/year extraction.
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            Destination path inside the movies staging directory.
        """
        if config is not None:
            entry = find_by_file_type(config, FileType.MOVIE)
            movies_dir = staging_path(config, entry)
        else:
            movies_dir = staging_dir / "001-MOVIES"  # fallback for legacy call sites only
        folder = cleaner.clean_for_folder(name)

        if movies_dir.is_dir():
            candidates = [d for d in movies_dir.iterdir() if d.is_dir()]
            match = find_matching_directory(folder, candidates, respect_year=True)
            if match is not None:
                return match

        return movies_dir / folder
```

- [ ] Update `TVShowStrategy.get_destination`:

```python
    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config=None) -> Path:
        """Return {dirname}/Show Name/ or existing matching folder.

        Args:
            name: Raw TV show filename or directory name.
            staging_dir: Root staging directory.
            cleaner: NameCleaner for title extraction.
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            Destination path inside the TV shows staging directory.
        """
        if config is not None:
            entry = find_by_file_type(config, FileType.TVSHOW)
            tvshows_dir = staging_path(config, entry)
        else:
            tvshows_dir = staging_dir / "002-TVSHOWS"  # fallback for legacy call sites only

        cleaned = cleaner.clean(name)
        parts = cleaned.split()
        show_parts = []
        for part in parts:
            if part.upper().startswith("S") and len(part) >= 3 and part[1:].replace("E", "").isdigit():
                break
            show_parts.append(part)
        show_name = " ".join(show_parts) if show_parts else cleaned

        if tvshows_dir.is_dir():
            candidates = [d for d in tvshows_dir.iterdir() if d.is_dir()]
            match = find_matching_directory(show_name, candidates, respect_year=False)
            if match is not None:
                return match

        return tvshows_dir / show_name
```

- [ ] Update `DefaultStrategy.get_destination`:

```python
    def get_destination(self, name: str, staging_dir: Path, cleaner: NameCleaner, config=None) -> Path:
        """Return the type-specific directory path.

        Args:
            name: Raw filename or directory name (unused for default strategy).
            staging_dir: Root staging directory.
            cleaner: NameCleaner (unused for default strategy).
            config: Loaded Config instance for staging_dirs lookup.

        Returns:
            The type-specific directory path.
        """
        if config is not None:
            try:
                entry = find_by_file_type(config, self.file_type)
            except KeyError:
                entry = find_by_file_type(config, FileType.OTHER)
            return staging_path(config, entry)
        # Fallback hardcoded names — only reached before config is wired
        _fallback: dict[FileType, str] = {
            FileType.EBOOK: "003-EBOOKS",
            FileType.AUDIO: "004-AUDIO",
            FileType.APP: "005-APPS",
            FileType.OTHER: "098-AUTRES",
        }
        return staging_dir / _fallback.get(self.file_type, "098-AUTRES")
```

### Step 2.2.2 — Refactor `tests/sorter/test_strategies.py`

- [ ] Replace the test file content entirely. Tests now inject a Config fixture and use dynamic `folder_name()` assertions:

```python
"""Tests for personalscraper.sorter.strategies — sorting strategies."""

import pytest

from personalscraper.conf.models import Config, StagingDirConfig
from personalscraper.conf.staging import folder_name, find_by_file_type, staging_path
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.file_type import FileType
from personalscraper.sorter.strategies import DefaultStrategy, MovieStrategy, TVShowStrategy


_STAGING_DIRS = [
    {"id": 1, "name": "movies", "file_type": "movie"},
    {"id": 2, "name": "tvshows", "file_type": "tvshow"},
    {"id": 3, "name": "ebooks", "file_type": "ebook"},
    {"id": 4, "name": "audio", "file_type": "audio"},
    {"id": 5, "name": "apps", "file_type": "app"},
    {"id": 6, "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres", "file_type": "other"},
]


@pytest.fixture
def config(tmp_path) -> Config:
    """Provide a Config with staging_dirs pointing at tmp_path."""
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": _STAGING_DIRS,
        }
    )


@pytest.fixture
def cleaner() -> NameCleaner:
    return NameCleaner()


@pytest.fixture
def staging(config, tmp_path) -> "Path":
    """Create staging subdirs on disk matching config."""
    from personalscraper.conf.staging import folder_name
    staging_root = config.paths.staging_dir
    staging_root.mkdir(parents=True, exist_ok=True)
    for entry in config.staging_dirs:
        (staging_root / folder_name(entry)).mkdir(parents=True, exist_ok=True)
    return staging_root


class TestMovieStrategy:
    """MovieStrategy — places movies in {movies_dir}/Title (Year)/."""

    def test_new_movie_creates_folder(self, staging, cleaner, config):
        strategy = MovieStrategy()
        dest = strategy.get_destination("Movie.Title.2024.1080p.BluRay.x264-GROUP", staging, cleaner, config)
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        assert dest.parent == movies_dir
        assert "Movie Title" in dest.name
        assert "(2024)" in dest.name

    def test_new_movie_without_year(self, staging, cleaner, config):
        strategy = MovieStrategy()
        dest = strategy.get_destination("Some.Movie.1080p.BluRay", staging, cleaner, config)
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        assert dest.parent == movies_dir

    def test_existing_movie_fuzzy_match(self, staging, cleaner, config):
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        existing = movies_dir / "The Matrix (1999)"
        existing.mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("The.Matrix.1999.Remaster.1080p.BluRay", staging, cleaner, config)
        assert dest == existing

    def test_different_year_no_match(self, staging, cleaner, config):
        movies_dir = staging_path(config, find_by_file_type(config, FileType.MOVIE))
        existing = movies_dir / "The Matrix (1999)"
        existing.mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("The.Matrix.Reloaded.2003.1080p", staging, cleaner, config)
        assert dest != existing

    def test_custom_config_different_folder_name(self, tmp_path, cleaner):
        """Custom id=10,name='mega' → dir is 010-MEGA."""
        custom_dirs = [
            {"id": 10, "name": "mega", "file_type": "movie"},
            {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
        ]
        config = Config.model_validate(
            {
                "paths": {
                    "torrent_complete_dir": str(tmp_path / "torrents"),
                    "staging_dir": str(tmp_path / "staging"),
                    "data_dir": str(tmp_path / ".data"),
                },
                "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
                "staging_dirs": custom_dirs,
            }
        )
        staging_root = config.paths.staging_dir
        staging_root.mkdir(parents=True)
        (staging_root / "010-MEGA").mkdir()
        strategy = MovieStrategy()
        dest = strategy.get_destination("Inception.2010.1080p", staging_root, cleaner, config)
        assert dest.parent == staging_root / "010-MEGA"


class TestTVShowStrategy:
    """TVShowStrategy — places TV shows in {tvshows_dir}/Show Name/."""

    def test_new_show_creates_folder(self, staging, cleaner, config):
        strategy = TVShowStrategy()
        dest = strategy.get_destination("Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX", staging, cleaner, config)
        tvshows_dir = staging_path(config, find_by_file_type(config, FileType.TVSHOW))
        assert dest.parent == tvshows_dir
        assert "Shrinking" in dest.name

    def test_show_folder_has_no_year(self, staging, cleaner, config):
        strategy = TVShowStrategy()
        dest = strategy.get_destination("The.Boys.S05E01.MULTi.1080p", staging, cleaner, config)
        assert "(" not in dest.name or "S05" in dest.name

    def test_existing_show_fuzzy_match(self, staging, cleaner, config):
        tvshows_dir = staging_path(config, find_by_file_type(config, FileType.TVSHOW))
        existing = tvshows_dir / "Shrinking"
        existing.mkdir()
        strategy = TVShowStrategy()
        dest = strategy.get_destination("Shrinking.S03.MULTi.1080p.WEBRiP-R3MiX", staging, cleaner, config)
        assert dest == existing

    def test_episode_file_matches_show_folder(self, staging, cleaner, config):
        tvshows_dir = staging_path(config, find_by_file_type(config, FileType.TVSHOW))
        existing = tvshows_dir / "The Boys"
        existing.mkdir()
        strategy = TVShowStrategy()
        dest = strategy.get_destination("The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP-R3MiX", staging, cleaner, config)
        assert dest == existing


class TestDefaultStrategy:
    """DefaultStrategy — places items in type-specific directories."""

    @pytest.mark.parametrize(
        "file_type,expected_name",
        [
            (FileType.EBOOK, "003-EBOOKS"),
            (FileType.AUDIO, "004-AUDIO"),
            (FileType.APP, "005-APPS"),
            (FileType.OTHER, "098-AUTRES"),
        ],
    )
    def test_type_directory_mapping(self, staging, cleaner, config, file_type, expected_name):
        strategy = DefaultStrategy(file_type)
        dest = strategy.get_destination("file.ext", staging, cleaner, config)
        assert dest == config.paths.staging_dir / expected_name
```

### Step 2.2.3 — Run sorter tests

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/sorter/ -v
```

Expected: all PASS.

### Step 2.2.4 — Verify `TYPE_DIR_MAP` removed

- [ ] Run:

```bash
grep -n "TYPE_DIR_MAP\|get_type_dir_map" "/Volumes/IznoServer SSD/A TRIER/personalscraper/sorter/strategies.py"
```

Expected: 0 matches.

### Step 2.2.5 — Commit sub-phase 2.2

- [ ] Stage:

```bash
git add personalscraper/sorter/strategies.py tests/sorter/test_strategies.py
```

- [ ] Commit:

```bash
git commit -m "refactor(ext-staging): remove TYPE_DIR_MAP and get_type_dir_map from strategies.py"
```

---

## Sub-phase 2.3 — Remove 7 `*_dir_name` fields from `config.py` Settings

**Files:**

- Modify: `personalscraper/config.py`

### Step 2.3.1 — Remove the 7 fields and their docstring lines

- [ ] Open `personalscraper/config.py`. Remove the following from the `Settings` class:
  1. Docstring lines for `ingest_dir_name`, `movies_dir_name`, `tvshows_dir_name`, `ebooks_dir_name`, `audio_dir_name`, `apps_dir_name`, `other_dir_name` (lines 43–49 in the current docstring).
  2. The field definitions:
     - `ingest_dir_name: str = "097-TEMP"`
     - `movies_dir_name: str = "001-MOVIES"`
     - `tvshows_dir_name: str = "002-TVSHOWS"`
     - `ebooks_dir_name: str = "003-EBOOKS"`
     - `audio_dir_name: str = "004-AUDIO"`
     - `apps_dir_name: str = "005-APPS"`
     - `other_dir_name: str = "098-AUTRES"`
  3. The `ingest_dir()` method that depended on `ingest_dir_name` (it will be replaced by `find_ingest_dir` from `conf/staging.py`).

- [ ] Also update the class docstring `Note:` line to remove the reference to `*_dir_name` fields.

### Step 2.3.2 — Update call sites that used `settings.ingest_dir()`

- [ ] Run:

```bash
grep -rn "ingest_dir\|ingest_dir_name\|movies_dir_name\|tvshows_dir_name\|ebooks_dir_name\|audio_dir_name\|apps_dir_name\|other_dir_name" "/Volumes/IznoServer SSD/A TRIER/personalscraper/" --include="*.py"
```

For each match: replace `settings.ingest_dir(config.paths.staging_dir)` with `staging_path(config, find_ingest_dir(config))` (importing from `personalscraper.conf.staging`).

### Step 2.3.3 — Verify removal

- [ ] Run:

```bash
grep -n "_dir_name" "/Volumes/IznoServer SSD/A TRIER/personalscraper/config.py"
```

Expected: 0 matches.

### Step 2.3.4 — Run tests

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && make test
```

Expected: PASS.

### Step 2.3.5 — Commit sub-phase 2.3

```bash
git add personalscraper/config.py
git commit -m "refactor(ext-staging): remove 7 *_dir_name Settings fields"
```

---

## Sub-phase 2.4 — Sweep remaining 18 files for hardcoded staging literals

**Files to sweep** (excluding `strategies.py` done in 2.2 and `config.py` done in 2.3):

```
personalscraper/cli.py
personalscraper/conf/migration.py
personalscraper/conf/models.py
personalscraper/dispatch/run.py
personalscraper/enforce/coherence_checker.py
personalscraper/enforce/file_sanitizer.py
personalscraper/enforce/structure_validator.py
personalscraper/info/run.py
personalscraper/lock.py
personalscraper/pipeline.py
personalscraper/process/cleanup.py
personalscraper/process/dedup.py
personalscraper/process/reclean.py
personalscraper/process/run.py
personalscraper/sorter/__init__.py
personalscraper/sorter/run.py
personalscraper/sorter/sorter.py
personalscraper/sorter/file_type.py
```

### Step 2.4.1 — Find all remaining literals

- [ ] Run:

```bash
grep -rn "001-MOVIES\|002-TVSHOWS\|003-EBOOKS\|004-AUDIO\|005-APPS\|006-ANDROID\|097-TEMP\|098-AUTRES" \
  "/Volumes/IznoServer SSD/A TRIER/personalscraper/" --include="*.py"
```

Record each file and line. For each occurrence:

- If it is a **string comparison or path construction** → replace with a call to `folder_name(find_by_file_type(config, FileType.X))` or `folder_name(find_ingest_dir(config))`, adding `config` as a parameter if the function doesn't already have it.
- If it is a **docstring example** → rewrite to placeholder form like `{dirname}/Title (Year)/` so the grep returns 0 matches.
- If it is a **comment** → rewrite to not embed the literal.

### Step 2.4.2 — Verify 0 matches remain

- [ ] Run:

```bash
grep -rn "\"0[0-9]\{2\}-" "/Volumes/IznoServer SSD/A TRIER/personalscraper/" --include="*.py"
```

Expected: 0 matches. If any remain, fix them before proceeding.

### Step 2.4.3 — Run full test suite

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && make test
```

Expected: PASS.

### Step 2.4.4 — Commit sub-phase 2.4

```bash
git add personalscraper/
git commit -m "refactor(ext-staging): replace all staging path literals with config lookup"
```

---

## Sub-phase 2.5 — Update `commands/init_config.py` `--from-current` to emit `staging_dirs`

**Files:**

- Modify: `personalscraper/commands/init_config.py`

### Step 2.5.1 — Understand current `--from-current` flow

- [ ] Read `personalscraper/conf/migration.py` function `generate_config_from_env()` to understand how env vars are currently consumed.

### Step 2.5.2 — Add `staging_dirs` emission

The `--from-current` mode reads the user's `.env`. The 7 `*_dir_name` env vars are now removed from `Settings`, but the user may still have them in their `.env`. `init_config.py` should read them directly (raw dict lookup) and convert to `staging_dirs` entries.

- [ ] In `personalscraper/commands/init_config.py`, add a helper:

```python
def _build_staging_dirs_from_env(env: dict[str, str]) -> list[dict]:
    """Convert legacy *_dir_name env vars to staging_dirs entries.

    Reads the raw .env dict (not Settings) to extract the 7 old dir name
    overrides. Missing keys fall back to the canonical defaults.

    Args:
        env: Dict of env var names → values from the user's .env file.

    Returns:
        List of staging_dirs dicts ready for injection into config.json5.
    """
    def _get(key: str, default: str) -> str:
        return env.get(key, default)

    # Build entries matching the canonical convention
    return [
        {"id": 1,  "name": _folder_to_name(_get("MOVIES_DIR_NAME",  "001-MOVIES")),  "file_type": "movie"},
        {"id": 2,  "name": _folder_to_name(_get("TVSHOWS_DIR_NAME", "002-TVSHOWS")), "file_type": "tvshow"},
        {"id": 3,  "name": _folder_to_name(_get("EBOOKS_DIR_NAME",  "003-EBOOKS")),  "file_type": "ebook"},
        {"id": 4,  "name": _folder_to_name(_get("AUDIO_DIR_NAME",   "004-AUDIO")),   "file_type": "audio"},
        {"id": 5,  "name": _folder_to_name(_get("APPS_DIR_NAME",    "005-APPS")),    "file_type": "app"},
        {"id": 6,  "name": "android",                                                 "file_type": "app"},
        {"id": 97, "name": _folder_to_name(_get("INGEST_DIR_NAME",  "097-TEMP")),    "file_type": None, "role": "ingest"},
        {"id": 98, "name": _folder_to_name(_get("OTHER_DIR_NAME",   "098-AUTRES")),  "file_type": "other"},
    ]


def _folder_to_name(folder: str) -> str:
    """Extract kebab-case name from a folder like '001-MOVIES' → 'movies'.

    Args:
        folder: Folder name string in NNN-NAME format.

    Returns:
        Lowercase kebab-case name portion (e.g. 'movies', 'tv-shows').
    """
    # Strip NNN- prefix, lowercase
    parts = folder.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1].lower()
    return folder.lower()
```

- [ ] Call `_build_staging_dirs_from_env(env)` in the `--from-current` code path and inject the result into the generated config dict under the key `staging_dirs`.

### Step 2.5.3 — Test `--from-current` emits `staging_dirs`

- [ ] Run the existing `init_config` tests:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/ -k "init_config" -v
```

Expected: PASS.

- [ ] If there is no test for `--from-current` emitting `staging_dirs`, add one to the existing test file for `init_config`:

```python
def test_from_current_emits_staging_dirs(tmp_path, monkeypatch):
    """--from-current must emit a staging_dirs section."""
    env_file = tmp_path / ".env"
    env_file.write_text("STAGING_DIR=/tmp/staging\nTORRENT_COMPLETE_DIR=/tmp/torrents\n")
    # ... invoke init_config with --from-current --yes pointing at env_file
    # ... load the generated config.json5
    # assert "staging_dirs" in generated config
    # assert len(generated["staging_dirs"]) == 8
```

(Fill in the invocation pattern matching the existing `init_config` test style.)

### Step 2.5.4 — Commit sub-phase 2.5

```bash
git add personalscraper/commands/init_config.py
git commit -m "refactor(ext-staging): update init_config --from-current to emit staging_dirs"
```

---

## Sub-phase 2.6 — Refactor sorter tests + other impacted tests

**Files:**

- Modify: `tests/sorter/test_sorter.py`, `tests/sorter/test_run.py`, `tests/sorter/test_e2e.py` (if any reference hardcoded staging names)
- Modify: any other test file referencing `"001-MOVIES"` etc.

### Step 2.6.1 — Find all test files with hardcoded staging literals

- [ ] Run:

```bash
grep -rn "001-MOVIES\|002-TVSHOWS\|003-EBOOKS\|004-AUDIO\|005-APPS\|097-TEMP\|098-AUTRES" \
  "/Volumes/IznoServer SSD/A TRIER/tests/" --include="*.py"
```

For each match in tests: replace literal strings with `folder_name(entry)` using a test config fixture (same pattern as `test_strategies.py` refactor in 2.2).

### Step 2.6.2 — Run full test suite

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && make lint && make test
```

Expected: all PASS.

### Step 2.6.3 — Full phase 2 exit gate verification

- [ ] Run:

```bash
grep -rn "TYPE_DIR_MAP\|get_type_dir_map" "/Volumes/IznoServer SSD/A TRIER/personalscraper/" --include="*.py"
```

Expected: **0 matches**.

- [ ] Run:

```bash
grep -n "_dir_name" "/Volumes/IznoServer SSD/A TRIER/personalscraper/config.py"
```

Expected: **0 matches**.

- [ ] Run:

```bash
grep -rn "\"0[0-9]\{2\}-" "/Volumes/IznoServer SSD/A TRIER/personalscraper/" --include="*.py"
```

Expected: **0 matches**.

- [ ] Check `data_dir` unchanged:

```bash
grep "data_dir" "/Volumes/IznoServer SSD/A TRIER/config.example.json5"
```

Expected: contains `/Volumes/IznoServer SSD/A TRIER/.data`.

### Step 2.6.4 — Commit sub-phase 2.6

```bash
git add tests/
git commit -m "refactor(ext-staging): refactor sorter + impacted tests to inject config"
```

---

## Phase 2 milestone commit

- [ ] Stage everything not yet committed:

```bash
git status
```

- [ ] Create the milestone commit (only if there are uncommitted changes remaining):

```bash
git commit -m "refactor(ext-staging): replace TYPE_DIR_MAP and Settings *_dir_name with config-driven lookup"
```

---

## Exit gate

- [ ] `grep -rn "TYPE_DIR_MAP\|get_type_dir_map" personalscraper/ --include="*.py" -r` → 0 matches
- [ ] `grep -n "_dir_name" personalscraper/config.py` → 0 matches
- [ ] `grep -rn "\"0[0-9]\{2\}-" personalscraper/ --include="*.py"` → 0 matches
- [ ] `make lint && make test` green
- [ ] `grep "data_dir" config.example.json5` contains `/Volumes/IznoServer SSD/A TRIER/.data`
