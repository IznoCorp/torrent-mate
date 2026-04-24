# Design — ext-staging: Decouple Staging from Project

**Date**: 2026-04-22
**Codename**: `ext-staging`
**Type**: minor (feat)
**Version bump**: 0.3.0 → 0.4.0
**Branch**: `feat/ext-staging`

## Context

The staging/triage area (`001-MOVIES/`, `002-TVSHOWS/`, `097-TEMP/`, etc.)
currently lives **inside the git repository root**. This mixes code and user
data in the same directory tree.

The staging directory names are **partially configurable today**: a dict
`TYPE_DIR_MAP` in `personalscraper/sorter/strategies.py` holds the defaults,
and a wrapper `get_type_dir_map()` consults seven `{ingest,movies,tvshows,
ebooks,audio,apps,other}_dir_name` fields on `Settings` (env-driven,
pydantic-settings) that can override them one-by-one. This two-layer setup
is awkward: overrides live in `.env` while other config now lives in
`config.json5`, and the list of staging dirs is implicit in the Settings
schema rather than declared as a unit.

`config.paths.staging_dir` already exists (defaulting to the repo root) but is
incompletely decoupled: staging directories are scaffolded in the repo via
`.gitkeep` markers, and `099-SCRIPTS/` contains a 20k-line JSON dump + archived
Python scripts that bloat the repo.

## Goal

1. **Single source of truth for staging dir names**: introduce a `staging_dirs`
   section in `config.json5` that fully replaces the `TYPE_DIR_MAP` dict
   **and** the seven `*_dir_name` env-override fields on `Settings`. Folder
   names are computed from `{id:03d}-{name.upper()}` (e.g.
   `{id:1, name:"movies"}` → `001-MOVIES`).
2. **External staging by default**: move the staging tree out of the repo,
   defaulting to `/Volumes/IznoServer SSD/staging/` in the user's `config.json5`.
   `config.example.json5` uses a **portable relative default** (`./staging/`)
   so CI and fresh clones on any OS work without edits.
3. **Auto-create** the staging tree on first run (silent, warning log).
4. **Remove** all staging directories and `099-SCRIPTS/` from git tracking.
5. **Manual migration** (no tool): user moves existing staging content via
   `rsync` or `mv` after upgrading — documented in MANUAL.md.

## Non-Goals

- **No migration tool.** Manual migration documented in MANUAL.md only.
- **No backward compatibility.** `staging_dirs` is **required** in
  `config.json5`. Users upgrading must edit their config. Minor bump is
  accepted because the project is pre-1.0.
- **No physical move of `data_dir`.** The default path for `data_dir`
  remains at `/Volumes/IznoServer SSD/A TRIER/.data` (current location).
  The config value becomes explicit so the user can relocate it later
  with a single config edit. **Phase gates assert this path is not
  changed by the feature.**
- **No physical move of `099-SCRIPTS/` files.** `git rm --cached` only;
  the files stay on disk. **Phase 4 gate asserts `099-SCRIPTS/` physical
  content (`ls`) is unchanged before and after the commit.** The user
  will deal with the files in a separate project if needed.
- **No logic changes** beyond lookup replacement: the pipeline (ingest,
  sort, scrape, verify, dispatch, process, enforce) keeps its current
  behavior. Only the source of directory names changes.

## Scope

### In scope

- New config schema: `staging_dirs: list[StagingDirConfig]` at top level
  of `config.json5`, with Pydantic validation.
- Refactor of `personalscraper/sorter/strategies.py`:
  - Remove `TYPE_DIR_MAP` dict.
  - Remove `get_type_dir_map()` wrapper.
  - Replace both with lookups via the config-driven helper
    `find_by_file_type(config, file_type)`.
- Removal from `personalscraper/config.py` of the seven `Settings`
  fields: `ingest_dir_name`, `movies_dir_name`, `tvshows_dir_name`,
  `ebooks_dir_name`, `audio_dir_name`, `apps_dir_name`, `other_dir_name`.
  Their docstrings in lines 43–49 are also removed.
- Replacement of every string literal referencing `001-MOVIES`,
  `002-TVSHOWS`, `097-TEMP`, etc. in `personalscraper/**/*.py` by a
  config-backed lookup. (20 files per literal-string grep; see
  "File inventory" below.)
- New module `personalscraper/conf/staging.py` with model helpers
  (Phase 2) and `ensure_staging_tree(config)` (Phase 3).
- Hook: `ensure_staging_tree` called at the start of every CLI command
  that touches staging, and at the start of `pipeline.run()`.
