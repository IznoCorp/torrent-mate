"""R-conformity-o — every segmented choice is the view switch's drawing.

THE DEFECT THIS ENDS. The add screen drew its kind and its provider choices with
a segmented control of its own (`segmentSmall`), beside the view switch the
lists already drew: two drawings for one need. A choice between a few values in
place is `viewSwitch` at its text size, wherever it is offered.

WHAT IT READS, on the add screen's states with the « by identifier » fold
opened, and in the drawer's appearance choice: every group of pressed buttons
sits in a `view/switch`, and every such button — the kinds, the providers, the
appearances alike — reads one drawing. And, read in the sources: the frame
(`app/`) imports nothing from a feature's variants — a frame drawing a
feature's control is how the drawer came to wear the add screen's.
"""
import asyncio
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

STATES = ("acq-add-empty", "acq-add-results", "acq-identify")
APP = pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "app"
FEATURE_VARIANTS = re.compile(r'from\s+"[^"]*features/[^"]*/variants"')

READ = """()=>{
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="add:"]');
  if (!screen) return null;
  screen.querySelectorAll('details').forEach((fold) => { fold.open = true; });
  const drawing = (button) => {
    const style = getComputedStyle(button);
    return [style.fontSize, style.fontWeight, style.paddingTop, style.paddingLeft, style.borderRadius].join(' ');
  };
  const pressed = [...screen.querySelectorAll('button[aria-pressed]')];
  return {
    groups: pressed.length,
    outside: pressed.filter((button) => !button.closest('[data-part="view/switch"]')).length,
    drawings: [...new Set(pressed.map(drawing))],
  };
}"""


DRAWER = """()=>{
  const drawer = document.querySelector('#drawer[data-open]');
  if (!drawer) return null;
  const pressed = [...drawer.querySelectorAll('button[aria-pressed]')];
  const drawing = (button) => {
    const style = getComputedStyle(button);
    return [style.fontSize, style.fontWeight, style.paddingTop, style.paddingLeft, style.borderRadius].join(' ');
  };
  return {groups: pressed.length,
          outside: pressed.filter((button) => !button.closest('[data-part="view/switch"]')).length,
          drawings: [...new Set(pressed.map(drawing))]};
}"""


async def main():
    """Reads the segmented choices of the add screen's states."""
    journal = Journal("R-conformity-o — one segmented choice")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            # The folds open on the first read; the second reads them open.
            await page.evaluate(READ)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ)
            journal.check(f"{state}: the kinds and the providers are offered", bool(read) and read["groups"] >= 6,
                          f"{read}")
            journal.check(f"{state}: every choice sits in the view switch",
                          bool(read) and read["outside"] == 0, f"{read}")
            journal.check(f"{state}: every choice reads one drawing", bool(read) and len(read["drawings"]) == 1,
                          f"{read}")
        await page.evaluate("(id)=>window.__go(id)", "drawer-navigation")
        await page.wait_for_timeout(SETTLED)
        appearance = await page.evaluate(DRAWER)
        journal.check("the drawer's appearance choice is the view switch, one drawing",
                      bool(appearance) and appearance["outside"] == 0 and len(appearance["drawings"]) == 1,
                      f"{appearance}")
        await context.close()
        await browser.close()
    imports = [path.name for path in sorted(APP.rglob("*.ts*")) if FEATURE_VARIANTS.search(path.read_text(encoding="utf-8"))]
    journal.check("the frame imports nothing from a feature's variants", not imports, f"{imports}")
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
