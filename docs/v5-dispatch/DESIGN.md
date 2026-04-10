# V5 — DISPATCH : Design

> Déplacement intelligent des médias vers Disk1-4 (merge séries, replace films, free space)

## Architecture

### Fichiers

```
personalscraper/dispatch/
├── __init__.py
├── media_index.py      # Index JSON des médias sur les 4 disques
├── disk_scanner.py     # Scan des disques, espace libre, catégories
└── dispatcher.py       # Orchestrateur dispatch (replace/merge/new)
```

> **Note** : le `genre_mapper.py` est à la racine du package (`personalscraper/genre_mapper.py`).
> Import : `from personalscraper.genre_mapper import GenreMapper`
> Partagé entre V4 (verify) et V5 (dispatch) — single source of truth.

### Intégration avec V4 (verify)

V5 reçoit la liste des médias validés par V4 via `Verifier.get_dispatchable()`.
Chaque `VerifyResult` contient la `category` déjà calculée par V4's `GenreMapper`.
V5 ne recalcule PAS la catégorie — il utilise celle de V4.

### Dépendances

- `rapidfuzz` — fuzzy matching dans `MediaIndex.find()` (fallback, voir [docs/rapidfuzz-reference.md](../rapidfuzz-reference.md))
- `rsync` (subprocess, pré-installé macOS) — transferts cross-filesystem robustes (reprise, checksum, progress)
- Stdlib pour le reste (`json`, `shutil`, `pathlib`, `xml.etree`, `subprocess`)

## Interfaces

### `media_index.py` — Index des médias

```python
@dataclass
class IndexEntry:
    """A single media entry in the index."""
    name: str                  # Normalized name
    disk: str                  # "Disk1", "Disk2", etc.
    category: str              # "films", "series", "films animations", etc.
    path: str                  # Full path on disk
    media_type: str            # "movie" | "tvshow"
    last_updated: str          # ISO datetime

class MediaIndex:
    """JSON-based index of all media across storage disks."""

    INDEX_PATH = Path("~/.personalscraper/media_index.json").expanduser()
    # Cohérent avec V1 tracker : ~/.personalscraper/ingested_torrents.json

    def __init__(self):
        ...

    def load(self) -> None:
        """Load index from JSON file."""

    def save(self) -> None:
        """Save index to JSON file. Uses atomic write (write .tmp then os.rename)."""

    def rebuild(self, disks: list[DiskConfig]) -> int:
        """Full rebuild: scan all disks. Returns entry count."""

    def find(self, name: str, media_type: str) -> IndexEntry | None:
        """Find a media by normalized name.
        Strategy: exact dict lookup first, rapidfuzz WRatio fallback (score >= 85).
        Uses media_processor from confidence.py for accent-insensitive matching."""

    def add(self, entry: IndexEntry) -> None:
        """Add or update an entry."""

    def remove_stale(self, disks: list[DiskConfig]) -> int:
        """Remove entries for paths that no longer exist. Returns count."""
```

### `disk_scanner.py` — Scan des disques

```python
@dataclass
class DiskConfig:
    """Configuration for a storage disk."""
    name: str                     # "Disk1"
    path: Path                    # /Volumes/Disk1/medias
    categories: list[str]         # ["films", "series", "films animations", ...]

@dataclass
class DiskStatus:
    """Current status of a disk."""
    config: DiskConfig
    free_space_gb: float
    is_mounted: bool

def get_disk_configs(settings: Settings) -> list[DiskConfig]:
    """Build disk configs from settings. Category mapping from config file."""

def get_disk_status(config: DiskConfig) -> DiskStatus:
    """Get current free space and mount status."""

def choose_disk(
    disks: list[DiskStatus],
    category: str,
    min_free_gb: int,
) -> DiskStatus | None:
    """Choose the best disk for a new media item.
    Filters: is_mounted, has_category, free_space >= min_free_gb + item_size.
    Sorts: most free space first.
    Returns None if no disk qualifies."""
```

