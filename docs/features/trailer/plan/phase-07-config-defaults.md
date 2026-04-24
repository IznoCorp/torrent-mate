# Phase 7 — Config schema via Pydantic defaults

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

> **Scope note (v0.7.0)**: only filters actually wired in phases 3a/3b/6/8 are included in
> `TrailersConfig`. Advanced filters (duration bounds, official-channel preference, custom
> TMDB video filters, explicit `max_resolution` knob) are documented in DESIGN §9 but
> deferred to v0.8.0. This prevents dead config keys that users set without effect.
>
> Concretely, v0.7.0 KEEPS: `filters.min_file_size_bytes`, `filters.max_filesize_mb`,
> `filters.allowed_extensions`, `youtube_api.cache_ttl_days`.
>
> v0.7.0 REMOVES (deferred to v0.8.0): `fallback_youtube_search` (YouTube API 403 fallback
> stays on by design, no knob), `filters.min_duration_sec`, `filters.max_duration_sec`,
> `filters.prefer_official_channels`, `filters.max_resolution` (yt-dlp `format` string
> already caps at 1080p), `tmdb_video_filters` (the `_best_video` helper hard-codes
> `site == "YouTube"` + Trailer/Teaser preference; acceptable for v0.7.0).

**Goal:** Implement DESIGN §9 (Configuration split). Add `TrailersConfig` Pydantic model
to `personalscraper/conf/models.py` with `Field(default_factory=...)` so that omitting the
`trailers` section in `config.json5` yields sensible defaults with `enabled: false`. Update
`Config` to include `trailers: TrailersConfig`. Update `.env.example` with
`YOUTUBE_API_KEY`, `YOUTUBE_COOKIES_FILE`, and `YOUTUBE_COOKIES_FROM_BROWSER`. Verify that
configs without a `trailers` block parse cleanly.

**Ordering note**: Phase 7 (config) lands **before** Phase 8 (CLI) so the CLI can consume
`cfg.trailers.*` at runtime without mocks. The previous draft had the order reversed; it
was flipped after plan review flagged that the CLI tests passed only because `MagicMock`
masked the missing config schema — runtime execution would have crashed.

**Architecture:** `TrailersConfig` uses nested Pydantic models for `placement`, `filters`,
`circuit_breakers` (two distinct breakers: `tmdb_videos` + `youtube`), `youtube_api`, and
`ytdlp`. All fields have defaults. `Config` gets a new field
`trailers: TrailersConfig = Field(default_factory=TrailersConfig)`.

**Tech Stack:** Python, Pydantic v2, `pytest`.

---

## Gate (entry condition)

Phase 6 must be complete (orchestrator is importable — its config consumption shape is what
this phase locks in).

```bash
python -c "from personalscraper.trailers.orchestrator import TrailersOrchestrator; print('OK')"
```

---

## Dependencies

- Phase 6 (`TrailersOrchestrator` — its config-attribute access points define the schema
  shape this phase freezes)

---

## Invariants for this phase

- Existing `tests/conf/` tests and `tests/test_config.py` must pass without modification.
- A `config.json5` without a `trailers` section loads cleanly (`Config` parses without error).
- `Config.trailers.enabled` defaults to `False` — the feature is opt-in.
- No `init-config` migration code added (DESIGN §9 explicitly calls this out as out of scope).

---

## Sub-phase 7.1 — `TrailersConfig` nested models

### Files

| Action | Path                             | Responsibility                                    |
| ------ | -------------------------------- | ------------------------------------------------- |
| Modify | `personalscraper/conf/models.py` | Add TrailersConfig + nested models + Config field |

### Step 1: Write failing tests

Add to `tests/conf/test_models.py` (or `tests/test_config.py` — whichever covers conf models):

