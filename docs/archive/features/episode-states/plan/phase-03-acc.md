# Phase 03 — ACC + preuve 390 px + gate

## Étapes

1. ACC-01→04 par tests backend ; ACC-05 UI par tests + **preuve Chrome 390 px** (harnais
   iframe sur staging) : puce annonce visible, légende présente (1 couleur/statut), date au
   clic sur un diffusé ET un annoncé, aucun popover clippé, `scrollWidth-innerWidth==0`.
2. Preuve réelle : une série suivie ayant des épisodes futurs (ex. Furious S01E04+ annoncés
   03/08) affiche bien les annoncés avec date — capture.
3. CHANGELOG 0.60.0.
4. `make check` + `audit_design_coverage --strict` + `update_feature_map --check` + smoke.

## Gate

ACC 6/6 (ou différé documenté daté) ; make check vert ; preuve 390 px collée dans
IMPLEMENTATION.md.