- Update of `personalscraper/commands/init_config.py`:
  `init-config --from-current` emits a `staging_dirs` section in the
  generated `config.json5`, mapping the old `*_dir_name` env values to
  new `staging_dirs` entries.
- `git rm --cached` of 9 top-level directories (001-006, 097, 098, 099).
  **Phase 4 preamble enumerates `git ls-files` blast radius** before the
  `rm --cached`.
- `.gitignore` cleanup: 17+ existing lines replaced by a single pattern
  `[0-9][0-9][0-9]-*/`.
- Docstring updates in `personalscraper/sorter/strategies.py`:
  docstring examples like `"001-MOVIES/Title (Year)/"` are rewritten
  using placeholder notation (`{dirname}/Title (Year)/`) so Success
  criterion 3 holds without AST scanning.
- Docs: MANUAL.md, CONFIGURATION.md, INSTALLATION.md, README.md, CLAUDE.md
  updated to reflect the new layout and manual migration steps.
- Tests: new unit tests for bootstrap + config validation; refactor of
  existing sorter tests to inject a test config; new E2E test verifying
  auto-create from a fresh tmpdir staging_dir.

### Out of scope

- `data_dir` is made explicit in config but not physically moved.
- `099-SCRIPTS/` files stay on disk (git untracked only).
- `config.json5` migration tooling.
- Global test fixture overhaul (tests refactor is limited to what the
  sorter refactor requires).
- Runtime behavior changes to any pipeline step.

## Architecture — 5 Sequential Phases

### Phase 1 — Config schema, additive

**Intent**: introduce the config model **as optional** so existing
`config.json5` still loads. Consumers switch over in Phase 2.

Operations:

- Add `StagingDirConfig` Pydantic model in `personalscraper/conf/models.py`:
  - `id: int` with `ge=0, le=999`
  - `name: str` matching `^[a-z0-9]+(-[a-z0-9]+)*$` (kebab-case, no
    underscores, since `.upper()` produces `"MY-CAT"` consistently)
  - `file_type: Optional[str]` (resolved to `FileType` enum via validator;
    duplicate `file_type` across entries is **allowed** — multiple dirs
    can share a FileType for domain-specific routing, though current
    convention is one-to-one)
  - `role: Optional[str]` (currently only `"ingest"` is defined)
- Add `staging_dirs: Optional[list[StagingDirConfig]] = None` to `Config`
  root (optional in Phase 1, required in Phase 2).
- Validators (at `Config` root level, triggered only if `staging_dirs`
  present):
  - Unique `id` values.
  - Exactly 1 entry with `role: "ingest"`.
  - Every `file_type` points to a valid `FileType` enum member.
- Update `config.example.json5`:
  - `staging_dir` default: **`./staging/`** (relative, portable)
  - Add `staging_dirs` section with the 8 current entries (ids 1-6, 97, 98)
- **Do NOT update the user's local `config.json5` in Phase 1.** That
  migration happens only when the user edits it (documented in MANUAL.md)
  or when they run `init-config --from-current` after Phase 2.

Tests:

- `tests/conf/test_models_staging.py`:
  - valid config passes
  - duplicate id fails
  - two `role: "ingest"` fail
  - zero `role: "ingest"` fails
  - invalid `file_type` fails
  - invalid `name` (uppercase, underscore, special char) fails
  - id out of range (−1, 1000) fails

Gate:

- `make test` green
- `grep -n "TYPE_DIR_MAP" personalscraper/sorter/strategies.py` returns
  the existing occurrences (Phase 1 does **not** remove them yet)
- `paths.data_dir` in `config.example.json5` **unchanged** from current
  value

Commit: `feat(ext-staging): add StagingDirConfig schema`

### Phase 2 — Sorter refactor + Settings cleanup

**Intent**: switch every consumer from `TYPE_DIR_MAP` / `Settings.*_dir_name`
to config lookup. Make `staging_dirs` **required** in `Config`.

Operations:

- Create `personalscraper/conf/staging.py` with helpers:
  - `folder_name(entry: StagingDirConfig) -> str` → `f"{entry.id:03d}-{entry.name.upper()}"`
  - `staging_path(config: Config, entry: StagingDirConfig) -> Path`
  - `find_by_file_type(config: Config, file_type: FileType) -> StagingDirConfig` (raises if no match)
  - `find_ingest_dir(config: Config) -> StagingDirConfig` (invariant: exactly one, Phase 1 validator enforces)
- In `Config` model: tighten `staging_dirs` from `Optional[...] = None`
  to **required** (`staging_dirs: list[StagingDirConfig]`). Add a custom
  `model_validator` emitting: **"`staging_dirs` missing from config.json5
  — see MANUAL.md §Staging layout for migration steps."**
