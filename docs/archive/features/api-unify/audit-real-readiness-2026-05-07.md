# api-unify — audit de readiness réelle

**Date**: 2026-05-07
**Auteur**: pipeline-monitor run on local machine, exercising the full pipeline end-to-end against real qBittorrent + real disks.
**Branche évaluée**: `feat/api-unify` au commit `b77ebde` (`docs(api-unify): record review cycle 2 — fixes verified by gates, ready for merge`)
**Verdict**: **PAS prête à merger**. Le label "ready for merge" est trompeur.

---

## 1. Résumé exécutif

Le pipeline ne peut PAS tourner en production sur cette branche dans son état pre-fix. 5 bugs critiques bloquaient déjà le démarrage (config, ingest), et au moins 4-5 modules consumer-side n'ont jamais été migrés vers les modèles Pydantic typés (`SearchResult`, `MediaDetails`, etc.) malgré que les API clients les retournent. Un `# TODO(api-unify): migrate _tvdb_series_to_show_data to accept MediaDetails` a même été commité en l'état avec un `# type: ignore[arg-type]` pour faire passer mypy.

Les 5 phases de PR review (cycle 1 + 2) ont surtout audité **du code en isolation, mocké contre les fixtures de test**. Les fixtures de test elles-mêmes utilisent encore les anciennes shapes dict, ce qui masque la divergence avec ce que les API clients renvoient maintenant. **Aucun cycle de review n'a invoqué `personalscraper run` from a fresh shell**.

## 2. Bugs corrigés sur la branche pendant l'audit (5 commits)

| Commit    | Bug                                                                                                                                 | Fichiers                                                                                                                               |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `5689a5c` | #5 — `load_dotenv()` non appelé au démarrage CLI → toutes les creds invisibles                                                      | `personalscraper/__init__.py` (+ test subprocess)                                                                                      |
| `55a4b47` | #6 — `QBIT_HOST`/`QBIT_PORT`, `TRANSMISSION_HOST`/`PORT` legacy env vars silently ignorés                                           | `conf/loader.py` warning + .env.example cleanup + CONFIGURATION.md migration section + test fixture realignment                        |
| `b6848fa` | #8 — `TorrentItem.ratio` field absent → `min_ratio` gate fail-open sur 100% des qBit torrents                                       | `api/torrent/_base.py` + `api/torrent/qbittorrent.py` + `transmission.py` (+ tests parity)                                             |
| `8c75404` | #3 + #9 — typos templates : `HEALTHCHECK_PING_URL` (code attend `HEALTHCHECK_URL`), `TRAKT_CLIENT_SECRET` cité (code n'en veut pas) | `config.example/notify.json5`, `config.example/metadata.json5`                                                                         |
| `ac4959f` | #10 (partiel) — `confidence.py` matching utilisait `.get()` sur `SearchResult`                                                      | `scraper/confidence.py` + `tests/scraper/test_confidence.py` + `tests/integration/conftest.py` (FakeTMDB/FakeTVDB return SearchResult) |

Tous : 2802 tests pass, lint clean, vérifiés concrètement par re-run du pipeline ou tests subprocess.

## 3. Bugs trouvés mais NON corrigés (dette technique cachée)

### 3.1 TODO + type:ignore explicite laissé dans le code

`scraper/tv_service.py:497` :

```python
# TODO(api-unify): migrate _tvdb_series_to_show_data to accept MediaDetails
show_data = _tvdb_series_to_show_data(
    tvdb_data,  # type: ignore[arg-type]
    ...
)
```

Le dev savait que `_tvdb_series_to_show_data` n'avait pas été migré, a inséré un `type: ignore` pour faire passer mypy, et a quand même labellisé la branche "ready to merge".

### 3.2 Consumer modules toujours en mode dict (≈ 25 sites)

Tous ces fichiers reçoivent maintenant des `MediaDetails` / `SearchResult` / etc. typés, mais accèdent encore aux champs en mode dict (`.get("...")`) :

