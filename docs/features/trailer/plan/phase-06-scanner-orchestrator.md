# Phase 6 — Scanner + orchestrator

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §3 (`trailers/scanner.py`, `trailers/orchestrator.py`) and
DESIGN §8 (source-of-truth disk verification). Create `scanner.py` — the "media without
trailer" detection module that walks either staging or the library — and `orchestrator.py`
— the glue that runs `scanner → trailer_finder → ytdlp_downloader → placement → state`.
Tests use tmpdir-based fake media trees.

**Architecture:**

- `Scanner.scan_staging(staging_dir) -> list[ScanItem]` — walks sorted staging subdirs
- `Scanner.scan_library(config, filters) -> list[ScanItem]` — wraps `library.scanner.scan_library()`
  with fresh-scan threshold logic (24h default, configurable)
- `ScanItem` dataclass: path, media_type, title, year, tmdb_id
- `TrailersOrchestrator.run() -> dict[str, int]` — runs the full pipeline for a batch of `ScanItem`

**Tech Stack:** Python, `pytest`, `unittest.mock`, `tmpdir`.

---

## Gate (entry condition)

Phases 4 and 5 must be complete:

```bash
python -c "from personalscraper.trailers.state import TrailerStateStore; print('OK')"
python -c "from personalscraper.trailers.step import run_trailers; print('OK')"
```

---

## Dependencies

