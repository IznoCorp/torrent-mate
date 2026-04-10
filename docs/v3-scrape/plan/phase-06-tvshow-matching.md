# Phase 6 — Matching séries (TVDB → TMDB fallback)

## Objectif

Implémenter le matching séries avec TVDB prioritaire et fallback TMDB.

## Sous-phases

### 3.6.1 — Matching séries via TVDB

- [ ] Implémenter `match_tvshow_tvdb(tvdb_client, title, year)` → MatchResult | None
- [ ] Rechercher sur TVDB → scorer → même logique de confiance que les films
- [ ] ⚠️ La recherche TVDB retourne des champs snake_case (`tvdb_id`, `image_url`, `first_air_time`) — utiliser `tvdb_id` (pas `id`) pour l'identifiant
- [ ] Récupérer les IDs croisés via `get_series(id)` → `remoteIds[]` :
  - IMDB : `sourceName=="IMDB"` + `type==2`
  - TMDB : `sourceName=="TheMovieDB.com"` + `type==12` (12 = séries TV, pas 10 qui est films)
- [ ] Tests avec des séries réelles de 002-TVSHOWS/

**Commit** : `v3.6.1: Implement TV show matching via TVDB`

### 3.6.2 — Fallback TMDB si TVDB échoue

- [ ] Implémenter `match_tvshow(tvdb_client, tmdb_client, title, year)` → MatchResult | None
- [ ] Flow : TVDB search → si pas de match ou confiance faible → TMDB search
- [ ] Combiner les résultats : TVDB prioritaire, TMDB en fallback
- [ ] Le `source` dans MatchResult indique "tvdb" ou "tmdb"
- [ ] Tests : cas où TVDB trouve, cas où seul TMDB trouve

**Commit** : `v3.6.2: Add TMDB fallback for TV show matching`

### 3.6.3 — Récupération des épisodes d'une saison

- [ ] Implémenter `get_episode_titles(match, season, lang="fra")` → dict[int, str]
- [ ] Si source=tvdb :
  - `tvdb_client.get_season_episodes(series_id, season)` → liste d'épisodes (noms en anglais)
  - Pour chaque épisode, appeler `get_episode_translation(episode_id, lang)` pour obtenir le titre FR
  - ⚠️ Codes langue TVDB en 3 chars : `fra` (pas `fr`)
- [ ] Si source=tmdb :
  - `tmdb_client.get_tv_season(tv_id, season)` → épisodes déjà en FR (via `language=fr-FR`)
- [ ] Retourner {episode_number: episode_title} pour le renommage
- [ ] Gérer le cas : saison n'existe pas dans l'API → log warning
- [ ] Gérer le cas : traduction FR indisponible → fallback titre anglais (`eng`), puis titre original si anglais absent
- [ ] Tests avec des saisons réelles

**Commit** : `v3.6.3: Implement episode title fetching for renaming`
