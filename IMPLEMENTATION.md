# Implementation Progress — api-unify

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `api-unify`
**Feature**: Third-Party API Consumer Unification (minor)
**Bump**: 0.10.0 → 0.11.0
**Branch**: feat/api-unify
**Design**: docs/features/api-unify/DESIGN.md (v2)
**Master plan**: docs/features/api-unify/plan/INDEX.md
**PR**: _(created after last phase)_
**PR merge**: manual

## Phases

| #   | Phase                              | Type  | File                                                                                                      | Status |
| --- | ---------------------------------- | ----- | --------------------------------------------------------------------------------------------------------- | ------ |
| 1   | Foundation — contracts + transport | infra | [phase-01-foundation-transport.md](docs/features/api-unify/plan/phase-01-foundation-transport.md)         | [x]    |
| 2   | Config infra + activation          | infra | [phase-02-config-activation.md](docs/features/api-unify/plan/phase-02-config-activation.md)               | [x]    |
| 3   | Metadata family base               | infra | [phase-03-metadata-base.md](docs/features/api-unify/plan/phase-03-metadata-base.md)                       | [x]    |
| 4   | TMDB API doc                       | doc   | [phase-04-tmdb-doc.md](docs/features/api-unify/plan/phase-04-tmdb-doc.md)                                 | [x]    |
| 5   | TMDB migration                     | impl  | [phase-05-tmdb-impl.md](docs/features/api-unify/plan/phase-05-tmdb-impl.md)                               | [x]    |
| 6   | TVDB API doc                       | doc   | [phase-06-tvdb-doc.md](docs/features/api-unify/plan/phase-06-tvdb-doc.md)                                 | [x]    |
| 7   | TVDB migration                     | impl  | [phase-07-tvdb-impl.md](docs/features/api-unify/plan/phase-07-tvdb-impl.md)                               | [ ]    |
| 8   | Torrent base + qBittorrent doc     | mixed | [phase-08-torrent-base-qbit-doc.md](docs/features/api-unify/plan/phase-08-torrent-base-qbit-doc.md)       | [ ]    |
| 9   | qBittorrent migration              | impl  | [phase-09-qbit-impl.md](docs/features/api-unify/plan/phase-09-qbit-impl.md)                               | [ ]    |
| 10  | Transmission API doc               | doc   | [phase-10-transmission-doc.md](docs/features/api-unify/plan/phase-10-transmission-doc.md)                 | [ ]    |
| 11  | Transmission implementation        | impl  | [phase-11-transmission-impl.md](docs/features/api-unify/plan/phase-11-transmission-impl.md)               | [ ]    |
| 12  | OMDB API doc                       | doc   | [phase-12-omdb-doc.md](docs/features/api-unify/plan/phase-12-omdb-doc.md)                                 | [ ]    |
| 13  | OMDB implementation                | impl  | [phase-13-omdb-impl.md](docs/features/api-unify/plan/phase-13-omdb-impl.md)                               | [ ]    |
| 14  | Trakt API doc                      | doc   | [phase-14-trakt-doc.md](docs/features/api-unify/plan/phase-14-trakt-doc.md)                               | [ ]    |
| 15  | Trakt implementation               | impl  | [phase-15-trakt-impl.md](docs/features/api-unify/plan/phase-15-trakt-impl.md)                             | [ ]    |
| 16  | Tracker base + ranking engine      | infra | [phase-16-tracker-base-ranking.md](docs/features/api-unify/plan/phase-16-tracker-base-ranking.md)         | [ ]    |
| 17  | LaCale API doc                     | doc   | [phase-17-lacale-doc.md](docs/features/api-unify/plan/phase-17-lacale-doc.md)                             | [ ]    |
| 18  | LaCale implementation              | impl  | [phase-18-lacale-impl.md](docs/features/api-unify/plan/phase-18-lacale-impl.md)                           | [ ]    |
| 19  | C411 API doc                       | doc   | [phase-19-c411-doc.md](docs/features/api-unify/plan/phase-19-c411-doc.md)                                 | [ ]    |
| 20  | C411 implementation                | impl  | [phase-20-c411-impl.md](docs/features/api-unify/plan/phase-20-c411-impl.md)                               | [ ]    |
| 21  | Notify base + Telegram doc         | mixed | [phase-21-notify-base-telegram-doc.md](docs/features/api-unify/plan/phase-21-notify-base-telegram-doc.md) | [ ]    |
| 22  | Telegram migration                 | impl  | [phase-22-telegram-impl.md](docs/features/api-unify/plan/phase-22-telegram-impl.md)                       | [ ]    |
| 23  | Healthchecks API doc               | doc   | [phase-23-healthchecks-doc.md](docs/features/api-unify/plan/phase-23-healthchecks-doc.md)                 | [ ]    |
| 24  | Healthchecks migration             | impl  | [phase-24-healthchecks-impl.md](docs/features/api-unify/plan/phase-24-healthchecks-impl.md)               | [ ]    |
| 25  | Final cleanup + ROADMAP            | infra | [phase-25-final-cleanup.md](docs/features/api-unify/plan/phase-25-final-cleanup.md)                       | [ ]    |

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

| Phase | Sub-phase        | SHA | Date |
| ----- | ---------------- | --- | ---- |
| —     | Design v2 + plan | —   | —    |

## Next action

Run `/implement:phase` to start Phase 1.
