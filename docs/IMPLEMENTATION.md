# IMPLEMENTATION.md — Media Pipeline Automation

## Vue d'ensemble

Automatisation complète du workflow media : de la récupération des torrents terminés jusqu'au dispatch sur les disques de stockage, avec scraping metadata et notifications.

```
torrents/complete → A TRIER/ → Sort+Clean → Scrape → Verify → Disk1-4
                                                                  ↓
                                                             Log + Notify
```

## Workflow global

Le projet suit **deux grandes étapes séquentielles** :

### Étape A — Modélisation complète (AVANT tout code)

Toutes les versions (V0→V7) sont entièrement modélisées avant de toucher au code.
Pour chaque version :

1. **Brainstorming** — Explorer les besoins, contraintes, options → `BRAINSTORMING.md`
2. **Design** — Architecture, modules, interfaces, flux de données → `DESIGN.md`
3. **Plan** — Découpage en phases et sous-phases → `plan/INDEX.md` + `plan/phase-XX.md`

Quand toutes les versions sont planifiées → **review globale** de cohérence inter-versions.

### Étape B — Implémentation (APRÈS validation complète)

Les versions sont implémentées séquentiellement (V0 → V1 → ... → V7).
Pour chaque version :

1. Implémenter phase par phase, sous-phase par sous-phase
2. **Un commit par sous-phase** (format : `vX.Y.Z: Description`)
3. **Mise à jour de l'avancement** (IMPLEMENTATION.md + plan/INDEX.md) **à chaque sous-phase** — pas en batch
4. **Contrôle de cohérence** entre chaque phase (voir ci-dessous)
5. Test end-to-end de la version complète
6. **Compaction du contexte** : vérifier après chaque sous-phase si le contexte dépasse 80% — si oui, compacter avant de continuer
7. **Flux continu** : ne JAMAIS demander confirmation pour passer à la phase/version suivante — enchaîner automatiquement. Seules raisons d'arrêt : erreur bloquante nécessitant une décision utilisateur, ou compaction contexte

### Conventions de code

- **Docstrings Google Style** obligatoires sur tous les modules, classes, fonctions et méthodes
- **Commentaires inline** pour expliquer le "pourquoi" (pas le "quoi") sur la logique non triviale
- Les docstrings de fonctions incluent : description, `Args:`, `Returns:`, `Raises:` (si applicable)
- Les docstrings de classes incluent : description, `Attributes:` (si applicable)
- Les docstrings de modules incluent : description du rôle du module dans le pipeline
- Langue des docstrings/commentaires : **anglais**

### Contrôles de cohérence (entre chaque phase implémentée)

Avant de passer à la phase suivante, vérifier :

- [ ] Le code implémenté respecte le design prévu
- [ ] Les interfaces exposées correspondent à ce que les phases suivantes attendent
- [ ] Les conventions de nommage/structure sont cohérentes avec les autres versions
- [ ] Les choix techniques ne contredisent pas les décisions des versions ultérieures
- [ ] Le `--dry-run` fonctionne correctement
- [ ] Les erreurs sont gérées selon la stratégie définie dans le design

Si un écart est détecté → mettre à jour le design/plan AVANT de continuer.

---

## Avancement global

