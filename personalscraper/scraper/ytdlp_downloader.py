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

from pydantic import ValidationError

from personalscraper.logger import get_logger

logger = get_logger(__name__)

# APFS/HFS+ volume roots (macOS) — cookie files must live here for security.
# /private is included because macOS symlinks /tmp → /private/tmp and /var → /private/var;
# path.resolve() dereferences the symlink, so we must also recognise the canonical prefix.
_APFS_NATIVE_PREFIXES = ("/Users", "/opt", "/private", "/tmp", "/var")

# Bot-detection patterns sourced from yt-dlp error messages.
_BOT_DETECTION_PHRASES = ("sign in", "not a bot", "confirm your age")

# Default wall-clock timeout for a single download attempt (DESIGN §12).
_DEFAULT_WALL_CLOCK_SEC = 180

# Default max filesize cap; overridden by caller via max_filesize_bytes constructor arg.
# 500 MiB is a safe ceiling for trailer-quality clips.
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


@dataclass(frozen=True, slots=True)
class CookieConfig:
    """Cookie authentication configuration for yt-dlp.

    Exactly one of ``cookie_file`` and ``cookie_from_browser`` must be set;
    the dual-empty case has no meaning (callers should pass ``None`` instead
    of a CookieConfig). The mutual-exclusion check runs at construction so
    the dual-source ambiguity never reaches yt-dlp.

    Attributes:
        cookie_file: Path to a static Netscape-format cookies.txt, or None.
        cookie_from_browser: Browser profile name for live extraction, or None.
    """

    cookie_file: Path | None
    cookie_from_browser: str | None

    def __post_init__(self) -> None:
        """Enforce mutual exclusion between cookie sources.

        Raises:
            CookieError: If both fields are set or both are None.
        """
        has_file = self.cookie_file is not None
        has_browser = self.cookie_from_browser is not None
        if has_file and has_browser:
            raise CookieError(
                "CookieConfig accepts at most one of cookie_file / cookie_from_browser",
            )
        if not has_file and not has_browser:
            raise CookieError(
                "CookieConfig requires one of cookie_file / cookie_from_browser; "
                "callers should pass None instead of an empty CookieConfig",
            )

    @classmethod
    def from_env(cls) -> "CookieConfig | None":
        """Build CookieConfig from Settings (.env-loaded) or process env.

        Reads ``settings.youtube_cookies_file`` and
        ``settings.youtube_cookies_from_browser`` first (so values from a
        ``.env`` file load via pydantic-settings), then falls back to raw env
        vars for backward compatibility with explicit ``os.environ`` overrides.

        Priority: YOUTUBE_COOKIES_FILE > YOUTUBE_COOKIES_FROM_BROWSER > None.

        Returns:
            CookieConfig if any value is set, None otherwise.

        Raises:
            CookieError: If YOUTUBE_COOKIES_FILE is set but the file does not
                exist, or is on an NTFS/macFUSE volume.
        """
        # Settings is the canonical source — it auto-loads .env via pydantic-settings.
        # Falling back to os.getenv preserves the contract for callers who prefer to set
        # the env var directly (CI, tests with monkeypatch.setenv).
        from personalscraper.config import get_settings  # noqa: PLC0415

        try:
            settings = get_settings()
        except (ImportError, ValidationError) as exc:
            # Settings construction can fail when .env parsing breaks or a required
            # field is malformed. Log loud enough to surface the misconfig but fall
            # back to bare env so cookies aren't silently disabled.
            logger.debug(
                "cookie_config_settings_unavailable",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            file_path_str = os.getenv("YOUTUBE_COOKIES_FILE")
            browser = os.getenv("YOUTUBE_COOKIES_FROM_BROWSER")
        else:
            file_path_str = settings.youtube_cookies_file or os.getenv("YOUTUBE_COOKIES_FILE")
            browser = settings.youtube_cookies_from_browser or os.getenv("YOUTUBE_COOKIES_FROM_BROWSER")

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
            except OSError as exc:
                # NTFS/macFUSE-style mounts don't expose mode bits reliably.
                # Log at DEBUG so a permission audit can still see the failure.
                logger.debug(
                    "cookie_file_stat_failed",
                    path=str(cookie_file),
                    error=str(exc),
                )
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
            as ``max_filesize``. Caller wires this from
            ``config.trailers.filters.max_filesize_mb`` × 1 MiB.
        max_wall_clock_sec: Wall-clock SIGALRM timeout for a single download attempt
            (Unix only). On Windows the alarm is skipped; ``socket_timeout_sec``
            provides best-effort protection. NOTE: SIGALRM only fires on the main
            thread, so calling ``download()`` from a worker thread silently disables
            the wall-clock guard.
        ffmpeg: Required on PATH for multi-stream formats (separate video+audio).
            Construction logs a warning when missing; single-stream formats still
            work without it.
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
        # yt-dlp interprets the outtmpl extension as part of the FILENAME, not as
        # the desired container — it always appends the actual format extension
        # ("webm", "mkv"…). Passing "<name>-trailer.mp4" thus yields
        # "<name>-trailer.mp4.webm" when the format negotiates to webm. Strip the
        # caller's extension and let yt-dlp inject the merged container ext via
        # %(ext)s, then pin merge_output_format=mp4 so ffmpeg always remuxes to a
        # Plex/Kodi-friendly .mp4. final_ext is yt-dlp's authoritative hint for
        # the post-merge extension.
        outtmpl = f"{output_path.with_suffix('')}.%(ext)s"
        opts: dict[str, Any] = {
            "format": self._ytdlp_format,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "final_ext": "mp4",
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
        old_handler: Any = signal.SIG_DFL

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

    def _verify_output(self, output_path: Path) -> DownloadResult | None:
        """Verify the expected output file exists and meets the minimum size.

        Globs the parent directory for siblings with the same stem but a
        different extension (e.g. ``.webm`` when ffmpeg merge failed). Returns
        a ``YTDLP_ERROR`` result if the file is absent or too small, or ``None``
        when the file looks good (callers proceed to declare ``SUCCESS``).

        Args:
            output_path: The expected output path (e.g. ``name-trailer.mp4``).

        Returns:
            ``None`` if the file exists and is large enough.
            A ``DownloadResult(YTDLP_ERROR)`` otherwise.
        """
        if not output_path.exists():
            # Check for a sibling with a different extension — ffmpeg-merge failure
            # leaves the raw stream (e.g. ``.webm``) while reporting success.
            stem = output_path.with_suffix("").name
            siblings = [p for p in output_path.parent.glob(f"{stem}.*") if p.suffix != output_path.suffix]
            if siblings:
                got_ext = siblings[0].suffix
                msg = (
                    f"downloaded file extension mismatch (got {got_ext}, "
                    f"expected {output_path.suffix}); ffmpeg merge failed"
                )
            else:
                msg = "downloaded file missing"
            logger.warning("ytdlp_output_verification_failed", output_path=str(output_path), reason=msg)
            return DownloadResult(status=DownloadStatus.YTDLP_ERROR, error_message=msg)

        # File exists — check minimum size.
        actual_size = output_path.stat().st_size
        if actual_size <= 0:
            msg = f"downloaded file is empty (size={actual_size})"
            logger.warning("ytdlp_output_verification_failed", output_path=str(output_path), reason=msg)
            return DownloadResult(status=DownloadStatus.YTDLP_ERROR, error_message=msg)

        return None

    def _cleanup_partial_files(self, output_path: Path, url: str) -> None:
        """Remove yt-dlp partial/fragment files left by a failed download.

        Enumerates ``output_path.parent`` for files sharing the same stem as
        ``output_path`` but with a different suffix (e.g. ``.part``, ``.frag1``,
        ``.temp.xxx``). Unlinks each one and emits a single summary log event.

        Args:
            output_path: The intended final output path (its suffix is kept).
            url: Original download URL, forwarded to the log event for tracing.
        """
        stem = output_path.with_suffix("").name
        removed = 0
        for candidate in output_path.parent.glob(f"{stem}.*"):
            if candidate.suffix == output_path.suffix:
                # Keep the actual completed file (if any) — callers verify it
                # separately.
                continue
            try:
                candidate.unlink()
                removed += 1
            except OSError as exc:
                logger.warning(
                    "ytdlp_partial_cleanup_error",
                    path=str(candidate),
                    error=str(exc),
                )
        logger.info("ytdlp_partial_cleanup", url=url, removed=removed)

    def download(self, url: str, output_path: Path) -> DownloadResult:
        """Download a video from url to output_path using yt-dlp.

        Tries with cookies first; if bot-detection error occurs, retries
        once without cookies. Never raises — returns DownloadResult.

        After each successful yt-dlp call, verifies that the expected output
        file exists and is non-empty (C3). On any failure path, removes partial
        files (``.part``, ``.frag*``, ``.temp.*``) via a ``finally`` sweep (C4).

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
        except _WallClockTimeout:
            logger.warning("ytdlp_download_timeout", url=url, wall_clock_sec=self._max_wall_clock_sec)
            # C4: clean up partial files left by a timed-out download.
            self._cleanup_partial_files(output_path, url)
            return DownloadResult(
                status=DownloadStatus.YTDLP_ERROR,
                error_message="wall-clock timeout",
            )
        except Exception as exc:  # noqa: BLE001 — yt-dlp raises untyped DownloadError
            error_msg = str(exc)
            if not _is_bot_detection_error(error_msg):
                # Non-bot error — do not retry.
                logger.warning(
                    "ytdlp_download_error",
                    url=url,
                    error=error_msg,
                    error_type=type(exc).__name__,
                )
                # C4: clean up partial files left by the failed download.
                self._cleanup_partial_files(output_path, url)
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
            except _WallClockTimeout:
                logger.warning(
                    "ytdlp_download_timeout_no_cookies",
                    url=url,
                    wall_clock_sec=self._max_wall_clock_sec,
                )
                # C4: clean up partial files left by a timed-out retry.
                self._cleanup_partial_files(output_path, url)
                return DownloadResult(
                    status=DownloadStatus.YTDLP_ERROR,
                    error_message="wall-clock timeout (retry without cookies)",
                )
            except Exception as retry_exc:  # noqa: BLE001
                retry_msg = str(retry_exc)
                # I3: re-classify the retry exception — only genuine bot-detection
                # signals are BOT_DETECTED; transport errors get YTDLP_ERROR so
                # the state store applies normal retry-after semantics.
                if _is_bot_detection_error(retry_msg):
                    logger.warning("ytdlp_bot_detected_retry_failed", url=url, error=retry_msg)
                    # C4: clean up partial files.
                    self._cleanup_partial_files(output_path, url)
                    return DownloadResult(
                        status=DownloadStatus.BOT_DETECTED,
                        error_message=retry_msg,
                    )
                logger.warning(
                    "ytdlp_retry_transport_error",
                    url=url,
                    error=retry_msg,
                    error_type=type(retry_exc).__name__,
                )
                # C4: clean up partial files.
                self._cleanup_partial_files(output_path, url)
                return DownloadResult(
                    status=DownloadStatus.YTDLP_ERROR,
                    error_message=retry_msg,
                )
            # Retry succeeded — fall through to C3 verification below.
            logger.info("ytdlp_download_success_no_cookies", url=url, output_path=str(output_path))
            # C3: verify the retry output file before declaring success.
            verify_result = self._verify_output(output_path)
            if verify_result is not None:
                self._cleanup_partial_files(output_path, url)
                return verify_result
            return DownloadResult(status=DownloadStatus.SUCCESS, output_path=output_path)

        # First attempt succeeded — C3: verify the output file before declaring success.
        verify_result = self._verify_output(output_path)
        if verify_result is not None:
            # C4: clean up any partial/sibling files (e.g. the .webm from a failed merge).
            self._cleanup_partial_files(output_path, url)
            return verify_result

        logger.info("ytdlp_download_success", url=url, output_path=str(output_path))
        return DownloadResult(status=DownloadStatus.SUCCESS, output_path=output_path)
