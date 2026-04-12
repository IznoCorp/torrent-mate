# Phase 1 — Pipeline orchestrator + gate

## Objectif

Extraire la logique d'orchestration de `cli.py:run()` dans un `Pipeline` class dedié, ajouter la gate `assert_temp_empty`, et adapter le CLI pour deleguer.

## Sous-phases

### 9.1.1 — Pipeline class avec \_run_step et phases

- [ ] Creer `personalscraper/pipeline.py`
- [ ] `Pipeline.__init__(settings, dry_run, interactive, verbose, console)`
- [ ] `Pipeline.run() -> PipelineReport` — appelle les 5 phases via `_run_step()`
- [ ] Deplacer `_run_step()` de `cli.py` vers `pipeline.py`
- [ ] Report avec 7 slots : ingest, sort, clean, scrape, cleanup, verify, dispatch
- [ ] Phase 5 dispatch skip si `verified` est None ou vide
- [ ] Tests unitaires : Pipeline.run() avec mocks des 5 phases, gate pass/fail
- [ ] Tests : \_run_step handles tuple return, exception, normal StepReport

**Commit** : `v9.1.1: Extract Pipeline orchestrator from cli.py`

### 9.1.2 — Gate assert_temp_empty

- [x] Ajouter `assert_temp_empty(settings) -> list[str]` dans `sorter/run.py`
- [x] Ignore `.gitkeep`, `.DS_Store`, fichiers caches (startswith `.`)
- [x] Retourne la liste des fichiers restants (vide = gate OK)
- [x] Pipeline appelle la gate entre sort et process
- [x] Si fichiers restants : log WARNING + continue (ne bloque pas le pipeline)
- [x] Tests : gate passe si vide, retourne noms si fichiers restent, ignore hidden

**Commit** : `v9.1.2: Add assert_temp_empty gate between sort and process`

### 9.1.3 — CLI delegation a Pipeline

- [x] `cli.py:run()` instancie Pipeline et appelle `.run()`
- [x] Garder le lock/unlock, healthcheck, telegram dans cli.py (pas dans Pipeline)
- [x] Panel final affiche 7 lignes (ingest, sort, clean, scrape, cleanup, verify, dispatch)
- [x] `PipelineReport.to_html()` mis a jour pour 7 steps
- [x] Supprimer le code dupliqué de l'ancien run()
- [x] Tests existants cli passent toujours
- [x] Test : panel final avec 7 rows

**Commit** : `v9.1.3: Wire CLI run() to Pipeline, 7-step panel`
