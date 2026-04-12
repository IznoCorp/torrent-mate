# V9 — PIPELINE INTEGRITY : Plan d'implementation

> Pipeline sequentiel exhaustif avec check de coherence avant dispatch.

## Phases

| #   | Phase                          | Fichier                                                | Status |
| --- | ------------------------------ | ------------------------------------------------------ | ------ |
| 1   | Pipeline orchestrator + gate   | [phase-01-pipeline.md](phase-01-pipeline.md)           | [x]    |
| .   | _Controle de coherence P1→P2_  |                                                        | [x]    |
| 2   | Process: reclean + dedup       | [phase-02-process-clean.md](phase-02-process-clean.md) | [x]    |
| .   | _Controle de coherence P2→P3_  |                                                        | [x]    |
| 3   | Process: cleanup + run_process | [phase-03-process-run.md](phase-03-process-run.md)     | [x]    |
| .   | _Controle de coherence P3→P4_  |                                                        | [x]    |
| 4   | Verify renforce + titre local  | [phase-04-verify-title.md](phase-04-verify-title.md)   | [x]    |
| .   | _Controle de coherence P4→P5_  |                                                        | [x]    |
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

- [x] `Pipeline.run()` appelle `_run_step()` pour chaque phase dans le bon ordre
- [x] `_assert_temp_empty()` log WARNING si fichiers restants (ne bloque pas — decision D5)
- [x] `_assert_temp_empty()` ignore `.gitkeep`, `.DS_Store`, fichiers caches
- [x] `cli.py:run()` delegue a `Pipeline` sans dupliquer de logique
- [x] Les commandes standalone (`personalscraper ingest`, etc.) fonctionnent toujours
- [x] 911 tests passent (baseline 898)

### Apres Phase 2 (Process clean → Process run)

- [x] `is_title_polluted()` detecte les tokens release dans un titre
- [x] `reclean_folders()` renomme les dossiers pollues via guessit
- [x] `dedup_folders()` fusionne les doublons fuzzy (year guard actif)
- [x] Aucun faux positif de dedup sur les dossiers existants (tests)
- [x] StepReport "clean" comptabilise re-cleans + dedup merges (combined in run_process)

### Apres Phase 3 (Process run → Verify)

- [x] `cleanup_empty_dirs()` supprime recursivement les dossiers vides
- [x] `cleanup_empty_dirs()` ne supprime PAS les dossiers non-vides ou `.actors/`
- [x] `run_process()` retourne 3 StepReports (clean, scrape, cleanup)
- [x] `run_process()` appelle reclean → dedup → scrape → cleanup dans cet ordre
- [x] Le scrape fonctionne normalement apres reclean/dedup

### Apres Phase 4 (Verify + titre → Integration)

- [x] `episode_renamed` check : videos dans Saison XX/ matchent `S\d{2}E\d{2} - .+`
- [x] `poster_present` check : films `Title-poster.jpg`, series `poster.jpg`
- [x] `no_empty_dirs` check : recursif, pas de sous-dossiers vides
- [x] `_resolve_title()` utilise le titre FR quand `prefer_local_title=True`
- [x] `_resolve_title()` fallback sur titre API si pas de traduction FR
- [x] Le setting `SCRAPER_PREFER_LOCAL_TITLE` est configurable via `.env`
- [x] Items qui echouent les nouveaux checks → blocked (pas dispatches)

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
