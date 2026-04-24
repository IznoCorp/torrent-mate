# Phase 5 — Docs + E2E + Final Gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update all user-facing documentation to reflect external staging, add a full E2E test validating the auto-create feature end-to-end, and verify the complete feature gate.

**Architecture:** Docs-heavy phase. Six sub-tasks: MANUAL, CONFIGURATION, INSTALLATION, README, CLAUDE.md, E2E test. All run under the same commit scope `ext-staging`.

**Tech Stack:** Markdown, Python 3.11+, pytest, typer test runner

---

## Gate (entry)

Phase 4 must be complete:

- [ ] `git ls-files | grep -E "^[0-9]{3}-"` → 0 lines
- [ ] Physical `099-SCRIPTS/` count unchanged vs preamble
- [ ] `make lint && make test` green

---

## Task 1: Update `MANUAL.md`

**Files:**

- Modify: `MANUAL.md`

### Step 1.1 — Add "Staging layout" section

- [ ] Open `MANUAL.md`. Add a new section titled `## Staging layout` (before or after the existing pipeline steps section — keep logical flow). The section must include:

**Sub-section: Overview**

```markdown
## Staging layout

PersonalScraper uses a staging area where downloaded media lands before
being processed and dispatched to permanent storage. From version 0.4.0,
the staging tree lives **outside the repository** at the path configured
in `config.json5` under `paths.staging_dir`.

The subdirectory names are defined by `staging_dirs` in `config.json5`.
Each entry has an `id` (numeric prefix, 0–999) and a `name` (kebab-case).
The on-disk folder name is `{id:03d}-{name.upper()}`, e.g.:

| id  | name    | folder name |
| --- | ------- | ----------- |
| 1   | movies  | 001-MOVIES  |
| 2   | tvshows | 002-TVSHOWS |
| 97  | temp    | 097-TEMP    |
```

**Sub-section: Migration steps (upgrading from ≤ 0.3.0)**

````markdown
### Migrating from ≤ 0.3.0

After upgrading, your `config.json5` must be updated to include
`staging_dirs`. Without it, PersonalScraper will exit with:

> `staging_dirs` missing from config.json5 — see MANUAL.md §Staging layout for migration steps.

**Step 1**: Add `staging_dirs` to your `config.json5`. Copy the section
from `config.example.json5` and adjust if you have custom directory names.

**Step 2**: Set `paths.staging_dir` to the external location. Default
used in production: `/Volumes/IznoServer SSD/staging/`.

**Step 3**: Move your existing staging content to the new location. One
command per directory:

```bash
rsync -a "/Volumes/IznoServer SSD/A TRIER/001-MOVIES/" \
         "/Volumes/IznoServer SSD/staging/001-MOVIES/"
rsync -a "/Volumes/IznoServer SSD/A TRIER/002-TVSHOWS/" \
         "/Volumes/IznoServer SSD/staging/002-TVSHOWS/"
rsync -a "/Volumes/IznoServer SSD/A TRIER/003-EBOOKS/" \
         "/Volumes/IznoServer SSD/staging/003-EBOOKS/"
rsync -a "/Volumes/IznoServer SSD/A TRIER/004-AUDIO/" \
         "/Volumes/IznoServer SSD/staging/004-AUDIO/"
rsync -a "/Volumes/IznoServer SSD/A TRIER/005-APPS/" \
         "/Volumes/IznoServer SSD/staging/005-APPS/"
rsync -a "/Volumes/IznoServer SSD/A TRIER/006-ANDROID/" \
         "/Volumes/IznoServer SSD/staging/006-ANDROID/"
rsync -a "/Volumes/IznoServer SSD/A TRIER/097-TEMP/" \
         "/Volumes/IznoServer SSD/staging/097-TEMP/"
rsync -a "/Volumes/IznoServer SSD/A TRIER/098-AUTRES/" \
         "/Volumes/IznoServer SSD/staging/098-AUTRES/"
```
````

After rsync completes, verify the transfer, then delete the originals from
the repository directory if desired.

