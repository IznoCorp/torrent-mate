# Manuel d'utilisation — Zone de tri media

Ce document explique comment utiliser la zone de staging (tri) et les outils disponibles pour organiser les fichiers media.

> Voir aussi : [README.md](README.md) (vue d'ensemble du projet) | [INSTALLATION.md](INSTALLATION.md) (prérequis et installation)

## Vue d'ensemble

```
Torrents terminés  →  staging  →  Disques de stockage
                    personalscraper run     (9 étapes séquentielles)
```

**Pipeline automatisé (PersonalScraper) :**

1. **Ingest** — Les torrents terminés sont copiés/déplacés depuis qBittorrent vers le dossier ingest configurable via `staging_dirs`
2. **Sort** — Les fichiers sont triés dans les sous-dossiers de staging définis dans `staging_dirs`
3. **Clean** — Nettoyage noms (reclean) + dédoublonnage fuzzy (dedup)
4. **Scrape** — Métadonnées récupérées automatiquement via TMDB/TVDB APIs (.nfo, artwork, rename épisodes)
5. **Cleanup** — Suppression des dossiers vides
6. **Enforce** — Application des règles de conformité (nommage, structure)
7. **Verify** — Contrôle qualité avant dispatch (checker + fixer + catégorisation genre)
8. **Trailers** — Téléchargement des bandes-annonces via yt-dlp (optionnel, activé par défaut)
9. **Dispatch** — Déplacement vers le bon disque de stockage (replace films, merge séries)

> **Note :** MediaElch reste disponible comme fallback manuel pour le scraping si l'API ne trouve pas le résultat.

---

## Staging layout

PersonalScraper uses a staging area where downloaded media lands before
being processed and dispatched to permanent storage. From version 0.4.0,
the staging tree lives **outside the repository** at the path configured
in `config/paths.json5` under `paths.staging_dir`.

The subdirectory names are defined by `staging_dirs` in `config/patterns.json5`.
Each entry has an `id` (numeric prefix, 0–999) and a `name` (kebab-case).
The on-disk folder name is `{id:03d}-{name.upper()}`, e.g.:

| id  | name    | folder name |
| --- | ------- | ----------- |
| 1   | movies  | 001-MOVIES  |
| 2   | tvshows | 002-TVSHOWS |
| 97  | temp    | 097-TEMP    |

---

## Commandes PersonalScraper (CLI)

Le pipeline automatisé est accessible via la commande `personalscraper` :

```bash
# Pipeline complet (9 étapes en séquence)
personalscraper run                 # Exécute tout : ingest → sort → clean → scrape → cleanup → enforce → verify → trailers → dispatch
personalscraper run --dry-run       # Prévisualiser sans modifier

# Phase process seule (reclean + dedup + scrape + cleanup)
personalscraper process             # Nettoyer, dédoublonner, scraper, supprimer vides
personalscraper process --dry-run   # Prévisualiser

# Étapes individuelles
personalscraper ingest              # Copier/déplacer les torrents terminés depuis qBittorrent
personalscraper ingest --dry-run    # Prévisualiser
personalscraper sort                # Trier dans 001-MOVIES, 002-TVSHOWS, etc.
personalscraper scrape              # Récupérer métadonnées TMDB/TVDB (.nfo, artwork)
personalscraper enforce             # Appliquer les règles de conformité
personalscraper verify              # Contrôle qualité avant dispatch
personalscraper dispatch            # Déplacer vers disques de stockage
```

Certaines commandes supportent des options de filtrage (`--movies-only`, `--tvshows-only` pour `scrape` et `verify`). Voir `personalscraper <command> --help`.

### Commandes library (maintenance des disques)

```bash
# Indexer (DB-backed)
personalscraper library-index                    # Scan complet (tous les disques)
personalscraper library-index --mode quick       # Mode rapide (Merkle + dir-mtime)
personalscraper library-index --mode full --disk Disk1  # Rebuild complet d'un disque
personalscraper library-index --rebuild          # Quarantaine l'ancienne DB et repart de zéro
personalscraper library-status                   # Résumé du dernier scan
personalscraper library-verify                   # Re-stat tous les fichiers indexés
personalscraper library-search "<query>"         # Recherche flex-attr (ex: nfo_status:invalid)
personalscraper library-show <item_id>           # Détail complet d'un item
personalscraper library-repair                   # Drainer la file de réparation
personalscraper library-reconcile                # Détecter divergences index ↔ filesystem

# Disk-walking
personalscraper library-clean --apply            # Supprimer .actors/, dossiers vides, junk
personalscraper library-validate                 # Valider conformité NFO/artwork/nommage
personalscraper library-analyze                  # Scan ffprobe profond (codec, audio, subs)
personalscraper library-recommend                # Analyse ffprobe + liste de re-téléchargement
personalscraper library-rescrape                 # Re-scraper ciblé (artwork, NFO, épisodes)
personalscraper library-report                   # Statistiques de santé de la bibliothèque

# Utilitaires
personalscraper library-ghost-audit              # Auditer les entrées fantômes NTFS-via-macFUSE
personalscraper library-relink --apply           # Corriger les liens release manquants
```

### Commandes trailers (bandes-annonces)

```bash
personalscraper trailers scan                    # Scanner la bibliothèque pour les BA manquantes
personalscraper trailers download                # Télécharger les BA (yt-dlp)
personalscraper trailers audit                   # Auditer les BA existantes
personalscraper trailers purge                   # Purger les BA selon critères
```

**Prérequis :** fichier `.env` configuré avec les credentials des services). Voir `.env.example`.

**Scheduling :** un agent launchd (`com.personalscraper.pipeline.plist`) peut exécuter le pipeline automatiquement à une heure donnée.

