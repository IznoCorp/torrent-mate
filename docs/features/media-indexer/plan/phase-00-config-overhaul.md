# Phase 0 — Config Overhaul

## Gate

**Prerequisite:** `feat/trailer` merged to `main`; `feat/media-indexer` branch created at 0.8.0 bump.

**This phase's exit gate (verbatim from DESIGN §16):**

> Full test suite green on v2 config; `config migrate-to-v2` produces an exactly-equivalent `Config`.

---

## Scope

Split the monolithic `.personalscraper/config.json5` into one file per concern under `.personalscraper/config/`, introduce a unified multi-file loader with overlay support, ship a one-shot migration CLI, add `IndexerConfig` as a new pydantic submodel, and prove behavioural parity via golden tests. No indexer runtime code lands in this phase — only configuration infrastructure.

---

## Sub-phases

### 0.0 — Add runtime + dev dependencies

**Files touched:**

- `pyproject.toml`

**Deliverable:** Runtime deps `pymediainfo>=6.1.0`, `xxhash>=3.4.0`, `filelock>=3.13.0` and dev deps `sqlite-utils>=3.36`, `pyfakefs>=5.4.0`, `hypothesis>=6.100.0` added to `pyproject.toml`. System dep `brew install media-info` documented in `README.md` (or `docs/reference/storage.md` if it already covers system deps).

**Tests added:** None (deps verified by subsequent import in Phase 1).

**Commit:** `chore(media-indexer): 0.0 add runtime and dev dependencies`

---

### 0.1 — Loader + overlay skeleton

**Files touched:**

- `personalscraper/conf/loader.py` _(new)_
- `personalscraper/conf/overlay.py` _(new)_
- `tests/conf/__init__.py` _(new — empty)_
- `tests/conf/test_loader.py` _(new)_
- `tests/conf/test_overlay.py` _(new)_

**Deliverable:**

- `loader.py` exposes `load_config(config_dir: Path | None = None) -> Config`. Resolution order: `config.json5` (master) → each file listed in `overlays` key → optional `local.json5` (deep-merge). Returns validated pydantic `Config`.
- `overlay.py` exposes `merge_overlays(base: dict, *overlays: dict) -> dict`. Shallow-per-key merge; raises `ConfigConflictError` when two non-`local.json5` overlays own the same top-level key.
- Tests: happy path (two non-conflicting overlays), conflicting-key error, missing overlay file raises `ConfigLoadError`, `local.json5` wins on conflict.

**Tests added:** `tests/conf/test_loader.py`, `tests/conf/test_overlay.py`

**Commit:** `feat(media-indexer): 0.1 conf/loader + conf/overlay multi-file merge`

---

### 0.2 — Split config.json5 into per-concern files

**Files touched:**

- `.personalscraper/config/config.json5` _(new — master)_
- `.personalscraper/config/paths.json5` _(new)_
- `.personalscraper/config/disks.json5` _(new)_
- `.personalscraper/config/categories.json5` _(new)_
- `.personalscraper/config/patterns.json5` _(new)_
- `.personalscraper/config/encoding.json5` _(new)_
- `.personalscraper/config/scraper.json5` _(new)_
- `.personalscraper/config/trailers.json5` _(new)_

**Deliverable:** The legacy monolith content is hand-split across the eight new files. No pydantic schema change yet — the loader reads v2 files and produces the same `Config` as the old monolith. The old `.personalscraper/config.json5` is kept in place for now (removed in 0.3 after migration CLI exists).

**Tests added:** None (parity tested in 0.5).

**Commit:** `chore(media-indexer): 0.2 split config.json5 into per-concern files`

---

### 0.3 — Migration CLI

**Files touched:**

- `personalscraper/conf/migration.py` _(new)_
- `personalscraper/cli.py` or wherever the top-level CLI is assembled _(modify — add `config migrate-to-v2` subcommand)_
- `tests/conf/test_migration.py` _(new)_
- `tests/conf/test_migration_malformed.py` _(new)_

**Deliverable:**

- `migration.py` exposes `migrate_v1_to_v2(legacy_path: Path, target_dir: Path) -> None`. Reads old `config.json5`, splits across new files, writes to `target_dir`. Writes atomically: to `.in-progress/` then `os.rename()` to final. On any failure, leaves `.in-progress/` so the loader can detect and refuse.
- CLI: `personalscraper config migrate-to-v2 [--dry-run]`. `--dry-run` prints what would be written without touching disk.
- Migration handles unknown v1 keys by appending them to `local.json5` under `_migration_unknown_keys` and writing `migration-warnings.txt`.
- Tests: golden parity (v1 → v2 → `Config` equality), partial failure leaves `.in-progress/`, unknown keys land in `local.json5`, extra unknown keys, missing `staging_dirs`, comments-only, trailing-comma JSON5, `version: 2 already` — each either fails closed or migrates without data loss; `.v1.bak` always written.

