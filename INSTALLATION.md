# Installation

Guide d'installation et de configuration de PersonalScraper.

> Voir aussi : [README.md](README.md) (vue d'ensemble du projet) | [MANUAL.md](MANUAL.md) (manuel d'utilisation)

## Prérequis

### Système

- **macOS** (testé sur macOS Sonoma 14+)
- **Python 3.12+** (`python3 --version`)
- **pip** (`pip --version`)
- **rsync** (inclus avec macOS)
- **ffprobe** (inclus avec [FFmpeg](https://ffmpeg.org/))

```bash
# Installer FFmpeg si nécessaire (via Homebrew)
brew install ffmpeg

# Installer MediaInfo (requis par l'indexeur media — pymediainfo)
brew install media-info
```

### Services externes

- **qBittorrent** avec l'interface Web activée (Preferences > Web UI)
- Un compte **TMDB** avec clé API v3 — [inscription](https://www.themoviedb.org/settings/api)
- Un compte **TVDB** avec clé API v4 — [inscription](https://thetvdb.com/dashboard/account/apikeys)
- _(Optionnel)_ Un bot **Telegram** pour les notifications — [créer un bot](https://core.telegram.org/bots#how-do-i-create-a-bot)

## Installation

```bash
# Cloner le dépôt
git clone <repo-url> "/path/to/staging"
cd "/path/to/staging"

# Installer en mode développement (package + dépendances dev)
make install-dev
# ou directement :
pip install -e ".[dev]"
```

Cela installe :

- Le package `personalscraper` en mode éditable
- La commande CLI `personalscraper` dans le PATH
- Les outils de dev (pytest, ruff)

## Configuration

### Fichier .env

```bash
cp .env.example .env
```

Ouvrir `.env` et remplir au minimum les clés API et login/password des différents service :

```ini
QBIT_PASSWORD=votre_mot_de_passe
TMDB_API_KEY=votre_clé_tmdb
TVDB_API_KEY=votre_clé_tvdb
```

Pour le guide complet de toutes les variables d'environnement (12 au total), comment obtenir les clés API, et les options avancées (config JSON5), voir **[CONFIGURATION.md](CONFIGURATION.md)**.

### Répertoire de staging

Au premier lancement, PersonalScraper crée automatiquement l'arborescence du staging
dans `paths.staging_dir` (tel que défini dans votre `config/paths.json5`). Aucun `mkdir`
manuel n'est nécessaire.

Vous verrez un unique avertissement de log au premier lancement :

```
[warning] staging_tree_created paths=[...] count=8
```

Ce comportement est attendu — il confirme que les répertoires ont bien été créés.

### Vérification

```bash
# Vérifier que la CLI est accessible
personalscraper --help

# Vérifier que les tests passent
make test

# Prévisualiser le pipeline (sans rien modifier)
personalscraper run --dry-run
```

## Scheduling automatique (optionnel)

Le watcher `personalscraper watch` tourne en daemon via PM2 et déclenche
automatiquement le pipeline quand de nouveaux torrents sont terminés.

### Prérequis

PM2 doit être installé globalement (il gère déjà n8n sur IznoServer) :

```bash
npm install -g pm2
```

### Installer le daemon

```bash
# Depuis la racine du dépôt
pm2 start ecosystem.config.js && pm2 save
```

Cela démarre trois apps :

- **personalscraper-watch** — daemon qui poll qBittorrent toutes les 60s
  (configurable via `watch.poll_interval_s` dans `config/watch_seed.json5`).
  Quand un torrent se termine, le watcher applique un debounce de 15 min
  (`watch.debounce_s`) puis déclenche `personalscraper run`.
- **personalscraper-index-enrich** — cron PM2 (dimanche 04:30) :
  `library-index --mode enrich --budget 1800`
- **personalscraper-backfill-ids** — cron PM2 (dimanche 05:00) :
  `library-backfill-ids`

### Kill-switch

Le watcher peut être désactivé sans arrêter PM2 :

```json5
// config/watch_seed.json5
watch: {
  enabled: false,  // Le daemon tourne mais ne déclenche pas de run
}
```

Appliquer le changement : `pm2 restart personalscraper-watch`

### Gérer le daemon

```bash
# Statut
pm2 status personalscraper-watch

# Logs
pm2 logs personalscraper-watch

# Arrêter
pm2 stop personalscraper-watch

# Redémarrer
pm2 restart personalscraper-watch

# Déclencher un run immédiat (poke sans attendre le prochain poll)
personalscraper watch-now
```

### Persistance au boot

```bash
pm2 startup
pm2 save
```

PM2 redémarre automatiquement tous les daemons après un reboot.

### Logs

Les logs du pipeline sont écrits dans `logs/` (format JSON structuré). Pour consulter :

```bash
# Dernières entrées
tail -f logs/personalscraper.json

# Ou avec jq pour un affichage lisible
tail -f logs/personalscraper.json | python -m json.tool
```

## Mise à jour

```bash
cd "/path/to/staging"
git pull
pip install -e ".[dev]"
```

## Désinstallation

```bash
pm2 stop personalscraper-watch personalscraper-index-enrich personalscraper-backfill-ids
pm2 delete personalscraper-watch personalscraper-index-enrich personalscraper-backfill-ids
pm2 save
pip uninstall personalscraper
```
