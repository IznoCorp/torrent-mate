# Phase 01 — Backend : résolution TVDB pour les séries suivies par TMDB/IMDB

**Goal**: une série suivie par `tmdb_id`/`imdb_id` seul se voit rétro-remplir son `tvdb_id`
avant insertion (détection d'épisodes fonctionnelle), sinon `tvdb_unresolved=true` (non muet).

## Surface

| Fichier                                              | Action                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/api/metadata/tmdb.py`               | **NEW** `find_by_imdb(imdb_id: str) -> int \| None` : `GET /3/find/{imdb}?external_source=imdb_id`, renvoie `tv_results[0]["id"]` (tmdb) ou `None`. Réutilise le transport/policy existant ; docstring Google.                                                                                                 |
| `personalscraper/web/acquisition/` (helper ou route) | **NEW** `resolve_series_tvdb(media_ref, tmdb_client) -> int \| None` : si `tvdb_id` déjà set → le renvoyer ; sinon `tmdb_id = media_ref.tmdb_id or find_by_imdb(imdb_id)` ; si tmdb → `get_tv(tmdb).external_ids.get("tvdb")` (int). Fail-soft : toute exception → `None` (log WARNING). Pur d'effets DB.      |
| `personalscraper/web/routes/acquisition.py`          | Dans `create_follow`, si `body.kind == 'show'` et `media_ref.tvdb_id is None` : appeler `resolve_series_tvdb` (sous `scoped_provider_clients`), si résolu → reconstruire `media_ref` avec le `tvdb_id` AVANT `store.follow.add`. Sinon → poser `tvdb_unresolved=True` sur l'item de réponse. Films : inchangé. |
| `personalscraper/web/models/acquisition.py`          | `FollowedSeriesItem` gagne `tvdb_unresolved: bool = False` (transient, défaut False comme `priming_running`).                                                                                                                                                                                                  |
| tests                                                | ACC-01 (`find_by_imdb` golden), ACC-02 (résolution tmdb→tvdb et imdb→tvdb, spy provider, media_ref stocké porte le tvdb_id), ACC-03 (non résoluble → suivi créé + `tvdb_unresolved=True`, pas d'exception), ACC-04 (film tmdb/imdb → aucune résolution appelée, suivi créé).                                   |

## Règles

- **Séparation multi-provider** : TVDB reste primaire ; TMDB/IMDB ne servent qu'à le résoudre.
- **Fail-soft NON muet** : jamais d'exception qui bloque le 201 ; une série non résolue est créée
  mais signalée (`tvdb_unresolved`) — pas de suivi inerte silencieux (§méthode).
- Résolution bornée : ≤ 2 appels provider synchrones, sous `scoped_provider_clients`
  (`max_attempts=1`).
- `make openapi` : `tvdb_unresolved` dans schema.d.ts (commit régénéré).

## Gate

`make check` vert ; `make openapi` sans drift non commité ; rouge-avant vérifié sur ACC-02/03.
