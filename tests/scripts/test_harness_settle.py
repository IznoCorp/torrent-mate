"""A layer's wait is read from the page, not typed beside it (B-276).

WHAT IT PAID FOR. `touch.py` waited 420 ms between press surfaces and 340 ms
after closing the sheet, both calibrated against a layer that took 200–300 ms.
L12 drew the panel on `--duration-4`, the close became 450 ms with the scrim's
`visibility` delayed by as much, and the rule pressed a poster the scrim still
covered. `common.SETTLE` waits for the page's own running animations to end,
whatever the stylesheet draws them at.

Driven in a real browser on a page of its own; where no browser can be
launched it skips and says why.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "frontend" / "maquette" / "harness"
sys.path.insert(0, str(HARNESS))

import common  # noqa: E402

# A layer whose exit is drawn longer than any wait a rule ever typed, a
# visibility delayed by its length, and a spinner that never ends.
PAGE = """<!doctype html><body>
<style>
  #layer { transition: transform 900ms, visibility 0s 900ms; }
  #layer.gone { transform: translateY(100%); visibility: hidden; }
  #spinner { animation: turn 1s linear infinite; }
  @keyframes turn { to { rotate: 1turn; } }
</style>
<div id="layer">layer</div><div id="spinner">·</div>
</body>"""


@pytest.fixture(scope="module")
def page():
    """A browser page holding `PAGE`, or a skip where none can be launched."""
    playwright_api = pytest.importorskip("playwright.sync_api")
    with playwright_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel=common.browser_channel(), args=common.chrome_launch_args())
        except Exception as error:  # noqa: BLE001 — any launch failure means « no browser here »
            pytest.skip(f"no browser can be launched here: {error}")
        tab = browser.new_page()
        tab.set_content(PAGE)
        yield tab
        browser.close()


def test_a_layer_is_waited_for_until_its_drawn_exit_ends(page) -> None:
    """The wait outlasts the drawn exit and its delayed visibility, not a typed number."""
    page.evaluate("()=>document.querySelector('#layer').classList.add('gone')")

    waited = page.evaluate(common.SETTLE, common.SETTLE_CEILING_MS)

    assert 900 <= waited < common.SETTLE_CEILING_MS
    assert page.evaluate("()=>getComputedStyle(document.querySelector('#layer')).visibility") == "hidden"
