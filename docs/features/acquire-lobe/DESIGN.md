# Design — RP5c: the `acquire/` lobe + single injection handle

**Roadmap item**: RP5c (Vague 2, P1 prérequis) — _« Donner un home + un seam d'injection au lobe acquisition »_
**Codename**: _(derived at implement:brainstorm Step 2)_
**Version bump**: 0.24.0 → 0.25.0 (minor)
**Status**: design approved 2026-06-09, pre-branch (uncommitted)

## 1. Context & motivation

`personalscraper` is evolving from a media-triage pipeline into a closed-loop self-hosted
system: **ACQUIRE → TRIAGE → STORE & INDEX → SEED/RATIO → SUPERVISE**. The acquisition epic
(grab core RP5b, Follow, Ratio, Seed-Safety, Watcher) needs a structural home and a single,
disciplined injection seam **before** any of that behaviour is built — otherwise each feature
bolts its own field onto the frozen `AppContext` and it drifts into a service-locator.

RP5a (`tracker-wiring`, shipped #142) wired the `TrackerRegistry` into the composition root as
its **own** top-level `AppContext.tracker_registry` field, built by `build_tracker_registry`,
closed in `per_step_boundary`. Today **nothing consumes `tracker_registry`** — the consumer is
RP5b/Follow/Ratio, not yet built. It is a dangling acquisition-only handle waiting for a home.

RP5c provides that home (`acquire/` package) and the **single** injection handle, and folds the
unconsumed `tracker_registry` into it — making the skeleton non-vacuous from day one.

## 2. Decisions (frozen during brainstorm 2026-06-09)

- **D1 — How much to consolidate now → Consolidate.** Move `tracker_registry` (acquisition-only,
  unconsumed) under the single handle, which owns its `close()`. `torrent_client` stays top-level
  (shared with `ingest`), borrowed by reference.
- **D2 — `acquire.db` scope → Typed slot only.** The handle declares a typed `store` slot
  (`AcquireStore` or `None`), a minimal Protocol seam. RP3 supplies the store impl and fills the
  slot. No schema, no connection in RP5c.
- **D3 — Layering guard (RP-layer) → Graft into RP5c.** Extend `tests/architecture/test_layering.py`
  so `acquire/` may import downward only and never the triage packages. Boundary enforced from day
  one, not just documented.
- **D4 — Handle shape → Approach A.** `AcquireContext`, a frozen dataclass mirroring `AppContext`.
  No behaviour (orchestrator is RP5b).

## 3. Architecture & boundary

New top-level package **`personalscraper/acquire/`** — a peer of `ingest`/`sort`/`dispatch`/`indexer`.
Home of the acquisition lobe (future: orchestrator RP5b, store RP3, Follow/Ratio/Seed-Safety/Watcher).
At RP5c it contains **only the injection context** — zero behaviour.

**Import direction (enforced)**: `acquire/` → downward only (`api/`, `core/`, `conf/`, `events/`);
**never** the triage packages: `ingest`, `sort`, `sorter`, `process`, `scraper`, `dispatch`,
`indexer`, `enforce`, `verify`, `insights`, `maintenance`, `reports`, `trailers`, `pipeline`,
`pipeline_steps`, `commands`. The pipeline _composes_ `acquire/`; `acquire/` never imports the pipeline.

The single triage↔acquisition seam stays the seed-pure/useful-content **tag** (RP1) — RP5c adds no
new cross-lobe coupling. The EventBus remains observe-only: `acquire/` may hold an `EventBus`
reference to emit, but does not subscribe to triage.

## 4. Components

### 4.1 `acquire/context.py` — `AcquireContext`

Frozen dataclass mirroring `AppContext`'s own pattern:

```python
@dataclass(frozen=True)
class AcquireContext:
    tracker_registry: TrackerRegistry            # OWNED — migrated from AppContext (RP5a)
    store: AcquireStore | None = None            # SEAM slot — filled by RP3
    torrent_client: TorrentClient | None = None  # BORROWED — shared api/ port; lifecycle NOT owned here

    def close(self) -> None:
        """Close owned resources: tracker_registry (+ store if present). NOT torrent_client."""
```

`close()` closes `tracker_registry` and `store` (when present) but **must not** close
`torrent_client` — that port is shared with `ingest`, whose boundary owns its lifecycle.

### 4.2 `acquire/_ports.py` — `AcquireStore` Protocol (minimal seam)

```python
class AcquireStore(Protocol):
    def close(self) -> None: ...   # the only contract the lifecycle needs today; RP3 extends it
```

### 4.3 `acquire/_factory.py` — `build_acquire_context(...)`

Thin, config-driven assembler at parity with RP5a. Delegates the tracker part to the **unchanged**
`build_tracker_registry(config.tracker, config.ranking, settings=…, event_bus=…, cb_policy=…)`,
sets `store=None`, and borrows the already-built `torrent_client`. Adds **no** new validation —
boot validation remains RP5a's; `TrackerConfigError` still surfaces at the same boundary.

### 4.4 `core/app_context.py` — the swap (one handle)

`AppContext` **drops** the `tracker_registry` field and **gains one** field `acquire: AcquireContext`.
The other five fields are unchanged (`config, settings, event_bus, provider_registry, torrent_client`).
`torrent_client` stays a top-level field (shared with `ingest`). `acquire` is non-optional (always
built at boot); its sub-deps may be `None` (`store`, `torrent_client`).

### 4.5 `cli_helpers/__init__.py` — wiring (only impacted site)

`_build_app_context`: replace the RP5a `build_tracker_registry(...)` block + `tracker_registry=…`
kwarg with `acquire = build_acquire_context(…)` + `acquire=acquire`. `per_step_boundary` close path:
`app_context.acquire.close()` instead of `app_context.tracker_registry.close()`. This is the **only**
current reader of `tracker_registry`, so the blast radius is one module.

## 5. Layering guard (grafted)

Extend `tests/architecture/test_layering.py` with `test_acquire_does_not_import_triage()`, reusing the
existing pure `_collect_violations_from_source` helper against a `_TRIAGE_PREFIXES` set (the §3 triage
packages). Honour the `# layering: allow <justification>` marker, and add a **non-vacuous control test**:
a synthetic source `from personalscraper.dispatch import x` attributed under `acquire/` MUST be flagged
(positive anchor), and a downward import (`from personalscraper.api import x`) MUST NOT be flagged.

Out of scope: completing the existing `core/conf` `_FORBIDDEN_PREFIXES` enumeration (it omits
`insights/maintenance/enforce/process`) — that belongs to the broader RP-layer cleanup. RP5c's
`acquire/` forbidden set is, however, complete.

## 6. Testing strategy

- `tests/acquire/test_context.py` — `AcquireContext` is frozen; `close()` closes `tracker_registry`
  (mock) and `store` when present; **does not** call `torrent_client.close()` (non-ownership guard,
  mutation-proven RED if the guard is removed).
- `tests/acquire/test_factory.py` — `build_acquire_context` delegates to `build_tracker_registry`
  (real registry built), `store is None`, `torrent_client` propagated; `TrackerConfigError` surfaces.
- Wiring — adapt `tests/test_pipeline_app_context.py`: `app_context.acquire.tracker_registry` present,
  `close()` propagated through `per_step_boundary`.
- Layering — the non-vacuous control test in §5.
- `make check` green (existing ~6263 tests + the new ones); module-size budget respected (every new
  module ≪ 800 LOC).

## 7. Non-goals (explicit)

- ❌ Acquisition orchestrator / service (**RP5b**).
- ❌ `acquire.db` schema or connection (**RP3**) — only the typed `store` slot exists.
- ❌ Follow / Ratio / Seed-Safety / Watcher.
- ❌ Any behaviour (`grab`, `follow`, …).
- ❌ Completing the `core/conf` layering enumeration (RP-layer).

## 8. Acceptance (executable — per project convention)

Each criterion is a shell command with a documented expected output (finalised in `ACCEPTANCE.md`
during the phase). Sketch:

- `ACC-1` — package exists & importable:
  `python -c "import personalscraper.acquire; from personalscraper.acquire.context import AcquireContext"` → exit 0.
- `ACC-2` — single handle on AppContext, no stray `tracker_registry` field:
  `python -c "import dataclasses; from personalscraper.core.app_context import AppContext; f={x.name for x in dataclasses.fields(AppContext)}; assert 'acquire' in f and 'tracker_registry' not in f"` → exit 0.
- `ACC-3` — boot builds the handle with the tracker registry:
  a smoke that builds `_build_app_context` from a real config and asserts `ctx.acquire.tracker_registry is not None` → exit 0.
- `ACC-4` — layering guard active & non-vacuous:
  `pytest tests/architecture/test_layering.py -q` → all pass, including the `acquire/` triage-import control test.
- `ACC-5` — full gate: `make check` → `NNNN passed`, 0 failed/errors.

## 9. Version & docs

- SemVer **0.24.0 → 0.25.0** (minor: new package + additive `AppContext` field; single instance,
  no back-compat obligation).
- Update `docs/reference/architecture.md`: add `acquire/` to the module map and state the `acquire/`
  import-direction invariant.
