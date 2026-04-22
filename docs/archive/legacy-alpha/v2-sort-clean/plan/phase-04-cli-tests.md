# Phase 4 — CLI command + tests end-to-end

## Objectif

Connecter le sorter au CLI et valider end-to-end.

## Sous-phases

### 2.4.1 — Commande CLI sort

- [x] Implémenter la commande `personalscraper sort` dans `cli.py`
- [x] Connecter Settings → NameCleaner → Sorter → affichage résultats
- [x] Support --dry-run, --verbose
- [x] Implémenter `run_sort(settings, dry_run) -> StepReport` dans `sorter/run.py`
  - Instancier NameCleaner + Sorter, appeler process(), convertir list[SortResult] en StepReport
  - Le lock est acquis au niveau CLI, PAS dans run_sort()
- [x] Alimenter le StepReport avec les SortResult
- [x] Logger chaque opération

**Commit** : `v2.4.1: Wire sort command into CLI` ✅

### 2.4.2 — Tests end-to-end

- [x] Test avec structure de fichiers réaliste (tmp_path) — 11 tests
- [x] Vérifier le tri films vs séries
- [x] Vérifier le nettoyage des noms
- [x] Vérifier le dry-run
- [x] Vérifier les SortResult retournés
- [x] Test run_sort → StepReport avec Settings

**Commit** : `v2.4.2: Add end-to-end sort tests` ✅
