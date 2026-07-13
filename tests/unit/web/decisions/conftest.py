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


@pytest.fixture(autouse=True)
def _neutralize_pipeline_continuation() -> Iterator[None]:
    """Stop the §4 continuation from spawning a REAL pipeline run in tests.

    After a successful scrape-resolve the runner triggers a continuation via
    ``spawn_pipeline_run`` (the single trigger authority) so the media finishes its
    pipeline. In-process ``main()`` tests that drive the rc==0 success path would
    otherwise launch a real detached ``personalscraper run`` against the loaded
    config — a dangerous side effect. Stub it at its source module (the runner
    imports it lazily, so the call-time lookup picks up the patch) so the call is
    still exercised without launching anything. A test asserting the continuation
    nests its own capturing ``patch``.

    Yields:
        ``None`` — control returns to the test with ``spawn_pipeline_run`` stubbed.
    """
    with patch(
        "personalscraper.web.pipeline_trigger.spawn_pipeline_run",
        return_value="stub-continuation-uid",
    ):
        yield
