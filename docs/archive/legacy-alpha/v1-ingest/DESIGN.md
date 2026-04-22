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

### CLI (via Typer, défini en V0)

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

```
# Scheduling via launchd (V6) — exemple illustratif, voir V6 DESIGN pour la config réelle
# 0 3 * * * /path/to/venv/bin/personalscraper run
```

Note : le scheduling lance `run` (pipeline complet), pas `ingest` seul.

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
            REQUESTS_ARGS={"timeout": 30},   # Défaut lib = 15.1s, trop court pour le scheduling
            VERIFY_WEBUI_CERTIFICATE=False,   # API locale, pas de cert SSL
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
        """Atomic write : écrire dans .tmp puis os.replace() vers le fichier final.
        Évite la corruption si le processus est tué pendant l'écriture."""
```

### `ingest.py` — Orchestrateur principal

```python
def run_ingest(settings: Settings, dry_run: bool = False) -> StepReport:
    """
    Flux principal, appelé par la commande CLI `personalscraper ingest`.
    Retourne un StepReport pour le pipeline.

    Note : pas de paramètre `verbose` — le niveau de log est configuré
    globalement par le callback Typer dans cli.py via configure_logging().

    Note : le lock est géré par le CLI caller, pas par cette fonction.

    1. Se connecter à qBittorrent via Settings
    2. Récupérer les torrents complétés
    3. Nettoyer le tracker (retirer les torrents supprimés de qBit)
    4. Pour chaque torrent non encore ingéré :
       a. Résoudre le content_path
       b. Vérifier que le fichier/dossier existe
       c. Vérifier l'espace disque disponible sur le SSD
       d. Transférer via copie atomique (si seeding) ou move (si terminé)
       e. Vérifier la taille du fichier destination vs source
       f. Marquer comme ingéré dans le tracker
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

| Situation                          | Exception / détection               | Comportement                                    |
| ---------------------------------- | ----------------------------------- | ----------------------------------------------- |
| qBit API inaccessible              | `qbittorrentapi.APIConnectionError` | Log ERROR, retourner StepReport avec erreur     |
| Auth échouée                       | `qbittorrentapi.LoginFailed`        | Log ERROR, retourner StepReport avec erreur     |
| Torrent content_path introuvable   | `Path.exists() == False`            | Log WARNING, skip ce torrent, continuer         |
| Espace disque insuffisant          | `shutil.disk_usage()`               | Log WARNING, skip ce torrent, continuer         |
| Erreur de copie/move               | `OSError`, `PermissionError`        | Log ERROR pour ce torrent, continuer les autres |
| Fichier JSON corrompu              | `json.JSONDecodeError`              | Recréer un fichier vide, log WARNING            |
| Fichier déjà existant dans A TRIER | `Path.exists() == True`             | Log INFO (skip), ne pas écraser                 |

> Ref : [docs/qbittorrent-api-reference.md](../qbittorrent-api-reference.md) — hiérarchie exceptions, TorrentState enum

**Principe : ne jamais crasher sur un torrent individuel.**

## Protection contre les exécutions concurrentes (lock file)

> **Implémenté dès V1** (pas V6) — le lock protège dès la première commande qui modifie le filesystem.
> V6 (`run`) réutilise le même module.

```python
# personalscraper/lock.py
LOCK_FILE = Path("~/.personalscraper/pipeline.lock").expanduser()

def acquire_lock() -> bool:
    """Créer un lock file avec le PID du processus courant.
    Si le lock existe déjà :
    - Lire le PID stocké
    - Vérifier si le processus est encore vivant (os.kill(pid, 0))
    - Si mort → supprimer le stale lock, prendre le nouveau
    - Si vivant → retourner False (un autre run est en cours)
    """

def release_lock() -> None:
    """Supprimer le lock file."""
```

Le lock est acquis au **niveau CLI** (dans la commande Typer), pas dans les `run_*()` functions.
Cela évite un double-lock quand `run` appelle `run_ingest()` (les deux auraient pris le même lock).

Commandes qui acquièrent le lock : `ingest`, `sort`, `scrape`, `verify`, `dispatch`, `run`.
Chaque commande appelle `acquire_lock()` au début et `release_lock()` en `try/finally`.
Les `run_*()` functions ne gèrent PAS le lock elles-mêmes.
Le lock peut être supprimé manuellement si nécessaire (`rm ~/.personalscraper/pipeline.lock`).

## Transfert atomique (copie sûre)

> Problème : si le processus est interrompu pendant un `shutil.copytree`, un fichier
> partiellement copié reste dans `A TRIER/`. La prochaine exécution le détecte comme
> "déjà existant" et le skip — l'utilisateur se retrouve avec un fichier corrompu.

```python
STAGING_TMP_PREFIX = ".ingest_tmp_"

def transfer_torrent(source: Path, dest: Path, copy: bool) -> None:
    """Transfert atomique d'un torrent vers staging_dir.

    Si copy=True (torrent en seed) :
    1. Copier vers dest.parent / '.ingest_tmp_{hash}/' (dossier temporaire)
    2. Vérifier taille : dest_tmp.stat().st_size == source.stat().st_size (par fichier)
    3. os.rename(dest_tmp, dest) — atomique sur même filesystem (SSD)
    → Si interruption en étape 1 : seul le .tmp existe, nettoyé au prochain run
    → Si interruption en étape 3 : impossible (rename est atomique)

    Si copy=False (torrent terminé) :
    1. shutil.move(source, dest) — sur même filesystem c'est un rename atomique
    2. Vérifier que dest existe et a la bonne taille

    Au début de chaque run : nettoyer les .ingest_tmp_* orphelins.
    """
```

**Vérification post-transfert** : après chaque copie/move, vérifier
`dest.stat().st_size == source.stat().st_size` (par fichier, récursivement pour les dossiers).
Instantané et détecte 99% des corruptions. Si mismatch → supprimer dest, log ERROR, continuer.
