"""R-conformity-p — one primary action: the pick and the save are one button.

THE DEFECT THIS ENDS. The resolution's « Choisir » was a pill of its own — a
full round, a smaller type — beside the interface's primary action button that
the settings' save already is. One need, one component: the pick is
`actionButton` in its primary tone, at its 44 px.

WHAT IT READS: on `acq-resolution-tie`, every candidate's pick; on
`settings-edited`, the save. Each is at least a finger tall, in the primary
ground, and all of them read one drawing — type, weight, corner.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

TOUCH_FLOOR = 44
# state → the primary actions it offers.
ACTIONS = {
    "acq-resolution-tie": '[data-part="screen"][data-open] [data-part="card/pick"]',
    "settings-edited": '#savebar [data-save]',
}

READ = """(selector)=>{
  const probe = document.createElement('span');
  probe.className = 'bg-primary';
  document.body.appendChild(probe);
  const primary = getComputedStyle(probe).backgroundColor;
  probe.remove();
  return [...document.querySelectorAll(selector)].map((action) => {
    const style = getComputedStyle(action);
    return {height: Math.round(action.getBoundingClientRect().height),
            primary: style.backgroundColor === primary,
            drawing: [style.fontSize, style.fontWeight, style.borderRadius].join(' ')};
  });
}"""


async def main():
    """Reads the primary actions of each state and holds them against one another."""
    journal = Journal("R-conformity-p — one primary action")
    drawings = set()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state, selector in ACTIONS.items():
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            actions = await page.evaluate(READ, selector)
            journal.check(f"{state}: the primary action is drawn", bool(actions), selector)
            journal.check(f"{state}: at least {TOUCH_FLOOR} px, in the primary ground",
                          bool(actions) and all(one["height"] >= TOUCH_FLOOR and one["primary"] for one in actions),
                          f"{actions[:2]}")
            drawings.update(one["drawing"] for one in actions)
        await context.close()
        await browser.close()
    journal.check("the pick and the save read one drawing", len(drawings) == 1, f"{sorted(drawings)}")
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
