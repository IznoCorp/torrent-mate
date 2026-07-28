# Phase 03 — ACC + preuve 390 px + gate

## Étapes

1. ACC-01→03 par tests (phases 1-2). ACC-04 : `make check` vert + `make openapi` sans drift.
2. ACC-05 — preuve terrain sur staging : déployer `feat/game-hide` sur tm-staging, vérifier
   (harnais Chrome 390 px) que `Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto` **n'apparaît
   plus** dans l'onglet Medias ; confirmer le log `staging_game_hidden` (staging logs) ; si un
   autre item « other » non-jeu existe, vérifier qu'il reste visible.
3. `make check` + `audit_design_coverage --strict` + `update_feature_map --check` + smoke import.

## Gate

ACC 5/5 (ou différé documenté daté) ; `make check` vert ; preuve 390 px + ligne de log collées
dans IMPLEMENTATION.md ; restaurer staging → main après la preuve.
