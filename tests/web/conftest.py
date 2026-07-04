"""Shared fixtures for web backend tests (tm-shell feature).

Provides a ``web_app`` fixture (FastAPI TestClient) wired to the synthetic
``test_config`` from ``tests/fixtures/config.py``.  Tests that need a
different WebConfig (e.g. Redis unreachable) build their own app inline via
``create_app``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.web.app import create_app


@pytest.fixture
def web_app(test_config):
    """Create a TestClient wrapping ``create_app`` with test config + default settings.

    Uses ``Settings(_env_file=None)`` to avoid reading the real ``.env`` file.
    The synthetic ``test_config`` carries default ``WebConfig`` values
    (host, port, redis_url, etc.).

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.

    Returns:
        A ``TestClient`` instance ready for request assertions.
    """
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    app = create_app(test_config, settings)
    return TestClient(app)
