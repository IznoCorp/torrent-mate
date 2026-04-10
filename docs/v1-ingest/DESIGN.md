# V1 — INGEST : Design

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

## Architecture

### Fichiers créés

```
personalscraper/ingest/
├── __init__.py
├── qbit_client.py          # Client API qBittorrent (auth, list, status)
├── tracker.py              # Gestion du JSON de tracking (hash → état)
└── ingest.py               # Orchestrateur ingest
```

Fichier de données persistant : `~/.personalscraper/ingested_torrents.json` (non gitté)

### Dépendances Python

- `qbittorrent-api>=2025.1.0` — client Python officieux pour l'API Web qBittorrent
  (gestion auto de l'auth, re-login, CSRF, support qBit v5.0+ avec `stoppedUP`)
- `pydantic-settings` — via Settings de V0 (pas de chargement .env propre)
- Stdlib uniquement pour le reste (`shutil`, `json`, `pathlib`)

## Interfaces

### CLI (via Click, défini en V0)

```bash
# Lancement manuel
personalscraper ingest

# Dry-run (prévisualisation, aucune action)
personalscraper ingest --dry-run

# Mode verbose
personalscraper ingest --verbose

# Combinable
personalscraper ingest --dry-run --verbose
```

### Cron (via la commande CLI installée)

```cron
0 3 * * * /path/to/venv/bin/personalscraper run >> /dev/null 2>&1
```

Note : le cron lance `run` (pipeline complet), pas `ingest` seul.

## Modules

### `qbit_client.py` — Wrapper autour de `qbittorrent-api`

```python
import qbittorrentapi

class QBitClient:
    """Wrapper autour de qbittorrent-api pour le pipeline ingest.
    Utilise la librairie qbittorrent-api qui gère automatiquement :
    - Auth (login/re-login si cookie expiré)
    - Headers CSRF (Referer/Origin)
    - Compatibilité qBit v4.x (pausedUP) et v5.0+ (stoppedUP)
    """

    def __init__(self, host: str, port: int, username: str, password: str):
        self._client = qbittorrentapi.Client(
            host=host, port=port, username=username, password=password,
        )

    def __enter__(self) / __exit__(self):
        """Context manager : auth_log_in() / auth_log_out()."""

    def get_completed_torrents(self) -> list[qbittorrentapi.TorrentDictionary]:
        """Retourne les torrents complétés via torrents_info(status_filter='completed')."""

    def is_seeding(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        """Utilise torrent.state_enum.is_uploading (couvre uploading/stalledUP/forcedUP/queuedUP).
        Retourne False si is_complete and not is_uploading (pausedUP/stoppedUP)."""

    def get_content_path(self, torrent: qbittorrentapi.TorrentDictionary) -> Path:
        """Retourne Path(torrent.content_path)."""

    def get_all_torrent_hashes(self) -> set[str]:
        """Retourne {t.hash for t in self._client.torrents_info()}."""
```

### `tracker.py` — Tracking des torrents traités

```python
TRACKER_DIR = Path("~/.personalscraper").expanduser()
TRACKER_FILE = TRACKER_DIR / "ingested_torrents.json"

class IngestTracker:
    """Persiste l'état des torrents déjà ingérés dans un fichier JSON."""

    def __init__(self, tracker_path: Path = TRACKER_FILE):
        ...

    def is_ingested(self, torrent_hash: str) -> bool:
    def mark_ingested(self, torrent_hash: str, torrent_name: str, action: str) -> None:
    def cleanup(self, active_hashes: set[str]) -> int:
    def load(self) -> dict:
    def save(self) -> None:
```

### `ingest.py` — Orchestrateur principal

```python
def run_ingest(settings: Settings, dry_run: bool = False, verbose: bool = False) -> StepReport:
    """
    Flux principal, appelé par la commande CLI `personalscraper ingest`.
    Retourne un StepReport pour le pipeline.

    1. Se connecter à qBittorrent via Settings
    2. Récupérer les torrents complétés
    3. Nettoyer le tracker (retirer les torrents supprimés de qBit)
    4. Pour chaque torrent non encore ingéré :
       a. Résoudre le content_path
       b. Vérifier que le fichier/dossier existe
       c. Vérifier l'espace disque disponible sur le SSD
       d. Copier (si seeding) ou déplacer (si terminé)
       e. Marquer comme ingéré dans le tracker
    5. Retourner le StepReport
    """
```

## Flux de données

```
                    ┌──────────────┐
                    │  Settings    │
                    │ (V0 config)  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐         ┌─────────────────┐
                    │ qbit_client  │────────▶│ qBittorrent API │
                    │  .login()    │◀────────│  :8081          │
                    └──────┬───────┘         └─────────────────┘
                           │
              get_completed_torrents()
                           │
                    ┌──────▼───────┐
                    │   tracker    │◀──── ~/.personalscraper/ingested_torrents.json
                    │ .is_ingested │
                    └──────┬───────┘
                           │
                    filtrer les nouveaux
                           │
              ┌────────────▼────────────┐
              │   Pour chaque torrent   │
              │  is_seeding? → copy     │
              │  else → move            │
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │  StepReport  │
                    └──────────────┘
```

## Configuration (via Settings V0)

Utilise les champs de `personalscraper/config.py` (V0) :

- `qbit_host`, `qbit_port`, `qbit_username`, `qbit_password`
- `torrent_complete_dir`
- `staging_dir`
- `min_free_space_staging_gb` (seuil espace SSD)

## Gestion d'erreurs

| Situation                          | Comportement                                    |
| ---------------------------------- | ----------------------------------------------- |
| qBit API inaccessible              | Log ERROR, retourner StepReport avec erreur     |
| Auth échouée                       | Log ERROR, retourner StepReport avec erreur     |
| Torrent content_path introuvable   | Log WARNING, skip ce torrent, continuer         |
| Espace disque insuffisant          | Log WARNING, skip ce torrent, continuer         |
| Erreur de copie/move               | Log ERROR pour ce torrent, continuer les autres |
| Fichier JSON corrompu              | Recréer un fichier vide, log WARNING            |
| Fichier déjà existant dans A TRIER | Log INFO (skip), ne pas écraser                 |

**Principe : ne jamais crasher sur un torrent individuel.**
