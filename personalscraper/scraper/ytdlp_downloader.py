"""yt-dlp wrapper with cookies handling and retry-without-cookies fallback.

Provides:
- ``CookieConfig``: reads YOUTUBE_COOKIES_FILE / YOUTUBE_COOKIES_FROM_BROWSER
  from env, validates filesystem permissions (APFS-only, mode 600 check).
- ``YtdlpDownloader``: calls ``yt_dlp.YoutubeDL(opts).download([url])``
  with retry-without-cookies on bot-detection failure. (Implemented in sub-phase 3b.2.)
- ``DownloadResult``: typed result with status, output path, error message.

yt-dlp is invoked via its Python API only — no subprocess, no shell interpolation.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# APFS/HFS+ volume roots (macOS) — cookie files must live here for security.
# This list is user-extendable via a future `config.trailers.ytdlp.cookies.native_prefixes`
# key (follow-up to the phase-07 config additions; not modified in this pass).
# TODO: replace with runtime check via os.statvfs + mount table in v0.8.0
# /private is added because macOS symlinks /tmp → /private/tmp and /var → /private/var;
# path.resolve() dereferences the symlink, so we must recognise the canonical prefix too.
_APFS_NATIVE_PREFIXES = ("/Users", "/opt", "/private", "/tmp", "/var")


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


# ── Stubs for sub-phase 3b.2 ────────────────────────────────────────────────
# These are declared here so that test collection does not fail while
# YtdlpDownloader is not yet implemented (implemented in sub-phase 3b.2).


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

    Not yet implemented — stub present to allow test file collection.
    Full implementation in sub-phase 3b.2.

    Args:
        output_dir: Directory where downloaded files are written.
        ytdlp_format: yt-dlp format selector string (e.g. ``"best[ext=mp4]/best"``).
        socket_timeout_sec: Network socket timeout in seconds.
        retries: Number of HTTP retries passed to yt-dlp.
        cookie_config: Optional cookie authentication configuration.
    """

    def __init__(
        self,
        output_dir: Path,
        ytdlp_format: str,
        socket_timeout_sec: int,
        retries: int,
        cookie_config: CookieConfig | None,
    ) -> None:
        """Initialise the downloader and check for ffmpeg on PATH.

        Args:
            output_dir: Directory where downloaded files are written.
            ytdlp_format: yt-dlp format selector string.
            socket_timeout_sec: Network socket timeout in seconds.
            retries: Number of HTTP retries passed to yt-dlp.
            cookie_config: Optional cookie authentication configuration.
        """
        raise NotImplementedError("YtdlpDownloader is implemented in sub-phase 3b.2")

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
        raise NotImplementedError("YtdlpDownloader is implemented in sub-phase 3b.2")