**Note on `099-SCRIPTS/`**: This directory has been removed from git
tracking but its files remain on disk at their original location. The user
is responsible for moving or archiving these files separately.

````

---

## Task 2: Update `CONFIGURATION.md`

**Files:**

- Modify: `CONFIGURATION.md`

### Step 2.1 — Document `paths.staging_dir` new default

- [ ] Find the section documenting `paths.staging_dir` in `CONFIGURATION.md`. Update the description:

```markdown
### `paths.staging_dir`

Path to the root staging directory where media lands for processing.

- **Example (config.example.json5):** `./staging/` (relative, portable — resolves to `<repo>/staging/` on CI)
- **Production default:** `/Volumes/IznoServer SSD/staging/`
- Relative paths are resolved to absolute at load time via `Path.expanduser().resolve()`.
- The staging tree is auto-created on first run — no manual `mkdir` required.
````

### Step 2.2 — Document `paths.data_dir` (explicit)

- [ ] Add or update the `paths.data_dir` entry:

```markdown
### `paths.data_dir`

Path to the pipeline state directory (index, locks, analysis cache).

- **Default:** `/Volumes/IznoServer SSD/A TRIER/.data`
- This value is **explicit** in `config.json5` — it can be relocated with a
  single config edit. The physical directory has not moved.
- Not the same as `staging_dir`.
```

### Step 2.3 — Document `staging_dirs` section

- [ ] Add a new section for the `staging_dirs` configuration:

````markdown
## `staging_dirs`

**Required** (since 0.4.0). Defines the subdirectory layout of the staging area.

Each entry:

| Field       | Type         | Required | Description                                                                           |
| ----------- | ------------ | -------- | ------------------------------------------------------------------------------------- |
| `id`        | int [0–999]  | yes      | Numeric prefix. Used to compute folder name: `f"{id:03d}-{name.upper()}"`.            |
| `name`      | string       | yes      | Kebab-case label (e.g. `"movies"`, `"tv-shows"`). Lowercased + upper for folder.      |
| `file_type` | string\|null | no       | FileType enum value: `"movie"`, `"tvshow"`, `"ebook"`, `"audio"`, `"app"`, `"other"`. |
| `role`      | string\|null | no       | Functional role. Only `"ingest"` is defined. Exactly one entry must have this value.  |

**Validation rules:**

- `id` values must be unique across all entries.
- Exactly one entry must have `role: "ingest"`.
- `file_type` must be a valid FileType enum member if set.

**Example:**

```json5
staging_dirs: [
  {id: 1,  name: "movies",  file_type: "movie"},
  {id: 97, name: "temp",    file_type: null,   role: "ingest"},
],
```
````

````

---

## Task 3: Update `INSTALLATION.md`

**Files:**

- Modify: `INSTALLATION.md`

### Step 3.1 — Add note about auto-created staging tree

- [ ] Find the installation / first-run section. Add the following note:

```markdown
### Staging directory

On first run, PersonalScraper automatically creates the staging directory
tree at `paths.staging_dir` (as defined in your `config.json5`). No manual
`mkdir` is required.

You will see a single log warning on first run:

````

[warning] staging_tree_created paths=[...] count=8

```

This is expected behavior — it confirms the directories were created.
```

---

## Task 4: Update `README.md`

**Files:**

- Modify: `README.md`

### Step 4.1 — Remove staging directories from "Structure du projet" tree

- [ ] Find the "Structure du projet" (or equivalent project structure) section in `README.md`. Remove lines referencing `001-MOVIES/`, `002-TVSHOWS/`, `003-EBOOKS/`, `004-AUDIO/`, `005-APPS/`, `006-ANDROID/`, `097-TEMP/`, `098-AUTRES/`, `099-SCRIPTS/`.

- [ ] Keep only the code directories. The tree should look like:

```
A TRIER/
├── personalscraper/     # Package source
├── tests/               # Test suite
├── docs/                # Documentation
├── config.json5         # User configuration (git-tracked)
├── config.example.json5 # Example configuration
├── Makefile
└── ...
```

