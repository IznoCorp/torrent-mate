"""R234 — « Découvrir » is a page of the bottom bar, at its own address.

« Découvrir » LEAVES Acquisition and becomes a
bottom-bar page. Its place in the bar and its address are read off the
navigation table and the address model, never written here; its body is its own
oracle region, `discover/body`, as every page's (RULINGS 18).

1. the table marks the page `inBar`, and the bar carries its button;
2. a tap on that button lands on the page's own address, and the page draws its
   body — the discovery surface, its note included;
3. the address opened cold lands on the same page.

Red before the move: no such page exists.
"""
import asyncio
import pathlib
import re

from common import ACTED, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TABLE = (SOURCE / "app/navigation.ts").read_text(encoding="utf-8")
IN_BAR = [identifier for identifier, flag
          in re.findall(r'\bid: "([^"]+)",.*?\binBar: (true|false)', TABLE, re.S) if flag == "true"]
PAGE = "discover"
# The page's body, by the part it is; `discover/body` is its oracle region.
BODY = '[data-part="surface/body"]'

DRAWN = f"""() => {{
  const body = document.querySelector('#view {BODY}');
  return {{
    page: window.state?.page ?? null,
    where: location.pathname,
    body: !!body,
    note: !!(body && body.querySelector('[data-part="note"]')),
  }};
}}"""


async def main():
    journal = Journal("R234 — « Découvrir » is a bar page at its own address")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        journal.check("the table marks « Découvrir » a page of the bar", PAGE in IN_BAR, str(IN_BAR))
        journal.check("and the address model declares its address", PAGE in PAGE_PATHS, str(PAGE_PATHS))
        answer = await page.evaluate(
            "()=>{try{window.__go('acq-todo-loaded');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-todo-loaded exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        tapped = await page.evaluate(f"""()=>{{const b=document.querySelector('#nav button[data-page="{PAGE}"]');
            if(!b) return false; b.click(); return true;}}""")
        await page.wait_for_timeout(ACTED)
        drawn = await page.evaluate(DRAWN)
        journal.check("the bar carries its button, and a tap lands on its address",
                      tapped and drawn["where"] == PAGE_PATHS.get(PAGE) and drawn["page"] == PAGE,
                      f"tapped {tapped}, {drawn}")
        journal.check("and the page draws its body, the discovery surface",
                      drawn["body"] and drawn["note"], str(drawn))

        cold = await browser.new_context(**PHONE)
        fresh = await cold.new_page()
        fresh.on("pageerror", lambda error: errors.append(str(error)))
        await fresh.goto(PROTOTYPE.rstrip("/") + PAGE_PATHS.get(PAGE, "/discover"), wait_until="load")
        await fresh.evaluate("()=>window.__loadingDone?.()")
        await fresh.wait_for_timeout(SETTLED)
        opened = await fresh.evaluate(DRAWN)
        journal.check("its address opened cold lands on the page",
                      opened["page"] == PAGE and opened["body"], str(opened))
        await cold.close()

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
