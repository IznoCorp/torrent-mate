# Phase 2 — Fix DEV #2 IDs Propagation (regression tests first)

## Goal

Résoudre le bug **DEV #2 du pipeline-monitor 2026-05-17** : les NFOs épisode TV sont écrits sans `<uniqueid>` parce que les IDs sont jetés au fetch et hardcodés `""` dans `_generate_episode_nfos`. **Approche TDD stricte** (memory `feedback_regression_test_per_bug`) : tests qui reproduisent le bug d'abord, puis le fix.

## Gate (prerequisites)

- Phase 1 mergée (capabilities Protocols disponibles, pas encore appliquées).
- Pas de modif du DB schema requise à ce stade — on travaille en mémoire + NFO.

## Sub-phases

### 2.1 — Tests régression DEV #2 (RED phase, doivent FAIL avant fix)

Écrire les tests qui reproduisent le bug, runner pour confirmer qu'ils fail sur la branche actuelle :

- `test_regression_dev2_tvdb_fetch_propagates_episode_id` — `_tvdb_fetch` payload doit inclure `tvdb_episode_id`. **FAIL avant fix** (payload n'a que title + still_path).
- `test_regression_dev2_tmdb_fetch_propagates_tmdb_and_imdb_episode_id` — `_tmdb_fetch` payload doit inclure `tmdb_episode_id` et `imdb_episode_id` (depuis `external_ids` TMDb). **FAIL avant fix**.
- `test_regression_dev2_match_episode_files_propagates_provider_ids` — matched dict doit propager les `*_episode_id` keys. **FAIL avant fix**.
- `test_regression_dev2_generate_episode_nfo_writes_uniqueid_when_id_propagated` — NFO output doit contenir `<uniqueid type="tvdb">` quand `tvdb_id` propagé non vide. **FAIL avant fix** (`_generate_episode_nfos` hardcode `""`).

Commit : `test(provider-ids): regression tests for DEV #2 episode id propagation`

### 2.2 — Fix `_tvdb_fetch` + `_tmdb_fetch` payload

`personalscraper/scraper/tv_service.py:972-998` : ajouter `tvdb_episode_id` / `tmdb_episode_id` + `imdb_episode_id` aux payloads. Le test 2.1 (a, b) doit passer.

Commit : `fix(provider-ids): propagate episode IDs from tvdb/tmdb fetchers`

### 2.3 — Fix `match_episode_files`

`personalscraper/scraper/episode_manager.py:164,188,228` : passthrough des `*_episode_id` keys du source vers le matched dict. Le test 2.1 (c) doit passer.

Commit : `fix(provider-ids): propagate episode IDs through match_episode_files`

### 2.4 — Fix `_generate_episode_nfos`

`personalscraper/scraper/tv_service.py:1161-1173` : remplacer `"id": "", "tvdb_id": ""` par lecture depuis `info["tmdb_episode_id"]` etc. Le test 2.1 (d) doit passer.

Commit : `fix(provider-ids): use propagated episode IDs in _generate_episode_nfos`

## Tests to write (en plus du 2.1 RED)

- `test_tvdb_fetch_payload_includes_episode_id` (unit, post-fix GREEN)
- `test_tmdb_fetch_payload_includes_tmdb_and_imdb_episode_id`
- `test_match_episode_files_phantom_remap_preserves_ids`
- `test_match_episode_files_fallback_no_ids` (synthetic = pas d'ID propagé, attendu)
- `test_generate_episode_nfo_writes_all_available_uniqueids` (canonical + xref)
- `test_generate_episode_nfo_omits_uniqueid_when_id_blank` (compat existante préservée)

## Acceptance criteria

- Les 4 tests RED 2.1 passent en GREEN après les 3 fix.
- Les NFOs épisode générés par un `personalscraper process` sur un show TV portent `<uniqueid type="tvdb">` (canonical) quand TVDB a scrapé.
- L'attribut `default="true"` reste mis selon la logique existante (Q6=A sera affiné en phase 6).
- Aucun cross-contamination : `<uniqueid type="tvdb">` contient un ID TVDB authentique.

## Migration / config touch

Aucune (changements code-only).

## DESIGN reference

§1 (Problem statement + root cause), §6.3 (modules scraper refactorés), §9 (TDD sequencing phase 2).
