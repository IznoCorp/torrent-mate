# Phase 4 — Client API TVDB

> Ref : [docs/TVDB-API.md](../../TVDB-API.md) — documentation complète vérifiée par tests live

## Objectif

Implémenter le client HTTP pour l'API TVDB v4 (séries prioritaire).

## Sous-phases

### 3.4.1 — Authentification bearer token + mapping langues

- [x] Créer `personalscraper/scraper/tvdb_client.py`
- [x] Implémenter `TVDBClient.__init__(api_key)` avec session requests
- [x] Implémenter `login()` : POST `/login` avec `{"apikey": "..."}` (sans PIN pour clé Negotiated Contract)
- [x] Stocker le token dans la session (header `Authorization: Bearer {token}`)
- [x] Token valide 1 mois — implémenter re-login automatique si HTTP 401
- [x] ⚠️ Deux formats d'erreur : login retourne `{status, message, data}`, endpoints retournent `{message}` seul
- [x] Implémenter le MetadataProvider Protocol (search, get_details, get_artwork_urls)
- [x] Méthode privée `_get(endpoint, params)` décorée `@retry` (tenacity) :
  - `wait_exponential(multiplier=1, min=1, max=30)`, `stop_after_attempt(3)`, `reraise=True`
  - `before_sleep=before_sleep_log(logger, logging.WARNING)`
  - Ref : [docs/tenacity-reference.md](../../tenacity-reference.md) — pattern TVDB
- [x] Implémenter `LANG_MAP` : conversion codes internes pipeline (2-chars) → codes TVDB API (3-chars) (`fr`→`fra`, `en`→`eng`)
  - ⚠️ `shortCode` dans `/languages` est toujours null — mapping manuel obligatoire
  - Appliqué AVANT chaque appel API nécessitant un code langue (get_episode_translation, etc.)
- [x] Tests : 14 tests (login, auto-login, re-login on 401, lang mapping, retry)

**Commit** : `v3.4.1: Implement TVDB client with bearer token auth`

### 3.4.2 — Recherche séries

- [x] Implémenter `search_series(title, year=None)` → list[dict]
- [x] ⚠️ La recherche retourne des champs en snake_case (`image_url`, `first_air_time`, `tvdb_id`) — passés en l'état (normalisation côté matching en P5-P6)
- [x] ⚠️ Recherche vide = HTTP 200 avec `data: []` (pas 404) — vérifié dans tests
- [x] Tests : 4 tests (basic search, with year, empty, protocol dispatch)

**Commit** : `v3.4.2: Implement TVDB series search`

### 3.4.3 — Détails série et épisodes

- [x] Implémenter `get_series(series_id)` → dict via `GET /series/{id}/extended?short=true`
  - `short=true` exclut artworks/characters/trailers (réduit le payload)
  - ⚠️ `short=true` met les arrays à `null` (pas `[]`) — testé avec `is not None`
- [x] Implémenter `get_season_episodes(series_id, season)` → list[dict] via `GET /series/{id}/episodes/default?season={n}&page=0`
  - ⚠️ Pagination 0-indexed (page=0 est la première page)
  - ⚠️ Sans `?season=N`, retourne TOUS les épisodes y compris spéciaux (saison 0)
- [x] Implémenter `get_episode_translation(episode_id, lang)` → dict via `GET /episodes/{id}/translations/{lang}`
  - ⚠️ Codes langue 3 chars : `fra`, `eng` (pas `fr`, `en`) — auto-conversion via LANG_MAP
  - Returns None on 404 (missing translation)
- [x] Tests : 7 tests (short=true, genres, null arrays, episodes, translations, 404)

**Commit** : `v3.4.3: Implement TVDB series details and episode listing`

### 3.4.4 — Artworks, artwork types cache, et IDs croisés

- [x] Au démarrage, appeler `GET /artwork/types` et cacher le résultat (données stables, 27 types)
  - Types utiles : 2=Poster série, 3=Background série, 7=Poster saison, 14=Poster film, 15=Background film, 23=ClearLogo série
  - ⚠️ Pas de type "landscape" ni "discart" dans TVDB — Background (1920×1080) est l'équivalent
- [x] Implémenter `get_series_artworks(series_id, type_id=None)` → list[dict]
  - ⚠️ Retourne un `SeriesExtendedRecord`, pas juste les artworks — extraire `data.artworks`
  - Filtrer par type via `?type={id}` (ex: `?type=2` pour posters uniquement)
- [x] Extraire les IDs croisés depuis `remoteIds[]` de get_series()
  - ⚠️ TMDB a 4 source type IDs différents : 10=films, 12=séries TV, 15=personnes, 28=collections
  - Pour les séries : chercher `sourceName=="TheMovieDB.com"` + `type==12`
  - Pour IMDB : chercher `sourceName=="IMDB"` + `type==2`
- [x] Tests : 7 tests (artworks, type filter, cache, remote IDs, null IDs, protocol)

**Commit** : `v3.4.4: Implement TVDB artworks and cross-reference IDs`
