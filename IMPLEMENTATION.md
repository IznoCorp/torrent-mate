# Implementation Progress — scrape-follow-id

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Au scrape d'une série suivie, réutiliser l'ID TVDB du suivi (anti-split)
**Type**: fix
**Version bump**: 0.62.0 → 0.63.0 (minor)
**Branch**: feat/scrape-follow-id
**Ticket**: #338 — claimed
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/scrape-follow-id/DESIGN.md
**Master plan**: docs/features/scrape-follow-id/plan/INDEX.md

## Phases

| #   | Phase                             | File                                                                 | Status |
| --- | --------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Résolveur `resolve_followed_tvdb` | [phase-01](docs/features/scrape-follow-id/plan/phase-01-resolver.md) | [ ]    |
| 2   | Injection orchestrateur + wiring  | [phase-02](docs/features/scrape-follow-id/plan/phase-02-inject.md)   | [ ]    |
| 3   | ACC + gate                        | [phase-03](docs/features/scrape-follow-id/plan/phase-03-acc.md)      | [ ]    |

## Review cycles

_(filled by implement:pr-review)_

## Next action

Run `/implement:phase` (phase 1)
