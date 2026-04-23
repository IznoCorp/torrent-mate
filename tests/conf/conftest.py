"""Fixtures for conf unit tests.

Ensures structlog is configured once per session so that stdlib caplog
fixtures can capture structured log records from classifier.py and loader.py.
"""

import pytest

from personalscraper.logger import configure_logging


@pytest.fixture(scope="session", autouse=True)
def _configure_logging_for_conf_tests() -> None:
    """Initialize structlog stdlib bridge for conf unit tests.

    Needed so that caplog.at_level(logger="personalscraper.conf.*") correctly
    captures records emitted via get_logger(). Without this, structlog uses
    its default PrintLoggerFactory which bypasses the stdlib hierarchy.
    """
    configure_logging()
