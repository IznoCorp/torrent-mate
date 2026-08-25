# Phase 9 — The divergence register, computed

## Scope

- `scripts/compare-contracts.py` — diffs `frontend/maquette/contract/openapi.json` against
  `frontend/openapi.json` and emits the register.
- `docs/reference/frontend-backend-demands.md` — the register, committed.

## Why computed and not written

A register written by hand rots the first time either contract moves, and « the recorded
divergences ARE that future specification » (D7) — a specification nobody recalculates is a
specification nobody can act on. The script computes it; `--check` refuses a committed register
that differs from the computed one, so the two cannot separate.

## What a divergence is

Four kinds, and each carries what the backend would have to do:

- **An operation the interface requires that the backend does not have** — the Médiathèque's
  whole read surface is here.
- **An operation whose shape the interface needs differently** — a field added, a field the
  interface cannot use.
- **A field the interface carries pre-formatted** because the fixture does (D-L08-5) — the demand
  is « supply the underlying fact ».
- **An operation the backend has that the interface does not use** — recorded, because it says
  what the switchover may retire.

## What this phase does NOT do

It touches no backend. Nothing under `personalscraper/` changes, and ACC-22 proves it with a
`git diff --stat` that must be empty.

## Done when

- The register exists, committed, and every entry names the demand.
- `python3 scripts/compare-contracts.py --check` exits 0, and exits 1 with the operation named
  when the maquette contract gains an operation without a re-run.
- ACC-21, ACC-22 green.
