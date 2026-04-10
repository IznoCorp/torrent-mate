# V4 — VERIFY : Design

> Quality gate : vérification, correction et qualification des médias scrapés avant dispatch

## Architecture

### Fichiers

```
personalscraper/verify/
├── __init__.py
├── checker.py           # Vérification d'un dossier média (critères + sévérités)
├── fixer.py             # Corrections automatiques (renommage, restructuration)
└── verifier.py          # Orchestrateur : fix → check → rapport
```

Note : `genre_mapper.py` vit à la racine du package (`personalscraper/genre_mapper.py`)
car il est partagé entre V4 (verify) et V5 (dispatch). Import : `from personalscraper.genre_mapper import GenreMapper`

### Dépendances

- `xml.etree.ElementTree` (stdlib) — parsing NFO XML
- `personalscraper.naming_patterns` (V3) — patterns de nommage de référence
- Aucune dépendance réseau — V4 travaille uniquement sur les fichiers locaux

## Interfaces

### `checker.py` — Vérification d'un dossier

```python
from enum import Enum
from personalscraper.genre_mapper import GenreMapper

class Severity(Enum):
    ERROR = "error"      # Bloque le dispatch
    WARNING = "warning"  # Signalé mais non bloquant

@dataclass
class CheckResult:
    """Résultat d'un check individuel."""
    name: str            # Ex: "nfo_present", "category_identified"
    passed: bool
    severity: Severity
    message: str         # Description du problème si failed
    fixable: bool        # True si auto-corrigeable

class MediaChecker:
    """Vérifie qu'un dossier média est conforme aux standards."""

    def __init__(self, patterns: NamingPatterns, genre_mapper: "GenreMapper"):
        ...

    def check_movie(self, movie_dir: Path) -> list[CheckResult]:
        """Vérifie un dossier film. Critères :
        - video_present : au moins 1 fichier vidéo
        - not_sample : fichier vidéo > 100 Mo (WARNING si < 100 Mo, possible sample)
        - dir_naming : format Title (Year)/
        - nfo_present : Title.nfo existe
        - nfo_valid : XML parseable + tags obligatoires (title, uniqueid tmdb+imdb)
        - artwork_poster : Title-poster.jpg
        - artwork_landscape : Title-landscape.jpg
        - streamdetails : <fileinfo><streamdetails> dans le NFO
        - category : genre → catégorie identifiée
        """

    def check_tvshow(self, show_dir: Path) -> list[CheckResult]:
        """Vérifie un dossier série. Critères :
        - video_present
        - dir_naming : format Show Name (Year)/
        - nfo_present : tvshow.nfo existe
        - nfo_valid : XML + tags (title, uniqueid tvdb)
        - artwork_poster : poster.jpg
        - artwork_landscape : landscape.jpg
        - season_structure : Saison XX/ avec épisodes S01E01 - Titre.ext
        - season_posters : seasonNN-poster.jpg par saison
        - episode_nfo : .nfo par épisode
        - streamdetails : dans les NFO épisode
        - category : genre → catégorie identifiée
        """

    def _parse_nfo(self, nfo_path: Path) -> ET.Element | None:
        """Parse un NFO XML, retourne None si invalide."""

    def _extract_genres(self, nfo_root: ET.Element) -> list[str]:
        """Extraire les <genre> tags du NFO."""

    def _extract_country(self, nfo_root: ET.Element) -> str | None:
        """Extraire le <country> tag du NFO (pour détection anime)."""
```

### `fixer.py` — Corrections automatiques

