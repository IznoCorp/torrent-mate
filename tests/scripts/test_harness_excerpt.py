"""Tests for what `run.sh` prints of a failed rule's log."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "harness_excerpt.py"


def load():
    """Imports the excerpt tool by its path."""
    spec = importlib.util.spec_from_file_location("harness_excerpt", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOG = """R52 — the installed app
  PASS the manifest is served
Traceback (most recent call last):
  File "/harness/pwa.py", line 465, in main
    await page.goto(DEPLOYED, wait_until="load")
  File "/site-packages/playwright/async_api/_generated.py", line 8991, in goto
    return mapping.from_maybe_impl(
playwright._impl._errors.TimeoutError: Page.goto: Timeout 30000ms exceeded.
"""


def test_a_traceback_keeps_the_frame_that_names_its_line() -> None:
    """B-571: the filter dropped `File …, line N`, so which `goto` expired was unknowable.

    Two hosts are reached by two `goto` calls in `pwa.py`; only the rule's own
    frame says which one timed out.
    """
    excerpt = load().excerpt(LOG)

    assert '  File "/harness/pwa.py", line 465, in main' in excerpt
    assert excerpt.rstrip().endswith("Timeout 30000ms exceeded.")


def test_a_failed_hold_with_no_traceback_keeps_its_fail_lines() -> None:
    """The ordinary verdict is still read by its FAIL lines."""
    log = "R1\n  PASS one\n  FAIL two — 3 px\n  PASS three\n"

    assert load().excerpt(log).strip() == "FAIL two — 3 px"