**Tests added:** `tests/conf/test_migration.py`, `tests/conf/test_migration_malformed.py`

**Commit:** `feat(media-indexer): 0.3 conf/migration + config migrate-to-v2 CLI`

---

### 0.4 — IndexerConfig pydantic submodel

**Files touched:**

- `personalscraper/conf/models.py` _(modify — add `IndexerConfig`, extend `Config`)_
- `personalscraper/indexer/config.py` _(new — thin re-export so indexer sub-package can import without conf cycle)_
- `.personalscraper/config/indexer.json5` _(new — default values from DESIGN §5.3)_

**Deliverable:**

- `IndexerConfig` pydantic model with all fields from DESIGN §5.3 (`db_path`, `scan.*`, `fingerprint.*`, `mediainfo.*`, `drift.*`, `spotlight.*`, `repair.*`, `log.*`).
- `Config` extended with `indexer: IndexerConfig` field (default from `indexer.json5`).
- The loader reads `indexer.json5` and validates through `IndexerConfig`.
- Per-disk `spotlight_enabled` field added to the disk config model.
- Loader rejects `db_path` that resolves to an external/macFUSE mount.

**Tests added:** Extend `tests/conf/test_loader.py` with `IndexerConfig` round-trip test.

**Commit:** `feat(media-indexer): 0.4 IndexerConfig pydantic submodel`

---

### 0.5 — Golden tests + parity assertions

**Files touched:**

- `tests/conf/test_migration.py` _(extend — add field-by-field equality assertions)_
- `tests/conf/test_loader.py` _(extend — v1 auto-detect deprecation warning test)_

**Deliverable:**

- Golden test: load v1 monolith directly → `Config_v1`. Run `migrate_v1_to_v2` → load split files → `Config_v2`. Assert `Config_v1 == Config_v2` field-by-field (not just `==`, iterate fields explicitly to get readable failure messages).
- v1 auto-detect: loader receiving the old `config.json5` path (not a directory) emits a `DeprecationWarning` at startup with the exact migration CLI invocation.
- Full existing test suite (`pytest`) passes without modification.

**Tests added:** Extensions to `tests/conf/test_migration.py`, `tests/conf/test_loader.py`

**Commit:** `test(media-indexer): 0.5 golden parity tests for config v1→v2`

---

## Acceptance criteria

- [ ] `pytest tests/conf/` passes (all new tests green).
- [ ] `pytest` (full suite) passes with v2 config loaded — no existing test broken.
- [ ] `personalscraper config migrate-to-v2` on the real `config.json5` produces a split directory; loading it via `load_config()` returns a `Config` equal to the monolith-loaded one.
- [ ] `personalscraper config migrate-to-v2 --dry-run` prints planned writes and exits 0 without touching disk.
- [ ] Loading v1 path directly logs a deprecation warning containing the migration CLI command.
- [ ] `IndexerConfig` validates all fields from DESIGN §5.3 with correct defaults.
- [ ] Loader raises `ConfigConflictError` when two overlays own the same top-level key.
- [ ] Migration with unknown v1 keys: `local.json5` contains `_migration_unknown_keys`; `migration-warnings.txt` lists them; `Config` round-trip still passes.
- [ ] Partial migration failure (simulated mid-write crash): `.in-progress/` present; `load_config()` refuses with actionable message.

---

## DESIGN cross-references

Implements: §5.1 (target layout), §5.2 (loader), §5.3 (IndexerConfig), §5.4 (migration), §5.5 (loader v1 detection), §15.4 (golden tests), §15.4.1 (referenced for fixture location), §17.1 (migration failure modes).

---

## Out of scope for this phase

- The indexer subsystem (`personalscraper/indexer/`) — Phase 1+.
- `indexer.json5` being loaded by any runtime indexer code — Phase 1.
- Removal of the old monolith `config.json5` — kept until Phase 6 cleanup.
- Per-disk sentinel files — Phase 2.
- Any changes to `tests/dispatch/`, `tests/library/`, `tests/trailers/`.
