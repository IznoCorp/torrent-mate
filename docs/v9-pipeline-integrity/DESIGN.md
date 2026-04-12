# V9 — PIPELINE INTEGRITY : Design

> Pipeline sequentiel exhaustif avec check de coherence avant dispatch.

## Architecture

### Fichiers crees

```
personalscraper/
├── pipeline.py          # NOUVEAU — orchestrateur central (remplace logique inline cli.py:run)
├── process/             # NOUVEAU — Phase 3 modules
│   ├── __init__.py
│   ├── run.py           # run_process() entry point → 3 StepReports
│   ├── reclean.py       # reclean_folders() — re-nettoyage noms bruts
│   ├── dedup.py         # dedup_folders() — fusion doublons fuzzy
│   └── cleanup.py       # cleanup_empty_dirs() — suppression dossiers vides
├── cli.py               # MODIFIE — run() delegue a Pipeline
├── config.py            # MODIFIE — ajout SCRAPER_PREFER_LOCAL_TITLE
├── scraper/scraper.py   # MODIFIE — utilise titre local FR pour rename
├── sorter/run.py        # MODIFIE — ajout gate assert_temp_empty
└── verify/checker.py    # MODIFIE — criteres renforces (episodes, poster, empty dirs)
```

### Dependances

Aucune nouvelle dependance externe. Utilise guessit (V2), rapidfuzz (V2/V3/V5), structlog (V6) deja installes.

## Interfaces

### pipeline.py

```python
class Pipeline:
    """Sequential exhaustive pipeline orchestrator.

    Executes 5 phases with gates between them. Each phase must
    complete fully before the next one starts. The dispatch phase
    only runs if verified items exist.

    Attributes:
        settings: Pipeline configuration.
        dry_run: Preview mode.
        interactive: Prompt for ambiguous matches.
        verbose: Show per-item details.
        console: Rich console for output.
    """

    def __init__(
        self,
        settings: Settings,
        dry_run: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        console: Console | None = None,
    ) -> None: ...

    def run(self) -> PipelineReport:
        """Execute all 5 phases sequentially with gates.

        Returns:
            PipelineReport with 7 StepReports
            (ingest, sort, clean, scrape, cleanup, verify, dispatch).
        """

    def _assert_temp_empty(self) -> None:
        """Gate: verify 097-TEMP is empty after sort.

        Raises:
            PipelineGateError: If unsorted files remain.
        """
```

### process/run.py

```python
def run_process(
    settings: Settings,
    dry_run: bool = False,
    interactive: bool = False,
) -> tuple[StepReport, StepReport, StepReport]:
    """Run Phase 3: re-clean + dedup + scrape + cleanup.

    Args:
        settings: Pipeline configuration.
        dry_run: Preview mode.
        interactive: Prompt for ambiguous matches.

    Returns:
        Tuple of (clean_report, scrape_report, cleanup_report).
    """
```

### process/reclean.py

```python
def reclean_folders(
    category_dir: Path,
    dry_run: bool = False,
) -> StepReport:
    """Re-clean folder names in a category directory.

    Two-pass detection:
    1. Local pass: guessit detects release tokens in title → re-clean
    2. API pass: folders without NFO that don't match API → re-clean + retry

    Also detects and merges fuzzy duplicates via dedup_folders().

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.
        dry_run: Preview mode.

    Returns:
        StepReport with clean + dedup counts.
    """

def is_title_polluted(title: str) -> bool:
    """Check if a folder title contains release group tokens.

    Uses guessit to detect screen_size, video_codec, release_group,
    or other non-title tokens in the string.

    Args:
        title: Extracted title from folder name.

    Returns:
        True if title contains release tokens.
    """
```

### process/dedup.py

```python
def dedup_folders(
    category_dir: Path,
    dry_run: bool = False,
) -> int:
    """Find and merge fuzzy duplicate folders within a category.

    Uses fuzzy_match_score to compare all folder pairs. When duplicates
    are found, merges the less-complete folder into the more-complete one
    (the one with more files / has NFO / has artwork).

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.
        dry_run: Preview mode.

    Returns:
        Number of folders merged.
    """
```

### process/cleanup.py

```python
def cleanup_empty_dirs(
    category_dir: Path,
    dry_run: bool = False,
) -> StepReport:
    """Recursively remove empty directories within a category.

    Bottom-up traversal: removes leaf empty dirs first, then checks
    if parent became empty, etc. Skips .actors/ directories.

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.
        dry_run: Preview mode.

    Returns:
        StepReport with cleanup counts.
    """
```

### Modifications existantes

#### config.py

```python
# New setting
scraper_prefer_local_title: bool = True
```

#### scraper/scraper.py