```python
# Tests to ADD to the existing config test file:

def test_trailers_config_defaults_to_disabled():
    """TrailersConfig defaults to enabled=False when not present in config.json5."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.enabled is False

def test_config_without_trailers_section_is_valid(tmp_path):
    """Config without a trailers block parses cleanly (enabled=False by default)."""
    import pyjson5
    cfg_file = tmp_path / "config.json5"
    # Minimal valid config without trailers section
    cfg_file.write_text(
        '{ disks: [], categories: {}, paths: { staging_dir: "/tmp" } }',
        encoding="utf-8",
    )
    from personalscraper.conf.loader import load_config
    config = load_config(cfg_file)
    assert config.trailers.enabled is False

def test_trailers_config_languages_default():
    """TrailersConfig.languages defaults to ['fr-FR', 'en-US']."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.languages == ["fr-FR", "en-US"]

def test_trailers_config_retry_after_days_default():
    """TrailersConfig.retry_after_days defaults to [1, 7, 30]."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.retry_after_days == [1, 7, 30]

def test_trailers_config_state_file_default():
    """TrailersConfig.state_file defaults to '.data/trailers_state.json'."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.state_file == ".data/trailers_state.json"

def test_trailers_placement_defaults():
    """TrailersPlacementConfig uses the flat convention for movies AND TV."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    # Flat `{folder}/{name}-trailer.{ext}` — compatible with Plex + Kodi + Jellyfin.
    # Extension is dynamic (yt-dlp may deliver mp4/mkv/webm) so the pattern has no hardcoded suffix.
    assert cfg.placement.movie_pattern == "{folder}/{name}-trailer.{ext}"
    assert cfg.placement.tvshow_pattern == "{folder}/{name}-trailer.{ext}"

def test_trailers_filters_defaults():
    """TrailersFiltersConfig defaults match DESIGN §9 spec (v0.7.0 minimal set).

    Advanced filters (duration bounds, official-channel preference, max_resolution,
    tmdb_video_filters) are deferred to v0.8.0 — see the Scope note at the top of
    this phase.
    """
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.filters.min_file_size_bytes == 102400
    assert cfg.filters.max_filesize_mb == 500
    # Allowed extensions drive the Phase 8 `verify` subcommand's extension check.
    assert set(cfg.filters.allowed_extensions) == {"mp4", "mkv", "webm"}

def test_trailers_ytdlp_defaults():
    """TrailersYtdlpConfig defaults match DESIGN §9 spec (1080p cap + fallback search).

    `fallback_youtube_search` was removed in v0.7.0 — the YouTube API 403 → yt-dlp
    fallback is always on. Only `default_search = "ytsearch1"` remains configurable.
    """
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert "height<=1080" in cfg.ytdlp.format
    assert cfg.ytdlp.socket_timeout_sec == 30
    assert cfg.ytdlp.retries == 3
    # yt-dlp fallback search is used when YOUTUBE_API_KEY is absent or quota is exhausted.
    assert cfg.ytdlp.default_search == "ytsearch1"

def test_trailers_two_circuit_breakers():
    """Two distinct breakers prevent YouTube failures from tripping TMDB."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.circuit_breakers.tmdb_videos.errors_threshold == 5
    assert cfg.circuit_breakers.tmdb_videos.cooldown_sec == 1800
    assert cfg.circuit_breakers.youtube.errors_threshold == 5
    assert cfg.circuit_breakers.youtube.cooldown_sec == 3600

def test_trailers_youtube_api_defaults():
    """YouTube Data API v3 quota accounting defaults."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.youtube_api.daily_quota_units == 10_000
    assert cfg.youtube_api.search_list_cost_units == 100
    assert cfg.youtube_api.cache_ttl_days == 7

def test_trailers_bot_detected_bounded_retry():
    """Bounded bot_detected retry prevents infinite YouTube spam on age-restricted content."""
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.bot_detected_max_consecutive_attempts == 5


def test_trailers_config_has_seasons_default_disabled():
    """DESIGN §4 extension: season-level trailer download is opt-in (default off).

    Most shows lack TMDB season-level trailers; enabling by default would spam
    YouTube searches that return nothing.
    """
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.seasons.enabled is False
    assert cfg.seasons.language_fallback is None
    assert cfg.seasons.search_query_format == "{title} {year} saison {season} bande annonce"


def test_trailers_config_check_library_default_true():
    """DESIGN §8 extension: library-aware idempotence is on by default.

    Prevents re-downloading trailers for media that already exists on one of
    the storage disks (e.g. a new episode of an already-shelved show).
    """
    from personalscraper.conf.models import TrailersConfig
    cfg = TrailersConfig()
    assert cfg.check_library_before_download is True
```

### Step 2: Run failing tests

