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

---

## Sub-phase 6.1 — `scanner.py` + tests

### Files

| Action | Path                                      | Responsibility                               |
| ------ | ----------------------------------------- | -------------------------------------------- |
| Create | `personalscraper/trailers/scanner.py`     | Staging + library scan logic                 |
| Create | `tests/trailers/test_scanner.py`          | Tmpdir-based unit tests                      |

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
        trailers_dir = d / "trailers"
        trailers_dir.mkdir()
        (trailers_dir / "trailer.mp4").write_bytes(b"x" * 200000)
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
```

**`Scanner` class — key methods:**

```python
class Scanner:
    def __init__(self, min_file_size_bytes: int) -> None: ...

    def scan_staging(self, staging_dir: Path) -> list[ScanItem]:
        """Walk staging_dir for all sorted media subdirs lacking a trailer.

        Uses ``trailer_path_for_movie()`` and ``trailer_path_for_tvshow()``
        from placement.py, then calls ``trailer_exists()`` to determine absence.
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
- Use `placement.trailer_path_for_movie()` / `placement.trailer_path_for_tvshow()` then
  `placement.trailer_exists()` to check current absence.

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

| Action | Path                                         | Responsibility                                      |
| ------ | -------------------------------------------- | --------------------------------------------------- |
| Create | `personalscraper/trailers/orchestrator.py`   | Glue: scanner → finder → downloader → placement     |
| Create | `tests/trailers/test_orchestrator.py`        | Unit tests (all dependencies mocked)                |

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
            Counts dict with keys: downloaded, already_present, no_trailer,
            bot_detected, http_error, ytdlp_error, skipped_by_state, error.
        """

    @property
    def failed_items(self) -> list[tuple[str, str, str]]:
        """List of (key, status, reason) for items that did not get a trailer."""
```

**Algorithm per item:**

1. `state_store.auto_gc()` once at start of `run()`.
2. For each `ScanItem`:
   a. Build composite state key via `make_state_key()`.
   b. `state_store.should_skip(key)` → if True, increment `skipped_by_state`.
   c. **SOT recheck**: `trailer_exists(expected_path, min_size_bytes)` → if True, increment `already_present`.
   d. `finder.find(tmdb_id, media_type, title, year)` → if None, record `no_trailer`.
   e. `downloader.download(url, output_path)` → handle each `DownloadStatus`.
   f. Update state via `state_store.set()` with appropriate `TrailerState`.
3. Return counts dict.

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
