# Phase 1 — Backend skeleton

## Gate

- Branch `feat/tm-shell` exists, `IMPLEMENTATION.md` header initialized
- `DESIGN.md` is on the branch at `docs/features/tm-shell/DESIGN.md`
- `make lint && make test` pass on the current HEAD (baseline `b24eabfa`)
- Python 3.12.4, pyenv active; Redis running (`redis-cli ping` → `PONG`)

## Sub-phases

### 1.1 — Config model + Settings secrets + config files

**Commit**: `chore(tm-shell): add web config model + Settings secrets`

**Files**:

| Action | Path                                      |
| ------ | ----------------------------------------- |
| Create | `personalscraper/conf/models/web.py`      |
| Modify | `personalscraper/conf/models/__init__.py` |
| Modify | `personalscraper/config.py`               |
| Create | `config.example/web.json5`                |
| Create | `config/web.json5`                        |
| Modify | `.env.example`                            |

**Work**:

1. `conf/models/web.py` — Pydantic `WebConfig(BaseModel, extra='forbid')` with
   fields per DESIGN §4.3: `enabled`, `host`, `port`, `username`, `redis_url`,
   `stream_key`, `stream_maxlen`, `session_ttl_hours`, `cookie_secure`,
   `dev_mode`. Re-export via `conf/models/__init__.py`.
2. `Config` model (`conf/models/config.py`) — add `web: WebConfig` field.
3. `personalscraper/config.py` `Settings` — add `WEB_PASSWORD_HASH: str = ""`
   and `WEB_JWT_SECRET: str = ""`; register both in `_SECRET_FIELDS`.
4. `config.example/web.json5` + `config/web.json5` — contents per DESIGN §4.3.
5. `.env.example` — add `WEB_PASSWORD_HASH=` + `WEB_JWT_SECRET=` lines.

**Verification**: `python -c "from personalscraper.conf.models.web import
WebConfig; print(WebConfig())"` succeeds; `python -c "from personalscraper.config
import Settings; print(Settings._SECRET_FIELDS)"` shows both new keys.

### 1.2 — FastAPI app factory + health/version/static

**Commit**: `feat(tm-shell): create FastAPI app with health and version routes`

**Files**:

| Action | Path                                     |
| ------ | ---------------------------------------- |
| Create | `personalscraper/web/__init__.py`        |
| Create | `personalscraper/web/app.py`             |
| Create | `personalscraper/web/deps.py`            |
| Create | `personalscraper/web/routes/__init__.py` |
| Create | `personalscraper/web/routes/health.py`   |
| Create | `personalscraper/web/routes/version.py`  |
| Create | `personalscraper/web/static.py`          |
| Create | `personalscraper/web/static/.gitkeep`    |
| Modify | `pyproject.toml`                         |

**Work**:

1. Add deps to `pyproject.toml`: `fastapi`, `uvicorn[standard]`, `redis`, `PyJWT`.
   Dev: `httpx`, `fakeredis`. Run `pip install -e ".[dev]"`.
2. `web/__init__.py` — package docstring, re-export `create_app`.
3. `web/app.py` — `create_app(config, settings) → FastAPI`: mounts health/version
   routers, mounts static dir + SPA fallback.
4. `web/deps.py` — `get_web_config(request) → WebConfig`, `get_settings() → Settings`.
5. `web/routes/health.py` — `GET /api/health`: `{status: "ok", redis: bool, db: bool}`.
6. `web/routes/version.py` — `GET /api/version`: `{version, build_commit}`.
7. `web/static.py` — `StaticFiles` mount + `index.html` fallback for non-`/api`/`/ws`
   paths; reads `static/BUILD_COMMIT` at startup.
8. `web/static/.gitkeep` — gitignored dir placeholder (Vite fills at deploy time).

**Verification**: `python -c "from personalscraper.web.app import create_app;
from personalscraper.config import get_settings; from pathlib import Path;
app = create_app(None, get_settings())"` imports cleanly.

### 1.3 — `personalscraper web` command + PM2

**Commit**: `feat(tm-shell): add web daemon command and PM2 app`

**Files**:

| Action | Path                              |
| ------ | --------------------------------- |
| Create | `personalscraper/commands/web.py` |
| Modify | `personalscraper/cli.py`          |
| Modify | `ecosystem.config.js`             |

**Work**:

1. `commands/web.py` — patterned on `commands/watch.py`: `@command_with_telemetry("web")`,
   `@handle_cli_errors`; loads config + settings, `_build_app_context`, then
   `uvicorn.run(create_app(...), host=..., port=...)`. SIGTERM/SIGINT graceful
   shutdown. Refuses boot if `static/index.html` missing and not `dev_mode`.
2. `cli.py` — import `personalscraper.commands.web` at line ~117 (alongside other
   command imports).
3. `ecosystem.config.js` — add `torrentmate-web` app: `interpreter: "none"`,
   script → pyenv personalscraper shim, `args: "web"`, `autorestart: true`,
   `kill_timeout: 30000`, `env: { PYTHONUNBUFFERED: "1" }`, port in comment.

**Verification**: `personalscraper web --help` prints usage; PM2 app syntax valid
(`node -e "require('./ecosystem.config.js')"`).

### 1.4 — Tests

**Commit**: `test(tm-shell): add web backend skeleton tests`

**Files**:

| Action | Path                        |
| ------ | --------------------------- |
| Create | `tests/web/conftest.py`     |
| Create | `tests/web/test_health.py`  |
| Create | `tests/web/test_version.py` |
| Create | `tests/web/test_static.py`  |
| Create | `tests/web/test_cli.py`     |

**Work**:

1. `tests/web/conftest.py` — fixture `web_app` using TestClient against
   `create_app(test_config, test_settings)`; `test_config` via `Config()` with
   WebConfig defaults; `test_settings` via `Settings()`.
2. `test_health.py` — health route returns 200 + correct shape; Redis
   down→`redis: false`.
3. `test_version.py` — version route returns `version` + `build_commit` keys.
4. `test_static.py` — 404 on missing SPA; 200 with index when `dev_mode=true`.
5. `test_cli.py` — `personalscraper web --help` output, boot-refuse when
   `static/index.html` missing + `dev_mode=false`. MUST patch
   `personalscraper.conf.loader.load_config` (CI has no `config/`).

## Verification

```bash
make lint                    # ruff + mypy + check_logging — zero errors
make test                    # all tests pass, new web/ coverage ≥ 90%
python scripts/check-module-size.py  # no new violations
python -c "import personalscraper"   # smoke test
rg "old\.module\.path" tests/        # no stale imports (baseline check)
```

**Manual checks**:

- `personalscraper web` boots and serves `/api/health` (401 OK — no auth yet).
- PM2: `pm2 start ecosystem.config.js --only torrentmate-web && pm2 logs torrentmate-web`
  shows boot log, `pm2 stop torrentmate-web` clean shutdown.
