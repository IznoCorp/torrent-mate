# Implementation Plan — mobile-shell

**Ticket**: #330 · **Design**: `docs/features/mobile-shell/DESIGN.md` · **Branch**: `fix/mobile-shell` · **Merge**: auto

## Phase table

| #   | Phase                                         | File                                                     | Status |
| --- | --------------------------------------------- | -------------------------------------------------------- | ------ |
| 1   | Garde-fou d'abord (rouge-avant) + clamp shell | [phase-01-guard-clamp.md](phase-01-guard-clamp.md)       | [ ]    |
| 2   | Coupables ponctuels + preuve réelle 390 px    | [phase-02-culprits-proof.md](phase-02-culprits-proof.md) | [ ]    |

## Invariants

Le garde-fou est écrit et rouge AVANT le clamp (il prouve qu'il attrape la régression). Aucune
régression sur la sidebar desktop (≥ md). Viewport de test réel 390 px.
