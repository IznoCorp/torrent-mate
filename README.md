# PersonalScraper

![CI](https://github.com/LounisBou/personal-scraper/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/LounisBou/personal-scraper/badge.svg)](https://codecov.io/gh/LounisBou/personal-scraper)

Pipeline d'automatisation media — ingestion, tri, scraping, verification, dispatch.

Les torrents terminés sont automatiquement triés, enrichis de métadonnées (TMDB/TVDB), puis déplacés vers les disques de stockage, prêts pour Kodi/Plex.

## Pipeline

```
qBittorrent  →  staging/  →  Disques de stockage (configurés)
               personalscraper run
```

| Etape        | Commande                   | Description                                                              |
| ------------ | -------------------------- | ------------------------------------------------------------------------ |
| **Ingest**   | `personalscraper ingest`   | Copie/déplace les torrents terminés depuis qBittorrent                   |
| **Sort**     | `personalscraper sort`     | Tri dans les dossiers de staging (définis dans `staging_dirs`)           |
| **Clean**    | `personalscraper clean`    | Nettoyage noms + dédoublonnage fuzzy (standalone ou intégré au pipeline) |
| **Scrape**   | `personalscraper scrape`   | Métadonnées TMDB/TVDB (.nfo, artwork, rename)                            |
| **Cleanup**  | `personalscraper cleanup`  | Suppression des dossiers vides (standalone ou intégré)                   |
| **Enforce**  | `personalscraper enforce`  | Application des règles de conformité (nommage, structure)                |
| **Verify**   | `personalscraper verify`   | Contrôle qualité + catégorisation par genre                              |
| **Trailers** | (intégré au pipeline)      | Téléchargement bandes-annonces via yt-dlp                                |
| **Dispatch** | `personalscraper dispatch` | Déplacement vers le bon disque de stockage                               |

Toutes les étapes s'enchaînent avec `personalscraper run` (ou `--dry-run` pour prévisualiser).

## Demarrage rapide

```bash
# Installation
git clone <votre-repo-url> "/path/to/staging"
cd "/path/to/staging"
pip install -e ".[dev]"
./hooks/install.sh                                  # Une seule fois par clone — active core.hooksPath et le hook pre-commit (régénère tests/feature_map/*.json)

# Configuration
cp .env.example .env                                # Secrets API uniquement (TMDB_API_KEY, TVDB_API_KEY, ...)
personalscraper init-config                         # Génère config.json5 depuis le template (chemins, disques, catégories, règles)

# Lancer le pipeline
personalscraper run --dry-run   # Prévisualiser
personalscraper run             # Exécuter
```

Voir [INSTALLATION.md](INSTALLATION.md) pour les instructions détaillées.

## Structure du projet

```
personal-scraper/        # Racine du dépôt git
├── personalscraper/     # Package Python (ingest, sorter, process, scraper, enforce, verify, dispatch, indexer, trailers, commands)
├── tests/               # Tests unitaires + E2E
├── docs/                # Documentation
├── scripts/             # Scripts utilitaires (check-logging.py, etc.)
├── config.example/      # Template de configuration (v2 split)
├── config/              # Configuration utilisateur — chemins, disques, catégories, règles (gitignored)
├── .env                 # Secrets API uniquement — TMDB/TVDB keys, qBit credentials (gitignored)
├── .env.example         # Template .env
├── assets/              # Fichiers .torrent pour tests E2E
├── ecosystem.config.js  # Configuration PM2 (watcher daemon + crons)
└── Makefile             # make test/lint/format/install-dev
```

Les dossiers de staging se trouvent dans le dossier défini par `paths.staging_dir` dans `config/paths.json5` en dehors du dépôt par défaut.

## Commandes utiles

```bash
# Pipeline complet
personalscraper run                     # Tout exécuter
personalscraper run --dry-run           # Prévisualiser

# Etapes individuelles
personalscraper ingest --dry-run        # Prévisualiser l'ingestion
personalscraper sort                    # Trier les fichiers
personalscraper clean --dry-run         # Nettoyage noms + dédoublonnage fuzzy
personalscraper scrape                  # Scraper les métadonnées
personalscraper cleanup --dry-run       # Supprimer les dossiers vides
personalscraper enforce                 # Appliquer les règles de conformité
personalscraper verify                  # Vérifier la qualité
personalscraper dispatch                # Déplacer vers stockage

# Library (indexeur media)
personalscraper library-index           # Scanner les disques
personalscraper library-search          # Rechercher dans l'index

# Configuration
personalscraper init-config             # Créer le dossier config/

# Développement
make test                               # Lancer les tests
make lint                               # Vérifier le code
make format                             # Formater le code
```

## Documentation

| Document                             | Contenu                                                   |
| ------------------------------------ | --------------------------------------------------------- |
| [INSTALLATION.md](INSTALLATION.md)   | Prérequis, installation, scheduling                       |
| [CONFIGURATION.md](CONFIGURATION.md) | Guide config.json5 + .env — toutes les sections, clés API |
| [MANUAL.md](MANUAL.md)               | Manuel d'utilisation — commandes, disques, nommage        |

## Dépendances système

```bash
brew install media-info   # pymediainfo backend (stream extraction for the indexer)
```

## Technologies

- **Python 3.12+** avec [Typer](https://typer.tiangolo.com/) (CLI) et [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) (config)
- **guessit** — Parsing intelligent des noms de fichiers media
- **TMDB / TVDB APIs** — Métadonnées, artwork, noms d'épisodes
- **rapidfuzz** — Matching flou pour les titres (5-100x plus rapide que thefuzz)
- **rsync** — Transferts cross-filesystem (resume, checksum, crash-safe)
- **structlog** — Logging JSON structuré (console + fichier)
- **rich** — Affichage CLI (progress bars, tables, couleurs)
- **pymediainfo** — Extraction des streams vidéo/audio (requiert `brew install media-info`)
- **yt-dlp** — Téléchargement des bandes-annonces YouTube
- **qbittorrent-api** — Interface avec le client qBittorrent
- **tenacity** — Retry avec backoff pour les appels API
- **json5** — Fichiers de configuration avec commentaires
- **xxhash** — Hashing rapide pour la détection de doublons

## Licence

MIT
