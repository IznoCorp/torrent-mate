"""Pytest fixtures for E2E tests — session-scoped setup for real pipeline testing.

Fixtures provide: unique session UUID, test registry, qBittorrent client,
and torrent file discovery. All skip gracefully if dependencies are unavailable.
"""

import uuid
from pathlib import Path

import pytest

from tests.e2e.registry import TestRegistry

# .torrent files live in assets/torrents/ at the project root
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "torrents"


@pytest.fixture(scope="session")
def e2e_session_id():
    """Generate a unique UUID for this test session.

    Returns:
        A UUID4 string identifying all resources created in this session.
    """
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def e2e_registry(e2e_session_id):
    """Create a TestRegistry for tracking test-created files.

    Yields:
        A TestRegistry instance. Cleaned up after all tests complete.
    """
    # Store registry in project dir (writable) instead of ~/.personalscraper/
    project_dir = Path(__file__).resolve().parent.parent.parent
    reg = TestRegistry(session_id=e2e_session_id, base_dir=project_dir)
    yield reg
    # Registry file cleanup happens in the E2E cleanup phase, not here


@pytest.fixture(scope="session")
def e2e_qbit_client():
    """Connect to qBittorrent. Skip all E2E torrent tests if unavailable.

    Returns:
        A qbittorrentapi.Client connected to the local instance.
    """
    try:
        import qbittorrentapi
    except ImportError:
        pytest.skip("qbittorrent-api not installed")

    try:
        from personalscraper.config import get_settings
        settings = get_settings()
        client = qbittorrentapi.Client(
            host=settings.qbit_host,
            port=settings.qbit_port,
            username=settings.qbit_username,
            password=settings.qbit_password,
        )
        client.auth_log_in()
        return client
    except Exception as exc:
        pytest.skip(f"qBittorrent not available: {exc}")


@pytest.fixture(scope="session")
def e2e_torrent_files():
    """Discover .torrent files in assets/torrents/.

    Skip if no torrent files are found.

    Returns:
        List of Path objects to .torrent files.
    """
    if not ASSETS_DIR.is_dir():
        pytest.skip(f"assets/torrents/ directory not found at {ASSETS_DIR}")
    files = sorted(ASSETS_DIR.glob("*.torrent"))
    if not files:
        pytest.skip("No .torrent files in assets/torrents/")
    return files


@pytest.fixture(scope="session")
def e2e_settings():
    """Load pipeline settings. Skip if .env is not configured.

    Returns:
        A Settings instance.
    """
    from personalscraper.config import get_settings
    return get_settings()
