"""Shared fixtures for the decisions-runner test suite.

The runner's ``main()`` (Finding A hardening) registers a process-global
``SIGTERM`` handler that finalizes the run row and then calls ``os._exit``.
Several tests here invoke the real ``main()`` **in-process** (rather than in a
child process), so without protection each call would leave that handler
installed in the current pytest-xdist worker. When xdist — or the CI runner —
later sends the worker ``SIGTERM`` at shutdown, the leaked handler fires and
``os._exit`` kills the worker abruptly. That is invisible on a local macOS run
but reproducibly cancels the whole ``test`` job on Linux CI, surfacing as
"the runner has received a shutdown signal" + "OSError: cannot send (already
closed?)".
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _neutralize_runner_sigterm_handler() -> Iterator[None]:
    """Neutralize ``signal.signal`` so in-process ``main()`` never leaks a handler.

    The runner's real ``_on_sigterm`` handler must never survive a test in the
    pytest-xdist worker. The dedicated SIGTERM unit test nests its own capturing
    ``patch`` inside this one to still exercise the handler, so this fixture
    does not weaken that coverage — it only prevents the handler from surviving
    the test and killing the worker at shutdown.

    Yields:
        ``None`` — control returns to the test with ``signal.signal`` patched.
    """
    with patch("personalscraper.web.decisions.runner.signal.signal"):
        yield
