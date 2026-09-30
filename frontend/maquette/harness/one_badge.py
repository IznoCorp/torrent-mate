"""R-conformity-k — one count badge: the bar's, the menu's, the drawer's and a tab's.

THE DEFECT THIS ENDS. Three counts were three drawings — the bottom bar's
corner badge, the menu button's, the drawer entry's count — at three sizes and
two fills. One badge, placed: only where it sits differs.

WHAT IT READS, on each state below, every count badge drawn — the bar's
(`shell/tab-badge`), the menu's (`shell/menu-badge`), the drawer's
(`shell/drawer-count`) and a tab's (`segment/count`) — and holds that all of
them share one height, one fill, one ink and one type.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

STATES = ("menu-system-badge", "drawer-navigation", "acq-todo-loaded")
PARTS = ("shell/tab-badge", "shell/menu-badge", "shell/drawer-count", "segment/count")

READ = """(parts)=>parts.flatMap((part) => [...document.querySelectorAll(`[data-part="${part}"]`)]
  .filter((badge) => badge.getBoundingClientRect().height > 0)
  .map((badge) => {
    const style = getComputedStyle(badge);
    return {part, drawing: [Math.round(badge.getBoundingClientRect().height), style.backgroundColor, style.color,
                            style.fontSize, style.fontWeight].join(' ')};
  }))"""


async def main():
    """Reads every count badge of each state, and holds them to one drawing."""
    journal = Journal("R-conformity-k — one count badge")
    seen = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            for badge in await page.evaluate(READ, list(PARTS)):
                seen.setdefault(badge["part"], set()).add(badge["drawing"])
        await context.close()
        await browser.close()
    journal.check("every placement of the badge is drawn somewhere", set(seen) == set(PARTS),
                  f"drawn: {sorted(seen)}")
    drawings = set().union(*seen.values()) if seen else set()
    journal.check("and every one reads one height, fill, ink and type", len(drawings) == 1,
                  f"{ {part: sorted(values) for part, values in seen.items()} }")
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
