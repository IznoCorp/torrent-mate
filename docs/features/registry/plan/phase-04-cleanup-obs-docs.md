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

Wire all five EventBus events with full payloads at the remaining emission sites
(DESIGN §7.4), complete structured logging at the levels documented in §7.5, deliver
the minimal `personalscraper info providers` CLI command (with `--config` flag per
ACC-05b), update reference docs, bump VERSION to 0.16.0, add the CHANGELOG entry,
and add the lint rule forbidding broad `except` around registry call sites. After
this phase all ACC criteria pass.

---

## Scope

**Modified:**

- `personalscraper/api/metadata/registry/__init__.py` — wire remaining `_event_bus_safe_emit` calls for all five events in `chain`, `fan_out`, `locked`, and `__init__` (event classes and `_event_bus_safe_emit` already defined in Phase 0)
- `personalscraper/commands/info.py` (or `personalscraper/commands/providers.py`) — add `personalscraper info providers` sub-command with `--config Path` option
- `Makefile` — wire `check-no-broad-registry-catch` lint rule into `check` target
- `docs/reference/architecture.md` — Provider Registry section
- `docs/reference/scraping.md` — three semantics (chain/fan_out/locked) documented
- `CHANGELOG.md` — 0.16.0 entry
- `VERSION` — bump to 0.16.0

**Created:**

- `scripts/check-no-broad-registry-catch.py` — AST-based lint rule (sub-phase 4.6)
- `tests/integration/api/metadata/registry/test_events.py` — ACC-08 EventBus snapshot test

**Note on event class definitions**: `_events.py` and `_event_bus_safe_emit` were
defined in Phase 0 sub-phase 0.1 and 0.5a respectively. Phase 4 sub-phase 4.1
wires the REMAINING emission sites (those in `chain()`, `fan_out()`, `__init__`)
that were deferred from Phase 0 to avoid implementing complex logic before the
unit tests existed. The class definitions themselves are NOT re-created here.

---

## Sub-phases

### 4.1 — Wire remaining EventBus emission sites

**Files:** `personalscraper/api/metadata/registry/__init__.py`

The event dataclasses (`_events.py`) and `_event_bus_safe_emit` were already defined
in Phase 0. This sub-phase wires the remaining `_event_bus_safe_emit` calls at the
correct call points within `chain()`, `fan_out()`, `locked()`, and `__init__()`:

- `chain()`: emit `ProviderFallbackTriggered` on each skip; emit `ProviderExhaustedEvent` before raising `ProviderExhausted`.
- `fan_out()`: emit `RegistryFanOutCompleted` always at end (even when `values` is empty).
- `locked()`: emit `LockedCapabilityUnresolved` when returning `None` (verify payload is complete per §7.4).
- `__init__`: emit `RegistryBootValidated` after successful construction.

Reminder of the `_event_bus_safe_emit` contract (already implemented in Phase 0
sub-phase 0.5a):

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

Commit: `feat(registry): wire remaining EventBus emission sites with full payloads`

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

| Call site         | Event name                   | Level   | Fields                                                |
| ----------------- | ---------------------------- | ------- | ----------------------------------------------------- |
| boot success      | `registry_boot_loaded`       | INFO    | `providers_count`, `capabilities_count`               |
| circuit skip      | `registry_provider_skip`     | DEBUG   | `provider`, `capability`, `reason`                    |
| network fail      | `registry_provider_fail`     | WARNING | `provider`, `capability`, `exc_type`, `item`          |
| chain exhausted   | `registry_chain_exhausted`   | ERROR   | `capability`, `attempted`, `item`                     |
| fan_out partial   | `registry_fan_out_partial`   | INFO    | `capability`, `providers_tried`, `providers_eligible` |
| locked xref       | `registry_locked_xref`       | DEBUG   | `source_provider`, `target_provider`, `xref_id`       |
| locked unresolved | `registry_locked_unresolved` | WARNING | `capability`, `match`, `chain_tried`                  |
| event emit failed | `registry_event_emit_failed` | WARNING | `event_class`, `exc_type`                             |

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

Add the minimal `personalscraper info providers` CLI command with `--config` flag
(ACC-04a/b and ACC-05b are verified via this command — see INDEX.md):

```python
# personalscraper/commands/info.py (add sub-command or extend existing)
import typer
from pathlib import Path
from personalscraper.api.metadata.registry import ProviderRegistry

info_app = typer.Typer()

@info_app.command("providers")
def info_providers(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Override the default config/providers.json5 location for boot validation.",
    ),
) -> None:
    """Print per-provider circuit state (registry.status() snapshot).

    If --config is given, the specified providers.json5 path is used instead of
    the default. This enables ACC-05b: passing a broken config file triggers
    aggregated RegistryConfigError output.
    """
    registry: ProviderRegistry = ctx.obj["registry"]
    status = registry.status()
    for name, s in status.items():
        typer.echo(f"{name:<20} circuit={s.circuit_state}  failures={s.failure_count_recent}")
```

