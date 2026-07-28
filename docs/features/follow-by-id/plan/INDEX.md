# Implementation Plan — follow-by-id

**Ticket**: #336 · **Design**: `docs/features/follow-by-id/DESIGN.md` · **Branch**: `feat/follow-by-id` · **Merge**: auto

## Phase table

| #   | Phase                            | File                                         | Status |
| --- | -------------------------------- | -------------------------------------------- | ------ |
| 1   | Backend — résolution TVDB séries | [phase-01-backend.md](phase-01-backend.md)   | [ ]    |
| 2   | Frontend — sélecteur de provider | [phase-02-frontend.md](phase-02-frontend.md) | [ ]    |
| 3   | ACC + preuve 390 px + gate       | [phase-03-acc.md](phase-03-acc.md)           | [ ]    |

## Invariants

TVDB reste le primaire de scrape/détection (séparation multi-provider) · une série suivie par
TMDB/IMDB voit son TVDB résolu AVANT insertion, sinon `tvdb_unresolved=true` (jamais de suivi
inerte muet, §méthode) · les films ne requièrent pas de TVDB (cycle titre) · ≤ 2 appels provider
bornés · contrat typé régénéré (`make openapi`).
