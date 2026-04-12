"""Structured logging module — dual output (console + JSON file) via structlog."""

import logging
import logging.config
from pathlib import Path

import structlog

LOGS_DIR = Path("logs")


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

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
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
        },
    })

    structlog.configure(
        processors=shared_processors + [
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
    return structlog.get_logger(name)


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
        except OSError:
            pass  # File locked by active log handler — not worth logging
    return deleted
