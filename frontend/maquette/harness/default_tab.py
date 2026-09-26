"""R202 — Acquisition opens on « Suivis », then on the last tab opened.

The operator's rule for the tab Acquisition opens on, when nothing names one:
« Suivis par défaut, puis le dernier onglet ouvert (mémoire locale) ». The first
opening lands on « Suivis »; afterwards, on the tab opened last, kept in the
device's local storage. Storage that is empty, unreadable, or holds a value that
is no tab, is « Suivis ». An address that names its tab always wins.

Each case is a COLD entry at `/acquisition` in a fresh context whose storage is
prepared before the document loads, so what is read is what the boot reads:

1. empty storage → « Suivis »;
2. « À traiter » remembered → « À traiter »;
3. storage that throws on every read → « Suivis »;
4. a value that is no tab → « Suivis »;
5. « À traiter » remembered, `?tab=now` in the address → « En cours »;
6. a tab tapped is remembered: « En cours » tapped, the page opened again cold in
   the same context → « En cours ».
"""
import asyncio
import json

from common import ACTED, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal
from playwright.async_api import async_playwright

ENTRY = PROTOTYPE.rstrip("/") + PAGE_PATHS["acq"]
# The storage key the tab is remembered under.
KEY = "acquisition-tab"
FIRST = "follows"

SELECTED = """() => document.querySelector('[data-acqtab][aria-selected="true"]')?.dataset.acqtab ?? null"""


def prepared(value=None, throwing=False):
    """An init script that sets the storage before the document loads."""
    if throwing:
        return ("Storage.prototype.getItem = function () { throw new Error('storage refused'); };"
                "Storage.prototype.setItem = function () { throw new Error('storage refused'); };")
    if value is None:
        return "try { localStorage.clear(); } catch (error) {}"
    return f"try {{ localStorage.setItem({json.dumps(KEY)}, {json.dumps(value)}); }} catch (error) {{}}"


async def cold(browser, script, address=ENTRY):
    """Opens the address cold in a fresh context, its storage prepared first."""
    context = await browser.new_context(**PHONE)
    if script:
        await context.add_init_script(script)
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.goto(address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.wait_for_timeout(SETTLED)
    return context, page, errors


async def main():
    journal = Journal("R202 — « Suivis », then the last tab opened")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")

        for label, script, address, wanted in (
            ("empty storage opens « Suivis »", prepared(), ENTRY, FIRST),
            ("« À traiter » remembered opens « À traiter »", prepared("todo"), ENTRY, "todo"),
            ("storage that throws opens « Suivis »", prepared(throwing=True), ENTRY, FIRST),
            ("a remembered value that is no tab opens « Suivis »", prepared("nowhere"), ENTRY, FIRST),
            ("an address naming its tab wins over the memory", prepared("todo"), ENTRY + "?tab=now", "now"),
        ):
            context, page, errors = await cold(browser, script, address)
            selected = await page.evaluate(SELECTED)
            journal.check(label, selected == wanted, f"{selected!r} — wanted {wanted!r}")
            journal.check(f"no JS error ({label})", not errors, str(errors))
            await context.close()

        # A TAB TAPPED IS REMEMBERED, and read back by the next cold entry. No
        # init script here: one would run again on the second page and undo
        # the very memory being read — a fresh context's storage is empty.
        context, page, errors = await cold(browser, None)
        await page.evaluate("""()=>document.querySelector('[data-acqtab="now"]')?.click()""")
        await page.wait_for_timeout(ACTED)
        second = await context.new_page()
        await second.goto(ENTRY, wait_until="load")
        await second.evaluate("()=>window.__loadingDone?.()")
        await second.wait_for_timeout(SETTLED)
        selected = await second.evaluate(SELECTED)
        journal.check("a tab tapped is the one the next cold entry opens", selected == "now",
                      f"{selected!r}")
        journal.check("no JS error around the memory", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