Add a note below the tree:

```markdown
The staging directories (`001-MOVIES/`, `002-TVSHOWS/`, etc.) live at
`paths.staging_dir` from `config.json5` — outside the repository by default.
They are not tracked by git.
```

---

## Task 5: Update `CLAUDE.md`

**Files:**

- Modify: `CLAUDE.md`

### Step 5.1 — Update project layout references

- [ ] Open `CLAUDE.md`. Search for any mention of `001-MOVIES`, `002-TVSHOWS`, `097-TEMP`, `099-SCRIPTS`, or "staging directories inside the repo". Update to reflect the external staging layout.

- [ ] If the "Purpose" section mentions staging directories by their `NNN-NAME` form, replace with: "staging directories (defined in `config.json5` `staging_dirs`, living at `paths.staging_dir`)".

---

## Task 6: New E2E test `tests/e2e/test_staging_bootstrap_e2e.py`

**Files:**

- Create: `tests/e2e/test_staging_bootstrap_e2e.py`

### Step 6.1 — Write the E2E test

- [ ] Create `tests/e2e/test_staging_bootstrap_e2e.py`:

```python
"""E2E test: auto-create staging tree on first run via CLI.

Validates the full path: config.json5 with empty staging_dir → CLI invocation
→ staging subdirectories created on disk → no error exit code.
"""

from __future__ import annotations

from pathlib import Path

import json5
import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.conf.staging import folder_name
from personalscraper.conf.models import Config


_STAGING_DIRS = [
    {"id": 1,  "name": "movies",  "file_type": "movie"},
    {"id": 2,  "name": "tvshows", "file_type": "tvshow"},
    {"id": 3,  "name": "ebooks",  "file_type": "ebook"},
    {"id": 4,  "name": "audio",   "file_type": "audio"},
    {"id": 5,  "name": "apps",    "file_type": "app"},
    {"id": 6,  "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp",    "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres",  "file_type": "other"},
]


@pytest.fixture
def e2e_env(tmp_path: Path):
    """Create a minimal config.json5 in tmp_path with an empty staging_dir."""
    staging = tmp_path / "staging"
    # Do NOT create staging — let the CLI auto-create it

    config_data = {
        "config_version": 1,
        "paths": {
            "torrent_complete_dir": str(tmp_path / "torrents"),
            "staging_dir": str(staging),
            "data_dir": str(tmp_path / ".data"),
        },
        "disks": [
            {"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}
        ],
        "staging_dirs": _STAGING_DIRS,
    }
    config_file = tmp_path / "config.json5"
    config_file.write_text(json5.dumps(config_data))

    # Create the disk dir so dispatch can resolve it
    (tmp_path / "disk_a").mkdir()

    return {"tmp_path": tmp_path, "staging": staging, "config_file": config_file}


class TestStagingBootstrapE2E:
    """Full E2E: staging tree auto-created on first run via `run --dry-run`."""

    def test_dry_run_creates_staging_tree(self, e2e_env):
        """personalscraper run --dry-run creates all 8 staging subdirs from scratch."""
        runner = CliRunner()
        config_path = str(e2e_env["config_file"])
        staging = e2e_env["staging"]

        # Staging does not exist before the run
        assert not staging.exists(), "Pre-condition: staging dir must not exist"

        result = runner.invoke(app, ["--config", config_path, "run", "--dry-run"])

        # Exit code 0 (dry-run succeeds even with empty staging)
        assert result.exit_code == 0, (
            f"Expected exit code 0, got {result.exit_code}.\nOutput:\n{result.output}"
        )

        # All 8 subdirectories created
        assert staging.is_dir(), "staging_dir root must have been created"

        config = Config.model_validate(
            {
                "paths": {
                    "torrent_complete_dir": str(e2e_env["tmp_path"] / "torrents"),
                    "staging_dir": str(staging),
                    "data_dir": str(e2e_env["tmp_path"] / ".data"),
                },
                "disks": [{"id": "disk_a", "path": str(e2e_env["tmp_path"] / "disk_a"), "categories": ["movies"]}],
                "staging_dirs": _STAGING_DIRS,
            }
        )
        for entry in config.staging_dirs:
            expected = staging / folder_name(entry)
            assert expected.is_dir(), f"Expected staging subdir {expected} to be created"

    def test_dry_run_idempotent_no_error(self, e2e_env):
        """Second dry-run on complete tree exits 0 and does not error."""
        runner = CliRunner()
        config_path = str(e2e_env["config_file"])

        # First run creates the tree
        runner.invoke(app, ["--config", config_path, "run", "--dry-run"])

        # Second run should also succeed
        result = runner.invoke(app, ["--config", config_path, "run", "--dry-run"])
        assert result.exit_code == 0, (
            f"Second run failed with exit code {result.exit_code}.\nOutput:\n{result.output}"
        )

    def test_missing_staging_dirs_config_exits_nonzero(self, tmp_path):
        """Config without staging_dirs section fails with a friendly error message."""
        config_data = {
            "config_version": 1,
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            # staging_dirs intentionally omitted
        }
        config_file = tmp_path / "config.json5"
        config_file.write_text(json5.dumps(config_data))

        runner = CliRunner()
        result = runner.invoke(app, ["--config", str(config_file), "run", "--dry-run"])

        assert result.exit_code != 0
        assert "MANUAL.md" in result.output or "staging_dirs" in result.output
```