```bash
pytest tests/ -k "trailers_config" -v 2>&1 | head -20
```

Expected: `ImportError` (models not defined yet).

### Step 3: Implement nested models in `personalscraper/conf/models.py`

Add the following classes **before** the main `Config` class. All use `_StrictModel`
(the existing strict base that forbids extra fields).

**Signature table:**

| Class                           | Key fields (all with defaults)                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TrailersPlacementConfig`       | `movie_pattern: str` (`"{folder}/{name}-trailer.{ext}"`), `tvshow_pattern: str` (same — flat convention)                                                                                                                                                                                                                                                                                          |
| `TrailersFiltersConfig`         | `min_file_size_bytes: int` (102400), `max_filesize_mb: int` (500), `allowed_extensions: list[str]` (`["mp4", "mkv", "webm"]`) — v0.7.0 minimal set; advanced filters deferred to v0.8.0                                                                                                                                                                                                           |
| `TrailersCircuitBreakerConfig`  | `errors_threshold: int`, `cooldown_sec: int`                                                                                                                                                                                                                                                                                                                                                      |
| `TrailersCircuitBreakersConfig` | `tmdb_videos: TrailersCircuitBreakerConfig`, `youtube: TrailersCircuitBreakerConfig` (two distinct instances per DESIGN §1)                                                                                                                                                                                                                                                                       |
| `TrailersYoutubeApiConfig`      | `daily_quota_units: int` (10 000), `search_list_cost_units: int` (100), `cache_ttl_days: int` (7)                                                                                                                                                                                                                                                                                                 |
| `TrailersYtdlpConfig`           | `format: str` (1080p cap), `socket_timeout_sec`, `retries`, `default_search: str` (`"ytsearch1"`)                                                                                                                                                                                                                                                                                                 |
| `TrailersSeasonsConfig`         | `enabled: bool` (False, opt-in per DESIGN §4), `language_fallback: list[str] \| None` (None → inherit `TrailersConfig.languages`), `search_query_format: str` (`"{title} {year} saison {season} bande annonce"`)                                                                                                                                                                                  |
| `TrailersConfig`                | `enabled`, `languages`, `search_query_format`, `placement`, `filters`, `state_file`, `retry_after_days`, `bot_detected_max_consecutive_attempts: int` (5), `library_scan_max_age_hours`, `circuit_breakers: TrailersCircuitBreakersConfig`, `youtube_api: TrailersYoutubeApiConfig`, `ytdlp`, `seasons: TrailersSeasonsConfig`, `check_library_before_download: bool` (True, DESIGN §8 extension) |

All defaults match exactly the values in DESIGN §9.

**Ordering note (critical — Python evaluates `Field(default_factory=ClassName)` at class
definition time):** declare leaves-first, then composites, so every class is defined
before any `default_factory=` reference to it. Order used below (top → down):
`TrailersCircuitBreakerConfig` → `TrailersCircuitBreakersConfig` → `TrailersFiltersConfig`
→ `TrailersYoutubeApiConfig` → `TrailersYtdlpConfig` → `TrailersPlacementConfig` →
`TrailersConfig`.

```python
class TrailersCircuitBreakerConfig(_StrictModel):
    """One circuit breaker config (per external service)."""
    errors_threshold: int = 5
    cooldown_sec: int = 1800


class TrailersCircuitBreakersConfig(_StrictModel):
    """Two independent breakers: one per external service.

    A YouTube outage must never trip the TMDB breaker used by the rest of the
    scraper (and vice-versa).
    """
    tmdb_videos: TrailersCircuitBreakerConfig = Field(
        default_factory=lambda: TrailersCircuitBreakerConfig(
            errors_threshold=5, cooldown_sec=1800,
        )
    )
    youtube: TrailersCircuitBreakerConfig = Field(
        default_factory=lambda: TrailersCircuitBreakerConfig(
            errors_threshold=5, cooldown_sec=3600,
        )
    )


