# acquire-lobe — Implementation Plan Index

**Feature**: RP5c — `acquire/` lobe + single injection handle
**Codename**: acquire-lobe
**Branch**: `feat/acquire-lobe`
**Version bump**: 0.24.0 → 0.25.0 (minor)

**Goal**: Create the `acquire/` peer package with `AcquireContext` (frozen dataclass), `AcquireStore` Protocol seam, `build_acquire_context` factory, swap `AppContext.tracker_registry` → `AppContext.acquire`, wire `cli_helpers`, extend the layering guard, and ship `ACCEPTANCE.md` + docs update. No behaviour — skeleton only.

**Non-goals**: orchestrator (RP5b), DB schema (RP3), Follow/Ratio/Watcher, completing core/conf layering enumeration.

---

## Phases

| #   | Phase                                                             | File                                                                 | Status |
| --- | ----------------------------------------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | acquire/ skeleton + AcquireStore + AcquireContext + close() tests | [phase-01-package-skeleton.md](phase-01-package-skeleton.md)         | [ ]    |
| 2   | build_acquire_context factory + tests                             | [phase-02-factory.md](phase-02-factory.md)                           | [ ]    |
| 3   | AppContext swap + cli_helpers wiring + wiring tests               | [phase-03-appcontext-wiring.md](phase-03-appcontext-wiring.md)       | [ ]    |
| 4   | Layering guard extension (acquire/ → never triage)                | [phase-04-layering-guard.md](phase-04-layering-guard.md)             | [ ]    |
| 5   | ACCEPTANCE.md + architecture.md update + make check gate          | [phase-05-acceptance-docs-gate.md](phase-05-acceptance-docs-gate.md) | [ ]    |

---

## Dependency order

Phases are designed to be independently completable, with one soft dependency:

- Phase 03 (AppContext swap) reads the `AcquireContext` type from Phase 01. Phase 01 must be committed before Phase 03 starts.
- Phase 02 (factory) can proceed in parallel with Phase 03 prep, but `cli_helpers` wiring in Phase 03 calls `build_acquire_context`, so Phase 02 must be committed before the Phase 03 wiring task.
- Phase 04 (layering guard) is fully independent — it only adds tests and does not touch source. Can be done any time after Phase 01.
- Phase 05 (gate) must be last.

## Key files touched

| File                                       | Change                                                             |
| ------------------------------------------ | ------------------------------------------------------------------ |
| `personalscraper/acquire/__init__.py`      | Create — package root                                              |
| `personalscraper/acquire/_ports.py`        | Create — `AcquireStore` Protocol                                   |
| `personalscraper/acquire/context.py`       | Create — `AcquireContext` frozen dataclass + `close()`             |
| `personalscraper/acquire/_factory.py`      | Create — `build_acquire_context` factory                           |
| `personalscraper/core/app_context.py`      | Modify — drop `tracker_registry`, add `acquire`                    |
| `personalscraper/cli_helpers/__init__.py`  | Modify — wire `build_acquire_context`, close via `acquire.close()` |
| `tests/acquire/__init__.py`                | Create — test package                                              |
| `tests/acquire/test_context.py`            | Create — `AcquireContext` + mutation-proven close() tests          |
| `tests/acquire/test_factory.py`            | Create — factory unit tests                                        |
| `tests/acquire/test_appcontext_swap.py`    | Create — field-swap + wiring tests                                 |
| `tests/architecture/test_layering.py`      | Modify — add acquire/ triage guard + 2 control tests               |
| `tests/test_pipeline_app_context.py`       | Modify — update `_stub_app()` for `acquire` field                  |
| `docs/features/acquire-lobe/ACCEPTANCE.md` | Create — ACC-1..5 as executable shell commands                     |
| `docs/reference/architecture.md`           | Modify — add `acquire/` to module map                              |