- Remove from `personalscraper/config.py`:
  - Fields: `ingest_dir_name`, `movies_dir_name`, `tvshows_dir_name`,
    `ebooks_dir_name`, `audio_dir_name`, `apps_dir_name`, `other_dir_name`
  - Their docstring lines (43–49).
- Remove from `personalscraper/sorter/strategies.py`:
  - `TYPE_DIR_MAP` dict (line 19)
  - `get_type_dir_map()` function (lines 29–61)
  - All call sites (lines 104, 136, 188 and wherever else) switch to
    `find_by_file_type(config, file_type)` → `folder_name(...)`.
  - Docstring examples rewritten to placeholder form (e.g.
    `"{dirname}/Title (Year)/"`).
- Sweep 20 files for literal references to `"001-MOVIES"`, `"002-TVSHOWS"`,
  …, `"098-AUTRES"`, `"097-TEMP"` and replace with config lookup (see
  File inventory).
- Update `personalscraper/commands/init_config.py`: `--from-current`
  emits a `staging_dirs` section, converting the now-deleted `*_dir_name`
  env values read from the user's `.env` into entries. (Schema: id 1
  for movies, 2 for tvshows, etc., matching current convention.)
- Refactor `tests/sorter/test_strategies.py`: inject a test config with
  the 8 entries. Assertions become dynamic via `folder_name(entry)`.
- Other tests asserting staging paths — same treatment.

Tests:

- Updated sorter tests pass with both the default config and a custom
  config (e.g. `id=10, name="mega"` → `010-MEGA`).
- `init_config --from-current` E2E test asserts a `staging_dirs` section
  is present in the generated config.
- Model validator emits the friendly error message when `staging_dirs`
  is missing.

Gate:

- `grep -n "TYPE_DIR_MAP\|get_type_dir_map" personalscraper/ --include="*.py" -r` returns 0 matches
- `grep -n "_dir_name" personalscraper/config.py` returns 0 matches
  (all 7 fields removed)
- `grep -rn "\"0[0-9]\{2\}-" personalscraper/ --include="*.py"` returns
  0 matches (docstring examples rewritten in this phase)
- `make lint && make test` green
- `paths.data_dir` in `config.example.json5` unchanged

Commit: `refactor(ext-staging): replace TYPE_DIR_MAP and Settings *_dir_name with config-driven lookup`

### Phase 3 — Auto-create staging tree

**Intent**: first run creates the staging tree silently.

Operations:

- Add to `personalscraper/conf/staging.py`:

  ```python
  def ensure_staging_tree(config: Config) -> list[Path]:
      """Create staging_dir + per-entry subdirs if absent.

      Returns the list of paths that were created (empty if all existed).
      Emits a single structlog warning if anything was created.
      """
  ```

- Call sites:
  - `personalscraper/pipeline.py` — at the very start of `run()`
  - `personalscraper/cli.py` — before each command handler that touches
    staging (ingest, sort, process, scrape, verify, enforce, dispatch)
- Use a decorator or shared utility to avoid repetition.

Tests:

- `tests/conf/test_staging_bootstrap.py`:
  - full absent tree → full create, warning emitted once, returns list of paths
  - full present tree → no-op, no warning, returns `[]`
  - partial tree → ciblé create, warning emitted, returns missing paths only
  - idempotence: 2nd call on now-complete tree is a no-op

Gate:

- `make lint && make test` green
- `personalscraper run --dry-run` in an empty staging_dir creates the tree

Commit: `feat(ext-staging): auto-create staging tree on first run`

### Phase 4 — Repo cleanup

**Intent**: remove staging directories and 099-SCRIPTS/ from git tracking.
Explicit blast-radius measurement before the `rm --cached`.

Operations:

- **Preamble gate** (pre-removal measurement):
  ```bash
  echo "Tracked files under staging trees and 099-SCRIPTS:"
  git ls-files 001-MOVIES 002-TVSHOWS 003-EBOOKS 004-AUDIO 005-APPS \
               006-ANDROID 097-TEMP 098-AUTRES 099-SCRIPTS | tee /tmp/tracked-before.txt | wc -l
  echo "Physical file count under 099-SCRIPTS:"
  find 099-SCRIPTS -type f | wc -l
  ```
- `git rm -r --cached 001-MOVIES 002-TVSHOWS 003-EBOOKS 004-AUDIO 005-APPS 006-ANDROID 097-TEMP 098-AUTRES 099-SCRIPTS`
- `.gitignore` diff:
  - Remove all `0XX-*/*` lines (8 current)
  - Remove all `!0XX-*/.gitkeep` lines (8 current)
  - Remove `099-SCRIPTS/plex/contents.json` line
  - Add single line: `[0-9][0-9][0-9]-*/`