class TrailersFiltersConfig(_StrictModel):
    """v0.7.0 minimal filter set.

    Advanced filters (duration bounds, prefer_official_channels, max_resolution,
    tmdb_video_filters) are deferred to v0.8.0 — see the Scope note at the top
    of this phase. Each key below is wired into a concrete consumer phase:

    - ``min_file_size_bytes``: ``has_existing_trailer`` skip check (phases 3c/6/8).
    - ``max_filesize_mb``: passed into yt-dlp opts (phase 3b Steps 4/5) as
      ``"max_filesize": max_filesize_mb * 1024 * 1024``.
    - ``allowed_extensions``: extension check in the ``verify`` subcommand (phase 8).
    """
    min_file_size_bytes: int = 102400
    max_filesize_mb: int = 500
    allowed_extensions: list[str] = Field(
        default_factory=lambda: ["mp4", "mkv", "webm"]
    )


class TrailersYoutubeApiConfig(_StrictModel):
    daily_quota_units: int = 10_000
    search_list_cost_units: int = 100
    # Consumed by trailers_cache in phase 3a: TTL = cache_ttl_days * 24 * 3600.
    cache_ttl_days: int = 7


class TrailersYtdlpConfig(_StrictModel):
    format: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    socket_timeout_sec: int = 30
    retries: int = 3
    default_search: str = "ytsearch1"


class TrailersPlacementConfig(_StrictModel):
    movie_pattern: str = "{folder}/{name}-trailer.{ext}"
    tvshow_pattern: str = "{folder}/{name}-trailer.{ext}"


class TrailersSeasonsConfig(_StrictModel):
    """Opt-in season-level trailer download (DESIGN §4 extension).

    Default off — most shows lack TMDB season-level trailers, so enabling by
    default would spam YouTube searches that return nothing. The path
    convention is fixed (see ``placement.trailer_path_for_season``); only
    discovery knobs are exposed here.

    Attributes:
        enabled: Master switch. Default ``False``.
        language_fallback: Optional override for the language order used when
            calling TMDB ``/tv/{id}/season/{N}/videos``. When ``None``, the
            top-level ``TrailersConfig.languages`` list is reused.
        search_query_format: YouTube fallback query template. Available
            placeholders: ``{title}``, ``{year}``, ``{season}``.
    """

    enabled: bool = False
    language_fallback: list[str] | None = None
    search_query_format: str = "{title} {year} saison {season} bande annonce"


class TrailersStepConfig(_StrictModel):
    """Operational safeguards for the pipeline step (DESIGN §12)."""
    max_duration_sec: int = 1800  # 30-minute step-level budget


class TrailersPipelineConfig(_StrictModel):
    """Defaults for pipeline-level flags. CLI flags take precedence at runtime."""
    skip: bool = False
    continue_on_error: bool = False


class TrailersConfig(_StrictModel):
    enabled: bool = False
    languages: list[str] = Field(default_factory=lambda: ["fr-FR", "en-US"])
    search_query_format: str = "{title} {year} bande annonce"
    placement: TrailersPlacementConfig = Field(default_factory=TrailersPlacementConfig)
    filters: TrailersFiltersConfig = Field(default_factory=TrailersFiltersConfig)
    state_file: str = ".data/trailers_state.json"
    retry_after_days: list[int] = Field(default_factory=lambda: [1, 7, 30])
    bot_detected_max_consecutive_attempts: int = 5
    library_scan_max_age_hours: int = 24
    circuit_breakers: TrailersCircuitBreakersConfig = Field(
        default_factory=TrailersCircuitBreakersConfig
    )
    youtube_api: TrailersYoutubeApiConfig = Field(
        default_factory=TrailersYoutubeApiConfig
    )
    ytdlp: TrailersYtdlpConfig = Field(default_factory=TrailersYtdlpConfig)
    step: TrailersStepConfig = Field(default_factory=TrailersStepConfig)
    pipeline: TrailersPipelineConfig = Field(default_factory=TrailersPipelineConfig)
    # DESIGN §4 extension: opt-in season-level trailer discovery.
    seasons: TrailersSeasonsConfig = Field(default_factory=TrailersSeasonsConfig)
    # DESIGN §8 extension: library-aware idempotence — consult library.scanner
    # before any discovery call to avoid re-downloading trailers that already
    # exist on one of the storage disks. Default ON.
    check_library_before_download: bool = True
