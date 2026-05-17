# Implementation Progress — provider-ids

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `provider-ids`
**Feature**: Multi-Provider IDs Propagation + Capabilities Refactor (type: minor)
**Version bump**: 0.14.0 → 0.15.0
**Branch**: feat/provider-ids
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/provider-ids/DESIGN.md
**Master plan**: docs/features/provider-ids/plan/INDEX.md

## Active memories (à respecter pour TOUTES les phases)

- `feedback_multi_provider_ids_separation` — hiérarchie TVDB primaire → TMDB info+fallback → IMDb info, séparation stricte des familles, idempotence par famille.
- `feedback_no_backcompat_before_v1` — pas de scripts de migration generic ; modifs schema/config/NFO appliquées directement à l'unique instance dans le même PR (< v1.0.0).
- `feedback_regression_test_per_bug` — chaque bug code détecté a un test RED qui le reproduit avant le fix.
- `feedback_event_bus_no_deferral` (appliqué à provider-ids) — aucun item DESIGN différé. Phase qui déborde → découper en sub-phases.
- `feedback_pipeline_dry_run_first` — pour toute commande pipeline pendant l'implémentation, dry-run d'abord, valider, puis real.
- `feedback_tooling_diagnostics` — utiliser `command python` / `command rg`, trust `make test`.

## Codebase sync notes (post contre-analyse 2026-05-17)

Le DESIGN initial référence un snapshot du codebase (HEAD `8ef2c87`) antérieur aux features mergées récemment (api-unify v0.11.0, pipeline-obs v0.13.0, event-bus v0.14.0). Sync vérifiée par grep direct sur HEAD `ec44b3e` :

