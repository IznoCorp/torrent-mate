# Installation

Guide d'installation et de configuration de PersonalScraper.

> Voir aussi : [README.md](README.md) (vue d'ensemble du projet) | [MANUAL.md](MANUAL.md) (manuel d'utilisation)

## Prérequis

### Système

- **macOS** (testé sur macOS Sonoma 14+)
- **Python 3.10+** (`python3 --version`)
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

### Disques de stockage

Les 4 disques doivent être montés pour que le dispatch fonctionne :

```
/Volumes/Disk1/medias
/Volumes/Disk2/medias
/Volumes/Disk3/medias
/Volumes/Disk4/medias
```

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

Ouvrir `.env` et remplir au minimum les clés API et le mot de passe qBittorrent :

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

Un agent launchd permet d'exécuter le pipeline automatiquement tous les jours à 3h du matin.

### Installer l'agent

```bash
# Utiliser le script d'installation (substitue les placeholders du template)
bash scripts/install-launchd.sh
```

### Gérer l'agent

```bash
# Lancer manuellement
launchctl start com.personalscraper.pipeline

# Vérifier le statut
launchctl list | grep personalscraper

# Désactiver
launchctl unload ~/Library/LaunchAgents/com.personalscraper.pipeline.plist
```

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
pip uninstall personalscraper
launchctl unload ~/Library/LaunchAgents/com.personalscraper.pipeline.plist
rm ~/Library/LaunchAgents/com.personalscraper.pipeline.plist
```