```python
@dataclass
class FixAction:
    """Description d'une correction appliquée."""
    description: str     # Ex: "Renamed dir 'Fight Club' → 'Fight Club (1999)'"
    old_path: Path
    new_path: Path | None

class MediaFixer:
    """Tente de corriger les problèmes auto-corrigeables."""

    def __init__(self, patterns: NamingPatterns, dry_run: bool = False):
        ...

    def fix_movie(self, movie_dir: Path, checks: list[CheckResult]) -> list[FixAction]:
        """Corrige les problèmes fixables d'un dossier film.
        - dir_naming failed + NFO existe → extraire titre/année du NFO → renommer
        - artwork mal nommé → renommer selon NamingPatterns
        """

    def fix_tvshow(self, show_dir: Path, checks: list[CheckResult]) -> list[FixAction]:
        """Corrige les problèmes fixables d'un dossier série.
        - dir_naming failed + NFO existe → renommer
        - épisodes non renommés mais pattern reconnaissable → renommer
        - artwork mal nommé → renommer
        """
```

### `genre_mapper.py` — Mapping genres → catégories

> **Emplacement** : `personalscraper/genre_mapper.py` (racine du package, partagé V4+V5)
> Import : `from personalscraper.genre_mapper import GenreMapper`

```python
class GenreMapper:
    """Mappe les genres TMDB/TVDB vers les catégories de destination disques.

    Ref :
    - Genres TMDB films : docs/TMDB-API.md#genres-films (19 genres, IDs stables)
    - Genres TMDB TV : docs/TMDB-API.md#genres-tv (16 genres, IDs différents des films)
    - Genres TVDB : docs/TVDB-API.md#genres (36 genres, IDs propres)

    ⚠️ Les IDs de genres sont DIFFÉRENTS entre TMDB films, TMDB TV, et TVDB.
    Ce mapper gère les 3 systèmes.
    """

    # TMDB film genre IDs
    TMDB_ANIMATION = 16
    TMDB_DOCUMENTARY = 99

    # TMDB TV genre IDs (différents des films !)
    TMDB_TV_ANIMATION = 16        # Même ID que film pour Animation
    TMDB_TV_DOCUMENTARY = 99      # Même ID que film pour Documentaire
    TMDB_TV_REALITY = 10764
    TMDB_TV_TALK = 10767
    TMDB_TV_NEWS = 10763

    # TVDB genre IDs
    TVDB_ANIMATION = 17
    TVDB_ANIME = 27
    TVDB_DOCUMENTARY = 3
    TVDB_REALITY = 8
    TVDB_TALK_SHOW = 10
    TVDB_NEWS = 11

    # Catégories connues (frozenset exporté pour validation par V5)
    KNOWN_CATEGORIES: frozenset[str] = frozenset({
        "films", "films animations", "films documentaires",
        "spectacles", "theatres",
        "series", "series animations", "series documentaires",
        "series animes", "emissions",
        "livres audios",
    })
    # Validation : chaque disk.categories doit être un sous-ensemble de KNOWN_CATEGORIES
    # Vérifié au démarrage de V5 dispatch

    def categorize_movie(self, genres: list[str], genre_ids: list[int] | None = None) -> str:
        """Retourne la catégorie film : 'films', 'films animations', 'films documentaires'.
        Utilise genre_ids si dispo (plus fiable), sinon les noms de genres.
        ⚠️ 'spectacles' et 'theatres' ne sont PAS détectables via genres TMDB/TVDB
        → voir categorize_from_nfo() qui check le fichier .category en priorité."""

    def categorize_tvshow(
        self, genres: list[str], genre_ids: list[int] | None = None,
        origin_country: str | None = None, source: str = "tmdb"
    ) -> str:
        """Retourne la catégorie série : 'series', 'series animations', 'series documentaires',
        'series animes', 'emissions'.
        ⚠️ Anime = Animation + origin_country JP (TMDB) ou genre Anime (TVDB).
        ⚠️ source='tmdb' ou 'tvdb' pour utiliser les bons genre IDs."""

    def categorize_from_nfo(self, nfo_path: Path, media_type: str) -> str | None:
        """Déterminer la catégorie d'un dossier média.

        Ordre de priorité :
        1. Fichier `.category` dans le dossier parent du NFO
           → Si présent et contenu ∈ KNOWN_CATEGORIES, retourner directement
           → Ceci permet la catégorisation manuelle des spectacles/théâtres
             (aucun genre TMDB/TVDB ne correspond à ces catégories)
        2. Sinon, parser le NFO XML :
           - Parse <genre> tags → genre names (pas d'IDs dans le NFO)
           - Parse <country> pour détection anime
           - Parse <uniqueid> pour déterminer la source (tmdb/tvdb)
           - Appeler categorize_movie() ou categorize_tvshow()
        3. Retourne None si genres absents ou catégorie non identifiable."""
```

