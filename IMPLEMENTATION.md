# Implementation Progress — game-hide

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Détecter les jeux (ISO) et les masquer de la médiathèque
**Type**: feat
**Version bump**: 0.60.0 → 0.61.0 (minor)
**Branch**: feat/game-hide
**Ticket**: #334 — claimed
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/game-hide/DESIGN.md
**Master plan**: docs/features/game-hide/plan/INDEX.md

## Phases

| #   | Phase                         | File                                                        | Status |
| --- | ----------------------------- | ----------------------------------------------------------- | ------ |
| 1   | Détection — `is_game_release` | [phase-01](docs/features/game-hide/plan/phase-01-detect.md) | [x]    |
| 2   | Filtre read-model + log       | [phase-02](docs/features/game-hide/plan/phase-02-filter.md) | [ ]    |
| 3   | ACC + preuve 390 px + gate    | [phase-03](docs/features/game-hide/plan/phase-03-acc.md)    | [ ]    |

## Review cycles

_(filled by implement:pr-review)_

## Next action

Run `/implement:phase` (phase 1)
