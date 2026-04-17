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

| Fix ID            | Trigger                                                          | Action                                              | Risk                         |
| ----------------- | ---------------------------------------------------------------- | --------------------------------------------------- | ---------------------------- |
| `no_empty_dirs`   | Empty subdirectories detected                                    | Delete empty dirs                                   | None (empty = no data loss)  |
| `ntfs_safe_names` | Filenames with `<>:"/\|?*` characters                            | Rename with safe characters                         | Low (character substitution) |
| `dir_naming`      | Directory name missing `(Year)` but NFO has `<title>` + `<year>` | Rename directory to `Title (Year)` via `MediaFixer` | Low (NFO is source of truth) |

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

### Implementation

**Modified files:**

- `personalscraper/library/validator.py` — Add `fix` and `apply` parameters to `validate_library()`, call `MediaFixer` for fixable items
- `personalscraper/cli.py` — Pass `fix`/`apply` to `validate_library()`
- `tests/library/test_validator.py` — Tests for fix dry-run and apply

**Logic:**

```python
def validate_library(disk_configs, ..., fix=False, apply=False):
    checker = MediaChecker(NamingPatterns(), GenreMapper())
    fixer = MediaFixer(NamingPatterns(), dry_run=not apply) if fix else None

    for media_dir in iterate_disks(...):
        checks = checker.check_movie(media_dir)  # or check_tvshow
        errors, warnings = _classify_results(checks)

        fixes_applied = []
        if fix and errors:
            # Only fix what MediaFixer can handle
            fixable = [c for c in checks if not c.passed and c.fixable]
            if fixable:
                actions = fixer.fix_movie(media_dir, fixable)
                fixes_applied = [a.description for a in actions]

            # Additional fixes: empty dirs
            if "no_empty_dirs" in errors:
                _fix_empty_dirs(media_dir, dry_run=not apply)
                fixes_applied.append("Removed empty subdirectories")

        # Determine final status
        remaining_errors = [e for e in errors if e not in fixed_errors]
        if not remaining_errors:
            status = "fixed" if fixes_applied else "valid"
        else:
            status = "issues"
```

**Result:** `ValidationItem.status` can now be `"valid"`, `"fixed"`, or `"issues"`. `fixes_applied` list is populated. `LibraryValidationResult.fixed_count` is non-zero when fixes are applied.

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
   → nfo_utils.is_nfo_complete() + scanner._extract_nfo_ids()

2. If no ID found, re-match via title + year from directory name:
   → confidence.match_movie(tmdb_client, title, year)
   → confidence.match_tvshow(tvdb_client, tmdb_client, title, year)

3. Match confidence check:
   - >= 80% → auto-accept
   - < 80% + --interactive → prompt user for confirmation
   - < 80% without --interactive → skip, log as "needs manual attention"
```

### Reused Components (zero rewrite)

| Component                                 | Import                                            | Used For                                                     |
| ----------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------ |
| `ArtworkDownloader`                       | `personalscraper.scraper.artwork`                 | Re-download poster, landscape, fanart (skips existing files) |
| `NFOGenerator`                            | `personalscraper.scraper.nfo_generator`           | Generate movie/tvshow/episode NFO XML                        |
| `extract_stream_info`                     | `personalscraper.scraper.mediainfo`               | Extract codec/resolution for `<streamdetails>`               |
| `match_movie` / `match_tvshow`            | `personalscraper.scraper.confidence`              | Re-match items without IDs                                   |
| `match_episode_files` / `rename_episodes` | `personalscraper.scraper.episode_manager`         | Match and rename TV episodes                                 |
| `create_season_dirs`                      | `personalscraper.scraper.episode_manager`         | Create Saison XX/ directories                                |
| `TMDBClient` / `TVDBClient`               | `personalscraper.scraper.tmdb_client/tvdb_client` | API calls for metadata                                       |
| `_extract_nfo_ids`                        | `personalscraper.library.scanner`                 | Extract TMDB/IMDB IDs from NFO                               |
| `_parse_title_year`                       | `personalscraper.library.scanner`                 | Parse title/year from directory name                         |
| `NamingPatterns`                          | `personalscraper.naming_patterns`                 | Artwork/NFO file naming conventions                          |
| `SEASON_DIR_RE`                           | `personalscraper.naming_patterns`                 | Season directory regex                                       |

### Architecture

**New file:** `personalscraper/library/rescraper.py`

```python
@dataclass
class RescrapeAction:
    """Single repair action taken on a media item."""
    path: str
    title: str
    media_type: str           # "movie" or "tvshow"
    disk: str
    category: str
    actions_taken: list[str]  # ["nfo_regenerated", "artwork_downloaded", "episodes_renamed"]
    actions_skipped: list[str]  # ["low_confidence_match"]
    errors: list[str]         # Per-item errors (API failure, etc.)
    tmdb_id: str | None
    match_confidence: float | None


