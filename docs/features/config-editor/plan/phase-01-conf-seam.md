# Phase 01 — Config Validation Seam + Envfile Extraction

## Gate

None — first phase. Requires `feat/config-editor` branch on top of `8b905c74`.

## Goal

Establish the three conf-layer primitives every subsequent phase imports:

1. **ContextVar** for `_PROJECT_ROOT` so `validate_candidate()` can run in FastAPI threadpool.
2. **`validate_candidate()`** — pure validation entry point usable by the web route without touching disk.
3. **`envfile.py`** — shared `.env` upsert module extracted from `commands/web.py`.

## Sub-phases

### 1.1 — Promote `_PROJECT_ROOT` to ContextVar (`personalscraper/conf/models/paths.py`)

**Files**:

- Modify: `personalscraper/conf/models/paths.py` — replace `_PROJECT_ROOT: Path | None = None` with a `ContextVar[Path | None]`
- Verify: `personalscraper/conf/loader.py:194-204` — `paths_model._PROJECT_ROOT = …` / restore block switches to `ContextVar.set()` / `ContextVar.reset(token)`
- Grep: all `_PROJECT_ROOT` reads in `personalscraper/` and `tests/` — confirm they read via `.get()` not direct attribute

**ContextVar shape**:

```python
from contextvars import ContextVar

_project_root: ContextVar[Path | None] = ContextVar("project_root", default=None)
```

**Loader change** (`loader.py:194-204`):

```python
token = paths_model._project_root.set(project_root)
try:
    config = Config.model_validate(merged)
finally:
    paths_model._project_root.reset(token)
```

**Commit**: `refactor(config-editor): promote _PROJECT_ROOT to ContextVar`

### 1.2 — Add `validate_candidate()` to loader (`personalscraper/conf/loader.py`)

**Files**:

- Modify: `personalscraper/conf/loader.py` — new function + export in `__all__`
- Create: `tests/conf/test_validate_candidate.py` — 11 tests (accept/reject/isolation/mutation)

**Signature**:

```python
def validate_candidate(
    config_dir: Path,
    replaced: dict[str, dict[str, Any]],
) -> tuple[Config, list[str]]:
    """Validate a candidate config without touching the filesystem.

    Reads overlay files from *config_dir*, substitutes the values in
    *replaced* (mapping overlay filenames → replacement dicts) in memory,
    then runs the full merge + Pydantic validation pipeline.

    Differs from load_config_dir in two ways:
    - Skips the category-orphan DB check (no DB touch).
    - Runs genuine filesystem probes (WAL-safety of db_path) that are real
      validation, not side effects.

    Args:
        config_dir: Path to the config directory (read-only).
        replaced: Mapping of overlay filenames (e.g. ``"paths.json5"``) to
            candidate dicts that replace the on-disk file content during
            validation.

    Returns:
        (validated_config, warnings) — same shape as load_config_dir output,
        minus the orphan check.

    Raises:
        ConfigNotFoundError, ConfigValidationError, ConfigConflictError:
        same as load_config_dir.
    """
```

**Commit**: `feat(config-editor): add validate_candidate() entry point`

### 1.3 — Extract `_write_env_keys` to `personalscraper/conf/envfile.py`

**Files**:

- Create: `personalscraper/conf/envfile.py` — `write_env_keys()` (public, renamed from `_write_env_keys`)
- Modify: `personalscraper/commands/web.py` — import from new location, remove old definition
- Verify: `set-password` CLI still works after extraction

**Module API**:

```python
# personalscraper/conf/envfile.py
def write_env_keys(keys: dict[str, str], env_path: Path) -> None:
    """Atomically upsert KEY=value pairs into a .env file.

    Existing lines with matching keys are replaced in place; comments,
    blanks, and unrelated keys are preserved. Missing keys are appended.
    Values are never logged.

    Args:
        keys: Mapping of KEY → value to upsert.
        env_path: Path to the .env file (created if absent).
    """

def read_env_catalog(env_example_path: Path) -> dict[str, str]:
    """Parse .env.example into {KEY: description} catalog.

    Used by the secrets GET endpoint to enumerate known keys without
    ever reading actual values from .env.
    """
```

**Commit**: `refactor(config-editor): extract write_env_keys to conf/envfile.py`

## Coherence gate → Phase 2

After Phase 1 merge:

- [ ] `from personalscraper.conf.loader import validate_candidate` works
- [ ] `from personalscraper.conf.envfile import write_env_keys, read_env_catalog` works
- [ ] `personalscraper web set-password` still functional (imports envfile, not old private function)
- [ ] `make test` passes with zero failures (ContextVar regression)
- [ ] `make lint` passes
