# Phase 03 — ACC + gate

## Étapes

1. ACC-01→04 par tests (phases 1-2). ACC-05 : `make check` vert + `make openapi` sans dérive
   (aucun changement de contrat web).
2. Preuve : un test d'intégration (ou une trace) montrant qu'un dossier de show correspondant à des
   `wanted` grabbed d'un suivi déclenche `scrape_tvshow_forced` avec le tvdb du suivi (pas un re-match
   d'une fiche concurrente). Cas Rooster (457770) comme golden.
3. `make check` + `audit_design_coverage --strict` + `update_feature_map --check` + smoke.

## Gate

ACC 5/5 ; `make check` vert ; preuve collée dans IMPLEMENTATION.md.
