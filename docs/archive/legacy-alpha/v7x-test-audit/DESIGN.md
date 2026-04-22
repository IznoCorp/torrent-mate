# V7.x — TEST AUDIT : Design

> Audit exhaustif des tests + golden files E2E pour valider l'exactitude du scrape et dispatch.

## Architecture

### Fichiers créés

```
tests/
├── e2e/
│   └── golden.py                  # NOUVEAU — GoldenFileLoader + assertions golden file
assets/
└── torrents/
    └── expected/                  # NOUVEAU — Golden files par torrent
        ├── jumanji_1995/
        │   ├── expected_nfo.json
        │   ├── expected_artwork.json
        │   ├── expected_structure.json
        │   └── expected_dispatch.json
        └── malcolm_in_the_middle_s01/
            ├── expected_nfo.json
            ├── expected_artwork.json
            ├── expected_structure.json
            └── expected_dispatch.json
```

### Fichiers modifiés

```
tests/
├── test_cli.py                    # MODIFIÉ — fix test_sort_stub
├── e2e/
│   ├── assertions.py              # MODIFIÉ — intégrer golden file assertions
│   ├── test_pipeline_movies.py    # MODIFIÉ — utiliser golden files
│   └── test_pipeline_tvshows.py   # MODIFIÉ — utiliser golden files
├── dispatch/
│   ├── test_dispatcher.py         # MODIFIÉ — ajouter tests replace/merge/rsync errors
│   └── test_media_index.py        # MODIFIÉ — ajouter tests edge cases
├── ingest/
│   └── test_ingest.py             # NOUVEAU — tests orchestration ingest.py (13% → 70%+)
├── scraper/
│   ├── test_scraper.py            # MODIFIÉ — ajouter tests orchestration
│   └── test_confidence.py         # MODIFIÉ — ajouter tests réponses malformées
└── verify/
    └── test_verifier.py           # MODIFIÉ — ajouter tests cycle check→fix→recheck
```

### Dépendances

Aucune nouvelle dépendance. Utilise `json`, `xml.etree.ElementTree`, `pathlib` (stdlib).

## Interfaces

### 1. Golden File Format

#### expected_nfo.json (Film)

```json
{
  "media_type": "movie",
  "title": "Jumanji",
  "year": 1995,
  "tmdb_id": 8844,
  "imdb_id": "tt0113497",
  "genres": ["Aventure", "Fantastique", "Familial"],
  "expected_category": "films",
  "folder_name_pattern": "Jumanji (1995)",
  "required_nfo_tags": [
    "title",
    "originaltitle",
    "year",
    "tmdbid",
    "imdbid",
    "genre",
    "plot",
    "director",
    "runtime"
  ],
  "nfo_invariants": {
    "title": "Jumanji",
    "year": "1995",
    "tmdbid": "8844",
    "imdbid": "tt0113497"
  }
}
```

`nfo_invariants` = champs dont la VALEUR exacte est vérifiée (IDs, titre, année).
`required_nfo_tags` = tags qui doivent EXISTER dans le XML (pas de vérif valeur).

#### expected_nfo.json (Série TV)

```json
{
  "media_type": "tvshow",
  "title": "Malcolm in the Middle",
  "year": 2000,
  "tvdb_id": "73838",
  "imdb_id": "tt0212671",
  "tmdb_id": 2004,
  "genres": ["Comédie", "Familial"],
  "expected_category": "series",
  "folder_name_pattern": "Malcolm in the Middle (2000)",
  "required_nfo_tags": ["title", "year", "tvdbid", "imdbid", "genre", "plot"],
  "nfo_invariants": {
    "title": "Malcolm in the Middle",
    "tvdbid": "73838"
  },
  "seasons": {
    "1": {
      "episode_count": 16,
      "season_dir": "Saison 01",
      "episode_pattern": "S01E{:02d}",
      "sample_episodes": {
        "1": "S01E01 - Pilot",
        "16": "S01E16 - Water Park"
      }
    }
  }
}
```

