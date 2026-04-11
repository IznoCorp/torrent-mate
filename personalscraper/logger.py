"""Structured logging module — dual output (console + JSON file) via structlog."""

import logging
import logging.config
from pathlib import Path

import structlog

LOGS_DIR = Path("logs")


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog + stdlib logging for dual output.

    Console handler: colored dev output via ConsoleRenderer.
    File handler: JSON Lines via TimedRotatingFileHandler (logs/personalscraper.json).
    verbose=True → DEBUG, quiet=True → WARNING, default → INFO.
    foreign_pre_chain captures stdlib logs (requests, urllib3, qbittorrent-api).
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
    """Return a structlog bound logger."""
    return structlog.get_logger(name)


def cleanup_old_logs(logs_dir: Path = LOGS_DIR, retention_days: int = 30) -> int:
    """Delete log files older than retention_days. Returns count deleted.
    Complement to TimedRotatingFileHandler's backupCount."""
    import time

    if not logs_dir.exists():
        return 0
    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    for f in logs_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    return deleted
