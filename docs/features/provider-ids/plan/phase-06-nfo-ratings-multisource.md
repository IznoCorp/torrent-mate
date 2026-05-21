# Phase 6 — NFO Ratings Multi-Source + Uniqueid Default Canonical

## Goal

Étendre `_add_ratings` du `NFOGenerator` pour écrire un `<rating>` enfant par source disponible (themoviedb, imdb, rottentomatoes, metacritic), au format Plex prioritaire. Et appliquer Q6=A : `default="true"` sur l'uniqueid de la famille canonique.

## Gate (prerequisites)

- Phase 3 mergée (IMDb/RT façades fournissent les ratings).
- Phase 5 mergée (xref enrichment fournit les IDs xref qui contribuent aux uniqueid).

## Sub-phases

### 6.1 — Étendre `_add_ratings` pour accepter une liste de Notations

`personalscraper/scraper/nfo_generator.py:534-554` : signature actuelle `_add_ratings(root, data, rating_name="themoviedb")` → nouvelle signature `_add_ratings(root, ratings: list[Notation], canonical_source="themoviedb")`. Itère sur la liste, un `<rating>` enfant par source. Source qui match `canonical_source` reçoit `default="true"`.

**Backward compat** : maintenir le call site avec dict legacy en transformant interne vers `[Notation(source="themoviedb", value=..., votes=...)]`.

Commit : `feat(provider-ids): _add_ratings accepts multi-source Notation list`

### 6.2 — Caller side : passer la liste de Notations

Dans `generate_movie_nfo`, `generate_tvshow_nfo`, `generate_episode_nfo` : construire la liste de Notations depuis `_resolve_external_ids` ratings_dict + le rating natif TMDb existant. Appeler `_add_ratings(root, notations)`.

Commit : `feat(provider-ids): pass multi-source ratings to _add_ratings`

### 6.3 — `default="true"` selon canonical pour uniqueid (Q6=A)

`generate_episode_nfo` : marquer `<uniqueid type=canonical_provider default="true">`. Si canonical=tvdb → uniqueid tvdb default, tmdb sans default. Si canonical=tmdb → inverse. Lit `canonical_provider` depuis `show_data` (passé en argument).

Commit : `feat(provider-ids): uniqueid default attribute reflects canonical provider`

### 6.4 — Tests format Plex / Kodi

Tests qui valident le format de sortie NFO contre des fixtures de référence (XML golden files).

Commit : `test(provider-ids): golden NFO files for multi-source ratings + canonical default`

## Tests to write

- `test_add_ratings_writes_multiple_rating_children_in_one_ratings_element`
- `test_add_ratings_canonical_source_receives_default_true`
- `test_add_ratings_non_canonical_sources_no_default`
- `test_add_ratings_themoviedb_keeps_default_true_when_canonical` (compat)
- `test_add_ratings_max_attribute_set_correctly_per_source` (10 vs 100)
- `test_generate_episode_nfo_uniqueid_default_attribute_on_canonical_family` (Q6=A)
- `test_generate_episode_nfo_uniqueid_secondary_family_no_default`
- `test_generate_episode_nfo_tvdb_canonical_writes_uniqueid_tvdb_default_true`
- `test_generate_episode_nfo_tmdb_fallback_writes_uniqueid_tmdb_default_true`
- `test_nfo_golden_movie_with_all_ratings_matches_fixture` (golden)
- `test_nfo_golden_episode_with_all_ratings_matches_fixture` (golden)

## Acceptance criteria

- Un NFO épisode généré porte un bloc `<ratings>` avec un `<rating>` enfant par source disponible (themoviedb, imdb, rottentomatoes, metacritic).
- L'attribut `default="true"` apparait UNE seule fois dans `<ratings>` (sur la source canonical).
- L'attribut `default="true"` apparait UNE seule fois sur `<uniqueid>` (sur la famille canonique).
- Format compatible Plex ET Kodi (validation via golden files).

## Migration / config touch

Aucune (les NFOs sont régénérés au prochain process — pas de mass-update legacy ici, c'est le job de la phase 8 backfill).

## DESIGN reference

§7 (NFO format Plex prioritaire), §6.3 (nfo_generator étendu), §3 décision Q6.
