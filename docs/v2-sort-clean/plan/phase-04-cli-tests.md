# Phase 4 — CLI command + tests end-to-end

## Objectif

Connecter le sorter au CLI et valider end-to-end.

## Sous-phases

### 2.4.1 — Commande CLI sort

- [ ] Implémenter la commande `personalscraper sort` dans `cli.py`
- [ ] Connecter Settings → NameCleaner → Sorter → affichage résultats
- [ ] Support --dry-run, --verbose
- [ ] Alimenter le StepReport avec les SortResult
- [ ] Logger chaque opération

**Commit** : `v2.4.1: Wire sort command into CLI`

### 2.4.2 — Tests end-to-end

- [ ] Test avec structure de fichiers réaliste (tmp_path)
- [ ] Vérifier le tri films vs séries
- [ ] Vérifier le nettoyage des noms
- [ ] Vérifier le dry-run
- [ ] Vérifier les SortResult retournés
- [ ] Test avec `personalscraper sort --dry-run` via CliRunner

**Commit** : `v2.4.2: Add end-to-end sort tests`
