"""The drawer-gaps rule names a group it cannot reach by its own title, even a group with no entry (B-712).

WHAT IT PAID FOR. ``drawer_gaps.unreachable_groups`` scrolls each group's last entry into view. A
group with no entry has none to bring: the page answered ``null``, the title went with it, and the
journal said ``group 0`` instead of the heading the reader sees.

Driven in a real browser on a page of its own; where no browser can be launched it skips and says why.
"""

from __future__ import annotations

import asyncio
import sys

import pytest
from _repo_paths import HARNESS

sys.path.insert(0, str(HARNESS))

# The harness modules import Playwright at load; CI's `test` job does not install it.
pytest.importorskip("playwright")

import drawer_gaps
from common import browser_channel, chrome_launch_args

# A drawer whose first group has a heading and no entry, and whose second is whole.
PAGE = """<!doctype html><body style="margin:0">
<div id="drawer"><nav style="height:200px;overflow:auto">
  <div class="grp"><div class="sect">Empty group</div></div>
  <div class="grp"><div class="sect">Whole group</div><a href="#" style="display:block;height:20px">entry</a></div>
</nav></div>
</body>"""


async def _unreachable() -> list[str]:
    """Open ``PAGE`` in a browser and read the groups the rule cannot reach.

    Returns:
        The rule's answer, or a skip where no browser can be launched.
    """
    playwright_api = pytest.importorskip("playwright.async_api")
    async with playwright_api.async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        except Exception as error:  # noqa: BLE001 — any launch failure means « no browser here »
            pytest.skip(f"no browser can be launched here: {error}")
        try:
            tab = await browser.new_page()
            await tab.set_content(PAGE)
            return await drawer_gaps.unreachable_groups(tab)
        finally:
            await browser.close()


def test_a_group_with_no_entry_is_named_by_its_title() -> None:
    """The empty group is reported under its heading, not under its index."""
    assert asyncio.run(_unreachable()) == ["Empty group"]
