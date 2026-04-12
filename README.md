# PersonalScraper

Pipeline d'automatisation media — ingestion, tri, scraping, verification, dispatch.

Les torrents terminés sont automatiquement triés, enrichis de métadonnées (TMDB/TVDB), puis déplacés vers les disques de stockage, prêts pour Kodi/Plex.

## Pipeline

```
qBittorrent  →  A TRIER/ (staging)  →  Disques de stockage (Disk1-4)
               personalscraper run
```

| Etape        | Commande                   | Description                                            |
| ------------ | -------------------------- | ------------------------------------------------------ |
| **Ingest**   | `personalscraper ingest`   | Copie/déplace les torrents terminés depuis qBittorrent |
| **Sort**     | `personalscraper sort`     | Tri dans 001-MOVIES, 002-TVSHOWS, 004-AUDIO, etc.      |
| **Scrape**   | `personalscraper scrape`   | Métadonnées TMDB/TVDB (.nfo, artwork, rename)          |
| **Verify**   | `personalscraper verify`   | Contrôle qualité + catégorisation par genre            |
| **Dispatch** | `personalscraper dispatch` | Déplacement vers le bon disque de stockage             |

Toutes les étapes s'enchaînent avec `personalscraper run` (ou `--dry-run` pour prévisualiser).

## Demarrage rapide

```bash
# Installation
git clone <votre-repo-url> "/Volumes/IznoServer SSD/A TRIER"
cd "/Volumes/IznoServer SSD/A TRIER"
pip install -e ".[dev]"

# Configuration
cp .env.example .env
# Remplir les clés API (TMDB, TVDB) et credentials qBittorrent

# Lancer le pipeline
personalscraper run --dry-run   # Prévisualiser
personalscraper run             # Exécuter
```

Voir [INSTALLATION.md](INSTALLATION.md) pour les instructions détaillées.

## Structure du projet

```
A TRIER/
├── 001-MOVIES/          # Films en attente de traitement
├── 002-TVSHOWS/         # Séries en attente
├── 004-AUDIO/           # Livres audio
├── personalscraper/     # Package Python (ingest, sorter, scraper, verify, dispatch)
├── tests/               # 530 tests unitaires + 3 E2E
├── pyproject.toml       # Dépendances et configuration
├── Makefile             # make test/lint/format/install-dev
└── .env.example         # Template de configuration
```

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

| Document                           | Contenu                                                    |
| ---------------------------------- | ---------------------------------------------------------- |
| [INSTALLATION.md](INSTALLATION.md) | Prérequis, installation, configuration, scheduling         |
| [MANUAL.md](MANUAL.md)             | Manuel d'utilisation complet — commandes, disques, nommage |

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