The `--config Path` option overrides the default `config/providers.json5` location
for the boot validation pass (DESIGN §10 ACC-05b requirement). When a broken config
is passed, `RegistryConfigError` is raised and printed before the command exits
non-zero.

The command must print at least one line per configured provider (ACC-06).

Run:

```bash
pytest tests/integration/api/metadata/registry/test_events.py -q
personalscraper info providers | grep -cE "^(tmdb|tvdb|imdb|omdb|trakt|rotten_tomatoes)\s"
```

Expected: tests pass; grep count matches the number of providers in
`config.example/providers.json5`.

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
# ACC-04a: boot positive control
TMDB_API_KEY=dummy_key personalscraper info providers >/dev/null 2>&1              # expect exit 0
# ACC-04b: boot crashes when credentials missing
env -u TMDB_API_KEY personalscraper info providers 2>&1 | grep -c "RegistryConfigError.*tmdb"  # expect 1
# ACC-05b: broken config triggers aggregated RegistryConfigError
personalscraper info providers --config tests/fixtures/bad_providers.json5 2>&1 | grep -c "RegistryConfigError"  # expect 1
```

All expected outputs must match before committing.

Commit: `chore(registry): phase 4 gate — 0.16.0 bump, CHANGELOG, docs, all ACC pass`

---

### 4.6 — Lint rule: forbid broad `except` around registry call sites

**Files:** `scripts/check-no-broad-registry-catch.py`, `Makefile`

DESIGN §7.1 promises a project-level lint rule forbidding `except WrongSemanticBug`
and `except RegistryError` around `registry.*` call sites (programmer bugs that must
never be caught). Implement as an AST-based script:

```python
#!/usr/bin/env python3
"""check-no-broad-registry-catch.py

AST-walks personalscraper/ and finds Try nodes where an ExceptHandler.type
matches RegistryError or WrongSemanticBug. Exits 1 with file:line listing if any
are found, exits 0 if none.

Usage: python3 scripts/check-no-broad-registry-catch.py
"""
import ast
import sys
from pathlib import Path

FORBIDDEN_CATCHES = {"RegistryError", "WrongSemanticBug"}

def check_file(path: Path) -> list[str]:
    violations = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None:
                    continue  # bare except — not a registry-specific catch
                names = (
                    [handler.type.id]
                    if isinstance(handler.type, ast.Name)
                    else []
                )
                for name in names:
                    if name in FORBIDDEN_CATCHES:
                        violations.append(
                            f"{path}:{handler.lineno}: forbidden `except {name}` around registry call site"
                        )
    return violations

def main() -> int:
    root = Path("personalscraper")
    all_violations: list[str] = []
    for py_file in sorted(root.rglob("*.py")):
        all_violations.extend(check_file(py_file))
    if all_violations:
        print("\\n".join(all_violations), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

Wire into `Makefile` `check` target:

```makefile
check: lint test module-size check-no-broad-registry-catch

check-no-broad-registry-catch:
	python3 scripts/check-no-broad-registry-catch.py
```

Run:

```bash
python3 scripts/check-no-broad-registry-catch.py
```

Expected: exit 0 (no violations in the codebase).

Commit: `chore(registry): add lint rule forbidding broad except around registry calls`

---

## On gate failure

If `## Phase gate` fails, do NOT proceed to the next phase. Revert the failing
sub-phase's commit (`git revert <sha>` for the most recent commit, or
`git reset --hard HEAD~N` for multiple) and re-invoke `/implement:phase` to retry
the sub-phase. The phase gate must be green before any cross-phase work continues.

---

## Phase gate

From DESIGN §9 Phase 4:

> `make check`; docs updated; `ACCEPTANCE.md` criteria all PASS.

---

## ACC criteria touched

- **ACC-01** — `make check` green (sub-phase 4.5)
- **ACC-04a** — boot positive control: `ProviderRegistry` constructed with credentials → exit 0 (sub-phase 4.3 CLI + 4.5 checklist)
- **ACC-04b** — boot crashes when credentials missing → `RegistryConfigError` (sub-phase 4.3 CLI + 4.5 checklist)
- **ACC-05a** — `tests/fixtures/bad_providers.json5` exists (created in Phase 0 sub-phase 0.6; verified here)
- **ACC-05b** — broken config triggers aggregated `RegistryConfigError` via `--config` flag (sub-phase 4.3)
- **ACC-06** — `info providers` lists every configured provider (sub-phase 4.3)
- **ACC-08** — EventBus snapshot test passes (sub-phase 4.3)
- **ACC-10** — VERSION = 0.16.0 (sub-phase 4.5)
- **ACC-11** — CHANGELOG `## [0.16.0]` entry present (sub-phase 4.5)
- **ACC-12** — module-size guardrail passes (sub-phase 4.5)