### `dispatcher.py` — Orchestrateur

> **Catégorisation** : V5 ne fait PAS de mapping genre→catégorie.
> La catégorie est fournie par V4 (verify) dans `VerifyResult.category`.
> V5 utilise `from personalscraper.genre_mapper import GenreMapper` uniquement
> en mode standalone (si V5 est exécuté sans V4, fallback sur le genre_mapper directement).

```python
@dataclass
class DispatchResult:
    """Result of dispatching a single media item."""
    source: Path
    destination: Path | None     # None if skipped
    disk: str | None
    action: str                  # "replaced", "merged", "moved", "skipped", "error"
    reason: str | None = None    # Why skipped/error
    files_copied: int = 0
    size_mb: float = 0

class Dispatcher:
    """Main dispatch orchestrator."""

    def __init__(self, settings: Settings, index: MediaIndex,
                 dry_run: bool = False):
        ...

    def process(self, verified: list["VerifyResult"] | None = None,
                staging_dir: Path | None = None) -> list[DispatchResult]:
        """Dispatch verified media to storage disks.
        If verified provided: dispatch only valid/fixed items (V4 output).
        If staging_dir provided (standalone mode): scan filesystem + categorize via genre_mapper fallback.
        At least one of verified/staging_dir must be provided."""

    def dispatch_movie(self, movie_dir: Path, category: str) -> DispatchResult:
        """Dispatch a movie:
        1. Category already determined by V4 (passed as parameter)
        2. Search index for existing
        3. If found → replace (delete old, move new)
        4. If new → choose_disk(most free space) → move
        """

    def dispatch_tvshow(self, show_dir: Path, category: str) -> DispatchResult:
        """Dispatch a TV show:
        1. Category already determined by V4 (passed as parameter)
        2. Search index for existing
        3. If found → merge (copy new files only)
        4. If new → choose_disk(most free space) → move
        """

    def _replace(self, source: Path, dest: Path) -> DispatchResult:
        """Safe cross-filesystem replace via rsync.

        ⚠️ source (SSD A TRIER) et dest (Disk1-4) sont sur des filesystems différents.
        os.rename() échoue en cross-device. shutil.move() fait copy+delete non-atomique.

        Algorithme crash-safe :
        1. rsync source → dest.new.tmp/ sur le disque destination (même FS que dest)
           - `rsync -a --partial --checksum source/ dest.new.tmp/`
           - --partial : garde les fichiers partiels pour reprise si interrompu
           - --checksum : vérifie l'intégrité après transfert
        2. os.rename(dest, dest.old.tmp) — atomique (même filesystem)
        3. os.rename(dest.new.tmp, dest) — atomique (même filesystem)
        4. shutil.rmtree(dest.old.tmp) — nettoyage de l'ancien
        5. Supprimer la source dans A TRIER/

        Recovery :
        - Crash en étape 1 : seul dest.new.tmp partiel existe, dest intact → re-run rsync reprend
        - Crash en étape 2 : dest.old.tmp + dest.new.tmp existent → détecter au prochain run
        - Crash en étape 4 : dest est OK, dest.old.tmp reste → nettoyage au prochain run
        """

    def _merge(self, source: Path, dest: Path) -> DispatchResult:
        """Merge séries TV avec backup des fichiers écrasés.

        ⚠️ Le merge écrase potentiellement des épisodes existants (même nom → overwrite).
        Sans backup, un merge échoué = perte de données irréversible.

        Algorithme avec rollback :
        1. Lister les fichiers dans source qui existent déjà dans dest
        2. Copier ces fichiers existants dans dest/.merge-backup-{timestamp}/
        3. rsync source → dest avec `rsync -a --partial --checksum`
           (dirs_exist_ok est le comportement par défaut de rsync)
        4. Vérifier l'intégrité (tailles des fichiers copiés)
        5. Si OK → supprimer dest/.merge-backup-{timestamp}/ et la source
        6. Si ERREUR → restaurer depuis le backup, log ERROR

        Gère la structure Saison XX/ récursivement.
        Copie aussi les fichiers associés (.srt, .sub, .idx) aux côtés des vidéos."""

    def _rsync(self, source: Path, dest: Path, delete: bool = False) -> bool:
        """Wrapper rsync pour transferts cross-filesystem.
        Args:
            source: chemin source (avec trailing slash pour contenu)
            dest: chemin destination
            delete: si True, supprime les fichiers dans dest absents de source
        Returns: True si succès (returncode 0).
        Raises: DispatchError si rsync absent ou returncode non-0."""

    def _verify_transfer(self, source: Path, dest: Path) -> bool:
        """Verify file sizes match after transfer (recursive for directories).
        Pour chaque fichier dans source, vérifier que le fichier correspondant
        dans dest a la même taille. Retourne False au premier mismatch."""

    def _cleanup_stale_temps(self, disk_path: Path) -> None:
        """Nettoyer les .new.tmp, .old.tmp, .merge-backup-* orphelins
        laissés par des runs précédents interrompus."""
```

