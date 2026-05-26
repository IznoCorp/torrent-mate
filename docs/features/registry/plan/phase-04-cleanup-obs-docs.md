# Phase 4 — Cleanup, observability, docs

> **Feature**: registry | **Version**: 0.15.1 → 0.16.0
> **Commit scope**: `(registry)`
> **Design ref**: DESIGN.md §7.4, §7.5, §9 Phase 4, §10

---

## Gate

Phase 3 must have produced:

- `rg -e TMDBClient -e TVDBClient --type py personalscraper/ -l | grep -v api/metadata/`
  returns empty stdout.
- `make check` green.
- All 13 consumer files migrated.

---

## Goal

Wire all five EventBus events with full payloads (DESIGN §7.4), complete structured
logging at the levels documented in §7.5, deliver the minimal `personalscraper info
providers` CLI command, update reference docs, bump VERSION to 0.16.0, and add
the CHANGELOG entry. After this phase all ACC criteria pass.

---

## Scope

**Modified:**

- `personalscraper/api/metadata/registry/__init__.py` — wire `_event_bus_safe_emit` calls for all five events in `chain`, `fan_out`, `locked`, and `__init__`
- `personalscraper/api/metadata/registry/_errors.py` — add EventBus event dataclasses if not already in a dedicated module
- `personalscraper/commands/info.py` (or `personalscraper/commands/providers.py`) — add `personalscraper info providers` sub-command
- `docs/reference/architecture.md` — Provider Registry section
- `docs/reference/scraping.md` — three semantics (chain/fan_out/locked) documented
- `CHANGELOG.md` — 0.16.0 entry
- `VERSION` — bump to 0.16.0

**Created:**

- `personalscraper/api/metadata/registry/_events.py` — five EventBus event dataclasses (if not already defined in `__init__.py`)
- `tests/integration/api/metadata/registry/test_events.py` — ACC-08 EventBus snapshot test

---

## Sub-phases

### 4.1 — EventBus event dataclasses + full payload wiring

**Files:** `personalscraper/api/metadata/registry/_events.py`, `personalscraper/api/metadata/registry/__init__.py`

Define all five event classes from DESIGN §7.4 with their exact payload fields:

```python
# personalscraper/api/metadata/registry/_events.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal
from personalscraper.api.metadata.registry import AttemptOutcome, ProviderMatch

@dataclass(frozen=True)
class ProviderFallbackTriggered:
    """Emitted when a chain moves from one provider to the next."""
    capability: str
    from_provider: str
    to_provider: str
    reason: Literal["circuit_open", "network", "empty_result"]
    exc_type: str | None
    item: dict[str, Any]

@dataclass(frozen=True)
class ProviderExhaustedEvent:
    """Emitted when all providers in a chain failed for an item."""
    capability: str
    attempted: list[AttemptOutcome]
    item: dict[str, Any]

@dataclass(frozen=True)
class LockedCapabilityUnresolved:
    """Emitted when locked() cannot bind a provider via IDCrossRef."""
    capability: str
    match: ProviderMatch
    chain_tried: list[str]

@dataclass(frozen=True)
class RegistryFanOutCompleted:
    """Always emitted after fan_out returns (even on full success)."""
    capability: str
    attempted: list[AttemptOutcome]
    succeeded: int

@dataclass(frozen=True)
class RegistryBootValidated:
    """Emitted when boot completed successfully."""
    providers: list[str]
    capabilities: dict[str, list[str]]
```

Wire `_event_bus_safe_emit` calls in `ProviderRegistry`:

- `chain()`: emit `ProviderFallbackTriggered` on each skip; emit `ProviderExhaustedEvent` before raising `ProviderExhausted`.
- `fan_out()`: emit `RegistryFanOutCompleted` always at end (even when `values` is empty).
- `locked()`: emit `LockedCapabilityUnresolved` when returning `None` (already present in Phase 0 implementation — verify and complete payload).
- `__init__`: emit `RegistryBootValidated` after successful construction.

`_event_bus_safe_emit` implementation (must be in `__init__.py`):

```python
def _event_bus_safe_emit(self, event: object) -> None:
    """Emit an event; catch and log any bus failure. Never propagates."""
    if self._event_bus is None:
        return  # test context — no-op
    try:
        self._event_bus.emit(event)
    except Exception as exc:
        log.warning(
            "registry_event_emit_failed",
            event_class=type(event).__name__,
            exc_type=type(exc).__name__,
        )
```

