# TorrentMate

![CI](https://github.com/IznoCorp/torrent-mate/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/IznoCorp/torrent-mate/badge.svg)](https://codecov.io/gh/IznoCorp/torrent-mate)

Pipeline d'automatisation media — ingestion, tri, scraping, vérification, dispatch — piloté en ligne de commande ou depuis **TorrentMate**, une web app installable (PWA).

Les torrents terminés sont automatiquement triés, enrichis de métadonnées (TMDB/TVDB), vérifiés, puis déplacés vers les disques de stockage, prêts pour Kodi/Plex.

> **TorrentMate** est le nom du projet ; la commande CLI est **`torrentmate`** (l'ancienne commande **`personalscraper`** reste un alias fonctionnel). Le package Python et les apps PM2 conservent encore l'identifiant `personalscraper` en attendant le rename complet du code ([issue #223](https://github.com/IznoCorp/torrent-mate/issues/223)).

## Pipeline

```
qBittorrent  →  staging/  →  Disques de stockage (configurés)
               torrentmate run
```

Ordre d'exécution : ingest → sort → clean → scrape → cleanup → enforce → verify → trailers → dispatch.

| Étape        | Commande               | Description                                                                             |
| ------------ | ---------------------- | --------------------------------------------------------------------------------------- |
| **Ingest**   | `torrentmate ingest`   | Copie les torrents terminés depuis qBittorrent vers le staging                          |
| **Sort**     | `torrentmate sort`     | Tri dans les dossiers de catégories (`001-MOVIES/`, `002-TVSHOWS/`, …)                  |
| **Clean**    | `torrentmate clean`    | Nettoyage des noms + dédoublonnage fuzzy (sous-étape de `process`)                      |
| **Scrape**   | `torrentmate scrape`   | Métadonnées TMDB/TVDB (`.nfo`, artwork, rename des épisodes)                            |
| **Cleanup**  | `torrentmate cleanup`  | Suppression des dossiers vides (sous-étape de `process`)                                |
| **Enforce**  | `torrentmate enforce`  | Sanitize des noms, validation de structure, suppression des `.DS_Store`                 |
| **Verify**   | `torrentmate verify`   | Contrôle qualité avant dispatch (NFO valide, poster/landscape, nommage) — lecture seule |
| **Trailers** | (intégré au pipeline)  | Téléchargement des bandes-annonces via TMDB → YouTube → yt-dlp                          |
| **Dispatch** | `torrentmate dispatch` | Déplacement vers le bon disque de stockage (replace films / merge séries)               |

Toutes les étapes s'enchaînent avec `torrentmate run` (ajouter `--dry-run` pour prévisualiser sans écriture). Chaque étape individuelle accepte également `--dry-run`.

**Règles de dispatch** (voir [MANUAL.md](MANUAL.md)) :

- **Films → REPLACE** : un dossier de même nom déjà présent sur un disque est remplacé par la version du staging.
- **Séries → MERGE** : les nouveaux épisodes sont fusionnés dans le dossier existant (les épisodes déjà présents sont remplacés).
- **Nouveau media** (aucun dossier existant) → disque **éligible avec le plus d'espace libre**.

## TorrentMate — interface web (PWA)

**TorrentMate** est une **Progressive Web App installable** (mobile-first : Android, iOS/iPadOS et desktop) pour piloter et observer le pipeline depuis un navigateur ou un icône sur l'écran d'accueil.

- **En ligne** :
  - Prod → [https://tm.iznogoudatall.xyz](https://tm.iznogoudatall.xyz)
  - Staging → [https://tm-staging.iznogoudatall.xyz](https://tm-staging.iznogoudatall.xyz) (logo cyan + bandeau, même nom d'app)
- **Backend** : daemon FastAPI (`torrentmate web`) servant le SPA React, une API REST (`/api/*`) et un flux d'évènements temps réel WebSocket (`/ws/events`).
- **Flux temps réel** : l'`EventBus` du pipeline est relayé au process web via **Redis Streams** (fan-out vers tous les clients WebSocket) — fail-soft si Redis est indisponible.
- **Auth** : utilisateur unique `izno`, session par cookie JWT (`tm_session`).
- **Déploiement « push-to-deploy »** : un push sur `main` redéploie la prod, un push sur `staging` redéploie le staging (poller PM2 `torrentmate-autodeploy`), derrière un reverse-proxy **Caddy** (TLS).

Détails complets : [docs/reference/web-ui.md](docs/reference/web-ui.md).

## Démarrage rapide

### Pipeline (CLI)

```bash
# 1. Cloner et se placer dans le dépôt
git clone <votre-repo-url> torrent-mate
cd torrent-mate

# 2. Python 3.12+ (géré via pyenv) + installation editable avec les extras dev
pyenv local 3.12.4                     # ou toute version 3.12+
pip install -e ".[dev]"

# 3. Hooks git (une seule fois par clone — configure core.hooksPath)
./hooks/install.sh

# 4. Générer config/ depuis le template
torrentmate init-config

# 5. Renseigner les secrets dans .env (clés API TMDB/TVDB, credentials qBittorrent,
#    passkeys trackers, TELEGRAM_*, HEALTHCHECK_URL, WEB_JWT_SECRET, …)
cp .env.example .env
$EDITOR .env

# 6. Lancer le pipeline
torrentmate run --dry-run          # Prévisualiser
torrentmate run                    # Exécuter
```

Smoke test : `python -c "import personalscraper"` et `torrentmate --help`.
Gate local complet : `make check` (lint + tests + garde-fous).

### Interface web TorrentMate

Prérequis : **Redis** en fonctionnement (`brew install redis && brew services start redis`) et **Node.js 22** pour builder le SPA.

```bash
# 1. Secrets web (une seule fois) — génère le hash scrypt + le secret JWT
torrentmate web set-password       # écrit WEB_PASSWORD_HASH / WEB_JWT_SECRET

# 2. Builder le SPA React (npm run build → frontend/dist/, sortie Vite par défaut)
cd frontend && npm ci && npm run build && cd ..
# Puis recopier le build vers le dossier servi (ou lancer ./scripts/deploy.sh qui le fait) :
rsync -a --delete frontend/dist/ personalscraper/web/static/

# 3. Lancer le daemon web (par défaut 127.0.0.1:8710)
torrentmate web                    # --host / --port pour surcharger
```

Le daemon refuse de démarrer si le SPA n'est pas buildé (`static/index.html` absent) tant que `web.dev_mode` est `false`.
Configuration : `config/web.json5`. Développement front avec HMR : `cd frontend && npm run dev`.

Voir [INSTALLATION.md](INSTALLATION.md) pour les instructions détaillées (prérequis, scheduling PM2, déploiement prod/staging).

## Fonctionnalités

- **Pipeline de triage media** — ingest → sort → scrape → verify → dispatch, idempotent et re-jouable, avec `--dry-run` sur chaque étape.
- **Scraping multi-provider** — TMDB/TVDB (+ OMDb/Trakt pour infos et ratings), écriture de NFO Kodi/MediaElch et de l'artwork (poster, fanart, banner, landscape…).
- **Stockage multi-disques NTFS/macFUSE** — 4 disques, routage par catégorie + espace libre, transferts rsync crash-safe.
- **Indexeur de bibliothèque** — base SQLite (`library.db`), scans full/quick/incrémental/enrich, réparation et réconciliation index ↔ filesystem (commandes `library-*`).
- **Acquisition** — suivi de séries (`follow`), détection d'épisodes diffusés (`follow detect`), recherche + grab sur trackers (`grab`), cross-seeding.
- **Watcher** — daemon PM2 qui déclenche le pipeline à chaque nouveau torrent terminé.
- **Bandes-annonces** — découverte TMDB → YouTube, téléchargement yt-dlp, placement conforme Plex.
- **TorrentMate (PWA)** — pilotage et observation temps réel du pipeline depuis le web, installable sur mobile et desktop.
- **Health-check + notifications** — monitoring local horaire (PM2) et alertes Telegram.

## Structure du projet

```
torrent-mate/          # Racine du dépôt git
├── personalscraper/      # Package Python (ingest, sorter, process, scraper, enforce,
│   │                     #   verify, dispatch, indexer, trailers, acquire, commands…)
│   └── web/              # App FastAPI TorrentMate (REST /api/* + WebSocket /ws/events)
├── frontend/             # TorrentMateUI — SPA React/Vite/TypeScript (PWA)
├── tests/                # Tests unitaires + intégration + E2E
├── docs/                 # Documentation (reference/, features/, archive/)
├── scripts/              # Scripts utilitaires (deploy.sh, check_logging.py, …)
├── config.example/       # Template de configuration (JSON5, split en overlays)
├── config/               # Configuration utilisateur — chemins, disques, catégories (gitignored)
├── .env / .env.example   # Secrets (clés API, credentials, WEB_JWT_SECRET…) (gitignored)
├── ecosystem.config.js   # Configuration PM2 (watcher, web, autodeploy, crons)
└── Makefile              # make test / lint / check / format / install-dev / openapi
```

Les dossiers de staging vivent dans le répertoire défini par `paths.staging_dir` (`config/paths.json5`), en dehors du dépôt par défaut. La disposition des sous-dossiers (`001-MOVIES/`, `002-TVSHOWS/`, …) est configurée dans la section `staging_dirs` de `config/patterns.json5`.

## Commandes utiles

```bash
# Pipeline complet
torrentmate run                     # Tout exécuter
torrentmate run --dry-run           # Prévisualiser

# Étapes individuelles
torrentmate ingest --dry-run        # Prévisualiser l'ingestion
torrentmate sort                    # Trier les fichiers
torrentmate scrape                  # Scraper les métadonnées
torrentmate verify                  # Contrôle qualité avant dispatch
torrentmate dispatch                # Déplacer vers le stockage

# Library (indexeur media)
torrentmate library-index           # Scanner les disques (--mode full|quick|incremental|enrich)
torrentmate library-search "QUERY"  # Rechercher dans l'index
torrentmate library-report          # Stats + rapport de santé

# Acquisition
torrentmate follow add --tvdb 121361 # Suivre une série
torrentmate follow detect            # Enfiler les épisodes diffusés
torrentmate grab --dry-run           # Chercher + prévisualiser les grabs

# Interface web + supervision
torrentmate web                      # Daemon TorrentMate (SPA + API + WebSocket)
torrentmate web set-password         # Générer le hash scrypt + secret JWT
torrentmate health-check             # Monitoring local (liveness + logs) → Telegram
torrentmate info                     # Version, chemins config, état des disques

# Configuration
torrentmate init-config              # Créer le dossier config/

# Développement
make test                                # Lancer la suite de tests
make lint                                # Ruff + mypy + check_logging
make check                               # lint + tests + garde-fous (gate)
make format                              # Formater le code
make openapi                             # Régénérer le contrat OpenAPI + types TS du front
```

La surface CLI complète est documentée dans [docs/reference/commands.md](docs/reference/commands.md).

## Documentation

| Document                             | Contenu                                                    |
| ------------------------------------ | ---------------------------------------------------------- |
| [INSTALLATION.md](INSTALLATION.md)   | Prérequis, installation, scheduling PM2, déploiement web   |
| [CONFIGURATION.md](CONFIGURATION.md) | Guide `config/` (JSON5) + `.env` — sections, clés, secrets |
| [MANUAL.md](MANUAL.md)               | Manuel d'utilisation — commandes, disques, nommage         |
| [docs/reference/](docs/reference/)   | Références techniques approfondies (voir ci-dessous)       |

Références détaillées (dans `docs/reference/`) : [`commands.md`](docs/reference/commands.md) (CLI),
[`storage.md`](docs/reference/storage.md) (disques, rsync, règles de move), [`naming.md`](docs/reference/naming.md) (nommage films/séries),
[`scraping.md`](docs/reference/scraping.md) (TMDB/TVDB, NFO), [`indexer.md`](docs/reference/indexer.md) (base de bibliothèque),
[`web-ui.md`](docs/reference/web-ui.md) (TorrentMate), [`event-bus.md`](docs/reference/event-bus.md), [`architecture.md`](docs/reference/architecture.md) (carte des modules).

## Dépendances système

```bash
brew install ffmpeg        # ffprobe — extraction des streams + transcode des trailers
brew install media-info    # backend pymediainfo (extraction streams pour l'indexeur)
brew install redis         # relais d'évènements (Redis Streams) pour l'interface web
brew install unar          # extraction des archives RAR avant scrape
```

Les disques de stockage sont montés en **NTFS via macFUSE + ntfs-3g** (Homebrew).
**PM2** gère les daemons et les tâches planifiées (watcher, web, autodeploy, crons) ; **Caddy** sert de reverse-proxy TLS pour l'interface web.

## Technologies

- **Python 3.12+** avec [Typer](https://typer.tiangolo.com/) (CLI) et [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) (config)
- **FastAPI + Uvicorn** — API REST et daemon web TorrentMate
- **React 19 + Vite + TypeScript** (strict) — SPA/PWA TorrentMateUI (shadcn/ui, TanStack, vite-plugin-pwa)
- **Redis** — Redis Streams pour le relais d'évènements cross-process → WebSocket
- **guessit** — Parsing intelligent des noms de fichiers media
- **TMDB / TVDB APIs** — Métadonnées, artwork, noms d'épisodes (OMDb/Trakt en complément)
- **rapidfuzz** — Matching flou pour les titres
- **rsync** — Transferts cross-filesystem (resume, checksum, crash-safe)
- **structlog** — Logging JSON structuré (console + fichier)
- **rich** — Affichage CLI (progress bars, tables, couleurs)
- **pymediainfo** — Extraction des streams vidéo/audio (requiert `brew install media-info`)
- **yt-dlp** — Téléchargement des bandes-annonces YouTube
- **qbittorrent-api** / **transmission-rpc** — Interface avec les clients torrent
- **tenacity** — Retry avec backoff pour les appels API
- **json5** — Fichiers de configuration avec commentaires
- **xxhash** — Hashing rapide pour la détection de doublons

## Licence

MIT
