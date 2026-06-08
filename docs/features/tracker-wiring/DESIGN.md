# RP5a — Wire the Tracker Registry into the Composition Root — Design

**Codename**: tracker-wiring
**Type**: minor (0.23.0 → 0.24.0)
**ROADMAP**: Vague 2, RP5a (P1 prereq) — first unstarted link on the critical path to RP5b
(the shared grab core, "gate de l'épopée"). Unblocks LaCale Deprecation.

## Purpose / Intent

The tracker provider registry (`TrackerRegistry`, `api/tracker/_registry.py`) is fully built and
unit-tested but **never instantiated in production** — its constructor takes a pre-built
`dict[str, TorrentSearchable]`, there is no factory, no boot validation, and `AppContext` carries
no tracker handle. Today the only live activation lever is the `tracker.json5 <t>.enabled` flag,
read by nothing.

RP5a closes this gap **at parity with the metadata registry**: a config-driven factory, fail-loud
boot validation, and a single handle on the frozen application context — so RP5b (the shared grab
core) and everything downstream (Follow, Ratio, Watcher) can consume a live, validated tracker
registry. RP5a **wires** the registry; it adds **no consumer** (no search call site) and **no
user-facing surface**.

Per the ROADMAP, wiring "absorbe le besoin de conteneur d'injection (le contexte porte le
registre)" and must be built "à parité avec le registre metadata … pour éviter une 2e voie
divergente".

## Scope (what RP5a delivers)

1. A **config-driven factory** — `api/tracker/_factory.py` (new) — that reads `config.tracker`,
   resolves active+credentialed trackers, builds each enabled tracker's `HttpTransport` + client,
   validates, and returns a populated `TrackerRegistry`. Layered **above** the existing
   pre-built-dict constructor (which stays intact).
2. **Fail-loud boot validation** with a severity tier (error | warning) — a tracker-local
   structured error in `api/tracker/_errors.py` mirroring `RegistryConfigError`'s aggregated-issue
   shape.
3. A single **`tracker_registry`** handle on the frozen `AppContext`, constructed in the one
   composition root (`cli_helpers/__init__.py::_build_app_context`) and released in
   `per_step_boundary`.
4. Tests (factory, validation severity split, composition-root integration) + ACCEPTANCE criteria
   (executable shell commands proving end-to-end boot wiring).

**No new config schema and no new `.env` keys** — `TrackerConfig`
(`providers{enabled, economy?}`, `priority`, `priority_by_media_type`, caps) and the
`LACALE_API_KEY`/`C411_API_KEY` credential map already exist. RP5a is pure consumption of existing
plumbing.

## Non-Goals (explicit — guard against scope creep)

- **No tracker consumer** — no search/rank call site. The first consumer is RP5b (shared grab
  core, Vague 3). RP5a wires the registry only; `search_all`/`rank`/the fetch bridge stay
  unwired.
- **No `info`/Web UI tracker-status surface** — registry observability is a distinct, later
  roadmap track (Web UI S6 "registry + health", S7 acquisition pages). Showing tracker status
  before any consumer would be a dial connected to nothing. Boot validation (fail-loud) is the
  observable proof that the wiring is live.
- **No LaCale deprecation / no `deprecated` warning case** — that is the **LaCale Deprecation**
  item (gated on RP5a). RP5a provides the severity tier _ready to host_ a future warning-level
  issue; it does not add a deprecated flag or deactivate LaCale.
- **No economy/passkey consumption** — `TrackerProviderConfig.economy` (RP2) and the announce
  passkey stay data-carriers until Vague 5 (Ratio C1, Seed-Safety O2). The factory keeps
  `config.tracker.providers` reachable for that future wiring but reads neither.
- **No new acquisition event** — the acquisition event catalogue is RP4's territory; emitting a
  `TrackerRegistryBootValidated` event would touch the pinned event count and the eager-import
  hub, which is out of scope. RP5a logs a structured boot line via structlog instead.
- **No change to the existing `TrackerRegistry.__init__` signature** — the factory is layered
  above it, preserving the 4 existing dict-ctor unit tests.
- Pre-1.0 single instance → no back-compat shims; `config.example/` and the live `config/`
  overlay evolve together if touched.

## Frozen decisions (from the brainstorm)

