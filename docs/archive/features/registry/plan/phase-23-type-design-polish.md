# Phase 23 — Type design polish

Created from `type-design-analyzer` audit (2026-05-27). Three concrete, low-cost
fixes:

1. `FanOutResult` is the only mutable return type in the registry (`values:
list[C]` is not frozen). A consumer can `result.values.clear()` after
   receiving it.
2. Three `# type: ignore` debt items:
   - `_events.py:44` — `attempted: list  # type: ignore[type-arg]` (circular
     import workaround).
   - `_events.py:74` — same.
   - `__init__.py:652` — `status()` uses `# type: ignore[arg-type]` on the
     Literal-typed `state` field.
3. `_events.py::LockedCapabilityUnresolved.match: object` is too loose — should
   be `ProviderMatch` via TYPE_CHECKING import.

## Gate

- Phases 7–22 complete.
- Type design overall solid; this phase polishes the remaining edges.

## Goal

- `FanOutResult` is frozen (immutable post-construction).
- Zero `# type: ignore` in `registry/_events.py` and `registry/__init__.py`'s
  `status()` site.
- `LockedCapabilityUnresolved.match` typed as `ProviderMatch`.

## Scope

- `personalscraper/api/metadata/registry/_events.py` — drop type ignores + TYPE_CHECKING import.
- `personalscraper/api/metadata/registry/__init__.py::status` — normalize state
  via explicit dict check instead of cast/ignore.
- `personalscraper/api/metadata/registry/__init__.py::FanOutResult` — add
  `frozen=True` decorator.
- Tests confirming the type changes don't break consumers.

## Sub-phases

### 23.1 — Freeze FanOutResult

```python
@dataclass(frozen=True)
class FanOutResult(Generic[C]):
    values: list[C]
    attempted: list[AttemptOutcome]
```

Verify no consumer mutates `.values` or `.attempted` after construction.
`rg --type py "FanOutResult" personalscraper/ tests/` to find call sites.

Commit: `refactor(registry): freeze FanOutResult dataclass (consistency with siblings)`

### 23.2 — Drop type-arg ignores in \_events.py via TYPE_CHECKING

```python
# In _events.py
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import AttemptOutcome, ProviderMatch

@dataclass(frozen=True)
class ProviderExhaustedEvent:
    capability: str
    attempted: list[AttemptOutcome]   # no more `# type: ignore`
    item: dict[str, Any]
```

`from __future__ import annotations` is already present at L4 (per audit), so
the import only needs to be added under TYPE_CHECKING.

Also tighten `LockedCapabilityUnresolved.match: ProviderMatch` (was `object`).

Commit: `refactor(registry): drop type-arg ignores in _events.py via TYPE_CHECKING`

### 23.3 — Drop arg-type ignore in status()

`__init__.py:652` (status getter) casts a state string to Literal via
`# type: ignore[arg-type]`. Replace with explicit check:

```python
state_str = getattr(p.circuit, "state", "CLOSED")
if state_str not in {"CLOSED", "OPEN", "HALF_OPEN"}:
    state_str = "CLOSED"  # or raise — defensive default
status[name] = ProviderStatus(
    provider_name=RegistryProviderName(name),
    circuit_state=state_str,  # type: ignore goes away
    ...
)
```

Commit: `refactor(registry): drop arg-type ignore in status() via explicit Literal check`

### 23.4 — Verify all type-ignores gone

```bash
rg --type py "# type: ignore" personalscraper/api/metadata/registry/
```

Expected: only legitimate items remain (e.g. consumer-site `[type-abstract,
type-var]` from Phase 8.3). Document any survivors with explicit rationale.

Commit (only if survivors need documenting): `docs(registry): document residual
type-ignores with rationale`

## Phase gate

- `rg --type py "# type: ignore\[type-arg\]" personalscraper/api/metadata/registry/`
  returns empty.
- `rg --type py "# type: ignore\[arg-type\]" personalscraper/api/metadata/registry/`
  returns empty.
- `FanOutResult.values.append(...)` raises `dataclasses.FrozenInstanceError` (smoke test).
- `make test` 5636+ passed.
- `make lint` clean.

## ACC criteria touched

- ACC-01 (`make check`) — must remain green.

## Cost estimate

- 23.1: ~5 min DeepSeek.
- 23.2: ~10 min DeepSeek.
- 23.3: ~5 min DeepSeek.
- 23.4: ~2 min verification.
- Total: ~25 min.

## Risk

Low. Frozen-dataclass conversion only fails if a consumer mutates the field —
caught by tests.