```python
# In _scrape_movie and _scrape_tvshow, after matching:
# Use local title (FR) from detailed API data when prefer_local_title=True
def _resolve_title(
    self,
    match: MatchResult,
    api_data: dict,
    fallback_title: str,
) -> str:
    """Pick the best title for folder renaming.

    When scraper_prefer_local_title is True, uses the title from
    api_data (fetched with scraper_language=fr-FR). Falls back to
    match.api_title if no local translation exists.

    Args:
        match: API match result.
        api_data: Full movie/show data from TMDB.
        fallback_title: Original title to fall back to.

    Returns:
        Best title string for folder naming.
    """
```

#### sorter/run.py

```python
def assert_temp_empty(settings: Settings) -> list[str]:
    """Check that ingest_dir is empty after sort.

    Ignores .gitkeep, .DS_Store, and hidden files.

    Args:
        settings: Pipeline configuration.

    Returns:
        List of remaining file names (empty if gate passes).
    """
```

#### verify/checker.py

New checks added to `check_movie()` and `check_tvshow()`:

```python
# Movie checks (added):
# - poster_present: Title-poster.jpg exists
# - no_empty_dirs: no empty subdirectories

# TVShow checks (added):
# - episode_renamed: all videos in Saison XX/ match S\d{2}E\d{2} - .+
# - poster_present: poster.jpg exists at show root
# - no_empty_dirs: no empty subdirectories (recursive)
```

## Flux de donnees detaille

```
cli.py:run()
  │
  ├─ acquire_lock()
  ├─ Pipeline(settings, dry_run, interactive, verbose, console)
  │    │
  │    ├─ Phase 1: run_ingest(settings, dry_run)
  │    │    └─ StepReport("ingest")
  │    │
  │    ├─ Phase 2: run_sort(settings, dry_run)
  │    │    └─ StepReport("sort")
  │    │
  │    ├─ GATE: _assert_temp_empty()
  │    │    └─ PipelineGateError if files remain
  │    │
  │    ├─ Phase 3: run_process(settings, dry_run, interactive)
  │    │    ├─ reclean_folders(movies_dir) + dedup_folders(movies_dir)
  │    │    ├─ reclean_folders(tvshows_dir) + dedup_folders(tvshows_dir)
  │    │    │    └─ StepReport("clean")
  │    │    ├─ run_scrape(settings, dry_run, interactive)
  │    │    │    └─ StepReport("scrape")
  │    │    └─ cleanup_empty_dirs(movies_dir) + cleanup_empty_dirs(tvshows_dir)
  │    │         └─ StepReport("cleanup")
  │    │
  │    ├─ Phase 4: run_verify(settings, dry_run)
  │    │    └─ StepReport("verify"), list[VerifyResult]
  │    │
  │    └─ Phase 5: run_dispatch(settings, dry_run, verified=dispatchable)
  │         └─ StepReport("dispatch") — or skip if no dispatchable
  │
  ├─ Panel final (7 rows: ingest, sort, clean, scrape, cleanup, verify, dispatch)
  ├─ Telegram notification
  ├─ Healthcheck ping
  └─ release_lock()
```

## Configuration

```ini
# .env — new setting
SCRAPER_PREFER_LOCAL_TITLE=true   # Use FR title for folder renaming (default: true)
```

## Gestion d'erreurs

| Situation                         | Comportement                                                                                                                                                                            |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gate 097-TEMP non vide            | Log WARNING avec liste des fichiers restants. Continue le pipeline (les fichiers seront traites au prochain run). Ne bloque PAS le process/verify/dispatch des items deja dans 001/002. |
| reclean echoue sur un dossier     | Log WARNING, skip le dossier. Il sera "blocked" au verify.                                                                                                                              |
| dedup faux positif                | Protege par fuzzy_match_score (year guard + length guard + threshold 90%+). En cas de doute, ne fusionne PAS.                                                                           |
| Scrape match API echoue           | Mode interactif : propose alternatives. Mode auto : log warning, skip. Item blocked au verify.                                                                                          |
| cleanup supprime un dossier utile | Impossible : ne supprime que les dossiers strictement vides (aucun fichier).                                                                                                            |
| Verify trouve des blocked         | Rapport detaille dans le panel + logs. Dispatch partiel sur les valid/fixed.                                                                                                            |
| Dispatch echoue sur un item       | Existant inchange (rollback V8). L'item reste dans 001/002.                                                                                                                             |

## Securite

- Aucune nouvelle surface d'attaque
- Les appels API existants (TMDB/TVDB) inchanges
- Le `_force_rmtree` (V8.6) ne s'applique qu'aux tmp dirs du dispatch
- Le cleanup ne supprime jamais de fichiers, seulement des dossiers vides
