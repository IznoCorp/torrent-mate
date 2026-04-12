# Phase 5 — Integration CLI + tests E2E

## Objectif

Integrer tous les composants V9 dans le CLI, mettre a jour le notifier Telegram, et ecrire les tests d'integration E2E qui valident le flux complet.

## Sous-phases

### 9.5.1 — CLI run() final wiring

- [x] `cli.py:run()` passe `interactive` a Pipeline (done in 9.1.3)
- [x] Ajouter `--interactive` a la commande `run` (done in 9.1.3)
- [x] Panel final avec 7 lignes : ingest, sort, clean, scrape, cleanup, verify, dispatch (done in 9.1.3)
- [x] Chaque StepReport de run_process() affiché via `_log_step_summary()` dans Pipeline (done in 9.3.2)
- [x] `PipelineReport.to_html()` mis a jour pour 7 steps (done in 9.1.3)
- [x] `step_icons` dans `_run_step` etendu a 7 steps (done in 9.1.1)
- [x] Tests : panel 7 lignes, Telegram HTML contient les 7 steps (done in 9.1.3)

**Commit** : `v9.5.1: Wire 7-step pipeline in CLI with --interactive`

### 9.5.2 — Commande standalone process

- [x] Ajouter commande `personalscraper process` dans cli.py
- [x] Options : `--dry-run`, `--interactive`
- [x] Appelle `run_process()` directement (sans ingest/sort/verify/dispatch)
- [x] Affiche les 3 StepReports (clean, scrape, cleanup)
- [x] Tests : test_cli pour la commande process

**Commit** : `v9.5.2: Add standalone process command`

### 9.5.3 — Tests integration pipeline complet

- [x] Test : pipeline complet 7 steps dans le bon ordre
- [x] Test : reclean sur dossier pollue dans 001-MOVIES
- [x] Test : 097-TEMP non vide apres sort → warning logged, pipeline continue
- [x] Test : dispatch skip quand aucun item dispatchable
- [x] Test : --dry-run traverse les 7 phases
- [x] Test : --interactive propage aux phases process et scrape
- [x] 961 tests passent (baseline 898)

**Commit** : `v9.5.3: Add integration tests for full 7-step pipeline`

### 9.5.4 — Update docs et CLAUDE.md

- [x] Mettre a jour CLAUDE.md : section Pipeline Versions (ajouter V9)
- [x] Mettre a jour CLAUDE.md : section Directory Structure (ajouter process/)
- [x] Mettre a jour CLAUDE.md : section Commands (ajouter `personalscraper process`)
- [x] Mettre a jour IMPLEMENTATION.md : V9 status [x]
- [x] Mettre a jour plan/INDEX.md : toutes les phases [x]
- [x] Commit final

**Commit** : `v9.5.4: Update docs — V9 pipeline integrity, 7-step flow`
