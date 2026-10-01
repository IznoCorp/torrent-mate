"""A harness press lands on an icon, and names an icon that covers (B-364).

WHAT IT PAID FOR. The hit-tested presses — `busy.py`'s two and
`queued_ask_mark.py`'s — ask `elementFromPoint` what a finger at the control's
centre would touch and then call `hit.click()` on that answer. When the centre
is an icon, the answer is an `SVGElement`, which has no `click`: the rule threw
`hit.click is not a function` instead of pressing. The coverer the failure names
was `hit.className`, which on an SVG reads `[object SVGAnimatedString]`.

Driven in a real browser on a page of its own; where no browser can be
launched it skips and says why.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "frontend" / "maquette" / "harness"
sys.path.insert(0, str(HARNESS))

# The harness modules import Playwright at load; CI's `test` job does not install it.
pytest.importorskip("playwright")

import busy  # noqa: E402
import queued_ask_mark  # noqa: E402
from common import browser_channel  # noqa: E402

# Two controls whose whole centre is an icon — a sheet action and a named
# control — and a row an icon covers.
PAGE = """<!doctype html><body style="margin:0">
<div id="sheetin">
  <button data-part="sheet/action" data-pause style="width:60px;height:60px;padding:0">
    <svg class="icon" width="60" height="60"><rect width="60" height="60"/></svg>
  </button>
</div>
<button data-part="icon-only" style="width:60px;height:60px;padding:0">
  <svg class="icon" width="60" height="60"><rect width="60" height="60"/></svg>
</button>
<div data-panel="Covered" style="position:relative;width:60px;height:60px;margin-top:20px">row</div>
<svg width="60" height="60" style="position:absolute;left:0;top:140px">
  <rect class="cover" width="60" height="60"/>
</svg>
<script>
  window.presses = 0;
  document.addEventListener("click", (event) => {
    if (event.target.closest("button")) window.presses += 1;
  });
</script>
</body>"""


@pytest.fixture(scope="module")
def page():
    """A browser page holding `PAGE`, or a skip where none can be launched."""
    playwright_api = pytest.importorskip("playwright.sync_api")
    with playwright_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel=browser_channel())
        except Exception as error:  # noqa: BLE001 — any launch failure means « no browser here »
            pytest.skip(f"no browser can be launched here: {error}")
        tab = browser.new_page()
        tab.set_content(PAGE)
        yield tab
        browser.close()


def test_a_press_by_part_lands_on_an_icon(page) -> None:
    """The press by name reaches a control whose centre is its icon."""
    page.evaluate("window.presses = 0")
    answer = page.evaluate(busy.PRESS_THE_ACTION_BY_PART, "icon-only")
    assert answer["pressed"] is True
    assert page.evaluate("window.presses") == 1


def test_a_press_by_verb_lands_on_an_icon(page) -> None:
    """The press by verb reaches a sheet action whose centre is its icon."""
    page.evaluate("window.presses = 0")
    answer = page.evaluate(busy.PRESS_THE_ACTION, "pause")
    assert answer["pressed"] is True
    assert page.evaluate("window.presses") == 1


def test_an_icon_that_covers_is_named_by_its_class(page) -> None:
    """A row an icon covers is not pressed, and the coverer reads as its class."""
    answer = page.evaluate(queued_ask_mark.RAISE, "Covered")
    assert answer["reachable"] is False
    assert answer["covering"] == "cover"
