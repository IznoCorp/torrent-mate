# Phase 02 — Backend Config API Routes

## Gate

- [ ] Phase 01 merged — `validate_candidate()` and `envfile` module importable
- [ ] `make test` green on current HEAD

## Goal

Expose the 9 config endpoints (DESIGN §4.2) on the guarded `/api/config/*` router, with Pydantic response models, sha256 preconditioning, atomic write+backup, restart-impact classification, and role gating.

Reference patterns: `personalscraper/web/routes/maintenance.py` (S3 route structure, guarded router), `personalscraper/web/routes/pipeline.py` (mutating endpoints with `X-Requested-With`).

## Sub-phases

### 2.1 — Response models (`personalscraper/web/routes/config_models.py`)

**Files**:

- Create: `personalscraper/web/routes/config_models.py`

**Models** (Pydantic v2, `extra="forbid"`):

```python
class FileInfo(BaseModel):
    name: str
    owned_keys: list[str]
    sha256: str
    mtime: float
    size: int
    shadowed_keys: list[str]  # keys overridden by local.json5

class FilesResponse(BaseModel):
    files: list[FileInfo]

class FileContent(BaseModel):
    name: str
    values: dict[str, Any]
    sha256: str
    shadowed_keys: list[str]

class SchemaResponse(BaseModel):
    schema: dict[str, Any]          # Config.model_json_schema()
    ownership: dict[str, str]       # {top_level_key → file}
    restart_impact: dict[str, bool] # {top_level_key → restart_required}

class PutRequest(BaseModel):
    values: dict[str, Any]
    base_sha256: str

class PutResponse(BaseModel):
    warnings: list[str]
    restart_required: bool

class ValidateRequest(BaseModel):
    file_name: str
    values: dict[str, Any]

class StatusResponse(BaseModel):
    role: str                    # "prod" | "staging"
    read_only: bool
    restart_required: bool
    stale_files: list[str]       # filenames whose sha256 changed since boot

class SecretEntry(BaseModel):
    key: str
    description: str
    is_set: bool

class SecretsResponse(BaseModel):
    secrets: list[SecretEntry]

class SecretsPutRequest(BaseModel):
    __root__: dict[str, str]     # {KEY: value, …} — keys must be in catalog

class RestartResponse(BaseModel):
    status: str                  # "scheduled"
```

**Guarantor notes (apply when implementing)**:

- `SecretsPutRequest` with `__root__` is Pydantic **v1** syntax — use `RootModel[dict[str, str]]` (v2).
- `SchemaResponse.schema` shadows the `BaseModel` namespace — name the field `json_schema` (or use an alias) to avoid the v2 shadow warning.
- The restart handler must NOT `time.sleep()` before responding — detach the delay (e.g. `subprocess.Popen(["sh", "-c", "sleep 0.5 && pm2 restart …"])` or a FastAPI `BackgroundTask`) so the 202 flushes first (DESIGN §4.2).

**Commit**: `feat(config-editor): add config route response models`

### 2.2 — Route handlers: read endpoints (`personalscraper/web/routes/config.py`)

**Files**:

- Create: `personalscraper/web/routes/config.py`

**Router**: `APIRouter(prefix="/api/config", tags=["config"])`

**Endpoints** (this sub-phase — GETs only):

