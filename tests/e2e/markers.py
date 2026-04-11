"""E2E test marker files — safety mechanism for cleanup.

Places .e2e-test-marker files inside directories created by tests.
The triple-check system (marker exists + UUID matches + path in registry)
prevents accidental deletion of real media files on the storage disks.
"""

from pathlib import Path

from tests.e2e.registry import TestRegistry

MARKER_FILENAME = ".e2e-test-marker"


def place_marker(directory: Path, session_id: str) -> None:
    """Create a .e2e-test-marker file containing the session UUID.

    Args:
        directory: Directory to mark as test-created.
        session_id: UUID of the current test session.
    """
    marker = directory / MARKER_FILENAME
    marker.write_text(session_id)


def verify_marker(directory: Path, session_id: str, registry: TestRegistry) -> bool:
    """Verify a directory has a valid test marker — TRIPLE CHECK.

    All three checks must pass before cleanup is allowed:
    1. The marker file exists in the directory
    2. The marker content matches the expected session_id
    3. The directory path is registered in the test registry

    Args:
        directory: Directory to verify.
        session_id: Expected session UUID.
        registry: TestRegistry to check path against.

    Returns:
        True only if all three checks pass.
    """
    marker = directory / MARKER_FILENAME

    # Check 1: marker file exists
    if not marker.exists():
        return False

    # Check 2: marker content matches session_id
    if marker.read_text().strip() != session_id:
        return False

    # Check 3: directory is in the registry
    if not registry.contains(directory):
        return False

    return True


def find_orphan_markers(base_paths: list[Path]) -> list[Path]:
    """Find .e2e-test-marker files from previous test sessions.

    Scans directories recursively for marker files that may have been
    left behind by crashed or interrupted test sessions.

    Args:
        base_paths: Root directories to scan (e.g. staging dir, disk paths).

    Returns:
        List of directories containing orphan markers.
    """
    orphans = []
    for base in base_paths:
        if not base.exists():
            continue
        for marker in base.rglob(MARKER_FILENAME):
            orphans.append(marker.parent)
    return orphans
