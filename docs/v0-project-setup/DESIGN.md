# V0 — PROJECT SETUP : Design

> Mise en place du projet Python `personalscraper` + intégration FileMate + module logging

## Architecture

### Structure du package

```
personalscraper/
├── pyproject.toml
├── Makefile
├── .env                          # Config (non gitté)
├── .env.example                  # Template synchronisé
├── .gitignore
├── personalscraper/
│   ├── __init__.py               # __version__, public API
│   ├── cli.py                    # Click CLI entry point (groups)
│   ├── config.py                 # Pydantic Settings (single .env)
│   ├── models.py                 # Dataclasses partagées (SortResult, MediaInfo, etc.)
│   ├── logger.py                 # Module logging JSON structuré (V5)
│   ├── notifier.py               # Module Telegram (V5, stub en V0)
│   ├── naming_patterns.py        # Patterns de nommage MediaElch (partagé sorter/scraper)
│   ├── ingest/                   # V1
│   │   ├── __init__.py
│   │   ├── qbit_client.py
│   │   ├── tracker.py
│   │   └── ingest.py
│   ├── sorter/                   # V2 (FileMate intégré)
│   │   ├── __init__.py
│   │   ├── cleaner.py            # Regex-based name cleaner
│   │   ├── file_type.py          # File type detection
│   │   ├── strategies.py         # Movie/TVShow/Default strategies
│   │   └── sorter.py             # Main sorting orchestrator
│   ├── scraper/                  # V3
│   │   ├── __init__.py
│   │   ├── tmdb_client.py
│   │   ├── tvdb_client.py
│   │   ├── nfo_generator.py
│   │   ├── artwork.py
│   │   ├── mediainfo.py
│   │   └── scraper.py
│   └── dispatch/                 # V4
│       ├── __init__.py
│       ├── media_index.py
│       ├── disk_scanner.py
│       └── dispatcher.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_logger.py
│   ├── ingest/
│   ├── sorter/
│   ├── scraper/
│   └── dispatch/
└── logs/                         # Logs JSON (non gitté)
```

### Dépendances

```toml
[project]
dependencies = [
    "click>=8.1.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0.0",
    "requests>=2.31.0",
    "qbittorrent-api>=2025.1.0",
    "guessit>=3.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
]
```

> **Notes sur les dépendances** :
>
> - `pymediainfo` supprimé — V3 utilise `ffprobe` (subprocess, déjà installé via `brew install ffmpeg`)
> - `qbittorrent-api` — V1 wrapper qBittorrent (gère auth, CSRF, compat qBit v5.0+)
> - `guessit` — V2 parsing noms de fichiers media (remplace le regex custom prévu)
> - `config.py` utilise `pydantic-settings` (réécrit from scratch, pas copié de TorrentMaker qui utilise des dataclasses)

## Interfaces

### CLI (Click groups)

```python
@click.group()
@click.version_option()
@click.option("--verbose", "-v", is_flag=True)
@click.option("--quiet", "-q", is_flag=True)
def cli(verbose, quiet):
    """PersonalScraper — Media pipeline automation."""

@cli.command()
@click.option("--dry-run", is_flag=True)
def ingest(dry_run):
    """Ingest completed torrents from qBittorrent."""

@cli.command()
@click.option("--dry-run", is_flag=True)
def sort(dry_run):
    """Sort and clean media files."""

@cli.command()
@click.option("--dry-run", is_flag=True)
@click.option("--interactive", "-i", is_flag=True)
def scrape(dry_run, interactive):
    """Scrape metadata and artwork from TMDB/TVDB."""

@cli.command()
@click.option("--dry-run", is_flag=True)
def dispatch(dry_run):
    """Move media to storage disks."""

@cli.command()
@click.option("--dry-run", is_flag=True)
def run(dry_run):
    """Run full pipeline (ingest → sort → scrape → dispatch)."""
```

Entry point : `personalscraper = "personalscraper.cli:cli"`

### Config (pydantic-settings)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # qBittorrent
    qbit_host: str = "localhost"
    qbit_port: int = 8081
    qbit_username: str = "izno"
    qbit_password: str = ""

    # Paths
    torrent_complete_dir: Path
    staging_dir: Path
    disk1_dir: Path
    disk2_dir: Path
    disk3_dir: Path
    disk4_dir: Path

    # TMDB
    tmdb_api_key: str = ""

    # TVDB
    tvdb_api_key: str = ""

    # Scraper
    scraper_language: str = "fr-FR"
    scraper_fallback_language: str = "en-US"

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Thresholds
    min_free_space_staging_gb: int = 20   # V1: SSD staging area
    min_free_space_disk_gb: int = 100     # V4: storage disks
```

### Logger (JSON structuré, détail en V5 design)

```python
def get_logger(name: str, verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """Configure and return a JSON structured logger."""
```

## Flux de données — V0 ne produit pas de données

V0 met en place la structure. Le flux de données commence à V1.

## Ce que V0 implémente concrètement

1. `pyproject.toml` complet (basé sur TorrentMaker)
2. `Makefile` (clean, test, lint, format, install-dev)
3. `.env.example` avec toutes les sections
4. `.gitignore` mis à jour (logs/, .env, **pycache**, etc.)
5. Package `personalscraper/` avec `__init__.py`, `cli.py`, `config.py`
6. Module `logger.py` fonctionnel (JSON, rotation, verbose/quiet)
7. Module `notifier.py` en stub (interface définie, implémentation en V5)
8. `models.py` avec les dataclasses partagées (vides, remplies par V1-V4)
9. `tests/conftest.py` avec fixtures de base
10. Ruff config dans `pyproject.toml`
11. Archivage de `099-SCRIPTS/` vers `~/dev/099-SCRIPTS-archive/`
12. Suppression de `099-SCRIPTS/` du repo

## Gestion d'erreurs

V0 ne fait pas de traitement de données. Les erreurs possibles :

- `.env` manquant → message clair, exit 1
- Dépendance manquante → erreur à l'import, message clair
