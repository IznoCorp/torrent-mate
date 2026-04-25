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

import os
import shutil
import signal
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# APFS/HFS+ volume roots (macOS) — cookie files must live here for security.
# This list is user-extendable via a future `config.trailers.ytdlp.cookies.native_prefixes`
# key (follow-up to the phase-07 config additions; not modified in this pass).
# TODO: replace with runtime check via os.statvfs + mount table in v0.8.0
# /private is added because macOS symlinks /tmp → /private/tmp and /var → /private/var;
# path.resolve() dereferences the symlink, so we must recognise the canonical prefix too.
_APFS_NATIVE_PREFIXES = ("/Users", "/opt", "/private", "/tmp", "/var")

# Bot-detection patterns sourced from yt-dlp error messages.
_BOT_DETECTION_PHRASES = ("sign in", "not a bot", "confirm your age")

# Default wall-clock timeout for a single download attempt (DESIGN §12).
_DEFAULT_WALL_CLOCK_SEC = 180

# Default max filesize cap; overridden by caller via max_filesize_bytes constructor arg.
# 500 MiB is a safe ceiling for trailer-quality clips (phase-07 will wire config here).
_DEFAULT_MAX_FILESIZE_BYTES = 500 * 1024 * 1024


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


def _is_bot_detection_error(message: str) -> bool:
    """Return True if the error message indicates YouTube bot-detection.

    Args:
        message: Exception message string to check.

    Returns:
        True if any known bot-detection phrase is present (case-insensitive).
    """
    lower = message.lower()
    return any(phrase in lower for phrase in _BOT_DETECTION_PHRASES)


class _WallClockTimeout(Exception):
    """Raised by the SIGALRM handler when the wall-clock timeout fires."""


def _raise_wall_clock_timeout(signum: int, frame: object) -> None:  # noqa: ARG001
    """SIGALRM handler — raises _WallClockTimeout to abort the download.

    Args:
        signum: Signal number (unused — always SIGALRM).
        frame: Current stack frame (unused).

    Raises:
        _WallClockTimeout: Always.
    """
    raise _WallClockTimeout("wall-clock timeout")


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
                raise CookieError(f"YOUTUBE_COOKIES_FILE not found: {cookie_file}")
            if not _is_apfs_native(cookie_file):
                raise CookieError(
                    f"YOUTUBE_COOKIES_FILE is on an NTFS/macFUSE volume — "
                    f"cookie files must reside on APFS-native storage for security. "
                    f"Got: {cookie_file}"
                )
            # Warn if permissions are not 600 (POSIX only — NTFS mounts report 0o777 anyway,
            # but we already rejected NTFS paths above).
            try:
                mode = cookie_file.stat().st_mode & 0o777
                if mode != stat.S_IRUSR | stat.S_IWUSR:
                    logger.warning(
                        "cookie_file_permissions_loose",
                        path=str(cookie_file),
                        mode=oct(mode),
                        recommended="600",
                    )
            except OSError:
                # Silently skip on filesystems that don't support mode bits.
                pass
            return cls(cookie_file=cookie_file, cookie_from_browser=None)

        if browser:
            return cls(cookie_file=None, cookie_from_browser=browser)

        return None


class DownloadStatus(Enum):
    """Status codes for a yt-dlp download attempt."""

    SUCCESS = "success"
    BOT_DETECTED = "bot_detected"
    YTDLP_ERROR = "ytdlp_error"
    HTTP_ERROR = "http_error"


@dataclass
class DownloadResult:
    """Result of a single yt-dlp download attempt.

    Attributes:
        status: Outcome of the download.
        output_path: Local path to the downloaded file, or None on failure.
        error_message: Human-readable error string, or None on success.
    """

    status: DownloadStatus
    output_path: Path | None = None
    error_message: str | None = None