### `verifier.py` — Orchestrateur

```python
@dataclass
class VerifyResult:
    """Résultat de vérification d'un dossier média."""
    media_path: Path
    media_type: str                # "movie" | "tvshow"
    category: str | None           # Catégorie dispatch identifiée
    status: str                    # "valid", "fixed", "blocked"
    errors: list[str]              # Erreurs bloquantes restantes
    warnings: list[str]            # Avertissements non bloquants
    fixes_applied: list[str]       # Corrections effectuées

class Verifier:
    """Orchestrateur verify : fix → check → rapport."""

    def __init__(self, settings: Settings, patterns: NamingPatterns,
                 dry_run: bool = False, fix: bool = True):
        ...

    def verify_movie(self, movie_dir: Path) -> VerifyResult:
        """Vérifie un dossier film :
        1. check_movie() → première passe
        2. Si fix=True et problèmes fixables → fix_movie()
        3. check_movie() → deuxième passe (après fixes)
        4. Catégoriser via genre_mapper
        5. Retourner VerifyResult
        """

    def verify_tvshow(self, show_dir: Path) -> VerifyResult:
        """Vérifie un dossier série (même logique que film)."""

    def verify_all_movies(self, movies_dir: Path) -> list[VerifyResult]:
        """Vérifier tous les sous-dossiers de 001-MOVIES/."""

    def verify_all_tvshows(self, tvshows_dir: Path) -> list[VerifyResult]:
        """Vérifier tous les sous-dossiers de 002-TVSHOWS/."""

    def get_dispatchable(self, results: list[VerifyResult]) -> list[VerifyResult]:
        """Filtrer les résultats : retourner uniquement status='valid' ou 'fixed'."""
```

## Flux de données

```
001-MOVIES/Title (Year)/
    │
    ▼
┌──────────────┐
│ check_movie  │──▶ list[CheckResult]
└──────┬───────┘
       │ (si fixable)
       ▼
┌──────────────┐
│  fix_movie   │──▶ list[FixAction] (renommages, corrections)
└──────┬───────┘
       │ (re-check)
       ▼
┌──────────────┐
│ check_movie  │──▶ list[CheckResult] (après corrections)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ genre_mapper │──▶ category: "films" | "films animations" | ...
└──────┬───────┘
       │
       ▼
  VerifyResult(status="valid"|"fixed"|"blocked")
```

## Gestion d'erreurs

| Situation                       | Comportement                                         |
| ------------------------------- | ---------------------------------------------------- |
| NFO XML mal formé               | ERROR, pas fixable → blocked                         |
| NFO absent                      | ERROR, pas fixable → blocked (V3 a échoué)           |
| Pas de fichier vidéo            | ERROR, pas fixable → blocked                         |
| Dossier mal nommé + NFO présent | Fixable → renommer dossier depuis titre/année du NFO |
| Artwork manquant                | WARNING → dispatch quand même                        |
| Genre non reconnu / catégorie ? | ERROR → blocked (dispatch ne saurait pas où mettre)  |
| Erreur I/O pendant fix          | Catch, log error, marquer comme non fixé, re-check   |
| Dossier vide                    | ERROR → blocked + log                                |
| Permission denied sur fichier   | ERROR → blocked + log                                |
