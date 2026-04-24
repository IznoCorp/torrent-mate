# qbittorrent-api — Reference Documentation

> Date : 2026-04-10 | Contexte : V1 INGEST — wrapper qBittorrent pour le pipeline PersonalScraper

## Qu'est-ce que qbittorrent-api ?

[qbittorrent-api](https://github.com/rmartin16/qbittorrent-api) est un client Python pour l'API Web
de qBittorrent. Il remplace un client HTTP maison en gérant automatiquement :

- Authentification (login/re-login si cookie expiré)
- Headers CSRF (Referer/Origin)
- Compatibilité qBittorrent v4.x et v5.0+ (pausedUP/stoppedUP)
- Enum `TorrentState` avec helpers (`is_complete`, `is_uploading`, `is_stopped`)
- Retry intégré avec backoff exponentiel

**Version courante** : 2025.11.1 (supporte qBittorrent jusqu'à v5.1.4, Web API v2.11.4)
**Licence** : MIT
**Stars** : 493

## Installation

```bash
pip install qbittorrent-api
```

**Python** : >= 3.9
**Dépendances** : `requests >= 2.16.0`, `urllib3 >= 1.24.2`, `packaging`

## Connexion et authentification

### Context manager (recommandé)

```python
import qbittorrentapi

with qbittorrentapi.Client(
    host="localhost",
    port=8081,
    username="izno",
    password="secret",
) as qbt:
    # auth_log_in() appelé automatiquement à l'entrée
    torrents = qbt.torrents_info()
    # auth_log_out() appelé automatiquement à la sortie
```

### Connexion manuelle

```python
qbt = qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
)

try:
    qbt.auth_log_in()
except qbittorrentapi.LoginFailed:
    print("Identifiants incorrects")
except qbittorrentapi.APIConnectionError:
    print("qBittorrent non accessible")

# ... travail ...

qbt.auth_log_out()
```

### Auto-reconnexion

Si le cookie de session expire pendant une opération, la librairie intercepte le HTTP 403,
re-appelle `auth_log_in()`, et rejoue la requête automatiquement. Transparent pour l'appelant.

### Variables d'environnement (fallback)

| Variable                                         | Rôle                 |
| ------------------------------------------------ | -------------------- |
| `QBITTORRENTAPI_HOST`                            | Host                 |
| `QBITTORRENTAPI_USERNAME`                        | Username             |
| `QBITTORRENTAPI_PASSWORD`                        | Password             |
| `QBITTORRENTAPI_DO_NOT_VERIFY_WEBUI_CERTIFICATE` | Désactiver vérif SSL |

## Constructeur Client — paramètres clés

```python
qbittorrentapi.Client(
    host="localhost",
    port=8081,
    username="izno",
    password="secret",
    VERIFY_WEBUI_CERTIFICATE=True,    # False pour certificats auto-signés
    REQUESTS_ARGS={"timeout": 30},    # Timeout en secondes (défaut : 15.1s)
    SIMPLE_RESPONSES=False,           # True = dicts bruts au lieu d'objets riches
)
```

## Lister les torrents — `torrents_info()`

```python
torrents = qbt.torrents_info(
    status_filter=None,     # Filtrer par état (voir tableau ci-dessous)
    category=None,          # Filtrer par catégorie
    sort=None,              # Trier par champ
    reverse=None,           # Inverser le tri
    limit=None,             # Max résultats
    offset=None,            # Offset (négatif = depuis la fin)
    torrent_hashes=None,    # Filtrer par hash(es)
    tag=None,               # Filtrer par tag ("" = sans tag)
)
```

### Valeurs de `status_filter`

| Filtre                  | Description                                                 |
| ----------------------- | ----------------------------------------------------------- |
| `"all"`                 | Tous les torrents                                           |
| `"downloading"`         | En cours de téléchargement                                  |
| `"seeding"`             | En seed (upload après complétion)                           |
| `"completed"`           | Téléchargement terminé (100%), quel que soit l'état de seed |
| `"paused"`              | En pause (terme qBit v4.x)                                  |
| `"stopped"`             | Arrêté (terme qBit v5.x, remplace "paused")                 |
| `"active"`              | Transfert de données en cours                               |
| `"inactive"`            | Pas de transfert                                            |
| `"stalled"`             | Bloqué (pas de peers)                                       |
| `"stalled_uploading"`   | Bloqué en upload                                            |
| `"stalled_downloading"` | Bloqué en download                                          |
| `"errored"`             | En erreur                                                   |
| `"checking"`            | Vérification en cours                                       |
| `"moving"`              | Déplacement en cours                                        |

### API fluide (alternative)

```python
# Équivalents :
qbt.torrents_info(status_filter="completed")
qbt.torrents.info.completed()

qbt.torrents_info(status_filter="seeding")
qbt.torrents.info.seeding()
```

## TorrentDictionary — propriétés du torrent

Chaque torrent retourné par `torrents_info()` est un `TorrentDictionary` : à la fois dict et objet.

```python
torrent = qbt.torrents_info()[0]

# Les deux syntaxes fonctionnent :
torrent.name            # "Shrinking.S03.MULTi.1080p..."
torrent["name"]         # idem

torrent.hash            # "a1b2c3d4e5..."
torrent.content_path    # "/path/to/torrents/complete/Shrinking.S03..."
torrent.save_path       # "/path/to/torrents/complete/"
torrent.progress        # 1.0
torrent.size            # 5368709120 (bytes)
torrent.state           # "uploading"
torrent.state_enum      # TorrentState.UPLOADING
```

### Propriétés principales

| Propriété       | Type         | Description                                      |
| --------------- | ------------ | ------------------------------------------------ |
| `hash`          | str          | Hash SHA-1 du torrent                            |
| `name`          | str          | Nom d'affichage                                  |
| `state`         | str          | État brut ("uploading", "stalledUP", etc.)       |
| `state_enum`    | TorrentState | Enum avec helpers                                |
| `content_path`  | str          | Chemin absolu du contenu (fichier ou dossier)    |
| `save_path`     | str          | Dossier de destination                           |
| `progress`      | float        | Progression (0.0 à 1.0)                          |
| `size`          | int          | Taille en bytes                                  |
| `total_size`    | int          | Taille totale en bytes                           |
| `completion_on` | int          | Timestamp Unix de complétion (-1 si pas terminé) |
| `added_on`      | int          | Timestamp Unix d'ajout                           |
| `ratio`         | float        | Ratio de partage                                 |
| `seeding_time`  | int          | Temps de seed en secondes                        |
| `category`      | str          | Catégorie assignée                               |
| `tags`          | str          | Tags (séparés par virgule)                       |
| `tracker`       | str          | URL du premier tracker actif                     |
| `dlspeed`       | int          | Vitesse download (bytes/s)                       |
| `upspeed`       | int          | Vitesse upload (bytes/s)                         |
| `amount_left`   | int          | Bytes restants à télécharger                     |
| `magnet_uri`    | str          | Lien magnet                                      |

## TorrentState — enum et helpers

### Tous les états

| État                       | Valeur API             | Description                           |
| -------------------------- | ---------------------- | ------------------------------------- |
| `UPLOADING`                | `"uploading"`          | Seed actif                            |
| `STALLED_UPLOAD`           | `"stalledUP"`          | Seed sans peers                       |
| `FORCED_UPLOAD`            | `"forcedUP"`           | Seed forcé                            |
| `QUEUED_UPLOAD`            | `"queuedUP"`           | En file d'attente pour seed           |
| `CHECKING_UPLOAD`          | `"checkingUP"`         | Vérification après complétion         |
| `PAUSED_UPLOAD`            | `"pausedUP"`           | En pause après complétion (qBit v4.x) |
| `STOPPED_UPLOAD`           | `"stoppedUP"`          | Arrêté après complétion (qBit v5.x)   |
| `DOWNLOADING`              | `"downloading"`        | Téléchargement actif                  |
| `STALLED_DOWNLOAD`         | `"stalledDL"`          | Download sans peers                   |
| `FORCED_DOWNLOAD`          | `"forcedDL"`           | Download forcé                        |
| `QUEUED_DOWNLOAD`          | `"queuedDL"`           | En file d'attente pour download       |
| `CHECKING_DOWNLOAD`        | `"checkingDL"`         | Vérification pendant download         |
| `PAUSED_DOWNLOAD`          | `"pausedDL"`           | En pause pendant download (v4.x)      |
| `STOPPED_DOWNLOAD`         | `"stoppedDL"`          | Arrêté pendant download (v5.x)        |
| `METADATA_DOWNLOAD`        | `"metaDL"`             | Récupération metadata                 |
| `FORCED_METADATA_DOWNLOAD` | `"forcedMetaDL"`       | Metadata forcée (v5.0+)               |
| `ERROR`                    | `"error"`              | Erreur                                |
| `MISSING_FILES`            | `"missingFiles"`       | Fichiers manquants                    |
| `ALLOCATING`               | `"allocating"`         | Allocation disque                     |
| `CHECKING_RESUME_DATA`     | `"checkingResumeData"` | Vérification au démarrage             |
| `MOVING`                   | `"moving"`             | Déplacement en cours                  |
| `UNKNOWN`                  | `"unknown"`            | État inconnu                          |

### Helpers booléens

| Helper           | True pour                                                             | Utilisation pipeline                    |
| ---------------- | --------------------------------------------------------------------- | --------------------------------------- |
| `is_complete`    | Tous les états \*UP (uploading, stalledUP, pausedUP, stoppedUP, etc.) | Torrent terminé (prêt pour copie/move)  |
| `is_uploading`   | uploading, stalledUP, checkingUP, queuedUP, forcedUP                  | En seed actif (copier, ne pas déplacer) |
| `is_stopped`     | pausedUP, stoppedUP, pausedDL, stoppedDL                              | Arrêté (safe pour déplacer)             |
| `is_downloading` | Tous les états \*DL                                                   | En cours de download                    |
| `is_errored`     | error, missingFiles                                                   | En erreur                               |
| `is_checking`    | checkingUP, checkingDL, checkingResumeData                            | Vérification                            |
| `is_paused`      | Alias de `is_stopped`                                                 | Compatibilité                           |

### Logique pour le pipeline ingest

```python
for torrent in qbt.torrents_info(status_filter="completed"):
    state = torrent.state_enum

    if state.is_uploading:
        # En seed → COPIER (ne pas supprimer la source)
        action = "copy"
    elif state.is_complete and not state.is_uploading:
        # Terminé, plus en seed → DEPLACER
        action = "move"
    else:
        continue  # skip (checking, etc.)
```

## Gestion d'erreurs

### Hiérarchie d'exceptions

```
APIError (base)
├── UnsupportedQbittorrentVersion
├── FileError (IOError)
│   └── TorrentFileError
│       ├── TorrentFileNotFoundError
│       └── TorrentFilePermissionError
└── APIConnectionError (requests.RequestException)
    ├── LoginFailed
    └── HTTPError (requests.HTTPError)
        ├── HTTP4XXError
        │   ├── HTTP400Error / InvalidRequest400Error
        │   ├── HTTP401Error / Unauthorized401Error
        │   ├── HTTP403Error / Forbidden403Error
        │   ├── HTTP404Error / NotFound404Error
        │   └── HTTP409Error / Conflict409Error
        └── HTTP5XXError
            └── HTTP500Error / InternalServerError500Error
```

### Pattern pour le pipeline

```python
import qbittorrentapi

try:
    with qbittorrentapi.Client(
        host="localhost", port=8081,
        username="izno", password="secret",
    ) as qbt:
        completed = qbt.torrents_info(status_filter="completed")
        # ... traitement ...

except qbittorrentapi.LoginFailed:
    # Identifiants incorrects ou WebUI auth désactivée
    log.error("qBittorrent: échec d'authentification")

except qbittorrentapi.APIConnectionError:
    # qBittorrent non accessible (pas lancé, mauvais host/port)
    log.error("qBittorrent: connexion impossible")

except qbittorrentapi.APIError as e:
    # Autre erreur API
    log.error(f"qBittorrent: erreur API — {e}")
```

## CSRF et sécurité

La librairie gère automatiquement :

- **Cookie de session** : `SID` (v4.x) ou `QBT_SID_{port}` (v5.2+)
- **Re-login transparent** si le cookie expire
- **CSRF** : géré côté serveur par qBittorrent, pas de token nécessaire côté client

**Ban IP** : après trop de tentatives de login échouées, qBittorrent ban l'IP (HTTP 403).
Configurable via `web_ui_max_auth_fail_count` et `web_ui_ban_duration` dans les settings qBit.

## Compatibilité qBittorrent v4.x vs v5.x

La librairie abstrait les différences :

| Concept           | v4.x                | v5.x               | Librairie                     |
| ----------------- | ------------------- | ------------------ | ----------------------------- |
| Pause             | `torrents_pause()`  | `torrents_stop()`  | Les deux fonctionnent (alias) |
| Resume            | `torrents_resume()` | `torrents_start()` | Les deux fonctionnent (alias) |
| État pause upload | `pausedUP`          | `stoppedUP`        | Les deux dans l'enum          |
| Filtre pause      | `"paused"`          | `"stopped"`        | Les deux acceptés             |
| Filtre resume     | `"resumed"`         | `"running"`        | Les deux acceptés             |

Le code n'a **pas besoin de vérifier la version** de qBittorrent.

## Timeout et retry

- **Timeout par défaut** : 15.1 secondes
- **Retry intégré** : 2 niveaux
  - HTTPAdapter : 1 retry pour erreurs connexion/lecture et codes 500/502/504
  - Request manager : jusqu'à 2 retries avec backoff exponentiel (max 10s)

```python
# Timeout custom :
qbt = qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
    REQUESTS_ARGS={"timeout": 30},  # 30 secondes
)
```

## Patterns pour le pipeline PersonalScraper

### Lister les torrents terminés

```python
with qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
) as qbt:
    for torrent in qbt.torrents_info(status_filter="completed"):
        print(f"{torrent.name}")
        print(f"  Hash:    {torrent.hash}")
        print(f"  Path:    {torrent.content_path}")
        print(f"  Size:    {torrent.size / 1e9:.1f} Go")
        print(f"  State:   {torrent.state}")
        print(f"  Seeding: {torrent.state_enum.is_uploading}")
```

### Copier ou déplacer selon l'état de seed

```python
from pathlib import Path
import shutil

STAGING = Path("/path/to/staging")

with qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
) as qbt:
    for torrent in qbt.torrents_info(status_filter="completed"):
        source = Path(torrent.content_path)
        dest = STAGING / source.name

        if dest.exists():
            continue  # déjà présent

        if torrent.state_enum.is_uploading:
            # En seed → copier
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
        else:
            # Plus en seed → déplacer
            shutil.move(str(source), str(dest))
```

### Récupérer tous les hash (pour le tracker)

```python
with qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
) as qbt:
    all_hashes = {t.hash for t in qbt.torrents_info()}
    # Utiliser pour nettoyer le tracker (retirer les hash disparus)
```

### Connexion robuste avec retry

```python
import time
import qbittorrentapi

def connect_qbit(host, port, username, password, max_retries=3, delay=5):
    """Connexion avec retry pour le cron."""
    for attempt in range(max_retries):
        try:
            qbt = qbittorrentapi.Client(
                host=host, port=port,
                username=username, password=password,
                REQUESTS_ARGS={"timeout": 30},
            )
            qbt.auth_log_in()
            return qbt
        except qbittorrentapi.LoginFailed:
            raise  # Ne pas réessayer si mauvais credentials
        except qbittorrentapi.APIConnectionError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
```

## Imports utiles

```python
# Client
from qbittorrentapi import Client

# Enum états
from qbittorrentapi import TorrentState

# Exceptions
from qbittorrentapi import (
    APIError,
    APIConnectionError,
    LoginFailed,
    Forbidden403Error,
)
```

## Sources

- [PyPI](https://pypi.org/project/qbittorrent-api/) — v2025.11.1
- [GitHub](https://github.com/rmartin16/qbittorrent-api) — 493 stars, MIT
- [qBittorrent Web API wiki](<https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)>)
