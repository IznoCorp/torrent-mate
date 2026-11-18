"""Name what the preprod lacks before a staging deploy starts its scheduled jobs.

The preprod's jobs act on the torrent client prod shares (follow, search, grab, the seed
sweep, the purge that deletes torrents and their files) and write into the preprod's
roots. `scripts/deploy-staging.sh` starts them only when the preprod is set up: its
overlay directory, its secrets file, an overlay that loads in ``staging`` (which proves
the data directory's ``.tm-environment`` reads ``staging``, the code's own isolation
check), and every root the overlay names marked as the preprod's and mounted (the code's
own sandbox guard). Anything else leaves the jobs stopped and the deploy says why.

Run with the staging venv's interpreter so the code judging is the code just installed.

Usage:
    python scripts/preprod_preconditions.py <overlay-dir> <secrets-file>

Exit status 0 with no output when every precondition holds; 1 with one line per missing
precondition otherwise.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from personalscraper import config as settings_config
from personalscraper.conf.environment import ENV_VAR, Environment
from personalscraper.conf.loader import load_config_dir
from personalscraper.conf.sandbox_guard import SandboxGuardError, assert_sandbox_root, sandbox_roots


def _one_line(error: Exception) -> str:
    """Flatten an error's message to one line.

    Args:
        error: The error to describe.

    Returns:
        Its message with every run of whitespace (newlines included) collapsed to one space.
    """
    return " ".join(str(error).split())


def missing_preconditions(config_dir: Path, env_file: Path) -> list[str]:
    """List the preprod preconditions that do not hold.

    The process must already run in ``staging`` (``PERSONALSCRAPER_ENV``): the overlay is
    loaded, and its roots judged, as the preprod's own processes would.

    Args:
        config_dir: The preprod's overlay directory (``PERSONALSCRAPER_CONFIG`` of its apps).
        env_file: The preprod's secrets file (``PERSONALSCRAPER_ENV_FILE`` of its apps).

    Returns:
        One message per missing precondition; empty when the jobs may start.
    """
    if not config_dir.is_dir():
        # Nothing else can be judged without the overlay.
        return [f"the preprod overlay {config_dir} does not exist"]
    missing: list[str] = []
    local_env = settings_config._local_env_path()
    if local_env.is_file():
        missing.append(f"the staging clone carries its own {local_env}, which the preprod must not hold: move it out")
    if not env_file.is_file():
        missing.append(f"the preprod secrets file {env_file} does not exist")
    try:
        config = load_config_dir(config_dir)
    except (OSError, ValueError) as exc:
        # Every refusal the loader raises (missing file, bad overlay, failed validation —
        # the isolation check among them) is an OSError or a ValueError.
        missing.append(f"the preprod overlay {config_dir} does not load in 'staging': {_one_line(exc)}")
        return missing
    for root in sandbox_roots(config):
        try:
            assert_sandbox_root(root, Environment.STAGING)
        except SandboxGuardError as exc:
            missing.append(_one_line(exc))
    return missing


def main(argv: Sequence[str] | None = None) -> int:
    """Print every missing preprod precondition, one per line.

    Args:
        argv: ``[overlay-dir, secrets-file]``; ``sys.argv[1:]`` when ``None``.

    Returns:
        0 when every precondition holds, 1 when one is missing, 2 on a usage error.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: preprod_preconditions.py <overlay-dir> <secrets-file>", file=sys.stderr)
        return 2
    os.environ[ENV_VAR] = Environment.STAGING.value
    missing = missing_preconditions(Path(args[0]), Path(args[1]))
    for message in missing:
        print(message)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
