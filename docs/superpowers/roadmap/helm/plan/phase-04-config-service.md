# Phase 4 — Config service (load / validate / atomic write / seed)

**Goal:** the `app/` imperative shell that ties model + serializer + validator to the
filesystem (DESIGN §3.1, §6, §7). This is the single seam the HTTP entrypoint and CLI both call.

**Files:** `src/kanbanmate/app/config_service.py` (new),
`tests/app/test_config_service.py` (new). Read-only refs: `app/wiring.py`.

> **Layering (HEAD-verified):** the `CLONE_COLUMNS_RELPATH` / `CLONE_TRANSITIONS_RELPATH`
> constants live in **`cli/init.py`**, and `app/` may NOT import `cli/` (the layering guard
> forbids `app → cli`). So the config service **does not resolve paths itself** — it takes the
> already-resolved `transitions_path` / `columns_path` as **injected inputs** from its caller
> (the `cli config` command or the `http/` entrypoint, both of which may import `cli.init`).
> The functions below therefore take explicit `Path`s, not a `config_dir` to resolve.
>
> **Scope (PR 1):** the resolution the CLI/entrypoint performs is the **registry/clone path**
> only (the registry clone's `.claude/kanban/{columns,transitions}.yml`, mirroring the daemon).
> Resolving arbitrary `explicit-config.yml` paths is **deferred** (added to non-goals).

### 4.1 — `load_current`

`load_current(columns_path: Path, transitions_path: Path | None) -> PipelineConfig` reads the
live `columns.yml` + `transitions.yml` (when `transitions_path` is given and the file exists)
from the **injected** paths, then builds the draft via `PipelineConfig.from_loaded`. A missing
`transitions.yml` (`None` or non-existent) falls back to the built-in default (parity with the
daemon).

**Acceptance:** given temp paths to the shipped templates, returns a `PipelineConfig` matching
the default; with no `transitions.yml`, still returns the default flow (not a column model).
Tests use `tmp_path`.

### 4.2 — `validate`

`validate(cfg: PipelineConfig) -> ValidationResult` — a thin pass-through to
`core.config_validate.validate` (kept in `app/` so the transport layer never imports `core`
directly for this). No I/O.

**Acceptance:** delegates correctly; a known-bad draft returns `valid=False`. One test.

### 4.3 — `write` (atomic, validate-first)

`write(cfg: PipelineConfig, columns_path: Path, transitions_path: Path) -> list[Path]`
(injected paths, per the layering note above). Define `ConfigInvalid(findings: list[Finding])`
**owned by this module** (DESIGN §3.1.a).

1. `validate(cfg)` — **refuse on any error** (raise `ConfigInvalid` carrying the findings).
2. `render_pipeline(cfg)` → two strings.
3. Write each via a **temp file in the target file's OWN parent dir + `os.replace`** (atomic
   rename — `os.replace` is only atomic within the same filesystem, so the temp MUST be a
   sibling of its destination, not in a shared scratch dir). Never leave a partial file.

**Acceptance:** a valid draft writes both files and they re-`load` cleanly; an invalid draft
raises `ConfigInvalid` and writes **nothing** (assert the original files are untouched / no
temp residue). Tests assert atomicity by rendering a known-good then verifying no `.tmp` files
remain beside either target, and that each temp lived in its destination's parent dir.

### 4.4 — `seed_from_default`

`seed_from_default(project: str, columns_path: Path, transitions_path: Path)` renders the
default `PipelineConfig` (bound to `project`) and writes both files via the same atomic path as
4.3 — the programmatic equivalent of what `kanban init` does for the config files (parity, not a
replacement of `init`). Paths are injected (layering note above).

**Acceptance:** seeding empty target paths produces files identical (semantically) to the
shipped templates for that project slug. Test.

### Phase gate

`rm -rf .mypy_cache && make check` green; atomicity + parity tests pass; no residual imports.
