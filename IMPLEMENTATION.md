# Implementation Progress — reswitch

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Auto-bascule d'une release bloquée + seeders renforcés dans le score
**Type**: feat
**Version bump**: 0.64.0 → 0.65.0 (minor)
**Branch**: feat/reswitch
**Ticket**: #342 — claimed
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/reswitch/DESIGN.md
**Master plan**: docs/features/reswitch/plan/INDEX.md

## Phases

| #   | Phase                                          | File                                                          | Status |
| --- | ---------------------------------------------- | ------------------------------------------------------------- | ------ |
| 1   | Seeders renforcés (config + test)              | [phase-01](docs/features/reswitch/plan/phase-01-seeders.md)   | [x]    |
| 2   | Observabilité swarm (`swarm_seeds` + classify) | [phase-02](docs/features/reswitch/plan/phase-02-swarm.md)     | [ ]    |
| 3   | Mémoire hashes tentés + exclusion ranking      | [phase-03](docs/features/reswitch/plan/phase-03-exclusion.md) | [ ]    |
| 4   | Acteur de rebascule (`reswitch_stalled`)       | [phase-04](docs/features/reswitch/plan/phase-04-actor.md)     | [ ]    |
| 5   | Surfaçage UI + events + ACC + déploiement      | [phase-05](docs/features/reswitch/plan/phase-05-acc.md)       | [ ]    |

## Review cycles

_(filled by implement:pr-review)_

## Next action

Run `/implement:phase` (phase 1)