| Étape                                     | Status                                          |
| ----------------------------------------- | ----------------------------------------------- |
| A. Modélisation V0 (PROJECT SETUP)        | [x] Brainstorming + Design + Plan               |
| A. Modélisation V1 (INGEST)               | [x] Brainstorming + Design + Plan               |
| A. Modélisation V2 (SORT+CLEAN)           | [x] Brainstorming + Design + Plan               |
| A. Modélisation V3 (SCRAPE)               | [x] Brainstorming + Design + Plan               |
| A. Modélisation V4 (VERIFY)               | [x] Brainstorming + Design + Plan               |
| A. Modélisation V5 (DISPATCH)             | [x] Brainstorming + Design + Plan               |
| A. Modélisation V6 (LOG+NOTIFY)           | [x] Brainstorming + Design + Plan               |
| A. Modélisation V7 (E2E TESTS)            | [x] Brainstorming + Design + Plan               |
| A. Review globale inter-versions          | [x] 79 issues fixed across 5 passes (5/5 CLEAN) |
| B. Implémentation V0                      | [x] 4 phases, 14 sous-phases                    |
| B. Implémentation V1                      | [x] 5 phases, 10 sous-phases                    |
| B. Implémentation V2                      | [x] 4 phases, 8 sous-phases                     |
| B. Implémentation V3                      | [x] 13 phases, 41 sous-phases                   |
| B. Implémentation V4                      | [x] 4 phases, 13 sous-phases                    |
| B. Implémentation V5                      | [x] 3 phases, 5 sous-phases                     |
| B. Implémentation V6                      | [x] 3 phases, 7 sous-phases                     |
| B. Implémentation V7                      | [x] 5 phases, 15 sous-phases                    |
| A. Modélisation V7.x (TEST AUDIT)         | [x] Brainstorming + Design + Plan               |
| B. Implémentation V7.x                    | [x] 4 phases, 12 sous-phases                    |
| A. Modélisation V8 (ROBUSTNESS)           | [x] Brainstorming + Design + Plan               |
| B. Implémentation V8                      | [x] 5 phases, 14 sous-phases                    |
| A. Modélisation V9 (PIPELINE INTEGRITY)   | [x] Brainstorming + Design + Plan               |
| B. Implémentation V9                      | [x] 5 phases, 15 sous-phases                    |
| A. Modélisation V10 (PIPELINE RESILIENCE) | [x] Brainstorming + Design + Plan               |
| B. Implémentation V10                     | [x] 5 phases, 14 sous-phases                    |
| A. Modélisation V11 (CODE QUALITY)        | [x] Design + Plan                               |
| B. Implémentation V11                     | [x] 4 phases, 4 sous-phases                     |

---

## Versions

### V0 — PROJECT SETUP `[x] Modélisation terminée`

> Mise en place du projet Python (pyproject.toml, Makefile, ruff, pytest, CLI Typer, pydantic-settings) + intégration FileMate

| Document      | Fichier                                                                | Status |
| ------------- | ---------------------------------------------------------------------- | ------ |
| Brainstorming | [v0-project-setup/BRAINSTORMING.md](v0-project-setup/BRAINSTORMING.md) | [x]    |
| Design        | [v0-project-setup/DESIGN.md](v0-project-setup/DESIGN.md)               | [x]    |
| Plan (index)  | [v0-project-setup/plan/INDEX.md](v0-project-setup/plan/INDEX.md)       | [x]    |

**4 phases, 14 sous-phases** — Package personalscraper/, CLI Typer, pydantic-settings, logger JSON

---

### V1 — INGEST `[x] Modélisation terminée`

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

| Document      | Fichier                                                  | Status |
| ------------- | -------------------------------------------------------- | ------ |
| Brainstorming | [v1-ingest/BRAINSTORMING.md](v1-ingest/BRAINSTORMING.md) | [x]    |
| Design        | [v1-ingest/DESIGN.md](v1-ingest/DESIGN.md)               | [x]    |
| Plan (index)  | [v1-ingest/plan/INDEX.md](v1-ingest/plan/INDEX.md)       | [x]    |

**5 phases, 10 sous-phases** — Modules : `qbit_client.py`, `tracker.py`, `ingest.py`

---

### V2 — SORT + CLEAN `[x] Modélisation terminée`

> Tri automatique via FileMate (amélioré) + nettoyage des noms de fichiers

| Document      | Fichier                                                          | Status |
| ------------- | ---------------------------------------------------------------- | ------ |
| Brainstorming | [v2-sort-clean/BRAINSTORMING.md](v2-sort-clean/BRAINSTORMING.md) | [x]    |
| Design        | [v2-sort-clean/DESIGN.md](v2-sort-clean/DESIGN.md)               | [x]    |
| Plan (index)  | [v2-sort-clean/plan/INDEX.md](v2-sort-clean/plan/INDEX.md)       | [x]    |

**4 phases, 8 sous-phases** — NameCleaner (guessit), FileMate strategies, Sorter → list[SortResult]

---

### V3 — SCRAPE `[x] Modélisation terminée`

> Scraping automatique des métadonnées (TMDB/TVDB), génération NFO, téléchargement artwork

