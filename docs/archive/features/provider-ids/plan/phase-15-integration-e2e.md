# Phase 15 — Integration + E2E + Final Wire

## Goal

Vérifier que toutes les phases s'assemblent correctement bout-en-bout. Run tests d'intégration (HTTP mocked) sur les flows complets, tests E2E sur 1 fixture show réelle, et tests de régression contre les bugs DEV #2 du pipeline-monitor 2026-05-17. Vérifie les 10 acceptance criteria du DESIGN §12.

## Gate (prerequisites)

- Phases 1-14 mergées (toutes les capabilities + fixes + ratings + DB + backfill + verify + consumers + tracker registry + torrent + notify).
- `make test` + `make lint` + `make check` passent localement.

## Sub-phases

### 15.1 — Tests intégration scrape pipeline

Écrire les tests integration qui parcourent `process` end-to-end avec HTTP mocked (TVDB, TMDb, OMDb) :

- `test_process_full_pipeline_tvdb_canonical_with_xref_tmdb_imdb_rt`
- `test_process_full_pipeline_tmdb_fallback_when_tvdb_fails`
- `test_process_idempotent_no_changes_on_second_run` (scrape_fast_skip valide)
- `test_process_backfills_xref_on_show_with_canonical_only`
- `test_process_does_not_rescrape_when_canonical_complete_and_xref_present`

Commit : `test(provider-ids): integration tests for scrape pipeline end-to-end`

### 15.2 — Tests intégration backfill + verify + dispatch

- `test_backfill_full_run_fills_all_gaps_on_legacy_library`
- `test_verify_blocks_dispatch_when_canonical_uniqueid_missing`
- `test_verify_allows_dispatch_when_only_xref_missing` (warning, pas error)
- `test_dispatch_after_full_pipeline_writes_to_correct_disk`

Commit : `test(provider-ids): integration tests for backfill + verify + dispatch`

### 15.3 — Test E2E avec fixture show

Nouveau `tests/e2e/test_provider_ids_e2e.py` :

- 1 fixture show TV ~3 episodes (placé dans tests/e2e/fixtures/ ou perf/.fixture/).
- Run `process` complet avec HTTP mocked.
- Assert NFOs final state : canonical uniqueid + xref + ratings.
- Assert DB final state : `external_ids_json` + `ratings_json` + `canonical_provider`.
- Run `--backfill-ids` après : no-op (tout déjà rempli).

Commit : `test(provider-ids): E2E test on fixture show end-to-end`

### 15.4 — Tests régression DEV #2 final (validation 6 shows staging)

Test qui simule le scenario du pipeline-monitor 2026-05-17 :

- Seed library avec NFOs sans uniqueid (état pré-fix des 6 shows).
- Run drift validator → trigger re-scrape.
- Run scrape → NFOs maintenant complets.
- Assert pas de cross-contamination.

Commit : `test(provider-ids): regression e2e for DEV #2 six shows scenario`

### 15.5 — Validate 10 acceptance criteria du DESIGN §12

Checklist manuelle ou test agrégat :

1. ✅ 6 shows staging → NFOs épisode avec uniqueid canonique post-rescrape
2. ✅ process nouveau show TV → NFOs complets (canonical + xref imdb)
3. ✅ `personalscraper indexer --backfill-ids` comble gaps sans destruction
4. ✅ BDD sans colonnes legacy, queries existantes via `external_ids_json`
5. ✅ `OverrideRule.imdb_id` supprimé + config réelle migrée
6. ✅ api/\* en capabilities composées, plus de Protocol monolithique
7. ✅ TrackerRegistry priority-aware fonctionne
8. ✅ Tests 100% pass, coverage ≥ 90% sur lignes touchées
9. ✅ CLI publique inchangée hors `--backfill-ids`
10. ✅ Pipeline-run dispatch 2026-05-17-09h24 relançable post-merge

Commit : `docs(provider-ids): acceptance criteria validation report`

### 15.6 — Update CLAUDE.md + docs/reference

- `CLAUDE.md` : ajouter référence à provider-ids dans le tableau "Reference Index" :
  - `docs/reference/external-ids-flow.md` — flow data nominal + fallback + backfill
  - `docs/reference/indexer-json-shapes.md` — mise à jour pour `external_ids_json` + `ratings_json`
- Nouveau `docs/reference/external-ids-flow.md` (succinct) : flow data nominal + fallback + backfill + format NFO ratings.
- Update `docs/reference/architecture.md` : section api/ avec les 11+ capabilities metadata + 4 tracker + 3 torrent + 2 notify.
- Update `docs/reference/scraping.md` : mention de la nouvelle hiérarchie scrape + xref enrichment.
- Update `docs/reference/indexer-json-shapes.md` : documenter les nouveaux shapes JSON :
  - `external_ids_json` : `{"tvdb": {"series_id": ..., "episode_id": ...}, "tmdb": {...}, "imdb": {...}}`
  - `ratings_json` : `{"entries": [{"source": "imdb", "score": "8.5/10", "votes": 50000}, ...]}`
  - `canonical_provider` : `"tvdb"` ou `"tmdb"`
- Update `docs/reference/logging.md` : nouveaux event names backfill :
  - `BackfillStarted`, `BackfillItemCompleted`, `BackfillSkipped`, `BackfillCompleted` (phase 8.4)

Commit : `docs(provider-ids): update CLAUDE.md and reference docs`

## Tests to write

(Voir 15.1-15.4 — déjà détaillés.)

## Acceptance criteria

- Tous les tests pass (unit + integration + e2e).
- `make check` (lint + test + module-size + typed-api guardrails) green.
- Les 10 acceptance criteria §12 du DESIGN cochés.
- Pipeline-run du 2026-05-17-09h24 (staging area conservée) relançable et dispatchable.

## Migration / config touch

Aucune nouvelle migration ici (toutes les modifs de schema/config faites aux phases précédentes).

## DESIGN reference

§9 (Testing strategy + TDD sequencing phase 15), §12 (Acceptance criteria).
