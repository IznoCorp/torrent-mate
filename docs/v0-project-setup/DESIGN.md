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
│   ├── logger.py                 # Module logging JSON structuré (V6)
│   ├── lock.py                   # Lock file PID (V1, utilisé par toutes les commandes)
│   ├── notifier.py               # Module Telegram (V6, stub en V0)
│   ├── naming_patterns.py        # Patterns de nommage MediaElch (partagé sorter/scraper/verify)
│   ├── genre_mapper.py           # Mapping genres API → catégories dispatch (partagé verify/dispatch)
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
│   ├── verify/                   # V4
│   │   ├── __init__.py
│   │   ├── checker.py
│   │   ├── fixer.py
│   │   └── verifier.py
│   └── dispatch/                 # V5
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
│   ├── verify/
│   ├── dispatch/
│   └── e2e/
└── logs/                         # Logs JSON (non gitté)
```

### Dépendances

```toml
[project]
dependencies = [
    "typer>=0.12.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0.0",
    "requests>=2.31.0",
    "qbittorrent-api>=2025.1.0",
    "guessit>=3.8.0",
    "rapidfuzz>=3.14.0",
    "tenacity>=9.1.0",
    "rich>=14.0.0",
    "structlog>=25.0.0",
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
> - `typer` — V0 CLI (wraps Click en interne, type hints = spec CLI, rich intégré nativement, même CliRunner pour tests)
> - `pymediainfo` supprimé — V3 utilise `ffprobe` (subprocess, déjà installé via `brew install ffmpeg`)
> - `qbittorrent-api` — V1 wrapper qBittorrent (gère auth, CSRF, compat qBit v5.0+)
> - `guessit` — V2 parsing noms de fichiers media (remplace le regex custom prévu)
> - `rapidfuzz` — V3 fuzzy matching titres (MIT, C++ 5-100x plus rapide que thefuzz, media_processor custom pour accents FR)
> - `tenacity` — V3 retry API calls (backoff exponentiel, wait_exception pour Retry-After, composable)
> - `rich` — V0 CLI output (progress bars, tables, theming, auto TTY detection — tiré par Typer automatiquement)
> - `structlog` — V6 logging JSON structuré (remplace JsonFormatter custom, context binding, switch dev/prod auto)
> - `config.py` utilise `pydantic-settings` (réécrit from scratch, pas copié de TorrentMaker qui utilise des dataclasses)

## Interfaces

### CLI (Typer)

> **Choix Typer vs Click** : Typer wraps Click en interne (même CliRunner pour les tests),
> mais les signatures de fonctions Python deviennent la définition CLI. Pas de décorateurs
> `@click.option` — les type hints suffisent. Rich est intégré nativement (help coloré, progress).

```python
import typer
from rich.console import Console

app = typer.Typer(help="PersonalScraper — Media pipeline automation.")

# État global partagé entre commandes
state = {"console": Console(), "verbose": False, "quiet": False}

@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
):
    """PersonalScraper — Media pipeline automation."""
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    state["console"] = Console(quiet=quiet)
    state["verbose"] = verbose
    state["quiet"] = quiet
    configure_logging(verbose=verbose, quiet=quiet)

@app.command()
def ingest(dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving")):
    """Ingest completed torrents from qBittorrent."""

@app.command()
def sort(dry_run: bool = typer.Option(False, "--dry-run")):
    """Sort and clean media files."""

@app.command()
def scrape(
    dry_run: bool = typer.Option(False, "--dry-run"),
    interactive: bool = typer.Option(False, "--interactive", "-i"),
):
    """Scrape metadata and artwork from TMDB/TVDB."""

@app.command()
def verify(dry_run: bool = typer.Option(False, "--dry-run")):
    """Verify and qualify scraped media before dispatch."""

@app.command()
def dispatch(dry_run: bool = typer.Option(False, "--dry-run")):
    """Move media to storage disks."""

@app.command()
def run(dry_run: bool = typer.Option(False, "--dry-run")):
    """Run full pipeline (ingest → sort → scrape → verify → dispatch)."""
```

Entry point : `personalscraper = "personalscraper.cli:app"`

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

    # Monitoring (optional)
    healthcheck_url: str = ""             # V6: healthchecks.io ping URL (filet de sécurité cron)

    # Thresholds
    min_free_space_staging_gb: int = 20   # V1: SSD staging area
    min_free_space_disk_gb: int = 100     # V5: storage disks
```

### Logger (structlog, détail en V6 design)

> Ref : [docs/structlog-reference.md](../structlog-reference.md)

```python
import structlog

def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog + stdlib logging.
    - Console handler: colored dev output via ConsoleRenderer
    - File handler: JSON Lines via TimedRotatingFileHandler (logs/personalscraper.json)
    - verbose=True → DEBUG, quiet=True → WARNING, default → INFO
    """

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger (thin wrapper around structlog.get_logger)."""
    return structlog.get_logger(name)
```

## Flux de données — V0 ne produit pas de données

V0 met en place la structure. Le flux de données commence à V1.

## Ce que V0 implémente concrètement

1. `pyproject.toml` complet (basé sur TorrentMaker)
2. `Makefile` (clean, test, lint, format, install-dev)
3. `.env.example` avec toutes les sections
4. `.gitignore` mis à jour (logs/, .env, **pycache**, etc.)
5. Package `personalscraper/` avec `__init__.py`, `cli.py`, `config.py`
6. Module `logger.py` fonctionnel (structlog, dual output console+JSON, verbose/quiet)
7. Module `notifier.py` en stub (interface définie, implémentation en V6)
8. `models.py` avec les dataclasses partagées (vides, remplies par V1-V4)
9. `tests/conftest.py` avec fixtures de base
10. Ruff config dans `pyproject.toml`
11. Archivage de `099-SCRIPTS/` vers `~/dev/099-SCRIPTS-archive/`
12. Suppression de `099-SCRIPTS/` du repo

## Gestion d'erreurs

V0 ne fait pas de traitement de données. Les erreurs possibles :

- `.env` manquant → message clair, exit 1
- Dépendance manquante → erreur à l'import, message clair
