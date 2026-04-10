# IMPLEMENTATION.md — Media Pipeline Automation

## Vue d'ensemble

Automatisation complète du workflow media : de la récupération des torrents terminés jusqu'au dispatch sur les disques de stockage, avec scraping metadata et notifications.

```
torrents/complete → A TRIER/ → Sort+Clean → Scrape → Disk1-4
                                                        ↓
                                                   Log + Notify
```

## Workflow d'implémentation

Chaque version suit ce processus :

1. **Brainstorming** — Explorer les besoins, contraintes, options. Produit `BRAINSTORMING.md`
2. **Design** — Architecture, choix techniques, interfaces. Produit `DESIGN.md`
3. **Plan** — Découpage en phases et sous-phases. Produit `plan/INDEX.md` + `plan/phase-XX.md`
4. **Implémentation** — Code, tests, commit par sous-phase
5. **Validation** — Test end-to-end de la version, mise à jour de ce fichier

> **Règle : un commit par sous-phase complétée.** Le message de commit référence la version et la sous-phase (ex: `v1.1.2: Implement file stability check`).

---

## Versions

### V1 — INGEST `[ ] Non commencé`

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

| Document      | Fichier                                                  | Status |
| ------------- | -------------------------------------------------------- | ------ |
| Brainstorming | [v1-ingest/BRAINSTORMING.md](v1-ingest/BRAINSTORMING.md) | [ ]    |
| Design        | [v1-ingest/DESIGN.md](v1-ingest/DESIGN.md)               | [ ]    |
| Plan (index)  | [v1-ingest/plan/INDEX.md](v1-ingest/plan/INDEX.md)       | [ ]    |

---

### V2 — SORT + CLEAN `[ ] Non commencé`

> Tri automatique via FileMate (amélioré) + nettoyage des noms de fichiers

| Document      | Fichier                                                          | Status |
| ------------- | ---------------------------------------------------------------- | ------ |
| Brainstorming | [v2-sort-clean/BRAINSTORMING.md](v2-sort-clean/BRAINSTORMING.md) | [ ]    |
| Design        | [v2-sort-clean/DESIGN.md](v2-sort-clean/DESIGN.md)               | [ ]    |
| Plan (index)  | [v2-sort-clean/plan/INDEX.md](v2-sort-clean/plan/INDEX.md)       | [ ]    |

---

### V3 — SCRAPE `[ ] Non commencé`

> Scraping automatique des métadonnées (TMDB/TVDB), génération NFO, téléchargement artwork

| Document      | Fichier                                                  | Status |
| ------------- | -------------------------------------------------------- | ------ |
| Brainstorming | [v3-scrape/BRAINSTORMING.md](v3-scrape/BRAINSTORMING.md) | [ ]    |
| Design        | [v3-scrape/DESIGN.md](v3-scrape/DESIGN.md)               | [ ]    |
| Plan (index)  | [v3-scrape/plan/INDEX.md](v3-scrape/plan/INDEX.md)       | [ ]    |

---

### V4 — DISPATCH `[ ] Non commencé`

> Déplacement intelligent des médias vers Disk1-4 (merge séries, replace films, free space)

| Document      | Fichier                                                      | Status |
| ------------- | ------------------------------------------------------------ | ------ |
| Brainstorming | [v4-dispatch/BRAINSTORMING.md](v4-dispatch/BRAINSTORMING.md) | [ ]    |
| Design        | [v4-dispatch/DESIGN.md](v4-dispatch/DESIGN.md)               | [ ]    |
| Plan (index)  | [v4-dispatch/plan/INDEX.md](v4-dispatch/plan/INDEX.md)       | [ ]    |

---

### V5 — LOG + NOTIFY `[ ] Non commencé`

> Logging structuré + notifications Telegram

| Document      | Fichier                                                          | Status |
| ------------- | ---------------------------------------------------------------- | ------ |
| Brainstorming | [v5-log-notify/BRAINSTORMING.md](v5-log-notify/BRAINSTORMING.md) | [ ]    |
| Design        | [v5-log-notify/DESIGN.md](v5-log-notify/DESIGN.md)               | [ ]    |
| Plan (index)  | [v5-log-notify/plan/INDEX.md](v5-log-notify/plan/INDEX.md)       | [ ]    |

---

## Ressources existantes

| Outil                 | Emplacement                   | Rôle dans le pipeline                   |
| --------------------- | ----------------------------- | --------------------------------------- |
| FileMate              | `~/dev/FileMate/`             | V2 — Tri par type, nettoyage noms       |
| YoutubeTrailerScraper | `/opt/YoutubeTrailerScraper/` | V3 — Patterns TMDB API réutilisables    |
| BashMate/MediaMate    | `~/BashMate/MediaMate/`       | V4 — Index/recherche media (à évaluer)  |
| Scripts plex          | `099-SCRIPTS/plex/`           | V4/V5 — cleanFileSystem, trailerScraper |

## Décisions techniques

| Sujet         | Décision                              | Raison                                                |
| ------------- | ------------------------------------- | ----------------------------------------------------- |
| Déclenchement | Cron 1x/jour à 3h + commande manuelle | Robustesse, pas de risque fichier en cours d'écriture |
| FileMate      | Intégrer et améliorer (pas remplacer) | Code existant solide, architecture propre             |
| Metadata      | TMDB API (clé existante)              | Gratuit, multi-langue, artwork inclus                 |
| Notifications | Telegram bot                          | Choix utilisateur                                     |
| Architecture  | Modulaire (1 fichier par concern)     | Testable indépendamment, maintenable                  |

## Conventions

- **Commits** : `vX.Y.Z: Description` (X=version, Y=phase, Z=sous-phase)
- **Langue** : Docs en français, code/comments en anglais
- **Tests** : Chaque module critique a ses tests
- **Dry-run** : Chaque opération destructive supporte `--dry-run`