| Document      | Fichier                                                  | Status |
| ------------- | -------------------------------------------------------- | ------ |
| Brainstorming | [v3-scrape/BRAINSTORMING.md](v3-scrape/BRAINSTORMING.md) | [x]    |
| Design        | [v3-scrape/DESIGN.md](v3-scrape/DESIGN.md)               | [x]    |
| Plan (index)  | [v3-scrape/plan/INDEX.md](v3-scrape/plan/INDEX.md)       | [x]    |

**13 phases, 42 sous-phases** — TMDB/TVDB clients, NFO MediaElch, artwork, episode rename

---

### V4 — VERIFY `[x] Modélisation terminée`

> Quality gate : vérification, correction et qualification des médias scrapés avant dispatch

| Document      | Fichier                                                  | Status |
| ------------- | -------------------------------------------------------- | ------ |
| Brainstorming | [v4-verify/BRAINSTORMING.md](v4-verify/BRAINSTORMING.md) | [x]    |
| Design        | [v4-verify/DESIGN.md](v4-verify/DESIGN.md)               | [x]    |
| Plan (index)  | [v4-verify/plan/INDEX.md](v4-verify/plan/INDEX.md)       | [x]    |

**4 phases, 13 sous-phases** — GenreMapper, MediaChecker, MediaFixer, Verifier CLI

---

### V5 — DISPATCH `[x] Modélisation terminée`

> Déplacement intelligent des médias vers Disk1-4 (merge séries, replace films, free space)

| Document      | Fichier                                                      | Status |
| ------------- | ------------------------------------------------------------ | ------ |
| Brainstorming | [v5-dispatch/BRAINSTORMING.md](v5-dispatch/BRAINSTORMING.md) | [x]    |
| Design        | [v5-dispatch/DESIGN.md](v5-dispatch/DESIGN.md)               | [x]    |
| Plan (index)  | [v5-dispatch/plan/INDEX.md](v5-dispatch/plan/INDEX.md)       | [x]    |

**3 phases, 6 sous-phases** — MediaIndex JSON, Dispatcher replace/merge (catégorisation via V4 genre_mapper)

---

### V6 — LOG + NOTIFY `[x] Modélisation terminée`

> Logging structuré + notifications Telegram

| Document      | Fichier                                                          | Status |
| ------------- | ---------------------------------------------------------------- | ------ |
| Brainstorming | [v6-log-notify/BRAINSTORMING.md](v6-log-notify/BRAINSTORMING.md) | [x]    |
| Design        | [v6-log-notify/DESIGN.md](v6-log-notify/DESIGN.md)               | [x]    |
| Plan (index)  | [v6-log-notify/plan/INDEX.md](v6-log-notify/plan/INDEX.md)       | [x]    |

**3 phases, 7 sous-phases** — TelegramNotifier, pipeline `run`, launchd 3h

---

### V7 — E2E TESTS `[x] Modélisation terminée`

> Tests end-to-end complets du pipeline V1→V6 avec de vrais fichiers torrents

| Document      | Fichier                                                        | Status |
| ------------- | -------------------------------------------------------------- | ------ |
| Brainstorming | [v7-e2e-tests/BRAINSTORMING.md](v7-e2e-tests/BRAINSTORMING.md) | [x]    |
| Design        | [v7-e2e-tests/DESIGN.md](v7-e2e-tests/DESIGN.md)               | [x]    |
| Plan (index)  | [v7-e2e-tests/plan/INDEX.md](v7-e2e-tests/plan/INDEX.md)       | [x]    |

**5 phases, 15 sous-phases** — Registry+markers, torrent setup, assertions, E2E films/séries, cleanup sécurisé

---

### V7.x — TEST AUDIT `[x] Modélisation terminée`

> Audit exhaustif des tests + golden files E2E : résultats attendus pour scrape et dispatch, renforcement couverture

| Document      | Fichier                                                            | Status |
| ------------- | ------------------------------------------------------------------ | ------ |
| Brainstorming | [v7x-test-audit/BRAINSTORMING.md](v7x-test-audit/BRAINSTORMING.md) | [x]    |
| Design        | [v7x-test-audit/DESIGN.md](v7x-test-audit/DESIGN.md)               | [x]    |
| Plan (index)  | [v7x-test-audit/plan/INDEX.md](v7x-test-audit/plan/INDEX.md)       | [x]    |

**4 phases, 13 sous-phases** — Fix tests + renforcement couverture, golden file infrastructure, génération manuelle, intégration E2E

---