Commit: `feat(registry): EventBus event dataclasses + full payload wiring`

---

### 4.2 — Structured logging at all documented levels

**Files:** `personalscraper/api/metadata/registry/__init__.py`, `_factory.py`, `_validation.py`

Wire all eight log events from DESIGN §7.5 at the correct structlog levels.
Add the logger binding at module top:

```python
import structlog
log = structlog.get_logger(__name__)
```

Ensure each call site uses the exact event name and context fields from DESIGN §7.5:

| Call site         | Event name                   | Level   | Fields                                                 |
| ----------------- | ---------------------------- | ------- | ------------------------------------------------------ |
| boot success      | `registry_boot_loaded`       | INFO    | `providers_count`, `capabilities_count`                |
| circuit skip      | `registry_provider_skip`     | DEBUG   | `provider`, `capability`, `reason`                     |
| network fail      | `registry_provider_fail`     | WARNING | `provider`, `capability`, `exc_type`, `item`           |
| chain exhausted   | `registry_chain_exhausted`   | ERROR   | `capability`, `attempted`, `item`                      |
| fan_out partial   | `registry_fan_out_partial`   | INFO    | `capability`, `providers_tried`, `providers_succeeded` |
| locked xref       | `registry_locked_xref`       | DEBUG   | `source_provider`, `target_provider`, `xref_id`        |
| locked unresolved | `registry_locked_unresolved` | WARNING | `capability`, `match`, `chain_tried`                   |
| event emit failed | `registry_event_emit_failed` | WARNING | `event_class`, `exc_type`                              |

Run: `pytest tests/unit/api/metadata/registry/ -q`
Expected: all pass (logging assertions are covered by existing event-bus unit tests).

Commit: `feat(registry): structured logging at all documented levels (§7.5)`

---

### 4.3 — EventBus integration test (ACC-08) + `info providers` CLI command

**Files:** `tests/integration/api/metadata/registry/test_events.py`, `personalscraper/commands/info.py`

Write the ACC-08 snapshot test:

```python
# tests/integration/api/metadata/registry/test_events.py
"""EventBus snapshot test — ACC-08."""

def test_boot_emits_registry_boot_validated(registry_with_real_config, captured_events):
    assert any(isinstance(e, RegistryBootValidated) for e in captured_events)

def test_chain_fallback_emits_provider_fallback_triggered(registry, mock_bus):
    # Force first provider to return empty, second to succeed
    providers = registry.chain(Searchable)
    assert any(isinstance(e, ProviderFallbackTriggered) for e in mock_bus.emitted)

def test_fan_out_always_emits_completed(registry, mock_bus):
    registry.fan_out(RatingProvider)
    assert any(isinstance(e, RegistryFanOutCompleted) for e in mock_bus.emitted)

def test_locked_unresolved_emits_event(registry_no_xref, match, mock_bus):
    result = registry_no_xref.locked(ArtworkProvider, match)
    assert result is None
    assert any(isinstance(e, LockedCapabilityUnresolved) for e in mock_bus.emitted)

def test_event_bus_failure_does_not_crash_registry(registry, broken_bus):
    # broken_bus.emit() raises RuntimeError
    # registry must not propagate it
    result = registry.chain(Searchable)
    assert isinstance(result, list)  # registry returned normally
```

Add the minimal `personalscraper info providers` CLI command:

```python
# personalscraper/commands/info.py (add sub-command or extend existing)
import typer
from personalscraper.api.metadata.registry import ProviderRegistry

info_app = typer.Typer()

@info_app.command("providers")
def info_providers(ctx: typer.Context) -> None:
    """Print per-provider circuit state (registry.status() snapshot)."""
    registry: ProviderRegistry = ctx.obj["registry"]
    status = registry.status()
    for name, s in status.items():
        typer.echo(f"{name:<20} circuit={s.circuit_state}  failures={s.failure_count_recent}")
```

The command must print at least one line per configured provider (ACC-06).

Run:

```bash
pytest tests/integration/api/metadata/registry/test_events.py -q
personalscraper info providers | grep -cE "^(tmdb|tvdb|imdb|omdb|trakt|rotten_tomatoes)\s"
```

Expected: tests pass; grep count matches `${N_PROVIDERS}` from `config.example/providers.json5`.

Commit: `feat(registry): EventBus integration test (ACC-08) + info providers CLI`

---

