# Implementation Progress — episode-states

> For Claude: read this file at session start.

**Feature**: Statut « Annoncé » (épisodes futurs) + légende couleurs + date au clic
**Type**: feat · **Version bump**: 0.59.1 → 0.60.0 (minor) · **Branch**: feat/episode-states
**Ticket**: #332 — claimed · **PR merge**: auto
**Design**: docs/features/episode-states/DESIGN.md · **Master plan**: docs/features/episode-states/plan/INDEX.md

## Contexte

Tâches opérateur #9 (légende couleurs des puces) + #10 (statut « Annoncé » = épisodes futurs
connus, avec date de diffusion, affichée au clic) — groupées (même zone, la légende doit
inclure Annoncé). Décisions opérateur : tous les futurs connus (pas la saison courante seule) ;
1 couleur/statut ; date au clic sur chaque puce. Invariant : le cache stocke les futurs mais
la file wanted ne prend que les diffusés (un futur n'est pas cherchable).

## Phases

| #   | Phase                                   | File                                                              | Status |
| --- | --------------------------------------- | ----------------------------------------------------------------- | ------ |
| 1   | Backend — cache élargi + état `annonce` | [phase-01](docs/features/episode-states/plan/phase-01-backend.md) | [x]    |
| 2   | UI — statut, légende, date au clic      | [phase-02](docs/features/episode-states/plan/phase-02-ui.md)      | [ ]    |
| 3   | ACC + preuve 390 px + gate              | [phase-03](docs/features/episode-states/plan/phase-03-acc.md)     | [ ]    |

## Next action

/implement:phase (phase 1)
