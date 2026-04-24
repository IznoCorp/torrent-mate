# Phase 3b — Download wrapper (`ytdlp_downloader`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §3 (`scraper/ytdlp_downloader.py`) and DESIGN §5 (cookie
authentication strategy) and DESIGN §10 (testing: yt-dlp fully mocked). Create
`scraper/ytdlp_downloader.py`: a yt-dlp Python API wrapper with cookies handling, the
retry-without-cookies fallback, and filesystem permission checks for cookie files on APFS vs
NTFS/macFUSE volumes. Unit tests mock `yt_dlp.YoutubeDL` and assert the opts dict. One
`@pytest.mark.network` E2E test downloads Big Buck Bunny to a tmpdir.

**Architecture:** `YtdlpDownloader.download(url, output_path) -> DownloadResult`. Takes a
YouTube URL (from `TrailerFinder`) and an output `Path`, calls `yt_dlp.YoutubeDL(opts).download([url])`.
Cookie loading is handled by a `CookieConfig` helper that reads env vars and validates
filesystem permissions.

**Tech Stack:** Python, `yt-dlp`, `pytest`, `@pytest.mark.network`, `ruff`, `mypy`.

---

## Gate (entry condition)

Phase 3a must be complete:

```bash
python -c "from personalscraper.scraper.trailer_finder import TrailerFinder; print('OK')"
```

---

## Dependencies

- Phase 3a (TrailerFinder defines the URL string contract)

---

## Invariants for this phase

- `yt_dlp.YoutubeDL` is **never called with real network** in unit tests — always patched.
- Cookie files on NTFS/macFUSE paths are rejected at load time with a clear error message
  (DESIGN §12 security requirement).
- The `@pytest.mark.network` test is skipped in CI by default — guarded by
  `pytest.mark.skipif(not os.getenv("TRAILER_INTEGRATION_TESTS"), reason="network test")`.

---

## Sub-phase 3b.1 — `CookieConfig` + cookie permission tests

### Files

| Action | Path                                            | Responsibility                                       |
| ------ | ----------------------------------------------- | ---------------------------------------------------- |
| Create | `personalscraper/scraper/ytdlp_downloader.py`   | Skeleton + `CookieConfig` class                      |
| Create | `tests/scraper/test_ytdlp_downloader.py`        | Cookie config tests (no network)                     |

### Step 1: Write failing cookie tests first

Create `tests/scraper/test_ytdlp_downloader.py` (initial section):

```python
"""Unit tests for YtdlpDownloader — yt-dlp wrapper with cookies handling.

yt_dlp.YoutubeDL is fully mocked; no network calls in unit tests.
The @pytest.mark.network E2E test is opt-in via TRAILER_INTEGRATION_TESTS env var.
"""

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.scraper.ytdlp_downloader import (
    CookieConfig,
    CookieError,
    DownloadResult,
    DownloadStatus,
    YtdlpDownloader,
)


# ── CookieConfig ─────────────────────────────────────────────────────────────

class TestCookieConfig:
    def test_no_cookies_when_env_not_set(self, monkeypatch):
        """CookieConfig.from_env() returns None when no env vars are set."""
        monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
        monkeypatch.delenv("YOUTUBE_COOKIES_FROM_BROWSER", raising=False)
        cfg = CookieConfig.from_env()
        assert cfg is None

    def test_file_cookie_takes_priority(self, tmp_path, monkeypatch):
        """YOUTUBE_COOKIES_FILE takes priority over YOUTUBE_COOKIES_FROM_BROWSER."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape cookies", encoding="utf-8")
        # Set 600 permissions
        cookie_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        monkeypatch.setenv("YOUTUBE_COOKIES_FROM_BROWSER", "firefox")
        cfg = CookieConfig.from_env()
        assert cfg is not None
        assert cfg.cookie_file == cookie_file
        assert cfg.cookie_from_browser is None

    def test_browser_cookie_used_when_no_file(self, monkeypatch):
        """YOUTUBE_COOKIES_FROM_BROWSER is used when no file is configured."""
        monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
        monkeypatch.setenv("YOUTUBE_COOKIES_FROM_BROWSER", "firefox")
        cfg = CookieConfig.from_env()
        assert cfg is not None
        assert cfg.cookie_from_browser == "firefox"
        assert cfg.cookie_file is None

    def test_nonexistent_cookie_file_raises(self, monkeypatch):
        """CookieConfig raises CookieError when the cookie file does not exist."""
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", "/nonexistent/cookies.txt")
        with pytest.raises(CookieError, match="not found"):
            CookieConfig.from_env()

    def test_ntfs_cookie_file_raises(self, tmp_path, monkeypatch):
        """CookieConfig raises CookieError when cookie file is on NTFS mount."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        # Simulate NTFS detection by patching the internal check
        with patch(
            "personalscraper.scraper.ytdlp_downloader._is_apfs_native",
            return_value=False,
        ):
            with pytest.raises(CookieError, match="NTFS"):
                CookieConfig.from_env()
```

