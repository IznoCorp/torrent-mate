# Implementation Plan — game-hide

**Ticket**: #334 · **Design**: `docs/features/game-hide/DESIGN.md` · **Branch**: `feat/game-hide` · **Merge**: auto

## Phase table

| #   | Phase                         | File                                     | Status |
| --- | ----------------------------- | ---------------------------------------- | ------ |
| 1   | Détection — `is_game_release` | [phase-01-detect.md](phase-01-detect.md) | [ ]    |
| 2   | Filtre read-model + log       | [phase-02-filter.md](phase-02-filter.md) | [ ]    |
| 3   | ACC + preuve 390 px + gate    | [phase-03-acc.md](phase-03-acc.md)       | [ ]    |

## Invariants

Précision-first (jamais masquer un vrai média) · une image disque de FILM (token video-release)
n'est JAMAIS un jeu · prédicat pur (nom + extensions, testable golden) · aucune disparition
silencieuse (log `staging_game_hidden`) · zéro changement de config partagée · l'item existant
`Marvels.Spider-Man.2` est auto-masqué par le filtre (aucune migration).