### V8 — ROBUSTNESS `[x] Modélisation terminée`

> Durcissement du pipeline : circuit breaker API, anti-faux-positifs fuzzy, rollback dispatch, fallback disque, timeout E2E

| Document      | Fichier                                                          | Status |
| ------------- | ---------------------------------------------------------------- | ------ |
| Brainstorming | [v8-robustness/BRAINSTORMING.md](v8-robustness/BRAINSTORMING.md) | [x]    |
| Design        | [v8-robustness/DESIGN.md](v8-robustness/DESIGN.md)               | [x]    |
| Plan (index)  | [v8-robustness/plan/INDEX.md](v8-robustness/plan/INDEX.md)       | [x]    |

**5 phases, 14 sous-phases** — CircuitBreaker, fuzzy guards, dispatch rollback, disk fallback, E2E timeout

---

### V9 — PIPELINE INTEGRITY `[x] Modélisation terminée`

> Pipeline séquentiel exhaustif avec check de cohérence avant dispatch. Re-clean noms bruts, dedup doublons, verify renforcé, titre FR, gate 097-TEMP.

| Document      | Fichier                                                                          | Status |
| ------------- | -------------------------------------------------------------------------------- | ------ |
| Brainstorming | [v9-pipeline-integrity/BRAINSTORMING.md](v9-pipeline-integrity/BRAINSTORMING.md) | [x]    |
| Design        | [v9-pipeline-integrity/DESIGN.md](v9-pipeline-integrity/DESIGN.md)               | [x]    |
| Plan (index)  | [v9-pipeline-integrity/plan/INDEX.md](v9-pipeline-integrity/plan/INDEX.md)       | [x]    |

**5 phases, 15 sous-phases** — Pipeline orchestrator, reclean+dedup, cleanup+run_process, verify renforcé+titre FR, intégration CLI+E2E

---

### V10 — PIPELINE RESILIENCE `[x] Modélisation terminée`

> Idempotence renforcée des 7 phases, reprise après crash via validation par contenu, nettoyage artéfacts partiels, tests filesystem réalistes.

| Document      | Fichier                                                                              | Status |
| ------------- | ------------------------------------------------------------------------------------ | ------ |
| Brainstorming | [v10-pipeline-resilience/BRAINSTORMING.md](v10-pipeline-resilience/BRAINSTORMING.md) | [x]    |
| Design        | [v10-pipeline-resilience/DESIGN.md](v10-pipeline-resilience/DESIGN.md)               | [x]    |
| Plan (index)  | [v10-pipeline-resilience/plan/INDEX.md](v10-pipeline-resilience/plan/INDEX.md)       | [x]    |

**5 phases, 14 sous-phases** — Helpers validation+fast-skip, scrape resilience, verify+dispatch, tests filesystem, intégration+docs

---

### V11 — CODE QUALITY HARDENING `[x] Terminé`

> Fix 4 architectural issues from comprehensive code review: error isolation, CLI UX, dead code removal, DRY extraction.

| Document | Fichier                                                          | Status |
| -------- | ---------------------------------------------------------------- | ------ |
| Design   | [v11-code-quality/DESIGN.md](v11-code-quality/DESIGN.md)         | [x]    |
| Plan     | [v11-code-quality/plan/INDEX.md](v11-code-quality/plan/INDEX.md) | [x]    |

| Phase | Description                                    | Status |
| ----- | ---------------------------------------------- | ------ |
| 1     | Per-torrent error isolation + typed exceptions | [x]    |
| 2     | CLI config error decorator                     | [x]    |
| 3     | Remove dead TMDBClient.select_best_image       | [x]    |
| 4     | Extract shared \_is_retryable via factory      | [x]    |

**4 phases, all complete** — 1005 tests passing, 0 regressions

---

### V12 — PIPELINE HARDENING `[ ] En cours`

> Fix 17 bugs identified in comprehensive audit: NTFS-safe filenames, episode restructuring, stale path references, qBit pre-check, verify/dispatch safety, crash recovery, and minor improvements.

| Document | Fichier                                                                      | Status |
| -------- | ---------------------------------------------------------------------------- | ------ |
| Design   | [v12-pipeline-hardening/DESIGN.md](v12-pipeline-hardening/DESIGN.md)         | [x]    |
| Plan     | [v12-pipeline-hardening/plan/INDEX.md](v12-pipeline-hardening/plan/INDEX.md) | [x]    |

