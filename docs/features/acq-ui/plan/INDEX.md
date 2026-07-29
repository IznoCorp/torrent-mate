# Implementation Plan — acq-ui

**Ticket**: #340 · **Design**: `docs/features/acq-ui/DESIGN.md` · **Branch**: `feat/acq-ui` · **Merge**: auto

## Phase table

| #   | Phase                                      | File                              | Status |
| --- | ------------------------------------------ | --------------------------------- | ------ |
| 1   | Structure — retrait box + fusion recherche | [phase-01](phase-01-structure.md) | [ ]    |
| 2   | Comportement — reset + sous-onglets        | [phase-02](phase-02-behaviour.md) | [ ]    |
| 3   | ACC + preuve 390 px + gate                 | [phase-03](phase-03-acc.md)       | [ ]    |

## Invariants

Tout front (aucun changement de contrat, `make openapi` sans dérive) · full-width à 390 px
(`scrollWidth-innerWidth==0`) · pas de duplication du hook add-by-id · rétro-compat des autres onglets.
