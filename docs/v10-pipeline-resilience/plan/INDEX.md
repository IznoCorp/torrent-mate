# V10 — PIPELINE RESILIENCE : Plan d'implementation

> Idempotence renforcee des 7 phases, reprise apres crash, tests filesystem realistes.

## Phases

| #   | Phase                                  | Fichier                                                            | Status |
| --- | -------------------------------------- | ------------------------------------------------------------------ | ------ |
| 1   | Helpers validation + Ingest/Sort/Clean | [phase-01-helpers-idempotence.md](phase-01-helpers-idempotence.md) | [x]    |
| .   | _Controle de coherence P1→P2_          |                                                                    | [x]    |
| 2   | Scrape resilience                      | [phase-02-scrape-resilience.md](phase-02-scrape-resilience.md)     | [x]    |
| .   | _Controle de coherence P2→P3_          |                                                                    | [x]    |
| 3   | Verify + Dispatch resilience           | [phase-03-verify-dispatch.md](phase-03-verify-dispatch.md)         | [x]    |
| .   | _Controle de coherence P3→P4_          |                                                                    | [x]    |
| 4   | Tests resilience filesystem            | [phase-04-resilience-tests.md](phase-04-resilience-tests.md)       | [x]    |
| .   | _Controle de coherence P4→P5_          |                                                                    | [x]    |
| 5   | Integration + docs                     | [phase-05-integration-docs.md](phase-05-integration-docs.md)       | [x]    |

## Dependances entre phases

```
P1 (helpers + ingest/sort/clean) ──→ P2 (scrape utilise _is_nfo_complete de P1)
P2 (scrape resilience)           ──→ P3 (verify depend du scrape corrige)
P1 + P2 + P3                    ──→ P4 (tests testent tous les mecanismes)
P4 (tests)                       ──→ P5 (integration + docs)
```

## Controles de coherence

### Apres Phase 1 (Helpers + Ingest/Sort/Clean → Scrape)

- [x] `_is_nfo_complete()` valide XML parsable + `<uniqueid>` present (6 tests)
- [x] `_is_nfo_complete()` retourne False pour NFO tronque ou sans uniqueid
- [x] Sort skip exact duplicates (existant) + fast-skip si 097-TEMP vide
- [x] Clean skip source disparue (naturel via iterdir) + fast-skip si aucun pollue
- [x] Ingest deja idempotent (hash tracker, orphan cleanup)
- [x] 981 tests passent (baseline 963)

### Apres Phase 2 (Scrape → Verify)

- [x] Scrape detecte NFO corrompu (XML invalide) et le supprime avant re-scrape
- [x] Scrape detecte NFO sans uniqueid et le supprime avant re-scrape
- [x] Scrape detecte artwork manquant et re-download via TMDB ID du NFO
- [x] Scrape fast-skip si tous les NFO sont valides
- [x] 981 tests passent

### Apres Phase 3 (Verify/Dispatch → Tests)

- [x] Verify ne re-applique pas les fixes si aucun fixable_fails (deja le cas)
- [x] Verify fast-skip si aucun media folder
- [x] Dispatch nettoie `_tmp_dispatch_*` et `.merge_backup/` via `_cleanup_staging_orphans()`
- [x] Les 7 phases sont idempotentes (re-run safe)

### Apres Phase 4 (Tests → Integration)

- [x] 12 tests de resilience filesystem passent (10 scenarios + 2 dispatch orphan variants)
- [x] Aucun test ne touche les disques de stockage reels
- [x] Dispatch orphan cleanup teste via \_cleanup_staging_orphans (pas dispatch reel)
- [x] Tests couvrent : NFO corrompu, artwork partiel, merge partiel, orphelins, sort/clean/verify double-run

### Apres Phase 5 (Integration → Done)

- [x] Pipeline double-run integration test (test_second_run_mostly_skips)
- [x] CLAUDE.md mis a jour avec V10
- [x] IMPLEMENTATION.md mis a jour
- [x] 994 tests passent (baseline 963 → +31 tests)
