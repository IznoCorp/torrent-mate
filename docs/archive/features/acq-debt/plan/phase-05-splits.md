# Phase 05 — D6 : splits de modules (comportement pinné)

**Goal**: `web/routes/acquisition.py` (~990) et `acquire/service.py` (~900) sous 800
non-blank. Refactor PUR : zéro changement de comportement, les tests existants sont le pin.

## Surface

| Fichier                                     | Action                                                                                                                                                                                                                                    |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/web/routes/acquisition.py` | routes fines ; blocs cohérents extraits vers `web/acquisition/` (métadonnées de follow, construction d'items/overrides, helpers dry-run) — suivre les seams solidify existants (`web/acquisition/service.py` en a déjà)                   |
| `personalscraper/acquire/service.py`        | passes search/grab extraites en modules (`_search_pass.py`/`_grab_pass.py` ou équivalent) ; `AcquisitionService` = façade, surface publique inchangée (constructeur, run, run_search, RunSummary/SearchRunSummary, SEARCH_OUTCOME_STATUS) |
| imports/tests                               | mises à jour mécaniques d'imports UNIQUEMENT — toute modification d'assertion = échec de phase (sauf justification ligne à ligne)                                                                                                         |

## Règles

- Un commit par module scindé, `refactor(acq-debt): …`.
- Grep du chemin d'import ancien sur personalscraper/ ET tests/ après chaque déplacement.
- `make openapi` : AUCUN drift attendu (les routes ne changent pas de contrat).

## Gate

`python3 scripts/check-module-size.py` : les deux fichiers sous 800, zéro WARN nouveau ;
make test complet vert 0 ERROR ; mypy 0 ; diff des fichiers de tests = imports seuls.
