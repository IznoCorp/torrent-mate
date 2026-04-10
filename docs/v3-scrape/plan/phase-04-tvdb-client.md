# Phase 4 — Client API TVDB

## Objectif

Implémenter le client HTTP pour l'API TVDB v4 (séries prioritaire).

## Sous-phases

### 3.4.1 — Authentification bearer token

- [ ] Créer `personalscraper/scraper/tvdb_client.py`
- [ ] Implémenter `TVDBClient.__init__(api_key)` avec session requests
- [ ] Implémenter `login()` : POST `/login` → bearer token
- [ ] Stocker le token dans la session (header Authorization)
- [ ] Implémenter le refresh automatique si token expiré (401 → re-login)
- [ ] Méthode privée `_get(endpoint)` avec retry, timeout, auth
- [ ] Tests : vérifier login + token obtenu

**Commit** : `v3.4.1: Implement TVDB client with bearer token auth`

### 3.4.2 — Recherche séries

- [ ] Implémenter `search_series(title)` → list[dict]
- [ ] Parser les résultats : id, name, year, overview, status
- [ ] Normalisation titre avant recherche
- [ ] Tests avec l'API réelle : rechercher "Shrinking", "The Boys"

**Commit** : `v3.4.2: Implement TVDB series search`

### 3.4.3 — Détails série et épisodes

- [ ] Implémenter `get_series(series_id)` → dict (détails complets)
- [ ] Implémenter `get_season_episodes(series_id, season)` → list[dict]
- [ ] Parser les épisodes : number, name, overview, aired, runtime
- [ ] Gérer la pagination si nécessaire (API TVDB peut paginer)
- [ ] Tests : vérifier les données d'une série connue

**Commit** : `v3.4.3: Implement TVDB series details and episode listing`

### 3.4.4 — Artworks et IDs croisés

- [ ] Implémenter `get_series_artworks(series_id)` → list[dict]
- [ ] Filtrer par type : poster, fanart, season poster
- [ ] Récupérer les IDs croisés (IMDB, TMDB) depuis les données série
- [ ] Tests : vérifier les URLs artwork et les IDs croisés

**Commit** : `v3.4.4: Implement TVDB artworks and cross-reference IDs`