| #   | Decision                    | Choice                                                                                                                                                                                                                                                                             |
| --- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ①   | AppContext handle ownership | Own `tracker_registry` field — a **port** handle, peer of `provider_registry`/`torrent_client`. RP5c's "une seule poignée" rule governs the future `acquire/` **lobe** (a separate handle). No churn, no service-locator drift.                                                    |
| ②   | Constructor strategy        | **Factory layered above** the existing pre-built-dict `__init__` (new `api/tracker/_factory.py`). The dict ctor stays for tests; the factory is the single **production** construction path → no divergent second way where it matters.                                            |
| ③   | Boot-validation error type  | **Tracker-local** (`api/tracker/_errors.py`), same aggregated-issues shape as `RegistryConfigError`, caught at the composition root. Avoids an `api/tracker → api/metadata` cross-family import (the torrent precedent reuses it only at the root).                                |
| 1   | Boot-validation strictness  | **Unconditional + full fail-loud (Option A).** Registry built for every command that goes through the single composition root; raises on **any** tracker misconfig, including enabled-but-uncredentialed. Parity with metadata; default config (trackers disabled) boots silently. |
| 2   | Severity tier               | **Included in RP5a** (error \| warning) with ≥1 real RP5a warning case (`disabled_in_priority`). LaCale Deprecation later adds a `deprecated` warning with zero retrofit.                                                                                                          |
| 3   | Scope                       | **Pure wiring** — no `info`/Web UI surface; no consumer.                                                                                                                                                                                                                           |

## Components

### 1. Config-driven factory — `personalscraper/api/tracker/_factory.py` (new)

```python
def build_tracker_registry(
    tracker_config: TrackerConfig,
    ranking: RankingConfig,
    *,
    settings: Settings,
    event_bus: EventBus,
    cb_policy: CircuitPolicy,
    env: Mapping[str, str] | None = None,
) -> TrackerRegistry:
    """Build a live TrackerRegistry from config, at parity with the metadata registry.

    Mirrors api/torrent/_factory.py + api/metadata/registry/_factory.py:
      1. For each provider in tracker_config.providers:
           - enabled=False  → skipped (configured but off).
           - enabled=True   → resolve API key (PROVIDER_CREDS / env):
                                absent  → TrackerConfigIssue(error, missing_credentials); not built.
                                present → HttpTransport(<Client>.policy(api_key), event_bus, cb_policy)
                                          + <Client>(transport).
      2. Aggregate validation issues (see Component 2) over the built instances + config.
      3. Any error-severity issue → raise TrackerConfigError(issues).
         Else → log warnings (structlog), do not block.
      4. return TrackerRegistry(trackers=<built dict>, priority=tracker_config.priority,
                                ranking=ranking,
                                priority_by_media_type=tracker_config.priority_by_media_type)

    Raises:
        TrackerConfigError: if any error-severity issue is found (fail-loud at boot).
    """
```

- A name→class map (`{"lacale": LaCaleClient, "c411": C411Client}`) analogous to the metadata
  `PROVIDER_CLASSES` / torrent `build_client` indirection. Only `lacale`/`c411` exist today.
- Credential resolution reuses `api/_activation.PROVIDER_CREDS` + the `env=` injectable seam (so
  tests pass a fake env). It does **not** use `resolve_active`'s fail-soft skip — under Option A an
  enabled-but-uncredentialed tracker is an **error**, not a silent skip.
- `ranking` is pulled from `config.ranking` (separate from `config.tracker`), matching the
  existing `TrackerRegistry` constructor contract.
- The factory imports **no** `api/metadata` symbol (decision ③).

### 2. Boot validation + structured error — `personalscraper/api/tracker/_errors.py`

```python
@dataclass(frozen=True)
class TrackerConfigIssue:
    severity: Literal["error", "warning"]
    code: Literal["missing_credentials", "protocol_mismatch",
                  "unknown_provider", "disabled_in_priority"]
    provider: str | None
    message: str

class TrackerConfigError(TrackerError):
    """Aggregated, fail-loud tracker boot-config error (parity with RegistryConfigError).

    Carries every error-severity TrackerConfigIssue so the operator sees all problems at
    once (never fail-fast on the first). Raised at the composition root.
    """
    def __init__(self, issues: list[TrackerConfigIssue]) -> None: ...
```

Validation aggregates issues over the built instances + config:

**Errors (fatal — raise `TrackerConfigError`):**

- `missing_credentials` — tracker `enabled: true`, API key absent.
- `protocol_mismatch` — a built client fails `isinstance(client, TorrentSearchable)` (the
  `@runtime_checkable` capability Protocol).
- `unknown_provider` — a name in `priority` / `priority_by_media_type` **absent** from
  `providers` (config typo).

**Warning (logged, non-fatal):**

- `disabled_in_priority` — a name present in `providers` but `enabled: false`, referenced in
  `priority` / `priority_by_media_type`. **Emitted only when ≥1 tracker is active**, so the
  pristine default (all disabled → zero active) boots silently.

Not re-checked: `priority_by_media_type ⊆ providers.keys()` is already enforced at config-load by
`TrackerConfig` — no double-validation.

### 3. AppContext handle — `personalscraper/core/app_context.py`

```python
@dataclass(frozen=True)
class AppContext:
    config: Config
    settings: Settings
    event_bus: EventBus
    provider_registry: ProviderRegistry
    torrent_client: "QBitClient | TransmissionClient | None" = None
    tracker_registry: "TrackerRegistry | None" = None   # RP5a — own port handle
```