### Step 2: Implement `CookieConfig` + helpers in `ytdlp_downloader.py`

```python
"""yt-dlp wrapper with cookies handling and retry-without-cookies fallback.

Provides:
- ``CookieConfig``: reads YOUTUBE_COOKIES_FILE / YOUTUBE_COOKIES_FROM_BROWSER
  from env, validates filesystem permissions (APFS-only, mode 600 check).
- ``YtdlpDownloader``: calls ``yt_dlp.YoutubeDL(opts).download([url])``
  with retry-without-cookies on bot-detection failure.
- ``DownloadResult``: typed result with status, output path, error message.

yt-dlp is invoked via its Python API only — no subprocess, no shell interpolation.
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# APFS/HFS+ volume roots (macOS) — cookie files must live here for security
_APFS_NATIVE_PREFIXES = ("/Users", "/opt", "/path/to/<disk>", "/tmp", "/var")


def _is_apfs_native(path: Path) -> bool:
    """Return True if path lives on an APFS-native volume (not NTFS/macFUSE).

    Checks whether the path starts with known APFS-native mount prefixes.
    On NTFS/macFUSE mounts, permission bits are not enforced, so cookie files
    must not be placed there.

    Args:
        path: Absolute path to check.

    Returns:
        True if the path is on an APFS-native volume.
    """
    path_str = str(path.resolve())
    return any(path_str.startswith(prefix) for prefix in _APFS_NATIVE_PREFIXES)


class CookieError(Exception):
    """Raised when cookie configuration is invalid or insecure."""


@dataclass(frozen=True)
class CookieConfig:
    """Cookie authentication configuration for yt-dlp.

    Attributes:
        cookie_file: Path to a static Netscape-format cookies.txt, or None.
        cookie_from_browser: Browser profile name for live extraction, or None.
    """

    cookie_file: Path | None
    cookie_from_browser: str | None

    @classmethod
    def from_env(cls) -> "CookieConfig | None":
        """Build CookieConfig from environment variables.

        Priority: YOUTUBE_COOKIES_FILE > YOUTUBE_COOKIES_FROM_BROWSER > None.

        Returns:
            CookieConfig if any env var is set, None otherwise.

        Raises:
            CookieError: If YOUTUBE_COOKIES_FILE is set but the file does not
                exist, or is on an NTFS/macFUSE volume.
        """
        file_path_str = os.getenv("YOUTUBE_COOKIES_FILE")
        browser = os.getenv("YOUTUBE_COOKIES_FROM_BROWSER")

        if file_path_str:
            cookie_file = Path(file_path_str)
            if not cookie_file.exists():
                raise CookieError(
                    f"YOUTUBE_COOKIES_FILE not found: {cookie_file}"
                )
            if not _is_apfs_native(cookie_file):
                raise CookieError(
                    f"YOUTUBE_COOKIES_FILE is on an NTFS/macFUSE volume — "
                    f"cookie files must reside on APFS-native storage for security. "
                    f"Got: {cookie_file}"
                )
            # Warn if permissions are not 600 (POSIX only)
            try:
                mode = cookie_file.stat().st_mode & 0o777
                if mode != 0o600:
                    logger.warning(
                        "YOUTUBE_COOKIES_FILE has mode %03o — recommend 600 for security",
                        mode,
                    )
            except OSError:
                pass  # Silently skip on filesystems that don't support mode bits
            return cls(cookie_file=cookie_file, cookie_from_browser=None)

        if browser:
            return cls(cookie_file=None, cookie_from_browser=browser)

        return None
```

### Step 3: Run cookie tests

```bash
pytest tests/scraper/test_ytdlp_downloader.py::TestCookieConfig -v
```

### Step 4: Commit sub-phase 3b.1

```bash
git add personalscraper/scraper/ytdlp_downloader.py tests/scraper/test_ytdlp_downloader.py
git commit -m "feat(trailer): add CookieConfig with APFS security check and env loading"
```

---

## Sub-phase 3b.2 — `YtdlpDownloader` + mocked tests

### Files

| Action | Path                                          | Responsibility           |
| ------ | --------------------------------------------- | ------------------------ |
| Modify | `personalscraper/scraper/ytdlp_downloader.py` | Add `YtdlpDownloader`    |
| Modify | `tests/scraper/test_ytdlp_downloader.py`      | Add downloader unit tests|

### Step 1: Write failing tests (append to test file)

