# Phase 3 — Client API TMDB

## Objectif

Implémenter le client HTTP complet pour l'API TMDB v3.

## Sous-phases

### 3.3.1 — Base HTTP + authentification

- [ ] Créer `personalscraper/scraper/tmdb_client.py`
- [ ] Implémenter `TMDBClient.__init__(api_key, language)` avec session requests
- [ ] Méthode privée `_get(endpoint, params)` avec :
  - Auth par query param `api_key`
  - Language param automatique
  - Timeout 10s
  - Retry 3x avec backoff exponentiel
  - Logging des requêtes
- [ ] Tests : vérifier qu'un appel basique fonctionne

**Commit** : `v3.3.1: Implement TMDB client base HTTP with retry`

### 3.3.2 — Recherche films et séries

- [ ] Implémenter `search_movie(title, year=None)` → list[dict]
- [ ] Implémenter `search_tv(title, year=None)` → list[dict]
- [ ] Normalisation du titre avant recherche (strip accents optionnel)
- [ ] Tests avec l'API réelle : rechercher "The Piano Lesson", "Shrinking"

**Commit** : `v3.3.2: Implement TMDB search for movies and TV shows`

### 3.3.3 — Détails et crédits

- [ ] Implémenter `get_movie(movie_id)` → dict (avec `append_to_response=credits`)
- [ ] Implémenter `get_tv(tv_id)` → dict (avec `append_to_response=credits`)
- [ ] Implémenter `get_tv_season(tv_id, season)` → dict (liste épisodes + titres)
- [ ] Tests : vérifier les champs retournés (title, year, genres, cast, ids)

**Commit** : `v3.3.3: Implement TMDB movie/tv details with credits`

### 3.3.4 — Images et URLs

- [ ] Implémenter `get_movie_images(movie_id)` → dict (posters, backdrops)
- [ ] Implémenter `get_tv_images(tv_id)` → dict
- [ ] Implémenter `get_image_url(path, size="original")` → URL complète
- [ ] Sélection de la meilleure image par langue (fr-FR > en > null > other)
- [ ] Tests : vérifier que les URLs sont valides (HEAD request optionnel)

**Commit** : `v3.3.4: Implement TMDB image fetching and URL building`
