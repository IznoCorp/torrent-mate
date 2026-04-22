# Phase 3 — CLI command + tests end-to-end

## Objectif

Connecter le dispatcher au CLI et valider end-to-end.

## Sous-phases

### 5.3.1 — Commande CLI dispatch

- [ ] Implémenter `personalscraper dispatch` dans `cli.py`
- [ ] Option `--rebuild-index` pour forcer un rebuild complet
- [ ] Support --dry-run, --verbose
- [ ] Implémenter `run_dispatch(settings, dry_run, verified=None) -> StepReport`
  - Si verified fourni (pipeline mode) : utiliser directement
  - Si verified=None (standalone) : scanner staging_dir + catégoriser via GenreMapper
  - Le lock est acquis au niveau CLI, PAS dans run_dispatch()
- [ ] Alimenter StepReport avec les DispatchResult
- [ ] Afficher résumé (X films → DiskY, X épisodes merged, X skippés)

**Commit** : `v5.3.1: Wire dispatch command into CLI`

### 5.3.2 — Tests end-to-end

- [ ] Test dry-run avec médias réels dans 001-MOVIES/ et 002-TVSHOWS/
- [ ] Vérifier que l'index est construit correctement
- [ ] Vérifier le choix du bon disque
- [ ] Vérifier replace (films) et merge (séries)
- [ ] Vérifier skip si espace insuffisant
- [ ] Test avec `personalscraper dispatch --dry-run` via CliRunner

**Commit** : `v5.3.2: Add end-to-end dispatch tests`
