# Phase 5 — Integration CLI + tests E2E

## Objectif

Integrer tous les composants V9 dans le CLI, mettre a jour le notifier Telegram, et ecrire les tests d'integration E2E qui valident le flux complet.

## Sous-phases

### 9.5.1 — CLI run() final wiring

- [ ] `cli.py:run()` passe `interactive` a Pipeline
- [ ] Ajouter `--interactive` a la commande `run` (en plus de `scrape`)
- [ ] Panel final avec 7 lignes : ingest, sort, clean, scrape, cleanup, verify, dispatch
- [ ] Chaque StepReport de run_process() affiché via `_run_step()` dans Pipeline
- [ ] `PipelineReport.to_html()` mis a jour pour 7 steps (Telegram)
- [ ] `step_icons` dans `_run_step` etendu a 7 steps (1/7 a 7/7)
- [ ] Tests : panel 7 lignes, Telegram HTML contient les 7 steps

**Commit** : `v9.5.1: Wire 7-step pipeline in CLI with --interactive`

### 9.5.2 — Commande standalone process

- [ ] Ajouter commande `personalscraper process` dans cli.py
- [ ] Options : `--dry-run`, `--interactive`, `--movies-only`, `--tvshows-only`
- [ ] Appelle `run_process()` directement (sans ingest/sort/verify/dispatch)
- [ ] Affiche les 3 StepReports (clean, scrape, cleanup)
- [ ] Tests : test_cli pour la commande process

**Commit** : `v9.5.2: Add standalone process command`

### 9.5.3 — Tests integration pipeline complet

- [ ] Test : fichier brut dans 097-TEMP → sort → process (reclean+scrape) → verify → dispatch OK
- [ ] Test : doublon dans 001-MOVIES → process (dedup+merge) → verify → dispatch OK
- [ ] Test : fichier non-matchable → process skip → verify blocked → dispatch partiel
- [ ] Test : 097-TEMP non vide apres sort → warning logged, pipeline continue
- [ ] Test : dispatch skip quand aucun item dispatchable
- [ ] Test : --dry-run traverse les 7 phases sans modifier le filesystem
- [ ] Test : --interactive propage aux phases process et scrape
- [ ] Verifier 898+ tests existants passent toujours

**Commit** : `v9.5.3: Add integration tests for full 7-step pipeline`

### 9.5.4 — Update docs et CLAUDE.md

- [ ] Mettre a jour CLAUDE.md : section Pipeline Versions (ajouter V9)
- [ ] Mettre a jour CLAUDE.md : section Directory Structure (ajouter process/)
- [ ] Mettre a jour CLAUDE.md : section Commands (ajouter `personalscraper process`)
- [ ] Mettre a jour IMPLEMENTATION.md : V9 status [x]
- [ ] Mettre a jour plan/INDEX.md : toutes les phases [x]
- [ ] Commit final

**Commit** : `v9.5.4: Update docs — V9 pipeline integrity, 7-step flow`
