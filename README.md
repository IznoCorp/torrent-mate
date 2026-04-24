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

| Etape        | Commande                   | Description                                                    |
| ------------ | -------------------------- | -------------------------------------------------------------- |
| **Ingest**   | `personalscraper ingest`   | Copie/déplace les torrents terminés depuis qBittorrent         |
| **Sort**     | `personalscraper sort`     | Tri dans les dossiers de staging (définis dans `staging_dirs`) |
| **Scrape**   | `personalscraper scrape`   | Métadonnées TMDB/TVDB (.nfo, artwork, rename)                  |
| **Verify**   | `personalscraper verify`   | Contrôle qualité + catégorisation par genre                    |
| **Dispatch** | `personalscraper dispatch` | Déplacement vers le bon disque de stockage                     |

Toutes les étapes s'enchaînent avec `personalscraper run` (ou `--dry-run` pour prévisualiser).

## Demarrage rapide

```bash
# Installation
git clone <votre-repo-url> "/path/to/staging"
cd "/path/to/staging"
pip install -e ".[dev]"

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
staging/
├── personalscraper/     # Package Python (ingest, sorter, scraper, verify, dispatch)
├── tests/               # Tests unitaires + E2E
├── docs/                # Documentation
├── config.json5         # Configuration principale — chemins, disques, catégories, règles (gitignored)
├── config.example.json5 # Exemple de config.json5
├── .env                 # Secrets API uniquement — TMDB/TVDB keys, qBit credentials (gitignored)
├── .env.example         # Exemple de .env
└── Makefile             # make test/lint/format/install-dev
```

Les dossiers de staging (`001-MOVIES/`, `002-TVSHOWS/`, etc.) se trouvent dans le dossier
défini par `paths.staging_dir` dans `config.json5` — en dehors du dépôt par défaut.
Ils ne sont pas suivis par git.

## Commandes utiles

```bash
# Pipeline complet
personalscraper run                     # Tout exécuter
personalscraper run --dry-run           # Prévisualiser

# Etapes individuelles
personalscraper ingest --dry-run        # Prévisualiser l'ingestion
personalscraper sort                    # Trier les fichiers
personalscraper scrape                  # Scraper les métadonnées
personalscraper verify                  # Vérifier la qualité
personalscraper dispatch                # Déplacer vers stockage

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

## Technologies

- **Python 3.10+** avec [Typer](https://typer.tiangolo.com/) (CLI) et [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) (config)
- **guessit** — Parsing intelligent des noms de fichiers media
- **TMDB / TVDB APIs** — Métadonnées, artwork, noms d'épisodes
- **rapidfuzz** — Matching flou pour les titres (5-100x plus rapide que thefuzz)
- **rsync** — Transferts cross-filesystem (resume, checksum, crash-safe)
- **structlog** — Logging JSON structuré (console + fichier)
- **rich** — Affichage CLI (progress bars, tables, couleurs)

## Licence

MIT