- Phase 4 (`TrailerStateStore` — orchestrator reads/writes state)
- Phase 5 (`run_trailers` — orchestrator is the step's backend; this phase makes it real)

---

## Invariants for this phase

- **SOT rule**: every `download` decision re-checks the filesystem via `trailer_exists()`
  immediately before dispatching to `YtdlpDownloader` — never trusts scanner output alone.
- **Fresh-scan threshold**: `scan_library()` refreshes if last scan is older than
  `config.trailers.library_scan_max_age_hours` (default 24). `--no-refresh` bypasses this.
- The pipeline `trailers` step uses `scan_staging()` only — no library refresh during pipeline.
- Existing `tests/library/` tests remain green.
- **Season scanning is opt-in** (DESIGN §4): when `config.trailers.seasons.enabled` is False
  (the default), the scanner emits show-level `ScanItem`s only — same behaviour as before.
- **Library-aware SOT recheck** (DESIGN §8 extension): controlled by
  `config.trailers.check_library_before_download` (default True). When enabled, the
  orchestrator consults `library.scanner` once per run and short-circuits items whose
  trailers already exist on one of the storage disks.

---

## Sub-phase 6.1 — `scanner.py` + tests

### Files

| Action | Path                                  | Responsibility               |
| ------ | ------------------------------------- | ---------------------------- |
| Create | `personalscraper/trailers/scanner.py` | Staging + library scan logic |
| Create | `tests/trailers/test_scanner.py`      | Tmpdir-based unit tests      |

### Step 1: Write failing tests

Create `tests/trailers/test_scanner.py`:

```python
"""Unit tests for trailers/scanner.py — media-without-trailer detection.

Uses tmpdir fixtures to build fake media trees (movies and TV shows with/without
trailers). Library scanning path uses mocked library.scanner.scan_library().
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.trailers.scanner import ScanItem, Scanner


# ── Helper fixtures ───────────────────────────────────────────────────────────

def _make_movie_dir(parent: Path, name: str, with_trailer: bool = False) -> Path:
    """Create a fake movie directory with a minimal NFO."""
    d = parent / name
    d.mkdir(parents=True)
    title = name.split("(")[0].strip()
    year_match = name.split("(")[-1].rstrip(")")
    nfo = d / f"{title}.nfo"
    nfo.write_text(
        f'<movie><title>{title}</title>'
        f'<uniqueid type="tmdb">550</uniqueid>'
        f'</movie>',
        encoding="utf-8",
    )
    if with_trailer:
        (d / f"{name}-trailer.mp4").write_bytes(b"x" * 200000)
    return d


def _make_tvshow_dir(parent: Path, name: str, with_trailer: bool = False) -> Path:
    """Create a fake TV show directory with tvshow.nfo."""
    d = parent / name
    d.mkdir(parents=True)
    nfo = d / "tvshow.nfo"
    nfo.write_text(
        '<tvshow><title>Breaking Bad</title>'
        '<uniqueid type="tmdb">1396</uniqueid>'
        '</tvshow>',
        encoding="utf-8",
    )
    if with_trailer:
        # Flat convention per DESIGN §4: `{show_name}-trailer.{ext}` at show root
        # (no `trailers/` subfolder). Matches the unified trailer_path_for() output.
        (d / f"{name}-trailer.mp4").write_bytes(b"x" * 200000)
    return d


# ── scan_staging ──────────────────────────────────────────────────────────────

class TestScanStaging:
    def test_finds_movie_without_trailer(self, tmp_path):
        """scan_staging returns a ScanItem for a movie missing its trailer."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].title == "Fight Club"

    def test_skips_movie_with_existing_trailer(self, tmp_path):
        """scan_staging skips media whose trailer already exists and is large enough."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=True)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []

    def test_finds_tvshow_without_trailer(self, tmp_path):
        """scan_staging returns ScanItem for TV show missing trailers/ subdir."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_dir(tvshows_dir, "Breaking Bad (2008)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].media_type == "tvshow"

    def test_scan_item_has_tmdb_id(self, tmp_path):
        """ScanItem.tmdb_id is populated from the NFO."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items[0].tmdb_id == "550"

    def test_empty_staging_returns_empty_list(self, tmp_path):
        """scan_staging returns [] for an empty staging directory."""
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []


# ── ScanItem dataclass ────────────────────────────────────────────────────────

class TestScanItem:
    def test_scan_item_fields(self, tmp_path):
        """ScanItem carries path, media_type, title, year, tmdb_id."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        item = items[0]
        assert item.path.is_dir()
        assert item.media_type == "movie"
        assert item.title == "Fight Club"
        assert item.year == 1999
```

### Step 2: Implement `personalscraper/trailers/scanner.py`

**`ScanItem` dataclass:**

```python
@dataclass
class ScanItem:
    path: Path
    media_type: str       # "movie" or "tvshow"
    title: str
    year: int | None
    tmdb_id: str | None   # from NFO, or None if not found
    imdb_id: str | None = None
    # DESIGN §4 "Season trailers" extension. None for movies and show-level
    # TV ScanItems. Positive integer for season-level ScanItems emitted when
    # `config.trailers.seasons.enabled` is True. The expected trailer path
    # for a season-level ScanItem is computed via
    # `placement.trailer_path_for_season(show_dir, season_number, ext)`.
    season_number: int | None = None
```

**`Scanner` class — key methods:**

```python
class Scanner:
    def __init__(self, min_file_size_bytes: int) -> None: ...

    def scan_staging(self, staging_dir: Path) -> list[ScanItem]:
        """Walk staging_dir for all sorted media subdirs lacking a trailer.

        Uses the unified ``trailer_path_for(media_dir, media_name, ext=...)``
        from placement.py (single convention for movies and TV shows), then
        calls ``trailer_exists()`` to determine absence.
        Reads TMDb IDs from NFOs via ``library.scanner.extract_nfo_ids()``.
        """

    def scan_library(
        self,
        config: Config,
        disk_filter: str | None = None,
        category_filter: str | None = None,
        force_refresh: bool = False,
    ) -> list[ScanItem]:
        """Wrap library.scanner.scan_library() and filter for missing trailers.

        Applies fresh-scan threshold: refreshes if last scan timestamp is
        older than config.trailers.library_scan_max_age_hours.
        ``force_refresh=True`` bypasses the threshold.
        """
```

**Implementation notes:**

- `scan_staging()` iterates `staging_dir.iterdir()`, skips hidden dirs and non-dirs.
- For each subdir, detect movie vs. tvshow by checking whether `tvshow.nfo` exists.
- Use `library.scanner.parse_title_year(dir.name)` for title/year extraction.
- Use `library.scanner.extract_nfo_ids(nfo_path)` for tmdb_id.
- Use `placement.trailer_path_for(media_dir, media_name, ext=...)` (single unified
  convention) then `placement.trailer_exists()` to check current absence.

**Season-aware scanning** (DESIGN §4 — opt-in via `config.trailers.seasons.enabled`):

- `Scanner.__init__` gains a `seasons_enabled: bool = False` parameter, plumbed from
  `config.trailers.seasons.enabled` at construction time.
- When scanning a TV show directory AND `seasons_enabled` is True:
  - Always emit the show-level `ScanItem` (with `season_number=None`) as before.
  - Additionally enumerate `Saison XX/` subfolders inside the show directory using the
    regex `^Saison \d{2}$`. For each match, parse the integer season number and emit a
    second `ScanItem` with `media_type="tvshow"`, `season_number=<N>`, and an
    `expected_trailer_path` computed via
    `placement.trailer_path_for_season(show_dir, N, ext)`.
  - Skip seasons whose expected trailer path already exists with size
    ≥ `min_file_size_bytes` (same skip rule as show-level).
- When `seasons_enabled` is False, behaviour is unchanged (show-level ScanItems only).
  The regex enumeration is short-circuited; no `Saison XX/` walking is performed.

### Season-aware scanner tests (DESIGN §4 extension — opt-in)

Add the following tests to `tests/trailers/test_scanner.py` to cover the
`seasons_enabled` parameter and per-season `ScanItem` emission. The fixture helper
`_make_tvshow_dir` is extended (or a sibling helper added) to create
`Saison 01/`, `Saison 02/` subfolders so the regex walker has something to find.

```python
def _make_tvshow_with_seasons(parent: Path, name: str, season_count: int) -> Path:
    """Create a fake TV show directory with N `Saison XX/` subfolders.

    No trailers are placed — every season is missing its trailer file.
    """
    d = _make_tvshow_dir(parent, name, with_trailer=False)
    for n in range(1, season_count + 1):
        (d / f"Saison {n:02d}").mkdir()
    return d


class TestSeasonAwareScanning:
    def test_season_scanner_emits_one_item_per_saison_folder_when_enabled(self, tmp_path):
        """With seasons_enabled=True, scan emits show-level item + one item per season."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_with_seasons(tvshows_dir, "Breaking Bad (2008)", season_count=3)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=True)
        items = scanner.scan_staging(tmp_path)
        # Show-level + 3 seasons = 4 items
        assert len(items) == 4
        season_numbers = sorted(i.season_number for i in items if i.season_number is not None)
        assert season_numbers == [1, 2, 3]
        # Exactly one show-level entry (season_number is None)
        assert sum(1 for i in items if i.season_number is None) == 1

    def test_season_scanner_skips_seasons_when_disabled(self, tmp_path):
        """With seasons_enabled=False (default), only the show-level ScanItem is emitted."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_with_seasons(tvshows_dir, "Breaking Bad (2008)", season_count=3)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=False)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].season_number is None
```

### Library-aware orchestrator recheck tests (DESIGN §8 extension)

These tests live in `tests/trailers/test_orchestrator.py` (added in Sub-phase 6.2) but
the contract is anchored here so the scanner author understands the orchestrator's
expectations on `library.scanner` integration:

- `test_library_aware_recheck_skips_when_trailer_on_disk` — orchestrator queries
  `library.scanner.scan_library` once; for an item whose tmdb_id matches a
  `LibraryScanItem`, if a trailer file exists at the library location, the item is
  marked `already_present_on_disk` and the downloader is NOT called.
- `test_library_aware_recheck_falls_through_when_library_item_absent` — when the
  scanner returns no matching library item (new media not on any disk yet), the
  orchestrator falls through to the staging SOT recheck and continues normally.
- `test_library_aware_recheck_disabled_falls_through` — when
  `config.trailers.check_library_before_download=False`, the library scan is never
  performed and the orchestrator behaves as if no library existed.

### Step 3: Run tests

```bash
pytest tests/trailers/test_scanner.py -v
```

### Step 4: Commit sub-phase 6.1

```bash
git add personalscraper/trailers/scanner.py tests/trailers/test_scanner.py
git commit -m "feat(trailer): add Scanner with staging and library scan modes"
```

---

## Sub-phase 6.2 — `orchestrator.py` + tests

### Files

| Action | Path                                       | Responsibility                                  |
| ------ | ------------------------------------------ | ----------------------------------------------- |
| Create | `personalscraper/trailers/orchestrator.py` | Glue: scanner → finder → downloader → placement |
| Create | `tests/trailers/test_orchestrator.py`      | Unit tests (all dependencies mocked)            |

### Step 1: Write failing tests

Create `tests/trailers/test_orchestrator.py`:

```python
"""Unit tests for TrailersOrchestrator — full pipeline glue.

All dependencies (TrailerFinder, YtdlpDownloader, TrailerStateStore) are mocked.
Scanner is patched to return controlled ScanItem lists.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.scanner import ScanItem
from personalscraper.trailers.state import TrailerStatus


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.languages = ["fr-FR", "en-US"]
    cfg.trailers.fallback_youtube_search = True
    cfg.trailers.search_query_format = "{title} {year} bande annonce"
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.ytdlp.format = "best[ext=mp4]/best"
    cfg.trailers.ytdlp.socket_timeout_sec = 30
    cfg.trailers.ytdlp.retries = 3
    # DESIGN §4 + §8 extensions
    cfg.trailers.seasons.enabled = False
    cfg.trailers.seasons.language_fallback = None
    cfg.trailers.seasons.search_query_format = "{title} {year} saison {season} bande annonce"
    cfg.trailers.check_library_before_download = True
    return cfg


@pytest.fixture()
def orchestrator(tmp_path):
    config = _make_config(tmp_path)
    return TrailersOrchestrator(config=config, staging_dir=tmp_path)


_SCAN_ITEM = ScanItem(
    path=Path("/fake/Fight Club (1999)"),
    media_type="movie",
    title="Fight Club",
    year=1999,
    tmdb_id="550",
)


class TestTrailersOrchestrator:
    def test_downloaded_increments_counter(self, orchestrator, tmp_path):
        """Counts['downloaded'] is incremented when download succeeds."""
        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader, "download",
                return_value=DownloadResult(
                    status=DownloadStatus.SUCCESS,
                    output_path=tmp_path / "Fight Club (1999)-trailer.mp4",
                ),
            ),
        ):
            counts = orchestrator.run()
        assert counts["downloaded"] == 1

    def test_already_present_increments_counter(self, orchestrator, tmp_path):
        """Counts['already_present'] when trailer file exists before download."""
        # Create the trailer file to simulate "already present"
        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        trailer = media_dir / "Fight Club (1999)-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)

        item = ScanItem(
            path=media_dir,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
        )
        with patch.object(orchestrator._scanner, "scan_staging", return_value=[item]):
            counts = orchestrator.run()
        assert counts["already_present"] == 1

    def test_no_trailer_increments_counter_when_finder_returns_none(self, orchestrator):
        """Counts['no_trailer'] when TrailerFinder.find() returns None."""
        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=None),
        ):
            counts = orchestrator.run()
        assert counts["no_trailer"] == 1

    def test_skipped_by_state_when_should_skip(self, orchestrator):
        """Counts['skipped_by_state'] when state store says should_skip."""
        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._state_store, "should_skip", return_value=True),
        ):
            counts = orchestrator.run()
        assert counts["skipped_by_state"] == 1

    def test_empty_scan_returns_zero_counts(self, orchestrator):
        """run() returns all-zero counts when scanner finds nothing."""
        with patch.object(orchestrator._scanner, "scan_staging", return_value=[]):
            counts = orchestrator.run()
        assert all(v == 0 for v in counts.values())

    def test_sot_recheck_before_download(self, orchestrator, tmp_path):
        """Orchestrator re-checks trailer_exists immediately before download.

        Race simulation: the scanner reports the item as missing a trailer, but
        the trailer file materializes between scan and download (e.g. another
        run placed it). The SOT re-check MUST see the file and short-circuit
        to ``already_present`` without calling the downloader.
        """
        media_dir = tmp_path / "Fight Club (1999)"
        media_dir.mkdir()
        trailer = media_dir / "Fight Club (1999)-trailer.mp4"

        item = ScanItem(
            path=media_dir, media_type="movie",
            title="Fight Club", year=1999, tmdb_id="550",
        )

        def create_trailer_on_find(tmdb_id, media_type, title, year):
            # Simulate trailer appearing between scan and the SOT re-check.
            trailer.write_bytes(b"x" * 200000)
            return "https://youtube.com/watch?v=X"

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
            patch.object(orchestrator._finder, "find", side_effect=create_trailer_on_find),
            patch.object(orchestrator._downloader, "download") as mock_download,
        ):
            counts = orchestrator.run()

        # The SOT re-check MUST detect the trailer before download is attempted.
        assert counts.get("already_present", 0) == 1, (
            "SOT re-check failed to notice trailer that appeared between scan and download"
        )
        assert counts.get("downloaded", 0) == 0, (
            "Downloader was called despite the trailer already existing on disk"
        )
        mock_download.assert_not_called()
```

### Step 2: Implement `personalscraper/trailers/orchestrator.py`

**Public interface:**

```python
class TrailersOrchestrator:
    def __init__(self, config: Config, staging_dir: Path) -> None:
        """Wire up Scanner, TrailerFinder, YtdlpDownloader, TrailerStateStore.

        Args:
            config: Loaded pipeline Config.
            staging_dir: Path to staging area (for pipeline step) or None
                for library-mode (CLI). When None, scan_library() is used.
        """

    def run(self) -> dict[str, int]:
        """Execute the full trailer acquisition loop.

        Returns:
            Counts dict with keys: downloaded, already_present,
            already_present_on_disk, no_trailer, bot_detected, http_error,
            ytdlp_error, skipped_by_state, error.
        """

    @property
    def failed_items(self) -> list[tuple[str, str, str]]:
        """List of (key, status, reason) for items that did not get a trailer."""
```

**Algorithm per item:**

1. `state_store.auto_gc()` once at start of `run()`.
2. **Step budget**: record `step_start = time.monotonic()`. Read
   `config.trailers.step.max_duration_sec` (default 1800 s — DESIGN §12 Timeouts).
   2bis. **Library index init (lazy)**: if `config.trailers.check_library_before_download`
   is True, build `self._library_index` once on first access by calling
   `library.scanner.scan_library(config.disks, config)` and indexing the returned
   `LibraryScanItem`s by `(category, tmdb_id)` and `(category, tvdb_id)` tuples
   (skip entries whose ids are None). The cache lives for the orchestrator instance's
   lifetime — one scan per run is enough; the cache is invalidated on the next
   orchestrator instantiation. When the flag is False, the index stays empty and the
   library-aware recheck is skipped entirely.
3. For each `ScanItem`:
   a. Build composite state key via `make_state_key()`. For season-level ScanItems,
   pass `season_number=item.season_number` so the key carries the `:season:{N}` suffix.
   b. `state_store.should_skip(key)` → if True, increment `skipped_by_state`.
   b-new. **Library-aware SOT recheck** (DESIGN §8 extension, controlled by
   `config.trailers.check_library_before_download`, default `True`):
   1. Build a library lookup key from the ScanItem's NFO ids (`tmdb_id` preferred,
      `tvdb_id` fallback).
   2. Look up the matching `LibraryScanItem` in `self._library_index`. If found:
      - Compute the expected trailer path at the library location (using
        `trailer_path_for(library_item.path, library_item.path.name, ext)` for
        movies / show-level TV, or
        `trailer_path_for_season(library_item.path, item.season_number, ext)`
        for season-level items — using the LIBRARY path, not the staging path).
      - If that file exists with size ≥ `config.trailers.filters.min_file_size_bytes`,
        write a state entry with `status=ALREADY_PRESENT_ON_DISK`,
        `trailer_path=<library_path>`, increment the `already_present_on_disk`
        counter, and continue to the next item (no network call).
   3. If not found on disk OR no trailer present at the library location, fall
      through to step c (staging SOT recheck) as before.
      c. **SOT recheck**: `trailer_exists(expected_path, min_size_bytes)` → if True, increment `already_present`.
      d. **Disk-space pre-check** (DESIGN §12 Disk space): compute
      `required = config.trailers.filters.max_filesize_mb * 1024 * 1024 * 1.5`
      (50% safety margin). If `shutil.disk_usage(expected_path.parent).free < required`,
      log event `trailers_disk_space_low` with bytes free + required, increment
      `skipped_by_filter`, and continue to next item (do NOT call the downloader).
      e. **Step-budget check**: if `time.monotonic() - step_start >= max_duration_sec`, log
      `trailers_step_budget_exceeded` and break the loop. Remaining items are not
      attempted; the StepReport returned by `run_trailers()` is `partial`.
      f. `finder.find(tmdb_id, media_type, title, year)` → if None, record `no_trailer`.
      g. `downloader.download(url, output_path)` → handle each `DownloadStatus`.
      h. Update state via `state_store.set()` with appropriate `TrailerState`.
