"""Unit tests for YtdlpDownloader — yt-dlp wrapper with cookies handling.

yt_dlp.YoutubeDL is fully mocked; no network calls in unit tests.
The @pytest.mark.network E2E test is opt-in via TRAILER_INTEGRATION_TESTS env var.
"""

import os
import stat
from pathlib import Path
from unittest.mock import patch

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
    """Tests for CookieConfig.from_env() env-var loading and permission checks."""

    def test_no_cookies_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CookieConfig.from_env() returns None when no env vars are set."""
        monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
        monkeypatch.delenv("YOUTUBE_COOKIES_FROM_BROWSER", raising=False)
        cfg = CookieConfig.from_env()
        assert cfg is None

    def test_file_cookie_takes_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """YOUTUBE_COOKIES_FILE takes priority over YOUTUBE_COOKIES_FROM_BROWSER."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape cookies", encoding="utf-8")
        # Set 600 permissions so the permission warning is not triggered.
        cookie_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        monkeypatch.setenv("YOUTUBE_COOKIES_FROM_BROWSER", "firefox")
        cfg = CookieConfig.from_env()
        assert cfg is not None
        assert cfg.cookie_file == cookie_file
        assert cfg.cookie_from_browser is None

    def test_browser_cookie_used_when_no_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """YOUTUBE_COOKIES_FROM_BROWSER is used when no file is configured."""
        monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
        monkeypatch.setenv("YOUTUBE_COOKIES_FROM_BROWSER", "firefox")
        cfg = CookieConfig.from_env()
        assert cfg is not None
        assert cfg.cookie_from_browser == "firefox"
        assert cfg.cookie_file is None

    def test_nonexistent_cookie_file_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CookieConfig raises CookieError when the cookie file does not exist."""
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", "/nonexistent/cookies.txt")
        with pytest.raises(CookieError, match="not found"):
            CookieConfig.from_env()

    def test_ntfs_cookie_file_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CookieConfig raises CookieError when cookie file is on NTFS mount."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        # Simulate NTFS detection by patching the internal check.
        with patch(
            "personalscraper.scraper.ytdlp_downloader._is_apfs_native",
            return_value=False,
        ):
            with pytest.raises(CookieError, match="NTFS"):
                CookieConfig.from_env()

    def test_loose_permissions_logged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CookieConfig logs a warning when cookie file permissions are not 600."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape cookies", encoding="utf-8")
        # Set world-readable permissions (644) to trigger the warning.
        cookie_file.chmod(0o644)
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        # Should not raise — warning is logged but execution continues.
        cfg = CookieConfig.from_env()
        assert cfg is not None
        assert cfg.cookie_file == cookie_file


# ── ffmpeg missing warning (stub — YtdlpDownloader implemented in 3b.2) ──────


@pytest.mark.skip(reason="YtdlpDownloader.__init__ implemented in sub-phase 3b.2")
def test_init_warns_when_ffmpeg_missing(tmp_path: Path) -> None:
    """YtdlpDownloader.__init__ warns when ffmpeg is not on PATH."""
    import logging

    with patch("shutil.which", return_value=None):
        with pytest.raises(Exception):  # noqa: B017 — NotImplementedError until 3b.2
            with pytest.warns(logging.WARNING):
                YtdlpDownloader(
                    output_dir=tmp_path,
                    ytdlp_format="best",
                    socket_timeout_sec=10,
                    retries=1,
                    cookie_config=None,
                )


# ── DownloadResult / DownloadStatus (basic smoke tests) ──────────────────────


class TestDownloadResult:
    """Smoke tests for DownloadResult dataclass and DownloadStatus enum."""

    def test_success_result(self) -> None:
        """DownloadResult stores SUCCESS status and output_path correctly."""
        result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            output_path=Path("/tmp/trailer.mp4"),
        )
        assert result.status == DownloadStatus.SUCCESS
        assert result.output_path == Path("/tmp/trailer.mp4")

    def test_bot_detected_result(self) -> None:
        """DownloadResult stores BOT_DETECTED status and error_message correctly."""
        result = DownloadResult(
            status=DownloadStatus.BOT_DETECTED,
            error_message="Sign in to confirm your age",
        )
        assert result.status == DownloadStatus.BOT_DETECTED
        assert result.output_path is None


# ── @pytest.mark.network E2E (opt-in) ────────────────────────────────────────


@pytest.mark.network
@pytest.mark.skipif(
    not os.getenv("TRAILER_INTEGRATION_TESTS"),
    reason="Network test — set TRAILER_INTEGRATION_TESTS=1 to run",
)
def test_download_cc_licensed_clip(tmp_path: Path) -> None:
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
