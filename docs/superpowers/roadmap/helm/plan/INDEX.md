# Plan — `helm` PR 1: Config core + HTTP API

> Prepared ahead-of-time (not committed). Design: `../specs/DESIGN.md`.
> **This plan covers PR 1 only** (the headless config core + local HTTP API). PR 2 (Vue UI)
> and PR 3 (board repatriation) are designed in `DESIGN.md` §9 but get their own
> branch/plan later via `/implement:feature`.

## Scope (PR 1)

A backend-neutral, headless **config model + serializer + validator** for the KanbanMate
pipeline, an `app/` **config service** (load / validate / atomic write, over injected paths),
and a **local HTTP API** as a top-level `http/` **entrypoint** (FastAPI, optional `[ui]` extra)

- a thin `kanban config` Typer **sub-app** + a JSON Schema. No web UI, no board mutation.
  Round-trips with the existing YAML loaders; introduces no `core/` I/O.

## Ordering rationale (incremental green)

Each phase leaves `make check` green. Dependencies flow strictly forward:
**model → serializer → validator (reuses serializer as oracle) → service → entrypoint.**

| Phase | Title                                                   | File                         | Layer                       | Depends on |
| ----- | ------------------------------------------------------- | ---------------------------- | --------------------------- | ---------- |
| 1     | Editable config model + definition/binding split        | `phase-01-config-model.md`   | `core/` (pure)              | —          |
| 2     | Serializer (`render_pipeline`) + authoritative defaults | `phase-02-serializer.md`     | `core/` (pure)              | 1          |
| 3     | Validator (V1–V8) + move-resolution simulation          | `phase-03-validator.md`      | `core/` (pure)              | 1, 2       |
| 4     | Config service (load / validate / atomic write / seed)  | `phase-04-config-service.md` | `app/`                      | 1, 2, 3    |
| 5     | HTTP API (`[ui]`) + CLI + JSON Schema + ACCEPTANCE      | `phase-05-http-api-cli.md`   | `http/` (entrypoint), `cli` | 4          |

## Invariants carried from DESIGN

- `core/` stays I/O-free (layering guard). The HTTP surface is a top-level **entrypoint**
  (`http/`, NOT under `adapters/` — it imports `app`, which `adapters/` may not); the daemon
  must never transitively import the `[ui]` extra (asserted by a **runtime** test:
  `"fastapi" not in sys.modules` after importing `kanbanmate.daemon`).
- **Merge stays human-only**: validator V8 keeps `Merge` out of launch targets (the canonical
  `Review→Merge` gate has no prompt); `bypass*` permission modes are rejected (V3 imports the
  loader's allowed-mode frozenset). The real merge ban lives in perms `deny` + branch protection.
- Writes are **atomic** (temp→rename, each in the target file's own parent dir); validation is
  **server-enforced** before any write. The config service takes **injected resolved paths**
  (`app/` may not import `cli/init.py`'s `CLONE_*_RELPATH`).
- Round-trip **semantic equivalence**: `render(load(X)) ≡ load(X)` (comments not preserved;
  `from_loaded` re-parses the raw YAML since `TransitionConfig` has no transition list). Tested
  with a **purpose-built** fixture (the live config equals the default).
- Defaults home: **`transitions.yml` `defaults:` is authoritative** (genesis phase 30 / #4 —
  `build_tick_config` reads it; the `columns.yml` block is a commented fallback).
- Backend-neutral `definition` (column keys + `column_class` + transitions + defaults) is
  isolated from GitHub `binding` (project slug + `key→label` map) — the extensibility seam for
  PR 3, which extends the existing `Seeder` (no parallel `BoardProvisioner`).

## Phase gate checklist (every phase)

1. `rm -rf .mypy_cache && make lint` — zero errors.
2. `make test` — all pass (check the summary line; any ERROR = collection crash).
3. `make check` — lint + test + module-size guards (soft 800 / hard 1000 LOC).
4. Residual-import grep for any renamed/removed symbol in `src/` **and** `tests/`.
5. `python -c "import kanbanmate"` smoke test.
