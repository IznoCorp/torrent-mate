# Phase 2 — Config API

## Gate

**Prerequisites**: Phase 1 complete. `api/transport/` and `api/_contracts.py` exist and pass `make check`.

## Goal

Create 5 new config files + Pydantic models + `ProviderActivation` logic. Update `config.example/` so `init-config` generates them.

## Sub-phases

### 2.1 — Pydantic models for new config

Create `personalscraper/conf/models/api_config.py` with models for all 5 new config files:

```python
"""Pydantic models for api/ config files."""
from pydantic import BaseModel


class MetadataProviderConfig(BaseModel):
    enabled: bool = True

class MetadataPriorities(BaseModel):
    movie_scraping: dict[str, int] = {}
    series_scraping: dict[str, int] = {}
    episode_scraping: dict[str, int] = {}
    recommendations: dict[str, int] = {}
    notations: dict[str, int] = {}

class MetadataDefaults(BaseModel):
    language: str = "fr-FR"
    fallback_language: str = "en-US"
    prefer_local_title: bool = True

class MetadataConfig(BaseModel):
    providers: dict[str, MetadataProviderConfig] = {}
    priorities: MetadataPriorities = MetadataPriorities()
    defaults: MetadataDefaults = MetadataDefaults()

class TorrentClientEntry(BaseModel):
    enabled: bool = True
    host: str = "localhost"
    port: int = 8080

class TorrentConfig(BaseModel):
    active: str = "qbittorrent"
    clients: dict[str, TorrentClientEntry] = {}

class TrackerProviderConfig(BaseModel):
    enabled: bool = True

class TrackerConfig(BaseModel):
    providers: dict[str, TrackerProviderConfig] = {}
    priority: list[str] = []
    max_total_results: int = 50
    max_per_tracker: int = 30
    timeout_per_tracker: int = 15

class RankingCriterion(BaseModel):
    field: str
    weight: float = 1.0
    values: dict[str, int] | None = None
    thresholds: dict[str, int] | None = None
    prefer: str | None = None  # "higher" | "lower"

class RankingBonuses(BaseModel):
    freeleech: int = 10
    silverleech: int = 5

class RankingConfig(BaseModel):
    criteria: list[RankingCriterion] = []
    bonuses: RankingBonuses = RankingBonuses()

class NotifyProviderConfig(BaseModel):
    enabled: bool = True

class NotifyConfig(BaseModel):
    telegram: NotifyProviderConfig = NotifyProviderConfig()
    healthchecks: NotifyProviderConfig = NotifyProviderConfig()
```

**Commit**: `feat(api-unify): add Pydantic models for api config`

### 2.2 — Add `ProviderActivation` module

Create `personalscraper/api/_activation.py`:

```python
"""Provider activation: enabled toggle + credential presence check."""
import os
from personalscraper.logger import get_logger

log = get_logger("api.activation")

# Hardcoded per provider — credentials stay in .env
PROVIDER_CREDS: dict[str, list[str]] = {
    "tmdb":         ["TMDB_API_KEY"],
    "tvdb":         ["TVDB_API_KEY"],
    "omdb":         ["OMDB_API_KEY"],
    "trakt":        ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET"],
    "qbittorrent":  ["QBIT_USERNAME", "QBIT_PASSWORD"],
    "transmission": ["TRANSMISSION_USERNAME", "TRANSMISSION_PASSWORD"],
    "lacale":       ["LACALE_API_KEY"],
    "c411":         ["C411_API_KEY"],
    "telegram":     ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "healthchecks": ["HEALTHCHECK_PING_URL"],
}


def resolve_active(providers: dict, family: str) -> list[str]:
    """Return names of providers with enabled=true AND all creds in .env."""
    active = []
    for name, cfg in providers.items():
        if not cfg.enabled:
            continue
        required = PROVIDER_CREDS.get(name, [])
        missing = [c for c in required if not os.getenv(c)]
        if missing:
            log.warning("provider_disabled_missing_creds",
                        provider=name, family=family, missing=missing,
                        hint="Set credentials in .env or set enabled=false in config")
            continue
        active.append(name)
    return active
```

**Commit**: `feat(api-unify): add ProviderActivation with credential check`

### 2.3 — Create config.example/ files

Create 5 template files in `config.example/`:

- `config.example/metadata.json5` (from DESIGN §8.2)
- `config.example/torrent.json5` (from DESIGN §8.3)
- `config.example/tracker.json5` (from DESIGN §8.4)
- `config.example/ranking.json5` (from DESIGN §8.5)
- `config.example/notify.json5` (from DESIGN §8.6)

**Commit**: `feat(api-unify): add api config templates to config.example/`

### 2.4 — Wire into Config loading

Update `personalscraper/conf/models/config.py` to load new config files. Add fields to the top-level `Config` model:

- `metadata: MetadataConfig`
- `torrent: TorrentConfig`
- `tracker: TrackerConfig`
- `ranking: RankingConfig`
- `notify: NotifyConfig`

Update `personalscraper/config.py` to load these files from the `config/` directory.

**Commit**: `feat(api-unify): wire api config into Config loader`

### 2.5 — Phase 2 gate

```bash
make check && python3 scripts/check-module-size.py
python -c "from personalscraper.conf.models.api_config import MetadataConfig, TorrentConfig, TrackerConfig, RankingConfig, NotifyConfig"
python -c "from personalscraper.api._activation import resolve_active"
```

**Commit**: `chore(api-unify): phase 2 gate — config api done`
