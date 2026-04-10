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
- `ffprobe` (via `subprocess`) — extraction codec/resolution/audio (installé via `brew install ffmpeg`, pas de dep Python)
- `xml.etree.ElementTree` (stdlib) — génération NFO XML

## Interfaces

### `tmdb_client.py` — Client TMDB

> Ref : [docs/TMDB-API.md](../TMDB-API.md)

```python
class TMDBClient:
    """Client for The Movie Database API v3."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, language: str = "fr-FR"):
        """Auth par Bearer token (recommandé) ou api_key query param."""
        ...

    def search_movie(self, title: str, year: int | None = None) -> list[dict]:
        """GET /search/movie — returns list of results.
        ⚠️ Le param 'year' booste la pertinence mais n'exclut PAS les autres années.
        Filtrer côté client par release_date si besoin d'un filtre strict.
        Réponse vide = HTTP 200 avec results:[] (pas 404)."""

    def get_movie(self, movie_id: int) -> dict:
        """GET /movie/{id}?append_to_response=credits,images,external_ids,release_dates
        &include_image_language=fr,en,null
        ⚠️ include_image_language est OBLIGATOIRE sinon 5x-31x moins d'images.
        release_dates nécessaire pour extraire la certification FR (type=3 theatrical).
        Ref : docs/TMDB-API.md#certifications-fr--extraction"""

    def search_tv(self, title: str, year: int | None = None) -> list[dict]:
        """GET /search/tv — fallback for TV shows.
        Utilise first_air_date_year (pas year) pour les séries."""

    def get_tv(self, tv_id: int) -> dict:
        """GET /tv/{id}?append_to_response=aggregate_credits,images,external_ids,content_ratings
        &include_image_language=fr,en,null
        ⚠️ Utiliser aggregate_credits (pas credits) pour les séries — regroupe les rôles multiples.
        ⚠️ episode_run_time est vide pour les séries récentes → utiliser runtime par épisode."""

    def get_tv_season(self, tv_id: int, season: int) -> dict:
        """GET /tv/{id}/season/{season}?append_to_response=images
        Retourne tous les épisodes avec crew + guest_stars + runtime par épisode."""

    def get_image_url(self, path: str, size: str = "original") -> str:
        """Build full image URL: https://image.tmdb.org/t/p/{size}{path}"""
```

### `tvdb_client.py` — Client TVDB

> Ref : [docs/TVDB-API.md](../TVDB-API.md)

```python
class TVDBClient:
    """Client for TheTVDB API v4."""

    BASE_URL = "https://api4.thetvdb.com/v4"

    # Mapping langue TMDB → TVDB (pas d'API pour ça, shortCode toujours null)
    LANG_MAP = {"fr": "fra", "en": "eng", "es": "spa", "de": "deu", "it": "ita", "ja": "jpn"}

    def __init__(self, api_key: str):
        ...

    def login(self) -> None:
        """POST /login — obtain bearer token (clé Negotiated Contract, pas de PIN).
        Token valide 1 mois. Re-login automatique sur HTTP 401."""

    def search_series(self, title: str, year: int | None = None) -> list[dict]:
        """GET /search?query={title}&type=series[&year={year}]
        ⚠️ La recherche retourne des résultats en snake_case (image_url, first_air_time, tvdb_id)
        alors que les endpoints entity utilisent du camelCase."""

    def get_series(self, series_id: int) -> dict:
        """GET /series/{id}/extended?short=true — détails + genres + seasons + remoteIds + contentRatings.
        short=true exclut artworks/characters/trailers (réduit le payload).
        ⚠️ Les champs audioLanguages/subtitleLanguages/spokenLanguages n'existent PAS."""

    def get_season_episodes(self, series_id: int, season: int) -> list[dict]:
        """GET /series/{id}/episodes/default?season={season}&page=0
        ⚠️ Pagination 0-indexed. Sans ?season=N, retourne TOUS les épisodes (spéciaux inclus)."""

    def get_episode_translations(self, episode_id: int, lang: str = "fra") -> dict:
        """GET /episodes/{id}/translations/{lang} — titre et synopsis traduits.
        ⚠️ Codes langue 3 chars : fra, eng, spa (pas fr, en, es)."""

    def get_series_artworks(self, series_id: int, type_id: int | None = None) -> list[dict]:
        """GET /series/{id}/artworks[?type={type_id}]
        ⚠️ Retourne un SeriesExtendedRecord (pas juste les artworks).
        Type IDs vérifiés : 2=Poster série, 3=Background série, 7=Poster saison.
        Pas de 'landscape' dans TVDB — Background (1920×1080) est l'équivalent.
        Ref : docs/TVDB-API.md#types-dartwork"""

    def get_remote_ids(self, series_data: dict) -> dict:
        """Extraire IMDB/TMDB IDs depuis remoteIds[].
        ⚠️ TMDB a 4 source type IDs : 10=films, 12=séries TV, 15=personnes, 28=collections.
        Utiliser sourceName='TheMovieDB.com' + type=12 pour les séries."""
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

### `mediainfo.py` — Extraction streamdetails via ffprobe

```python
import subprocess
import json

