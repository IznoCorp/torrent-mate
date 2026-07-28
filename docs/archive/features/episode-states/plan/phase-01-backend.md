# Phase 01 — Backend : cache élargi + état `annonce`

**Goal**: le cache stocke les épisodes futurs, l'état `annonce` est dérivé, la file `wanted`
reste sur les seuls diffusés. Contrat régénéré.

## Surface

| Fichier                                           | Action                                                                                                                                                                                                                                                       |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `personalscraper/acquire/airing.py`               | `poll_known` (ou `poll_aired(..., include_future=True)`) : retourne TOUS les épisodes à date connue, chacun avec `air_date` ; UN seul appel provider par série (ne pas re-poll). Garder `poll_aired` (diffusés) pour l'enfilage, ou dériver l'un de l'autre. |
| `personalscraper/acquire/detect.py`               | `_persist_aired_cache` écrit le résultat élargi (futurs compris) ; **`_enqueue` garde le filtre `air_date <= today`** — un futur ne devient jamais un `wanted`.                                                                                              |
| `personalscraper/web/acquisition/states.py`       | `EpisodeState += "annonce"` ; `derive_episode_state(…, air_date, today)` retourne `annonce` en TÊTE si `air_date > today`.                                                                                                                                   |
| `personalscraper/web/acquisition/completeness.py` | passe `air_date`/`today` à la dérivation ; `SeasonCompleteness` gagne un compteur `announced` (les diffusés restent dans owned/queued/total).                                                                                                                |
| `personalscraper/web/models/acquisition.py`       | `EpisodeState` (régénéré), `SeasonCompleteness.announced: int` ; agrégation carte : `annonce` NE remonte PAS au `FollowStatus`.                                                                                                                              |
| tests                                             | ACC-01 (futur → cache, pas wanted), ACC-02 (dérivation annonce, rouge-avant), ACC-03 (carte à jour malgré futurs), ACC-04 (un seul poll — spy).                                                                                                              |

## Règles

- `annonce` hors des compteurs d'action de la carte et hors du `FollowStatus` agrégé.
- Pas de migration (le cache garde son schéma ; `air_date` porte la distinction).
- `make openapi` : `annonce` + `announced` dans schema.d.ts (commit régénéré).

## Gate

`make check` vert ; rouge-avant vérifié ; `make openapi` sans drift non commité ;
`rg -n "poll_aired\|poll_known" -t py` — un seul poll par série (pas de double appel).