@dataclass
class RescrapeResult:
    """Top-level container for library_rescrape.json."""
    rescraped_at: str
    disk_filter: str | None
    category_filter: str | None
    only_filter: str | None       # "nfo", "artwork", "episodes", or None (all)
    dry_run: bool
    total_processed: int
    fixed_count: int
    skipped_count: int            # Low confidence, already OK, etc.
    error_count: int
    items: list[RescrapeAction]
```

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
) -> RescrapeResult:
```

**Per-item flow:**

```python
def _rescrape_item(media_dir, media_type, disk, category, tmdb_client, tvdb_client,
                   nfo_gen, artwork_dl, patterns, only, interactive, dry_run):
    # 1. Detect what needs repair
    needs_nfo, needs_artwork, needs_episodes = _detect_needs(media_dir, media_type, only)

    if not any([needs_nfo, needs_artwork, needs_episodes]):
        return None  # Item is OK, skip

    # 2. Resolve TMDB/TVDB ID
    tmdb_id, confidence = _resolve_id(media_dir, media_type, tmdb_client, tvdb_client, interactive)
    if tmdb_id is None:
        return RescrapeAction(..., actions_skipped=["no_match"], ...)

    # 3. Fetch API data (once)
    api_data = tmdb_client.get_movie(tmdb_id) or tmdb_client.get_tv(tmdb_id)

    # 4. Apply targeted fixes
    actions = []
    if needs_nfo:
        stream_info = extract_stream_info(video_file) if video_file else None
        xml = nfo_gen.generate_movie_nfo(api_data, stream_info)
        if not dry_run:
            nfo_gen.write_nfo(xml, nfo_path)
        actions.append("nfo_regenerated")

    if needs_artwork:
        if not dry_run:
            artwork_dl.download_movie_artwork(api_data, media_dir, patterns)
        actions.append("artwork_downloaded")

    if needs_episodes and media_type == "tvshow":
        # Fetch episode data, match, rename
        ...
        actions.append("episodes_renamed")

    return RescrapeAction(..., actions_taken=actions, ...)
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

- `personalscraper/library/validator.py` — Add fix/apply logic
- `personalscraper/library/reporter.py` — Add rescrape section
- `personalscraper/cli.py` — Add `library-rescrape` command, pass fix/apply to validate
- `tests/library/test_validator.py` — Fix tests
- `tests/library/test_reporter.py` — Rescrape section test
- `tests/test_cli.py` — CLI tests for rescrape + validate --fix

### Unchanged (reused as-is)

- `personalscraper/scraper/artwork.py`
- `personalscraper/scraper/nfo_generator.py`
- `personalscraper/scraper/episode_manager.py`
- `personalscraper/scraper/confidence.py`
- `personalscraper/scraper/mediainfo.py`
- `personalscraper/scraper/tmdb_client.py`
- `personalscraper/scraper/tvdb_client.py`

---

## Acceptance Criteria

1. `library-validate --fix` shows fixable items in dry-run mode
2. `library-validate --fix --apply` fixes empty dirs, NTFS names, directory naming
3. `library-validate --fix --apply` acquires pipeline lock
4. Fixed items show `status="fixed"` and populated `fixes_applied` list
5. Non-fixable items suggest `library-rescrape`
6. `library-rescrape --dry-run` previews repairs without modifying files
7. `library-rescrape` regenerates missing/broken NFOs from TMDB/TVDB
8. `library-rescrape` re-downloads missing artwork (skips existing)
9. `library-rescrape --only artwork` only downloads artwork, skips NFO/episodes
10. `library-rescrape --interactive` prompts for low-confidence matches
11. Low-confidence matches without `--interactive` are skipped and reported
12. Per-item error isolation (one failure does not abort the command)
13. `library-rescrape` output saved as `library_rescrape.json`
14. `library-report` includes rescrape section with fix details
15. All existing tests still pass (0 regressions)