def extract_stream_info(video_path: Path) -> dict | None:
    """Extract video/audio/subtitle info from a video file using ffprobe.
    Calls: ffprobe -v quiet -print_format json -show_streams -show_format <path>
    Returns dict compatible with NFO <streamdetails> format:
    {
        "video": {
            "codec": "hevc",
            "width": 3840,
            "height": 2160,
            "aspect": 1.778,          # Converti de "16:9" → decimal
            "scantype": "progressive", # Depuis field_order (progressive/interlaced)
            "durationinseconds": 7627, # round(float(format.duration))
        },
        "audio": [
            {"language": "fra", "codec": "eac3", "channels": 6},
            {"language": "eng", "codec": "atmos", "channels": 6},  # EAC3+Atmos → "atmos"
        ],
        "subtitle": [{"language": "fra"}, {"language": "eng"}]
    }
    Returns None if ffprobe not available or file unreadable.

    ⚠️ Conversions critiques (voir docs/ffprobe-reference.md) :
    - Langue ISO 639-2/B → 639-2/T : ffprobe retourne "fre", Kodi attend "fra" (20 codes)
    - Aspect ratio : "16:9" → 1.778 (division + round(3))
    - Durée : round(float(format.duration)), cohérent avec MediaElch
    - EAC3 + profile Atmos → codec "atmos" dans le NFO
    - Scantype : field_order "progressive"/"tt"/"bb" → "progressive"/"interlaced"
    """

# ISO 639-2/B → 639-2/T mapping (codes qui diffèrent)
LANG_B_TO_T = {
    "alb": "sqi", "arm": "hye", "baq": "eus", "bur": "mya",
    "chi": "zho", "cze": "ces", "dut": "nld", "fre": "fra",
    "geo": "kat", "ger": "deu", "gre": "ell", "ice": "isl",
    "mac": "mkd", "mao": "mri", "may": "msa", "per": "fas",
    "rum": "ron", "slo": "slk", "tib": "bod", "wel": "cym",
}

def _normalize_language(lang: str) -> str:
    """Convert ISO 639-2/B to 639-2/T. 'fre' → 'fra', 'ger' → 'deu'."""
    return LANG_B_TO_T.get(lang, lang)

def _parse_aspect_ratio(ratio_str: str) -> float:
    """Convert '16:9' → 1.778, '4:3' → 1.333."""
    num, den = ratio_str.split(":")
    return round(int(num) / int(den), 3)
```

> Ref : [docs/ffprobe-reference.md](../ffprobe-reference.md) — sections 9 (codec mapping), 4-6 (extraction)
>
> Points critiques documentés :
>
> - **Langue** : ffprobe retourne ISO 639-2/B (`fre`), Kodi NFO attend 639-2/T (`fra`) — 20 codes diffèrent
> - **Aspect ratio** : ffprobe retourne `"16:9"`, NFO attend `1.778` decimal
> - **Durée** : `round(float(format.duration))` pour correspondre à MediaElch
> - **Dolby Atmos** : EAC3 avec `profile="Dolby Digital Plus + Dolby Atmos"` → codec `"atmos"`
> - **Performance** : ~65ms par fichier (lecture headers uniquement, pas le contenu)

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

    # Pas de load() depuis fichier — ces patterns sont des standards Kodi/MediaElch
    # et ne changent pas. Si un besoin de personnalisation apparaît, trivial à ajouter.
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
│ mediainfo    │────▶│   ffprobe   │
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
| ffprobe indisponible                | Générer NFO sans `<streamdetails>`, log WARNING |
| Épisode non trouvé dans l'API       | Garder le nom original, log WARNING             |
| Rate limit API                      | Respecter les headers Retry-After, backoff      |