4. Return counts dict.

**Tests to add** (in `tests/trailers/test_orchestrator.py`):

- `test_skips_item_when_disk_space_low` — monkeypatch `shutil.disk_usage` to return free
  bytes less than `max_filesize_mb * 1024 * 1024 * 1.5`; assert item skipped with
  `skipped_by_filter` count incremented; downloader never called.
- `test_step_budget_exceeded_breaks_loop` — set `max_duration_sec=0` in config; assert only
  the first item is attempted; remaining items produce no state updates.
- `test_library_aware_recheck_skips_when_trailer_on_disk` — patch
  `library.scanner.scan_library` to return a `LibraryScanItem` whose path matches the
  ScanItem's tmdb_id; create the trailer file at the library location with size ≥
  `min_file_size_bytes`. Assert the orchestrator increments `already_present_on_disk`,
  writes a state entry with `status=ALREADY_PRESENT_ON_DISK` and
  `trailer_path=<library_path>`, and never calls the downloader nor the finder.
- `test_library_aware_recheck_falls_through_when_library_item_absent` — patch
  `library.scanner.scan_library` to return an empty list. Assert the orchestrator falls
  through to the staging SOT recheck and proceeds normally (downloader is reachable
  if the staging trailer is missing).
- `test_library_aware_recheck_disabled_falls_through` — set
  `config.trailers.check_library_before_download = False`. Assert
  `library.scanner.scan_library` is NEVER called and behaviour is identical to a
  staging-only orchestrator.