- Optionally `rm` the `.gitkeep` files on disk (they become orphans
  after `--cached`). Documented in MANUAL.md migration steps.

Tests:

- No test changes.

Gate:

- `git ls-files | grep -E "^[0-9]{3}-"` returns 0 lines.
- Physical count under `099-SCRIPTS/` **unchanged** before vs after
  commit: `find 099-SCRIPTS -type f | wc -l` identical.
- `make lint && make test` green.

Commit: `chore(ext-staging): remove staging directories and 099-SCRIPTS from repo`

### Phase 5 — Docs + E2E + final gate

**Intent**: documentation matches the new reality; full E2E test
validates the feature end-to-end.

Operations:

- `MANUAL.md`:
  - New section "Staging layout" describing `staging_dir` and `staging_dirs`
  - Migration steps: `rsync -a "$(pwd)/001-MOVIES/" /Volumes/IznoServer\ SSD/staging/001-MOVIES/` (repeat per dir)
  - Note: `099-SCRIPTS/` stays on disk; user responsibility
  - Note: after upgrading, users must add `staging_dirs` to their
    `config.json5` — point to the generated `config.example.json5`
- `CONFIGURATION.md`:
  - Document `paths.staging_dir` (new default in example: `./staging/`)
  - Document `paths.data_dir` (explicit, **unchanged** physically)
  - Document `staging_dirs` section with field-by-field reference
- `INSTALLATION.md`:
  - Note: "on first run, `personalscraper` auto-creates the staging tree
    at `paths.staging_dir` — no manual setup required"
- `README.md`:
  - Remove `001-MOVIES`, `002-TVSHOWS` etc. from the "Structure du projet" tree
  - Keep only the code directories (`personalscraper/`, `tests/`, etc.)
- `CLAUDE.md`:
  - Update reference to project layout if needed
- New E2E test `tests/e2e/test_staging_bootstrap_e2e.py`:
  - Setup: tmpdir + config.json5 where `paths.staging_dir = tmpdir / "staging"`
  - Run: `personalscraper run --dry-run`
  - Assert: 8 staging directories created, no error, warning logged once

Gate:

- `make lint && make test` green (full suite).
- E2E passes.
- `git ls-files | grep -E "^[0-9]{3}-"` returns 0 lines.
- `paths.data_dir` value in repo config still `/Volumes/IznoServer SSD/A TRIER/.data`.

Commit: `docs(ext-staging): update manual, config, installation, readme for external staging`

Final milestone commit (per /implement:phase pattern): `chore(ext-staging): phase 5 gate — docs + E2E`

## File inventory — refactor targets

Python files currently referencing staging-path literals
(`001-MOVIES`, `002-TVSHOWS`, `097-TEMP`, or `098-AUTRES`), discovered
via `grep -rn "001-MOVIES\|002-TVSHOWS\|097-TEMP\|098-AUTRES"
personalscraper/ --include="*.py" -l | sort -u` — **20 files**:

- `personalscraper/cli.py`
- `personalscraper/config.py` (Settings `*_dir_name` fields to be removed here)
- `personalscraper/conf/migration.py`
- `personalscraper/conf/models.py`
- `personalscraper/dispatch/run.py`
- `personalscraper/enforce/coherence_checker.py`
- `personalscraper/enforce/file_sanitizer.py`
- `personalscraper/enforce/structure_validator.py`
- `personalscraper/info/run.py`
- `personalscraper/lock.py`
- `personalscraper/pipeline.py`
- `personalscraper/process/cleanup.py`
- `personalscraper/process/dedup.py`
- `personalscraper/process/reclean.py`
- `personalscraper/process/run.py`
- `personalscraper/sorter/__init__.py`
- `personalscraper/sorter/run.py`
- `personalscraper/sorter/sorter.py`
- `personalscraper/sorter/strategies.py` (`TYPE_DIR_MAP`, `get_type_dir_map`)
- `personalscraper/sorter/file_type.py`

Each file is reviewed in Phase 2 — most reference `staging_dir` already
correctly via `config.paths.staging_dir`, only the string-literal
subdirectory names need replacement.

## Success criteria

1. `staging_dirs` section present in `config.example.json5`, with 8
   entries matching current behavior.
2. `grep -rn "TYPE_DIR_MAP\|get_type_dir_map" personalscraper/ --include="*.py"`
   returns 0 matches.
