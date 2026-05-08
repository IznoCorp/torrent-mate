"""Regression test for BUG #5 — personalscraper must load .env on package import.

The api-unify branch (PR ready 2026-05-07) introduced code paths that read
``os.environ`` directly via ``build_active_torrent_client(config.torrent, os.environ)``
and ``api/_activation.py``. Before api-unify, the legacy
``personalscraper.config.Settings(BaseSettings)`` extended pydantic-settings
with ``env_file=".env"`` and auto-loaded credentials. The new code path
bypasses that mechanism, so the package itself must call ``load_dotenv()``.

Without this bootstrap, every CLI invocation fails with
``Missing required credentials: QBIT_USERNAME, QBIT_PASSWORD`` even though
the user has a valid ``.env`` on disk.

This test passed during api-unify development because ``tests/conftest.py``
itself calls ``load_dotenv()`` at module import — the test harness masks the
production bug. We therefore spawn a fresh subprocess with a stripped-down
environment and an isolated ``.env`` file, then verify the package loads it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_personalscraper_loads_dotenv_on_import(tmp_path: Path) -> None:
    """Importing ``personalscraper`` must trigger ``load_dotenv()``.

    Spawns a subprocess in *tmp_path* with a minimal env (PATH only) and a
    crafted ``.env`` containing a sentinel variable. The subprocess imports
    ``personalscraper`` and prints the sentinel from ``os.environ``. The test
    asserts the sentinel is visible after the import.
    """
    sentinel_value = "BUG5_REGRESSION_SENTINEL_VALUE"
    env_file = tmp_path / ".env"
    env_file.write_text(f"BUG5_REGRESSION_SENTINEL={sentinel_value}\n", encoding="utf-8")

    # Minimal subprocess env: PATH for python resolution, nothing else.
    # Critically, no BUG5_REGRESSION_SENTINEL exported — only the .env file.
    repo_root = Path(__file__).resolve().parents[1]
    subprocess_env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "PYTHONPATH": str(repo_root),
        "HOME": str(tmp_path),  # Avoid touching user's real $HOME.
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; import personalscraper; print(os.environ.get('BUG5_REGRESSION_SENTINEL', 'MISSING'))",
        ],
        cwd=tmp_path,
        env=subprocess_env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, f"subprocess failed: stderr={result.stderr}"
    assert sentinel_value in result.stdout, (
        f"personalscraper did not load .env on import. "
        f"Expected '{sentinel_value}' in stdout, got: {result.stdout!r}. "
        f"stderr: {result.stderr!r}"
    )
