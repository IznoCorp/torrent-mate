# tracker-wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `TrackerRegistry` into the composition root — config-driven factory, fail-loud boot validation with severity tiers, `TrackerRegistry.close()`, and a `tracker_registry` field on `AppContext` — at parity with the metadata provider registry. No tracker consumer added (RP5b).

**Architecture:** A new `api/tracker/_errors.py` extension defines `TrackerError` / `TrackerConfigIssue` / `TrackerConfigError`; a new `api/tracker/_factory.py` builds a live `TrackerRegistry` from config with fail-loud validation (errors raise, warnings log); `TrackerRegistry` gains a `close()` method; `AppContext` gains a `tracker_registry` field; and `cli_helpers/__init__.py::_build_app_context` wires all of this together at the composition-root boundary, with `per_step_boundary` releasing the registry on exit.

**Tech Stack:** Python 3.11+, Pydantic v2 (TrackerConfig already defined), structlog, pytest, `make check` (ruff + mypy + tests + module-size + typed-api).

---

## Phases

| #   | Phase                                                                      | File                                                                                 | Status |
| --- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------ |
| 1   | Error types — `TrackerError` + `TrackerConfigIssue` + `TrackerConfigError` | [phase-01-error-types.md](phase-01-error-types.md)                                   | [ ]    |
| 2   | Factory — `build_tracker_registry` implementation                          | [phase-02-factory-impl.md](phase-02-factory-impl.md)                                 | [ ]    |
| 3a  | Factory unit tests — error cases + silent boot                             | [phase-03a-factory-tests-error-cases.md](phase-03a-factory-tests-error-cases.md)     | [ ]    |
| 3b  | Factory unit tests — warning, severity split, happy path                   | [phase-03b-factory-tests-warning-happy.md](phase-03b-factory-tests-warning-happy.md) | [ ]    |
| 4   | `TrackerRegistry.close()` + regression guard                               | [phase-04-registry-close.md](phase-04-registry-close.md)                             | [ ]    |
| 5a  | `AppContext.tracker_registry` field                                        | [phase-05a-appcontext-field.md](phase-05a-appcontext-field.md)                       | [ ]    |
| 5b  | Composition-root wiring + integration tests                                | [phase-05b-composition-root-wiring.md](phase-05b-composition-root-wiring.md)         | [ ]    |
| 6   | ACCEPTANCE.md + `make check` gate                                          | [phase-06-acceptance.md](phase-06-acceptance.md)                                     | [ ]    |

## Dependency graph

```
Phase 1 (error types + unit tests)
    └── Phase 2 (factory implementation — imports error types)
            └── Phase 3a (factory unit tests — error cases + silent boot)
                    └── Phase 3b (factory unit tests — warning, severity split, happy path)
                            └── Phase 4 (TrackerRegistry.close() + regression guard)
                                    └── Phase 5a (AppContext.tracker_registry field)
                                            └── Phase 5b (composition-root wiring + integration tests)
                                                    └── Phase 6 (ACCEPTANCE.md + make check gate)
```

## Files touched

| File                                                     | Action     | Phase |
| -------------------------------------------------------- | ---------- | ----- |
| `personalscraper/api/tracker/_errors.py`                 | **Modify** | 1     |
| `tests/unit/test_tracker_config_errors.py`               | **Create** | 1     |
| `personalscraper/api/tracker/_factory.py`                | **Create** | 2     |
| `tests/unit/test_tracker_factory.py`                     | **Create** | 3a    |
| `tests/unit/test_tracker_factory.py`                     | **Modify** | 3b    |
| `personalscraper/api/tracker/_registry.py`               | **Modify** | 4     |
| `tests/unit/test_tracker_registry_close.py`              | **Create** | 4     |
| `personalscraper/core/app_context.py`                    | **Modify** | 5a    |
| `personalscraper/cli_helpers/__init__.py`                | **Modify** | 5b    |
| `tests/integration/api/tracker/__init__.py`              | **Create** | 5b    |
| `tests/integration/api/tracker/test_composition_root.py` | **Create** | 5b    |
| `docs/features/tracker-wiring/ACCEPTANCE.md`             | **Create** | 6     |

## Commit convention

All commits use scope `tracker-wiring`:

```
feat(tracker-wiring): <description>
test(tracker-wiring): <description>
chore(tracker-wiring): <description>
```
