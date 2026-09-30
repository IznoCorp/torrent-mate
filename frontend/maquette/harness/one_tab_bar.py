"""R-conformity-b — one tab bar: the same height, composition and count on every page.

THE DEFECT THIS ENDS. Acquisition, Médiathèque and Trackers each drew their own
tab bar, at three heights, one with its count in a pill and one with a class of
its own. One need, one component: `ui/tabs.tsx` is Acquisition's bar as it
stood, and the other pages come to it.

WHAT IT READS, on each state below, the page's tab bar (`[role="tablist"]` in
`#view`): every tab is at least a finger tall and all of them are one height;
the bar's own box, a tab's type and a count's drawing are read as one
signature, and every bar's signature is Acquisition's.

THE THREE ARE HELD FROM THE START. Médiathèque's and Trackers' bars already
wear the variants the component draws (components I moved them), so each bar
is held here, not owed; the pages' own markup comes to `Tabs` with their phases.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

TOUCH_FLOOR = 44
# The reference bar first: every other bar is read against it.
REFERENCE = "acq-follows-list"
STATES = (REFERENCE, "lib-grid", "trackers-page")

READ = """()=>{
  const bar = document.querySelector('#view [role="tablist"]');
  if (!bar) return null;
  const pick = (style, names) => Object.fromEntries(names.map((name) => [name, style[name]]));
  const tabs = [...bar.querySelectorAll('[role="tab"]')];
  const count = bar.querySelector('[data-part="segment/count"]');
  const barStyle = getComputedStyle(bar);
  return {
    heights: tabs.map((tab) => Math.round(tab.getBoundingClientRect().height)),
    signature: {
      bar: {height: Math.round(bar.getBoundingClientRect().height),
            ...pick(barStyle, ['paddingTop', 'paddingLeft', 'borderRadius', 'backgroundColor', 'gap'])},
      tab: tabs[0] ? pick(getComputedStyle(tabs[0]), ['fontSize', 'fontWeight', 'borderRadius', 'paddingTop']) : null,
      count: count ? pick(getComputedStyle(count), ['fontSize', 'fontWeight', 'borderRadius', 'backgroundColor', 'color']) : null,
    },
  };
}"""


def agrees(signature: dict, reference: dict) -> bool:
    """Whether a bar's signature is the reference's — a count is compared only where both draw one."""
    if signature["bar"] != reference["bar"] or signature["tab"] != reference["tab"]:
        return False
    return signature["count"] is None or reference["count"] is None or signature["count"] == reference["count"]


async def main():
    """Reads the tab bar of each state and holds it against Acquisition's."""
    journal = Journal("R-conformity-b — one tab bar")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        bars = {}
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            bars[state] = await page.evaluate(READ)
        await context.close()
        await browser.close()
    reference = bars[REFERENCE]
    journal.check(f"{REFERENCE}: the reference bar is drawn", reference is not None, "no tab bar")
    if reference is None:
        journal.summary()
    for state in STATES:
        bar = bars[state]
        held = (bar is not None and min(bar["heights"], default=0) >= TOUCH_FLOOR
                and len(set(bar["heights"])) == 1 and agrees(bar["signature"], reference["signature"]))
        detail = f"{bar}" if state == REFERENCE else f"{bar} against {reference['signature']}"
        journal.check(f"{state}: every tab at least {TOUCH_FLOOR} px, one height, the reference's drawing",
                      held, detail)
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