| Route                          | Handler                   | Key logic                                                                                                                                  |
| ------------------------------ | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET /api/config/schema`       | `get_schema(request)`     | `Config.model_json_schema()` + ownership from loader overlays array + restart-impact static map. Cached on `request.app.state`.            |
| `GET /api/config/files`        | `get_files(request)`      | Iterate overlays array; per file: `sha256` of bytes, `os.stat`, shadowed keys from `local.json5`.                                          |
| `GET /api/config/files/{name}` | `get_file(name, request)` | `json5.load` the file, return values + sha256. 404 if name not in overlays.                                                                |
| `GET /api/config/status`       | `get_status(request)`     | Boot sha256 snapshots vs current disk sha256 → `stale_files` + `restart_required`. Read `PERSONALSCRAPER_WEB_ROLE` env (default `"prod"`). |

**Commit**: `feat(config-editor): add config read endpoints (schema, files, status)`

### 2.3 — Route handlers: write endpoints

**Files**:

- Modify: `personalscraper/web/routes/config.py` — add mutating handlers

**Endpoints**:

| Route                          | Handler                         | Key logic                                                                                                                                                                                                                                                                                   |
| ------------------------------ | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/config/validate`    | `validate_file(body, request)`  | Call `validate_candidate()` with single-file replacement. Return 200 `{warnings}` or 422 `{detail, loc}`. No disk write.                                                                                                                                                                    |
| `PUT /api/config/files/{name}` | `put_file(name, body, request)` | 403 if read-only role → 412 if `base_sha256` ≠ current file sha256 → call `validate_candidate()` → backup (`.backups/{name}.{utc}.json5`, prune to 10) → `json5.dumps` with header comment + atomic `os.replace` → 200 `{warnings, restart_required}`. Serialize writes via `asyncio.Lock`. |
| `GET /api/config/secrets`      | `get_secrets(request)`          | Parse `.env.example` via `read_env_catalog()`, check `.env` for `is_set`. Values never returned.                                                                                                                                                                                            |
| `PUT /api/config/secrets`      | `put_secrets(body, request)`    | 403 if read-only → allowlist keys against catalog → `write_env_keys()` → 200 `{restart_required: true}`.                                                                                                                                                                                    |
| `POST /api/config/restart-web` | `restart_web(request)`          | 403 if staging → 404 if `PERSONALSCRAPER_PM2_NAME` unset → `subprocess.Popen(["pm2", "restart", name])` after `time.sleep(0.5)` for response flush → 202.                                                                                                                                   |

**Commit**: `feat(config-editor): add config write, validate, secrets, and restart endpoints`

### 2.4 — Router registration + restart-impact map + architecture test

**Files**:

- Modify: `personalscraper/web/app.py` — `guarded_api.include_router(config_router)` after maintenance router
- Create: `tests/unit/web/routes/test_config.py` — route tests with mocked config dir, tmp paths
- Create: `tests/unit/web/routes/test_config_restart_impact.py` — architecture test

**Restart-impact static map** (in `config.py`):

```python
RESTART_IMPACT: dict[str, bool] = {
    "web": True, "paths": True, "indexer": True,
    # All others → False ("effective next run"):
    "disks": False, "categories": False, "custom_categories": False,
    "category_rules": False, "anime_rule": False, "genre_mapping": False,
    "staging_dirs": False, "library": False, "scraper": False,
    "ingest": False, "fuzzy_match": False, "trailers": False,
    "thresholds": False, "metadata": False, "providers": False,
    "torrent": False, "tracker": False, "ranking": False,
    "notify": False, "acquire": False, "watch_seed": False,
}
```

**Architecture test**: iterate `Config.model_fields` keys; every key must be in `RESTART_IMPACT` or the test fails. Unknown keys default to `True` at runtime (fail-safe), but the test enforces explicit classification for every known key.

**Router registration** (`app.py`, after maintenance router line):

```python
from personalscraper.web.routes.config import router as config_router
guarded_api.include_router(config_router)
```

**Commit**: `feat(config-editor): register config router + restart-impact map + arch test`

## Tests (cumulative, covered across sub-phases)

- **Models**: roundtrip serialization for each response/request model
- **Auth guard**: unauthenticated → 401 on every endpoint (inherited from `guarded_api`)
- **Staging 403s**: write endpoints return 403 when `PERSONALSCRAPER_WEB_ROLE=staging`
- **412 precondition**: PUT with wrong `base_sha256` → 412
- **422 error shape**: invalid values → 422 with Pydantic `loc` paths
- **Secrets never-echo**: response body + log capture — no secret values
- **Backup + atomic write**: write against tmp config dir, verify `.backups/` file exists, old file replaced
- **Restart endpoint**: mock `subprocess.Popen`, verify pm2 restart command
- **Restart-impact architecture test**: every `Config.model_fields` key classified

## Coherence gate → Phase 3

- [ ] All 9 endpoints return documented shapes
- [ ] `make test` green — config route tests pass with tmp dirs (no real `config/` in CI)
- [ ] `make lint` green
- [ ] `curl -s http://localhost:8710/api/config/schema | jq ".ownership | keys | length"` returns 28
