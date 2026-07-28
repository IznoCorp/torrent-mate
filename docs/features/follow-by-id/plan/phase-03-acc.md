# Phase 03 — ACC + preuve 390 px + gate

## Étapes

1. ACC-01→04 par tests backend ; ACC-05 par vitest + **preuve Chrome 390 px** sur `tm.` (prod,
   post-déploiement) OU harnais iframe : le sélecteur TVDB/TMDB/IMDB est présent, IMDB validé,
   un ajout par TMDB fonctionne.
2. **Preuve réelle** : suivre une série connue par son `tmdb_id` (ex. une série ayant un mapping
   TVDB) et vérifier en base que le `media_ref` stocké porte bien le `tvdb_id` résolu (donc
   `poll_known` la détectera) ; suivre un cas sans mapping et vérifier `tvdb_unresolved`.
3. `make check` + `make openapi` (schema.d.ts régénéré) + `audit_design_coverage --strict` +
   `update_feature_map --check` + smoke.

## Gate

ACC 6/6 (ou différé documenté daté) ; `make check` vert ; preuve collée dans IMPLEMENTATION.md.
