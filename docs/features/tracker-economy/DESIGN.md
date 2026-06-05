# RP2 — Per-Tracker Economy Config — Design

**Codename**: tracker-economy
**Type**: minor (0.22.0 → 0.23.0)
**ROADMAP**: Vague 1, RP2 (P1 prereq) — the only remaining P1 in the current wave.

## Purpose / Intent

Extend the per-tracker config — today **activation-only** (`TrackerProviderConfig.enabled`) —
with a per-tracker **economy** policy: a ratio policy + an announce-passkey reference. RP2 only
**carries** this data and provides one new primitive (an optional-secret resolver); it does **not**
measure ratio, enforce seed obligations, or consume the passkey. Those are downstream consumers in
Vague 5 (Ratio C1, Seed-Safety O2). Strikes the "no new config schema" non-goal of the
Additional-Trackers work, before torr9/digitalcore land.

## Scope (what RP2 delivers)

1. A new `TrackerEconomyConfig` Pydantic model, attached optionally to `TrackerProviderConfig`.
2. A humanized-duration parser for the seed-time fields.
3. A non-gating optional-secret mechanism in `api/_activation.py` for the announce passkey
   (`PROVIDER_OPTIONAL_SECRETS` map + `resolve_optional_secret()` helper).
4. Config files (`config.example/tracker.json5` + `config/tracker.json5` overlay) + `.env.example`
   - reference-doc updates.
5. Tests (schema validation, duration parsing, optional-secret resolution + non-gating proof,
   config-load integration).

## Non-Goals (explicit — guard against scope creep)

- **No ratio measurement** — that is Ratio C1 (Vague 5; frozen decision Q2: API → qBit-fallback cascade).
- **No seed-obligation enforcement / deletion authority** — that is Seed-Safety O2 (Vague 5).
- **No passkey consumption and no passkey-presence validation** — deferred to the first real
  consumer (Vague 5). RP2 provides the resolver primitive only; it has no caller yet.
- **No activation gating on the passkey** — a missing passkey must never deactivate a tracker nor
  fail boot (search/fetch authenticate via the API key / per-result JWT, not the passkey).
- Pure additive data-carrier. Pre-1.0 single instance → no back-compat shims; config + schema
  evolve in place (`config.example/` and the live `config/` overlay updated together).

## Frozen decisions (from the brainstorm)

| #   | Decision                      | Choice                                                                                                                                                                                                                                     |
| --- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | Ratio policy richness         | **Rich**: `target_ratio` + `min_ratio` + `min_seed_time` + `hit_and_run_grace`.                                                                                                                                                            |
| D2  | Passkey secret handling       | Env-driven, **not** in committed config. Registered in a new **non-gating** `PROVIDER_OPTIONAL_SECRETS` map.                                                                                                                               |
| D3  | Passkey home                  | Sibling map + `resolve_optional_secret()` in `_activation.py`; never consulted by `resolve_active()`.                                                                                                                                      |
| D4  | Duration representation       | **Humanized string** (`"72h"`, `"3d"`) parsed to **int seconds** at load (consistent with the `"1GB"` ranking-threshold ergonomics).                                                                                                       |
| D5  | `hit_and_run_grace` semantics | **Delay after download completion** during which an unmet seed obligation is **not yet** counted as a hit-and-run. After it elapses without meeting `min_ratio` **or** `min_seed_time`, O2 (later) treats the torrent as an H&R violation. |

## Components

### 1. Economy schema — `personalscraper/conf/models/api_config.py`

```python
class TrackerEconomyConfig(_StrictModel):
    """Per-tracker seeding economy. Data-carrier for Ratio C1 + Seed-Safety O2 (Vague 5).

    Attributes:
        target_ratio: Ratio Ratio-C1 loops toward. Required when economy is set. >= min_ratio.
        min_ratio: Floor below which a torrent must not be deleted (read by O2). Default 1.0.
        min_seed_time: Minimum seed obligation in seconds (read by O2). Humanized at load.
        hit_and_run_grace: Seconds after download completion before an unmet obligation
            becomes an H&R violation (read by O2). Humanized at load. Default 0 (no grace).
    """
    target_ratio: float
    min_ratio: float = 1.0
    min_seed_time: int          # seconds; field validator parses "72h"/"3d"
    hit_and_run_grace: int = 0  # seconds; field validator parses humanized strings

    # model_validator(after): target_ratio >= min_ratio; all values >= 0.
```

Attach optionally to the existing model:

