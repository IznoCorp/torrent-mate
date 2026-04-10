# V4 — DISPATCH : Design

> Déplacement intelligent des médias vers Disk1-4 (merge séries, replace films, free space)

## Architecture

### Fichiers

```
personalscraper/dispatch/
├── __init__.py
├── media_index.py      # Index JSON des médias sur les 4 disques
├── disk_scanner.py     # Scan des disques, espace libre, catégories
├── genre_mapper.py     # Mapping genre TMDB/TVDB → sous-type (animation, anime, etc.)
└── dispatcher.py       # Orchestrateur dispatch (replace/merge/new)
```

### Dépendances

Aucune dépendance supplémentaire. Stdlib uniquement (`json`, `shutil`, `pathlib`, `xml.etree`).

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
        """Save index to JSON file."""

    def rebuild(self, disks: list[DiskConfig]) -> int:
        """Full rebuild: scan all disks. Returns entry count."""

    def find(self, name: str, media_type: str) -> IndexEntry | None:
        """Find a media by normalized name. Uses fuzzy matching."""

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

### `genre_mapper.py` — Mapping genre → sous-type

```python
# Default mapping (configurable)
GENRE_TO_SUBTYPE = {
    # Movies
    ("movie", "Animation"): "films animations",
    ("movie", "Documentaire"): "films documentaires",
    ("movie", "Documentary"): "films documentaires",
    ("movie", None): "films",  # default

    # TV Shows
    # Anime detection: V3 includes <country> from API origin_country in tvshow.nfo
    # If country contains "JP" + genre "Animation" → anime
    ("tvshow", "Animation", "JP"): "series animes",
    ("tvshow", "Animation"): "series animations",
    ("tvshow", "Documentaire"): "series documentaires",
    ("tvshow", "Documentary"): "series documentaires",
    ("tvshow", None): "series",  # default
}

def determine_category(
    media_type: str,
    nfo_path: Path,
) -> str:
    """Read genre from .nfo XML, map to disk category.
    Falls back to default if genre not in mapping."""
```

> **Limites de la détection anime** :
>
> - L'heuristique `Animation + JP` est une approximation. Certains animes sont co-produits
>   hors Japon (Netflix originals, co-productions), et `origin_country` peut ne pas contenir "JP".
> - TMDB utilise `origin_country` (code ISO "JP"), TVDB peut utiliser un nom complet ("Japan")
>   — normaliser les deux formats dans le mapper.
> - Le terme "anime" est souvent un tag communautaire, pas un genre officiel API.
> - Pour les cas ambigus, l'utilisateur peut déplacer manuellement ou ajouter un override
>   dans le mapping configurable.

### `dispatcher.py` — Orchestrateur

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

    def process(self, staging_dir: Path) -> list[DispatchResult]:
        """Dispatch all media from 001-MOVIES/ and 002-TVSHOWS/."""

    def dispatch_movie(self, movie_dir: Path) -> DispatchResult:
        """Dispatch a movie:
        1. Read genre from .nfo → determine category
        2. Search index for existing
        3. If found → replace (delete old, move new)
        4. If new → choose_disk(most free space) → move
        """

    def dispatch_tvshow(self, show_dir: Path) -> DispatchResult:
        """Dispatch a TV show:
        1. Read genre from .nfo → determine category
        2. Search index for existing
        3. If found → merge (copy new files only)
        4. If new → choose_disk(most free space) → move
        """

    def _replace(self, source: Path, dest: Path) -> DispatchResult:
        """Delete dest, move source to dest."""

    def _merge(self, source: Path, dest: Path) -> DispatchResult:
        """Copy files from source that don't exist in dest (or same name → overwrite)."""

    def _verify_transfer(self, source: Path, dest: Path) -> bool:
        """Verify file sizes match after transfer."""
```

## Flux de données

```
001-MOVIES/Title (Year)/          002-TVSHOWS/Show Name (Year)/
        │                                   │
        ▼                                   ▼
┌──────────────┐                  ┌──────────────┐
│ read .nfo    │                  │ read .nfo    │
│ → genre      │                  │ → genre      │
└──────┬───────┘                  └──────┬───────┘
       │                                 │
       ▼                                 ▼
┌──────────────┐                  ┌──────────────┐
│ genre_mapper │                  │ genre_mapper │
│ → category   │                  │ → category   │
└──────┬───────┘                  └──────┬───────┘
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

| Situation                     | Comportement                                             |
| ----------------------------- | -------------------------------------------------------- |
| Disque non monté              | Skip ce disque, log WARNING                              |
| Espace insuffisant (< 100 Go) | Skip + WARNING + notification                            |
| Aucun disque compatible       | Skip + WARNING + notification, média reste dans A TRIER/ |
| .nfo absent (pas de genre)    | Utiliser la catégorie par défaut (films/series)          |
| Erreur pendant le move        | Log ERROR, ne pas supprimer la source, continuer         |
| Vérification post-move échoue | Log ERROR, garder source et dest, signaler               |
| Index corrompu                | Recréer l'index (rebuild), log WARNING                   |
