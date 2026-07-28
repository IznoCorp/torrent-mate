# Phase 03 — Retrait torr9 (code, tests, activation)

**Goal**: torr9 disparaît du code. Les données historiques (obligations de seed, lignes
wanted done) restent intactes en base.

**Design**: DESIGN §3 D3.

## Surface

| Fichier                                                 | Action                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/api/tracker/torr9.py` (578 L)          | **SUPPRIMÉ**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `tests/unit/test_torr9_client.py`                       | **SUPPRIMÉ**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `personalscraper/api/_activation.py`                    | entrées torr9 retirées                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `personalscraper/api/_contracts.py`                     | `ProviderName.TORR9` retiré                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `personalscraper/acquire/_factory.py` + registry        | branche torr9 retirée (attention aux commentaires « lazy tracker (torr9) » dans _registry.py/_factory.py — reformuler, le pattern lazy peut rester si un autre client l'utilise, sinon le retirer aussi)                                                                                                                                                                                                                                                                                                                                                                         |
| `personalscraper/conf/models/api_config.py`             | mentions torr9 (lignes ~286-289, option de ranking) — vérifier si l'option est torr9-only → la retirer avec                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `config/tracker.json5` + `config.example/tracker.json5` | entrée torr9 purgée (la coupure commentée de la phase 0 saute)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| tous les tests listant torr9                            | `tests/unit/test_activation.py`, `test_tracker_factory.py`, `test_tracker_parser_schema_drift.py`, `test_tracker_capabilities_composition.py`, `tests/acquire/test_filters.py`, `test_grab_title_query.py`, `tests/integration/api/tracker/test_composition_root.py`, `tests/e2e/test_cross_seed_roundtrip.py`, `tests/integration/acquire/test_cross_seed_service.py`, `tests/conf/test_tracker_config_priority_by_media_type.py`, `tests/manual/e2e_watch_seed.py` — adapter en préservant l'intention (souvent : remplacer torr9 par tr4ker comme « second tracker » de test) |

## Règles

- Grep résiduel OBLIGATOIRE : `rg -n "torr9|Torr9|TORR9" -t py personalscraper/ tests/` → **0 hit**.
  (CHANGELOG et docs/archive exclus — l'histoire ne se réécrit pas.)
- Les obligations de seed torr9 en base : intactes. Si un code de reconcile/obligations
  résout par ProviderName, vérifier qu'une ligne historique `tracker='torr9'` ne crashe
  pas après retrait de l'enum (fail-soft sur tracker inconnu — test dédié).
- Suppression = collection pytest à re-vérifier (`ERROR` de collecte = phase rouge).

## Sous-phases

### 3.1 — `feat(torznab): remove the torr9 client and its activation`

### 3.2 — `test(torznab): retarget torr9-dependent tests to tr4ker`

### 3.3 — `test(torznab): historical torr9 seed obligations stay readable` (le test fail-soft)

## Gate

1. Grep résiduel zéro (règle ci-dessus, sortie collée dans le commit de gate).
2. `make test` — zéro failed, zéro ERROR de collecte.
3. `python3 -m mypy personalscraper/` — 0.
4. `python3 -c "import personalscraper"` — smoke.
