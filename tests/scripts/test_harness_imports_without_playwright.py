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
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "frontend" / "maquette" / "harness"

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


def test_the_timeout_wait_still_answers_false_when_the_ceiling_comes_first() -> None:
    """The lazy import keeps `screen_arrives()`'s behaviour: a Playwright timeout reads False."""
    pytest.importorskip("playwright")
    import asyncio

    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    sys.path.insert(0, str(HARNESS))
    import common

    class Page:
        async def wait_for_function(self, *args, **kwargs):
            raise PlaywrightTimeoutError("ceiling")

    assert asyncio.run(common.screen_arrives(Page(), "screen", 1)) is False
