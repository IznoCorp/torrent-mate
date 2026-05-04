# Implementation Progress — api-unify

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `api-unify`
**Feature**: Third-Party API Consumer Unification (minor)
**Bump**: 0.10.0 → 0.11.0
**Branch**: feat/api-unify
**Design**: docs/features/api-unify/DESIGN.md
**Master plan**: docs/features/api-unify/plan/INDEX.md
**PR**: _(created after last phase)_
**PR merge**: manual

## Phases

| #   | Phase                    | File                                                                                            | Status |
| --- | ------------------------ | ----------------------------------------------------------------------------------------------- | ------ |
| 1   | Transport + contracts    | [phase-01-transport-contracts.md](docs/features/api-unify/plan/phase-01-transport-contracts.md) | [ ]    |
| 2   | Config API               | [phase-02-config-api.md](docs/features/api-unify/plan/phase-02-config-api.md)                   | [ ]    |
| 3   | Doc TMDB + TVDB          | [phase-03-doc-tmdb-tvdb.md](docs/features/api-unify/plan/phase-03-doc-tmdb-tvdb.md)             | [ ]    |
| 4   | Migration TMDB           | [phase-04-migration-tmdb.md](docs/features/api-unify/plan/phase-04-migration-tmdb.md)           | [ ]    |
| 5   | Migration TVDB           | [phase-05-migration-tvdb.md](docs/features/api-unify/plan/phase-05-migration-tvdb.md)           | [ ]    |
| 6   | Migration qBittorrent    | [phase-06-migration-qbit.md](docs/features/api-unify/plan/phase-06-migration-qbit.md)           | [ ]    |
| 7   | Doc OMDB + Trakt         | [phase-07-doc-omdb-trakt.md](docs/features/api-unify/plan/phase-07-doc-omdb-trakt.md)           | [ ]    |
| 8   | New OMDB                 | [phase-08-new-omdb.md](docs/features/api-unify/plan/phase-08-new-omdb.md)                       | [ ]    |
| 9   | New Trakt                | [phase-09-new-trakt.md](docs/features/api-unify/plan/phase-09-new-trakt.md)                     | [ ]    |
| 10  | Doc LaCale + C411        | [phase-10-doc-lacale-c411.md](docs/features/api-unify/plan/phase-10-doc-lacale-c411.md)         | [ ]    |
| 11  | New trackers + ranking   | [phase-11-new-trackers.md](docs/features/api-unify/plan/phase-11-new-trackers.md)               | [ ]    |
| 12  | Migration Notify+cleanup | [phase-12-notify-cleanup.md](docs/features/api-unify/plan/phase-12-notify-cleanup.md)           | [ ]    |

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

Run `/implement:phase` to start Phase 1.
