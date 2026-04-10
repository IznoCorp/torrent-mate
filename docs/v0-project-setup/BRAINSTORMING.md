# V0 — PROJECT SETUP : Brainstorming

> Mise en place du projet Python propre + intégration de FileMate dans le projet

## Contexte

Le projet actuel est un dossier de staging media avec des scripts Python legacy éparpillés dans `099-SCRIPTS/`.
Il faut le transformer en un vrai projet Python packagé, avec une structure moderne inspirée de TorrentMaker.

FileMate (`~/dev/FileMate/`) doit être intégré directement dans ce projet car il n'est utilisé que pour ça.

## Décisions prises

### Nom du package

- **`personalscraper`** (même nom que le repo)
- CLI : `personalscraper ingest`, `personalscraper sort`, `personalscraper scrape`, `personalscraper dispatch`

### Template de référence

- **TorrentMaker** (`~/dev/TorrentMaker/`) comme modèle de structure
- `pyproject.toml` PEP 621 avec setuptools
- Python >= 3.10

> Note : TorrentMaker utilise des dataclasses simples + `load_dotenv()` pour sa config.
> PersonalScraper utilise `pydantic-settings` à la place — le `config.py` est réécrit
> from scratch, pas copié de TorrentMaker. Le template sert pour pyproject.toml, Makefile, ruff.

### Outillage

- **Ruff** pour linting + formatting (remplace Black/isort/flake8)
- **pytest** pour les tests
- **Click** pour le CLI (groups de commandes)
- **pydantic-settings** pour la config (type-safe, auto .env)
- **Makefile** pour l'automatisation (clean, test, lint, format, install-dev)

### Structure du package

- Layout plat (pas de `src/`) : `personalscraper/` à la racine du projet
- CLI avec sous-commandes Click groups
- Entry point dans `pyproject.toml` : `[project.scripts]`

### Intégration FileMate

- Copier le code source de FileMate dans le package (pas de dépendance externe)
- Adapter au nouveau système de config (pydantic-settings au lieu de .env custom)
- Conserver l'architecture strategy pattern
- Améliorer le nettoyage de noms (approche regex dynamique plutôt que fichiers statiques)

### Scripts legacy (`099-SCRIPTS/`)

- **Migrés** : les scripts utiles sont intégrés dans `personalscraper/`
- **Archivés** : une copie est placée dans `~/dev/099-SCRIPTS-archive/` (ou similaire)
- **Supprimés du projet** : plus de `099-SCRIPTS/` dans le repo

### Configuration `.env` unique

- Un seul `.env` pour tout le pipeline, organisé par sections logiques
- Pas organisé par version du pipeline mais par **domaine fonctionnel**

```env
# ── qBittorrent ──────────────────────────────
QBIT_HOST=localhost
QBIT_PORT=8081
QBIT_USERNAME=izno
QBIT_PASSWORD=

# ── Paths ────────────────────────────────────
TORRENT_COMPLETE_DIR=/Volumes/IznoServer SSD/torrents/complete
STAGING_DIR=/Volumes/IznoServer SSD/A TRIER
DISK1_DIR=/Volumes/Disk1/medias
DISK2_DIR=/Volumes/Disk2/medias
DISK3_DIR=/Volumes/Disk3/medias
DISK4_DIR=/Volumes/Disk4/medias

# ── TMDB / TVDB ──────────────────────────────
TMDB_API_KEY=
TVDB_API_KEY=
SCRAPER_LANGUAGE=fr-FR

# ── Telegram ─────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── Thresholds ───────────────────────────────
MIN_FREE_SPACE_GB=20
```

## Ressources

- Template : `/Users/izno/dev/TorrentMaker/`
- FileMate : `/Users/izno/dev/FileMate/`