| Phase | Description                                         | Status |
| ----- | --------------------------------------------------- | ------ |
| 1     | sanitize_filename cohérent (bugs #3,4,5,9,10,13,16) | [x]    |
| 2     | Restructuration épisodes (bugs #1,2,6,7,8)          | [x]    |
| 3     | result.media_path stale (bug #11)                   | [x]    |
| 4     | qBit auth pre-check (bug #12)                       | [x]    |
| 5     | Verify/Dispatch NTFS-safe (bugs #14,15)             | [x]    |
| 6     | Crash recovery pipeline (bug #17)                   | [ ]    |
| 7     | Améliorations mineures                              | [ ]    |
| 8     | pipeline-monitor skill                              | [ ]    |
| 9     | Test audit final                                    | [ ]    |

**Phase 1 complete** — `_cleanup_stale_files` + `sanitize_filename` in reclean — 1010 tests passing, 0 regressions

**Phase 2 complete** — `_find_video_file` recursive (rglob + largest), `_cleanup_empty_release_dirs` after episode rename — 1014 tests passing, 0 regressions

**Phase 5 complete** — `ntfs_safe_names` check in verify checker + `_has_ntfs_illegal_names` pre-scan in dispatcher — 1015 tests passing, 0 regressions

---

## Ressources existantes

| Outil                 | Emplacement                         | Rôle dans le pipeline                                               |
| --------------------- | ----------------------------------- | ------------------------------------------------------------------- |
| TorrentMaker          | `~/dev/TorrentMaker/`               | V0 — Template projet Python (pyproject.toml, Makefile, ruff, Typer) |
| FileMate              | `~/dev/FileMate/`                   | V2 — Intégré au projet, tri par type, nettoyage noms                |
| YoutubeTrailerScraper | `/opt/YoutubeTrailerScraper/`       | V3 — Patterns TMDB API réutilisables                                |
| BashMate/MediaMate    | `~/BashMate/MediaMate/`             | V5 — Index/recherche media (à évaluer)                              |
| Scripts plex          | `099-SCRIPTS/plex/`                 | V5/V6 — cleanFileSystem, trailerScraper                             |
| TMDB API docs         | `docs/TMDB-API.md`                  | V3/V4 — Référence API vérifiée par tests live                       |
| TVDB API docs         | `docs/TVDB-API.md`                  | V3/V4 — Référence API vérifiée par tests live                       |
| guessit evaluation    | `docs/guessit-evaluation.md`        | V2 — Evaluation, tests réels, comparaison regex vs guessit          |
| qbittorrent-api ref   | `docs/qbittorrent-api-reference.md` | V1 — Client, TorrentState enum, erreurs, patterns pipeline          |
| ffprobe reference     | `docs/ffprobe-reference.md`         | V3 — Extraction streamdetails, mapping codec Kodi, langue ISO       |
| rapidfuzz reference   | `docs/rapidfuzz-reference.md`       | V3 — Fuzzy matching titres, scorers, media_processor, confidence    |
| tenacity reference    | `docs/tenacity-reference.md`        | V3 — Retry API calls, backoff exponentiel, rate limits TMDB/TVDB    |
| rich reference        | `docs/rich-reference.md`            | V0 — CLI output, progress bars, tables, theming, Typer integration  |
| structlog reference   | `docs/structlog-reference.md`       | V6 — Logging JSON structuré, context binding, switch dev/prod       |

## Décisions techniques

| Sujet             | Décision                                                           | Raison                                                          |
| ----------------- | ------------------------------------------------------------------ | --------------------------------------------------------------- |
| Déclenchement     | Cron 1x/jour à 3h + commande manuelle                              | Robustesse, pas de risque fichier en cours d'écriture           |
| FileMate          | Intégrer dans ce projet (pas fork externe)                         | Utilisé uniquement ici, simplifie la maintenance                |
| Template projet   | Basé sur TorrentMaker                                              | pyproject.toml, Makefile, ruff, Typer, pydantic-settings        |
| Config            | pydantic-settings (from scratch)                                   | TorrentMaker utilise des dataclasses — config réécrite          |
| Nettoyage noms    | guessit (moteur de règles)                                         | Remplace regex custom, 140+ services, cas edge robustes         |
| Dossiers saison   | Créés par V3 (scraper), pas V2                                     | MediaElch le faisait avant, V3 prend le relais                  |
| Metadata films    | TMDB API (clé existante)                                           | Gratuit, multi-langue, artwork inclus                           |
| Metadata séries   | TVDB API v4 (prioritaire), TMDB fallback                           | TVDB meilleur pour séries/anime, TMDB en complément             |
| Streamdetails     | ffprobe (subprocess)                                               | Déjà installé, zéro dep Python, standard industrie              |
| Notifications     | Telegram bot                                                       | Choix utilisateur                                               |
| Architecture      | Modulaire (1 fichier par concern)                                  | Testable indépendamment, maintenable                            |
| Client torrent    | qbittorrent-api (Python lib)                                       | Gère auth/CSRF/compat qBit v5.0+, plus fiable que maison        |
| Tracking ingest   | JSON par hash torrent                                              | Simple, suffisant pour le volume                                |
| Lock pipeline     | .personalscraper/pipeline.lock (configurable via DATA_DIR_NAME)    | Empêche les exécutions concurrentes (scheduling + manuel)       |
| Données locales   | .personalscraper/ (sous staging_dir, configurable)                 | Cohérent : tracker, index media, lock                           |
| Quality gate      | V4 verify entre scrape et dispatch                                 | Corrige puis bloque les dossiers non conformes                  |
| Catégorisation    | genre_mapper.py (racine package, partagé V4/V5)                    | Mapping genres TMDB/TVDB → catégories disques                   |
| Tests E2E         | Vrais torrents + vrais appels API                                  | Marker files + registre pour cleanup sécurisé                   |
| Sécurité E2E      | Triple vérification avant suppression                              | Marker + UUID session + registre — jamais rm -rf                |
| Fuzzy matching    | rapidfuzz (WRatio + media_processor)                               | MIT (vs GPL thefuzz), C++ 5-100x plus rapide, accents FR        |
| API retry         | tenacity (backoff exponentiel)                                     | Gère 429/5xx, wait_exception pour Retry-After, composable       |
| CLI output        | rich (progress, tables, theming)                                   | 56k stars, Click-compatible, auto-détection TTY                 |
| Logging struct.   | structlog (JSON + context binding)                                 | Remplace JsonFormatter custom, switch dev/prod auto             |
| Shared text       | `text_utils.py` (media_processor partagé)                          | NFD accents FR, utilisé par V2 matcher, V3 confidence, V5       |
| Modèles partagés  | `models.py` (SortResult, StepReport)                               | Contrat inter-versions : chaque run\_\*() → StepReport          |
| Dossiers TV       | V2 `Show Name/`, V3 → `Show Name (Year)/`                          | V2 n'a pas l'année, V3 renomme après matching API               |
| Seuil disque      | `max(min_free_gb, item_size_gb * 1.5)`                             | Formule unifiée V5, garantit marge pour gros fichiers           |
| E2E marker        | Placement unique après ingest, survit au pipeline                  | Pas de re-placement — sécurité cleanup par design               |
| Circuit breaker   | Interne (pas pybreaker), 5 erreurs → cooldown 5 min                | Tenacity = transitoire, CB = panne durable, pas de nouvelle dep |
| Anti-faux-positif | fuzzy_match_score() partagé (année ±1, len ratio, seuil adaptatif) | Un seuil fixe ne suffit pas — titres courts trop sensibles      |
| Dispatch rollback | staging→commit (_tmp_dispatch_\*) + backup merge                   | Garantit état cohérent sur disque, même pattern que \_replace() |
| Disk fallback     | Auto-create catégorie pour nouveaux, skip pour existants           | Nouveaux = sans risque, existants = impact Kodi/Plex            |
| E2E timeout       | ceil(GB) × 3 min, minimum 10 min                                   | Empêche tests bloqués indéfiniment, ≈5.7 MB/s minimum           |

## Conventions

- **Commits** : `vX.Y.Z: Description` (X=version, Y=phase, Z=sous-phase)
- **Langue** : Docs en français, code/comments en anglais
- **Tests** : Chaque module critique a ses tests
- **Dry-run** : Chaque opération destructive supporte `--dry-run`
- **Cohérence** : Contrôle systématique entre chaque phase implémentée