#### expected_artwork.json

```json
{
  "required": ["poster.jpg", "fanart.jpg"],
  "optional": ["banner.jpg", "clearlogo.png", "landscape.jpg"],
  "min_poster_size_bytes": 10000,
  "season_artwork": {
    "1": ["season01-poster.jpg"]
  }
}
```

`required` = fichiers qui DOIVENT exister. Test fail si absent.
`optional` = fichiers qui PEUVENT exister. Pas de fail si absent.
`min_poster_size_bytes` = taille minimale (éviter les placeholders vides).

#### expected_structure.json

```json
{
  "root_dir": "Jumanji (1995)",
  "required_files": ["*.mkv", "*.nfo", "*-poster.jpg"],
  "required_dirs": [],
  "forbidden_patterns": ["*.txt", "*.url", "*.nfo.bak"]
}
```

Pour les séries TV :

```json
{
  "root_dir": "Malcolm in the Middle (2000)",
  "required_files": ["tvshow.nfo", "poster.jpg"],
  "required_dirs": ["Saison 01"],
  "season_files": {
    "Saison 01": {
      "min_episode_count": 10,
      "episode_pattern": "S01E*.mkv",
      "episode_nfo_pattern": "S01E*.nfo"
    }
  },
  "forbidden_patterns": ["*.txt", "*.url"]
}
```

#### expected_dispatch.json

```json
{
  "action": "moved",
  "target_category": "films",
  "eligible_disks": ["Disk1", "Disk3", "Disk4"],
  "selection_rule": "most_free_space",
  "destination_contains": "films/Jumanji (1995)"
}
```