| Fichier                         | Sites    | Notes                                                                                                                                                                               |
| ------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scraper/classifier.py`         | 8 sites  | `api_data.get("genres")`, `origin_country`, `production_countries`, `original_title`, `original_name` — la classification de catégories par genre est cassée                        |
| `scraper/artwork.py`            | 14 sites | `images.get("posters")`, `backdrops`, `seasons`, `vote_average`, `iso_639_1`, `file_path` — la sélection d'artwork multi-langue est cassée                                          |
| `scraper/episode_manager.py`    | 3 sites  | `ep.get("season_number")`, `seasonNumber`, `still_path` — la création de dossiers `Saison XX/` est cassée                                                                           |
| `scraper/confidence.py:225-226` | 2 sites  | `series.get("seasons")`, `season.get("number")` dans `_candidate_has_any_season` — la disambiguation par seasons est CASSÉE (la seasons list n'existe même pas dans `MediaDetails`) |

**Sans ces fixes, PROCESS échoue avec `AttributeError: 'MediaDetails' object has no attribute 'get'` sur 100% des items**. Vérifié sur un run réel ce 2026-05-07.

### 3.3 Champs perdus dans la migration vers les modèles typés

`MediaDetails` (le successeur typé de la réponse `details` brute) ne contient PAS :

| Champ dropped                                              | Conséquence                                                                                                                                                                                                                               |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `seasons: list[...]` (TVDB `/series/{id}/extended`)        | `_candidate_has_any_season` ne peut plus filtrer les candidats par seasons disponibles. Les spin-offs/parallel-numbering sont à nouveau confondables. Veto bypass à `SEASON_VETO_BYPASS=0.95` ne s'active jamais avec les bonnes données. |
| `images: { posters, backdrops, season_posters }`           | Toute la sélection d'artwork est cassée. ArtworkSelector relit les listes via `.get("posters")` etc.                                                                                                                                      |
| `genres: list[{ id, name }]` (TMDB) ou `genres: list[str]` | `MediaDetails` a `genres: list[str]` mais le classifier veut les IDs. La cartographie genre→category est cassée.                                                                                                                          |
| `origin_country` / `production_countries`                  | Le classifier utilisait ces champs pour les règles "anime" et "FR documentaries".                                                                                                                                                         |
| `original_title` / `original_name`                         | Le matching localisé (ex: "L'Effet papillon" + "The Butterfly Effect") n'a plus de fallback. Test skip `test_original_title_used_for_localized_movie_score` documente la regression.                                                      |

`SearchResult` ne contient pas non plus `original_title`. Voir 3.5.

### 3.4 Tests masquent les régressions

Pattern systémique trouvé dans toutes les classes de bugs :

| Bug                                                     | Pourquoi tests passaient                                                     | Source                                    |
| ------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------- |
| #5 (load_dotenv)                                        | `tests/conftest.py:21` charge `.env` dans le harness                         | Production = `.env` jamais chargé         |
| #6 (port)                                               | `test_qbittorrent.py:81` hardcode `port=8081`                                | Production = config default 8080          |
| #8 (ratio)                                              | `FakeTorrent.ratio: float = 0.0`                                             | Real `TorrentItem` n'avait pas le champ   |
| #10 (.get on SearchResult)                              | `_make_tmdb_client(list[dict])`, `tvdb.search_series.return_value = [{...}]` | Real client retourne `list[SearchResult]` |
| Tous les consumers (classifier/artwork/episode_manager) | Tests passent des dict legacy directement à ces modules                      | Production = `MediaDetails` typé          |

**Cause racine** : les fixtures de test n'ont jamais été migrées au modèle typé. Le harness teste contre la SHAPE legacy, pas contre la shape réelle de production.

### 3.5 Réflexion sur la philosophie du DESIGN §1.1 ("Zero backward compatibility")

Le DESIGN §1.1 interdit explicitement les "compat shims". C'est défendable, mais l'application a été incomplète :

- L'upgrade DOC manque (CONFIGURATION.md ne mentionnait pas la migration QBIT_HOST/PORT — réparé par commit `55a4b47`).
- Aucun script `init-config --migrate-from-pre-0.11` n'a été ajouté.
- Pas de warning au boot quand la config legacy est détectée — réparé par `55a4b47`.
- Les _consumers_ à l'intérieur du code n'ont pas eu de migration : ils utilisent toujours des dicts là où le code amont fournit du typé.

→ "Zero backward compatibility" devrait être appliqué aux SHAPES (typed everywhere), pas seulement aux fonctions exportées.

## 4. Scope de travail restant pour finir vraiment api-unify

### 4.1 Étendre les modèles typés (DESIGN §4.2 update)

Ajouter à `api/metadata/_base.py` :

- `MediaDetails.seasons: list[SeasonInfo]` avec `SeasonInfo(season_number: int, episode_count: int, poster_url: str)`
- `MediaDetails.images: ImagesPayload` avec `posters: list[ArtworkItem]`, `backdrops: list[ArtworkItem]`, `season_posters: dict[int, list[ArtworkItem]]`
- `MediaDetails.genre_ids: list[int]` (en plus de `genres: list[str]`)
- `MediaDetails.origin_countries: list[str]`
- `MediaDetails.production_countries: list[str]`
- `MediaDetails.original_title: str` (déjà là — vérifier le populate)
- `SearchResult.original_title: str | None` (pour le matching localisé)

Update parsers `_tmdb_parsers.py:parse_media_details` et `_tvdb_parsers.py:parse_media_details` pour remplir ces champs.

### 4.2 Migrer les consumers (≈ 25 sites .get())

Pour chaque module dans 3.2 :

1. Remplacer les `.get("field")` par `obj.field` ou `obj.field if obj.field else default`
2. Adapter les fixtures de test à utiliser des `MediaDetails(...)` au lieu de dicts
3. Lancer le module sur des données réelles (pas seulement tests) avec un dry-run

### 4.3 Re-tester end-to-end

- `personalscraper run --dry-run` doit terminer sans AttributeError
- `personalscraper process` (réel) doit produire des NFO valides + artwork
- Tester sur 3-5 séries de complexité variable (single ep, full season, spin-off avec season-veto)

### 4.4 Test e2e + smoke test "fresh shell"

Ajouter un test qui spawn un subprocess complètement isolé et lance la pipeline sur des fixtures media réelles. Le test doit échouer si N'IMPORTE QUEL `.get()` sur un typed model est rencontré.

## 5. Recommandation

Re-ouvrir la PR avec :

- Statut : `Draft / Not ready` (retirer le label "ready to merge")
- Mentionner cet audit en commentaire haut de la PR
- Phase 27 (nouvelle) : "Consumer-side migration" couvrant 4.1 + 4.2 + 4.3
- Pré-merge gate : `personalscraper process --dry-run` doit terminer sans AttributeError sur 5 fixtures de test (1 movie, 2 single-ep TV, 1 full-season TV, 1 spin-off pour season-veto)

Si le scope est trop gros pour une seule PR : split en deux features

- `api-unify-clients` (déjà fait) : couche client + tests unit
- `api-unify-consumers` (nouvelle) : migration des 4 modules consumer + tests integration
