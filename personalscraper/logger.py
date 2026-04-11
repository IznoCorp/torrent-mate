"""Structured logging module — stub, replaced by full implementation in phase 0.3."""

import structlog


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog + stdlib logging. Stub — real implementation in phase 0.3."""
    pass


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name)