```bash
# Installer et activer (via le script d'installation)
bash scripts/install-launchd.sh

# Désactiver
launchctl unload ~/Library/LaunchAgents/com.personalscraper.pipeline.plist

# Lancer manuellement
launchctl start com.personalscraper.pipeline

# Statut
launchctl list | grep personalscraper
```

---

## Tests

```bash
# Tests unitaires (rapide, ~6s)
make test                               # ou: python -m pytest -v

# Tests E2E torrents (MANUEL — nécessite qBittorrent actif)
python -m pytest -m e2e_torrent -v -s   # 3 tests pipeline (film, série, CLI mixte)

# Tests E2E roundtrip (MANUEL — nécessite clés API TMDB/TVDB)
python -m pytest -m roundtrip -v -s     # 2 tests (matching aller-retour film + série)

# Tests réseau (MANUEL)
python -m pytest -m network -v -s       # Tests trailers (YouTube, yt-dlp)
TRAILER_INTEGRATION_TESTS=1 python -m pytest -m network -v -s

# Autres marqueurs
python -m pytest -m slow -v -s          # Tests lents
python -m pytest -m darwin_only -v -s   # Tests spécifiques macOS
```

**Marqueurs disponibles :** `e2e`, `roundtrip`, `e2e_torrent`, `e2e_idempotence`, `network`, `slow`, `darwin_only`.

**Important :** les tests E2E et réseau ne sont **jamais** lancés par `make test` — ils nécessitent un lancement manuel explicite avec `-m <marqueur>`. Ils téléchargent de vrais torrents depuis les fichiers `.torrent` dans `assets/torrents/`, appellent les APIs TMDB/TVDB, et nettoient tout à la fin. Le dispatch tourne toujours en dry-run (les disques de stockage ne sont jamais modifiés).

---

## Commandes shell

### Espace disque

```bash
df -h /Volumes/Disk{1,2,3,4}
```

---

## Structure des dossiers

### Zone de tri

```
<repo>/
├── personalscraper/     Package Python (CLI)
│   ├── ingest/          qBittorrent → dossier ingest (ex: 097-TEMP/)
│   ├── sorter/          guessit + strategies → dossiers catégorie
│   ├── process/         reclean, dedup, cleanup
│   ├── scraper/         TMDB/TVDB matching, NFO, artwork
│   ├── enforce/         Règles de conformité (nommage, structure)
│   ├── verify/          contrôle qualité renforcé
│   ├── dispatch/        rsync vers disques configurés
│   ├── trailers/        Téléchargement bandes-annonces (yt-dlp)
│   ├── indexer/         Index SQLite des disques (scan, query, drift)
│   ├── conf/            Modèles Pydantic + loader JSON5
│   ├── commands/        Groupes de commandes Typer
│   ├── pipeline.py      Orchestrateur 9 étapes séquentiel
│   └── pipeline_steps.py Registre des étapes du pipeline
├── tests/               Tests unitaires + E2E
└── assets/torrents/     Fichiers .torrent pour tests E2E
```

Les dossiers de staging se trouvent dans le dossier défini par `paths.staging_dir` dans `config/paths.json5`.

### Nommage des films

```
Titre du Film (Année)/
  Titre du Film.mkv
  Titre du Film.nfo
  Titre du Film-poster.jpg
  Titre du Film-fanart.jpg
  Titre du Film-banner.jpg
  Titre du Film-clearlogo.png
  Titre du Film-clearart.png
  Titre du Film-discart.png
  Titre du Film-landscape.jpg
  .actors/
```

### Nommage des séries

```
Nom de la Série (Année)/
  tvshow.nfo
  poster.jpg
  fanart.jpg
  banner.jpg
  clearlogo.png
  season01-poster.jpg
  .actors/
  Saison 01/
    S01E01 - Titre de l'Episode.mkv
    S01E01 - Titre de l'Episode.nfo
    S01E01 - Titre de l'Episode-thumb.jpg
  Saison 02/
    ...
```

Voir `config/scraper.json5`

---

## Scraping des métadonnées

### Automatique (recommandé) — `personalscraper scrape`

Le scraping est automatisé via les APIs TMDB et TVDB :

```bash
personalscraper scrape              # Scrape tous les médias (films + séries)
```

Produit : fichiers `.nfo` (XML Kodi), posters, fanarts, banners, et renomme les épisodes au format `S01E01 - Titre.mkv`.

### Fallback manuel — MediaElch

Si l'API ne trouve pas un résultat, MediaElch (application de bureau GUI) peut être utilisé manuellement :

1. Ouvrir MediaElch, charger le dossier de staging des films ou des séries (ex: `001-MOVIES/` ou `002-TVSHOWS/`)
2. Lancer la recherche (TMDb/TheTVDB)
3. Télécharger poster, fanart, banner, etc.
4. Sauvegarder → génère le fichier `.nfo`

**Un media est prêt à déplacer quand il a au minimum :** un fichier vidéo + un fichier `.nfo`.

---

| Unpack.py.bak | Variante d'unpack seul | Archivé |
| TVDBNameToNum.py.bak | Matcher les noms d'épisodes via TheTVDB | Archivé → remplacé par la version actuelle |
| EpisodesTVDBNamer.py.bak | Renommage d'épisodes TVDB | Archivé → remplacé par la version actuelle |
| videoCutter.py.bak | Couper des vidéos | Archivé |
| videoMerger.py.bak | Fusionner des vidéos | Archivé |
| SensCritiqueScrapper.py.bak | Scraping SensCritique | Archivé |

---

## Notes importantes

- **Espaces dans les chemins** — Toujours mettre les chemins entre guillemets dans le terminal : `"/path/to/staging/"`
