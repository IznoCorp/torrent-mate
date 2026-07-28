# Phase 04 — D3 + m24 : carte film open-rows-latest + index partiel pipeline_run

**Goal**: la règle « une ligne fermée = histoire » vaut aussi pour les films ; la requête
d'amorce du GET /followed cesse de scanner pipeline_run.

## Surface

| Fichier                                                            | Action                                                                                                                                                                              |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/web/acquisition/truth.py` (`compute_movie_truth`) | sélection alignée sur `select_wanted_facts` (open-rows-latest) — la règle most-recent-any-status meurt ; sans ligne ouverte ni possession ⇒ facts « no-row » ⇒ `non_verifie`        |
| tests unit/web                                                     | rouge-avant : film dont la SEULE ligne est `abandoned` (verdict conclu) ⇒ carte `non_verifie` (était « En attente ») ; cas ouverts inchangés ; CHANGELOG note le changement visible |
| `personalscraper/indexer/migrations/NNN_*.sql` (numéro suivant)    | `CREATE INDEX IF NOT EXISTS idx_pipeline_run_open_command ON pipeline_run (command) WHERE ended_at IS NULL;` — le TODO m24 de routes/acquisition.py tombe                           |
| tests indexer migrations                                           | application + idempotence, pattern des migrations existantes                                                                                                                        |

## Règles

- Migration indexer = appliquée au boot web (lifespan #245) — additive, sans danger.
- Le doc de l'arbitrage : le PR body de #320 listait cet item « à arbitrer » ; l'arbitrage
  (unifier) est celui de la complétion TODO — le dire dans le commit ET le CHANGELOG.

## Gate

pytest tests/unit/web/ tests/indexer/ -q vert ; mypy 0 ; rouge-avant vérifié ;
`rg -n "m24|most recent row of ANY status" -t py personalscraper/` ⇒ 0 marqueur restant.
