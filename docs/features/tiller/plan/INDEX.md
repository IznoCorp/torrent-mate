# tiller Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan phase-by-phase.

**Goal:** Add an interactive agent terminal, marker-safe ticket description editing, and UI finishes
to KanbanMateUI (tiller v0.15.0).

**Architecture:** Hexagonal — `core/` pure (no I/O), `adapters/` implement `ports/` Protocols,
`http/` is a top entrypoint. WebSocket transport (xterm.js + FastAPI WS) for the terminal;
`core/body_regions.py` for marker-safe body splitting/merging.

**Tech Stack:** Python / FastAPI (backend WS + REST), xterm.js + @xterm/addon-fit (frontend
terminal), React (JSX), CodeMirror + marked (body editor), pytest + FastAPI TestClient (tests).

---

## Phases

| #   | Phase                              | File                                                                 | Status |
| --- | ---------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Backend terminal                   | [phase-01-backend-terminal.md](phase-01-backend-terminal.md)         | [ ]    |
| 2   | Frontend terminal                  | [phase-02-frontend-terminal.md](phase-02-frontend-terminal.md)       | [ ]    |
| 3   | Editable description (marker-safe) | [phase-03-editable-description.md](phase-03-editable-description.md) | [ ]    |
| 4   | UI finishes                        | [phase-04-ui-finishes.md](phase-04-ui-finishes.md)                   | [ ]    |
| 5   | Final gate + ACCEPTANCE            | [phase-05-final-gate.md](phase-05-final-gate.md)                     | [ ]    |

## Parallelism notes

- Phase 3 (Editable description) has **no runtime dependency on Phase 2** — can start as soon as
  Phase 1 is complete (backend WS + reaper sentinel) or even independently (the `core/body_regions`
  sub-phase is fully standalone).
- Phase 4 (UI finishes) sub-phases 4.1–4.4 have **no backend dependency** — collapse, cards,
  timeline are all frontend-only. Sub-phase 4.5 (`/api/health` version) requires a one-line backend
  change.
- Phase 5 is always last: it re-exercises ALL acceptance criteria end-to-end.

## Global Constraints

- Commit scope: `{type}(tiller): description` — Conventional Commits, `tiller` as scope.
- Module hard ceiling: 1000 LOC (soft warning 800). Enforce with `make check`.
- Hexagonal layering: `core/` MUST NOT import `adapters/`, `http/`, `app/`, or `cli/`.
- Every `rg` invocation MUST include a type/glob filter (`--type py`, `-g '*.py'`).
- Every network command MUST include `--connect-timeout N --max-time N`.
- Tests: `pytest.importorskip("fastapi", ...)` guard in all `tests/http/` files.
- Version is already 0.15.0 — do NOT re-bump.
