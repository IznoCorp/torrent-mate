"""Holds on the mock-keychain arm: a bare Chrome launch is refused, wherever it hides.

The corpus this arm reads is `frontend/maquette/harness/*.py`, and its own
launch call has one shape today (`common.chrome_launch_args()` invented it, so
nothing else could yet carry a second one) — the fixtures below are that shape
and its two ways of breaking: a launch with no `args=` at all, and one that
passes the helper's flag by hand instead of the helper itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_arm():
    """Imports the arm by path, the way `make check` invokes it.

    Returns:
        The module object.
    """
    spec = importlib.util.spec_from_file_location("check_mock_keychain", ROOT / "scripts" / "check-mock-keychain.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_mock_keychain"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="arm")
def arm_fixture():
    """Provides the loaded arm.

    Returns:
        The module object.
    """
    return load_arm()


def test_a_bare_launch_is_refused(arm):
    """RED: one launch with no `args=` at all is caught, by its own line.

    Args:
        arm: The loaded module.
    """
    fixture = (
        "async def main():\n"
        "    async with async_playwright() as p:\n"
        '        b = await p.chromium.launch(channel="chrome")\n'
    )
    assert arm.violations_in(fixture) == [3]


def test_the_flag_passed_by_hand_is_still_refused(arm):
    """RED: the helper is the contract, not the flag it adds.

    A rule that reaches for `--use-mock-keychain` itself, without going
    through `chrome_launch_args`, would defeat the one place that flag is
    composed with a per-rule `extra` — silently, the day a second Chrome
    switch joins the helper and this call site does not carry it.

    Args:
        arm: The loaded module.
    """
    fixture = 'b = await p.chromium.launch(channel="chrome", args=["--use-mock-keychain"])\n'
    assert arm.violations_in(fixture) == [1]


def test_the_helper_with_no_extra_is_accepted(arm):
    """GREEN: the shape every bare call in the corpus was converted to.

    Args:
        arm: The loaded module.
    """
    fixture = 'b = await p.chromium.launch(channel="chrome", args=chrome_launch_args())\n'
    assert arm.violations_in(fixture) == []


def test_the_helper_composed_with_extra_is_accepted(arm):
    """GREEN: the shape `entry.py` and `pwa.py` carry, per-rule args included.

    Args:
        arm: The loaded module.
    """
    fixture = (
        'b = await p.chromium.launch(channel="chrome", args=chrome_launch_args(resolve_deployed_host_locally(HOST)))\n'
    )
    assert arm.violations_in(fixture) == []


def test_a_webkit_launch_is_not_this_arms_subject(arm):
    """A launch naming no Chrome channel at all is out of scope, not a false GREEN.

    Args:
        arm: The loaded module.
    """
    assert arm.violations_in("b, _, pg = await on_the_list(p, lambda: p.webkit.launch())\n") == []


def test_the_corpus_floor_guards_against_a_reader_that_stopped_reading(arm):
    """A directory rename must fall this arm, not pass it by reading nothing.

    Args:
        arm: The loaded module.
    """
    assert len(arm.sources()) >= arm.CORPUS_FLOOR


def test_the_arm_passes_over_the_repository(arm):
    """GREEN: the real tree, converted, holds against its own rule.

    Args:
        arm: The loaded module.
    """
    assert arm.main() == 0