### 4.4 — Docs: architecture.md + scraping.md

**Files:** `docs/reference/architecture.md`, `docs/reference/scraping.md`

Add a **Provider Registry** section to `docs/reference/architecture.md`:

- Module map: `api/metadata/registry/` with each submodule's responsibility.
- Boot sequence summary (DESIGN §6.1 in prose).
- Three operations: `chain`, `fan_out`, `locked` — one-line description each.
- Reference to `config/providers.json5` for ordering.

Add **three semantics** section to `docs/reference/scraping.md`:

- `chain`: ordered fallback, first usable result wins. Raises `ProviderExhausted` on exhaustion.
- `fan_out`: aggregates all eligible providers. Returns empty list on full miss (no error).
- `locked`: identity-bound to the match's provider, with `IDCrossRef` escape hatch. Returns `None` when unresolvable.
- Include a table mirroring DESIGN §4 (Mode / Protocols / Behavior / Return on exhaustion).

Docs are in Markdown; use `git add -f` if the global `.gitignore` blocks `docs/`:

```bash
git add -f docs/reference/architecture.md docs/reference/scraping.md
```

Commit: `docs(registry): architecture + scraping reference docs updated`

---

### 4.5 — VERSION bump + CHANGELOG + final gate

**Files:** `VERSION`, `CHANGELOG.md`

Bump VERSION:

```bash
echo "0.16.0" > VERSION
```

Add CHANGELOG entry at the top (must match ACC-11 grep):

```markdown
## [0.16.0] — 2026-05-26

### Added

- **Provider Registry** (`personalscraper/api/metadata/registry/`): `ProviderRegistry`
  class with `chain`, `fan_out`, and `locked` operations. Config-driven provider
  ordering via `config/providers.json5`. Circuit-breaker aware. Boot-time validation
  with aggregated `RegistryConfigError`. EventBus events for all dispatch outcomes.
- `personalscraper info providers` CLI command: prints per-provider circuit state snapshot.
- `conf/models/providers.py`: `ProvidersConfig` Pydantic model.
- `config.example/providers.json5`: provider ordering template.

### Changed

- `scraper/orchestrator.py`, `movie_service.py`, `tv_service.py`: hardcoded
  `self._tmdb`/`self._tvdb` replaced by `registry.chain(...)`. No façade.
- `trailers/orchestrator.py`, `library/rescraper.py`, `commands/library/scan.py`:
  migrated to registry injection.
- All 13 direct `TMDBClient`/`TVDBClient` consumer files now route through the registry.

### Internal

- Characterization tests (`test_legacy_fallback_snapshot.py`) locked in pre-refactor
  behavior as equivalence anchor through migration.
```

Run the full ACC checklist before committing:

```bash
make check
rg -e TMDBClient -e TVDBClient --type py personalscraper/ -l | grep -v api/metadata/  # expect empty
rg -e "self\._tmdb" -e "self\._tvdb" --type py personalscraper/scraper/             # expect empty
pytest tests/integration/scraper/test_legacy_fallback_snapshot.py -q               # ACC-13
pytest tests/integration/api/metadata/registry/test_events.py -q                   # ACC-08
pytest tests/unit/api/metadata/registry/ --collect-only -q | tail -1               # ACC-07 ≥45
personalscraper info providers | grep -cE "^(tmdb|tvdb)\s"                         # ACC-06
grep -c "^## \[0.16.0\]" CHANGELOG.md                                              # ACC-11 = 1
cat VERSION                                                                          # ACC-10 = 0.16.0
python3 scripts/check-module-size.py                                                # ACC-12
```

All expected outputs must match before committing.

Commit: `chore(registry): phase 4 gate — 0.16.0 bump, CHANGELOG, docs, all ACC pass`

---

## Phase gate

From DESIGN §9 Phase 4:

> `make check`; docs updated; `ACCEPTANCE.md` criteria all PASS.

---

## ACC criteria touched

- **ACC-01** — `make check` green (sub-phase 4.5)
- **ACC-06** — `info providers` lists every configured provider (sub-phase 4.3)
- **ACC-08** — EventBus snapshot test passes (sub-phase 4.3)
- **ACC-10** — VERSION = 0.16.0 (sub-phase 4.5)
- **ACC-11** — CHANGELOG `## [0.16.0]` entry present (sub-phase 4.5)
- **ACC-12** — module-size guardrail passes (sub-phase 4.5)