### Step 3: Run tests

```bash
pytest tests/trailers/test_orchestrator.py -v
```

### Step 4: Commit sub-phase 6.2

```bash
git add personalscraper/trailers/orchestrator.py tests/trailers/test_orchestrator.py
git commit -m "feat(trailer): add TrailersOrchestrator gluing scanner to finder, downloader, state"
```

---

## Phase 6 quality gate

- [ ] `pytest tests/trailers/ -q` — all green
- [ ] `pytest tests/library/ -q` — no regressions in library tests
- [ ] `python -m ruff check personalscraper/trailers/scanner.py personalscraper/trailers/orchestrator.py` — no errors
- [ ] `python -m mypy personalscraper/trailers/orchestrator.py personalscraper/trailers/scanner.py` — no type errors

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/trailers/ -q
pytest tests/library/ -q
python -m ruff check personalscraper/trailers/scanner.py personalscraper/trailers/orchestrator.py
python -m mypy personalscraper/trailers/orchestrator.py personalscraper/trailers/scanner.py
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 06 gate — scanner + orchestrator with SOT disk verification"
```

## Exit condition for Phase 7

Phase 7 may start only when:

- `TrailersOrchestrator`, `Scanner`, `ScanItem` importable
- `pytest tests/trailers/ -q` exits 0
- The milestone commit is on the branch
