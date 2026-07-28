# Implementation Plan — episode-states

**Ticket**: #332 · **Design**: `docs/features/episode-states/DESIGN.md` · **Branch**: `feat/episode-states` · **Merge**: auto

## Phase table

| #   | Phase                                   | File                                       | Status |
| --- | --------------------------------------- | ------------------------------------------ | ------ |
| 1   | Backend — cache élargi + état `annonce` | [phase-01-backend.md](phase-01-backend.md) | [ ]    |
| 2   | UI — statut, légende, date au clic      | [phase-02-ui.md](phase-02-ui.md)           | [ ]    |
| 3   | ACC + preuve 390 px + gate              | [phase-03-acc.md](phase-03-acc.md)         | [ ]    |

## Invariants

Cache-connu ≠ file-cherchable (un futur ne s'enfile jamais) · un seul poll provider par série ·
`annonce` ne dégrade pas la carte · vocabulaire source-unique meta.ts · contrat typé régénéré.
