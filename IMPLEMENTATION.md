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

Le DESIGN initial référence un snapshot du codebase (HEAD `8ef2c87`) antérieur aux features mergées récemment (api-unify v0.11.0, pipeline-obs v0.13.0, event-bus v0.14.0). **Sync vérifiée par grep direct (tous les file:line refs ci-dessous validés sur `feat/provider-ids` HEAD le plus récent — chaque exécution de phase doit re-vérifier au cas où le code aurait bougé entretemps) :**

- **`_build_episode_map`** def à `tv_service.py:605` ; les 2 inner functions à modifier (phase 2.2) sont `_tvdb_fetch` (`:698-711`) et `_tmdb_fetch` (`:712-725`) — payloads actuels `{"title", "still_path": ""}`.
- `_generate_episode_nfos` à `tv_service.py:818` (def).
- `match_episode_files` def à `episode_manager.py:97` ; les 3 assignations `matched[video_path] = ...` aux lignes `153, 177, 202`.
- `nfo_generator.generate_episode_nfo` def à `nfo_generator.py:381` ; bloc uniqueid à `:401-419` ; `_add_ratings` à `:534`.
- `existing_validator.verify_tvshow_scrape_drift` def à `:94` ; check #4 sibling NFO à `:184-186`.
- `api/_contracts.py` existe avec 5 classes (`MediaType`, `ProviderName`, `AuthMode`, `ApiError`, `CircuitOpenError`) — phase 1.1 **ajoute** `HasName`.
- `MetadataProvider` Protocol monolithique à `api/metadata/_base.py:259` avec **8 méthodes publiques** (`search`, `get_details`, `get_artwork_urls`, `get_keywords`, `get_videos`, `get_season`, `get_notations`, `get_recommendations`) — phase 1.2 décompose en **11 capabilities** (8 méthodes + 2 nouveaux `IDValidator`/`IDCrossRef` + 1 split `get_details` → `Movie`/`Tv` DetailsProvider). Décision Option A : capabilities atomiques pour les 4 méthodes "extras" (`ArtworkProvider`, `KeywordProvider`, `VideoProvider`, `RecommendationProvider`).
- `TrackerClient` Protocol à `api/tracker/_base.py:102` (méthodes `search`, `get_categories`) — phase 11 drop + LaCale/C411 composent les 4 capabilities.
- `TorrentClient` Protocol à `api/torrent/_base.py:43` avec **7 méthodes** (`get_completed`, `get_all_hashes`, `is_seeding`, `get_content_path`, `pause`, `resume`, `delete`) — phase 13 drop. Décomposé en **5 capabilities atomiques** (`TorrentLister`, `TorrentInspector`, `AuthenticatedClient`, `TorrentStateInspector`, `TorrentController`) — voir phase 1.4 + phase 13.
- **`api/notify/_base.py` contient déjà** `Notifier(Protocol)` à `:17` (`send`, `send_report`) ET `HealthChecker(Protocol)` à `:35` (`ping_start`, `ping_success`, `ping_fail`) — pas monolithique, déjà capability-style. **Phase 1.5 + 14 ne créent rien de nouveau** : juste migrent les 2 Protocols vers `_contracts.py`, ajoutent `@runtime_checkable`, rendent la composition explicite sur `TelegramNotifier` (`telegram.py:49`, pas `TelegramClient`) et `HealthcheckClient` (`healthchecks.py:46`). Noms et signatures **inchangés**.
- `OverrideRule.imdb_id` existe (`conf/models/preferences.py:82`) ; **aucun import de `OverrideRule` hors `conf/models/`** — suppression triviale. Pas de `config/api.json5` (le fichier référencé dans le DESIGN n'existe pas).
- `Notations` est une dataclass `_base.py:149` avec `provider`, `source`, `score`, `votes_count` — singulière malgré le nom au pluriel. `list[Notations]` = multi-source. Phase 6.1 utilise ce type tel quel.

Statut : **contre-analyse appliquée et complète** (corrections inline dans phase-01, phase-02, phase-13, phase-14, DESIGN §4 §6.2). Phase 13 décision tranchée → Option A : 5 capabilities atomiques (`TorrentLister`, `TorrentInspector`, `AuthenticatedClient`, `TorrentStateInspector`, `TorrentController`). Phase 14 corrigée → Protocols existants (`Notifier`+`HealthChecker`) migrés sans rename.

## Phases

| #   | Phase                                                         | File                                  | Status |
| --- | ------------------------------------------------------------- | ------------------------------------- | ------ |
| 1   | Capabilities Protocols (api/\_contracts.py + per-domain)      | phase-01-capabilities-protocols.md    | [x]    |
| 2   | Fix DEV #2 — IDs propagation (regression tests first)         | phase-02-fix-dev2-ids-propagation.md  | [x]    |
| 3   | Façades IMDb + RottenTomatoes (sur OMDbAdapter)               | phase-03-imdb-rt-facades.md           | [x]    |
| 4   | Drift validator renforcé (canonical uniqueid required)        | phase-04-drift-validator-hardening.md | [x]    |
| 5   | Xref enrichment sequential + \_resolve_external_ids           | phase-05-xref-enrichment.md           | [x]    |
| 6   | NFO ratings multi-source + uniqueid default canonical         | phase-06-nfo-ratings-multisource.md   | [x]    |
| 7   | DB schema — external_ids_json + ratings_json + canonical_prov | phase-07-db-schema-external-ids.md    | [x]    |
| 8   | Backfill mode + CLI + auto-trigger post-scrape                | phase-08-backfill-mode.md             | [x]    |
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

| Sub  | Scope                                                                 | SHA     | Status |
| ---- | --------------------------------------------------------------------- | ------- | ------ |
| 1.1  | Add HasName to existing api/\_contracts.py                            | 2e04938 | [x]    |
| 1.2  | Metadata capabilities (11 atomiques) + decompose MetadataProvider     | bf5b676 | [x]    |
| 1.2b | Migration plan for MetadataProvider consumers                         | b0b1ed8 | [x]    |
| 1.3  | Tracker capabilities                                                  | d0f5e94 | [x]    |
| 1.4  | Torrent capabilities (5 atomiques pour 7 méthodes)                    | 0c75f47 | [x]    |
| 1.5  | Notify : migrate Notifier+HealthChecker existants vers \_contracts.py | 29f7ca0 | [x]    |
| 1.6  | Helpers + ProviderFeatureUnavailable                                  | 723ee8f | [x]    |

### Phase 2 — Fix DEV #2 IDs Propagation

| Sub | Scope                                                      | SHA     | Status |
| --- | ---------------------------------------------------------- | ------- | ------ |
| 2.1 | Regression tests DEV #2 (RED) + EpisodeInfo.external_ids   | 7ef4994 | [x]    |
| 2.2 | Fix `_build_episode_map` payload (TVDB + TMDb episode IDs) | afd06b2 | [x]    |
| 2.3 | Fix `match_episode_files` passthrough                      | 16aa51c | [x]    |
| 2.4 | Fix `_generate_episode_nfos` use propagated IDs            | 306dfc7 | [x]    |

### Phase 3 — IMDb + RT Façades

| Sub  | Scope                                                  | SHA     | Status |
| ---- | ------------------------------------------------------ | ------- | ------ |
| 3.1  | OMDbAdapter refactor (mark internal, alias OMDBClient) | 0c72d81 | [x]    |
| 3.2  | IMDbClient façade                                      | 00fd673 | [x]    |
| 3.3  | RottenTomatoesClient façade                            | 7be760c | [x]    |
| 3.4  | `_activation.py` wiring (PROVIDER_CREDS)               | dc8f876 | [x]    |
| 3.4b | `api/metadata/__init__.py` exports                     | c7a0f57 | [x]    |
| 3.5  | `config.example/metadata.json5` documents IMDb+RT      | 00cd61f | [x]    |

### Phase 4 — Drift Validator Hardening

| Sub  | Scope                                                | SHA     | Status |
| ---- | ---------------------------------------------------- | ------- | ------ |
| 4.1  | Tests RED drift sans canonical uniqueid              | fb497ea | [x]    |
| 4.2  | Helper `_read_canonical_provider` + `_episode_nfo_*` | cfd3dd2 | [x]    |
| 4.3  | Étendre check #4 (drop into the same commit as 4.2)  | cfd3dd2 | [x]    |
| 4.3b | Update existing scraper test fixtures                | 2c8b3e6 | [x]    |
| 4.4  | Test intégration drift → re-scrape                   | 4e5dd17 | [x]    |

### Phase 5 — Xref Enrichment

| Sub  | Scope                                            | SHA     | Status |
| ---- | ------------------------------------------------ | ------- | ------ |
| 5.1  | `_xref_enrichment` dans tv_service               | c7cb588 | [x]    |
| 5.2  | `_resolve_external_ids` (Q5=B re-validation)     | 9621cdf | [x]    |
| 5.3  | Wire dans `scrape_tvshow` flow                   | 905f574 | [x]    |
| 5.4  | Réécriture NFOs xref-add (sans écrasement)       | 9c70a34 | [x]    |
| 5.5  | Symétrique movie_service                         | 965a265 | [x]    |
| 5.5b | Extract xref helpers to `_xref.py` (size budget) | 9aebe50 | [x]    |

### Phase 6 — NFO Ratings Multi-Source

| Sub | Scope                                   | SHA     | Status |
| --- | --------------------------------------- | ------- | ------ |
| 6.1 | `_add_ratings` accepte liste Notations  | fc7aa25 | [x]    |
| 6.2 | Caller side pass multi-source           | bacda30 | [x]    |
| 6.3 | `default="true"` selon canonical (Q6=A) | 5841d22 | [x]    |
| 6.4 | Tests golden NFO format Plex/Kodi       | cb61fb0 | [x]    |

### Phase 7 — DB Schema external_ids_json

| Sub  | Scope                                                         | SHA     | Status |
| ---- | ------------------------------------------------------------- | ------- | ------ |
| 7.1  | Migration 005 + MediaItemRow updates                          | 11016c2 | [x]    |
| 7.1b | item_repo.py + outbox/\_apply.py write to external_ids_json   | fbb9a3d | [x]    |
| 7.2  | Backup `library.db` avant migration                           | -       | manual |
| 7.2b | (Plan A retained) no SQL one-shot script — reset+rescrape     | -       | n/a    |
| 7.3  | `indexer/query.py` FieldSpec via json_extract                 | f6fcc13 | [x]    |
| 7.4  | Pydantic models `ExternalIds` + `Ratings`                     | (7.4)   | [x]    |
| 7.5  | dispatch/library scanners write external_ids_json             | f771b53 | [x]    |
| 7.5b | trailers scanner/orchestrator read ids from external_ids_json | 6c3d6e4 | [x]    |
| 7.6  | Plan A (Plan B unused — no cleanup script needed)             | -       | n/a    |

**Décision Plan A vs Plan B** : à trancher avant exécution. Library < 100 items → Plan A (reset+rescrape) préféré.

### Phase 8 — Backfill Mode

| Sub | Scope                                                                          | SHA                                  | Status  |
| --- | ------------------------------------------------------------------------------ | ------------------------------------ | ------- |
| 8.1 | `backfill_ids.py` gap detection + safe-merge helpers (pure)                    | 11016c2 (init), 970d045 (typing fix) | [x]     |
| 8.2 | `scanner/_modes/backfill_ids.py` driver + `run_backfill_ids()` entrypoint      | (8.2)                                | [x]     |
| 8.3 | Auto-trigger post-scrape — emit-based via EventBus subscriber (CLI wiring TBD) | (8.4)                                | partial |
| 8.4 | EventBus events: BackfillStarted/ItemCompleted/Skipped/Completed + factories   | c369451                              | [x]     |

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

**Démarrage de session (fresh `/clear`)** :

1. **Lire ce fichier en entier** (`IMPLEMENTATION.md`) — tu y es.
2. Lire `docs/features/provider-ids/DESIGN.md` pour le contexte complet de la feature (13 sections, 567 lignes).
3. Lire `docs/features/provider-ids/plan/INDEX.md` pour la vue d'ensemble des 15 phases.
4. Lire `docs/features/provider-ids/plan/phase-02-fix-dev2-ids-propagation.md` (prochaine phase à exécuter — Phase 1 [x] mergée gate 2e04938..723ee8f).
5. Lancer `/implement:phase` pour démarrer Phase 2.

**Mémoires utilisateur à recharger** (la skill `/implement:phase` doit en tenir compte à chaque sub-phase) : voir la section **Active memories** ci-dessus. Les 6 mémoires sont stockées dans `/Users/izno/.claude/projects/-Users-izno-dev-PersonnalScaper/memory/feedback_*.md`.

## Autopilot discipline (mode chaînage automatique des 15 phases)

L'utilisateur a explicitement demandé un **enchainement automatique** des phases sans pause inutile. Règles strictes pour ce mode :

### Boucle d'exécution par sub-phase

```
1. Lire la sub-phase courante (depuis le phase file)
2. Re-grep les file:line refs cités contre le codebase actuel (peut avoir bougé)
3. TDD : écrire les tests RED en premier (cf. memory feedback_regression_test_per_bug)
4. Implémenter le code pour faire passer les tests
5. `make test` ciblé sur les tests nouveaux → GREEN
6. Commit conventional : `<type>(provider-ids): <description>`
7. Update IMPLEMENTATION.md sub-phase tracking : SHA + status [x]
8. /implement:check sur la sub-phase → 7 contrôles
9. Si check pass → sub-phase suivante. Si fail → fix immédiat, pas de defer.
```

### Boucle d'exécution par phase

```
1. Toutes sub-phases d'une phase [x] → quality gate :
   - make lint (ruff + mypy) → 0 erreur
   - make test → tous tests pass, 0 ERROR/FAILED
   - make check (lint + test + module-size + typed-api)
   - residual import grep si modules supprimés
   - python -c "import personalscraper" smoke
2. Commit gate : `chore(provider-ids): phase N gate — <résumé>`
3. Update IMPLEMENTATION.md phase row : [x]
4. Vérifier si découverte de phase N impacte phases N+1..15 (read forward).
   - Si oui : update phase file(s) + commit `docs(provider-ids): adjust plan after phase N`
5. Lancer immédiatement phase N+1 — pas de pause utilisateur, pas de /compact manuel.
```

### Gestion proactive du contexte (zéro pause /compact)

Le système Claude Code **compresse automatiquement** les messages quand le contexte approche la limite ("your conversation with the user is not limited by the context window"). Pas besoin d'invoquer `/compact` à la main entre les phases.

Pour minimiser la pression sur le contexte au quotidien, appliquer les 5 disciplines suivantes :

1. **Dispatcher en subagent les opérations lourdes** :
   - `/implement:check` (7 contrôles) → subagent (`general-purpose` ou agent dédié)
   - Code review d'une grosse diff → subagent (`pr-review-toolkit:code-reviewer`)
   - Analyse d'output de test long → subagent (`general-purpose`)
   - Investigation cross-modules (où est utilisé X ?) → `Explore` agent
   - Le subagent a son propre contexte ; il renvoie un résumé concis.

2. **Lectures minimales en main session** :
   - `Bash` avec `head -N`, `tail -N`, `grep -c`, `sed -n 'X,Yp'` au lieu de `Read` complet.
   - Si un fichier dépasse 200 lignes et qu'on veut juste vérifier une chose : `grep` cible direct.
   - `Read` avec `offset` + `limit` quand on connaît la zone d'intérêt.

3. **Externaliser l'état sur disque immédiatement après chaque sub-phase** :
   - Commit SHA → update IMPLEMENTATION.md sub-phase tracking row → "oublier" les détails internes.
   - Si on a besoin du détail plus tard : `git show <SHA>` pour relire.
   - Toutes les décisions architecturales : DESIGN.md (committed).
   - Toutes les nouvelles règles : `feedback_*.md` memory (committed à la convention).

4. **Ne pas re-lire les mêmes gros fichiers plusieurs fois** :
   - DESIGN.md : lu UNE fois en début de session, puis re-grep cible.
   - INDEX.md : lu UNE fois pour avoir la map, puis on accède directement aux phase files.
   - Chaque phase file : lu UNE fois au début de la phase, puis on consulte par section si besoin.
   - Si on doute → `grep "section-name" docs/features/provider-ids/...` pour cibler.

5. **Trust auto-compression** :
   - Pas de `/compact` manuel pré-emptif. Le système gère.
   - Pas de "je dois libérer du contexte avant la phase suivante" — on continue.
   - Si la compression auto retire un détail critique : tout est sur disque committed, on relit.

**Anti-patterns à éviter pour le contexte** :

| Anti-pattern                                                | Alternative                                             |
| ----------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------ |
| `Read` du DESIGN.md (600 lignes) après chaque sub-phase     | `grep` ciblé sur la section relevante                   |
| Coller le contenu de 5 phase files dans une seule analyse   | Subagent qui lit les 5 et renvoie un résumé             |
| Faire `make test` en main session sur l'output complet      | `make test 2>&1                                         | tail -50` pour ne voir que le résumé |
| Re-lire IMPLEMENTATION.md complet à chaque sub-phase        | Read avec offset sur la sub-phase tracking row courante |
| Logger en main session tous les détails de chaque sub-phase | Subagent qui exécute + commit + renvoie SHA + résumé    |

### Pauses AUTORISÉES uniquement dans ces 6 cas

| Situation                                                   | Action                                               |
| ----------------------------------------------------------- | ---------------------------------------------------- |
| Rate-limit TVDB/TMDB/OMDb pendant re-scrape                 | Attendre fenêtre, reprendre                          |
| API key absente (`OMDB_API_KEY`, etc.)                      | Demander à l'utilisateur, pas inventer               |
| Cas non couvert par DESIGN §3 (séparation familles ambiguë) | Mini-brainstorm avec l'utilisateur                   |
| PR review remonte point HORS scope plan                     | Demander : fix maintenant ou queue pour cycle séparé |
| Test fixture HTTP recorded échoue (API drift)               | Demander : re-record ou mock                         |
| Conflit entre 2 mémoires utilisateur                        | Demander arbitrage                                   |

**Tout le reste est auto-pilot.** Ne jamais demander :

- "Veux-tu que je passe à la phase suivante ?" — non, je passe.
- "Devrais-je découper cette sub-phase ?" — oui si > 150 LOC ou > 1 commit logique, je découpe.
- "Faut-il updater le DESIGN ?" — oui si une découverte le contredit, je update + commit.
- "Faut-il committer ?" — oui après chaque sub-phase, faut commit.

### Adaptation dynamique des phases suivantes

Si pendant phase N je découvre qu'une décision change le scope de phase N+k :

1. **Update le phase file concerné** (ajout sub-phase, modif acceptance criteria, etc.).
2. **Update IMPLEMENTATION.md sub-phase tracking** (nouvelles rows).
3. **Update DESIGN.md** si la décision architecturale change.
4. Commit unique : `docs(provider-ids): adjust phase N+k after phase N findings`.
5. Continuer phase N — ne PAS faire phase N+k en avance.

### Découpage sur dépassement (au lieu de défer)

Si sub-phase N.x déborde naturellement :

- **NON** : "je le mets en TODO pour plus tard" ← `feedback_event_bus_no_deferral` interdit.
- **OUI** : "je découpe en N.x.a + N.x.b" avec acceptance criteria split. Update IMPLEMENTATION.md.

### Recovery post-/compact ou post-/clear

À chaque nouveau démarrage de session :

1. Read `IMPLEMENTATION.md` complet (tu y es).
2. Identifier la dernière sub-phase `[x]` dans le sub-phase tracking → la suivante = à exécuter.
3. Read le phase file correspondant.
4. Re-grep les file:line refs contre le codebase actuel (vérification de sync).
5. Continuer la boucle d'exécution par sub-phase.

Aucune information critique n'est en mémoire conversationnelle — tout est sur disque committed ou dans `feedback_*.md`.

## Critical invariants (NE JAMAIS oublier pendant l'implémentation)

Ces 5 règles s'appliquent à TOUTES les phases sans exception :

1. **Séparation stricte des familles d'IDs** — TVDB / TMDB / IMDb sont 3 familles distinctes. `<uniqueid type="tvdb">` contient un **vrai** ID TVDB ; pas de cross-write. Cf. memory `feedback_multi_provider_ids_separation`.
2. **Hiérarchie scrape canonique fixe** — TVDB primaire → TMDB info+fallback → IMDb info (jamais primary scrape). Cf. DESIGN §3.
3. **Idempotence par famille** — chaque step pipeline peut backfill une famille sans écraser les autres. Cf. DESIGN §3 invariants.
4. **Pre-1.0 : pas de retro-compat, pas de scripts génériques** — toute modif schema/config/NFO appliquée directement à l'unique instance dans le même PR. Cf. memory `feedback_no_backcompat_before_v1`.
5. **TDD strict pour les bugs** — tests RED qui reproduisent le bug AVANT le fix. Cf. memory `feedback_regression_test_per_bug`.

## Hard gate (interdictions explicites)

- **Ne PAS différer** un item du DESIGN (`feedback_event_bus_no_deferral`). Si une phase déborde → découper en sub-phases additionnelles, jamais "remettre à plus tard".
- **Ne PAS commiter** sans avoir vérifié les file:line refs cités dans la sub-phase contre le codebase actuel (le code a peut-être bougé depuis la rédaction du plan — re-grep avant de toucher).
- **Ne PAS ajouter** de capability hors des 11 metadata / 4 tracker / 5 torrent / 2 notify définies. Si un besoin émerge → re-brainstorm.
- **Ne PAS sauter** le commit `chore({codename}): phase N gate` à la fin d'une phase (cf. `CLAUDE.md` Phase Gate Checklist).

## Session-start cheat sheet

| Question                                       | Réponse                                                                                                   |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Quelle branche ?                               | `feat/provider-ids` (créée par `b980433`)                                                                 |
| Quelle version ?                               | `0.15.0` (bumpée depuis 0.14.0, minor Y+1)                                                                |
| Combien de phases ?                            | 15                                                                                                        |
| Combien de capabilities à créer ?              | 22 Protocols (11 metadata + 4 tracker + 5 torrent + 2 notify migrés) + 1 helper (HasName)                 |
| Quel est le bug initial ?                      | DEV #2 du pipeline-run 2026-05-17-09h24 — NFOs épisode sans `<uniqueid>` (root cause 5 layers, DESIGN §1) |
| Quels shows en staging attendent un dispatch ? | 8 (voir Pipeline-run pending ci-dessus)                                                                   |
| Quelles features sont prerequis ?              | event-bus (mergée v0.14.0), pipeline-obs (v0.13.0), api-unify (v0.11.0) — toutes sur main                 |
| Quel merge mode ?                              | manual (`gh pr merge --squash` à la fin)                                                                  |
| Où sont les 6 mémoires utilisateur ?           | `/Users/izno/.claude/projects/-Users-izno-dev-PersonnalScaper/memory/feedback_*.md`                       |
