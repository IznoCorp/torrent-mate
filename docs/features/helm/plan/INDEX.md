# helm — PR 1 Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Codename**: `helm` · **Ticket**: #5 · **Branch**: `feat/helm`
**Design**: `docs/features/helm/DESIGN.md`
**SemVer**: minor (additive subsystem — no breaking changes to existing engine)
**Scope**: PR 1 only — config core + headless HTTP API. No UI (PR 2), no board mutation (PR 3).

---

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | Core: profiles relocation + config model | phase-01-core-profiles-and-model.md | [ ] |
| 2 | Serializer (render_pipeline) | phase-02-serializer.md | [ ] |
| 3 | Validator + resolve | phase-03-validator-and-resolve.md | [ ] |
| 4 | Config service (app) | phase-04-config-service.md | [ ] |
| 5 | HTTP API + CLI + packaging | phase-05-http-cli-packaging.md | [ ] |

---

## Build order rationale

The dependency chain is: **model** → **serializer** (needs model) → **validator/resolve** (needs
render to run the oracle pass) → **config service** (needs all core) → **http/cli** (needs service
+ registry loaders from `cli.init`).

Each phase ends with the standard phase gate (CLAUDE.md):
1. `make lint` — ruff + mypy, zero errors
2. `make test` — all pass (check the summary line; `ERROR` = collection crash)
3. `make check` — lint + test + module-size guards (<1000 LOC per module)
4. Residual-import grep in `src/` AND `tests/` — zero matches for any deleted/renamed symbol
5. `python -c "import kanbanmate"` smoke test

## Files produced by this feature (PR 1)

| Layer | New/Edit | Path |
|-------|----------|------|
| `core` | **New** | `src/kanbanmate/core/profiles.py` |
| `core` | **New** | `src/kanbanmate/core/config_model.py` |
| `core` | **New** | `src/kanbanmate/core/config_serialize.py` |
| `core` | **New** | `src/kanbanmate/core/config_validate.py` |
| `adapters` | **Edit** | `src/kanbanmate/adapters/perms.py` |
| `app` | **New** | `src/kanbanmate/app/config_service.py` |
| `http` | **New** | `src/kanbanmate/http/config_api.py` |
| `cli` | **New** | `src/kanbanmate/cli/config.py` |
| root | **Edit** | `pyproject.toml` |
| `tests/core` | **New** | `tests/core/test_profiles.py` |
| `tests/core` | **New** | `tests/core/test_config_model.py` |
| `tests/core` | **New** | `tests/core/test_config_serialize.py` |
| `tests/core` | **New** | `tests/core/test_config_validate.py` |
| `tests/app` | **New** | `tests/app/test_config_service.py` |
| `tests/http` | **New** | `tests/http/test_config_api.py` |
