"""Entry point for ``python -m personalscraper``.

Used by the Watcher daemon to spawn ``personalscraper run`` /
``personalscraper cross-seed`` as subprocesses (``sys.executable -m
personalscraper <command>``).

Importing ``personalscraper.cli`` triggers the side-effect registration
of all Typer commands (pipeline, cross-seed, library, …) onto the shared
``cli_app.app`` instance.  Importing ``cli_app`` alone would give an empty
Typer with no registered commands.
"""

from __future__ import annotations

import personalscraper.cli  # noqa: F401 — side-effect command registration
from personalscraper.cli_app import app

if __name__ == "__main__":
    app()
