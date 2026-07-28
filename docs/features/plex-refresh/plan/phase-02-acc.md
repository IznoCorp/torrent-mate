# Phase 02 — Docs + env + ACC + preuve réelle

## Surface

`.env.example` (PLEX_URL/PLEX_TOKEN, valeurs vides, commentaires) ; `docs/reference/plex-api.md`
(client, auth, refresh partiel, mapping sections, fail-soft contract) + ligne d'index CLAUDE.md ;
CHANGELOG 0.59.0.

## ACC (DESIGN §ACC)

ACC-01→03 par tests ; **ACC-04 réel** : un refresh ciblé sur un dossier existant de la
médiathèque réelle → HTTP 200 (une seule requête) ; ACC-05 make check + audit strict.

## Gate

make check vert ; ACC 5/5 collés dans IMPLEMENTATION.md ; grep token réel sur docs/ + example → 0.
