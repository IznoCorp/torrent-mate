"""Structured logging module — dual output (console + JSON file) via structlog."""

import logging
import logging.config
import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, cast

import structlog
from structlog.types import Processor

# Top-level exact-match for short, well-known secret field names.
_SECRET_KEY_EXACT_RE = re.compile(r"^(api[_-]?key|authorization|cookie|secret|token|password)$", re.IGNORECASE)
# Segment-boundary match for compound names like ``youtube_api_key``,
# ``tmdb_api_key``, ``tvdb_api_key``, ``cookies_file``, ``cookie_file``.
# Uses ``(^|[_-])`` as a segment boundary because ``_`` is a word character
# and ``\b`` does not fire between letters and underscores.
#
# Intentionally does NOT include bare ``cookie|secret|token|password`` — those
# are short exact-match names handled by ``_SECRET_KEY_EXACT_RE`` above.  The
# bare alternations caused over-matching on compound counters such as
# ``cookie_count``, ``token_count``, ``secret_count`` and ``password_count``,
# which are legitimate integer fields that must NOT be redacted.
_SECRET_KEY_COMPOUND_RE = re.compile(r"(?i)(^|[_\-])(api[_\-]?key|authorization|cookies?[_\-]file)($|[_\-])")
_URL_KEY_PARAM_RE = re.compile(r"([?&])key=[^&]*")


def redact_secrets(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Recursively redact secret-looking values from the event dict.

    Also strips the ``key=<value>`` query parameter from any string field
    that looks like a URL (contains ``?key=`` or ``&key=``).

    Args:
        _logger: Unused — required by the structlog processor interface.
        _method_name: Unused — required by the structlog processor interface.
        event_dict: The structlog event dict to sanitize.

    Returns:
        A new dict with secret values replaced by ``"***REDACTED***"``.
    """

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: (
                    "***REDACTED***" if _SECRET_KEY_EXACT_RE.match(k) or _SECRET_KEY_COMPOUND_RE.search(k) else _walk(v)
                )
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        if isinstance(obj, str) and "key=" in obj and ("?" in obj or "&" in obj):
            return _URL_KEY_PARAM_RE.sub(r"\1key=***REDACTED***", obj)
        return obj

    result: dict[str, Any] = _walk(event_dict)
    return result


LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog + stdlib logging for dual output.

    Sets up two handlers: colored console (dev) and JSON Lines file (ops).
    foreign_pre_chain captures stdlib logs (requests, urllib3, qbittorrent-api).

    Args:
        verbose: If True, set log level to DEBUG.
        quiet: If True, set log level to WARNING. Ignored if verbose is True.
    """
    LOGS_DIR.mkdir(exist_ok=True)

    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "WARNING"
    else:
        log_level = "INFO"

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
    ]

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.processors.format_exc_info,
                        structlog.processors.JSONRenderer(),
                    ],
                    "foreign_pre_chain": shared_processors,
                },
                "colored": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.dev.ConsoleRenderer(colors=True),
                    ],
                    "foreign_pre_chain": shared_processors,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "colored",
                    "level": log_level,
                },
                "file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": str(LOGS_DIR / "personalscraper.json"),
                    "when": "midnight",
                    "backupCount": 30,
                    "formatter": "json",
                    "level": "DEBUG",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["console", "file"],
                    "level": "DEBUG",
                    "propagate": True,
                },
                # Third-party loggers default to WARNING to reduce noise.
                # qbittorrentapi INFO surfaces session lifecycle events (login, logout, cookie refresh)
                # that aid ingest debugging without DEBUG-level request traces.
                "rebulk": {"level": "DEBUG" if verbose else "WARNING"},
                "guessit": {"level": "DEBUG" if verbose else "WARNING"},
                "urllib3": {"level": "DEBUG" if verbose else "WARNING"},
                "requests": {"level": "DEBUG" if verbose else "WARNING"},
                "qbittorrentapi": {"level": "DEBUG" if verbose else "INFO"},
                "httpcore": {"level": "DEBUG" if verbose else "WARNING"},
                "httpx": {"level": "DEBUG" if verbose else "WARNING"},
            },
        }
    )

    structlog.configure(
        processors=shared_processors
        + [
            redact_secrets,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger.

    Args:
        name: Logger name (typically module name, e.g. "ingest").

    Returns:
        A BoundLogger instance with the given name.
    """
    # structlog.get_logger() returns Any; cast to the concrete wrapper we configure above.
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def cleanup_old_logs(logs_dir: Path = LOGS_DIR, retention_days: int = 30) -> int:
    """Delete log files older than retention_days.

    Complement to TimedRotatingFileHandler's backupCount for time-based cleanup.

    Args:
        logs_dir: Directory containing log files.
        retention_days: Delete files older than this many days.

    Returns:
        Number of files deleted.
    """
    import time

    if not logs_dir.exists():
        return 0
    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    for f in logs_dir.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError as exc:
            # File may be locked by active log handler, or real FS error
            structlog.get_logger("logger").debug("cannot_delete_log", file=f.name, error=str(exc))
    return deleted
