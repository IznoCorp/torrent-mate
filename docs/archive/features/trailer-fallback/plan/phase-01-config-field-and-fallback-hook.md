# Phase 1 — Config field + fallback hook (TDD)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `TrailersConfig.fallback_youtube_search: bool = True`, add `_youtube_search_fallback()` helper to `TrailersOrchestrator`, insert the same-run fallback at orchestrator.py:494 (after first download, before the unchanged status-dispatch block 497-638), and ensure AC-8 back-compat is preserved.

**Architecture:** TDD throughout — write each failing test first, then the minimal implementation that makes it pass. The fallback hook is a single `if` block inserted between the download call (line 494) and the existing `if result.status == DownloadStatus.SUCCESS:` (line 497). A private helper `_youtube_search_fallback` delegates to `self._finder._youtube_search.search(title, year)` with `CircuitOpenError`-safe wrapping. No structural changes to the dispatch block (lines 497–638).

**Tech Stack:** Python 3.12, pytest, pydantic v2, `personalscraper.logger.get_logger`, `personalscraper.api._contracts.CircuitOpenError`, `personalscraper.scraper.youtube_search.YoutubeSearch`.

**Scope constraints:**

- Every `rg` command MUST use `-g '*.py'` (no bare `rg` — 14 GB fixture dir will crash the machine).
- No command containing the word "fetch" at a word boundary (shell proxy hook blocks it).
- Use `command python` and `command rg` to bypass shell proxy rewrites.
- Logger: `personalscraper.logger.get_logger` — NOT `structlog.get_logger` (invisible to ruff/mypy but caught by `make lint`'s `check_logging.py`).

---

## File Map

| Action | Path                                       | Purpose                                                                                                      |
| ------ | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Modify | `personalscraper/conf/models/trailers.py`  | Add `fallback_youtube_search: bool = True` field to `TrailersConfig`                                         |
| Modify | `config.example/trailers.json5`            | Add `fallback_youtube_search: true` comment+entry in lock-step with model                                    |
| Modify | `personalscraper/trailers/orchestrator.py` | Add `_youtube_search_fallback()` helper (~line 655) + fallback hook (~line 495) + read config at run() start |
| Modify | `tests/trailers/test_orchestrator.py`      | Amend AC-8 existing test + add AC-1..AC-7 new tests                                                          |
| Modify | `tests/conf/test_models.py`                | Add AC-9 config field test                                                                                   |

---

## Task 1: AC-9 — Wire `TrailersConfig.fallback_youtube_search` + config.example

### Files

- Modify: `personalscraper/conf/models/trailers.py:174` (append after `library_check` field)
- Modify: `config.example/trailers.json5` (add field with comment)
- Modify: `tests/conf/test_models.py` (add AC-9 test in `TestTrailersConfig` class)

- [ ] **Step 1.1: Write the failing AC-9 test**

Open `tests/conf/test_models.py`. Locate the `TestTrailersConfig` class (around line 495). Add this test at the end of the class, after `test_trailers_config_library_check_defaults`:

```python
def test_trailers_config_fallback_youtube_search_default(self):
    """TrailersConfig.fallback_youtube_search defaults to True (AC-9).

    The field must exist on the real model (not just MagicMock) and default
    to True so existing configs without the key get the opt-in behavior.
    """
    from personalscraper.conf.models.trailers import TrailersConfig

    cfg = TrailersConfig()
    assert cfg.fallback_youtube_search is True
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
command python -m pytest tests/conf/test_models.py::TestTrailersConfig::test_trailers_config_fallback_youtube_search_default -v
```

Expected: `FAILED` — `AttributeError: 'TrailersConfig' object has no attribute 'fallback_youtube_search'` (or pydantic ValidationError / AttributeError).

- [ ] **Step 1.3: Add the model field**

Open `personalscraper/conf/models/trailers.py`. After line 173 (`library_check: TrailersLibraryCheckConfig = Field(default_factory=TrailersLibraryCheckConfig)`), add:

```python
    # Same-run fallback: when a TMDB-found URL fails to download, attempt a
    # YouTube search for an alternative upload and re-download once.
    # Default True (opt-in by default); set False to disable.
    fallback_youtube_search: bool = True
```

- [ ] **Step 1.4: Update config.example/trailers.json5 in lock-step**

Open `config.example/trailers.json5`. After the `library_check` block (before the closing `}`), add:

```json5
    // When a TMDB-found trailer URL fails to download (YTDLP_ERROR / HTTP_ERROR),
    // attempt a YouTube search for an alternative upload and re-download once.
    // Set to false to keep the pre-0.35.0 behavior (hard failure on first miss).
    fallback_youtube_search: true,
```

- [ ] **Step 1.5: Run AC-9 test to verify it passes**

```bash
command python -m pytest tests/conf/test_models.py::TestTrailersConfig::test_trailers_config_fallback_youtube_search_default -v
```

Expected: `PASSED`.

- [ ] **Step 1.6: Verify no existing TrailersConfig snapshot tests break**

```bash
command python -m pytest tests/conf/test_models.py -v -k "Trailers"
```

Expected: all tests pass. The `_StrictModel` base allows adding new fields with defaults without breaking existing tests. If any test breaks with "unexpected field", that test uses `model_validate` with `extra='forbid'` — fix it by adding `fallback_youtube_search` to its input dict.

- [ ] **Step 1.7: Commit**

```bash
git add personalscraper/conf/models/trailers.py config.example/trailers.json5 tests/conf/test_models.py
git commit -m "feat(trailer-fallback): add TrailersConfig.fallback_youtube_search field (AC-9)"
```

---

## Task 2: AC-8 — Amend existing `test_run_ytdlp_error_increments_counter`

**Context:** This existing test at `tests/trailers/test_orchestrator.py:708` does NOT patch `_finder._youtube_search.search`. Once the fallback is wired (Task 4), that test will make a live call to YouTube unless patched now. The `_make_config()` fixture at line 32 already sets `cfg.trailers.fallback_youtube_search = True`, so the fallback will activate. We fix the test before the implementation so it is already correct at Task 4's integration point.

### Files

- Modify: `tests/trailers/test_orchestrator.py:708-731`

- [ ] **Step 2.1: Read the existing test to understand its structure**

```bash
command python -m pytest tests/trailers/test_orchestrator.py::TestTrailersOrchestratorBasic::test_run_ytdlp_error_increments_counter -v
```

Expected: `PASSED` (it passes now because the fallback isn't wired yet).

- [ ] **Step 2.2: Amend the test**

Open `tests/trailers/test_orchestrator.py`. Find the `test_run_ytdlp_error_increments_counter` method (around line 708). Replace it with:

```python
def test_run_ytdlp_error_increments_counter(self, orchestrator: "TrailersOrchestrator") -> None:
    """counts[ytdlp_error] is incremented when downloader returns an unhandled status.

    AC-8 (back-compat): _finder._youtube_search.search is patched to None so the
    test does not make a live call when the same-run fallback is active.
    """
    from unittest.mock import patch

    from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

    with (
        patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
        patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
        patch.object(
            orchestrator._downloader,
            "download",
            return_value=DownloadResult(
                status=DownloadStatus.YTDLP_ERROR,
                output_path=None,
                error_message="ytdlp failed",
            ),
        ),
        patch.object(orchestrator._finder._youtube_search, "search", return_value=None),
    ):
        counts = orchestrator.run()
    assert counts["ytdlp_error"] == 1
```

- [ ] **Step 2.3: Run the amended test**

```bash
command python -m pytest tests/trailers/test_orchestrator.py::TestTrailersOrchestratorBasic::test_run_ytdlp_error_increments_counter -v
```

Expected: `PASSED` (still passes — `_youtube_search.search` is not called yet since fallback isn't wired).

- [ ] **Step 2.4: Commit**

```bash
git add tests/trailers/test_orchestrator.py
git commit -m "test(trailer-fallback): patch _youtube_search.search in AC-8 back-compat test"
```

---

## Task 3: AC-1..AC-7 — Write all failing fallback tests

**Context:** All tests go into `tests/trailers/test_orchestrator.py`. Add a new test class `TestTrailersOrchestratorFallback` after the existing `TestTrailersOrchestratorBasic` class. These tests will FAIL until Task 4 wires the fallback.

The `_SCAN_ITEM` at line 68 (`ScanItem(path=Path("/fake/Fight Club (1999)"), media_type="movie", title="Fight Club", year=1999, tmdb_id="550")`) is reused by all tests.

The `orchestrator` fixture (defined in the same file or `conftest.py`) uses `_make_config()` which already sets `cfg.trailers.fallback_youtube_search = True`.

### Files

- Modify: `tests/trailers/test_orchestrator.py` (add `TestTrailersOrchestratorFallback` class)

- [ ] **Step 3.1: Add the test class**

Find the end of `TestTrailersOrchestratorBasic` in `tests/trailers/test_orchestrator.py` and add the following class after it:

```python
class TestTrailersOrchestratorFallback:
    """Tests for the same-run YouTube-search fallback (feat/trailer-fallback).

    All tests reproduce the SMG/FROM miss: TMDB finds a URL, download fails,
    fallback searches YouTube, re-download may succeed or fail. AC-1..AC-7.
    """

    def test_ytdlp_failure_triggers_youtube_fallback_and_succeeds(
        self, orchestrator: "TrailersOrchestrator"
    ) -> None:
        """AC-1: TMDB URL → YTDLP_ERROR, YouTube search → ALT_URL → SUCCESS.

        Reproduces the Super Mario Galaxy / FROM miss (2026-06-16 run).
        download() is called twice; final state is DOWNLOADED with
        source=="youtube" and youtube_url==ALT_URL. ytdlp_error counter stays 0.
        """
        from unittest.mock import MagicMock, call, patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        alt_url = "https://youtube.com/watch?v=ALT_GOOD"

        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        success_result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            output_path=MagicMock(),
            error_message=None,
        )
        download_mock = MagicMock(side_effect=[fail_result, success_result])

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=alt_url),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        # download called twice: once with tmdb_url, once with alt_url
        assert download_mock.call_count == 2
        assert download_mock.call_args_list[0] == call(tmdb_url, MagicMock())
        assert download_mock.call_args_list[1] == call(alt_url, MagicMock())

        # Counters: success path, not error path
        assert counts.get("downloaded", 0) == 1
        assert counts.get("ytdlp_error", 0) == 0

        # State written with DOWNLOADED + source=youtube + youtube_url=alt_url
        assert mock_state.call_count == 1
        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.DOWNLOADED
        assert state_arg.source == "youtube"
        assert state_arg.youtube_url == alt_url

    def test_ytdlp_failure_fallback_also_fails_keeps_terminal_state(
        self, orchestrator: "TrailersOrchestrator"
    ) -> None:
        """AC-2: Both downloads fail → download×2, ytdlp_error==1, terminal state.

        When the fallback also returns YTDLP_ERROR, the item ends in the same
        terminal state as before (YTDLP_ERROR + next_retry_at) and the counter
        increments once.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        alt_url = "https://youtube.com/watch?v=ALT_ALSO_DEAD"

        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(side_effect=[fail_result, fail_result])

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=alt_url),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        assert download_mock.call_count == 2
        assert counts.get("ytdlp_error", 0) == 1
        assert counts.get("downloaded", 0) == 0

        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.YTDLP_ERROR
        assert state_arg.next_retry_at is not None

    def test_ytdlp_failure_fallback_returns_none_no_second_download(
        self, orchestrator: "TrailersOrchestrator"
    ) -> None:
        """AC-3: YouTube search returns None → no 2nd download, terminal state.

        When the search engine finds nothing, the fallback is a no-op:
        download is called exactly once and the item fails terminally.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=None),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        assert download_mock.call_count == 1
        assert counts.get("ytdlp_error", 0) == 1

        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.YTDLP_ERROR

    def test_ytdlp_failure_fallback_returns_same_url_no_double_download(
        self, orchestrator: "TrailersOrchestrator"
    ) -> None:
        """AC-4: YouTube search returns the already-failed URL → tried-set blocks 2nd download.

        When the fallback search returns the same URL that just failed,
        the tried-set guard prevents a redundant re-download.
        download is called exactly once.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        tmdb_url = "https://youtube.com/watch?v=SAME"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=tmdb_url),
        ):
            counts = orchestrator.run()

        assert download_mock.call_count == 1

    def test_fallback_disabled_by_config(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-5: fallback_youtube_search=False → search NOT called, download×1, terminal.

        When the operator disables the fallback, behavior is identical to
        pre-0.35.0: one download attempt, terminal failure, no YouTube search.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        orchestrator._config.trailers.fallback_youtube_search = False

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)
        search_mock = MagicMock()

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", search_mock),
        ):
            counts = orchestrator.run()

        search_mock.assert_not_called()
        assert download_mock.call_count == 1
        assert counts.get("ytdlp_error", 0) == 1

    def test_fallback_youtube_circuit_open_is_clean(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-6: CircuitOpenError from YouTube search → no crash, no 2nd download, terminal.

        A tripped YouTube circuit breaker must not propagate as an unhandled
        exception. The fallback is silently skipped and the item fails
        terminally (same as search-returns-None).
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.api._contracts import CircuitOpenError
        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        fail_result = DownloadResult(status=DownloadStatus.YTDLP_ERROR, output_path=None, error_message="dead")
        download_mock = MagicMock(return_value=fail_result)

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(
                orchestrator._finder._youtube_search,
                "search",
                side_effect=CircuitOpenError("youtube circuit open"),
            ),
        ):
            # Must NOT raise
            counts = orchestrator.run()

        assert download_mock.call_count == 1
        assert counts.get("ytdlp_error", 0) == 1

    def test_http_error_also_triggers_fallback(self, orchestrator: "TrailersOrchestrator") -> None:
        """AC-7: HTTP_ERROR also falls back to YouTube search.

        The fallback must activate on ALL non-SUCCESS statuses, not just
        YTDLP_ERROR. BOT_DETECTED is excluded: re-downloading immediately
        would reset bot_detected_consecutive_attempts incorrectly.
        Only HTTP_ERROR is covered here (YTDLP_ERROR covered by AC-1..AC-3).
        """
        from unittest.mock import MagicMock, call, patch

        from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus
        from personalscraper.trailers.state import TrailerStatus

        tmdb_url = "https://youtube.com/watch?v=TMDB_DEAD"
        alt_url = "https://youtube.com/watch?v=ALT_GOOD"

        http_fail = DownloadResult(status=DownloadStatus.HTTP_ERROR, output_path=None, error_message="403")
        success_result = DownloadResult(status=DownloadStatus.SUCCESS, output_path=MagicMock(), error_message=None)
        download_mock = MagicMock(side_effect=[http_fail, success_result])

        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value=tmdb_url),
            patch.object(orchestrator._downloader, "download", download_mock),
            patch.object(orchestrator._finder._youtube_search, "search", return_value=alt_url),
            patch("personalscraper.trailers.orchestrator._set_state_for_item") as mock_state,
        ):
            counts = orchestrator.run()

        assert download_mock.call_count == 2
        assert download_mock.call_args_list[1] == call(alt_url, MagicMock())
        assert counts.get("downloaded", 0) == 1
        assert counts.get("http_error", 0) == 0

        state_arg = mock_state.call_args[0][2]
        assert state_arg.status == TrailerStatus.DOWNLOADED
```

- [ ] **Step 3.2: Run all AC-1..AC-7 tests to confirm they FAIL**

```bash
command python -m pytest tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback -v 2>&1 | tail -20
```

Expected: All 7 tests `FAILED`. Acceptable failure reasons: `AttributeError` (no `_youtube_search_fallback`), `AssertionError` (download called once instead of twice), or similar. If any pass without implementation, something is already wired — investigate before proceeding.

- [ ] **Step 3.3: Commit the failing tests**

```bash
git add tests/trailers/test_orchestrator.py
git commit -m "test(trailer-fallback): add failing AC-1..AC-7 fallback tests"
```

---

## Task 4: Implement `_youtube_search_fallback()` helper + fallback hook

### Files

- Modify: `personalscraper/trailers/orchestrator.py`
  - Add helper `_youtube_search_fallback` (near line 655, after `failed_items` property)
  - Read config flag at run() start (near line 264, with other config reads)
  - Insert fallback hook (between line 494 and 497)

- [ ] **Step 4.1: Add config-flag read in `run()`**

Open `personalscraper/trailers/orchestrator.py`. In the `run()` method, find the block of config reads near line 260–267:

```python
        max_duration_sec = int(self._config.trailers.step.max_duration_sec)
        min_size = int(self._config.trailers.filters.min_file_size_bytes)
        max_filesize_mb = int(self._config.trailers.filters.max_filesize_mb)
        required_free: float = max_filesize_mb * 1024 * 1024 * 1.5
        retry_policy: list[int] = list(self._config.trailers.retry_after_days)
        movies_check = bool(self._config.trailers.library_check.movies)
        tvshows_check = bool(self._config.trailers.library_check.tv_shows)
```

Add one line after `tvshows_check`:

```python
        fallback_yt_search: bool = bool(self._config.trailers.fallback_youtube_search)
```

- [ ] **Step 4.2: Add the `_youtube_search_fallback()` helper method**

Find the `_build_finder` method (line 655). Add the new private helper BEFORE `_build_finder`:

```python
    def _youtube_search_fallback(self, item: "Any") -> "str | None":
        """Search YouTube for an alternative trailer URL when the first download fails.

        Delegates to ``self._finder._youtube_search.search(title, year)`` without
        calling ``finder.find()`` — avoids re-hitting the TMDB tier and avoids
        writing the ``__no_result__`` cache sentinel.

        Handles ``CircuitOpenError`` cleanly (mirrors the pattern at
        ``orchestrator.py:415-417``): a tripped YouTube breaker returns None
        rather than propagating as an unhandled exception.

        Args:
            item: A ``ScanItem``-compatible object with ``title: str`` and
                  ``year: int | None`` attributes.

        Returns:
            A YouTube video URL string, or None when the search fails, the
            circuit is open, or ``_finder`` is not available.
        """
        from personalscraper.api._contracts import CircuitOpenError  # noqa: PLC0415

        log = get_logger(__name__)

        if self._finder is None:
            return None
        try:
            return self._finder._youtube_search.search(item.title, item.year)
        except CircuitOpenError:
            log.warning(
                "trailers_fallback_circuit_open",
                title=item.title,
            )
            return None
        except Exception:  # noqa: BLE001
            log.warning(
                "trailers_fallback_search_error",
                title=item.title,
                exc_info=True,
            )
            return None
```

Note: `get_logger` is already imported at the module top level in `orchestrator.py`. Verify with:

```bash
command rg "from personalscraper.logger import get_logger\|get_logger" /Users/izno/dev/PersonnalScaper/personalscraper/trailers/orchestrator.py -g '*.py' | head -5
```

If `get_logger` is not imported, add at the top of the file:

```python
from personalscraper.logger import get_logger
```

- [ ] **Step 4.3: Insert the fallback hook between download (line 494) and dispatch (line 497)**

Find this block in `run()` (currently lines 494-497):

```python
            result = self._downloader.download(url, expected_path)
            now_iso = datetime.now(timezone.utc).isoformat()

            if result.status == DownloadStatus.SUCCESS:
```

Replace with (insert the fallback block between the download and `now_iso`):

```python
            tried: set[str] = {url}
            result = self._downloader.download(url, expected_path)

            # Same-run YouTube-search fallback (feat/trailer-fallback).
            # Fires when the first download fails AND the fallback is enabled
            # AND the search is not circuit-open. Re-downloads at most once.
            # BOT_DETECTED is excluded: re-downloading immediately would
            # reset bot_detected_consecutive_attempts incorrectly.
            if (
                result.status not in (DownloadStatus.SUCCESS, DownloadStatus.BOT_DETECTED)
                and fallback_yt_search
            ):
                alt = self._youtube_search_fallback(item)
                if alt and alt not in tried:
                    tried.add(alt)
                    url = alt  # state/NFO/events record the URL actually used
                    result = self._downloader.download(url, expected_path)

            now_iso = datetime.now(timezone.utc).isoformat()

            if result.status == DownloadStatus.SUCCESS:
```

- [ ] **Step 4.4: Run AC-1..AC-7 tests to verify they now PASS**

```bash
command python -m pytest tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback -v
```

Expected: All 7 tests `PASSED`.

- [ ] **Step 4.5: Run AC-8 back-compat test**

```bash
command python -m pytest tests/trailers/test_orchestrator.py::TestTrailersOrchestratorBasic::test_run_ytdlp_error_increments_counter -v
```

Expected: `PASSED`.

- [ ] **Step 4.6: Run full orchestrator test suite**

```bash
command python -m pytest tests/trailers/test_orchestrator.py -v 2>&1 | tail -30
```

Expected: All tests pass, 0 failures.

- [ ] **Step 4.7: Run all trailers tests**

```bash
command python -m pytest tests/trailers/ -v 2>&1 | tail -30
```

Expected: All tests pass, 0 failures.

- [ ] **Step 4.8: Commit the implementation**

```bash
git add personalscraper/trailers/orchestrator.py
git commit -m "feat(trailer-fallback): add _youtube_search_fallback helper + same-run hook (AC-1..AC-7)"
```

---

## Task 5: Smoke + check_logging guard

- [ ] **Step 5.1: Smoke-test the import**

```bash
command python -c "import personalscraper; from personalscraper.trailers.orchestrator import TrailersOrchestrator; print('OK')"
```

Expected: `OK` (no ImportError).

- [ ] **Step 5.2: Run check_logging to confirm logger usage is correct**

```bash
command python scripts/check_logging.py personalscraper/trailers/orchestrator.py 2>&1 || true
```

If the command doesn't exist at that path:

```bash
find /Users/izno/dev/PersonnalScaper -name "check_logging*" -g '*.py' 2>/dev/null | head -5
```

Then run it. Expected: no violations for `get_logger` in orchestrator.py.

- [ ] **Step 5.3: Run ruff + mypy on changed files**

```bash
command python -m ruff check personalscraper/conf/models/trailers.py personalscraper/trailers/orchestrator.py tests/trailers/test_orchestrator.py tests/conf/test_models.py
command python -m mypy personalscraper/conf/models/trailers.py personalscraper/trailers/orchestrator.py --ignore-missing-imports
```

Expected: zero errors from ruff; mypy may warn about `Any` type usage in the helper (acceptable — matches existing patterns in the file).

- [ ] **Step 5.4: Commit if any trivial fixes were needed**

```bash
git add -p
git commit -m "chore(trailer-fallback): fix ruff/mypy nits in fallback implementation"
```

(Only if there were actual fixes. Skip this step if step 5.3 was already clean.)
