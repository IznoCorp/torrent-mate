"""R-conformity-c — one switch, whatever it turns on.

THE DEFECT THIS ENDS. The settings panel drew its own switch — a 48 px track
with a child knob — while the quality profile drew the design system's
`toggleSwitch`, 46 px with a drawn knob: two switches for one need.

WHAT IT READS: the settings field's switch (`field/toggle`, on
`settings-field-boolean`, inside the panel) and the quality profile's
(`switch`, on `screen-profile`) have ONE geometry — width, height, radius — and
both draw their knob the same way (no child element).
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, PANEL_IN, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

READ = """(selector)=>{
  const node = document.querySelector(selector);
  if (!node) return null;
  const box = node.getBoundingClientRect();
  const style = getComputedStyle(node);
  return {width: Math.round(box.width), height: Math.round(box.height), radius: style.borderTopLeftRadius,
          children: node.children.length, role: node.getAttribute('role')};
}"""


async def main():
    """Reads both switches and compares them."""
    journal = Journal("R-conformity-c — one switch")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        await page.evaluate("(id)=>window.__go(id)", "screen-profile")
        await page.wait_for_timeout(SETTLED)
        profile = await page.evaluate(READ, '[data-part="screen"][data-open] [data-part="switch"]')
        await page.evaluate("(id)=>window.__go(id)", "settings-field-boolean")
        await page.wait_for_timeout(PANEL_IN)
        field = await page.evaluate(READ, '#sheetin [data-part="field/toggle"]')
        journal.check("both switches are drawn", bool(profile) and bool(field), f"profile {profile}, field {field}")
        if profile and field:
            same = {key: (profile[key], field[key]) for key in ("width", "height", "radius", "children")}
            journal.check("the settings switch is the design system's switch: one geometry, one knob",
                          all(one == other for one, other in same.values()), f"{same}")
            journal.check("both are switches to assistive technology",
                          profile["role"] == field["role"] == "switch", f"{profile['role']}, {field['role']}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
