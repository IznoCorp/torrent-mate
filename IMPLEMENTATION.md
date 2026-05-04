# Implementation Progress — api-unify

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `api-unify`
**Feature**: Third-Party API Consumer Unification (minor)
**Bump**: 0.10.0 → 0.11.0
**Branch**: feat/api-unify
**Design**: docs/features/api-unify/DESIGN.md
**Master plan**: _(to be defined after /implement:plan)_
**PR**: _(created after last phase)_
**PR merge**: manual

## Phases

_(filled by /implement:plan)_

## Quality gate (every commit)

```bash
make check
python3 scripts/check-module-size.py
```

A commit is acceptable when `make lint test` exits 0, the size script exits 0, no new file > 1000 LOC, and coverage delta ≥ 0.

## Conventional Commits scope

All commits use scope `api-unify`:

- `feat(api-unify): ...`
- `refactor(api-unify): ...`
- `docs(api-unify): ...`
- `test(api-unify): ...`
- `chore(api-unify): ...`

## Sub-phase → SHA mapping

| Phase | Sub-phase               | SHA | Date |
| ----- | ----------------------- | --- | ---- |
| —     | Design + archive + bump | —   | —    |

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
