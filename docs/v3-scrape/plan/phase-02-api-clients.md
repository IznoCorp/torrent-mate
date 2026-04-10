# Phase 2 — Clients API (TMDB + TVDB)

## Objectif

Implémenter les clients HTTP pour TMDB et TVDB.

## Sous-phases

### 3.2.1 — Client TMDB

- [ ] Créer `personalscraper/scraper/tmdb_client.py`
- [ ] Implémenter `TMDBClient.__init__(api_key, language)`
- [ ] Implémenter `search_movie(title, year)` et `get_movie(id)`
- [ ] Implémenter `search_tv(title, year)`, `get_tv(id)`, `get_tv_season(id, season)`
- [ ] Implémenter `get_movie_images(id)`, `get_tv_images(id)`
- [ ] Implémenter `get_image_url(path, size)`
- [ ] Retry logic (3 tentatives, backoff exponentiel)
- [ ] Tests avec l'API réelle (1-2 requêtes de validation)

**Commit** : `v3.2.1: Implement TMDB API client`

### 3.2.2 — Client TVDB

- [ ] Créer `personalscraper/scraper/tvdb_client.py`
- [ ] Implémenter `TVDBClient.__init__(api_key)` + `login()` (bearer token)
- [ ] Implémenter `search_series(title)`
- [ ] Implémenter `get_series(id)`, `get_season_episodes(id, season)`
- [ ] Implémenter `get_series_artworks(id)`
- [ ] Retry logic + token refresh
- [ ] Tests avec l'API réelle

**Commit** : `v3.2.2: Implement TVDB API client`
