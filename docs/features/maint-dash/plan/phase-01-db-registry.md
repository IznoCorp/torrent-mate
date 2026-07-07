# Phase 1 — DB Migration 012 + Maintenance Action Registry

## Gate

**Prerequisite**: `feat/maint-dash` branch exists on `b47bd9eb7`. No prior phase.

**Produces for Phase 2+3+4**: `pipeline_run` with 4 new columns (`kind`, `command`, `options_json`, `output_tail`). Importable registry module with 25 action entries + canonical serialization. After this phase:

- Migration 012 applied → new columns exist with correct defaults.
- `personalscraper/web/maintenance/` package exists with `registry.py` and `__init__.py`.
- `make lint` + `make test` green (migration test verifies 011→012 upgrade, registry test verifies 25 entries).

### DESIGN §4.1 Risk re-verification (mandated by DESIGN itself)

Before coding the registry, verify EVERY `library-*` CLI signature against the risk table in DESIGN §4.1. The CLI is ground truth — if a command gained a `--dry-run` flag since the DESIGN was written, its `dry_run` field must be `"supported"`. If a command moved from `ro` to `write`, the risk classification changes. The grep to re-derive ground truth:

```bash
for cmd in analyze audit dedup_titles doctor fix_canonical_provider fix_nfo \
  fix_orphan_files fix_season_counts gc maintenance query scan; do
  echo "=== $cmd ==="
  command rg -n "def library_" personalscraper/commands/library/$cmd.py | head -5
  command rg -n "dry.run" personalscraper/commands/library/$cmd.py
done
```

## Sub-phases

### 1.1 — Migration 012 (`chore(maint-dash): add kind/command/options/output_tail to pipeline_run`)

**Files:**

- Create: `personalscraper/indexer/migrations/012_pipeline_run_maintenance.sql`
- Create: `tests/unit/indexer/test_migration_012.py`

**Migration SQL** (`012_pipeline_run_maintenance.sql`):

```sql
-- Migration 012 — extend pipeline_run for S3 maintenance actions.
-- Additive: all existing S2 columns and rows are preserved.

ALTER TABLE pipeline_run ADD COLUMN kind          TEXT NOT NULL DEFAULT 'pipeline';
ALTER TABLE pipeline_run ADD COLUMN command       TEXT NULL;
ALTER TABLE pipeline_run ADD COLUMN options_json  TEXT NULL;
ALTER TABLE pipeline_run ADD COLUMN output_tail   TEXT NULL;

CREATE INDEX idx_pipeline_run_kind ON pipeline_run(kind);

INSERT INTO schema_version (version) VALUES (12);
PRAGMA user_version = 12;
```

**Test** (`test_migration_012.py`): apply 011 → apply 012 → verify `kind='pipeline'` default on a row inserted via the 011 schema (no columns), then insert a maintenance row with all 4 new columns set, verify read-back. Use a temporary in-memory DB + `apply_migrations(dir_=indexer_migrations_dir)`.

### 1.2 — Registry module (`feat(maint-dash): add maintenance action registry with 25 typed entries`)

**Files:**

- Create: `personalscraper/web/maintenance/__init__.py` (docstring package header)
- Create: `personalscraper/web/maintenance/registry.py`
- Create: `tests/unit/web/maintenance/test_registry.py`

**Key interfaces** (exported by `registry.py`):

```python
class ActionOption(BaseModel):
    name: str
    type: Literal["str", "int", "bool", "enum"]
    enum_values: list[str] | None = None
    default: str | int | bool | None = None
    required: bool = False
    label: str
    help: str

class MaintenanceAction(BaseModel):
    id: str
    title: str
    description: str
    category: Literal["query", "scan", "repair", "clean", "analyze", "fix"]
    risk: Literal["ro", "write", "destructive"]
    long_running: bool
    dry_run: Literal["unsupported", "supported"]
    options: list[ActionOption]

REGISTRY: list[MaintenanceAction]  # 25 entries at time of writing
```

**The registry** is a module-level `REGISTRY: list[MaintenanceAction]` covering the 25 `library-*` commands REGISTERED on the Typer app (`@app.command` in `personalscraper/commands/library/*.py`) — NOT `__all__`, which is stale ground truth (it lists 23 names, missing `library_scan` and `library_backfill_ids`). Each entry includes: `id` (kebab-case CLI name), `title` (FR), `description` (FR one-liner), `category`, `risk`, `long_running` (True if the command touches disk I/O beyond DB), `dry_run` (`"supported"` if CLI has `--dry-run` flag, checked per Phase 1 CLI verification), `options` (curated list — high-value targeting flags only, no `--config`/`--db`/`--wait-for-lock`/`--confirm-bulk-change`).

**Test** (`test_registry.py`): (1) `{a.id for a in REGISTRY}` equals the set of `library-*` command names registered on the library Typer app (introspect `app.registered_commands`, deriving each CLI name from `command.name` or the kebab-cased function name) — catches drift when a command is added/removed, and is immune to `__all__` staleness. (2) All `id` values are unique. (3) Every `options[].name` is a valid CLI flag for its command (grep the source module). (4) Every `risk='destructive'` entry has `dry_run='supported'` (backend-enforced invariant).

### 1.3 — Canonical serialization (`feat(maint-dash): add canonical options_json serializer`)

**Files:**

- Modify: `personalscraper/web/maintenance/registry.py` (add helper function)
- Create: `tests/unit/web/maintenance/test_options_serialization.py`

**Function**:

```python
def canonical_options_json(options: dict[str, object]) -> str:
    """Serialize validated options to canonical JSON (sorted keys, no spaces)."""
    return json.dumps(options, sort_keys=True, separators=(",", ":"))
```

**Test**: verify `{"b": 1, "a": 2}` → `{"a":2,"b":1}` (sorted keys). Verify empty dict → `{}`. Verify nested structures sort recursively. The canonical form is what `POST .../run` stores in `options_json` and what the 428 precondition queries compare by string equality.
