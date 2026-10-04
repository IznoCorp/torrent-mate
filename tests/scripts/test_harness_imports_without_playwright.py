"""The harness modules the pytest suite imports load without Playwright installed.

WHAT IT PAID FOR (B-684). CI's `test` job runs `pip install -e ".[dev]"`, which
carries no Playwright; the harness's browser rules run in their own workflow.
`common.py` imported `PlaywrightTimeoutError` at module level, so every test that
loaded `common` died on collection in that job — and #681, which introduced the
import, touched no Python, so the job skipped its steps and stayed green.

These tests load each module in a fresh interpreter in which `playwright` cannot
be imported, whether or not it is installed here.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from _repo_paths import HARNESS

# The modules the suite loads (`test_harness_scratch`, `test_harness_settle`,
# `test_harness_entry_points`); a rule script that drives a browser is not one.
MODULES_THE_SUITE_LOADS = ("common", "served_copy")

BLOCKER = """
import sys
sys.modules["playwright"] = None
sys.modules["playwright.async_api"] = None
sys.path.insert(0, {harness!r})
import {module}
"""


@pytest.mark.parametrize("module", MODULES_THE_SUITE_LOADS)
def test_the_module_imports_where_playwright_cannot(module: str) -> None:
    """Importing the module needs no Playwright; only running a browser does."""
    result = subprocess.run(
        [sys.executable, "-c", BLOCKER.format(harness=str(HARNESS), module=module)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


TIMEOUT_CHILD = """
import asyncio, sys, types
class TimeoutError(Exception):
    pass
api = types.ModuleType("playwright.async_api")
api.TimeoutError = TimeoutError
package = types.ModuleType("playwright")
package.async_api = api
sys.modules["playwright"] = package
sys.modules["playwright.async_api"] = api
sys.path.insert(0, {harness!r})
import common

class Page:
    async def wait_for_function(self, *args, **keywords):
        raise TimeoutError("ceiling")

assert asyncio.run(common.screen_arrives(Page(), "screen", 1)) is False
"""


def test_the_timeout_wait_still_answers_false_when_the_ceiling_comes_first() -> None:
    """The lazy import keeps `screen_arrives()`'s behaviour: a Playwright timeout reads False.

    Run in a child with a stand-in `playwright`, so what other tests leave in
    `sys.modules` cannot change the answer.
    """
    result = subprocess.run(
        [sys.executable, "-c", TIMEOUT_CHILD.format(harness=str(HARNESS))],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
