# Phase 2 — Config Infra + Activation

**Type**: infra
**Goal**: Wire 5 new config files, Pydantic models, `ProviderActivation`, and update `init-config`.

## Gate (prereq)

Phase 1 complete. `api/_contracts.py`, `api/_units.py`, `api/transport/` exist and pass `make check`.

## Sub-phases

### 2.1 — Pydantic models — `personalscraper/conf/models/api_config.py`

Create models for the 5 config files (DESIGN §8.2–§8.6). Implement:

- `MetadataProviderConfig`, `MetadataPriorities`, `MetadataDefaults`, `MetadataConfig`.
- `TorrentClientEntry`, `TorrentConfig` (with `active: str`).
- `TrackerProviderConfig`, `TrackerConfig`.
- `ThresholdEntry`, `RankingCriterion`, `RankingBonuses`, `RankingConfig`.
- `NotifyProviderConfig`, `NotifyConfig`.

Create `personalscraper/api/tracker/__init__.py` and
`personalscraper/api/tracker/_ranking.py` in this phase even though tracker
providers land later. `personalscraper/conf/models/api_config.py` imports and
re-exports the ranking models so config validation and runtime ranking share one
source of truth.

`api/tracker/_ranking.py` validator:

```python
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from personalscraper.api._units import ByteSize


class ThresholdEntry(BaseModel):
    at: int
    score: int

    @field_validator("at", mode="before")
    @classmethod
    def _parse_at(cls, v):
        if isinstance(v, str):
            return ByteSize.parse(v).bytes
        if isinstance(v, ByteSize):
            return v.bytes
        return int(v)


class RankingCriterion(BaseModel):
    field: str
    weight: float = 1.0
    values: dict[str, int] | None = None
    thresholds: list[ThresholdEntry] | None = None
    prefer: Literal["higher", "lower"] | None = None


class RankingBonuses(BaseModel):
    freeleech: int = 10
    silverleech: int = 5


class RankingConfig(BaseModel):
    criteria: list[RankingCriterion] = Field(default_factory=list)
    bonuses: RankingBonuses = Field(default_factory=RankingBonuses)
    min_seeders: int = 1
```

Unit tests in `tests/unit/test_api_config_models.py`:

- `ThresholdEntry(at="1GB", score=10)` → `at == 1_000_000_000`.
- `ThresholdEntry(at=100, score=5)` → `at == 100`.
- `RankingConfig` round-trip from `config.example/ranking.json5`.

**Commit**: `feat(api-unify): add Pydantic models for api config`

### 2.2 — `api/_activation.py`

Implement DESIGN §8.7. `PROVIDER_CREDS` hardcoded dict (10 entries). `resolve_active(providers, family, env=None)` returns list of active provider names with WARNING-on-missing-creds behavior.

Default `env=None` → `os.environ`. Pass-through via parameter for testability.

Unit tests:

- `enabled=True` + creds present → in active list.
- `enabled=True` + creds missing → not in list, WARNING logged.
- `enabled=False` → not in list, no warning.
- Multiple required creds, partial missing → not active, WARNING with all missing names.

**Commit**: `feat(api-unify): add ProviderActivation with credential check`

### 2.3 — `config.example/` templates

Create 5 new files under `config.example/`:

- `metadata.json5` (DESIGN §8.2)
- `torrent.json5` (DESIGN §8.3)
- `tracker.json5` (DESIGN §8.4)
- `ranking.json5` (DESIGN §8.5) — uses `at: "1GB"` literal to validate parsing
- `notify.json5` (DESIGN §8.6)

Each file has top-of-file comments documenting which `.env` vars are required (mirroring DESIGN tables).

Default enablement in `config.example/`:

- Existing behavior-equivalent providers stay enabled: `tmdb`, `tvdb`, `qbittorrent`.
- New optional integrations stay disabled to avoid warning noise before credentials exist: `omdb`, `trakt`, `transmission`, `lacale`, `c411`, `telegram`, `healthchecks`.

**Commit**: `feat(api-unify): add config.example templates for api`

### 2.4 — Wire into top-level `Config`

Update `personalscraper/conf/models/config.py`:

- Add fields: `metadata: MetadataConfig`, `torrent: TorrentConfig`, `tracker: TrackerConfig`, `ranking: RankingConfig`, `notify: NotifyConfig`.

Update the JSON5 config loading path (`personalscraper/conf/loader.py`, and `personalscraper/conf/resolver.py` if the resolver owns overlay assembly):

- Load each new JSON5 file from `config/` directory.
- If a file is missing on first run → use Pydantic defaults (graceful — pipeline still runs without `tracker.json5` if user didn't enable trackers).
- Validate via Pydantic on load; surface clear error message on parse failure.

Do **not** add JSON5 config loading to `personalscraper/config.py`; that module is the `.env` / secrets settings loader and should stay secrets-only.

Update `personalscraper init-config` command:

- Generate the 5 new files from `config.example/` if missing.
- Idempotent: existing files NOT overwritten.

**Local-only step (NOT committed)**: directly adapt the active project `config/`
for this feature branch by setting providers intentionally exercised by the
rollout to `enabled: true` there, even if their `config.example` default is
`false`. `config/` is gitignored — these files are personal/machine-local and
must NOT be staged. This adaptation is separate from `config.example` so new
users do not get missing-credential warnings for integrations they have not
opted into.

**Commit**: `feat(api-unify): wire api config into Config loader and init-config`

### 2.5 — Phase 2 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.conf.models.api_config import MetadataConfig, TorrentConfig, TrackerConfig, RankingConfig, NotifyConfig"
python -c "from personalscraper.api._activation import resolve_active, PROVIDER_CREDS; assert len(PROVIDER_CREDS) == 10"
ls config.example/{metadata,torrent,tracker,ranking,notify}.json5
```

Run `personalscraper init-config` in a temp directory — verify all 5 new files created, Pydantic loads them.

**Commit**: `chore(api-unify): phase 2 gate — config infra done`
