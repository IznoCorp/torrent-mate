# V3 — SCRAPE : Design

> Scraping metadata TMDB/TVDB, génération NFO, artwork, renommage épisodes

## Architecture

### Fichiers

```
personalscraper/scraper/
├── __init__.py
├── tmdb_client.py        # Client API TMDB (films + fallback séries)
├── tvdb_client.py        # Client API TVDB (séries principal)
├── nfo_generator.py      # Génération XML NFO Kodi (movie, tvshow, episodedetails)
├── artwork.py            # Téléchargement artwork (poster, landscape, season poster)
├── mediainfo.py          # Extraction streamdetails via pymediainfo
├── confidence.py         # Score de confiance pour le matching
└── scraper.py            # Orchestrateur principal
```

Note : `naming_patterns.py` vit à `personalscraper/naming_patterns.py` (partagé sorter/scraper).

**Important V2→V3** : V2 crée les dossiers TV sans année (`Show Name/`). V3 renomme le dossier
en `Show Name (Year)/` après matching sur TVDB/TMDB (car il connaît maintenant l'année).
V3 re-parse les noms de dossiers indépendamment de V2 (plus résilient aux exécutions indépendantes).

### Dépendances

- `requests` — API calls (déjà dans deps)
- `pymediainfo>=7.0.0` — extraction codec/resolution/audio (déjà dans deps)
- `xml.etree.ElementTree` (stdlib) — génération NFO XML

## Interfaces

### `tmdb_client.py` — Client TMDB

```python
class TMDBClient:
    """Client for The Movie Database API v3."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, language: str = "fr-FR"):
        ...

    def search_movie(self, title: str, year: int | None = None) -> list[dict]:
        """GET /search/movie — returns list of results."""

    def get_movie(self, movie_id: int) -> dict:
        """GET /movie/{id}?append_to_response=credits — full movie details."""

    def get_movie_images(self, movie_id: int) -> dict:
        """GET /movie/{id}/images — posters, backdrops."""

    def search_tv(self, title: str, year: int | None = None) -> list[dict]:
        """GET /search/tv — fallback for TV shows."""

    def get_tv(self, tv_id: int) -> dict:
        """GET /tv/{id}?append_to_response=credits"""

    def get_tv_season(self, tv_id: int, season: int) -> dict:
        """GET /tv/{id}/season/{season} — episode list with titles."""

    def get_tv_images(self, tv_id: int) -> dict:
        """GET /tv/{id}/images"""

    def get_image_url(self, path: str, size: str = "original") -> str:
        """Build full image URL from TMDB path."""
```

### `tvdb_client.py` — Client TVDB

```python
class TVDBClient:
    """Client for TheTVDB API v4."""

    BASE_URL = "https://api4.thetvdb.com/v4"

    def __init__(self, api_key: str):
        ...

    def login(self) -> None:
        """POST /login — obtain bearer token."""

    def search_series(self, title: str) -> list[dict]:
        """GET /search?query={title}&type=series"""

    def get_series(self, series_id: int) -> dict:
        """GET /series/{id}/extended — full details."""

    def get_season_episodes(self, series_id: int, season: int) -> list[dict]:
        """GET /series/{id}/episodes/default/{season}"""

    def get_series_artworks(self, series_id: int) -> list[dict]:
        """GET /series/{id}/artworks — posters, fanart, etc."""
```

### `confidence.py` — Score de confiance

```python
@dataclass
class MatchResult:
    """Result of matching a local media to an API result."""
    api_id: int
    api_title: str
    api_year: int | None
    confidence: float        # 0.0 → 1.0
    source: str              # "tmdb" | "tvdb"

def score_match(
    local_title: str,
    local_year: int | None,
    api_title: str,
    api_year: int | None,
) -> float:
    """Score a match between local and API data.
    1.0 = exact title + exact year
    0.8+ = high confidence (auto-accept)
    0.5-0.8 = medium (interactive only)
    <0.5 = low (skip)
    """

HIGH_CONFIDENCE_THRESHOLD = 0.8
```

### `nfo_generator.py` — Génération NFO XML

```python
class NFOGenerator:
    """Generate Kodi-compatible .nfo XML files (MediaElch format)."""

    def generate_movie_nfo(self, movie_data: dict, stream_info: dict | None) -> str:
        """Generate <movie> NFO XML string."""

    def generate_tvshow_nfo(self, show_data: dict) -> str:
        """Generate <tvshow> NFO XML string."""

    def generate_episode_nfo(self, episode_data: dict, stream_info: dict | None) -> str:
        """Generate <episodedetails> NFO XML string."""

    def write_nfo(self, xml_content: str, path: Path) -> None:
        """Write NFO to file with UTF-8 encoding."""
```

### `artwork.py` — Téléchargement artwork

```python
class ArtworkDownloader:
    """Download artwork images from TMDB/TVDB."""

    def download_image(self, url: str, dest: Path) -> bool:
        """Download image to dest. Returns True on success."""

    def download_movie_artwork(self, movie_data: dict, movie_dir: Path, patterns: NamingPatterns) -> list[Path]:
        """Download poster + landscape for a movie."""

    def download_tvshow_artwork(self, show_data: dict, show_dir: Path, patterns: NamingPatterns) -> list[Path]:
        """Download poster + landscape + season posters for a TV show."""
```

### `mediainfo.py` — Extraction streamdetails

```python
def extract_stream_info(video_path: Path) -> dict | None:
    """Extract video/audio/subtitle info from a video file using pymediainfo.
    Returns dict compatible with NFO <streamdetails> format:
    {
        "video": {"codec": "hevc", "width": 1920, "height": 1080, "aspect": 1.778},
        "audio": [{"language": "fra", "codec": "eac3", "channels": 6}],
        "subtitle": [{"language": "fra"}, {"language": "eng"}]
    }
    Returns None if pymediainfo not available or file unreadable.
    """
```

### `naming_patterns.py` — Patterns de nommage (partagé)

```python
@dataclass
class NamingPatterns:
    """Configurable naming patterns (MediaElch-compatible defaults)."""

    # Directories
    movie_dir: str = "{Title} ({Year})"
    tvshow_dir: str = "{Title} ({Year})"
    season_dir: str = "Saison {Season:02d}"

    # Movie files
    movie_video: str = "{Title}.{ext}"
    movie_nfo: str = "{Title}.nfo"
    movie_poster: str = "{Title}-poster.jpg"
    movie_landscape: str = "{Title}-landscape.jpg"

    # TV show level
    tvshow_nfo: str = "tvshow.nfo"
    tvshow_poster: str = "poster.jpg"
    tvshow_landscape: str = "landscape.jpg"
    season_poster: str = "season{Season:02d}-poster.jpg"

    # Episode files
    episode_video: str = "S{Season:02d}E{Episode:02d} - {EpisodeTitle}.{ext}"
    episode_nfo: str = "S{Season:02d}E{Episode:02d} - {EpisodeTitle}.nfo"
    episode_thumb: str = "S{Season:02d}E{Episode:02d} - {EpisodeTitle}-thumb.jpg"

    def format(self, pattern_name: str, **kwargs) -> str:
        """Format a pattern with given variables."""

    @classmethod
    def load(cls, path: Path | None = None) -> "NamingPatterns":
        """Load patterns from config file, or use defaults."""
```

### `scraper.py` — Orchestrateur

```python
@dataclass
class ScrapeResult:
    """Result of scraping a single media item."""
    media_path: Path
    media_type: str              # "movie" | "tvshow"
    match: MatchResult | None    # None if no match found
    nfo_written: bool
    artwork_downloaded: list[str]
    episodes_renamed: int        # 0 for movies
    action: str                  # "scraped", "skipped_low_confidence", "skipped_already_done", "error"
    error: str | None = None

class Scraper:
    """Main scraping orchestrator."""

    def __init__(self, settings: Settings, patterns: NamingPatterns,
                 dry_run: bool = False, interactive: bool = False):
        ...

    def process_movies(self, movies_dir: Path) -> list[ScrapeResult]:
        """Scrape all movies in 001-MOVIES/."""

    def process_tvshows(self, tvshows_dir: Path) -> list[ScrapeResult]:
        """Scrape all TV shows in 002-TVSHOWS/."""

    def scrape_movie(self, movie_dir: Path) -> ScrapeResult:
        """Scrape a single movie: match → NFO → artwork."""

    def scrape_tvshow(self, show_dir: Path) -> ScrapeResult:
        """Scrape a TV show: match → tvshow.nfo → artwork →
        create Saison XX/ → rename episodes → episode NFO."""

    def _match_movie(self, title: str, year: int | None) -> MatchResult | None:
        """Search TMDB, score confidence, return best match or None."""

    def _match_tvshow(self, title: str, year: int | None) -> MatchResult | None:
        """Search TVDB first, fallback TMDB, score confidence."""

    def _prompt_user(self, results: list[MatchResult]) -> MatchResult | None:
        """Interactive mode: present results, ask user to choose."""
```

## Flux de données

```
001-MOVIES/Title (Year)/
    │
    ▼
┌──────────────┐     ┌───────────┐
│ _match_movie │────▶│ TMDB API  │
│  confidence  │     └───────────┘
└──────┬───────┘
       │ MatchResult (confidence >= 0.8)
       ▼
┌──────────────┐     ┌─────────────┐
│ mediainfo    │────▶│ pymediainfo │
│ .extract()   │     └─────────────┘
└──────┬───────┘
       │ stream_info
       ▼
┌──────────────┐
│ nfo_generator│──▶ Title.nfo
│ artwork      │──▶ Title-poster.jpg, Title-landscape.jpg
└──────────────┘


002-TVSHOWS/Show Name/
    │
    ▼
┌──────────────┐     ┌───────────┐     ┌───────────┐
│ _match_tvshow│────▶│ TVDB API  │────▶│ TMDB API  │ (fallback)
│  confidence  │     └───────────┘     └───────────┘
└──────┬───────┘
       │ MatchResult
       ▼
┌──────────────────────────────┐
│ tvshow.nfo + poster.jpg      │
│ + landscape.jpg              │
│                              │
│ Pour chaque saison détectée: │
│   mkdir Saison XX/           │
│   season poster              │
│   rename episodes            │
│   episode .nfo               │
└──────────────────────────────┘
```

## Gestion d'erreurs

| Situation                           | Comportement                                    |
| ----------------------------------- | ----------------------------------------------- |
| API inaccessible (timeout)          | Retry 3x avec backoff, puis skip + WARNING      |
| Aucun résultat API                  | Skip + log "no match found"                     |
| Confiance faible (< 0.8, mode auto) | Skip + log + ajout au rapport                   |
| Confiance faible (mode interactif)  | Proposer les résultats à l'utilisateur          |
| .nfo déjà existant                  | Skip (ne pas écraser), log INFO                 |
| Artwork déjà existant               | Skip (ne pas re-télécharger), log INFO          |
| pymediainfo indisponible            | Générer NFO sans `<streamdetails>`, log WARNING |
| Épisode non trouvé dans l'API       | Garder le nom original, log WARNING             |
| Rate limit API                      | Respecter les headers Retry-After, backoff      |
