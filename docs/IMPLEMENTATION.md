# IMPLEMENTATION.md — Media Pipeline Automation

## Vue d'ensemble

Automatisation complète du workflow media : de la récupération des torrents terminés jusqu'au dispatch sur les disques de stockage, avec scraping metadata et notifications.

```
torrents/complete → A TRIER/ → Sort+Clean → Scrape → Disk1-4
                                                        ↓
                                                   Log + Notify
```

## Workflow global

Le projet suit **deux grandes étapes séquentielles** :

### Étape A — Modélisation complète (AVANT tout code)

Toutes les versions (V1→V5) sont entièrement modélisées avant de toucher au code.
Pour chaque version :

1. **Brainstorming** — Explorer les besoins, contraintes, options → `BRAINSTORMING.md`
2. **Design** — Architecture, modules, interfaces, flux de données → `DESIGN.md`
3. **Plan** — Découpage en phases et sous-phases → `plan/INDEX.md` + `plan/phase-XX.md`

Quand les 5 versions sont planifiées → **review globale** de cohérence inter-versions.

### Étape B — Implémentation (APRÈS validation complète)

Les versions sont implémentées séquentiellement (V1 → V2 → ... → V5).
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

| Étape                              | Status                               |
| ---------------------------------- | ------------------------------------ |
| A. Modélisation V0 (PROJECT SETUP) | [~] Brainstorming OK, design à faire |
| A. Modélisation V1 (INGEST)        | [x] Brainstorming + Design + Plan    |
| A. Modélisation V2 (SORT+CLEAN)    | [~] Brainstorming OK, design à faire |
| A. Modélisation V3 (SCRAPE)        | [~] Brainstorming OK, design à faire |
| A. Modélisation V4 (DISPATCH)      | [~] Brainstorming OK, design à faire |
| A. Modélisation V5 (LOG+NOTIFY)    | [~] Brainstorming OK, design à faire |
| A. Review globale inter-versions   | [ ] Après modélisation complète      |
| B. Implémentation V0               | [ ] Après review globale             |
| B. Implémentation V1               | [ ]                                  |
| B. Implémentation V2               | [ ]                                  |
| B. Implémentation V3               | [ ]                                  |
| B. Implémentation V4               | [ ]                                  |
| B. Implémentation V5               | [ ]                                  |

---

## Versions

### V0 — PROJECT SETUP `[ ] Modélisation à faire`

> Mise en place du projet Python (pyproject.toml, Makefile, ruff, pytest, CLI Click, pydantic-settings) + intégration FileMate

| Document      | Fichier                                                                | Status |
| ------------- | ---------------------------------------------------------------------- | ------ |
| Brainstorming | [v0-project-setup/BRAINSTORMING.md](v0-project-setup/BRAINSTORMING.md) | [ ]    |
| Design        | [v0-project-setup/DESIGN.md](v0-project-setup/DESIGN.md)               | [ ]    |
| Plan (index)  | [v0-project-setup/plan/INDEX.md](v0-project-setup/plan/INDEX.md)       | [ ]    |

---

### V1 — INGEST `[x] Modélisation terminée`

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

| Document      | Fichier                                                  | Status |
| ------------- | -------------------------------------------------------- | ------ |
| Brainstorming | [v1-ingest/BRAINSTORMING.md](v1-ingest/BRAINSTORMING.md) | [x]    |
| Design        | [v1-ingest/DESIGN.md](v1-ingest/DESIGN.md)               | [x]    |
| Plan (index)  | [v1-ingest/plan/INDEX.md](v1-ingest/plan/INDEX.md)       | [x]    |

**5 phases, 12 sous-phases** — Modules : `qbit_client.py`, `tracker.py`, `ingest.py`

---

### V2 — SORT + CLEAN `[ ] Modélisation à faire`

> Tri automatique via FileMate (amélioré) + nettoyage des noms de fichiers

| Document      | Fichier                                                          | Status |
| ------------- | ---------------------------------------------------------------- | ------ |
| Brainstorming | [v2-sort-clean/BRAINSTORMING.md](v2-sort-clean/BRAINSTORMING.md) | [ ]    |
| Design        | [v2-sort-clean/DESIGN.md](v2-sort-clean/DESIGN.md)               | [ ]    |
| Plan (index)  | [v2-sort-clean/plan/INDEX.md](v2-sort-clean/plan/INDEX.md)       | [ ]    |

---