- Added with a `None` default → low blast radius for direct-construction test fixtures. In
  production `_build_app_context` always sets it to a real (possibly empty) registry, so it is
  never `None` at runtime.
- `TrackerRegistry` imported under `TYPE_CHECKING`.
- No change to `tests/architecture/test_app_context_boundary.py`: the AST allowlist governs
  functions that **take/build** `AppContext`, not its fields. No new module receives `AppContext`.

### 4. Composition-root wiring — `personalscraper/cli_helpers/__init__.py`

```python
# inside _build_app_context, after event_bus + cb_policy + provider_registry:
tracker_registry = build_tracker_registry(          # lazy import (CLI import-time hygiene)
    config.tracker, config.ranking,
    settings=settings, event_bus=event_bus, cb_policy=cb_policy,
)
return AppContext(..., tracker_registry=tracker_registry)
```

- `build_tracker_registry` is **lazily imported** (mirror the `ProviderRegistry` lazy import) so
  `--help`/`init-config` stay fast and network-light.
- `TrackerConfigError` surfaces here — the same boundary where `RegistryConfigError`
  (metadata/torrent) already surfaces → a uniform "invalid config = the app does not start"
  failure surface.
- `per_step_boundary`'s `finally` calls `app_context.tracker_registry.close()` next to
  `provider_registry.close()`.
- **`commands/info.py`** builds its own `ProviderRegistry` directly (a second construction site).
  RP5a routes its tracker concern through `_build_app_context` only; `info` is left untouched
  (it surfaces no tracker status — decision 3). Confirm in the plan that `info` still boots.

### 5. `TrackerRegistry.close()` — `personalscraper/api/tracker/_registry.py`

Add a `close()` that releases the `HttpTransport` instances the registry owns (parity with
`ProviderRegistry.close()`). The existing pre-built-dict `__init__` is otherwise **unchanged**.
An empty registry (no active trackers) closes cleanly as a no-op.

### 6. Tests

- **Factory / validation (unit)**: valid config (2 enabled+credentialed) → registry with 2
  trackers; enabled-no-key → `TrackerConfigError`/`missing_credentials`; unknown name in
  `priority` → `unknown_provider`; disabled-in-priority with ≥1 active → warning logged + boot OK;
  default all-disabled → empty registry, **no** warning emitted; a fake non-`TorrentSearchable`
  class → `protocol_mismatch`. Severity split: error raises, warning does not.
- **Composition-root integration**: `_build_app_context` populates `app_context.tracker_registry`;
  a bad tracker config raises at boot; `per_step_boundary` calls `close()`.
- **Regression guard**: the 4 existing `TrackerRegistry` dict-ctor tests stay green (factory is
  layered above, signature unchanged) — per CLAUDE.md "after any constructor signature change,
  grep tests/". (No signature change here, by design.)

## Data flow

```
config.tracker (providers{enabled,creds}, priority, priority_by_media_type)
config.ranking (RankingConfig)
.env: <T>_API_KEY ──┐
                    ▼
   build_tracker_registry(...)  ──validate(fail-loud)──▶ TrackerConfigError? ──raise at boot
                    │ ok
                    ▼
   TrackerRegistry(trackers, priority, ranking, …)
                    ▼
   AppContext.tracker_registry  ──[Vague 3: RP5b grab core reads it via the bundle]
```

## Validation rules (boot-time, fail-loud — Option A)

- Every **enabled** tracker must have its API key → else `error/missing_credentials`.
- Every built tracker must satisfy `TorrentSearchable` → else `error/protocol_mismatch`.
- Every `priority` / `priority_by_media_type` name must exist in `providers` → else
  `error/unknown_provider`.
- A present-but-disabled tracker referenced in priority, when ≥1 tracker is active →
  `warning/disabled_in_priority` (logged, non-fatal).
- Any error-severity issue → `TrackerConfigError` at the composition root → the app does not
  start (any command). Default config (all disabled) → empty registry, silent boot.

## Acceptance criteria seeds (executable, per project convention)

- A valid tracker config (an enabled tracker with its `*_API_KEY` set) → `personalscraper <cmd>`
  boots (exit 0) and `app_context.tracker_registry` contains that tracker.
- A tracker `enabled: true` with its `*_API_KEY` **unset** → `personalscraper <cmd>` exits non-zero
  at boot with a message naming the tracker and the missing credential (proves end-to-end wiring
  through the real composition root).
- The default config (both trackers disabled) → `personalscraper <cmd>` boots silently, no
  tracker warning, `tracker_registry` empty.
- A `priority` listing a present-but-disabled tracker, with one other tracker active → boots (exit 0) and logs a `disabled_in_priority` warning.
- `make check` green; the 4 pre-existing `TrackerRegistry` dict-ctor tests still pass.

## SemVer

Minor — additive runtime capability (config-driven factory + boot validation + composition-root
handle), no breaking change, no schema change. 0.23.0 → 0.24.0.
