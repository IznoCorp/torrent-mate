# V9 — PIPELINE INTEGRITY : Plan d'implementation

> Pipeline sequentiel exhaustif avec check de coherence avant dispatch.

## Phases

| #   | Phase                          | Fichier                                                | Status |
| --- | ------------------------------ | ------------------------------------------------------ | ------ |
| 1   | Pipeline orchestrator + gate   | [phase-01-pipeline.md](phase-01-pipeline.md)           | [ ]    |
| .   | _Controle de coherence P1→P2_  |                                                        | [ ]    |
| 2   | Process: reclean + dedup       | [phase-02-process-clean.md](phase-02-process-clean.md) | [ ]    |
| .   | _Controle de coherence P2→P3_  |                                                        | [ ]    |
| 3   | Process: cleanup + run_process | [phase-03-process-run.md](phase-03-process-run.md)     | [ ]    |
| .   | _Controle de coherence P3→P4_  |                                                        | [ ]    |
| 4   | Verify renforce + titre local  | [phase-04-verify-title.md](phase-04-verify-title.md)   | [ ]    |
| .   | _Controle de coherence P4→P5_  |                                                        | [ ]    |
| 5   | Integration CLI + tests E2E    | [phase-05-integration.md](phase-05-integration.md)     | [ ]    |

## Dependances entre phases

```
P1 (Pipeline + gate) ──→ P3 (run_process utilise Pipeline)
P2 (reclean + dedup)  ──→ P3 (run_process appelle reclean + dedup)
P3 (cleanup + run)    ──→ P5 (integration teste run_process)
P4 (verify + titre)   ──→ P5 (integration teste verify renforce)
```

P1 et P2 sont independantes. P3 depend de P1+P2. P4 est independante de P1-P3. P5 integre tout.

## Controles de coherence

### Apres Phase 1 (Pipeline + gate → Process clean)

- [ ] `Pipeline.run()` appelle `_run_step()` pour chaque phase dans le bon ordre
- [ ] `_assert_temp_empty()` leve `PipelineGateError` si fichiers restants
- [ ] `_assert_temp_empty()` ignore `.gitkeep`, `.DS_Store`, fichiers caches
- [ ] `cli.py:run()` delegue a `Pipeline` sans dupliquer de logique
- [ ] Les commandes standalone (`personalscraper ingest`, etc.) fonctionnent toujours
- [ ] 898 tests existants passent

### Apres Phase 2 (Process clean → Process run)

- [ ] `is_title_polluted()` detecte les tokens release dans un titre
- [ ] `reclean_folders()` renomme les dossiers pollues via guessit
- [ ] `dedup_folders()` fusionne les doublons fuzzy (year guard actif)
- [ ] Aucun faux positif de dedup sur les dossiers existants (tests)
- [ ] StepReport "clean" comptabilise re-cleans + dedup merges

### Apres Phase 3 (Process run → Verify)

- [ ] `cleanup_empty_dirs()` supprime recursivement les dossiers vides
- [ ] `cleanup_empty_dirs()` ne supprime PAS les dossiers non-vides ou `.actors/`
- [ ] `run_process()` retourne 3 StepReports (clean, scrape, cleanup)
- [ ] `run_process()` appelle reclean → dedup → scrape → cleanup dans cet ordre
- [ ] Le scrape fonctionne normalement apres reclean/dedup

### Apres Phase 4 (Verify + titre → Integration)

- [ ] `episode_renamed` check : videos dans Saison XX/ matchent `S\d{2}E\d{2} - .+`
- [ ] `poster_present` check : films `Title-poster.jpg`, series `poster.jpg`
- [ ] `no_empty_dirs` check : recursif, pas de sous-dossiers vides
- [ ] `_resolve_title()` utilise le titre FR quand `prefer_local_title=True`
- [ ] `_resolve_title()` fallback sur titre API si pas de traduction FR
- [ ] Le setting `SCRAPER_PREFER_LOCAL_TITLE` est configurable via `.env`
- [ ] Items qui echouent les nouveaux checks → blocked (pas dispatches)

### Apres Phase 5 (Integration → Done)

- [ ] `personalscraper run` affiche 7 lignes dans le panel final
- [ ] Pipeline complet avec fichier brut → scrape → verify → dispatch fonctionne
- [ ] Pipeline avec doublons → dedup → merge → verify → dispatch fonctionne
- [ ] Dispatch skip si aucun item dispatchable
- [ ] Dispatch partiel : items valid dispatches, blocked restent
- [ ] `--interactive` fonctionne pour re-clean et scrape
- [ ] `--dry-run` fonctionne pour toutes les phases
- [ ] Telegram notification inclut les 7 steps
- [ ] Tests E2E couvrent le flux complet