### Step 6.2 — Run the E2E test

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/e2e/test_staging_bootstrap_e2e.py -v
```

Expected: all 3 tests PASS.

- [ ] If `test_dry_run_creates_staging_tree` fails because `run --dry-run` exits non-zero (e.g. because no items to process), check whether the `--dry-run` flag returns 0 on empty staging. Adjust the assertion to allow exit code 0 or a known "nothing to do" code — whichever `personalscraper run --dry-run` emits on an empty pipeline.

---

## Task 7: Full final gate

### Step 7.1 — Run complete test suite

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && make lint && make test
```

Expected: all tests PASS, including the new E2E test.

### Step 7.2 — Verify no numeric staging paths in git

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && git ls-files | grep -E "^[0-9]{3}-"
```

Expected: **0 lines**.

### Step 7.3 — Assert `data_dir` unchanged

- [ ] Run:

```bash
grep "data_dir" "/Volumes/IznoServer SSD/A TRIER/config.example.json5"
```

Expected: contains `/Volumes/IznoServer SSD/A TRIER/.data` — value unchanged from main baseline.

---

## Task 8: Commit docs and E2E

- [ ] Stage all modified docs and the new test:

```bash
git add MANUAL.md CONFIGURATION.md INSTALLATION.md README.md CLAUDE.md \
        tests/e2e/test_staging_bootstrap_e2e.py
```

- [ ] Commit:

```bash
git commit -m "docs(ext-staging): update manual, config, installation, readme for external staging"
```

---

## Task 9: Milestone commit

- [ ] Run `git status` to confirm working tree is clean.

- [ ] Create the milestone commit:

```bash
git commit --allow-empty -m "chore(ext-staging): phase 5 gate — docs + E2E"
```

(Use `--allow-empty` only if everything was committed in Task 8. Prefer a non-empty commit if any file was missed.)

---

## Exit gate

- [ ] `make lint && make test` green (full suite, including E2E)
- [ ] E2E test `tests/e2e/test_staging_bootstrap_e2e.py` passes (3 tests)
- [ ] `git ls-files | grep -E "^[0-9]{3}-"` → 0 lines
- [ ] `grep "data_dir" config.example.json5` contains `/Volumes/IznoServer SSD/A TRIER/.data` (unchanged vs main baseline)
- [ ] `MANUAL.md` contains a "Staging layout" section with rsync migration commands
- [ ] `CONFIGURATION.md` documents `staging_dirs`, `paths.staging_dir`, and `paths.data_dir`
- [ ] `README.md` project structure tree no longer lists `NNN-NAME` directories
