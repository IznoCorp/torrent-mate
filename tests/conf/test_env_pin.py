"""The test suite pins ``PERSONALSCRAPER_ENV`` so a checkout's ``.env`` cannot reach a child process.

A dev checkout carries ``PERSONALSCRAPER_ENV=dev`` in its ``.env``, and the package calls
``load_dotenv()`` (``override=False``) at import time in every process, children included.
An unset variable would let that ``.env`` turn a child into ``dev`` on the hermetic,
unmarked test config, where the isolation guard refuses it. The autouse fixture sets the
variable to the empty string (production) instead, which ``load_dotenv`` leaves alone.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from personalscraper.conf.environment import ENV_VAR

# The child loads a ``.env`` the way the package does, then reads the environment.
_CHILD = (
    "from dotenv import load_dotenv\n"
    "from personalscraper.conf.environment import current_environment\n"
    "load_dotenv('.env')\n"
    "print(current_environment().value)\n"
)


def test_child_process_ignores_a_dev_dotenv(tmp_path: Path) -> None:
    """A child process started by a test stays ``prod`` though a ``.env`` names ``dev``.

    Args:
        tmp_path: Pytest tmp_path fixture value; the child's working directory.
    """
    (tmp_path / ".env").write_text(f"{ENV_VAR}=dev\n", encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(root), os.environ.get("PYTHONPATH")]))}

    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )

    assert result.stdout.strip() == "prod"
