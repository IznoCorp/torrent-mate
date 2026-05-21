# Implementation Plan — provider-ids

> Generated from `docs/features/provider-ids/DESIGN.md` §9 (TDD sequencing).
> 15 phases ordonnées par dépendance. Chaque phase est indépendamment exécutable
> dès lors que les phases précédentes (gate) sont marquées `[x]`.

## Phases

| #   | Phase                                                         | File                                  | Status |
| --- | ------------------------------------------------------------- | ------------------------------------- | ------ |
| 1   | Capabilities Protocols (api/\_contracts.py + per-domain)      | phase-01-capabilities-protocols.md    | [ ]    |
| 2   | Fix DEV #2 — IDs propagation (regression tests first)         | phase-02-fix-dev2-ids-propagation.md  | [ ]    |
| 3   | Façades IMDb + RottenTomatoes (sur OMDbAdapter)               | phase-03-imdb-rt-facades.md           | [ ]    |
| 4   | Drift validator renforcé (canonical uniqueid required)        | phase-04-drift-validator-hardening.md | [ ]    |
| 5   | Xref enrichment sequential + \_resolve_external_ids           | phase-05-xref-enrichment.md           | [ ]    |
| 6   | NFO ratings multi-source + uniqueid default canonical         | phase-06-nfo-ratings-multisource.md   | [ ]    |
| 7   | DB schema — external_ids_json + ratings_json + canonical_prov | phase-07-db-schema-external-ids.md    | [ ]    |
| 8   | Backfill mode + CLI + auto-trigger post-scrape                | phase-08-backfill-mode.md             | [ ]    |
| 9   | Verify checker — 3 nouveaux checks                            | phase-09-verify-checker-extensions.md | [ ]    |
| 10  | Consommateurs library/conf/trailers refactor                  | phase-10-consumers-refactor.md        | [ ]    |
| 11  | Tracker capabilities + LaCale/C411 refactor                   | phase-11-tracker-capabilities.md      | [ ]    |
| 12  | Tracker registry priority-aware par type de média             | phase-12-tracker-registry-priority.md | [ ]    |
| 13  | Torrent capabilities + QBit/Transmission refactor             | phase-13-torrent-capabilities.md      | [ ]    |
| 14  | Notify capabilities + Telegram/Healthchecks refactor          | phase-14-notify-capabilities.md       | [ ]    |
| 15  | Integration + E2E + final wire                                | phase-15-integration-e2e.md           | [ ]    |

## Dependency graph

```
1 (capabilities) → 2 (fix IDs) → 3 (façades IMDb/RT) → 4 (drift) → 5 (xref) → 6 (NFO) → 7 (DB)
                                                                                          ↓
                                                                                  8 (backfill)
                                                                                          ↓
                                                                              9 (verify checks)
                                                                                          ↓
                                                                              10 (consumers)
                                                                                          ↓
1 → 11 (tracker caps) → 12 (tracker registry)
                                                                                          ↓
1 → 13 (torrent caps)
                                                                                          ↓
1 → 14 (notify caps)
                                                                                          ↓
                                                                              15 (integration+e2e)
```

Phases 11, 13, 14 dépendent uniquement de phase 1 (capabilities) ; pourront être
parallélisées si l'utilisateur le souhaite (mais l'ordre par défaut est séquentiel
pour limiter les conflits de merge).

## Memory constraints respected

- `feedback_no_backcompat_before_v1` : phases 7 (DB), 10-14 (config tracker) appliquent les modifs **directement** à la BDD/config réelle dans le même commit (pas de scripts de migration generic).
- `feedback_multi_provider_ids_separation` : aucune phase n'autorise cross-contamination familles. La hiérarchie TVDB primaire → TMDB info+fallback → IMDb info est respectée bout en bout.
- `feedback_regression_test_per_bug` : phase 2 commence par les tests qui reproduisent DEV #2 (test fail → fix → test pass).
- `feedback_event_bus_no_deferral` (appliqué à provider-ids) : aucun item DESIGN différé. Si une phase déborde, on découpe en sub-phases plutôt que reporter à un cycle futur.

## Acceptance global (= §12 DESIGN)

Au merge de la PR provider-ids, les 10 acceptance criteria §12 doivent tous passer :

1. 6 shows staging → NFOs épisode avec uniqueid canonique
2. process nouveau show → NFOs complets (canonical + cross-ref)
3. `personalscraper indexer --backfill-ids` comble gaps sans destruction
4. BDD sans colonnes legacy, queries existantes OK via external_ids_json
5. `OverrideRule.imdb_id` supprimé + config migrée
6. api/\* en capabilities composées, plus de Protocol monolithique
7. TrackerRegistry priority-aware fonctionne
8. Tests 100% pass, coverage ≥ 90% sur lignes touchées
9. CLI publique inchangée hors `--backfill-ids`
10. Pipeline-run dispatch 2026-05-17-09h24 relançable post-merge

## Next action

Run `/implement:phase` to start Phase 1 (Capabilities Protocols).
