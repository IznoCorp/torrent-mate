# Implementation Progress — mobile-shell

> For Claude: read this file at session start.

**Feature**: Garde structurelle anti-scroll-horizontal + bottom-bar fixe
**Type**: fix · **Version bump**: 0.59.0 → 0.59.1 (patch) · **Branch**: fix/mobile-shell
**Ticket**: #330 — claimed · **PR merge**: auto
**Design**: docs/features/mobile-shell/DESIGN.md · **Master plan**: docs/features/mobile-shell/plan/INDEX.md

## Contexte

Régression mobile récurrente (menu invisible sans scroll sur Contrôle, bottom-bar qui scrolle
horizontalement). Audit Chrome 390 px : `/` scrolle de 13 px (span non tronqué), 4 routes ont
des enfants débordant jusqu'à 444 px masqués par overflow-hidden. Cause : le shell
(AppShell.tsx) ne clampe pas le débordement horizontal. Fix STRUCTUREL + garde-fou exécutable
pour tuer la classe de bug.

## Phases

| #   | Phase                                         | File                                                                   | Status |
| --- | --------------------------------------------- | ---------------------------------------------------------------------- | ------ |
| 1   | Garde-fou d'abord (rouge-avant) + clamp shell | [phase-01](docs/features/mobile-shell/plan/phase-01-guard-clamp.md)    | [x]    |
| 2   | Coupables ponctuels + preuve réelle 390 px    | [phase-02](docs/features/mobile-shell/plan/phase-02-culprits-proof.md) | [x]    |

## ACC-05 — preuve réelle 390 px (staging tm-staging., 393dfde2, 2026-07-28)

Harnais iframe 390 px, 6 routes : `scrollWidth-innerWidth == 0` PARTOUT (Contrôle : 13 → 0),
bottom-bar fixe (bottom=844) et non-scrollable (barOvf=0) sur les 6. Les enfants larges
(pipeline 444, systeme 434, acquisition 430) sont désormais clippés par le shell — bombes
latentes désamorcées structurellement.

| route        | overflowX | barOvf | barBottom |
| ------------ | --------- | ------ | --------- |
| /            | 0         | 0      | 844       |
| /pipeline    | 0         | 0      | 844       |
| /medias      | 0         | 0      | 844       |
| /acquisition | 0         | 0      | 844       |
| /systeme     | 0         | 0      | 844       |
| /config      | 0         | 0      | 844       |

## Next action

feature-pr : PR + CI + review + merge + deploy.
