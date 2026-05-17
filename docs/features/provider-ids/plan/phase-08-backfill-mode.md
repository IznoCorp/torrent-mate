# Phase 8 — Backfill Mode + CLI + Auto-Trigger Post-Scrape

## Goal

Nouveau mode scanner `backfill_ids` qui scanne toute la library pour combler les gaps IDs **et** ratings sans toucher les familles canoniques. Réécrit les NFOs (Q4=A) au format Plex prioritaire. Q2=Hybride : commande CLI manuelle + auto-trigger post-scrape.

## Gate (prerequisites)

- Phase 7 mergée (DB schema `external_ids_json` + `ratings_json` en place).
- Phases 3 + 5 + 6 mergées (façades + xref + ratings disponibles).

## Sub-phases

### 8.1 — `indexer/scanner/_modes/backfill_ids.py`

Nouveau mode qui :

- Itère sur `media_item` rows.
- Pour chaque item : parse `external_ids_json` actuel, détecte gaps (familles non-canonique manquantes, ratings manquants).
- Appelle façades api/metadata (capability-based : `isinstance(p, RatingProvider)` etc.).
- Construit le nouveau `external_ids_json` et `ratings_json` **sans écraser** les valeurs canoniques existantes (json_set if not exists).
- Réécrit le NFO via `nfo_generator` (Q4=A, format Plex).
- Update DB transactionnellement avec le write NFO.
- Respect circuit breaker pour ne pas bombarder les APIs.

Commit : `feat(provider-ids): add backfill_ids scanner mode`

### 8.2 — CLI command `personalscraper indexer --backfill-ids`

Ajouter le flag à la commande `personalscraper indexer` existante. Sub-flags :

- `--show=NAME` : restreindre à un show spécifique
- `--ratings-only` : ne backfill que les ratings, pas les IDs
- `--ids-only` : ne backfill que les IDs, pas les ratings
- `--dry-run` : affiche le plan sans modifier

Commit : `feat(provider-ids): indexer --backfill-ids CLI command`

### 8.3 — Auto-trigger post-scrape

Dans `scraper/run.py` : après un scrape OK d'un show, détecter si le show a des gaps xref/ratings. Si oui → fire un backfill ciblé `--show=NAME`. Async-fire-and-forget si possible (pas bloquer le pipeline).

Commit : `feat(provider-ids): auto-trigger backfill post-scrape when gap detected`

### 8.4 — Logging + observability

Events typés via EventBus (feature précédente event-bus disponible) :

- `BackfillStarted(scope, item_count)`
- `BackfillItemCompleted(item, gaps_filled)`
- `BackfillSkipped(item, reason)` (canonical OK + xref + ratings tous présents)
- `BackfillCompleted(total, succeeded, skipped, failed)`

Commit : `feat(provider-ids): backfill events on EventBus`

## Tests to write

- `test_backfill_detects_missing_tmdb_xref_on_tvdb_canonical`
- `test_backfill_detects_missing_imdb_id`
- `test_backfill_detects_missing_imdb_rating`
- `test_backfill_detects_missing_rt_rating`
- `test_backfill_rewrites_nfo_when_gap_filled` (Q4=A)
- `test_backfill_does_not_overwrite_canonical_id`
- `test_backfill_does_not_overwrite_existing_rating`
- `test_backfill_no_op_when_all_complete`
- `test_backfill_respects_circuit_breaker_on_provider_fail`
- `test_cli_backfill_ids_show_filter`
- `test_cli_backfill_ids_dry_run_no_writes`
- `test_auto_trigger_post_scrape_fires_backfill_on_gap`
- `test_auto_trigger_post_scrape_skips_when_no_gap`
- `test_backfill_emits_events_on_event_bus`
- `test_backfill_rate_limit_respects_circuit_breaker_across_batch` (smoke — vérifie que le backfill batch n'envoie pas plus de requêtes que le circuit breaker ne le permet)

## Acceptance criteria

- `personalscraper indexer --backfill-ids` scanne toute la library et comble les gaps.
- Les 6 shows en staging (Dexter, AmDad, Top Chef, ST '85, LOL, The Boys) post-rescrape (phase 4) ont leurs `external_ids_json` complets (tvdb + tmdb + imdb) et `ratings_json` (imdb + rt) après un `--backfill-ids`.
- Auto-trigger ne ralentit pas significativement le pipeline (~+10s max par show scrapé).

## Migration / config touch

Aucune (le mode est additif, ne touche pas le schema déjà migré en phase 7).

## DESIGN reference

§6.5 (indexer/), §3 décisions Q2 + Q4, §5 (idempotence).