```

**Class ordering reminder**: declare `TrailersStepConfig`, `TrailersPipelineConfig`, and
`TrailersSeasonsConfig` BEFORE `TrailersConfig` (alongside the other leaf classes — same
reason as other nested configs: `Field(default_factory=X)` needs `X` defined).

**Wiring note for consumer phases** (ensures no dead config keys):

- **Phase 3a (`trailers_cache`)**: replace any module-level `_YOUTUBE_TTL_SECONDS`
  constant with a runtime read of
  `config.trailers.youtube_api.cache_ttl_days * 24 * 3600`.
- **Phase 3a (`trailer_finder`)**: when handling season-level ScanItems, read
  `config.trailers.seasons.language_fallback` (falling back to
  `config.trailers.languages` if `None`). Use
  `config.trailers.seasons.search_query_format` for the YouTube fallback search query
  (placeholders: `{title}`, `{year}`, `{season}`).
- **Phase 3b (`ytdlp_downloader`)**: in the opts dict built by `download()` (Steps 4/5),
  add `"max_filesize": config.trailers.filters.max_filesize_mb * 1024 * 1024`.
- **Phase 6 (orchestrator)**: read `config.trailers.check_library_before_download`
  to enable/disable the library-aware SOT recheck. Read
  `config.trailers.seasons.enabled` to decide whether the scanner emits per-season
  `ScanItem`s in addition to show-level ones.
- **Phase 8 (`trailers verify`)**: use `config.trailers.filters.allowed_extensions` for
  the extension check instead of a hardcoded `{"mp4", "mkv", "webm"}` set.

### Step 4: Add `trailers` field to `Config`

In the existing `Config` model, add:

```python
trailers: TrailersConfig = Field(default_factory=TrailersConfig)
```

### Step 5: Run tests — all must pass

```bash
pytest tests/ -k "trailers_config or config" -v
```

Also verify the full config test suite and existing conf tests:

```bash
pytest tests/conf/ tests/test_config.py -q
```

### Step 6: Commit sub-phase 7.1

```bash
git add personalscraper/conf/models.py
git commit -m "feat(trailer): add TrailersConfig Pydantic model with sensible defaults"
```

---

## Sub-phase 7.2 — Update `.env.example`

### Files

| Action | Path           | Responsibility              |
| ------ | -------------- | --------------------------- |
| Modify | `.env.example` | Add YouTube cookie env vars |

### Step 1: Locate `.env.example`

```bash
ls "$(git rev-parse --show-toplevel)/.env.example"
```

### Step 2: Add YouTube env vars (append to existing file)

Add after any existing TMDB key entries:

```
# YouTube Data API v3 key (primary trailer search path).
# Leave blank to fall back to yt-dlp `ytsearch1` (slower, no quota). The primary path
# costs 100 quota units per search.list call (default daily quota = 10 000 units).
YOUTUBE_API_KEY=

# YouTube cookies for yt-dlp bot-detection bypass (optional)
# Option A: static Netscape-format cookies.txt (must be on APFS-native storage, mode 600)
YOUTUBE_COOKIES_FILE=
# Option B: live extraction from a browser profile
# Valid values: firefox, chrome, chromium, edge, opera, brave, safari
YOUTUBE_COOKIES_FROM_BROWSER=
```

### Step 3: Commit sub-phase 7.2

```bash
git add .env.example
git commit -m "docs(trailer): add YouTube cookie env vars to .env.example"
```

---

## Phase 7 quality gate

- [ ] `pytest tests/conf/ tests/test_config.py -q` — all green, no regressions
- [ ] `python -m ruff check personalscraper/conf/models.py` — no errors
- [ ] `python -m mypy personalscraper/conf/models.py` — no type errors
- [ ] `python -c "from personalscraper.conf.models import TrailersConfig; c=TrailersConfig(); print(c.enabled)"` prints `False`

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/conf/ tests/test_config.py -q
python -m ruff check personalscraper/conf/models.py
python -m mypy personalscraper/conf/models.py
python -c "from personalscraper.conf.models import TrailersConfig; c=TrailersConfig(); print(c.enabled)"
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 07 gate — TrailersConfig Pydantic defaults + .env.example update"
```

## Exit condition for Phase 8

Phase 8 may start only when:

- `from personalscraper.conf.models import TrailersConfig` works
- `TrailersConfig().enabled is False`
- All conf/config tests pass
- The milestone commit is on the branch
