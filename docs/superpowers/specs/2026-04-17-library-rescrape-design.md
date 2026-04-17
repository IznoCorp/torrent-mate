# Library Rescrape & Validate Fix — Design Spec

> **Context:** V14 Library Maintenance added 6 commands for scanning, cleaning, validating, analyzing, recommending, and reporting on the existing media library. Testing revealed that validation identifies 699 non-conforming items but cannot fix them. Two missing capabilities: (1) local fixes without API calls (`library-validate --fix --apply`), (2) targeted re-scraping via TMDB/TVDB for items that need fresh metadata (`library-rescrape`).

## Scope

Two features added to the existing V14 PR (same branch `feat/library-maintenance`):

1. **`library-validate --fix --apply`** — Local fixes (no API): empty dirs, NTFS-unsafe names, directory rename from existing NFO data
2. **`library-rescrape`** — Targeted API-based repairs: regenerate broken/missing NFOs, re-download missing artwork, rename episodes

## Non-Goals

- Full re-scrape of the entire library (that's what `personalscraper scrape` does on staging)
- Moving media between disks or categories
- Encoding/transcoding recommendations (that's `library-recommend`)
- Genre-based recategorization

---

## Feature 1: `library-validate --fix --apply`

### Purpose

Fix conformity issues that do NOT require API calls. Uses data already on disk (existing NFO content, filesystem operations).

### Supported Fixes

| Fix ID            | Trigger                                                          | Action                                                 | Risk                         |
| ----------------- | ---------------------------------------------------------------- | ------------------------------------------------------ | ---------------------------- |
| `no_empty_dirs`   | Empty subdirectories detected                                    | Delete empty dirs                                      | None (empty = no data loss)  |
| `ntfs_safe_names` | Filenames with `<>:"/\|?*` characters                            | Rename with `sanitize_filename()` from `text_utils.py` | Low (character substitution) |
| `dir_naming`      | Directory name missing `(Year)` but NFO has `<title>` + `<year>` | Rename directory to `Title (Year)` via `MediaFixer`    | Low (NFO is source of truth) |

### NOT fixed by --fix (requires API = library-rescrape)

`nfo_present`, `nfo_valid`, `poster_present`, `artwork_landscape`, `episode_renamed`, `nfo_ids`, `category`, `season_structure`, `season_posters`, `episode_nfo`

When these are encountered, the output says: "Use `personalscraper library-rescrape` to fix API-dependent issues."

### CLI Interface

```
personalscraper library-validate --fix                  # Dry-run: show what would be fixed
personalscraper library-validate --fix --apply          # Execute fixes (acquires pipeline lock)
personalscraper library-validate --fix --apply --disk Disk1  # Single disk
```

- `--fix` alone = dry-run (show fixes without executing)
- `--fix --apply` = execute fixes (acquires pipeline lock, same as library-clean --apply)
- `--apply` without `--fix` = error (existing behavior preserved)

**Note:** The CLI already defines `--fix` and `--apply` flags with lock handling. Only the forwarding to `validate_library()` and post-fix display need changes.

### Implementation

**Modified files:**

- `personalscraper/library/validator.py` — Add `fix` and `apply` parameters to `validate_library()`, call `MediaFixer` for fixable items, handle `ntfs_safe_names` via `sanitize_filename()`
- `personalscraper/verify/fixer.py` — Already handles `dir_naming`; no changes needed (NTFS fix handled in validator directly)
- `personalscraper/cli.py` — Forward existing `fix`/`apply` parameters to `validate_library()` (flags already exist but are not yet passed to the function)
- `tests/library/test_validator.py` — Tests for fix dry-run and apply

**New dependency:** `personalscraper/text_utils.py` (specifically `sanitize_filename`) for NTFS name fix.

**Logic:**

```python
def validate_library(disk_configs, ..., fix=False, apply=False):
    checker = MediaChecker(NamingPatterns(), GenreMapper())
    fixer = MediaFixer(NamingPatterns(), dry_run=not apply) if fix else None

    for media_dir in iterate_disks(...):
        checks = checker.check_movie(media_dir)  # or check_tvshow
        errors, warnings = _classify_results(checks)

        fixes_applied = []
        fixed_error_names = set()

        if fix and errors:
            # Fix 1: MediaFixer handles dir_naming (rename from NFO title+year)
            fixable = [c for c in checks if not c.passed and c.fixable]
            if fixable:
                actions = fixer.fix_movie(media_dir, fixable)
                for a in actions:
                    fixes_applied.append(a.description)
                    fixed_error_names.add("dir_naming")

            # Fix 2: Empty subdirectories
            if "no_empty_dirs" in errors:
                _fix_empty_dirs(media_dir, dry_run=not apply)
                fixes_applied.append("Removed empty subdirectories")
                fixed_error_names.add("no_empty_dirs")

            # Fix 3: NTFS-unsafe filenames
            if "ntfs_safe_names" in errors:
                _fix_ntfs_names(media_dir, dry_run=not apply)
                fixes_applied.append("Renamed NTFS-unsafe filenames")
                fixed_error_names.add("ntfs_safe_names")

        # Determine final status
        remaining_errors = [e for e in errors if e not in fixed_error_names]
        if not remaining_errors:
            status = "fixed" if fixes_applied else "valid"
        else:
            status = "issues"
```

**`_fix_ntfs_names` implementation:**

```python
from personalscraper.text_utils import sanitize_filename

def _fix_ntfs_names(media_dir: Path, dry_run: bool) -> None:
    """Rename files with NTFS-illegal characters using sanitize_filename."""
    for item in media_dir.rglob("*"):
        safe_name = sanitize_filename(item.name)
        if safe_name != item.name:
            if not dry_run:
                item.rename(item.parent / safe_name)
```

**Result:** `ValidationItem.status` can now be `"valid"`, `"fixed"`, or `"issues"`. `fixes_applied` list is populated. `LibraryValidationResult.fixed_count` is non-zero when fixes are applied.

**`ValidationItem.__post_init__` enforcement (new):**

```python
_VALID_STATUSES = {"valid", "fixed", "issues"}

def __post_init__(self) -> None:
    if self.status not in _VALID_STATUSES:
        raise ValueError(f"status must be one of {_VALID_STATUSES}")
    if self.status == "fixed" and not self.fixes_applied:
        raise ValueError("status='fixed' requires non-empty fixes_applied")
    if self.status == "valid" and (self.errors or self.fixes_applied):
        raise ValueError("status='valid' must have empty errors and fixes_applied")
```

---

## Feature 2: `library-rescrape`

### Purpose

Targeted re-scraping of library items that need fresh metadata from TMDB/TVDB. Only repairs what is broken for each item — does not re-scrape items that are already conforming.

### CLI Interface

```
personalscraper library-rescrape                              # Auto-detect and fix all issues
personalscraper library-rescrape --only nfo                   # Only regenerate NFOs
personalscraper library-rescrape --only artwork               # Only re-download missing artwork
personalscraper library-rescrape --only episodes              # Only rename episodes
personalscraper library-rescrape --disk Disk1                 # Single disk
personalscraper library-rescrape --category films             # Single category
personalscraper library-rescrape --interactive                # Confirm low-confidence matches
personalscraper library-rescrape --dry-run                    # Preview without modifying
personalscraper library-rescrape --max-items 50               # Limit for testing/cron
```

**Note:** `--only nfo` regenerates the entire NFO from API data (not just streamdetails). If the existing NFO has correct metadata but missing `<streamdetails>`, the NFO will be fully regenerated from the API, which may update other fields too.

### Detection Logic

For each media item, determine what needs repair:

| Condition                               | Action Flag      | What happens                                                    |
| --------------------------------------- | ---------------- | --------------------------------------------------------------- |
| NFO absent                              | `needs_nfo`      | Re-match + generate NFO from API                                |
| NFO present but XML invalid             | `needs_nfo`      | Re-match (or extract ID if partially readable) + regenerate NFO |
| NFO valid but no poster                 | `needs_artwork`  | Extract ID from NFO + download artwork                          |
| NFO valid but missing landscape/fanart  | `needs_artwork`  | Extract ID from NFO + download artwork                          |
| TV show with unrenamed episodes         | `needs_episodes` | Extract ID from NFO + fetch episode titles + rename             |
| NFO valid but missing `<streamdetails>` | `needs_nfo`      | Extract stream info + regenerate NFO with streamdetails         |

If `--only` is specified, only the matching flag is acted on (e.g., `--only artwork` skips NFO and episode fixes).

### ID Resolution Strategy

```
1. Try to extract TMDB/TVDB ID from existing NFO (even partially valid ones)
   → nfo_utils.is_nfo_complete() + extract_nfo_ids()
   → Returns str IDs — convert to int() before passing to API clients

2. If no ID found, re-match via title + year from directory name:
   → confidence.match_movie(tmdb_client, title, year)
   → confidence.match_tvshow(tvdb_client, tmdb_client, title, year)
   → MatchResult.api_id is int, MatchResult.source is "tmdb" or "tvdb"

3. TVDB-to-TMDB cross-reference (when source="tvdb"):
   → match_tvshow() may return a TVDB ID. The existing scraper.py handles
     this by fetching TVDB remote IDs to find the TMDB ID, then using TMDB
     for NFO/artwork generation. Rescraper must replicate this pattern:
     tvdb_client.get_remote_ids(tvdb_id) → tmdb_id → tmdb_client.get_tv(tmdb_id)

4. Match confidence check:
   - >= 0.8 (80%) → auto-accept
   - < 0.8 + --interactive → prompt user for confirmation
   - < 0.8 without --interactive → skip, log as "needs manual attention"
```

### Reused Components (no signature changes needed)

| Component                                 | Import                                            | Used For                                                                                                                    |
| ----------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `ArtworkDownloader`                       | `personalscraper.scraper.artwork`                 | Re-download poster, landscape, fanart (skips existing files)                                                                |
| `NFOGenerator`                            | `personalscraper.scraper.nfo_generator`           | Generate movie/tvshow/episode NFO XML                                                                                       |
| `extract_stream_info`                     | `personalscraper.scraper.mediainfo`               | Extract codec/resolution for `<streamdetails>`                                                                              |
| `match_movie` / `match_tvshow`            | `personalscraper.scraper.confidence`              | Re-match items without IDs                                                                                                  |
| `match_episode_files` / `rename_episodes` | `personalscraper.scraper.episode_manager`         | Match and rename TV episodes                                                                                                |
| `create_season_dirs`                      | `personalscraper.scraper.episode_manager`         | Create Saison XX/ directories                                                                                               |
| `TMDBClient` / `TVDBClient`               | `personalscraper.scraper.tmdb_client/tvdb_client` | API calls (uses `settings.tmdb_api_key`, `settings.tvdb_api_key`, `settings.scraper_language`, `settings.artwork_language`) |
| `extract_nfo_ids`                         | `personalscraper.library.scanner`                 | Extract TMDB/IMDB IDs from NFO (promoted to public API)                                                                     |
| `parse_title_year`                        | `personalscraper.library.scanner`                 | Parse title/year from directory name (promoted to public API)                                                               |
| `NamingPatterns`                          | `personalscraper.naming_patterns`                 | Artwork/NFO file naming conventions                                                                                         |
| `SEASON_DIR_RE`                           | `personalscraper.naming_patterns`                 | Season directory regex                                                                                                      |
| `sanitize_filename`                       | `personalscraper.text_utils`                      | NTFS-safe filename sanitization                                                                                             |

### Architecture

**New file:** `personalscraper/library/rescraper.py` — Core rescrape logic.

**Models in `personalscraper/library/models.py`** (following codebase convention — all JSON-serialized result types live together):

```python
# --- Rescrape action constants ---

ACTION_NFO_REGENERATED = "nfo_regenerated"
ACTION_ARTWORK_DOWNLOADED = "artwork_downloaded"
ACTION_EPISODES_RENAMED = "episodes_renamed"
SKIP_LOW_CONFIDENCE = "low_confidence_match"
SKIP_NO_MATCH = "no_match"
SKIP_ALREADY_OK = "already_conforming"

_VALID_ACTIONS = {ACTION_NFO_REGENERATED, ACTION_ARTWORK_DOWNLOADED, ACTION_EPISODES_RENAMED}
_VALID_SKIPS = {SKIP_LOW_CONFIDENCE, SKIP_NO_MATCH, SKIP_ALREADY_OK}
_VALID_ONLY_FILTERS = {"nfo", "artwork", "episodes"}


@dataclass
class RescrapeAction:
    """Single repair action taken on a media item.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        title: Media title.
        media_type: "movie" or "tvshow".
        disk: Disk name.
        category: Category name.
        actions_taken: List of action constants performed.
        actions_skipped: List of skip reason constants.
        errors: Per-item errors (API failure, NTFS write error, etc.).
        tmdb_id: TMDB ID used for API calls (str, converted from int for JSON).
        id_source: How the ID was obtained: "nfo" (extracted) or "api_match" (re-matched).
        match_confidence: Match confidence 0.0-1.0 (None if ID from NFO).
        rescraped_at: ISO 8601 timestamp of this action.
    """

    path: str
    title: str
    media_type: str
    disk: str
    category: str
    actions_taken: list[str]
    actions_skipped: list[str]
    errors: list[str]
    tmdb_id: str | None
    id_source: str | None       # "nfo" or "api_match"
    match_confidence: float | None
    rescraped_at: str = ""

    def __post_init__(self) -> None:
        """Enforce media_type and confidence constraints."""
        if self.media_type not in ("movie", "tvshow"):
            raise ValueError(f"media_type must be 'movie' or 'tvshow', got '{self.media_type}'")
        if self.match_confidence is not None and not (0.0 <= self.match_confidence <= 1.0):
            raise ValueError(f"match_confidence must be 0.0-1.0, got {self.match_confidence}")
        if self.tmdb_id is None and self.match_confidence is not None:
            self.match_confidence = None


@dataclass
class LibraryRescrapeResult:
    """Top-level container for library_rescrape.json.

    Attributes:
        rescraped_at: ISO 8601 timestamp of rescrape start.
        disk_filter: Disk filter applied (None = all disks).
        category_filter: Category filter applied (None = all).
        only_filter: Action filter ("nfo", "artwork", "episodes", or None = all).
        dry_run: Whether this was a dry-run (no actual changes).
        fixed_count: Items successfully repaired.
        skipped_count: Items skipped (low confidence, already OK, etc.).
        error_count: Items with errors.
        items: List of per-item rescrape actions.
    """

    rescraped_at: str
    disk_filter: str | None
    category_filter: str | None
    only_filter: str | None
    dry_run: bool
    fixed_count: int
    skipped_count: int
    error_count: int
    items: list[RescrapeAction] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate only_filter."""
        if self.only_filter is not None and self.only_filter not in _VALID_ONLY_FILTERS:
            raise ValueError(f"only_filter must be one of {_VALID_ONLY_FILTERS} or None")
```

**Note:** `total_processed` removed — it equals `fixed_count + skipped_count + error_count` and can be derived. Avoids consistency trap.

**Core function:**

```python
def rescrape_library(
    disk_configs: list,
    settings: Settings,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    only: str | None = None,       # "nfo", "artwork", "episodes"
    interactive: bool = False,
    dry_run: bool = True,
    max_items: int | None = None,
) -> LibraryRescrapeResult:
```

**Settings fields used:** `settings.tmdb_api_key`, `settings.tvdb_api_key`, `settings.scraper_language`, `settings.scraper_fallback_language`, `settings.artwork_language`, `settings.data_dir`.

**Per-item flow:**

```python
def _rescrape_item(
    media_dir: Path,
    media_type: str,
    disk: str,
    category: str,
    *,
    tmdb_client: TMDBClient,
    tvdb_client: TVDBClient,
    nfo_gen: NFOGenerator,
    artwork_dl: ArtworkDownloader,
    patterns: NamingPatterns,
    only: str | None,
    interactive: bool,
    dry_run: bool,
) -> RescrapeAction | None:
    title, year = parse_title_year(media_dir.name)

    # 1. Detect what needs repair
    needs_nfo, needs_artwork, needs_episodes = _detect_needs(media_dir, media_type, only)

    if not any([needs_nfo, needs_artwork, needs_episodes]):
        return None  # Item is OK, skip

    # 2. Resolve TMDB ID
    tmdb_id, id_source, confidence = _resolve_tmdb_id(
        media_dir, media_type, title, year,
        tmdb_client, tvdb_client, interactive,
    )
    # _resolve_tmdb_id:
    #   - Tries extract_nfo_ids() first → returns (str_id, "nfo", None)
    #   - If no ID, calls match_movie/match_tvshow → returns (int_id, "api_match", confidence)
    #   - If source="tvdb", cross-refs via tvdb_client.get_remote_ids() to get TMDB ID
    #   - Returns (None, None, None) if no match

    if tmdb_id is None:
        return RescrapeAction(..., actions_skipped=[SKIP_NO_MATCH], ...)

    # 3. Fetch API data (once) — tmdb_id is always a TMDB ID at this point
    api_id = int(tmdb_id)  # Convert str→int for API client
    if media_type == "movie":
        api_data = tmdb_client.get_movie(api_id)
    else:
        api_data = tmdb_client.get_tv(api_id)

    # 4. Apply targeted fixes
    actions = []

    if needs_nfo:
        # Construct NFO path using NamingPatterns
        if media_type == "movie":
            parsed_title = title  # from dir name or API title
            nfo_name = patterns.format("movie_nfo", Title=parsed_title)
            nfo_path = media_dir / nfo_name
            video_file = _find_largest_video(media_dir)
            stream_info = extract_stream_info(video_file) if video_file else None
            xml = nfo_gen.generate_movie_nfo(api_data, stream_info)
        else:
            nfo_path = media_dir / "tvshow.nfo"
            xml = nfo_gen.generate_tvshow_nfo(api_data)
        if not dry_run:
            nfo_gen.write_nfo(xml, nfo_path)
        actions.append(ACTION_NFO_REGENERATED)

    if needs_artwork:
        if not dry_run:
            if media_type == "movie":
                artwork_dl.download_movie_artwork(api_data, media_dir, patterns)
            else:
                artwork_dl.download_tvshow_artwork(api_data, media_dir, patterns)
        actions.append(ACTION_ARTWORK_DOWNLOADED)

    if needs_episodes and media_type == "tvshow":
        # Fetch season/episode data from TMDB, match files, rename
        _rescrape_episodes(media_dir, api_data, api_id,
                           tmdb_client, tvdb_client, nfo_gen, artwork_dl,
                           patterns, dry_run)
        actions.append(ACTION_EPISODES_RENAMED)

    return RescrapeAction(
        path=str(media_dir), title=title, media_type=media_type,
        disk=disk, category=category,
        actions_taken=actions, actions_skipped=[], errors=[],
        tmdb_id=str(tmdb_id), id_source=id_source,
        match_confidence=confidence,
        rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )
```

### API Rate Limiting

The rescrape command makes TMDB/TVDB API calls. Existing `tenacity` retry decorators and circuit breakers on the clients handle rate limiting. No additional rate limiting needed — the USB disk I/O is the bottleneck, not the API.

### Lock Policy

`library-rescrape` modifies files on storage disks → acquires pipeline lock (same pattern as `library-clean --apply`). `--dry-run` does NOT acquire lock.

### Error Handling

- **Per-item isolation:** One item's failure does not abort the command (same pattern as scanner/cleaner)
- **API failures:** Caught per-item, logged, counted in `error_count`
- **NTFS errors:** Caught per-file operation, same as disk_cleaner pattern
- **Circuit breaker:** If TMDB/TVDB circuit opens (5 consecutive failures), remaining items are skipped with clear message

### Output

- `library_rescrape.json` saved to `.personalscraper/`
- Console output: progress + summary (X fixed, Y skipped, Z errors)
- Integrated into `library-report` as section "RESCRAPE"

---

## Feature 3: `library-report` Integration

### Additional Section

Inserted between section 5 (TOP 20) and the ACTIONS SUGGÉRÉES block:

```
======================================================================
  6. RESCRAPE — Réparations effectuées
======================================================================

    Dernier rescrape: 2026-04-17T14:00:00
    Items traités: 408
    Réparés: 350
    Skippés (match incertain): 45
    Erreurs: 13

    Détail:
      NFO régénérés: 280
      Artwork téléchargé: 120
      Épisodes renommés: 85
```

### Updated Actions

After rescrape, the suggested actions update:

- "Re-scraper 408 items" becomes "Re-scraper 58 items restants (45 matchs incertains + 13 erreurs)"
- New suggestion: "Relancer avec --interactive pour les 45 matchs incertains"

---

## File Map

### New Files

- `personalscraper/library/rescraper.py` — Core rescrape logic
- `tests/library/test_rescraper.py` — Unit tests

### Modified Files

- `personalscraper/library/models.py` — Add `RescrapeAction`, `LibraryRescrapeResult`, action constants, `ValidationItem.__post_init__`
- `personalscraper/library/validator.py` — Add `fix` and `apply` parameters, call `MediaFixer` + `_fix_empty_dirs` + `_fix_ntfs_names`
- `personalscraper/library/scanner.py` — Promote `_extract_nfo_ids` → `extract_nfo_ids` and `_parse_title_year` → `parse_title_year` (public API)
- `personalscraper/library/reporter.py` — Add rescrape section (section 6, before ACTIONS SUGGÉRÉES)
- `personalscraper/cli.py` — Add `library-rescrape` command, forward existing `fix`/`apply` to `validate_library()`
- `tests/library/test_validator.py` — Fix dry-run and apply tests
- `tests/library/test_models.py` �� `ValidationItem.__post_init__` tests, `RescrapeAction`/`LibraryRescrapeResult` tests
- `tests/library/test_reporter.py` — Rescrape section test
- `tests/library/test_scanner.py` — Update imports for renamed public functions
- `tests/test_cli.py` — CLI tests for rescrape + validate --fix

### Unchanged (reused as-is)

- `personalscraper/scraper/artwork.py`
- `personalscraper/scraper/nfo_generator.py`
- `personalscraper/scraper/episode_manager.py`
- `personalscraper/scraper/confidence.py`
- `personalscraper/scraper/mediainfo.py`
- `personalscraper/scraper/tmdb_client.py`
- `personalscraper/scraper/tvdb_client.py`
- `personalscraper/verify/fixer.py`
- `personalscraper/text_utils.py`

---

## Acceptance Criteria

### Feature 1: library-validate --fix

1. `library-validate --fix` shows fixable items in dry-run mode
2. `library-validate --fix --apply` fixes empty dirs, NTFS names, directory naming
3. `library-validate --fix --apply` acquires pipeline lock
4. Fixed items show `status="fixed"` and populated `fixes_applied` list
5. Non-fixable items output message: "Use `personalscraper library-rescrape` to fix API-dependent issues"
6. `ValidationItem.__post_init__` rejects `status="fixed"` with empty `fixes_applied`

### Feature 2: library-rescrape

7. `library-rescrape --dry-run` previews repairs without modifying files
8. `library-rescrape` regenerates missing/broken NFOs from TMDB/TVDB using correct `NamingPatterns` paths
9. `library-rescrape` re-downloads missing artwork (skips existing)
10. `library-rescrape --only artwork` only downloads artwork, skips NFO/episodes
11. `library-rescrape --only episodes` renames unrenamed episodes using TMDB/TVDB episode titles
12. `library-rescrape --interactive` prompts for low-confidence matches (< 0.8)
13. Low-confidence matches without `--interactive` are skipped and reported
14. TVDB-sourced matches are cross-referenced to TMDB ID before API calls
15. Per-item error isolation (one failure does not abort the command)
16. Circuit breaker: 5 consecutive API failures → remaining items skipped with clear message
17. `library-rescrape --max-items 5` processes at most 5 items
18. `library-rescrape --category films` only processes items in the "films" category
19. `library-rescrape` output saved as `library_rescrape.json`

### Feature 3: library-report integration

20. `library-report` includes rescrape section (section 6) with fix details
21. After rescrape, ACTIONS SUGGÉRÉES section reflects remaining issues (not already-fixed ones)

### General

22. `extract_nfo_ids` and `parse_title_year` promoted to public API in scanner.py
23. All existing tests still pass (0 regressions)
