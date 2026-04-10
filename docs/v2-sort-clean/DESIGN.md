# V2 — SORT + CLEAN : Design

> Tri automatique des fichiers par type + nettoyage agressif des noms

## Architecture

### Fichiers

```
personalscraper/sorter/
├── __init__.py
├── cleaner.py           # Nettoyage noms via guessit (voir docs/guessit-evaluation.md)
├── file_type.py         # FileType enum + detection (guessit type + extensions FileMate)
├── strategies.py        # Movie/TVShow/Default strategies (from FileMate)
├── matcher.py           # Fuzzy directory matching (from FileMate)
└── sorter.py            # Main sorting orchestrator
```

### Dépendances

- `guessit>=3.8.0` — parsing de noms media (ajouté dans V0 `pyproject.toml`)
- `rapidfuzz>=3.14.0` — fuzzy matching dossiers existants (ajouté dans V0 `pyproject.toml`)
- Stdlib pour le reste (`pathlib`, `shutil`, `dataclasses`)

## Interfaces

### `cleaner.py` — Nettoyage via guessit

```python
from guessit import guessit as guess

class NameCleaner:
    """Media filename cleaner powered by guessit.
    Remplace le système regex custom par guessit (moteur de règles)
    qui gère 140+ streaming services, titres avec chiffres/années,
    conventions françaises (VFF, VOSTFR, TRUEFRENCH, MULTi, Saison).
    Voir docs/guessit-evaluation.md pour l'évaluation complète.
    """

    def clean(self, name: str) -> str:
        """Clean a media filename. Returns title only (+ season/episode preserved).
        Input:  'Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX'
        Output: 'Shrinking S03'
        """
        r = guess(name)
        title = r.get("title", name)
        season = r.get("season")
        episode = r.get("episode")
        if season and episode:
            return f"{title} S{season:02d}E{episode:02d}"
        if season:
            return f"{title} S{season:02d}"
        return title

    def extract_year(self, name: str) -> int | None:
        """Extract year from name via guessit."""
        return guess(name).get("year")

    def extract_season_episode(self, name: str) -> tuple[int | None, int | None]:
        """Extract season and episode numbers.
        Supports: S01E04, s01e04, 1x04, Saison 1 Episode 4, S03, double episodes."""
        r = guess(name)
        return r.get("season"), r.get("episode")

    def clean_for_folder(self, name: str) -> str:
        """Clean name for folder creation: 'Title (Year)' or 'Title'."""
        r = guess(name)
        title = r.get("title", name)
        year = r.get("year")
        return f"{title} ({year})" if year else title

    def get_media_type(self, name: str) -> str | None:
        """Return guessit media type: 'movie' or 'episode', or None if unknown.
        Used by file_type.py to reinforce movie vs tvshow detection."""
        return guess(name).get("type")
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
    """Detect media type from file extension + guessit type.
    1. Extension non-vidéo → EBOOK/AUDIO/APP/OTHER (logique FileMate)
    2. Extension vidéo → guessit(name).get("type"):
       - "episode" → TVSHOW (guessit détecte S01E04, Saison, etc.)
       - "movie" → MOVIE
       - fallback extension-only si guessit ne sait pas
    Voir docs/guessit-evaluation.md — guessit détecte aussi les packs saison (S01-S08).
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
    V2 crée les dossiers séries SANS année (`Show Name/`) — l'année est ajoutée par V3 après matching API.
    Uses fuzzy matching to find existing show folders."""

class DefaultStrategy(SortingStrategy):
    """Destination: staging_dir/{type_dir}/"""
```

### `matcher.py` — Fuzzy directory matching (rapidfuzz)

> **Changement vs FileMate** : le matcher bidirectionnel custom est remplacé par `rapidfuzz.fuzz.WRatio`
> avec le `media_processor` custom (normalisation accents FR). Cela unifie le matching
> entre V2 (dossiers existants), V3 (titres API), et V5 (index média).
> Ref : [docs/rapidfuzz-reference.md](../rapidfuzz-reference.md)

```python
from rapidfuzz import fuzz, process
from personalscraper.text_utils import media_processor

# media_processor(s: str) -> str
# Défini dans `personalscraper/text_utils.py` (module partagé).
# Import : `from personalscraper.text_utils import media_processor`
# Normalise pour le matching média : lowercase, NFD decomposition (accents FR),
# suppression ponctuation. Partagé avec V3/V5.

def find_matching_directory(
    name: str,
    candidates: list[Path],
    respect_year: bool = True,
    threshold: float = 85.0,
) -> Path | None:
    """Find best matching existing directory via rapidfuzz WRatio.
    Uses media_processor for accent-insensitive French title matching.
    Returns None if best score < threshold.
    If respect_year=True and both names contain a year, years must match."""
```

### `sorter.py` — Orchestrateur

````python
## Note: SortResult est défini dans `personalscraper/models.py` (V0), pas ici.

```python
# from personalscraper.models import SortResult

class Sorter:
    """Main sorting orchestrator."""

    def __init__(self, settings: Settings, cleaner: NameCleaner, dry_run: bool = False):
        ...

    def process(self, staging_dir: Path) -> list[SortResult]:
        """Sort all items at the root of staging_dir into type subdirectories.
        Returns list of SortResult for each processed item."""

    def sort_item(self, item: Path) -> SortResult:
        """Sort a single file or directory."""
````

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
│  find_matching_directory()│ → (fuzzy match existing dirs)
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
