# Phase 5 — Xref Enrichment Sequential + \_resolve_external_ids

## Goal

Implémenter le **xref enrichment sequential** (Q1) : après le canonical fetch (TVDB ou TMDB selon disponibilité), un fetch xref sur l'autre provider enrichit les IDs sans toucher la famille canonique. Implémenter aussi `_resolve_external_ids(canonical_provider, series_ids)` qui appelle les façades (IMDb, RT) pour la validation Q5=B + récupération ratings.

## Gate (prerequisites)

- Phase 2 mergée (IDs propagés correctement).
- Phase 3 mergée (IMDb/RT façades disponibles).
- Phase 4 mergée (drift validator catch les incomplets).

## Sub-phases

### 5.1 — `_xref_enrichment` method dans `tv_service.py`

Nouvelle méthode `_xref_enrichment(api_episodes, canonical_provider, series_ids, season_nums)`. Sequential (pas async). Si canonical=tvdb : fetch TMDb season episodes pour les mêmes (s,e) tuples, merge `tmdb_episode_id` dans `api_episodes[(s,e)]` **uniquement si absent** (json_set if not exists pattern). Inverse si canonical=tmdb.

Commit : `feat(provider-ids): add _xref_enrichment sequential post-canonical`

### 5.2 — `_resolve_external_ids` method dans `tv_service.py`

Nouvelle méthode `_resolve_external_ids(canonical_provider, series_ids: dict[str, str]) -> tuple[dict, dict]`. Pour chaque famille (tvdb, tmdb, imdb) :

- Si la famille canonique = celle-là → ID déjà validé par le scrape principal.
- Sinon → appelle la façade correspondante (`TMDbClient.validate_id` ou `IMDbClient.validate_id`) pour confirmer titre/année (Q5=B).
- Récupère le rating via `IMDbClient.get_rating` + `RottenTomatoesClient.get_rating`.

Retourne `(external_ids_dict, ratings_dict)` série-level.

Commit : `feat(provider-ids): add _resolve_external_ids with Q5=B re-validation`

### 5.3 — Wire `_xref_enrichment` dans le flow `scrape_tvshow`

Modifier le flow `scrape_tvshow_canonical` pour appeler `_xref_enrichment` après le canonical fetch et avant la génération des episode NFOs. Les NFOs portent alors les uniqueid canonical + xref.

Commit : `feat(provider-ids): wire xref enrichment in scrape_tvshow flow`

### 5.4 — Réécriture NFOs xref-add (si déjà écrit avant xref)

Pour les NFOs déjà écrits par le canonical : ré-ouvrir, ajouter `<uniqueid type=other>` si absent, ré-écrire. **Pas d'écrasement** si déjà présent.

Commit : `feat(provider-ids): add xref uniqueid to existing episode NFOs without overwrite`

### 5.5 — Symétrique movie_service.py

Reproduire la logique de `_xref_enrichment` + `_resolve_external_ids` dans `movie_service.py` pour les films.

Commit : `feat(provider-ids): xref enrichment for movies in movie_service`

## Tests to write

- `test_xref_enrichment_adds_tmdb_to_tvdb_canonical_episodes`
- `test_xref_enrichment_does_not_overwrite_existing_tmdb_id`
- `test_xref_enrichment_sequential_called_after_canonical` (assertion ordre)
- `test_xref_enrichment_failure_does_not_break_canonical` (TMDb fail → log warning, scrape OK)
- `test_resolve_external_ids_revalidates_tmdb_via_get_tv` (Q5=B)
- `test_resolve_external_ids_revalidates_imdb_via_omdb` (Q5=B)
- `test_resolve_external_ids_returns_canonical_id_without_revalidation` (canonical = trusted)
- `test_xref_enrichment_for_movies_symmetric_to_tv`

## Acceptance criteria

- Un nouveau scrape TV TVDB-canonical produit des NFOs épisode avec `<uniqueid type="tvdb" default="true">` ET `<uniqueid type="tmdb">` (si TMDb dispo).
- Un fallback TVDB→TMDB produit des NFOs avec `<uniqueid type="tmdb" default="true">` ET `<uniqueid type="tvdb">` (si TVDB redevient dispo via xref).
- Xref failure n'aborte pas le scrape — log WARNING, scrape continue.
- Cross-contamination interdite : un test prouve qu'on ne remplace jamais un ID canonique par un ID xref.

## Migration / config touch

Aucune (changements code-only).

## DESIGN reference

§5 (Data flow §5.1 nominal §5.2 fallback), §6.3 (`_xref_enrichment` + `_resolve_external_ids`), §3 (séparation familles, idempotence).
