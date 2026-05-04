# Plan — api-unify

> Auto-generated from DESIGN.md by /implement:plan. Do not edit manually.

> **Revision v2** (2026-05-04): plan rewritten to enforce 1-phase-per-API granularity
> with interactive doc-before-impl checkpoints. See DESIGN §15 for revision notes.

## Phase types

- **infra** — package skeleton, contracts, foundation modules.
- **doc** — API study + reference doc + **interactive checkpoint with the user** to confirm scope before code.
- **impl** — implementation of one provider (or migration), tests, import updates.
- **mixed** — package base co-shipped with a doc phase (used when the family base is small enough to ship together).

## Phases

| #   | Phase                              | Type  | File                                                                         | Status |
| --- | ---------------------------------- | ----- | ---------------------------------------------------------------------------- | ------ |
| 1   | Foundation — contracts + transport | infra | [phase-01-foundation-transport.md](phase-01-foundation-transport.md)         | [ ]    |
| 2   | Config infra + activation          | infra | [phase-02-config-activation.md](phase-02-config-activation.md)               | [ ]    |
| 3   | Metadata family base               | infra | [phase-03-metadata-base.md](phase-03-metadata-base.md)                       | [ ]    |
| 4   | TMDB API doc                       | doc   | [phase-04-tmdb-doc.md](phase-04-tmdb-doc.md)                                 | [ ]    |
| 5   | TMDB migration                     | impl  | [phase-05-tmdb-impl.md](phase-05-tmdb-impl.md)                               | [ ]    |
| 6   | TVDB API doc                       | doc   | [phase-06-tvdb-doc.md](phase-06-tvdb-doc.md)                                 | [ ]    |
| 7   | TVDB migration                     | impl  | [phase-07-tvdb-impl.md](phase-07-tvdb-impl.md)                               | [ ]    |
| 8   | Torrent base + qBittorrent doc     | mixed | [phase-08-torrent-base-qbit-doc.md](phase-08-torrent-base-qbit-doc.md)       | [ ]    |
| 9   | qBittorrent migration              | impl  | [phase-09-qbit-impl.md](phase-09-qbit-impl.md)                               | [ ]    |
| 10  | Transmission API doc               | doc   | [phase-10-transmission-doc.md](phase-10-transmission-doc.md)                 | [ ]    |
| 11  | Transmission implementation        | impl  | [phase-11-transmission-impl.md](phase-11-transmission-impl.md)               | [ ]    |
| 12  | OMDB API doc                       | doc   | [phase-12-omdb-doc.md](phase-12-omdb-doc.md)                                 | [ ]    |
| 13  | OMDB implementation                | impl  | [phase-13-omdb-impl.md](phase-13-omdb-impl.md)                               | [ ]    |
| 14  | Trakt API doc                      | doc   | [phase-14-trakt-doc.md](phase-14-trakt-doc.md)                               | [ ]    |
| 15  | Trakt implementation               | impl  | [phase-15-trakt-impl.md](phase-15-trakt-impl.md)                             | [ ]    |
| 16  | Tracker base + ranking engine      | infra | [phase-16-tracker-base-ranking.md](phase-16-tracker-base-ranking.md)         | [ ]    |
| 17  | LaCale API doc                     | doc   | [phase-17-lacale-doc.md](phase-17-lacale-doc.md)                             | [ ]    |
| 18  | LaCale implementation              | impl  | [phase-18-lacale-impl.md](phase-18-lacale-impl.md)                           | [ ]    |
| 19  | C411 API doc                       | doc   | [phase-19-c411-doc.md](phase-19-c411-doc.md)                                 | [ ]    |
| 20  | C411 implementation                | impl  | [phase-20-c411-impl.md](phase-20-c411-impl.md)                               | [ ]    |
| 21  | Notify base + Telegram doc         | mixed | [phase-21-notify-base-telegram-doc.md](phase-21-notify-base-telegram-doc.md) | [ ]    |
| 22  | Telegram migration                 | impl  | [phase-22-telegram-impl.md](phase-22-telegram-impl.md)                       | [ ]    |
| 23  | Healthchecks API doc               | doc   | [phase-23-healthchecks-doc.md](phase-23-healthchecks-doc.md)                 | [ ]    |
| 24  | Healthchecks migration             | impl  | [phase-24-healthchecks-impl.md](phase-24-healthchecks-impl.md)               | [ ]    |
| 25  | Final cleanup + ROADMAP            | infra | [phase-25-final-cleanup.md](phase-25-final-cleanup.md)                       | [ ]    |

## Standard sub-phase scaffolding

Every phase ends with a **gate sub-phase** that:

1. Runs `make check && python3 scripts/check-module-size.py`.
2. Runs the residual-import grep listed in the phase.
3. Runs `make lint test` (when a code change occurred).
4. Verifies a targeted import smoke (`python -c "from personalscraper... import ..."`).
5. Commits a milestone: `chore(api-unify): phase N gate — <summary>`.

## Doc-phase interactive checkpoint format

Every **doc** phase ends with this exchange:

> Doc complete: `docs/reference/<provider>-api.md`.
> Particularities found:
>
> - <bullet list of API quirks, undocumented fields, rate limits, auth specifics>
>
> Proposed implementation scope (next phase):
>
> - Endpoints to wire: <list>
> - Typed models: <list>
> - Out of scope: <list>
>
> Confirm or adjust before next phase?

The user response must be captured in the phase commit message body. No code is written until confirmation.