```python
class TrackerProviderConfig(_StrictModel):
    enabled: bool = False
    economy: TrackerEconomyConfig | None = None   # None = no economy policy
```

`economy` is optional so a tracker can stay activation-only. `_StrictModel` keeps
extra-forbidden, so typos in the economy block are rejected at boot.

### 2. Duration parser

A small `parse_duration(value: str | int) -> int` helper (seconds), used as a Pydantic
`field_validator(mode="before")` on `min_seed_time` / `hit_and_run_grace`.

- Accepts `"<int><unit>"` with unit in `{s, m, h, d, w}` (e.g. `"72h"`, `"3d"`, `"90m"`).
- Accepts a bare int (already seconds) for forward flexibility.
- Rejects malformed input with a clear `ValueError` (surfaced at config-load).
- Home: a focused module (e.g. `conf/models/_duration.py`) — sibling to the ranking threshold
  parser pattern, kept tiny and independently testable.

### 3. Optional secret resolver — `personalscraper/api/_activation.py`

```python
PROVIDER_OPTIONAL_SECRETS: dict[str, list[str]] = {
    "lacale": ["LACALE_PASSKEY"],
    "c411": ["C411_PASSKEY"],
}

def resolve_optional_secret(provider: str, env: Mapping[str, str] = os.environ) -> dict[str, str | None]:
    """Resolve a provider's optional, non-activation-gating secrets from the environment.

    Unlike PROVIDER_CREDS (consumed by resolve_active to gate activation), an absent value
    here returns None and never deactivates the provider nor fails boot. Consumers (Vague 5
    Ratio/Seed-Safety) decide what to do with a missing passkey.
    """
```

**Invariant**: `resolve_active()` is unchanged and never reads `PROVIDER_OPTIONAL_SECRETS`. A
regression test pins that an enabled tracker with no passkey still resolves as active.

### 4. Config files + docs

- `config.example/tracker.json5`: add a commented `economy { target_ratio, min_ratio,
min_seed_time: "72h", hit_and_run_grace: "48h" }` example under a tracker, plus a comment
  documenting the `<TRACKER>_PASSKEY` env-var convention.
- `config/tracker.json5` (live overlay): add an `economy` block for the active tracker(s) (c411).
  Both files updated together (no overlay drift).
- `.env.example`: document `LACALE_PASSKEY`, `C411_PASSKEY` (commented, optional).
- Reference doc: document the economy schema + duration format + the optional-secret convention
  (in the relevant `docs/reference/` config/tracker doc).

### 5. Tests

- `TrackerEconomyConfig` validation: valid policy; `target_ratio < min_ratio` rejected; negative
  values rejected; `economy=None` accepted; extra field rejected.
- `parse_duration`: each unit, bare int, malformed rejected.
- `resolve_optional_secret`: present → value; absent → None; **`resolve_active` unaffected by a
  missing optional secret** (the non-gating proof).
- Config-load integration: a `tracker.json5` with an `economy` block parses into the typed model
  with humanized durations converted to seconds.

## Data flow

```
config/tracker.json5 ──load──▶ TrackerConfig.providers[<t>].economy  (typed, seconds)
                                       └─▶ [Vague 5: Ratio C1 reads target_ratio;
                                            Seed-Safety O2 reads min_ratio/min_seed_time/grace]
.env: <TRACKER>_PASSKEY ──resolve_optional_secret()──▶ [Vague 5: seeding/ratio consumers]
```

## Validation rules (boot-time, fail-loud)

- `target_ratio >= min_ratio` (else `ValueError` at load).
- `min_ratio >= 0`, `target_ratio >= 0`, `min_seed_time >= 0`, `hit_and_run_grace >= 0`.
- Durations: humanized parse or bare int; malformed → `ValueError`.
- `economy` optional; extra keys forbidden (`_StrictModel`).
- Passkey presence: **not** validated here (deferred).

## Acceptance criteria seeds (executable, per project convention)

- A `tracker.json5` with an `economy` block loads; `target_ratio < min_ratio` fails load with a
  clear message.
- `min_seed_time: "72h"` resolves to `259200` seconds in the typed model.
- An enabled tracker with no `*_PASSKEY` env var is still in `resolve_active()`'s active set
  (non-gating proof) while `resolve_optional_secret()` returns `{"<TRACKER>_PASSKEY": None}`.
- `make check` green.

## SemVer

Minor — additive config schema + new (uncalled) primitive, no breaking change. 0.22.0 → 0.23.0.