```python
# ── DownloadResult / DownloadStatus ─────────────────────────────────────────

class TestDownloadResult:
    def test_success_result(self):
        result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            output_path=Path("/tmp/trailer.mp4"),
        )
        assert result.status == DownloadStatus.SUCCESS
        assert result.output_path == Path("/tmp/trailer.mp4")

    def test_bot_detected_result(self):
        result = DownloadResult(
            status=DownloadStatus.BOT_DETECTED,
            error_message="Sign in to confirm your age",
        )
        assert result.status == DownloadStatus.BOT_DETECTED
        assert result.output_path is None


# ── YtdlpDownloader (mocked yt_dlp) ─────────────────────────────────────────

@pytest.fixture()
def downloader(tmp_path) -> YtdlpDownloader:
    return YtdlpDownloader(
        output_dir=tmp_path,
        ytdlp_format="best[ext=mp4]/best",
        socket_timeout_sec=30,
        retries=3,
        cookie_config=None,
    )


class TestYtdlpDownloader:
    def test_download_success(self, downloader, tmp_path):
        """download() returns SUCCESS when YoutubeDL.download() exits cleanly."""
        output_file = tmp_path / "test-trailer.mp4"

        def fake_download(self_ydl, urls):
            # Simulate yt-dlp creating the output file
            output_file.write_bytes(b"fake_video_data")
            return 0

        with patch("yt_dlp.YoutubeDL") as MockYDL:
            instance = MockYDL.return_value.__enter__.return_value
            instance.download.side_effect = lambda urls: output_file.write_bytes(b"x") or 0
            result = downloader.download(
                "https://www.youtube.com/watch?v=test",
                output_file,
            )

        assert result.status == DownloadStatus.SUCCESS

    def test_opts_dict_contains_format(self, downloader, tmp_path):
        """download() passes format option to YoutubeDL."""
        output_file = tmp_path / "trailer.mp4"
        captured_opts: list[dict] = []

        def capture_opts(opts):
            captured_opts.append(opts)
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock.download = MagicMock(return_value=0)
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=capture_opts):
            downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert captured_opts[0]["format"] == "best[ext=mp4]/best"

    def test_opts_dict_contains_retries(self, downloader, tmp_path):
        """download() passes retries option to YoutubeDL."""
        output_file = tmp_path / "trailer.mp4"
        captured_opts: list[dict] = []

        def capture_opts(opts):
            captured_opts.append(opts)
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock.download = MagicMock(return_value=0)
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=capture_opts):
            downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert captured_opts[0]["retries"] == 3

    def test_cookie_file_added_to_opts(self, tmp_path):
        """download() adds cookiefile to opts when CookieConfig provides a file."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        cfg = CookieConfig(cookie_file=cookie_file, cookie_from_browser=None)
        d = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=1,
            cookie_config=cfg,
        )
        output_file = tmp_path / "trailer.mp4"
        captured_opts: list[dict] = []

        def capture_opts(opts):
            captured_opts.append(opts)
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock.download = MagicMock(return_value=0)
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=capture_opts):
            d.download("https://www.youtube.com/watch?v=test", output_file)

        assert str(cookie_file) in str(captured_opts[0].get("cookiefile", ""))

    def test_bot_detected_retry_succeeds_without_cookies(self, tmp_path):
        """First attempt fails with bot detection; retry without cookies SUCCEEDS."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        cfg = CookieConfig(cookie_file=cookie_file, cookie_from_browser=None)
        d = YtdlpDownloader(
            output_dir=tmp_path, ytdlp_format="best",
            socket_timeout_sec=10, retries=1, cookie_config=cfg,
        )
        call_count = 0
        captured_opts: list[dict] = []

        def fake_ydl(opts):
            nonlocal call_count
            call_count += 1
            captured_opts.append(opts)
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            if call_count == 1:
                mock.download.side_effect = Exception("Sign in to confirm your age")
            else:
                mock.download.return_value = 0
            return mock

        output_file = tmp_path / "trailer.mp4"
        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            result = d.download("https://www.youtube.com/watch?v=test", output_file)

        assert call_count == 2, "bot-detection retry was not attempted"
        # Retry dropped the cookiefile — critical invariant for the "retry sans cookies" path.
        assert "cookiefile" not in captured_opts[1]
        assert result.status == DownloadStatus.SUCCESS

    def test_bot_detected_retry_fails_marks_status(self, tmp_path):
        """First attempt fails with bot detection AND retry fails → BOT_DETECTED."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        cfg = CookieConfig(cookie_file=cookie_file, cookie_from_browser=None)
        d = YtdlpDownloader(
            output_dir=tmp_path, ytdlp_format="best",
            socket_timeout_sec=10, retries=1, cookie_config=cfg,
        )
        call_count = 0

        def fake_ydl(opts):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            # Both attempts fail with the same class of error.
            mock.download.side_effect = Exception("Sign in to confirm your age")
            return mock

        output_file = tmp_path / "trailer.mp4"
        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            result = d.download("https://www.youtube.com/watch?v=test", output_file)

        assert call_count == 2  # tried with and without cookies
        assert result.status == DownloadStatus.BOT_DETECTED, (
            "bot-detection must NOT be coerced into SUCCESS when the retry also fails"
        )


# ── @pytest.mark.network E2E (opt-in) ────────────────────────────────────────

@pytest.mark.network
@pytest.mark.skipif(
    not os.getenv("TRAILER_INTEGRATION_TESTS"),
    reason="Network test — set TRAILER_INTEGRATION_TESTS=1 to run",
)
def test_download_cc_licensed_clip(tmp_path):
    """Download a stable CC-licensed clip to verify yt-dlp integration end-to-end.

    Uses the Blender Foundation's 'Agent 327' teaser — hosted on the official
    @BlenderAnimationStudio channel under Creative Commons, stable since 2017.
    """
    url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
    output_file = tmp_path / "clip-trailer.mp4"
    downloader = YtdlpDownloader(
        output_dir=tmp_path,
        ytdlp_format="worst[ext=mp4]/worst",  # smallest quality for speed
        socket_timeout_sec=60,
        retries=2,
        cookie_config=None,
    )
    result = downloader.download(url, output_file)
    assert result.status == DownloadStatus.SUCCESS
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.output_path.stat().st_size > 102400  # > 100 KiB
```

