"""Unit tests for YtdlpDownloader — yt-dlp wrapper with cookies handling.

yt_dlp.YoutubeDL is fully mocked; no network calls in unit tests.
The @pytest.mark.network E2E test is opt-in via TRAILER_INTEGRATION_TESTS env var.
"""

import logging
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
    """Tests for CookieConfig.from_env() env-var loading and permission checks."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache(self) -> None:
        """Bust the get_settings() lru_cache before each test.

        from_env() goes through get_settings() which is @lru_cache. Without this
        clear, monkeypatch.setenv() has no effect for tests sharing a worker
        with a previous test that already populated the cache (xdist races).
        """
        from personalscraper.config import get_settings

        get_settings.cache_clear()

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

    def test_loose_permissions_logged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """CookieConfig logs a warning when cookie file permissions are not 600."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape cookies", encoding="utf-8")
        # Set world-readable permissions (644) to trigger the warning.
        cookie_file.chmod(0o644)
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        with caplog.at_level(logging.WARNING):
            cfg = CookieConfig.from_env()
        assert cfg is not None
        assert cfg.cookie_file == cookie_file
        assert "cookie_file_permissions_loose" in caplog.text

    def test_direct_constructor_rejects_both_sources(self, tmp_path: Path) -> None:
        """CookieConfig(cookie_file=..., cookie_from_browser=...) raises CookieError."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        with pytest.raises(CookieError, match="at most one"):
            CookieConfig(cookie_file=cookie_file, cookie_from_browser="firefox")

    def test_direct_constructor_rejects_no_source(self) -> None:
        """CookieConfig(None, None) raises CookieError — callers must pass None instead."""
        with pytest.raises(CookieError, match="requires one of"):
            CookieConfig(cookie_file=None, cookie_from_browser=None)


class TestBotDetectionPhrases:
    """All known bot-detection phrases must trigger the retry-without-cookies path."""

    @pytest.mark.parametrize(
        "phrase",
        [
            "Sign in to confirm your age",
            "We need to make sure you're not a bot",
            "Please confirm your age to continue",
        ],
    )
    def test_phrase_triggers_bot_detected_path(self, tmp_path: Path, phrase: str) -> None:
        """A typo dropping any phrase from the tuple would fail this test."""
        from personalscraper.scraper.ytdlp_downloader import _is_bot_detection_error

        assert _is_bot_detection_error(phrase) is True


class TestSigalrmTimeout:
    """SIGALRM-based wall-clock timeout fires when yt-dlp hangs."""

    def test_timeout_returns_ytdlp_error(self, tmp_path: Path) -> None:
        """A yt-dlp call exceeding max_wall_clock_sec returns YTDLP_ERROR."""
        import signal as _signal
        import time as _time

        if not hasattr(_signal, "SIGALRM"):  # pragma: no cover — Windows
            pytest.skip("SIGALRM not available on this platform")

        downloader = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=0,
            cookie_config=None,
            max_wall_clock_sec=1,
        )

        def slow_download(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            mock = _make_mock_ydl()
            # Block longer than the 1s alarm; SIGALRM should interrupt this.
            mock.download.side_effect = lambda urls: _time.sleep(5)
            return mock

        out = tmp_path / "trailer.mp4"
        with patch("yt_dlp.YoutubeDL", side_effect=slow_download):
            result = downloader.download("https://www.youtube.com/watch?v=t", out)

        assert result.status == DownloadStatus.YTDLP_ERROR
        assert result.error_message == "wall-clock timeout"


# ── ffmpeg missing warning ────────────────────────────────────────────────────


def test_init_warns_when_ffmpeg_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """YtdlpDownloader.__init__ logs ytdlp_ffmpeg_missing at WARNING when ffmpeg absent."""
    with patch("shutil.which", return_value=None):
        with caplog.at_level(logging.WARNING):
            YtdlpDownloader(
                output_dir=tmp_path,
                ytdlp_format="best",
                socket_timeout_sec=10,
                retries=1,
                cookie_config=None,
            )
    assert "ytdlp_ffmpeg_missing" in caplog.text


# ── DownloadResult / DownloadStatus ──────────────────────────────────────────


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


# ── YtdlpDownloader (mocked yt_dlp) ──────────────────────────────────────────


def _make_mock_ydl(return_value: int = 0) -> MagicMock:
    """Return a context-manager-compatible YoutubeDL mock.

    Args:
        return_value: Value returned by mock.download().

    Returns:
        A MagicMock whose __enter__ returns itself and download() returns return_value.
    """
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.download.return_value = return_value
    return mock


@pytest.fixture()
def downloader(tmp_path: Path) -> YtdlpDownloader:
    """Provide a default YtdlpDownloader for unit tests (no cookies, no network)."""
    return YtdlpDownloader(
        output_dir=tmp_path,
        ytdlp_format="best[ext=mp4]/best",
        socket_timeout_sec=30,
        retries=3,
        cookie_config=None,
    )


class TestYtdlpDownloader:
    """Unit tests for YtdlpDownloader.download() — yt_dlp.YoutubeDL fully mocked."""

    def test_download_success(self, downloader: YtdlpDownloader, tmp_path: Path) -> None:
        """download() returns SUCCESS when YoutubeDL.download() exits cleanly."""
        output_file = tmp_path / "test-trailer.mp4"

        with patch("yt_dlp.YoutubeDL") as MockYDL:
            instance = MockYDL.return_value.__enter__.return_value
            # Simulate yt-dlp writing the output file.
            instance.download.side_effect = lambda urls: output_file.write_bytes(b"x") or 0
            result = downloader.download(
                "https://www.youtube.com/watch?v=test",
                output_file,
            )

        assert result.status == DownloadStatus.SUCCESS

    def test_opts_dict_contains_format(self, downloader: YtdlpDownloader, tmp_path: Path) -> None:
        """download() passes format option to YoutubeDL."""
        output_file = tmp_path / "trailer.mp4"
        captured_opts: list[dict] = []  # type: ignore[type-arg]

        def capture_opts(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            captured_opts.append(opts)
            return _make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=capture_opts):
            downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert captured_opts[0]["format"] == "best[ext=mp4]/best"

    def test_opts_outtmpl_strips_extension_and_pins_mp4(self, downloader: YtdlpDownloader, tmp_path: Path) -> None:
        """Outtmpl drops the caller's extension and pins merge to mp4.

        Regression: prior to the fix, passing "...-trailer.mp4" as ``output_path``
        made yt-dlp produce "...-trailer.mp4.webm" because yt-dlp interprets the
        outtmpl extension as a literal part of the filename and appends the real
        format ext on top. The fix strips the suffix and lets yt-dlp inject the
        merged container ext via %(ext)s, with merge_output_format=mp4 forcing
        ffmpeg to remux to .mp4.
        """
        output_file = tmp_path / "show-trailer.mp4"
        captured_opts: list[dict] = []  # type: ignore[type-arg]

        def capture_opts(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            captured_opts.append(opts)
            return _make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=capture_opts):
            downloader.download("https://www.youtube.com/watch?v=test", output_file)

        opts = captured_opts[0]
        # The outtmpl must NOT contain the caller's literal ".mp4" before %(ext)s,
        # otherwise yt-dlp would emit ".mp4.<actual_ext>".
        assert opts["outtmpl"] == f"{tmp_path / 'show-trailer'}.%(ext)s"
        assert opts["merge_output_format"] == "mp4"
        assert opts["final_ext"] == "mp4"

    def test_opts_dict_contains_retries(self, downloader: YtdlpDownloader, tmp_path: Path) -> None:
        """download() passes retries option to YoutubeDL."""
        output_file = tmp_path / "trailer.mp4"
        captured_opts: list[dict] = []  # type: ignore[type-arg]

        def capture_opts(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            captured_opts.append(opts)
            return _make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=capture_opts):
            downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert captured_opts[0]["retries"] == 3

    def test_cookie_file_added_to_opts(self, tmp_path: Path) -> None:
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
        captured_opts: list[dict] = []  # type: ignore[type-arg]

        def capture_opts(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            captured_opts.append(opts)
            return _make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=capture_opts):
            d.download("https://www.youtube.com/watch?v=test", output_file)

        assert str(cookie_file) in str(captured_opts[0].get("cookiefile", ""))

    def test_bot_detected_retry_succeeds_without_cookies(self, tmp_path: Path) -> None:
        """First attempt fails with bot detection; retry without cookies SUCCEEDS."""
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
        call_count = 0
        captured_opts: list[dict] = []  # type: ignore[type-arg]
        output_file = tmp_path / "trailer.mp4"

        def fake_ydl(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            nonlocal call_count
            call_count += 1
            captured_opts.append(opts)
            mock = _make_mock_ydl()
            if call_count == 1:
                # First call: simulate bot detection.
                mock.download.side_effect = Exception("Sign in to confirm your age")
            else:
                # Second call (retry without cookies): write the output file so that
                # _verify_output() reports success.
                mock.download.side_effect = lambda urls: output_file.write_bytes(b"x" * 1024) or 0
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            result = d.download("https://www.youtube.com/watch?v=test", output_file)

        assert call_count == 2, "bot-detection retry was not attempted"
        # Retry must have dropped the cookiefile — critical invariant.
        assert "cookiefile" not in captured_opts[1]
        assert result.status == DownloadStatus.SUCCESS

    def test_bot_detected_retry_fails_marks_status(self, tmp_path: Path) -> None:
        """First attempt fails with bot detection AND retry fails → BOT_DETECTED."""
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
        call_count = 0

        def fake_ydl(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            nonlocal call_count
            call_count += 1
            mock = _make_mock_ydl()
            # Both attempts fail with bot-detection error.
            mock.download.side_effect = Exception("Sign in to confirm your age")
            return mock

        output_file = tmp_path / "trailer.mp4"
        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            result = d.download("https://www.youtube.com/watch?v=test", output_file)

        assert call_count == 2, "expected two attempts (with and without cookies)"
        assert result.status == DownloadStatus.BOT_DETECTED, (
            "bot-detection must NOT be coerced into SUCCESS when the retry also fails"
        )


# ── Sub-phase 10.1 new tests ─────────────────────────────────────────────────


class TestOutputVerification:
    """C3 — download() verifies the output file after a successful yt-dlp call."""

    def test_download_returns_ytdlp_error_when_output_extension_mismatch(
        self, downloader: YtdlpDownloader, tmp_path: Path
    ) -> None:
        """Returns YTDLP_ERROR when yt-dlp writes a .webm instead of the expected .mp4.

        This simulates an ffmpeg-merge failure: yt-dlp writes the raw video stream
        at the .webm path while result.output_path claims .mp4.
        """
        output_file = tmp_path / "movie-trailer.mp4"
        # yt-dlp writes a .webm sibling instead of the expected .mp4.
        sibling_webm = tmp_path / "movie-trailer.webm"

        def fake_download(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            # Write .webm — not .mp4 — simulating a failed ffmpeg remux.
            sibling_webm.write_bytes(b"x" * 1024)
            return _make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=fake_download):
            result = downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert result.status == DownloadStatus.YTDLP_ERROR
        assert result.error_message is not None
        assert ".webm" in result.error_message
        assert "mismatch" in result.error_message

    def test_download_returns_ytdlp_error_when_output_missing(
        self, downloader: YtdlpDownloader, tmp_path: Path
    ) -> None:
        """Returns YTDLP_ERROR when yt-dlp exits cleanly but writes no file at all."""
        output_file = tmp_path / "movie-trailer.mp4"

        def fake_download(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            # Write nothing — simulates yt-dlp silently producing no output.
            return _make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=fake_download):
            result = downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert result.status == DownloadStatus.YTDLP_ERROR
        assert result.error_message == "downloaded file missing"


class TestPartialFileCleanup:
    """C4 — download() removes partial files on every non-success path."""

    def test_download_cleans_up_partial_files_on_exception(self, downloader: YtdlpDownloader, tmp_path: Path) -> None:
        """Partial files (.part, .frag1) are removed when yt-dlp raises an exception.

        The expected .mp4 output is NOT created; only the partial intermediates are
        present before the exception fires.
        """
        output_file = tmp_path / "movie-trailer.mp4"
        # Pre-create partial files that yt-dlp would leave behind.
        part_file = tmp_path / "movie-trailer.part"
        frag_file = tmp_path / "movie-trailer.frag1"
        part_file.write_bytes(b"partial data")
        frag_file.write_bytes(b"fragment data")

        def fake_download(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            mock = _make_mock_ydl()
            mock.download.side_effect = Exception("Connection reset by peer")
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=fake_download):
            result = downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert result.status == DownloadStatus.YTDLP_ERROR
        # Both partial files must be gone after the cleanup sweep.
        assert not part_file.exists(), ".part file was not cleaned up"
        assert not frag_file.exists(), ".frag1 file was not cleaned up"
        # The expected .mp4 was never created — no file should exist.
        assert not output_file.exists()


class TestRetryTransportErrorClassification:
    """I3 — retry-without-cookies path re-classifies exceptions correctly."""

    def test_retry_without_cookies_classifies_transport_error_as_ytdlp_error(self, tmp_path: Path) -> None:
        """A transport error on the cookie-less retry returns YTDLP_ERROR, not BOT_DETECTED.

        Before the fix every exception in the retry was classified as BOT_DETECTED,
        which made the state store exempt those entries from next_retry_at and
        retry them on every single run (infinite re-attempts on transport errors).
        """
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
        call_count = 0

        def fake_ydl(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            nonlocal call_count
            call_count += 1
            mock = _make_mock_ydl()
            if call_count == 1:
                # First attempt: bot-detection triggers the retry path.
                mock.download.side_effect = Exception("Sign in to confirm your age")
            else:
                # Second attempt: a real transport error (not bot-detection).
                mock.download.side_effect = Exception("Connection reset by peer")
            return mock

        output_file = tmp_path / "trailer.mp4"
        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            result = d.download("https://www.youtube.com/watch?v=test", output_file)

        assert call_count == 2, "expected exactly two attempts"
        # Transport error on retry must be classified as YTDLP_ERROR so that the
        # state store schedules a normal retry-after cooldown.
        assert result.status == DownloadStatus.YTDLP_ERROR, (
            f"expected YTDLP_ERROR for transport error on retry, got {result.status}"
        )


# ── Extra coverage — settings fallback, stat-OSError, browser cookies, ──────
# ── timeout-on-retry, post-retry verify-fail, partial cleanup OSError, etc. ─


class TestFromEnvSettingsFallback:
    """Cover the get_settings() exception → bare-env fallback (lines 157-167)."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache(self) -> None:
        """Reset get_settings() lru_cache between tests."""
        from personalscraper.config import get_settings

        get_settings.cache_clear()

    def test_settings_validation_error_falls_back_to_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If get_settings() raises ValidationError, the env vars are read directly."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        cookie_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        monkeypatch.delenv("YOUTUBE_COOKIES_FROM_BROWSER", raising=False)

        from pydantic import BaseModel, ValidationError

        # Build a real ValidationError — it's used by the except clause.
        try:

            class _M(BaseModel):
                x: int

            _M(x="not-an-int")  # type: ignore[arg-type]
        except ValidationError as ve:
            fake_error = ve

        # ``get_settings`` is imported lazily inside ``from_env`` — patch the
        # canonical location so the lazy import resolves to our side-effect.
        with patch(
            "personalscraper.config.get_settings",
            side_effect=fake_error,
        ):
            cfg = CookieConfig.from_env()

        assert cfg is not None
        assert cfg.cookie_file == cookie_file


