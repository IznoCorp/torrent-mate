# V10 — PIPELINE RESILIENCE : Plan d'implementation

> Idempotence renforcee des 7 phases, reprise apres crash, tests filesystem realistes.

## Phases

| #   | Phase                                  | Fichier                                                            | Status |
| --- | -------------------------------------- | ------------------------------------------------------------------ | ------ |
| 1   | Helpers validation + Ingest/Sort/Clean | [phase-01-helpers-idempotence.md](phase-01-helpers-idempotence.md) | [ ]    |
| .   | _Controle de coherence P1→P2_          |                                                                    | [ ]    |
| 2   | Scrape resilience                      | [phase-02-scrape-resilience.md](phase-02-scrape-resilience.md)     | [ ]    |
| .   | _Controle de coherence P2→P3_          |                                                                    | [ ]    |
| 3   | Verify + Dispatch resilience           | [phase-03-verify-dispatch.md](phase-03-verify-dispatch.md)         | [ ]    |
| .   | _Controle de coherence P3→P4_          |                                                                    | [ ]    |
| 4   | Tests resilience filesystem            | [phase-04-resilience-tests.md](phase-04-resilience-tests.md)       | [ ]    |
| .   | _Controle de coherence P4→P5_          |                                                                    | [ ]    |
| 5   | Integration + docs                     | [phase-05-integration-docs.md](phase-05-integration-docs.md)       | [ ]    |

## Dependances entre phases

```
P1 (helpers + ingest/sort/clean) ──→ P2 (scrape utilise _is_nfo_complete de P1)
P2 (scrape resilience)           ──→ P3 (verify depend du scrape corrige)
P1 + P2 + P3                    ──→ P4 (tests testent tous les mecanismes)
P4 (tests)                       ──→ P5 (integration + docs)
```

## Controles de coherence

### Apres Phase 1 (Helpers + Ingest/Sort/Clean → Scrape)

- [ ] `_is_nfo_complete()` valide XML parsable + `<uniqueid>` present
- [ ] `_is_nfo_complete()` retourne False pour NFO tronque ou sans uniqueid
- [ ] Sort skip les items deja presents en 001/002 (fuzzy match)
- [ ] Sort fast-skip si 097-TEMP vide
- [ ] Clean skip dossier source disparu apres crash mid-rename
- [ ] Clean fast-skip si aucun dossier pollue
- [ ] Ingest fast-skip si aucun torrent non-ingere
- [ ] 963+ tests passent

### Apres Phase 2 (Scrape → Verify)

- [ ] Scrape detecte NFO corrompu (XML invalide) et le re-scrape
- [ ] Scrape detecte NFO sans uniqueid et le re-scrape
- [ ] Scrape detecte artwork manquant et re-download sans re-scrape NFO
- [ ] Scrape fast-skip si tous les NFO sont valides
- [ ] Le re-scrape produit un NFO valide (parsable + uniqueid)

### Apres Phase 3 (Verify/Dispatch → Tests)

- [ ] Verify ne re-applique pas les fixes si tous les checks passent au premier run
- [ ] Verify double-run produit le meme resultat
- [ ] Dispatch nettoie les `_tmp_dispatch_*` et `.merge_backup/` au debut
- [ ] Les 7 phases sont idempotentes (re-run safe)

### Apres Phase 4 (Tests → Integration)

- [ ] Les 10 tests de resilience filesystem passent
- [ ] Aucun test ne touche les disques de stockage reels
- [ ] Dispatch reste en dry-run dans tous les tests
- [ ] Les tests couvrent : NFO corrompu, artwork partiel, merge partiel, orphelins, double-run

### Apres Phase 5 (Integration → Done)

- [ ] Pipeline double-run complet : 2e run skip tout en fast path
- [ ] CLAUDE.md mis a jour avec V10
- [ ] IMPLEMENTATION.md mis a jour
- [ ] Tous les tests passent (963+ tests)