### Step 2: Implement `YtdlpDownloader`, `DownloadResult`, `DownloadStatus` in `ytdlp_downloader.py`

**Signatures:**

```python
class DownloadStatus(Enum):
    SUCCESS = "success"
    BOT_DETECTED = "bot_detected"
    YTDLP_ERROR = "ytdlp_error"
    HTTP_ERROR = "http_error"

@dataclass
class DownloadResult:
    status: DownloadStatus
    output_path: Path | None = None
    error_message: str | None = None

class YtdlpDownloader:
    def __init__(
        self,
        output_dir: Path,
        ytdlp_format: str,
        socket_timeout_sec: int,
        retries: int,
        cookie_config: CookieConfig | None,
    ) -> None: ...

    def download(self, url: str, output_path: Path) -> DownloadResult:
        """Download a video from url to output_path using yt-dlp.

        Tries with cookies first; if bot-detection error occurs, retries
        once without cookies. Never raises — returns DownloadResult.
        """
```

**Implementation notes:**
- Build opts dict: `{"format": ..., "outtmpl": str(output_path), "socket_timeout": ..., "retries": ..., "quiet": True}`.
- If `cookie_config.cookie_file`: add `"cookiefile": str(path)`.
- If `cookie_config.cookie_from_browser`: add `"cookiesfrombrowser": (browser,)`.
- Use context manager: `with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])`.
- Bot-detection detection: check exception message for `"Sign in"` or `"bot"` (case-insensitive).
- On bot-detection: retry once with cookies stripped from opts; set `status=BOT_DETECTED` if retry also fails.

### Step 3: Run tests

```bash
pytest tests/scraper/test_ytdlp_downloader.py -v -k "not network"
```

### Step 4: Commit sub-phase 3b.2

```bash
git add personalscraper/scraper/ytdlp_downloader.py tests/scraper/test_ytdlp_downloader.py
git commit -m "feat(trailer): add YtdlpDownloader with cookies handling and bot-detection retry"
```

---

## Phase 3b quality gate

- [ ] `pytest tests/scraper/test_ytdlp_downloader.py -v -k "not network"` — all green
- [ ] `python -m ruff check personalscraper/scraper/ytdlp_downloader.py` — no errors
- [ ] `python -m mypy personalscraper/scraper/ytdlp_downloader.py` — no type errors
- [ ] `pytest tests/scraper/ -q` — no regressions in other scraper tests

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/scraper/test_ytdlp_downloader.py -v -k "not network"
python -m ruff check personalscraper/scraper/ytdlp_downloader.py
python -m mypy personalscraper/scraper/ytdlp_downloader.py
pytest tests/scraper/ -q
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 03b gate — ytdlp_downloader with cookies and bot-detection retry"
```

## Exit condition for Phase 5

Phase 5 may start only when:

- `DownloadResult`, `DownloadStatus`, `YtdlpDownloader`, `CookieConfig` importable from `personalscraper.scraper.ytdlp_downloader`
- `pytest tests/scraper/ -q` exits 0
- The milestone commit is on the branch