3. `grep -rn "\"0[0-9]\{2\}-" personalscraper/ --include="*.py"`
   returns 0 matches (docstring placeholders rewritten in Phase 2).
4. `grep -rn "_dir_name" personalscraper/config.py` returns 0 matches
   (seven Settings fields removed).
5. `git ls-files | grep -E "^[0-9]{3}-"` returns 0 matches.
6. `personalscraper run --dry-run` on an empty staging_dir creates the
   tree and succeeds.
7. Full `make lint && make test` green.
8. `VERSION` and `personalscraper.__version__` both `0.4.0`.
9. `paths.data_dir` value in repo-tracked `config.example.json5` and
   user `config.json5` unchanged vs `main` baseline.
10. Physical file count under `099-SCRIPTS/` identical before and after
    Phase 4.

## Risk analysis

| Risk                                                                                       | Mitigation                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Missed string literal in a rarely-tested code path                                         | Systematic grep in Phase 2 gate; E2E test in Phase 5 catches runtime misses                                                                                                                                                           |
| Existing user upgrades without editing config → `staging_dirs` absent → hard error         | Custom model validator emits friendly error message pointing to MANUAL.md §Staging layout. Pre-1.0, breaking changes acceptable.                                                                                                      |
| 099-SCRIPTS `.gitkeep` / tracked files reappear on disk operations                         | `git rm --cached` preserves files; `.gitignore` pattern catches them going forward. Phase 4 gate asserts physical file count unchanged.                                                                                               |
| Tests rely on hardcoded `"001-MOVIES"` strings                                             | Phase 2 explicitly refactors tests to use dynamic `folder_name(entry)`                                                                                                                                                                |
| Manual migration steps confuse users                                                       | MANUAL.md includes copy-pasteable commands (rsync / mv examples)                                                                                                                                                                      |
| **CI or fresh clone fails because default staging path is macOS-absolute**                 | **`config.example.json5` uses a portable relative path `./staging/`. The user's production `config.json5` uses the absolute `/Volumes/IznoServer SSD/staging/`. CI runs against `config.example.json5` (or a test-specific config).** |
| **Phase 1 makes `staging_dirs` required → intermediate commit breaks tests**               | **Phase 1 makes it `Optional[...] = None`; Phase 2 tightens to required after all consumers are switched. Phase 1 gate explicitly asserts `TYPE_DIR_MAP` is still present.**                                                          |
| **Phase boundary leak: `staging.py` helpers in Phase 2, `ensure_staging_tree` in Phase 3** | **Module created in Phase 2 with helpers only. Phase 3 adds `ensure_staging_tree()` to the existing module — no cross-phase file ownership issue.**                                                                                   |
| **`data_dir` silently modified during refactor**                                           | **Phase 1, 2, 5 gates explicitly assert `config.example.json5` `paths.data_dir` unchanged vs main baseline.**                                                                                                                         |

## Deliverables summary

**Created**:

- `personalscraper/conf/staging.py`
- `tests/conf/test_staging_bootstrap.py`
- `tests/conf/test_models_staging.py`
- `tests/e2e/test_staging_bootstrap_e2e.py`

**Modified** (20 Python files per inventory + config + docs):

- `personalscraper/conf/models.py` (add `StagingDirConfig`, extend `Config`)
- `personalscraper/config.py` (remove 7 `*_dir_name` Settings fields + docstrings)
- `personalscraper/commands/init_config.py` (emit `staging_dirs` in `--from-current`)
- 18 other files in `personalscraper/**/*.py` (string-literal replacements + staging_bootstrap calls)
- `config.example.json5`
- `.gitignore`
- `MANUAL.md`, `CONFIGURATION.md`, `INSTALLATION.md`, `README.md`, `CLAUDE.md`
- Existing sorter tests (dynamic assertions)

**Removed from git** (files stay on disk):

- 9 top-level directories: `001-MOVIES/.gitkeep`, ..., `099-SCRIPTS/**`

**Unchanged**:

- Pipeline logic (ingest, sort, scrape, verify, dispatch, process, enforce)
- `data_dir` physical location and config value
- Media/test fixtures
- `099-SCRIPTS/` physical file contents

## Version bump

- Current: 0.3.0
- Target: 0.4.0 (minor)
- Rationale: pre-1.0 tolerates breaking config-schema changes under minor;
  feature is functionally additive (new config section, new module,
  config-driven behavior replaces hardcoded + env-overridden equivalents).

## Next step

Invoke `superpowers:writing-plans` via `/implement:plan` to produce
per-phase plan files at `docs/features/ext-staging/plan/`.