class YtdlpDownloader:
    """yt-dlp Python API wrapper with cookie handling and bot-detection retry.

    Downloads a single video URL to a given output path. Retries once without
    cookies when bot-detection is triggered. Never raises — always returns a
    DownloadResult.

    A SIGALRM-based wall-clock timeout (Unix only) guards against hung downloads.
    On non-Unix platforms the alarm is skipped; socket_timeout_sec acts as a
    best-effort fallback.

    Args:
        output_dir: Directory where downloaded files are written.
        ytdlp_format: yt-dlp format selector string (e.g. ``"best[ext=mp4]/best"``).
        socket_timeout_sec: Network socket timeout in seconds.
        retries: Number of HTTP retries passed to yt-dlp.
        cookie_config: Optional cookie authentication configuration.
        max_filesize_bytes: Maximum allowed download size in bytes. Passed to yt-dlp
            as ``max_filesize``. Defaults to 500 MiB. Phase-07 will wire this from
            ``config.trailers.filters.max_filesize_mb``.
        max_wall_clock_sec: Wall-clock timeout for a single download attempt (Unix only).
            Defaults to 180 seconds.
    """

    def __init__(
        self,
        output_dir: Path,
        ytdlp_format: str,
        socket_timeout_sec: int,
        retries: int,
        cookie_config: CookieConfig | None,
        max_filesize_bytes: int = _DEFAULT_MAX_FILESIZE_BYTES,
        max_wall_clock_sec: int = _DEFAULT_WALL_CLOCK_SEC,
    ) -> None:
        """Initialise the downloader and check for ffmpeg on PATH.

        Args:
            output_dir: Directory where downloaded files are written.
            ytdlp_format: yt-dlp format selector string.
            socket_timeout_sec: Network socket timeout in seconds.
            retries: Number of HTTP retries passed to yt-dlp.
            cookie_config: Optional cookie authentication configuration.
            max_filesize_bytes: Maximum download size cap passed to yt-dlp.
            max_wall_clock_sec: SIGALRM wall-clock timeout (Unix only).
        """
        self._output_dir = output_dir
        self._ytdlp_format = ytdlp_format
        self._socket_timeout_sec = socket_timeout_sec
        self._retries = retries
        self._cookie_config = cookie_config
        self._max_filesize_bytes = max_filesize_bytes
        self._max_wall_clock_sec = max_wall_clock_sec

        # Check ffmpeg availability once at construction time.
        # Multi-stream downloads (separate video + audio tracks) require ffmpeg for merging.
        # Single-stream formats (e.g. "worst[ext=mp4]") still work without it.
        if shutil.which("ffmpeg") is None:
            logger.warning("ytdlp_ffmpeg_missing", hint="brew install ffmpeg / apt-get install ffmpeg")

    def _build_opts(self, output_path: Path, include_cookies: bool = True) -> dict[str, Any]:
        """Build the yt-dlp options dict for a download attempt.

        Args:
            output_path: Destination file path for the downloaded video.
            include_cookies: Whether to include cookie options from ``cookie_config``.

        Returns:
            A dict suitable for passing to ``yt_dlp.YoutubeDL(opts)``.
        """
        opts: dict[str, Any] = {
            "format": self._ytdlp_format,
            "outtmpl": str(output_path),
            "socket_timeout": self._socket_timeout_sec,
            "retries": self._retries,
            "max_filesize": self._max_filesize_bytes,
            "quiet": True,
            # Suppress yt-dlp's own progress output — structlog handles our logging.
            "no_warnings": False,
        }

        if include_cookies and self._cookie_config is not None:
            if self._cookie_config.cookie_file is not None:
                opts["cookiefile"] = str(self._cookie_config.cookie_file)
            elif self._cookie_config.cookie_from_browser is not None:
                # yt-dlp expects a tuple: (browser_name,) or (browser_name, profile)
                opts["cookiesfrombrowser"] = (self._cookie_config.cookie_from_browser,)

        return opts

    def _attempt_download(self, url: str, output_path: Path, opts: dict[str, Any]) -> None:
        """Execute a single yt-dlp download call with a wall-clock timeout guard.

        Uses SIGALRM on Unix platforms for a hard wall-clock cutoff. On non-Unix
        platforms (Windows), the alarm is skipped and socket_timeout provides
        best-effort protection.

        Args:
            url: Video URL to download.
            output_path: Destination file path (passed via opts["outtmpl"]).
            opts: yt-dlp options dict.

        Raises:
            _WallClockTimeout: When the SIGALRM fires before yt-dlp finishes.
            Exception: Any exception raised by yt-dlp itself (e.g. DownloadError).
        """
        import yt_dlp  # lazy import — yt-dlp is a runtime-only dependency

        has_sigalrm = hasattr(signal, "SIGALRM")

        if has_sigalrm:
            # Install the timeout handler and arm the alarm.
            old_handler = signal.signal(signal.SIGALRM, _raise_wall_clock_timeout)
            signal.alarm(self._max_wall_clock_sec)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        finally:
            if has_sigalrm:
                # Disarm the alarm regardless of outcome and restore the previous handler.
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

    def download(self, url: str, output_path: Path) -> DownloadResult:
        """Download a video from url to output_path using yt-dlp.

        Tries with cookies first; if bot-detection error occurs, retries
        once without cookies. Never raises — returns DownloadResult.

        Args:
            url: YouTube (or other yt-dlp-supported) video URL.
            output_path: Destination file path for the downloaded video.

        Returns:
            DownloadResult with status and optional path or error message.
        """
        # --- First attempt (with cookies if configured) ---
        opts = self._build_opts(output_path, include_cookies=True)
        try:
            self._attempt_download(url, output_path, opts)
            logger.info("ytdlp_download_success", url=url, output_path=str(output_path))
            return DownloadResult(status=DownloadStatus.SUCCESS, output_path=output_path)
        except _WallClockTimeout:
            logger.warning("ytdlp_download_timeout", url=url, wall_clock_sec=self._max_wall_clock_sec)
            return DownloadResult(
                status=DownloadStatus.YTDLP_ERROR,
                error_message="wall-clock timeout",
            )
        except Exception as exc:  # noqa: BLE001 — yt-dlp raises untyped DownloadError
            error_msg = str(exc)
            if not _is_bot_detection_error(error_msg):
                # Non-bot error — do not retry.
                logger.warning("ytdlp_download_error", url=url, error=error_msg)
                return DownloadResult(
                    status=DownloadStatus.YTDLP_ERROR,
                    error_message=error_msg,
                )
            # --- Bot-detection: retry without cookies ---
            logger.warning(
                "ytdlp_bot_detected_retrying",
                url=url,
                error=error_msg,
                hint="retrying without cookies",
            )
            opts_no_cookies = self._build_opts(output_path, include_cookies=False)
            try:
                self._attempt_download(url, output_path, opts_no_cookies)
                logger.info("ytdlp_download_success_no_cookies", url=url, output_path=str(output_path))
                return DownloadResult(status=DownloadStatus.SUCCESS, output_path=output_path)
            except _WallClockTimeout:
                logger.warning(
                    "ytdlp_download_timeout_no_cookies",
                    url=url,
                    wall_clock_sec=self._max_wall_clock_sec,
                )
                return DownloadResult(
                    status=DownloadStatus.YTDLP_ERROR,
                    error_message="wall-clock timeout (retry without cookies)",
                )
            except Exception as retry_exc:  # noqa: BLE001
                retry_msg = str(retry_exc)
                logger.warning("ytdlp_bot_detected_retry_failed", url=url, error=retry_msg)
                return DownloadResult(
                    status=DownloadStatus.BOT_DETECTED,
                    error_message=retry_msg,
                )
