# Phase 12 — Migration Notify + Cleanup

## Gate

**Prerequisites**: Phase 11 complete. All new providers and trackers implemented. Only `notifier.py` remains to migrate.

## Goal

Migrate `notifier.py` (120 LOC) → `api/notify/`. Final cleanup: residual imports, dead config, stale docs, ROADMAP update.

## Sub-phases

### 12.1 — Create `api/notify/` package + `_base.py`

**Files**:

- `personalscraper/api/notify/__init__.py`
- `personalscraper/api/notify/_base.py`

Contains `Notifier` Protocol and `HealthChecker` Protocol (from DESIGN §7.1).

**Commit**: `feat(api-unify): add notify package with base protocols`

### 12.2 — Create `api/notify/telegram.py`

Migrate `TelegramNotifier` from `notifier.py`:

- `REQUIRED_CREDS = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]`
- Replace `requests.post` → `HttpTransport` with `NoAuth` (Telegram uses token in URL)
- Keep fail-soft behavior (never raises)
- Implement `Notifier` Protocol

**Commit**: `refactor(api-unify): migrate Telegram notifier to api/notify/`

### 12.3 — Create `api/notify/healthchecks.py`

Migrate `ping_healthcheck` from `notifier.py`:

- `REQUIRED_CREDS = ["HEALTHCHECK_PING_URL"]`
- Replace `requests.get` → `HttpTransport`
- Keep fail-soft behavior

**Commit**: `refactor(api-unify): migrate healthchecks to api/notify/`

### 12.4 — Update consumers + delete `notifier.py`

```bash
rg "from personalscraper.notifier import" personalscraper/ --files-with-matches
rg "from personalscraper import notifier" personalscraper/ --files-with-matches
```

Update all import sites. Delete `notifier.py`.

**Commit**: `refactor(api-unify): delete notifier.py`

### 12.5 — Final cleanup

**Residual import check** — verify zero references to deleted modules:

```bash
for old in "scraper.tmdb_client" "scraper.tvdb_client" "scraper.circuit_breaker" "scraper.http_retry" "ingest.qbit_client" "notifier"; do
  echo -n "$old: "; rg "$old" personalscraper/ --files-with-matches | wc -l
done
# Expected: 0 for all
```

**Dead config audit** — remove any config fields referencing old module paths.

**Doc update** — update `docs/reference/architecture.md` with new `api/` package tree. Update `CLAUDE.md` reference index if needed. Archive docs (`docs/archive/`) NOT modified.

**ROADMAP update** — add torr9 + digitalcore entry (from DESIGN §13).

**Commit**: `refactor(api-unify): final cleanup — dead imports, config, docs`

### 12.6 — Phase 12 gate (final)

```bash
make check && python3 scripts/check-module-size.py
make lint && make test
python -c "import personalscraper"
```

Verify all 6 old modules are gone, all 8 docs exist, all 5 config templates exist.

**Commit**: `chore(api-unify): phase 12 gate — notify migration + cleanup done, feature complete`
