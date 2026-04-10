# V1 — INGEST : Design

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

## Architecture

### Fichiers créés

```
099-SCRIPTS/pipeline/
├── .env                    # Config (non gitté) : credentials qBit, chemins, seuils
├── .env.example            # Template synchronisé avec .env (gitté)
├── ingest.py               # Script principal — point d'entrée CLI + cron
├── qbit_client.py          # Client API qBittorrent (auth, list, status)
├── tracker.py              # Gestion du JSON de tracking (hash → état)
└── ingested_torrents.json  # État persistant : torrents déjà traités (non gitté)
```

### Dépendances Python

- `requests` — appels HTTP vers l'API qBittorrent
- `python-dotenv` — chargement du `.env`
- Stdlib uniquement pour le reste (`shutil`, `json`, `argparse`, `logging`, `os`, `pathlib`)

Pas de dépendance lourde. `requests` et `python-dotenv` sont probablement déjà installés (utilisés par FileMate).

## Interfaces

### CLI

```bash
# Lancement manuel (mode interactif)
python3 099-SCRIPTS/pipeline/ingest.py

# Dry-run (prévisualisation, aucune action)
python3 099-SCRIPTS/pipeline/ingest.py --dry-run

# Mode verbose
python3 099-SCRIPTS/pipeline/ingest.py --verbose

# Combinable
python3 099-SCRIPTS/pipeline/ingest.py --dry-run --verbose
```

À terme, un alias shell `media-ingest` pourra être créé.

### Cron

```cron
0 3 * * * /usr/bin/python3 "/Volumes/IznoServer SSD/A TRIER/099-SCRIPTS/pipeline/ingest.py" >> "/Volumes/IznoServer SSD/A TRIER/099-SCRIPTS/pipeline/logs/ingest.log" 2>&1
```

## Modules

### `qbit_client.py` — Client API qBittorrent

```python
class QBitClient:
    """Client pour l'API Web de qBittorrent."""

    def __init__(self, host: str, port: int, username: str, password: str):
        ...

    def login(self) -> None:
        """POST /api/v2/auth/login — obtient le cookie SID."""

    def get_completed_torrents(self) -> list[dict]:
        """GET /api/v2/torrents/info — retourne les torrents complétés (progress=1.0).
        Inclut ceux en seed ET ceux arrêtés."""

    def is_seeding(self, torrent: dict) -> bool:
        """Vérifie si le torrent est en seed actif.
        States 'uploading', 'stalledUP', 'forcedUP', 'queuedUP' → True
        States 'pausedUP', 'stoppedUP', 'missingFiles' → False"""

    def get_torrent_hash(self, torrent: dict) -> str:
        """Retourne le hash unique du torrent."""

    def get_content_path(self, torrent: dict) -> Path:
        """Retourne le chemin complet du contenu (fichier ou dossier)."""

    def get_all_torrent_hashes(self) -> set[str]:
        """Retourne tous les hash de torrents connus de qBit (pour le nettoyage du tracker)."""
```

### `tracker.py` — Tracking des torrents traités

```python
class IngestTracker:
    """Persiste l'état des torrents déjà ingérés dans un fichier JSON."""

    def __init__(self, tracker_path: Path):
        ...

    def is_ingested(self, torrent_hash: str) -> bool:
        """Vérifie si ce torrent a déjà été traité."""

    def mark_ingested(self, torrent_hash: str, torrent_name: str, action: str) -> None:
        """Enregistre un torrent comme traité.
        action = 'copied' | 'moved'"""

    def cleanup(self, active_hashes: set[str]) -> int:
        """Retire du tracker les torrents qui ne sont plus dans qBit.
        Retourne le nombre d'entrées supprimées."""

    def load(self) -> dict:
        """Charge le JSON."""

    def save(self) -> None:
        """Sauvegarde le JSON."""
```

**Format du fichier JSON :**

```json
{
  "abc123def456": {
    "name": "The.Boys.S05E01.MULTi...",
    "action": "copied",
    "ingested_at": "2026-04-10T03:00:12"
  }
}
```

### `ingest.py` — Orchestrateur principal

```python
def main(dry_run: bool = False, verbose: bool = False) -> None:
    """
    Flux principal :
    1. Charger la config (.env)
    2. Se connecter à qBittorrent
    3. Récupérer les torrents complétés
    4. Nettoyer le tracker (retirer les torrents supprimés de qBit)
    5. Pour chaque torrent non encore ingéré :
       a. Résoudre le content_path
       b. Vérifier que le fichier/dossier existe
       c. Vérifier l'espace disque disponible sur le SSD
       d. Copier (si seeding) ou déplacer (si terminé)
       e. Marquer comme ingéré dans le tracker
    6. Afficher/logger le résumé
    """
```

## Flux de données détaillé

```
                    ┌──────────────┐
                    │  .env        │
                    │ (credentials)│
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
                    │   tracker    │◀──── ingested_torrents.json
                    │ .is_ingested │
                    └──────┬───────┘
                           │
                    filtrer les nouveaux
                           │
              ┌────────────▼────────────┐
              │   Pour chaque torrent   │
              │                         │
              │  is_seeding? ──┐        │
              │       │    YES │        │
              │       NO       │        │
              │       │        │        │
              │    shutil    shutil     │
              │    .move()   .copytree()│
              │       │        │        │
              │       └────┬───┘        │
              │            │            │
              │   tracker.mark_ingested │
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │   Résumé     │
                    │ (stdout/log) │
                    └──────────────┘
```

## Configuration (.env)

```env
# qBittorrent API
QBIT_HOST=localhost
QBIT_PORT=8081
QBIT_USERNAME=izno
QBIT_PASSWORD=your_password_here

# Paths
TORRENT_COMPLETE_DIR=/Volumes/IznoServer SSD/torrents/complete
INGEST_TARGET_DIR=/Volumes/IznoServer SSD/A TRIER

# Thresholds
MIN_FREE_SPACE_GB=20
```

## Gestion d'erreurs

| Situation                          | Comportement                                    |
| ---------------------------------- | ----------------------------------------------- |
| qBit API inaccessible              | Log ERROR, exit code 1                          |
| Auth échouée                       | Log ERROR, exit code 1                          |
| Torrent content_path introuvable   | Log WARNING, skip ce torrent, continuer         |
| Espace disque insuffisant          | Log WARNING, skip ce torrent, continuer         |
| Erreur de copie/move               | Log ERROR pour ce torrent, continuer les autres |
| Fichier JSON corrompu              | Recréer un fichier vide, log WARNING            |
| Fichier déjà existant dans A TRIER | Log INFO (skip), ne pas écraser                 |

**Principe : ne jamais crasher sur un torrent individuel.** On traite tout ce qu'on peut et on reporte les erreurs.

## Sécurité

- Le `.env` contient le mot de passe qBit → **non gitté**, ajouté au `.gitignore`
- Le `ingested_torrents.json` contient des métadonnées de torrents → **non gitté**
- Aucune donnée sensible dans les logs (pas de mot de passe loggé)
