# Phase 3 — Client API TMDB

> Ref : [docs/TMDB-API.md](../../TMDB-API.md) — documentation complète vérifiée par tests live

## Objectif

Implémenter le client HTTP complet pour l'API TMDB v3.

## Sous-phases

### 3.3.1 — Base HTTP + authentification

- [ ] Créer `personalscraper/scraper/tmdb_client.py`
- [ ] Implémenter `TMDBClient.__init__(api_key, language)` avec session requests
- [ ] Implémenter le MetadataProvider Protocol (search, get_details, get_artwork_urls)
- [ ] Méthode privée `_get(endpoint, params)` décorée `@retry` (tenacity) :
  - Auth par header `Authorization: Bearer {token}` (recommandé par TMDB, pas query param)
  - Language param automatique
  - Timeout 10s
  - tenacity : `wait_exponential_jitter(multiplier=0.5, max=10, jitter=0.5)`, `stop_after_attempt(4)`, `reraise=True`
  - `retry_if_exception` : retry sur 429/500/502/503/504 et ConnectionError/Timeout
  - Ne PAS retrier sur HTTP 401/403/404 (erreurs fatales ou absence de résultat)
  - `before_sleep=before_sleep_log(logger, logging.WARNING)` pour tracer les retries
  - Gestion des erreurs TMDB : parser `status_code` interne (7=clé invalide, 34=not found, 25=rate limit)
  - Ref : [docs/tenacity-reference.md](../../tenacity-reference.md) — pattern TMDB
- [ ] Tests : vérifier qu'un appel basique fonctionne + retry sur mock 429

**Commit** : `v3.3.1: Implement TMDB client base HTTP with tenacity retry`

### 3.3.2 — Recherche films et séries

- [ ] Implémenter `search_movie(title, year=None)` → list[dict]
- [ ] Implémenter `search_tv(title, year=None)` → list[dict]
  - ⚠️ Utiliser `first_air_date_year` (pas `year`) pour les séries
- [ ] Normalisation du titre avant recherche (strip accents optionnel)
- [ ] ⚠️ `year` booste la pertinence mais N'EXCLUT PAS les autres années (vérifié) — le scoring en phase 5 doit filtrer côté client
- [ ] ⚠️ Recherche vide = HTTP 200 avec `results: []` — vérifier `len(results)`, pas le status HTTP
- [ ] Tests avec l'API réelle : rechercher "Le Comte de Monte-Cristo" (2024), "Lupin"

**Commit** : `v3.3.2: Implement TMDB search for movies and TV shows`

### 3.3.3 — Détails, crédits et IDs (via append_to_response)

- [ ] Implémenter `get_movie(movie_id)` → dict avec `append_to_response=credits,images,external_ids,release_dates` et `include_image_language=fr,en,null`
  - ⚠️ `include_image_language` est OBLIGATOIRE sinon 5x-31x moins d'images (vérifié)
  - Certification FR : extraire de `release_dates.results[]` → `iso_3166_1=="FR"` → `type==3` (theatrical)
- [ ] Implémenter `get_tv(tv_id)` → dict avec `append_to_response=aggregate_credits,images,external_ids,content_ratings` et `include_image_language=fr,en,null`
  - ⚠️ Utiliser `aggregate_credits` (pas `credits`) pour les séries — regroupe les rôles multiples via `roles[]`/`jobs[]`
  - ⚠️ `episode_run_time` est vide pour les séries récentes — utiliser `runtime` par épisode dans season details
  - Certification FR séries : extraire de `content_ratings.results[]` → `iso_3166_1=="FR"` → `rating`
- [ ] Implémenter `get_tv_season(tv_id, season)` → dict avec `append_to_response=images`
  - Retourne tous les épisodes avec `crew[]`, `guest_stars[]`, `runtime` (fiable, par épisode)
  - Season images ne retournent que des `posters` (pas de backdrops)
- [ ] Tests : vérifier les champs retournés (title, year, genres, cast, ids, images)

**Commit** : `v3.3.3: Implement TMDB movie/tv details with append_to_response`

### 3.3.4 — Sélection d'images et URLs

- [ ] Implémenter `get_image_url(path, size="original")` → URL complète (`https://image.tmdb.org/t/p/{size}{path}`)
- [ ] Implémenter `select_best_image(images, image_type)` → sélection par priorité langue :
  1. `iso_639_1 == "fr"` (image française)
  2. `iso_639_1 == "en"` (fallback anglais)
  3. `iso_639_1 is None` (image neutre, sans texte — majorité des backdrops)
  4. Au sein d'une même langue, trier par `vote_average` descendant
- [ ] ⚠️ Les images sont DÉJÀ dans la réponse de `get_movie()`/`get_tv()` via `append_to_response` — PAS besoin d'endpoints séparés `get_movie_images()`/`get_tv_images()`
- [ ] Tests : vérifier que les URLs sont valides (HEAD request optionnel)

**Commit** : `v3.3.4: Implement image selection logic and URL building`
