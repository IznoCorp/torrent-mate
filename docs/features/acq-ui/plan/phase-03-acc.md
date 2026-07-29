# Phase 03 — ACC + preuve 390 px + gate

## Étapes
1. ACC-01→04 par tests (vitest). ACC-05 : `make check` + `make openapi` sans dérive.
2. Preuve Chrome 390 px sur `tm.` (post-déploiement) OU harnais iframe : full-width
   (`scrollWidth-innerWidth==0`), pas d'empty-state à vide, sous-onglets séries/films, reset après Suivre.
3. `make check` + smoke.

## Gate
ACC 5/5 ; `make check` vert ; preuve collée dans IMPLEMENTATION.md.