## Flux de données

```
V4 VerifyResult[]                 (category déjà calculée par V4)
        │                                   │
  ┌─────┴─────────────┐            ┌────────┴──────────────┐
  │ movie_dir + category│           │ show_dir + category    │
  └─────┬─────────────┘            └────────┬──────────────┘
       │                                 │
       ▼                                 ▼
┌──────────────┐                  ┌──────────────┐
│ index.find() │                  │ index.find() │
└──────┬───────┘                  └──────┬───────┘
       │                                 │
   ┌───┴───┐                         ┌───┴───┐
  found   new                       found   new
   │       │                         │       │
   ▼       ▼                         ▼       ▼
REPLACE  choose_disk()            MERGE   choose_disk()
   │       │                         │       │
   ▼       ▼                         ▼       ▼
 move    move                     copy    move
   │       │                      files     │
   └───┬───┘                         └──┬──┘
       │                                │
       ▼                                ▼
  index.add()                     index.add()
       │                                │
       ▼                                ▼
  DispatchResult                  DispatchResult
```

## Configuration — Disk category mapping

```python
# In config.py or separate config file
DISK_CATEGORIES = {
    "Disk1": ["films", "films animations", "films documentaires", "livres audios",
              "series", "series animations", "series documentaires",
              "spectacles", "theatres", "emissions"],
    "Disk2": ["series", "series animes"],
    "Disk3": ["films", "films animations", "films documentaires", "livres audios",
              "series", "series animations", "series documentaires",
              "spectacles", "theatres", "emissions"],
    "Disk4": ["films", "films animations", "series", "series animations",
              "series documentaires", "emissions"],
}
```

## Gestion d'erreurs

| Situation                                          | Comportement                                                                                    |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Disque non monté                                   | Skip ce disque, log WARNING                                                                     |
| Espace insuffisant (< max(100 Go, item_size\*1.5)) | Skip + WARNING + notification                                                                   |
| Aucun disque compatible                            | Skip + WARNING + notification, média reste dans A TRIER/                                        |
| .nfo absent (pas de genre)                         | Ne devrait pas arriver si V4 a bloqué. En mode standalone : catégorie par défaut (films/series) |
| rsync échoue (returncode != 0)                     | Log ERROR, ne pas supprimer la source, continuer. dest.new.tmp nettoyé au prochain run          |
| rsync absent (macOS minimal)                       | Erreur fatale au \_\_init\_\_, message clair "rsync required"                                   |
| Vérification post-rsync échoue                     | Log ERROR, garder source et dest, signaler                                                      |
| Merge échoue à mi-chemin                           | Restaurer depuis .merge-backup-{timestamp}/, log ERROR, garder source                           |
| Index corrompu                                     | Recréer l'index (rebuild), log WARNING                                                          |
