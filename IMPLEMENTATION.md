# Implementation Progress — acq-debt

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Reliquat de review PR #320 + dette de modules
**Type**: fix
**Version bump**: 0.57.1 → 0.58.0 (minor)
**Branch**: fix/acq-debt
**Ticket**: #324 — claimed (session locale, heartbeat actif)
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/acq-debt/DESIGN.md
**Master plan**: `docs/features/acq-debt/plan/INDEX.md`

## Contexte

Solde les ouverts « PR #320 review » (M6 I/O borné, M9 hash d'intention pré-add,
carte film open-rows-latest, m15 taxons d'erreur SearchOutcome, m23 close registry,
m24 index partiel) + splits `routes/acquisition.py` et `acquire/service.py` sous 800.
ACC-12 de #320 (clic réel + 390 px) rattaché — fenêtre visée : 15:10-15:20 du jour
si tr4ker rend les épisodes American Dad disponibles.

## Phases

| #   | Phase                                         | File                                                              | Status |
| --- | --------------------------------------------- | ----------------------------------------------------------------- | ------ |
| 1   | M9 — hash d'intention pré-add                 | [phase-01](docs/features/acq-debt/plan/phase-01-intent-hash.md)   | [x]    |
| 2   | m15 — taxons d'erreur SearchOutcome           | [phase-02](docs/features/acq-debt/plan/phase-02-error-taxa.md)    | [ ]    |
| 3   | M6 + m23 — I/O borné + registry fermé         | [phase-03](docs/features/acq-debt/plan/phase-03-bounded-io.md)    | [ ]    |
| 4   | D3 + m24 — carte film + index partiel         | [phase-04](docs/features/acq-debt/plan/phase-04-film-index.md)    | [ ]    |
| 5   | D6 — splits de modules                        | [phase-05](docs/features/acq-debt/plan/phase-05-splits.md)        | [ ]    |
| 6   | ACC + gate finale (+ ACC-12 réel de #320)     | [phase-06](docs/features/acq-debt/plan/phase-06-acc.md)           | [ ]    |

## Review cycles

_(après implement:pr-review)_

## Next action

/implement:phase (phase 1)