class TestCookieStatFailure:
    """Cover the OSError branch in cookie_file.stat() (lines 193-196)."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache(self) -> None:
        """Reset get_settings() lru_cache between tests."""
        from personalscraper.config import get_settings

        get_settings.cache_clear()

    def test_stat_oserror_logged_at_debug_and_continues(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When stat() raises OSError (e.g. NTFS mount), we log at DEBUG and continue."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookie_file))
        monkeypatch.delenv("YOUTUBE_COOKIES_FROM_BROWSER", raising=False)

        # Selectively raise OSError only on the stat() call performed for the
        # permission audit (line 185 in ytdlp_downloader.py). Use frame-caller
        # inspection so we don't depend on Path.exists() internals — those
        # differ across Python versions (3.10/3.11 call stat() without kwargs,
        # 3.12+ adds follow_symlinks=True), making kwarg-based filtering
        # version-fragile.
        import inspect

        original_stat = Path.stat

        def selective_stat(self: Path, *args: object, **kwargs: object) -> object:
            if self == cookie_file:
                frame = inspect.currentframe()
                caller = frame.f_back if frame else None
                if caller and caller.f_code.co_filename.endswith("ytdlp_downloader.py"):
                    raise OSError("mount detached")
            return original_stat(self, *args, **kwargs)  # type: ignore[arg-type]

        with patch.object(Path, "stat", selective_stat):
            with caplog.at_level(logging.DEBUG, logger="personalscraper.scraper.ytdlp_downloader"):
                cfg = CookieConfig.from_env()

        assert cfg is not None
        assert cfg.cookie_file == cookie_file
        assert "cookie_file_stat_failed" in caplog.text


class TestBrowserCookiesOpts:
    """Cover the cookiesfrombrowser opts-building branch (lines 333-335)."""

    def test_browser_cookies_passed_to_ytdlp(self, tmp_path: Path) -> None:
        """download() forwards cookiesfrombrowser=(browser,) when browser cookies are configured."""
        cfg = CookieConfig(cookie_file=None, cookie_from_browser="firefox")
        d = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=1,
            cookie_config=cfg,
        )
        captured: list[dict] = []  # type: ignore[type-arg]
        output_file = tmp_path / "trailer.mp4"

        def capture(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            captured.append(opts)
            mock = _make_mock_ydl()
            mock.download.side_effect = lambda urls: output_file.write_bytes(b"x" * 1024) or 0
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=capture):
            d.download("https://www.youtube.com/watch?v=test", output_file)

        assert captured[0]["cookiesfrombrowser"] == ("firefox",)
        assert "cookiefile" not in captured[0]


class TestNoSigalrmPlatform:
    """Cover the has_sigalrm=False branches (360->365, 369->exit)."""

    def test_download_works_without_sigalrm(self, tmp_path: Path) -> None:
        """When SIGALRM is unavailable, the download still runs without arming the alarm."""
        downloader = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=0,
            cookie_config=None,
        )
        output_file = tmp_path / "clip.mp4"

        # Patch hasattr so the SIGALRM gate evaluates to False inside _attempt_download.
        import personalscraper.scraper.ytdlp_downloader as mod

        original_hasattr = mod.hasattr if hasattr(mod, "hasattr") else hasattr

        def fake_hasattr(obj: object, name: str) -> bool:
            if name == "SIGALRM":
                return False
            return original_hasattr(obj, name)

        with patch("personalscraper.scraper.ytdlp_downloader.hasattr", fake_hasattr, create=True):
            with patch("yt_dlp.YoutubeDL") as MockYDL:
                instance = MockYDL.return_value.__enter__.return_value
                instance.download.side_effect = lambda urls: output_file.write_bytes(b"x" * 1024) or 0
                result = downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert result.status == DownloadStatus.SUCCESS


class TestEmptyOutputFile:
    """Cover the size<=0 branch in _verify_output (lines 411-413)."""

    def test_empty_output_returns_ytdlp_error(self, tmp_path: Path) -> None:
        """When yt-dlp creates a zero-byte file, _verify_output returns YTDLP_ERROR."""
        downloader = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=0,
            cookie_config=None,
        )
        output_file = tmp_path / "empty.mp4"

        def fake_dl(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            mock = _make_mock_ydl()
            # Create the file but with zero bytes.
            mock.download.side_effect = lambda urls: output_file.write_bytes(b"") or 0
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=fake_dl):
            result = downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert result.status == DownloadStatus.YTDLP_ERROR
        assert result.error_message is not None
        assert "empty" in result.error_message


class TestCleanupPartialFilesOSError:
    """Cover unlink-failure branch in _cleanup_partial_files (lines 434, 438-439)."""

    def test_cleanup_partial_unlink_oserror_logged(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """An OSError on candidate.unlink() is logged but does not abort cleanup."""
        downloader = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=0,
            cookie_config=None,
        )
        output_file = tmp_path / "clip.mp4"
        # Pre-create partial files; one (.part) will fail to unlink.
        part = tmp_path / "clip.part"
        frag = tmp_path / "clip.frag1"
        part.write_bytes(b"x")
        frag.write_bytes(b"y")

        def fake_dl(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            mock = _make_mock_ydl()
            # yt-dlp raises a non-bot exception so the cleanup branch fires.
            mock.download.side_effect = Exception("Connection reset")
            return mock

        original_unlink = Path.unlink

        def flaky_unlink(self: Path, *args: object, **kwargs: object) -> None:
            if self == part:
                raise OSError(errno.EACCES, "unlink denied")
            original_unlink(self, *args, **kwargs)

        import errno

        with patch("yt_dlp.YoutubeDL", side_effect=fake_dl):
            with patch.object(Path, "unlink", flaky_unlink):
                with caplog.at_level(logging.WARNING):
                    downloader.download("https://www.youtube.com/watch?v=test", output_file)

        assert "ytdlp_partial_cleanup_error" in caplog.text


class TestRetryTimeout:
    """Cover wall-clock timeout on the retry-without-cookies path (lines 503-510)."""

    def test_retry_timeout_returns_ytdlp_error(self, tmp_path: Path) -> None:
        """A SIGALRM timeout fires during the retry → YTDLP_ERROR with retry-marker message."""
        import signal as _signal

        if not hasattr(_signal, "SIGALRM"):  # pragma: no cover — Windows
            pytest.skip("SIGALRM not available")

        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        cfg = CookieConfig(cookie_file=cookie_file, cookie_from_browser=None)
        d = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=0,
            cookie_config=cfg,
            max_wall_clock_sec=1,
        )
        output_file = tmp_path / "clip.mp4"
        call_count = 0

        def fake_dl(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            nonlocal call_count
            call_count += 1
            mock = _make_mock_ydl()
            if call_count == 1:
                # First call: bot-detection triggers retry.
                mock.download.side_effect = Exception("Sign in to confirm your age")
            else:
                # Second call: hang long enough for SIGALRM to fire.
                import time as _time

                mock.download.side_effect = lambda urls: _time.sleep(5)
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=fake_dl):
            result = d.download("https://www.youtube.com/watch?v=test", output_file)

        assert call_count == 2
        assert result.status == DownloadStatus.YTDLP_ERROR
        assert "retry without cookies" in (result.error_message or "")


class TestPostRetryVerifyFail:
    """Cover post-retry _verify_output fail branch (lines 544-545)."""

    def test_retry_succeeds_but_output_missing_returns_ytdlp_error(self, tmp_path: Path) -> None:
        """Retry call returns cleanly but produces no file → verify fails → YTDLP_ERROR."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# cookies", encoding="utf-8")
        cfg = CookieConfig(cookie_file=cookie_file, cookie_from_browser=None)
        d = YtdlpDownloader(
            output_dir=tmp_path,
            ytdlp_format="best",
            socket_timeout_sec=10,
            retries=0,
            cookie_config=cfg,
        )
        output_file = tmp_path / "clip.mp4"
        call_count = 0

        def fake_dl(opts: dict) -> MagicMock:  # type: ignore[type-arg]
            nonlocal call_count
            call_count += 1
            mock = _make_mock_ydl()
            if call_count == 1:
                mock.download.side_effect = Exception("Sign in to confirm your age")
            else:
                # Retry exits cleanly without writing the file.
                mock.download.return_value = 0
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=fake_dl):
            result = d.download("https://www.youtube.com/watch?v=test", output_file)

        assert call_count == 2
        assert result.status == DownloadStatus.YTDLP_ERROR
        assert result.error_message == "downloaded file missing"


# ── @pytest.mark.network E2E (opt-in) ────────────────────────────────────────


@pytest.mark.network
@pytest.mark.skipif(
    not os.getenv("YOUTUBE_API_KEY"),
    reason="Network test — requires .env with YOUTUBE_API_KEY (skipped on CI)",
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
