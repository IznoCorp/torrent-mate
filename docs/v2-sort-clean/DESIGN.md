# V2 — SORT + CLEAN : Design

> Tri automatique des fichiers par type + nettoyage agressif des noms

## Architecture

### Fichiers

```
personalscraper/sorter/
├── __init__.py
├── cleaner.py           # Regex-based name cleaner (remplace clean_words.txt)
├── file_type.py         # FileType enum + detection (from FileMate)
├── strategies.py        # Movie/TVShow/Default strategies (from FileMate)
├── matcher.py           # Fuzzy directory matching (from FileMate)
├── sorter.py            # Main sorting orchestrator
└── naming_patterns.py   # Configurable naming pattern loader
```

### Dépendances

Aucune dépendance supplémentaire au-delà de V0.
Tout est stdlib (`re`, `pathlib`, `shutil`, `dataclasses`).

## Interfaces

### `cleaner.py` — Nettoyage regex des noms

```python
class NameCleaner:
    """Regex-based media filename cleaner."""

    # Pattern categories compiled at init
    RESOLUTION: re.Pattern    # 1080p, 720p, 2160p, 4K, UHD
    CODEC: re.Pattern         # [HhXx]26[45], HEVC, AVC, AV1, VP9
    AUDIO: re.Pattern         # DDP?\d?\.\d, AC3, DTS, AAC, Atmos, EAC3, TrueHD
    SOURCE: re.Pattern        # WEB(-?DL|-?Rip)?, Blu-?Ray, BDRip, AMZN, NF, DSNP
    VIDEO_PROPS: re.Pattern   # HDR\d*, DV, Dolby.Vision, 10bit
    LANGUAGE: re.Pattern      # MULTi, VFF?, VOST(FR)?, FRENCH, TRUEFRENCH
    RELEASE_GROUP: re.Pattern # -[A-Za-z0-9]+$ (trailing group tag)
    MISC: re.Pattern          # REPACK, PROPER, EXTENDED, INTERNAL, COMPLETE

    def clean(self, name: str) -> str:
        """Clean a media filename. Returns title only (+ year/season/episode preserved).
        Input:  'Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX'
        Output: 'Shrinking S03'
        """

    def extract_year(self, name: str) -> int | None:
        """Extract 4-digit year (1900-2099) from name."""

    def extract_season_episode(self, name: str) -> tuple[int | None, int | None]:
        """Extract season and episode numbers.
        Supports: S01E04, s01e04, 1x04, Saison 1 Episode 4, S03"""

    def clean_for_folder(self, name: str) -> str:
        """Clean name for folder creation: 'Title (Year)' or 'Title'."""
```

### `file_type.py` — Détection de type

```python
class FileType(Enum):
    MOVIE = "movie"
    TVSHOW = "tvshow"
    EBOOK = "ebook"
    AUDIO = "audio"
    APP = "app"
    OTHER = "other"

def detect_file_type(path: Path) -> FileType:
    """Detect media type from file extension and name patterns.
    Video + season/episode pattern → TVSHOW
    Video without pattern → MOVIE
    """

def detect_dir_type(path: Path) -> FileType:
    """Detect type from directory contents (majority vote on children)."""
```

### `strategies.py` — Stratégies de destination

```python
class SortingStrategy(ABC):
    @abstractmethod
    def get_destination(self, name: str, staging_dir: Path) -> Path: ...

class MovieStrategy(SortingStrategy):
    """Destination: staging_dir/001-MOVIES/Title (Year)/"""

class TVShowStrategy(SortingStrategy):
    """Destination: staging_dir/002-TVSHOWS/Show Name/
    Uses fuzzy matching to find existing show folders."""

class DefaultStrategy(SortingStrategy):
    """Destination: staging_dir/{type_dir}/"""
```

### `matcher.py` — Fuzzy directory matching

```python
def find_matching_directory(
    name: str,
    candidates: list[Path],
    respect_year: bool = True,
) -> Path | None:
    """Bidirectional token matching to find existing directory.
    Prevents duplicates like 'The Matrix (1999)' vs 'The Matrix Remastered (1999)'.
    From FileMate, conservé tel quel."""
```

### `sorter.py` — Orchestrateur

```python
@dataclass
class SortResult:
    """Result of sorting a single media item."""
    source: Path
    destination: Path
    media_type: FileType
    title: str
    year: int | None
    season: int | None
    episode: int | None
    action: str  # "moved", "skipped", "error"
    error: str | None = None

class Sorter:
    """Main sorting orchestrator."""

    def __init__(self, settings: Settings, cleaner: NameCleaner, dry_run: bool = False):
        ...

    def process(self, staging_dir: Path) -> list[SortResult]:
        """Sort all items at the root of staging_dir into type subdirectories.
        Returns list of SortResult for each processed item."""

    def sort_item(self, item: Path) -> SortResult:
        """Sort a single file or directory."""
```

**Changement clé vs FileMate** : `process()` retourne `list[SortResult]` au lieu de None.

## Flux de données

```
Racine A TRIER/
    │
    ├── Shrinking.S03.MULTi.1080p...-R3MiX/
    ├── The.Boys.S05E01.MULTi...-R3MiX/
    └── Your.Friends...H265-TFA.mkv
         │
         ▼
┌─────────────────┐
│  detect_type()  │ → TVSHOW / MOVIE / ...
└────────┬────────┘
         │
┌────────▼────────┐
│  cleaner.clean()│ → "Shrinking S03" / "The Boys S05E01"
│  extract_year() │ → None / 2025
└────────┬────────┘
         │
┌────────▼────────────────┐
│  strategy.get_dest()    │ → 002-TVSHOWS/Shrinking/
│  matcher.find_match()   │ → (fuzzy match existing dirs)
└────────┬────────────────┘
         │
┌────────▼────────┐
│  shutil.move()  │ (ou log en dry-run)
└────────┬────────┘
         │
         ▼
    SortResult{source, destination, type, title, year, ...}
```

## Gestion d'erreurs

| Situation                                   | Comportement                                  |
| ------------------------------------------- | --------------------------------------------- |
| Fichier/dossier déjà existant à destination | Log WARNING, skip                             |
| Type non reconnu                            | Sort vers `098-AUTRES/`                       |
| Nom impossible à nettoyer                   | Garder le nom original, log WARNING           |
| Permission denied sur move                  | Log ERROR pour cet item, continuer les autres |
| Dossier vide                                | Skip, log INFO                                |
