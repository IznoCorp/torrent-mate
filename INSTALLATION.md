# Installation

Guide d'installation et de configuration de **TorrentMate** — le pipeline de
sync media (moteur `personalscraper`) et son interface web.

> Voir aussi : [README.md](README.md) (vue d'ensemble du projet) | [MANUAL.md](MANUAL.md) (manuel d'utilisation) | [CONFIGURATION.md](CONFIGURATION.md) (variables d'environnement et config JSON5)

## Prérequis

### Système

Tous ces composants sont installés sur l'hôte « IznoServer » (macOS Sonoma 14.5,
Apple Silicon arm64). Chacun couvre un besoin précis du pipeline ou de l'UI :

| Prérequis             | Version / installation                        | Pourquoi c'est nécessaire                                                                                                      |
| --------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Python**            | **3.12+** via pyenv (l'hôte utilise `3.12.4`) | Requis par le package (`requires-python = ">=3.12"`) ; toutes les apps Python PM2 invoquent directement le shim pyenv `3.12.4` |
| **pip**               | fourni avec Python                            | Installation éditable du package et des extras dev                                                                             |
| **Node.js**           | **22**                                        | Build du frontend (React/Vite/TS) et génération des types TS depuis l'OpenAPI (`cd frontend && npm run gen-api`)               |
| **Redis**             | **5.0+**                                      | Relais d'événements inter-process de l'UI web (Redis Streams → WebSocket)                                                      |
| **macFUSE + ntfs-3g** | via Homebrew                                  | Monter et écrire les disques de stockage NTFS sous `/Volumes/`                                                                 |
| **PM2**               | global (npm)                                  | Gestionnaire de process et scheduler de tous les daemons et jobs cron                                                          |
| **Caddy**             | via Homebrew                                  | Reverse-proxy + TLS de l'UI web (prod `tm.iznogoudatall.xyz`, staging `tm-staging.iznogoudatall.xyz`)                          |
| **ffmpeg / ffprobe**  | via Homebrew                                  | Transcode des bandes-annonces + extraction des flux/codecs/langues (ffprobe) pour les NFO                                      |
| **unrar / unar**      | via Homebrew                                  | Extraction des archives RAR avant scrape (phase torrent-write) — backend système requis par la dépendance pip `rarfile`        |
| **rsync**             | inclus avec macOS                             | Déplacement/merge des médias vers le stockage permanent                                                                        |

```bash
# Homebrew — outils système
brew install ffmpeg media-info unrar redis caddy
brew install --cask macfuse
# ntfs-3g (macFUSE) selon votre méthode d'installation habituelle

# PM2 s'installe via npm global (aucune formule Homebrew `pm2`)
npm install -g pm2
```

> `media-info` (MediaInfo) est requis par l'indexeur média via la dépendance
> `pymediainfo` ; `ffprobe` (fourni par FFmpeg) reste utilisé pour l'extraction
> des flux vers les NFO.

### Services externes

- **qBittorrent** (ou **Transmission**) avec l'API/interface activée
- Un compte **TMDB** avec clé API v3 — [inscription](https://www.themoviedb.org/settings/api)
- Un compte **TVDB** avec clé API v4 — [inscription](https://thetvdb.com/dashboard/account/apikeys)
- _(Optionnel)_ Un bot **Telegram** pour les notifications — [créer un bot](https://core.telegram.org/bots#how-do-i-create-a-bot)
- _(Optionnel)_ Une URL **healthchecks.io** pour le heartbeat des jobs planifiés

### Dépendances Python (installées par pip)

Pour référence, `pip install -e ".[dev]"` installe automatiquement, entre autres :
`typer`, `pydantic-settings`, `python-dotenv`, `requests`, `qbittorrent-api`,
`transmission-rpc`, `guessit`, `rapidfuzz`, `tenacity`, `rich`, `structlog`,
`json5`, `xmltodict`, `yt-dlp`, `pymediainfo`, `enzyme`, `xxhash`, `filelock`,
`rarfile`, `fastapi`, `uvicorn[standard]`, `redis`, `PyJWT`.

Les extras `[dev]` ajoutent : `pytest`, `pytest-cov`, `pytest-xdist`, `ruff`,
`mypy`, `types-requests`, `pip-audit`, `pip-licenses`, `sqlite-utils`,
`pyfakefs`, `hypothesis`, `responses`, `httpx`, `fakeredis`.

## Installation

```bash
# 1. Cloner le dépôt
git clone <repo-url> torrent-mate
cd torrent-mate

# 2. Installer en mode développement (package + dépendances dev)
pip install -e ".[dev]"
# ou de façon équivalente :
make install-dev

# 3. Câbler les hooks git (une seule fois par clone)
./hooks/install.sh
```

Cela installe :

- Le package `personalscraper` en mode éditable
- Les commandes CLI `torrentmate` **et** `personalscraper` (alias) dans le PATH
- Les outils de dev (pytest, ruff, mypy…)

> **TorrentMate** est le nom du projet ; la commande est **`torrentmate`**
> (l'ancienne **`personalscraper`** reste un alias fonctionnel). Le package Python
> et les apps PM2 conservent encore l'identifiant `personalscraper` en attendant le
> rename complet du code ([issue #223](https://github.com/IznoCorp/torrent-mate/issues/223)).

### Hooks git (`./hooks/install.sh`)

Le script est **idempotent** : il configure uniquement `core.hooksPath = hooks`
pour ce clone (écrit dans `.git/config`, **jamais** dans `~/.gitconfig`), rend
les hooks exécutables, et refuse de s'exécuter hors d'un dépôt git.

Option : `./hooks/install.sh --install-cron` ajoute aussi l'entrée crontab
d'audit de couverture semestriel.

### Générer la configuration

```bash
# Crée config/ à partir du template config.example/
torrentmate init-config
```

> Les disques de stockage se déclarent dans `config/disks.json5` (requis avant que
> `dispatch` puisse déplacer les médias) — voir [CONFIGURATION.md](CONFIGURATION.md).

## Configuration

### Fichier .env

```bash
cp .env.example .env
```

Ouvrir `.env` et remplir au minimum les clés API et identifiants des services :

```ini
QBIT_PASSWORD=votre_mot_de_passe
TMDB_API_KEY=votre_clé_tmdb
TVDB_API_KEY=votre_clé_tvdb
```

> Le `.env` ne contient que les identifiants qBittorrent — l'hôte et le port
> vivent dans `config/torrent.json5` (`clients.qbittorrent.host` / `.port`).

Le `.env` héberge tous les secrets (gitignoré) : clés API, passkeys de trackers,
`TELEGRAM_*`, `HEALTHCHECK_URL`, identifiants du client torrent, ainsi que les
secrets de l'UI web (`WEB_PASSWORD_HASH`, `WEB_JWT_SECRET` — voir la section
[Déploiement de l'UI web](#déploiement-de-lui-web-torrentmate)).

Pour le guide complet de toutes les variables d'environnement, comment obtenir
les clés API et les options avancées (config JSON5), voir
**[CONFIGURATION.md](CONFIGURATION.md)**.

### Répertoire de staging

Au premier lancement, TorrentMate crée automatiquement l'arborescence du
staging dans `paths.staging_dir` (tel que défini dans votre `config/paths.json5`).
Aucun `mkdir` manuel n'est nécessaire.

Vous verrez un unique avertissement de log au premier lancement :

```
[warning] staging_tree_created paths=[...] count=8
```

Ce comportement est attendu — il confirme que les répertoires ont bien été créés.

### Vérification

```bash
# Smoke test : le package s'importe
python -c "import personalscraper"

# La CLI est accessible
torrentmate --help

# Suite de tests complète (pytest -v -n auto)
make test

# Barrière locale complète (lint + tests + module-size + typed-api…)
make check

# Prévisualiser le pipeline (sans rien modifier)
torrentmate run --dry-run
```

## Scheduling automatique (PM2)

Tous les daemons et jobs planifiés sont gérés par **PM2** via
`ecosystem.config.js` à la racine du dépôt. Les apps Python utilisent
`interpreter: none` : PM2 lance directement le shim pyenv `3.12.4`. Les champs
cron sont en **heure locale** (format 5 champs `min heure jour mois jour-semaine`).

### Mise en route

```bash
# Depuis la racine du dépôt
pm2 start ecosystem.config.js && pm2 save
```

> **Nommage** : le package Python, les apps PM2 `personalscraper-*` et le dossier
> local `~/dev/PersonalScraper` (cwd des daemons, `PERSONALSCRAPER_CONFIG`) gardent
> encore l'identifiant `personalscraper` — c'est le nom réel du déploiement en cours.
> Le rename complet vers `torrentmate` est suivi par l'issue #223.

### Daemons (`autorestart`, sans cron)

| App PM2                   | Commande                       | Cadence        | cwd                     | Notes                                                                                    |
| ------------------------- | ------------------------------ | -------------- | ----------------------- | ---------------------------------------------------------------------------------------- |
| `personalscraper-watch`   | `watch`                        | daemon continu | `~/dev/PersonalScraper` | Poll du client torrent, debounce, puis `run` ; `restart_delay: 5000`, `max_restarts: 10` |
| `torrentmate-web`         | `web`                          | daemon continu | `~/deploy/torrentmate`  | **Prod**, port 8710, `tm.iznogoudatall.xyz` ; venv de prod                               |
| `torrentmate-web-staging` | `web --port 8711`              | daemon continu | `~/staging/torrentmate` | **Staging**, port 8711, `tm-staging.iznogoudatall.xyz` ; venv de staging                 |
| `torrentmate-autodeploy`  | `./scripts/autodeploy-poll.sh` | boucle 60 s    | `~/dev/PersonalScraper` | `interpreter: /bin/bash` ; redéploie prod/staging sur avancée de branche                 |

### Jobs planifiés (`cron_restart`)

Tous en shim pyenv `3.12.4`, cwd `~/dev/PersonalScraper` :

| App PM2                         | Commande                                                      | `cron_restart`  | Signification                                                     |
| ------------------------------- | ------------------------------------------------------------- | --------------- | ----------------------------------------------------------------- |
| `personalscraper-index-enrich`  | `library-index --mode enrich --budget 1800 --wait-for-lock 0` | `30 4 * * 0`    | Dimanche 04:30 (heures creuses)                                   |
| `personalscraper-backfill-ids`  | `library-backfill-ids`                                        | `0 5 * * 0`     | Dimanche 05:00 (après enrich)                                     |
| `personalscraper-follow-detect` | `follow detect`                                               | `0 3 * * *`     | Quotidien 03:00 — enqueue des épisodes fraîchement diffusés       |
| `personalscraper-grab`          | `grab`                                                        | `20 3,15 * * *` | Quotidien 03:20 et 15:20 (post-detect + retry de midi)            |
| `personalscraper-health-check`  | `health-check`                                                | `15 * * * *`    | Chaque heure à :15 — liveness + anomalies de log, alerte Telegram |

### Kill-switch du watcher

Le watcher peut être désactivé sans arrêter PM2 :

```json5
// config/watch_seed.json5
watch: {
  enabled: false,  // Le daemon tourne mais ne déclenche pas de run
}
```

Appliquer : `pm2 restart personalscraper-watch`

### Gérer les daemons

```bash
# Statut / logs
pm2 status
pm2 logs personalscraper-watch

# Arrêter / redémarrer une app
pm2 stop personalscraper-watch
pm2 restart personalscraper-watch

# Déclencher un run immédiat (poke sans attendre le prochain poll)
torrentmate watch-now
```

### Persistance au boot

```bash
pm2 startup
pm2 save
```

PM2 redémarre automatiquement tous les daemons après un reboot.

### Logs du pipeline

Les logs sont écrits dans `logs/` (JSON structuré) :

```bash
tail -f logs/personalscraper.json
# Affichage lisible
tail -f logs/personalscraper.json | python -m json.tool
```

## Déploiement de l'UI web (TorrentMate)

**TorrentMate** est l'application web (SPA React servie par un daemon FastAPI
derrière Caddy, avec un flux d'événements temps-réel via Redis et une PWA
installable). `personalscraper` est le nom de code du moteur Python ; le
frontend est **TorrentMateUI**.

Deux clones de déploiement reproduisent le modèle de KanbanMate : chacun a son
**propre venv** (isolation de l'install éditable de dev) et sa **propre copie
complète du `.env`**, mais tous deux pointent vers l'unique config canonique via
`PERSONALSCRAPER_CONFIG=/Users/izno/dev/PersonalScraper/config`.

| Rôle    | URL                                    | Chemin du clone         | Suit      | App PM2                   | Port | Venv (override)                                  |
| ------- | -------------------------------------- | ----------------------- | --------- | ------------------------- | ---- | ------------------------------------------------ |
| Prod    | `https://tm.iznogoudatall.xyz`         | `~/deploy/torrentmate`  | `main`    | `torrentmate-web`         | 8710 | `~/deploy/torrentmate-venv` (`TM_VENV`)          |
| Staging | `https://tm-staging.iznogoudatall.xyz` | `~/staging/torrentmate` | `staging` | `torrentmate-web-staging` | 8711 | `~/staging/torrentmate-venv` (`TM_STAGING_VENV`) |

### Secrets de l'UI web

L'UI s'authentifie en mono-utilisateur (`web.username`, `izno` par défaut) avec
un cookie de session JWT. Deux secrets vivent dans le `.env` :

```bash
# Génère le hash scrypt du mot de passe (écrit/affiche les lignes .env)
torrentmate web set-password
#   → WEB_PASSWORD_HASH=scrypt$N$r$p$salt$hash
#   → WEB_JWT_SECRET  (sinon : python -c "import secrets; print(secrets.token_urlsafe(32))")
```

Un `WEB_JWT_SECRET` vide ou un `WEB_PASSWORD_HASH` manquant fait échouer le
login en `401` (fail-closed), jamais en `500`.

### Préparer un clone de déploiement

```bash
# Exemple pour la prod (idem staging avec le chemin/venv correspondants)
git clone <repo-url> ~/deploy/torrentmate
python -m venv ~/deploy/torrentmate-venv
~/deploy/torrentmate-venv/bin/pip install -e ~/deploy/torrentmate

# Copie complète du .env (secrets identiques à l'instance de dev)
cp ~/dev/PersonalScraper/.env ~/deploy/torrentmate/.env

# Pré-build du SPA (sortie Vite → frontend/dist/ ; scripts/deploy.sh le rsync
# ensuite vers personalscraper/web/static/, le dossier réellement servi)
cd ~/deploy/torrentmate/frontend && npm ci && npm run build
```

> `torrentmate web` refuse de démarrer si `static/index.html` est absent et
> que `web.dev_mode` est `false` — cela évite de servir une app à moitié
> déployée.

### Modèle « push to deploy »

- **Pousser sur `main`** → la prod se redéploie automatiquement.
- **Pousser sur `staging`** → le staging se redéploie automatiquement.

C'est le rôle du daemon `torrentmate-autodeploy` (boucle 60 s,
`AUTODEPLOY_INTERVAL` pour override, `--once` pour les tests, fail-soft par
cycle — un passage en échec ne tue jamais la boucle) :

- **Prod** : `git fetch origin main` → si `main` a avancé → `git pull --ff-only`
  → `scripts/deploy.sh`.
- **Staging** : `git fetch origin staging` → si `staging` a avancé →
  `git reset --hard origin/staging` (le staging peut être rebasé/force-push) →
  `scripts/deploy-staging.sh`.

> Les remotes des clones de déploiement doivent être en **SSH** (le poller est
> non-interactif ; HTTPS+GCM demanderait des identifiants à chaque passe). Les
> opérations réseau git sont bornées par `timeout` (`TM_GIT_NET_TIMEOUT`,
> défaut 60 s). Chemins de clone surchargables via `TM_PROD_CLONE` /
> `TM_STAGING_CLONE`.

`scripts/deploy.sh` (prod, `main` uniquement) et `scripts/deploy-staging.sh`
(staging, branche courante du clone) enchaînent : build du frontend →
`rsync -a --delete` du build vers `personalscraper/web/static/` → stamp
`BUILD_COMMIT` → `pip install -e .` dans le venv → `pm2 startOrRestart … --only
<app> --update-env` → post-check `curl 127.0.0.1:<port>/api/health` == 200
(retry 15 × 2 s). Le staging tamponne `"branche @ sha"` à l'identique dans
`TM_BUILD_COMMIT` et `BUILD_COMMIT` (sinon la PWA signalerait une mise à jour
fantôme perpétuelle).

### Reverse-proxy Caddy

Les blocs Caddy sont **appliqués manuellement par l'opérateur** (pas de script)
dans `/opt/homebrew/etc/Caddyfile` :

```caddy
https://tm.iznogoudatall.xyz {
    import tls_config
    reverse_proxy localhost:8710
}
https://tm-staging.iznogoudatall.xyz {
    import tls_config
    reverse_proxy localhost:8711
}
```

Le proxying WebSocket est natif à `reverse_proxy` (aucune directive
supplémentaire). Pas de basicauth Caddy : l'app impose sa propre auth JWT-cookie
sur `/api/*` et le handshake WS. Pré-requis opérateur : les enregistrements DNS
`A`/`CNAME` de `tm` et `tm-staging` doivent pointer vers IznoServer avant la
première émission de certificat.

Le détail complet (protocole WebSocket, relais Redis, PWA, contrat REST)
est documenté dans **[docs/reference/web-ui.md](docs/reference/web-ui.md)**.

## Mise à jour

```bash
cd ~/dev/PersonalScraper
git pull
pip install -e ".[dev]"
```

Les clones de déploiement se mettent à jour tout seuls via
`torrentmate-autodeploy` (push sur `main`/`staging`).

## Désinstallation

```bash
pm2 stop personalscraper-watch personalscraper-index-enrich personalscraper-backfill-ids \
        personalscraper-follow-detect personalscraper-grab personalscraper-health-check \
        torrentmate-web torrentmate-web-staging torrentmate-autodeploy
pm2 delete personalscraper-watch personalscraper-index-enrich personalscraper-backfill-ids \
           personalscraper-follow-detect personalscraper-grab personalscraper-health-check \
           torrentmate-web torrentmate-web-staging torrentmate-autodeploy
pm2 save
pip uninstall personalscraper
```