`eligible_disks` = disques qui ont la catégorie (d'après DISK_CATEGORIES).
`selection_rule` = la logique attendue (pour doc, pas vérifié automatiquement).
`destination_contains` = sous-chaîne attendue dans `DispatchResult.destination`.

### 2. GoldenFileLoader (`tests/e2e/golden.py`)

```python
from dataclasses import dataclass
from pathlib import Path


EXPECTED_DIR = Path(__file__).parents[2] / "assets" / "torrents" / "expected"


@dataclass
class GoldenFile:
    """Loaded golden file data for a single torrent.

    Attributes:
        name: Torrent identifier (e.g. "jumanji_1995").
        nfo: Expected NFO data.
        artwork: Expected artwork data.
        structure: Expected directory structure.
        dispatch: Expected dispatch results.
    """

    name: str
    nfo: dict
    artwork: dict
    structure: dict
    dispatch: dict


def load_golden_file(torrent_slug: str) -> GoldenFile:
    """Load all golden files for a torrent.

    Args:
        torrent_slug: Directory name in expected/ (e.g. "jumanji_1995").

    Returns:
        GoldenFile with all expected data loaded.

    Raises:
        FileNotFoundError: If the golden file directory doesn't exist.
    """


def match_torrent_to_golden(torrent_name: str) -> GoldenFile | None:
    """Match a torrent name to its golden file.

    Uses fuzzy matching to find the correct golden file directory
    from the torrent filename (e.g. "[LaCale]-Jumanji.1995..." → "jumanji_1995").

    Args:
        torrent_name: Raw torrent filename.

    Returns:
        GoldenFile if matched, None if no golden file exists.
    """


def discover_golden_files() -> list[GoldenFile]:
    """Discover all golden files in assets/torrents/expected/.

    Returns:
        List of all available GoldenFile objects.
    """
```

### 3. Golden File Assertions (`tests/e2e/assertions.py` additions)

```python
def assert_scrape_golden(
    media_dir: Path,
    golden: GoldenFile,
) -> None:
    """Assert scrape results match golden file expectations.

    Checks:
    1. Directory name matches golden.nfo["folder_name_pattern"]
    2. NFO file exists and is valid XML
    3. All required_nfo_tags are present in NFO XML
    4. All nfo_invariants match exact values in NFO XML
    5. Required artwork files exist (golden.artwork["required"])
    6. Artwork files meet minimum size (golden.artwork["min_poster_size_bytes"])
    7. For TV shows: season dirs exist, episode count matches

    Args:
        media_dir: The scraped media directory (in 001-MOVIES or 002-TVSHOWS).
        golden: Expected golden file data.

    Raises:
        AssertionError: If any check fails (with descriptive message).
    """


def assert_dispatch_golden(
    result,  # DispatchResult
    golden: GoldenFile,
) -> None:
    """Assert dispatch dry-run results match golden file expectations.

    Checks:
    1. result.action matches golden.dispatch["action"]
    2. result.disk is in golden.dispatch["eligible_disks"]
    3. golden.dispatch["destination_contains"] is in str(result.destination)
    4. result.action != "error" and result.action != "skipped"

    Args:
        result: DispatchResult from run_dispatch(dry_run=True).
        golden: Expected golden file data.

    Raises:
        AssertionError: If any check fails (with descriptive message).
    """


def assert_structure_golden(
    media_dir: Path,
    golden: GoldenFile,
) -> None:
    """Assert directory structure matches golden file expectations.

    Checks:
    1. Required files exist (glob patterns from golden.structure["required_files"])
    2. Required dirs exist (golden.structure["required_dirs"])
    3. Forbidden patterns are absent (golden.structure["forbidden_patterns"])
    4. For TV: season files match (episode count, patterns)

    Args:
        media_dir: The media directory to check.
        golden: Expected golden file data.

    Raises:
        AssertionError: If any check fails.
    """
```

### 4. Modified E2E Pipeline Tests

```python
# test_pipeline_movies.py — after scrape step:
golden = match_torrent_to_golden(torrent_name)
if golden:
    media_dir = find_media_dir(movies_dir, golden.nfo["folder_name_pattern"])
    assert_scrape_golden(media_dir, golden)
    assert_structure_golden(media_dir, golden)

# test_pipeline_movies.py — after dispatch step:
if golden:
    # Find the DispatchResult matching this torrent
    matching_result = find_dispatch_result(dispatch_results, torrent_name)
    assert_dispatch_golden(matching_result, golden)
```

Les assertions existantes (`assert_scrape_complete`, etc.) restent en place — les golden files ajoutent une couche de vérification supplémentaire, pas un remplacement.

### 5. Test Renforcement — Tests à ajouter

#### tests/ingest/test_ingest.py (NOUVEAU)

Couvrir `ingest.py` orchestration (13% → 70%+) :

```python
# Tests à implémenter :
def test_run_ingest_no_completed_torrents(): ...
def test_run_ingest_already_ingested_skip(): ...
def test_run_ingest_copy_when_seeding(): ...
def test_run_ingest_move_when_done(): ...
def test_run_ingest_disk_space_check_fail(): ...
def test_run_ingest_transfer_verify_fail(): ...
def test_run_ingest_orphan_tmp_cleanup(): ...
def test_run_ingest_dry_run(): ...
def test_run_ingest_step_report_counts(): ...
def test_run_ingest_multiple_torrents(): ...
```

#### tests/dispatch/test_dispatcher.py (extensions)

```python
# Tests à ajouter :
def test_replace_rsync_failure_cleanup(): ...
def test_replace_atomic_swap_failure_restore(): ...
def test_merge_rsync_failure(): ...
def test_merge_verify_failure(): ...
def test_move_new_success(): ...
def test_move_new_rsync_failure(): ...
def test_dispatch_movie_replace(): ...
def test_dispatch_movie_new(): ...
def test_dispatch_tvshow_merge(): ...
def test_dispatch_tvshow_new(): ...
def test_dispatch_no_category_skip(): ...
def test_dispatch_dry_run_no_rsync(): ...
```

#### tests/verify/test_verifier.py (extensions)

```python
# Tests à ajouter :
def test_verify_check_then_fix_then_recheck(): ...
def test_verify_fix_rename_creates_valid(): ...
def test_verify_multiple_issues_all_fixed(): ...
def test_verify_partial_fix_still_blocked(): ...
def test_verify_category_assignment_correct(): ...
```

#### tests/scraper/test_scraper.py (extensions)

```python
# Tests à ajouter :
def test_process_movie_api_failure_skip(): ...
def test_process_movie_low_confidence_skip(): ...
def test_process_tvshow_full_flow(): ...
def test_process_tvshow_episode_rename(): ...
def test_scraper_already_scraped_skip(): ...
```

#### tests/scraper/test_confidence.py (extensions)

```python
# Tests à ajouter :
def test_malformed_tmdb_response_no_crash(): ...
def test_malformed_tvdb_response_no_crash(): ...
def test_tmdb_tvdb_conflict_prefer_higher_confidence(): ...
```

## Flux de données détaillé

```
                    ┌────────────────────────────────┐
                    │     Golden File System          │
                    │                                 │
                    │  assets/torrents/expected/      │
                    │  ├── jumanji_1995/              │
                    │  │   ├── expected_nfo.json      │
                    │  │   ├── expected_artwork.json   │
                    │  │   ├── expected_structure.json │
                    │  │   └── expected_dispatch.json  │
                    │  └── malcolm_in_the_middle_s01/ │
                    │      └── ...                    │
                    └──────────────┬─────────────────┘
                                   │
                    ┌──────────────▼─────────────────┐
                    │    GoldenFileLoader (golden.py)  │
                    │                                 │
                    │  load_golden_file(slug)         │
                    │  match_torrent_to_golden(name)  │
                    │  discover_golden_files()        │
                    └──────────────┬─────────────────┘
                                   │
                    ┌──────────────▼─────────────────┐
                    │    Assertions (assertions.py)    │
                    │                                 │
                    │  assert_scrape_golden()          │
                    │  assert_dispatch_golden()        │
                    │  assert_structure_golden()       │
                    │                                 │
                    │  (existants conservés :)         │
                    │  assert_scrape_complete()        │
                    │  assert_dispatch_complete()      │
                    └──────────────┬─────────────────┘
                                   │
                    ┌──────────────▼─────────────────┐
                    │    E2E Pipeline Tests            │
                    │                                 │
                    │  1. Anciennes assertions (smoke) │
                    │  2. + Golden assertions (exact)  │
                    │  3. Golden = optionnel           │
                    │     (si pas de golden file,      │
                    │      juste les smoke tests)      │
                    └────────────────────────────────┘
```

## Configuration

Pas de nouvelle configuration. Les golden files sont des fixtures statiques dans `assets/torrents/expected/`.

## Gestion d'erreurs

| Situation                                   | Comportement                                      |
| ------------------------------------------- | ------------------------------------------------- |
| Golden file non trouvé pour un torrent      | Log warning, continuer avec les smoke tests seuls |
| NFO invariant ne correspond pas             | AssertionError avec le champ attendu vs trouvé    |
| Artwork required manquant                   | AssertionError avec le nom de fichier manquant    |
| Episode count inférieur au golden           | AssertionError avec expected vs actual count      |
| DispatchResult.action != golden             | AssertionError avec action attendue vs reçue      |
| DispatchResult.disk pas dans eligible_disks | AssertionError avec disque + liste éligible       |
| Golden file JSON invalide                   | JSONDecodeError au chargement (fail early)        |

## Sécurité

- Les golden files ne contiennent PAS de clés API
- Les golden files ne contiennent PAS de chemins absolus (juste des patterns relatifs)
- Les résultats attendus sont **publics** (titres, IDs TMDB/TVDB — données ouvertes)