### V3 — SCRAPE `[ ] Modélisation à faire`

> Scraping automatique des métadonnées (TMDB/TVDB), génération NFO, téléchargement artwork

| Document      | Fichier                                                  | Status |
| ------------- | -------------------------------------------------------- | ------ |
| Brainstorming | [v3-scrape/BRAINSTORMING.md](v3-scrape/BRAINSTORMING.md) | [ ]    |
| Design        | [v3-scrape/DESIGN.md](v3-scrape/DESIGN.md)               | [ ]    |
| Plan (index)  | [v3-scrape/plan/INDEX.md](v3-scrape/plan/INDEX.md)       | [ ]    |

---

### V4 — DISPATCH `[ ] Modélisation à faire`

> Déplacement intelligent des médias vers Disk1-4 (merge séries, replace films, free space)

| Document      | Fichier                                                      | Status |
| ------------- | ------------------------------------------------------------ | ------ |
| Brainstorming | [v4-dispatch/BRAINSTORMING.md](v4-dispatch/BRAINSTORMING.md) | [ ]    |
| Design        | [v4-dispatch/DESIGN.md](v4-dispatch/DESIGN.md)               | [ ]    |
| Plan (index)  | [v4-dispatch/plan/INDEX.md](v4-dispatch/plan/INDEX.md)       | [ ]    |

---

### V5 — LOG + NOTIFY `[ ] Modélisation à faire`

> Logging structuré + notifications Telegram

| Document      | Fichier                                                          | Status |
| ------------- | ---------------------------------------------------------------- | ------ |
| Brainstorming | [v5-log-notify/BRAINSTORMING.md](v5-log-notify/BRAINSTORMING.md) | [ ]    |
| Design        | [v5-log-notify/DESIGN.md](v5-log-notify/DESIGN.md)               | [ ]    |
| Plan (index)  | [v5-log-notify/plan/INDEX.md](v5-log-notify/plan/INDEX.md)       | [ ]    |

---

## Ressources existantes

| Outil                 | Emplacement                   | Rôle dans le pipeline                                               |
| --------------------- | ----------------------------- | ------------------------------------------------------------------- |
| TorrentMaker          | `~/dev/TorrentMaker/`         | V0 — Template projet Python (pyproject.toml, Makefile, ruff, Click) |
| FileMate              | `~/dev/FileMate/`             | V2 — Intégré au projet, tri par type, nettoyage noms                |
| YoutubeTrailerScraper | `/opt/YoutubeTrailerScraper/` | V3 — Patterns TMDB API réutilisables                                |
| BashMate/MediaMate    | `~/BashMate/MediaMate/`       | V4 — Index/recherche media (à évaluer)                              |
| Scripts plex          | `099-SCRIPTS/plex/`           | V4/V5 — cleanFileSystem, trailerScraper                             |

## Décisions techniques

| Sujet           | Décision                                   | Raison                                                   |
| --------------- | ------------------------------------------ | -------------------------------------------------------- |
| Déclenchement   | Cron 1x/jour à 3h + commande manuelle      | Robustesse, pas de risque fichier en cours d'écriture    |
| FileMate        | Intégrer dans ce projet (pas fork externe) | Utilisé uniquement ici, simplifie la maintenance         |
| Template projet | Basé sur TorrentMaker                      | pyproject.toml, Makefile, ruff, Click, pydantic-settings |
| Nettoyage noms  | Tout virer sauf titre+année                | Seul le nécessaire au scraping doit rester               |
| Dossiers saison | Créés par V3 (scraper), pas V2             | MediaElch le faisait avant, V3 prend le relais           |
| Metadata        | TMDB API (clé existante)                   | Gratuit, multi-langue, artwork inclus                    |
| Notifications   | Telegram bot                               | Choix utilisateur                                        |
| Architecture    | Modulaire (1 fichier par concern)          | Testable indépendamment, maintenable                     |
| Client torrent  | qBittorrent, API Web port 8081             | Client principal, API REST disponible                    |
| Tracking ingest | JSON par hash torrent                      | Simple, suffisant pour le volume                         |

## Conventions

- **Commits** : `vX.Y.Z: Description` (X=version, Y=phase, Z=sous-phase)
- **Langue** : Docs en français, code/comments en anglais
- **Tests** : Chaque module critique a ses tests
- **Dry-run** : Chaque opération destructive supporte `--dry-run`
- **Cohérence** : Contrôle systématique entre chaque phase implémentée