- **`_build_episode_map`** def à `tv_service.py:605` ; les 2 inner functions à modifier (phase 2.2) sont `_tvdb_fetch` (`:698-711`) et `_tmdb_fetch` (`:712-725`) — payloads actuels `{"title", "still_path": ""}`.
- `_generate_episode_nfos` à `tv_service.py:818` (def).
- `match_episode_files` def à `episode_manager.py:97` ; les 3 assignations `matched[video_path] = ...` aux lignes `153, 177, 202`.
- `nfo_generator.generate_episode_nfo` def à `nfo_generator.py:381` ; bloc uniqueid à `:401-419` ; `_add_ratings` à `:534`.
- `existing_validator.verify_tvshow_scrape_drift` def à `:94` ; check #4 sibling NFO à `:184-186`.
- `api/_contracts.py` existe avec 5 classes (`MediaType`, `ProviderName`, `AuthMode`, `ApiError`, `CircuitOpenError`) — phase 1.1 **ajoute** `HasName`.
- `MetadataProvider` Protocol monolithique à `api/metadata/_base.py:259` avec **8 méthodes publiques** (`search`, `get_details`, `get_artwork_urls`, `get_keywords`, `get_videos`, `get_season`, `get_notations`, `get_recommendations`) — phase 1.2 décompose en **11 capabilities** (8 méthodes + 2 nouveaux `IDValidator`/`IDCrossRef` + 1 split `get_details` → `Movie`/`Tv` DetailsProvider). Décision Option A : capabilities atomiques pour les 4 méthodes "extras" (`ArtworkProvider`, `KeywordProvider`, `VideoProvider`, `RecommendationProvider`).
- `TrackerClient` Protocol à `api/tracker/_base.py:102` (méthodes `search`, `get_categories`) — phase 11 drop + LaCale/C411 composent les 4 capabilities.
- `TorrentClient` Protocol à `api/torrent/_base.py:43` avec **7 méthodes** (`get_completed`, `get_all_hashes`, `is_seeding`, `get_content_path`, `pause`, `resume`, `delete`) — phase 13 drop. Note : `is_seeding`, `pause`, `resume`, `delete` ne sont pas couverts par les 3 capabilities initiales (`TorrentLister`, `TorrentInspector`, `AuthenticatedClient`) — à raffiner pendant la phase 13 (probable ajout `TorrentController` / `TorrentStateInspector`).
- **`api/notify/_base.py` contient déjà** `Notifier(Protocol)` à `:17` (`send`, `send_report`) ET `HealthChecker(Protocol)` à `:35` (`ping_start`, `ping_success`, `ping_fail`) — pas monolithique, déjà capability-style. **Phase 1.5 + 14 ne créent rien de nouveau** : juste migrent les 2 Protocols vers `_contracts.py`, ajoutent `@runtime_checkable`, rendent la composition explicite sur `TelegramNotifier` (`telegram.py:49`, pas `TelegramClient`) et `HealthcheckClient` (`healthchecks.py:46`). Noms et signatures **inchangés**.
- `OverrideRule.imdb_id` existe (`conf/models/preferences.py:82`) ; **aucun import de `OverrideRule` hors `conf/models/`** — suppression triviale. Pas de `config/api.json5` (le fichier référencé dans le DESIGN n'existe pas).
- `Notations` est une dataclass `_base.py:149` avec `provider`, `source`, `score`, `votes_count` — singulière malgré le nom au pluriel. `list[Notations]` = multi-source. Phase 6.1 utilise ce type tel quel.

Statut : **contre-analyse appliquée et complète** (corrections inline dans phase-01, phase-02, phase-13, phase-14, DESIGN §4 §6.2). Phase 13 décision tranchée → Option A : 5 capabilities atomiques (`TorrentLister`, `TorrentInspector`, `AuthenticatedClient`, `TorrentStateInspector`, `TorrentController`). Phase 14 corrigée → Protocols existants (`Notifier`+`HealthChecker`) migrés sans rename.

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

## Sub-phase tracking (filled by /implement:phase)

> Format par phase : sub-phase number, scope, SHA commit, durée, notes. Filled au fur et à mesure de l'exécution.

### Phase 1 — Capabilities Protocols

| Sub  | Scope                                                                 | SHA | Status |
| ---- | --------------------------------------------------------------------- | --- | ------ |
| 1.1  | Add HasName to existing api/\_contracts.py                            | -   | [ ]    |
| 1.2  | Metadata capabilities (11 atomiques) + decompose MetadataProvider     | -   | [ ]    |
| 1.2b | Migration plan for MetadataProvider consumers                         | -   | [ ]    |
| 1.3  | Tracker capabilities                                                  | -   | [ ]    |
| 1.4  | Torrent capabilities (5 atomiques pour 7 méthodes)                    | -   | [ ]    |
| 1.5  | Notify : migrate Notifier+HealthChecker existants vers \_contracts.py | -   | [ ]    |
| 1.6  | Helpers + ProviderFeatureUnavailable                                  | -   | [ ]    |

### Phase 2 — Fix DEV #2 IDs Propagation

| Sub | Scope                                                      | SHA | Status |
| --- | ---------------------------------------------------------- | --- | ------ |
| 2.1 | Regression tests DEV #2 (RED)                              | -   | [ ]    |
| 2.2 | Fix `_build_episode_map` payload (TVDB + TMDb episode IDs) | -   | [ ]    |
| 2.3 | Fix `match_episode_files` passthrough                      | -   | [ ]    |
| 2.4 | Fix `_generate_episode_nfos` use propagated IDs            | -   | [ ]    |

### Phase 3 — IMDb + RT Façades

| Sub | Scope                                             | SHA | Status |
| --- | ------------------------------------------------- | --- | ------ |
| 3.1 | OMDbAdapter refactor (mark internal)              | -   | [ ]    |
| 3.2 | IMDbClient façade                                 | -   | [ ]    |
| 3.3 | RottenTomatoesClient façade                       | -   | [ ]    |
| 3.4 | `_activation.py` wiring + `metadata.json5` update | -   | [ ]    |

### Phase 4 — Drift Validator Hardening

| Sub | Scope                                     | SHA | Status |
| --- | ----------------------------------------- | --- | ------ |
| 4.1 | Tests RED drift sans canonical uniqueid   | -   | [ ]    |
| 4.2 | Helper `_read_canonical_provider`         | -   | [ ]    |
| 4.3 | Étendre check #4                          | -   | [ ]    |
| 4.4 | Test intégration drift → re-scrape (auto) | -   | [ ]    |

### Phase 5 — Xref Enrichment

| Sub | Scope                                        | SHA | Status |
| --- | -------------------------------------------- | --- | ------ |
| 5.1 | `_xref_enrichment` dans tv_service           | -   | [ ]    |
| 5.2 | `_resolve_external_ids` (Q5=B re-validation) | -   | [ ]    |
| 5.3 | Wire dans `scrape_tvshow` flow               | -   | [ ]    |
| 5.4 | Réécriture NFOs xref-add (sans écrasement)   | -   | [ ]    |
| 5.5 | Symétrique movie_service                     | -   | [ ]    |

### Phase 6 — NFO Ratings Multi-Source

| Sub | Scope                                   | SHA | Status |
| --- | --------------------------------------- | --- | ------ |
| 6.1 | `_add_ratings` accepte liste Notations  | -   | [ ]    |
| 6.2 | Caller side pass multi-source           | -   | [ ]    |
| 6.3 | `default="true"` selon canonical (Q6=A) | -   | [ ]    |
| 6.4 | Tests golden NFO format Plex/Kodi       | -   | [ ]    |

### Phase 7 — DB Schema external_ids_json

| Sub  | Scope                                         | SHA | Status |
| ---- | --------------------------------------------- | --- | ------ |
| 7.1  | `indexer/schema.py` new + drop legacy columns | -   | [ ]    |
| 7.2  | Backup `library.db` avant migration           | -   | [ ]    |
| 7.2b | (Plan B fallback) SQL one-shot script         | -   | [ ]    |
| 7.3  | `indexer/query.py` json_extract refactor      | -   | [ ]    |
| 7.4  | Pydantic models `ExternalIds` + `Ratings`     | -   | [ ]    |
| 7.5  | `indexer/scanner.py` write side               | -   | [ ]    |
| 7.6  | Cleanup script one-shot (si Plan B)           | -   | [ ]    |

**Décision Plan A vs Plan B** : à trancher avant exécution. Library < 100 items → Plan A (reset+rescrape) préféré.

### Phase 8 — Backfill Mode

| Sub | Scope                                        | SHA | Status |
| --- | -------------------------------------------- | --- | ------ |
| 8.1 | `_modes/backfill_ids.py` scanner mode        | -   | [ ]    |
| 8.2 | CLI `personalscraper indexer --backfill-ids` | -   | [ ]    |
| 8.3 | Auto-trigger post-scrape                     | -   | [ ]    |
| 8.4 | EventBus events (Backfill\*)                 | -   | [ ]    |

### Phase 9 — Verify Checker Extensions

| Sub | Scope                                            | SHA | Status |
| --- | ------------------------------------------------ | --- | ------ |
| 9.1 | Check `episode_canonical_uniqueid_present` ERROR | -   | [ ]    |
| 9.2 | Check `episode_xref_secondary_id_present` WARN   | -   | [ ]    |
| 9.3 | Check `episode_xref_imdb_id_present` WARN        | -   | [ ]    |
| 9.4 | Update output + checks_total 15→18               | -   | [ ]    |

### Phase 10 — Consumers Refactor

| Sub  | Scope                                          | SHA | Status |
| ---- | ---------------------------------------------- | --- | ------ |
| 10.1 | `library/recommender.py` via external_ids_json | -   | [ ]    |
| 10.2 | `library/scanner.py` writes                    | -   | [ ]    |
| 10.3 | Drop `OverrideRule.imdb_id`                    | -   | [ ]    |
| 10.4 | `trailers/scanner.py` + `orchestrator.py`      | -   | [ ]    |
| 10.5 | `config.example/` cleanup                      | -   | [ ]    |

### Phase 11 — Tracker Capabilities

| Sub  | Scope                                    | SHA | Status |
| ---- | ---------------------------------------- | --- | ------ |
| 11.1 | Drop monolithic `TrackerClient` Protocol | -   | [ ]    |
| 11.2 | `LaCaleClient` composes capabilities     | -   | [ ]    |
| 11.3 | `C411Client` composes capabilities       | -   | [ ]    |
| 11.4 | Update `TrackerRegistry` type hints      | -   | [ ]    |

### Phase 12 — Tracker Registry Priority-Aware

| Sub  | Scope                                       | SHA | Status |
| ---- | ------------------------------------------- | --- | ------ |
| 12.1 | `__init__` accepts `priority_by_media_type` | -   | [ ]    |
| 12.2 | `search_all(query, media_type=None)`        | -   | [ ]    |
| 12.3 | Schema `TrackerConfig` field                | -   | [ ]    |
| 12.4 | `config.example/tracker.json5` update       | -   | [ ]    |
| 12.5 | `_activation.py` wiring                     | -   | [ ]    |

### Phase 13 — Torrent Capabilities

| Sub  | Scope                                                         | SHA | Status |
| ---- | ------------------------------------------------------------- | --- | ------ |
| 13.1 | Drop monolithic `TorrentClient` Protocol                      | -   | [ ]    |
| 13.2 | `QBitClient` composes 5 capabilities (full)                   | -   | [ ]    |
| 13.3 | `TransmissionClient` composes subset (no AuthenticatedClient) | -   | [ ]    |
| 13.4 | `_factory.py` type hints                                      | -   | [ ]    |
| 13.5 | Consommateurs `ingest/` adaptés                               | -   | [ ]    |

### Phase 14 — Notify Capabilities (pas de drop monolithique — Protocols Notifier+HealthChecker existent déjà)

| Sub  | Scope                                                                 | SHA | Status |
| ---- | --------------------------------------------------------------------- | --- | ------ |
| 14.1 | Vérif `_base.py` (Notifier+HealthChecker déjà séparés en 2 Protocols) | -   | [ ]    |
| 14.2 | `TelegramNotifier` (telegram.py:49) déclare `Notifier` explicitement  | -   | [ ]    |
| 14.3 | `HealthcheckClient` déclare `HealthChecker` (pas HealthBeacon)        | -   | [ ]    |
| 14.4 | Consommateurs (pipeline, cron) annotations                            | -   | [ ]    |

### Phase 15 — Integration + E2E

| Sub  | Scope                                                                  | SHA | Status |
| ---- | ---------------------------------------------------------------------- | --- | ------ |
| 15.1 | Integration tests scrape pipeline                                      | -   | [ ]    |
| 15.2 | Integration tests backfill + verify + dispatch                         | -   | [ ]    |
| 15.3 | E2E test sur fixture show                                              | -   | [ ]    |
| 15.4 | Regression e2e DEV #2 (6 shows scenario)                               | -   | [ ]    |
| 15.5 | Validate 10 acceptance criteria DESIGN §12                             | -   | [ ]    |
| 15.6 | Update CLAUDE.md + docs/reference (incl. indexer-json-shapes, logging) | -   | [ ]    |

## Quality gates (à passer à chaque phase gate commit)

Per `CLAUDE.md` Phase Gate Checklist :

1. `make lint` (ruff + mypy) — zéro erreur
2. `make test` — tous les tests pass, 0 ERROR / 0 FAILED
3. `make check` — lint + test + module-size + typed-api guardrails
4. Residual import grep — pour chaque module deleted, `rg "old.module.path" personalscraper/ tests/ --type py` = 0
5. `command python -c "import personalscraper"` — smoke test

## Review cycles

_(filled by implement:pr-review — max 3 cycles après création PR)_

| Cycle | Date | Issues catched | Resolved | Notes |
| ----- | ---- | -------------- | -------- | ----- |
| -     | -    | -              | -        | -     |

## Pipeline-run pending

Staging area du run 2026-05-17-09h24 conservée intacte (8 items dispatch-ready) : I Origins (2014), American Dad! S22, Dexter New Blood S01, FROM (2022), LOL Qui rit sort ! S06, Stranger Things Tales from '85 S01, The Boys S05, Top Chef S17. (Top Chef Le Concours Parallèle S17E10 reste blocked par root_video_files safety net — DESIGN_CONFORM.)

Post-merge provider-ids → relancer le dispatch sur cette staging area (acceptance criterion #10 du DESIGN).

## Next action

1. Attendre fin des modifs manuelles utilisateur sur les phase files.
2. Au signal utilisateur : lancer contre-analyse complète (cohérence DESIGN ↔ phases ↔ codebase actuel ↔ memories).
3. Adapter / corriger les phase files si nécessaire.
4. Puis `/implement:phase` pour démarrer Phase 1 (Capabilities Protocols).
