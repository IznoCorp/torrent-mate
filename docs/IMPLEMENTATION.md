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
3. **Contrôle de cohérence** entre chaque phase (voir ci-dessous)
4. Test end-to-end de la version complète
5. Mise à jour de ce fichier

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

| Étape                              | Status                            |
| ---------------------------------- | --------------------------------- |
| A. Modélisation V0 (PROJECT SETUP) | [x] Brainstorming + Design + Plan |
| A. Modélisation V1 (INGEST)        | [x] Brainstorming + Design + Plan |
| A. Modélisation V2 (SORT+CLEAN)    | [x] Brainstorming + Design + Plan |
| A. Modélisation V3 (SCRAPE)        | [x] Brainstorming + Design + Plan |
| A. Modélisation V4 (VERIFY)        | [x] Brainstorming + Design + Plan |
| A. Modélisation V5 (DISPATCH)      | [x] Brainstorming + Design + Plan |
| A. Modélisation V6 (LOG+NOTIFY)    | [x] Brainstorming + Design + Plan |
| A. Modélisation V7 (E2E TESTS)     | [x] Brainstorming + Design + Plan |
| A. Review globale inter-versions   | [x] 62 issues fixed (17C+30I+15M) |
| B. Implémentation V0               | [ ]                               |
| B. Implémentation V1               | [ ]                               |
| B. Implémentation V2               | [ ]                               |
| B. Implémentation V3               | [ ]                               |
| B. Implémentation V4               | [ ]                               |
| B. Implémentation V5               | [ ]                               |
| B. Implémentation V6               | [ ]                               |
| B. Implémentation V7               | [ ]                               |

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

| Sujet            | Décision                                          | Raison                                                    |
| ---------------- | ------------------------------------------------- | --------------------------------------------------------- |
| Déclenchement    | Cron 1x/jour à 3h + commande manuelle             | Robustesse, pas de risque fichier en cours d'écriture     |
| FileMate         | Intégrer dans ce projet (pas fork externe)        | Utilisé uniquement ici, simplifie la maintenance          |
| Template projet  | Basé sur TorrentMaker                             | pyproject.toml, Makefile, ruff, Typer, pydantic-settings  |
| Config           | pydantic-settings (from scratch)                  | TorrentMaker utilise des dataclasses — config réécrite    |
| Nettoyage noms   | guessit (moteur de règles)                        | Remplace regex custom, 140+ services, cas edge robustes   |
| Dossiers saison  | Créés par V3 (scraper), pas V2                    | MediaElch le faisait avant, V3 prend le relais            |
| Metadata films   | TMDB API (clé existante)                          | Gratuit, multi-langue, artwork inclus                     |
| Metadata séries  | TVDB API v4 (prioritaire), TMDB fallback          | TVDB meilleur pour séries/anime, TMDB en complément       |
| Streamdetails    | ffprobe (subprocess)                              | Déjà installé, zéro dep Python, standard industrie        |
| Notifications    | Telegram bot                                      | Choix utilisateur                                         |
| Architecture     | Modulaire (1 fichier par concern)                 | Testable indépendamment, maintenable                      |
| Client torrent   | qbittorrent-api (Python lib)                      | Gère auth/CSRF/compat qBit v5.0+, plus fiable que maison  |
| Tracking ingest  | JSON par hash torrent                             | Simple, suffisant pour le volume                          |
| Lock pipeline    | ~/.personalscraper/pipeline.lock (PID)            | Empêche les exécutions concurrentes (scheduling + manuel) |
| Données locales  | Tout dans ~/.personalscraper/                     | Cohérent : tracker, index media, lock                     |
| Quality gate     | V4 verify entre scrape et dispatch                | Corrige puis bloque les dossiers non conformes            |
| Catégorisation   | genre_mapper.py (racine package, partagé V4/V5)   | Mapping genres TMDB/TVDB → catégories disques             |
| Tests E2E        | Vrais torrents + vrais appels API                 | Marker files + registre pour cleanup sécurisé             |
| Sécurité E2E     | Triple vérification avant suppression             | Marker + UUID session + registre — jamais rm -rf          |
| Fuzzy matching   | rapidfuzz (WRatio + media_processor)              | MIT (vs GPL thefuzz), C++ 5-100x plus rapide, accents FR  |
| API retry        | tenacity (backoff exponentiel)                    | Gère 429/5xx, wait_exception pour Retry-After, composable |
| CLI output       | rich (progress, tables, theming)                  | 56k stars, Click-compatible, auto-détection TTY           |
| Logging struct.  | structlog (JSON + context binding)                | Remplace JsonFormatter custom, switch dev/prod auto       |
| Shared text      | `text_utils.py` (media_processor partagé)         | NFD accents FR, utilisé par V2 matcher, V3 confidence, V5 |
| Modèles partagés | `models.py` (SortResult, StepReport)              | Contrat inter-versions : chaque run\_\*() → StepReport    |
| Dossiers TV      | V2 `Show Name/`, V3 → `Show Name (Year)/`         | V2 n'a pas l'année, V3 renomme après matching API         |
| Seuil disque     | `max(min_free_gb, item_size_gb * 1.5)`            | Formule unifiée V5, garantit marge pour gros fichiers     |
| E2E marker       | Placement unique après ingest, survit au pipeline | Pas de re-placement — sécurité cleanup par design         |

## Conventions

- **Commits** : `vX.Y.Z: Description` (X=version, Y=phase, Z=sous-phase)
- **Langue** : Docs en français, code/comments en anglais
- **Tests** : Chaque module critique a ses tests
- **Dry-run** : Chaque opération destructive supporte `--dry-run`
- **Cohérence** : Contrôle systématique entre chaque phase implémentée
